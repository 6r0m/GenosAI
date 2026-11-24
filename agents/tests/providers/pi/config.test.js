import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {spawn,spawnSync} from 'node:child_process';
import {resolveShell} from '../../../providers/pi/permissions/adapter.js';
import {configure} from '../../../providers/pi/runtime/configure.js';
import {pluginLaunch,pluginOptions,selectPlugins} from '../../../providers/pi/runtime/plugins.js';
const scratch=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../../../tmp');
const one=(provider='deepseek',model='a',credential='secrets/a.key')=>({active:'first',profiles:{first:{provider,model,credential}}});
function fixture(t) {
 const root=fs.mkdtempSync(path.join(scratch,'pi-profile Юникод-'));
 fs.mkdirSync(path.join(root,'secrets'));for(const id of ['a','b'])fs.writeFileSync(path.join(root,'secrets',id+'.key'),'synthetic');
 const dir=path.join(root,'agent');fs.mkdirSync(dir);
 const opts={op:'install',root,dir,profiles:one()};
 t.after(()=>fs.rmSync(root,{recursive:true,force:true}));return opts;
}
const read=(o,file)=>JSON.parse(fs.readFileSync(path.join(o.dir,file),'utf8'));
test('Pi validates global and selected-profile plugins before projecting native state',async t=>{
 const o=fixture(t),profiles=one();
 profiles.plugins={'image-budget':{maxRequestBytes:100000,maxImages:20}};
 profiles.profiles.first.plugins={'image-budget':{maxImages:8}};
 profiles.profiles.second={provider:'deepseek',model:'b',credential:'secrets/b.key'};
 assert.equal((await configure({...o,profiles,op:'validate'})).plugins['image-budget'].maxImages,8);
 assert.equal((await configure({...o,profiles,op:'validate',profileId:'second'})).plugins['image-budget'].maxImages,20);
 await configure({...o,op:'validate',setup:true,profiles:{active:null,profiles:{},plugins:profiles.plugins}});
 profiles.profiles.second.plugins={'image-budget':{maxRequestBytes:0}};
 await assert.rejects(configure({...o,profiles}),/maxRequestBytes/);
 assert.deepEqual(fs.readdirSync(o.dir),[]);
});
test('managed plugin selection switches reviewed entrypoints without lifecycle changes',t=>{
 const o=fixture(t);
 const definition=name=>{
  const entrypoint=path.join(o.root,name+'.js');
  fs.writeFileSync(entrypoint,'export default function() {}\n');
  return {entrypoint,validateOptions(options){assert.ok(Number.isInteger(options.limit));},
   validateSelection(options){assert.ok(options.limit>0);},validateModel(model){assert.equal(model.id,'fixture');}};
 };
 const definitions={primary:definition('primary'),alternate:definition('alternate')};
 const model={id:'fixture',provider:'synthetic',api:'openai-completions',baseUrl:'https://example.invalid/v1/'};
 const select=id=>pluginLaunch(selectPlugins({},pluginOptions({[id]:{limit:16}},definitions),definitions),model,'profile',definitions);
 for(const id of Object.keys(definitions)){
  const launch=select(id);
  assert.deepEqual(launch.entries,[definitions[id].entrypoint]);
  assert.deepEqual(JSON.parse(launch.options),{route:{...model,baseUrl:'https://example.invalid/v1'},plugins:{[id]:{limit:16}},profile:'profile'});
 }
});
function snapshotTree(dir) {
 const output={};
 for(const name of fs.readdirSync(dir).sort()){const file=path.join(dir,name),info=fs.lstatSync(file);output[name]=info.isSymbolicLink()?{link:fs.readlinkSync(file)}:info.isDirectory()?snapshotTree(file):fs.readFileSync(file,'utf8');}
 return output;
}
function settingsStub(pkg) {
 const file=path.join(pkg,'dist/core/settings-manager.js');fs.mkdirSync(path.dirname(file),{recursive:true});
 fs.writeFileSync(file,`import fs from 'node:fs';import path from 'node:path';
 export class FileSettingsStorage {
  constructor(cwd,dir){this.file=path.join(dir,'settings.json');}
  withLock(scope,fn){const next=fn(fs.existsSync(this.file)?fs.readFileSync(this.file,'utf8'):undefined);if(next!==undefined)fs.writeFileSync(this.file,next);}
 }`);
}

function scopedFixture(t) {
 const o=fixture(t),prefix=path.join(o.root,'runtime'),pkg=path.join(prefix,'node_modules/@earendil-works/pi-coding-agent');
 const cli=path.join(pkg,'dist/bundle/cli.js');fs.mkdirSync(path.dirname(cli),{recursive:true});
 settingsStub(pkg);
 fs.writeFileSync(cli,"if(process.env.PI_TEST_LOCAL_INSTALL_FAIL || (process.argv[2]==='remove' && process.env.PI_TEST_LOCAL_REMOVE_FAIL))process.exit(7);const fs=require('fs'),path=require('path'),dir=process.env.PI_CODING_AGENT_DIR,file=path.join(dir,'settings.json'),data=fs.existsSync(file)?JSON.parse(fs.readFileSync(file)):{};data.packages=(data.packages??[]).filter(x=>x!==process.argv[3]);if(process.argv[2]==='install')data.packages.push(process.argv[3]);fs.writeFileSync(file,JSON.stringify(data));");
 const catalog=path.join(prefix,'node_modules/@earendil-works/pi-ai/dist/providers/data');fs.mkdirSync(catalog,{recursive:true});
 for(const provider of ['deepseek','other'])fs.writeFileSync(path.join(catalog,provider+'.json'),JSON.stringify({models:{a:{id:'a',api:'openai-completions'},b:{id:'b',api:'openai-completions'},flash:{id:'deepseek-flash',api:'openai-completions',contextWindow:1048577}}}));
 return {...o,cli,profileScope:true};
}
const retryPolicy={enabled:true,maxRetries:5,baseDelayMs:60000,maxAgentDelayMs:900000};
test('DeepSeek Flash compaction manages only its calculated reserve',async t=>{
 const o=scopedFixture(t),{agentDir:dir}=await configure(o);
 const key='deepseek/deepseek-flash',file=path.join(dir,'settings.json');
 const settings=read({dir},'settings.json');
 settings.compaction={reserveTokens:17000,keepRecentTokens:18000,modelOverrides:{
  [key]:{keepRecentTokens:19000},'other/deepseek-flash':{reserveTokens:24000},
 }};
 fs.writeFileSync(file,JSON.stringify(settings));
 const initial=fs.readFileSync(file,'utf8');
 await configure({...o,profiles:one('other','deepseek-flash')});
 assert.equal(fs.readFileSync(file,'utf8'),initial);
 const flash={...o,profiles:one('deepseek','deepseek-flash')};
 await configure(flash);
 settings.compaction.modelOverrides[key].reserveTokens=314574;
 assert.deepEqual(read({dir},'settings.json'),settings);
 assert.equal(read({dir},'agents-sot-state.json').flashCompactionReserve,314574);
 const applied=fs.readFileSync(file,'utf8');
 await configure(flash);
 assert.equal(fs.readFileSync(file,'utf8'),applied);
 settings.compaction.modelOverrides[key].reserveTokens=250000;
 fs.writeFileSync(file,JSON.stringify(settings));
 const conflicting=snapshotTree(dir);
 await assert.rejects(configure(flash),/compaction.*reserveTokens conflicts/);
 assert.deepEqual(snapshotTree(dir),conflicting);
});
test('scoped retry policy is projected after package registration and records field ownership',async t=>{
 const o=scopedFixture(t),{agentDir:dir}=await configure(o);
 assert.deepEqual(read({dir},'settings.json').retry,retryPolicy);
 assert.equal(read({dir},'settings.json').packages.length,1);
 assert.deepEqual(read({dir},'agents-sot-state.json').retryPolicy,retryPolicy);
});
test('installed Pi loads the wrapper thinking display default and retains a saved override', {skip:!process.env.PI_TEST_NATIVE_CLI},async t=>{
 const o={...fixture(t),cli:process.env.PI_TEST_NATIVE_CLI,expected:'1.5.2',profileScope:true,profiles:one('deepseek','deepseek-flash')};
 const {agentDir:dir}=await configure(o),pkg=path.resolve(path.dirname(o.cli),'../..');
 const {SettingsManager}=await import(pathToFileURL(path.join(pkg,'dist/core/settings-manager.js')).href);
 assert.equal(SettingsManager.create(o.root,dir).getHideThinkingBlock(),false);
 await configure({...o,hideThinkingBlock:true});
 const settings=SettingsManager.create(o.root,dir);
 assert.equal(settings.getHideThinkingBlock(),true);
 settings.setHideThinkingBlock(false);
 await settings.flush();
 const file=path.join(dir,'settings.json'),before=fs.readFileSync(file,'utf8');
 await configure({...o,hideThinkingBlock:true});
 assert.equal(SettingsManager.create(o.root,dir).getHideThinkingBlock(),false);
 assert.equal(fs.readFileSync(file,'utf8'),before);
});
test('scoped retry accepts the fifteen-minute cap and updates the earlier managed policy',async t=>{
 const o=scopedFixture(t),file=path.join(o.root,'previous-policy.json');
 const previous={enabled:true,maxRetries:5,baseDelayMs:4000,maxAgentDelayMs:60000};
 fs.writeFileSync(file,JSON.stringify(previous));
 const {agentDir:dir}=await configure({...o,retryPolicyFile:file});
 const settingsFile=path.join(dir,'settings.json'),settings=read({dir},'settings.json');
 settings.theme='preserved';settings.retry.provider={maxRetries:0};fs.writeFileSync(settingsFile,JSON.stringify(settings));
 fs.writeFileSync(file,JSON.stringify(retryPolicy));
 await configure({...o,retryPolicyFile:file});
 assert.deepEqual(read({dir},'settings.json'),{...settings,retry:{...retryPolicy,provider:{maxRetries:0}}});
 assert.deepEqual(read({dir},'agents-sot-state.json').retryPolicy,retryPolicy);
});
test('scoped retry reconciliation preserves native preferences and refuses foreign edits',async t=>{
 const o=scopedFixture(t),{agentDir:dir}=await configure(o),file=path.join(dir,'settings.json');
 const settings=read({dir},'settings.json');
 settings.theme='synthetic';settings.defaultModel='native-model';settings.future={enabled:true};
 settings.packages.push('npm:foreign');settings.retry={...retryPolicy,provider:{maxRetries:2},future:17};
 fs.writeFileSync(file,JSON.stringify(settings));
 const before=fs.readFileSync(file,'utf8'),mtime=fs.statSync(file).mtimeMs;
 await configure(o);assert.equal(fs.readFileSync(file,'utf8'),before);assert.equal(fs.statSync(file).mtimeMs,mtime);
 settings.retry.maxRetries=9;fs.writeFileSync(file,JSON.stringify(settings));
 const drift=snapshotTree(dir);
 await assert.rejects(configure(o),/retry.maxRetries/);assert.deepEqual(snapshotTree(dir),drift);
});
test('scoped retry updates are lazy, isolated and recover after ownership promotion fails',async t=>{
 const o=scopedFixture(t),policyFile=path.join(o.root,'policy.json');
 fs.writeFileSync(policyFile,JSON.stringify(retryPolicy));o.retryPolicyFile=policyFile;
 o.profiles.profiles.second={provider:'other',model:'b',credential:'secrets/b.key'};
 const first=(await configure(o)).agentDir,second=(await configure({...o,profileId:'second'})).agentDir;
 const firstBefore=snapshotTree(first),next={...retryPolicy,baseDelayMs:5000};
 fs.writeFileSync(policyFile,JSON.stringify(next));
 const file=path.join(second,'settings.json'),settings=read({dir:second},'settings.json');
 settings.theme='keep';settings.retry.provider={maxRetries:0};fs.writeFileSync(file,JSON.stringify(settings));
 const rename=fs.renameSync;let promotions=0;
 const mock=t.mock.method(fs,'renameSync',(source,target)=>{
  if(target===path.join(second,'agents-sot-state.json') && ++promotions===2)throw Error('synthetic ownership promotion failure');
  return rename(source,target);
 });
 try {await assert.rejects(configure({...o,profileId:'second'}),/synthetic ownership promotion failure/);}
 finally {mock.mock.restore();}
 assert.deepEqual(read({dir:second},'settings.json').retry,{...next,provider:{maxRetries:0}});
 assert.deepEqual(read({dir:second},'agents-sot-state.json').retryPolicy,retryPolicy);
 await configure({...o,profileId:'second'});
 assert.deepEqual(read({dir:second},'agents-sot-state.json').retryPolicy,next);
 assert.equal(read({dir:second},'settings.json').theme,'keep');assert.deepEqual(snapshotTree(first),firstBefore);
 await configure(o);assert.deepEqual(read({dir:first},'settings.json').retry,next);
});
test('scoped retry initial adoption refuses foreign values and accepts desired values',async t=>{
 const o=scopedFixture(t),{agentDir:dir}=await configure(o),file=path.join(dir,'settings.json'),stateFile=path.join(dir,'agents-sot-state.json');
 const state=read({dir},'agents-sot-state.json');delete state.retryPolicy;fs.writeFileSync(stateFile,JSON.stringify(state));
 const settings=read({dir},'settings.json');settings.retry={enabled:false,provider:{maxRetries:0}};fs.writeFileSync(file,JSON.stringify(settings));
 const before=snapshotTree(dir);await assert.rejects(configure(o),/retry.enabled/);assert.deepEqual(snapshotTree(dir),before);
 settings.retry={...retryPolicy,provider:{maxRetries:0}};fs.writeFileSync(file,JSON.stringify(settings));
 const bytes=fs.readFileSync(file,'utf8');await configure(o);assert.equal(fs.readFileSync(file,'utf8'),bytes);
 assert.deepEqual(read({dir},'agents-sot-state.json').retryPolicy,retryPolicy);
});
test('scoped retry first-install interruption finalizes policy ownership before connection promotion',async t=>{
 const o=scopedFixture(t),dir=path.join(o.dir,'profiles/first'),rename=fs.renameSync;let promotions=0;
 const mock=t.mock.method(fs,'renameSync',(source,target)=>{
  if(target===path.join(dir,'agents-sot-state.json') && ++promotions===2)throw Error('synthetic first policy ownership failure');
  return rename(source,target);
 });
 try {await assert.rejects(configure(o),/synthetic first policy ownership failure/);}
 finally {mock.mock.restore();}
 assert.deepEqual(read({dir},'settings.json').retry,retryPolicy);
 assert.equal(fs.existsSync(path.join(dir,'auth.json')),false,'connection promotion must wait until retry ownership is recorded');
 await configure(o);assert.deepEqual(read({dir},'agents-sot-state.json').retryPolicy,retryPolicy);
});
test('scoped retry policy and native file validation refuse before mutation',async t=>{
 const o=scopedFixture(t),file=path.join(o.root,'policy.json');o.retryPolicyFile=file;
 for(const value of [null,[],{...retryPolicy,extra:1},{...retryPolicy,enabled:1},{...retryPolicy,maxRetries:0},{...retryPolicy,maxRetries:11},{...retryPolicy,baseDelayMs:1.5},{...retryPolicy,maxAgentDelayMs:900001},{...retryPolicy,maxAgentDelayMs:1}]) {
  fs.writeFileSync(file,JSON.stringify(value));await assert.rejects(configure(o),/retry policy|configuration must be an object/);assert.deepEqual(fs.readdirSync(o.dir),[]);
 }
 fs.unlinkSync(file);await assert.rejects(configure(o),/retry policy/);assert.deepEqual(fs.readdirSync(o.dir),[]);
 const policyTarget=path.join(o.root,'linked-policy.json');fs.writeFileSync(policyTarget,JSON.stringify(retryPolicy));fs.symlinkSync(policyTarget,file,'file');
 await assert.rejects(configure(o),/ordinary file/);assert.deepEqual(fs.readdirSync(o.dir),[]);fs.unlinkSync(file);
 fs.writeFileSync(file,JSON.stringify(retryPolicy));
 const {agentDir:dir}=await configure(o),settingsFile=path.join(dir,'settings.json'),original=fs.readFileSync(settingsFile,'utf8');
 for(const text of ['{bad','[]','{"retry":false}']) {
  fs.writeFileSync(settingsFile,text);const before=snapshotTree(dir);await assert.rejects(configure(o));assert.deepEqual(snapshotTree(dir),before);
 }
 const target=path.join(o.root,'outside.json');fs.writeFileSync(target,original);fs.unlinkSync(settingsFile);fs.symlinkSync(target,settingsFile,'file');
 const before=snapshotTree(dir);await assert.rejects(configure(o),/symbolic/);assert.deepEqual(snapshotTree(dir),before);assert.equal(fs.readFileSync(target,'utf8'),original);
 fs.unlinkSync(settingsFile);fs.mkdirSync(settingsFile);await assert.rejects(configure(o),/ordinary file/);fs.rmdirSync(settingsFile);
 const missing=snapshotTree(dir);await assert.rejects(configure(o),/retry.enabled/);assert.deepEqual(snapshotTree(dir),missing,'missing owned values must not silently replace native edits');
});
test('scoped retry validation and inspection do not apply a changed policy',async t=>{
 const o=scopedFixture(t),{agentDir:dir}=await configure(o),file=path.join(o.root,'policy.json');
 fs.writeFileSync(file,JSON.stringify({...retryPolicy,maxRetries:6}));o.retryPolicyFile=file;
 const before=snapshotTree(o.dir);
 await configure({...o,op:'validate'});await configure({...o,op:'inspect'});
 assert.deepEqual(snapshotTree(o.dir),before);
 await configure({...o,op:'uninstall'});
 assert.deepEqual(read({dir},'settings.json').retry,retryPolicy);
 await configure(o);assert.deepEqual(read({dir},'settings.json').retry,{...retryPolicy,maxRetries:6});
});
test('installed Pi retry settings use the native lock, load normally and preserve concurrent writes', {skip:!process.env.PI_TEST_NATIVE_CLI},async t=>{
 const o={...fixture(t),cli:process.env.PI_TEST_NATIVE_CLI,expected:'1.5.2',profileScope:true,profiles:one('deepseek','deepseek-flash')};
 const {agentDir:dir}=await configure(o),pkg=path.resolve(path.dirname(o.cli),'../..');
 const moduleUrl=pathToFileURL(path.join(pkg,'dist/core/settings-manager.js')).href;
 const {SettingsManager}=await import(moduleUrl);
 assert.deepEqual(SettingsManager.create(o.root,dir).getRetrySettings(),retryPolicy);
 assert.equal(SettingsManager.create(o.root,dir).getProviderRetrySettings().maxRetries,undefined);
 const flash=read({dir},'models.json').providers.deepseek.models[0];
 const model={...flash,provider:'deepseek'};
 const settings=SettingsManager.create(o.root,dir);
 const compaction=settings.getCompactionSettings(model);
 const {shouldCompact}=await import(pathToFileURL(path.join(pkg,'dist/core/compaction/compaction.js')).href);
 const threshold=flash.contextWindow-Math.ceil(flash.contextWindow*0.30);
 assert.equal(shouldCompact(threshold,flash.contextWindow,compaction),false);
 assert.equal(shouldCompact(threshold+1,flash.contextWindow,compaction),true);
 assert.equal(compaction.keepRecentTokens,settings.getCompactionSettings().keepRecentTokens);
 const policyFile=path.join(o.root,'policy.json'),next={...retryPolicy,baseDelayMs:5000};fs.writeFileSync(policyFile,JSON.stringify(next));
 const helper=path.join(o.root,'native-writer.mjs'),ready=path.join(o.root,'writer-ready');
 fs.writeFileSync(helper,`import fs from 'node:fs';import {FileSettingsStorage} from ${JSON.stringify(moduleUrl)};
 new FileSettingsStorage(process.argv[2],process.argv[2]).withLock('global',text=>{
  const data=JSON.parse(text);fs.writeFileSync(process.argv[3],'locked');
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,120);
  data.theme='concurrent-native';data.retry.provider={maxRetries:0};return JSON.stringify(data);
 });`);
 const writer=spawn(process.execPath,[helper,dir,ready],{stdio:['ignore','pipe','pipe']});
 let errors='';writer.stderr.on('data',chunk=>errors+=chunk);
 const exited=new Promise((resolve,reject)=>{writer.on('error',reject);writer.on('exit',code=>code===0?resolve():reject(Error(errors)));});
 t.after(()=>{if(writer.exitCode===null)writer.kill();});
 const until=Date.now()+10000;
 while(!fs.existsSync(ready)){if(Date.now()>until || writer.exitCode!==null)throw Error('native writer failed to acquire lock: '+errors);await new Promise(resolve=>setTimeout(resolve,5));}
 assert.ok(fs.existsSync(path.join(dir,'settings.json.lock')),'native settings lock must be held at reconciliation start');
 await configure({...o,retryPolicyFile:policyFile});await exited;
 const loaded=read({dir},'settings.json');assert.equal(loaded.theme,'concurrent-native');
 assert.deepEqual(loaded.retry,{...next,provider:{maxRetries:0}});
 assert.deepEqual(SettingsManager.create(o.root,dir).getRetrySettings(),next);
 const bytes=fs.readFileSync(path.join(dir,'settings.json'),'utf8');await configure({...o,retryPolicyFile:policyFile});assert.equal(fs.readFileSync(path.join(dir,'settings.json'),'utf8'),bytes);
 const lock=path.join(dir,'settings.json.lock');fs.mkdirSync(lock);
 try {
  const before=snapshotTree(dir);
  await assert.rejects(configure({...o,retryPolicyFile:policyFile}),error=>error.code==='ELOCKED');
  assert.deepEqual(snapshotTree(dir),before,'native lock exhaustion must leave settings and ownership unchanged');
 } finally {fs.rmdirSync(lock);}
 const project=path.join(o.root,'project/.pi');fs.mkdirSync(project,{recursive:true});fs.writeFileSync(path.join(project,'settings.json'),JSON.stringify({retry:{maxRetries:1}}));
 assert.equal(SettingsManager.create(path.dirname(project),dir).getRetrySettings().maxRetries,1);
 await configure({...o,op:'uninstall'});assert.equal(read({dir},'settings.json').theme,'concurrent-native');
 await configure({...o,retryPolicyFile:policyFile});assert.equal(read({dir},'settings.json').theme,'concurrent-native');
});
test('installed Pi retry helper enforces the policy budget, schedule, reset and terminal errors', {skip:!process.env.PI_TEST_NATIVE_CLI},async t=>{
 const pkg=path.resolve(path.dirname(process.env.PI_TEST_NATIVE_CLI),'../..');
 const ai=[path.join(pkg,'node_modules/@earendil-works/pi-ai'),path.join(path.dirname(pkg),'pi-ai')].find(file=>fs.existsSync(file));
 const {retryAssistantCall,retryDelayMs}=await import(pathToFileURL(path.join(ai,'dist/utils/retry.js')).href);
 const {retryProviderRequest}=await import(pathToFileURL(path.join(ai,'dist/utils/provider-retry.js')).href);
 assert.deepEqual([1,2,3,4,5].map(attempt=>retryDelayMs(retryPolicy,attempt)),[60000,120000,240000,480000,900000]);
 const waits=[],realTimer=globalThis.setTimeout;
 const timer=t.mock.method(globalThis,'setTimeout',(fn,ms,...args)=>{
  if(ms>=retryPolicy.baseDelayMs && ms<=retryPolicy.maxAgentDelayMs){waits.push(ms);queueMicrotask(()=>fn(...args));return 0;}
  return realTimer(fn,ms,...args);
 });
 const failure={role:'assistant',stopReason:'error',errorMessage:'503 service unavailable'},success={role:'assistant',stopReason:'stop'};
 try {
  let calls=0;await retryAssistantCall(async()=>{calls++;return failure;},retryPolicy);assert.equal(calls,6);assert.deepEqual(waits,[60000,120000,240000,480000,900000]);
  for(let run=0;run<2;run++) {let calls=0;const scheduled=[];assert.equal(await retryAssistantCall(async()=>++calls===1?failure:success,retryPolicy,undefined,{onRetryScheduled:attempt=>scheduled.push(attempt)}),success);assert.deepEqual(scheduled,[1]);}
  for(const errorMessage of ['401 unauthorized','429 insufficient_quota','429 billing hard limit reached','429 out of budget']) {
   let calls=0;await retryAssistantCall(async()=>{calls++;return {...failure,errorMessage};},retryPolicy);assert.equal(calls,1,errorMessage);
  }
  calls=0;await retryAssistantCall(async()=>{calls++;return {role:'assistant',stopReason:'aborted'};},retryPolicy);assert.equal(calls,1);
  const controller=new AbortController();calls=0;
  const cancelled=await retryAssistantCall(async()=>{calls++;return failure;},retryPolicy,controller.signal,{onRetryScheduled:()=>controller.abort()});assert.equal(cancelled.stopReason,'aborted');assert.equal(calls,1);
  calls=0;await assert.rejects(retryProviderRequest(async()=>{calls++;throw Object.assign(Error('503 service unavailable'),{status:503});},{}));assert.equal(calls,1,'provider retries remain disabled by default');
 } finally {timer.mock.restore();}
});
test('scoped profiles preserve earlier provider and same-provider credential references',async t=>{
 const o=scopedFixture(t),profiles=one();
 profiles.profiles.second={provider:'other',model:'b',credential:'secrets/b.key'};
 profiles.profiles.third={provider:'deepseek',model:'a',credential:'secrets/b.key'};
 const first=await configure({...o,profiles,profileScope:true});
 const firstDir=first.agentDir??o.dir;
 const before=fs.readFileSync(path.join(firstDir,'auth.json'),'utf8');
 await configure({...o,profiles,profileId:'second',profileScope:true});
 assert.equal(fs.readFileSync(path.join(firstDir,'auth.json'),'utf8'),before,'another provider must not remove live profile auth');
 await configure({...o,profiles,profileId:'third',profileScope:true});
 assert.equal(fs.readFileSync(path.join(firstDir,'auth.json'),'utf8'),before,'same provider must not replace another profile key');
 assert.equal(first.agentDir,path.join(o.dir,'profiles','first'));
});
test('scoped inspection and refusal never provision a directory or require a key',async t=>{
 const o=scopedFixture(t),before=fs.readdirSync(o.dir);
 await assert.rejects(configure({...o,op:'inspect'}),/not initialized/);
 assert.deepEqual(fs.readdirSync(o.dir),before);
 const first=await configure(o);fs.unlinkSync(path.join(o.root,'secrets/a.key'));
 assert.equal((await configure({...o,op:'inspect'})).agentDir,first.agentDir);
 const outside=path.join(o.root,'outside');fs.mkdirSync(outside);
 fs.symlinkSync(outside,path.join(o.dir,'profiles/escape'),process.platform==='win32'?'junction':'dir');
 await assert.rejects(configure({...o,profiles:{active:'escape',profiles:{escape:{provider:'deepseek',model:'a',credential:'secrets/b.key'}}}}),/symbolic|link|escape/);
 assert.deepEqual(fs.readdirSync(outside),[]);
});
test('scoped cleanup removes exact session links while preserving history and foreign state',async t=>{
 const o=scopedFixture(t),first=await configure(o),dir=first.agentDir??o.dir;
 assert.ok(fs.lstatSync(path.join(dir,'sessions')).isSymbolicLink());
 const sentinel=path.join(o.dir,'sessions/history');fs.writeFileSync(sentinel,'synthetic-history');
 fs.writeFileSync(path.join(dir,'foreign.txt'),'keep');
 await configure({...o,op:'uninstall'});
 assert.equal(fs.readFileSync(sentinel,'utf8'),'synthetic-history');
 assert.equal(fs.readFileSync(path.join(dir,'foreign.txt'),'utf8'),'keep');
 assert.equal(fs.existsSync(path.join(dir,'sessions')),false);
 await assert.rejects(configure({...o,op:'inspect'}),/not initialized/);
 await configure(o);
 fs.unlinkSync(path.join(dir,'sessions'));
 const foreign=path.join(o.root,'foreign-history');fs.mkdirSync(foreign);fs.writeFileSync(path.join(foreign,'sentinel'),'keep');
 fs.symlinkSync(foreign,path.join(dir,'sessions'),process.platform==='win32'?'junction':'dir');
 const before=snapshotTree(dir);
 await assert.rejects(configure({...o,op:'uninstall'}),/tampered|foreign/);
 assert.deepEqual(snapshotTree(dir),before);
 assert.equal(fs.readFileSync(path.join(foreign,'sentinel'),'utf8'),'keep');
});
test('scoped failed provisioning retries and runtime-free removal preserves native preferences',async t=>{
 const o=scopedFixture(t);
 const previous=process.env.PI_TEST_LOCAL_INSTALL_FAIL;process.env.PI_TEST_LOCAL_INSTALL_FAIL='1';
 try {await assert.rejects(configure(o),/package install failed/);}
 finally {if(previous===undefined)delete process.env.PI_TEST_LOCAL_INSTALL_FAIL;else process.env.PI_TEST_LOCAL_INSTALL_FAIL=previous;}
 const dir=path.join(o.dir,'profiles/first');assert.equal(fs.existsSync(path.join(dir,'auth.json')),false);
 await configure(o);
 const file=path.join(dir,'settings.json'),settings=JSON.parse(fs.readFileSync(file));settings.theme='synthetic-theme';settings.packages.push('npm:synthetic-foreign');fs.writeFileSync(file,JSON.stringify(settings));
 const bin=path.join(dir,'bin'),fd=path.join(bin,process.platform==='win32'?'fd.exe':'fd');fs.mkdirSync(bin);fs.writeFileSync(fd,'native-owned-cache');
 const cached=fs.readFileSync(fd),mtime=fs.statSync(fd).mtimeMs;
 await configure(o);await configure(o);assert.deepEqual(fs.readFileSync(fd),cached);assert.equal(fs.statSync(fd).mtimeMs,mtime);
 await configure({...o,op:'uninstall',cli:undefined});
 assert.deepEqual(JSON.parse(fs.readFileSync(file)),{...settings,packages:['npm:synthetic-foreign']});
 await configure(o);assert.equal(JSON.parse(fs.readFileSync(file)).theme,'synthetic-theme');
 assert.deepEqual(fs.readFileSync(fd),cached);assert.equal(fs.statSync(fd).mtimeMs,mtime);
});
test('scoped package removal failure preserves projections and permits a normal retry',async t=>{
 const o=scopedFixture(t),{agentDir:dir}=await configure(o);
 fs.writeFileSync(path.join(o.dir,'sessions/history'),'synthetic-history');
 const auth=path.join(dir,'auth.json'),original=fs.readFileSync(auth,'utf8');
 fs.writeFileSync(auth,JSON.stringify({deepseek:{type:'api_key',key:'synthetic-foreign'}}));
 const drifted=snapshotTree(o.dir);
 await assert.rejects(configure({...o,op:'uninstall'}),/managed authentication changed/);
 assert.deepEqual(snapshotTree(o.dir),drifted,'genuine drift must refuse before removing resources');
 fs.writeFileSync(auth,original);
 const before=snapshotTree(o.dir),previous=process.env.PI_TEST_LOCAL_REMOVE_FAIL;
 process.env.PI_TEST_LOCAL_REMOVE_FAIL='1';
 try {await assert.rejects(configure({...o,op:'uninstall'}),/package remove failed/);}
 finally {if(previous===undefined)delete process.env.PI_TEST_LOCAL_REMOVE_FAIL;else process.env.PI_TEST_LOCAL_REMOVE_FAIL=previous;}
 assert.deepEqual(snapshotTree(o.dir),before,'failed native removal must preserve auth, models, ownership and links');
 await configure({...o,op:'uninstall'});
 assert.deepEqual(read({dir},'auth.json'),{});
 assert.deepEqual(read({dir},'models.json').providers,{});
 assert.deepEqual(read({dir},'agents-sot-state.json').managed,{});
 assert.deepEqual(read({dir},'settings.json').packages,[]);
 assert.equal(fs.existsSync(path.join(dir,'sessions')),false);
 assert.equal(fs.readFileSync(path.join(o.dir,'sessions/history'),'utf8'),'synthetic-history');
});
test('scoped disabled setup refuses foreign directory and ownership links before reading them',async t=>{
 for(const kind of ['directory','ownership'])await t.test(kind,async t=>{
  const o=scopedFixture(t),outside=path.join(o.root,'outside'),dir=path.join(o.dir,'profiles/foreign');
  fs.mkdirSync(outside);fs.mkdirSync(path.dirname(dir));
  // Invalid JSON distinguishes a link refusal from following the foreign ownership file.
  const external=path.join(outside,'agents-sot-state.json');fs.writeFileSync(external,'foreign-unreadable-json');
  if(kind==='directory')fs.symlinkSync(outside,dir,process.platform==='win32'?'junction':'dir');
  else {fs.mkdirSync(dir);fs.symlinkSync(external,path.join(dir,'agents-sot-state.json'),'file');}
  const before=snapshotTree(o.dir),foreign=snapshotTree(outside);
  for(const op of ['validate','install']) {
   await assert.rejects(configure({...o,op,profiles:{active:null,profiles:{}},setup:true}),/symbolic/,kind+' link must refuse without parsing the target');
   assert.deepEqual(snapshotTree(o.dir),before);assert.deepEqual(snapshotTree(outside),foreign);
  }
 });
 const o=scopedFixture(t),container=path.join(o.dir,'profiles');fs.mkdirSync(container);
 const outside=path.join(o.root,'ignored');fs.mkdirSync(outside);fs.writeFileSync(path.join(outside,'agents-sot-state.json'),'foreign-unreadable-json');
 fs.symlinkSync(outside,path.join(container,'invalid.id'),process.platform==='win32'?'junction':'dir');
 const before=snapshotTree(o.dir),foreign=snapshotTree(outside);
 await configure({...o,profiles:{active:null,profiles:{}},setup:true});
 assert.deepEqual(snapshotTree(o.dir),before);assert.deepEqual(snapshotTree(outside),foreign);
});
test('scoped launch preserves legacy state and explicit retirement removes only owned entries',async t=>{
 const o=scopedFixture(t);
 const foreign={foreign:{type:'api_key',key:'synthetic-foreign'}};
 fs.writeFileSync(path.join(o.dir,'auth.json'),JSON.stringify(foreign));
 await configure({...o,profileScope:false});
 const legacy=Object.fromEntries(['auth.json','agents-sot-state.json'].map(name=>[name,fs.readFileSync(path.join(o.dir,name),'utf8')]));
 await configure(o);
 for(const [name,bytes] of Object.entries(legacy))assert.equal(fs.readFileSync(path.join(o.dir,name),'utf8'),bytes);
 await configure({...o,op:'retire'});
 assert.deepEqual(read(o,'auth.json'),foreign);
 assert.equal(fs.existsSync(path.join(o.dir,'agents-sot-state.json')),false);
 assert.ok(fs.existsSync(path.join(o.dir,'profiles/first/auth.json')));
});
test('scoped invalid second profile leaves the existing profile and source unchanged',async t=>{
 const o=scopedFixture(t),selected=await configure(o),before=snapshotTree(selected.agentDir);
 for(const entry of [{provider:'deepseek',model:'a',credential:'secrets/missing.key'},{provider:'deepseek',model:'absent',credential:'secrets/b.key'}]) {
  const profiles={...o.profiles,profiles:{...o.profiles.profiles,bad:entry}},source=JSON.stringify(profiles);
  await assert.rejects(configure({...o,profiles,profileId:'bad'}));
  assert.deepEqual(snapshotTree(selected.agentDir),before);assert.equal(JSON.stringify(profiles),source);
  assert.equal(fs.existsSync(path.join(o.dir,'profiles/bad')),false);
 }
});
test('external credential owner confines references and survives validation, refusal and removal',async t=>{
 const o=fixture(t),secretRoot=path.join(o.root,'private credentials');fs.mkdirSync(secretRoot);
 const key=path.join(secretRoot,'a.key');fs.writeFileSync(key,'synthetic-external-key');
 const profiles=one();profiles.profiles.inactive={provider:'inactive',model:'absent',credential:'secrets/missing.key'};
 const foreign={other:{type:'api_key',key:'synthetic-foreign'}};
 fs.writeFileSync(path.join(o.dir,'auth.json'),JSON.stringify(foreign));
 const options={...o,secretRoot,profiles};
 await configure({...options,op:'validate'});assert.deepEqual(fs.readdirSync(o.dir),['auth.json']);
 await configure(options);assert.ok(read(o,'auth.json').deepseek.key.includes(secretRoot));
 const before=fs.readFileSync(path.join(o.dir,'auth.json'),'utf8');
 const outside=path.join(o.root,'outside');fs.mkdirSync(outside);fs.writeFileSync(path.join(outside,'x.key'),'synthetic-outside');
 fs.symlinkSync(outside,path.join(secretRoot,'escape'),process.platform==='win32'?'junction':'dir');
 for(const credential of ['secrets/missing.key','secrets/escape/x.key']) {
  await assert.rejects(configure({...options,profiles:one('deepseek','a',credential)}));
  assert.equal(fs.readFileSync(path.join(o.dir,'auth.json'),'utf8'),before);
  assert.ok(!fs.existsSync(path.join(o.dir,'.agents-sot.lock')));
 }
 if(process.platform!=='win32'&&process.getuid()!==0) {
  fs.chmodSync(key,0);
  try {
   if((fs.statSync(key).mode&0o444)===0) {await assert.rejects(configure(options));assert.equal(fs.readFileSync(path.join(o.dir,'auth.json'),'utf8'),before);}
   else t.diagnostic('filesystem does not enforce POSIX file modes; unreadable-key acceptance needs a native Linux filesystem');
  }
  finally {fs.chmodSync(key,0o600);}
 }
 await configure({...options,op:'uninstall'});assert.deepEqual(read(o,'auth.json'),foreign);
 assert.equal(fs.readFileSync(key,'utf8'),'synthetic-external-key');
});
test('profile override selects an arbitrary configured entry without changing its default',async t=>{
 const o=fixture(t),profiles=one();
 profiles.profiles.alternate={provider:'fixture-provider',model:'other-model',credential:'secrets/b.key',thinking:'high',endpoint:'https://provider.example.invalid/v1'};
 const before=JSON.stringify(profiles);
 const result=await configure({...o,profiles,profileId:'alternate'});
 assert.equal(result.profile,'alternate');assert.equal(result.provider,'fixture-provider');
 assert.match(read(o,'auth.json')['fixture-provider'].key,/b\.key/);
 assert.equal(read(o,'models.json').providers['fixture-provider'].baseUrl,profiles.profiles.alternate.endpoint);
 assert.equal(JSON.stringify(profiles),before);
 await configure({...o,profiles});assert.equal(read(o,'agents-sot-state.json').profile,'first');
});
test('invalid profile overrides refuse before projections or locks',async t=>{
 const o=fixture(t);
 for(const profileId of ['', '../bad', 'unknown', 'constructor', '--high', 42]) {
  await assert.rejects(configure({...o,profileId}),/profile/);
  assert.deepEqual(fs.readdirSync(o.dir),[]);
 }
});
const custom=()=>({provider:'tencent-tokenhub',model:'hy4',credential:'secrets/a.key',thinking:'high',endpoint:'http://127.0.0.1:5555/v1',api:'openai-completions',compatibleModel:{name:'Synthetic Hy4',reasoning:true,input:['text','image'],contextWindow:1000000,maxTokens:64000,thinkingLevelMap:{off:'no_think',minimal:null,low:null,medium:null,high:'high',xhigh:null,max:null},compat:{supportsReasoningEffort:true,thinkingFormat:'openai',maxTokensField:'max_tokens'}}});
test('custom model projection and profile switches retain one managed owner',async t=>{
 const o=fixture(t),entry=custom(),profiles=selected=>({active:'selected',profiles:{selected}});
 const foreign={baseUrl:'https://foreign.example.invalid/v1'};
 fs.writeFileSync(path.join(o.dir,'models.json'),JSON.stringify({providers:{foreign}}));
 await configure(o);
 await configure({...o,profiles:profiles(entry)});
 let projected=read(o,'models.json').providers['tencent-tokenhub'];
 assert.equal(projected.authHeader,true);assert.equal(projected.apiKey,undefined);
 assert.equal(projected.models[0].id,'hy4');assert.deepEqual(projected.models[0].thinkingLevelMap,entry.compatibleModel.thinkingLevelMap);
 await configure({...o,profiles:profiles({...entry,model:'second',credential:'secrets/b.key'})});
 assert.deepEqual(read(o,'models.json').providers['tencent-tokenhub'].models.map(model=>model.id),['second']);
 assert.match(read(o,'auth.json')['tencent-tokenhub'].key,/b\.key/);
 const file=path.join(o.dir,'models.json'),before=fs.readFileSync(file,'utf8');
 const changed=read(o,'models.json');changed.providers['tencent-tokenhub'].models[0].maxTokens=1;fs.writeFileSync(file,JSON.stringify(changed));
 const drift=fs.readFileSync(file,'utf8');await assert.rejects(configure({...o,profiles:profiles(entry)}),/drift/);
 assert.equal(fs.readFileSync(file,'utf8'),drift);fs.writeFileSync(file,before);
 await configure(o);assert.equal(read(o,'models.json').providers['tencent-tokenhub'],undefined);
 await configure({...o,op:'uninstall'});assert.deepEqual(read(o,'models.json').providers,{foreign});
 assert.ok(fs.existsSync(path.join(o.root,'secrets/a.key')));
});
test('custom metadata structural refusals create no projections',async t=>{
 const o=fixture(t),entry=custom();
 for(const selected of [{...entry,compatibleModel:null},{...entry,compatibleModel:[]},{...entry,endpoint:''},{...entry,api:''},{...entry,compatibleModel:{...entry.compatibleModel,headers:{Authorization:'synthetic'}}},{...entry,compatibleModel:{...entry.compatibleModel,thinkingLevelMap:{turbo:'high'}}}]) {
  await assert.rejects(configure({...o,profiles:{active:'selected',profiles:{selected}}}));
  assert.deepEqual(fs.readdirSync(o.dir),[]);
 }
});
test('inactive credentials are not required until their profile is selected',async t=>{
 const o=fixture(t),profiles=one();
 profiles.profiles.inactive={...custom(),credential:'secrets/missing.key'};
 await configure({...o,profiles});
 const before=fs.readFileSync(path.join(o.dir,'auth.json'),'utf8');
 await assert.rejects(configure({...o,profiles:{...profiles,active:'inactive'}}),/credential file missing/);
 assert.equal(fs.readFileSync(path.join(o.dir,'auth.json'),'utf8'),before);
});
test('profile switch removes only owned references',async t=>{
 const o=fixture(t);fs.writeFileSync(path.join(o.dir,'auth.json'),JSON.stringify({foreign:{type:'api_key',key:'synthetic-foreign'}}));
 await configure(o);const first=read(o,'auth.json').deepseek.key;
 await configure({...o,profiles:{active:'second',profiles:{second:{provider:'other',model:'b',credential:'secrets/b.key',endpoint:'http://127.0.0.1:5555',api:'openai-completions'}}}});
 const auth=read(o,'auth.json');assert.equal(auth.deepseek,undefined);assert.notEqual(auth.other.key,first);assert.equal(auth.foreign.key,'synthetic-foreign');
 await configure({...o,op:'uninstall'});assert.deepEqual(read(o,'auth.json'),{foreign:{type:'api_key',key:'synthetic-foreign'}});
 assert.ok(fs.existsSync(path.join(o.root,'secrets/a.key')));assert.ok(fs.existsSync(path.join(o.root,'secrets/b.key')));
});
test('collision and drift refuse without replacing protected files',async t=>{
 const o=fixture(t);await configure(o);
 const file=path.join(o.dir,'auth.json');const data=read(o,'auth.json');data.deepseek.key='operator-edited';fs.writeFileSync(file,JSON.stringify(data));
 const before=fs.readFileSync(file,'utf8');await assert.rejects(configure(o),/drift/);assert.equal(fs.readFileSync(file,'utf8'),before);
});
test('missing credential and invalid profile do not create projections',async t=>{
 const o=fixture(t);
 for(const profiles of [
  one('deepseek','a','secrets/missing.key'),
  one('deepseek','a','../outside.key'),
  one('','a','secrets/a.key'),
  {active:'first',profiles:{first:{provider:'deepseek',model:'a',credential:'secrets/a.key',thinking:'turbo'}}},
  {active:'first',profiles:{first:{provider:'deepseek',model:'a',credential:'secrets/a.key',vendor:'extra'}}},
  {active:'missing',profiles:{first:{provider:'deepseek',model:'a',credential:'secrets/a.key'}}}
 ]) await assert.rejects(configure({...o,profiles}));
 assert.deepEqual(fs.readdirSync(o.dir),[]);
});
test('preflight checks projections without creating directories or locks',async t=>{
 const o=fixture(t);
 fs.rmdirSync(o.dir);
 await configure({...o,op:'validate'});
 assert.equal(fs.existsSync(o.dir),false);
 fs.mkdirSync(path.join(o.root,'secrets/directory.key'));
 await assert.rejects(configure({...o,op:'validate',profiles:one('deepseek','a','secrets/directory.key')}),/regular file/);
 assert.equal(fs.existsSync(o.dir),false);
 fs.mkdirSync(o.dir);
 const file=path.join(o.dir,'auth.json');
 const foreign=JSON.stringify({deepseek:{type:'api_key',key:'synthetic-foreign'}});
 fs.writeFileSync(file,foreign);
 await assert.rejects(configure({...o,op:'validate'}),/collision/);
 assert.deepEqual(fs.readdirSync(o.dir),['auth.json']);
 assert.equal(fs.readFileSync(file,'utf8'),foreign);
 fs.unlinkSync(file);await configure(o);
 const state=fs.readFileSync(path.join(o.dir,'agents-sot-state.json'),'utf8');
 const drift=JSON.stringify({deepseek:{type:'api_key',key:'synthetic-drift'}});
 fs.writeFileSync(file,drift);
 await assert.rejects(configure({...o,op:'validate'}),/drift/);
 assert.equal(fs.readFileSync(file,'utf8'),drift);
 assert.equal(fs.readFileSync(path.join(o.dir,'agents-sot-state.json'),'utf8'),state);
 assert.equal(fs.existsSync(path.join(o.dir,'.agents-sot.lock')),false);
});
test('malformed JSON preserved',async t=>{
 const o=fixture(t);const file=path.join(o.dir,'auth.json');fs.writeFileSync(file,'{bad');
 await assert.rejects(configure(o));assert.equal(fs.readFileSync(file,'utf8'),'{bad');
});
test('native model projection collision refuses even without an endpoint override',async t=>{
 const o=fixture(t);
 const file=path.join(o.dir,'models.json');
 const before=JSON.stringify({providers:{deepseek:{modelOverrides:{a:{reasoning:false}}}}});
 fs.writeFileSync(file,before);
 await assert.rejects(configure({...o,op:'validate'}),/foreign model configuration collision/);
 assert.equal(fs.readFileSync(file,'utf8'),before);
 assert.deepEqual(fs.readdirSync(o.dir),['models.json']);
});
test('invalid native projection shapes refuse without mutation',async t=>{
 const o=fixture(t);
 for(const [name,value] of [['models.json',{providers:[]}],['models.json',{providers:null}],['agents-sot-state.json',{managed:[]}]]) {
  const file=path.join(o.dir,name);const before=JSON.stringify(value);fs.writeFileSync(file,before);
  await assert.rejects(configure(o),'invalid shape must refuse');
  assert.equal(fs.readFileSync(file,'utf8'),before);
  assert.equal(fs.existsSync(path.join(o.dir,'auth.json')),false);
  fs.unlinkSync(file);
 }
});
test('concurrent native projections keep one consistent owner',async t=>{
 const o=fixture(t);
 // The low-level shared-directory control exercises the projector's writer lock.
 const scripts=[['deepseek','a'],['fixture','b']].map(([provider,model],index)=>{
  const runtime=path.join(o.root,'runtime-'+index);fs.mkdirSync(runtime,{recursive:true});
  fs.writeFileSync(path.join(runtime,'writer.mjs'),`import {configure} from ${JSON.stringify(new URL('../../../providers/pi/runtime/configure.js',import.meta.url).href)};import fs from 'node:fs';await configure({op:'install',dir:process.argv[3],root:process.argv[4],profiles:JSON.parse(fs.readFileSync(new URL('./profiles.json',import.meta.url)))});`);
  fs.writeFileSync(path.join(runtime,'profiles.json'),JSON.stringify({active:'first',profiles:{first:{provider,model,credential:'secrets/'+model+'.key',endpoint:'http://127.0.0.1:9999',api:'openai-completions',...(index===1?{compatibleModel:custom().compatibleModel}:{})}}}));
  return path.join(runtime,'writer.mjs');
 });
 await Promise.all(Array.from({length:4},(_,i)=>new Promise((resolve,reject)=>{
  const child=spawn(process.execPath,[scripts[i%2],'install',o.dir,o.root]);
  let error='';child.stderr.on('data',data=>error+=data);
  child.on('error',reject);child.on('close',code=>code===0?resolve():reject(Error(error)));
 })));
 const state=read(o,'agents-sot-state.json');
 assert.deepEqual(read(o,'auth.json'),state.managed.auth);
 assert.deepEqual(read(o,'models.json').providers,state.managed.models);
 assert.equal(Object.keys(state.managed.auth).length,1);
});
test('SOT-only changes select native managed launch on each platform',t=>{
 const o=fixture(t),repo=o.root;
 const runtime=path.join(repo,'ai/agents/providers/pi/runtime'),lifecycle=path.join(repo,'ai/agents/lifecycle');
 for(const [source,target] of [['providers/pi/runtime/launch.sh',path.join(runtime,'launch.sh')],['providers/pi/runtime/configure.js',path.join(runtime,'configure.js')],['providers/pi/runtime/retry-policy.json',path.join(runtime,'retry-policy.json')],['providers/pi/runtime/plugins.js',path.join(runtime,'plugins.js')],['providers/pi/runtime/image-engine.js',path.join(runtime,'image-engine.js')],['providers/pi/runtime/profiles.json',path.join(runtime,'profiles.json')],['lifecycle/registry.sh',path.join(lifecycle,'registry.sh')],['lifecycle/providers.conf.sh',path.join(lifecycle,'providers.conf.sh')]]) {
  fs.mkdirSync(path.dirname(target),{recursive:true});
  fs.copyFileSync(fileURLToPath(new URL('../../../'+source,import.meta.url)),target);
 }
 for(const relative of ['config.py','permissions/run-guard.sh','permissions/guards/_paths.py']) {
  const target=path.join(repo,'ai/agents',relative);fs.mkdirSync(path.dirname(target),{recursive:true});
  fs.copyFileSync(fileURLToPath(new URL('../../../'+relative,import.meta.url)),target);
 }
 fs.writeFileSync(path.join(repo,'ai/config.local.json'),JSON.stringify({pi:{secret_root:path.join(repo,'secrets'),ownership_root:repo,hide_thinking_block:true}}));

 const configFile=path.join(lifecycle,'providers.conf.sh');
 const home=path.join(repo,'home');fs.mkdirSync(home);
 const win=process.platform==='win32';
 const prefix=path.join(home,win?'AppData/Roaming/pi-sot':'.local/share/pi-sot');
 const packageDir=path.join(prefix,'node_modules/@earendil-works/pi-coding-agent');
 const cli=path.join(packageDir,'dist/bundle/cli.js');fs.mkdirSync(path.dirname(cli),{recursive:true});
 settingsStub(packageDir);
 const argsFixture=path.join(packageDir,'dist/cli/args.js');
 fs.mkdirSync(path.dirname(argsFixture),{recursive:true});
 fs.writeFileSync(argsFixture,`export function parseArgs(args) {
  const result={extensions:[]};
  for (let i=0;i<args.length;i++) {
   if (args[i]==='--') break;
   if (['-ne','--no-extensions'].includes(args[i])) result.noExtensions=true;
   if (['-e','--extension'].includes(args[i])) result.extensions.push(args[++i]);
   if (args[i]==='--session') i++;
  }
  return result;
 }`);
 const record=path.join(repo,'dispatch.json');
 fs.writeFileSync(cli,"const fs=require('fs'),path=require('path');if(process.argv[2]==='install'||process.argv[2]==='remove'){const f=path.join(process.env.PI_CODING_AGENT_DIR,'settings.json');fs.writeFileSync(f,JSON.stringify({packages:process.argv[2]==='install'?[process.argv[3]]:[]}));}else{fs.writeFileSync(process.env.PI_TEST_RECORD,JSON.stringify(process.argv.slice(2)));fs.writeFileSync(process.env.PI_TEST_RECORD+'.dir',process.env.PI_CODING_AGENT_DIR??'');}");
 fs.writeFileSync(path.join(repo,'ai/agents/AGENTS.md'),'Synthetic instructions');
 fs.copyFileSync(fileURLToPath(new URL('../../../package.json',import.meta.url)),path.join(repo,'ai/agents/package.json'));
 const capability=path.join(prefix,'node_modules/@earendil-works/pi-ai/dist');fs.mkdirSync(path.join(capability,'providers/data'),{recursive:true});
 const pin=/^PI_PACKAGE='[^']*@([^']+)'/m.exec(fs.readFileSync(configFile,'utf8'))[1];
 const packageFile=path.join(packageDir,'package.json');
 fs.writeFileSync(packageFile,JSON.stringify({name:'@earendil-works/pi-coding-agent',version:pin}));
 fs.writeFileSync(path.join(capability,'index.js'),"export function getSupportedThinkingLevels(){return ['off','low','high','max'];}\n");
 fs.writeFileSync(path.join(capability,'providers/data/deepseek.json'),JSON.stringify({models:{flash:{id:'deepseek-flash',api:'openai-completions',contextWindow:1000000},other:{id:'other-model',api:'openai-completions'}}}));
 if(!win){const node=path.join(home,'.nvm/versions/node/v24.8.0/bin/node');fs.mkdirSync(path.dirname(node),{recursive:true});fs.symlinkSync(process.execPath,node);}
 fs.writeFileSync(path.join(repo,'secrets/deepseek-pi.key'),'synthetic');
 const profileFile=path.join(runtime,'profiles.json'),first={provider:'deepseek',model:'deepseek-flash',credential:'secrets/deepseek-pi.key',thinking:'max'};
 const writeProfiles=(active,profiles)=>fs.writeFileSync(profileFile,JSON.stringify({active,profiles}));
 const alternate={provider:'fixture-provider',model:'fixture-model',credential:'secrets/b.key',thinking:'high',endpoint:'https://provider.example.invalid/v1'};
 fs.writeFileSync(path.join(capability,'providers/data/fixture-provider.json'),JSON.stringify({models:{entry:{id:alternate.model,api:'openai-completions'}}}));
 writeProfiles('deepseek-direct',{'deepseek-direct':first,alternate});
 const launch=(...args)=>spawnSync(resolveShell(),['-c',win?'export HOME="$(cygpath -u "$PI_TEST_HOME")"; exec bash "$PI_TEST_LAUNCH" "$@"':'exec bash "$PI_TEST_LAUNCH" "$@"','pi-launch-test',...args],{env:{...process.env,HOME:home,PI_TEST_HOME:home,PI_TEST_LAUNCH:path.join(runtime,'launch.sh').replaceAll('\\','/'),PI_TEST_RECORD:record},encoding:'utf8'});
 let result=launch();assert.equal(result.status,0,result.stderr);
 assert.equal(path.resolve(fs.readFileSync(record+'.dir','utf8')),path.join(home,'.pi/agent/profiles/deepseek-direct'),'native startup must receive the SOT agent directory');
 assert.deepEqual(JSON.parse(fs.readFileSync(record)),['--provider','deepseek','--model','deepseek-flash','--thinking','max']);
 const policyBefore=fs.readFileSync(profileFile,'utf8');
 for(const selector of [['--profile','alternate'],['--profile=alternate']]) {
  result=launch(...selector,'-p','literal prompt','--thinking','low');assert.equal(result.status,0,result.stderr);
  assert.deepEqual(JSON.parse(fs.readFileSync(record)),['--provider',alternate.provider,'--model',alternate.model,'--thinking','high','-p','literal prompt','--thinking','low']);
  assert.equal(fs.readFileSync(profileFile,'utf8'),policyBefore);
  const generated=JSON.parse(fs.readFileSync(path.join(home,'.pi/agent/profiles/alternate/models.json'))).providers;
  assert.deepEqual(Object.keys(generated),[alternate.provider]);
  assert.equal(generated[alternate.provider].baseUrl,alternate.endpoint);
 }
 const retryFile=path.join(runtime,'retry-policy.json'),retrySource=fs.readFileSync(retryFile,'utf8');
 const firstDir=path.join(home,'.pi/agent/profiles/deepseek-direct'),alternateDir=path.join(home,'.pi/agent/profiles/alternate');
 assert.equal(read({dir:firstDir},'settings.json').hideThinkingBlock,true);
 assert.equal(read({dir:alternateDir},'settings.json').hideThinkingBlock,true);
 assert.deepEqual(read({dir:firstDir},'settings.json').compaction,{modelOverrides:{'deepseek/deepseek-flash':{reserveTokens:300000}}});
 assert.equal(read({dir:alternateDir},'settings.json').compaction,undefined);
 const firstSnapshot=snapshotTree(firstDir),alternateSettings=path.join(alternateDir,'settings.json');
 fs.writeFileSync(retryFile,JSON.stringify({...retryPolicy,baseDelayMs:5000}));
 const alternateBefore=snapshotTree(alternateDir);
 result=launch('--profile','alternate','list');assert.equal(result.status,0,result.stderr);assert.deepEqual(snapshotTree(alternateDir),alternateBefore);
 result=launch('--profile','alternate');assert.equal(result.status,0,result.stderr);
 assert.equal(JSON.parse(fs.readFileSync(alternateSettings)).retry.baseDelayMs,5000);assert.deepEqual(snapshotTree(firstDir),firstSnapshot);
 const settings=JSON.parse(fs.readFileSync(alternateSettings));settings.retry.maxRetries=9;fs.writeFileSync(alternateSettings,JSON.stringify(settings));
 const drift=snapshotTree(alternateDir),dispatchBefore=fs.readFileSync(record,'utf8');
 result=launch('--profile','alternate');assert.notEqual(result.status,0);assert.match(result.stderr,/retry.maxRetries/);
 assert.deepEqual(snapshotTree(alternateDir),drift);assert.equal(fs.readFileSync(record,'utf8'),dispatchBefore);
 settings.retry.maxRetries=retryPolicy.maxRetries;fs.writeFileSync(alternateSettings,JSON.stringify(settings));fs.writeFileSync(retryFile,retrySource);
 if(win) {
  const baseEnv={...process.env,PI_TEST_HOME:home,PI_TEST_RECORD:record};
  const converted=spawnSync(resolveShell(),['-c','cygpath -u "$PI_TEST_HOME"'],{env:baseEnv,encoding:'utf8'});
  assert.equal(converted.status,0,converted.stderr);
  const env={...baseEnv,HOME:converted.stdout.trim()};
  const cmdShim=path.join(home,'pi-sot.cmd'),bashShim=path.join(home,'pi-sot');
  const writer=fileURLToPath(new URL('../../../providers/pi/lifecycle.sh',import.meta.url));
  const generated=spawnSync(resolveShell(),['-c','source "$(cygpath -u "$1")"; pi_write_windows_launcher "$(cygpath -u "$2")" "$3" "$4"',
   'fixture',writer,cmdShim,resolveShell(),path.join(runtime,'launch.sh')],{env,encoding:'utf8'});
  assert.equal(generated.status,0,generated.stderr);
  const cmdEntry=path.join(home,'codepage-entry.cmd');
  fs.writeFileSync(cmdEntry,'@echo off\r\nchcp 866 >nul || exit /b 1\r\ncall "%~dp0pi-sot.cmd" %*\r\n');
  fs.writeFileSync(bashShim,'#!/usr/bin/env bash\n# agents SOT launcher\nexec bash "'+path.join(runtime,'launch.sh').replaceAll('\\','/')+'" "$@"\n');
  for(const [command,args] of [['cmd.exe',['/d','/c',cmdEntry,'--profile','alternate','--version']],[resolveShell(),[bashShim,'--profile','alternate','--version']]]) {
   result=spawnSync(command,args,{env,encoding:'utf8'});assert.equal(result.status,0,result.stderr);
   assert.deepEqual(JSON.parse(fs.readFileSync(record)),['--provider',alternate.provider,'--model',alternate.model,'--thinking','high','--version']);
   assert.equal(fs.readFileSync(profileFile,'utf8'),policyBefore);
  }
 }
 result=launch();assert.equal(result.status,0,result.stderr);
 assert.deepEqual(JSON.parse(fs.readFileSync(record)),['--provider','deepseek','--model','deepseek-flash','--thinking','max']);
 assert.equal(fs.readFileSync(profileFile,'utf8'),policyBefore);
 const snapshot=()=>snapshotTree(path.join(home,'.pi/agent'));
 const beforeSelection=snapshot(),beforeDispatch=fs.readFileSync(record,'utf8');
 for(const args of [['--profile'],['--profile='],['--profile',''],['--profile','../bad'],['--profile','unknown'],['--profile','constructor'],['--profile','--help'],['--profile','alternate','--profile','deepseek-direct'],['--profile','unknown','list'],['--profile','alternate','auth']]) {
  result=launch(...args);assert.notEqual(result.status,0,JSON.stringify(args));
  assert.equal(fs.readFileSync(record,'utf8'),beforeDispatch);
  assert.deepEqual(snapshot(),beforeSelection);
  assert.equal(fs.readFileSync(profileFile,'utf8'),policyBefore);
 }
 result=launch('--profile','alternate','list');assert.equal(result.status,0,result.stderr);
 assert.deepEqual(JSON.parse(fs.readFileSync(record)),['list']);assert.deepEqual(snapshot(),beforeSelection);
 assert.equal(path.resolve(fs.readFileSync(record+'.dir','utf8')),path.join(home,'.pi/agent/profiles/alternate'));
 const alternateKey=path.join(repo,'secrets/b.key');fs.renameSync(alternateKey,alternateKey+'.hidden');
 try {result=launch('--profile','alternate','list');assert.equal(result.status,0,result.stderr);}
 finally {fs.renameSync(alternateKey+'.hidden',alternateKey);}
 const expanded=JSON.parse(policyBefore);expanded.profiles.uninitialized={...first,credential:'secrets/missing.key'};
 fs.writeFileSync(profileFile,JSON.stringify(expanded));
 result=launch('--profile','uninitialized','list');assert.notEqual(result.status,0);assert.match(result.stderr,/not initialized/);
 assert.equal(fs.existsSync(path.join(home,'.pi/agent/profiles/uninitialized')),false);
 assert.deepEqual(snapshot(),beforeSelection);fs.writeFileSync(profileFile,policyBefore);
 for(const args of [['--','--profile','literal'],['--system-prompt','--profile','-p','literal'],['--version'],['--help']]) {
  const beforeInfo=snapshot();
  result=launch(...args);assert.equal(result.status,0,result.stderr);
  assert.deepEqual(JSON.parse(fs.readFileSync(record)),args.length===1 ? args : ['--provider','deepseek','--model','deepseek-flash','--thinking','max',...args]);
  assert.equal(fs.readFileSync(profileFile,'utf8'),policyBefore);
  if(args.length===1)assert.deepEqual(snapshot(),beforeInfo);
 }
 const configScript=path.join(runtime,'configure.js'),ownerSource=fs.readFileSync(configScript,'utf8');
 const selectionAnchor="  const chosen = op === 'uninstall' ? null : resolveProfiles(options.profiles !== undefined ? options.profiles : readProfiles(options.profileFile ?? defaultProfileFile), setup || op==='inspect');";
 assert.equal(ownerSource.split(selectionAnchor).length,2);
 const racePolicy={...JSON.parse(policyBefore),active:'alternate'};
 const replacement=JSON.parse(JSON.stringify(racePolicy));
 replacement.profiles.alternate={...replacement.profiles.alternate,credential:'secrets/a.key',endpoint:'https://changed.example.invalid/v1'};
 const readCount=path.join(runtime,'snapshot-count.json');
 const injected="\n  const counter=path.join(here,'snapshot-count.json');const reads=fs.existsSync(counter)?JSON.parse(fs.readFileSync(counter)):0;fs.writeFileSync(counter,JSON.stringify(reads+1));if(reads===0)fs.writeFileSync(defaultProfileFile,"+JSON.stringify(JSON.stringify(replacement))+");";
 const acceptanceDir=path.join(repo,'ai/agents/tests/providers/pi');fs.mkdirSync(acceptanceDir,{recursive:true});
 const acceptanceScript=path.join(acceptanceDir,'run.sh');
 fs.copyFileSync(fileURLToPath(new URL('./run.sh',import.meta.url)),acceptanceScript);
 fs.writeFileSync(path.join(acceptanceDir,'live.js'),"import fs from 'node:fs';fs.writeFileSync(process.env.PI_TEST_RECORD,JSON.stringify(process.argv.slice(-4)));fs.writeFileSync(process.env.PI_TEST_RECORD+'.dir',process.env.PI_CODING_AGENT_DIR??'')");
 const acceptance=()=>spawnSync(resolveShell(),['-c',win?'export HOME="$(cygpath -u "$PI_TEST_HOME")"; exec bash "$PI_TEST_ACCEPTANCE" "$PI_TEST_FIXTURE"':'exec bash "$PI_TEST_ACCEPTANCE" "$PI_TEST_FIXTURE"'],{env:{...process.env,HOME:home,PI_TEST_HOME:home,PI_TEST_ACCEPTANCE:acceptanceScript.replaceAll('\\','/'),PI_TEST_FIXTURE:path.join(repo,'acceptance-fixture').replaceAll('\\','/'),PI_TEST_RECORD:record},encoding:'utf8'});
 try {
  for(const entry of ['launcher','acceptance']) {
   fs.writeFileSync(profileFile,JSON.stringify(racePolicy));fs.rmSync(readCount,{force:true});
   fs.writeFileSync(configScript,ownerSource.replace(selectionAnchor,selectionAnchor+injected));
   result=entry==='launcher'?launch('--profile','alternate'):acceptance();assert.equal(result.status,0,result.stderr);
   assert.equal(path.resolve(fs.readFileSync(record+'.dir','utf8')),path.join(home,'.pi/agent/profiles/alternate'),'each consumer must export the same resolved native directory');
   assert.equal(JSON.parse(fs.readFileSync(path.join(home,'.pi/agent/profiles/alternate/models.json'))).providers[alternate.provider].baseUrl,alternate.endpoint,'launch must project the endpoint from its one validated snapshot');
   assert.match(JSON.parse(fs.readFileSync(path.join(home,'.pi/agent/profiles/alternate/auth.json')))[alternate.provider].key,/b\.key/,'launch must retain the credential from that same snapshot');
   assert.equal(JSON.parse(fs.readFileSync(readCount)),1,'managed launch must read its profile selection once');
   assert.deepEqual(JSON.parse(fs.readFileSync(record)),entry==='launcher'?['--provider',alternate.provider,'--model',alternate.model,'--thinking',alternate.thinking]:['alternate',alternate.provider,alternate.model,alternate.thinking]);
   assert.equal(fs.readFileSync(profileFile,'utf8'),JSON.stringify(replacement),'only the simulated editor may change the SOT');
  }
 } finally {fs.writeFileSync(configScript,ownerSource);fs.writeFileSync(profileFile,policyBefore);}
 writeProfiles('renamed-default',{'renamed-default':first,alternate});
 result=launch();assert.equal(result.status,0,result.stderr);
 assert.equal(JSON.parse(fs.readFileSync(path.join(home,'.pi/agent/profiles/renamed-default/agents-sot-state.json'))).profile,'renamed-default','renaming a profile ID must retain ownership of its existing projections');
 assert.deepEqual(JSON.parse(fs.readFileSync(record)),['--provider','deepseek','--model','deepseek-flash','--thinking','max']);
 result=launch('--thinking','low');assert.equal(result.status,0,result.stderr);
 assert.deepEqual(JSON.parse(fs.readFileSync(record)),['--provider','deepseek','--model','deepseek-flash','--thinking','max','--thinking','low'],'explicit CLI override stays session-local and wins over the SOT default');
 result=launch('list');assert.equal(result.status,0,result.stderr);
 assert.deepEqual(JSON.parse(fs.readFileSync(record)),['list'],'native package subcommand must remain argv[0]');
 assert.equal(path.resolve(fs.readFileSync(record+'.dir','utf8')),path.join(home,'.pi/agent/profiles/renamed-default'));
 const managedDir=path.join(home,'.pi/agent');
 const managedBefore=snapshotTree(managedDir);
 const dispatchedBefore=fs.readFileSync(record,'utf8');
 for (const args of [['--no-extensions'],['-ne'],['-e','npm:image-budget'],['--extension','github.com/fixture/extension']]) {
  const refused=launch(...args);
  assert.notEqual(refused.status,0,refused.stderr);
  assert.match(refused.stderr,/permission extension|explicit local extension/);
  assert.equal(fs.readFileSync(record,'utf8'),dispatchedBefore);
  assert.deepEqual(snapshotTree(managedDir),managedBefore);
 }

 for(const command of ['auth','config','install','remove','uninstall','update','mcp']) {
  result=launch(command,'--help');
  assert.notEqual(result.status,0,command+' must refuse before native dispatch');
  assert.match(result.stderr,/managed|SOT/);
  assert.equal(fs.readFileSync(record,'utf8'),dispatchedBefore);
  assert.deepEqual(snapshotTree(managedDir),managedBefore);
 }
 writeProfiles('alternate',{'deepseek-direct':first,alternate:{provider:'deepseek',model:'other-model',credential:'secrets/b.key',endpoint:'http://127.0.0.1:9999',api:'openai-completions'}});
 result=launch();assert.equal(result.status,0,result.stderr);
 assert.deepEqual(JSON.parse(fs.readFileSync(record)),['--provider','deepseek','--model','other-model'],'a profile without a thinking level must not force one');
 const dir=path.join(home,'.pi/agent/profiles/alternate');
 assert.equal(JSON.parse(fs.readFileSync(path.join(dir,'models.json'))).providers.deepseek.baseUrl,'http://127.0.0.1:9999');
 assert.match(JSON.parse(fs.readFileSync(path.join(dir,'auth.json'))).deepseek.key,/b\.key/);
 const config=fs.readFileSync(configFile,'utf8');
 const anchor='register_provider pi .pi/agent ';
 assert.equal(config.split(anchor).length,2);
 fs.writeFileSync(configFile,config.replace(anchor,'register_provider pi .pi-alternate/agent '));
 result=launch();assert.equal(result.status,0,result.stderr);
 assert.equal(path.resolve(fs.readFileSync(record+'.dir','utf8')),path.join(home,'.pi-alternate/agent/profiles/alternate'));
 assert.ok(fs.existsSync(path.join(home,'.pi-alternate/agent/profiles/alternate/auth.json')));
 const before=fs.readFileSync(record,'utf8');
 writeProfiles('missing',{'deepseek-direct':first});
 assert.notEqual(launch().status,0);assert.equal(fs.readFileSync(record,'utf8'),before);
 writeProfiles('deepseek-direct',{'deepseek-direct':first});
 fs.writeFileSync(packageFile,JSON.stringify({name:'@earendil-works/pi-coding-agent',version:'0.99.1'}));
 const tree=()=>snapshotTree(managedDir);
 const managedFresh=tree();
 result=launch();assert.notEqual(result.status,0,'installed version drift must refuse before dispatch');
 assert.match(result.stderr,/does not match managed pin/);
 assert.match(result.stderr,/install\.sh --provider pi --runtime/);
 assert.equal(fs.readFileSync(record,'utf8'),before,'drift refusal must not dispatch');
 assert.deepEqual(tree(),managedFresh,'drift refusal must not mutate managed configuration');
});
test('thinking capability resolves the native dependency in hoisted and nested layouts',async t=>{
 const o=fixture(t);
 const prefix=path.join(o.root,'prefix'),packageDir=path.join(prefix,'node_modules/@earendil-works/pi-coding-agent');
 const cli=path.join(packageDir,'dist/bundle/cli.js');fs.mkdirSync(path.dirname(cli),{recursive:true});fs.writeFileSync(cli,'');
 const profiles={active:'first',profiles:{first:{provider:'deepseek',model:'flash',credential:'secrets/a.key',thinking:'max'}}};
 for(const nested of [false,true]) {
  const ai=nested?path.join(packageDir,'node_modules/@earendil-works/pi-ai'):path.join(prefix,'node_modules/@earendil-works/pi-ai');
  fs.mkdirSync(path.join(ai,'dist/providers/data'),{recursive:true});
  fs.writeFileSync(path.join(ai,'dist/providers/data/deepseek.json'),JSON.stringify({models:{flash:{id:'flash',api:'openai-completions'}}}));
  fs.writeFileSync(path.join(ai,'dist/index.js'),"export function getSupportedThinkingLevels(){return ['off','high','max'];}\n");
  const label=nested?'nested':'hoisted';
  assert.equal((await configure({...o,op:'validate',profiles,cli})).thinking,'max',label+' layout must resolve the pinned capability');
  await assert.rejects(configure({...o,op:'validate',profiles:{active:'first',profiles:{first:{...profiles.profiles.first,thinking:'low'}}},cli}),/thinking level low unsupported/,'unsupported level must refuse in the '+label+' layout');
  fs.rmSync(ai,{recursive:true,force:true});
 }
 await assert.rejects(configure({...o,op:'validate',profiles,cli}),/native Pi dependency missing/,'absent capability dependency must refuse');
});

test('setup accepts only the exact disabled profile and preserves foreign native data',async t=>{
 const o=fixture(t),profiles={active:null,profiles:{}};
 fs.rmSync(path.join(o.root,'secrets'),{recursive:true});
 const foreign={foreign:{type:'api_key',key:'synthetic-foreign'}};
 fs.writeFileSync(path.join(o.dir,'auth.json'),JSON.stringify(foreign));
 const before=fs.readFileSync(path.join(o.dir,'auth.json'),'utf8');
 await configure({...o,profiles,setup:true,op:'validate'});
 await configure({...o,profiles,setup:true});
 assert.deepEqual(fs.readdirSync(o.dir),['auth.json']);
 assert.equal(fs.readFileSync(path.join(o.dir,'auth.json'),'utf8'),before);
 await assert.rejects(configure({...o,profiles}),/unconfigured/);
 await assert.rejects(configure({...o,profiles:{...profiles,unknown:true},setup:true}),/unknown/);
 await assert.rejects(configure({...o,profiles:{active:null,profiles:{first:one().profiles.first}},setup:true}),/active/);
 assert.equal(fs.readFileSync(path.join(o.dir,'auth.json'),'utf8'),before);
});
test('unconfigured setup refuses to discard an existing managed connection',async t=>{
 const o=fixture(t);await configure(o);
 const before=fs.readFileSync(path.join(o.dir,'agents-sot-state.json'),'utf8');
 await assert.rejects(configure({...o,profiles:{active:null,profiles:{}},setup:true}),/existing managed connection/);
 assert.equal(fs.readFileSync(path.join(o.dir,'agents-sot-state.json'),'utf8'),before);
});
