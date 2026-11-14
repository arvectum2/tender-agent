"""First-party GPB SSR list discovery, not a verified full tender record."""
from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

ORIGIN = "https://etpgpb.ru"
CARD = re.compile(r'<article\b[^>]*data-testid="procedure-card"[^>]*>.*?</article>', re.DOTALL)
NATIVE = re.compile(r"/procedures/([a-z_]+)/([0-9]+)-[^/]+/?$")
GOS = re.compile(r"/front/procedure/view/([0-9a-f-]{36})/?$")
LABELS = {
    "Секция": "section_raw", "Регионы": "regions_raw", "Заказчики": "customers_raw",
    "Организатор": "organizer_raw", "Начальная цена": "price_raw",
    "Подача заявок до": "deadline_raw", "Дата публикации": "published_raw",
}


class Card(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tokens = []
        self.links = []
        self.anchor = None

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "a" and d.get("href"):
            self.anchor = (d["href"], [])

    def handle_endtag(self, tag):
        if tag == "a" and self.anchor is not None:
            href, parts = self.anchor
            self.links.append((href, " ".join(parts)))
            self.anchor = None

    def handle_data(self, data):
        value = " ".join(data.split())
        if value:
            self.tokens.append(value)
            if self.anchor is not None:
                self.anchor[1].append(value)


def parse_list(raw: bytes, source_url: str):
    u = urlsplit(source_url)
    if u.scheme != "https" or u.netloc != "etpgpb.ru" or u.path != "/procedures/":
        raise ValueError("unsupported source")
    if len(raw) > 4_000_000:
        raise ValueError("oversize source")
    digest = hashlib.sha256(raw).hexdigest()
    rows = []
    for ordinal, html in enumerate(CARD.findall(raw.decode("utf-8")), 1):
        p = Card()
        p.feed(html)
        p.close()
        valid = []
        for href, label in p.links:
            target = urlsplit(urljoin(ORIGIN, href))
            match = NATIVE.fullmatch(target.path)
            if target.scheme == "https" and target.netloc == "etpgpb.ru" and match:
                valid.append((target.geturl(), match.groups(), label))
            elif target.scheme == "https" and target.netloc == "gos.etpgpb.ru":
                gos = GOS.fullmatch(target.path)
                if gos:
                    valid.append((target.geturl(), ("gos", gos.group(1)), label))
        if len(valid) < 2 or len({x[1] for x in valid}) != 1:
            raise ValueError("ambiguous card identity")
        link, (section, native_id), number = valid[0]
        title = valid[1][2]
        if not number.startswith("№") or not title:
            raise ValueError("missing source identity or title")
        row = {"source": "etp_gpb", "external_id": section + ":" + native_id,
               "number_raw": number, "title": title, "detail_url": link,
               "source_url": source_url, "source_sha256": digest, "source_row": ordinal,
               "verification": "PUBLIC_LIST_OBSERVATION_ONLY"}
        positions = [(i, LABELS[t]) for i, t in enumerate(p.tokens) if t in LABELS]
        for index, (start, key) in enumerate(positions):
            stop = positions[index+1][0] if index+1 < len(positions) else len(p.tokens)
            row[key] = " ".join(p.tokens[start+1:stop])
        rows.append(row)
    if not rows or len({r["external_id"] for r in rows}) != len(rows):
        raise ValueError("empty or duplicate source page")
    return rows
