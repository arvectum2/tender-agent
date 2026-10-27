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
    contracts, _ = _load(corpus / "official_registry_contracts_20261026.v1.json")
    # Do not upgrade the seed's secondary leads into confirmed awards.
    signed_equipment = contracts.get("equipment_only_signed_contracts_verified")
    if signed_equipment is not None and (type(signed_equipment) is not int or signed_equipment < 0):
        raise ValueError("Invalid signed equipment verification count")
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
        temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, target)
    events = output / "research_events.jsonl"
    if events.exists():
        existing_events = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
        if len(existing_events) != len(STAGES) or [event.get("stage") for event in existing_events] != list(STAGES):
            raise ValueError("Existing research event journal is incomplete or corrupt")
    else:
        with events.open("x", encoding="utf-8") as handle:
            for i, stage in enumerate(STAGES):
                event = {"schema_version": "1.0", "event_id": f"pq-mi013-{i:02}",
                         "study_id": "PQ-RU-MI013",
                         "occurred_at": datetime.now(timezone.utc).isoformat(),
                         "stage": stage, "action": "offline_corpus_stage",
                         "candidate_id": None, "source_tier": "none",
                         "evidence": [], "decision": {"label": stage, "status": "pending"
                         if stage not in ("S0_SCOPE", "S1_SOURCE_MAP") else "accepted"},
                         "reason": "Offline source-bound baseline; live collection not executed",
                         "review_status": "unreviewed", "training_eligible": False}
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return manifest


def run_eis_batch(*, root: Path, ontology: Path, first, last, regions: list[str],
                  subsystems: list[str], max_calls: int = 4, execute: bool = False,
                  client=None) -> dict:
    """Bounded EIS source-day discovery; execute=True uses existing audited collector."""
    from .eis_history_plan import execute_plan, plan_history
    import yaml
    plan = plan_history(root=root, first=first, last=last, regions=regions,
                        subsystems=subsystems, max_calls=max_calls)
    if not execute:
        return {"plan": plan, "outcomes": [], "live_executed": False}
    terms = yaml.safe_load(ontology.read_text(encoding="utf-8"))
    outcomes = execute_plan(plan=plan, root=root, ontology=terms, client=client)
    return {"plan": plan, "outcomes": outcomes, "live_executed": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--eis-root", type=Path)
    parser.add_argument("--ontology", type=Path)
    parser.add_argument("--date-from", type=lambda x: __import__("datetime").date.fromisoformat(x))
    parser.add_argument("--date-to", type=lambda x: __import__("datetime").date.fromisoformat(x))
    parser.add_argument("--region", action="append")
    parser.add_argument("--subsystem", action="append")
    parser.add_argument("--max-calls", type=int, default=2)
    parser.add_argument("--execute-eis", action="store_true")
    args = parser.parse_args()
    result = run(corpus=args.corpus, output=args.output)
    eis_args = (args.eis_root, args.ontology, args.date_from, args.date_to,
                args.region, args.subsystem)
    if any(eis_args):
        if not all(eis_args):
            parser.error("EIS batch requires root, ontology, dates, regions and subsystems")
        batch = run_eis_batch(root=args.eis_root, ontology=args.ontology,
                              first=args.date_from, last=args.date_to,
                              regions=args.region, subsystems=args.subsystem,
                              max_calls=args.max_calls, execute=args.execute_eis)
        result["eis_batch"] = batch
        target = args.output.resolve() / "eis_batch.json"
        if target.exists() and json.loads(target.read_text(encoding="utf-8")) != batch:
            raise ValueError("EIS batch differs from previous run; use another output directory")
        target.write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
