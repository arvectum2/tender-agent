"""Frozen R7 canonical-output persistence, independent of a run-root adapter."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class PersistedCanonicalFiles:
    requirements_path: Path
    canonical_report_path: Path
    report_json_path: Path
    report_html_path: Path
    steps_path: Path
    canonical_report: dict[str, Any]


@dataclass(frozen=True)
class PersistedCanonicalOutputs(PersistedCanonicalFiles):
    requirements_bytes: bytes
    canonical_report_bytes: bytes
    source_graph: dict[str, Any]
    source_graph_hash: str
    production_model_hash: str
    report_model_hash: str
    requirements_file_sha256: str
    canonical_report_file_sha256: str


@dataclass(frozen=True)
class ValidatedFrozenSourceGraph:
    graph: dict[str, Any]
    source_graph_hash: str


SOURCE_GRAPH_HASH_ALGORITHM = "sha256-json-c14n-v1"
_HASH = re.compile(r"^[0-9a-f]{64}$")


class FrozenCanonicalError(RuntimeError):
    pass


class FrozenCanonicalContractError(FrozenCanonicalError):
    """Persisted R7 output is malformed; callers map this to a controlled failure."""


class FrozenCanonicalPersistenceError(FrozenCanonicalError):
    pass


def source_graph_hash(source_graph: dict[str, Any]) -> str:
    """Versioned canonical serialization of the persisted frozen graph."""
    return hashlib.sha256(json.dumps(source_graph, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_frozen_source_graph(source_graph: dict[str, Any], production_model_hash: str, canonical_report: dict[str, Any]) -> ValidatedFrozenSourceGraph:
    if not isinstance(source_graph, dict) or not source_graph:
        raise FrozenCanonicalContractError("Frozen R7 source graph is missing")
    if source_graph.get("graph_version") != "procurement-source-graph-v2":
        raise FrozenCanonicalContractError("Frozen R7 source graph version is invalid")
    if source_graph.get("production_model_hash") != production_model_hash or not isinstance(production_model_hash, str) or not _HASH.fullmatch(production_model_hash):
        raise FrozenCanonicalContractError("Frozen R7 source graph production hash is invalid")
    fragments = source_graph.get("structured_fragments")
    if not isinstance(fragments, list) or not isinstance(source_graph.get("canonical_item_edges"), list):
        raise FrozenCanonicalContractError("Frozen R7 source graph records are invalid")
    keys = []
    for fragment in fragments:
        if not isinstance(fragment, dict) or not isinstance(fragment.get("fragment_key"), str) or not fragment["fragment_key"]:
            raise FrozenCanonicalContractError("Frozen R7 source fragment is invalid")
        keys.append(fragment["fragment_key"])
    if len(keys) != len(set(keys)):
        raise FrozenCanonicalContractError("Frozen R7 source fragments are not unique")
    keyset = set(keys)
    for edge in source_graph.get("parent_child_edges", []):
        if not isinstance(edge, dict) or edge.get("parent") not in keyset or edge.get("child") not in keyset:
            raise FrozenCanonicalContractError("Frozen R7 parent-child edge is dangling")
    seen_edges = set()
    for edge in source_graph["canonical_item_edges"]:
        if not isinstance(edge, dict) or edge.get("source_fragment_key") not in keyset or not edge.get("canonical_item_id") or not edge.get("field_name"):
            raise FrozenCanonicalContractError("Frozen R7 canonical item edge is dangling")
        identity = (edge["canonical_item_id"], edge["source_fragment_key"], edge["field_name"])
        if identity in seen_edges: raise FrozenCanonicalContractError("Frozen R7 canonical item edge is duplicated")
        seen_edges.add(identity)
    for key in ("cross_source_matches", "cardinality_decisions"):
        if not isinstance(source_graph.get(key), list):
            raise FrozenCanonicalContractError("Frozen R7 source graph relation set is invalid")
    provenance = canonical_report.get("provenance") if isinstance(canonical_report, dict) else None
    if not isinstance(provenance, dict) or provenance.get("production_model_hash") != production_model_hash:
        raise FrozenCanonicalContractError("Frozen R7 production model hash mismatch")
    return ValidatedFrozenSourceGraph(source_graph, source_graph_hash(source_graph))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    # Frozen R7 contract: indent=2 and intentionally no trailing newline.
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def persist_canonical_outputs(*, output_dir: Path, run_id: str, metadata: dict, outputs: dict, steps: list, render_html: Callable[[dict], str], now_factory: Callable[[], str]) -> PersistedCanonicalFiles:
    from src.modules.tender_operator_agent_demo.report_model import (
        build_customer_report_projection,
        build_procurement_report_model,
        canonical_report_to_markdown,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in outputs.items():
        _write_json(output_dir / f"{name}.json", payload)
    canonical = build_procurement_report_model(metadata, outputs)
    canonical_path = output_dir / "canonical_report.json"; _write_json(canonical_path, canonical)
    html_path = output_dir / "report.html"; html_path.write_text(render_html(canonical), encoding="utf-8")
    report_path = output_dir / "report.json"
    customer_projection = build_customer_report_projection(canonical)
    _write_json(report_path, {"run_id": run_id, "report_title": "Отчёт по загруженному прогону тендерного агента", "generated_at": now_factory(), "recommendation": outputs["final_recommendation"]["recommendation"], "recommendation_label": outputs["final_recommendation"]["label"], "executive_summary": outputs["final_recommendation"]["rationale"], "manual_checks": outputs["final_recommendation"]["manual_checks"], "sections": [{"title": item.title, "kind": "bullets", "items": item.findings} for item in steps], "report_markdown": canonical_report_to_markdown(canonical), "decision_core": customer_projection.get("decision_core")})
    steps_path = output_dir / "steps.json"; _write_json(steps_path, {"steps": [item.model_dump(mode="json") for item in steps]})
    requirements_path = output_dir / "requirements.json"
    return PersistedCanonicalFiles(requirements_path, canonical_path, report_path, html_path, steps_path, canonical)


def verify_persisted_canonical_outputs(*, output_dir: Path, expected_outputs: dict | None = None, expected_canonical_report: dict | None = None) -> PersistedCanonicalOutputs:
    requirements_path, canonical_path = output_dir / "requirements.json", output_dir / "canonical_report.json"
    try:
        requirements_bytes = requirements_path.read_bytes()
        canonical_report_bytes = canonical_path.read_bytes()
    except OSError as exc:
        raise FrozenCanonicalPersistenceError("Frozen canonical output files are unreadable") from exc
    return verify_canonical_bytes(
        requirements_bytes=requirements_bytes,
        canonical_report_bytes=canonical_report_bytes,
        requirements_path=requirements_path,
        canonical_report_path=canonical_path,
        report_json_path=output_dir / "report.json",
        report_html_path=output_dir / "report.html",
        steps_path=output_dir / "steps.json",
        expected_outputs=expected_outputs,
        expected_canonical_report=expected_canonical_report,
    )


def verify_canonical_bytes(
    *,
    requirements_bytes: bytes,
    canonical_report_bytes: bytes,
    requirements_path: Path | None = None,
    canonical_report_path: Path | None = None,
    report_json_path: Path | None = None,
    report_html_path: Path | None = None,
    steps_path: Path | None = None,
    expected_outputs: dict | None = None,
    expected_canonical_report: dict | None = None,
) -> PersistedCanonicalOutputs:
    """Verify exact frozen bytes without consulting a mutable working directory.

    This is deliberately the sole parser/graph-policy boundary used by both
    R7 persisted-output verification and the R8 immutable snapshot publisher.
    """
    if not isinstance(requirements_bytes, bytes) or not requirements_bytes:
        raise FrozenCanonicalContractError("Frozen R7 requirements bytes are invalid")
    if not isinstance(canonical_report_bytes, bytes) or not canonical_report_bytes:
        raise FrozenCanonicalContractError("Frozen R7 canonical report bytes are invalid")
    try:
        persisted_requirements = json.loads(requirements_bytes)
        preliminary = persisted_requirements["preliminary_analysis"]
        canonical_model = preliminary["canonical_procurement_model"]
        graph = canonical_model["source_graph"]
        production_hash = canonical_model["production_model_hash"]
        persisted_canonical = json.loads(canonical_report_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise FrozenCanonicalContractError("Frozen R7 canonical source-graph contract is incomplete") from exc
    if not isinstance(graph, dict) or not production_hash:
        raise FrozenCanonicalContractError("Frozen R7 canonical source-graph contract is invalid")
    if expected_outputs is not None:
        try:
            if graph != expected_outputs["requirements"]["preliminary_analysis"]["canonical_procurement_model"]["source_graph"]:
                raise FrozenCanonicalContractError("Persisted frozen source graph differs from in-memory result")
        except (KeyError, TypeError) as exc: raise FrozenCanonicalContractError("Expected frozen graph is invalid") from exc
    if expected_canonical_report is not None and persisted_canonical != expected_canonical_report:
        raise FrozenCanonicalContractError("Persisted frozen canonical report differs from in-memory result")
    validated_graph = validate_frozen_source_graph(graph, production_hash, persisted_canonical)
    model_hash = hashlib.sha256(json.dumps(persisted_canonical, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    unknown = Path("<verified-bytes>")
    return PersistedCanonicalOutputs(
        requirements_path or unknown,
        canonical_report_path or unknown,
        report_json_path or unknown,
        report_html_path or unknown,
        steps_path or unknown,
        persisted_canonical,
        requirements_bytes,
        canonical_report_bytes,
        validated_graph.graph,
        validated_graph.source_graph_hash,
        production_hash,
        model_hash,
        hashlib.sha256(requirements_bytes).hexdigest(),
        hashlib.sha256(canonical_report_bytes).hexdigest(),
    )
