"""Evidence-bound lexical document triage, not semantic or award acceptance."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import defaultdict
from pathlib import Path

PATTERNS = {
    "electrical": r"электрооборудован|электроснабжен|электродвигател|трансформатор|распределительн.{0,20}устройств|\bкру\b|\bктп\b|\bрза\b|электротехник|электропривод|частотн.{0,15}преобразовател",
    "automation_instrumentation": r"\bасу\s*тп\b|\bкип(?:иа)?\b|автоматизац|газоанализатор|контроллер|расходомер|датчик|метрологи|телемеханик|измерительн",
    "power_quality": r"\bукрм\b|\bstatcom\b|статком|компенсац.{0,25}реактив|фильтр.{0,20}гармоник|качество электроэнерг|тиристорн.{0,25}компенсатор",
    "engineering_epc": r"проектирован|проектн.{0,20}работ|модернизац|реконструкц|пусконалад|\bпнр\b|\bсмр\b|строительно-монтаж|\bepc\b|техническ.{0,15}перевооруж",
}


def classify_text(text, cap=3):
    evidence = {}
    for category, pattern in PATTERNS.items():
        matches = []
        for m in re.finditer(pattern, text, re.IGNORECASE):
            start = max(0, m.start() - 85)
            end = min(len(text), m.end() + 85)
            matches.append({"start": start, "end": end,
                            "excerpt": text[start:end], "match": m.group()})
            if len(matches) == cap:
                break
        if matches:
            evidence[category] = matches
    return evidence


def build(root):
    docs = root / "documents"
    claims = defaultdict(set)
    records = {}
    for f in sorted(docs.glob("*.json")):
        if len(f.stem) != 64:
            continue
        r = json.loads(f.read_text())
        if r["status"] != "captured":
            continue
        sha = r["sha256"]
        original = docs / r["file"]
        if hashlib.sha256(original.read_bytes()).hexdigest() != sha:
            raise ValueError("original identity mismatch")
        claims[sha].update(x["external_id"] for x in r["references"])
    for f in sorted(docs.glob("*.dp-result.json")):
        row = json.loads(f.read_text())
        sha, result = row["source_sha256"], row["result"]
        if sha not in claims:
            continue
        if result["canonical_uri"] != "content-sha256://" + sha:
            raise ValueError("extraction receipt mismatch")
        text = result["text"]
        record = {"source_sha256": sha, "procedure_ids": sorted(claims[sha]),
                  "document_id": result["document_id"], "extraction_status": result["extraction_status"],
                  "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                  "possible_text_cap": len(text) >= 200000,
                  "classification": "LEXICAL_CANDIDATE_REQUIRES_REVIEW",
                  "matches": classify_text(text) if result["extraction_status"] == "extracted" else {}}
        if sha in records and records[sha] != record:
            raise ValueError("extraction versions disagree")
        records[sha] = record
    return [records[k] for k in sorted(records)]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    os.umask(0o077)
    if args.output.resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError("private excerpts cannot be written into repository")
    records = build(args.root)
    with args.output.open("x") as stream:
        json.dump(records, stream, ensure_ascii=False, indent=2)
    print("processed", len(records), "candidates", sum(bool(r["matches"]) for r in records))


if __name__ == "__main__":
    main()
