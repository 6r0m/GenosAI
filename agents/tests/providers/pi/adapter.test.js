import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {identity} from './process.js';
import {fileURLToPath} from 'node:url';
const modulePath = new URL('../../../providers/pi/permissions/adapter.js', import.meta.url);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const {default:adapter,decideTool, runGate, resolveShell} = await import(modulePath);
const event = {toolName:'bash', input:{command:'git status'}};
const ctx = {cwd:root};
for (const [label,result,blocked] of [
  ['allow',{code:0,stdout:'{"pi_gate":1,"allow":true}'},false],
  ['deny',{code:0,stdout:'{"pi_gate":1,"allow":false,"reason":"denied"}'},true],
  ['missing marker',{code:0,stdout:'{}'},true],
  ['exit',{code:1,stdout:''},true], ['parse',{code:0,stdout:'garbage'},true],
]) test(label, async()=>assert.equal(Boolean((await decideTool(event,ctx,{runner:async()=>result}))?.block),blocked));
test('runner failure and hung injection refuse', async()=>{
  for(const runner of [async()=>{throw Error('spawn');}, ()=>new Promise(()=>{})])
    assert.equal((await decideTool(event,ctx,{runner,timeoutMs:30})).block,true);
});
test('powershell and invalid context do not spawn', async()=>{
  const runner=()=>{throw Error('must not spawn');};
  assert.equal((await decideTool({toolName:'powershell',input:{}},ctx,{runner})).block,true);
  assert.equal((await decideTool(event,{cwd:''},{runner})).block,true);
});
test('context envelope and child environment', async()=>{
  process.env.CLAUDE_PROJECT_DIR='misleading';
  let observed;
  await decideTool({...event,cwd:'wrong'},ctx,{runner:async(envelope,opts)=>{
    observed={envelope,opts};return {code:0,stdout:'{"pi_gate":1,"allow":true}'};
  }});
  assert.equal(observed.envelope.cwd,root);
  assert.equal(observed.opts.env.CLAUDE_PROJECT_DIR,undefined);
  assert.equal(process.env.CLAUDE_PROJECT_DIR,'misleading');delete process.env.CLAUDE_PROJECT_DIR;
});
test('shell resolver excludes PATH Bash on Windows',()=>{
  assert.equal(resolveShell('linux'),'/bin/bash');
  assert.match(resolveShell('win32',{ProgramFiles:'C:\\Program Files'},()=>true),/Git[\\/]bin[\\/]bash.exe$/);
});
test('real gate wire protocol',async()=>{
  assert.equal(await decideTool(event,ctx),undefined);
  assert.equal((await decideTool({toolName:'bash',input:{command:'git add -A'}},ctx)).block,true);
});
test('startup health controls registered tool handler',async()=>{
  for(const healthy of [false,true]) {
    const handlers={},notices=[];
    let calls=0;
    adapter({on:(name,fn)=>handlers[name]=fn,registerCommand(){}},{runner:async()=>{
      calls++;
      return {code:0,stdout:JSON.stringify(calls===1?{pi_gate:1,healthy:true,cases:Array.from({length:8},(_,i)=>({allow:!healthy&&i===0}))}:{pi_gate:1,allow:true})};
    }});
    await handlers.session_start({}, {...ctx,ui:{notify:message=>notices.push(message)}});
    const result=await handlers.tool_call(event,ctx);
    assert.equal(Boolean(result?.block),!healthy);
    assert.equal(calls,healthy?2:1);
    assert.equal(notices.length,healthy?0:1);
  }
});
test('real sleeping interpreter is terminated',async()=>{
  const dir=fs.mkdtempSync(path.join(root,'../tmp/pi-timeout-'));
  const record=path.join(dir,'pid.json');
  fs.mkdirSync(path.join(dir,'guards'));
  const script=path.join(dir,'guards/pi_gate.py');
  fs.copyFileSync(path.join(root,'permissions/run-guard.sh'),path.join(dir,'run-guard.sh'));
  fs.writeFileSync(script,`import os,json,time\nfrom pathlib import Path\nPath(${JSON.stringify(record)}).write_text(json.dumps({'pid':os.getpid()}))\ntime.sleep(60)\n`);
  const shell=resolveShell();
  const command=[path.join(dir,'run-guard.sh').replaceAll('\\','/'),'pi_gate.py'];
  let shellPid;
  const pending=runGate({}, {shell,args:command,cwd:root,timeoutMs:5000,onSpawn:pid=>shellPid=pid});
  const deadline=Date.now()+3000;
  while(!fs.existsSync(record)&&Date.now()<deadline)await new Promise(resolve=>setTimeout(resolve,25));
  assert.ok(fs.existsSync(record),'fixture must signal readiness');
  const {pid}=JSON.parse(fs.readFileSync(record));
  const before=new Map([pid,shellPid].map(id=>[id,identity(id)]));
  assert.ok(before.get(pid),'known-bad control: sleeping fixture is still alive');
  const result=await pending;
  assert.equal(result.timedOut,true);
  assert.equal(result.cleanup,true, result.stderr);
  for(const [id,start] of before)if(start!==null)assert.notEqual(identity(id),start,'spawned process generation survived timeout');
  fs.rmSync(dir,{recursive:true,force:true});
});
