import json

from scripts.research.run_sibur_archive_import import next_batch


def test_ready_pages_batched_and_partial_flushed(tmp_path):
    folder=tmp_path/"107"
    folder.mkdir()
    for i in range(1,27):
        (folder/f"p{i:05d}.json").write_text("{}")
    (tmp_path/"state.json").write_text(json.dumps({"107":{"status":"capturing"}}))
    assert next_batch(tmp_path,{},True)==("107",list(range(1,26)))
    assert next_batch(tmp_path,{"107":25},True) is None
    assert next_batch(tmp_path,{"107":25},False)==("107",[26])


def test_gap_not_skipped(tmp_path):
    p=tmp_path/"108"
    p.mkdir()
    (p/"p00002.json").write_text("{}")
    assert next_batch(tmp_path,{},False) is None
