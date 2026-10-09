"""APR-06 evidence-first commercial acceptance; fail closed on missing review.

No HTTP calls, no decisions, no automatic submission: consumes frozen references,
operator-reviewed observations and writes deterministic, auditable artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from urllib.parse import urlsplit

NOTICES = {"44fz": re.compile(r"\d{19}\Z"), "223fz": re.compile(r"\d{11}\Z")}
DECISIONS = {"GO", "NO_GO", "DEFER"}
METRICS = (
    "time_to_decision_minutes_p90",
    "manual_correction_rate",
    "citation_coverage",
    "unknown_rate",
    "missed_blockers",
    "false_go_no_go",
    "application_package_rework",
)
ALLOWED_SOURCES = {
    "zakupki.gov.ru", "zakupki.kontur.ru", "b2b-center.ru",
    "www.b2b-center.ru", "synapsenet.ru",
}
HASH_PATTERN = re.compile(r"[a-f0-9]{64}\Z")
TIMESTAMP_PATTERN = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)\Z")


class AcceptanceError(ValueError):
    pass


def _error(message: str) -> None:
    raise AcceptanceError(message)


def _required(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _error(f"{label}: nonempty text required")
    return value.strip()


def _time(raw: object, label: str) -> datetime:
    value = _required(raw, label)
    if not TIMESTAMP_PATTERN.fullmatch(value):
        _error(f"{label}: offset-aware ISO timestamp required")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AcceptanceError(f"{label}: invalid timestamp") from exc
    if result.tzinfo is None:
        _error(f"{label}: timezone required")
    return result.astimezone(timezone.utc)


def _hash(raw: object, label: str) -> str:
    value = _required(raw, label)
    if not HASH_PATTERN.fullmatch(value):
        _error(f"{label}: lowercase SHA-256 required")
    return value


def canonical(obj: object) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(obj: object) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def load_json(path: Path) -> dict:
    if not path.is_file() or path.is_symlink():
        _error(f"Missing or symlinked JSON file: {path}")
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise AcceptanceError(f"Invalid JSON: {path}") from exc
    if not isinstance(obj, dict):
        _error(f"Expected JSON object: {path}")
    return obj


def _source(url: object, label: str) -> str:
    value = _required(url, label)
    parts = urlsplit(value)
    if parts.scheme != "https" or parts.hostname not in ALLOWED_SOURCES or parts.username or parts.password:
        _error(f"{label}: HTTPS approved provenance host required")
    if len(value) > 2000:
        _error(f"{label}: URL too long")
    return value


def validate_manifest(manifest: dict, *, require_frozen: bool = False) -> dict:
    if manifest.get("schema_version") != "apr06-corpus-v1":
        _error("schema_version must be apr06-corpus-v1")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not 20 <= len(cases) <= 30:
        _error("APR-06 requires exactly 20-30 procurement cases")
    ids: set[str] = set()
    laws: Counter = Counter()
    for pos, case in enumerate(cases):
        if not isinstance(case, dict):
            _error(f"cases[{pos}] must be an object")
        case_id = _required(case.get("reg_number"), f"cases[{pos}].reg_number")
        law = case.get("law")
        if law not in NOTICES or not NOTICES[law].fullmatch(case_id):
            _error(f"{case_id}: invalid EIS registry number for {law}")
        if case_id in ids:
            _error(f"duplicate procurement: {case_id}")
        ids.add(case_id)
        laws[law] += 1
        _source(case.get("listing_source_url"), f"{case_id}.listing_source_url")
        _required(case.get("subject"), f"{case_id}.subject")
        _required(case.get("procedure"), f"{case_id}.procedure")
        verification = case.get("verification")
        if not isinstance(verification, dict):
            _error(f"{case_id}: explicit verification state required")
        state = verification.get("state")
        if state not in {"candidate", "eis_verified"}:
            _error(f"{case_id}: invalid verification state")
        if state == "eis_verified":
            _source(verification.get("eis_source_url"), f"{case_id}.eis_source_url")
            if urlsplit(verification["eis_source_url"]).hostname != "zakupki.gov.ru":
                _error(f"{case_id}: verification requires official EIS source")
            _hash(verification.get("notice_sha256"), f"{case_id}.notice_sha256")
            doc_hashes = verification.get("document_sha256", [])
            if not isinstance(doc_hashes, list) or not doc_hashes:
                _error(f"{case_id}: verified EIS case requires hashed documents")
            for idx, content_hash in enumerate(doc_hashes):
                _hash(content_hash, f"{case_id}.document_sha256[{idx}]")
            _time(verification.get("verified_at"), f"{case_id}.verified_at")
        if require_frozen and state != "eis_verified":
            _error(f"{case_id}: not verified against real EIS documents")
    if laws["44fz"] == 0 or laws["223fz"] == 0:
        _error("Corpus must contain both 44-FZ and 223-FZ")
    frozen = manifest.get("freeze")
    if require_frozen:
        if not isinstance(frozen, dict) or frozen.get("state") != "frozen":
            _error("Explicit frozen corpus required")
        claimed = _hash(frozen.get("manifest_sha256"), "freeze.manifest_sha256")
        immutable = {key: value for key, value in manifest.items() if key != "freeze"}
        if sha256(immutable) != claimed:
            _error("Frozen manifest digest does not match its cases and metadata")
        _time(frozen.get("frozen_at"), "freeze.frozen_at")
    return {"count": len(cases), "laws": dict(laws),
            "verified": sum(c["verification"]["state"] == "eis_verified" for c in cases)}


def freeze_manifest(manifest: dict, *, frozen_at: str) -> dict:
    validate_manifest(manifest)
    if "freeze" in manifest:
        _error("Cannot re-freeze an existing manifest; preserve history")
    for case in manifest["cases"]:
        if case["verification"]["state"] != "eis_verified":
            _error("Cannot freeze candidate-only procurement cases")
    _time(frozen_at, "frozen_at")
    locked = dict(manifest)
    locked["freeze"] = {
        "state": "frozen", "frozen_at": frozen_at,
        "manifest_sha256": sha256(manifest),
    }
    validate_manifest(locked, require_frozen=True)
    return locked


def thresholds_valid(policy: dict) -> dict:
    if policy.get("schema_version") != "apr06-thresholds-v1":
        _error("threshold policy schema_version mismatch")
    vals = policy.get("limits")
    if not isinstance(vals, dict) or set(vals) != set(METRICS):
        _error("Threshold policy must explicitly define all seven metrics")
    for name, val in vals.items():
        if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(val) or val < 0:
            _error(f"{name}: invalid threshold")
    if vals["citation_coverage"] > 1 or vals["unknown_rate"] > 1 or vals["manual_correction_rate"] > 1 or vals["false_go_no_go"] > 1 or vals["application_package_rework"] > 1:
        _error("Rates must be within 0..1")
    approval = policy.get("approval")
    if not isinstance(approval, dict) or approval.get("state") not in {"proposed", "approved"}:
        _error("Thresholds need explicit proposed or approved state")
    if approval["state"] == "approved":
        _required(approval.get("approver"), "approval.approver")
        _time(approval.get("approved_at"), "approval.approved_at")
        _required(approval.get("decision_reference"), "approval.decision_reference")
    return vals


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator > 0 else None


def _p90(values: list[float]) -> float | None:
    if not values:
        return None
    values.sort()
    return round(values[math.ceil(len(values) * .9) - 1], 4)


def _positive_int(item: dict, name: str, *, zero: bool = True) -> int:
    value = item.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < (0 if zero else 1):
        _error(f"{name}: nonnegative integer required")
    return value


def evaluate_observation(case: dict, obj: dict) -> dict:
    reg = case["reg_number"]
    if obj.get("schema_version") != "apr06-observation-v1" or obj.get("reg_number") != reg:
        _error(f"{reg}: observation schema or procurement identity mismatch")
    _hash(obj.get("source_manifest_sha256"), f"{reg}.source_manifest_sha256")
    if obj["source_manifest_sha256"] != case["verification"]["notice_sha256"]:
        _error(f"{reg}: observation not bound to frozen EIS notice hash")
    if obj.get("law") != case["law"]:
        _error(f"{reg}: observed law mismatch")
    if obj.get("workflow_status") != "completed_with_human_review":
        _error(f"{reg}: full workflow and human review not complete")
    _required(obj.get("run_id"), f"{reg}.run_id")
    reviewer = obj.get("operator_review")
    if not isinstance(reviewer, dict):
        _error(f"{reg}: attributed operator review missing")
    reviewer_id = _required(reviewer.get("reviewer_id"), f"{reg}.reviewer_id")
    review_ref = _required(reviewer.get("evidence_ref"), f"{reg}.review_ref")
    decision = reviewer.get("decision")
    if decision not in DECISIONS:
        _error(f"{reg}: human decision must be GO/NO_GO/DEFER")
    started = _time(obj.get("started_at"), f"{reg}.started_at")
    decided = _time(reviewer.get("decided_at"), f"{reg}.decided_at")
    if decided <= started or (decided - started).total_seconds() > 7 * 24 * 3600:
        _error(f"{reg}: unsupported time-to-decision")
    report_decision = obj.get("suggested_decision")
    if report_decision not in DECISIONS | {"UNKNOWN"}:
        _error(f"{reg}: suggested decision invalid")
    _required(obj.get("analysis_evidence_ref"), f"{reg}.analysis_evidence_ref")
    claims = obj.get("claims")
    if not isinstance(claims, list) or not claims:
        _error(f"{reg}: no report claims to verify")
    cited = 0
    for idx, claim in enumerate(claims):
        if not isinstance(claim, dict):
            _error(f"{reg}: claims[{idx}] invalid")
        _required(claim.get("claim_id"), f"{reg}.claim_id")
        if type(claim.get("citation_verified")) is not bool:
            _error(f"{reg}: verified citation marker missing")
        if claim["citation_verified"]:
            _required(claim.get("source_ref"), f"{reg}.citation_ref")
            cited += 1
    fields = _positive_int(obj, "reviewed_fields", zero=False)
    corrections = _positive_int(obj, "corrected_fields")
    unknown = _positive_int(obj, "unsupported_facts")
    required = _positive_int(obj, "required_facts", zero=False)
    if corrections > fields or unknown > required:
        _error(f"{reg}: impossible denominator")
    expected = obj.get("human_confirmed_blockers")
    surfaced = obj.get("reported_blockers")
    if not isinstance(expected, list) or not isinstance(surfaced, list):
        _error(f"{reg}: explicit human/AI blocker lists required")
    if any(not isinstance(x, str) or not x.strip() for x in expected + surfaced):
        _error(f"{reg}: invalid blocker ID")
    if len(set(expected)) != len(expected) or len(set(surfaced)) != len(surfaced):
        _error(f"{reg}: duplicate blockers")
    package = obj.get("application_package")
    if not isinstance(package, dict) or type(package.get("reviewed")) is not bool or type(package.get("required_rework")) is not bool:
        _error(f"{reg}: explicit package review/rework state required")
    confirmed = obj.get("confirmed_defects")
    if not isinstance(confirmed, list):
        _error(f"{reg}: explicit confirmed defects inventory required")
    found = []
    for idx, defect in enumerate(confirmed):
        if not isinstance(defect, dict):
            _error(f"{reg}: confirmed_defects[{idx}] invalid")
        identifier = _required(defect.get("defect_id"), "defect_id")
        source_ref = _required(defect.get("source_ref"), "defect source_ref")
        summary = _required(defect.get("summary"), "defect summary")
        found.append({"reg_number": reg, "defect_id": identifier,
                      "source_ref": source_ref, "summary": summary,
                      "reviewer_id": reviewer_id, "review_ref": review_ref})
    missed = sorted(set(expected) - set(surfaced))
    if missed:
        defect_keys = {x["defect_id"] for x in found}
        if any(f"missed_blocker:{key}" not in defect_keys for key in missed):
            _error(f"{reg}: all human-confirmed missed blockers need regressions")
    false_decision = int(
        (report_decision == "GO" and decision == "NO_GO")
        or (report_decision == "NO_GO" and decision == "GO")
    )
    return {
        "reg_number": reg, "run_id": obj["run_id"],
        "time_minutes": (decided - started).total_seconds() / 60,
        "claims_total": len(claims), "claims_cited": cited,
        "reviewed_fields": fields, "corrected_fields": corrections,
        "required_facts": required, "unsupported_facts": unknown,
        "blockers_missed": len(missed), "false_go_no_go": false_decision,
        "decision_comparison_count": int(report_decision in {"GO", "NO_GO"}),
        "package_reviewed": int(package["reviewed"]),
        "package_reworked": int(package["reviewed"] and package["required_rework"]),
        "regressions": found,
    }


def score(manifest: dict, observations: dict[str, dict], thresholds: dict) -> dict:
    info = validate_manifest(manifest, require_frozen=True)
    limits = thresholds_valid(thresholds)
    case_map = {item["reg_number"]: item for item in manifest["cases"]}
    if set(observations) - set(case_map):
        _error("Unexpected case observations outside frozen corpus")
    ready: list[dict] = []
    blocked: list[dict] = []
    runs: set[str] = set()
    for case in manifest["cases"]:
        reg = case["reg_number"]
        if reg not in observations:
            blocked.append({"reg_number": reg, "reason": "missing_observation"})
            continue
        try:
            item = evaluate_observation(case, observations[reg])
        except AcceptanceError as exc:
            blocked.append({"reg_number": reg, "reason": str(exc)})
            continue
        if item["run_id"] in runs:
            blocked.append({"reg_number": reg, "reason": "duplicate_tender_run"})
            continue
        runs.add(item["run_id"])
        ready.append(item)
    sums = lambda key: sum(row[key] for row in ready)
    metrics = {
        "time_to_decision_minutes_p90": _p90([r["time_minutes"] for r in ready]),
        "manual_correction_rate": _rate(sums("corrected_fields"), sums("reviewed_fields")),
        "citation_coverage": _rate(sums("claims_cited"), sums("claims_total")),
        "unknown_rate": _rate(sums("unsupported_facts"), sums("required_facts")),
        "missed_blockers": sums("blockers_missed"),
        "false_go_no_go": _rate(sums("false_go_no_go"), sums("decision_comparison_count")),
        "application_package_rework": _rate(sums("package_reworked"), sums("package_reviewed")),
    }
    comparisons = {
        key: None if val is None else (val >= limits[key] if key == "citation_coverage" else val <= limits[key])
        for key, val in metrics.items()
    }
    regression_list = [d for row in ready for d in row["regressions"]]
    fingerprints = set()
    for defect in regression_list:
        key = (defect["reg_number"], defect["defect_id"])
        if key in fingerprints:
            _error(f"Duplicate regression {key}")
        fingerprints.add(key)
    full = len(ready) == info["count"] and not blocked and all(v is not None for v in metrics.values())
    thresholds_approved = thresholds["approval"]["state"] == "approved"
    meets = all(x is True for x in comparisons.values())
    if not full:
        status = "INSUFFICIENT_REVIEW_EVIDENCE"
    elif not thresholds_approved:
        status = "PENDING_OWNER_THRESHOLD_APPROVAL"
    else:
        status = "ACCEPTED" if meets else "FAILED_ACCEPTANCE"
    return {
        "schema_version": "apr06-report-v1",
        "corpus_manifest_sha256": manifest["freeze"]["manifest_sha256"],
        "corpus_size": info["count"],
        "eligible_count": len(ready),
        "unreviewed_or_invalid": blocked,
        "metrics": metrics,
        "threshold_limits": limits,
        "threshold_checks": comparisons,
        "thresholds_approved": thresholds_approved,
        "status": status,
        "operator_verified_cases": len(ready),
        "confirmed_regressions": regression_list,
        "regressions_total": len(regression_list),
        "no_automatic_bid_or_payment": True,
        "methodology": "Full human review required; failed/missing artifacts never count as passes",
    }


def _new_file(path: Path, obj: dict) -> None:
    """Atomic create-no-overwrite: freeze/report history is append-only."""
    if path.exists() or path.is_symlink():
        _error(f"Output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    import os
    import tempfile

    fd, name = tempfile.mkstemp(prefix=".apr06-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(obj, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
        os.link(name, path)
    except FileExistsError as exc:
        raise AcceptanceError(f"Output appeared concurrently: {path}") from exc
    finally:
        Path(name).unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="APR-06 fail-closed commercial acceptance")
    parser.add_argument("command", choices=["validate", "freeze", "score"])
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--thresholds", type=Path)
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--frozen-at", type=str)
    args = parser.parse_args(argv)
    try:
        manifest = load_json(args.manifest)
        if args.command == "validate":
            result = validate_manifest(manifest)
        elif args.command == "freeze":
            if not args.output or not args.frozen_at:
                _error("freeze needs --output and --frozen-at")
            result = freeze_manifest(manifest, frozen_at=args.frozen_at)
            _new_file(args.output, result)
        else:
            if not args.thresholds or not args.observations or not args.output:
                _error("score needs --thresholds --observations --output")
            if not args.observations.is_dir() or args.observations.is_symlink():
                _error("Observations directory not present or symlinked")
            cases = {case["reg_number"] for case in manifest.get("cases", []) if isinstance(case, dict)}
            seen = {}
            for file in sorted(args.observations.glob("*.json")):
                if file.stem not in cases:
                    _error(f"Unknown case file {file.name}")
                seen[file.stem] = load_json(file)
            result = score(manifest, seen, load_json(args.thresholds))
            _new_file(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("status") == "ACCEPTED" or args.command in {"validate", "freeze"} else 2
    except AcceptanceError as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
