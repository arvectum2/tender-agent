"""Separate UPS/battery review from the general industrial equipment channel.

Keep mixed packages for manual scope allocation. This is routing of research
candidates, not a supplier assignment, authorization to bid or contract award.
"""
import re
from collections import Counter

from scripts.research.build_sibur_sales_map import UPS_FAMILY

OTHER_POWER = r"\b(?:УКРМ|STATCOM|СТАТКОМ|СОПТ|ЩПТ)\b|компенсаци\w*\s+реакт\w+\s+мощност|конденсаторн\w+\s+установ|фильтр\w*\s+(?:высш\w+\s+)?гармоник|тиристорн\w+\s+компенсатор"


def split(report):
    results = []
    seen = set()
    for row in report["candidates"]:
        if not row["core_tags"]:
            continue
        ident = row["external_id"]
        if ident in seen:
            raise ValueError("duplicate source identity")
        seen.add(ident)
        ups = bool(row.get("ups_tags"))
        other = set(row["core_tags"]) - {UPS_FAMILY}
        # Old power category mixes PQ, UPS and converters; do not send pure
        # UPS to both channels merely because of the inherited generic tag.
        if ups and not re.search(OTHER_POWER, " ".join([row["title"], *row["subject"]]), re.IGNORECASE):
            other.discard("Источники и качество питания")
        routes = []
        if other:
            routes.append("industrial_equipment")
        if ups:
            routes.append("ups_battery")
        if not routes:
            raise ValueError("unrouted core record")
        allocation = (
            "mixed_package_manual_scope_review" if len(routes) > 1
            else "ups_battery_application_review" if ups and "explicit_ups" not in row["ups_tags"]
            else "single_channel_review"
        )
        results.append({"external_id": ident, "channels":routes, "allocation":allocation,
                        "industrial_tags":sorted(other),"ups_tags":row.get("ups_tags", []),
                        "source_receipts":row["source_receipts"],"supplier_assigned":False,
                        "execution_allowed":False})
    return {"schema":"equipment_sales_channel_routing_v1","unique_records":len(results),
            "channel_counts":dict(Counter(c for r in results for c in r["channels"])),
            "allocation_counts":dict(Counter(r["allocation"] for r in results)),
            "records":results}
