from __future__ import annotations

from typing import Any

DECISION_CORE_CONTRACT_VERSION = "decision-core-v1"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_procurement_regime(model: dict[str, Any]) -> str:
    raw = _text(model.get("procurement_regime") or model.get("procurement_law")).lower()
    compact = raw.replace("-", "").replace("_", "").replace(" ", "")
    if compact in {"44fz", "44фз"}:
        return "44fz"
    if compact in {"223fz", "223фз"}:
        return "223fz"
    return "unknown"


def _evidence_from_ref(source_ref: Any, *, fallback_document: str | None = None) -> dict[str, Any] | None:
    ref = _text(source_ref)
    if not ref:
        return None
    prefix, _, locator = ref.partition(":")
    document = fallback_document or {
        "eis_notice": "Извещение о закупке",
        "notice": "Извещение о закупке",
        "contract": "Проект контракта",
    }.get(prefix, "Документы закупки")
    return {
        "source_ref": ref,
        "document": document,
        "locator": locator or ref,
    }


def _dedupe_evidence(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in values:
        key = (_text(item.get("source_ref")), _text(item.get("document")), _text(item.get("locator")))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _field_evidence(model: dict[str, Any], field: str) -> list[dict[str, Any]]:
    mapping = model.get("field_evidence")
    if not isinstance(mapping, dict):
        return []
    raw = mapping.get(field)
    refs = raw if isinstance(raw, list) else [raw]
    result = [item for value in refs if (item := _evidence_from_ref(value)) is not None]
    excerpt = model.get(field)
    if excerpt not in (None, ""):
        for item in result:
            item["excerpt"] = excerpt
    return result


def _mapped_evidence(model: dict[str, Any], evidence_id: Any) -> dict[str, Any] | None:
    target = _text(evidence_id)
    if not target:
        return None
    for row in model.get("evidence_map", []) or []:
        if not isinstance(row, dict) or _text(row.get("evidence_id")) != target:
            continue
        return {
            "source_ref": target,
            "document": _text(row.get("document")) or "Документы закупки",
            "locator": _text(row.get("row")) or "раздел документа",
            "excerpt": row.get("short_excerpt"),
        }
    return None


def _contract_evidence(model: dict[str, Any]) -> list[dict[str, Any]]:
    documents = [str(item) for item in model.get("contract_draft_documents", []) or [] if item]
    fallback_document = documents[0] if documents else "Проект контракта"
    result: list[dict[str, Any]] = []
    for evidence_id in model.get("contract_draft_evidence_ids", []) or []:
        result.append(
            _mapped_evidence(model, evidence_id)
            or _evidence_from_ref(evidence_id, fallback_document=fallback_document)
        )
    return _dedupe_evidence([item for item in result if item])


def _risk_evidence(model: dict[str, Any], risk_index: int) -> list[dict[str, Any]]:
    prefix = f"risk:{risk_index}:"
    result: list[dict[str, Any]] = []
    for row in model.get("evidence_map", []) or []:
        if not isinstance(row, dict):
            continue
        evidence_id = _text(row.get("evidence_id"))
        if not evidence_id.startswith(prefix):
            continue
        result.append(
            {
                "source_ref": evidence_id,
                "document": _text(row.get("document")) or "Документы закупки",
                "locator": _text(row.get("row")) or "раздел документа",
                "excerpt": row.get("short_excerpt"),
            }
        )
    return _dedupe_evidence(result)


def _readiness(
    code: str,
    label: str,
    status: str,
    summary: str,
    *,
    required: bool = True,
    blocking: bool = False,
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "label": label,
        "status": status,
        "required": required,
        "blocking": blocking,
        "summary": summary,
        "evidence": list(evidence or []),
    }


def build_decision_core(
    model: dict[str, Any],
    *,
    supplier_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build fail-closed procurement decision semantics from source-bound canonical facts.

    The function never authorizes an external procurement action. A hard NO_GO is
    emitted only for an explicitly supported hard blocker; unsupported or missing
    evidence degrades to NEEDS_REVIEW rather than being promoted to fact.
    """

    blockers: list[dict[str, Any]] = []
    readiness: list[dict[str, Any]] = []
    unknowns: list[dict[str, Any]] = []
    rationale: list[str] = []
    regime = _normalize_procurement_regime(model)
    is_223fz = regime == "223fz"

    title_evidence = _field_evidence(model, "procurement_title")
    deadline_evidence = _field_evidence(model, "application_deadline")
    nmck_evidence = _field_evidence(model, "nmck")
    facts = {
        "procurement_title": {
            "status": "KNOWN" if title_evidence and model.get("procurement_title") not in (None, "") else "UNKNOWN",
            "value": model.get("procurement_title") if title_evidence else None,
            "evidence": title_evidence,
        },
        "application_deadline": {
            "status": "KNOWN" if deadline_evidence and model.get("application_deadline") not in (None, "") else "UNKNOWN",
            "value": model.get("application_deadline") if deadline_evidence else None,
            "evidence": deadline_evidence,
        },
        "nmck": {
            "status": "KNOWN" if nmck_evidence and _number(model.get("nmck")) is not None else "UNKNOWN",
            "value": model.get("nmck") if nmck_evidence else None,
            "evidence": nmck_evidence,
        },
    }

    deadline_status = _text(model.get("deadline_status")).lower()
    if is_223fz:
        readiness.append(
            _readiness(
                "APPLICATION_WINDOW",
                "Срок подачи заявок",
                "UNKNOWN",
                "223-ФЗ: срок извлечён как source-bound факт, но правовой статус окна подачи не интерпретируется без отдельно утверждённой режимной семантики.",
                blocking=True,
                evidence=deadline_evidence,
            )
        )
        unknowns.append(
            {
                "code": "223FZ_APPLICATION_WINDOW_SEMANTICS",
                "summary": "Правовая интерпретация срока подачи для 223-ФЗ не утверждена в текущем Decision Core.",
            }
        )
    elif deadline_status == "expired" and deadline_evidence:
        blockers.append(
            {
                "code": "APPLICATION_DEADLINE_EXPIRED",
                "summary": "Срок подачи заявок истёк.",
                "hard": True,
                "evidence": deadline_evidence,
            }
        )
        readiness.append(
            _readiness(
                "APPLICATION_WINDOW",
                "Срок подачи заявок",
                "BLOCKED",
                "Подтверждённый срок подачи заявок истёк.",
                blocking=True,
                evidence=deadline_evidence,
            )
        )
    elif deadline_status == "open" and deadline_evidence:
        readiness.append(
            _readiness(
                "APPLICATION_WINDOW",
                "Срок подачи заявок",
                "SATISFIED",
                "Срок подачи заявок подтверждён и не истёк.",
                evidence=deadline_evidence,
            )
        )
    else:
        readiness.append(
            _readiness(
                "APPLICATION_WINDOW",
                "Срок подачи заявок",
                "UNKNOWN",
                "Срок подачи или его статус не подтверждены источником.",
                blocking=True,
            )
        )
        unknowns.append(
            {
                "code": "APPLICATION_WINDOW_EVIDENCE",
                "summary": "Нельзя использовать срок подачи как факт без source binding.",
            }
        )

    contract_status = _text(model.get("contract_draft_status")).lower()
    contract_evidence = _contract_evidence(model)
    if is_223fz:
        facts["contract_draft"] = {
            "status": "UNKNOWN",
            "value": None,
            "evidence": contract_evidence,
        }
        readiness.append(
            _readiness(
                "CONTRACT_DRAFT",
                "Проект договора/контракта",
                "UNKNOWN",
                "223-ФЗ: договорная готовность не интерпретируется по 44-ФЗ-семантике без отдельно утверждённого source-bound правила.",
                blocking=True,
                evidence=contract_evidence,
            )
        )
        unknowns.append(
            {
                "code": "223FZ_CONTRACT_READINESS_SEMANTICS",
                "summary": "Договорная readiness-семантика 223-ФЗ не утверждена в текущем Decision Core.",
            }
        )
    else:
        facts["contract_draft"] = {
            "status": "KNOWN" if contract_evidence and contract_status == "present" else "UNKNOWN",
            "value": "present" if contract_evidence and contract_status == "present" else None,
            "evidence": contract_evidence,
        }
        if contract_status == "present" and contract_evidence:
            readiness.append(
                _readiness(
                    "CONTRACT_DRAFT",
                    "Проект контракта",
                    "SATISFIED",
                    "Проект контракта присутствует и связан с доказательством.",
                    evidence=contract_evidence,
                )
            )
        elif contract_status == "present":
            readiness.append(
                _readiness(
                    "CONTRACT_DRAFT",
                    "Проект контракта",
                    "UNKNOWN",
                    "Наличие проекта контракта заявлено без source binding.",
                    blocking=True,
                )
            )
            unknowns.append(
                {"code": "CONTRACT_DRAFT_EVIDENCE", "summary": "Нужна привязка проекта контракта к источнику."}
            )
        else:
            readiness.append(
                _readiness(
                    "CONTRACT_DRAFT",
                    "Проект контракта",
                    "MISSING",
                    "Проект контракта отсутствует или его наличие не подтверждено.",
                    blocking=True,
                )
            )

    profile_bound = isinstance(supplier_profile, dict) and bool(supplier_profile)
    if profile_bound:
        readiness.append(
            _readiness(
                "SUPPLIER_PROFILE",
                "Профиль поставщика",
                "SATISFIED",
                "Профиль поставщика привязан к анализу.",
            )
        )
        criteria = supplier_profile.get("criteria") if isinstance(supplier_profile.get("criteria"), dict) else {}
        price_min = _number(criteria.get("price_min"))
        price_max = _number(criteria.get("price_max"))
        nmck = _number(model.get("nmck"))
        if nmck is not None and nmck_evidence and (price_min is not None or price_max is not None):
            outside = (price_min is not None and nmck < price_min) or (price_max is not None and nmck > price_max)
            readiness.append(
                _readiness(
                    "SUPPLIER_PRICE_RANGE",
                    "Диапазон цены поставщика",
                    "REVIEW" if outside else "SATISFIED",
                    "НМЦК выходит за настроенный диапазон профиля и требует решения оператора."
                    if outside
                    else "НМЦК находится в настроенном диапазоне профиля поставщика.",
                    evidence=nmck_evidence,
                )
            )
    else:
        readiness.append(
            _readiness(
                "SUPPLIER_PROFILE",
                "Профиль поставщика",
                "MISSING",
                "Профиль поставщика не привязан; персональное решение невозможно подтвердить.",
                blocking=True,
            )
        )

    risks = [item for item in model.get("risks", []) or [] if isinstance(item, dict)]
    risk_review_evidence: list[dict[str, Any]] = []
    risk_requires_review = False
    if is_223fz:
        for index, risk in enumerate(risks, start=1):
            evidence = _risk_evidence(model, index)
            risk_review_evidence.extend(evidence)
            unknowns.append(
                {
                    "code": f"223FZ_RISK_{index}_SEMANTICS",
                    "summary": f"Риск «{_text(risk.get('risk') or risk.get('description')) or index}» не классифицируется как hard blocker без утверждённой 223-ФЗ-семантики.",
                }
            )
        readiness.append(
            _readiness(
                "RISK_REVIEW",
                "Риски закупки",
                "REVIEW" if risks else "UNKNOWN",
                "223-ФЗ: риск-семантика требует ручной проверки; 44-ФЗ hard-blocker классификация не наследуется.",
                blocking=True,
                evidence=_dedupe_evidence(risk_review_evidence),
            )
        )
        if not risks:
            unknowns.append(
                {
                    "code": "223FZ_RISK_SEMANTICS",
                    "summary": "Отсутствие риск-флагов не считается подтверждением 223-ФЗ readiness.",
                }
            )
    else:
        for index, risk in enumerate(risks, start=1):
            evidence = _risk_evidence(model, index)
            if not evidence:
                unknowns.append(
                    {
                        "code": f"RISK_{index}_EVIDENCE",
                        "summary": f"Риск «{_text(risk.get('risk') or risk.get('description')) or index}» не имеет source binding.",
                    }
                )
                risk_requires_review = True
                continue
            risk_review_evidence.extend(evidence)
            classification = _text(risk.get("classification")).lower()
            if classification in {"hard_blocker", "confirmed_hard_blocker"} and not bool(risk.get("operator_decision_required")):
                blockers.append(
                    {
                        "code": f"RISK_{index}_HARD_BLOCKER",
                        "summary": _text(risk.get("risk") or risk.get("description")) or "Подтверждённый жёсткий риск.",
                        "hard": True,
                        "evidence": evidence,
                    }
                )
            else:
                risk_requires_review = True

        if risks:
            readiness.append(
                _readiness(
                    "RISK_REVIEW",
                    "Риски закупки",
                    "REVIEW" if risk_requires_review else "SATISFIED",
                    "Риски требуют решения оператора." if risk_requires_review else "Подтверждённые риски не требуют отдельной эскалации.",
                    blocking=risk_requires_review,
                    evidence=_dedupe_evidence(risk_review_evidence),
                )
            )
        else:
            readiness.append(
                _readiness("RISK_REVIEW", "Риски закупки", "SATISFIED", "Подтверждённых риск-флагов для эскалации нет.")
            )

    contradictions = [item for item in model.get("contradictions", []) or [] if item]
    if contradictions:
        readiness.append(
            _readiness(
                "SOURCE_CONSISTENCY",
                "Согласованность источников",
                "REVIEW",
                "В источниках обнаружены противоречия; требуется ручная проверка.",
                blocking=True,
            )
        )
        rationale.append("Обнаружены противоречия между источниками; без ручной проверки решение не может быть безусловным.")
    else:
        readiness.append(
            _readiness("SOURCE_CONSISTENCY", "Согласованность источников", "SATISFIED", "Зафиксированных противоречий источников нет.")
        )

    hard_blockers = [item for item in blockers if item.get("hard")]
    non_satisfied = [item for item in readiness if item.get("status") != "SATISFIED"]
    if hard_blockers:
        status = "NO_GO"
        rationale.insert(0, "Есть подтверждённый жёсткий блокер участия.")
        confidence = "high"
        next_action = "Не подавать заявку по текущей закупке; сохранить доказательства и искать повторную/аналогичную закупку."
    elif non_satisfied or unknowns:
        status = "NEEDS_REVIEW"
        rationale.insert(0, "Недостаточно подтверждённых данных для безусловного GO; требуется ручная проверка.")
        confidence = "medium" if not unknowns else "low"
        next_action = "Закрыть отмеченные пробелы/проверки и повторно оценить участие; внешние действия выполнять только после решения человека."
    else:
        status = "GO"
        rationale.insert(0, "Обязательные условия текущего Decision Core подтверждены источниками; жёстких блокеров не выявлено.")
        confidence = "high"
        next_action = "Перейти к коммерческой проверке и подготовке решения об участии; внешние действия остаются под контролем человека."

    decision_evidence: list[dict[str, Any]] = []
    for item in hard_blockers or readiness:
        if isinstance(item, dict):
            decision_evidence.extend(item.get("evidence") or [])
    decision_evidence = _dedupe_evidence(decision_evidence)

    return {
        "contract_version": DECISION_CORE_CONTRACT_VERSION,
        "procurement_regime": regime,
        "facts": facts,
        "supplier_profile_bound": profile_bound,
        "decision": {
            "status": status,
            "confidence": confidence,
            "rationale": rationale,
            "next_action": next_action,
            "evidence": decision_evidence,
            "human_control_required": True,
            "external_action_allowed": False,
        },
        "blockers": blockers,
        "readiness": readiness,
        "unknowns": unknowns,
        "safety": {
            "bid_submission_allowed": False,
            "rfq_or_invitation_allowed": False,
            "winner_selection_allowed": False,
            "signing_allowed": False,
            "external_commercial_effect_allowed": False,
        },
    }


def legacy_bid_decision(decision_core: dict[str, Any]) -> dict[str, Any]:
    """Project Decision Core into the historical bid_decision shape."""

    decision = decision_core.get("decision") if isinstance(decision_core.get("decision"), dict) else {}
    readiness = [item for item in decision_core.get("readiness", []) or [] if isinstance(item, dict)]
    blockers = [item for item in decision_core.get("blockers", []) or [] if isinstance(item, dict)]
    return {
        "status": _text(decision.get("status")).lower() or "needs_review",
        "rationale": list(decision.get("rationale") or []),
        "blockers": [item.get("summary") for item in blockers if item.get("summary")],
        "conditions": [item.get("summary") for item in readiness if item.get("status") != "SATISFIED"],
        "assumptions": [],
        "confidence": decision.get("confidence") or "low",
        "next_action": decision.get("next_action"),
        "evidence_ids": [
            item.get("source_ref")
            for item in decision.get("evidence", []) or []
            if isinstance(item, dict) and item.get("source_ref")
        ],
    }
