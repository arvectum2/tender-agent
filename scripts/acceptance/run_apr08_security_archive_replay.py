"""Replay existing SHA-pinned EIS archives without network or model calls."""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import tempfile
import zipfile
from pathlib import Path

NAV = Path('/Volumes/ArvectumSSD/Arvectum/runtime/ta-apr06-overlap-review-20261117/review-navigation.json')
RECEIPT = Path('docs/acceptance/apr06_overlap_historical_source_packets_2026-11-17.json')
CASES = {
    '0348100024426000039': (('6225.00', '0.5'), (None, '30.0')),
    '0895100000126000897': (('101385.00', '1.0'), ('1013850.00', '10.0')),
    '0127100008626000013': ((None, None), (None, '10.0')),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    nav = json.loads(NAV.read_text())
    receipts = json.loads(RECEIPT.read_text())
    with tempfile.TemporaryDirectory(prefix='apr08-security-replay-') as tmp:
        root = Path(tmp)
        os.environ['AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR'] = str(root)
        from src.modules.tender_operator_agent_demo.eis_official_procedure import (
            classify_official_eis_archive,
        )
        from src.modules.tender_operator_agent_demo.evidence_grounded_questions import (
            GroundedQuestion,
            answer_grounded_question,
        )

        for index, (number, expectations) in enumerate(CASES.items()):
            nav_row = next(x for x in nav['cases'] if x['registry_number'] == number)
            receipt = next(x for x in receipts['cases'] if x['registry_number'] == number)['archive']
            original = Path(nav_row['archive_path'])
            assert not original.is_symlink() and digest(original) == receipt['zip_sha256']
            run = f'toa-run-20261117120000-{index:06x}'
            directory = root / run / 'input'
            directory.mkdir(parents=True)
            archive = directory / 'documentation-archive.zip'
            shutil.copyfile(original, archive)
            classification = classify_official_eis_archive(archive, number)
            assert classification['status'] == 'ATTESTED_COMPETITIVE'
            assert classification['notice_xml_sha256'] == receipt['selected_xml_sha256']
            files = []
            with zipfile.ZipFile(archive) as z:
                for member in z.infolist():
                    if not re.fullmatch(r'epNotification(?:EF|EZK|EOK)2020_' + number + r'_\d+_[A-Fa-f0-9]{32}\.xml', member.filename):
                        continue
                    assert member.file_size <= 5 * 1024 * 1024
                    raw = z.read(member)
                    (directory / member.filename).write_bytes(raw)
                    files.append({'file_id': f'FILE-{len(files)+1:02d}', 'stored_name': member.filename,
                                  'original_name': member.filename, 'display_name': member.filename, 'extension': '.xml',
                                  'size_bytes': len(raw), 'content_type': 'application/xml'})
            metadata = {'run_id': run, 'procurement_id': number, 'procurement_source': 'zakupki_gov_ru_getdocs_ip',
                        'archive_stored_name': archive.name, 'official_eis_procedure': classification, 'files': files,
                        'created_at': '2026-11-17T12:00:00+00:00', 'mode': 'procurement_search_intake',
                        'tender_title': 'Архивное извещение '+number, 'tender_category': 'Архивная проверка',
                        'customer_name': 'Не установлен в оболочке теста', 'law': '44-ФЗ', 'notice_number': number,
                        'status': 'ready_to_analyze', 'archive_downloaded': True, 'attachments_status': 'downloaded'}
            (root / run / 'metadata.json').write_text(json.dumps(metadata))
            for question, expected in zip(('Какой размер обеспечения заявки?', 'Какой размер обеспечения исполнения контракта?'), expectations, strict=True):
                answer = answer_grounded_question(run, GroundedQuestion(question=question))
                if expected == (None, None):
                    assert answer['status'] == 'UNKNOWN' and not answer['citations']
                else:
                    assert answer['status'] == 'ARCHIVED_SECURITY_FIELDS'
                    observation = answer['observation']
                    assert (observation['amount'], observation['percent']) == expected
                    assert observation['calculated_amount'] is None and observation['currency'] is None
                    assert len(answer['citations']) == sum(value is not None for value in expected)
                assert not answer['bid_ready'] and not answer['current_revision_attested'] and not answer['legal_requirement_attested']
                print('APR08_ARCHIVED_SECURITY', number, answer['intent'], answer['status'], *expected)
            if number == '0348100024426000039':
                for question, scope in [('Поясни требования к обеспечению заявки','applicationGuarantee'), ('Поясни требования к обеспечению исполнения контракта','contractGuarantee')]:
                    legal = answer_grounded_question(run, GroundedQuestion(question=question))
                    assert legal['status'] == 'CUSTOMER_TERMS_LEGAL_REFERENCES'
                    obs = legal['observation']
                    assert obs['customer_text_verified'] and not obs['statute_text_verified'] and obs['legal_conclusion'] is None
                    assert any(ref.get('article') == '45' and ref.get('act') == '44-ФЗ' for ref in obs['references'])
                    assert legal['citations'][0]['locator'].endswith(scope+'/procedureInfo')
                    assert not legal['bid_ready'] and not legal['legal_requirement_attested']
                    print('APR08_CUSTOMER_LEGAL_REFERENCE', number, scope, len(obs['references']))
                if os.environ.get('APR08_PINNED_BROWSER_ACCEPTANCE') == '1':
                    from fastapi import FastAPI

                    from scripts.acceptance.apr08_browser_harness import run_browser
                    from src.modules.tender_operator_agent_demo import (
                        router as operator_router,
                    )
                    from src.shared.api.middleware import TenderPilotBasicAuthMiddleware
                    from src.shared.config.settings import get_settings

                    password = secrets.token_urlsafe(32)
                    os.environ.update(AI_CORP_PILOT_AUTH_ENABLED='true', AI_CORP_PILOT_AUTH_USERNAME='apr08-replay',
                                      AI_CORP_PILOT_AUTH_PASSWORD=password,
                                      AI_CORP_PILOT_AUTH_PROTECTED_PREFIXES='/pilot/tender-agent,/api/demo/tender-agent',
                                      AI_CORP_PILOT_AUTH_PUBLIC_PATHS='/health')
                    get_settings.cache_clear()
                    app = FastAPI()
                    app.include_router(operator_router.router)
                    app.add_middleware(TenderPilotBasicAuthMiddleware, username='apr08-replay', password=password,
                                       protected=('/pilot/tender-agent','/api/demo/tender-agent'), public=('/health',))
                    from scripts.acceptance.run_apr08_real_dp_replay import inventory

                    before = inventory(root / run)
                    run_browser(app, run, password, Path(os.environ['APR08_SCREENSHOT_DIR']), scenario='pinned')
                    assert inventory(root / run) == before
            assert digest(original) == receipt['zip_sha256']
    print('APR08_SECURITY_ARCHIVE_REPLAY_PASS 3 archives 6 questions originals unchanged')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
