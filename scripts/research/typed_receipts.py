"""Isolated source-scoped output receipts; no external authority or worker."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass

from scripts.research.source_catalog import SourceIdentity

STAGES = frozenset({"discover", "detail", "attachment", "extract", "index", "outcome"})
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024


def check_sha(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("invalid SHA256")


def _reject_duplicate_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("ambiguous duplicate JSON key")
        value[key] = item
    return value


@dataclass(frozen=True, slots=True)
class StageReceipt:
    """Exact bytes + membership, not a signature or original-source approval."""

    job_id: str
    source: str
    namespace: str
    stage: str
    external_id: str | None
    unit_sha256: str
    input_sha256: str
    parent_receipt_sha256: str | None
    artifact_sha256: str
    artifact_size: int
    members: tuple[str, ...]
    explicit_empty: bool = False

    def __post_init__(self):
        for value in (self.job_id, self.unit_sha256, self.input_sha256, self.artifact_sha256):
            check_sha(value)
        if self.parent_receipt_sha256 is not None:
            check_sha(self.parent_receipt_sha256)
        if not isinstance(self.stage, str) or self.stage not in STAGES:
            raise ValueError("invalid receipt stage")
        if not isinstance(self.members, tuple) or len(self.members) > 4096:
            raise ValueError("unbounded receipt membership")
        if not all(isinstance(member, str) for member in self.members):
            raise ValueError("invalid member type")
        if len(set(self.members)) != len(self.members):
            raise ValueError("duplicate receipt membership")
        if type(self.artifact_size) is not int or not 0 < self.artifact_size <= MAX_ARTIFACT_BYTES:
            raise ValueError("invalid byte count")
        if type(self.explicit_empty) is not bool:
            raise ValueError("invalid empty evidence flag")
        if self.stage == "discover":
            if self.external_id is not None or self.parent_receipt_sha256 is not None:
                raise ValueError("discovery cannot be parented")
            if self.explicit_empty != (not self.members):
                raise ValueError("explicit empty evidence required")
        else:
            if self.parent_receipt_sha256 is None or self.members != (self.external_id,) or self.explicit_empty:
                raise ValueError("receipt not bound to exact procurement")
        for member in self.members:
            SourceIdentity(self.source, self.namespace, member)
        if self.stage != "discover":
            SourceIdentity(self.source, self.namespace, self.external_id)

    @property
    def canonical(self):
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @property
    def sha256(self):
        return hashlib.sha256(self.canonical.encode()).hexdigest()

    def verify_artifact(self, artifact: bytes):
        if type(artifact) is not bytes or len(artifact) != self.artifact_size:
            raise ValueError("artifact byte count mismatch")
        if hashlib.sha256(artifact).hexdigest() != self.artifact_sha256:
            raise ValueError("artifact content mismatch")
        if self.stage == "discover":
            try:
                payload = json.loads(artifact, object_pairs_hook=_reject_duplicate_keys)
            except (ValueError, UnicodeError) as exc:
                raise ValueError("discovery membership artifact invalid") from exc
            if (not isinstance(payload, dict) or payload.get("members") != list(self.members)
                    or payload.get("explicit_empty") is not self.explicit_empty):
                raise ValueError("discovery artifact membership mismatch")
