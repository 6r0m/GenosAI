import fs from 'node:fs';
import path from 'node:path';
import {randomUUID} from 'node:crypto';

export function requestLimit(payload,count,ctx) {
  if(count!==1||!payload||typeof payload!=='object'||!Array.isArray(payload.messages)) {
    ctx.abort();ctx.shutdown();return {payload,valid:false};
  }
  return {payload:{...payload,max_tokens:2048},valid:true};
}
export function thinkingFields(payload) {
  return Object.fromEntries(['thinking','reasoning','reasoning_effort','output_config'].filter(key=>payload?.[key]!==undefined).map(key=>[key,payload[key]]));
}
export default function(pi) {
  let used=false,requests=0,failed=false,inProbe=false;
  const record=process.env.PI_PROBE_RECORD;
  if(!record)throw Error('PI_PROBE_RECORD required for bounded acceptance fixture');
  const evidence={requests:0,outputCap:2048,cases:[],complete:false};
  const save=()=>fs.writeFileSync(record,JSON.stringify(evidence,null,2));
  const refuse=(ctx,reason)=>{failed=true;evidence.error=reason;save();ctx.abort();ctx.shutdown();};
  pi.on('before_provider_request',(event,ctx)=>{
    requests++;evidence.requests=requests;
    evidence.thinkingLevel=ctx.thinkingLevel;evidence.nativeThinking=thinkingFields(event.payload);
    const result=requestLimit(event.payload,requests,ctx);
    if(!result.valid)refuse(ctx,'request limit or unknown payload');
    save();return result.payload;
  });
  pi.on('tool_call',(event)=>{
    if(event.toolName==='guard_probe'&&!used)return;
    if(inProbe&&event.parentToolCallId)return;
    failed=true;evidence.error='unrelated or repeated top-level tool';save();
    return {block:true,reason:evidence.error};
  });
  pi.on('turn_end',(event,ctx)=>{
    if(event.message?.stopReason==='length'||event.message?.stopReason==='error')refuse(ctx,'incomplete provider response');
    evidence.complete=used&&!failed&&evidence.cases.length===(process.platform==='win32'?12:11)&&requests===1;
    save();ctx.shutdown();return {continue:false};
  });
  pi.registerTool({name:'guard_probe',label:'Permission probe',description:'Execute fixed harmless guard checks once',
    parameters:{type:'object',properties:{},additionalProperties:false},
    execute:async(_id,_args,_signal,_onUpdate,ctx)=>{
      if(used){failed=true;save();throw Error('probe already used');}
      used=true;inProbe=true;
      const absent=path.join(process.env.USERPROFILE??process.env.HOME,'pi-probe-absent-'+randomUUID());
      if(fs.existsSync(absent))throw Error('probe targets must be absent');
      evidence.absentTarget=absent;save();
      const cases=[['bash',{command:'git status --short'}],['read',{path:'README.md'}],
        ['write',{path:'scratch/ok.txt',content:'probe\n'}],['bash',{command:`rm -rf "${absent.replaceAll('\\','/')}"/t`}],
        ['write',{path:path.join(absent,'x.txt'),content:'absent'}],['bash',{command:'git add -A'}],
        ['bash',{command:'true && git restore --staged README.md'}],['bash',{command:'git commit --allow-empty -m probe'}],
        ['bash',{command:'git push origin HEAD'}],['read',{path:'secrets/pi-probe-absent.key'}],
        ['bash',{command:'cat ~/.ssh/pi-probe-absent'}]];
      if(process.platform==='win32')cases.push(['powershell',{command:'Get-Date'}]);
      try {
        for(let i=0;i<cases.length;i++) {
          const [tool,args]=cases[i];const outcome=await ctx.executeTool(tool,args);
          const isError=Boolean(outcome.isError);
          const reason=outcome.error??(outcome.result?.content??outcome.content??[]).filter(c=>c.type==='text').map(c=>c.text).join('\n');
          evidence.cases.push({id:'P'+(i+1),tool,isError,reason});
          if(isError!==(i>=3)){failed=true;evidence.error='unexpected outcome P'+(i+1);}
          save();
        }
      }finally{inProbe=false;}
      evidence.complete=!failed&&requests===1;save();
      return {content:[{type:'text',text:JSON.stringify(evidence)}],details:evidence,isError:failed};
    }});
}
