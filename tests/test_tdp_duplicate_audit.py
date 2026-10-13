"""Clone detectors are deterministic and make no deletion decisions."""

from __future__ import annotations

from pathlib import Path

from scripts.ops.audit_tdp_duplicate_functions import duplicate_groups


def test_exact_duplicate_function_bodies_are_recorded_without_false_deletion(tmp_path: Path):
    repo_a = tmp_path / "a"
    repo_b = tmp_path / "b"
    repo_a.mkdir()
    repo_b.mkdir()
    implementation = """
def normalize(value):
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if cleaned.startswith('prefix:'):
        cleaned = cleaned.removeprefix('prefix:')
    return cleaned.lower()
"""
    (repo_a / "first.py").write_text(implementation, encoding="utf-8")
    (repo_b / "second.py").write_text(
        implementation.replace("def normalize", "def normalize_source"),
        encoding="utf-8",
    )
    matches = duplicate_groups(("tender-agent", repo_a), ("data-platform", repo_b), min_lines=8)
    assert len(matches) == 1
    assert matches[0]["cross_repo"] is True
    assert len(matches[0]["occurrences"]) == 2
    assert matches[0]["max_lines"] >= 8
