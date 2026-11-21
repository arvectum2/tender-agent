"""Source-SHA-bound sole participant and negotiated offer; no signed-supplier inference."""
import argparse
import hashlib
import io
import json
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
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

CID = "223fz:32515582393:lot1"
KEY = "bashkirenergo_sole_participant_20261102"
ZIP_REL = ("captures/223fz_32515582393_lot1/"
           "20261030T104432387724Z-02d32388-842cfe42c4ad5f79.bin")
ZIP_SHA = "842cfe42c4ad5f797cf6d4d104015406ea43d246ecc8c1cf60364861ea69ffae"
ZIP_URL = ("https://zakupki.gov.ru/223/filestore/public/1.0/download/fz223/"
           "file.html?uid=1D3831568559425290E8693A3165000C")
EIS_REL = ("captures/223fz_32515582393_lot1/"
           "20261102T163143156151Z-bd4ec281-8def93c5cba42bb1.bin")
EIS_SHA = "8def93c5cba42bb177d8fd838a456328de3b7ad364bd9c484f26932b8aba76d3"
EIS_URL = ("https://zakupki.gov.ru/epz/order/notice/protocol223/printForm/view.html"
           "?protocolGuid=a9898519-3612-0004-0000-6992e9033f64"
           "&purchaseNoticeNumber=32515582393")
PDFS = {
    "№ 26-003065 протокол итоговый.pdf":
        "028b7c02597f2f5adb7b4881334b9e4f13dc39d5e8b4a54c660c2ea7dd66298f",
    "№ 26-003065 # Протокол ЗК_преддоговорные_26.pdf":
        "a5d0232672daf75f602b1cfe8dc60d0b1cff30e8605f17d2c7dac539132151e7",
}
FIELDS = {
    "bid": "4900000.00",
    "commission_selected_participant": "ООО «УК КОНДЕНСАТОР»",
    "negotiated_offer_rub": "4850000.00",
    "protocol_status_note": (
        "Итоговый протокол АО БЭСК №2026.ЗК-000577/02 от 12.02.2026: "
        "тендер несостоявшийся (одно соответствующее предложение), "
        "закупка у единственного участника ООО «УК КОНДЕНСАТОР» "
        "за 4 900 000 руб. без НДС; переговоры №2026.ЗК-000577/03 "
        "от 16.02.2026 снизили предложение до 4 850 000 руб. без НДС. "
        "Реестр ЕИС: договор на 4 850 000 руб.; личность подписавшего "
        "поставщика и факт оплаты не установлены. "
        "Не является подтверждением победы в конкурентном тендере."
    ),
}


def checked(rel, sha, url):
    root = ROOT.resolve(strict=True)
    if root != Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live"):
        raise RuntimeError("Internal APFS required")
    p = (root / rel).resolve(strict=True)
    if root not in p.parents or p.is_symlink() or not 1000 < p.stat().st_size < 2000000:
        raise RuntimeError("Unsafe original")
    raw = p.read_bytes()
    receipt = json.loads(Path(str(p) + ".json").read_text())
    if (hashlib.sha256(raw).hexdigest() != sha
            or receipt.get("sha256") != sha or receipt.get("case_id") != CID
            or receipt.get("relative_file") != rel or receipt.get("source_url") != url
            or receipt.get("http_status") != 200):
        raise RuntimeError("SHA/receipt mismatch")
    return raw


def proof():
    texts = {}
    with zipfile.ZipFile(io.BytesIO(checked(ZIP_REL, ZIP_SHA, ZIP_URL))) as archive:
        for suffix, sha in PDFS.items():
            matches = [n for n in archive.namelist() if n.endswith(suffix)]
            if len(matches) != 1 or archive.getinfo(matches[0]).file_size > 1000000:
                raise RuntimeError("Unsafe embedded protocol")
            raw = archive.read(matches[0])
            if hashlib.sha256(raw).hexdigest() != sha:
                raise RuntimeError("Embedded PDF SHA mismatch")
            out = subprocess.run(["pdftotext", "-layout", "-", "-"], input=raw,
                                 capture_output=True, timeout=15, check=True)
            texts[suffix] = " ".join(out.stdout.decode("utf-8").split())
    final = texts["№ 26-003065 протокол итоговый.pdf"]
    talks = texts["№ 26-003065 # Протокол ЗК_преддоговорные_26.pdf"]
    if not all(q in final for q in (
        "2026.ЗК-000577/02", "ООО «УК КОНДЕНСАТОР»",
        "Признать открытый тендер несостоявшимся",
        "единственного участника", "4 900 000 руб. без НДС")):
        raise RuntimeError("Final commission quotes missing")
    if not all(q in talks for q in (
        "2026.ЗК-000577/03", "ООО «УК КОНДЕНСАТОР»",
        "4 850 000 руб. без НДС", "преддоговорных переговоров")):
        raise RuntimeError("Negotiation quotes missing")
    eis = checked(EIS_REL, EIS_SHA, EIS_URL).decode("utf-8", "replace")
    if not all(q in eis for q in ("32515582393-02", "4 900 000.00")):
        raise RuntimeError("EIS protocol corroboration missing")
    return {"zip_url": ZIP_URL, "zip_sha256": ZIP_SHA, "eis_url": EIS_URL,
            "eis_sha256": EIS_SHA, "embedded_pdf_sha256": PDFS,
            "role": "selected_sole_participant_not_competitive_winner",
            "signed_supplier_verified": False, "paid_verified": False}


def prepare(row, source):
    d = row["data"]
    if (row["id"] != CID or row["owner"] != "tender-agent"
            or d.get("canonical_id") != CID or d.get("procedure_id") != "32515582393"
            or d.get("scope") != "supply" or d.get("customer", {}).get("inn") != "0277071467"
            or d.get("contract_registered_price_rub") != "4850000.00"
            or d.get("registered_signed_contract_verified") is not True
            or d.get("winner") is not None or d.get("contract_signatory") is not None
            or digest(d) != row["hash"] or KEY in row["meta"]
            or any(d.get(k) is not None for k in FIELDS)):
        raise RuntimeError("Owner/identity/old-null guard failed")
    data = {**d, **FIELDS, "evidence": [*d.get("evidence", []),
        {"url": ZIP_URL, "sha256": ZIP_SHA, "source_tier": "first_party_etp_commission_zip",
         "excerpt": "Протокол №2026.ЗК-000577/02: один участник ООО «УК КОНДЕНСАТОР», "
                    "тендер несостоявшийся; переговоры: 4 850 000 руб. без НДС"},
        {"url": EIS_URL, "sha256": EIS_SHA, "source_tier": "first_party_eis_protocol",
         "excerpt": "Протокол №32515582393-02: анонимная заявка №1, 4 900 000 руб."}]}
    h = digest(data)
    meta = {**row["meta"], "source_content_hash": h, KEY: {
        "fields": FIELDS, "proof": source, "previous_hash": row["hash"],
        "previous_revision": row["rev"], "signed_supplier_verified": False,
        "paid_pq_equipment_sale_verified": False}}
    return data, meta, h


def apply(row, source, before):
    data, meta, h = prepare(row, source)
    old, rev = row["hash"], row["rev"]
    nulls = " AND ".join(
        f"((d.data->'{k}') IS NULL OR (d.data->'{k}')='null'::jsonb)" for k in FIELDS)
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
THEN RAISE EXCEPTION 'PQ CAS/owner/count mismatch'; END IF; END $g$;
UPDATE dp_records d SET data={js(data)},metadata={js(meta)},
revision=revision+1,updated_at=now()
FROM dp_resources r WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{CID}' AND r.content_hash='{old}' AND d.revision={rev} AND {nulls};
UPDATE dp_resources SET content_hash='{h}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{old}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{h}'
AND d.revision={rev+1} AND d.data->>'bid'='4900000.00'
AND d.metadata->'{KEY}'->'proof'->>'zip_sha256'='{ZIP_SHA}')<>1
THEN RAISE EXCEPTION 'PQ postwrite mismatch'; END IF; END $g$;
COMMIT;"""
    psql(sql)
    after = snapshot()
    actual = get_row(CID)
    if (before != after or actual["hash"] != h or actual["rev"] != rev + 1
            or any(actual["data"].get(k) != v for k, v in FIELDS.items())):
        raise RuntimeError("Postwrite readback mismatch")
    return {"id": CID, "before": before, "after": after, "new_verified_fields": len(FIELDS),
            "new_unique_lots": 0, "new_named_selected_participants": 1,
            "new_competitive_winners": 0, "new_signed_suppliers": 0,
            "new_paid_pq_equipment_sales": 0, "source_sha256": ZIP_SHA,
            "corroborating_eis_sha256": EIS_SHA, "old_hash": old, "new_hash": h}


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
                          "fields": FIELDS, "source_sha256": ZIP_SHA}, ensure_ascii=False))
        return
    if not a.backup_manifest or not a.receipt:
        raise RuntimeError("Fresh backup and receipt required")
    gate = subprocess.run([sys.executable, "-m",
                           "scripts.market_intelligence.verify_internal_runtime"],
                          capture_output=True, text=True, check=True, timeout=60)
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("Acceptance blocked")
    backup = verified_backup(a.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("Fresh SHA+pg_restore backup required")
    result = apply(row, source, before)
    result["backup_sha256"] = backup["sha256"]
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    with a.receipt.open("x", encoding="utf8") as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
