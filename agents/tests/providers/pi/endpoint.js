import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {launchBounded} from './live.js';
import {thinkingFields} from './probe.js';
import {acquireImageEngine} from '../../../providers/pi/runtime/image-engine.js';
import {resolveShell} from '../../../providers/pi/permissions/adapter.js';
const agents=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const root=fs.mkdtempSync(path.resolve(agents,'../tmp/pi-endpoint-'));
const copy=path.join(root,'ai/agents'),runtime=path.join(copy,'providers/pi/runtime'),lifecycle=path.join(copy,'lifecycle');
for(const relative of ['providers/pi/runtime/launch.sh','providers/pi/runtime/configure.js','providers/pi/runtime/retry-policy.json','providers/pi/runtime/plugins.js','providers/pi/runtime/image-engine.js','providers/pi/runtime/profiles.json','lifecycle/registry.sh','lifecycle/providers.conf.sh','config.py','permissions/run-guard.sh','permissions/guards/_paths.py']) {
 const target=path.join(copy,relative);fs.mkdirSync(path.dirname(target),{recursive:true});fs.copyFileSync(path.join(agents,relative),target);
}
fs.writeFileSync(path.join(root,'ai/config.local.json'),JSON.stringify({pi:{secret_root:path.join(root,'secrets'),ownership_root:root}}));
fs.copyFileSync(path.join(agents,'package.json'),path.join(copy,'package.json'));
for(const relative of ['AGENTS.md','skills','providers/pi/permissions','providers/pi/plugins'])fs.symlinkSync(path.join(agents,relative),path.join(copy,relative),process.platform==='win32'&&relative!=='AGENTS.md'?'junction':relative==='AGENTS.md'?'file':'dir');
const home=path.join(root,'home'),win=process.platform==='win32';fs.mkdirSync(home);
const packageDir=path.resolve(path.dirname(process.argv[2]),'../..');
const prefixRoot=path.join(home,win?'AppData/Roaming/pi-sot':'.local/share/pi-sot');
const target=path.join(prefixRoot,'node_modules/@earendil-works/pi-coding-agent');
fs.mkdirSync(path.dirname(target),{recursive:true});fs.symlinkSync(packageDir,target,win?'junction':'dir');
// The pinned runtime resolves @earendil-works/pi-ai from its install prefix, so mirror whichever
// layout the installed release uses (nested with a shrinkwrap, hoisted without one).
const aiDir=[path.join(packageDir,'node_modules/@earendil-works/pi-ai'),path.join(path.dirname(packageDir),'pi-ai')].find(candidate=>fs.existsSync(candidate));
assert.ok(aiDir,'installed Pi runtime must carry @earendil-works/pi-ai');
const {ModelRuntime}=await import(pathToFileURL(path.join(packageDir,'dist/core/model-runtime.js')));
const {getSupportedThinkingLevels}=await import(pathToFileURL(path.join(aiDir,'dist/index.js')));
fs.symlinkSync(fs.realpathSync(aiDir),path.join(prefixRoot,'node_modules/@earendil-works/pi-ai'),win?'junction':'dir');
if(!win){const node=path.join(home,'.nvm/versions/node/v24.8.0/bin/node');fs.mkdirSync(path.dirname(node),{recursive:true});fs.symlinkSync(process.execPath,node);}
const baseAgent=path.join(home,'.pi/agent');let agent=baseAgent;fs.mkdirSync(agent,{recursive:true});
fs.symlinkSync(fs.realpathSync(path.join(agents,'AGENTS.md')),path.join(agent,'AGENTS.md'));
fs.writeFileSync(path.join(agent,'settings.json'),JSON.stringify({packages:[agents],retry:{enabled:false,provider:{maxRetries:0}},compaction:{enabled:false},cacheWarming:'off',enableInstallTelemetry:false}));
fs.mkdirSync(path.join(root,'secrets'));for(const name of ['primary','alternate'])fs.writeFileSync(path.join(root,'secrets',name+'.key'),'synthetic-endpoint-key');
const fixture=path.join(root,'selection.mjs');fs.writeFileSync(fixture,"export default pi=>{pi.on('agent_start',async()=>{if(process.env.PI_TEST_BARRIER)await fetch(process.env.PI_TEST_BARRIER);});pi.on('before_provider_request',(event,ctx)=>({...event.payload,max_tokens:2048,pi_thinking_level:ctx.thinkingLevel}));}");
const requests=[];
let expectedKeys;
function responseBody(payload,url) {
 if(new URL(url,'http://fixture.invalid').pathname.endsWith('/messages')) {
  const events=[
   {type:'message_start',message:{id:'selection',type:'message',role:'assistant',model:payload.model,content:[],stop_reason:null,stop_sequence:null,usage:{input_tokens:1,output_tokens:0}}},
   {type:'content_block_start',index:0,content_block:{type:'text',text:''}},
   {type:'content_block_delta',index:0,delta:{type:'text_delta',text:'ok'}},
   {type:'content_block_stop',index:0},
   {type:'message_delta',delta:{stop_reason:'end_turn',stop_sequence:null},usage:{output_tokens:1}},
   {type:'message_stop'}
  ];
  return events.map(event=>'event: '+event.type+'\ndata: '+JSON.stringify(event)+'\n\n').join('');
 }
 const chunk=(delta,finish_reason)=>'data: '+JSON.stringify({id:'selection',object:'chat.completion.chunk',created:0,model:payload.model,choices:[{index:0,delta,finish_reason}]})+'\n\n';
 return chunk({role:'assistant',content:'ok'},null)+chunk({},'stop')+'data: [DONE]\n\n';
}
const makeServer=async id=>{
 const server=http.createServer(async(req,res)=>{
  let body='';for await(const part of req)body+=part;const payload=JSON.parse(body);requests.push({id,model:payload.model,max_tokens:payload.max_tokens,level:payload.pi_thinking_level,nativeThinking:thinkingFields(payload),...(expectedKeys?{authMatches:req.headers.authorization==='Bearer '+expectedKeys[id]}:{})});
  res.writeHead(200,{'Content-Type':'text/event-stream'});
  res.end(responseBody(payload,req.url));
 });await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));return server;
};
const first=await makeServer('first'),second=await makeServer('second');
const profileFile=path.join(runtime,'profiles.json');
let profiles={
 first:{provider:'deepseek',model:'deepseek-flash',credential:'secrets/primary.key',endpoint:`http://127.0.0.1:${first.address().port}`,api:'openai-completions',thinking:'max'},
 second:{provider:'deepseek',model:'deepseek-v4-pro',credential:'secrets/alternate.key',endpoint:`http://127.0.0.1:${second.address().port}`,api:'openai-completions',thinking:'high'}
};
const production=JSON.parse(fs.readFileSync(process.argv[3]??path.join(agents,'tests/providers/pi/profiles.json'),'utf8'));
assert.ok(production.profiles[production.active],'configured active profile must exist');
const selectedProfiles={},definitions={};
for(const [id,entry] of Object.entries(production.profiles)) {
 if(entry.compatibleModel)definitions[id]={...entry.compatibleModel,api:entry.api,baseUrl:entry.endpoint};
 else {
  const catalog=JSON.parse(fs.readFileSync(path.join(aiDir,'dist/providers/data',entry.provider+'.json'),'utf8'));
  definitions[id]=Object.values(catalog).flatMap(group=>Object.values(group)).find(value=>value.id===entry.model);
 }
 assert.ok(definitions[id],'configured model must have explicit metadata or a pinned native definition');
 assert.ok(new URL(entry.endpoint||definitions[id].baseUrl));
 selectedProfiles[id]={...entry,credential:'secrets/'+id+'.key',endpoint:`http://127.0.0.1:${first.address().port}`};
 fs.writeFileSync(path.join(root,selectedProfiles[id].credential),'synthetic-profile-key');
}
const writeProfiles=active=>fs.writeFileSync(profileFile,JSON.stringify({active,profiles}));
let launched=0;
const launch=(...selector)=>launchWithEnv({},...selector);
const launchWithEnv=async({expectBudgetRefusal=false,...extraEnv},...selector)=>{
 const id=selector[0]==='--profile'?selector[1]:JSON.parse(fs.readFileSync(profileFile)).active;
 const selectedAgent=path.join(baseAgent,'profiles',id);
 const args=['-c',win?'export HOME="$(cygpath -u "$PI_TEST_HOME")"; exec bash "$PI_TEST_LAUNCH" "$@"':'exec bash "$PI_TEST_LAUNCH" "$@"','endpoint-test',...selector,'-e',fixture,'-p','respond ok'];
 const streamFile=path.join(root,'launch-'+(++launched)+'.log');
 const result=await launchBounded(resolveShell(),args,{cwd:root,env:{...process.env,HOME:home,PI_OFFLINE:'1',PI_TELEMETRY:'0',PI_TEST_HOME:home,PI_TEST_LAUNCH:path.join(runtime,'launch.sh').replaceAll('\\','/'),...extraEnv},timeoutMs:30000,streamFile});
 if(expectBudgetRefusal){
  const output=fs.readFileSync(streamFile,'utf8');
  assert.equal(result.timedOut,false,output);
  assert.equal(result.code,1,output);
  assert.match(output,/image-budget: request refused/);
  return;
 }
 if(result.code!==0||result.timedOut)throw Error('native endpoint launch refused: '+fs.readFileSync(streamFile,'utf8'));
 agent=selectedAgent;
};

try {
 writeProfiles('first');
 await launch();
 writeProfiles('second');
 await launch();
 assert.deepEqual(requests,[
  {id:'first',model:'deepseek-flash',max_tokens:2048,level:'max',nativeThinking:{thinking:{type:'enabled'},reasoning_effort:'max'}},
  {id:'second',model:'deepseek-v4-pro',max_tokens:2048,level:'high',nativeThinking:{thinking:{type:'enabled'},reasoning_effort:'high'}}],'profile thinking must reach the native request fields');
 assert.ok(JSON.parse(fs.readFileSync(path.join(agent,'auth.json'))).deepseek.key.includes('alternate.key'));
 profiles=selectedProfiles;
 writeProfiles(production.active);
 const policyBefore=fs.readFileSync(profileFile,'utf8');
 const ids=[production.active,...Object.keys(profiles).filter(id=>id!==production.active),production.active];
 for(const [index,id] of ids.entries()) {
  await launch(...(index===ids.length-1?[]:['--profile',id]));
  assert.equal(fs.readFileSync(profileFile,'utf8'),policyBefore,'CLI selection must not rewrite the profile SOT');
  const sent=requests.at(-1),selected=production.profiles[id];
  assert.equal(sent.id,'first');assert.equal(sent.model,selected.model);
  assert.equal(sent.max_tokens,2048);
  if(selected.thinking)assert.equal(sent.level,selected.thinking);
  const native=await ModelRuntime.create({authPath:path.join(agent,'auth.json'),modelsPath:path.join(agent,'models.json'),allowModelNetwork:false,refreshOnCreate:false});
  assert.equal(native.getError(),undefined);
  const model=native.getModel(selected.provider,selected.model);
  assert.equal(model.api,definitions[id].api);
  assert.equal(model.baseUrl,profiles[id].endpoint);
  assert.deepEqual(model.thinkingLevelMap,definitions[id].thinkingLevelMap);
  assert.ok(getSupportedThinkingLevels(model).includes(sent.level));
  let reference;
  const response=await native.completeSimple(model,{messages:[{role:'user',content:'synthetic reference',timestamp:0}]},{reasoning:selected.thinking||sent.level,maxRetries:0,fetch:async(input,init)=>{
   reference=JSON.parse(init.body);
   const url=typeof input==='string'||input instanceof URL?String(input):input.url;
   return new Response(responseBody(reference,url),{headers:{'content-type':'text/event-stream'}});
  }});
  assert.equal(response.stopReason,'stop',response.errorMessage);
  assert.deepEqual(sent.nativeThinking,thinkingFields(reference),'outgoing effort must match native serialization of the selected config');
  const auth=JSON.parse(fs.readFileSync(path.join(agent,'auth.json')));
  assert.deepEqual(Object.keys(auth),[selected.provider],'provider switch must remove the previous owned auth');
  assert.ok(auth[selected.provider].key.includes(id+'.key'),'selected credential must follow the profile');
  assert.deepEqual(Object.keys(JSON.parse(fs.readFileSync(path.join(agent,'models.json'))).providers),[selected.provider],'provider switch must remove the previous owned model');
 }
 const count=requests.length;
 const protectedBefore=Object.fromEntries(['auth.json','models.json','agents-sot-state.json'].map(name=>[name,fs.readFileSync(path.join(agent,name),'utf8')]));
 profiles[production.active]={...profiles[production.active],thinking:'invalid'};writeProfiles(production.active);
 await assert.rejects(launch);assert.equal(requests.length,count);
 assert.deepEqual(Object.fromEntries(Object.keys(protectedBefore).map(name=>[name,fs.readFileSync(path.join(agent,name),'utf8')])),protectedBefore);
 fs.writeFileSync(profileFile,policyBefore);
 const before=fs.readFileSync(path.join(agent,'auth.json'),'utf8');
 let missing='unconfigured-profile';while(Object.hasOwn(profiles,missing))missing+='-missing';
 await assert.rejects(()=>launch('--profile',missing));assert.equal(requests.length,count);assert.equal(fs.readFileSync(path.join(agent,'auth.json'),'utf8'),before);
 assert.equal(fs.readFileSync(profileFile,'utf8'),policyBefore);
 expectedKeys={first:'synthetic-concurrent-a',second:'synthetic-concurrent-b'};
 fs.writeFileSync(path.join(root,'secrets/primary.key'),expectedKeys.first);
 fs.writeFileSync(path.join(root,'secrets/alternate.key'),expectedKeys.second);
 profiles={first:{provider:'deepseek',model:'deepseek-flash',credential:'secrets/primary.key',endpoint:`http://127.0.0.1:${first.address().port}`,thinking:'high'},second:{provider:'deepseek',model:'deepseek-flash',credential:'secrets/alternate.key',endpoint:`http://127.0.0.1:${second.address().port}`,thinking:'high'}};
 writeProfiles('first');
 let ready,release;const loaded=new Promise(resolve=>ready=resolve);
 const barrier=http.createServer((_req,res)=>{release=()=>res.end('go');ready();});
 await new Promise(resolve=>barrier.listen(0,'127.0.0.1',resolve));
 const start=requests.length;
 const runningA=launchWithEnv({PI_TEST_BARRIER:`http://127.0.0.1:${barrier.address().port}`},'--profile','first');
 try {
  await Promise.race([loaded,runningA.then(()=>{throw Error('A ended before reaching its barrier');})]);
  await launch('--profile','second');release();await runningA;
 } finally {release?.();await runningA.catch(()=>{});barrier.closeAllConnections();await new Promise(resolve=>barrier.close(resolve));}
 assert.deepEqual(requests.slice(start).map(r=>[r.id,r.authMatches]),[['second',true],['first',true]],'two live CLI processes must retain independent key/endpoint pairs');
 const {SessionManager}=await import(pathToFileURL(path.join(packageDir,'dist/core/session-manager.js')));
 const savedAgent=process.env.PI_CODING_AGENT_DIR;process.env.PI_CODING_AGENT_DIR=path.join(baseAgent,'profiles/first');
 let history;
 try {history=await SessionManager.list(root);assert.ok(history.length);assert.equal((await SessionManager.list(root,path.join(baseAgent,'sessions'))).length,0);}
 finally {if(savedAgent===undefined)delete process.env.PI_CODING_AGENT_DIR;else process.env.PI_CODING_AGENT_DIR=savedAgent;}
 await launch('--profile','second','--session',history[0].path);
 assert.equal(requests.at(-1).id,'second');assert.equal(requests.at(-1).authMatches,true);
 const beforeBudget=requests.length;
 profiles.first.plugins={'image-budget':{maxRequestBytes:64,maxImages:8}};
 writeProfiles('first');
 const firstAgent=path.join(baseAgent,'profiles/first');
 const managedFiles=['auth.json','models.json','agents-sot-state.json','settings.json'];
 const projected=()=>managedFiles.map(name=>{
  const file=path.join(firstAgent,name);
  return fs.existsSync(file)?fs.readFileSync(file,'utf8'):null;
 });
 const existingProjection=projected();
 for (const args of [['--no-extensions'],['-ne'],['-e','npm:fixture-plugin'],['--extension','git:github.com/fixture/plugin']]) {
  await assert.rejects(launch('--profile','first',...args),/requires (?:its permission extension|an existing explicit local extension path)/);
  assert.deepEqual(projected(),existingProjection,'forbidden flags must refuse before projection');
  assert.equal(requests.length,beforeBudget,'forbidden flags must refuse before dispatch');
 }
 await assert.rejects(launch('--profile','first'),/run make install PROVIDER=pi/);
 assert.equal(requests.length,beforeBudget,'a missing checkout must refuse locally');
 await acquireImageEngine(baseAgent,root,process.argv[2]);
 await launchWithEnv({expectBudgetRefusal:true},'--profile','first');
 assert.equal(requests.length,beforeBudget,'the selected profile must load the budget and abort before dispatch');
 await launch('--profile','second');
 assert.equal(requests.length,beforeBudget+1,'an unrelated profile must retain normal dispatch');
 delete profiles.first.plugins;
 writeProfiles('first');
 await launch('--profile','first');
 assert.equal(requests.length,beforeBudget+2,'disabling plugin in config must take effect on the next launch');

 console.log(JSON.stringify({platform:process.platform,requests,invalidProfileRefused:true,concurrentProcesses:2,resumeUsesSelectedProfile:true,keysPreserved:fs.existsSync(path.join(root,'secrets/primary.key'))&&fs.existsSync(path.join(root,'secrets/alternate.key'))}));
}finally {first.closeAllConnections();second.closeAllConnections();await Promise.all([new Promise(r=>first.close(r)),new Promise(r=>second.close(r))]);fs.rmSync(root,{recursive:true,force:true});}
