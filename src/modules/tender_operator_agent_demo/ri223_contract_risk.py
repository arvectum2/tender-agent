"""Narrow, reviewed historical contract clause observations, not legal advice."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from unicodedata import normalize

from .ri223_attachment_evidence import verified_container_lineage
from .ri223_linked_contract import linked_contract_observation
from .verified_original_quote import verify_operator_run_quote

_NUMBER = '32616445795'
_MEMBER = '3727-МИ/3. Проект договора с приложениями новый.docx'
_SHA = '32d01aa62b786c14db26fba8e600eb7cdea61d6412d0f24253fc3ef004401c05'
# Manually reviewed clause-level mappings, pinned to this exact original only.
_CLAUSES = (
    ('delivery','1.7','ежедневно, кроме субботы и воскресенья, с 08 час. 30 мин. до 17 час. 20 мин.',
     'Проверить доступность персонала в режиме заказчика.'),
    ('subcontract_personal','2.1.2, вариант 1','Оказать Услуги лично, если иное не будет дополнительно согласовано Сторонами.',
     'Вариант проекта; согласовать применимый способ исполнения.'),
    ('subcontract_consent','2.1.2, вариант 2','после получения согласия Заказчика в письменном виде, Исполнитель вправе передать третьему лицу',
     'Не считать привлечение соисполнителей безусловно разрешённым.'),
    ('scope_change','2.3.2','В одностороннем порядке изменять задания, если эти изменения не выходят за пределы содержания и объёма',
     'Проверить границы объёма и процедуру изменения задания.'),
    ('acceptance','3.4','не позднее 10 (десяти) рабочих дней с даты его получения от Исполнителя.',
     'Срок подписания либо мотивированного отказа не равен гарантированной дате приёмки.'),
    ('rework','3.4','Все доработки по мотивированному отказу производятся Исполнителем за свой счёт в срок, указанный Заказчиком.',
     'Заложить затраты на доработки; срок зависит от заказчика.'),
    ('payment','4.3','в течение 7 (семи) рабочих дней с даты подписания Акта об оказании услуг/УПД.',
     'Оплата зависит от подписанного акта; фактический кассовый разрыв неизвестен.'),
    ('losses','5.2','Исполнитель обязан возместить Заказчику все возникшие в связи с этим убытки.',
     'Проверить весь договор на предел ответственности и исключения.'),
    ('delay_penalty','5.3','5.3. За нарушение сроков оказания Услуг, указанных в пункте 1.2 настоящего Договора, Заказчик вправе начислить пени из расчёта 0,1% (Ноль целых одну десятую процента) от цены настоящего Договора за каждый день просрочки.',
     'Расчёт от всей цены договора, а не от просроченного этапа.'),
    ('delay_termination','5.3','При просрочке свыше 10-ти (десяти) календарных дней Заказчик вправе в одностороннем порядке расторгнуть настоящий Договор',
     'Право расторжения, а не автоматическое прекращение.'),
    ('tax_loss','5.5','Заказчик вправе удержать потери из причитающихся Исполнителю платежей по Договору',
     'Проверить налоговую оговорку и условия удержания; применимость неизвестна.'),
    ('assignment','5.6','5.6. В случае передачи Исполнителем права требования без получения согласия от Заказчика (в том числе денежных требований по договорам цессии и факторинга) по настоящему Договору Заказчик вправе потребовать уплаты штрафа в размере 20% от общей цены настоящего Договора.',
     'За уступку без согласия, включая цессию и факторинг; не штраф за просрочку.'),
    ('termination','7.2','Заказчик вправе в любое время в одностороннем порядке отказаться от исполнения настоящего Договора',
     'Проверить инвестиции, фактически понесённые расходы и возможность возмещения.'),
    ('termination_costs','7.2','при условии компенсации Исполнителю фактически понесенных им расходов',
     'Компенсация документально подтверждённых расходов не равна гарантии прибыли.'),
)


def observe_contract_risk(run_id: str, run: Path, metadata: dict, economics: dict) -> dict:
    base={'status':'UNKNOWN','final_contract_verified':False,'legal_conclusion':False,
          'liability_cap_rub':None,'go_eligible':False,'clauses':[],'scenario_exposure':None}
    if metadata.get('procurement_id')!=_NUMBER:
        return base
    candidates=[r for r in metadata['files'] if r.get('source')=='ri223_container_member'
                and normalize('NFC',r.get('ri223_container',{}).get('member_path',''))==normalize('NFC',_MEMBER)]
    if len(candidates)!=1:
        return base
    row=candidates[0]
    lineage=verified_container_lineage(run,metadata,row)
    if not lineage or lineage['member_sha256']!=_SHA:
        return base
    clauses=[]
    for key,section,quote,review_note in _CLAUSES:
        checked=verify_operator_run_quote(run_id=run_id,file_id=row['file_id'],exact_quote=quote)
        ev=checked.get('evidence')
        confirmed=(checked.get('status')=='literal_quote_found_in_extracted_original_only'
                   and isinstance(ev,dict) and ev.get('original_sha256')==_SHA
                   and ev.get('quote')==quote and ev.get('ri223_container')==lineage)
        item={'clause':key,'section':section,'status':'VERIFIED_LITERAL_FRAGMENT' if confirmed else 'UNKNOWN'}
        if confirmed:
            item.update(source=ev,operator_review_note=review_note)
        clauses.append(item)
    verified={row['clause'] for row in clauses if row['status']=='VERIFIED_LITERAL_FRAGMENT'}
    exposures=None
    offer=economics.get('calculation',{}).get('offer_scenario')
    if economics.get('status')=='ARCHIVED_LOT_EXPLICIT_SCENARIO_ONLY' and offer:
        price=Decimal(offer['offer_price_rub'])
        def rub(x):
            return format(x.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP),'f')
        exposures={'status':'HYPOTHETICAL_CLAUSE_EXPOSURE_ONLY','assumed_contract_price_rub':rub(price),
                   'daily_delay_penalty_rub':rub(price*Decimal('0.001')) if 'delay_penalty' in verified else None,
                   'delay_10_days_rub':rub(price*Decimal('0.01')) if 'delay_penalty' in verified else None,
                   'unauthorized_assignment_penalty_rub':rub(price*Decimal('0.20')) if 'assignment' in verified else None,
                   'actual_liability_rub':None,'aggregate_risk_cap_rub':None,
                   'all_sanctions_additive':None}
    return {**base,'status':'ARCHIVED_CONTRACT_CLAUSE_REVIEW_ONLY' if verified else 'UNKNOWN',
            'clauses':clauses,'verified_clause_count':len(verified),
            'linked_conditions':linked_contract_observation(run_id,row['file_id'],lineage,economics,verifier=verify_operator_run_quote),
            'source_lineage':lineage,'scenario_exposure':exposures,
            'subcontract_variant_selected':None,'risk_score':None,
            'current_revision_attested':False,'requires_human_review':True}
