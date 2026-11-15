"""Read-only archive-derived XML facts for procurement RAG; never invent NMC."""
from __future__ import annotations

import io
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from scripts.procurement_llm import official_eis_xml_context as x
from scripts.procurement_llm.analysis_queue_worker import PinnedSource
from scripts.procurement_llm.prepare_eis_original_documents import (
    SourcePreparationError,
)

NUMBER = "0163200000326005243"
ARCHIVE_SHA = "a" * 64
XML_SHA = "b" * 64


def _xml():
    root = ET.Element("export")
    notice = ET.SubElement(root, "epNotificationEOK2020")
    def node(parts, value):
        n = notice
        for part in parts[:-1]:
            matches = [c for c in n if c.tag == part]
            n = matches[0] if matches else ET.SubElement(n, part)
        ET.SubElement(n, parts[-1]).text = value
    node(("commonInfo","purchaseNumber"),NUMBER)
    node(("commonInfo","purchaseObjectInfo"),"Оказание услуг по изменению сайта Смоленской областной Думы")
    node(("commonInfo","publishDTInEIS"),"2026-10-16T15:29:24+03:00")
    node(("commonInfo","placingWay","name"),"Открытый конкурс в электронной форме")
    node(("commonInfo","ETP","name"),"РТС-тендер")
    node(("notificationInfo","contractConditionsInfo","maxPriceInfo","maxPrice"),"497178.33")
    node(("notificationInfo","procedureInfo","collectingInfo","startDT"),"2026-10-14T17:12:54+03:00")
    node(("notificationInfo","procedureInfo","collectingInfo","endDT"),"2026-10-30T11:00:00+03:00")
    for i in range(14):
        segment=ET.SubElement(notice,"characteristicsUsingTextForm")
        ET.SubElement(segment,"name").text=f"Требование {i}: реализовать адаптивный интерфейс №{i}"
    return ET.tostring(root,encoding="utf-8")


def test_exact_original_nmc_not_qualifications_price():
    fields = x.render_source_facts(
        _xml(), registry_number=NUMBER, xml_sha=XML_SHA,
        archive_sha=ARCHIVE_SHA, revision=2,
    )
    assert "НМЦК РУБ — сумма контракта, НЕ лимит квалификационного опыта: 497178.33" in fields
    assert "Окончание приёма заявок: 2026-10-30T11:00:00+03:00" in fields
    assert sum(t.startswith("Требование ТЗ #") for t in fields)==14
    assert all("15000000" not in item for item in fields)
    assert all("текущ" not in item.lower() for item in fields[7:10])


@pytest.mark.parametrize("wrong", [
    lambda xml: xml.replace(b"497178.33",b""),
    lambda xml: xml.replace(b"497178.33",b"15 million"),
    lambda xml: xml.replace(NUMBER.encode(),b"0163200000326005244"),
    lambda xml: b"<!DOCTYPE a [<!ENTITY x 'attack'>]>" + xml,
    lambda xml: b"<other><junk>none</junk></other>",
])
def test_missing_unparseable_or_wrong_official_fields_fail_closed(wrong):
    with pytest.raises(SourcePreparationError):
        x.render_source_facts(
            wrong(_xml()), registry_number=NUMBER,
            xml_sha=XML_SHA, archive_sha=ARCHIVE_SHA, revision=2,
        )


def test_fact_extraction_does_not_auto_fill_missing_characteristics():
    body = _xml()
    root=ET.fromstring(body)
    for item in list(root.iter()):
        if item.tag == "characteristicsUsingTextForm":
            parent=next(n for n in root.iter() if item in list(n))
            parent.remove(item)
    with pytest.raises(SourcePreparationError,match="characteristics"):
        x.render_source_facts(
            ET.tostring(root), registry_number=NUMBER,
            xml_sha=XML_SHA, archive_sha=ARCHIVE_SHA, revision=2,
        )


def test_derived_docx_has_original_sha_and_complete_requirements(monkeypatch,tmp_path):
    source = PinnedSource("a"*64,NUMBER,"manual:ta-eis-zip:sha",ARCHIVE_SHA,
                          tmp_path/"archive.zip","eis")
    monkeypatch.setattr(x,"attest_source",lambda src,root=None:None)
    monkeypatch.setattr(x,"_selected_notice",lambda src:(
        _xml(),{"notice_xml_sha256":XML_SHA,"source_version":2}))
    a, receipt=x.source_context_blob(source,root=tmp_path)
    b, again=x.source_context_blob(source,root=tmp_path)
    assert a == b and receipt==again
    assert receipt["source_facts"]["НМЦК РУБ — сумма контракта, НЕ лимит квалификационного опыта"]=="497178.33"
    assert receipt["characteristics_included"]==14
    assert receipt["not_original_eis_signed_document"] is True
    with ZipFile(io.BytesIO(a)) as z:
        text=z.read("word/document.xml").decode()
    assert "497178.33" in text
    assert "2026-10-30" in text
    assert "Требование ТЗ #14" in text


def test_xml_path_ambiguity_fails_closed():
    root=ET.fromstring(_xml())
    notice=next(x for x in root if x.tag=="epNotificationEOK2020")
    common=next(x for x in notice if x.tag=="commonInfo")
    ET.SubElement(common,"purchaseNumber").text=NUMBER
    with pytest.raises(SourcePreparationError,match="ambiguous"):
        x.render_source_facts(ET.tostring(root),registry_number=NUMBER,
                              xml_sha=XML_SHA,archive_sha=ARCHIVE_SHA,revision=2)
