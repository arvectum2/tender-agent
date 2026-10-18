"""First-party public marketplace card preservation: no false legal GO."""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from scripts.procurement_llm import collect_public_market_originals as c
from src.modules.procurement_learning_corpus.models import (
    ProcurementLearningObservation,
)
from src.shared.db.base import Base

DATE = datetime(2026, 10, 18, 18, 42, tzinfo=UTC)


def cards():
    return [
        {"platform": "workspace", "id": "19043",
         "url": ("https://workspace.ru/tenders/"
                 "obnovlenie-sayta-digital-agentstva-19043/")},
        {"platform": "b2bcenter", "id": "4632891",
         "url": ("https://www.b2b-center.ru/app/market-next/"
                 "rfi-crm-x5-import/tender-4632891/")},
    ]


def raw_html(card, *, revision="a"):
    title = (
        "Design website competition"
        if card["platform"] == "workspace"
        else "RFI CRM — Тендер № 4632891 — original page"
    )
    metas = ""
    if card["platform"] == "workspace":
        metas = (
            f'<link rel="canonical" href="{card["url"]}">'
            f'<meta property="og:url" content="{card["url"]}">'
        )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{title}</title>{metas}</head>"
        f"<body>Revision {revision}. Official source snapshot only; no owner BID GO. "
        + ("A" * 1800) + "</body></html>"
    ).encode()


def fake_fetch(cards_set=None, *, revision="a"):
    data = cards_set or cards()
    originals = {item["url"]: raw_html(item, revision=revision) for item in data}
    def fetch(url):
        return originals[url], "text/html"
    return fetch


def prep_root(tmp_path):
    path = tmp_path / "private"
    path.mkdir(mode=0o700)
    path.chmod(0o700)
    return path


def test_pilot_manifest_is_strict_and_original_ids_unique():
    data = c._read_manifest(c.DEFAULT_MANIFEST)
    entries = c.validate_manifest(data)
    assert len(entries) == 2
    assert {r["platform"] for r in entries} == {"workspace", "b2bcenter"}
    assert len({r["platform"] + r["id"] for r in entries}) == 2


def test_offline_dry_run_neither_writes_file_nor_uses_database(tmp_path):
    root = prep_root(tmp_path)
    before = cards()
    result = c.collect(
        before, fetch=fake_fetch(), root=root, observed=DATE,
        engine_factory=lambda: (_ for _ in ()).throw(AssertionError("DB used")),
    )
    assert result["mode"] == "dry_run"
    assert result["sources"] == 2
    assert result["database_mutations"] == 0
    assert result["private_snapshots_written"] == 0
    assert not (root / "original-snapshots").exists()
    assert before == cards()


def test_two_originals_private_snapshots_and_existing_db_append_only(tmp_path):
    root = prep_root(tmp_path)
    engine = create_engine("sqlite+pysqlite:///" + str(tmp_path / "db.sqlite3"))
    Base.metadata.create_all(engine)
    get_engine = lambda: create_engine("sqlite+pysqlite:///" + str(tmp_path / "db.sqlite3"))
    before = c.collect(cards(), fetch=fake_fetch(), root=root, observed=DATE,
                       apply=True, engine_factory=get_engine)
    assert before == {
        "mode": "existing_arvectum_applied", "sources": 2,
        "inserted": 2, "existing": 0, "private_snapshots_new": 2,
        "training_promotions": 0, "source_legal_bid_go": False,
    }
    with Session(engine) as db:
        entries = db.scalars(select(ProcurementLearningObservation)).all()
        assert len(entries) == 2
        for entry in entries:
            assert entry.visibility_scope == "owner_internal"
            assert entry.customer_id is None
            assert entry.training_status == "candidate_unreviewed"
            assert entry.candidate_split == "manual_candidate_not_blind"
            assert entry.event_kind == "manual_review"
            payload = entry.payload_json
            assert payload["owner_bid_go"] is False
            assert payload["buyer_deadline_current_verified"] is False
            assert payload["human_verified_interpretation"] is False
            assert payload["source_gate"] == "PUBLIC_HTML_ORIGINAL_ATTESTED_NOT_LEGAL_STAGE"
            p = Path(payload["source_snapshot_owner_private_path"])
            assert p.exists()
            assert p.stat().st_mode & 0o077 == 0
            assert hashlib.sha256(p.read_bytes()).hexdigest() == (
                payload["original_html_response_bytes_sha256"]
            )
            assert "A" * 1000 not in json.dumps(payload)
            assert "private_chat_in_db" in payload
    replay = c.collect(cards(), fetch=fake_fetch(), root=root, observed=DATE,
                       apply=True, engine_factory=get_engine)
    assert replay["inserted"] == 0
    assert replay["existing"] == 2
    assert replay["private_snapshots_new"] == 0
    # Later time, EXACT same source content: no collision and no mutation
    # of the immutable first observed timestamp or provenance SHA.
    from datetime import timedelta
    later = c.collect(cards(), fetch=fake_fetch(), root=root,
                      observed=DATE + timedelta(hours=3),
                      apply=True, engine_factory=get_engine)
    assert later["inserted"] == 0
    assert later["existing"] == 2
    with Session(engine) as db:
        assert all(
            x.payload_json["source_observed_at_utc"] == DATE.isoformat()
            for x in db.query(ProcurementLearningObservation)
        )
    updated = c.collect(cards(), fetch=fake_fetch(revision="b"), root=root,
                        observed=DATE, apply=True, engine_factory=get_engine)
    assert updated["inserted"] == 2
    assert updated["private_snapshots_new"] == 2
    with Session(engine) as db:
        assert db.query(ProcurementLearningObservation).count() == 4
    engine.dispose()


@pytest.mark.parametrize("url", [
    "http://workspace.ru/tenders/a-19043/",
    "https://workspace.ru/tenders/a-19043/?token=x",
    "https://workspace.ru/tenders/a-19043/#session",
    "https://evil.invalid/tenders/a-19043/",
    "https://user:pass@workspace.ru/tenders/a-19043/",
    "https://workspace.ru/tenders/a-19044/",
    "https://workspace.ru:1234/tenders/a-19043/",
    "https://workspace.ru/tenders/a-19043%2f",
    "https://localhost/tenders/a-19043/",
])
def test_wrong_domain_private_query_inconsistent_number_refused(url):
    item = copy.deepcopy(cards()[0])
    item["url"] = url
    with pytest.raises(c.PublicOriginalError):
        c._url(item)


def test_b2b_mismatched_number_or_page_title_refused():
    item = cards()[1]
    raw = raw_html(item).replace(b"4632891", b"4632892")
    with pytest.raises(c.PublicOriginalError, match="identity"):
        c._identity_on_page(item, raw)


def test_workspace_page_canonical_identity_must_match_original():
    item = cards()[0]
    raw = raw_html(item).replace(b"og:url", b"og:unrelated")
    with pytest.raises(c.PublicOriginalError, match="identity"):
        c._identity_on_page(item, raw)


def test_duplicate_watchlist_records_refused():
    item = cards()[0]
    with pytest.raises(c.PublicOriginalError, match="duplicate"):
        c.validate_manifest({
            "contract_version": "public_original_sources_v1", "cards": [item, item]
        })


def test_oversized_unexpected_or_missing_manifest_rejected(tmp_path):
    file = tmp_path / "dup.json"
    file.write_text('{"a":1,"a":2}', encoding="utf8")
    with pytest.raises(c.PublicOriginalError, match="duplicate"):
        c._read_manifest(file)
    file.write_bytes(b" " * 35_000)
    with pytest.raises(c.PublicOriginalError, match="large"):
        c._read_manifest(file)
    file.unlink()
    with pytest.raises(c.PublicOriginalError):
        c._read_manifest(file)


def test_network_source_error_fails_before_any_transaction(tmp_path):
    root = prep_root(tmp_path)
    def fetch(url):
        if url == cards()[1]["url"]:
            raise c.PublicOriginalError("source not HTTP200")
        return raw_html(cards()[0]), "text/html"
    with pytest.raises(c.PublicOriginalError):
        c.collect(cards(), fetch=fetch, root=root, observed=DATE, apply=True,
                  engine_factory=lambda: (_ for _ in ()).throw(AssertionError("used DB")))
    assert not (root / "original-snapshots").exists()


def test_database_append_failure_cleans_only_new_snapshot_files(tmp_path, monkeypatch):
    root = prep_root(tmp_path)
    engine = create_engine("sqlite+pysqlite:///" + str(tmp_path / "db.sqlite3"))
    Base.metadata.create_all(engine)
    data = cards()
    def broken_append(_session, _candidate):
        raise RuntimeError("simulated outage")
    monkeypatch.setattr(c, "append_candidate", broken_append)
    with pytest.raises(RuntimeError, match="outage"):
        c.collect(data, fetch=fake_fetch(), root=root, observed=DATE, apply=True,
                  engine_factory=lambda: create_engine(
                      "sqlite+pysqlite:///" + str(tmp_path / "db.sqlite3")
                  ))
    assert not any(root.rglob("*.html"))
    with Session(engine) as db:
        assert db.query(ProcurementLearningObservation).count() == 0
    engine.dispose()


def test_invalid_original_attestation_cannot_write_raw_secret(tmp_path):
    root = prep_root(tmp_path)
    bad = cards()[0]
    raw = raw_html(bad) + b"?auth_key=secret"
    path = c._private_path(root, bad, hashlib.sha256(raw).hexdigest())
    # The source text itself may be public HTML, but no raw source is written
    # unless the HTML passes exact original identity validation first.
    with pytest.raises(c.PublicOriginalError):
        c.snapshot_event(bad, b"No original canonical data" * 100, DATE, path)
    assert not any(root.rglob("*.html"))


def test_snapshot_symlink_and_permissions_fail_closed(tmp_path):
    root = prep_root(tmp_path)
    card = cards()[0]
    raw = raw_html(card)
    path = c._private_path(root, card, hashlib.sha256(raw).hexdigest())
    path.parent.mkdir(parents=True, mode=0o700)
    path.parent.parent.chmod(0o700)
    (root / "original-snapshots").chmod(0o700)
    path.symlink_to(tmp_path / "outside")
    with pytest.raises(c.PublicOriginalError, match="unsafe"):
        c._write_snapshot(path, raw, root)


def test_no_fake_official_legal_status_if_original_public_html_200():
    item = cards()[0]
    source = raw_html(item)
    path = Path("/private/original-snapshots/workspace/19043/") / (
        hashlib.sha256(source).hexdigest() + ".html"
    )
    candidate = c.snapshot_event(item, source, DATE, path)
    assert candidate["payload_json"]["owner_bid_go"] is False
    assert candidate["payload_json"]["company_bid_eligibility_verified"] is False
    assert candidate["payload_json"]["buyer_deadline_current_verified"] is False
    assert candidate["payload_json"]["training_labels"] == "NOT_REVIEWED"
