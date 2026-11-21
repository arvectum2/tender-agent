"""Pinned reviewed paragraphs, not a general legal engine."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from .verified_original_quote import verify_operator_run_quote

_SOURCE_SHA = '32d01aa62b786c14db26fba8e600eb7cdea61d6412d0f24253fc3ef004401c05'
_PARAGRAPHS = {'3.4': '3.4. Заказчик подписывает Акт об оказании услуг/УПД услуг или представляет мотивированный '
        'отказ в его подписании не позднее 10 (десяти) рабочих дней с даты его получения от '
        'Исполнителя. Все доработки по мотивированному отказу производятся Исполнителем за свой '
        'счёт в срок, указанный Заказчиком.',
 '4.3': '4.3. Оплата по настоящему Договору производится Заказчиком на основании подписанного '
        'сторонами Акта об оказании услуг/УПД и представленных Исполнителем счёта и счёта-фактуры '
        'путем перечисления денежных средств на расчётный счёт Исполнителя в следующие сроки и '
        'порядке: в течение 7 (семи) рабочих дней с даты подписания Акта об оказании услуг/УПД.',
 '4.4': '4.4. Оплата по Договору производится Заказчиком путём перечисления денежных средств на '
        'расчетный счет Исполнителя. Датой платежа считается дата списания денежных средств с '
        'расчетного счета Заказчика. По соглашению Сторон допускается исполнение обязательств по '
        'оплате в иной форме, не противоречащей действующему законодательству Российской '
        'Федерации.',
 '5.3': '5.3. За нарушение сроков оказания Услуг, указанных в пункте 1.2 настоящего Договора, '
        'Заказчик вправе начислить пени из расчёта 0,1% (Ноль целых одну десятую процента) от цены '
        'настоящего Договора за каждый день просрочки. При просрочке свыше 10-ти (десяти) '
        'календарных дней Заказчик вправе в одностороннем порядке расторгнуть настоящий Договор, '
        'направив Исполнителю соответствующее уведомление. Договор считается расторгнутым по '
        'истечении 15 дней с момента направления такого уведомления в адрес Исполнителя.',
 '5.4': '5.4. Уплата неустойки не освобождает Исполнителя от выполнения принятых по настоящему '
        'Договору обязательств и/или устранения нарушений.',
 '5.6': '5.6. В случае передачи Исполнителем права требования без получения согласия от Заказчика '
        '(в том числе денежных требований по договорам цессии и факторинга) по настоящему Договору '
        'Заказчик вправе потребовать уплаты штрафа в размере 20% от общей цены настоящего '
        'Договора.',
 '7.2': '7.2. Заказчик вправе в любое время в одностороннем порядке отказаться от исполнения '
        'настоящего Договора при условии компенсации Исполнителю фактически понесенных им '
        'расходов, связанных с исполнением своих обязательств по настоящему Договору, '
        'подтвержденных документально.'}

# Explicit partitions of the reviewed, SHA-pinned paragraphs. Each part must
# independently bind to one chunk; joining with one space must equal the
# entire reviewed paragraph. No inferred adjacency for arbitrary documents.
_SPLIT_AT = {'4.3':'Исполнителя в следующие сроки и порядке:', '5.3':'При просрочке свыше 10-ти'}


def paragraph_parts(section, text):
    marker = _SPLIT_AT.get(section)
    if not marker:
        return [text]
    if text.count(marker)!=1:
        raise ValueError('Reviewed paragraph boundary changed')
    left,right=text.split(marker,1)
    parts=[left.rstrip(),marker+right]
    if ' '.join(parts)!=text:
        raise ValueError('Reviewed paragraph partition mismatch')
    return parts


_GROUPS = {
    'acceptance_payment': ('3.4','4.3','4.4'),
    'delay_and_termination': ('5.3','5.4'),
    'assignment': ('5.6',),
    'withdrawal_costs': ('7.2',),
}


def linked_contract_observation(run_id, file_id, lineage, economics, *, verifier=verify_operator_run_quote):
    sources = {}
    if lineage.get('member_sha256') == _SOURCE_SHA:
        for section, quote in _PARAGRAPHS.items():
            fragments=[]
            for part in paragraph_parts(section, quote):
                checked = verifier(run_id=run_id,file_id=file_id,exact_quote=part)
                ev = checked.get('evidence')
                if not (checked.get('status')=='literal_quote_found_in_extracted_original_only'
                        and isinstance(ev,dict) and ev.get('quote')==part
                        and ev.get('original_sha256')==_SOURCE_SHA
                        and ev.get('ri223_container')==lineage and ev.get('file_id')==file_id
                        and ev.get('chunk_id')):
                    break
                fragments.append(ev)
            if ' '.join(x['quote'] for x in fragments)==quote:
                sources[section]={'status':'FULL_PINNED_PARAGRAPH_PARTS_VERIFIED','fragments':fragments}
    groups={k:{'status':'VERIFIED_REVIEWED_PARAGRAPH_GROUP' if all(x in sources for x in sections) else 'INCOMPLETE',
               'required_sections':list(sections),'source_sections':{x:sources[x] for x in sections if x in sources}}
            for k,sections in _GROUPS.items()}
    def ready(k):
        return groups[k]['status']=='VERIFIED_REVIEWED_PARAGRAPH_GROUP'
    timing=None
    if ready('acceptance_payment'):
        timing={'status':'CONDITIONAL_DRAFT_SEQUENCE_ONLY','acceptance_or_refusal_working_days':10,
                'payment_after_signed_act_working_days':7,'illustrative_no_refusal_working_days':17,
                'conditions':['no motivated refusal','signed act or UPD','invoice and invoice-facture provided',
                              'no alternative agreed payment form'],
                'payment_date_definition':'debit from customer account','rework_at_supplier_cost':True,
                'actual_receipt_date':None,'actual_cash_gap_days':None,'guaranteed_maximum_days':None}
    offer=economics.get('calculation',{}).get('offer_scenario')
    scenarios=[]
    if economics.get('status')=='ARCHIVED_LOT_EXPLICIT_SCENARIO_ONLY' and offer and 'economic_profit_rub' in offer:
        price=Decimal(offer['offer_price_rub']);profit=Decimal(offer['economic_profit_rub'])
        def money(v):
            return format(v.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP),'f')
        def add(code,group,amount,**conditions):
            scenarios.append({'code':code,'source_group':group,'modeled_penalty_rub':money(amount),
                              'profit_less_assumed_penalty_rub':money(profit-amount),**conditions})
        if ready('delay_and_termination'):
            for days in (1,10,11):
                add('DELAY_'+str(days),'delay_and_termination',price*Decimal('0.001')*days,
                    assumed_delay_days=days,termination_right_scenario=days>10,
                    actual_termination=None,penalty_payment_does_not_itself_release_obligations=True)
        if ready('assignment'):
            add('UNAUTHORIZED_ASSIGNMENT','assignment',price*Decimal('0.20'),assumed_no_customer_consent=True)
    return {'status':'ARCHIVED_LINKED_PARAGRAPH_REVIEW_ONLY','groups':groups,'payment_sequence':timing,
            'scenario_sensitivity':scenarios,'aggregate_penalty_attested':False,
            'actual_peak_working_capital_rub':None,'actual_liability_rub':None,
            'whole_contract_complete':False,'current_revision_attested':False,
            'go_eligible':False,'legal_conclusion':False}
