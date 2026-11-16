"""Conservative parser for server-captured public commercial cards.

Input is a trusted transport observation, never a client-supplied proof of HTTP/TLS.
This pure function performs no HTTP, storage, tenant admission or external action.
Unknown layouts fail closed; live adapter acceptance is a separate gate.
"""
from __future__ import annotations

import hashlib
import re
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from lxml import html

from src.modules.saas_foundation.commercial_sources import commercial_identity

MAX_CARD_BYTES = 900_000
MOSCOW = ZoneInfo("Europe/Moscow")
MONTHS = {name: month for month, name in enumerate(("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"), 1)}
RECEIVING = {"прием заявок", "идет прием заявок"}
TERMINAL = {"завершен", "завершено", "прием заявок завершен", "отменен", "отменено", "закрыт"}


def _norm(value):
    return " ".join(value.casefold().replace("ё", "е").split())


def _one(values, field):
    if len(values) != 1 or not values[0]:
        raise ValueError(f"Missing or ambiguous public card {field}")
    return values[0]


def _text(node):
    return " ".join(node.text_content().split())


def _label_value(values, labels, pattern, field):
    """Require one visible label and a bounded immediately following value."""
    matches = []
    for i, value in enumerate(values):
        for label in labels:
            if value.startswith(label):
                tail = value[len(label):].strip() or (values[i + 1] if i + 1 < len(values) else "")
                matches.append(tail)
                break
    value = _one(matches, field)
    if not re.fullmatch(pattern, value):
        raise ValueError(f"Unrecognized public card {field}")
    return value


def verify_card_snapshot(*, requested_url: str, final_url: str, status_code: int, tls_verified: bool,
                         content_type: str, raw: bytes, observed_at: datetime) -> dict:
    platform, external_id = commercial_identity(requested_url)
    if final_url != requested_url or status_code != 200 or tls_verified is not True:
        raise ValueError("Exact successful TLS card observation required")
    if content_type.split(";", 1)[0].strip().lower() != "text/html":
        raise ValueError("Expected public HTML")
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_CARD_BYTES:
        raise ValueError("Invalid public card size")
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("Observation requires timezone")
    tree = html.fromstring(raw.decode("utf-8", errors="strict"), parser=html.HTMLParser(no_network=True))
    # Canonical metadata may corroborate, but conflicting metadata never passes.
    declared = tree.xpath('//link[@rel="canonical"]/@href | //meta[@property="og:url"]/@content')
    if any(value != requested_url for value in declared):
        raise ValueError("Card canonical identity mismatch")
    for element in tree.xpath('//script|//style|//noscript|//svg|//template|//*[@hidden or @aria-hidden="true"]'):
        if element.getparent() is not None:
            element.drop_tree()
    title = _one([_text(n) for n in tree.xpath('//h1')], "heading")
    if not 5 < len(title) <= 500:
        raise ValueError("Invalid public heading")
    visible = [" ".join(v.split()) for v in tree.xpath('//body//text()') if v.strip()]
    if platform == "workspace":
        # The existing original-card audit establishes these exact CSS/label anchors.
        # Require a corroborating canonical identity rather than a generic login/list page.
        if not declared:
            raise ValueError("Workspace body has no corroborating canonical URL")
        stage = _one([_text(n) for n in tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," tendercart-type__status-public ")]')], "stage")
        visibility = _one(tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," reference ") and (contains(concat(" ",normalize-space(@class)," ")," _public ") or contains(concat(" ",normalize-space(@class)," ")," _private "))]/@class'), "visibility")
        classes = set(visibility.split())
        if len(classes & {"_public", "_private"}) != 1 or "_public" not in classes:
            raise ValueError("Not a public Workspace card")
        organizer = _label_value(visible, ("Oрганизатор", "Организатор"), r"Юридическое лицо|Частное лицо", "organizer type")
        deadline_literal = _label_value(visible, ("Крайний срок приема заявок:",), r"\d{1,2} [А-Яа-яё]+ 20\d{2}", "deadline")
        day, month, year = deadline_literal.casefold().split()
        if month not in MONTHS:
            raise ValueError("Unrecognized deadline month")
        deadline = date(int(year), MONTHS[month], int(day)).isoformat()
        precision = "date_only"
        organizer_type, organizer_name = organizer, None
    else:
        # Legacy cards include the number in the heading. Observed market-next
        # layout instead uses a separate visible exact ID and a canonical URL.
        # Do not accept an incidental substring, hidden ID, or ambiguous match.
        heading_matches = bool(re.search(r"(?<![0-9])" + re.escape(external_id) + r"(?![0-9])", title))
        if not heading_matches:
            standalone = [v for v in visible[:150] if re.fullmatch(r"(?:№\s*|N\s*|Номер(?: закупки)?:?\s*)?" + re.escape(external_id), v, re.IGNORECASE)]
            if not declared or len(standalone) != 1:
                raise ValueError("B2B heading or canonical standalone number does not corroborate requested number")
        stage = _one([v for v in visible[:100] if _norm(v) in RECEIVING | TERMINAL], "stage")
        deadline_literal = _one([v for v in visible[:120] if re.fullmatch(r"до \d{2}\.\d{2}\.20\d{2} \d{2}:\d{2}, по МСК", v)], "deadline")
        deadline = datetime.strptime(deadline_literal, "до %d.%m.%Y %H:%M, по МСК").replace(tzinfo=MOSCOW).isoformat()
        precision = "moscow_minute"
        # A printed legal-name prefix is not proof of legal identity/qualification.
        organizer_name = _label_value(visible[:150], ("Организатор:", "Организатор"), r"(?:АО|ПАО|ООО|ЗАО|ОАО) [^<>]{2,200}", "organizer")
        organizer_type = None
    normalized_stage = _norm(stage)
    if normalized_stage not in RECEIVING | TERMINAL:
        raise ValueError("Unknown displayed stage")
    observed_local = observed_at.astimezone(MOSCOW)
    elapsed = (datetime.fromisoformat(deadline) <= observed_at if precision == "moscow_minute" else date.fromisoformat(deadline) < observed_local.date())
    same_day = precision == "date_only" and date.fromisoformat(deadline) == observed_local.date()
    if normalized_stage in TERMINAL or elapsed:
        state = "CLOSED_AT_CAPTURE"
    elif same_day:
        state = "CUTOFF_TIME_UNKNOWN"
    elif organizer_type == "Частное лицо":
        state = "PERSONAL_ORGANIZER_REVIEW"
    else:
        state = "PUBLIC_STAGE_AT_CAPTURE_ONLY"
    return {"schema": "commercial_public_card_observation_v1", "source_platform": platform, "external_id": external_id,
            "source_url": requested_url, "observed_at": observed_at.astimezone(UTC).isoformat(),
            "html_sha256": hashlib.sha256(raw).hexdigest(), "html_bytes": len(raw), "title": title,
            "displayed_stage": stage, "displayed_deadline": deadline, "deadline_literal": deadline_literal,
            "deadline_precision": precision, "organizer_type": organizer_type, "organizer_name_literal": organizer_name,
            "observation_state": state, "full_documents_verified": False, "legal_identity_verified": False,
            "current_live_notice_status_verified": False, "qualification_verified": False,
            "external_submission_allowed": False, "human_review_required": True}
