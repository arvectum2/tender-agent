from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.modules.counterparty_cards.schemas import (
    CounterpartyCardResponse,
    CounterpartyEvidenceRefResponse,
    CounterpartyFactorResponse,
    CounterpartyHistoryItemResponse,
    CounterpartyHistoryResponse,
    CounterpartyRiskAggregateResponse,
)
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
)
from src.shared.errors import NotFoundError
from src.tender_research.models import ProcurementTender

_HISTORY_LIMIT = 10
_RISK_CALCULATION = (
    "Observed risk score = 100 * (1 - confidence_score) from the latest canonical "
    "M-020 supplier-verification record. The band mirrors that record's verification_result. "
    "Factor-level deductions are not reconstructed because M-020 does not persist a "
    "per-flag numeric deduction. Neutral history/rating context is not added to this score."
)


def _evidence(
    source_type: str,
    source_ref: str,
    label: str,
    *,
    url: str | None = None,
) -> CounterpartyEvidenceRefResponse:
    return CounterpartyEvidenceRefResponse(
        source_type=source_type,
        source_ref=source_ref,
        label=label,
        url=url,
    )


def _verification_band(result: object) -> str:
    normalized = str(result).strip().upper()
    if normalized in {"PASS", "NEEDS_REVIEW", "FAIL"}:
        return normalized
    return "NEEDS_REVIEW"


def _unknown_risk(*, reason: str) -> CounterpartyRiskAggregateResponse:
    return CounterpartyRiskAggregateResponse(
        available=False,
        observed_risk_score=None,
        band="INSUFFICIENT_EVIDENCE",
        calculation=_RISK_CALCULATION,
        included_factor_codes=[],
        limitations=[
            reason,
            "The card is an evidence projection, not a legal, sanctions, solvency, or reliability opinion.",
        ],
    )


def _customer_refs(session: Session, customer_id: str) -> list[CustomerExternalRef]:
    return list(
        session.scalars(
            select(CustomerExternalRef)
            .where(CustomerExternalRef.customer_id == customer_id)
            .order_by(
                CustomerExternalRef.created_at.asc(), CustomerExternalRef.id.asc()
            )
        )
    )


def _supplier_refs(session: Session, supplier_id: str) -> list[SupplierExternalRef]:
    return list(
        session.scalars(
            select(SupplierExternalRef)
            .where(SupplierExternalRef.supplier_id == supplier_id)
            .order_by(
                SupplierExternalRef.created_at.asc(), SupplierExternalRef.id.asc()
            )
        )
    )


def get_customer_counterparty_card(
    session: Session, customer_id: str
) -> CounterpartyCardResponse:
    customer = session.scalar(
        select(CustomerProfile).where(CustomerProfile.customer_id == customer_id)
    )
    if not customer:
        raise NotFoundError(f"Customer '{customer_id}' was not found")

    external_refs = _customer_refs(session, customer_id)
    identity_evidence = [
        _evidence(
            "CUSTOMER_EXTERNAL_REF",
            f"{item.source_type}:{item.source_ref}",
            f"{item.source_type} customer reference",
            url=item.source_ref
            if str(item.source_ref).startswith(("http://", "https://"))
            else None,
        )
        for item in external_refs
    ]
    identity_evidence.append(
        _evidence(
            "CUSTOMER_PROFILE",
            f"CUSTOMER:{customer.customer_id}",
            "Canonical M-005 customer profile",
        )
    )

    factors = [
        CounterpartyFactorResponse(
            factor_code="IDENTITY_PROFILE",
            category="IDENTITY",
            state="OBSERVED",
            severity="INFO",
            summary="Canonical customer identity is projected from the existing M-005 registry.",
            evidence=identity_evidence,
        )
    ]

    history_items: list[CounterpartyHistoryItemResponse] = []
    procurement_count = 0
    procurement_nmck_total: float | None = None
    if customer.inn:
        procurement_count, procurement_nmck_total = session.execute(
            select(
                func.count(ProcurementTender.id),
                func.sum(ProcurementTender.nmck_amount),
            ).where(ProcurementTender.customer_inn == customer.inn)
        ).one()
        procurement_count = int(procurement_count or 0)
        procurement_nmck_total = (
            float(procurement_nmck_total)
            if procurement_nmck_total is not None
            else None
        )
        tenders = list(
            session.scalars(
                select(ProcurementTender)
                .where(ProcurementTender.customer_inn == customer.inn)
                .order_by(
                    ProcurementTender.publication_date.desc(),
                    ProcurementTender.created_at.desc(),
                    ProcurementTender.id.desc(),
                )
                .limit(_HISTORY_LIMIT)
            )
        )
        for tender in tenders:
            source_ref = tender.registry_number or tender.external_id
            source_url = tender.eis_url or tender.platform_url
            history_items.append(
                CounterpartyHistoryItemResponse(
                    history_type="PROCUREMENT",
                    record_id=str(tender.id),
                    title=tender.title,
                    status=tender.status,
                    amount=tender.nmck_amount,
                    currency=tender.currency,
                    occurred_at=tender.publication_date,
                    evidence=[
                        _evidence(
                            "PROCUREMENT_NOTICE",
                            f"{tender.source}:{source_ref}",
                            f"Procurement {source_ref}",
                            url=source_url,
                        )
                    ],
                )
            )
        if procurement_count:
            factors.append(
                CounterpartyFactorResponse(
                    factor_code="PROCUREMENT_HISTORY",
                    category="HISTORY",
                    state="OBSERVED",
                    severity="INFO",
                    summary=(
                        f"Found {procurement_count} procurement record(s) by exact customer INN; "
                        "this is activity evidence, not a reliability conclusion."
                    ),
                    evidence=[
                        item.evidence[0] for item in history_items if item.evidence
                    ],
                )
            )
        else:
            factors.append(
                CounterpartyFactorResponse(
                    factor_code="PROCUREMENT_HISTORY",
                    category="HISTORY",
                    state="UNKNOWN",
                    severity="UNKNOWN",
                    summary=(
                        "No procurement history is present in the current local corpus for the exact customer INN; "
                        "absence from this corpus is not evidence of absence."
                    ),
                )
            )
    else:
        factors.append(
            CounterpartyFactorResponse(
                factor_code="PROCUREMENT_HISTORY",
                category="HISTORY",
                state="UNKNOWN",
                severity="UNKNOWN",
                summary=(
                    "Customer INN is missing, so procurement history is not matched by name. "
                    "This fail-closed rule prevents ambiguous counterparty-role matching."
                ),
            )
        )

    factors.append(
        CounterpartyFactorResponse(
            factor_code="CUSTOMER_RISK_SIGNALS",
            category="RISK",
            state="UNKNOWN",
            severity="UNKNOWN",
            summary=(
                "No canonical adverse customer-risk dataset is connected to this card. "
                "A customer risk score is therefore intentionally not computed."
            ),
        )
    )

    return CounterpartyCardResponse(
        counterparty_type="CUSTOMER",
        counterparty_id=customer.customer_id,
        legal_name=customer.legal_name,
        inn=customer.inn,
        profile_status=str(customer.customer_status),
        factors=factors,
        risk=_unknown_risk(
            reason=(
                "Customer-side adverse risk evidence is not available in the current canonical data model; "
                "procurement activity is shown separately and is not scored as reliability."
            )
        ),
        history=CounterpartyHistoryResponse(
            procurement_count=procurement_count,
            procurement_nmck_total=procurement_nmck_total,
            supplier_contract_count=0,
            items=history_items,
        ),
    )


def _latest_supplier_verification(
    session: Session,
    supplier_id: str,
) -> tuple[SupplierVerificationRecord | None, list[SupplierVerificationFlag]]:
    record = session.scalar(
        select(SupplierVerificationRecord)
        .where(SupplierVerificationRecord.supplier_id == supplier_id)
        .order_by(
            SupplierVerificationRecord.created_at.desc(),
            SupplierVerificationRecord.id.desc(),
        )
        .limit(1)
    )
    if not record:
        return None, []
    flags = list(
        session.scalars(
            select(SupplierVerificationFlag)
            .where(
                SupplierVerificationFlag.supplier_verification_id
                == record.supplier_verification_id
            )
            .order_by(
                SupplierVerificationFlag.created_at.asc(),
                SupplierVerificationFlag.id.asc(),
            )
        )
    )
    return record, flags


def _latest_supplier_rating(
    session: Session,
    supplier_id: str,
) -> tuple[SupplierRatingUpdateRecord | None, list[SupplierRatingFactor]]:
    row = session.execute(
        select(SupplierRatingUpdateRecord, SupplierRatingUpdateSet)
        .join(
            SupplierRatingUpdateSet,
            SupplierRatingUpdateSet.supplier_rating_update_set_id
            == SupplierRatingUpdateRecord.supplier_rating_update_set_id,
        )
        .where(SupplierRatingUpdateSet.supplier_id == supplier_id)
        .order_by(
            SupplierRatingUpdateRecord.created_at.desc(),
            SupplierRatingUpdateRecord.id.desc(),
        )
        .limit(1)
    ).first()
    if not row:
        return None, []
    record = row[0]
    factors = list(
        session.scalars(
            select(SupplierRatingFactor)
            .where(
                SupplierRatingFactor.supplier_rating_update_id
                == record.supplier_rating_update_id
            )
            .order_by(
                SupplierRatingFactor.created_at.asc(), SupplierRatingFactor.id.asc()
            )
        )
    )
    return record, factors


def _supplier_contract_history(
    session: Session,
    supplier_id: str,
) -> tuple[int, list[CounterpartyHistoryItemResponse]]:
    total = int(
        session.scalar(
            select(func.count(SupplierContractSet.id)).where(
                SupplierContractSet.supplier_id == supplier_id
            )
        )
        or 0
    )
    sets = list(
        session.scalars(
            select(SupplierContractSet)
            .where(SupplierContractSet.supplier_id == supplier_id)
            .order_by(
                SupplierContractSet.created_at.desc(), SupplierContractSet.id.desc()
            )
            .limit(_HISTORY_LIMIT)
        )
    )
    items: list[CounterpartyHistoryItemResponse] = []
    for contract_set in sets:
        record = session.scalar(
            select(SupplierContractRecord)
            .where(
                SupplierContractRecord.supplier_contract_set_id
                == contract_set.supplier_contract_set_id
            )
            .order_by(
                SupplierContractRecord.created_at.desc(),
                SupplierContractRecord.id.desc(),
            )
            .limit(1)
        )
        evidence = [
            _evidence(
                "SUPPLIER_CONTRACT_SET",
                f"SUPPLIER_CONTRACT_SET:{contract_set.supplier_contract_set_id}",
                f"Canonical supplier contract set for deal {contract_set.deal_id}",
            )
        ]
        if record:
            evidence.append(
                _evidence(
                    "SUPPLIER_CONTRACT",
                    f"SUPPLIER_CONTRACT:{record.supplier_contract_id}",
                    "Canonical supplier contract record",
                )
            )
        items.append(
            CounterpartyHistoryItemResponse(
                history_type="SUPPLIER_CONTRACT",
                record_id=contract_set.supplier_contract_set_id,
                title=record.summary_text
                if record
                else f"Supplier contract for deal {contract_set.deal_id}",
                status=str(contract_set.contract_status),
                occurred_at=contract_set.created_at,
                evidence=evidence,
            )
        )
    return total, items


def get_supplier_counterparty_card(
    session: Session, supplier_id: str
) -> CounterpartyCardResponse:
    supplier = session.scalar(
        select(SupplierProfile).where(SupplierProfile.supplier_id == supplier_id)
    )
    if not supplier:
        raise NotFoundError(f"Supplier '{supplier_id}' was not found")

    external_refs = _supplier_refs(session, supplier_id)
    factors: list[CounterpartyFactorResponse] = [
        CounterpartyFactorResponse(
            factor_code="IDENTITY_PROFILE",
            category="IDENTITY",
            state="OBSERVED",
            severity="INFO",
            summary="Canonical supplier identity is projected from the existing M-006 registry.",
            evidence=[
                _evidence(
                    "SUPPLIER_PROFILE",
                    f"SUPPLIER:{supplier.supplier_id}",
                    "Canonical M-006 supplier profile",
                ),
                *[
                    _evidence(
                        "SUPPLIER_EXTERNAL_REF",
                        f"{item.ref_type}:{item.ref_value}",
                        f"{item.ref_type} supplier reference",
                        url=item.ref_value
                        if str(item.ref_value).startswith(("http://", "https://"))
                        else None,
                    )
                    for item in external_refs
                ],
            ],
        )
    ]

    verification, flags = _latest_supplier_verification(session, supplier_id)
    included_factor_codes: list[str] = []
    if verification is None:
        factors.append(
            CounterpartyFactorResponse(
                factor_code="SUPPLIER_VERIFICATION",
                category="RISK",
                state="UNKNOWN",
                severity="UNKNOWN",
                summary=(
                    "No canonical supplier-verification record is available. "
                    "The card does not infer reliability from registry presence alone."
                ),
            )
        )
        risk = _unknown_risk(
            reason="No canonical supplier-verification record is available for this supplier."
        )
    else:
        if flags:
            for flag in flags:
                severity = str(flag.severity).upper()
                code = str(flag.flag_code)
                included_factor_codes.append(code)
                evidence_ref = (
                    flag.source_ref or f"SUPPLIER_VERIFICATION_FLAG:{flag.id}"
                )
                factors.append(
                    CounterpartyFactorResponse(
                        factor_code=code,
                        category="RISK",
                        state="ADVERSE",
                        severity=severity
                        if severity in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
                        else "UNKNOWN",
                        risk_points=None,
                        contributes_to_score=True,
                        summary=flag.summary,
                        evidence=[
                            _evidence(
                                "SUPPLIER_VERIFICATION_FLAG",
                                evidence_ref,
                                f"Verification flag {code}",
                            )
                        ],
                    )
                )
        else:
            included_factor_codes.append("SUPPLIER_VERIFICATION_PASS")
            factors.append(
                CounterpartyFactorResponse(
                    factor_code="SUPPLIER_VERIFICATION_PASS",
                    category="RISK",
                    state="OBSERVED",
                    severity="INFO",
                    risk_points=None,
                    contributes_to_score=True,
                    summary=(
                        f"Latest canonical supplier verification has no adverse flags "
                        f"(result={verification.verification_result}, confidence={verification.confidence_score:.2f})."
                    ),
                    evidence=[
                        _evidence(
                            "SUPPLIER_VERIFICATION",
                            f"SUPPLIER_VERIFICATION:{verification.supplier_verification_id}",
                            "Latest canonical supplier verification record",
                        )
                    ],
                )
            )
        confidence = max(0.0, min(1.0, float(verification.confidence_score)))
        score = round((1.0 - confidence) * 100.0, 2)
        risk = CounterpartyRiskAggregateResponse(
            available=True,
            observed_risk_score=score,
            source_confidence_score=confidence,
            band=_verification_band(verification.verification_result),
            calculation=_RISK_CALCULATION,
            included_factor_codes=included_factor_codes,
            limitations=[
                (
                    f"Score reuses the latest canonical M-020 supplier-verification record "
                    f"{verification.supplier_verification_id}; no ARV-053-specific factor weights are invented."
                ),
                (
                    "Per-flag numeric deductions are intentionally omitted because the canonical "
                    "verification record persists only the aggregate confidence and evidence flags."
                ),
                "This is not a legal, sanctions, solvency, or reliability opinion.",
                "Neutral contract history and internal execution ratings are displayed separately and are not double-counted.",
            ],
        )

    rating, rating_factors = _latest_supplier_rating(session, supplier_id)
    if rating is None:
        factors.append(
            CounterpartyFactorResponse(
                factor_code="INTERNAL_EXECUTION_RATING",
                category="EXECUTION_HISTORY",
                state="UNKNOWN",
                severity="UNKNOWN",
                summary="No post-execution supplier rating is available yet.",
            )
        )
    else:
        factors.append(
            CounterpartyFactorResponse(
                factor_code="INTERNAL_EXECUTION_RATING",
                category="EXECUTION_HISTORY",
                state="OBSERVED",
                severity="INFO",
                summary=(
                    f"Internal operational rating={rating.updated_rating_value:.1f}, band={rating.rating_band}. "
                    "It is shown as historical execution context and is not added to the ARV-053 risk score."
                ),
                evidence=[
                    _evidence(
                        "SUPPLIER_RATING",
                        f"SUPPLIER_RATING:{rating.supplier_rating_update_id}",
                        "Latest internal supplier execution rating",
                    ),
                    *[
                        _evidence(
                            "SUPPLIER_RATING_FACTOR",
                            f"SUPPLIER_RATING_FACTOR:{item.id}",
                            f"{item.factor_code}: {item.summary}",
                        )
                        for item in rating_factors
                    ],
                ],
            )
        )

    contract_count, contract_items = _supplier_contract_history(session, supplier_id)
    if contract_count:
        factors.append(
            CounterpartyFactorResponse(
                factor_code="SUPPLIER_CONTRACT_HISTORY",
                category="HISTORY",
                state="OBSERVED",
                severity="INFO",
                summary=(
                    f"Found {contract_count} canonical supplier contract set(s). "
                    "Contract existence/status is activity evidence and is not treated as proof of reliability."
                ),
                evidence=[item.evidence[0] for item in contract_items if item.evidence],
            )
        )
    else:
        factors.append(
            CounterpartyFactorResponse(
                factor_code="SUPPLIER_CONTRACT_HISTORY",
                category="HISTORY",
                state="UNKNOWN",
                severity="UNKNOWN",
                summary="No canonical supplier contract history is available yet.",
            )
        )

    return CounterpartyCardResponse(
        counterparty_type="SUPPLIER",
        counterparty_id=supplier.supplier_id,
        legal_name=supplier.legal_name,
        inn=supplier.inn,
        profile_status=str(supplier.status),
        factors=factors,
        risk=risk,
        history=CounterpartyHistoryResponse(
            procurement_count=0,
            procurement_nmck_total=None,
            supplier_contract_count=contract_count,
            items=contract_items,
        ),
    )
