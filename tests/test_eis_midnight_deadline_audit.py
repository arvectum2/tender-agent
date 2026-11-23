"""Synthetic, strictly offline checks of full-EIS exact deadline evidence parsing."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.diagnostics.audit_eis_midnight_deadlines import (
    ProofFailure,
    _read_snapshot,
    _unique_notice_url,
    audit_batch,
    extract_exact_eis_deadline,
)

REGISTRY = "0845500000526000021"
URL = (
    "https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html"
    "?regNumber=0845500000526000021"
)


def _html(registry: str, date: str = "30.11.2026", clock: str = "09:00",
          zone: str = "МСК") -> str:
    return (
        f"<html><body>{registry}"
        '<section class="blockInfo__section">'
        '<span class="section__title">Дата и время окончания срока подачи заявок</span>'
        f'<span class="section__info">{date} {clock} '
        f"<span class='timeZoneName'>({zone})</span>"
        "</span></section></body></html>"
    )


@pytest.mark.parametrize(("zone", "clock", "expected"), [
    ("МСК", "09:00", "2026-11-30T06:00:00+00:00"),
    ("МСК+7", "08:00", "2026-11-13T22:00:00+00:00"),
    ("МСК-1", "10:00", "2026-11-30T08:00:00+00:00"),
    ("МСК+9", "12:00", "2026-11-30T00:00:00+00:00"),
])
def test_exact_time_and_timezone(zone, clock, expected):
    date = "14.11.2026" if zone == "МСК+7" else "30.11.2026"
    parsed = extract_exact_eis_deadline(_html(REGISTRY, date, clock, zone), REGISTRY)
    assert parsed["official_utc"] == expected
    assert parsed["official_timezone"] == zone


@pytest.mark.parametrize("page", [
    "<html>Окончание подачи заявок 30.11.2026</html>",
    _html(REGISTRY, clock=""),
    _html(REGISTRY, zone="UTC"),
    _html(REGISTRY).replace("Дата и время окончания срока подачи заявок", "Окончание подачи заявок"),
    _html(REGISTRY) * 2,
])
def test_no_invented_time_or_ambiguous_source(page):
    with pytest.raises(ProofFailure):
        extract_exact_eis_deadline(page, REGISTRY)


def test_other_notice_identity_not_accepted():
    with pytest.raises(ProofFailure, match="does not identify"):
        extract_exact_eis_deadline(_html(REGISTRY), "0119100000126000001")


@pytest.mark.parametrize("bad", [
    "https://evil.example/epz/order/notice/zk20/view/common-info.html?regNumber=" + REGISTRY,
    "http://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=" + REGISTRY,
    "https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=999",
    "https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html",
    "https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber="
    + REGISTRY + "&other=1",
])
def test_strict_first_party_identity_allowlist(bad):
    with pytest.raises(ProofFailure):
        _unique_notice_url(bad, REGISTRY)


def test_preserve_both_raw_source_and_verifiable_receipt(tmp_path: Path, monkeypatch):
    root = tmp_path / "audit"
    root.mkdir(mode=0o700)
    data = []
    for index in range(196):
        registry = f"{index:019d}"
        n = 2 if index < 102 else 1  # 204+94 = 298 rows
        for j in range(n):
            data.append({
                "id": f"{index}-{j}", "registry_number": registry,
                "law": "44fz", "source": "public_eis_html_44fz",
                "source_url": (
                    "https://zakupki.gov.ru/epz/order/notice/ea20/"
                    f"view/common-info.html?regNumber={registry}"
                ),
                "deadline_at": "2026-11-29T21:00:00+00:00",
                "stored_deadline_msk": "2026-11-30T00:00:00+03:00",
                "status": "MANAGER_READY",
            })
    snap = root / "snapshot.json"
    snap.write_text(json.dumps({
        "metadata": {
            "midnight_rows": 298, "distinct_registry": 196,
            "isolation": "repeatable_read_read_only",
        },
        "records": data,
    }))
    expected = hashlib.sha256(snap.read_bytes()).hexdigest()
    _read_snapshot(snap, expected)
    from scripts.diagnostics import audit_eis_midnight_deadlines as module

    def synthetic_fetch(url: str, registry: str) -> dict:
        assert "zakupki.gov.ru" in url
        raw = _html(registry).encode()
        return {"raw": raw, "html": raw.decode(), "status": 200}

    monkeypatch.setattr(module, "_fetch", synthetic_fetch)
    value = audit_batch(snap, expected, root, limit=1)
    assert value["processed"] == 1
    assert value["remaining"] == 195
    receipt_files = list((root / "receipts").glob("*.json"))
    assert len(receipt_files) == 1
    receipt = json.loads(receipt_files[0].read_text())
    assert receipt["status"] == "official_exact_verified"
    assert receipt["row_count"] == 2
    assert receipt["exactly_matching_rows"] == 0
    assert receipt["mismatching_rows"] == 2
    source_file = root / "html" / (receipt["registry_number"] + ".html")
    assert hashlib.sha256(source_file.read_bytes()).hexdigest() == receipt["source_html_sha256"]
    assert source_file.stat().st_mode & 0o777 == 0o600


def test_snapshot_hash_and_scope_mandatory(tmp_path: Path):
    path = tmp_path / "snapshot.json"
    path.write_text('{"metadata": {"midnight_rows": 1}, "records": []}')
    with pytest.raises(ProofFailure):
        _read_snapshot(path, hashlib.sha256(path.read_bytes()).hexdigest())
    with pytest.raises(ProofFailure):
        _read_snapshot(path, "a" * 64)
