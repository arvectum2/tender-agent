from datetime import UTC, datetime

from src.modules.customer_registry.models import CustomerExternalRef, CustomerProfile
from src.modules.supplier_contracts.models import (
    SupplierContractRecord,
    SupplierContractSet,
)
from src.modules.supplier_ratings.models import (
    SupplierRatingFactor,
    SupplierRatingUpdateRecord,
    SupplierRatingUpdateSet,
)
from src.modules.supplier_registry.models import SupplierExternalRef, SupplierProfile
from src.modules.supplier_verification.models import (
    SupplierVerificationFlag,
    SupplierVerificationRecord,
    SupplierVerificationSet,
)
from src.shared.enums import CustomerStatus, SupplierStatus
from src.tender_research.models import ProcurementTender


def _customer(session, *, customer_id: str = "CUST-053", inn: str | None = "7701000000") -> CustomerProfile:
    item = CustomerProfile(
        customer_id=customer_id,
        legal_name="АО Тестовый заказчик",
        inn=inn,
        kpp="770101001" if inn else None,
        customer_status=CustomerStatus.ACTIVE,
    )
    session.add(item)
    session.flush()
    return item


def _supplier(session, *, supplier_id: str = "SUP-053") -> SupplierProfile:
    item = SupplierProfile(
        supplier_id=supplier_id,
        legal_name='ООО "Поставщик 053"',
        display_name="Поставщик 053",
        inn="7702000000",
        country_code="RU",
        status=SupplierStatus.ACTIVE,
    )
    session.add(item)
    session.flush()
    return item


def test_customer_card_uses_exact_inn_procurement_evidence_and_does_not_invent_risk(client, session):
    customer = _customer(session)
    session.add(
        CustomerExternalRef(
            customer_id=customer.customer_id,
            source_type="EIS",
            source_ref="https://zakupki.gov.ru/customer/7701000000",
        )
    )
    session.add_all(
        [
            ProcurementTender(
                source="eis",
                external_id="p-053-1",
                registry_number="1000000000000000001",
                title="Поставка кабеля",
                customer_name=customer.legal_name,
                customer_inn=customer.inn,
                nmck_amount=1_200_000.0,
                currency="RUB",
                status="PUBLISHED",
                eis_url="https://zakupki.gov.ru/epz/order/notice/1",
                publication_date=datetime(2026, 9, 1, tzinfo=UTC),
            ),
            ProcurementTender(
                source="eis",
                external_id="p-053-2",
                registry_number="1000000000000000002",
                title="Поставка автоматики",
                customer_name=customer.legal_name,
                customer_inn=customer.inn,
                nmck_amount=800_000.0,
                currency="RUB",
                status="COMPLETED",
                eis_url="https://zakupki.gov.ru/epz/order/notice/2",
                publication_date=datetime(2026, 8, 1, tzinfo=UTC),
            ),
        ]
    )
    session.commit()

    response = client.get(f"/counterparties/customers/{customer.customer_id}")
    assert response.status_code == 200
    payload = response.json()

    assert payload["counterparty_type"] == "CUSTOMER"
    assert payload["risk"]["available"] is False
    assert payload["risk"]["observed_risk_score"] is None
    assert payload["risk"]["band"] == "INSUFFICIENT_EVIDENCE"
    assert payload["risk"]["authoritative_reliability_conclusion"] is False
    assert payload["risk"]["participation_decision"] is False
    assert payload["history"]["procurement_count"] == 2
    assert payload["history"]["procurement_nmck_total"] == 2_000_000.0
    assert len(payload["history"]["items"]) == 2
    assert payload["history"]["items"][0]["evidence"][0]["source_type"] == "PROCUREMENT_NOTICE"
    factors = {item["factor_code"]: item for item in payload["factors"]}
    assert factors["PROCUREMENT_HISTORY"]["state"] == "OBSERVED"
    assert factors["PROCUREMENT_HISTORY"]["evidence"]
    assert factors["CUSTOMER_RISK_SIGNALS"]["state"] == "UNKNOWN"


def test_customer_card_without_inn_fails_closed_instead_of_name_matching(client, session):
    customer = _customer(session, customer_id="CUST-NO-INN", inn=None)
    session.add(
        ProcurementTender(
            source="eis",
            external_id="same-name-but-ambiguous",
            registry_number="2000000000000000001",
            title="Не должна привязаться по имени",
            customer_name=customer.legal_name,
            customer_inn="9999999999",
        )
    )
    session.commit()

    payload = client.get(f"/counterparties/customers/{customer.customer_id}").json()

    assert payload["history"]["procurement_count"] == 0
    assert payload["history"]["items"] == []
    history_factor = next(item for item in payload["factors"] if item["factor_code"] == "PROCUREMENT_HISTORY")
    assert history_factor["state"] == "UNKNOWN"
    assert "not matched by name" in history_factor["summary"]


def test_supplier_card_projects_verification_flags_contracts_and_rating_with_transparent_score(client, session):
    supplier = _supplier(session)
    session.add(
        SupplierExternalRef(
            supplier_id=supplier.supplier_id,
            ref_type="website",
            ref_value="https://supplier.example",
        )
    )
    verification_set = SupplierVerificationSet(
        supplier_verification_set_id="SVS-053",
        deal_id="DEAL-053",
        supplier_shortlist_id="SHORT-053",
        verification_status="PARTIAL",
    )
    session.add(verification_set)
    session.flush()
    verification = SupplierVerificationRecord(
        supplier_verification_id="SV-053",
        supplier_verification_set_id=verification_set.supplier_verification_set_id,
        supplier_id=supplier.supplier_id,
        verification_result="NEEDS_REVIEW",
        confidence_score=0.72,
        notes="Evidence-backed supplier verification",
    )
    session.add(verification)
    session.flush()
    session.add_all(
        [
            SupplierVerificationFlag(
                supplier_verification_id=verification.supplier_verification_id,
                flag_code="MISSING_PRIMARY_CONTACT",
                severity="MEDIUM",
                summary="No primary contact is registered.",
                source_ref=f"SUPPLIER:{supplier.supplier_id}",
            ),
            SupplierVerificationFlag(
                supplier_verification_id=verification.supplier_verification_id,
                flag_code="NO_TENDER_READY_TAG",
                severity="LOW",
                summary="Tender-ready tag is missing.",
                source_ref=f"SUPPLIER:{supplier.supplier_id}",
            ),
        ]
    )

    contract_set = SupplierContractSet(
        supplier_contract_set_id="SCS-053",
        deal_id="DEAL-053",
        supplier_id=supplier.supplier_id,
        contract_status="SIGNED",
    )
    session.add(contract_set)
    session.flush()
    session.add(
        SupplierContractRecord(
            supplier_contract_id="SC-053",
            supplier_contract_set_id=contract_set.supplier_contract_set_id,
            summary_text="Signed supplier contract for test delivery.",
            contract_manifest_json={"source": "canonical-test"},
        )
    )

    rating_set = SupplierRatingUpdateSet(
        supplier_rating_update_set_id="SRUS-053",
        deal_id="DEAL-053",
        supplier_id=supplier.supplier_id,
        supplier_contract_set_id=contract_set.supplier_contract_set_id,
        postmortem_set_id="PM-053",
        rating_status="UPDATED",
    )
    session.add(rating_set)
    session.flush()
    rating = SupplierRatingUpdateRecord(
        supplier_rating_update_id="SRU-053",
        supplier_rating_update_set_id=rating_set.supplier_rating_update_set_id,
        prior_rating_value=None,
        updated_rating_value=82.0,
        rating_band="APPROVED",
        rationale_text="Operational history only",
    )
    session.add(rating)
    session.flush()
    session.add(
        SupplierRatingFactor(
            supplier_rating_update_id=rating.supplier_rating_update_id,
            factor_code="DELIVERY_SIGNAL",
            factor_score=30.0,
            summary="Delivery checkpoint was reached.",
        )
    )
    session.commit()

    response = client.get(f"/counterparties/suppliers/{supplier.supplier_id}")
    assert response.status_code == 200
    payload = response.json()

    assert payload["counterparty_type"] == "SUPPLIER"
    assert payload["risk"]["available"] is True
    assert payload["risk"]["observed_risk_score"] == 20.0
    assert payload["risk"]["band"] == "MEDIUM"
    assert payload["risk"]["included_factor_codes"] == [
        "MISSING_PRIMARY_CONTACT",
        "NO_TENDER_READY_TAG",
    ]
    assert payload["risk"]["authoritative_reliability_conclusion"] is False
    assert payload["history"]["supplier_contract_count"] == 1
    factors = {item["factor_code"]: item for item in payload["factors"]}
    assert factors["MISSING_PRIMARY_CONTACT"]["risk_points"] == 15.0
    assert factors["MISSING_PRIMARY_CONTACT"]["evidence"][0]["source_ref"] == f"SUPPLIER:{supplier.supplier_id}"
    assert factors["NO_TENDER_READY_TAG"]["risk_points"] == 5.0
    assert factors["INTERNAL_EXECUTION_RATING"]["contributes_to_score"] is False
    assert any(
        item["source_type"] == "SUPPLIER_RATING_FACTOR"
        for item in factors["INTERNAL_EXECUTION_RATING"]["evidence"]
    )
    assert factors["SUPPLIER_CONTRACT_HISTORY"]["state"] == "OBSERVED"


def test_supplier_card_without_verification_does_not_score_registry_presence_as_reliability(client, session):
    supplier = _supplier(session, supplier_id="SUP-NO-VERIFICATION")
    session.commit()

    payload = client.get(f"/counterparties/suppliers/{supplier.supplier_id}").json()

    assert payload["risk"]["available"] is False
    assert payload["risk"]["observed_risk_score"] is None
    assert payload["risk"]["band"] == "INSUFFICIENT_EVIDENCE"
    verification_factor = next(
        item for item in payload["factors"] if item["factor_code"] == "SUPPLIER_VERIFICATION"
    )
    assert verification_factor["state"] == "UNKNOWN"
    assert verification_factor["evidence"] == []
