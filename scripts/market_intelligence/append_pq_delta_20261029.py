"""Append SHA-verified EIS cases to an owned collection; dry-run by default."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

# Prefer a verified internal APFS runtime after macOS removable-volume access
# failures. Keep legacy source root only when stable storage is not provisioned.
_INTERNAL_ROOT = Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live")
_LEGACY_ROOT = Path("/Volumes/ArvectumSSD/Arvectum/runtime/market-intelligence/pq-agent-pilot-live")
ROOT = Path(os.environ.get("ARVECTUM_MI_RUNTIME_ROOT",
                           str(_INTERNAL_ROOT if _INTERNAL_ROOT.is_dir() else _LEGACY_ROOT)))
COL = "arvectum-market-pq-6-35kv"
SOURCE = "market_intelligence_procurement_research"


def psql(sql: str) -> str:
    p = subprocess.run(
        ["docker", "exec", "-i", "arvectum-postgres", "sh", "-c",
         'psql -X -A -t -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d arvectum_data'],
        input=sql, capture_output=True, text=True, timeout=60, check=False,
    )
    if p.returncode:
        raise RuntimeError(p.stderr[-950:])
    return p.stdout.strip()


def snapshot() -> dict:
    sql = """BEGIN READ ONLY;
SELECT jsonb_build_object(
  'owner',(SELECT owner FROM dp_collections WHERE collection_id='arvectum-market-pq-6-35kv'),
  'rows',(SELECT count(*) FROM dp_resources WHERE collection_id='arvectum-market-pq-6-35kv'),
  'unique',(SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='arvectum-market-pq-6-35kv'),
  'records',(SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
       WHERE r.collection_id='arvectum-market-pq-6-35kv'))::text;
COMMIT;"""
    result = json.loads(next(line for line in psql(sql).splitlines() if line.startswith("{")))
    if result["owner"] != "tender-agent" or result["rows"] != result["unique"] or result["rows"] != result["records"]:
        raise RuntimeError("Target collection mismatched")
    return result


def source_data(manifest: Path) -> tuple[list[dict], dict]:
    m = json.loads(manifest.read_text(encoding="utf-8"))
    if m["schema_version"] != "mi-pq-source-bound-incremental/1":
        raise ValueError("Unrecognized source schema")
    cases = m["new_cases"]
    if not 1 <= len(cases) <= 10:
        raise ValueError("Case limit")
    out = []
    seen = set()
    for item in cases:
        record = item["source_record"]
        cid = record["canonical_id"]
        if not re.fullmatch(
            r"(?:223fz:[0-9]{11}|commercial:РН[0-9]{8}):lot[1-9][0-9]*", cid
        ) or cid in seen:
            raise ValueError("Bad/duplicate identity")
        regime = "commercial" if cid.startswith("commercial:") else "223-fz"
        if (record["procedure_id"] != cid.split(":")[1]
                or record.get("procurement_regime") != regime):
            raise ValueError("Wrong procedure identity/regime")
        if regime == "commercial" and (
            record.get("market_scope") != "core_6kv_equipment_supply_notice"
            or record.get("technical", {}).get("voltage_kv") != 6
            or record.get("nmck_rub") is not None
            or record.get("signed_supplier_verified") is not False
        ):
            raise ValueError("Unreviewed commercial core or price promotion")
        for flag in ("signed_supplier_verified", "supplier_verified", "paid_verified"):
            if record.get(flag) is not False:
                raise ValueError("Prohibited unverified supplier/payment promotion")
        if record.get("realized_equipment_revenue_rub") is not None:
            raise ValueError("Unverified sale")
        original_shas = set()
        for original in item["verified_originals"]:
            relative = Path(original["private_relative"])
            root = ROOT.resolve()
            path = (root / relative).resolve(strict=True)
            if (relative.is_absolute() or ".." in relative.parts or root not in path.parents
                    or path.is_symlink() or not path.is_file() or path.stat().st_size > 20_000_000):
                raise ValueError("Unsafe original")
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if digest != original["sha256"] or len(raw) != original["bytes"]:
                raise ValueError("SHA or size drift")
            original_shas.add(digest)
        evidence = record.get("evidence", [])
        if (len(original_shas) < 3 or not evidence or
                not all(isinstance(e.get("url"), str) and e["url"].startswith("https://")
                        and len(e.get("sha256", "")) == 64 for e in evidence)
                or not any(e["sha256"] in original_shas for e in evidence)):
            raise ValueError("Not enough source-bound primary evidence")
        full = hashlib.sha256(cid.encode()).hexdigest()
        content = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        metadata = {
            "data_version": "incremental_20261029_v1",
            "mi013_import_batch": "source-bound-20261029",
            "procurement_id": cid,
            "procedure_id": record["procedure_id"],
            "regime": regime, "family": record["family"], "scope": record["scope"],
            "market_scope": record["market_scope"], "buyer": record["customer"],
            "status": record["status"], "nmck_rub": record["nmck_rub"],
            "source_urls": list(dict.fromkeys(e["url"] for e in evidence)),
            "source_tiers": [e["source_tier"] for e in evidence],
            "source_original_sha256": sorted(original_shas),
            "research_not_market_population": True,
            "winning_supplier_only_if_verified": None,
        }
        digest = hashlib.sha256(content).hexdigest()
        out.append({"cid": cid, "id": full[:48], "uri": "urn:arvectum:pq:procurement:" + full,
                    "hash": digest, "record": record, "metadata": metadata,
                    "record_metadata": {"research_version": "incremental_20261029_v1",
                                        "source_content_hash": digest,
                                        "source_evidence_urls": metadata["source_urls"]}})
        seen.add(cid)
    return out, m


def js(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "convert_from(decode('" + raw.hex() + "','hex'),'UTF8')::jsonb"


def verified_backup(path: Path) -> dict:
    obj = json.loads(path.read_text())
    dump = path.parent / obj["backup_file"]
    if (dump.is_symlink() or not dump.is_file() or obj["database"] != "arvectum_data"
            or dump.stat().st_size != obj["bytes"] or
            hashlib.sha256(dump.read_bytes()).hexdigest() != obj["sha256"]):
        raise RuntimeError("Full backup verification failed")
    return obj


def insert(rows: list[dict], expected: int) -> dict:
    after = expected + len(rows)
    ids = " OR ".join("external_id='" + r["cid"] + "'" for r in rows)
    sql = [
        "BEGIN ISOLATION LEVEL SERIALIZABLE;",
        "SET LOCAL statement_timeout='55s';",
        "SET LOCAL lock_timeout='9s';",
        "SELECT pg_advisory_xact_lock(hashtext('arvectum-market-pq-6-35kv-delta'));",
        "LOCK TABLE dp_resources, dp_records IN SHARE ROW EXCLUSIVE MODE;",
        f"""DO $g$ BEGIN
        IF current_database() <> 'arvectum_data'
          OR (SELECT owner FROM dp_collections WHERE collection_id='{COL}')<>'tender-agent'
          OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COL}')<>{expected}
          OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
              WHERE r.collection_id='{COL}')<>{expected}
          OR (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COL}')<>{expected}
          OR EXISTS(SELECT 1 FROM dp_resources WHERE collection_id='{COL}' AND ({ids}))
        THEN RAISE EXCEPTION 'Collection drift or duplicate: refusing import';
        END IF; END $g$;""",
    ]
    for r in rows:
        sql.append(
            "INSERT INTO dp_resources(resource_id,collection_id,source_type,canonical_uri,external_id,"
            "content_hash,status,metadata,first_seen_at,last_seen_at,created_at,updated_at) VALUES("
            f"'{r['id']}','{COL}','{SOURCE}','{r['uri']}','{r['cid']}','{r['hash']}',"
            f"'staged_unreviewed',{js(r['metadata'])},now(),now(),now(),now());"
        )
        sql.append(
            "INSERT INTO dp_records(record_id,resource_id,record_type,data,revision,review_status,"
            "metadata,created_at,updated_at) VALUES ("
            f"'pq:{r['id']}','{r['id']}','pq_procurement_notice_lot',"
            f"{js(r['record'])},1,'unreviewed',{js(r['record_metadata'])},now(),now());"
        )
    sql += [
        f"""DO $g$ BEGIN IF
        (SELECT count(*) FROM dp_resources WHERE collection_id='{COL}')<>{after}
        OR (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COL}')<>{after}
        OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
            WHERE r.collection_id='{COL}')<>{after}
        THEN RAISE EXCEPTION 'Post-insert cardinality error';
        END IF; END $g$;""",
        "COMMIT;",
    ]
    psql("\n".join(sql))
    current = snapshot()
    if any(current[k] != after for k in ("rows", "unique", "records")):
        raise RuntimeError("Post-commit readback invalid")
    check = " OR ".join("external_id='" + r["cid"] + "'" for r in rows)
    receipt = psql(
        f"""BEGIN READ ONLY;
        SELECT jsonb_agg(jsonb_build_object('id',r.external_id,'hash',r.content_hash,
        'status',r.status,'review',d.review_status,'revision',d.revision))::text
        FROM dp_resources r JOIN dp_records d USING(resource_id)
        WHERE r.collection_id='{COL}' AND ({check}); COMMIT;"""
    )
    verified = json.loads(next(line for line in receipt.splitlines() if line.startswith("[")))
    if len(verified) != len(rows) or any(
        not any(v["id"] == r["cid"] and v["hash"] == r["hash"]
                and v["status"] == "staged_unreviewed" and v["review"] == "unreviewed"
                for v in verified) for r in rows
    ):
        raise RuntimeError("Inserted rows not found or hashes differ")
    return {"after": current, "readback": verified}


def main() -> None:
    cli = argparse.ArgumentParser()
    cli.add_argument("--manifest", type=Path, required=True)
    cli.add_argument("--apply", action="store_true")
    cli.add_argument("--backup-manifest", type=Path)
    cli.add_argument("--receipt", type=Path)
    args = cli.parse_args()
    rows, data = source_data(args.manifest)
    before = snapshot()
    if any(before[k] != data["base_db_expected_records"] for k in ("rows", "unique", "records")):
        raise RuntimeError("Unexpected baseline; do not mutate DB")
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "before": before, "staged": len(rows),
                          "ids": [r["cid"] for r in rows]}, ensure_ascii=False))
        return
    if not args.backup_manifest or not args.receipt or args.receipt.is_symlink():
        raise RuntimeError("Apply requires backup manifest and receipt path")
    backup = verified_backup(args.backup_manifest)
    result = insert(rows, expected=before["rows"])
    receipt = {
        "schema_version": "pq-incremental-db-import-receipt/1", "before": before, **result,
        "backup_sha256": backup["sha256"], "backup_file": backup["backup_file"],
        "source_manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "new_unique_lots": len(rows), "signed_supplier_additions": 0,
        "verified_equipment_sales_rub_additions": 0,
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
