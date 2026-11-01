"""CAS-guarded first-party identity enrichment for Vanino design-only lot."""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from lxml import html

from scripts.market_intelligence.append_pq_delta_20261029 import (
    COL,
    ROOT,
    js,
    psql,
    snapshot,
    verified_backup,
)
from scripts.market_intelligence.enrich_pq_missing_field import digest, get_row

CID = "223fz:32616506708:lot1"
NUMBER = "32616506708"
INN = "7728589190"
PLATFORM = "РТС-тендер"
URL = "https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber=32616506708"
SHA = "9ecb0dab2ed15573a387f258c3a9f4301e65dd53f9b280d4568258bfa908d749"
REL = "captures/223fz_32616506708_lot1/20261101T043012405423Z-3a1e8634-9ecb0dab2ed15573.bin"
INTERNAL = Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live")
QUOTES = ("Реестровый номер извещения 32616506708", "ИНН 7728589190",
          "Электронная площадка РТС-тендер")


def source(root=ROOT):
    root = Path(root).resolve(strict=True)
    if root != INTERNAL:
        raise ValueError("Internal APFS required")
    p = (root / REL).resolve(strict=True)
    if root not in p.parents or p.is_symlink() or p.stat().st_size > 2_000_000:
        raise ValueError("Unsafe source")
    b = p.read_bytes()
    receipt = json.loads(Path(str(p) + ".json").read_text())
    text = " ".join(" ".join(html.fromstring(b).itertext()).split())
    if (hashlib.sha256(b).hexdigest() != SHA or receipt.get("sha256") != SHA
            or receipt.get("source_url") != URL or receipt.get("case_id") != CID
            or receipt.get("http_status") != 200 or receipt.get("bytes") != len(b)
            or not all(q in text for q in QUOTES)):
        raise ValueError("Source SHA/receipt/exact quotes mismatch")
    return {"url": URL, "sha256": SHA, "relative_file": REL,
            "exact_original_quotes": list(QUOTES)}


def validate(row):
    d = row["data"]
    if (row["id"] != CID or row["owner"] != "tender-agent"
            or d.get("canonical_id") != CID or d.get("procedure_id") != NUMBER
            or d.get("scope") != "design" or d.get("buyer_inn") is not None
            or d.get("platform") is not None or d.get("source_urls") is not None
            or "eis_ntc_vanino_p0" in row["meta"] or digest(d) != row["hash"]):
        raise RuntimeError("Old-null/identity/owner/hash CAS blocked")


def sql_for(row, data, meta, new_hash, before):
    old, rev = row["hash"], row["rev"]
    where = (f"r.collection_id='{COL}' AND r.external_id='{CID}' "
             f"AND r.content_hash='{old}' AND d.revision={rev} "
             "AND (d.data->'buyer_inn') IS NULL "
             "AND (d.data->'platform') IS NULL "
             "AND (d.data->'source_urls') IS NULL")
    return f"""BEGIN ISOLATION LEVEL SERIALIZABLE;
SET LOCAL statement_timeout='55s'; SET LOCAL lock_timeout='9s';
SELECT pg_advisory_xact_lock(hashtext('{COL}-delta'));
LOCK TABLE dp_resources, dp_records IN SHARE ROW EXCLUSIVE MODE;
DO $g$ BEGIN IF current_database()<>'arvectum_data'
OR (SELECT owner FROM dp_collections WHERE collection_id='{COL}')<>'tender-agent'
OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE {where})<>1
THEN RAISE EXCEPTION 'Vanino prewrite CAS'; END IF; END $g$;
UPDATE dp_records d SET data={js(data)}, metadata={js(meta)},
revision=revision+1,updated_at=now() FROM dp_resources r
WHERE d.resource_id=r.resource_id AND {where};
UPDATE dp_resources SET content_hash='{new_hash}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{old}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}'
AND r.content_hash='{new_hash}' AND d.revision={rev+1}
AND d.data->>'buyer_inn'='{INN}' AND d.data->>'platform'='{PLATFORM}'
AND d.data->'source_urls'->0->>'sha'='{SHA}'
AND d.metadata->'eis_ntc_vanino_p0'->'source'->>'sha256'='{SHA}')<>1
THEN RAISE EXCEPTION 'Vanino postwrite CAS'; END IF; END $g$;
COMMIT;"""


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--apply", action="store_true")
    a.add_argument("--backup-manifest", type=Path)
    a.add_argument("--receipt", type=Path)
    args = a.parse_args()
    src = source()
    before = snapshot()
    row = get_row(CID)
    validate(row)
    data = {**row["data"], "buyer_inn": INN, "platform": PLATFORM,
            "source_urls": [{"url": URL, "tier": "first_party", "sha": SHA}]}
    h = digest(data)
    meta = {**row["meta"], "source_content_hash": h,
            "eis_ntc_vanino_p0": {"source": src,
                                  "fields": ["buyer_inn", "platform", "source_urls"],
                                  "old_hash": row["hash"], "old_revision": row["rev"]}}
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "case": CID, "before": before,
                          "fields": meta["eis_ntc_vanino_p0"]["fields"],
                          "source_sha256": SHA}, ensure_ascii=False))
        return
    if not args.backup_manifest or not args.receipt:
        raise RuntimeError("Fresh backup and receipt required")
    gate = subprocess.run([sys.executable, "-m",
                           "scripts.market_intelligence.verify_internal_runtime"],
                          capture_output=True, text=True, check=True, timeout=60)
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("Acceptance blocked")
    backup = verified_backup(args.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("Fresh SHA+pg_restore backup required")
    psql(sql_for(row, data, meta, h, before))
    after = snapshot()
    got = get_row(CID)
    if (after != before or got["hash"] != h or got["rev"] != row["rev"] + 1
            or got["data"] != data
            or got["meta"].get("eis_ntc_vanino_p0") != meta["eis_ntc_vanino_p0"]):
        raise RuntimeError("Postwrite readback/count mismatch")
    result = {"case": CID, "before": before, "after": after,
              "new_unique_lots": 0, "new_verified_fields": 3,
              "old_hash": row["hash"], "new_hash": h, "source": src,
              "backup_sha256": backup["sha256"]}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
