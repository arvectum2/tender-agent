"""Pure source-adapter discovery contract; no I/O or runtime activation.

An adapter listing is documentation of capabilities, never a grant to fetch,
write, or bid. Customer/GEH filters are scopes, not new source identities.
"""

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class Evidence(StrEnum):
    IMPLEMENTED = "implemented"
    PILOT = "pilot"
    UNVERIFIED = "unverified"


@dataclass(frozen=True, slots=True)
class SourceSpec:
    source_id: str
    namespaces: tuple[str, ...]
    fresh: Evidence
    archive: Evidence
    documents: Evidence
    note: str


# Keep the existing executors and locks unchanged. Each future adapter must
# prove its own contracts and be admitted separately before scheduling.
SOURCES = MappingProxyType(
    {
        "eis": SourceSpec(
            "eis",
            ("44fz", "223fz", "capital_repair"),
            Evidence.IMPLEMENTED,
            Evidence.UNVERIFIED,
            Evidence.IMPLEMENTED,
            "Official notice number; not a commercial lot ID.",
        ),
        "etp_gpb": SourceSpec(
            "etp_gpb",
            ("etp", "gos", "price_request", "etp_click", "sale"),
            Evidence.PILOT,
            Evidence.IMPLEMENTED,
            Evidence.IMPLEMENTED,
            "GEH is a customer scope; sale is observation-only, not procurement demand; never infer winner from list status.",
        ),
        "sibur": SourceSpec(
            "sibur",
            ("procedure",),
            Evidence.PILOT,
            Evidence.IMPLEMENTED,
            Evidence.IMPLEMENTED,
            "Historical registry and OOXML document lane; other formats separately reviewed.",
        ),
        "mos_portal": SourceSpec(
            "mos_portal",
            ("auction",),
            Evidence.PILOT,
            Evidence.PILOT,
            Evidence.UNVERIFIED,
            "Observed HTTP 402; do not bypass access restrictions.",
        ),
        "tek_torg": SourceSpec(
            "tek_torg",
            (),
            Evidence.UNVERIFIED,
            Evidence.UNVERIFIED,
            Evidence.UNVERIFIED,
            "Redirect loops/storefront shell are not a verified listing.",
        ),
        "eat": SourceSpec(
            "eat",
            (),
            Evidence.UNVERIFIED,
            Evidence.UNVERIFIED,
            Evidence.UNVERIFIED,
            "Intermediate loading page is not a verified listing.",
        ),
    }
)


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    source: str
    namespace: str
    external_id: str

    def __post_init__(self):
        spec = SOURCES.get(self.source)
        if spec is None or self.namespace not in spec.namespaces:
            raise ValueError("unregistered source namespace")
        x = self.external_id
        if (
            not isinstance(x, str)
            or not x
            or len(x) > 256
            or x != x.strip()
            or any(ord(c) < 32 or ord(c) == 127 for c in x)
        ):
            raise ValueError("invalid external identity")

    @property
    def key(self) -> tuple[str, str, str]:
        return self.source, self.namespace, self.external_id


class Coverage(StrEnum):
    COMPLETE = "complete_for_requested_window"
    PARTIAL = "partial"
    FAILED = "failed"


def classify_coverage(
    *,
    source: str,
    namespaces: tuple[str, ...],
    reported_count: int | None,
    observed_ids: tuple[SourceIdentity, ...],
    all_pages_verified: bool,
    explicit_empty: bool = False,
    source_error: bool = False,
) -> Coverage:
    """Only classify coverage of a bound request, never entire market coverage."""
    spec = SOURCES.get(source)
    if (
        spec is None
        or not namespaces
        or len(set(namespaces)) != len(namespaces)
        or not set(namespaces) <= set(spec.namespaces)
    ):
        raise ValueError("unregistered requested source scope")
    if (
        type(source_error) is not bool
        or type(explicit_empty) is not bool
        or type(all_pages_verified) is not bool
    ):
        raise ValueError("coverage evidence must use boolean flags")
    if source_error:
        return Coverage.FAILED
    if (
        type(reported_count) is not int
        or reported_count < 0
        or not all_pages_verified
        or (reported_count == 0 and not explicit_empty)
        or (explicit_empty and reported_count != 0)
        or len(observed_ids) != reported_count
        or len({x.key for x in observed_ids}) != reported_count
        or any(
            x.source != source or x.namespace not in namespaces for x in observed_ids
        )
    ):
        return Coverage.PARTIAL
    return Coverage.COMPLETE
