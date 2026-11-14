"""Offline source-bound S0 research brief; no supplier/sale claims or network calls."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path

import yaml

from .portfolio_pipeline import PortfolioInputError, _safe_public_website


def build_brief(profile_file: Path, *, root: Path) -> dict:
    if profile_file.is_symlink() or not profile_file.is_file():
        raise PortfolioInputError("profile must be a regular file")
    raw = profile_file.read_bytes()
    if not raw or len(raw) > 128_000:
        raise PortfolioInputError("profile size")
    profile = json.loads(raw)
    if not isinstance(profile, dict) or profile.get("schema_version") != "mi-supplier-profile/1":
        raise PortfolioInputError("unsupported profile schema")
    name = profile.get("profile_id")
    if not isinstance(name, str) or not re.fullmatch("[a-z][a-z0-9-]{2,62}", name):
        raise PortfolioInputError("profile id")
    supplier = profile.get("supplier")
    if not isinstance(supplier, dict):
        raise PortfolioInputError("supplier object")
    supplier_name = supplier.get("name")
    urls = supplier.get("official_portfolio_urls")
    if (not isinstance(supplier_name, str) or not supplier_name.strip()
            or len(supplier_name) > 200 or not isinstance(urls, list)
            or not 1 <= len(urls) <= 8):
        raise PortfolioInputError("supplier inputs")
    urls = [_safe_public_website(url) for url in urls]
    if len(set(urls)) != len(urls):
        raise PortfolioInputError("duplicate URL")
    study = profile.get("study")
    if not isinstance(study, dict):
        raise PortfolioInputError("study object")
    first, last = date.fromisoformat(study["from"]), date.fromisoformat(study["through"])
    if study.get("country") != "RU" or last < first or (last-first).days > 5*366:
        raise PortfolioInputError("research window")
    voltage = study.get("voltage_kv")
    if (not isinstance(voltage, list) or len(voltage) != 2
            or any(type(x) not in (int, float) for x in voltage)
            or not 0 < voltage[0] <= voltage[1] <= 1000):
        raise PortfolioInputError("voltage window")
    path = profile.get("ontology_file")
    if path != "data/market_intelligence/power_quality/ontology.v1.yaml":
        raise PortfolioInputError("unapproved ontology")
    original_ontology = (root / path).read_bytes()
    ontology = yaml.safe_load(original_ontology)
    families = {item["id"]: item for item in ontology["families"]}
    selected = profile.get("family_ids")
    if (not isinstance(selected, list) or not selected
            or any(not isinstance(family_id, str) for family_id in selected)
            or len(set(selected)) != len(selected)
            or any(family_id not in families for family_id in selected)):
        raise PortfolioInputError("unknown product family")
    # Optional product evidence is a versioned source receipt, not proof of a
    # signed order. Its path is confined to this repository for reproducibility.
    evidence_rel = profile.get("product_evidence_file")
    source_evidence = None
    if evidence_rel is not None:
        if not isinstance(evidence_rel, str):
            raise PortfolioInputError("product evidence path")
        evidence_path = root / evidence_rel
        resolved_root = root.resolve()
        if (Path(evidence_rel).is_absolute() or evidence_path.is_symlink()
                or resolved_root not in evidence_path.resolve().parents
                or evidence_path.suffix.lower() != ".json"):
            raise PortfolioInputError("product evidence must be a local JSON receipt")
        evidence_bytes = evidence_path.read_bytes()
        if not 10 <= len(evidence_bytes) <= 128_000:
            raise PortfolioInputError("product evidence size")
        evidence = json.loads(evidence_bytes)
        if (not isinstance(evidence, dict)
                or evidence.get("schema_version") != "pq-source-investigation/1"
                or evidence.get("supplier", {}).get("name") != supplier_name):
            raise PortfolioInputError("product evidence identity/schema")
        source = evidence.get("supplier_technical_primary")
        if (not isinstance(source, dict)
                or source.get("source_grade") not in {
                    "first_party_partial_quote_verified",
                    "first_party_complete_quote_verified",
                }
                or not isinstance(source.get("quotes"), list)
                or not source["quotes"]
                or not isinstance(source.get("sha256"), str)
                or len(source["sha256"]) != 64):
            raise PortfolioInputError("product evidence source grade")
        source_evidence = {
            "receipt_sha256": hashlib.sha256(evidence_bytes).hexdigest(),
            "captured_primary_sha256": source["sha256"],
            "source_grade": source["source_grade"],
            "provisional_technical_quote_count": len(source["quotes"]),
            "supplier_sale_proven": False,
        }

    return {
        "schema_version": "mi-research-brief/1", "study_id": name,
        "supplier": supplier_name, "portfolio_urls": urls,
        "profile_sha256": hashlib.sha256(raw).hexdigest(),
        "ontology_sha256": hashlib.sha256(original_ontology).hexdigest(),
        "study": study,
        "supplier_product_evidence": source_evidence,
        "search_families": [{"id": id, "positive": families[id]["positive"]}
                            for id in selected],
        "status": "S0_UNVERIFIED",
        "verified_signed_suppliers": 0,
        "verified_equipment_sales": 0,
        "next_step": "Verify supplier catalogue by model and start S1 source coverage",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    print(json.dumps(build_brief(args.profile, root=args.root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
