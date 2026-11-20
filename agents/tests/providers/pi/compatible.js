import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {configure} from '../../../providers/pi/runtime/configure.js';
import {spawnSync} from 'node:child_process';

const cli=path.resolve(process.argv[2]);
const packageDir=path.resolve(path.dirname(cli),'../..');
const expected=/^PI_PACKAGE='[^']*@([^']+)'/m.exec(fs.readFileSync(new URL('../../../lifecycle/providers.conf.sh',import.meta.url),'utf8'))[1];
assert.equal(JSON.parse(fs.readFileSync(path.join(packageDir,'package.json'))).version,expected);
const require=createRequire(path.join(packageDir,'package.json'));
const aiDir=require.resolve.paths('@earendil-works/pi-ai').map(base=>path.join(base,'@earendil-works/pi-ai')).find(candidate=>fs.existsSync(path.join(candidate,'package.json')));
assert.ok(aiDir);
const {ModelRuntime}=await import(pathToFileURL(path.join(packageDir,'dist/core/model-runtime.js')));
const {getSupportedThinkingLevels}=await import(pathToFileURL(path.join(aiDir,'dist/index.js')));
const scratch=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../../../tmp');
const root=fs.mkdtempSync(path.join(scratch,'pi-compatible-'));
const dir=path.join(root,'agent');
const definition={name:'Synthetic Hy4',reasoning:true,input:['text','image'],contextWindow:1000000,maxTokens:64000,
 thinkingLevelMap:{off:'no_think',minimal:null,low:null,medium:null,high:'high',xhigh:null,max:null},
 compat:{supportsReasoningEffort:true,thinkingFormat:'openai',maxTokensField:'max_tokens'}};
const profile={provider:'tencent-tokenhub',model:'hy4',credential:'secrets/synthetic.key',endpoint:'https://tokenhub-intl.tencentcloudmaas.com/v1',api:'openai-completions',thinking:'high',compatibleModel:definition};
const profiles=entry=>({active:'selected',profiles:{selected:entry}});
const options={op:'install',root,dir,profiles:profiles(profile),cli,expected};
const read=name=>JSON.parse(fs.readFileSync(path.join(dir,name),'utf8'));
const snapshot=()=>Object.fromEntries(fs.readdirSync(dir).map(name=>[name,fs.readFileSync(path.join(dir,name),'utf8')]));
const nativeFetch=globalThis.fetch;
globalThis.fetch=async()=>{throw Error('compatible acceptance forbids network');};
let refusals=0;

try {
 fs.mkdirSync(path.join(root,'secrets'));
 fs.writeFileSync(path.join(root,'secrets/synthetic.key'),'synthetic-compatible-key');
 await configure({...options,op:'validate'});
 assert.equal(fs.existsSync(dir),false,'validation must not create native state');
 const bad=[
  {...profile,compatibleModel:null},
  {...profile,compatibleModel:[]},
  {...profile,compatibleModel:{...definition,headers:{Authorization:'synthetic'}}},
  {...profile,compatibleModel:{...definition,apiKey:'synthetic'}},
  {...profile,compatibleModel:{...definition,maxTokens:'64000'}},
  {...profile,compatibleModel:{...definition,contextWindow:0}},
  {...profile,compatibleModel:{...definition,reasoning:'yes'}},
  {...profile,compatibleModel:{...definition,thinkingLevelMap:{high:42}}},
  {...profile,compatibleModel:{...definition,thinkingLevelMap:{high:'high',turbo:'high'}}},
  {...profile,compatibleModel:{...definition,compat:{supportsReasoningEffort:'yes'}}},
  {...profile,compatibleModel:{...definition,compat:{supportsReasoningEfforts:true}}},
  {...profile,endpoint:''},
  {...profile,api:''},
  {...profile,thinking:'max'},
  {...profile,thinking:'low'},
  {...profile,provider:'deepseek'}
 ];
 for(const entry of bad) {
  await assert.rejects(configure({...options,op:'validate',profiles:profiles(entry)}));
  assert.equal(fs.existsSync(dir),false,'invalid metadata must not create state');refusals++;
 }
 const {compatibleModel,...implicit}=profile;
 await assert.rejects(configure({...options,op:'validate',profiles:profiles(implicit)}),/unsupported native provider catalog/);
 fs.mkdirSync(dir);
 const foreign={baseUrl:'https://foreign.example.invalid/v1',api:'openai-completions',models:[{id:'foreign'}]};
 fs.writeFileSync(path.join(dir,'models.json'),JSON.stringify({providers:{foreign}}));
 await configure(options);
 assert.equal(read('models.json').providers['tencent-tokenhub'].authHeader,true);
 assert.equal(read('models.json').providers['tencent-tokenhub'].apiKey,undefined);
 const before=snapshot();
 await assert.rejects(configure({...options,profiles:profiles({...profile,thinking:'max'})}));
 assert.deepEqual(snapshot(),before,'unsupported effort must preserve all projected files');
 const modes=[];let retainedRuntime,retainedModel;
 for(const thinking of ['high','off']) {
  await configure({...options,profiles:profiles({...profile,thinking})});
  const runtime=await ModelRuntime.create({authPath:path.join(dir,'auth.json'),modelsPath:path.join(dir,'models.json'),allowModelNetwork:false});
  assert.equal(runtime.getError(),undefined);
  const model=runtime.getModel(profile.provider,profile.model);
  retainedRuntime=runtime;retainedModel=model;
  assert.deepEqual(getSupportedThinkingLevels(model),['off','high']);
  const requests=[];
  const fetch=async(input,init)=>{
   const url=typeof input==='string'||input instanceof URL?String(input):input.url;
   assert.equal(url,profile.endpoint+'/chat/completions');
   const payload=JSON.parse(init.body);requests.push(payload);
   assert.equal(payload.reasoning_effort,thinking==='off'?'no_think':'high');
   assert.equal(payload.max_tokens,100);
   const chunk=(delta,finish_reason=null)=>'data: '+JSON.stringify({id:'compatible-test',object:'chat.completion.chunk',created:0,model:payload.model,choices:[{index:0,delta,finish_reason}]})+'\n\n';
   const body=requests.length===1
    ?chunk({role:'assistant',reasoning_content:'synthetic reasoning'})+chunk({tool_calls:[{index:0,id:'inspect-1',type:'function',function:{name:'inspect_fixture',arguments:'{}'}}]})+chunk({},'tool_calls')
    :chunk({role:'assistant',content:'done'})+chunk({},'stop');
   const usage='data: '+JSON.stringify({choices:[],usage:{prompt_tokens:10,completion_tokens:5,total_tokens:15}})+'\n\n';
   return new Response(body+usage+'data: [DONE]\n\n',{headers:{'content-type':'text/event-stream'}});
  };
  const image='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC';
  const context={messages:[{role:'user',timestamp:0,content:[{type:'text',text:'synthetic prompt'},{type:'image',data:image,mimeType:'image/png'}]}],tools:[{name:'inspect_fixture',description:'Synthetic tool',parameters:{type:'object',properties:{}}}]};
  const transport={reasoning:thinking,maxTokens:100,maxRetries:0,fetch};
  const first=await runtime.completeSimple(model,context,transport);
  assert.equal(first.stopReason,'toolUse',first.errorMessage);
  assert.equal(requests[0].messages[0].content.find(part=>part.type==='image_url').image_url.url,'data:image/png;base64,'+image);
  const result={role:'toolResult',toolCallId:'inspect-1',toolName:'inspect_fixture',content:[{type:'text',text:'synthetic result'}],isError:false,timestamp:1};
  const second=await runtime.completeSimple(model,{...context,messages:[...context.messages,first,result]},transport);
  assert.equal(second.stopReason,'stop',second.errorMessage);
  assert.equal(requests[1].messages.find(message=>message.role==='assistant').reasoning_content,'synthetic reasoning');
  assert.equal(requests[1].messages.at(-1).tool_call_id,'inspect-1');
  assert.equal(second.usage.input,10);assert.equal(second.usage.output,5);
  modes.push({thinking,effort:requests[0].reasoning_effort,requests:requests.length,reasoningReplay:true,imageInput:true});
 }
 await configure({...options,profiles:profiles({...profile,model:'synthetic-second'})});
 assert.deepEqual(read('models.json').providers['tencent-tokenhub'].models.map(model=>model.id),['synthetic-second']);
 assert.ok((await retainedRuntime.getAuth(retainedModel))?.auth?.apiKey,'retained runtime must initially resolve synthetic provider auth');
 await configure({...options,profiles:profiles({provider:'deepseek',model:'deepseek-flash',credential:profile.credential,thinking:'max'})});
 assert.equal(read('models.json').providers['tencent-tokenhub'],undefined);
 assert.deepEqual(read('models.json').providers.foreign,foreign);
 assert.equal(Boolean(await retainedRuntime.getAuth(retainedModel)),false,'shared projection switching can remove auth from an already loaded runtime');
 await configure({...options,op:'uninstall'});
 assert.deepEqual(read('models.json').providers,{foreign});
 assert.ok(fs.existsSync(path.join(root,profile.credential)));
 const scoped=path.join(root,'scoped');
 fs.writeFileSync(path.join(root,'secrets/second.key'),'synthetic-second-key');
 const connections={alpha:profile,beta:{provider:'deepseek',model:'deepseek-flash',credential:profile.credential},gamma:{...profile,credential:'secrets/second.key',endpoint:'http://127.0.0.1:43211/v1'}};
 const scopedProfiles={active:'alpha',profiles:connections},retained=[];
 for(const profileId of Object.keys(connections)) {
  const selected=await configure({...options,dir:scoped,profiles:scopedProfiles,profileId,profileScope:true});
  const runtime=await ModelRuntime.create({authPath:path.join(selected.agentDir,'auth.json'),modelsPath:path.join(selected.agentDir,'models.json'),allowModelNetwork:false,refreshOnCreate:false});
  const entry=connections[profileId],model=runtime.getModel(entry.provider,entry.model);
  assert.ok(model);retained.push({profileId,runtime,model,agentDir:selected.agentDir});
 }
 for(const {profileId,runtime,model} of [...retained,retained[0]]) {
  const entry=connections[profileId],key=profileId==='gamma'?'synthetic-second-key':'synthetic-compatible-key';
  assert.ok((await runtime.getAuth(model))?.auth.apiKey===key,'retained runtime must resolve its own synthetic credential');
  let calls=0;
  const response=await runtime.completeSimple(model,{messages:[{role:'user',content:'synthetic isolation',timestamp:0}]},{maxTokens:100,maxRetries:0,fetch:async(input,init)=>{
   calls++;const url=typeof input==='string'||input instanceof URL?String(input):input.url;
   assert.equal(url,model.baseUrl.replace(/\/$/,'')+'/chat/completions');
   assert.ok(new Headers(init.headers).get('authorization')==='Bearer '+key,'request must retain its synthetic credential');
   const chunk={id:'isolated',object:'chat.completion.chunk',created:0,model:entry.model,choices:[{index:0,delta:{role:'assistant',content:'ok'},finish_reason:'stop'}]};
   return new Response('data: '+JSON.stringify(chunk)+'\n\ndata: [DONE]\n\n',{headers:{'content-type':'text/event-stream'}});
  }});
  assert.equal(response.stopReason,'stop',response.errorMessage);assert.equal(calls,1);
 }
 for(const {agentDir} of retained.slice(0,2)) {
  const check=spawnSync(process.execPath,[fileURLToPath(new URL('./native.js',import.meta.url)),path.join(packageDir,'dist/index.js'),path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..'),agentDir],{env:{...process.env,PI_CODING_AGENT_DIR:agentDir,PI_OFFLINE:'1',PI_TELEMETRY:'0'},encoding:'utf8',timeout:30000});
  assert.equal(check.status,0,check.stdout+check.stderr);
 }
 await configure({...options,dir:scoped,op:'uninstall',profileScope:true});
 console.log(JSON.stringify({platform:process.platform,version:expected,refusals,modes,ownedCleanup:true,retainedRuntimeAuthRemoved:true,isolatedRetainedRuntimes:3,isolatedRequests:4,guardedProfileLoaders:2,networkRequests:0}));
} finally {
 globalThis.fetch=nativeFetch;
 fs.rmSync(root,{recursive:true,force:true});
}
