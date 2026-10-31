"""EIS 223-FZ: immutable original and atomic null-only contract enrichment."""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
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

CID = "223fz:32514476448:lot1"
NUM = "50277071467250001900000"
D = "captures/223fz_32514476448_lot1/"
FILES = [
    (
        "20261031T023241356072Z-9e30ff25-8162f01dee6578df.bin",
        "8162f01dee6578dfa1255724dfa2ed93428d937df8b8ffb70d7d108c831ba05b",
        "contract-info",
    ),
    (
        "20261031T023312424406Z-3268fe34-9829cd966e60fa7e.bin",
        "9829cd966e60fa7e924c4b1a23b4dc0315fe7d145318d08c7a614e869b018b5b",
        "contract-subject",
    ),
    (
        "20261031T023313152303Z-1ccb7b9e-61d110b017ac6449.bin",
        "61d110b017ac6449cc1d7a2813f52d9284cb659db0de4b521b676c7cdb2262fe",
        "event-log",
    ),
]
FIELDS = {
    "contract_registered_price_rub": "2922405.35",
    "contract_registry_number": NUM,
    "contract_register_date": "2025-03-26",
    "registered_signed_contract_verified": True,
    "contract_execution_completed": True,
}


class T(HTMLParser):
    def __init__(self):
        super().__init__()
        self.p = []
        self.skip = 0

    def handle_starttag(self, t, a):
        if t in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, t):
        if t in ("script", "style"):
            self.skip -= 1

    def handle_data(self, x):
        if not self.skip and x.strip():
            self.p.append(x.strip())


def proof():
    root = ROOT.resolve(strict=True)
    if root != Path(
        "/Users/master/ArvectumSafe/runtime/market-intelligence/pq-agent-pilot-live"
    ):
        raise ValueError("internal APFS required")
    out = []
    texts = []
    for file, sha, kind in FILES:
        p = (root / D / file).resolve(strict=True)
        if root not in p.parents or p.is_symlink() or p.stat().st_size > 1000000:
            raise ValueError("unsafe source")
        raw = p.read_bytes()
        m = json.loads(Path(str(p) + ".json").read_text())
        url = f"https://zakupki.gov.ru/epz/contractfz223/card/{kind}.html?reestrNumber={NUM}"
        if (
            hashlib.sha256(raw).hexdigest() != sha
            or m["sha256"] != sha
            or m["source_url"] != url
            or m["relative_file"] != D + file
            or m["case_id"] != CID
            or m["http_status"] != 200
        ):
            raise ValueError("source SHA/identity mismatch")
        t = T()
        t.feed(raw.decode("utf-8", errors="replace"))
        s = " ".join(" ".join(t.p).split()).replace("\xa0", " ")
        if NUM not in s or "2 922 405,35" not in s:
            raise ValueError("contract/price absent")
        texts.append(s)
        out.append({"url": url, "sha256": sha})
    if not all(
        x in texts[0]
        for x in (
            "Извещение о закупке № 32514476448",
            "Номер договора РЭС-1.16.7/Д-01408",
            "Дата заключения договора 26.03.2025",
            "Исполнение завершено",
        )
    ):
        raise ValueError("contract identity")
    if "Работы электромонтажные, связанные с установкой приборов" not in texts[1]:
        raise ValueError("EPC scope")
    if (
        "переведен в статус «Исполнение завершено»" not in texts[2]
        or "17.12.2025" not in texts[2]
    ):
        raise ValueError("completion")
    return {
        "sources": out,
        "role": "registered_completed_epc_not_equipment_sale",
        "supplier_verified": False,
        "payment_verified": False,
    }


def validate(r, p):
    d = r.get("data", {})
    if (
        r.get("id") != CID
        or r.get("owner") != "tender-agent"
        or d.get("canonical_id") != CID
        or d.get("procedure_id") != "32514476448"
        or d.get("scope") != "epc"
        or digest(d) != r.get("hash")
        or d.get("reported_contract_total_rub") != "2922405.35"
        or d.get("linked_contract_registry_number") != NUM
        or d.get("reported_contract_date") != "2025-03-26"
        or any(d.get(k) is not None for k in FIELDS)
        or r.get("meta", {}).get("eis_contract_enrichment")
        or not any("32514476448" in x.get("url", "") for x in d.get("evidence", []))
        or len(p["sources"]) != 3
    ):
        raise RuntimeError("CAS/identity/null-only blocked")


def write(r, before, p):
    validate(r, p)
    d = {**r["data"], **FIELDS}
    d["evidence"] = [
        *r["data"]["evidence"],
        *(
            {
                "url": s["url"],
                "sha256": s["sha256"],
                "source_tier": "first_party_eis_contract",
                "excerpt": "Номер договора РЭС-1.16.7/Д-01408",
            }
            for s in p["sources"]
        ),
    ]
    h = digest(d)
    meta = {
        **r["meta"],
        "source_content_hash": h,
        "eis_contract_enrichment": {
            **p,
            "fields": FIELDS,
            "previous_hash": r["hash"],
            "previous_revision": r["rev"],
        },
    }
    nulls = " AND ".join(f"(d.data->'{k}') IS NULL" for k in FIELDS)
    sql = f"""BEGIN ISOLATION LEVEL SERIALIZABLE;
SET LOCAL statement_timeout='55s';SET LOCAL lock_timeout='9s';
SELECT pg_advisory_xact_lock(hashtext('{COL}-delta'));
LOCK TABLE dp_resources,dp_records IN SHARE ROW EXCLUSIVE MODE;
DO $g$ BEGIN IF current_database()<>'arvectum_data'
OR (SELECT owner FROM dp_collections WHERE collection_id='{COL}')<>'tender-agent'
OR (SELECT count(*) FROM dp_resources WHERE collection_id='{COL}')<>{before["rows"]}
OR (SELECT count(DISTINCT external_id) FROM dp_resources WHERE collection_id='{COL}')<>{before["rows"]}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id) WHERE r.collection_id='{COL}')<>{before["rows"]}
OR (SELECT count(*) FROM dp_records d JOIN dp_resources r USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{r["hash"]}'
AND d.revision={r["rev"]} AND {nulls})<>1
THEN RAISE EXCEPTION 'EIS CAS/owner/count mismatch';END IF;END $g$;
UPDATE dp_records d SET data={js(d)},metadata={js(meta)},revision=revision+1,updated_at=now()
FROM dp_resources r WHERE d.resource_id=r.resource_id AND r.collection_id='{COL}'
AND r.external_id='{CID}' AND r.content_hash='{r["hash"]}' AND d.revision={r["rev"]} AND {nulls};
UPDATE dp_resources SET content_hash='{h}',updated_at=now()
WHERE collection_id='{COL}' AND external_id='{CID}' AND content_hash='{r["hash"]}';
DO $g$ BEGIN IF (SELECT count(*) FROM dp_resources r JOIN dp_records d USING(resource_id)
WHERE r.collection_id='{COL}' AND r.external_id='{CID}' AND r.content_hash='{h}'
AND d.revision={r["rev"] + 1} AND d.data->>'contract_registry_number'='{NUM}'
AND d.data->>'contract_registered_price_rub'='2922405.35'
AND d.data->>'registered_signed_contract_verified'='true'
AND d.data->>'contract_execution_completed'='true'
AND d.metadata->'eis_contract_enrichment'->'sources'->0->>'sha256'='{FILES[0][1]}')<>1
THEN RAISE EXCEPTION 'EIS postwrite mismatch';END IF;END $g$;
COMMIT;"""
    psql(sql)
    after = snapshot()
    actual = get_row(CID)
    if (
        before != after
        or actual["hash"] != h
        or actual["rev"] != r["rev"] + 1
        or any(actual["data"].get(k) != v for k, v in FIELDS.items())
    ):
        raise RuntimeError("postwrite readback")
    return {
        "case": CID,
        "before": before,
        "after": after,
        "fields": FIELDS,
        "new_verified_fields": len(FIELDS),
        "new_hash": h,
        "proof": p,
    }


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--apply", action="store_true")
    a.add_argument("--backup-manifest", type=Path)
    a.add_argument("--receipt", type=Path)
    args = a.parse_args()
    p = proof()
    before = snapshot()
    r = get_row(CID)
    validate(r, p)
    if not args.apply:
        print(
            json.dumps(
                {"mode": "dry_run", "case": CID, "before": before, "fields": FIELDS},
                ensure_ascii=False,
            )
        )
        return
    if not args.backup_manifest or not args.receipt:
        raise RuntimeError("backup/receipt mandatory")
    gate = subprocess.run(
        [sys.executable, "-m", "scripts.market_intelligence.verify_internal_runtime"],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    if json.loads(gate.stdout)["status"] != "pass":
        raise RuntimeError("preflight blocked")
    backup = verified_backup(args.backup_manifest)
    age = (
        datetime.now(UTC) - datetime.fromisoformat(backup["created_at_utc"])
    ).total_seconds()
    if backup.get("pg_restore_list_verified") is not True or not 0 <= age <= 1800:
        raise RuntimeError("fresh full backup required")
    result = write(r, before, p)
    result["backup_sha256"] = backup["sha256"]
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
