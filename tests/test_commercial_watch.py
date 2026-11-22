"""Synthetic-only tests for commercial watch. No network, production DB or original files."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.research.commercial_watch import (
    EvidenceRejected,
    compile_watch,
    render_markdown,
)

NOW = datetime(2026, 11, 22, 19, 20, tzinfo=UTC)


def _dump(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthetic_inputs(tmp_path: Path):
    snap = tmp_path / "geh"
    original = snap / "geh_active_p1.html"
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_text("<html>Synthetic public source listing</html>")
    sha = hashlib.sha256(original.read_bytes()).hexdigest()
    base = {
        "source": "etp_gpb", "verification": "PUBLIC_LIST_OBSERVATION_ONLY",
        "source_sha256": sha,
        "source_url": "https://etpgpb.ru/procedures/?page=1",
        "customers_raw": "ПАО ТГК-1", "organizer_raw": "ООО ГЭХ Закупки",
        "deadline_raw": "25 ноября 2026, 07:00 Z",
    }
    first = {"observation": dict(base, external_id="etp:123",
        title="Пусконаладочные работы АСУ ТП",
        detail_url="https://etpgpb.ru/procedures/etp/123/"),
        "observed_at": "2026-11-22T10:00:00Z"}
    second = {"observation": dict(base, external_id="price_request:124",
        title="Поставка электродвигателя",
        detail_url="https://etpgpb.ru/procedures/price_request/124/"),
        "observed_at": "2026-11-22T10:00:00Z"}
    other = {"observation": dict(base, external_id="etp:125",
        title="Топливные карты",
        detail_url="https://etpgpb.ru/procedures/etp/125/"),
        "observed_at": "2026-11-22T10:00:00Z"}
    _dump(snap / "capture-status.json", {"complete": True, "expected_pages": 1, "verified_pages": 1})
    _dump(snap / "gpb-geh-section-receipts.json", [
        {"name": "geh_active_p1", "sha256": sha, "current_page": 1,
         "advertised_last_page": 1}
    ])
    plan = [first, second, other]
    plan_sha = _dump(snap / "verified-active-plan.json", plan)
    new_sha = _dump(snap / "guarded-ingest" / "new-only.json", {"accepted": [first, second]})
    _dump(snap / "guarded-ingest" / "state.json", {
        "status": "completed", "stage": "verified", "inflight": False,
        "old_rows_unchanged": True, "replay_inserted": 0, "new": 2,
        "inserted": 2, "before": 10, "after": 12, "valid": 3,
        "review": 0, "source_input_sha256": new_sha, "plan_sha256": plan_sha,
    })
    sibur_path = tmp_path / "sibur.json"
    _dump(sibur_path, {"as_of": "2026-11-17T09:29:11Z",
        "snapshot_receipts_sha256": "a" * 64,
        "rows": [{
            "procedure_id": "12345/1", "deadline_msk": "2026-11-27 10:00",
            "priority": "P0", "commercial_kind": "commissioning",
            "observation": {
                "external_id": "12345/1", "source": "sibur_public",
                "source_sha256": "a" * 64, "verification": "PUBLIC_SNAPSHOT_ONLY",
                "title": "ПНР электрооборудования", "organizer": "ПАО СИБУР",
                "category": "Электрооборудование",
                "source_url": "https://www.sibur.ru/ru/procurement/buy/?PAGEN_1=1",
            },
        }, {
            "procedure_id": "12345/2", "deadline_msk": "2026-11-20 10:00",
            "observation": {
                "external_id": "12345/2", "source": "sibur_public",
                "source_sha256": "a" * 64, "verification": "PUBLIC_SNAPSHOT_ONLY",
                "title": "Поставка электрооборудования", "organizer": "ПАО СИБУР",
                "category": "Электрооборудование",
                "source_url": "https://www.sibur.ru/ru/procurement/buy/?PAGEN_1=2",
            },
        }],
    })
    return snap, sibur_path


def test_real_delta_and_stale_status_never_look_like_live_eligibility(tmp_path):
    snap, watch = synthetic_inputs(tmp_path)
    result = compile_watch(snap, watch, NOW)
    assert result["geh"]["summary"]["actually_inserted"] == 2
    assert len(result["geh"]["candidates"]) == 2
    assert result["geh"]["candidates"][0]["external_id"] == "etp:123"
    assert {x["evidence_status"] for x in result["geh"]["candidates"]} == {
        "MARKET_RESEARCH_ONLY", "PUBLIC_LIST_CARD_RECHECK",
    }
    assert result["sibur"]["summary"]["expired_observed_deadlines"] == 1
    assert result["sibur"]["summary"]["freshness"] == "stale"
    assert len(result["sibur"]["candidates"]) == 1
    assert result["sibur"]["candidates"][0]["evidence_status"] == "STALE_SIBUR_SNAPSHOT_RECHECK"
    rendered = render_markdown(result)
    assert "ПАО ТГК-1" in rendered
    assert "https://etpgpb.ru/procedures/etp/123/" in rendered
    assert "не подтверждён доступ к участию" in rendered
    assert result["production_database_modified"] is False
    assert result["submissions_sent"] is False


def test_expired_gehs_excluded_and_no_false_fuel_keywords(tmp_path):
    snap, watch = synthetic_inputs(tmp_path)
    path = snap / "guarded-ingest" / "new-only.json"
    state = snap / "guarded-ingest" / "state.json"
    d = json.loads(path.read_text())
    d["accepted"][0]["observation"]["deadline_raw"] = "21 ноября 2026, 07:00 Z"
    new_sha = _dump(path, d)
    s = json.loads(state.read_text()); s["source_input_sha256"] = new_sha
    _dump(state, s)
    # Plan proof must still match this known change; no unverified state accepted.
    plan_path = snap / "verified-active-plan.json"
    plan = json.loads(plan_path.read_text())
    plan[0] = d["accepted"][0]
    plan_sha = _dump(plan_path, plan)
    s["plan_sha256"] = plan_sha
    _dump(state, s)
    value = compile_watch(snap, watch, NOW)
    assert [c["external_id"] for c in value["geh"]["candidates"]] == ["price_request:124"]


@pytest.mark.parametrize("target", [
    "html", "plan", "state", "new_only", "capture",
])
def test_gehs_reject_tampering_before_business_claims(tmp_path, target):
    snap, watch = synthetic_inputs(tmp_path)
    paths = {
        "html": snap / "geh_active_p1.html",
        "plan": snap / "verified-active-plan.json",
        "state": snap / "guarded-ingest" / "state.json",
        "new_only": snap / "guarded-ingest" / "new-only.json",
        "capture": snap / "capture-status.json",
    }
    path = paths[target]
    if target == "html":
        path.write_bytes(b"unverified mutation")
    elif target == "capture":
        data = json.loads(path.read_text());data["complete"] = False;_dump(path, data)
    elif target == "state":
        data = json.loads(path.read_text());data["inserted"] = 300;_dump(path, data)
    elif target == "new_only":
        data = json.loads(path.read_text());data["accepted"] = [];_dump(path, data)
    else:
        data = json.loads(path.read_text());data[0]["observation"]["title"] = "MUTATED";_dump(path, data)
    with pytest.raises(EvidenceRejected):
        compile_watch(snap, watch, NOW)


def test_nonfirstparty_detail_and_missing_source_sha_rejected(tmp_path):
    snap, watch = synthetic_inputs(tmp_path)
    plan_path = snap / "verified-active-plan.json"
    new_path = snap / "guarded-ingest" / "new-only.json"
    state_path = snap / "guarded-ingest" / "state.json"
    entries = json.loads(plan_path.read_text())
    entries[0]["observation"]["detail_url"] = "https://evil.example/procedures/etp/123"
    new = {"accepted": entries[:2]}
    plan_sha = _dump(plan_path, entries)
    new_sha = _dump(new_path, new)
    state = json.loads(state_path.read_text())
    state.update(plan_sha256=plan_sha, source_input_sha256=new_sha)
    _dump(state_path, state)
    with pytest.raises(EvidenceRejected, match="non-first-party"):
        compile_watch(snap, watch, NOW)


def test_missing_sibur_evidence_fails_closed(tmp_path):
    snap, watch = synthetic_inputs(tmp_path)
    data = json.loads(watch.read_text())
    data["rows"][0]["observation"]["source_sha256"] = ""
    _dump(watch, data)
    with pytest.raises(EvidenceRejected, match="page SHA"):
        compile_watch(snap, watch, NOW)


def test_no_live_network_or_database_imports():
    import inspect

    import scripts.research.commercial_watch as module
    source = inspect.getsource(module)
    for forbidden in ("requests.get(", "subprocess.run(", "create_engine(", "http.client", "urllib.request"):
        assert forbidden not in source


def test_known_geh_in_current_verified_pages_remains_a_business_lead(tmp_path):
    snap, watch = synthetic_inputs(tmp_path)
    plan_path = snap / "verified-active-plan.json"
    plan = json.loads(plan_path.read_text())
    plan[2]["observation"]["title"] = "Монтаж КИПиА и ПНР"
    sha = _dump(plan_path, plan)
    state_path = snap / "guarded-ingest" / "state.json"
    state = json.loads(state_path.read_text())
    state["plan_sha256"] = sha
    _dump(state_path, state)
    value = compile_watch(snap, watch, NOW)
    known = next(c for c in value["geh"]["candidates"] if c["external_id"] == "etp:125")
    assert known["novelty"] == "previous_observation"
    assert value["geh"]["summary"]["actually_inserted"] == 2
    assert value["geh"]["summary"]["matching_unexpired"] == 3
    assert value["geh"]["summary"]["new_relevant"] == 2
    assert value["geh"]["summary"]["already_known_relevant"] == 1


def test_category_only_sibur_match_has_limited_priority(tmp_path):
    snap, watch = synthetic_inputs(tmp_path)
    d = json.loads(watch.read_text())
    row = d["rows"][0]["observation"]
    row["title"] = "NB ИМПОРТ комплектующие КОС"
    row["category"] = "Системы и средства автоматизации, метрологии и КИП"
    _dump(watch, d)
    value = compile_watch(snap, watch, NOW)
    candidate = value["sibur"]["candidates"][0]
    assert candidate["priority_score"] <= 65
    assert candidate["topic"].startswith("Только категория:")
    assert candidate["freshness"] == "older_than_48h_requires_refresh"
