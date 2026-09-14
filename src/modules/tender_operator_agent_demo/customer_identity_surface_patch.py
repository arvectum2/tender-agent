"""Narrow source-faithful boundary hardening for customer identities.

`customer_name` is the legal identity surface, not an adjacent source alias
introduced only for later shorthand (for example ``(далее - ГБУ ...)``).
This patch removes only definitional alias parentheticals while keeping ordinary
legal-name parentheticals, casing, quotes and locality text intact.

Alias removal happens both before candidate collection and at candidate
acceptance.  Pre-collection removal matters because the base preamble parser
intentionally treats ``в дальнейшем`` as a role-clause boundary; an alias such
as ``(в дальнейшем по тексту: ГУ ...)`` would otherwise prevent the legal-name
candidate from being formed at all.  Acceptance-time removal keeps equal-strength
plain and aliased source occurrences from becoming a false conflict.
"""
from __future__ import annotations

import re

from src.modules.tender_operator_agent_demo import customer_role_facts as _facts

_INSTALLED = False
_ORIGINAL_ACCEPT = None
_ORIGINAL_COLLECT = None

_DEFINITIONAL_ALIAS_PAREN_RE = re.compile(
    r"\s*\(\s*(?:далее|в\s+дальнейшем(?:\s+по\s+тексту)?|"
    r"сокращ[её]нное\s+наименование)"
    r"\s*(?:[-–—:]\s*)?[^()\n]{1,220}\)",
    re.IGNORECASE,
)
_DEFINITIONAL_ALIAS_SUFFIX_RE = re.compile(
    _DEFINITIONAL_ALIAS_PAREN_RE.pattern + r"\s*$",
    re.IGNORECASE,
)


def _strip_definitional_alias_suffix(value: str) -> str:
    """Remove one trailing shorthand-definition parenthetical, if present."""

    match = _DEFINITIONAL_ALIAS_SUFFIX_RE.search(value)
    if match is None:
        return value
    legal_name = value[: match.start()].rstrip(" ,.;:")
    return legal_name or value


def _strip_definitional_alias_parentheticals(text: str) -> str:
    """Remove source-defined shorthand before role-clause parsing."""

    return _DEFINITIONAL_ALIAS_PAREN_RE.sub("", text)


def _accept(value, *, evidence_kind, source_role):
    if isinstance(value, str):
        value = _strip_definitional_alias_suffix(value)
    return _ORIGINAL_ACCEPT(value, evidence_kind=evidence_kind, source_role=source_role)


def _collect(text, source_role):
    if isinstance(text, str):
        text = _strip_definitional_alias_parentheticals(text)
    return _ORIGINAL_COLLECT(text, source_role)


def install() -> None:
    """Install the alias-boundary wrappers exactly once."""

    global _INSTALLED, _ORIGINAL_ACCEPT, _ORIGINAL_COLLECT
    if _INSTALLED:
        return
    _ORIGINAL_ACCEPT = _facts._accept
    _ORIGINAL_COLLECT = _facts._collect
    _facts._accept = _accept
    _facts._collect = _collect
    _INSTALLED = True
