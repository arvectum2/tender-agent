"""Read-only preparation: preserve legacy serialized fingerprints, verify once."""
import json,sys
from pathlib import Path
from scripts.research.link_gpb_document_receipts import prepare as prepare_links
from scripts.research.persist_gpb_protocol_decisions import prepare as prepare_decisions

def prepare(root):
    links=prepare_links(root)
    decisions=prepare_decisions(root,verified_receipts=links)
    return {'links_json':json.dumps(links,ensure_ascii=False)+'\n','decisions_json':json.dumps(decisions,ensure_ascii=False)+'\n'}

if __name__=='__main__':
    print(json.dumps(prepare(Path(sys.argv[1])),ensure_ascii=False))
