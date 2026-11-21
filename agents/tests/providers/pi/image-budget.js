import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import {once} from 'node:events';
import {spawn} from 'node:child_process';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {deflateSync,crc32} from 'node:zlib';
import {acquireImageEngine,imageEngine,removeImageEngines} from '../../../providers/pi/runtime/image-engine.js';
import {launchBounded} from './live.js';

const cli=path.resolve(process.argv[2]);
const nativeRoot=path.resolve(path.dirname(cli),'../..');
assert.equal(JSON.parse(fs.readFileSync(path.join(nativeRoot,'package.json'))).version,'1.5.2');
const {SessionManager}=await import(pathToFileURL(path.join(nativeRoot,'dist/core/session-manager.js')));
const {normalizeToolResultImages}=await import(pathToFileURL(path.join(nativeRoot,'dist/utils/tool-result-images.js')));
const scratch=fileURLToPath(new URL('../../../../tmp/',import.meta.url));
const root=fs.mkdtempSync(path.join(scratch,'pi-budget-'));
const plugin=fileURLToPath(new URL('../../../providers/pi/plugins/image-budget.ts',import.meta.url));
const agent=path.join(root,'Profile fixture 数据','agent');
fs.mkdirSync(agent,{recursive:true});
const model='budget-vision',otherModel='budget-alternate',provider='budget-fixture';
const requests=[];
let scenario,engine;

function image(seed,width=128,height=128,level=0) {
  const chunk=(type,data)=>{
    const header=Buffer.alloc(8),crc=Buffer.alloc(4);
    header.writeUInt32BE(data.length);header.write(type,4);
    crc.writeUInt32BE(crc32(Buffer.concat([header.subarray(4),data]))>>>0);
    return Buffer.concat([header,data,crc]);
  };
  const header=Buffer.alloc(13);
  header.writeUInt32BE(width);header.writeUInt32BE(height,4);header[8]=8;header[9]=2;
  const raw=Buffer.alloc((width*3+1)*height);
  for(let i=0;i<raw.length;i++) if(i%(width*3+1)!==0)raw[i]=(seed+i)%256;
  return {type:'image',mimeType:'image/png',data:Buffer.concat([
    Buffer.from('89504e470d0a1a0a','hex'),chunk('IHDR',header),
    chunk('IDAT',deflateSync(raw,{level})),chunk('IEND',Buffer.alloc(0)),
  ]).toString('base64')};
}

const server=http.createServer(async(req,res)=>{
  const chunks=[];
  for await (const chunk of req)chunks.push(chunk);
  const body=Buffer.concat(chunks),request=JSON.parse(body);
  const summary=request.messages.some(m=>typeof m.content==='string' && m.content.includes('You are a context summarization assistant'));
  const images=request.messages.flatMap(m=>Array.isArray(m.content)?m.content.filter(p=>p.type==='image_url').map(p=>p.image_url.url):[]);
  const first=requests.length===0;
  const gatewayLimit = scenario.startsWith('large') ? 48*1024**2 : 240000;
  const countCap = scenario==='count-overflow' ? 20 : Infinity;
  let status=200,message,code;
  if (!summary) {
    if (first && scenario==='token') {
      status=400; message='Input exceeds the maximum context length of 100000 tokens'; code='context_length_exceeded';
    } else if (scenario==='ambiguous') {
      status=503; message='Temporary provider failure'; code='unavailable';
    } else if (images.length>countCap) {
      status=400; message=`Too many images; maximum of ${countCap} images`; code='invalid_request';
    } else if (body.length>gatewayLimit || scenario==='repeated-413') {
      status=413; message='Request exceeds the maximum size'; code='request_too_large';
    }
  }
  requests.push({bytes:body.length,summary,images,status,model:request.model});
  if(status!==200){
    res.writeHead(status,{'content-type':'application/json'}).end(JSON.stringify({
      error:{message,code},
    }));
    return;
  }
  const chunk=(delta,finish_reason,usage)=>'data: '+JSON.stringify({
    id:'budget',object:'chat.completion.chunk',created:0,model:request.model,choices:[{index:0,delta,finish_reason}],
    usage,
  })+'\n\n';
  const usage=scenario==='threshold' && !summary ? {prompt_tokens:99980,completion_tokens:1,total_tokens:99981} : undefined;
  res.writeHead(200,{'content-type':'text/event-stream'}).end(chunk({content:'fixture answer'},null)+chunk({},'stop',usage)+'data: [DONE]\n\n');
});
server.listen(0,'127.0.0.1');
await once(server,'listening');
const baseUrl=`http://127.0.0.1:${server.address().port}`;
fs.writeFileSync(path.join(agent,'models.json'),JSON.stringify({
  providers:{[provider]:{baseUrl,api:'openai-completions',apiKey:'synthetic-image-budget',
    models:[model,otherModel].map(id=>({id,name:id,input:['text','image'],contextWindow:100000,maxTokens:1024}))}},
}));

function seed(includeImages=true,turns=4,createImage=image,unfinished=[]) {
  const session=SessionManager.create(root,path.join(root,'sessions'));
  session.appendModelChange(provider,model);
  for(let i=1;i<=turns;i++){
    session.appendMessage({role:'user',timestamp:i*10,content:[{type:'text',text:`retained text ${i}`},...(includeImages?[createImage(i)]:[])]});
    session.appendMessage({role:'assistant',timestamp:i*10+1,content:[{type:'text',text:'done'}],api:'openai-completions',
      provider,model,stopReason:'stop',usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}});
  }
  if (unfinished.length) session.appendMessage({role:'user',timestamp:995,
    content:[{type:'text',text:'Current screenshots awaiting an answer'},...unfinished]});
  return session.getSessionFile();
}

async function runRpc(args,env,streamFile,commands) {
  const child=spawn(process.execPath,args,{cwd:root,env,stdio:['pipe','pipe','pipe'],windowsHide:true});
  const timer=setTimeout(()=>child.kill(),25000);
  let output='',diagnostics='',cursor=0,index=-1,waitingForTurn=false;
  const next=()=>{
    const command=commands[++index];
    waitingForTurn=false;
    if (command) child.stdin.write(JSON.stringify({...command,id:String(index)})+'\n');
    else child.stdin.end();
  };
  child.stdout.setEncoding('utf8');
  child.stdout.on('data',part=>{
    output+=part;
    for (let end; (end=output.indexOf('\n',cursor))>=0; cursor=end+1) {
      const line=output.slice(cursor,end);
      if (child.stdin.writableEnded || !line.startsWith('{')) continue;
      const event=JSON.parse(line);
      if (event.type==='response' && event.id===String(index)) {
        if (!event.success) child.stdin.end();
        else if (commands[index].type==='prompt') waitingForTurn=true;
        else next();
      } else if (event.type==='agent_settled' && waitingForTurn) next();
    }
  });
  child.stderr.setEncoding('utf8');
  child.stderr.on('data',part=>diagnostics+=part);
  child.stdin.on('error',error=>diagnostics+=error.message);
  next();
  try {
    const [code]=await once(child,'close');
    fs.writeFileSync(streamFile,output);
    assert.equal(index,commands.length,diagnostics+output);
    return {code,timedOut:code===null};
  } finally {clearTimeout(timer);}
}

async function run(name, options, {keepRecentTokens=128, file=seed(), expectedPrompt='continue with the screenshots', mode='json', commands=[{type:'compact'}]}={}) {
  scenario=name;requests.length=0;
  fs.writeFileSync(path.join(agent,'settings.json'),JSON.stringify({
    retry:{enabled:true,maxRetries:1,provider:{maxRetries:1,timeoutMs:3000}},
    compaction:{enabled:true,keepRecentTokens},
    cacheWarming:'off',enableInstallTelemetry:false,
  }));
  const before=fs.readFileSync(file,'utf8').trimEnd().split('\n');
  const streamFile=path.join(root,name+'.log');
  const env=Object.fromEntries(Object.entries(process.env).filter(([key])=>/^(?:PATH|SystemRoot|windir|ComSpec|PATHEXT)$/i.test(key)));
  Object.assign(env,{HOME:root,USERPROFILE:root,APPDATA:root,LOCALAPPDATA:root,TMP:root,TEMP:root,TMPDIR:root,
    PI_CODING_AGENT_DIR:agent,PI_OFFLINE:'1',PI_TELEMETRY:'0'});
  if(options)env.PI_SOT_PLUGINS=JSON.stringify({route:{provider,id:model,api:'openai-completions',baseUrl},profile:'fixture',engine,plugins:{'image-budget':options}});
  const args=[
    cli,'--provider',provider,'--model',model,'--session',file,'--no-mcp','--no-tools',...(mode==='text'?['-p']:['--mode',mode]),
    ...(options?['-e',plugin]:[]),...(mode==='rpc'?[]:[expectedPrompt]),
  ];
  const result=mode==='rpc' ? await runRpc(args,env,streamFile,commands)
    : await launchBounded(process.execPath,args,{cwd:root,env,streamFile,timeoutMs:25000});
  const output=fs.readFileSync(streamFile,'utf8');
  assert.equal(result.timedOut,false,output);
  assert.equal(result.code,0,output);
  const lines=fs.readFileSync(file,'utf8').trimEnd().split('\n');
  assert.deepEqual(lines.slice(0,before.length),before,'saved original history must remain byte-identical');
  const entries=lines.slice(before.length).map(JSON.parse);
  const events=output.split('\n').filter(line=>line.startsWith('{')).map(JSON.parse);
  return {file,requests:requests.slice(),entries,events,output};
}

const limits={maxRequestBytes:600000,maxImages:20,compress:false,protectRecent:1};
const results={};
try {
  engine=await acquireImageEngine(agent,root,cli);
  assert.equal(await acquireImageEngine(agent,root,cli),engine);
  assert.ok(!fs.existsSync(path.join(agent,'settings.json')),'native SDK acquisition must not register the upstream entrypoint');
  if(process.argv.includes('--large')){
    const largeImage=index=>image(index,1024,1200);
    const largeLimits={...limits,maxRequestBytes:40*1024**2,maxInlineImageBytes:32*1024**2};
    const control=await run('large-control',null,{file:seed(true,11,largeImage),mode:'text'});
    assert.equal(control.requests[0].status,413);
    assert.ok(control.requests[0].bytes>48*1024**2);
    const guarded=await run('large-guard',largeLimits,{file:seed(true,11,largeImage),mode:'text'});
    assert.deepEqual(guarded.requests.map(r=>r.status),[200]);
    assert.ok(guarded.requests[0].bytes<largeLimits.maxRequestBytes);
    results.largeBoundary=[control.requests[0].bytes,guarded.requests[0].bytes];
    const singleLimits={...largeLimits,maxRequestBytes:48*1024**2,maxImageDimension:8192};
    const below=image(1,4096,2730), above=image(1,4096,2731);
    assert.ok(Buffer.from(below.data,'base64').length<singleLimits.maxInlineImageBytes);
    assert.ok(Buffer.from(above.data,'base64').length>singleLimits.maxInlineImageBytes);
    const small=await run('large-inline-below',singleLimits,{file:seed(true,1,()=>below),mode:'text'});
    assert.equal(small.requests[0].images.length,1);
    assert.ok(small.requests[0].images[0]==='data:image/png;base64,'+below.data,'an inline image just below 32 MiB should survive unchanged');
    const big=await run('large-inline-above',singleLimits,{file:seed(true,1,()=>above),mode:'text'});
    assert.equal(big.requests[0].images.length,1);
    const decoded=Buffer.from(big.requests[0].images[0].split(',')[1],'base64');
    assert.ok(decoded.length<=singleLimits.maxInlineImageBytes);
    results.inlineBoundary=[Buffer.from(below.data,'base64').length,decoded.length];
  }

  if(process.argv.includes('--red')){
    const baseline=await run('image-overflow',null);
    assert.equal(baseline.requests[0]?.status,413);
    assert.ok(baseline.requests.some(r=>r.summary),'known-bad baseline must really dispatch a summary');
    assert.ok(baseline.entries.some(e=>e.type==='compaction'),'known-bad baseline must persist compaction');
    assert.equal(baseline.requests.filter(r=>r.summary).length,0,'ordinary Pi compacts instead of recovering by image reduction');
  }
  const recovery=await run('image-overflow',limits);
  assert.deepEqual(recovery.requests.map(r=>r.status),[413,200],recovery.output);
  assert.ok(recovery.requests[0].images.length>recovery.requests[1].images.length);
  assert.ok(recovery.requests[0].bytes>recovery.requests[1].bytes);
  assert.ok(recovery.requests[1].images.includes('data:image/png;base64,'+image(4).data));
  assert.equal(recovery.requests.filter(r=>r.summary).length,0);
  assert.equal(recovery.entries.filter(e=>e.type==='compaction').length,0);
  assert.equal(recovery.entries.filter(e=>e.type==='context_edit').length,1,'reuse the native failed-attempt omission');
  assert.equal(recovery.entries.filter(e=>e.type==='custom'&&e.customType==='genosai-image-budget').length,1);
  results.recovery=recovery.requests.map(({status,bytes})=>({status,bytes}));
  const resumed=await run('resumed',limits,{file:recovery.file});
  assert.deepEqual(resumed.requests.map(r=>r.status),[200],resumed.output);
  assert.ok(resumed.requests[0].bytes<240000);
  results.resumedRequests=resumed.requests.length;
  const short=await run('short',limits,{keepRecentTokens:99999});
  assert.deepEqual(short.requests.map(r=>r.status),[413,200],short.output);
  assert.equal(short.entries.filter(e=>e.type==='context_edit').length,1);
  const repeated=await run('repeated-413',limits);
  const rejected=repeated.requests.filter(r=>!r.summary);
  assert.ok(rejected.length>=2 && rejected.every(r=>r.status===413),repeated.output);
  assert.ok(rejected[1].bytes<rejected[0].bytes);
  assert.equal(repeated.output.split('retrying once with a smaller request').length-1,1,repeated.output);
  assert.equal(repeated.entries.some(e=>e.type==='custom'&&e.customType==='genosai-image-budget'),false);
  const token=await run('token',limits);
  assert.equal(token.requests[0]?.status,400,token.output);
  assert.ok(token.requests.some(r=>r.summary),token.output);
  assert.ok(token.entries.some(e=>e.type==='compaction'),token.output);
  assert.equal(token.entries.filter(e=>e.type==='custom'&&e.customType==='genosai-image-budget').length,0);
  results.tokenSummaryRequests=token.requests.filter(r=>r.summary).length;
  const refusal=await run('refusal',{...limits,maxRequestBytes:32},{file:seed(false)});
  assert.equal(refusal.requests.length,0,refusal.output);
  assert.ok(refusal.events.some(e=>e.type==='agent_settled' && e.aborted),refusal.output);
  results.refusedRequests=refusal.requests.length;
  const count=await run('count',{...limits,maxImages:2});
  assert.equal(count.requests.length,1,count.output);
  assert.ok(count.requests[0].images.length<=2);
  assert.ok(count.requests[0].images.includes('data:image/png;base64,'+image(4).data));
  results.imageCount=count.requests[0].images.length;
  const tiny=index=>image(index,1,1,6);
  const threshold=await run('threshold',limits,{file:seed(true,4,tiny)});
  assert.ok(threshold.requests.some(r=>r.summary),threshold.output);
  assert.ok(threshold.entries.some(e=>e.type==='compaction'),threshold.output);
  const manual=await run('manual',limits,{mode:'rpc',file:seed(true,4,tiny)});
  assert.deepEqual(manual.requests.map(r=>r.summary),[true],manual.output);
  assert.ok(manual.entries.some(e=>e.type==='compaction'),manual.output);
  results.normalCompaction={threshold:threshold.requests.filter(r=>r.summary).length,manual:manual.requests.length};
  const switched=await run('model-switch',{...limits,maxRequestBytes:32},{mode:'rpc',file:seed(true,4,tiny),commands:[
    {type:'set_model',provider,modelId:otherModel},{type:'prompt',message:'Ask the alternate model'},
    {type:'set_model',provider,modelId:model},{type:'prompt',message:'Ask the budgeted model'},
  ]});
  assert.deepEqual(switched.requests.map(r=>r.model),[otherModel],switched.output);
  assert.deepEqual(switched.events.filter(e=>e.type==='agent_settled').map(e=>e.aborted),[false,true],switched.output);
  for(const cap of [8,20,30]) {
    const boundary=await run('count-boundary-'+cap,{...limits,maxImages:cap},{file:seed(true,cap,tiny)});
    assert.deepEqual(boundary.requests.map(r=>r.images.length),[cap]);
    const capped=await run('count-'+cap,{...limits,maxImages:cap},{file:seed(true,cap+5,tiny)});
    assert.equal(capped.requests.length,1);
    assert.ok(capped.requests[0].images.length>0 && capped.requests[0].images.length<=cap);
  }
  const countRecovery=await run('count-overflow',{...limits,maxImages:30},{file:seed(true,25,tiny)});
  assert.deepEqual(countRecovery.requests.map(r=>r.status),[400,200],countRecovery.output);
  assert.equal(countRecovery.requests[0].images.length,25);
  assert.ok(countRecovery.requests[1].images.length>0 && countRecovery.requests[1].images.length<=20);
  results.countRecovery=countRecovery.requests.map(r=>r.images.length);
  const ambiguous=await run('ambiguous',limits,{file:seed(true,4,tiny)});
  assert.ok(ambiguous.requests.length>0);
  assert.ok(ambiguous.requests.every(r=>r.status===503 && r.images.length===4));
  assert.doesNotMatch(ambiguous.output,/retrying once with a smaller request/);
  assert.equal(ambiguous.entries.some(e=>e.type==='custom'&&e.customType==='genosai-image-budget'),false);
  results.ambiguous503Requests=ambiguous.requests.length;
  const currentImages=[tiny(71),tiny(72)];
  const current=await run('current-images',{...limits,maxImages:2,protectRecent:0},
    {file:seed(true,4,tiny,currentImages)});
  assert.deepEqual(current.requests.map(r=>r.images),[currentImages.map(part=>'data:image/png;base64,'+part.data)]);
  const overCount=await run('protected-count',{...limits,maxImages:2,protectRecent:0},
    {file:seed(true,4,tiny,[...currentImages,tiny(73)])});
  assert.equal(overCount.requests.length,0,overCount.output);
  assert.ok(overCount.events.some(e=>e.type==='agent_settled' && e.aborted),overCount.output);
  results.unansweredImages=current.requests[0].images.length;
  const perImage=await run('per-image',{...limits,maxInlineImageBytes:1});
  assert.equal(perImage.requests.length,0,perImage.output);
  assert.ok(perImage.events.some(e=>e.type==='agent_settled' && e.aborted),perImage.output);
  results.invalidProtectedImageRequests=perImage.requests.length;
  const panoramic=image(1,4097,1,6);
  const makeDenseImage=index=>index===1 ? panoramic : image(index,1,1,6);
  const denseLimits={...limits,maxImageDimension:8192,denseImageCount:15,denseImageDimension:4096};
  const sparse=await run('sparse',denseLimits,{file:seed(true,14,makeDenseImage)});
  assert.equal(sparse.requests[0].images.length,14);
  assert.ok(sparse.requests[0].images.includes('data:image/png;base64,'+panoramic.data));
  const dense=await run('dense',denseLimits,{file:seed(true,15,makeDenseImage)});
  assert.equal(dense.requests[0].images.length,15);
  assert.ok(!dense.requests[0].images.includes('data:image/png;base64,'+panoramic.data),'the dense route must resize panoramas above its per-image limit');
  results.denseBoundary=[sparse.requests[0].images.length,dense.requests[0].images.length];
  const panoramicAtLimit=image(1,8192,1,6), oversizedPanoramic=image(1,8193,1,6);
  const dimension=await run('dimension',denseLimits,{file:seed(true,2,index=>index===1 ? panoramicAtLimit : oversizedPanoramic)});
  assert.equal(dimension.requests[0].images.length,2);
  assert.ok(dimension.requests[0].images.includes('data:image/png;base64,'+panoramicAtLimit.data));
  assert.ok(!dimension.requests[0].images.includes('data:image/png;base64,'+oversizedPanoramic.data));
  const corrupt={...oversizedPanoramic,data:Buffer.from(oversizedPanoramic.data,'base64').subarray(0,33).toString('base64')};
  const retainedResult=await normalizeToolResultImages([corrupt]);
  assert.deepEqual(retainedResult,[corrupt],'Pi retains the original tool image when native processing fails');
  const toolSession=SessionManager.open(seed(false,1));
  toolSession.appendMessage({role:'user',timestamp:994,content:[{type:'text',text:'Capture a fixture image'}]});
  toolSession.appendMessage({role:'assistant',timestamp:995,api:'openai-completions',provider,model,stopReason:'toolUse',
    content:[{type:'toolCall',id:'call_fixture',name:'fixture_image',arguments:{}}],
    usage:{input:1,output:1,cacheRead:0,cacheWrite:0,totalTokens:2,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}}});
  toolSession.appendMessage({role:'toolResult',timestamp:996,toolCallId:'call_fixture',toolName:'fixture_image',content:retainedResult,isError:false});
  const failedResize=await run('failed-resize',denseLimits,{file:toolSession.getSessionFile()});
  assert.equal(failedResize.requests.length,0,failedResize.output);
  assert.ok(failedResize.events.some(e=>e.type==='agent_settled' && e.aborted),failedResize.output);
  const marker=path.join(agent,'.agents-sot-image-budget','unrelated');
  fs.writeFileSync(marker,'preserve');
  const modified=path.join(engine,'src','errors.ts'),original=fs.readFileSync(modified);
  fs.appendFileSync(modified,'// tampered fixture');
  assert.throws(()=>imageEngine(agent,root),/differs from the pinned source/);
  assert.throws(()=>removeImageEngines(agent,root),/differs from the pinned source/);
  assert.equal(fs.readFileSync(marker,'utf8'),'preserve');
  fs.writeFileSync(modified,original);
  removeImageEngines(agent,root);
  assert.equal(fs.existsSync(engine),false);
  assert.equal(fs.readFileSync(marker,'utf8'),'preserve');
  console.log(JSON.stringify({platform:process.platform,...results,driftRefused:true}));
} finally {
  server.closeAllConnections();
  await new Promise(resolve=>server.close(resolve));
  fs.rmSync(root,{recursive:true,force:true});
}
