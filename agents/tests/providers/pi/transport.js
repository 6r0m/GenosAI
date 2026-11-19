import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {initializeFixture,runAcceptance} from './live.js';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..');
const directory=path.resolve(process.argv[4]);
const mode=process.argv[5]??'normal';
assert.ok(['normal','thinking-control','cap-control','stop-control','retry-control','provider-failure','truncated','fixture-error','missing-probe','timeout','redirect'].includes(mode));
initializeFixture(directory,root);
const agent=path.join(directory,'agent');fs.mkdirSync(agent);
fs.symlinkSync(fs.realpathSync(path.join(root,'AGENTS.md')),path.join(agent,'AGENTS.md'));
fs.writeFileSync(path.join(agent,'auth.json'),JSON.stringify({deepseek:{type:'api_key',key:'synthetic-transport-key'}}));
let fixture=fileURLToPath(new URL('./probe.js',import.meta.url));
if(mode==='cap-control') {
 const source=fs.readFileSync(fixture,'utf8');assert.equal(source.split('max_tokens:2048').length,2);
 fixture=path.join(directory,'probe-control.mjs');fs.writeFileSync(fixture,source.replace('max_tokens:2048','max_tokens:90000'));
}
const calls=[];
if(mode==='thinking-control') {
 const source=fs.readFileSync(fixture,'utf8'),anchor='payload:{...payload,max_tokens:2048}';
 assert.equal(source.split(anchor).length,2);
 fixture=path.join(directory,'probe-control.mjs');fs.writeFileSync(fixture,source.replace(anchor,"payload:{...payload,max_tokens:2048,reasoning_effort:'low'}"));
}
const server=http.createServer(async(req,res)=>{
 let text='';for await(const part of req)text+=part;
 const body=JSON.parse(text);calls.push(body);fs.writeFileSync(path.join(directory,'requests.json'),JSON.stringify(calls,null,2));
 if(mode==='timeout')return;
 if(mode==='redirect'){res.writeHead(307,{Location:'/redirect-target'});res.end();return;}
 if(calls.length>1){res.writeHead(500);res.end('unexpected continuation');return;}
 if(mode==='provider-failure'||mode==='retry-control'){res.writeHead(429,{'Retry-After':'0.01'});res.end('synthetic failure');return;}
 res.writeHead(200,{'Content-Type':'text/event-stream'});
 const chunk=(delta,finish_reason=null)=>res.write('data: '+JSON.stringify({id:'local-probe',object:'chat.completion.chunk',created:0,model:body.model,choices:[{index:0,delta,finish_reason}]})+'\n\n');
 if(mode==='missing-probe')chunk({role:'assistant',content:'No probe'});
 else chunk({role:'assistant',tool_calls:[{index:0,id:'probe-1',type:'function',function:{name:mode==='fixture-error'?'bash':'guard_probe',arguments:mode==='fixture-error'?'{"command":"git status"}':'{}'}}]});
 chunk({},mode==='truncated'?'length':mode==='missing-probe'?'stop':'tool_calls');
 res.write('data: '+JSON.stringify({id:'local-probe',object:'chat.completion.chunk',choices:[],usage:{prompt_tokens:10,completion_tokens:5,total_tokens:15}})+'\n\n');res.end('data: [DONE]\n\n');
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
fs.writeFileSync(path.join(agent,'models.json'),JSON.stringify({providers:{deepseek:{baseUrl:'http://127.0.0.1:'+server.address().port}}}));
// Harness files are outside the fixture's committed tree and belong to its explicit ignore contract.
fs.appendFileSync(path.join(directory,'.git/info/exclude'),'agent/\nrequests.json\nprobe-control.mjs\n');
let failure,summary;
try {summary=await runAcceptance({node:process.argv[2],index:path.resolve(path.dirname(process.argv[3]),'../index.js'),root,directory,agentDir:agent,provider:'deepseek',model:'deepseek-flash',profile:'synthetic-direct',thinking:'max',mode,fixture,timeoutMs:mode==='timeout'?10000:30000});}
catch(err){failure=err;}
finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
try {
 if(mode==='normal'){if(failure)throw failure;assert.equal(calls.length,1);assert.equal(calls[0].max_tokens,2048);assert.equal(calls[0].reasoning_effort,'max');assert.equal(calls[0].thinking.type,'enabled');console.log(JSON.stringify(summary));}
 else {
  assert.ok(failure,'known-bad control passed');
  const ledger=JSON.parse(fs.readFileSync(path.join(directory,'transport.json')));
  assert.equal(calls.length,1,'control must reach the real local transport exactly once');
  assert.equal(ledger.dispatches,1);
  const record=fs.existsSync(path.join(directory,'probe.json'))?JSON.parse(fs.readFileSync(path.join(directory,'probe.json'))):{};
  if(mode==='cap-control')assert.equal(calls[0].max_tokens,90000);
  if(mode==='thinking-control'){assert.equal(calls[0].reasoning_effort,'low');assert.match(failure.message,/native thinking payload changed/);}
  if(mode==='stop-control')assert.ok(record.requests>1||ledger.attempts>1,'disabled stop must attempt continuation');
  if(mode==='retry-control'){assert.ok(ledger.attempts>1,'disabled retries must attempt recovery');assert.equal(ledger.error,'single-dispatch limit');}
  if(mode==='redirect'){assert.equal(ledger.attempts,1);assert.equal(record.error,'incomplete provider response');}
  if(mode==='truncated')assert.equal(record.error,'incomplete provider response');
  if(mode==='fixture-error')assert.equal(record.error,'unrelated or repeated top-level tool');
  if(mode==='missing-probe')assert.equal(record.complete,false);
  if(mode==='timeout'){const state=JSON.parse(fs.readFileSync(path.join(directory,'preservation.json')));assert.equal(state.outcome.timedOut,true);assert.equal(state.outcome.cleanup,true);}
  console.log(JSON.stringify({platform:process.platform,mode,rejected:true,dispatches:ledger.dispatches,attempts:ledger.attempts,reason:failure.message}));
 }
}catch(err){console.error(err.message);process.exitCode=1;}
