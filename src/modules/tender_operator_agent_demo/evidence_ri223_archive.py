"""Explicit, bounded RI223 archived notice observation, not a general import path."""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from src.modules.tender_operator_agent_demo.operator_stored_file_paths import (
    checked_original_input_path,
)
from src.tender_research.providers.ri223_soap_evidence import (
    MAX_ARCHIVE_BYTES,
    MAX_XML_BYTES,
    Ri223EvidenceError,
    _data_root,
    _text,
    parse_ri223_archive,
)

# Independent APR06 archival receipt, not supplied by run metadata or user.
PINS = {'32616444788': ('494da21fc92e14d950e6cdc767b06ade83708f964cbac67332128f77692dbcc4',
                       '5bdc923c00021779a197b69b30a4fb00d2f6949282d0f84f60756e204aa71ee3', '1')}
SOURCE = 'zakupki_gov_ru_ri223_getdocs_ip'
BASE = '/purchaseNotice/body/item/purchaseNoticeData'


def trusted_pins() -> dict[str, tuple[str, str, str]]:
    from src.modules.tender_operator_agent_demo.ri223_receipt_catalog import (
        configured_catalog,
    )

    configured = configured_catalog()
    return PINS if configured is None else configured


def _digest(path: Path, limit: int) -> str:
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if not 0 < len(data) <= limit:
        raise ValueError('source size')
    return hashlib.sha256(data).hexdigest()


def ri223_archive_observation(run: Path, metadata: dict) -> dict:
    result = {'status':'UNKNOWN','regime':'223fz','citations':[], 'fields':{},
              'current_revision_attested':False,'legal_requirement_attested':False,
              'bid_ready':False,'external_action_allowed':False,'scope_complete':False,
              'timezone_attested':False,'award_attested':False}
    number = metadata.get('procurement_id')
    if metadata.get('procurement_source') != SOURCE or not isinstance(number,str):
        return {**result,'reason':'PINNED_RI223_SOURCE_REQUIRED'}
    try:
        pins = trusted_pins()
    except (OSError,ValueError,TypeError):
        return {**result,'reason':'RI223_CATALOG_UNVERIFIED'}
    if number not in pins:
        return {**result,'reason':'PINNED_RI223_SOURCE_REQUIRED'}
    archive_hash, xml_hash, version = pins[number]
    try:
        filename = metadata['archive_stored_name']
        if not isinstance(filename,str) or Path(filename).name != filename or not filename.endswith('.zip'):
            raise ValueError('unsafe archive')
        archive = checked_original_input_path(run/'input',filename)
        if _digest(archive,MAX_ARCHIVE_BYTES) != archive_hash:
            raise ValueError('archive changed')
        payload = parse_ri223_archive(archive,number).raw_payload
        proof = payload['evidence']
        member = proof['xml_member']
        if (proof['archive_sha256'],proof['xml_sha256'],payload['notice_version']) != (archive_hash,xml_hash,version):
            raise ValueError('selected revision mismatch')
        records = [f for f in metadata['files'] if isinstance(f,dict) and f.get('original_name') == member and f.get('extension') == '.xml']
        if len(records)!=1 or not isinstance(records[0].get('file_id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',records[0]['file_id']):
            raise ValueError('source file ambiguous')
        record=records[0]
        if sum(isinstance(f,dict) and f.get('file_id')==record['file_id'] for f in metadata['files'])!=1:
            raise ValueError('duplicate file identity')
        file=checked_original_input_path(run/'input',record['stored_name'])
        if _digest(file,MAX_XML_BYTES)!=xml_hash:
            raise ValueError('saved XML changed')
        with zipfile.ZipFile(archive) as z:
            raw=z.read(member)
        if hashlib.sha256(raw).hexdigest()!=xml_hash:
            raise ValueError('archive XML changed')
        root=_data_root(ET.fromstring(raw),'purchaseNotice','purchaseNoticeData')
        fields = {}
        cites = []

        def literal(key, value, locator):
            if not isinstance(value,str) or not 0<len(value)<=1200 or any(ord(c)<32 for c in value):
                return
            fields[key]=value
            cites.append({'source_ref':f'ri223-xml:{xml_hash}:{key}', 'file_id':record['file_id'],
                          'document':member,'locator':'XML:'+BASE+locator,'excerpt':value,
                          'source_sha256':xml_hash,'archive_sha256':archive_hash})

        literal('subject',_text(root,'name'),'/name')
        literal('method',_text(root,'purchaseCodeName'),'/purchaseCodeName')
        literal('archived_submission_deadline',_text(root,'submissionCloseDateTime'),'/submissionCloseDateTime')
        lots=payload['lots']
        # Never combine multi-lot prices or treat them as the whole procurement price.
        if len(lots)==1:
            lot=lots[0]
            amount=lot['initial_sum']
            currency=lot['currency_code']
            if isinstance(amount,str) and re.fullmatch(r'[0-9]{1,15}(?:\.[0-9]{1,2})?',amount) and currency=='RUB':
                literal('single_lot_initial_sum',amount,'/lots/lot[1]/lotData/initialSum')
                literal('single_lot_currency',currency,'/lots/lot[1]/lotData/currency/code')
        if not cites or _digest(archive,MAX_ARCHIVE_BYTES)!=archive_hash:
            raise ValueError('no verified fields')
        return {**result,'status':'PINNED_RI223_ARCHIVED_NOTICE','fields':fields,'citations':cites,
                'observed_version':version,'lot_count':len(lots),'protocols_observed':bool(payload['protocols']),
                'source_document_reference_count':payload['source_document_reference_count'],
                'actual_security_requirement':None,'bid_status':None}
    except (OSError,ValueError,KeyError,TypeError,IndexError,ET.ParseError,zipfile.BadZipFile,Ri223EvidenceError):
        return {**result,'reason':'RI223_PIN_OR_SOURCE_MISMATCH'}
