import json
from pathlib import Path

import pytest

from src.modules.market_intelligence.pq_primary_etp_capture import capture
from src.modules.market_intelligence.pq_primary_etp_audit import verify

URL = "https://bidzaar.com/app/process/light/019fb323-f23b-7872-845e-ba2cb6b43355"


def _setup(tmp_path: Path):
    number = "358-830"
    body = (
        "<!DOCTYPE html><html><head>"
        f"<title>Тендер {number} — Поставка активных фильтров гармоник | Bidzaar</title>"
        f'<meta property="og:url" content="{URL}">'
        '<meta name="description" content="ВАЙЛДБЕРРИЗ — '
        'Поставка активных фильтров гармоник">'
        "</head></html>"
    ).encode()
    root = tmp_path / "snapshots"
    d = capture(number=number, url=URL, source_root=root,
                fetch=lambda _: (body, URL))
    facts = tmp_path / "facts.json"
    facts.write_text(json.dumps({"schema_version": "pq-primary-etp-facts/1",
                                 "facts": [{
                                     "procedure_id": number,
                                     "slug": URL.rsplit("/", 1)[-1],
                                     "expected_sha256": d["original_html_sha256"],
                                     "source_quote": "Поставка активных фильтров гармоник",
                                     "platform_displayed_organizer": "ВАЙЛДБЕРРИЗ",
                                     "scope": "equipment_supply_tender",
                                     "family": "active_harmonic_filter",
                                     "signed_contract_verified": False
                                 }]}))
    return facts, root


def test_verified_primary_etp_demand_is_not_signed_contract(tmp_path: Path):
    facts, root = _setup(tmp_path)
    r = verify(facts=facts, source_root=root)
    assert r["original_etp_cases_verified"] == 1
    assert r["signed_contracts_verified"] == 0
    assert r["records"][0]["contract_price_rub"] is None
    assert r["records"][0]["platform_displayed_organizer"] == "ВАЙЛДБЕРРИЗ"


def test_reject_unquoted_fact_or_tampered_byte(tmp_path: Path):
    facts, root = _setup(tmp_path)
    data = json.loads(facts.read_text())
    data["facts"][0]["source_quote"] = "Поставка реакторов сверхвысоких частот"
    facts.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Quote missing"):
        verify(facts=facts, source_root=root)
    data["facts"][0]["source_quote"] = "Поставка активных фильтров гармоник"
    facts.write_text(json.dumps(data))
    html = next(root.glob("*/original-public-etp.html"))
    html.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash"):
        verify(facts=facts, source_root=root)


def test_reject_signed_claim(tmp_path: Path):
    facts, root = _setup(tmp_path)
    data = json.loads(facts.read_text())
    data["facts"][0]["signed_contract_verified"] = True
    facts.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="signed contract"):
        verify(facts=facts, source_root=root)
