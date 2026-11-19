import test from 'node:test';
import {spawn} from 'node:child_process';
import {identity,terminated} from './process.js';
import {endGeneration,acceptanceModel,redactEvidence} from './session.js';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import probe,{requestLimit,thinkingFields} from './probe.js';
import {launchBounded,verifyProbe,costEvidenceSource} from './live.js';
const scratch=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../../../tmp');
test('request cap and explicit cancellation',()=>{
 let calls=0;const ctx={abort:()=>calls++,shutdown:()=>calls++};
 const first=requestLimit({messages:[],max_tokens:90000},1,ctx);assert.equal(first.payload.max_tokens,2048);
 assert.equal(requestLimit({messages:[]},2,ctx).valid,false);assert.equal(calls,2);
 assert.equal(requestLimit({},1,ctx).valid,false);
});
test('cost evidence distinguishes provider totals from catalog estimates',()=>{
 assert.match(costEvidenceSource({cost:{totalFromProvider:true}}),/provider-reported/);
 assert.match(costEvidenceSource({cost:{totalFromProvider:false}}),/catalog estimate/);
});
test('acceptance disables native OpenRouter fallback without mutating model metadata',()=>{
 const original={compat:{thinkingFormat:'openrouter',openRouterRouting:{order:['fixture'],allow_fallbacks:true}}};
 const bounded=acceptanceModel(original);
 assert.deepEqual(bounded.compat.openRouterRouting,{order:['fixture'],allow_fallbacks:false});
 assert.equal(original.compat.openRouterRouting.allow_fallbacks,true);
 const direct={compat:{thinkingFormat:'openai'}};assert.equal(acceptanceModel(direct),direct);
});
test('acceptance redacts credential-shaped strings before event and session logging',()=>{
 const item={errorMessage:'sk-synthetic-fixture and '+'0'.repeat(32)+'.SYNTHETIC',note:'task-specific evidence',usage:{input:10}};
 assert.deepEqual(redactEvidence(item),{errorMessage:'[redacted] and [redacted]',note:'task-specific evidence',usage:{input:10}});
 assert.notEqual(item.errorMessage,redactEvidence(item).errorMessage);
});
test('acceptance token cap preserves native thinking fields',()=>{
 const payload={messages:[],max_tokens:90000,thinking:{type:'enabled'},reasoning_effort:'max',output_config:{effort:'high'}};
 const result=requestLimit(payload,1,{abort(){},shutdown(){}});
 assert.deepEqual(result.payload,{...payload,max_tokens:2048});
});
test('thinking evidence includes native OpenRouter reasoning',()=>{
 const payload={messages:[],reasoning:{effort:'high'}};
 assert.deepEqual(thinkingFields(payload),{reasoning:{effort:'high'}});
});
test('single-use probe refuses repeated and unrelated top-level tools',async t=>{
 const dir=fs.mkdtempSync(path.join(scratch,'pi-probe-fixture-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
 process.env.PI_PROBE_RECORD=path.join(dir,'record.json');const handlers={},tools=[];
 probe({on:(name,fn)=>handlers[name]=fn,registerTool:tool=>tools.push(tool)});
 const ctx={executeTool:async(name,args)=>({isError:!(name==='bash'&&args.command==='git status --short')&&!(name==='read'&&args.path==='README.md')&&!(name==='write'&&args.path==='scratch/ok.txt'),content:[]}),abort(){},shutdown(){}};
 handlers.before_provider_request({payload:{messages:[]}},ctx);
 await tools[0].execute('id',{},null,null,ctx);
 await assert.rejects(()=>tools[0].execute('id2',{},null,null,ctx),/already used/);
 assert.equal(handlers.tool_call({toolName:'bash'}).block,true);
 delete process.env.PI_PROBE_RECORD;
});
test('launcher deadline and incomplete evidence refusal',async t=>{
 const dir=fs.mkdtempSync(path.join(scratch,'pi-deadline-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
 const stream=path.join(dir,'events.jsonl');
 const result=await launchBounded(process.execPath,['-e','setInterval(()=>{},1000)'],{cwd:dir,env:process.env,timeoutMs:200,streamFile:stream});
 assert.equal(result.timedOut,true);
 assert.equal(result.cleanup,true);
 fs.writeFileSync(path.join(dir,'probe.json'),'{}');assert.throws(()=>verifyProbe(path.join(dir,'probe.json'),stream),/incomplete/);
});
test('native evidence rejects an extra assistant generation',t=>{
 const dir=fs.mkdtempSync(path.join(scratch,'pi-extra-turn-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
 const cases=Array.from({length:process.platform==='win32'?12:11},(_,i)=>({tool:i<3?['bash','read','write'][i]:'bash',isError:i>=3}));
 const record=path.join(dir,'probe.json'),stream=path.join(dir,'events.jsonl');
 fs.writeFileSync(record,JSON.stringify({complete:true,requests:1,outputCap:2048,cases}));
 fs.writeFileSync(path.join(dir,'transport.json'),JSON.stringify({attempts:1,dispatches:1,requests:[{max_tokens:2048}],stopDecisions:1}));
 const events=[{type:'message_end',message:{role:'assistant',stopReason:'toolUse',content:[{type:'toolCall',name:'guard_probe'}]}},{type:'message_end',message:{role:'toolResult',toolName:'guard_probe',nestedCalls:{complete:true,calls:cases.map(c=>({name:c.tool,status:c.isError?'error':'ok',...(c.isError?{error:'guard blocked'}:{})}))}}},{type:'message_end',message:{role:'assistant',stopReason:'stop',content:[]}}];
 fs.writeFileSync(stream,events.map(e=>JSON.stringify(e)).join('\n'));
 assert.throws(()=>verifyProbe(record,stream),/generation/);
});
test('native evidence rejects altered OpenRouter effort',t=>{
 const dir=fs.mkdtempSync(path.join(scratch,'pi-reasoning-evidence-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
 const cases=Array.from({length:process.platform==='win32'?12:11},(_,i)=>({tool:i<3?['bash','read','write'][i]:'bash',isError:i>=3}));
 const record=path.join(dir,'probe.json'),stream=path.join(dir,'events.jsonl');
 const nativeThinking=thinkingFields({reasoning:{effort:'high'}});
 fs.writeFileSync(record,JSON.stringify({complete:true,requests:1,outputCap:2048,cases,nativeThinking,thinkingLevel:'high',absentTarget:path.join(dir,'absent')}));
 const response={status:200,modelObserved:true,modelMatches:true};
 const transport={attempts:1,dispatches:1,requests:[{max_tokens:2048,nativeThinking}],stopDecisions:1,response};
 const save=()=>fs.writeFileSync(path.join(dir,'transport.json'),JSON.stringify(transport));save();
 const events=[{type:'message_end',message:{role:'assistant',stopReason:'toolUse',content:[{type:'toolCall',name:'guard_probe'}]}},{type:'message_end',message:{role:'toolResult',toolName:'guard_probe',nestedCalls:{complete:true,calls:cases.map(c=>({name:c.tool,status:c.isError?'error':'ok',...(c.isError?{error:'guard blocked'}:{})}))}}}];
 fs.writeFileSync(stream,events.map(e=>JSON.stringify(e)).join('\n'));
 assert.doesNotThrow(()=>verifyProbe(record,stream,process.platform,'high'));
 delete transport.response;save();
 assert.throws(()=>verifyProbe(record,stream,process.platform,'high'),/provider response status or model mismatch/);
 transport.response={...response,modelMatches:false,modelMismatch:true};save();
 assert.throws(()=>verifyProbe(record,stream,process.platform,'high'),/provider response status or model mismatch/);
 transport.response=response;
 transport.requests[0].nativeThinking=thinkingFields({reasoning:{effort:'low'}});save();
 assert.throws(()=>verifyProbe(record,stream,process.platform,'high'),/native thinking payload changed/);
});

test('SDK stop preserves native boundary persistence first',async()=>{
 const sequence=[];const agent={finishTurn:async()=>{sequence.push('native');return {action:'continue'};}};
 endGeneration(agent,()=>sequence.push('stop'));
 assert.deepEqual(await agent.finishTurn({},null),{action:'end'});
 assert.deepEqual(sequence,['native','stop']);
});
test('cleanup observer rejects a surviving process generation',async()=>{
 const child=spawn(process.execPath,['-e','setInterval(()=>{},1000)'],{stdio:'ignore'});
 await new Promise((resolve,reject)=>{child.once('spawn',resolve);child.once('error',reject);});
 const generation=identity(child.pid);const closed=new Promise(resolve=>child.once('close',resolve));
 try {assert.throws(()=>terminated(child.pid,generation),/survived/);}
 finally {child.kill();await closed;}
 terminated(child.pid,generation);
});
