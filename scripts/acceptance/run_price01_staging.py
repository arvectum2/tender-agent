"""Disposable real HTTPS PRICE-01 server, synthetic tenant data only."""
from __future__ import annotations

import base64
import json
import os
import plistlib
import secrets
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT=Path(__file__).resolve().parents[2]
REGISTRY='0158300034526000388'
FLAGS=('price_scenarios','price_itemized','cost_evidence','actual_costs','actual_evidence',
       'actual_samples','cost_norms','cost_norm_binding','historical_comparables','reviewed_contract_registry')


def seed(origin,context,password):
    with httpx.Client(base_url=origin,verify=context,trust_env=False,timeout=20) as c:
        def checked(r,status=200):
            if r.status_code!=status:
                raise RuntimeError(f'{r.request.method} {r.request.url.path}: HTTP {r.status_code}, expected {status}')
            return r.json()
        def tenant(name):
            operator=('price01-operator',password)
            customer=checked(c.post('/customers',auth=operator,json={'legal_name':name,'customer_status':'PROSPECT'}),201)
            t=checked(c.post('/api/operator/saas/tenants',auth=operator,json={'customer_id':customer['customer_id']}),201)
            token=checked(c.post('/api/saas/invitations/redeem',json={'invitation_code':t['invitation']['invitation_code'],'display_name':name}),201)['access_token']
            h={'Authorization':'Bearer '+token}
            policy=checked(c.get('/api/saas/legal',headers=h))
            checked(c.post('/api/saas/legal/accept',headers=h,json={'terms_version':policy['terms_version'],'privacy_version':policy['privacy_version'],'confirm_read':True}))
            return token,h
        token,h=tenant('Synthetic PRICE01 owner A')
        foreign,hb=tenant('Synthetic PRICE01 owner B')
        cases='/api/saas/company-portfolio/cases'
        def post(path,body,status=201):
            return checked(c.post(path,headers=h,json=body),status)
        case=post(cases,{'registry_number':REGISTRY})['case_id']
        path=cases+'/'+case
        assert c.get(path,headers=hb).status_code==404
        estimate={'lines':[{'category':'own_labor_rub','title':'Development','unit':'h','quantity':'10','rate_rub':'1000','source_kind':'ASSUMPTION','source_note':'Synthetic plan'}],
                  'zero_cost_categories':['external_direct_rub','cash_overhead_rub','reserve_rub','fixed_platform_fees_rub','guarantee_financing_cost_rub'],
                  'terms':{'revenue_tax_percent':'6','variable_platform_fee_percent':'0','minimum_profit_rub':'0','target_profit_rub':'0','manual_bid_prices_rub':[],'assumption_note':'Synthetic plan','accept_hypothetical_assumptions_only':True},'confirm_no_double_count':True}
        plan=post(path+'/price-scenarios/itemized',{'estimate':estimate,'expected_revision':0,'idempotency_key':'staging-plan-1'})
        actual=path+'/price-scenarios/'+plan['scenario_id']+'/actual-costs'
        baseline=checked(c.get(actual,headers=h))['baseline_sha256']
        snapshot=post(actual,{'snapshot':{'baseline_sha256':baseline,'as_of':'2026-11-15','observations':[{'ordinal':1,'quantity':'12','rate_rub':'1000','source_note':'Synthetic actual'}],'unplanned_costs':[],'note':'Synthetic cumulative report','confirm_cumulative_user_report':True,'confirm_no_double_count':True},'expected_revision':0,'idempotency_key':'staging-actual-1'})
        row=checked(c.get(actual+'/'+snapshot['snapshot_id']+'/rows/PLANNED/1/evidence',headers=h))
        proposal={'sample':{'category':'own_labor_rub','title':'Development','unit':'h','samples':[{'case_id':case,'scenario_id':plan['scenario_id'],'snapshot_id':snapshot['snapshot_id'],'row_kind':'PLANNED','ordinal':1,'line_sha256':row['line_sha256']}],'confirm_comparable_reported_rows':True,'confirm_one_cumulative_row_per_case':True},'norm_quantity':'10','norm_rate_rub':'1000','rationale':'Synthetic explicit manager decision','confirm_reported_source_limits':True}
        norms='/api/saas/company-portfolio/cost-norms'
        draft=post(norms+'/preview',proposal,200)
        approved=post(norms,{'proposal':proposal,'preview_sha256':draft['preview_sha256'],'expected_revision':0,'idempotency_key':'staging-norm-1','confirm_internal_approval':True})
        assert approved['action']=='APPROVED'
        assert c.get(norms,headers=hb).json()['items']==[]
        return {'origin':origin,'token':token,'foreign_token':foreign,'case_id':case,'norm_key':approved['norm_key'],'plan_id':plan['scenario_id']}


def simulator(fixture,root,env):
    sim=os.environ.get('PRICE01_SIMULATOR_ID')
    xctestrun=os.environ.get('PRICE01_XCTESTRUN')
    if not sim and not xctestrun:return
    if not sim or not xctestrun:raise ValueError('Both simulator and test build required')
    devices=json.loads(subprocess.check_output(['xcrun','simctl','list','devices','available','-j'],env=env))
    matches=[x for rows in devices['devices'].values() for x in rows if x['udid']==sim]
    if len(matches)!=1 or not matches[0]['name'].startswith('TA-PRICE01-Acceptance-') or matches[0]['state']!='Shutdown':
        raise ValueError('Dedicated shut-down PRICE01 simulator required')
    source=Path(xctestrun).resolve()
    spec=plistlib.loads(source.read_bytes())
    target=spec['TenderAgentTests']
    f={**fixture,'ca_base64':base64.b64encode(Path(fixture['ca_der']).read_bytes()).decode()}
    target.setdefault('EnvironmentVariables',{})['PRICE01_STAGE_FIXTURE']=base64.b64encode(json.dumps(f).encode()).decode()
    # Same directory preserves Xcode's __TESTROOT__; remove private fixture afterwards.
    fd,name=tempfile.mkstemp(prefix='price01-stage-',suffix='.xctestrun',dir=source.parent)
    try:
        with os.fdopen(fd,'wb') as out:plistlib.dump(spec,out)
        with (root/'simulator.log').open('w') as log:
            result=subprocess.run(['xcodebuild','-xctestrun',name,'-destination','platform=iOS Simulator,id='+sim,
                '-parallel-testing-enabled','NO','-only-testing:TenderAgentTests/CompanyStageAcceptanceTests/testRealHTTPSStage',
                '-resultBundlePath',str(root/'stage.xcresult'),'test-without-building'],cwd=root,env=env,
                stdout=log,stderr=log,timeout=240,check=False)
        text=(root/'simulator.log').read_text()
        if result.returncode or 'PRICE01_REAL_HTTPS_NATIVE_PASS' not in text or '** TEST EXECUTE SUCCEEDED **' not in text:
            # Do not print test environment or credentials.
            for line in text.splitlines():
                if 'failed' in line.lower() and 'Test Case' in line:print(line[:240])
            raise RuntimeError('Actual iOS HTTPS acceptance failed')
        print('PRICE01_IOS_SIMULATOR_HTTPS_PASS: 1 XCTest',flush=True)
    finally:
        Path(name).unlink(missing_ok=True)
        subprocess.run(['xcrun','simctl','shutdown',sim],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False,timeout=30)


def main():
    node=os.environ['PRICE01_NODE']
    browser_module=os.environ['PRICE01_PLAYWRIGHT_MODULE']
    chrome=os.environ['PRICE01_CHROME']
    with tempfile.TemporaryDirectory(prefix='ta-price01-stage-',dir='/tmp') as d:
        root=Path(d).resolve()
        (root/'data').mkdir(mode=0o700)
        # Only the disposable application config; never load repository .env.
        env={k:os.environ[k] for k in ('HOME','PATH','TMPDIR','LANG','LC_ALL') if k in os.environ}
        password=secrets.token_urlsafe(36)
        env.update(PYTHONPATH=str(ROOT),AI_CORP_DATABASE_URL='sqlite+pysqlite:///'+str(root/'stage.sqlite'),
                   AI_CORP_ARVECTUM_DATA_DIR=str(root/'data'),AI_CORP_SAAS_FOUNDATION_ENABLED='true',
                   AI_CORP_PILOT_AUTH_ENABLED='true',AI_CORP_PILOT_AUTH_USERNAME='price01-operator',
                   AI_CORP_PILOT_AUTH_PASSWORD=password,AI_CORP_ARVECTUM_REDIS_ENABLED='false',
                   TENDER_LEARNING_CAPTURE_ENABLED='0',AI_CORP_ALLOWED_HOSTS='127.0.0.1')
        env.update({'AI_CORP_SAAS_COMPANY_'+f.upper()+'_ENABLED':'true' for f in FLAGS})
        def run(args,**kwargs):
            subprocess.run(args,cwd=root,env=env,check=True,timeout=120,**kwargs)
        cert=root/'cert.pem';key=root/'key.pem';ca=root/'ca.pem';ca_key=root/'ca.key'
        config=root/'openssl.cnf'
        config.write_text('[req]\nprompt=no\ndistinguished_name=dn\nx509_extensions=ext\n[dn]\nCN=PRICE01 disposable CA\n[ext]\nbasicConstraints=critical,CA:TRUE,pathlen:0\nkeyUsage=critical,keyCertSign,cRLSign\nsubjectKeyIdentifier=hash\n')
        quiet={'stdout':subprocess.DEVNULL,'stderr':subprocess.DEVNULL}
        run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-keyout',str(ca_key),'-out',str(ca),'-config',str(config)],**quiet)
        run(['openssl','req','-new','-newkey','rsa:2048','-nodes','-subj','/CN=127.0.0.1','-keyout',str(key),'-out',str(root/'server.csr')],**quiet)
        config.write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=IP:127.0.0.1\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n')
        run(['openssl','x509','-req','-in',str(root/'server.csr'),'-CA',str(ca),'-CAkey',str(ca_key),'-CAcreateserial','-days','1','-sha256','-extfile',str(config),'-out',str(cert)],**quiet)
        run(['openssl','x509','-in',str(cert),'-outform','DER','-out',str(root/'cert.der')])
        run(['openssl','x509','-in',str(ca),'-outform','DER','-out',str(root/'ca.der')])
        run([sys.executable,'-c','from src.shared.db import models; from src.shared.db.base import Base; from sqlalchemy import create_engine; import os; Base.metadata.create_all(create_engine(os.environ["AI_CORP_DATABASE_URL"]))'])
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        origin=f'https://127.0.0.1:{port}'
        tls=ssl.create_default_context(cafile=str(ca))
        with (root/'server.log').open('w') as log:
            server=subprocess.Popen([sys.executable,'-m','uvicorn','src.main:app','--host','127.0.0.1','--port',str(port),'--ssl-keyfile',str(key),'--ssl-certfile',str(cert),'--no-access-log'],cwd=root,env=env,stdout=log,stderr=log)
            try:
                for _ in range(60):
                    if server.poll() is not None:raise RuntimeError('Disposable server exited')
                    try:
                        if httpx.get(origin+'/health',verify=tls,trust_env=False,timeout=1).status_code==200:break
                    except httpx.HTTPError:pass
                    time.sleep(.25)
                else:raise RuntimeError('Disposable server not ready')
                fixture=seed(origin,tls,password)
                fixture['certificate_der']=str(root/'cert.der');fixture['ca_der']=str(root/'ca.der')
                path=root/'client.json';path.write_text(json.dumps(fixture));path.chmod(0o600)
                client_env={**{k:env[k] for k in ('HOME','PATH','TMPDIR','LANG','LC_ALL') if k in env},'PRICE01_FIXTURE':str(path),'PRICE01_PLAYWRIGHT_MODULE':browser_module,'PRICE01_CHROME':chrome}
                subprocess.run([node,str(ROOT/'scripts/acceptance/run_price01_staging_browser.cjs')],cwd=root,env=client_env,timeout=120,check=True)
                print('STAGING_WEB_PASS',flush=True)
                subprocess.run(['/bin/bash',str(ROOT/'scripts/acceptance/run_price01_staging_native.sh')],cwd=root,env={**client_env,'PRICE01_REPO':str(ROOT)},timeout=120,check=True)
                print('STAGING_NATIVE_PASS',flush=True)
                simulator(fixture,root,client_env)
            finally:
                server.terminate()
                try:server.wait(timeout=10)
                except subprocess.TimeoutExpired:server.kill();server.wait()


if __name__=='__main__':
    main()
