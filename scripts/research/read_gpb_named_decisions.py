"""Extract older explicitly named best-bid clauses, without inferring INN or contract."""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from decimal import Decimal

from scripts.research.read_gpb_protocol_decisions import (
    BID_PRICE,
    INITIAL,
    read_docx_member,
)

HEADER = re.compile(r"в части подведения итогов.{1,280}?в электронной форме\s+№\s*(\d+(?:/[А-ЯЁA-Z0-9.-]+)*)\s*\)", re.IGNORECASE)
CLAUSE = re.compile(
    r"(?:определить лучшей заявку|выбрать наиболее выгодные условия (?:выполнения работ|оказания услуг|поставки товара) в заявке)"
    r"\s+(?P<name>(?:ООО|АО|ПАО|ФБУ|ФГУП|ФГБУ|ЗАО|ОАО)\s+«[^()\r\n]{1,180}?»)"
    r"\s*\((?P<address>\d{6},[^()\r\n]{3,350})\)", re.IGNORECASE)
SCHEMA = "gpb_named_outcome_v4"


def monetary(value):
    return str(Decimal(value.replace(" ","").replace("\u00a0","").replace(",",".")))


def tax_tail(text):
    match=re.match(r"\s*[,;]?\s*\(?\s*(без учета НДС|с учетом НДС|включая все налоги и платежи)",text,re.IGNORECASE)
    if not match:
        return None
    return {"без учета ндс":"excludes_vat","с учетом ндс":"includes_vat",
            "включая все налоги и платежи":"includes_all_taxes_and_payments"}[match[1].lower()]


def named_lines(lines,member,member_sha256,detail_title):
    headers=[(i,m[1]) for i,line in enumerate(lines[:25]) for m in HEADER.finditer(line)]
    if len(headers)!=1:
        raise ValueError("expected one older protocol procedure reference")
    h,ref=headers[0]
    if not re.search(r"(?:№\s*|Тендер на закупку\s+(?:(?:КО|МИ)\s+)?)"+re.escape(ref)+r"(?![\w/-]|\.[\w])",detail_title,re.IGNORECASE):
        raise ValueError("protocol number not bound to detail title")
    candidates=[(i,m) for i,line in enumerate(lines) for m in CLAUSE.finditer(line)]
    initial=[(i,m) for i,line in enumerate(lines) for m in INITIAL.finditer(line)]
    if len(candidates)!=1 or len(initial)!=1:
        raise ValueError("named decision or initial price ambiguous")
    i,m=candidates[0];j,n=initial[0]
    if i<=j or not re.search(r"№\s*"+re.escape(ref)+r"(?![\w/-]|\.[\w])",lines[i],re.IGNORECASE):
        raise ValueError("named decision not explicitly tied to procedure")
    prices=list(BID_PRICE.finditer(lines[i],m.end()))
    if len(prices)!=1:
        raise ValueError("named bid price absent or ambiguous")
    bid=prices[0]
    return {"member":member,"member_sha256":member_sha256,"parser_schema":SCHEMA,
            "decision":"BEST_BID_SELECTED_NOT_SIGNED_CONTRACT","participant_platform_id":None,
            "participant_role":"participant_named_in_protocol","participant_legal_identity":None,
            "participant_name_as_published":m["name"],"participant_address_as_published":m["address"],
            "participant_identity_verification":"PUBLISHED_NAME_AND_ADDRESS_IN_EXPLICIT_DECISION_NOT_INN_VERIFIED",
            "protocol_procedure_reference":ref,"protocol_reference_paragraph":h,
            "protocol_reference_evidence":lines[h],"detail_title_evidence":detail_title,
            "initial_price_rub":monetary(n[1]),"best_bid_rub":monetary(bid[1]),
            "initial_price_tax_basis":tax_tail(lines[j][n.end():]),"best_bid_tax_basis":tax_tail(lines[i][bid.end():]),
            "contract_amount":None,"best_bid_paragraph":i,"best_bid_evidence":lines[i],
            "initial_price_paragraph":j,"initial_price_evidence":lines[j]}


def parse_named_protocol(raw,detail_title):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist()
        if "word/document.xml" in z.namelist():
            content,member=raw,None
        else:
            if len(infos)>20 or sum(i.file_size for i in infos)>20_000_000:
                raise ValueError("archive bounds")
            ms=[i for i in infos if i.filename.lower().endswith(".docx")]
            if len(ms)!=1 or ms[0].file_size>1_000_000 or ms[0].flag_bits&1:
                raise ValueError("expected one bounded DOCX protocol")
            content,member=z.read(ms[0]),ms[0].filename
    return named_lines(read_docx_member(content),member,hashlib.sha256(content).hexdigest(),detail_title)
