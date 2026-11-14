"""Read explicit best-bid decisions from bounded ZIP/DOCX source protocols."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import zipfile
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
MONEY = r"([0-9][0-9 \u00a0]*,[0-9]{2})"
BEST = re.compile(r"Определить лучшей заявку участника с идентификационным номером\s+(\d+),\s+на (?:общую )?сумму\s+" + MONEY + r"\s*руб\.", re.IGNORECASE)
INITIAL = re.compile(r"Начальная \(максимальная\) цена договора:\s*" + MONEY + r"\s*руб\.", re.IGNORECASE)


def read_docx_member(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos = z.infolist()
        if len(infos) > 2000 or sum(i.file_size for i in infos) > 10_000_000:
            raise ValueError("OOXML bounds")
        if any(i.flag_bits & 1 for i in infos):
            raise ValueError("encrypted member")
        xml = z.read("word/document.xml")
    if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
        raise ValueError("unsupported XML declaration")
    root = ElementTree.fromstring(xml)
    return ["".join(t.text or "" for t in p.findall(".//w:t", NS))
            for p in root.findall(".//w:p", NS)]


def parse_protocol(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos = z.infolist()
        if len(infos) > 20 or sum(i.file_size for i in infos) > 20_000_000:
            raise ValueError("archive bounds")
        members = [i for i in infos if i.filename.lower().endswith(".docx")]
        if len(members) != 1 or members[0].file_size > 1_000_000 or members[0].flag_bits & 1:
            raise ValueError("expected one bounded DOCX protocol")
        member = members[0]
        content = z.read(member)
    lines = read_docx_member(content)
    best = [(i, BEST.search(line)) for i, line in enumerate(lines) if BEST.search(line)]
    initial = [(i, INITIAL.search(line)) for i, line in enumerate(lines) if INITIAL.search(line)]
    if len(best) != 1 or len(initial) != 1:
        raise ValueError("ambiguous or absent explicit decision")
    i, m = best[0]
    j, n = initial[0]

    def price(s):
        return str(Decimal(s.replace(" ", "").replace("\u00a0", "").replace(",", ".")))

    return {"member": member.filename, "member_sha256": hashlib.sha256(content).hexdigest(),
            "decision": "BEST_BID_SELECTED_NOT_SIGNED_CONTRACT",
            "participant_platform_id": m[1], "participant_legal_identity": None,
            "initial_price_rub": price(n[1]), "best_bid_rub": price(m[2]),
            "contract_amount": None, "best_bid_paragraph": i, "best_bid_evidence": lines[i],
            "initial_price_paragraph": j, "initial_price_evidence": lines[j]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    os.umask(0o077)
    rows = []
    for r in json.loads((a.root / "document-pilot-receipts.json").read_text()):
        if r.get("document_role") != "published_protocol" or r["capture_status"] != "captured":
            continue
        f = a.root / "originals" / r["file"]
        raw = f.read_bytes()
        if hashlib.sha256(raw).hexdigest() != r["sha256"]:
            raise ValueError("protocol source hash mismatch")
        try:
            result = parse_protocol(raw)
        except (ValueError, zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
            result = {"decision": "REVIEW_REQUIRED", "error": str(exc)}
        rows.append({"external_id": r["external_id"], "protocol_sha256": r["sha256"],
                     "document_url": r["document_url"], **result})
    with a.output.open("x") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print("protocols", len(rows), "explicit decisions", sum(r["decision"] == "BEST_BID_SELECTED_NOT_SIGNED_CONTRACT" for r in rows))


if __name__ == "__main__":
    main()
