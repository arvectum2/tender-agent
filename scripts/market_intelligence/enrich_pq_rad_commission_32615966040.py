"""Source-pinned RAD commission recommendation; NOT a signed contract."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
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
from scripts.market_intelligence.enrich_pq_docx_fields import docx_text
from scripts.market_intelligence.enrich_pq_missing_field import digest, get_row

CID = "223fz:32615966040:lot1"
D = "captures/223fz_32615966040_lot1/"
CARD = D + "20261031T003339887967Z-da2dead4-522df115aded8866.bin"
RAR = D + "20261031T003339536871Z-6e9a3536-86a6d2605f575465.bin"
CARD_SHA = "522df115aded8866baa444e728b0e597be76de11f6f1b7c85bd74a2c5d703ac8"
RAR_SHA = "86a6d2605f575465feebfb5cb84eae1d90f7f4ed56bd178588061dc200273744"
MEMBER = "Протокол подведения итогов №МВС-61_26 от 19.05.2026.docx"
MEMBER_SHA = "c4259db4db81d2d0af153acf2fc56ac6e3ac354999c84b9248431bb6814338d6"
WINNER = 'ООО "ЭНЕРГОСЕТЬ"'
INTERNAL = Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live")


def source(rel, expected, marker):
    root = ROOT.resolve(strict=True)
    if root != INTERNAL:
        raise ValueError("Internal APFS required")
    p = (root / rel).resolve(strict=True)
    if root not in p.parents or p.is_symlink() or p.stat().st_size > 4_000_000:
        raise ValueError("Unsafe original")
    raw = p.read_bytes()
    r = json.loads(Path(str(p) + ".json").read_text())
    if (hashlib.sha256(raw).hexdigest() != expected or r["sha256"] != expected
            or r["relative_file"] != rel or r["case_id"] != CID
            or r["http_status"] != 200
            or not r["source_url"].startswith("https://tender.lot-online.ru/etp/")
            or marker not in r["source_url"]):
        raise ValueError("Source receipt/SHA/identity mismatch")
    return raw, r["source_url"]


def proof():
    card, card_url = source(CARD, CARD_SHA, "LotCard")
    rar, rar_url = source(RAR, RAR_SHA, "downloadppf")
    if b"32615966040" not in card or b"RAD260020676" not in card:
        raise ValueError("Wrong official RAD lot")
    listing = subprocess.run(["/usr/bin/bsdtar", "-tf", "-"], input=rar,
                             capture_output=True, check=True, timeout=20).stdout.decode()
    names = listing.splitlines()
    if len(names) > 20 or names.count(MEMBER) != 1 or any(
        n.startswith("/") or ".." in Path(n).parts for n in names
    ):
        raise ValueError("RAR unsafe/ambiguous member")
    doc = subprocess.run(["/usr/bin/bsdtar", "-xOf", "-", MEMBER], input=rar,
                         capture_output=True, check=True, timeout=20).stdout
    if hashlib.sha256(doc).hexdigest() != MEMBER_SHA:
        raise ValueError("Contained DOCX SHA mismatch")
    t = docx_text(doc)
    if not all(s in t for s in (
        "РАД № RAD260020676 ЕИС 32615966040",
        "Всего поступила 1 Заявка",
        "признать Закупку несостоявшейся",
        "5 273 763,77 руб. с НДС",
    )):
        raise ValueError("Protocol context mismatch")
    if not re.search(r"Протокол №\s*МВС-\s*61\s*/26", t):
        raise ValueError("Protocol number mismatch")
    match = re.search(
        r'заключить договор.{0,1200}?с Участником №\s*490997\s*,\s*ООО "ЭНЕРГОСЕТЬ"', t
    )
    if not match:
        raise ValueError("Committee recommendation not proven")
    return {
        "source_urls": [card_url, rar_url],
        "source_sha256": [CARD_SHA, RAR_SHA],
        "member_sha256": MEMBER_SHA,
        "exact_original_quote": match.group(0),
        "role": "commission_recommended_contractor_not_signed_supplier",
        "procurement_failed_one_application": True,
        "signed_supplier_verified": False,
        "signed_contract_verified": False,
    }


def write(row, before, evidence):
    if (row["id"] != CID or row["owner"] != "tender-agent"
            or row["data"].get("procedure_id") != "32615966040"
            or digest(row["data"]) != row["hash"]
            or row["data"].get("winner") is not None
            or row["meta"].get("rad_commission_enrichment")
            or not any("32615966040" in e.get("url", "")
                       for e in row["data"].get("evidence", []))):
        raise RuntimeError("Owner/identity/null-only CAS failed")
    data = {**row["data"], "winner": WINNER}
    new_hash = digest(data)
    meta = {**row["meta"], "source_content_hash": new_hash,
            "rad_commission_enrichment": {
                **evidence, "field": "winner", "value": WINNER,
                "previous_hash": row["hash"], "previous_revision": row["rev"],
            }}
    sql = f"""BEGIN ISOLATION LEVEL SERIALIZABLE;
SET LOCAL statement_timeout='55s'; SET LOCAL lock_timeout='9s';
SELECT pg_advisory_xact_lock(hashtext('{COL}-delta'));
LOCK TABLE dp_resources, dp_records IN SHARE ROW EXCLUSIVE MODE;
DO $g$ BEGIN IF current_database()<>'arvectum_data'
OR (SELECT owner FROM dp_collections WHERE collection_id='{COL}')<>'tender-agent'
OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
 WHERE r.collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
 WHERE r.collection_id='{COL}' AND r.external_id='{CID}'
 AND r.content_hash='{row['hash']}' AND d.revision={row['rev']}
 AND (d.data->'winner') IS NULL AND d.data->>'procedure_id'='32615966040')<>1
THEN RAISE EXCEPTION 'RAD CAS/owner/count mismatch'; END IF; END $g$;
UPDATE dp_records d SET data={js(data)},metadata={js(meta)},revision=revision+1,updated_at=now()
FROM dp_resources r WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{CID}' AND r.content_hash='{row['hash']}' AND d.revision={row['rev']}
AND (d.data->'winner') IS NULL AND d.data->>'procedure_id'='32615966040';
UPDATE dp_resources SET content_hash='{new_hash}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{row['hash']}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
 WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{new_hash}'
 AND d.revision={row['rev'] + 1} AND d.data->'winner'={js(WINNER)}
 AND d.metadata->'rad_commission_enrichment'->>'member_sha256'='{MEMBER_SHA}')<>1
THEN RAISE EXCEPTION 'RAD postwrite mismatch'; END IF; END $g$;
COMMIT;"""
    psql(sql)
    after, actual = snapshot(), get_row(CID)
    if (before != after or actual["hash"] != new_hash
            or actual["rev"] != row["rev"] + 1 or actual["data"].get("winner") != WINNER):
        raise RuntimeError("RAD postwrite readback mismatch")
    return {"case": CID, "before": before, "after": after, "new_verified_fields": 1,
            "field": "winner", "value": WINNER, "proof": evidence, "new_hash": new_hash}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-manifest", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    evidence, before, row = proof(), snapshot(), get_row(CID)
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "before": before, "proof": evidence,
                          "winner_old": row["data"].get("winner")}, ensure_ascii=False))
        return
    if not args.backup_manifest or not args.receipt:
        raise RuntimeError("Fresh full backup and unique receipt mandatory")
    gate = subprocess.run([sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
                          capture_output=True, text=True, check=True, timeout=60)
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("Internal runtime acceptance blocked")
    backup = verified_backup(args.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("New verified full backup required")
    result = write(row, before, evidence)
    result["backup_sha256"] = backup["sha256"]
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
