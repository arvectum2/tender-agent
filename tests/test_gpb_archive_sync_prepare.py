import json
from pathlib import Path
from scripts.research import prepare_gpb_archive_sync as m

def test_prepare_reuses_exact_verified_links_and_legacy_serialization(monkeypatch):
    links=[{'external_id':'etp:1','document_url':'url'}];decisions=[{'decision':'проверено'}];calls=[]
    def l(root):calls.append('verify');return links
    def d(root,*,verified_receipts):assert verified_receipts is links;calls.append('parse');return decisions
    monkeypatch.setattr(m,'prepare_links',l);monkeypatch.setattr(m,'prepare_decisions',d)
    result=m.prepare(Path('.'));assert calls==['verify','parse'];assert result['links_json']==json.dumps(links,ensure_ascii=False)+'\n';assert result['decisions_json']==json.dumps(decisions,ensure_ascii=False)+'\n'
