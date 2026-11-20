import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {configure} from '../../../providers/pi/runtime/configure.js';

const cli=path.resolve(process.argv[2]);
const control=process.argv[3]==='unprojected-control';
assert.ok(process.argv[3]===undefined||control,'unknown catalog control');
const packageDir=path.resolve(path.dirname(cli),'../..');
const require=createRequire(path.join(packageDir,'package.json'));
const aiDir=require.resolve.paths('@earendil-works/pi-ai').map(base=>path.join(base,'@earendil-works/pi-ai')).find(candidate=>fs.existsSync(path.join(candidate,'package.json')));
assert.ok(aiDir,'installed native capability dependency required');
const aiIndex=path.join(aiDir,'dist/index.js');
const {ModelRuntime}=await import(pathToFileURL(path.join(packageDir,'dist/core/model-runtime.js')));
const {getSupportedThinkingLevels}=await import(pathToFileURL(aiIndex));
const catalog=JSON.parse(fs.readFileSync(path.join(aiDir,'dist/providers/data/deepseek.json'),'utf8'));
const bundled=Object.values(catalog).flatMap(group=>Object.values(group)).find(model=>model.id==='deepseek-flash');
assert.ok(bundled,'installed catalog must contain the selected native model');
const descriptor=fs.readFileSync(new URL('../../../lifecycle/providers.conf.sh',import.meta.url),'utf8');
const expected=/^PI_PACKAGE='[^']*@([^']+)'/m.exec(descriptor)[1];
assert.equal(JSON.parse(fs.readFileSync(path.join(packageDir,'package.json'),'utf8')).version,expected,'acceptance must use the managed runtime pin');
const scratch=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../../../tmp');
const root=fs.mkdtempSync(path.join(scratch,'pi-catalog-'));
const nativeFetch=globalThis.fetch;
let unexpectedNetwork=0,catalogRequests=0,catalogResponse;
globalThis.fetch=async(input,init)=>{
 const url=new URL(typeof input==='string'||input instanceof URL?String(input):input.url);
 const method=(init?.method??input.method??'GET').toUpperCase();
 if(catalogResponse&&method==='GET'&&url.origin==='https://pi.dev'&&url.pathname==='/api/models/providers/deepseek') {
  catalogRequests++;
  return new Response(JSON.stringify([catalogResponse]),{headers:{'content-type':'application/json','last-modified':'Thu, 01 Jan 2099 00:00:00 GMT'}});
 }
 unexpectedNetwork++;throw Error('catalog acceptance forbids network');
};
const results=[];

try {
 fs.mkdirSync(path.join(root,'secrets'));
 fs.writeFileSync(path.join(root,'secrets/synthetic.key'),'synthetic-catalog-key');
 for(const endpoint of ['', 'http://127.0.0.1:43210/v1']) {
  const base=path.join(root,endpoint?'override':'native');
  const profiles={active:'selected',profiles:{selected:{provider:'deepseek',model:bundled.id,credential:'secrets/synthetic.key',thinking:'max',...(endpoint?{endpoint}:{})}}};
  const {agentDir:dir}=await configure({op:'install',root,dir:base,profiles,cli,expected,profileScope:true});
  const modelsFile=path.join(dir,'models.json');
  if(control&&fs.existsSync(modelsFile)) {
   const data=JSON.parse(fs.readFileSync(modelsFile,'utf8'));
   delete data.providers.deepseek.models;
   if(Object.keys(data.providers.deepseek).length===0)delete data.providers.deepseek;
   fs.writeFileSync(modelsFile,JSON.stringify(data));
  }
  const poisoned={...bundled,baseUrl:'https://broker.example.invalid/v1',thinkingLevelMap:{...bundled.thinkingLevelMap,max:null}};
  fs.writeFileSync(path.join(dir,'models-store.json'),JSON.stringify({deepseek:{models:[poisoned],lastModified:8640000000000000,checkedAt:Date.now()}}));
  // Ordinary startup restores cached catalogs even with network refresh disabled.
  const runtime=await ModelRuntime.create({authPath:path.join(dir,'auth.json'),modelsPath:modelsFile,allowModelNetwork:false});
  assert.equal(runtime.getError(),undefined);
  for(const phase of ['cached','refreshed']) {
   if(phase==='refreshed') {
    const before=catalogRequests;catalogResponse=poisoned;
    const refreshed=await runtime.refresh({providers:['deepseek'],allowNetwork:true,force:true});
    catalogResponse=undefined;
    assert.equal(refreshed.errors.size,0);
    assert.equal(catalogRequests,before+1,'refresh must consume the synthetic remote catalog');
   }
   const effective=runtime.getModel('deepseek',bundled.id);
   const requests=[];
   const fetch=async(input,init)=>{
    const url=typeof input==='string'||input instanceof URL?String(input):input.url;
    const payload=JSON.parse(init.body);requests.push({url,effort:payload.reasoning_effort});
    const chunk=(delta,finish_reason)=>'data: '+JSON.stringify({id:'catalog-test',object:'chat.completion.chunk',created:0,model:payload.model,choices:[{index:0,delta,finish_reason}]})+'\n\n';
    return new Response(chunk({role:'assistant',content:'ok'},null)+chunk({},'stop')+'data: [DONE]\n\n',{headers:{'content-type':'text/event-stream'}});
   };
   const response=await runtime.completeSimple(effective,{messages:[{role:'user',content:'synthetic',timestamp:0}]},{reasoning:'max',maxTokens:100,maxRetries:0,fetch});
   assert.equal(response.stopReason,'stop',response.errorMessage);
   const intended=endpoint||bundled.baseUrl;
   const matches=effective.baseUrl===intended&&effective.api===bundled.api&&getSupportedThinkingLevels(effective).includes('max')&&requests.length===1&&requests[0].url===intended.replace(/\/$/,'')+'/chat/completions'&&requests[0].effort==='max';
   if(control) {
    assert.equal(matches,false,'unprojected control must expose the catalog mismatch');
    assert.equal(getSupportedThinkingLevels(effective).includes('max'),false,'control must restore the poisoned capability');
    assert.equal(requests[0].effort,'high','control must reach native transport with clamped effort');
   } else assert.equal(matches,true,'effective endpoint and native effort must match validated SOT metadata');
   results.push({phase,endpoint:intended,request:requests[0],controlRejected:control});
  }
 }
 assert.equal(unexpectedNetwork,0);
 console.log(JSON.stringify({platform:process.platform,version:expected,mode:control?'unprojected-control':'normal',networkRequests:unexpectedNetwork,syntheticCatalogRequests:catalogRequests,results}));
} finally {
 globalThis.fetch=nativeFetch;
 fs.rmSync(root,{recursive:true,force:true});
}
