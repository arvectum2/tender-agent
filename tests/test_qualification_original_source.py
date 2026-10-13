"""Original EIS ZIP / scoring DOCX extraction must be fail-closed and source-bound."""
from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import date
from xml.sax.saxutils import escape

import pytest

from src.modules.company_profile_store.qualification_original_source import (
    OriginalScoringEvidence,
    extract_official_qualification_criterion,
)
from src.modules.company_profile_store.qualification_references import (
    CompletedContractReferenceSnapshot,
    assess_references,
)

REG = "0348100024426000039"
UID = "01A0F10655C27A35B5A5A70090D2BB1A"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
RULE = (
    "Требования к документам для оценки показателя: Наличие исполненного "
    "договора на выполнение работ по разработке и (или) модернизации сайтов, "
    "веб-порталов, информационных систем либо их отдельных модулей, в состав "
    "которых входили работы по модификации чат-бота. Последний акт, "
    "составленный при исполнении договора, должен быть подписан не ранее чем "
    "за 5 лет до даты окончания срока подачи заявок; "
    "к оценке принимаются исполненные договоры № 44-ФЗ и № 223-ФЗ; "
    "договоры, являющиеся незавершенными, не подлежат оценке."
)


def _zip(items: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        for key, value in items.items():
            z.writestr(key, value)
    return output.getvalue()


def _docx_xml_row(cells: list[str]) -> str:
    return "<w:tr>" + "".join(
        "<w:tc><w:p><w:r><w:t>" + escape(x) + "</w:t></w:r></w:p></w:tc>"
        for x in cells
    ) + "</w:tr>"


def _docx(*, price="30,00", qualification="70,00", rule=RULE,
          extra_scoring_row=False, duplicate_table=False) -> bytes:
    score = [
        ["N", "Критерий оценки", "Значимость критерия оценки, процентов"],
        ["1", "Цена контракта, сумма цен единиц товара", price],
        ["4", "Квалификация участников закупки, наличие опыта работы", qualification],
    ]
    if extra_scoring_row:
        score.append(["5", "Затраты на эксплуатацию", "0,00"])
    detail = [
        ["№", "Наименование критерия", "Положение"],
        ["4.1.1", "Детализирующий показатель Общее количество исполненных участником закупки договоров", rule],
    ]
    tables = "".join(
        "<w:tbl>" + "".join(_docx_xml_row(row) for row in table) + "</w:tbl>"
        for table in ([score, detail, score] if duplicate_table else [score, detail])
    )
    xml = ('<?xml version="1.0"?>'
           '<w:document xmlns:w="' + W + '"><w:body>' + tables
           + '</w:body></w:document>').encode()
    return _zip({
        "[Content_Types].xml": b"<Types/>",
        "word/document.xml": xml,
    })


def _notice(*, version: int, doc_bytes: bytes, uid=UID, deadline="2026-10-23T10:00:00+03:00",
            reg=REG) -> bytes:
    return (
        "<x><epNotificationEOK2020>"
        f"<purchaseNumber>{escape(reg)}</purchaseNumber>"
        f"<versionNumber>{version}</versionNumber>"
        f"<endDT>{escape(deadline)}</endDT>"
        "<attachmentInfo>"
        f"<publishedContentId>{escape(uid)}</publishedContentId>"
        "<fileName>07-060577-26.docx</fileName>"
        f"<fileSize>{len(doc_bytes)}</fileSize>"
        f"<url>https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid={escape(uid)}</url>"
        "</attachmentInfo></epNotificationEOK2020></x>"
    ).encode()


def _evidence(*, doc=None, versions=(1, 4), uid=UID, deadline="2026-10-23T10:00:00+03:00",
              reg=REG, source_archive=None):
    doc = doc if doc is not None else _docx()
    latest = _notice(version=max(versions), doc_bytes=doc, uid=uid, deadline=deadline, reg=reg)
    original = source_archive if source_archive is not None else _zip({
        f"epNotificationEOK2020_{version}.xml":
            latest if version == max(versions) else _notice(version=version, doc_bytes=doc)
        for version in versions
    })
    receipt = OriginalScoringEvidence(
        schema_version="eis-original-scoring-receipt-v1",
        procurement_number=REG,
        procurement_law="44fz",
        notice_version=4,
        original_soap_archive_sha256=hashlib.sha256(original).hexdigest(),
        original_notice_xml_sha256=hashlib.sha256(latest).hexdigest(),
        scoring_document_uid=UID,
        scoring_document_sha256=hashlib.sha256(doc).hexdigest(),
    )
    return original, doc, receipt


def _extract(archive, doc, receipt):
    return extract_official_qualification_criterion(
        original_archive_bytes=archive,
        original_scoring_docx_bytes=doc,
        trusted_receipt=receipt,
        analysis_date=date(2026, 10, 13),
    )


def test_actual_table_semantics_are_extracted_without_user_entered_weights():
    archive, doc, receipt = _evidence()
    criterion = _extract(archive, doc, receipt)
    assert criterion.procurement_number == REG
    assert criterion.price_weight_percent == 30
    assert criterion.qualification_weight_percent == 70
    assert criterion.requires_chatbot is True
    assert criterion.accepted_contract_laws == ["44fz", "223fz"]
    assert criterion.lookback_years == 5
    assert criterion.application_deadline_date == date(2026, 10, 23)
    assert criterion.source_document_sha256 == hashlib.sha256(doc).hexdigest()
    owner = CompletedContractReferenceSnapshot(
        schema_version="completed-contract-references-v1",
        as_of_date=date(2026, 10, 13),
        owner_confirmed=True, completeness="COMPLETE", contracts=[],
    )
    assessment = assess_references(customer_id="tenant-a", criterion=criterion, snapshot=owner)
    assert assessment.recommendation == "NO_GO_QUALIFICATION_COMPETITIVENESS"
    assert assessment.eligibility_status == "NOT_ASSESSED"
    assert assessment.external_action_allowed is False


@pytest.mark.parametrize("alter", [
    {"price": "40,00"},  # weights don't sum
    {"price": "30,55"},  # unsupported fractional weight
    {"qualification": "unknown"},
    {"rule": RULE.replace("чат-бота", "телеграм-бота")},
    {"rule": RULE.replace("44-ФЗ", "22-ФЗ")},
    {"rule": RULE.replace("за 5 лет", "за неопределённый срок")},
    {"rule": RULE.replace("незавершенными", "готовыми")},
    {"extra_scoring_row": True},
    {"duplicate_table": True},
])
def test_conflicting_or_unsupported_scoring_docx_must_abstain(alter):
    archive, doc, receipt = _evidence(doc=_docx(**alter))
    with pytest.raises(ValueError):
        _extract(archive, doc, receipt)


def test_scoring_docx_mutation_rejected_even_when_embedded_in_xml_unchanged():
    archive, doc, receipt = _evidence()
    with pytest.raises(ValueError, match="checksum"):
        _extract(archive, doc + b"mutation", receipt)


def test_original_eis_soap_archive_mutation_rejected():
    archive, doc, receipt = _evidence()
    with pytest.raises(ValueError, match="checksum"):
        _extract(archive + b"mutation", doc, receipt)


def test_stale_original_eis_edition_v3_rejected_even_if_receipt_reissued():
    archive, doc, receipt = _evidence(versions=(1, 3))
    with pytest.raises(ValueError, match="stale/unknown"):
        _extract(archive, doc, receipt)


def test_original_scoring_docx_uid_absent_in_latest_notice_rejected():
    archive, doc, receipt = _evidence(uid="A" * 32)
    with pytest.raises(ValueError, match="UID absent"):
        _extract(archive, doc, receipt)


def test_original_eis_attachment_untrusted_url_rejected():
    doc = _docx()
    original = _notice(version=4, doc_bytes=doc).replace(
        b"https://zakupki.gov.ru/",
        b"https://other.invalid/",
    )
    archive = _zip({"epNotificationEOK2020_4.xml": original})
    _, _, receipt = _evidence(doc=doc, source_archive=archive)
    # Even when the receipt separately attests the mutant XML digest, the
    # official attachment host must remain allowed.
    receipt = receipt.model_copy(update={
        "original_notice_xml_sha256": hashlib.sha256(original).hexdigest(),
    })
    with pytest.raises(ValueError, match="HTTPS source URL"):
        _extract(archive, doc, receipt)


def test_original_deadline_without_moscow_timezone_rejected():
    archive, doc, receipt = _evidence(deadline="2026-10-23T07:00:00+00:00")
    with pytest.raises(ValueError, match="MSK"):
        _extract(archive, doc, receipt)


def test_original_soap_archive_with_path_traversal_rejected():
    doc = _docx()
    notice = _notice(version=4, doc_bytes=doc)
    archive = _zip({"../epNotificationEOK2020.xml": notice})
    _, _, receipt = _evidence(doc=doc,source_archive=archive)
    with pytest.raises(ValueError, match="Unsafe"):
        _extract(archive, doc, receipt)


def test_dtd_entity_in_original_soap_notice_rejected():
    doc = _docx()
    raw = b'<!DOCTYPE x [<!ENTITY x "boom">]>' + _notice(version=4,doc_bytes=doc)
    archive = _zip({"original.xml": raw})
    _, _, receipt = _evidence(doc=doc,source_archive=archive)
    with pytest.raises(ValueError, match="Unsafe XML"):
        _extract(archive, doc, receipt)


def test_invalid_owner_receipt_uid_and_digest_rejected():
    _, _, receipt = _evidence()
    for attr, wrong in (("scoring_document_uid", "not-uid"),
                        ("scoring_document_sha256", "wrong")):
        with pytest.raises(ValueError):
            OriginalScoringEvidence.model_validate({**receipt.model_dump(),attr:wrong})


def _original_run_fixture(tmp_path, monkeypatch, *, bad_name=False,
                          bad_provenance=False, tampered_archive=False):
    from src.modules.company_profile_store import qualification_run_service as run_service

    archive, doc, receipt = _evidence()
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "official-documentation.zip").write_bytes(
        archive + b"faked" if tampered_archive else archive
    )
    (input_dir / "evaluation.docx").write_bytes(doc)
    run_id = "toa-run-20261013000000-abc123"
    metadata = {
        "procurement_source": "zakupki_gov_ru_getdocs_ip",
        "reestr_number": REG,
        "archive_downloaded": True,
        "getdocs_status": "completed",
        "subsystem_type": "PRIZ",
        "token_owner": "individual",
        "archive_source_host": "int.zakupki.gov.ru",
        "files": [{
            "source_type": "manual_upload" if bad_provenance else "notice_xml_attachments",
            "original_name": "07-060577-26.docx",
            "stored_name": "../unsafe.docx" if bad_name else "evaluation.docx",
            "source_url": (
                "https://zakupki.gov.ru/44fz/filestore/public/1.0/download/"
                f"priz/file.html?uid={UID}"
            ),
        }],
    }
    monkeypatch.setattr(run_service, "load_demo_run_metadata", lambda _: metadata)
    monkeypatch.setattr(run_service, "get_demo_run_input_dir", lambda _: input_dir)
    return run_id, metadata


def test_auto_qualify_official_run_derives_no_go_without_manual_criterion(
    tmp_path, monkeypatch,
):
    from src.modules.company_profile_store.qualification_run_service import (
        discover_run_criterion,
    )

    run_id, _ = _original_run_fixture(tmp_path, monkeypatch)
    c = discover_run_criterion(run_id, analysis_date=date(2026, 10, 13))
    assert c.qualification_weight_percent == 70
    assert c.price_weight_percent == 30
    assert c.accepted_contract_laws == ["44fz", "223fz"]
    assert c.source_document_uid == UID
    assert c.application_deadline_date == date(2026, 10, 23)


@pytest.mark.parametrize("flags", [
    {"bad_name": True},
    {"bad_provenance": True},
    {"tampered_archive": True},
])
def test_auto_run_does_not_trust_manual_or_tampered_originals(
    tmp_path, monkeypatch, flags,
):
    from src.modules.company_profile_store.qualification_run_service import (
        discover_run_criterion,
    )

    run_id, _ = _original_run_fixture(tmp_path, monkeypatch, **flags)
    with pytest.raises(ValueError):
        discover_run_criterion(run_id, analysis_date=date(2026, 10, 13))


def test_auto_run_refuses_mismatched_provenance_or_unsupported_id(
    tmp_path, monkeypatch,
):
    from src.modules.company_profile_store.qualification_run_service import (
        discover_run_criterion,
    )

    run_id, metadata = _original_run_fixture(tmp_path, monkeypatch)
    for key, value in (
        ("archive_source_host", "untrusted.invalid"),
        ("token_owner", "unknown"),
        ("archive_downloaded", False),
        ("getdocs_status", "in_progress"),
        ("procurement_source", "manual_upload"),
    ):
        previous = metadata[key]
        metadata[key] = value
        with pytest.raises(ValueError):
            discover_run_criterion(run_id, analysis_date=date(2026, 10, 13))
        metadata[key] = previous
    with pytest.raises(ValueError, match="run identifier"):
        discover_run_criterion("../other-run", analysis_date=date(2026, 10, 13))


def test_auto_run_different_or_missing_reference_list_is_never_no_go(
    tmp_path, monkeypatch, session,
):
    from src.modules.company_profile_store.qualification_run_service import (
        assess_owned_run_qualification,
    )
    from src.modules.customer_registry.models import CustomerProfile

    run_id, _ = _original_run_fixture(tmp_path, monkeypatch)
    customer = CustomerProfile(
        customer_id="qa-tenant-1", legal_name="ООО проверка", customer_status="PROSPECT"
    )
    session.add(customer)
    session.commit()
    result = assess_owned_run_qualification(
        session, run_id=run_id, customer_id="qa-tenant-1",
        as_of=date(2026, 10, 13),
    )
    assert result["competitive_recommendation"] == "HUMAN_REVIEW_REQUIRED"
    assert result["qualifying_contracts"] is None
    assert result["electronic_signature_validated"] is False
    assert result["external_action_allowed"] is False


def test_auto_run_returns_safe_abstention_when_source_missing(
    tmp_path, monkeypatch, session,
):
    from src.modules.company_profile_store.qualification_run_service import (
        assess_owned_run_qualification,
    )

    run_id, metadata = _original_run_fixture(tmp_path, monkeypatch)
    metadata["files"] = []
    result = assess_owned_run_qualification(
        session, run_id=run_id, customer_id="any",
        as_of=date(2026, 10, 13),
    )
    assert result["source_status"] == "ORIGINAL_SOURCE_UNAVAILABLE_OR_UNSUPPORTED"
    assert result["competitive_recommendation"] == "NOT_ASSESSED"
    assert result["external_action_allowed"] is False
