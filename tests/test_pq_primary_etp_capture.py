import hashlib
import json
from pathlib import Path

import pytest

from src.modules.market_intelligence.pq_primary_etp_capture import (
    _validated_url, capture, batch,
)

URL = "https://bidzaar.com/app/process/light/019ce668-617b-7b1a-861e-113ed78182af"
NUMBER = "306-644"


def _html(number: str = NUMBER, address: str = URL) -> bytes:
    return (
        "<!DOCTYPE html><html><head>"
        f"<title>Тендер {number} — Монтаж УКРМ 6 кВ | Bidzaar</title>"
        f'<meta property="og:url" content="{address}">'
        '<meta name="description" content="СИБСТЕКЛО — '
        'работы по монтажу конденсаторных установок УКРМ 6 кВ">'
        "</head><body></body></html>"
    ).encode("utf-8")


def test_exact_id_and_html_sha_is_immutable(tmp_path: Path):
    result = capture(number=NUMBER, url=URL, source_root=tmp_path,
                     fetch=lambda _: (_html(), URL))
    assert result["metadata_exact_notice_verified"]
    assert result["source_evidence_verified"]
    assert result["winner_verified"] is False
    assert result["signed_contract_amount_rub"] is None
    assert result["original_html_sha256"] == hashlib.sha256(_html()).hexdigest()
    again = capture(number=NUMBER, url=URL, source_root=tmp_path,
                    fetch=lambda _: (_html("999-999"), URL))
    assert result == again
    case = tmp_path / URL.rsplit("/", 1)[-1]
    (case / "original-public-etp.html").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="changed"):
        capture(number=NUMBER, url=URL, source_root=tmp_path,
                fetch=lambda _: (_html(), URL))


@pytest.mark.parametrize("url", [
    URL.replace("https://", "http://"),
    URL.replace("bidzaar.com", "evil.bidzaar.com"),
    URL.replace("019ce668-", "../"),
    URL + "?token=x",
])
def test_reject_unapproved_original_etp_url(url: str):
    with pytest.raises(ValueError):
        _validated_url(url)


def test_mismatched_card_or_og_url_rejected(tmp_path: Path):
    with pytest.raises(ValueError, match="metadata"):
        capture(number=NUMBER, url=URL, source_root=tmp_path,
                fetch=lambda _: (_html(number="358-830"), URL))
    with pytest.raises(ValueError, match="metadata"):
        capture(number=NUMBER, url=URL, source_root=tmp_path,
                fetch=lambda _: (_html(address=URL.replace("019ce668", "019fb323")), URL))


def test_batch_resumes_without_repeated_card_download(tmp_path: Path):
    leads = tmp_path / "leads.json"
    leads.write_text(json.dumps({"records": [
        {"procedure_id": NUMBER, "evidence": [
            {"source_tier": "primary_platform", "url": URL},
            {"source_tier": "primary_platform", "url": URL}]}]}))
    journal = tmp_path / "journal.json"
    source = tmp_path / "source"
    calls = []
    def fetch(url: str):
        calls.append(url)
        return (_html(), URL)
    first = batch(leads=leads, source_root=source,
                  journal=journal, fetch=fetch)
    assert first["source_cards_verified"] == 1
    assert len(calls) == 1
    next_run = batch(leads=leads, source_root=source,
                     journal=journal, fetch=fetch)
    assert next_run["attempts"] == 0
    assert len(calls) == 1
    assert len(json.loads(journal.read_text())["attempts"]) == 1


def test_active_harmonic_filters_are_primary_pq_evidence(tmp_path: Path):
    number = "358-830"
    url = URL.replace("019ce668", "019fb323")
    body = (
        "<!DOCTYPE html><html><head>"
        f"<title>Тендер {number} — Поставка активных фильтров гармоник | Bidzaar</title>"
        f'<meta property="og:url" content="{url}">'
        '<meta name="description" content="ВАЙЛДБЕРРИЗ — поставка фильтров гармоник">'
        "</head></html>"
    ).encode()
    captured = capture(number=number, url=url, source_root=tmp_path,
                       fetch=lambda _: (body, url))
    assert captured["source_evidence_verified"] is True
    assert captured["signed_contract_amount_rub"] is None
