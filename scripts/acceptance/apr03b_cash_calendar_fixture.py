"""Synthetic schedule for the pinned archive; NOT observed contract payment dates."""
from src.modules.tender_operator_agent_demo.operator_cashflow_calendar import (
    CashCalendarRequest,
)


def calendar_fixture():
    rows=[
        ('2027-01-01','bid_security_hold','20000'),
        ('2027-01-02','fixed_platform_fee','10000'),
        ('2027-01-02','guarantee_fee','5000'),
        ('2027-01-02','contract_security_hold','100000'),
        ('2027-01-03','external_direct','100000'),
        ('2027-01-03','labor_cash','50000'),
        ('2027-01-04','advance','270000'),
        ('2027-01-05','bid_security_return','20000'),
        ('2027-01-10','external_direct','150000'),
        ('2027-01-10','labor_cash','100000'),
        ('2027-01-11','stage_payment','270000'),
        ('2027-01-12','reserve','50000'),
        ('2027-01-20','final_payment','360000'),
        ('2027-01-21','revenue_tax','54000'),
        ('2027-01-21','variable_platform_fee','9000'),
        ('2027-01-25','contract_security_return','100000'),
    ]
    return CashCalendarRequest(start_date='2027-01-01',end_date='2027-01-25',
        opening_available_cash_rub='200000',labor_cash_rub='150000',
        events=[{'event_id':f'e{i:02d}','event_date':day,'stage':'synthetic',
                 'category':category,'amount_rub':amount} for i,(day,category,amount) in enumerate(rows)],
        receipt_delay_calendar_days=[7,30],accept_hypothetical_assumptions_only=True)


def contract_calendar_fixture():
    from datetime import date, timedelta

    from src.modules.tender_operator_agent_demo.ri223_payment_calendar import (
        ContractPaymentCalendarRequest,
    )

    ledger=calendar_fixture().model_dump()
    ledger['end_date']='2027-03-31'
    ledger['events']=[x for x in ledger['events'] if x['category'] not in ('advance','stage_payment','final_payment')]
    # Explicit synthetic working dates, NOT Russian statutory holidays.
    start=date(2027,1,1)
    working=[(start+timedelta(days=i)).isoformat() for i in range(90) if (start+timedelta(days=i)).weekday()<5]
    return ContractPaymentCalendarRequest(ledger_without_customer_receipts=ledger,
        work_calendar={'coverage_start':'2027-01-01','coverage_end':'2027-03-31','working_dates':working,
                       'accept_complete_workday_list_as_assumption':True},
        act_received_date='2027-01-20',invoice_and_invoice_facture_provided_by_signing=True,
        assume_no_motivated_refusal=True,assume_bank_transfer_without_alternative_agreement=True,
        assume_single_full_settlement=True,bank_receipt_lag_calendar_days=2)
