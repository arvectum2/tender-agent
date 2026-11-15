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
DECISION = re.compile(
    r"(?:определить лучшей заявку|выбрать наиболее выгодные условия (?:выполнения работ|оказания услуг|поставки товара) в заявке)"
    r"\s+(?:участника с идентификационным номером\s+(?P<participant>\d+)|"
    r"Группы лиц\s*\(ID\s+Лидера\s*[-–]\s*(?P<leader>\d+)(?:\)|(?=, которой присвоен первый порядковый номер)))",
    re.IGNORECASE,
)
BID_PRICE = re.compile(r"на (?:общую )?сумму\s+" + MONEY + r"\s*руб\.", re.IGNORECASE)
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
    if raw.startswith(b"%PDF-"):
        raise ValueError("PDF protocol requires separate text-layer or OCR review")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos = z.infolist()
        if "word/document.xml" in z.namelist():
            return parse_decision_lines(read_docx_member(raw), None, hashlib.sha256(raw).hexdigest())
        if len(infos) > 20 or sum(i.file_size for i in infos) > 20_000_000:
            raise ValueError("archive bounds")
        members = [i for i in infos if i.filename.lower().endswith(".docx")]
        if len(members) != 1 or members[0].file_size > 1_000_000 or members[0].flag_bits & 1:
            raise ValueError("expected one bounded DOCX protocol")
        member = members[0]
        content = z.read(member)
    return parse_decision_lines(read_docx_member(content), member.filename, hashlib.sha256(content).hexdigest())


def parse_decision_lines(lines, member, member_sha256):
    best = [(i, DECISION.search(line)) for i, line in enumerate(lines) if DECISION.search(line)]
    initial = [(i, INITIAL.search(line)) for i, line in enumerate(lines) if INITIAL.search(line)]
    if len(best) != 1 or len(initial) != 1:
        return alternate_decision(lines, member, member_sha256)
    i, m = best[0]
    j, n = initial[0]
    prices = list(BID_PRICE.finditer(lines[i], m.end()))
    if len(prices) == 1:
        bid = prices[0]
        tax_tail = lines[i][bid.end():]
    elif len(prices) == 2 and prices[0].group().lower().startswith("на общую сумму") and re.search(
        r"с учетом единичных расценок\s*$", lines[i][prices[0].end():prices[1].start()], re.IGNORECASE
    ):
        bid = prices[0]
        tax_tail = lines[i][bid.end():prices[1].start()]
    else:
        raise ValueError("ambiguous or absent explicit bid price")
    def tax_basis(line):
        if re.search(r"без учета НДС", line, re.IGNORECASE):
            return "excludes_vat"
        if re.search(r"с учетом НДС", line, re.IGNORECASE):
            return "includes_vat"
        if re.search(r"включая все налоги и платежи", line, re.IGNORECASE):
            return "includes_all_taxes_and_payments"
        return None

    def price(s):
        return str(Decimal(s.replace(" ", "").replace("\u00a0", "").replace(",", ".")))

    return {"member": member, "member_sha256": member_sha256,
            "decision": "BEST_BID_SELECTED_NOT_SIGNED_CONTRACT",
            "participant_platform_id": m["participant"] or m["leader"],
            "participant_role": "group_leader" if m["leader"] else "participant",
            "participant_legal_identity": None,
            "initial_price_rub": price(n[1]), "best_bid_rub": price(bid[1]),
            "initial_price_tax_basis": tax_basis(lines[j]),
            "best_bid_tax_basis": tax_basis(tax_tail),
            "contract_amount": None, "best_bid_paragraph": i, "best_bid_evidence": lines[i],
            "initial_price_paragraph": j, "initial_price_evidence": lines[j]}


def alternate_decision(lines, member, member_sha256):
    base = {"member": member, "member_sha256": member_sha256,
            "participant_platform_id": None, "participant_legal_identity": None,
            "contract_amount": None, "parser_schema": "gpb_outcome_v3"}
    failed = [(i, line) for i, line in enumerate(lines) if re.search(
        r"признать.{0,180}несостоявш(?:имся|имися)", line, re.IGNORECASE)]
    if len(failed) == 1:
        i, evidence = failed[0]
        return {**base, "decision": "PROCEDURE_DECLARED_UNSUCCESSFUL",
                "decision_paragraph": i, "decision_evidence": evidence}
    winner = [(i, re.search(r"Комиссия приняла решение (?:о выборе наиболее выгодных условий.{0,220}в заявке|определить лучшей заявкой по Конкурентному отбору заявку) Участника №\s*(\d+)(?: \(далее [–-] Победитель\))? с ценовым предложением", line, re.IGNORECASE))
              for i, line in enumerate(lines)]
    winner = [(i, m) for i, m in winner if m]
    headers = [i for i, line in enumerate(lines) if re.search(
        r"Начальная \(максимальная\) цена договора:\s*$", line, re.IGNORECASE)]
    if len(winner) != 1 or len(headers) != 1:
        raise ValueError("ambiguous or absent explicit decision")
    i, m = winner[0]
    j = headers[0]
    gross = re.compile(r"^\s*-?\s*" + MONEY + r"\s*(?:руб\.\s*)?с НДС(?:[.;\s]|$)", re.IGNORECASE)
    def unique_amount(start):
        matches = [(k, gross.search(lines[k])) for k in range(start+1, min(start+5,len(lines)))]
        matches = [(k, v) for k, v in matches if v]
        if len(matches) != 1:
            raise ValueError("ambiguous gross price")
        k, v = matches[0]
        return k, str(Decimal(v[1].replace(" ", "").replace("\u00a0", "").replace(",", ".")))
    a, initial = unique_amount(j)
    b, bid = unique_amount(i)
    return {**base, "decision": "BEST_BID_SELECTED_NOT_SIGNED_CONTRACT",
            "participant_role": "procedure_local_ordinal", "participant_local_ordinal": m[1],
            "initial_price_rub": initial, "best_bid_rub": bid,
            "initial_price_tax_basis": "includes_vat", "best_bid_tax_basis": "includes_vat",
            "initial_price_paragraph": a, "initial_price_evidence": lines[a],
            "best_bid_paragraph": i, "best_bid_evidence": lines[i],
            "best_bid_price_paragraph": b, "best_bid_price_evidence": lines[b]}


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
