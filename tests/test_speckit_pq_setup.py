"""Read-only checks of Spec Kit's agent-neutral Tender Agent pilot."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pq_agent_neutral_setup():
    data = json.loads((ROOT / ".specify/init-options.json").read_text(encoding="utf-8"))
    assert data["integration"] == "none"
    assert data["speckit_version"] == "1.2.4"
    assert (ROOT / ".specify/workflows/speckit/workflow.yml").is_file()


def test_pq_governance_pointer_is_non_authoritative():
    adapter = (ROOT / ".specify/memory/constitution.md").read_text(encoding="utf-8")
    assert "non-canonical reference adapter" in adapter
    assert "ARVECTUM-ENGINEERING-STANDARD.md" in adapter
    assert "AGENTS.md" in adapter
    assert "[PRINCIPLE_1_NAME]" not in adapter


def test_pq_feature_plan_links_existing_workflow_and_coverage():
    spec = (ROOT / "specs/001-power-quality-evidence-closure/spec.md").read_text()
    tasks = (ROOT / "specs/001-power-quality-evidence-closure/tasks.md").read_text()
    assert "partial_do_not_extrapolate" in spec
    assert "0 independently verified signed suppliers" in spec
    assert "TA-MI-AUTONOMY-20261027" in tasks
    assert "2024" in tasks and "2025" in tasks and "2026" in tasks
