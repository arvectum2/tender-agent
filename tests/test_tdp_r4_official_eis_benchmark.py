"""R4 source/oracle/score fail-closed regressions; no model or EIS network."""

from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "acceptance"))
from benchmark_r4_official_eis import build_case, run, score

REG = "0372200172326000015"


def _make_source(tmp_path: Path) -> tuple[dict[str, str], Path]:
    root = tmp_path / REG
    root.mkdir()
    older = (f"<root><epNotificationEZK><versionNumber>1</versionNumber>"
             f"<purchaseNumber>{REG}</purchaseNumber><endDT>2026-10-01T10:00:00+03:00</endDT>"
             "<maxPrice>20.00</maxPrice></epNotificationEZK></root>").encode()
    latest = (f"<root><epNotificationEZK><versionNumber>2</versionNumber>"
              f"<purchaseNumber>{REG}</purchaseNumber><endDT>2026-10-12T08:00:00+03:00</endDT>"
              "<maxPrice>10.00</maxPrice><attachment><versionNumber>99</versionNumber>"
              "</attachment></epNotificationEZK></root>").encode()
    with zipfile.ZipFile(root / "documentation-archive.zip", "w") as z:
        z.writestr("first.xml", older)
        z.writestr("latest.xml", latest)
    return {
        "reg_number": REG, "official_SOAP_status": "completed",
        "official_zip_sha256": hashlib.sha256((root / "documentation-archive.zip").read_bytes()).hexdigest(),
        "highest_official_archived_version": "2",
        "highest_archive_endDT": "2026-10-12T08:00:00+03:00",
        "highest_archive_max_price_RUB": "10.00",
    }, tmp_path


def test_source_oracle_follows_latest_direct_notice_version(tmp_path: Path) -> None:
    row, archives = _make_source(tmp_path)
    case = build_case(row, archives)
    assert case["oracle"] == {
        "purchase_number": REG, "notice_version": 2,
        "deadline": "2026-10-12T08:00:00+03:00", "max_price_rub": "10.00",
    }
    assert "99" not in case["source_excerpt"]
    assert "<maxPrice>10.00</maxPrice>" in case["source_excerpt"]


@pytest.mark.parametrize("column,alter", [
    ("official_zip_sha256", "0" * 64),
    ("highest_official_archived_version", "99"),
    ("highest_archive_endDT", "2026-10-01"),
    ("highest_archive_max_price_RUB", "12.00"),
])
def test_wrong_oracle_source_receipt_fails_closed(
    tmp_path: Path, column: str, alter: str,
) -> None:
    row, archives = _make_source(tmp_path)
    row[column] = alter
    with pytest.raises(ValueError):
        build_case(row, archives)


def test_score_no_numerical_or_revision_hallucinations() -> None:
    gold = {"purchase_number": REG, "notice_version": 2,
            "deadline": None, "max_price_rub": "1000.00"}
    exact = {**gold, "max_price_rub": "1000"}
    assert all(score(gold, exact).values())
    guess = {**exact, "deadline": "2026-10-12", "notice_version": "2"}
    assert score(gold, guess) == {
        "purchase_number": True, "notice_version": False,
        "deadline": False, "max_price_rub": True,
    }
    assert not any(score(gold, {**exact, "decision": "GO"}).values())


def test_no_missing_cases_or_non_loopback_are_permitted(tmp_path: Path) -> None:
    row, archives = _make_source(tmp_path)
    with pytest.raises(ValueError, match="non_loopback"):
        run([row], archives, "https://unapproved.example", "mock", 5, 1, True)
    with pytest.raises(ValueError, match="exactly_20"):
        run([row], archives, "http://127.0.0.1:8081", "mock", 5, 1, True)
