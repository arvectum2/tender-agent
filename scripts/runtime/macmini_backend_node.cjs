'use strict';
// Launchd-compatible stable wrapper: only host launcher lives outside canonical SSD repo.
// Application source is always /Volumes/ArvectumSSD/Arvectum/repos/tender-agent.
const fs = require('node:fs');
const {spawn,execFileSync} = require('node:child_process');
const ROOT='/Volumes/ArvectumSSD/Arvectum/repos/tender-agent';
const ENV='/Volumes/ArvectumSSD/Arvectum/private/tender-agent/runtime/backend.env';
const SCRIPT=ROOT+'/scripts/runtime/start.sh';
for (const p of [ROOT,ENV,SCRIPT]) {
  try {fs.accessSync(p,fs.constants.R_OK);}
  catch (e) {console.error('Cannot access canonical backend resource:',p,e.code);process.exit(78);}
}
const runtimeEnv={...process.env,ARVECTUM_ENV_FILE:ENV};
const sha=execFileSync('/usr/bin/git',['-C',ROOT,'rev-parse','HEAD'],{encoding:'utf8',timeout:5000}).trim();
const child=spawn('/bin/bash',[SCRIPT],{cwd:ROOT,env:runtimeEnv,stdio:'inherit'});
const stateDir='/Volumes/ArvectumSSD/Arvectum/runtime/tender-agent';
fs.mkdirSync(stateDir,{recursive:true,mode:0o700});
const state=stateDir+'/backend-active.json';
const stateTmp=state+'.tmp-'+process.pid;
fs.writeFileSync(stateTmp,JSON.stringify({commit:sha,backend_pid:child.pid,launcher_pid:process.pid,started_at_utc:new Date().toISOString(),source:ROOT})+'\n',{mode:0o600});
fs.renameSync(stateTmp,state);
console.log('Tender Agent canonical backend commit:',sha.slice(0,12));
const forward=(signal)=>{if(child.exitCode===null && !child.killed)child.kill(signal);};
process.on('SIGTERM',()=>forward('SIGTERM'));
process.on('SIGINT',()=>forward('SIGINT'));
child.on('error',(e)=>{console.error('Backend launch failed:',e.code||e.name);process.exit(78);});
child.on('exit',(code,signal)=>process.exit(code===null?1:code));
