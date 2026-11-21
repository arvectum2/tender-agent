"""Source-specific archive contract, sharing the verified SIBUR HTML table primitives."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from urllib.parse import urlencode, urljoin, urlsplit

from src.modules.tender_connectors.sibur.parser import (
    _ID,
    FIELDS,
    HEADERS,
    MAX_RESPONSE,
    PAGE_SIZE,
    RegistryPage,
    _Pagination,
    _Table,
)

ARCHIVE = "https://www.sibur.ru/ru/procurement/buy/archive/"
CATEGORIES = {
    "107": ("1", "Электрооборудование"),
    "108": ("1", "Системы и средства автоматизации, метрологии и КИП"),
    "999_08": ("5", "Проектные и изыскательские работы"),
    "999_10": ("5", "Строительные работы"),
    "109": ("1", "Технологическое оборудование"),
    "112": ("1", "Общезаводское оборудование"),
    "132": ("1", "ЗИП к динамическому оборудованию"),
    "999_11": ("5", "Техническое обслуживание и ремонт"),
    "999_19": ("5", "Сопроводительные услуги при поставке оборудования"),
}
MAX_PAGES = 10000


def _unique_json_members(pairs):
    value = {}
    for key, member in pairs:
        if key in value:
            raise ValueError("duplicate SIBUR source JSON member")
        value[key] = member
    return value


def archive_url(category, page):
    if category not in CATEGORIES or type(page) is not int or not 1 <= page <= MAX_PAGES:
        raise ValueError("unsupported archive category/page")
    return ARCHIVE + "?" + urlencode({"PAGEN_1": page, "count": PAGE_SIZE,
                                      "catMTR": CATEGORIES[category][0], "catNMK": category})


def archive_page(raw, category, page):
    url = archive_url(category, page)
    if len(raw) > MAX_RESPONSE:
        raise ValueError("oversize archive response")
    payload = json.loads(raw, object_pairs_hook=_unique_json_members)
    if not isinstance(payload, dict) or not all(isinstance(payload.get(k), str) for k in ("content", "pagination")):
        raise ValueError("unexpected archive response")
    table, pagination = _Table(), _Pagination()
    table.feed(payload["content"])
    table.close()
    pagination.feed(payload["pagination"])
    pagination.close()
    if table.tables != 1 or table.active or not table.rows or tuple(table.rows[0]) != HEADERS:
        raise ValueError("unexpected archive table")
    if pagination.current != [page] or not pagination.pages:
        raise ValueError("archive pagination mismatch")
    last = max(pagination.pages)
    if not page <= last <= MAX_PAGES:
        raise ValueError("invalid archive page range")
    digest = hashlib.sha256(raw).hexdigest()
    rows = []
    for ordinal, cells in enumerate(table.rows[1:], 1):
        if len(cells) != len(HEADERS) or not _ID.fullmatch(cells[0]) or not cells[1]:
            raise ValueError("invalid archive identity")
        if cells[11] != CATEGORIES[category][1]:
            raise ValueError("archive category filter mismatch")
        datetime.strptime(cells[4], "%d.%m.%Y")
        row = {field: cells[index] for index, field in FIELDS.items()}
        links, rejected = [], 0
        for href in table.document_links[ordinal]:
            target = urlsplit(urljoin(ARCHIVE, href))
            if (target.scheme == "https" and target.netloc == "www.sibur.ru"
                    and target.path.startswith("/upload/tmp/example/") and not target.query
                    and not target.fragment and "%" not in target.path and ".." not in target.path.split("/")):
                links.append(target.geturl())
            else:
                rejected += 1
        row.update(source="sibur_public", source_url=url, source_sha256=digest,
                   verification="PUBLIC_SNAPSHOT_ONLY", source_row=str(ordinal),
                   documentation_urls=list(dict.fromkeys(links)), unverified_document_links=rejected)
        rows.append(row)
    if not 1 <= len(rows) <= PAGE_SIZE:
        raise ValueError("unexpected archive page size")
    return RegistryPage(page, last, digest, tuple(rows))
