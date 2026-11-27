"""EIS 223-FZ: 12 filter capacitors, signed registry, null-only SHA CAS."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
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

CID = "223fz:32515029641:lot1"
NUM = "54716016979250033980000"
PREFIX = "captures/223fz_32515029641_lot1/"
SOURCES = (
    ("20261031T223542804901Z-ad1f118b-b3571212f38a646f.bin",
     "b3571212f38a646f3686d30974ce3a4fd6df904e2a5b22a1cd51c3b9363ed0c6",
     "https://zakupki.gov.ru/223/purchase/public/download/download.html?id=104750729", "docx"),
    ("20261031T223556355520Z-afb70492-72a8d234dbaab2a7.bin",
     "72a8d234dbaab2a78f64297643a986d5a76dfd6882a7799dd7aa9805a4c414c6",
     f"https://zakupki.gov.ru/epz/contractfz223/card/contract-info.html?reestrNumber={NUM}", "html"),
    ("20261031T223556731881Z-ab76eee7-ecda30473b4c6fef.bin",
     "ecda30473b4c6fef92b459ea4b41e12af3f2ac34d997bef118ddc35525408463",
     f"https://zakupki.gov.ru/epz/contractfz223/printForm/view.html?reestrNumber={NUM}", "html"),
    ("20261031T223557088820Z-7da97266-9f2fcb5412e2b45f.bin",
     "9f2fcb5412e2b45f5647082fa227fe50703b171d0a40af7047a635805028c0c1",
     f"https://zakupki.gov.ru/epz/contractfz223/card/contract-subject.html?reestrNumber={NUM}", "html"),
    ("20261031T223557414971Z-7c902d57-e52ec01d1e69ac64.bin",
     "e52ec01d1e69ac64b4b1e04cd36a8f3b7502d5788a57c61fce27c8f1f2c06506",
     f"https://zakupki.gov.ru/epz/contractfz223/card/event-log.html?reestrNumber={NUM}", "html"),
)
FIELDS = {
    "commission_bid_rub": "3490560.00",
    "contract_registered_price_rub": "3490560.00",
    "reported_contract_total_rub": "3490560.00",
    "pq_equipment_only_contract_rub": "3490560.00",
    "linked_contract_registry_number": NUM,
    "contract_number": "123",
    "contract_signed_date": "2025-09-01",
    "contract_registry_number": NUM,
    "contract_register_date": "2025-09-02",
    "registered_signed_contract_verified": True,
    "quantity": 12,
    "equipment_model": "КЭПФ-12-450-2 УХЛ1",
    "unit_price_rub": "290880.00",
    "commission_recommended_counterparty": 'ООО "ЭСК ЮГ"',
    "contract_execution_status_verified": "Исполнение",
}


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())


def evidence():
    root = ROOT.resolve(strict=True)
    if root != Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live"):
        raise RuntimeError("internal APFS required")
    sources, texts = [], []
    for name, sha, url, kind in SOURCES:
        p = (root / PREFIX / name).resolve(strict=True)
        if root not in p.parents or p.is_symlink() or p.stat().st_size > 2000000:
            raise RuntimeError("unsafe original")
        raw = p.read_bytes()
        receipt = json.loads(Path(str(p) + ".json").read_text())
        if (
            hashlib.sha256(raw).hexdigest() != sha
            or receipt.get("sha256") != sha
            or receipt.get("http_status") != 200
            or receipt.get("case_id") != CID
            or receipt.get("source_url") != url
            or receipt.get("relative_file") != PREFIX + name
        ):
            raise RuntimeError("original SHA/receipt mismatch")
        if kind == "docx":
            with zipfile.ZipFile(p) as z:
                xml = " ".join(
                    z.read(n).decode("utf-8", "replace")
                    for n in z.namelist()
                    if n.startswith("word/") and n.endswith(".xml")
                )
            visible = unescape(re.sub(r"<[^>]*>", " ", xml))
            visible = " ".join(visible.split())
        else:
            parser = VisibleText()
            parser.feed(raw.decode("utf-8", "replace"))
            visible = " ".join(" ".join(parser.parts).split()).replace("\xa0", " ")
        texts.append(visible)
        sources.append({"url": url, "sha256": sha})
    protocol, card, printform, subject, events = texts
    if not all(x in protocol for x in (
        "32515029641", 'ООО "ЭСК ЮГ"', "3 490 560,00", "заключить",
        "19 . 0 8 .202 5",
    )):
        raise RuntimeError("final protocol mismatch")
    if not all(x in card for x in (
        NUM, "Номер договора 123", "Дата заключения договора 01.09.2025",
        "Извещение о закупке № 32515029641", "3 490 560,00",
    )):
        raise RuntimeError("contract card mismatch")
    if not all(x in printform for x in (
        NUM, "Номер договора: 123", "3 490 560.00",
        "Дата заключения договора: 01.09.2025",
    )):
        raise RuntimeError("contract printform mismatch")
    if not all(x in subject for x in (
        NUM, "Конденсатор КЭПФ-12-450-2 УХЛ1", "12 Штука 290 880,00",
    )):
        raise RuntimeError("equipment/unit price mismatch")
    if not all(x in events for x in (
        NUM, "переведен в статус «Исполнение»", "02.09.2025",
    )):
        raise RuntimeError("status mismatch")
    if 12 * 290880 != 3490560:
        raise RuntimeError("component price allocation mismatch")
    return {
        "sources": sources,
        "role": "12 capacitor components, not full 6-35kV PQ system",
        "named_bidder_only": 'ООО "ЭСК ЮГ"',
        "signed_supplier_identity": "unverified",
        "paid_amount": "unverified",
    }


def validate(row):
    data = row["data"]
    if (
        row["id"] != CID
        or row["owner"] != "tender-agent"
        or data.get("canonical_id") != CID
        or data.get("procedure_id") != "32515029641"
        or data.get("scope") != "supply_components"
        or data.get("nmck_rub") != "3621456"
        or digest(data) != row["hash"]
        or any(data.get(k) is not None for k in FIELDS)
        or row["meta"].get("eis_filter_32515029641_enrichment")
    ):
        raise RuntimeError("identity/owner/hash/old-null guard failed")


def apply(row, before, proof):
    validate(row)
    data = {
        **row["data"],
        **FIELDS,
        "evidence": [
            *row["data"].get("evidence", []),
            *(
                {
                    "url": e["url"],
                    "sha256": e["sha256"],
                    "source_tier": "first_party_eis_223_original",
                    "excerpt": "32515029641 / contract 54716016979250033980000",
                }
                for e in proof["sources"]
            ),
        ],
    }
    h = digest(data)
    meta = {
        **row["meta"],
        "source_content_hash": h,
        "eis_filter_32515029641_enrichment": {
            **proof,
            "fields": FIELDS,
            "previous_content_hash": row["hash"],
            "previous_revision": row["rev"],
        },
    }
    nulls = " AND ".join(f"(d.data->>'{k}') IS NULL" for k in FIELDS)
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
 WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{row['hash']}'
 AND d.revision={row['rev']} AND {nulls})<>1
THEN RAISE EXCEPTION 'PQ CAS/owner/count mismatch'; END IF; END $g$;
UPDATE dp_records d SET data={js(data)},metadata={js(meta)},revision=revision+1,updated_at=now()
FROM dp_resources r WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{CID}' AND r.content_hash='{row['hash']}' AND d.revision={row['rev']}
AND {nulls};
UPDATE dp_resources SET content_hash='{h}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{row['hash']}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{h}'
AND d.revision={row['rev']+1} AND d.data->>'contract_registry_number'='{NUM}'
AND d.data->>'registered_signed_contract_verified'='true'
AND d.data->>'quantity'='12'
AND d.metadata->'eis_filter_32515029641_enrichment'->'sources'->0->>'sha256'='{SOURCES[0][1]}')<>1
THEN RAISE EXCEPTION 'PQ postwrite mismatch'; END IF; END $g$;
COMMIT;"""
    psql(sql)
    after, actual = snapshot(), get_row(CID)
    if (
        before != after
        or actual["hash"] != h
        or actual["rev"] != row["rev"] + 1
        or any(actual["data"].get(k) != v for k, v in FIELDS.items())
    ):
        raise RuntimeError("postcommit readback mismatch")
    return {
        "case": CID,
        "before": before,
        "after": after,
        "new_verified_fields": len(FIELDS),
        "fields": FIELDS,
        "old_hash": row["hash"],
        "new_hash": h,
        "sources": proof["sources"],
        "signed_supplier_verified": False,
        "paid_verified": False,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--backup-manifest", type=Path)
    ap.add_argument("--receipt", type=Path)
    args = ap.parse_args()
    proof = evidence()
    before, row = snapshot(), get_row(CID)
    validate(row)
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "case": CID, "before": before,
                          "proof": proof}, ensure_ascii=False))
        return
    if not args.backup_manifest or not args.receipt:
        raise RuntimeError("Fresh backup and unique receipt path required")
    gate = subprocess.run(
        [sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
        capture_output=True, text=True, check=True, timeout=60,
    )
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("internal APFS acceptance failed")
    backup = verified_backup(args.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("new SHA + pg_restore checked backup required")
    result = apply(row, before, proof)
    result["backup_sha256"] = backup["sha256"]
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
