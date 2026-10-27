"""Materialize versioned PQ research source files; never infer awards."""
import argparse
import hashlib
import json
from pathlib import Path

ADDITIONS = [(8,"udsgroup_archive_2024_2025.json",60),(9,"rosseti_2025_pq_components_epc_delta.json",64),(10,"rosseti_bashkirenergo_2025_26_project_chain_delta.json",68),(11,"besk_joint_kep_rosseti_high_value_2026_delta.json",71),(13,"discovery_2023_2026_v13_delta.json",79),(14,"discovery_2023_2026_v14_delta.json",82),(15,"discovery_2023_2026_v15_delta.json",84),(16,"discovery_2023_2026_v16_delta.json",87),(17,"discovery_2023_2026_v17_delta.json",99),(18,"discovery_2023_2026_v18_delta.json",101)]

def materialize(root: Path) -> dict:
    rows = {}
    hashes = {}
    def read(name):
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("Missing required source: " + name)
        raw = path.read_bytes()
        hashes[name] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)
    def add(records, name):
        for record in records:
            row = dict(record)
            key = row.get("canonical_id") or row.get("id")
            if not key or key in rows:
                raise ValueError("Duplicate/missing ID in " + name + ": " + str(key))
            row["canonical_id"] = key
            row.setdefault("procedure_id", row.get("notice"))
            row.setdefault("publication_date", row.get("published"))
            row.setdefault("family", row.get("category"))
            row["source_record_files"] = [name]
            rows[key] = row
    base = "verified_public_leads_20261027.v7.json"
    add(read(base)["records"], base)
    if len(rows) != 58: raise ValueError("Wrong base count")
    for ver, name, count in ADDITIONS:
        add(read(name)["records"], name)
        if len(rows) != count:
            raise ValueError(f"Wrong v{ver} count {len(rows)}, expected {count}")
    def patch(name, entries):
        for item in entries:
            key = item["canonical_id"]
            if key not in rows: raise ValueError("Missing patch target: " + key)
            row = rows[key]
            for field, value in item.get("fields", {}).items():
                if field in ("canonical_id", "procedure_id") and row.get(field) != value:
                    raise ValueError("Identity override")
                row[field] = value
            row.setdefault("evidence", []).extend(item.get("evidence_append", []) or item.get("source_evidence", []))
            row["source_record_files"].append(name)
    patch("primary_archive_enrichment_v12.json",read("primary_archive_enrichment_v12.json")["patches"])
    corrected = read("source_corrections_20261027.v19.json")
    for removed in corrected["remove"]:
        key = removed["canonical_id"]
        if key not in rows: raise ValueError("Missing removal")
        del rows[key]
    if len(rows) != 100: raise ValueError("Wrong v19 count")
    patch("source_corrections_20261027.v19.json", corrected["enrich"])
    patch("original_protocol_participant_enrichment_20261027.v20.json",read("original_protocol_participant_enrichment_20261027.v20.json")["patches"])
    manifest = read("verified_public_leads_20261027.v20.manifest.json")
    if len(rows) != manifest["total_active_rows"]: raise ValueError("Wrong final count")
    return {"schema_version":"pq-research-leads/v20", "records":list(rows.values()),"record_count":len(rows),"source_sha256":hashes,"market_census_complete":False}
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-dir",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args = ap.parse_args()
    result = materialize(args.source_dir)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({"records":result["record_count"],"inputs":len(result["source_sha256"])}))
if __name__ == "__main__": main()
