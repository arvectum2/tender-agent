"""Synthetic ZIP acceptance through real isolated DP and operator HTTP/browser."""
import hashlib
import json
import os
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from scripts.acceptance.apr08_browser_harness import run_browser
from scripts.acceptance.run_apr08_real_dp_replay import inventory
from src.modules.tender_operator_agent_demo.ri223_offline_intake import import_archive

NUMBER='32600000000'
ENV='AI_CORP_RI223_RECEIPT_CATALOG'


def replay_zip(runs,app,password):
    prior={k:os.environ.get(k) for k in (ENV,ENV+'_SHA256')}
    try:
        with TemporaryDirectory(dir=runs.parent,prefix='synthetic-zip-') as temp:
            root=Path(temp)
            original=root/'synthetic.zip'
            with zipfile.ZipFile(original,'w',compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr('docs/spec.txt','Синтетический пример. Критерий оценки: качество услуг и цена предложения.\n')
                z.writestr('docs/table.csv','parameter,value\nfixture,20\n')
            raw=('<purchaseNotice xmlns="http://zakupki.gov.ru/223fz/purchase/1"><body><item><purchaseNoticeData>'
                 f'<registrationNumber>{NUMBER}</registrationNumber><name>SYNTHETIC ZIP FIXTURE</name>'
                 '<purchaseCodeName>Fixture method</purchaseCodeName><version>1</version>'
                 '<submissionCloseDateTime>2026-10-15T10:00:00</submissionCloseDateTime>'
                 '<attachments><document><contentUid>fixture</contentUid><fileName>synthetic.zip</fileName>'
                 '<url>https://zakupki.gov.ru/test?uid=fixture</url></document></attachments>'
                 '<lots><lot><ordinalNumber>1</ordinalNumber><lotData><subject>Fixture</subject>'
                 '<initialSum>100.25</initialSum><currency><code>RUB</code></currency></lotData></lot></lots>'
                 '</purchaseNoticeData></item></body></purchaseNotice>').encode()
            archive=root/'soap.zip'
            with zipfile.ZipFile(archive,'w') as z:z.writestr('notice.xml',raw)
            sha=hashlib.sha256(original.read_bytes()).hexdigest()
            xml_sha=hashlib.sha256(raw).hexdigest()
            receipt={'historical_ri223_cases':[{'registry_number':NUMBER,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
                'selected_xml_sha256':xml_sha,'observed_version':'1','archived_attachment_reference_coverage_complete':True,
                'documents':[{'name':'synthetic.zip','source_kind':'purchaseNotice','xml_sha256':xml_sha,'sha256':sha,'bytes':original.stat().st_size}]}]}
            path=root/'synthetic-catalog.json';path.write_text(json.dumps(receipt))
            os.environ.update({ENV:str(path),ENV+'_SHA256':hashlib.sha256(path.read_bytes()).hexdigest()})
            before=inventory(root)
            run=import_archive(runs,archive,NUMBER,attachments=[original],expand_zip=True)
            directory=runs/run
            meta=json.loads((directory/'metadata.json').read_text())
            assert meta['status']=='needs_review' and meta['ri223_attachment_extraction']['container_members']==2
            members=[f for f in meta['files'] if f['source']=='ri223_container_member']
            print('ZIP_SYNTHETIC_DP',[(f['extension'],f['extraction_status']) for f in members],flush=True)
            assert all(f['ri223_container']['container_format']=='ZIP' for f in members)
            assert members[0]['extracted_text_available']
            url=f'/api/demo/tender-agent/workspace/runs/{run}/evidence-search'
            with TestClient(app) as c:
                auth=('apr08-replay',password)
                assert c.post(url,json={'query':'критерий оценки'}).status_code==401
                result=c.post(url,auth=auth,json={'query':'критерий оценки'})
                assert result.status_code==200
                packet=result.json()
                assert packet['status']=='VERIFIED_EXCERPTS_ONLY' and packet['citations']
                assert all(x['ri223_container']['container_format']=='ZIP' and x['ri223_container']['parent_sha256']==sha for x in packet['citations'])
                assert c.post(f'/api/demo/tender-agent/runs/{run}/analyze',auth=auth).status_code==409
                saved=inventory(directory)
                if os.environ.get('APR08_BROWSER_ACCEPTANCE')=='1':
                    run_browser(app,run,password,Path(os.environ['APR08_SCREENSHOT_DIR']),scenario='ri223-zip')
                assert inventory(directory)==saved
                parent=directory/'input'/meta['files'][1]['stored_name']
                blob=parent.read_bytes();parent.write_bytes(blob+b' ')
                assert c.post(url,auth=auth,json={'query':'критерий оценки'}).json()['status']=='UNKNOWN'
                parent.write_bytes(blob)
                child=directory/'input'/members[0]['stored_name']
                child.write_bytes(child.read_bytes()+b' ')
                assert c.post(url,auth=auth,json={'query':'критерий оценки'}).json()['status']=='UNKNOWN'
            assert inventory(root)==before
            print('APR03B_RI223_ZIP_SYNTHETIC_REPLAY_PASS',meta['ri223_attachment_extraction']['searchable'],'parent/child tamper UNKNOWN')
    finally:
        for k,v in prior.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
