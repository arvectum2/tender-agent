"""Pure evidence-candidate lexical matching shared by SOAP and hybrid search."""

from __future__ import annotations

import re
from typing import Any

AMBIGUOUS = frozenset({"SVG", "SVC", "PQ", "УКМ", "КРМ", "БСК", "СТК", "TSC", "TCR", "ФЛИКЕР"})


def _matching_terms(text: str, ontology: dict[str, Any]) -> list[dict[str, str]]:
    hits = []
    normalized = text.casefold()
    for family in ontology.get("families", []):
        family_hits = []
        for synonym in family.get("positive", []):
            term = synonym.strip()
            if not term:
                continue
            if not re.search(r"(?<!\w)" + re.escape(term.casefold()) + r"(?!\w)", normalized):
                continue
            if term.upper() in AMBIGUOUS and not any(
                c.casefold() in normalized for c in family.get("contexts", [])
            ):
                continue
            if any(ex.casefold() in normalized for ex in family.get("exclusions", [])):
                continue
            family_hits.append(term)
        if family_hits:
            hits.append({"family": str(family["id"]), "terms": sorted(set(family_hits))})
    return hits
