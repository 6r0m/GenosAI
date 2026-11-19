import {spawn} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const shared = path.resolve(here,'../../../permissions');
const gatePath = path.relative(path.join(shared,'guards'),path.join(here,'gate.py')).replaceAll('\\','/');
const gateArgs = [path.join(shared,'run-guard.sh').replaceAll('\\','/'),gatePath];
const gated = new Set(['bash','read','edit','write','grep','find','ls']);
export function resolveShell(platform=process.platform,env=process.env,exists=fs.existsSync) {
  if(platform!=='win32')return '/bin/bash';
  for(const candidate of [env.PI_GUARD_SHELL,
      env.ProgramFiles && path.win32.join(env.ProgramFiles,'Git','bin','bash.exe'),
      env['ProgramFiles(x86)'] && path.win32.join(env['ProgramFiles(x86)'],'Git','bin','bash.exe')])
    if(candidate && path.win32.isAbsolute(candidate) && exists(candidate))return candidate;
  throw Error('Git Bash unavailable; configure an absolute PI_GUARD_SHELL');
}

export function runGate(envelope,{shell=resolveShell(),args,cwd=envelope.cwd,env=process.env,timeoutMs=10000,onSpawn}={}) {
  return new Promise((resolve,reject)=>{
    const child=spawn(shell,args??gateArgs,
      {cwd,env,detached:process.platform!=='win32',stdio:['pipe','pipe','pipe'],windowsHide:true});
    onSpawn?.(child.pid);
    let stdout='',stderr='',timedOut=false,cleanupTimer,closed=false,code=null,killed=false;
    const finish=()=>{
      if(!closed|| (timedOut&&!killed))return;
      clearTimeout(timer);clearTimeout(cleanupTimer);
      resolve({code,stdout,stderr,timedOut,cleanup:timedOut&&killed});
    };
    const stop=()=>{
      if(timedOut)return;
      timedOut=true;
      cleanupTimer=setTimeout(()=>resolve({code:null,stdout,stderr:stderr+' cleanup unobserved for PID '+child.pid,timedOut,cleanup:false}),3000);
      if(process.platform==='win32') {
        const killer=spawn('taskkill.exe',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});
        killer.on('error',err=>{stderr+=' cleanup: '+err.message;});
        killer.on('close',status=>{killed=status===0;finish();});
      } else {
        try {process.kill(-child.pid,'SIGKILL');killed=true;} catch(err){if(err.code==='ESRCH')killed=true;else stderr+=' cleanup: '+err.message;}
        finish();
      }
    };
    const timer=setTimeout(stop,timeoutMs);
    child.on('error',err=>{clearTimeout(timer);clearTimeout(cleanupTimer);reject(err);});
    child.stdout.on('data',data=>{stdout=(stdout+data).slice(0,1000001);if(stdout.length>1000000)stop();});
    child.stderr.on('data',data=>{stderr=(stderr+data).slice(-10000);});
    child.stdin.on('error',()=>{});
    child.on('close',status=>{code=status;closed=true;finish();});
    child.stdin.end(JSON.stringify(envelope));
  });
}

export async function decideTool(event,ctx,{runner=runGate,timeoutMs=10000,healthy=true}={}) {
  if(event.toolName==='powershell')return {block:true,reason:'powershell disabled: no POSIX permission guard'};
  if(!gated.has(event.toolName))return;
  if(!healthy)return {block:true,reason:'gate unhealthy: startup probe failed'};
  if(typeof ctx.cwd!=='string'||!path.isAbsolute(ctx.cwd)||!fs.existsSync(ctx.cwd))
    return {block:true,reason:'invalid Pi context cwd'};
  const env={...process.env};delete env.CLAUDE_PROJECT_DIR;
  let timer;
  try {
    const result=await Promise.race([runner({event,cwd:ctx.cwd},{cwd:ctx.cwd,env,timeoutMs}),
      new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('gate timeout')),timeoutMs+3500);})]);
    if(result.timedOut)return {block:true,reason:'gate timeout; cleanup '+(result.cleanup?'observed':'failed')};
    if(result.code!==0)return {block:true,reason:'gate exited '+result.code};
    let data;try{data=JSON.parse(result.stdout);}catch{return {block:true,reason:'unparseable gate output'};}
    if(data.pi_gate!==1||typeof data.allow!=='boolean')return {block:true,reason:'no gate decision'};
    if(!data.allow)return {block:true,reason:data.reason??'gate denied'};
  } catch(err){return {block:true,reason:'gate unavailable: '+err.message};}
  finally{clearTimeout(timer);}
}

export default function(pi,{runner=runGate}={}) {
  let status={healthy:false,reason:'startup probe not run'};
  pi.on('session_start',async(_event,ctx)=>{
    try {
      const env={...process.env};delete env.CLAUDE_PROJECT_DIR;
      const shell=resolveShell();
      const result=await runner({cwd:ctx.cwd},{shell,cwd:ctx.cwd,env,
        args:[...gateArgs,'--probe',ctx.cwd]});
      const data=JSON.parse(result.stdout);
      status={...data,shell,healthy:result.code===0&&!result.timedOut&&data.pi_gate===1&&data.healthy===true
        &&Array.isArray(data.cases)&&data.cases.length>=8&&data.cases.every(c=>c.allow===false)};
    }catch(err){status={healthy:false,reason:err.message};}
    if(!status.healthy)ctx.ui.notify('Pi gate unhealthy: '+(status.reason??'probe failed'),'error');
  });
  pi.on('tool_call',(event,ctx)=>decideTool(event,ctx,{healthy:status.healthy,runner}));
  pi.registerCommand('guard-status',{description:'Show permission adapter health without calling a model',
    handler:async(_args,ctx)=>ctx.ui.notify(JSON.stringify(status),status.healthy?'info':'error')});
}
