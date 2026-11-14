"""SHA-bound ranked commission offers for Slavyanskaya STK design, not hardware sales."""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

from scripts.market_intelligence.append_pq_delta_20261029 import (
    COL,
    ROOT,
    js,
    psql,
    snapshot,
    verified_backup,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest, get_row

CID = "223fz:32515225588:lot1"
KEY = "slavyanskaya_stk_final_protocol_20261102"
REL = ("captures/223fz_32515225588_lot1/"
       "20261102T173623038827Z-6fb68d41-50e50e068e2d5626.bin")
SHA = "50e50e068e2d5626d04d32baad3fdb6847f7bcd4793814ed17daa9a7ad057671"
URL = ("https://zakupki.gov.ru/epz/order/notice/protocol223/printForm/view.html"
       "?protocolGuid=b9d8cf86-89d4-4933-beae-4e064086c890"
       "&purchaseNoticeNumber=32515225588")
FIELDS = {
    "bid": "20107269.94",
    "protocol_signed_date": "2025-10-30",
    "protocol_participant_count": 4,
    "commission_first_place_application": "Заявка №3 (анонимная)",
    "protocol_status_note": (
        "Итоговый протокол ЕИС №32515225588-03: четыре допущенные заявки; "
        "заявка №3 — первое место и предложение 20 107 269,94 руб.; "
        "заявка №2 — второе место при меньшем предложении 17 793 360,90 руб. "
        "Первое место определено оценкой, а не минимальной ценой. "
        "Отдельно зарегистрирован договор на 20 442 391,10 руб. от 19.11.2025; "
        "имя участника №3 и подписавшего поставщика не подтверждено. "
        "Предмет — проектирование замены трёх СТК на ПС 220 кВ, "
        "не продажа оборудования PQ 6–35 кВ."
    ),
}
QUOTES = ("Протокол заседания комиссии по подведению итогов от 31.10.2025 № 32515225588-03",
          "Дата подписания протокола: 30.10.2025",
          "Цена поставщика: 20 107 269.94",
          "Цена поставщика: 17 793 360.90",
          "3 06.10.2025 11:06 19.11 1 место Да")


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def proof():
    root = ROOT.resolve(strict=True)
    if root != Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live"):
        raise ValueError("Internal APFS required")
    p = (root / REL).resolve(strict=True)
    if root not in p.parents or p.is_symlink() or not 1000 < p.stat().st_size < 500000:
        raise ValueError("Unsafe original")
    raw = p.read_bytes()
    receipt = json.loads(Path(str(p) + ".json").read_text())
    if (hashlib.sha256(raw).hexdigest() != SHA or receipt.get("sha256") != SHA
            or receipt.get("relative_file") != REL or receipt.get("case_id") != CID
            or receipt.get("source_url") != URL or receipt.get("http_status") != 200):
        raise ValueError("SHA/receipt mismatch")
    parser = Text()
    parser.feed(raw.decode("utf-8", "replace"))
    text = " ".join(unescape(" ".join(parser.parts)).split())
    if not all(q in text for q in QUOTES):
        raise ValueError("Exact source quotes not found")
    return {"url": URL, "sha256": SHA, "relative_file": REL, "quotes": QUOTES}


def prepare(row, source):
    d = row["data"]
    if (row["id"] != CID or row["owner"] != "tender-agent"
            or d.get("canonical_id") != CID or d.get("procedure_id") != "32515225588"
            or d.get("scope") != "design"
            or d.get("customer", {}).get("inn") != "4716016979"
            or d.get("nmck_rub") != "27175270"
            or d.get("contract_registered_price_rub") != "20442391.10"
            or d.get("contract_signed_date") != "2025-11-19"
            or d.get("registered_signed_contract_verified") is not True
            or d.get("winner") is not None or d.get("contract_signatory") is not None
            or digest(d) != row["hash"] or KEY in row["meta"]
            or any(d.get(k) is not None for k in FIELDS)):
        raise RuntimeError("Owner/identity/scope/old-null guard failed")
    new = {**d, **FIELDS, "evidence": [*d.get("evidence", []), {
        "url": URL, "sha256": SHA, "source_tier": "first_party_eis_final_commission",
        "excerpt": "; ".join(QUOTES)}]}
    h = digest(new)
    meta = {**row["meta"], "source_content_hash": h, KEY: {
        "fields": FIELDS, "proof": source, "previous_hash": row["hash"],
        "previous_revision": row["rev"], "signed_supplier_verified": False,
        "paid_equipment_sale_verified": False}}
    return new, meta, h


def apply(row, source, before):
    data, meta, new_hash = prepare(row, source)
    old = row["hash"]
    rev = row["rev"]
    nulls = " AND ".join(
        f"((d.data->'{k}') IS NULL OR (d.data->'{k}')='null'::jsonb)"
        for k in FIELDS
    )
    sql = f"""BEGIN ISOLATION LEVEL SERIALIZABLE;
SET LOCAL statement_timeout='55s'; SET LOCAL lock_timeout='9s';
SELECT pg_advisory_xact_lock(hashtext('{COL}-delta'));
LOCK TABLE dp_resources,dp_records IN SHARE ROW EXCLUSIVE MODE;
DO $g$ BEGIN IF current_database()<>'arvectum_data'
OR (SELECT owner FROM dp_collections WHERE collection_id='{COL}')<>'tender-agent'
OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{old}'
AND d.revision={rev} AND {nulls})<>1
THEN RAISE EXCEPTION 'PQ CAS/owner/count conflict'; END IF; END $g$;
UPDATE dp_records d SET data={js(data)},metadata={js(meta)},
revision=revision+1,updated_at=now()
FROM dp_resources r WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{CID}' AND r.content_hash='{old}' AND d.revision={rev}
AND {nulls};
UPDATE dp_resources SET content_hash='{new_hash}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{old}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{new_hash}'
AND d.revision={rev+1} AND d.data->>'bid'='20107269.94'
AND d.metadata->'{KEY}'->'proof'->>'sha256'='{SHA}')<>1
THEN RAISE EXCEPTION 'PQ postwrite mismatch'; END IF; END $g$;
COMMIT;"""
    psql(sql)
    after = snapshot()
    actual = get_row(CID)
    if (before != after or actual["hash"] != new_hash or actual["rev"] != rev + 1
            or any(actual["data"].get(k) != v for k, v in FIELDS.items())):
        raise RuntimeError("Postcommit readback mismatch")
    return {"id": CID, "before": before, "after": after,
            "new_verified_fields": len(FIELDS), "new_unique_lots": 0,
            "source_sha256": SHA, "old_hash": old, "new_hash": new_hash,
            "fields": FIELDS, "new_signed_suppliers": 0, "new_paid_sales": 0}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-manifest", type=Path)
    p.add_argument("--receipt", type=Path)
    a = p.parse_args()
    source = proof()
    before = snapshot()
    row = get_row(CID)
    prepare(row, source)
    if not a.apply:
        print(json.dumps({"mode": "dry_run", "id": CID, "before": before,
                          "fields": FIELDS, "source_sha256": SHA}, ensure_ascii=False))
        return
    if not a.backup_manifest or not a.receipt:
        raise RuntimeError("Fresh backup and receipt mandatory")
    gate = subprocess.run([sys.executable, "-m",
                           "scripts.market_intelligence.verify_internal_runtime"],
                          capture_output=True, text=True, check=True, timeout=60)
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("Acceptance blocked")
    backup = verified_backup(a.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("Fresh SHA+pg_restore full backup mandatory")
    result = apply(row, source, before)
    result["backup_sha256"] = backup["sha256"]
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    with a.receipt.open("x", encoding="utf8") as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
