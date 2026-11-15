import pytest

from scripts.research.import_gpb_archive_observations import separate


def test_skip_old_identity_without_changing_observation(monkeypatch):
    monkeypatch.setattr("scripts.research.import_gpb_archive_observations.normalize", lambda e: e)
    entries = [{"external_id": "etp:1", "content_hash": "new"},
               {"external_id": "etp:2", "content_hash": "same"},
               {"external_id": "etp:3", "content_hash": "unique"}]
    novel, replay, changed = separate(entries, {"etp:1": "prior", "etp:2": "same"})
    assert novel == [entries[2]]
    assert replay == ["etp:2"]
    assert changed == [{"external_id": "etp:1", "prior_hash": "prior", "incoming_hash": "new"}]
    with pytest.raises(ValueError, match="repeated"):
        separate(entries + [entries[0]], {})
