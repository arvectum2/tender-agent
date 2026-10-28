"""Verify supplier product quotes against captured first-party HTML bytes.

A received but truncated source is always marked PARTIAL; no marketing claim
or HTTP 200 response establishes OEM involvement in a procurement.
"""
from __future__ import annotations

import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from .portfolio_pipeline import PortfolioInputError, _safe_public_website


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, text: str) -> None:
        if not self.hidden:
            self.parts.append(text)


def audit_supplier_html(*, source: Path, url: str, quotes: list[str],
                        transport_complete: bool) -> dict:
    url = _safe_public_website(url)
    if source.is_symlink() or not source.is_file():
        raise PortfolioInputError("source must be a regular file")
    size = source.stat().st_size
    if not 100 <= size <= 2_000_000:
        raise PortfolioInputError("HTML source outside safe size range")
    raw = source.read_bytes()
    if b"<html" not in raw.lower():
        raise PortfolioInputError("missing HTML document")
    if not isinstance(quotes, list) or not 1 <= len(quotes) <= 20:
        raise PortfolioInputError("quotes must be a bounded list")
    if not isinstance(transport_complete, bool):
        raise PortfolioInputError("transport_complete must be explicit")
    # A successful closing tag alone is insufficient to assert network
    # completeness, but its absence always disproves a complete HTML capture.
    if transport_complete and b"</html>" not in raw.lower():
        raise PortfolioInputError("truncated capture cannot be complete")
    doc = _Text()
    doc.feed(raw.decode("utf-8", errors="replace"))
    normalized = re.sub(r"\s+", " ", " ".join(doc.parts)).strip()
    verified = []
    for quote in quotes:
        if not isinstance(quote, str) or not 5 <= len(quote) <= 400:
            raise PortfolioInputError("invalid quote")
        needle = re.sub(r"\s+", " ", quote).strip()
        if needle not in normalized:
            raise PortfolioInputError("source quote not found")
        verified.append(needle)
    return {
        "schema_version": "mi-supplier-primary-source-evidence/1",
        "source_url": url,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_bytes_received": len(raw),
        "transport_complete": transport_complete,
        "source_grade": ("first_party_complete_quote_verified" if transport_complete
                         else "first_party_partial_quote_verified"),
        "verified_technical_quotes": verified,
        "verified_signed_supplier": False,
        "verified_procurement_outcome": False,
        "eligible_for_market_turnover": False,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--url", required=True)
    parser.add_argument("--quotes-json", required=True, type=Path)
    parser.add_argument("--transport-complete", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    claims = json.loads(args.quotes_json.read_text(encoding="utf-8"))
    result = audit_supplier_html(source=args.source, url=args.url, quotes=claims,
                                 transport_complete=args.transport_complete)
    if args.output.is_symlink():
        raise PortfolioInputError("output cannot be symlink")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({"source_sha256": result["source_sha256"],
                      "source_grade": result["source_grade"],
                      "verified_quote_count": len(result["verified_technical_quotes"])}))


if __name__ == "__main__":
    main()
