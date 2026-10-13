"""Offline B2B-Center procedure/lot identity from source-verified HTML bytes.

Used for research deduplication only. The caller must independently establish
that bytes came from the original public platform and record the receipt.
A canonical procedure key is NEVER bidder eligibility or permission to bid.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlsplit

_CARD = re.compile(r"/market/[a-z0-9][a-z0-9-]*/tender-(\d+)/?")
_PARENT_LOT = re.compile(
    r"\bлот\s*№\s*(\d+)\s+предварительного\s+квалификационного\s+отбора\s*№\s*(\d+)",
    re.IGNORECASE,
)
_DIRECT_PROCEDURE = re.compile(
    r"\bпредварительный\s+квалификационный\s+отбор\s*№\s*(\d+)",
    re.IGNORECASE,
)
_SHA256 = re.compile(r"[0-9a-f]{64}")


class _TextFromHtml(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._ignored += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._ignored:
            self._ignored -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored:
            self._parts.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self._parts).split())


@dataclass(frozen=True)
class B2BCenterProcedureIdentity:
    state: str
    reason: str
    card_number: str | None = None
    procedure_number: str | None = None
    lot_number: str | None = None
    unique_procedure_key: str | None = None
    bid_ready: bool = False


def resolve_b2b_center_procedure_identity(
    *,
    original_card_url: str,
    original_html: bytes,
    expected_sha256: str,
) -> B2BCenterProcedureIdentity:
    """Return *procedure* identity, not an asserted separate contract or bid.

    The original card may have a distinct page ID for one lot of a parent
    prequalification. A missing/contradictory source reference abstains.
    A correctly shaped URL alone is never sufficient evidence of identity.
    """
    if not isinstance(original_html, bytes) or not isinstance(expected_sha256, str):
        return B2BCenterProcedureIdentity("REVIEW_REQUIRED", "missing_source_receipt")
    if _SHA256.fullmatch(expected_sha256) is None:
        return B2BCenterProcedureIdentity("REVIEW_REQUIRED", "invalid_source_sha256")
    if hashlib.sha256(original_html).hexdigest() != expected_sha256:
        return B2BCenterProcedureIdentity("REVIEW_REQUIRED", "source_bytes_sha256_mismatch")

    try:
        parts = urlsplit(original_card_url)
        valid_authority = (
            parts.scheme == "https"
            and parts.hostname in {"b2b-center.ru", "www.b2b-center.ru"}
            and parts.port is None and parts.username is None and parts.password is None
            and parts.query == "" and parts.fragment == ""
        )
        card = _CARD.fullmatch(parts.path) if valid_authority else None
    except (TypeError, ValueError):
        card = None
    if card is None:
        return B2BCenterProcedureIdentity("REVIEW_REQUIRED", "unsupported_original_card_url")
    number = card.group(1)

    parser = _TextFromHtml()
    parser.feed(original_html.decode("utf-8", errors="replace"))
    source_text = parser.text()
    lot_refs = set(_PARENT_LOT.findall(source_text))
    if len(lot_refs) > 1:
        return B2BCenterProcedureIdentity(
            "REVIEW_REQUIRED", "conflicting_parent_lot_references", card_number=number,
        )
    if len(lot_refs) == 1:
        lot, procedure = next(iter(lot_refs))
        if procedure == number:
            return B2BCenterProcedureIdentity(
                "REVIEW_REQUIRED", "ambiguous_same_id_lot_and_parent", card_number=number,
            )
        return B2BCenterProcedureIdentity(
            "PARENT_LOT_CONFIRMED",
            "lot_page_references_original_parent_procedure",
            card_number=number,
            procedure_number=procedure,
            lot_number=lot,
            unique_procedure_key=f"b2b-center:{procedure}",
        )

    direct_refs = set(_DIRECT_PROCEDURE.findall(source_text))
    if direct_refs == {number}:
        return B2BCenterProcedureIdentity(
            "DIRECT_PROCEDURE_CONFIRMED",
            "original_procedure_heading_matches_card_id",
            card_number=number,
            procedure_number=number,
            unique_procedure_key=f"b2b-center:{number}",
        )
    return B2BCenterProcedureIdentity(
        "REVIEW_REQUIRED",
        "conflicting_original_procedure_reference" if direct_refs else "procedure_identity_unverified",
        card_number=number,
    )
