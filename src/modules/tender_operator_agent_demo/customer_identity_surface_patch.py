"""Narrow source-faithful boundary hardening for customer identities.

`customer_name` is the legal identity surface, not an adjacent source alias
introduced only for later shorthand (for example ``(далее - ГБУ ...)``).
This patch trims only such trailing definitional parentheticals while keeping
ordinary legal-name parentheticals, casing, quotes and locality text intact.

The trimming is applied at candidate acceptance time, before candidate
conflict/ranking logic.  That way two equal-strength source occurrences of the
same legal name do not become a false conflict merely because one occurrence
also defines a shorthand.
"""
from __future__ import annotations

import re

from src.modules.tender_operator_agent_demo import customer_role_facts as _facts

_INSTALLED = False
_ORIGINAL_ACCEPT = None

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


def _accept(value, *, evidence_kind, source_role):
    if isinstance(value, str):
        value = _strip_definitional_alias_suffix(value)
    return _ORIGINAL_ACCEPT(value, evidence_kind=evidence_kind, source_role=source_role)


def install() -> None:
    """Install the alias-boundary candidate wrapper exactly once."""

    global _INSTALLED, _ORIGINAL_ACCEPT
    if _INSTALLED:
        return
    _ORIGINAL_ACCEPT = _facts._accept
    _facts._accept = _accept
    _INSTALLED = True
