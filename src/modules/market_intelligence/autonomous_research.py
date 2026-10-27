"""Read-only, resumable research runner bound to the existing Power Quality corpus.

No copy of the canonical corpus is created. Outputs live outside source directories.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_CORPUS = Path("data/market_intelligence/power_quality")
DEFAULT_SEED = "verified_public_leads_20261025.v2.json"
LATEST_MANIFEST = "verified_public_leads_20261027.v20.manifest.json"
STAGES = ("S0_SCOPE", "S1_SOURCE_MAP", "S2_DISCOVERY", "S3_ACQUIRE",
          "S4_EXTRACT", "S5_TRIAGE", "S6_RESOLVE", "S7_OUTCOME",
          "S8_ENTITY_GRAPH", "S9_METRICS", "S10_AUDIT", "S11_PUBLISH")
INPUTS = (LATEST_MANIFEST, DEFAULT_SEED, "official_registry_contracts_20261026.v1.json",
          "official_case_dossiers_20261026.v1.json",
          "official_source_coverage_20261026.v5.json")


def _load(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected object")
    return value, hashlib.sha256(raw).hexdigest()


def run(*, corpus: Path, output: Path) -> dict:
    corpus = corpus.resolve()
    output = output.resolve()
    if output == corpus or corpus in output.parents:
        raise ValueError("Output must be outside the immutable source corpus")
    if output == corpus.parent or output in corpus.parents:
        raise ValueError("Output must not overwrite source directories")
    sources = {}
    for name in INPUTS:
        path = corpus / name
        value, digest = _load(path)
        sources[name] = {"sha256": digest, "path": str(path),
                         "schema_version": value.get("schema_version")}
    seed, _ = _load(corpus / DEFAULT_SEED)
    latest, _ = _load(corpus / LATEST_MANIFEST)
    records = seed.get("records")
    if not isinstance(records, list):
        raise ValueError("Missing records in PQ seed")
    contracts, _ = _load(corpus / INPUTS[1])
    # Do not upgrade the seed's secondary leads into confirmed awards.
    signed_equipment = contracts.get("equipment_only_signed_contracts_verified")
    if not isinstance(signed_equipment, int) or signed_equipment < 0:
        raise ValueError("Signed equipment verification count missing")
    manifest = {"study_id": "PQ-RU-MI013", "corpus_mode": "read_only_existing",
                "source_manifest": sources, "discovery_record_count": len(records),
                "latest_mi013_manifest": LATEST_MANIFEST,
                "latest_mi013_manifest_metadata": latest,
                "verified_equipment_only_signed_contracts": signed_equipment,
                "market_total_rub": None,
                "status": "completed_with_gaps",
                "limitations": ["This is an offline corpus-bound run, not a live EIS/ETP crawl.",
                                "Discovery seed is not a representative market population.",
                                "No national TAM inferred from incomplete source coverage."]}
    output.mkdir(parents=True, exist_ok=True)
    target = output / "manifest.json"
    if target.exists():
        old = json.loads(target.read_text(encoding="utf-8"))
        if old["source_manifest"] != sources:
            raise ValueError("Existing run has different source hashes; choose another output")
    else:
        temp = target.with_suffix(".tmp")
        temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "
", encoding="utf-8")
        os.replace(temp, target)
    events = output / "research_events.jsonl"
    if not events.exists():
        with events.open("x", encoding="utf-8") as handle:
            for i, stage in enumerate(STAGES):
                event = {"schema_version": "1.0", "event_id": f"pq-mi013-{i:02}",
                         "study_id": "PQ-RU-MI013",
                         "occurred_at": datetime.now(timezone.utc).isoformat(),
                         "stage": stage, "action": "offline_corpus_stage",
                         "candidate_id": None, "source_tier": "none",
                         "evidence": [], "decision": {"label": stage, "status": "pending"
                         if stage in ("S3_ACQUIRE", "S4_EXTRACT") else "accepted"},
                         "reason": "Offline source-bound baseline; live collection not executed",
                         "review_status": "unreviewed", "training_eligible": False}
                handle.write(json.dumps(event, ensure_ascii=False) + "
")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(corpus=args.corpus, output=args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
