import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {pathToFileURL,fileURLToPath} from 'node:url';
import {thinkingFields} from './probe.js';

// Acceptance-only ownership: preserve native boundary dispatch before ending the first generation.
export function endGeneration(agent,onEnd,{disabled=false}={}) {
 const nativeFinish=agent.finishTurn;
 agent.finishTurn=async(turn,signal)=>{
  const decision=await nativeFinish?.(turn,signal);
  if(disabled)return decision;
  onEnd();return {action:'end'};
 };
}
export function acceptanceModel(model) {
 if(model.compat?.thinkingFormat!=='openrouter')return model;
 return {...model,compat:{...model.compat,openRouterRouting:{...model.compat.openRouterRouting,allow_fallbacks:false}}};
}
export function redactEvidence(value) {
 return JSON.parse(JSON.stringify(value,(_key,item)=>typeof item==='string'
  ?item.replace(/\bsk-[A-Za-z0-9_-]+/g,'[redacted]').replace(/\b[a-fA-F0-9]{32}\.[A-Za-z0-9_-]+/g,'[redacted]'):item));
}

async function run(config) {
 const {index,root,directory,agentDir,provider,model:identity,thinking,mode='normal',fixture}=config;
 const ledger={attempts:0,dispatches:0,requests:[],stopDecisions:0};
 const ledgerFile=path.join(directory,'transport.json');
 const save=()=>fs.writeFileSync(ledgerFile,JSON.stringify(ledger,null,2));
 const nativeFetch=globalThis.fetch;let endpoint,noFallback=false;const observations=[];
 globalThis.fetch=async(input,init)=>{
  ledger.attempts++;save();
  const reject=reason=>{ledger.error=reason;save();throw Error(reason);};
  if(ledger.dispatches!==0)return reject('single-dispatch limit');
  const url=new URL(typeof input==='string'||input instanceof URL?input:input.url);
  if(!endpoint||url.origin!==endpoint.origin||!url.pathname.startsWith(endpoint.pathname.replace(/\/$/, '')+'/'))return reject('unexpected transport endpoint');
  if((init?.method??input.method??'GET').toUpperCase()!=='POST')return reject('unknown transport method');
  let payload;try {payload=JSON.parse(init?.body??await input.clone().text());}catch{return reject('unknown transport payload');}
  if(!Array.isArray(payload.messages)||payload.model!==identity||!Number.isInteger(payload.max_tokens)||payload.max_tokens<=0)return reject('unknown transport fields');
  if(mode!=='cap-control'&&payload.max_tokens>2048)return reject('output-token cap exceeded');
  if(noFallback&&payload.provider?.allow_fallbacks!==false)return reject('provider fallback must be disabled');
  ledger.requests.push({url:url.toString(),model:payload.model,max_tokens:payload.max_tokens,nativeThinking:thinkingFields(payload),...(noFallback?{routing:payload.provider}:{})});
  ledger.dispatches++;save();
  const response=await nativeFetch(input,{...init,redirect:'error'});
  ledger.response={status:response.status,modelObserved:false,modelMatches:false};save();
  observations.push(response.clone().text().then(body=>{
   for(const line of body.split('\n')) {
    if(!line.startsWith('data: ')||line==='data: [DONE]')continue;
    let chunk;try {chunk=JSON.parse(line.slice(6));}catch {continue;}
    if(typeof chunk.model==='string') {
     ledger.response.modelObserved=true;
     if(chunk.model===identity)ledger.response.modelMatches=true;
     else ledger.response.modelMismatch=true;
    }
   }
   save();
  }).catch(()=>{ledger.response.observationFailed=true;save();}));
  return response;
 };
 save();
 const sdk=await import(pathToFileURL(index));
 const settings=sdk.SettingsManager.inMemory({packages:[root],retry:{enabled:false,maxRetries:0,provider:{maxRetries:mode==='retry-control'?1:0}},compaction:{enabled:false},cacheWarming:'off',enableInstallTelemetry:false});
 assert.equal(settings.getRetryEnabled(),false);assert.equal(settings.getCompactionSettings().enabled,false);
 assert.equal(settings.getCacheWarmingMode(),'off');assert.equal(settings.getProviderRetrySettings().maxRetries,mode==='retry-control'?1:0);
 const loader=new sdk.DefaultResourceLoader({cwd:directory,agentDir,settingsManager:settings,additionalExtensionPaths:[fixture]});
 await loader.reload();assert.deepEqual(loader.getExtensions().errors,[]);
 const expected=fs.readdirSync(path.join(root,'skills')).filter(name=>fs.existsSync(path.join(root,'skills',name,'SKILL.md'))).sort();
 const skills=loader.getSkills().skills;assert.deepEqual(skills.map(s=>s.name).sort(),expected);
 assert.ok(skills.every(s=>!s.filePath.replaceAll('\\','/').includes('/synced/')));
 const architect=skills.find(s=>s.name==='architect');assert.ok(fs.existsSync(path.resolve(path.dirname(architect.filePath),'../.shared/review-contract.md')));
 const instructions=loader.getAgentsFiles().agentsFiles;
 assert.ok(instructions.some(f=>path.resolve(f.path)===path.resolve(agentDir,'AGENTS.md')));
 assert.ok(instructions.some(f=>path.resolve(f.path)===path.resolve(root,'AGENTS.md')));
 const runtime=await sdk.ModelRuntime.create({authPath:path.join(agentDir,'auth.json'),modelsPath:path.join(agentDir,'models.json'),allowModelNetwork:false,refreshOnCreate:false});
 if(runtime.getError())throw Error('native model configuration unavailable');
 const selected=runtime.getModel(provider,identity);assert.ok(selected,'selected native model unavailable');
 const model=acceptanceModel(selected);
 noFallback=model.compat?.thinkingFormat==='openrouter';
 endpoint=new URL(model.baseUrl);
 const sessionManager=sdk.SessionManager.create(directory,path.join(directory,'sessions'));
 const appendMessage=sessionManager.appendMessage.bind(sessionManager);
 sessionManager.appendMessage=message=>appendMessage(redactEvidence(message));
 const {session}=await sdk.createAgentSession({cwd:directory,agentDir,modelRuntime:runtime,model,...(thinking?{thinkingLevel:thinking}:{}),settingsManager:settings,resourceLoader:loader,sessionManager,tools:['read','bash','edit','write','guard_probe',...(process.platform==='win32'?['powershell']:[])]});
 const errors=[],notices=[];
 session.subscribe(event=>process.stdout.write(JSON.stringify(redactEvidence(event))+'\n'));
 try {
  await session.bindExtensions({onError:e=>errors.push(e),uiContext:{...session.extensionRunner.createContext().ui,notify:m=>notices.push(m)}});
  const status=session.extensionRunner.getCommand('guard-status');assert.ok(status);
  await status.handler('',session.extensionRunner.createCommandContext());
  const health=JSON.parse(notices.at(-1));assert.equal(health.healthy,true);
  endGeneration(session.agent,()=>{ledger.stopDecisions++;save();},{disabled:mode==='stop-control'});
  fs.writeFileSync(path.join(directory,'loaded.json'),JSON.stringify({profile:config.profile,provider,model:identity,thinking:session.thinkingLevel,endpoint:model.baseUrl,skills:skills.map(s=>s.name),instructions:instructions.map(f=>f.path),health,retry:settings.getRetrySettings(),providerRetry:settings.getProviderRetrySettings(),compaction:settings.getCompactionSettings(),cacheWarming:settings.getCacheWarmingMode()},null,2));
  await session.prompt('Call guard_probe exactly once. It runs fixed harmless acceptance cases. Do not call any other tool. No final summary is needed.');
  if(errors.length)throw Error('native extension error');
 } finally {await Promise.all(observations);session.dispose();globalThis.fetch=nativeFetch;}
}
if(process.argv[1]&&path.resolve(process.argv[1])===path.resolve(fileURLToPath(import.meta.url))) {
 try {await run(JSON.parse(fs.readFileSync(process.argv[2],'utf8')));}
 catch(err){console.error('acceptance session failed: '+redactEvidence(err.message));process.exitCode=1;}
}
