"""Offline source-observation bridge to existing Procurement LLM candidate importer.

No SQL here. Dry-run by default. Optional 0600 private manual JSON can be
validated by scripts.procurement_llm.import_candidates (also dry-run by default).
Unreviewed source *metadata* is not LLM training labels or validated legal gold.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from scripts.procurement_llm.import_candidates import _manual_payload_items
from src.modules.procurement_learning_corpus.service import validate_candidate

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "docs/roadmap"
EIS_FILE = DOCS / "b2b_oct18_three_new_eis_originals.json"
B2B_SIX_FILE = DOCS / "b2bcenter_six_primary_oct18.json"
B2B_ONE_FILE = DOCS / "b2b_oct18_b2bcenter_4643484_firstparty.json"
PRIVATE_ROOT = Path("/Volumes/ArvectumSSD/Arvectum/private/tender-agent/pending-manual-evidence")
HEX = re.compile(r"[a-f0-9]{64}\Z")
EIS_ID = re.compile(r"\d{19}\Z")
WORKSPACE_ID = re.compile(r"workspace-(\d{4,6})\Z")
B2B_ID = re.compile(r"\d{7}\Z")
MAX_RECEIPT = 280_000


class ResearchIntakeError(ValueError):
    """Unverified or ambiguous original provenance: never create training facts."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read(path: Path) -> tuple[dict, str]:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size < MAX_RECEIPT:
        raise ResearchIntakeError("missing, symlink or oversized source receipt")
    raw = path.read_bytes()

    def unique_keys(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ResearchIntakeError("duplicate source JSON key")
            result[key] = value
        return result

    data = json.loads(raw, object_pairs_hook=unique_keys)
    if not isinstance(data, dict):
        raise ResearchIntakeError("source receipt not JSON object")
    return data, _sha(raw)


def _bool_false(record: dict, field: str) -> None:
    if record.get(field) is not False:
        raise ResearchIntakeError("unsafe/missing no-bid proof: " + field)


def _digest(value: object, key: str) -> str:
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise ResearchIntakeError("missing/invalid source SHA: " + key)
    return value


def _utc(value: object) -> str:
    if not isinstance(value, str):
        raise ResearchIntakeError("missing source observation time")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ResearchIntakeError("source UTC time not offset-aware")
    return dt.isoformat()


def _public_url(value: object, platform: str, code: str) -> str:
    if not isinstance(value, str):
        raise ResearchIntakeError("no original URL")
    parsed = urlsplit(value)
    host = {"workspace": "workspace.ru", "b2bcenter": "www.b2b-center.ru"}[platform]
    if (
        parsed.scheme != "https"
        or parsed.netloc != host
        or parsed.username or parsed.password
        or parsed.query or parsed.fragment
        or len(value) > 320
    ):
        raise ResearchIntakeError("private or wrong-domain source URL")
    if platform == "workspace":
        if not re.fullmatch(r"/tenders/[a-z0-9-]+-" + re.escape(code) + r"/", parsed.path):
            raise ResearchIntakeError("wrong Workspace original ID")
    elif not re.fullmatch(
        r"/(?:app/market-next|market)/[a-z0-9-]+/tender-" + re.escape(code) + r"/",
        parsed.path,
    ):
        raise ResearchIntakeError("wrong B2B-Center source original ID")
    return value


def _original_candidate(
    *, platform: str, ref: str, source_sha: str, receipt_sha: str,
    receipt_ref: str, time: str, evidence_gate: str, public_url: str | None,
    archival_version: int | None = None, additional: dict | None = None,
) -> dict:
    # Anchored to original source SHA + frozen research receipt SHA. Exact
    # replay idempotent; fresh source observation is append-only, even when
    # the external procurement ID and source bytes remain unchanged.
    seed = f"{platform}:{ref}:{source_sha}:{receipt_sha}"
    event_id = "ta-research:" + platform + ":" + ref + ":" + _sha(seed.encode())[:24]
    event = {
        "event_id": event_id,
        "procurement_ref": ref if platform == "eis" else platform + ":" + ref,
        "participation": "reviewed_only",
        "review_state": "source_documented",
        "source_role": "development_exposed",
        "origin": "read_only_firstparty_research_metadata",
        "source_platform": platform,
        "source_original_sha256": source_sha,
        "source_receipt_sha256": receipt_sha,
        "source_receipt_git_path": receipt_ref,
        "source_observed_at": _utc(time),
        "source_gate": evidence_gate,
        "current_legal_stage_verified": False,
        "company_bid_eligibility_verified": False,
        "owner_bid_go": False,
        "training_labels": "NOT_REVIEWED",
        "source_payload_is_only_metadata": True,
        "raw_document_bytes_copied": False,
        "model_output": None,
        "human_verified_interpretation": False,
        "blind_holdout": False,
    }
    if public_url:
        event["original_public_url"] = public_url
    if archival_version is not None:
        event["archived_notice_version"] = archival_version
    if additional:
        event.update(additional)
    # Validate against EXISTING canonical importer schema, no private DB.
    validate_candidate(_manual_payload_items({"schema": "manual-candidate-import-v1", "items": [event]})[0])
    return event


def build(
    *,
    workspace: tuple[dict, str] | None,
    eis: tuple[dict, str],
    b2b_six: tuple[dict, str],
    b2b_one: tuple[dict, str],
) -> dict:
    events = []
    stats = {"workspace": 0, "eis": 0, "b2bcenter": 0}
    if workspace is not None:
        j, receipt_sha = workspace
        if (j.get("contract_version") != "b2b_workspace_firstparty_public_originals_v1"
                or j.get("firstparty_http200_cards_parsed") != 21
                or len(j.get("items", [])) != 21
                or j.get("strict_owner_qualified_bid_opportunities") != 0):
            raise ResearchIntakeError("unverified Workspace receipt")
        for r in j["items"]:
            found = WORKSPACE_ID.fullmatch(r.get("id", ""))
            if not found or r.get("source_http_status") != 200:
                raise ResearchIntakeError("Workspace original identifier/status not proven")
            _bool_false(r, "authenticated_legal_entity_bidder_verified")
            _bool_false(r, "commercial_go")
            _bool_false(r, "external_actions_taken")
            if r.get("source_gate") not in {
                "PUBLIC_CORPORATE_CANDIDATE_ONLY",
                "EXCLUDE_PRIVATE_BUYER",
                "EXCLUDE_TERMINAL_PLATFORM_STATUS",
            }:
                raise ResearchIntakeError("unknown Workspace original source gate")
            _digest(r.get("source_html_sha256"), "workspace_original_html")
            _public_url(r.get("source_url"), "workspace", found.group(1))
            events.append(_original_candidate(
                platform="workspace", ref=found.group(1),
                source_sha=r["source_html_sha256"], receipt_sha=receipt_sha,
                receipt_ref="PR483:docs/roadmap/b2b_workspace_original_current_2026-10-18.json",
                time=r["observed_at_utc"], evidence_gate=r["source_gate"],
                public_url=r["source_url"],
                additional={"public_status": r.get("platform_status", "UNKNOWN"),
                            "public_corporate_source_candidate": r.get("public_corporate_candidate") is True},
            ))
            stats["workspace"] += 1
    j, receipt_sha = eis
    if (j.get("schema_version") != "b2b-firstparty-44fz-new-original-20261018-v1"
            or len(j.get("records", [])) != 3
            or j.get("owner_bid_ready_count") != 0
            or j.get("current_legal_status_verified") is not False):
        raise ResearchIntakeError("unverified archival official original receipt")
    for r in j["records"]:
        if not EIS_ID.fullmatch(r.get("number", "")) or r.get("archival_evidence") != "SHA_VERIFIED_NOTICE":
            raise ResearchIntakeError("not official verified EIS source")
        _bool_false(r, "current_live_legal_status_verified")
        _bool_false(r, "owner_qualified")
        _bool_false(r, "bid_ready")
        _bool_false(r, "etp_actions_executed")
        _digest(r.get("zip_sha256"), "zip")
        _digest(r.get("original_xml_sha256"), "xml")
        events.append(_original_candidate(
            platform="eis", ref=r["number"], source_sha=r["original_xml_sha256"],
            receipt_sha=receipt_sha, receipt_ref="docs/roadmap/b2b_oct18_three_new_eis_originals.json",
            time=r["observed_at_utc"], evidence_gate="ARCHIVED_ORIGINAL_NOT_LIVE_STATUS",
            public_url=None, archival_version=r["selected_archived_version"],
            additional={"official_original_zip_sha256": r["zip_sha256"]},
        ))
        stats["eis"] += 1
    j, receipt_sha = b2b_six
    if (j.get("contract_version") != "b2b_center_six_original_oct18_v1"
            or len(j.get("items", [])) != 6
            or j.get("strictly_qualified_current_company_bid_count") != 0):
        raise ResearchIntakeError("unverified B2B six receipt")
    for r in j["items"]:
        code = r.get("id")
        if not isinstance(code, str) or not B2B_ID.fullmatch(code):
            raise ResearchIntakeError("invalid original B2B ID")
        if r.get("original_http_status") != 200:
            raise ResearchIntakeError("not a direct 200 source")
        _bool_false(r, "bidder_legal_eligibility_verified")
        _bool_false(r, "owner_bid_go")
        _bool_false(r, "external_actions_taken")
        if r.get("source_gate") not in {
            "RFI_MARKET_RESEARCH_NOT_CONTRACT_AWARD",
            "EXCLUDE_LICENSE_RESALE_NOT_SOFTWARE_DEVELOPMENT",
            "EXCLUDE_PAST_OR_NONACCEPTING_PUBLIC_DEADLINE",
            "SOURCE_IDENTITY_OR_STAGE_REQUIRES_REVIEW",
            "TECHNICAL_FIT_AND_OWNER_ELIGIBILITY_REVIEW",
        }:
            raise ResearchIntakeError("unknown B2B original source gate")
        _digest(r.get("detail_html_sha256"), "b2b_html")
        url = _public_url(r.get("exact_original_card_url"), "b2bcenter", code)
        events.append(_original_candidate(
            platform="b2bcenter", ref=code, source_sha=r["detail_html_sha256"],
            receipt_sha=receipt_sha, receipt_ref="docs/roadmap/b2bcenter_six_primary_oct18.json",
            time=r["observed_at_utc"], evidence_gate=r["source_gate"],
            public_url=url,
            additional={"source_identity_parse_state": r.get("source_parse_state", "UNVERIFIED"),
                        "index_original_id": r.get("index_displayed_purchase_number"),
                        "original_source_has_a_legal_bid_right": False},
        ))
        stats["b2bcenter"] += 1
    j, receipt_sha = b2b_one
    if j.get("contract_version") != "b2bcenter_4643484_first_party_readonly_v1":
        raise ResearchIntakeError("unverified B2B original case 4643484")
    if j.get("registry_number") != "4643484":
        raise ResearchIntakeError("different primary B2B procurement ID")
    _bool_false(j, "buyer_go_or_bid_ready")
    url = _public_url(j.get("exact_platform_detail_url"), "b2bcenter", "4643484")
    source_sha = _digest(j.get("detail_html_sha256"), "b2b4643484_html")
    events.append(_original_candidate(
        platform="b2bcenter", ref="4643484", source_sha=source_sha,
        receipt_sha=receipt_sha,
        receipt_ref="docs/roadmap/b2b_oct18_b2bcenter_4643484_firstparty.json",
        time=j["observed_at_utc"], evidence_gate="FIRST_PARTY_PUBLIC_CARD_NOT_ELIGIBILITY",
        public_url=url,
    ))
    stats["b2bcenter"] += 1
    event_ids = [e["event_id"] for e in events]
    if len(event_ids) != len(set(event_ids)):
        raise ResearchIntakeError("duplicate source observation ID / original source")
    if len({e["procurement_ref"] for e in events}) != len(events):
        raise ResearchIntakeError("duplicate procurement ref in bounded snapshot")
    batch = {"schema": "manual-candidate-import-v1", "items": events}
    # Uses exact same pre-existing service + manual importer checks.
    checked = _manual_payload_items(batch)
    if len(checked) != len(events):
        raise ResearchIntakeError("not a one-to-one canonical intake")
    return {"batch": batch, "stats": stats, "total": len(events)}


def _private_write(path: Path, body: str) -> None:
    root = PRIVATE_ROOT.resolve()
    if path.is_symlink() or path.resolve().parent != root or not path.name.endswith(".json"):
        raise ResearchIntakeError("only canonical private existing intake directory supported")
    if not root.is_dir() or root.is_symlink():
        raise ResearchIntakeError("canonical private directory missing; no auto-create")
    if path.exists():
        if path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise ResearchIntakeError("existing private artifact too permissive")
        if path.read_text(encoding="utf8") != body:
            raise ResearchIntakeError("refusing to overwrite prior immutable candidate batch")
        return
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf8") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace-receipt", type=Path, help="Verified PR483 original JSON file in private staging")
    p.add_argument("--write-private", type=Path, help="Write existing canonical private staging folder, never DB")
    args = p.parse_args()
    result = build(
        workspace=_read(args.workspace_receipt) if args.workspace_receipt else None,
        eis=_read(EIS_FILE),
        b2b_six=_read(B2B_SIX_FILE),
        b2b_one=_read(B2B_ONE_FILE),
    )
    if args.write_private:
        _private_write(args.write_private, json.dumps(result["batch"], ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "mode": "private_pending_import" if args.write_private else "offline_dry_run",
        "total_source_metadata_candidates": result["total"],
        "source_types": result["stats"],
        "db_mutations": 0,
        "training_promotions": 0,
        "source_document_truth_or_bid_go_promotions": 0,
        "existing_canonical_importer": "scripts.procurement_llm.import_candidates",
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
