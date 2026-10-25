'use strict';
// Read-only periodic GitHub vs on-disk vs live-process drift check.
// Never runs git pull, changes commits, or restarts production by itself.
const fs=require('node:fs');
const {spawnSync}=require('node:child_process');
const REPORT='/Volumes/ArvectumSSD/Arvectum/runtime/tender-agent/backend-drift.json';
const VERIFIER='/Users/master/.local/bin/tender-agent-backend-verify.py';
const prev=(()=>{try{return JSON.parse(fs.readFileSync(REPORT,'utf8'));}catch{return {};}})();
const cmd=spawnSync('/opt/homebrew/bin/python3',[VERIFIER,'--json'],{encoding:'utf8',timeout:35000});
let result;
try {result=JSON.parse(cmd.stdout);}catch {result={status:'VERIFICATION_UNAVAILABLE',checks:{},error_type:'invalid_verifier_output'};}
result.checked_at_utc=new Date().toISOString();
const tmp=REPORT+'.tmp-'+process.pid;
fs.mkdirSync('/Volumes/ArvectumSSD/Arvectum/runtime/tender-agent',{recursive:true,mode:0o700});
fs.writeFileSync(tmp,JSON.stringify(result,null,2)+'\n',{mode:0o600});
fs.renameSync(tmp,REPORT);
if(result.status!=='OK' && prev.status==='OK'){
  spawnSync('/usr/bin/osascript',['-e','display notification "GitHub, SSD и запущенный backend расходятся. Проверьте Tender Agent." with title "Арвектум: backend drift"'],{timeout:5000});
}
console.log('Tender Agent backend drift guard:',result.status,
  'github',result.github_main_sha||'-','disk',result.local_main_sha||'-','active',result.active_backend_sha||'-');
process.exitCode=result.status==='OK'?0:1;
