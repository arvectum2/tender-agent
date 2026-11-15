"""Aksay vs Aksioma: exact official EIS notice subject scope, read-only exclusion."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from scripts.procurement_llm.audit_official_finals import SPECS, audit_original

AKSAY = "0158300034526000388"
AKSIOMA = "0187200001726001304"
MAX_ZIP = 32 * 1024 * 1024
MAX_XML = 2 * 1024 * 1024
EXPECTED_AKSAY = "Услуга по разработке веб сайта"
AKSIOMA_ANCHORS = (
    "Оказание услуг по разработке модуля",
    "пересечений границ земельных участков",
    "землями лесного фонда",
    "географическая информационная система",
    "Аксиома",
)


def original_notice_subject(path: Path, registry_number: str) -> dict:
    """Source identity is pinned by the shared original EIS final-audit spec."""
    spec = next((spec for spec in SPECS if spec.registry == registry_number), None)
    if spec is None or not path.is_file() or path.is_symlink():
        raise ValueError("unrecognized or unavailable official EIS archive")
    if not 1 <= path.stat().st_size <= MAX_ZIP:
        raise ValueError("invalid official EIS archive size")
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if sha != spec.zip_sha256:
        raise ValueError("official ZIP SHA mismatch")
    # Reuse the already maintained original final-protocol signature checks.
    audit_original(path, spec)
    regex = re.compile(rf"epNotificationEZK2020_{registry_number}_(\d+)_.*\.xml\Z")
    with ZipFile(path) as archive:
        candidates = []
        for member in archive.infolist():
            match = regex.fullmatch(member.filename)
            if match:
                candidates.append((int(match.group(1)), member))
        if not candidates:
            raise ValueError("official notice source not present")
        version = max(v for v, _ in candidates)
        current = [item for v, item in candidates if v == version]
        if len(current) != 1:
            raise ValueError("latest official notice version ambiguous")
        member = current[0]
        if not 1 <= member.file_size <= MAX_XML:
            raise ValueError("official notice XML invalid size")
        data = archive.read(member)
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("unsafe official notice XML")
    root = ET.fromstring(data)
    subjects = [
        " ".join((node.text or "").split())
        for node in root.iter()
        if node.tag.rsplit("}", 1)[-1] == "purchaseObjectInfo"
        and (node.text or "").strip()
    ]
    if len(subjects) != 1 or not 10 <= len(subjects[0]) <= 700:
        raise ValueError("procurement original subject ambiguous")
    return {
        "procurement_number": registry_number,
        "original_eis_zip_sha256": sha,
        "source_notice_member_sha256": hashlib.sha256(data).hexdigest(),
        "notice_version": version,
        "original_procurement_subject": subjects[0],
        "source_is_original_verified_notice": True,
    }


def assess_narrow_web_vs_gis(aksay: dict, aksioma: dict) -> dict:
    """This exact pair is a negative sample, not a universal SOW classifier."""
    if aksay["procurement_number"] != AKSAY or aksioma["procurement_number"] != AKSIOMA:
        raise ValueError("comparison source identity changed")
    if aksay["original_procurement_subject"] != EXPECTED_AKSAY:
        raise ValueError("website subject no longer attested")
    candidate = aksioma["original_procurement_subject"]
    if not all(part.casefold() in candidate.casefold() for part in AKSIOMA_ANCHORS):
        raise ValueError("GIS module original scope no longer attested")
    return {
        "schema_version": "ta-price01-source-verified-negative-comparator-v1",
        "candidate_count": 1,
        "approved_additional_comparable_procurements": 0,
        "cross_procurement_compatible_count_for_aksay_website": 1,
        "original_sources": [aksay, aksioma],
        "candidate_registry_number": AKSIOMA,
        "candidate_comparability": "EXCLUDED_SCOPE_MISMATCH",
        "reason": "Aksay is a public website creation, Aksioma is a forestry land-parcel intersection module for an existing geographic information system; different deliverables and pricing basis.",
        "candidate_price_must_not_be_in_aksay_website_distribution": True,
        "price_forecast_performed": False,
        "autonomous_bid_performed": False,
    }


def collect(*, root: Path) -> dict:
    a = original_notice_subject(root / AKSAY / "documentation-archive.zip", AKSAY)
    b = original_notice_subject(root / AKSIOMA / "documentation-archive.zip", AKSIOMA)
    return assess_narrow_web_vs_gis(a, b)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eis-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = collect(root=args.eis_root)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(report["candidate_registry_number"], report["candidate_comparability"],
          "COMPARABLE", report["cross_procurement_compatible_count_for_aksay_website"])


if __name__ == "__main__":
    main()
