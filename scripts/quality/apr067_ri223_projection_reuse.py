"""Paired same-run measurement; no production or semantic accuracy claim."""
import json
import time
from contextlib import nullcontext
from unittest.mock import patch

from src.modules.tender_operator_agent_demo import ri223_container_evidence as container
from src.modules.tender_operator_agent_demo import ri223_review_dossier as dossier
from src.modules.tender_operator_agent_demo.evidence_document_search import (
    checked_search_run,
)
from src.modules.tender_operator_agent_demo.ri223_offline_intake import import_archive


def measure(runs,root):
    number='32616445795'
    case=root/number
    run_id=import_archive(runs,case/'ri223-soap.zip',number,
                          attachments=[case/'attachments/01-3727.rar'],expand_rar=True)
    run,metadata=checked_search_run(run_id)
    rows=[]
    packets=[]
    # Same input, same process, no alternate lexical query or unverifiable shortcut.
    for name,scope in [('without_reuse',nullcontext),('with_reuse',container.container_projection_scope)]:
        with patch.object(dossier,'container_projection_scope',scope), patch.object(container,'_project_container',wraps=container._project_container) as decode:
            start=time.monotonic()
            packet=dossier.build_archived_review(run_id,run,metadata)
            elapsed=time.monotonic()-start
            rows.append({'mode':name,'seconds':round(elapsed,3),'full_projections':decode.call_count})
            packets.append(packet)
    assert packets[0]==packets[1]
    assert packets[1]['status']=='RI223_ARCHIVED_REVIEW_ONLY'
    assert packets[1]['source_backed_domains']==9
    assert packets[1]['inventory']['members_verified']==19
    assert rows[0]['full_projections']>1 and rows[1]['full_projections']==1
    print('APR067_PROJECTION_REUSE_PASS',json.dumps({'case':number,'identical_dossier':True,'members':19,
          'domains':9,'measurements':rows,'production_slo':False}),flush=True)
