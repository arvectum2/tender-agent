"""Attach verified DP receipts to existing committed archive document rows only."""
from __future__ import annotations
import json,os,sys
from datetime import UTC,datetime
from sqlalchemy import create_engine,select,text,update
from sqlalchemy.orm import Session
from src.tender_research.models import ProcurementTender,ProcurementTenderDocument
COLLECTION='tender-agent:sibur-public-research'


def attach(actual,captures,dp,sha):
    if not actual or not captures or any(c not in actual.get('capture_receipts',[]) for c in captures):raise ValueError('committed capture mismatch')
    if (dp.get('collection_id')!=COLLECTION or dp.get('canonical_uri')!='content-sha256://'+sha or dp.get('extraction_status')!='extracted' or type(dp.get('chunks')) is not int or dp['chunks']<=0 or dp['chunks']!=dp.get('embeddings')):raise ValueError('invalid DP receipt')
    if actual.get('dp_index') not in (None,dp):raise ValueError('existing DP identity differs')
    return {**actual,'dp_index':dp}


def main():
    p=json.load(sys.stdin); t=ProcurementTender.__table__;d=ProcurementTenderDocument.__table__;n=0;verified=0
    with Session(create_engine(os.environ['AI_CORP_DATABASE_URL'])) as s,s.begin():
        if s.execute(text('select current_database()')).scalar_one()!='arvectum_local':raise ValueError('wrong DB')
        for r in p['rows']:
            sha=r['sha256'];dp=p['indexed'][sha];groups={}
            for c in r['committed_captures']:groups.setdefault(c['reference']['external_id'],[]).append(c)
            for eid,captures in groups.items():
                rec=s.execute(select(d.c.id,d.c.raw_meta).select_from(d.join(t,d.c.tender_id==t.c.id)).where(t.c.source=='sibur_public',t.c.external_id==eid,d.c.sha256==sha).with_for_update(of=d)).one();new=attach(rec.raw_meta,captures,dp,sha);verified+=1
                if new!=rec.raw_meta:s.execute(update(d).where(d.c.id==rec.id).values(raw_meta=new,updated_at=datetime.now(UTC)));n+=1
    print(json.dumps({'updated':n,'verified_links':verified}))

if __name__=='__main__':main()
