"""Bounded, resumable Data Platform processing of verified SIBUR OOXML."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import mimetypes
import os
import subprocess
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.research.acquire_sibur_documents import source_refs

COLLECTION = "tender-agent:sibur-public-research"
WORKER = """
import hashlib,json,os,sys
from arvectum_data_client import DataPlatformClient
raw=sys.stdin.buffer.read()
mode,name,mime,sha=sys.argv[1:]
if hashlib.sha256(raw).hexdigest()!=sha:
    raise ValueError("SHA mismatch")
with DataPlatformClient(
    base_url=os.environ["AI_CORP_RAG_DATA_PLATFORM_BASE_URL"],
    api_key=os.environ["AI_CORP_RAG_DATA_PLATFORM_API_KEY"],
    timeout_seconds=25,
) as client:
    collection="tender-agent:sibur-public-research"
    uri="content-sha256://"+sha
    args=dict(collection_id=collection,canonical_uri=uri,title=name,
              filename=name,content=raw,content_type=mime)
    if mode=="extract":
        response=client.process_document(**args,max_chars=200000)
    elif mode=="index":
        owner=client.request_json("GET","/v1/collections/"+collection)
        if owner["owner"]!="tender-agent" or owner["access_policy"]!={"allowed_consumers":["tender-agent"]}:
            raise ValueError("collection policy mismatch")
        response=client.ingest_document_bytes(**args)
    else:
        raise ValueError("unknown mode")
    if response["canonical_uri"]!=uri or response["collection_id"]!=collection:
        raise ValueError("DP provenance mismatch")
    print(json.dumps({"source_sha256":sha,"result":response},ensure_ascii=False))
"""


def originals(snapshot, directory, formats=frozenset({".docx", ".xlsx"})):
    refs = source_refs(snapshot)
    result = {}
    for file in sorted(directory.glob("*.json")):
        if len(file.stem) != 64:
            continue
        row = json.loads(file.read_text())
        if row["status"] != "captured":
            continue
        if row["references"] != refs[row["url"]]:
            raise ValueError("source receipt mismatch")
        sha = row["sha256"]
        f = directory / row["file"]
        if f.is_symlink() or f.name != sha + f.suffix or f.parent != directory:
            raise ValueError("unexpected original path")
        if f.suffix.lower() not in formats:
            continue
        if sha in result and result[sha]["file"] != row["file"]:
            raise ValueError("original identity collision")
        if sha in result:
            result[sha]["references"].extend(row["references"])
        else:
            result[sha] = row
    return result


def verified_bytes(file, sha):
    if file.stat().st_size > 25 * 1024 * 1024:
        raise ValueError("oversized original")
    raw = file.read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha:
        raise ValueError("original hash mismatch")
    if file.suffix == ".pdf":
        if not raw.startswith(b"%PDF-") or b"%%EOF" not in raw[-4096:]:
            raise ValueError("PDF signature or EOF mismatch")
        return raw
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos = z.infolist()
        names = {i.filename for i in infos}
        required = {".docx": "word/document.xml", ".xlsx": "xl/workbook.xml",
                    ".pptx": "ppt/presentation.xml"}.get(file.suffix)
        if required is None:
            raise ValueError("unsupported processing extension")
        if (len(infos) >= 3000 or sum(i.file_size for i in infos) >= 100_000_000
                or required not in names or any(i.flag_bits & 1 for i in infos)):
            raise ValueError("OOXML validation failed")
    return raw


def select_batch(directory, rows, priority, mode, limit, max_chunks):
    extracted = {}
    for f in directory.glob("*.dp-result.json"):
        v = json.loads(f.read_text())
        extracted[v["source_sha256"]] = v["result"]
    indexed = {json.loads(f.read_text())["source_sha256"]
               for f in directory.glob("persistent-pilot-*.json")}
    result = []
    for sha, row in rows.items():
        if mode == "extract":
            if sha in extracted:
                continue
        else:
            prev = extracted.get(sha)
            if (sha in indexed or not prev or prev["extraction_status"] != "extracted"
                    or not 0 < len(prev["chunks"]) <= max_chunks):
                continue
        result.append(row)
    return sorted(result, key=lambda r: (
        not any(v["external_id"] in priority for v in r["references"]),
        len(extracted[r["sha256"]]["chunks"]) if mode == "index" else r["bytes"],
        r["sha256"],
    ))[:limit]


def operate(directory, row, mode):
    sha = row["sha256"]
    f = directory / row["file"]
    out = directory / (f.name + ".dp-result.json" if mode == "extract"
                       else "persistent-pilot-" + sha[:12] + ".json")
    try:
        raw = verified_bytes(f, sha)
        proc = subprocess.run(
            ["docker", "exec", "-i", "arvectum-local-e2e-api-1", "python", "-c", WORKER,
             mode, f.name, mimetypes.guess_type(f.name)[0] or "application/octet-stream", sha],
            input=raw, capture_output=True, timeout=30, check=True,
        )
        data = json.loads(proc.stdout)
        r = data["result"]
        if data["source_sha256"] != sha or r["collection_id"] != COLLECTION:
            raise ValueError("wrong DP receipt")
        if mode == "index" and (r["extraction_status"] != "extracted" or not r["embeddings"]):
            raise ValueError("incomplete index receipt")
        temporary = out.with_suffix(".partial")
        with temporary.open("xb") as stream:
            stream.write(proc.stdout)
            stream.flush()
            os.fsync(stream.fileno())
        if out.exists():
            raise ValueError("receipt already exists")
        temporary.replace(out)
        return sha[:12], r["extraction_status"], len(r["chunks"]) if mode == "extract" else r["chunks"]
    except (OSError, ValueError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        return sha[:12], "review", type(exc).__name__


def require_prewrite(gate, now=None):
    now = now or datetime.now(UTC)
    stamp = datetime.fromisoformat(gate["verified_at_utc"])
    if (stamp.tzinfo is None or not timedelta(0) <= now - stamp <= timedelta(minutes=45)
            or gate.get("status") != "pass"
            or gate.get("postgresql_mutated_by_preflight") is not False
            or gate.get("postgresql", {}).get("database") != "arvectum_data"
            or not gate.get("backup", {}).get("sha256")):
        raise ValueError("fresh canonical prewrite gate required")


def run_extraction_batch(directory, batch):
    """Bound concurrency; cease new requests after a transport failure."""
    width = 1 if any(Path(row["file"]).suffix == ".pdf" for row in batch) else 2
    with ThreadPoolExecutor(max_workers=width) as pool:
        for start in range(0, len(batch), width):
            wave = batch[start:start + width]
            results = list(pool.map(lambda row: operate(directory, row, "extract"), wave))
            for result in results:
                print(*result, flush=True)
            if any(r[1] == "review" and r[2] in {
                "CalledProcessError", "TimeoutExpired"
            } for r in results):
                print("transport failure: stop batch and reconcile", flush=True)
                raise SystemExit(2)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot", required=True, type=Path)
    p.add_argument("--directory", required=True, type=Path)
    p.add_argument("--priority-queue", required=True, type=Path)
    p.add_argument("--mode", choices=["extract", "index"], required=True)
    p.add_argument("--limit", type=int, default=12)
    p.add_argument("--max-chunks", type=int, default=5)
    p.add_argument("--formats", nargs="+", choices=["docx", "xlsx", "pdf", "pptx"],
                   default=["docx", "xlsx"])
    p.add_argument("--prewrite-receipt", type=Path)
    a = p.parse_args()
    os.umask(0o077)
    if not 1 <= a.limit <= 30 or not 1 <= a.max_chunks <= 100:
        raise ValueError("invalid batch")
    if a.mode == "index":
        gate = json.loads(a.prewrite_receipt.read_text()) if a.prewrite_receipt else {}
        require_prewrite(gate)
    priority = {r["external_id"] for r in json.loads(a.priority_queue.read_text()) if r["priority"]}
    rows = originals(a.snapshot, a.directory, frozenset("." + f for f in a.formats))
    batch = select_batch(a.directory, rows, priority, a.mode, a.limit, a.max_chunks)
    if a.mode == "extract":
        run_extraction_batch(a.directory, batch)
    else:
        for row in batch:
            result = operate(a.directory, row, a.mode)
            print(*result, flush=True)
            if result[1] == "review":
                raise SystemExit(2)
    print("planned", len(batch), flush=True)


if __name__ == "__main__":
    main()
