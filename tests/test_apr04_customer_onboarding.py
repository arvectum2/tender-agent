"""APR-04 operator onboarding, durable profile + evidence + cautious screening."""
from types import SimpleNamespace

from src.modules.customer_onboarding import router as module

BASE = "/api/onboarding/customers"


def sample(name="ООО Тестовый поставщик", **changes):
    item = {
        "legal_name": name,
        "inn": None,
        "kpp": None,
        "criteria": {
            "categories": ["Разработка ПО"], "regions": ["Москва"],
            "keywords": ["сайт"], "price_min": 100_000, "price_max": 500_000,
        },
        "commercial": {"target_margin_percent": 20},
        "qualification": {"licenses": ["Синтетическая лицензия"], "sro_approvals": []},
        "risk_preferences": {"tolerance": "low", "require_certificates": True},
    }
    item.update(changes)
    return item


def new_customer(client, name="ООО Тестовый поставщик"):
    response = client.post(BASE, json=sample(name))
    assert response.status_code == 201, response.text
    return response.json()["customer_id"]


def source_card(price=350_000, *, evidence=True):
    cited = ([{"source_ref": "source-card:1", "document": "Карточка ЕИС",
               "locator": "https://zakupki.gov.ru/epz/order/notice/" + "z" * 5}]
             if evidence else [])
    return {
        "contract_version": "fast-cited-preanalysis-v1",
        "initial_price": {"status": "KNOWN" if evidence else "UNKNOWN",
                          "value": price, "citations": cited},
        "subject": {"status": "KNOWN", "value": "Разработка сайта", "citations": cited},
        "decision": "HUMAN_REVIEW_REQUIRED", "external_action_allowed": False,
    }


def test_customer_profile_versioning_and_duplicate_guard(client):
    created = client.post(BASE, json=sample(inn="1234567890", kpp="123456789"))
    assert created.status_code == 201, created.text
    customer_id = created.json()["customer_id"]
    assert created.json()["profile_version"] == 1
    duplicate = client.post(BASE, json=sample(inn="1234567890", kpp="123456789"))
    assert duplicate.status_code == 409
    initial = client.get(f"{BASE}/{customer_id}")
    assert initial.status_code == 200, initial.text
    assert initial.json()["profile"]["criteria"]["price_max"] == 500_000
    assert initial.json()["status"] == "READY_FOR_HUMAN_SCREENING"
    assert initial.json()["documents"] == []
    revision = sample()
    revision.pop("legal_name")
    revision.pop("inn")
    revision.pop("kpp")
    revision["criteria"]["price_max"] = 250_000
    response = client.put(f"{BASE}/{customer_id}/profile", json=revision)
    assert response.status_code == 200, response.text
    assert response.json()["profile_version"] == 2
    updated = client.get(f"{BASE}/{customer_id}").json()
    assert updated["profile_version"] == 2
    assert updated["profile"]["criteria"]["price_max"] == 250_000


def test_onboarding_rejects_unusable_constraints(client):
    invalid = sample()
    invalid["criteria"]["categories"] = []
    invalid["criteria"]["keywords"] = []
    assert client.post(BASE, json=invalid).status_code == 422
    invalid = sample()
    invalid["criteria"]["price_min"] = 600_000
    assert client.post(BASE, json=invalid).status_code == 422
    invalid = sample()
    invalid["commercial"]["target_margin_percent"] = 110
    assert client.post(BASE, json=invalid).status_code == 422
    invalid = sample(inn="not-a-number")
    assert client.post(BASE, json=invalid).status_code == 422


def test_upload_real_pdf_checksum_scope_and_duplicate_guard(client, tmp_path, monkeypatch):
    monkeypatch.setattr(module, "get_settings", lambda: SimpleNamespace(arvectum_data_dir=str(tmp_path)))
    a = new_customer(client, "ООО Документы А")
    b = new_customer(client, "ООО Документы Б")
    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
    form = {
        "document_key": "license_test", "document_type": "LICENSE",
        "display_name": "Синтетическая лицензия",
    }
    uploaded = client.post(f"{BASE}/{a}/documents", data=form,
                           files={"file": ("license.pdf", pdf, "application/pdf")})
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["status"] == "UPLOADED_UNVERIFIED"
    assert uploaded.json()["sha256"]
    state = client.get(f"{BASE}/{a}").json()
    assert len(state["documents"]) == 1
    assert state["documents"][0]["verified_by_operator"] is False
    download = client.get(f"{BASE}/{a}/documents/license_test/download")
    assert download.status_code == 200 and download.content == pdf
    cross = client.get(f"{BASE}/{b}/documents/license_test/download")
    assert cross.status_code == 404
    duplicate = client.post(f"{BASE}/{a}/documents", data=form,
                            files={"file": ("copy.pdf", pdf, "application/pdf")})
    assert duplicate.status_code == 409
    invalid = client.post(f"{BASE}/{b}/documents",
                          data={**form, "document_key": "license_b"},
                          files={"file": ("bad.pdf", b"fake data", "application/pdf")})
    assert invalid.status_code == 415
    assert not list((tmp_path / "company-onboarding" / b).glob("*.pdf")) if (
        tmp_path / "company-onboarding" / b).exists() else True


def test_personalized_screen_uses_only_cited_nmck_and_requires_human(client, monkeypatch):
    a = new_customer(client, "ООО Персонализация")
    b = new_customer(client, "ООО Без профиля")
    monkeypatch.setattr(module, "preanalysis_from_public_search",
                        lambda reference: source_card(350_000))
    r = client.post(f"{BASE}/{a}/screen", json={"reference": "1234567890123456789"})
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["profile_checks"]["nmck"]["status"] == "WITHIN_BOUNDS"
    assert view["profile_checks"]["nmck"]["citations"]
    assert view["profile_checks"]["qualification"]["status"] == "UNKNOWN"
    assert view["human_control_required"] is True
    assert view["external_action_allowed"] is False
    assert view["decision"] == "HUMAN_REVIEW_REQUIRED"
    monkeypatch.setattr(module, "preanalysis_from_public_search",
                        lambda reference: source_card(900_000))
    outside = client.post(f"{BASE}/{a}/screen", json={"reference": "1234567890123456789"})
    assert outside.json()["profile_checks"]["nmck"]["status"] == "OUTSIDE_BOUNDS"
    monkeypatch.setattr(module, "preanalysis_from_public_search",
                        lambda reference: source_card(900_000, evidence=False))
    unknown = client.post(f"{BASE}/{a}/screen", json={"reference": "1234567890123456789"})
    assert unknown.json()["profile_checks"]["nmck"]["status"] == "UNKNOWN"
    # Missing profile state, while the customer exists, must fail closed.
    from src.modules.customer_registry.schemas import CreateCustomerRequest
    from src.modules.customer_registry.service import create_customer
    from src.shared.api.dependencies import get_db_session
    session_override = client.app.dependency_overrides[get_db_session]
    session = next(session_override())
    missing, _ = create_customer(session, CreateCustomerRequest(legal_name="ООО Без профиля 2"))
    miss = client.post(f"{BASE}/{missing.customer_id}/screen",
                       json={"reference": "1234567890123456789"})
    assert miss.status_code == 409
    assert b


def test_onboarding_ui_is_local_operator_flow(client):
    html = client.get("/pilot/onboarding")
    assert html.status_code == 200
    for word in ("Сохранить профиль", "Добавить документ", "Проверить по профилю"):
        assert word in html.text
    assert "https://cdn" not in html.text


def test_existing_analyzed_run_projection_is_profile_bound(client, monkeypatch):
    from types import SimpleNamespace

    customer_id = new_customer(client, "ООО Локальный анализ")
    core = {
        "procurement_regime": "44fz",
        "facts": {
            "nmck": {
                "status": "KNOWN",
                "value": 400000,
                "evidence": [
                    {"source_ref": "synthetic:1", "document": "Синтетический документ",
                     "locator": "page:1", "excerpt": "НМЦК 400000 руб."}
                ],
            }
        },
    }
    monkeypatch.setattr(module, "get_uploaded_demo_report",
                        lambda run_id: SimpleNamespace(decision_core=core))
    result = client.post(f"{BASE}/{customer_id}/runs/test-run/screen", json={})
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["profile_checks"]["nmck"]["status"] == "WITHIN_BOUNDS"
    assert body["profile_checks"]["nmck"]["citations"][0]["source_ref"] == "synthetic:1"
    assert body["profile_version"] == 1
    assert body["external_action_allowed"] is False
    assert body["decision"] == "HUMAN_REVIEW_REQUIRED"
