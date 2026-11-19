import {spawn} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
export async function launchBounded(command,args,{cwd,env,timeoutMs=180000,streamFile}={}) {
  const stream=fs.openSync(streamFile,'w');
  return new Promise((resolve,reject)=>{
    const child=spawn(command,args,{cwd,env,stdio:['ignore',stream,stream],detached:process.platform!=='win32',windowsHide:true});
    let timedOut=false,cleanupTimer,settled=false,closed=false,code=null,killed=false;
    const finish=(cleanup=timedOut&&killed)=>{
      if(settled)return;settled=true;
      clearTimeout(timer);clearTimeout(cleanupTimer);fs.closeSync(stream);
      resolve({code,timedOut,cleanup,pid:child.pid});
    };
    const timer=setTimeout(()=>{
      timedOut=true;
      cleanupTimer=setTimeout(()=>finish(false),3000);
      if(process.platform==='win32') {
        const killer=spawn('taskkill.exe',['/PID',String(child.pid),'/T','/F'],{stdio:'ignore',windowsHide:true});
        killer.on('error',()=>{});
        killer.on('close',status=>{killed=status===0;if(closed&&killed)finish();});
      }else {try{process.kill(-child.pid,'SIGKILL');killed=true;}catch(err){killed=err.code==='ESRCH';}if(closed&&killed)finish();}
    },timeoutMs);
    child.on('error',err=>{if(!settled){settled=true;clearTimeout(timer);clearTimeout(cleanupTimer);fs.closeSync(stream);reject(err);}});
    child.on('close',status=>{code=status;closed=true;if(!timedOut||killed)finish();});
  });
}
export function verifyProbe(record,stream,platform=process.platform,thinking) {
  const data=JSON.parse(fs.readFileSync(record,'utf8'));
  if(data.complete!==true||data.requests!==1||data.outputCap!==2048||data.error)throw Error('probe incomplete or bounds failed');
  const count=platform==='win32'?12:11;
  if(data.cases.length!==count||data.cases.some((c,i)=>c.isError!==(i>=3)))throw Error('unexpected probe outcomes');
  const events=fs.readFileSync(stream,'utf8').split('\n').filter(line=>line.startsWith('{')).map(line=>JSON.parse(line));
 const generations=events.filter(e=>e.type==='message_end'&&e.message?.role==='assistant');
 if(generations.length!==1||generations[0].message.stopReason!=='toolUse')throw Error('unexpected assistant generation count or outcome');
 const top=generations[0].message.content.filter(c=>c.type==='toolCall');
 if(top.length!==1||top[0].name!=='guard_probe')throw Error('unexpected top-level tool call');
  const result=events.find(e=>e.type==='message_end'&&e.message?.role==='toolResult'&&e.message?.toolName==='guard_probe');
  if(!result)throw Error('native probe tool result missing');
  if(events.filter(e=>e.type==='message_end'&&e.message?.role==='toolResult').length!==1)throw Error('unexpected top-level tool result');
 const transport=JSON.parse(fs.readFileSync(path.join(path.dirname(record),'transport.json'),'utf8'));
 if(transport.attempts!==1||transport.dispatches!==1||transport.stopDecisions!==1||transport.error||transport.requests.length!==1||transport.requests[0].max_tokens!==2048)throw Error('transport bounds or explicit stop unproven');
 if(!transport.response||!Number.isInteger(transport.response.status)||transport.response.status<200||transport.response.status>=300||transport.response.observationFailed||transport.response.modelObserved!==true||transport.response.modelMatches!==true||transport.response.modelMismatch)throw Error('provider response status or model mismatch');
 if(thinking&&data.thinkingLevel!==thinking)throw Error('selected thinking level mismatch');
 if(!data.nativeThinking||typeof data.nativeThinking!=='object'||Array.isArray(data.nativeThinking)||JSON.stringify(data.nativeThinking)!==JSON.stringify(transport.requests[0].nativeThinking))throw Error('native thinking payload changed');
 if(typeof data.absentTarget!=='string'||!path.isAbsolute(data.absentTarget)||fs.existsSync(data.absentTarget))throw Error('protected absent target was not preserved');
 const nested=result.message.nestedCalls;
  if(!nested||(!Array.isArray(nested)&&nested.complete!==true))throw Error('native nested-call evidence incomplete');
  const calls=Array.isArray(nested)?nested:nested.calls;
  if(!Array.isArray(calls)||calls.length!==count)throw Error('native nested-call count mismatch');
  for(let i=0;i<count;i++) {
    if(calls[i].name!==data.cases[i].tool||calls[i].status!==(i<3?'ok':'error')||(i>=3&&!calls[i].error))
      throw Error('native nested-call outcome mismatch');
  }
  return data;
}

export function initializeFixture(directory,root) {
 const scratch=path.resolve(root,'../tmp');
 if(!path.resolve(directory).startsWith(scratch+path.sep))throw Error('acceptance directory must be below repository tmp');
 if(fs.existsSync(directory))throw Error('acceptance requires a fresh fixture directory');
 fs.mkdirSync(directory,{recursive:true});fs.writeFileSync(path.join(directory,'README.md'),'# Harmless permission acceptance\n');
 const git=(...args)=>{
  const result=spawnSync('git',['-C',directory,...args],{encoding:'utf8'});
  if(result.status!==0)throw Error('fixture Git command failed: '+args[0]);return result.stdout;
 };
 git('init','-q');
 fs.writeFileSync(path.join(directory,'.git/info/exclude'),'runner.json\nevents.jsonl\nprobe.json\ntransport.json\nloaded.json\npreservation.json\nsummary.json\nsessions/\n');
 git('add','README.md');
 git('-c','user.name=Acceptance fixture','-c','user.email=fixture@example.invalid','-c','commit.gpgsign=false','commit','-qm','Fixture');
 return git;
}
export function repositoryState(git) {
 // Git may refresh index stat data; compare logical staging rather than index-file bytes.
 return {head:git('rev-parse','HEAD'),index:git('ls-files','--stage'),stash:git('stash','list'),status:git('status','--porcelain','--untracked-files=all')};
}
export function costEvidenceSource(usage) {
 return usage?.cost?.totalFromProvider===true
  ?'provider-reported total, not billing receipt'
  :'native model-catalog estimate, not billing receipt';
}
export async function runAcceptance({node,index,root,directory,agentDir,provider,model,profile,thinking,mode='normal',fixture=fileURLToPath(new URL('./probe.js',import.meta.url)),timeoutMs=180000}) {
 const git=(...args)=>{
  const r=spawnSync('git',['-C',directory,...args],{encoding:'utf8'});if(r.status!==0)throw Error('fixture Git observation failed');return r.stdout;
 };
 const before=repositoryState(git);
 const config=path.join(directory,'runner.json'),stream=path.join(directory,'events.jsonl'),record=path.join(directory,'probe.json');
 fs.writeFileSync(config,JSON.stringify({index,root,directory,agentDir,provider,model,profile,thinking,mode,fixture}));
 const start=Date.now();
 const outcome=await launchBounded(node,[fileURLToPath(new URL('./session.js',import.meta.url)),config],{cwd:directory,env:{...process.env,PI_PROBE_RECORD:record,PI_TELEMETRY:'0'},timeoutMs,streamFile:stream});
 const after=repositoryState(git);fs.writeFileSync(path.join(directory,'preservation.json'),JSON.stringify({before,after,outcome,elapsedMs:Date.now()-start},null,2));
 for(const field of ['head','index','stash'])if(before[field]!==after[field])throw Error('protected fixture Git state changed: '+field);
 if(outcome.code!==0||outcome.timedOut)throw Error('acceptance process failed or timed out');
 const evidence=verifyProbe(record,stream,process.platform,thinking);
 if(after.status!==before.status+'?? scratch/ok.txt\n')throw Error('unexpected fixture working-tree mutation');
 const loaded=JSON.parse(fs.readFileSync(path.join(directory,'loaded.json'),'utf8'));
 if(thinking&&loaded.thinking!==thinking)throw Error('loaded thinking level mismatch');
 const events=fs.readFileSync(stream,'utf8').split('\n').filter(s=>s.startsWith('{')).map(s=>JSON.parse(s));
 const assistant=events.find(e=>e.type==='message_end'&&e.message?.role==='assistant').message;
 const transport=JSON.parse(fs.readFileSync(path.join(directory,'transport.json')));
 const summary={platform:process.platform,profile,provider,model,thinking:loaded.thinking,endpoint:loaded.endpoint,httpStatus:transport.response?.status,responseModelMatched:transport.response?.modelMatches,nativeThinking:transport.requests[0].nativeThinking,providerRouting:transport.requests[0].routing??null,generations:1,dispatches:1,outputCap:2048,cases:evidence.cases.length,elapsedMs:Date.now()-start,usage:assistant.usage??null,costSource:costEvidenceSource(assistant.usage),preserved:true,complete:true};
 fs.writeFileSync(path.join(directory,'summary.json'),JSON.stringify(summary,null,2));return summary;
}
if(process.argv[1]&&path.resolve(process.argv[1])===path.resolve(fileURLToPath(import.meta.url))) {
 try {
  const [index,root,directory,agentDir,profile,provider,model,thinking]=process.argv.slice(2);
  if(!model)throw Error('usage: live.js <native-sdk-index> <agents-root> <fresh-repo-tmp-directory> <native-agent-dir> <profile> <provider> <model>');
  initializeFixture(path.resolve(directory),path.resolve(root));
  console.log(JSON.stringify(await runAcceptance({node:process.execPath,index,root:path.resolve(root),directory:path.resolve(directory),agentDir,profile,provider,model,thinking})));
 }catch(err){console.error(err.message);process.exitCode=1;}
}
