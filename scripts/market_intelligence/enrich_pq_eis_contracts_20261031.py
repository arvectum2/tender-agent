"""SHA-bound EIS signed contract enrichment, only previously null fields."""
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
    {"cid": "223fz:32616412267:lot1", "inn": "3801006828", "scope": "maintenance",
         "nmck": "4295282.00", "num": "53801006828260000720000",
         "fields": {"contract_registry_number": "53801006828260000720000",
                     "contract_number": "61/26кс/223", "contract_signed_date": "2026-10-19",
                     "contract_registered_price_rub": "2639026.64",
                     "registered_signed_contract_verified": True, "voltage_kv": "6"},
         "files": [
             ("20261031T113646106073Z-f6ac4760-a95df80e9044f505.bin",
              "a95df80e9044f5053756330c10a912d18001a79300c1fa0397f01fdd06c87f11",
              "https://zakupki.gov.ru/epz/contractfz223/card/contract-info.html?reestrNumber=53801006828260000720000",
              ["2 639 026,64", "19.10.2026", "6кВ"]),
             ("20261031T113646483594Z-413769f2-49200da5539bfa96.bin",
              "49200da5539bfa96f2f4c43b7d32b6eb2aef312ff7f136ee5da146488a8d3814",
              "https://zakupki.gov.ru/epz/contractfz223/printForm/view.html?reestrNumber=53801006828260000720000",
              ["2 639 026.64", "19.10.2026", "6кВ"])]},
    {"cid": "223fz:32616181358:lot1", "inn": "7724646338", "scope": "signed_equipment_supply",
         "nmck": "3078500.00", "num": "57724646338260000460000",
         "fields": {"contract_number": "060-26-Р", "contract_signed_date": "2026-08-19"},
         "files": [
             ("20261031T113646789391Z-073e8ec9-94170a4d9314d783.bin",
              "94170a4d9314d78307300f410c2e71fc3ee8ab4a3c9ea86633e48d1809b390aa",
              "https://zakupki.gov.ru/epz/contractfz223/card/contract-info.html?reestrNumber=57724646338260000460000",
              ["3 050 000,00", "19.08.2026"]),
             ("20261031T113647169789Z-9e6ddb2e-e887daa8160e963e.bin",
              "e887daa8160e963e2bea1b9664ff5cdd929b87a08510d5bbe1aed70dd0b995b2",
              "https://zakupki.gov.ru/epz/contractfz223/printForm/view.html?reestrNumber=57724646338260000460000",
              ["3 050 000.00", "19.08.2026"])]}
]


def proof(case):
    root = ROOT.resolve(strict=True)
    if root != Path("/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live"):
        raise RuntimeError("Internal APFS required")
    sources = []
    for name, sha, url, quotes in case["files"]:
        relative = Path("captures") / case["cid"].replace(":", "_") / name
        p = (root / relative).resolve(strict=True)
        if root not in p.parents or p.is_symlink() or not 32 <= p.stat().st_size <= 1000000:
            raise ValueError("Unsafe source")
        raw = p.read_bytes()
        receipt = json.loads(Path(str(p) + ".json").read_text())
        if (hashlib.sha256(raw).hexdigest() != sha or receipt["sha256"] != sha
                or receipt["case_id"] != case["cid"] or receipt["source_url"] != url
                or receipt["relative_file"] != relative.as_posix() or receipt["http_status"] != 200):
            raise ValueError("Original SHA/receipt mismatch")
        parser = Text()
        parser.feed(raw.decode("utf8", "replace"))
        text = " ".join(" ".join(parser.parts).replace("\u00a0", " ").split())
        if not all(q in text for q in [case["num"], case["cid"].split(":")[1],
                                       case["fields"]["contract_number"], *quotes]):
            raise ValueError("Original verbatim quote mismatch")
        sources.append({"url": url, "sha256": sha, "excerpt": "; ".join(quotes)})
    return sources


def validate(case, row):
    d = row["data"]
    if (row["id"] != case["cid"] or row["owner"] != "tender-agent"
            or d.get("canonical_id") != case["cid"]
            or d.get("procedure_id") != case["cid"].split(":")[1]
            or d.get("scope") != case["scope"] or d.get("nmck_rub") != case["nmck"]
            or d.get("customer", {}).get("inn") != case["inn"]
            or digest(d) != row["hash"]
            or any(d.get(k) is not None for k in case["fields"])
            or "eis_20261031_contract_enrichment" in row["meta"]):
        raise RuntimeError("CAS identity, old-null or hash conflict")
    if case["cid"] == "223fz:32616181358:lot1" and (
        d.get("contract_registry_number") != case["num"]
        or d.get("contract_registered_price_rub") != "3050000.00"
        or d.get("registered_signed_contract_verified") is not True):
        raise RuntimeError("RETO existing signed contract conflict")


def prepare(case, row, sources):
    d = {**row["data"], **case["fields"]}
    d["evidence"] = [*d.get("evidence", []),
                     *({"url": s["url"], "sha256": s["sha256"],
                            "source_tier": "first_party_eis_registered_contract",
                            "excerpt": s["excerpt"]} for s in sources)]
    h = digest(d)
    meta = {**row["meta"], "source_content_hash": h,
            "eis_20261031_contract_enrichment": {
                "fields": case["fields"], "sources": sources,
                "previous_hash": row["hash"], "previous_revision": row["rev"],
                "signed_supplier_verified": False, "paid_verified": False}}
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
THEN RAISE EXCEPTION 'PQ owner/count mismatch';END IF;END $g$;"""]
    for c, row, sources in items:
        cid = c["cid"]
        d, meta, h = prepare(c, row, sources)
        nulls = " AND ".join(f"(d.data->'{k}') IS NULL" for k in c["fields"])
        sql.extend([
            f"""DO $g$ BEGIN IF (SELECT count(*) FROM dp_records d
JOIN dp_resources r USING(resource_id) WHERE r.collection_id='{COL}'
AND r.external_id='{cid}' AND r.content_hash='{row['hash']}'
AND d.revision={row['rev']} AND {nulls})<>1
THEN RAISE EXCEPTION 'PQ old-null CAS conflict {cid}';END IF;END $g$;""",
            f"""UPDATE dp_records d SET data={js(d)},metadata={js(meta)},
revision=revision+1,updated_at=now() FROM dp_resources r
WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{cid}' AND r.content_hash='{row['hash']}'
AND d.revision={row['rev']} AND {nulls};""",
            f"""UPDATE dp_resources SET content_hash='{h}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{cid}' AND content_hash='{row['hash']}';""",
            f"""DO $g$ BEGIN IF (SELECT count(*) FROM dp_records d
JOIN dp_resources r USING(resource_id) WHERE r.collection_id='{COL}'
AND r.external_id='{cid}' AND r.content_hash='{h}'
AND d.revision={row['rev']+1} AND d.data->>'contract_number'='{c['fields']['contract_number']}'
AND d.metadata->'eis_20261031_contract_enrichment'->'sources'->0->>'sha256'='{sources[0]['sha256']}')<>1
THEN RAISE EXCEPTION 'PQ postwrite CAS mismatch {cid}';END IF;END $g$;""",
        ])
    psql("\n".join([*sql, "COMMIT;"]))
    after = snapshot()
    if before != after:
        raise RuntimeError("Corpus count changed")
    result = []
    for c, row, sources in items:
        actual = get_row(c["cid"])
        _, _, h = prepare(c, row, sources)
        if (actual["hash"] != h or actual["rev"] != row["rev"] + 1
                or any(actual["data"].get(k) != v for k, v in c["fields"].items())):
            raise RuntimeError("Postwrite readback mismatch")
        result.append({"id": c["cid"], "new_fields": c["fields"], "new_hash": h,
                           "source_shas": [s["sha256"] for s in sources]})
    return {"before": before, "after": after, "results": result, "new_verified_fields": 8}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup-manifest", type=Path)
    p.add_argument("--receipt", type=Path)
    args = p.parse_args()
    before = snapshot()
    items = []
    for c in CASES:
        sources = proof(c)
        row = get_row(c["cid"])
        validate(c, row)
        items.append((c, row, sources))
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "before": before,
                              "cases": [{"id": c["cid"], "fields": c["fields"]} for c in CASES]},
                         ensure_ascii=False))
        return
    if not args.backup_manifest or not args.receipt:
        raise RuntimeError("Backup and receipt mandatory")
    gate = subprocess.run([sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
                          capture_output=True, text=True, check=True, timeout=60)
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("Acceptance gate failed")
    backup = verified_backup(args.backup_manifest)
    age = (datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("Fresh verified full backup required")
    result = apply(items, before)
    result["backup_sha256"] = backup["sha256"]
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x", encoding="utf8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

