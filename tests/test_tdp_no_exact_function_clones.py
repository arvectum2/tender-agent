"""CI quality gate against reintroducing verified exact function clones.

AST-body equality is intentionally only a lower bound on duplication; it is
not a detector of semantic near-duplicates or permission to remove adapters.
"""
from __future__ import annotations

from pathlib import Path

from scripts.ops.audit_tdp_duplicate_functions import duplicate_groups


ROOT = Path(__file__).resolve().parents[1]


def test_no_long_identical_function_bodies_in_tender_agent():
    groups = duplicate_groups(("tender-agent", ROOT / "src"), min_lines=12)
    pairs = [
        [(entry["file"], entry["function"]) for entry in group["occurrences"]]
        for group in groups
    ]
    assert not pairs, (
        "Identical AST function bodies >=12 lines returned. Move shared logic "
        "to one owned module while preserving compatibility shims. "
        f"Duplicate groups: {pairs[:10]!r}"
    )
