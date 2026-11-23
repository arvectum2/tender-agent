"""Offline readiness inventory, never a commercial acceptance manifest or score."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.quality.apr067_corrected_cohort_integrity import (
    CORRECTED_PATH,
    ORIGINAL_PATH,
    CohortIntegrityError,
    _parse,
    audit,
)
from src.modules.commercial_acceptance.acceptance import METRICS, validate_manifest

ROOT = Path(__file__).resolve().parents[2]
POOL = ROOT / 'docs/acceptance/apr06_candidate_pool_2026-10-09.json'
POOL_SHA256 = '71032c9581a209c0cece7f159d51efbb0ce656427d9dcdd8a51d263b0079d796'


def inventory(pool_bytes: bytes, original_bytes: bytes, corrected_bytes: bytes) -> dict:
    if hashlib.sha256(pool_bytes).hexdigest() != POOL_SHA256:
        raise CohortIntegrityError('Candidate pool bytes changed')
    proof = audit(original_bytes, corrected_bytes)
    pool = _parse(pool_bytes)
    validate_manifest(pool)
    development = _parse(corrected_bytes)['cases']
    candidates = {row['reg_number']: row for row in pool['cases']}
    dev = {row['registry_number']: row for row in development}
    rows = []
    for number in sorted(candidates.keys() | dev.keys()):
        candidate = candidates.get(number)
        recorded = dev.get(number)
        group = ('BOTH' if candidate and recorded else 'CANDIDATE_ONLY' if candidate else 'DEVELOPMENT_ONLY')
        rows.append({
            'registry_number': number,
            'membership': group,
            'candidate_law': candidate['law'] if candidate else None,
            'candidate_procedure': candidate['procedure'] if candidate else None,
            'candidate_subject': candidate['subject'] if candidate else None,
            'candidate_verification_state': candidate['verification']['state'] if candidate else None,
            'archived_development_evidence': recorded,
            'required_next_review': ('VERIFY_ORIGINAL_REVISION_AND_COLLECT_ATTRIBUTED_REVIEW' if recorded else
                                     'ACQUIRE_AND_VERIFY_ORIGINALS_BEFORE_REVIEW'),
            'independently_verified_current_eis_revision': None,
            'attributed_human_review': None,
            'commercial_decision': None,
        })
    return {
        'schema': 'apr06_review_readiness_inventory_v1',
        'state': 'BLOCKED_INDEPENDENT_SOURCE_AND_OWNER_REVIEW',
        'candidate_pool_sha256': POOL_SHA256,
        'development_cohort_sha256': proof['corrected_snapshot_sha256'],
        'candidate_count': len(candidates),
        'archived_development_count': len(dev),
        'overlap_count': len(candidates.keys() & dev.keys()),
        'candidate_only_count': len(candidates.keys() - dev.keys()),
        'development_only_count': len(dev.keys() - candidates.keys()),
        'inventory_count_not_frozen_corpus': len(rows),
        'development_proof': proof,
        'current_source_verification_performed': False,
        'human_reviews_present_in_inputs': 0,
        'owner_threshold_approval_authenticated': False,
        'commercial_metrics': {metric: None for metric in METRICS},
        'commercial_release_authorized': False,
        'cases': rows,
    }


def main() -> int:
    try:
        for path in (POOL, ORIGINAL_PATH, CORRECTED_PATH):
            if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 300_000:
                raise CohortIntegrityError('Unsafe tracked snapshot')
        result = inventory(POOL.read_bytes(), ORIGINAL_PATH.read_bytes(), CORRECTED_PATH.read_bytes())
    except (ValueError, OSError) as exc:
        print(json.dumps({'ok': False, 'error': type(exc).__name__}))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
