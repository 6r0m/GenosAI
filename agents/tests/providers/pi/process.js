import fs from 'node:fs';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
export function identity(pid) {
 if(process.platform!=='win32') {
  try {const fields=fs.readFileSync('/proc/'+pid+'/stat','utf8').split(') ')[1].split(' ');return fields[0]==='Z'?null:fields[19];}
  catch(err){if(err.code==='ENOENT')return null;throw err;}
 }
 const result=spawnSync('powershell.exe',['-NoProfile','-Command',`try {$p=Get-Process -Id ${pid} -ErrorAction Stop; $p.StartTime.ToUniversalTime().Ticks} catch {if ($_.FullyQualifiedErrorId -like 'NoProcessFoundForGivenId,*') {exit 0}; throw}`],{encoding:'utf8'});
 assert.equal(result.status,0,result.stderr);return result.stdout.trim()||null;
}
export function terminated(pid,generation) {
 assert.ok(generation,'ready/alive process identity required');
 assert.notEqual(identity(pid),generation,'process generation survived timeout');
}
