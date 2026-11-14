"""Pure parser for the observed public SIBUR registry AJAX GET contract."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin, urlsplit

REGISTRY_URL = "https://www.sibur.ru/ru/procurement/buy/"
PAGE_SIZE = 12
MAX_RESPONSE = 4_000_000
HEADERS = (
    "Номер закупочной процедуры", "Наименование процедуры", "Предмет закупки",
    "Наименование способа закупки", "Дата публикации", "Срок подачи предложений",
    "Организатор", "Статус закупочной процедуры", "ФИО закупщика",
    "Телефон закупщика", "Email закупщика", "Номенклатурная категория", "Документация",
)
FIELDS = {
    0: "external_id", 1: "title", 2: "subject", 3: "method",
    4: "published_raw", 5: "deadline_raw", 6: "organizer",
    7: "status_raw", 11: "category", 12: "documentation_label",
}
_ID = re.compile(r"\d{7}/\d+")
_UI = {"Развернуть", "Свернуть", "Показать еще"}


def page_url(page: int) -> str:
    if type(page) is not int or not 1 <= page <= 1000:
        raise ValueError("invalid page")
    return REGISTRY_URL + "?" + urlencode({
        "PAGEN_1": page, "count": PAGE_SIZE, "catMTR": "all", "catNMK": "all",
    })


class _Table(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self.tables = 0
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.active = False
        self.document_links: list[list[str]] = []
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            if self.active:
                raise ValueError("nested procurement table")
            if "table__table" in dict(attrs).get("class", "").split():
                self.active = True
                self.tables += 1
        if not self.active:
            return
        if tag == "tr":
            if self.row is not None:
                raise ValueError("nested row")
            self.row = []
            self.links = []
        if tag == "a" and self.row is not None and len(self.row) == 12 and self.cell is not None:
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)
        if tag in {"td", "th"} and self.row is not None:
            if self.cell is not None:
                raise ValueError("nested cell")
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            value = " ".join(data.split())
            if value and value not in _UI:
                self.cell.append(value)

    def handle_endtag(self, tag):
        if not self.active:
            return
        if tag in {"td", "th"} and self.cell is not None and self.row is not None:
            self.row.append(" ".join(self.cell))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.cell is not None:
                raise ValueError("unterminated cell")
            self.rows.append(self.row)
            self.document_links.append(self.links)
            self.row = None
        elif tag == "table":
            if self.row is not None:
                raise ValueError("unterminated row")
            self.active = False


class _Pagination(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.pages: list[int] = []
        self.current: list[int] = []
        self.item = None
        self.text: list[str] = []

    def handle_starttag(self, tag, attrs):
        classes = dict(attrs).get("class", "").split()
        if tag == "a" and "pagination__items-item" in classes:
            self.item = "_current" in classes
            self.text = []

    def handle_data(self, data):
        if self.item is not None:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.item is not None:
            text = "".join(self.text).strip()
            if text.isdecimal():
                page = int(text)
                self.pages.append(page)
                if self.item:
                    self.current.append(page)
            self.item = None


@dataclass(frozen=True)
class RegistryPage:
    page: int
    last_page: int
    sha256: str
    records: tuple[dict[str, str | list[str] | int], ...]


def parse_page(raw: bytes, expected_page: int) -> RegistryPage:
    """Reject unexpected shape/page, keep original IDs and raw date/status text."""
    url = page_url(expected_page)
    if len(raw) > MAX_RESPONSE:
        raise ValueError("oversize response")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not all(
        isinstance(payload.get(k), str) for k in ("content", "pagination")
    ):
        raise ValueError("unexpected registry response")
    table, pagination = _Table(), _Pagination()
    table.feed(payload["content"])
    table.close()
    pagination.feed(payload["pagination"])
    pagination.close()
    if table.tables != 1 or table.active or not table.rows or tuple(table.rows[0]) != HEADERS:
        raise ValueError("unexpected procurement table")
    if pagination.current != [expected_page] or not pagination.pages:
        raise ValueError("unexpected pagination")
    last_page = max(pagination.pages)
    if not expected_page <= last_page <= 1000:
        raise ValueError("invalid page range")
    digest = hashlib.sha256(raw).hexdigest()
    records = []
    for ordinal, row in enumerate(table.rows[1:], 1):
        if len(row) != len(HEADERS) or not _ID.fullmatch(row[0]) or not row[1]:
            raise ValueError("invalid procurement row")
        record: dict[str, str | list[str] | int] = {field: row[index] for index, field in FIELDS.items()}
        links = table.document_links[ordinal]
        accepted = []
        rejected = 0
        for href in links:
            try:
                target = urlsplit(urljoin(REGISTRY_URL, href))
                safe = (
                    target.scheme == "https" and target.netloc == "www.sibur.ru"
                    and target.path.startswith("/upload/tmp/example/")
                    and not target.query and not target.fragment
                    and "%" not in target.path and ".." not in target.path.split("/")
                )
            except ValueError:
                safe = False
            if safe:
                accepted.append(target.geturl())
            else:
                rejected += 1
        record.update(source="sibur_public", source_url=url, source_sha256=digest,
                      verification="PUBLIC_SNAPSHOT_ONLY", source_row=str(ordinal))
        record["documentation_urls"] = list(dict.fromkeys(accepted))
        record["unverified_document_links"] = rejected
        records.append(record)
    if not records or len(records) > PAGE_SIZE:
        raise ValueError("unexpected page size")
    return RegistryPage(expected_page, last_page, digest, tuple(records))
