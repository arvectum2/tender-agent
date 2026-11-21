"""A cache hit never replaces a fresh receipt/child check."""
import json
from unittest.mock import patch

import pytest
from test_apr03b_ri223_archive_copilot import NUMBER
from test_apr03b_ri223_attachment_evidence import processor
from test_apr03b_ri223_zip_evidence import bundle, fixture

from src.modules.tender_operator_agent_demo import ri223_container_evidence as container
from src.modules.tender_operator_agent_demo.ri223_attachment_evidence import (
    verified_container_lineage,
)
from src.modules.tender_operator_agent_demo.ri223_offline_intake import import_archive
from src.modules.tender_operator_agent_demo.ri223_review_dossier import (
    verified_inventory,
)


def test_scope_exact_bytes_and_cleanup():
    a=bundle([('a.txt',b'first')])
    b=bundle([('a.txt',b'other')])
    with patch.object(container,'_project_container',wraps=container._project_container) as decode:
        with container.container_projection_scope():
            first=container.project_container(a,'.zip')
            assert container.project_container(bytes(bytearray(a)),'.zip') is first
            assert decode.call_count==1
            assert container.project_container(b,'.zip')[0].content==b'other'
            assert decode.call_count==2
            assert container.project_container(a,'.zip')==first
            assert decode.call_count==3
            with pytest.raises(ValueError):
                container.project_container(a,'.rar')
            assert decode.call_count==4
        container.project_container(a,'.zip')
        assert decode.call_count==5
        with container.container_projection_scope():
            container.project_container(a,'.zip')
        assert decode.call_count==6


def test_failure_and_nested_scope():
    a=bundle([('a.txt',b'first')])
    with patch.object(container,'_project_container',wraps=container._project_container) as decode:
        with pytest.raises(RuntimeError), container.container_projection_scope():
            outer=container.project_container(a,'.zip')
            with container.container_projection_scope():
                assert container.project_container(a,'.zip')==outer
                assert decode.call_count==2
            assert container.project_container(a,'.zip') is outer
            raise RuntimeError('stop')
        container.project_container(a,'.zip')
        assert decode.call_count==3


@pytest.mark.parametrize('change',['parent','child','receipt','member_path'])
def test_no_lineage_cache_after_mutation(tmp_path,monkeypatch,change):
    raw=bundle([('a.txt',b'first'),('b.txt',b'second')])
    root,archive,original=fixture(tmp_path,monkeypatch,raw)
    run=root/import_archive(root,archive,NUMBER,attachments=[original],processor=processor,expand_zip=True)
    meta=json.loads((run/'metadata.json').read_text())
    parent,child,_=meta['files'][1:]
    with container.container_projection_scope():
        assert verified_inventory(run,meta)['projection_complete']
        assert verified_container_lineage(run,meta,child)
        if change=='parent':
            (run/'input'/parent['stored_name']).write_bytes(raw+b' ')
        elif change=='child':
            (run/'input'/child['stored_name']).write_bytes(b'other')
        elif change=='receipt':
            child['ri223_receipts']=[]
        else:
            child['ri223_container']['member_path']='b.txt'
        assert verified_container_lineage(run,meta,child) is None
        assert not verified_inventory(run,meta)['projection_complete']
