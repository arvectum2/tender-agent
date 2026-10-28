"""Fail-closed audit for public ETP case facts tied to archived original HTML bytes.

Buyer/organizer in a public card is distinct from a signed buyer/supplier.
Title and description are explicitly primary-platform text, not a winner proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from .pq_primary_etp_capture import MetaParser, _validated_url


def verify(*, facts: Path, source_root: Path) -> dict:
    data = json.loads(facts.read_text(encoding="utf-8"))
    if data.get("schema_version") != "pq-primary-etp-facts/1":
        raise ValueError("Invalid primary ETP facts schema")
    result = []
    seen = set()
    for row in data.get("facts", [])[:20]:
        number = row.get("procedure_id")
        slug = row.get("slug")
        if (not isinstance(number, str) or not re.fullmatch(r"\d{1,6}-\d{1,6}", number)
                or not isinstance(slug, str)
                or not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f-]{27,}", slug)
                or number in seen):
            raise ValueError("Invalid or repeated ETP case identity")
        seen.add(number)
        source_url = _validated_url(f"https://bidzaar.com/app/process/light/{slug}")
        directory = source_root / slug
        raw_file = directory / "original-public-etp.html"
        receipt_file = directory / "receipt.json"
        if (directory.is_symlink() or receipt_file.is_symlink()
                or raw_file.is_symlink() or not receipt_file.is_file()
                or not raw_file.is_file()):
            raise ValueError("Missing safe original public ETP source bytes")
        receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
        blob = raw_file.read_bytes()
        source_sha = hashlib.sha256(blob).hexdigest()
        if (receipt.get("procedure_id") != number
                or receipt.get("source_url") != source_url
                or receipt.get("original_html_sha256") != source_sha
                or row.get("expected_sha256") != source_sha):
            raise ValueError("Original HTML hash, receipt or card identity mismatch")
        parser = MetaParser()
        parser.feed(blob.decode("utf-8", errors="replace"))
        title = " ".join(parser.title.split())
        description = " ".join((parser.props.get("description") or "").split())
        if (title != receipt["source_title"]
                or description != receipt["source_description"]
                or parser.props.get("og:url") != source_url):
            raise ValueError("Original public card metadata drift")
        visible = (title + "\n" + description).casefold()
        quote = row.get("source_quote")
        if not isinstance(quote, str) or " ".join(quote.casefold().split()) not in " ".join(visible.split()):
            raise ValueError("Quote missing from original platform title/description")
        organizer = row.get("platform_displayed_organizer")
        if not isinstance(organizer, str) or organizer.casefold() not in description.casefold():
            raise ValueError("Displayed organizer missing from platform text")
        if row.get("signed_contract_verified") is not False:
            raise ValueError("Public ETP snapshot does not verify signed contract")
        result.append({
            "procedure_id": number,
            "scope": row["scope"],
            "family": row["family"],
            "platform_displayed_organizer": organizer,
            "source_quote": quote,
            "source_url": source_url,
            "source_html_sha256": source_sha,
            "source_level": "original_public_etp_html_verified",
            "winner_verified": False,
            "supplier_verified": False,
            "signed_contract_verified": False,
            "contract_price_rub": None,
            "market_volume_rub": None,
        })
    return {"schema_version": "pq-primary-etp-audit/1",
            "original_etp_cases_verified": len(result),
            "price_verified_cases": 0, "signed_contracts_verified": 0,
            "records": result}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--facts", type=Path, required=True)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    audited = verify(facts=args.facts, source_root=args.source_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audited, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(json.dumps({k: v for k, v in audited.items() if k != "records"},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
