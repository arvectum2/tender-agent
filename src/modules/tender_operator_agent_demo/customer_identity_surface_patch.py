"""Narrow source-faithful boundary hardening for customer identities.

`customer_name` is the legal identity surface, not an adjacent source alias
introduced only for later shorthand (for example ``(далее - ГБУ ...)``).
This patch trims only such trailing definitional parentheticals while keeping
ordinary legal-name parentheticals, casing, quotes and locality text intact.
"""
from __future__ import annotations

import re

from src.modules.tender_operator_agent_demo import customer_role_facts as _facts

_INSTALLED = False
_ORIGINAL_RESOLVE = None

_DEFINITIONAL_ALIAS_SUFFIX_RE = re.compile(
    r"\s*\(\s*(?:далее|в\s+дальнейшем(?:\s+по\s+тексту)?)"
    r"\s*(?:[-–—:]\s*)?[^()]{1,220}\)\s*$",
    re.IGNORECASE,
)


def _strip_definitional_alias_suffix(value: str) -> str:
    """Remove one trailing shorthand-definition parenthetical, if present."""

    match = _DEFINITIONAL_ALIAS_SUFFIX_RE.search(value)
    if match is None:
        return value
    legal_name = value[: match.start()].rstrip(" ,.;:")
    return legal_name or value


def _resolve_customer_name(**kwargs):
    resolution = _ORIGINAL_RESOLVE(**kwargs)
    if resolution is None:
        return None
    value = _strip_definitional_alias_suffix(resolution.value)
    if value == resolution.value:
        return resolution
    return _facts.CustomerResolution(
        value=value,
        evidence_kind=resolution.evidence_kind,
        source_role=resolution.source_role,
        confidence=resolution.confidence,
    )


def install() -> None:
    """Install the alias-boundary wrapper exactly once."""

    global _INSTALLED, _ORIGINAL_RESOLVE
    if _INSTALLED:
        return
    _ORIGINAL_RESOLVE = _facts.resolve_customer_name
    _facts.resolve_customer_name = _resolve_customer_name
    _INSTALLED = True
