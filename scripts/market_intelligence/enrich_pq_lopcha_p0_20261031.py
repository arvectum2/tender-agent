"""Source-SHA-bound, null-only buyer identity enrichment for three existing notices."""
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

INN = "4716016979"
INTERNAL = Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live")
CASES = {
    "32515208744": ("epc", "20261031T193259718733Z-ac1b20f7-080e48e5aede0ff8.bin",
                    "080e48e5aede0ff8d44cbdc59b43918644c2f76a935298b1974c5319be0fd18d"),
    "32515584863": ("design", "20261031T193301584637Z-c376f321-916ae6462b343d87.bin",
                    "916ae6462b343d87f26aec20ab0a074ad252ed16653cdf409f77f709310b6234"),
    "32615760238": ("design", "20261031T193303791941Z-f0d71a5a-d230fc1a29457fda.bin",
                    "d230fc1a29457fdaa475ddc9fd35d8c519c3255ff64f8ae107d7157cf5a904c8"),
}
QUOTE = b'\xd0\x98\xd0\x9d\xd0\x9d 4716016979'


def source(number, root=ROOT):
    scope, name, sha = CASES[number]
    root = Path(root).resolve(strict=True)
    if root != INTERNAL:
        raise ValueError("internal APFS only")
    rel = f"captures/223fz_{number}_lot1/{name}"
    path = (root / rel).resolve(strict=True)
    if root not in path.parents or path.is_symlink() or path.stat().st_size > 2000000:
        raise ValueError("unsafe original")
    b = path.read_bytes()
    m = json.loads(Path(str(path) + ".json").read_text())
    url = f"https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber={number}"
    text = " ".join(" ".join(html.fromstring(b.decode("utf-8")).itertext()).split())
    if (hashlib.sha256(b).hexdigest() != sha or m.get("sha256") != sha
            or m.get("source_url") != url or m.get("case_id") != f"223fz:{number}:lot1"
            or m.get("http_status") != 200 or m.get("bytes") != len(b)
            or QUOTE.decode("utf-8") not in text or number not in text
            or b'\xd0\xa0\xd0\x9e\xd0\xa1\xd0\xa1\xd0\x95\xd0\xa2\xd0\x98' not in b):
        raise ValueError("SHA/receipt/buyer quote mismatch")
    return {"url": url, "sha256": sha, "relative_file": rel,
            "exact_original_quote": "ИНН 4716016979", "scope": scope}


def validate(number, row):
    d = row["data"]
    if (row["id"] != f"223fz:{number}:lot1" or row["owner"] != "tender-agent"
            or d.get("canonical_id") != row["id"] or d.get("procedure_id") != number
            or d.get("scope") != CASES[number][0]
            or d.get("buyer_inn") is not None or d.get("source_urls") is not None
            or digest(d) != row["hash"]
            or "eis_lopcha_p0" in row["meta"]):
        raise RuntimeError("old-null/source-owner/identity CAS blocked")


def prepared():
    out = []
    for number in CASES:
        src = source(number)
        row = get_row(f"223fz:{number}:lot1")
        validate(number, row)
        d = {**row["data"], "buyer_inn": INN,
             "source_urls": [{"url": src["url"], "tier": "first_party", "sha": src["sha256"]}]}
        h = digest(d)
        meta = {**row["meta"], "source_content_hash": h,
                "eis_lopcha_p0": {"source": src, "fields": ["buyer_inn", "source_urls"],
                                  "old_hash": row["hash"], "old_revision": row["rev"]}}
        out.append((number, row, d, meta, h, src))
    return out


def transaction(rows, before):
    sql = [f"""BEGIN ISOLATION LEVEL SERIALIZABLE;
SET LOCAL statement_timeout='55s'; SET LOCAL lock_timeout='9s';
SELECT pg_advisory_xact_lock(hashtext('{COL}-delta'));
LOCK TABLE dp_resources, dp_records IN SHARE ROW EXCLUSIVE MODE;
DO $g$ BEGIN IF current_database()<>'arvectum_data'
OR (SELECT owner FROM dp_collections WHERE collection_id='{COL}')<>'tender-agent'
OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}')<>{before['rows']}
THEN RAISE EXCEPTION 'global count/owner mismatch'; END IF; END $g$;"""]
    for number, row, data, meta, new_hash, src in rows:
        cid = f"223fz:{number}:lot1"
        old, rev = row["hash"], row["rev"]
        where = (f"r.collection_id='{COL}' AND r.external_id='{cid}' "
                 f"AND r.content_hash='{old}' AND d.revision={rev} "
                 "AND (d.data->'buyer_inn') IS NULL AND (d.data->'source_urls') IS NULL")
        sql += [
            f"""DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r JOIN dp_records d
USING(resource_id) WHERE {where})<>1 THEN RAISE EXCEPTION 'old-null CAS {number}';
END IF; END $g$;""",
            f"""UPDATE dp_records d SET data={js(data)}, metadata={js(meta)},
revision=revision+1, updated_at=now() FROM dp_resources r
WHERE d.resource_id=r.resource_id AND {where};""",
            f"""UPDATE dp_resources SET content_hash='{new_hash}', updated_at=now()
WHERE collection_id='{COL}' AND external_id='{cid}' AND content_hash='{old}';""",
            f"""DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r JOIN dp_records d
USING(resource_id) WHERE r.collection_id='{COL}' AND r.external_id='{cid}'
AND r.content_hash='{new_hash}' AND d.revision={rev+1}
AND d.data->>'buyer_inn'='{INN}'
AND d.data->'source_urls'->0->>'sha'='{src['sha256']}'
AND d.metadata->'eis_lopcha_p0'->'source'->>'sha256'='{src['sha256']}')<>1
THEN RAISE EXCEPTION 'postwrite CAS {number}'; END IF; END $g$;""",
        ]
    return "\n".join(sql + ["COMMIT;"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-manifest", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    before = snapshot()
    rows = prepared()
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "before": before,
                          "cases": list(CASES)}, ensure_ascii=False))
        return
    if not args.backup_manifest or not args.receipt:
        raise RuntimeError("fresh backup and unique receipt required")
    gate = subprocess.run([sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
                          capture_output=True, text=True, check=True, timeout=60)
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("acceptance gate failed")
    backup = verified_backup(args.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("fresh SHA+pg_restore full backup required")
    psql(transaction(rows, before))
    after = snapshot()
    if before != after:
        raise RuntimeError("corpus count drift")
    for number, row, data, _, h, _ in rows:
        got = get_row(f"223fz:{number}:lot1")
        if got["hash"] != h or got["rev"] != row["rev"]+1 or got["data"] != data:
            raise RuntimeError("postwrite readback mismatch")
    result = {"before": before, "after": after, "new_unique_lots": 0,
              "new_verified_db_fields": 6, "signed_supplier_gain": 0,
              "cases": [{"id": f"223fz:{n}:lot1", "source": src,
                         "old_hash": row["hash"], "new_hash": h}
                        for n, row, _, _, h, src in rows],
              "backup_sha256": backup["sha256"]}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
