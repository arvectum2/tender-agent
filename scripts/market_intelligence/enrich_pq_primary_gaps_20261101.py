"""Source-SHA/old-null CAS enrichment for two PQ cases; never paid sales."""
import argparse
import hashlib
import json
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
from scripts.market_intelligence.enrich_pq_eis_contract_32515582393 import Text
from scripts.market_intelligence.enrich_pq_missing_field import digest, get_row

CASES = [
    {"cid": "223fz:32514947144:lot1", "scope": "supply_components", "nmck": "3186960",
         "sha": "154bcd752de22220a99d3add5ed5724188fdd64ce68cc107fe8e4387100ed5ca",
         "rel": "captures/223fz_32514947144_lot1/20261101T084156419721Z-dc87c19e-154bcd752de22220.bin",
         "url": "https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber=32514947144",
         "quotes": ["32514947144", "Поставка конденсаторов для силовых фильтров", "ИНН 4716016979"],
         "field": "customer.inn", "value": "4716016979"},
    {"cid": "223fz:32616433248:lot1", "scope": "epc", "nmck": "56330673.93",
         "sha": "2345e8a88ff2731c05a43a69af49b50e74a28cc44ae4ae714ac386111627f8e3",
         "rel": "captures/223fz_32616433248_lot1/20261101T084156793250Z-f85b2f21-2345e8a88ff2731c.bin",
         "url": "https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber=32616433248",
         "quotes": ["32616433248", "устройства компенсирования реактивной мощности (УКРМ) 35 кВ (1 шт.)"],
         "field": "voltage_kv", "value": "35"},
]


def verify(c):
    root = ROOT.resolve(strict=True)
    if root != Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live"):
        raise RuntimeError("Internal APFS only")
    rel = Path(c["rel"])
    if rel.is_absolute() or ".." in rel.parts or rel.parts[0] != "captures":
        raise ValueError("Unsafe source path")
    p = (root / rel).resolve(strict=True)
    if root not in p.parents or p.is_symlink() or not 1000 < p.stat().st_size < 1000000:
        raise ValueError("Unsafe source")
    raw = p.read_bytes()
    r = json.loads(Path(str(p) + ".json").read_text())
    if (hashlib.sha256(raw).hexdigest() != c["sha"]
            or r.get("sha256") != c["sha"] or r.get("case_id") != c["cid"]
            or r.get("source_url") != c["url"] or r.get("relative_file") != c["rel"]
            or r.get("http_status") != 200):
        raise ValueError("Original receipt/SHA mismatch")
    parser = Text()
    parser.feed(raw.decode("utf8", "replace"))
    txt = " ".join(" ".join(parser.parts).replace("\u00a0", " ").split())
    if not all(q in txt for q in c["quotes"]):
        raise ValueError("Exact original quote mismatch")
    return {"url": c["url"], "sha256": c["sha"],
            "source_tier": "first_party_eis_notice", "excerpt": "; ".join(c["quotes"])}


def validate(c, r):
    d = r["data"]
    old = d.get("customer", {}).get("inn") if c["field"] == "customer.inn" else d.get(c["field"])
    if (r["id"] != c["cid"] or r["owner"] != "tender-agent"
            or d.get("canonical_id") != c["cid"]
            or d.get("procedure_id") != c["cid"].split(":")[1]
            or d.get("scope") != c["scope"] or d.get("nmck_rub") != c["nmck"]
            or digest(d) != r["hash"] or old is not None
            or d.get("source_urls") is not None
            or r["meta"].get("primary_gap_20261101")):
        raise RuntimeError("Owner/identity/old-null CAS conflict")


def prepare(c, r, s):
    d = {**r["data"]}
    d["source_urls"] = [{"url": s["url"], "sha": s["sha256"], "tier": "first_party"}]
    if c["field"] == "customer.inn":
        d["customer"] = {**d["customer"], "inn": c["value"]}
    else:
        d[c["field"]] = c["value"]
    d["evidence"] = [*d.get("evidence", []), s]
    h = digest(d)
    meta = {**r["meta"], "source_content_hash": h,
            "primary_gap_20261101": {"field": c["field"], "value": c["value"],
                "source_sha256": s["sha256"], "previous_hash": r["hash"],
                "previous_revision": r["rev"], "winner_verified": False,
                "paid_sale_verified": False}}
    return d, meta, h


def apply(items, before):
    sql = ["BEGIN ISOLATION LEVEL SERIALIZABLE;",
           "SET LOCAL statement_timeout='55s'; SET LOCAL lock_timeout='9s';",
           f"SELECT pg_advisory_xact_lock(hashtext('{COL}-delta'));",
           "LOCK TABLE dp_resources,dp_records IN SHARE ROW EXCLUSIVE MODE;",
           f"""DO $g$ BEGIN IF current_database()<>'arvectum_data'
OR (SELECT owner FROM dp_collections WHERE collection_id='{COL}')<>'tender-agent'
OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COL}')<>{before['rows']}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}')<>{before['rows']}
THEN RAISE EXCEPTION 'PQ corpus count/owner mismatch'; END IF; END $g$;"""]
    for c, r, s in items:
        cid = c["cid"]
        d, meta, h = prepare(c, r, s)
        old_null = ("((d.data->'customer'->'inn') IS NULL OR (d.data->'customer'->'inn') = 'null'::jsonb)"
                    if c["field"] == "customer.inn"
                    else f"(d.data->'{c['field']}') IS NULL")
        guard = (f"r.collection_id='{COL}' AND r.external_id='{cid}' "
                 f"AND r.content_hash='{r['hash']}' AND d.revision={r['rev']} "
                 f"AND (d.data->'source_urls') IS NULL AND {old_null}")
        sql.extend([
            f"""DO $g$ BEGIN IF (SELECT count(*) FROM dp_records d
JOIN dp_resources r USING(resource_id) WHERE {guard})<>1
THEN RAISE EXCEPTION 'PQ CAS mismatch {cid}'; END IF; END $g$;""",
            f"""UPDATE dp_records d SET data={js(d)},metadata={js(meta)},
revision=revision+1,updated_at=now() FROM dp_resources r
WHERE d.resource_id=r.resource_id AND {guard};""",
            f"""UPDATE dp_resources SET content_hash='{h}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{cid}'
AND content_hash='{r['hash']}';""",
            f"""DO $g$ BEGIN IF (SELECT count(*) FROM dp_records d
JOIN dp_resources r USING(resource_id) WHERE r.collection_id='{COL}'
AND r.external_id='{cid}' AND r.content_hash='{h}'
AND d.revision={r['rev'] + 1}
AND d.metadata->'primary_gap_20261101'->>'source_sha256'='{s['sha256']}')<>1
THEN RAISE EXCEPTION 'PQ postwrite mismatch {cid}'; END IF; END $g$;""",
        ])
    psql("\n".join([*sql, "COMMIT;"]))
    after = snapshot()
    if before != after:
        raise RuntimeError("Corpus counts changed")
    results = []
    for c, r, s in items:
        actual = get_row(c["cid"])
        d, _, h = prepare(c, r, s)
        if (actual["hash"] != h or actual["rev"] != r["rev"] + 1
                or actual["data"] != d):
            raise RuntimeError("Postwrite readback mismatch")
        results.append({"case": c["cid"], "field": c["field"],
                        "value": c["value"], "source_sha256": s["sha256"],
                        "new_hash": h})
    return {"before": before, "after": after, "results": results,
            "new_verified_fields": 4}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-manifest", type=Path)
    p.add_argument("--receipt", type=Path)
    a = p.parse_args()
    before = snapshot()
    items = []
    for c in CASES:
        s = verify(c)
        r = get_row(c["cid"])
        validate(c, r)
        items.append((c, r, s))
    if not a.apply:
        print(json.dumps({"mode": "dry_run", "before": before,
                          "cases": [x[0]["cid"] for x in items],
                          "new_verified_fields": 4}, ensure_ascii=False))
        return
    if not a.backup_manifest or not a.receipt:
        raise RuntimeError("Fresh backup and exclusive receipt required")
    gate = subprocess.run([sys.executable, "-m",
                           "scripts.market_intelligence.verify_internal_runtime"],
                          capture_output=True, text=True, check=True, timeout=60)
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("Acceptance failed")
    backup = verified_backup(a.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("Fresh SHA/pg_restore backup required")
    result = apply(items, before)
    result["backup_sha256"] = backup["sha256"]
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    with a.receipt.open("x", encoding="utf8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
