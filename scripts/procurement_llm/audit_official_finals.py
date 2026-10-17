"""Independently check archived EIS final XML protocols, never infer company identity.

Read only existing ArvectumSSD EIS ZIPs. Official fields are not human-gold labels.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from scripts.procurement_llm.source_recovery import inspect_final_eis_protocol

ROOT = Path("/Volumes/ArvectumSSD/Arvectum/data/tenders/eis")
_MAX_ORIGINAL_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class SourceSpec:
    registry: str
    application: str
    zip_sha256: str
    xml_sha256: str
    price_rub: str
    app_rating: str
    total_applications: int
    admitted_applications: int
    winner_price_rub: str


SPECS = (
    SourceSpec(
        "0187200001726001304", "3630084",
        "39fef1af482907b2c2382518d339d932e09197c2e36e68a6134fc5910ff7dd18",
        "183023905c0af4bca1f1468ea09837e7c85a86068a48f71f87db2b908da70ec4",
        "399000", "6", 17, 12, "119000",
    ),
    SourceSpec(
        "0158300034526000388", "122031738",
        "d25187191599e705427676cc9de64ce665029381efa2490607d65ff237837bb8",
        "2b9f510c48e7d828c432e32b4dca3a4fff8edb75c66c3da37d46a12af3456af5",
        "119000", "38", 55, 45, "28400",
    ),
)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _leaf_value(node: ET.Element, name: str) -> str | None:
    vals = {
        (e.text or "").strip()
        for e in node.iter()
        if _local(e.tag) == name and len(e) == 0
    }
    if len(vals) > 1:
        raise ValueError(f"Ambiguous official {name} field")
    return next(iter(vals), None)


def audit_original(path: Path, spec: SourceSpec) -> dict:
    """Fail closed if the archived original, registry or any source field differs."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_ORIGINAL_BYTES:
        raise ValueError("Missing or invalid canonical original ZIP")
    archive_sha = sha256(path.read_bytes()).hexdigest()
    if archive_sha != spec.zip_sha256:
        raise ValueError("Archived EIS original ZIP SHA mismatch")
    source = inspect_final_eis_protocol(path, spec.registry, spec.application)
    if source["original_archive_sha256"] != archive_sha:
        raise ValueError("Unstable archived EIS source")
    if source["protocol_xml_sha256"] != spec.xml_sha256:
        raise ValueError("Official EIS protocol XML SHA mismatch")
    if source["admitted_in_protocol"] != "true":
        raise ValueError("Target application not admitted in original EIS")
    if source["application_rating"] != spec.app_rating:
        raise ValueError("Target appRating differs from original EIS")
    try:
        if Decimal(source["final_price_rub"]) != Decimal(spec.price_rub):
            raise ValueError("Target bid price differs from original EIS")
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("Bad bid price in official EIS") from exc

    with ZipFile(path) as archive:
        data = archive.read(source["protocol_member"])
    if len(data) > _MAX_ORIGINAL_BYTES or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("Unsafe official EIS XML")
    root = ET.fromstring(data)
    rows = []
    for application in root.iter():
        if _local(application.tag) != "applicationInfo":
            continue
        number = _leaf_value(application, "appNumber")
        price = _leaf_value(application, "finalPrice")
        rating = _leaf_value(application, "appRating")
        admitted = _leaf_value(application, "admitted")
        if not number or not price or admitted not in {"true", "false"}:
            raise ValueError("Malformed EIS application row")
        try:
            price_value = Decimal(price)
        except InvalidOperation as exc:
            raise ValueError("Bad official EIS application price") from exc
        if price_value < 0:
            raise ValueError("Negative official EIS application price")
        if admitted == "true" and (not rating or not rating.isdigit()):
            raise ValueError("Admitted EIS application has no appRating")
        if admitted == "false" and rating is not None:
            raise ValueError("Rejected EIS application has unexpected rating")
        rows.append((number, price_value, int(rating) if rating else None, admitted == "true"))

    if len(rows) != spec.total_applications:
        raise ValueError("Official EIS original total application count mismatch")
    if len({r[0] for r in rows}) != len(rows):
        raise ValueError("Duplicate application ID in original EIS")
    accepted = [r for r in rows if r[3]]
    if len(accepted) != spec.admitted_applications:
        raise ValueError("Official EIS admitted count mismatch")
    if sorted(r[2] for r in accepted) != list(range(1, len(accepted) + 1)):
        raise ValueError("Official appRatings not contiguous")
    winning = next(r for r in accepted if r[2] == 1)
    if winning[1] != Decimal(spec.winner_price_rub):
        raise ValueError("Official EIS winner price mismatch")
    selected = next((r for r in rows if r[0] == spec.application), None)
    if selected != (spec.application, Decimal(spec.price_rub), int(spec.app_rating), True):
        raise ValueError("Official EIS target application data mismatch")

    return {
        "registry": spec.registry,
        "application_number": spec.application,
        "admitted": True,
        "final_price_rub": str(selected[1]),
        "app_rating_raw": str(selected[2]),
        "official_winner_price_rub": str(winning[1]),
        "official_winner_application_number": winning[0],
        "total_applications": len(rows),
        "admitted_applications": len(accepted),
        "original_zip_sha256": archive_sha,
        "original_xml_sha256": source["protocol_xml_sha256"],
        "identity_attribution_in_this_xml": False,
        "operator_email_identity_link_checked_offline_here": False,
        "training_ready": False,
        "mutations": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eis-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    if args.eis_root.is_symlink() or not args.eis_root.is_dir():
        parser.error("Existing canonical EIS root required")
    result = [
        audit_original(args.eis_root / s.registry / "documentation-archive.zip", s)
        for s in SPECS
    ]
    print(json.dumps({"source_class": "original_official_eis_final_xml", "cases": result,
                      "new_postgres_records": 0, "human_gold": 0},
                     ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
