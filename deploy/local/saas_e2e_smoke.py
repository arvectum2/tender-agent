#!/usr/bin/env python3
"""APR-05 live HTTP, PostgreSQL-backed SaaS E2E; synthetic tenants, real read-only EIS."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import httpx


def checked(response: httpx.Response, expected: int = 200) -> dict:
    if response.status_code != expected:
        raise RuntimeError(f"{response.request.method} {response.request.url.path}: HTTP {response.status_code}, expected {expected}")
    return response.json()


def credentials(path: Path) -> tuple[str, str]:
    values = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    return values["AI_CORP_PILOT_AUTH_USERNAME"], values["AI_CORP_PILOT_AUTH_PASSWORD"]


def profile() -> dict:
    return {
        "criteria": {"categories": ["Разработка ПО"], "regions": ["Москва"],
                     "keywords": ["разработка сайтов"], "price_min": 100_000,
                     "price_max": 900_000},
        "commercial": {"target_margin_percent": 20},
        "qualification": {"licenses": [], "sro_approvals": []},
        "risk_preferences": {"tolerance": "low"},
    }


def legal(c: httpx.Client):
    policy = checked(c.get("/api/saas/legal"))
    checked(c.post("/api/saas/legal/accept", json={
        "terms_version": policy["terms_version"],
        "privacy_version": policy["privacy_version"], "confirm_read": True,
    }))


def new_tenant(operator: httpx.Client, name: str) -> tuple[str, str, str]:
    payload = {"legal_name": name, **profile()}
    created = checked(operator.post("/api/onboarding/customers", json=payload), expected=201)
    company_id = created["customer_id"]
    tenant = checked(operator.post("/api/operator/saas/tenants",
                                   json={"customer_id": company_id, "plan_code": "pilot"}), expected=201)
    assert tenant["payment_collected"] is False
    return company_id, tenant["tenant_id"], tenant["invitation"]["invitation_code"]


def redeem(url: str, code: str, name: str) -> tuple[httpx.Client, dict]:
    r = httpx.post(url + "/api/saas/invitations/redeem",
                   json={"invitation_code": code, "display_name": name}, timeout=30)
    body = checked(r, expected=201)
    c = httpx.Client(base_url=url, headers={"Authorization": "Bearer " + body["access_token"]},
                     timeout=240.0, follow_redirects=False, trust_env=False)
    return c, body


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--url", default="http://127.0.0.1:18082")
    parser.add_argument("--real-eis", action="store_true")
    args = parser.parse_args()
    if args.url != "http://127.0.0.1:18082":
        raise ValueError("APR-05 accepts only loopback Mac mini E2E endpoint")
    name = "ООО Синтетический SaaS " + uuid4().hex[:8]
    evidence = {"contract": "apr05-macmini-saas-e2e-v1", "synthetic_tenants": True, "checks": {}}
    with httpx.Client(base_url=args.url, auth=credentials(args.env_file), timeout=240.0,
                      follow_redirects=False, trust_env=False) as operator:
        assert checked(operator.get("/health/ready"))["status"] == "ok"
        public = httpx.get(args.url + "/saas", timeout=15.0, trust_env=False)
        assert public.status_code == 200
        packages = checked(httpx.get(args.url + "/api/saas/packages", trust_env=False))
        assert packages["online_checkout_enabled"] is False
        assert all(package["price_rub"] is None for package in packages["packages"].values())
        evidence["checks"]["api_packages_offline"] = "pass"
        company_a, tenant_a, invite_a = new_tenant(operator, name + " A")
        company_b, tenant_b, invite_b = new_tenant(operator, name + " B")
        evidence["checks"]["operator_bootstrap"] = "pass"
        a, owner_a = redeem(args.url, invite_a, "Владелец компании A")
        b, owner_b = redeem(args.url, invite_b, "Владелец компании B")
        with a, b:
            assert a.get("/api/saas/me").status_code == 200
            assert b.get("/api/saas/me").status_code == 200
            assert a.get("/api/onboarding/customers/" + company_b).status_code == 401
            assert b.get("/api/onboarding/customers/" + company_a).status_code == 401
            assert a.put("/api/saas/profile", json=profile()).status_code == 428
            legal(a)
            legal(b)
            evidence["checks"]["separate_bearer_and_legal"] = "pass"
            saved = checked(a.put("/api/saas/profile", json=profile()))
            assert saved["profile_version"] == 2
            assert checked(b.get("/api/saas/profile"))["customer_id"] == company_b
            assert checked(b.get("/api/saas/profile"))["profile_version"] == 1
            evidence["checks"]["tenant_profile_isolation"] = "pass"
            pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
            upload = checked(a.post("/api/saas/documents", data={
                "document_key": "saas_test_document", "document_type": "LICENSE",
                "display_name": "Синтетический документ",
            }, files={"file": ("synthetic.pdf", pdf, "application/pdf")}), expected=201)
            assert upload["sha256"] == hashlib.sha256(pdf).hexdigest()
            assert a.get("/api/saas/documents/saas_test_document/download").content == pdf
            assert b.get("/api/saas/documents/saas_test_document/download").status_code == 404
            evidence["checks"]["pdf_tenant_boundary"] = "pass"

            files = [
                ("files", ("notice.txt", b"Notice: development of public website", "text/plain")),
                ("files", ("technical_spec.txt", b"Technical requirements: CMS and delivery", "text/plain")),
                ("files", ("contract_draft.txt", b"Contract: approval, risk and payment", "text/plain")),
            ]
            run = checked(a.post("/api/saas/runs", data={
                "tender_title": "Синтетическая разработка сайта", "tender_category": "ИТ",
            }, files=files), expected=201)
            run_id = run["run_id"]
            assert b.get("/api/saas/runs/" + run_id + "/report").status_code == 404
            assert b.post("/api/saas/runs/" + run_id + "/analyze").status_code == 404
            analyzed = checked(a.post("/api/saas/runs/" + run_id + "/analyze"))
            assert analyzed["status"] in {"completed", "completed_with_warnings", "needs_review"}
            assert a.post("/api/saas/runs/" + run_id + "/analyze").status_code == 409
            report = checked(a.get("/api/saas/runs/" + run_id + "/report"))
            assert report["run_id"] == run_id and report["external_action_allowed"] is False
            fit = checked(a.post("/api/saas/runs/" + run_id + "/screen"))
            assert fit["decision"] == "HUMAN_REVIEW_REQUIRED"
            evidence["checks"]["tenant_owned_tender_analysis"] = "pass"

            invited = checked(a.post("/api/saas/invitations",
                                     json={"role": "viewer", "acquisition_channel": "referral"}))
            viewer, detail = redeem(args.url, invited["invitation_code"], "Сотрудник-наблюдатель")
            with viewer:
                assert viewer.post("/api/saas/runs/" + run_id + "/analyze").status_code == 403
                legal(viewer)
                assert viewer.get("/api/saas/runs/" + run_id + "/report").status_code == 200
                assert viewer.put("/api/saas/profile", json=profile()).status_code == 403
                revoked = checked(a.post("/api/saas/members/" + detail["member_id"] + "/revoke"))
                assert revoked["active"] is False
                assert viewer.get("/api/saas/me").status_code == 401
            evidence["checks"]["roles_invites_revocation"] = "pass"

            if args.real_eis:
                eis = checked(a.post("/api/saas/runs/from-eis",
                                     json={"reference": "0372200172326000015"}), expected=201)
                assert eis["downloaded_files_count"] >= 1
                assert b.post("/api/saas/runs/" + eis["run_id"] + "/screen").status_code == 404
                if eis["status"] == "ready_to_analyze":
                    doc_analysis = checked(a.post("/api/saas/runs/" + eis["run_id"] + "/analyze"))
                    assert doc_analysis["status"] in {"completed", "completed_with_warnings", "needs_review"}
                    readback = checked(a.get("/api/saas/runs/" + eis["run_id"] + "/report"))
                    assert readback["human_control_required"]
                evidence["checks"]["real_eis_getdocs_tenant_bound"] = eis["status"]

            usage_a = checked(a.get("/api/saas/usage"))
            usage_b = checked(b.get("/api/saas/usage"))
            assert usage_a["metrics"]["screens"]["used"] >= 1
            assert usage_a["metrics"]["runs"]["used"] >= 1
            assert usage_b["metrics"]["runs"]["used"] == 0
            metrics = checked(a.get("/api/saas/metrics"))
            assert metrics["acquisition"]["activated_members"] >= 1
            assert metrics["product_metrics"]["owned_tender_runs"] >= 1
            evidence["checks"]["quotas_metrics_separate"] = "pass"
            assert owner_a["tenant_id"] == tenant_a and owner_b["tenant_id"] == tenant_b
            assert checked(a.post("/api/saas/logout"))["revoked"] is True
            assert a.get("/api/saas/me").status_code == 401
            evidence["checks"]["logout_revokes_secret"] = "pass"
            evidence["synthetic_company_ids"] = [company_a, company_b]
            evidence["synthetic_tenant_ids"] = [tenant_a, tenant_b]
            evidence["result"] = "PASS"
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
