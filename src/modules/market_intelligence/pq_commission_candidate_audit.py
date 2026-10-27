"""Conservative, source-quoted bidder candidates from reviewed commission protocols.

The identity of a person named in a protocol is not automatically the legally
contracted supplier. OCR candidates remain provisional until visual validation.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ORG = r'(?:ООО|ОБЩЕСТВО\s+С\s+ОГРАНИЧЕННОЙ\s+ОТВЕТСТВЕННОСТЬЮ)\s*[«"]([^»"]{2,110})[»"]'
PROPOSED = re.compile(r"(?i)признать\s+победителем.{0,260}?а\s+именно:\s*" + ORG, re.S)
ELIGIBLE = re.compile(r"(?i)(?:заявк[иа]\s+участник[а-я]*).{0,170}?" + ORG
                      + r".{0,120}?призна[ею]тся\s+соответствующими", re.S)
MAX_PACKETS = 500
MAX_TEXT = 100_000


def extract(*, outcome_path: Path, queue_dir: Path, max_packets: int = 300) -> dict:
    if not 1 <= max_packets <= MAX_PACKETS or queue_dir.is_symlink():
        raise ValueError("Invalid review queue budget")
    outcomes = json.loads(outcome_path.read_text(encoding="utf-8"))["records"]
    relevant = {str(x["procedure_id"]) for x in outcomes}
    records = []
    seen = set()
    files_seen = 0
    for file in sorted(queue_dir.glob("*.json")):
        if files_seen >= max_packets:
            break
        if file.is_symlink() or file.stat().st_size > 2_000_000:
            continue
        data = json.loads(file.read_text(encoding="utf-8"))
        if data.get("schema_version") != "pq-review-queue/1" or data.get("state") != "reviewed":
            continue
        packet = data.get("packet") or {}
        number = str(packet.get("registry_number") or "")
        if number not in relevant:
            continue
        files_seen += 1
        for doc in packet.get("documents", [])[:12]:
            text = str(doc.get("text") or "")[:MAX_TEXT]
            digest = doc.get("sha256")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                continue
            method = str(doc.get("method") or "")
            ocr = "ocr" in method.lower()
            for pattern, role in ((PROPOSED, "commission_proposed_winner"),
                                  (ELIGIBLE, "bidder_qualified_for_consideration")):
                for match in list(pattern.finditer(text))[:8]:
                    name = " ".join(match.group(1).split())
                    if not name or len(name) > 110:
                        continue
                    key = (number, role, name.casefold(), digest)
                    if key in seen:
                        continue
                    seen.add(key)
                    records.append({
                        "procedure_id": number,
                        "candidate_name": name,
                        "role_in_protocol": role,
                        "evidence_excerpt": text[match.start():match.end()][:550],
                        "source_document_sha256": digest,
                        "source_document_filename": doc.get("filename"),
                        "extraction_method": method,
                        "ocr_visual_review_required": ocr,
                        "contract_supplier_verified": False,
                        "award_legally_verified": False,
                    })
    return {
        "schema_version": "pq-commission-candidate-evidence/1",
        "contracts_considered": len(relevant),
        "review_packets_examined": files_seen,
        "candidate_mentions": len(records),
        "records": records,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--outcomes", type=Path, required=True)
    p.add_argument("--queue-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = extract(outcome_path=args.outcomes, queue_dir=args.queue_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "records"},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
