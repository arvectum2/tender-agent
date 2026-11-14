"""Source-bound signed-contract reconciliation in frozen V21 client dossiers."""
import json
from pathlib import Path

import pymupdf

DOCS = Path("docs/market_intelligence")
SNAP = Path("data/market_intelligence/power_quality/fgi_client_deck_snapshot_20261031_v21.json")


def test_v21_signed_registry_and_no_supplier_invention():
    data = json.loads(SNAP.read_text())
    assert data["unique_lots"] == 118
    row = next(x for x in data["items"] if x["id"] == "223fz:32616266007:lot1")
    assert row["signed_contract_verified"] is True
    assert row["signed_supplier_verified"] is False
    assert row["paid_verified"] is False
    assert row["contract_no"] == "1605245"
    assert row["contract_price"] == "662460.00"
    for lang in ("RU", "EN"):
        with pymupdf.open(DOCS / f"ARVECTUM_FGI_PQ_FULL_{lang}_20261031_V21.pdf") as pdf:
            assert len(pdf) == 258
            dossier = pdf[77].get_text()
            evidence = pdf[78].get_text()
            assert "1605245" in dossier and ("662 460" in dossier or "662,460" in dossier)
            assert "поставщик-подписант и оплата не установлены" in " ".join(dossier.split())
            assert "но подпись и исполнение не доказаны" not in dossier
            assert "Не установлено" in evidence or "Not verified" in evidence
