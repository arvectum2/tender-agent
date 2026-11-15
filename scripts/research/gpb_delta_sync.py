"""Prepare only missing or changed source-verified GPB link/decision groups.

All existing observations remain immutable. Compare complete groups before
selecting delta, within the caller's shared mutation lock.
"""
from __future__ import annotations

import json
import subprocess
from collections import defaultdict

from scripts.research.link_gpb_document_receipts import reconcile_capture_metadata
from scripts.research.persist_gpb_protocol_decisions import attach_decision

QUERY = """import json,os
from sqlalchemy import create_engine,text
with create_engine(os.environ['AI_CORP_DATABASE_URL']).connect() as c:
    rows=c.execute(text("select t.external_id,d.sha256,d.raw_meta "
        "from procurement_tender_documents d join procurement_tenders t on t.id=d.tender_id "
        "where t.source='etp_gpb'")).all()
    print(json.dumps([list(r) for r in rows],ensure_ascii=False))
"""


def db_snapshot():
    rows=json.loads(subprocess.check_output(
        ["docker","exec","arvectum-local-e2e-api-1","python","-c",QUERY],timeout=60))
    result={(e,s):m for e,s,m in rows}
    if len(result)!=len(rows):
        raise ValueError("duplicate DB document identity")
    return result


def plan(links, decisions, actual):
    groups=defaultdict(list)
    for r in links:
        groups[(r["external_id"],r["sha256"])].append(r)
    delta_links=[]
    expected={}
    for key,group in groups.items():
        group=sorted(group,key=lambda r:r["document_url"])
        proposed={"source":"etp_gpb","capture_status":"verified_private_original",
                  "capture_receipts":group,"dp_index":None}
        if key not in actual or reconcile_capture_metadata(actual[key],proposed):
            delta_links.extend(group)
        expected[key]=proposed
    pending=[]
    for r in decisions:
        key=(r["external_id"],r["protocol_sha256"])
        if key not in expected:
            raise ValueError("decision lacks complete verified link group")
        old=expected[key]
        new=attach_decision(old,r)
        if new!=old:
            pending.append(r)
            expected[key]=new
    return delta_links,pending


def verify_plan_empty(links,decisions,actual):
    a,b=plan(links,decisions,actual)
    if a or b:
        raise ValueError("source-bound DB replay still has pending delta")
