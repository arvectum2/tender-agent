"""Source-bound 223-FZ composite scoring must abstain from contract-score NO_GO."""
from __future__ import annotations

import hashlib
import io
import zipfile

import pytest

from src.modules.company_profile_store.qualification_223_observer import (
    observe_ri223_scoring_text,
    verify_ri223_originals,
)

PDF_TEXT = """РАЗДЕЛ 9. МЕТОДИКА ОЦЕНКИ ЗАЯВОК НА УЧАСТИЕ В ЗАКУПКАХ

 1  Стоимостной критерий              40 %        40 баллов
 2  Нестоимостные критерии            60 %        60 баллов
 Всего                                100 %       100 баллов

Нестоимостной критерий формируется из подкритериев.
При оценке нестоимостных подкритериев допускается установление следующего
долевого соотношением между критериями:
2.1      Деловая репутация           20%         20 баллов
2.2      Финансовое состояние        20%         20 баллов
2.3      Квалификация                60%         60 баллов
Всего                                100%        100 баллов
"""


def _archive(members: dict[str, bytes]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for key, value in members.items():
            z.writestr(key, value)
    return out.getvalue()


def _receipt(*, corrupt_url=False, xml_number="32616445795"):
    uid = "E8D018399C8C4BC18A621DCB8CBB6F12"
    url = (
        "https://zakupki.gov.ru/223/filestore/public/1.0/download/"
        f"fz223/file.html?uid={uid}"
    )
    xml = (
        "<purchaseNotice>"
        f"<registrationNumber>{xml_number}</registrationNumber>"
        "<version>1</version>"
        "<attachments><document><fileName>3727_МИ.rar</fileName>"
        f"<contentUid>{uid}</contentUid><url>{url}</url>"
        "</document></attachments>"
        "</purchaseNotice>"
    ).encode()
    member = "purchaseNotice_32616445795_1_original.xml"
    soap = _archive({member: xml})
    rar = b"RAR-ORIGINAL-SYNTHETIC-UNIT-ONLY"
    pdf = b"%PDF-SYNTHETIC-FIXTURE"
    source = {
        "law": "223fz",
        "procurement_number": "32616445795",
        "soap_original_sha256": hashlib.sha256(soap).hexdigest(),
        "soap_notice_member": member,
        "soap_notice_version": 1,
        "original_attachment_name": "3727_МИ.rar",
        "original_attachment_content_uid": uid,
        "original_attachment_url": url + ("&bad=1" if corrupt_url else ""),
        "original_attachment_sha256": hashlib.sha256(rar).hexdigest(),
        "evaluation_pdf_sha256": hashlib.sha256(pdf).hexdigest(),
    }
    return soap, rar, pdf, source


def test_real_style_composite_observation_not_a_reference_list_no_go():
    observation = observe_ri223_scoring_text(PDF_TEXT)
    assert observation["price_weight_percent"] == 40
    assert observation["nonprice_weight_percent"] == 60
    assert observation["candidate_nonprice_subweights"] == {
        "business_reputation": 20,
        "financial_condition": 20,
        "qualification": 60,
    }
    assert observation["supplier_qualification_total_weight_percent"] is None
    assert observation["completed_contracts_weight_percent"] is None
    assert observation["competitive_recommendation"] == "NOT_ASSESSED"
    assert observation["external_action_allowed"] is False
    assert observation["human_gold"] is False


@pytest.mark.parametrize("modification", [
    ("40 %", "50 %"),
    ("60 %        60 баллов", "50 %        50 баллов"),
    ("2.3      Квалификация                60%", "2.3      Квалификация                90%"),
    ("2.1      Деловая репутация           20%", "2.1      Деловая репутация           40%"),
    ("допускается установление", "наше мнение"),
    ("РАЗДЕЛ 9. МЕТОДИКА ОЦЕНКИ", "ПРИЛОЖЕНИЕ 9"),
])
def test_composite_observer_abstains_on_changed_or_unconfirmed_weights(modification):
    with pytest.raises(ValueError):
        observe_ri223_scoring_text(PDF_TEXT.replace(*modification))


def test_missing_or_duplicated_primary_weight_is_unsupported():
    with pytest.raises(ValueError):
        observe_ri223_scoring_text(
            PDF_TEXT + "\n 1  Стоимостной критерий 40 % 40 баллов"
        )


def test_original_223_eis_zip_rar_nested_pdf_are_related_by_uid_and_digests():
    soap, rar, pdf, receipt = _receipt()
    result = verify_ri223_originals(soap, rar, pdf, receipt)
    assert result["procurement_number"] == "32616445795"
    assert result["source_status"] == "ORIGINAL_BYTES_CORRELATED_SIGNATURE_NOT_VERIFIED"


@pytest.mark.parametrize("mutate", ["soap", "rar", "pdf", "uid", "registry", "url"])
def test_source_mutation_or_untrusted_notice_refuses_223_rubric(mutate):
    soap, rar, pdf, receipt = _receipt()
    if mutate == "soap":
        soap += b"x"
    elif mutate == "rar":
        rar += b"x"
    elif mutate == "pdf":
        pdf += b"x"
    elif mutate == "uid":
        receipt["original_attachment_content_uid"] = "A" * 32
    elif mutate == "registry":
        receipt["procurement_number"] = "32616445796"
    elif mutate == "url":
        receipt["original_attachment_url"] += "&bad=1"
    with pytest.raises(ValueError):
        verify_ri223_originals(soap, rar, pdf, receipt)


def test_eis_223_source_different_from_44_fz_root():
    soap, rar, pdf, receipt = _receipt()
    receipt["law"] = "44fz"
    with pytest.raises(ValueError, match="Unsupported"):
        verify_ri223_originals(soap, rar, pdf, receipt)
