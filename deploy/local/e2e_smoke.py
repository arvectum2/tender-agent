#!/usr/bin/env python3
"""APR-04 real-HTTP synthetic local end-to-end smoke; no bids, no external writes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import httpx


def load_operator_auth(path: Path) -> tuple[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    user = values.get("AI_CORP_PILOT_AUTH_USERNAME", "")
    password = values.get("AI_CORP_PILOT_AUTH_PASSWORD", "")
    if not user or not password:
        raise RuntimeError("operator auth not configured")
    return user, password


def checked(response: httpx.Response, *, expected=200) -> dict:
    if response.status_code != expected:
        raise RuntimeError(f"Unexpected HTTP {response.status_code} from {response.request.url.path}")
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--url", default="http://127.0.0.1:18082")
    args = parser.parse_args()
    if args.url != "http://127.0.0.1:18082":
        raise RuntimeError("Local-only acceptance must target the canonical Mac mini loopback port")
    auth = load_operator_auth(args.env_file)
    evidence = {"contract": "apr04-local-e2e-v1", "synthetic": True, "steps": {}}
    with httpx.Client(base_url=args.url, auth=auth, timeout=300.0, follow_redirects=False) as client:
        with httpx.Client(base_url=args.url, timeout=15) as anonymous:
            if anonymous.get("/pilot/onboarding").status_code != 401:
                raise RuntimeError("Basic-auth guard did not protect onboarding UI")
        if client.get("/pilot/onboarding").status_code != 200:
            raise RuntimeError("Onboarding HTML not reachable with operator authentication")
        evidence["steps"]["operator_auth"] = "pass"
        checked(client.get("/health"))
        evidence["steps"]["api_health"] = "pass"
        name = "ООО Синтетический APR04 " + uuid4().hex[:10]
        created = checked(client.post("/api/onboarding/customers", json={
            "legal_name": name,
            "criteria": {"categories": ["Разработка сайтов"], "regions": ["Москва"],
                         "keywords": ["сайт"], "price_min": 100000, "price_max": 900000},
            "commercial": {"target_margin_percent": 20},
            "qualification": {"licenses": [], "sro_approvals": []},
            "risk_preferences": {"tolerance": "low"},
        }), expected=201)
        cid = created["customer_id"]
        evidence["steps"]["company_created"] = "pass"
        profile = checked(client.get(f"/api/onboarding/customers/{cid}"))
        if profile["profile_version"] != 1 or profile["profile"]["criteria"]["price_max"] != 900000:
            raise RuntimeError("Profile was not persisted")
        evidence["steps"]["company_profile_readback"] = "pass"
        revision = profile["profile"].copy()
        revision["criteria"]["price_max"] = 750000
        updated = checked(client.put(f"/api/onboarding/customers/{cid}/profile", json=revision))
        if updated["profile_version"] != 2:
            raise RuntimeError("Profile version did not advance")
        evidence["steps"]["profile_versioning"] = "pass"

        pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
        result = checked(client.post(
            f"/api/onboarding/customers/{cid}/documents",
            data={"document_key": "synthetic_license", "document_type": "LICENSE",
                  "display_name": "Синтетическая лицензия (не настоящая)"},
            files={"file": ("synthetic.pdf", pdf, "application/pdf")},
        ), expected=201)
        if result["sha256"] != hashlib.sha256(pdf).hexdigest():
            raise RuntimeError("Onboarding checksum mismatch")
        downloaded = client.get(f"/api/onboarding/customers/{cid}/documents/synthetic_license/download")
        if downloaded.status_code != 200 or downloaded.content != pdf:
            raise RuntimeError("Document download round trip failed")
        evidence["steps"]["reusable_pdf_evidence"] = "pass"

        title = "Синтетическая закупка APR04: разработка сайта"
        data = {"tender_title": title, "tender_category": "Разработка сайтов",
                "customer_name": "Вымышленный заказчик", "target_margin_percent": "20"}
        files = [
            ("files", ("notice.txt", "Извещение: разработка сайта. НМЦК 650000 руб.".encode(), "text/plain")),
            ("files", ("technical_spec.txt",
                       "Техническое задание: создание сайта и сопровождение 12 месяцев.".encode(),
                       "text/plain")),
            ("files", ("contract_draft.txt",
                       "Проект договора: сдача работ, оплата после приёмки.".encode(), "text/plain")),
        ]
        run = checked(client.post("/api/demo/tender-agent/runs", data=data, files=files))
        run_id = run["run_id"]
        evidence["steps"]["tender_documents_uploaded"] = "pass"
        analyzed = checked(client.post(f"/api/demo/tender-agent/runs/{run_id}/analyze"))
        if analyzed["status"] not in ("completed", "completed_with_warnings", "needs_review"):
            raise RuntimeError("Tender analysis is not terminal")
        evidence["steps"]["tender_analysis"] = analyzed["status"]
        report = checked(client.get(f"/api/demo/tender-agent/runs/{run_id}/report"))
        if report.get("run_id") != run_id:
            raise RuntimeError("Report not linked to tender run")
        evidence["steps"]["report_retrieval"] = "pass"
        personalization = checked(client.post(
            f"/api/onboarding/customers/{cid}/runs/{run_id}/screen", json={}))
        if personalization.get("decision") != "HUMAN_REVIEW_REQUIRED" or personalization.get("external_action_allowed"):
            raise RuntimeError("Human review gate violated")
        if personalization.get("profile_version") != 2:
            raise RuntimeError("Personalization not bound to latest profile version")
        evidence["steps"]["personalized_cited_assessment"] = "human_review_required"
        evidence["company_id"] = cid
        evidence["tender_run_id"] = run_id
        evidence["result"] = "PASS"
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
