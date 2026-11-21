"""Deterministic, source-URL-bound ETP recovery queue from the immutable MI corpus.

This is discovery, NOT evidence of a notice, award, signed contract or supplier.
The existing ETP audit handles per-URL retry/cross-journal deduplication.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from .pq_etp_card_audit import ALLOW
from .pq_gap_recovery import _source_urls

_GENERIC_PATHS = ("/category", "/category-region/", "/customers/",
                  "/integrated/", "/substation/")


def expand(*, leads_file: Path, output: Path, max_leads: int = 500,
           max_urls: int = 500) -> dict:
    if (leads_file.is_symlink() or output.is_symlink()
            or not 1 <= max_leads <= 500 or not 1 <= max_urls <= 1000):
        raise ValueError("Invalid ETP queue scope")
    leads = json.loads(leads_file.read_text(encoding="utf-8"))["records"]
    if not isinstance(leads, list) or len(leads) > max_leads:
        raise ValueError("Invalid lead corpus")
    tasks: list[dict] = []
    by_url: dict[str, dict] = {}
    skipped = {"unsafe_or_unsupported": 0, "generic_index": 0,
               "missing_identity": 0}
    for lead in leads:
        if not isinstance(lead, dict):
            raise TypeError("Invalid lead record")
        identity = str(lead.get("procedure_id") or lead.get("canonical_id")
                       or lead.get("id") or "")
        for url in _source_urls(lead):
            parsed = urlsplit(url)
            if (parsed.scheme != "https" or parsed.hostname not in ALLOW
                    or parsed.username or parsed.password
                    or parsed.port not in (None, 443) or parsed.fragment):
                skipped["unsafe_or_unsupported"] += 1
                continue
            if parsed.path.lower().startswith(_GENERIC_PATHS):
                skipped["generic_index"] += 1
                continue
            if not identity:
                skipped["missing_identity"] += 1
                continue
            if url in by_url:
                if identity not in by_url[url]["aliases"]:
                    by_url[url]["aliases"].append(identity)
                continue
            if len(tasks) >= max_urls:
                raise ValueError("ETP queue URL budget exceeded")
            task = {
                "priority": 1,
                "procedure_id": identity,
                "aliases": [identity],
                "owner": "MI-013-v20",
                "mirror": url,
                "document_targets": ["original_notice", "technical_specification",
                                     "award_protocol", "signed_contract"],
                "need": "source observation only; no original or outcome inferred",
            }
            tasks.append(task)
            by_url[url] = task
    payload = {"schema_version": "pq-etp-source-queue/1",
               "source": "immutable_corpus_urls_only",
               "original_documents_verified": False,
               "signed_contracts_verified": False,
               "skipped": skipped, "tasks": tasks}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent,
                                     prefix=".etp-queue-", delete=False) as f:
        temp = Path(f.name)
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, output)
    return {"source_leads": len(leads), "unique_urls": len(tasks),
            "skipped": skipped, "output": str(output)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--leads-file", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(expand(leads_file=args.leads_file, output=args.output),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
