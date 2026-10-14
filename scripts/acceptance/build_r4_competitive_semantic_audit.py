"""Reproduce twenty first-party historical competitive EIS original reviews.

Read-only private pinned input originals; separate customer prose and internal
machine evidence. No current procurement status, legal eligibility or GO.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

from src.modules.tender_operator_agent_demo.r4_additional_original_claims import (
    audit_additional_sources,
)
from src.modules.tender_operator_agent_demo.r4_all_original_text_coverage import (
    verify_all_96_original_texts,
)
from src.modules.tender_operator_agent_demo.r4_archived_notice_attachment_coverage import (
    verify_attachment_coverage,
)
from src.modules.tender_operator_agent_demo.r4_material_condition_triage import (
    source_bound_triage,
)
from src.modules.tender_operator_agent_demo.r4_new_original_material_leads import (
    validate_clause_leads_against_official_attachments,
    verify_material_clause_leads,
)
from src.modules.tender_operator_agent_demo.r4_official_competitive_cohort import (
    validate_cohort,
    verify_original_notice,
)
from src.modules.tender_operator_agent_demo.r4_original_claim_audit import (
    audit_claims,
    index_binary_receipts,
)
from src.modules.tender_operator_agent_demo.r4_saved_report_deadline_audit import (
    audit_saved_decisions,
)

_PINS={
    "selection":"93f72ba5127f21c9b7744688da2b375d80779a49d64243155e6657ff4d436da1",
    "claims":"eb30969ac4bd421094a09573119e3710962ead7649c3bbe2fe72e579e257bd2e",
    "binaries":"4f453e12c0013a200422990bf65a96fdfc476be6eda2b69065d18115391d9822",
}


def _pinned(path:Path,pin:str)->dict:
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pin:
        raise ValueError("historical source proof is not byte-identical to pinned original")
    return json.loads(raw)


def build_review(originals:Path)->dict:
    ai=originals/"ai-expert-20261012"
    selected=_pinned(
        ai/"positive-eis-replacements-20261012/verified-competitive-20-plus-four-negative.json",
        _PINS["selection"],
    )
    expert=_pinned(ai/"rdc-expert-packet-20261012.json",_PINS["claims"])
    filestore=_pinned(originals/"independent-20261012/official-filestore-72-attachment-audit.json",_PINS["binaries"])
    cohort=validate_cohort(selected)
    official=[]
    for item in selected["positive_cases"]:
        base=(
            ai/"positive-eis-replacements-20261012"
            if item["role"]=="NEW_OFFICIAL_POSITIVE_REPLACEMENT"
            else originals/"independent-20261012"
        )
        packet=verify_original_notice(item,base/item["reg_number"]/"documentation-archive.zip")
        packet["source_class"]="COMPETITIVE_HISTORIC_ORIGINAL"
        official.append(packet)
    special=next(i for i in selected["negative_cases"] if i.get("notice"))
    negative_archive=verify_original_notice(
        special,originals/"independent-20261012"/special["reg_number"]/"documentation-archive.zip"
    )
    source_binary=index_binary_receipts(filestore)
    claims=audit_claims(
        expert,ai/"tender_operator_demo",source_binary,
        {item["reg_number"] for item in selected["positive_cases"]},
    )
    negatives=[{"registry_number":n["reg_number"],
                "reason":n["noncompetitive_reason"],
                "bid_ready":False} for n in selected["negative_cases"]]
    new_documents=audit_additional_sources(originals)
    full_attachment_coverage=verify_attachment_coverage(selected,originals)
    full_text_coverage=verify_all_96_original_texts(
        root=originals,
        attachment_inventory=full_attachment_coverage,
        additional_document_audit=new_documents,
    )
    material_leads=verify_material_clause_leads(
        ai/"competitive-25-original-text-20261014"
    )
    clause_original_link=validate_clause_leads_against_official_attachments(
        material_leads,full_attachment_coverage
    )
    all_original_topic_triage=source_bound_triage(originals,full_attachment_coverage)
    previous_deadlines=audit_saved_decisions(
        expert["cases"],official,ai/"tender_operator_demo"
    )
    report={
        "scope":"HISTORIC_FIRST_PARTY_OFFICIAL_20_COMPETITIVE_4_NEGATIVE_NOT_LIVE",
        "methodology":"Original ZIP and notice XML exact SHA+type; historic model source quotes only; legal interpretation not attested",
        "source_cohort":cohort,
        "official_source_verified":len(official)+1,
        "competitive_notices":sorted(official,key=lambda v:v["registry_number"]),
        "special_noncompetitive_original":negative_archive,
        "negative_controls":sorted(negatives,key=lambda v:v["registry_number"]),
        "separate_official_reserve":selected["reserve_case"]["reg_number"],
        "saved_model_claims":claims,
        "additional_four_cases_and_21_original_binaries":new_documents,
        "selected_original_notice_attachment_coverage":full_attachment_coverage,
        "selected_original_notice_text_availability":full_text_coverage,
        "historical_model_report_deadline_audit":previous_deadlines,
        "first_party_new_contract_clause_leads":material_leads,
        "all_original_material_condition_triage":all_original_topic_triage,
        "material_clause_verified_notice_provenance":clause_original_link,
        "all_saved_model_claims_checked":(
            claims["claims"] + new_documents["model_claims_checked"]
        ),
        "current_official_EIS_state_verified":False,
        "full_contract_semantic_review_signed":0,
        "human_gold_review_signed":0,
        "bid_ready":False,
    }
    return report



def _readable_archived_deadline(value: str | None) -> str:
    """Show a document's recorded local time, never a raw machine timestamp."""
    if not value:
        return "В архиве не подтверждён"
    parsed = datetime.fromisoformat(value)
    offset = parsed.utcoffset()
    if offset is None:
        raise ValueError("official source date lacks timezone")
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    zone = "МСК" if total_minutes == 180 else f"UTC{sign}{hours:02d}:{minutes:02d}"
    return parsed.strftime("%d.%m.%Y, %H:%M") + f" ({zone})"


def readable_review(review:dict)->str:
    items=review["competitive_notices"]
    claim_map={c["registry_number"]:c for c in review["saved_model_claims"]["cases"]}
    new_claims=review["additional_four_cases_and_21_original_binaries"]
    deadline_review=review["historical_model_report_deadline_audit"]
    attachment_coverage=review["selected_original_notice_attachment_coverage"]
    text_coverage=review["selected_original_notice_text_availability"]
    attachments_per_case={
        row["registry_number"]:row for row in attachment_coverage["cases"]
    }

    additional_ids={
        v["registry_number"] for v in new_claims["claim_checks"]
    }

    lines=[
        "# Независимая проверка 20 конкурентных закупок по документам ЕИС",
        "",
        ("**Основа:** ранее сохранённые оригиналы официальных извещений и отдельные исходные вложения. "
        "Проверены целостность документов, вид процедуры и буквальная доказательная опора сохранённых цитат. "
        "Это анализ архивных редакций, не подтверждение действующего приёма заявок."),
        "",
        "## Существенные результаты",
        "",
        ("- Из исходной выборки исключены три запроса ценовой информации и одна специальная закупка у единственного поставщика. "
        "Для полноценной двадцатки добавлены четыре независимо подтверждённых конкурентных извещения ЕИС."),
        ("- Исходные архивы и тексты извещений проверены по контрольным суммам для всех 20 конкурентных процедур, "
        "а также отдельно для специальной закупки."),
        (
            f"- Проверены {attachment_coverage['source_shas_attested']} из "
            f"{attachment_coverage['notice_attachment_references']} исходных приложений "
            "в выбранных исторических редакциях извещений. "
            "Подтверждены контрольные суммы и размеры файлов; правовой смысл "
            "и нынешняя редакция ЕИС проверяются отдельно."
        ),
        (
            f"- Для {text_coverage['attachments_with_nonempty_source_text']} из "
            f"{text_coverage['archived_original_attachments']} приложений выбранных архивных редакций "
            "имеется непустое текстовое представление, связанное с оригинальным файлом по контрольной сумме. "
            "Полнота таблиц, формул, сканов и юридических условий при этом не подтверждена."
        ),
        ("- Наличие цитаты в тексте ещё не доказывает правильность юридического вывода модели. "
        "Поэтому ни одна процедура не получила автоматического разрешения на участие."),
        "",
        "## По каждой конкурентной процедуре",
        "",
        "| № | Номер извещения | Предмет | Процедура | Документы по архиву | Архивная редакция | Срок по архиву | Доказательность цитат |",
        "|---:|---|---|---|---:|---:|---|---|",
    ]
    methods={
        "COMPETITIVE_ELECTRONIC_AUCTION":"Электронный аукцион",
        "COMPETITIVE_ELECTRONIC_QUOTATIONS":"Электронный запрос котировок",
        "COMPETITIVE_OPEN_ELECTRONIC_COMPETITION":"Открытый конкурс в электронной форме",
    }
    for i,case in enumerate(items,1):
        n=case["registry_number"]
        saved=claim_map.get(n)
        state=(
            "Выборочные цитаты сверены; полный анализ договора и ТЗ ещё требуется"
            if saved or n in additional_ids else
            "Нет проверенной подборки цитат по полному комплекту документов"
        )
        deadline=_readable_archived_deadline(case["archived_submission_end"])
        subject=" ".join(str(case.get("original_purchase_object") or "").split())
        subject=subject.replace("|","—")
        if len(subject)>115:
            subject=subject[:112].rstrip()+"…"
        if not subject:
            subject="Предмет требует уточнения по документам"
        docs=attachments_per_case.get(n)
        if not docs or docs["first_party_sha_verified"]!=docs["required_original_attachments"]:
            raise ValueError("client report cannot claim all procurement documents verified")
        docs_label=f"{docs['first_party_sha_verified']}/{docs['required_original_attachments']}"
        lines.append(
            f"| {i} | {n} | {subject} | {methods[case['method']]} | {docs_label} | {case['archived_version']} | {deadline} | {state} |"
        )
    clause_review=review["first_party_new_contract_clause_leads"]
    lines.extend([
        "",
        "## Существенные условия, обнаруженные в восстановленных документах",
        "",
        (
            f"Во всех {clause_review['source_original_attachments_with_text']} дополнительно восстановленных документах "
            f"извлечён текст, а в {clause_review['procurements_with_early_clause_leads']} закупках "
            f"найдено {clause_review['independently_located_clause_leads']} конкретных фрагментов, "
            "требующих отдельной правовой и технической оценки."
        ),
        "",
        "| Номер извещения | Вопрос для проверки | Документ и место | Фрагмент исходного текста |",
        "|---|---|---|---|",
    ])
    for clause in clause_review["leads"]:
        filename=clause["original_document_name"].replace("|", "—")
        excerpt=clause["literal_quote"].replace("|", "—")
        anchor=clause["evidence_locator"]
        lines.append(
            f"| {clause['registry_number']} | {clause['review_subject']} "
            f"({clause['question_category']}) | {filename}, {anchor} | «{excerpt}» |"
        )
    lines.extend([
        "",
        ("Здесь приведены проверенные цитаты и вопросы для оценки, а не юридические выводы: "
         "нельзя считать наличие лицензии, права на платформу, требования к безопасности или электронному "
         "подписанию основанием для отклонения без изучения полного ТЗ, договора и применимых правил."),
        ("Выполнена только первая выборочная проверка условий восстановленных 25 приложений; "
         "остальные документы корпуса не получили исчерпывающей независимой семантической оценки."),
    ])
    all_review=review["all_original_material_condition_triage"]
    flags=all_review["context_flag_totals"]
    occurrence_audit=all_review["all_topic_mentions_scan"]
    lines.extend([
        "",
        "## Тематическая проверка остальных оригиналов: вопросы для эксперта",
        "",
        (f"По {all_review['original_attachments_with_source_matched_text']} оригинальным "
         f"приложениям из {all_review['case_count']} закупок автоматически проверены "
         "текстовые признаки финансовых, договорных, правовых и технических условий. "
         "Это только указатель, где читать исходные документы; наличие или отсутствие "
         "слов не подтверждает применимость условия. Проверено лишь первое "
         "вхождение каждой из восьми тем в каждом текстовом представлении — "
         "это не исчерпывающая проверка всех пунктов договоров."),
        (f"Дополнительный проход нашёл {occurrence_audit['total_pattern_occurrences']} "
         f"вхождений этих восьми фиксированных текстовых шаблонов, из них "
         f"{occurrence_audit['additional_pattern_occurrences']} не попадали "
         "в прежнюю подборку первых упоминаний. Эти вхождения также не "
         "удостоверяют полноту обязательств, таблиц или юридическую применимость."),
        (f"Контекстная разметка: {flags.get('NEGATION_CUE_NEAR_MENTION', 0)} "
         "упоминания с признаком отрицания поблизости, "
         f"{flags.get('POSSIBLE_HEADING_OR_TABLE_LABEL', 0)} — возможные заголовки "
         "или метки, "
         f"{flags.get('OBLIGATION_VERB_NEAR_MENTION', 0)} — рядом с глаголами "
         "обязательства, "
         f"{flags.get('CONTEXT_UNCERTAIN', 0)} — не классифицированы. "
         "Это автоматические признаки контекста, а не подтверждённые "
         "юридические обязанности или освобождения от них."),
        "",
        "| Номер извещения | Исходные документы | Первые ориентиры | Все вхождения шаблонов | Дополнительно | Возможные отрицания | Заголовки/метки | Приоритетные темы для проверки |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ])
    for case in all_review["cases"]:
        lines.append(
            f"| {case['registry_number']} | {case['source_documents_read']} | "
            f"{case['literal_topic_leads']} | {case['all_pattern_occurrences']} | "
            f"{case['previously_unreported_additional_occurrences']} | "
            f"{case['negation_cue_leads']} | "
            f"{case['heading_like_leads']} | "
            f"{'; '.join(case['top_review_topics']) or 'Полное чтение оригиналов'} |"
        )
    lines.extend([
        "",
        ("Тематические ориентиры привязаны к исходным документам и местам в тексте "
         "в отдельной технической ведомости. Они могут встречаться в заголовках, "
         "отрицаниях и неприменимых разделах; отсутствие ориентира также не доказывает "
         "отсутствие требования. Рядом со словами о требованиях дополнительно выделены "
         "возможные отрицания и короткие заголовки, чтобы не принимать их за "
         "обязательства. Эти признаки не заменяют юридическую оценку."),
    ])
    further=occurrence_audit["one_additional_original_locator_per_case"]
    lines.extend([
        "",
        "### Дополнительные проверяемые места в документах",
        "",
        ("Для каждой из 20 конкурентных закупок выбран один дополнительный "
         "фрагмент из последующих вхождений, отсутствовавших в первичной подборке. "
         "Привязка проверена к исходному приложению архивной редакции. "
         "Это темы для чтения всего пункта договора или ТЗ, а не доказанные "
         "требования, запреты или основания для участия."),
        "",
        "| Номер извещения | Тема для проверки | Исходное приложение и место | Дословные слова |",
        "|---|---|---|---|",
    ])
    for item in further:
        lines.append(
            f"| {item['registry_number']} | {item['review_topic']} | "
            f"{item['original_filename'].replace('|', '—')}, {item['source_locator']} | "
            f"«{item['literal_text'].replace('|', '—')}» |"
        )
    lines.extend([
        "",
        ("Дословные слова приведены для навигации по оригиналу, не вместо "
         "самого положения. Прежде чем оценивать юридические последствия, "
         "эксперт должен прочитать связанные пункты, приложения и актуальную "
         "редакцию извещения."),
    ])
    licensed=occurrence_audit["license_context_role_clarifications"]
    lines.extend([
        "",
        "### Проверка роли упоминаний лицензий",
        "",
        ("В пяти оригинальных документах повторно проверено, о чьей именно "
         "лицензии говорится. Такое различение предотвращает ошибочное "
         "перенесение требований к банку-гаранту или условиям ПО на "
         "квалификацию самого участника. Никакое из этих условий не "
         "утверждено как юридическое основание для участия либо отказа."),
        "",
        "| Номер извещения | Проверяемый контекст | Оригинальный документ и место | Проверенные слова |",
        "|---|---|---|---|",
    ])
    for item in licensed:
        lines.append(
            f"| {item['registry_number']} | {item['source_question']} | "
            f"{item['original_filename'].replace('|', '—')}, {item['source_locator']} | "
            f"«{item['exact_original_words'].replace('|', '—')}» |"
        )
    lines.extend([
        "",
        ("Особого юридического внимания требует формулировка "
         "про лицензию исполнителя в закупке 0349100009326000005. "
         "Её обязательность для допуска, возможность соисполнения и "
         "соответствие правилам закупки не подтверждены экспертным заключением."),
    ])
    contrasted=all_review["cross_document_original_scope_review"]
    lines.extend([
        "",
        "### Несовпадение формулировок между договором, ТЗ и заявкой",
        "",
        (f"В {contrasted['case_count']} архивных конкурентных закупках вручную выбраны, а затем "
         "побайтово перепроверены по исходным приложениям короткие точные "
         "фрагменты с различиями в формулировке субъекта обязанности либо "
         "документа, подтверждающего право. Расхождение текста не означает "
         "незаконности условия и не подтверждает основания для отклонения заявки."),
        "",
        "| Номер извещения | Вопрос для эксперта | Связанные исходные доказательства |",
        "|---|---|---|",
    ])
    for item in contrasted["cases"]:
        evidence = "; ".join(
            f"{s['original_filename'].replace('|', '—')}, {s['source_locator']}: "
            f"«{s['exact_archival_quote'].replace('|', '—').replace(chr(9), ' ')}»"
            for s in item["archival_source_excerpts"]
        )
        lines.append(
            f"| {item['registry_number']} | {item['scope_question'].replace('|', '—')} "
            f"| {evidence} |"
        )
    lines.extend([
        "",
        ("Для любого окончательного заключения требуются чтение полного пункта, "
         "проверка актуальной редакции ЕИС, профильные нормы права и "
         "подтверждение квалифицированного эксперта. Подписанных решений нет."),
    ])
    negated_examples=all_review["manually_rechecked_archival_nonrequirement_wording"]
    lines.extend([
        "",
        "### Буквально сверенные условия с отрицательной формулировкой",
        "",
        ("Три коротких фрагмента повторно прочитаны в исходных архивных "
         "документах. Это дословный текст и адрес, но его действие в актуальной "
         "редакции договора ещё не подтверждено."),
        "",
        "| Номер извещения | Тема | Источник | Точный текст архивного документа |",
        "|---|---|---|---|",
    ])
    for e in negated_examples:
        lines.append(
            f"| {e['registry_number']} | {e['review_topic']} | "
            f"{e['original_filename'].replace('|', '—')}, {e['source_locator']} | "
            f"«{e['archived_quote'].replace('|', '—')}» |"
        )
    lines.extend([
        "",
        ("Также обнаружен ложный соседний сигнал: в извещении "
         "0377100005726000128 фраза «не требуется» относится к "
         "очному присутствию, а не к сдаче и приёмке работ. "
         "Контекстный фильтр разделяет эти предложения, "
         "чтобы не делать ошибочный вывод об отмене приёмки."),
    ])
    saved=review["saved_model_claims"]
    lines.extend([
        "",
        "## Проверка цитат и вывода модели",
        "",
        (
            f"В десяти исходных модельных запусках проверены {saved['claims']} цитат: "
            f"{saved['literal_official_originals']} дословно совпадают с текстом исходного файла, "
            f"{saved['whitespace_variant_official_originals']} совпадают после восстановления пробелов и переносов строк, "
            f"{saved['unsubstantiated_literal_quotes']} цитата требует исправления."
        ),
        (
            f"В четырёх дополнительных модельных запусках сверены {new_claims['model_claims_checked']} цитата "
            f"по {new_claims['original_binaries_sha_verified']} скачанному с ЕИС приложению: "
            f"{new_claims['model_claims_exact_source_quotes']} дословных совпадений, "
            f"{new_claims['claims_requiring_quote_correction']} цитата требует замены, "
            f"{new_claims['claims_breaching_quote_length_policy']} цитаты длиннее установленного лимита; "
            f"{new_claims['model_batches_exceeding_claim_count_cap']} ответа превысили ограничение на количество утверждений."
        ),
        "",
        ("Требуют отдельного исправления цитаты по закупкам 0376300000126000193 и 0162200011826003089. "
         "Три других расхождения в ранних отчётах сводятся к пробелам и переносам, но должны отображаться как текст документа, а не как выдуманная дословная цитата."),
        "",
        ("Даже при точной цитате смысл нормы договора и применимость требования к участнику требуют отдельной проверки. "
         "Подписанных юридических заключений по этой выборке нет."),
        "",
        (
            f"При повторной сверке {deadline_review['saved_reports_verified']} сохранённых пользовательских отчётов "
            f"найдены {deadline_review['date_conflict_count']} противоречия относительно официальной архивной редакции. "
            f"{deadline_review['unattested_strong_blocker_decisions']} прежних выводов о якобы подтверждённом жёстком "
            "препятствии не имеют независимого юридического утверждения и не должны автоматически использоваться "
            "для решения об участии."
        ),
    ])
    lines.extend([
        "",
        "## Выявленные ограничения и необходимые проверки",
        "",
        ("- Даты в таблице относятся исключительно к сохранённым архивам. "
        "У двух старых модельных отчётов сроки подачи противоречили позднейшей архивной редакции "
        "(0158300034526000388 и 0348100024426000039). До новой проверки ЕИС сроки нельзя использовать."),
        ("- Для части закупок отдельные DOC/DOCX/PDF не входят в ZIP извещения. "
        "Контрольная сумма XML не заменяет проверку исходного проекта контракта и полного ТЗ."),
        ("- Проверка буквального совпадения фрагмента с документом не устанавливает, что вывод о гарантиях, "
        "ответственности, лицензиях, трудоёмкости или допускающих условиях юридически корректен."),
        ("- Для каждой закупки необходимы актуальная официальная редакция, полный набор документов, "
        "проверка существенных условий договора и независимое утверждение экспертного заключения."),
        "",
        "## Записи, исключённые из конкурентной выборки",
        "",
        "- 0148300050426000047 — официальный запрос ценовой информации.",
        "- 0318200087026000163 — официальный запрос ценовой информации.",
        "- 0348100024426000052 — официальный запрос ценовой информации.",
        "- 0349500000226000003 — специальная закупка у единственного поставщика.",
        "",
        ("**Итог:** исторический источник проверен. Юридическая готовность, право участия, актуальный срок "
        "подачи заявок и коммерческое решение не удостоверены ни для одной из 20 процедур."),
        "",
    ])
    text="\n".join(lines)
    for forbidden in ("no_data","getDocsIP","Traceback","UNKNOWN/DEFER","HTTP 409","fallback_deterministic_adapter"):
        if forbidden in text:
            raise ValueError("technical diagnostics present in customer source review")
    return text


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--source-root",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args()
    packet=build_review(args.source_root)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/"r4-20-competitive-original-source-audit.json").write_text(
        json.dumps(packet,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf8"
    )
    (args.output_dir/"r4-20-competitive-independent-client-review.md").write_text(
        readable_review(packet),encoding="utf8"
    )
    print(json.dumps({"official_verified":packet["official_source_verified"],
        "competitive":packet["source_cohort"]["competitive"],
        "negative":packet["source_cohort"]["negative"],
        "claim_checks":packet["all_saved_model_claims_checked"],
        "human_signed":packet["human_gold_review_signed"]},sort_keys=True))


if __name__=="__main__":
    main()
