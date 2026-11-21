import io
import zipfile

import pytest

from scripts.market_intelligence.enrich_pq_docx_fields import (
    docx_text,
    validate,
    verify_fields,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest


def fields():
    return {
        "quantity": {"value": 5, "exact_original_quote": "Количество: 5 шт.."},
        "voltage_kv": {"value": "8.3", "exact_original_quote": "Напряжение номинальное, кВ 8,3"},
        "power": {"value": "592 кВАр", "exact_original_quote": "Номинальная мощность, кВАр 592"},
    }


def test_docx_xml_quotes():
    xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           '<w:body><w:p>' + "".join(f'<w:r><w:t>{part}</w:t></w:r>'
            for part in ("Количество: 5 шт..", "Напряжение номинальное, кВ 8,3",
                         "Номинальная мощность, кВАр 592")) + '</w:p></w:body></w:document>')
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("word/document.xml", xml)
    verify_fields(fields(), docx_text(out.getvalue()))


def test_rejects_unproven_quantity():
    f = fields()
    f["quantity"]["value"] = 6
    with pytest.raises(ValueError, match="does not prove"):
        verify_fields(f, " ".join(v["exact_original_quote"] for v in fields().values()))


def test_rejects_conflicting_preexisting_field():
    data = {"quantity": 1, "voltage_kv": None, "power": None,
            "evidence": [{"url": "https://zakupki.gov.ru/example", "sha256": "a" * 64}]}
    row = {"id": "223fz:32616266007:lot1", "owner": "tender-agent",
           "hash": digest(data), "rev": 1, "data": data, "meta": {}}
    m = {"canonical_id": row["id"], "expected_content_hash": row["hash"],
         "expected_revision": 1, "source_url": "https://zakupki.gov.ru/example",
         "source_sha256": "a" * 64}
    with pytest.raises(RuntimeError, match="Conflicting"):
        validate(m, row)


def test_rejects_source_unbound():
    data = {"quantity": None, "voltage_kv": None, "power": None, "evidence": []}
    row = {"id": "223fz:32616266007:lot1", "owner": "tender-agent",
           "hash": digest(data), "rev": 1, "data": data, "meta": {}}
    m = {"canonical_id": row["id"], "expected_content_hash": row["hash"],
         "expected_revision": 1, "source_url": "https://zakupki.gov.ru/example",
         "source_sha256": "a" * 64}
    with pytest.raises(RuntimeError, match="not bound"):
        validate(m, row)
