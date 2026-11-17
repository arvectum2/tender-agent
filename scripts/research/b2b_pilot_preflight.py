"""Local-only preflight for the operator-approved Arvectum pilot.

No HTTP requests, login, cookie export, or live runner activation. A reviewed
manifest is deliberate input; never enumerate private platform endpoints.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.research.b2b_network_guard import GuardError
from scripts.research.b2b_session_policy import (
    HOST,
    ExactScope,
    cookie_jar,
    private_json,
)
from src.modules.saas_foundation.commercial_sources import commercial_identity

CONSENT='PN-1356710-26'
ORIGIN='https://'+HOST


def preflight(manifest,session):
    if not isinstance(manifest,dict) or set(manifest)!={'schema','organization','operator_consent','card','routes','confirm_internal_read_only'} or manifest['schema']!=1 or manifest['organization']!='ООО Арвектум' or manifest['operator_consent']!=CONSENT or manifest['confirm_internal_read_only'] is not True:raise GuardError('Explicit internal pilot manifest required')
    try:platform,identifier=commercial_identity(manifest['card'])
    except (ValueError,TypeError):raise GuardError('Exact B2B card required') from None
    if platform!='b2bcenter':raise GuardError('Exact B2B card required')
    scope=ExactScope(ORIGIN,manifest['routes'])
    if scope.kind(manifest['card'])!='page':raise GuardError('Card must be explicitly reviewed')
    # Initial pilot is one page. Extra resources require positive URL review;
    # other procedure navigation is not authorized by the selected card.
    if sum(kind=='page' for kind in scope.routes.values())!=1:raise GuardError('One-card pilot only')
    jar=cookie_jar(session)
    return {'state':'LOCAL_INPUT_VALIDATED_LIVE_DISABLED','operator_consent':CONSENT,'external_id':identifier,'reviewed_route_count':len(scope.routes),'cookie_count':len(list(jar.jar)),'account_identity_verified':False,'live_network_performed':False,'external_submission_allowed':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--session',type=Path,required=True);args=parser.parse_args()
    try:result=preflight(private_json(args.manifest),private_json(args.session))
    except (GuardError,OSError,TypeError,ValueError):
        print(json.dumps({'state':'LOCAL_INPUT_REJECTED'}));return 1
    print(json.dumps(result,ensure_ascii=False));return 0


if __name__=='__main__':raise SystemExit(main())
