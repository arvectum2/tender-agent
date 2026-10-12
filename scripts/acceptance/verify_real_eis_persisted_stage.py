"""Prove five real EIS originals persist correctly in an *isolated* DP PostgreSQL.

The authorized operator first creates a disposable PostgreSQL/pgvector
instance, runs Data Platform migrations and starts the current Data Platform
API on port 18096. Never run against a production service/database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx


def run(receipt: Path, original_dir: Path, output: Path) -> None:
    base_url = os.environ.get("AI_CORP_RAG_DATA_PLATFORM_BASE_URL", "")
    key = os.environ.get("AI_CORP_RAG_DATA_PLATFORM_API_KEY", "")
    url = urlsplit(base_url)
    if url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"} or url.port != 18096 or not key:
        raise ValueError("Only explicit authenticated loopback disposable DP staging is permitted")

    items = json.loads(receipt.read_text(encoding="utf-8"))["files"]
    if len(items) != 5:
        raise ValueError("Expected the five-file original EIS acceptance corpus")
    names = (
        "01-price_justification.xls",
        "02-contract_draft.doc",
        "03-technical_spec.docx",
        "04-application_requirements.docx",
        "05-control_notice.pdf",
    )
    from arvectum_data.processing.chunking import normalize_text

    identities: list[dict[str, str]] = []
    with httpx.Client(base_url=base_url, headers={"X-Arvectum-Key": key}, timeout=90) as client:
        response = client.post(
            "/v1/collections",
            json={
                "collection_id": "tender:upload:processing",
                "owner": "tdp-isolated-staging",
                "name": "Local original EIS source contract",
                "default_language": "russian",
            },
        )
        assert response.status_code == 200, ("create_collection", response.status_code)

        for item, filename in zip(items, names, strict=True):
            uid = str(item["uid"])
            if len(uid) != 32 or not uid.isalnum():
                raise ValueError("Invalid source UID")
            original = (original_dir / (uid + ".bin")).read_bytes()
            digest = hashlib.sha256(original).hexdigest()
            if digest != item["sha256"]:
                raise ValueError("Original source SHA mismatch")
            ingested = client.post(
                "/v1/ingest/document",
                data={
                    "collection_id": "tender:upload:processing",
                    "canonical_uri": "tender-upload://" + digest,
                    "title": filename,
                },
                files={"file": (filename, original, "application/octet-stream")},
            )
            assert ingested.status_code == 200, ("ingest", ingested.status_code)
            result = ingested.json()
            identities.append({
                "original_sha256": digest,
                "resource_id": result["resource_id"],
                "document_id": result["document_id"],
            })

        exported = client.get(
            "/v1/collections/tender:upload:processing/export",
            params={"include_content": "true", "limit": 20},
        )
        assert exported.status_code == 200, ("export", exported.status_code)
        resources = exported.json()["resources"]
        assert len(resources) == 5, len(resources)
        chunk_count = 0
        for item, identity in zip(items, identities, strict=True):
            resource, = [r for r in resources if r["canonical_uri"] == "tender-upload://" + item["sha256"]]
            assert resource["content_hash"] == item["sha256"]
            assert resource["resource_id"] == identity["resource_id"]
            document, = resource["documents"]
            assert document["document_id"] == identity["document_id"]
            normalized = normalize_text(document["text"])
            for chunk in document["chunks"]:
                start, end = chunk["char_start"], chunk["char_end"]
                assert start >= 0 and end >= start
                assert chunk["text"] == normalized[start:end].strip()
                assert hashlib.sha256(chunk["text"].encode("utf-8")).hexdigest() == chunk["content_hash"]
                chunk_count += 1
        assert chunk_count == 127, chunk_count

    proof = {
        "scope": "EPHEMERAL_NONPRODUCTION_POSTGRESQL_HTTP_SOURCE_PROOF",
        "original_sha256_verified": 5,
        "persisted_resources": 5,
        "persisted_documents": 5,
        "persisted_chunks_verified": chunk_count,
        "source_identities": identities,
        "production_changed": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("DP_PERSISTED_REAL_EIS_ACCEPTANCE_PASS", "5 documents / 127 verified chunks")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--original-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.receipt, args.original_dir, args.output)


if __name__ == "__main__":
    main()
