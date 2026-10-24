"""MI-003: safe supplier portfolio intake and evidence-gated technical retrieval.

Uses Data Platform as the sole source ingestion/index/search API. Does not
assume that a retrieval hit establishes an awarded procurement.
"""

from __future__ import annotations

import hashlib
import ipaddress
import re
from datetime import date
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

from .technical_matching import _matching_terms

FILE_TYPES = {".txt", ".md", ".csv", ".html", ".htm", ".doc", ".docx",
              ".rtf", ".pdf", ".xls", ".xlsx", ".pptx"}
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TEXT_CHARS = 120_000
MAX_SEARCH_RESULTS = 30
DP_TERMINOLOGY_EXPANSION_LIMIT = 5


class PortfolioInputError(ValueError):
    """Supplier portfolio input or scope is malformed."""


class DataPlatformProtocol(Protocol):
    def contract(self) -> dict[str, Any]: ...
    def ensure_collection(self, *, collection_id: str, name: str, owner: str,
                          default_language: str = "russian") -> dict[str, Any]: ...
    def ingest_document(self, *, collection_id: str, canonical_uri: str,
                        title: str, text: str, filename: str,
                        pre_chunked: bool = False) -> dict[str, Any]: ...
    def ingest_document_bytes(self, *, collection_id: str, canonical_uri: str,
                              title: str, content: bytes, filename: str,
                              content_type: str = "application/octet-stream",
                              pre_chunked: bool = False) -> dict[str, Any]: ...
    def ingest_url(self, *, collection_id: str, url: str,
                   title: str | None = None) -> dict[str, Any]: ...
    def search(self, *, query: str, collections: list[str], limit: int,
               mode: str = "hybrid",
               terminology_groups: list[dict[str, Any]] | None = None,
               terminology_expansion_limit: int = 5,
               terminology_version: str | None = None,
               **kwargs: Any) -> list[dict[str, Any]]: ...


def _slug(value: str, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{1,62}", value):
        raise PortfolioInputError(f"{label}: requires 2–63 safe letters/numbers")
    return value


def portfolio_collection(tenant_id: str, run_id: str) -> str:
    """Stable, isolated collection; caller must bind tenant_id to authenticated user."""
    tenant = _slug(tenant_id, "tenant_id")
    run = _slug(run_id, "run_id")
    return f"mi-portfolio-{hashlib.sha256((tenant + '/' + run).encode()).hexdigest()[:24]}"


def _safe_public_website(value: str) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise PortfolioInputError("URL must be <=2048 chars")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise PortfolioInputError("only public HTTPS URL without embedded credentials is allowed")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost"} or host.endswith((".localhost", ".local", ".internal")):
        raise PortfolioInputError("non-public host")
    try:
        host_ip = ipaddress.ip_address(host)
    except ValueError:
        if "." not in host:
            raise PortfolioInputError("public DNS hostname required")
    else:
        if not host_ip.is_global:
            raise PortfolioInputError("non-public IP")
    if parsed.port not in (None, 443):
        raise PortfolioInputError("only default HTTPS port supported")
    return value


def _file(path: Path) -> tuple[str, bytes]:
    # Caller explicitly selects file; no recursive scanning, symlinks or directories.
    if path.is_symlink() or not path.is_file() or path.suffix.lower() not in FILE_TYPES:
        raise PortfolioInputError("unsupported document path or type")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise PortfolioInputError("file exceeds 20 MiB")
    content = path.read_bytes()
    if not content or len(content) > MAX_FILE_BYTES:
        raise PortfolioInputError("empty or oversized file")
    return path.name, content


def ingest_supplier(
    client: DataPlatformProtocol, *,
    tenant_id: str, run_id: str, company_name: str,
    text: str | None = None, urls: list[str] | None = None,
    files: list[Path] | None = None,
) -> dict[str, Any]:
    """Ingest only user-provided supplier materials into isolated DP collection."""
    collection_id = portfolio_collection(tenant_id, run_id)
    if not company_name.strip() or len(company_name) > 200:
        raise PortfolioInputError("company_name required, <=200 chars")
    urls = urls or []
    files = files or []
    if not isinstance(urls, list) or len(urls) > 8 or len(files) > 16:
        raise PortfolioInputError("URL/document count limit exceeded")
    if text is not None and (not isinstance(text, str) or len(text) > MAX_TEXT_CHARS):
        raise PortfolioInputError("portfolio text too large")
    sources: list[tuple[str, Any]] = []
    if text and text.strip():
        sources.append(("text", text))
    for url in urls:
        sources.append(("url", _safe_public_website(url)))
    for path in files:
        sources.append(("file", _file(path)))
    if not sources:
        raise PortfolioInputError("at least one supplier portfolio source is needed")
    # If any input is invalid, reject before creating/updating a remote collection.
    client.ensure_collection(
        collection_id=collection_id,
        name=f"Supplier intake {run_id}",
        owner=f"tender-agent:{_slug(tenant_id, 'tenant_id')}",
    )
    receipts = []
    for index, (kind, value) in enumerate(sources):
        if kind == "text":
            body = value
            receipt = client.ingest_document(
                collection_id=collection_id,
                canonical_uri=f"mi-intake://{collection_id}/text/{index}",
                title=f"Supplier description: {company_name}", text=body,
                filename=f"description-{index}.txt", pre_chunked=False,
            )
            digest = hashlib.sha256(body.encode()).hexdigest()
            item = {"kind": "text", "sha256": digest}
        elif kind == "url":
            receipt = client.ingest_url(collection_id=collection_id, url=value)
            item = {"kind": "url", "url": value}
        else:
            name, data = value
            ext = Path(name).suffix.lower()
            content_type = {
                ".pdf": "application/pdf", ".pptx":
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }.get(ext, "application/octet-stream")
            receipt = client.ingest_document_bytes(
                collection_id=collection_id,
                canonical_uri=f"mi-intake://{collection_id}/upload/{index}/{name}",
                title=name, content=data, filename=name,
                content_type=content_type, pre_chunked=False,
            )
            item = {"kind": "file", "filename": name, "sha256": hashlib.sha256(data).hexdigest()}
        if receipt.get("extraction_status") in {"empty", "failed", "unsupported"}:
            raise PortfolioInputError(
                f"{kind}: Data Platform extraction unavailable or empty; review indexing state"
            )
        receipts.append({
            **item, "collection_id": collection_id,
            "resource_id": receipt.get("resource_id"),
            "document_id": receipt.get("document_id"),
            "extraction_status": receipt.get("extraction_status", "unknown"),
        })
    return {
        "tenant_id": tenant_id, "run_id": run_id, "company_name": company_name,
        "portfolio_collection": collection_id,
        "materials": receipts, "material_count": len(receipts),
        "status": "indexed_unreviewed",
    }


def propose_families(text: str, ontology: dict[str, Any]) -> list[dict[str, Any]]:
    """Supplier text names families, not independently verified capabilities."""
    if len(text) > MAX_TEXT_CHARS:
        raise PortfolioInputError("portfolio description too large")
    by_id: dict[str, dict[str, Any]] = {}
    for statement in re.split(r"[.\n;]+", text):
        if not statement.strip():
            continue
        for hit in _matching_terms(statement, ontology):
            family = hit["family"]
            entry = by_id.setdefault(family, {
                "family": family, "matched_terms": set(),
                "source_excerpts": [], "review_state": "candidate_supplier_capability",
            })
            entry["matched_terms"].update(hit["terms"])
            if len(entry["source_excerpts"]) < 3:
                entry["source_excerpts"].append(statement.strip()[:260])
    return [
        {**row, "matched_terms": sorted(row["matched_terms"])}
        for _, row in sorted(by_id.items())
    ]


def search_demand(
    client: DataPlatformProtocol, *,
    tenant_id: str, source_collections: list[str],
    families: list[str], ontology: dict[str, Any],
    max_candidates: int = MAX_SEARCH_RESULTS,
    authorized_collection_ids: set[str] | None = None,
    reviewed_source_hashes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run DP hybrid queries for evidence candidates only; never merge into MI-001 awards."""
    _slug(tenant_id, "tenant_id")
    if not 1 <= max_candidates <= MAX_SEARCH_RESULTS:
        raise PortfolioInputError("max_candidates must be 1..30")
    if not source_collections or len(source_collections) > 8:
        raise PortfolioInputError("bounded pre-authorized procurement collections required")
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{1,127}", x) for x in source_collections):
        raise PortfolioInputError("invalid source collection identifier")
    if authorized_collection_ids is None or not set(source_collections).issubset(
        authorized_collection_ids
    ):
        raise PortfolioInputError("source collections must be explicitly authorized by caller")
    # The trusted caller must obtain this allowlist from tenant-scoped policy,
    # not from the customer request. DP server also enforces its own auth.
    allowed = {r["id"]: r for r in ontology["families"]}
    if not families or any(f not in allowed for f in families):
        raise PortfolioInputError("must select known technical product families")
    # Old servers may silently ignore unknown JSON fields. Require the
    # advertised DP capability before returning ANY apparently-empty results.
    if not callable(getattr(client, "contract", None)):
        raise PortfolioInputError("Data Platform contract negotiation required")
    contract = client.contract()
    if not isinstance(contract, dict) or "terminology_search_v1" not in contract.get(
        "capabilities", []
    ):
        raise PortfolioInputError(
            "Data Platform server does not advertise terminology_search_v1"
        )
    candidates: dict[tuple[str, str, str], dict[str, Any]] = {}
    queries = []
    for family in sorted(set(families)):
        record = allowed[family]
        aliases = [str(term).strip() for term in record.get("positive", []) if str(term).strip()]
        if not aliases:
            continue
        # Domain ontology remains in MI, but all actual synonym expansion and
        # context-sensitive hit tagging is executed within Data Platform.
        group = {
            "id": family,
            "aliases": aliases[:20],
            "contexts": list(record.get("contexts", []))[:16],
            "exclusions": list(record.get("exclusions", []))[:16],
            "ambiguous_aliases": [
                term for term in record.get("ambiguous_aliases", [])
                if term in aliases
            ][:16],
        }
        query = group["aliases"][0]
        queries.append({
            "family": family, "query": query,
            "expansion_owner": "data_platform",
            "terminology_group": group["id"],
        })
        try:
            hits = client.search(
                query=query, collections=source_collections,
                limit=max_candidates, mode="hybrid",
                terminology_groups=[group],
                terminology_expansion_limit=DP_TERMINOLOGY_EXPANSION_LIMIT,
                terminology_version=str(ontology.get("schema_version", "unknown/0.1")),
                expand_query=False,  # optional model-based expansion remains off
                collapse_by_canonical_uri=False,
            )
        except TypeError as exc:
            if "terminology_" not in str(exc):
                raise
            raise PortfolioInputError(
                "Data Platform Python SDK >=0.4 terminology contract is required"
            ) from exc
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            chunk_id, doc_id, uri = (
                str(hit.get(k) or "").strip()
                for k in ("chunk_id", "document_id", "canonical_uri")
            )
            if not chunk_id or not doc_id or not uri:
                continue
            metadata = hit.get("metadata") or {}
            if not isinstance(metadata, dict):
                metadata = {}
            raw_text = hit.get("text") or hit.get("preview") or ""
            if not isinstance(raw_text, str) or not raw_text.strip():
                continue
            # These terms are resolved by Data Platform's generic retrieval
            # engine and returned as chunk-scoped evidence annotations. MI
            # does not reimplement query expansion or lexical hit matching.
            dp_matches = metadata.get("terminology_matches")
            if not isinstance(dp_matches, list):
                dp_matches = []
            matched = {
                m.get("id"): m
                for m in dp_matches
                if isinstance(m, dict) and isinstance(m.get("id"), str)
            }
            direct = family in matched
            parsed_uri = urlsplit(uri)
            source_url_public = parsed_uri.scheme in ("https", "http") and bool(parsed_uri.hostname)
            # Provenance from DP search chunk is locator; original file hash may
            # be unknown. We cannot upgrade source validity on vector similarity alone.
            source_sha = metadata.get("source_sha256") or metadata.get("content_hash")
            digest_ok = isinstance(source_sha, str) and bool(
                re.fullmatch(r"[0-9a-fA-F]{64}", source_sha)
            )
            trusted_hash = (reviewed_source_hashes or {}).get(uri)
            source_grade = (
                "reviewed_source_manifest" if (
                    source_url_public and digest_ok and trusted_hash == source_sha
                ) else "unverified_index_metadata" if digest_ok and source_url_public
                else "pending_original_source_hash_or_url"
            )
            key = (family, doc_id, chunk_id)
            row = {
                "family": family, "canonical_uri": uri, "document_id": doc_id,
                "chunk_id": chunk_id, "title": str(hit.get("title") or ""),
                "excerpt": raw_text[:400],
                "source_locator": f"document:{doc_id}/chunk:{chunk_id}",
                "source_sha256": source_sha if digest_ok else None,
                "source_grade": source_grade,
                "terminology_version": metadata.get("terminology_version"),
                "matched_terms": matched.get(family, {}).get("terms", []),
                "query_method": "hybrid",
                "classification": (
                    "explicit_technical_candidate" if direct
                    else "semantic_candidate_requires_manual_review"
                ),
                "procurement_verified": False, "award_verified": False,
                "winner": None, "market_value_rub": None,
                "score": float((hit.get("scores") or {}).get("fusion") or 0),
            }
            if key not in candidates or row["score"] > candidates[key]["score"]:
                candidates[key] = row
    return {
        "schema_version": "mi-technical-demand-candidates/0.1",
        "tenant_id": tenant_id, "source_collections": sorted(set(source_collections)),
        "queries": queries,
        "retrieval_count": len(candidates),
        "review_required_count": len(candidates),
        "candidate_hits": sorted(
            candidates.values(), key=lambda r: (-r["score"], r["family"], r["chunk_id"])
        ),
        "contract_and_market_facts_promoted": 0,
        "status": "CANDIDATES_ONLY_NOT_CONTRACT_EVIDENCE",
    }


def validated_role_graph(
    assertions: list[dict[str, Any]], *,
    permitted_project_ids: set[str],
) -> dict[str, Any]:
    """Build project role edges *only* from reviewed primary documents.

    Buyers seen in aggregator cards should be rendered separately as prospects,
    never silently promoted to verified EPC or designer.
    """
    valid_roles = {"beneficiary", "buyer", "designer", "epc_contractor",
                   "supplier", "service_provider", "winning_bidder"}
    if not isinstance(assertions, list):
        raise PortfolioInputError("assertions must be a list")
    edges = []
    quarantine = []
    for index, source in enumerate(assertions):
        if not isinstance(source, dict):
            quarantine.append({"index": index, "reason": "not_mapping"})
            continue
        project = str(source.get("project_id") or "")
        role = str(source.get("role") or "")
        org = source.get("organization") or {}
        proof = source.get("evidence") or {}
        if (
            project not in permitted_project_ids or role not in valid_roles
            or not isinstance(org, dict)
            or not re.fullmatch(r"\d{10}|\d{12}", str(org.get("inn") or ""))
            or not isinstance(proof, dict)
            or proof.get("source_type") not in {"official_protocol", "signed_contract", "primary_project_document"}
            or proof.get("review_state") != "approved"
            or not str(proof.get("reviewer") or "").strip()
            or not str(proof.get("locator") or "").strip()
            or not str(proof.get("excerpt") or "").strip()
            or not str(proof.get("document_sha256") or "").strip()
            or not re.fullmatch(r"[0-9a-fA-F]{64}", str(proof.get("document_sha256")))
            or urlsplit(str(proof.get("url") or "")).scheme != "https"
        ):
            quarantine.append({"index": index, "reason": "insufficient_primary_role_proof"})
            continue
        # A winning bidder is not necessarily an equipment supplier, and EPC
        # status is only inferred from expressly reviewed EPC contract scope.
        if role in {"winning_bidder", "epc_contractor"} and proof["source_type"] not in {
            "official_protocol", "signed_contract"
        }:
            quarantine.append({"index": index, "reason": "winning_role_needs_award_or_contract"})
            continue
        edges.append({
            "project_id": project, "role": role,
            "organization": {"inn": str(org["inn"]), "name": str(org.get("name") or "")},
            "evidence": dict(proof), "confidence": "human_verified_primary",
        })
    unique: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for edge in edges:
        proof = edge["evidence"]
        key = (edge["project_id"], edge["role"], edge["organization"]["inn"],
               str(proof["document_sha256"]))
        unique[key] = edge
    return {
        "schema_version": "mi-project-role-graph/0.1",
        "verified_edges": list(unique.values()),
        "quarantined_assertions": quarantine,
        "unverified_role_count": len(quarantine),
        "role_edges_claimed_from_search_only": 0,
    }


def monthly_coverage(
    *, start: str, end: str,
    sources: list[str], receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Coverage denominators remain null until independently measured."""
    first = date.fromisoformat(start)
    last = date.fromisoformat(end)
    if first > last or not sources:
        raise PortfolioInputError("invalid coverage window")
    statuses = {"not_checked", "failed", "partial", "verified_complete"}
    observed: dict[tuple[str, str], dict[str, Any]] = {}
    for row in receipts:
        key = (str(row.get("source") or ""), str(row.get("month") or ""))
        if not re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", key[1]):
            raise PortfolioInputError("invalid coverage month")
        if key[1] < f"{first.year:04d}-{first.month:02d}" or key[1] > f"{last.year:04d}-{last.month:02d}":
            raise PortfolioInputError("coverage month outside reporting period")
        if key in observed:
            raise PortfolioInputError(f"duplicate coverage receipt {key}")
        if key[0] not in sources or row.get("status") not in statuses:
            raise PortfolioInputError("unrecognized source or coverage status")
        if row["status"] == "verified_complete" and (
            not isinstance(row.get("expected"), int)
            or not isinstance(row.get("observed"), int)
            or row["observed"] < 0 or row["observed"] != row["expected"]
            or not str(row.get("proof_url") or "").startswith("https://")
        ):
            raise PortfolioInputError("completeness must be independently measured")
        observed[key] = row
    years = []
    y,m = first.year, first.month
    while (y, m) <= (last.year, last.month):
        years.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y,m = y+1,1
    grid = []
    for source in sorted(set(sources)):
        for month in years:
            r = observed.get((source, month), {})
            grid.append({
                "source": source, "month": month,
                "status": r.get("status", "not_checked"),
                "expected": r.get("expected"),
                "observed": r.get("observed"),
                "proof_url": r.get("proof_url"),
            })
    return {
        "window_from": start, "window_to": end,
        "coverage_grid": grid,
        "source_month_slots": len(grid),
        "verified_complete_slots": sum(r["status"] == "verified_complete" for r in grid),
        "full_market_census": False,
        "national_tam_rub": None,
    }
