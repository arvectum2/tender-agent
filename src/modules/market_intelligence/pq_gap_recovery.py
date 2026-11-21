"""Inventory missing evidence for known PQ leads and generate safe recovery work.

Discovery candidates are NOT proof. Missing fields remain unknown until an
original authoritative document verifies them.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

FIELDS = ("original_notice", "technical_specification", "award_protocol",
          "signed_contract", "winner", "initial_price", "contract_price")


def _source_urls(lead: dict, *, limit: int = 10) -> list[str]:
    """Preserve exact public URLs across all immutable MI-013 v20 delta schemas.

    Inventory only; this does not authorize downloading or promote a secondary
    index to original evidence. Retrieval adapters enforce their own allowlists.
    """
    result: list[str] = []
    for key in ("evidence", "sources", "source_url", "source", "supporting_source"):
        values = lead.get(key) or []
        if not isinstance(values, list):
            values = [values]
        for value in values:
            url = value.get("url") if isinstance(value, dict) else value
            if not isinstance(url, str) or url in result:
                continue
            parsed = urlsplit(url)
            if (parsed.scheme not in ("http", "https") or not parsed.hostname
                    or parsed.username or parsed.password):
                continue
            result.append(url)
            if len(result) == limit:
                return result
    return result


def inventory(*, leads_file: Path, source_roots: list[Path],
              queue_dir: Path, output: Path, max_leads: int = 500) -> dict:
    data = json.loads(leads_file.read_text(encoding="utf-8"))
    leads = data["records"]
    if len(leads) > max_leads or not source_roots:
        raise ValueError("Invalid lead inventory scope")
    for root in source_roots:
        if root.is_symlink():
            raise ValueError("Unsafe source root")
    existing = {}
    if queue_dir.is_dir():
        for path in queue_dir.glob("*.json"):
            if path.is_symlink():
                continue
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if row.get("schema_version") == "pq-review-queue/1":
                existing.setdefault(row["packet"]["registry_number"], []).append(row)
    results = []
    for lead in leads:
        number = str(lead.get("procedure_id") or "")
        docs = []
        for root in source_roots:
            # An unnumbered index lead is not a procurement folder. root / ""
            # would otherwise scan the entire source root and count manifests
            # as case-specific original documents.
            if not number:
                continue
            folder = root / number
            if folder.is_dir() and not folder.is_symlink():
                # Receipts prove that a retrieval was attempted; they are not
                # original procurement documents. Counting receipt-only
                # directories as source coverage overstates the denominator.
                metadata_names = {
                    "public-page-receipt.json", "download_receipt.json",
                    "source-receipt.json", "receipt.json", "manifest.json",
                }
                docs.extend(str(p) for p in folder.iterdir()
                            if p.is_file() and not p.is_symlink()
                            and p.name.lower() not in metadata_names
                            and p.suffix.lower() != ".sha256")
        reviewed = [r for r in existing.get(number, []) if r.get("state") == "reviewed"]
        evidence_urls = _source_urls(lead)
        # Source-grounded verification requires document-level inspection; no
        # winner/contract/price is considered verified from mere file presence.
        gaps = list(FIELDS)
        if docs:
            gaps.remove("original_notice") if any("notice" in Path(p).name.lower() for p in docs) else None
        if reviewed:
            gaps = [f for f in gaps if f not in ("technical_specification",)] if any(
                any("техническ" in d.get("text", "").casefold() for d in r["packet"]["documents"])
                for r in reviewed) else gaps
        results.append({
            "procedure_id": number, "canonical_id": lead.get("canonical_id"),
            "family": lead.get("family"), "scope": lead.get("scope"),
            "source_documents_local": docs[:40],
            "reviewed_packets": len(reviewed),
            "evidence_urls": evidence_urls,
            "missing_or_unverified": gaps,
            "recovery_actions": [
                "Search official EIS notice/protocol by exact procedure ID",
                "Check original ETP card and revisions for technical specification and protocols",
                "Check EIS 223/44 contract registry for signed contract, supplier and price",
                "If official source unavailable, record attempt and retry later without inferring facts",
            ],
        })
    payload = {"schema_version": "pq-evidence-gap-recovery/1",
               "generated_at": datetime.now(UTC).isoformat(),
               "lead_count": len(results), "coverage": "known_leads_only_not_market_population",
               "cases": results}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent,
                                     prefix=".gap-", delete=False) as stream:
        tmp = Path(stream.name)
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, output)
    return {"lead_count": len(results), "with_local_documents": sum(
        bool(r["source_documents_local"]) for r in results),
        "with_reviewed_packets": sum(bool(r["reviewed_packets"]) for r in results),
        "output": str(output)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--leads-file", type=Path, required=True)
    p.add_argument("--source-root", type=Path, action="append", required=True)
    p.add_argument("--queue-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(inventory(leads_file=a.leads_file, source_roots=a.source_root,
                               queue_dir=a.queue_dir, output=a.output),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
