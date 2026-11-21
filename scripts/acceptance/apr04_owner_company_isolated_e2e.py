"""Private APR04 company-onboarding E2E with owner-provided corporate identity.

Input identity stays in private Mac runtime, never source control.
Only a deliberately synthetic PDF exercises document storage; original official
registration PDFs are *not* claimed to have been uploaded to Mac mini.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from secrets import token_urlsafe

LEGACY_ROOT = Path("/Volumes/ArvectumSSD/Arvectum/runtime/ta-apr04-owner-onboarding-20261015")
RUN_ID = "toa-run-20261012200402-7249ed"
RECEIPT = "output/apr04_owner_onboarding_e2e_receipt.json"


def _run(root: Path) -> int:
    identity_file = root / "company-identity-private.json"
    if (not identity_file.is_file() or not root.name.startswith("ta-apr04-replay-")
            or root.parent.resolve() != Path("/tmp").resolve()
            or (root / "apr04-isolated.sqlite").exists()):
        raise RuntimeError("APR04 isolated private runtime was not initialized")
    profile = json.loads(identity_file.read_text())
    assert len(profile["inn"]) == 10 and len(profile["kpp"]) == 9
    assert len(profile["documents_offline_not_uploaded"]) == 2
    original_id = RUN_ID
    report_path = root / "runs" / original_id / "output" / "report.json"
    source_report_sha = hashlib.sha256(report_path.read_bytes()).hexdigest()
    runtime_password = token_urlsafe(32)
    os.environ.update({
        "AI_CORP_DATABASE_URL": "sqlite:///" + str(root / "apr04-isolated.sqlite"),
        "AI_CORP_ARVECTUM_DATA_DIR": str(root / "data"),
        "AI_CORP_TENDER_OPERATOR_DEMO_RUNS_DIR": str(root / "runs"),
        "AI_CORP_PILOT_AUTH_ENABLED": "true",
        "AI_CORP_PILOT_AUTH_USERNAME": "apr04-local-operator",
        "AI_CORP_PILOT_AUTH_PASSWORD": runtime_password,
        "AI_CORP_PILOT_AUTH_PROTECTED_PREFIXES": "/api,/pilot",
        "AI_CORP_PILOT_AUTH_PUBLIC_PATHS": "/health",
    })
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from src.modules.customer_onboarding.router import router
    from src.shared.api.dependencies import get_db_session
    from src.shared.api.errors import register_exception_handlers
    from src.shared.api.middleware import TenderPilotBasicAuthMiddleware
    from src.shared.config.settings import get_settings
    from src.shared.db import models as _models  # noqa: F401
    from src.shared.db.base import Base

    get_settings.cache_clear()
    assert get_settings().pilot_auth_password_safe()
    engine = create_engine(os.environ["AI_CORP_DATABASE_URL"])
    Base.metadata.create_all(engine)
    api = FastAPI()
    register_exception_handlers(api)
    api.include_router(router)
    api.add_middleware(
        TenderPilotBasicAuthMiddleware,
        username="apr04-local-operator", password=runtime_password,
        protected=("/api", "/pilot"), public=("/health",),
    )

    def isolated_session():
        with Session(engine) as session:
            yield session

    api.dependency_overrides[get_db_session] = isolated_session
    headers = {
        "Authorization": "Basic " + base64.b64encode(
            ("apr04-local-operator:" + runtime_password).encode()
        ).decode()
    }
    base = "/api/onboarding/customers"
    checks: dict[str, object] = {}
    create = {
        "legal_name": profile["legal_name"],
        "inn": profile["inn"], "kpp": profile["kpp"],
        **profile["constraints"],
    }
    with TestClient(api) as client:
        checks["onboarding_no_auth"] = client.get("/pilot/onboarding").status_code
        checks["customer_create_no_auth"] = client.post(base, json=create).status_code
        checks["ui_auth"] = client.get("/pilot/onboarding", headers=headers).status_code
        response = client.post(base, json=create, headers=headers)
        checks["customer_create"] = response.status_code
        assert response.status_code == 201, response.text[:250]
        customer = response.json()["customer_id"]
        checks["company_id"] = customer
        checks["initial_profile_version"] = response.json()["profile_version"]
        assert response.json()["documents_verified"] is False
        duplicate = client.post(base, json=create, headers=headers)
        checks["duplicate_guard"] = duplicate.status_code
        initial = client.get(base + "/" + customer, headers=headers)
        checks["profile_reopened"] = initial.status_code
        actual = initial.json()
        assert actual["legal_name"] == profile["legal_name"]
        assert actual["inn"] == profile["inn"] and actual["kpp"] == profile["kpp"]
        assert actual["profile"]["criteria"]["price_min"] is None
        assert actual["profile"]["criteria"]["price_max"] is None
        assert not actual["profile"]["qualification"]["licenses"]
        assert actual["documents"] == []
        checks["profile_version"] = actual["profile_version"]

        # Price, licenses, profit and eligibility must not be treated as known
        # when the owner has supplied only registration records, not limits.
        screen = client.post(base + "/" + customer + "/runs/" + original_id + "/screen",
                             headers=headers)
        checks["archived_eis_screen_http"] = screen.status_code
        assert screen.status_code == 200, screen.text[:350]
        first = screen.json()
        checks["archived_eis_price_check"] = first["profile_checks"]["nmck"]["status"]
        checks["archived_eis_price_cited"] = bool(first["profile_checks"]["nmck"]["citations"])
        checks["qualification_check"] = first["profile_checks"]["qualification"]["status"]
        checks["margin_check"] = first["profile_checks"]["margin_and_risks"]["status"]
        checks["decision"] = first["decision"]
        checks["external_action_allowed"] = first["external_action_allowed"]
        assert checks["archived_eis_price_check"] == "UNKNOWN"
        assert checks["archived_eis_price_cited"] is True
        assert checks["qualification_check"] == checks["margin_check"] == "UNKNOWN"
        assert checks["decision"] == "HUMAN_REVIEW_REQUIRED"
        assert first["external_action_allowed"] is False

        # Exercise versioning with test-only commercial bounds, then restore
        # UNKNOWN so the final profile contains NO invented business choices.
        bounded = json.loads(json.dumps(profile["constraints"]))
        bounded["criteria"]["price_min"] = 900000
        bounded["criteria"]["price_max"] = 1100000
        revised = client.put(base + "/" + customer + "/profile",
                             headers=headers, json=bounded)
        checks["test_bound_update"] = revised.status_code
        bounded_screen = client.post(
            base + "/" + customer + "/runs/" + original_id + "/screen", headers=headers
        )
        checks["test_bound_nmck_status"] = bounded_screen.json()["profile_checks"]["nmck"]["status"]
        assert checks["test_bound_nmck_status"] == "WITHIN_BOUNDS"
        restored = client.put(base + "/" + customer + "/profile",
                              headers=headers, json=profile["constraints"])
        checks["restored_profile_version"] = restored.json()["profile_version"]

        # Synthetic fixture only: upload+read+cross-customer isolation is real
        # HTTP/filesystem, but it is NOT a tax record or regulatory approval.
        example_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
        evidence_form = {
            "document_key": "test_placeholder_01", "document_type": "STATUTORY",
            "display_name": "Synthetic APR04 storage probe, NOT official registration",
        }
        uploaded = client.post(base + "/" + customer + "/documents",
                               headers=headers, data=evidence_form,
                               files={"file": ("synthetic.pdf", example_pdf, "application/pdf")})
        checks["synthetic_document_uploaded"] = uploaded.status_code
        assert uploaded.status_code == 201, uploaded.text[:250]
        assert uploaded.json()["status"] == "UPLOADED_UNVERIFIED"
        downloaded = client.get(base + "/" + customer + "/documents/test_placeholder_01/download",
                                headers=headers)
        checks["synthetic_document_roundtrip"] = (
            downloaded.status_code == 200 and downloaded.content == example_pdf
        )
        after = client.get(base + "/" + customer, headers=headers).json()
        checks["synthetic_document_stays_unverified"] = (
            len(after["documents"]) == 1
            and after["documents"][0]["verified_by_operator"] is False
        )
        assert checks["synthetic_document_roundtrip"] is True
        assert checks["synthetic_document_stays_unverified"] is True
        assert after["profile_version"] == 3
        assert after["profile"]["criteria"]["price_min"] is None
        assert after["profile"]["criteria"]["price_max"] is None
        final_screen = client.post(base + "/" + customer + "/runs/" + original_id + "/screen",
                                   headers=headers)
        assert final_screen.status_code == 200
        assert final_screen.json()["profile_checks"]["nmck"]["status"] == "UNKNOWN"
        checks["final_profile_nmck_status"] = "UNKNOWN"
        assert hashlib.sha256(report_path.read_bytes()).hexdigest() == source_report_sha

        # Audit across separate customer boundary, without touching external data.
        other = client.post(base, headers=headers, json={
            **create, "legal_name": "ООО Синтетический контроль изоляции",
            "inn": None, "kpp": None,
        })
        assert other.status_code == 201
        other_id = other.json()["customer_id"]
        other_request = client.get(base + "/" + other_id
                                   + "/documents/test_placeholder_01/download",
                                   headers=headers)
        checks["cross_customer_document"] = other_request.status_code
        assert other_request.status_code == 404
    with Session(engine) as session:
        from src.modules.customer_onboarding.router import _profile
        persisted, version, state = _profile(session, customer)
        checks["database_session_reopen"] = (
            state == "ACTIVE" and version == 3
            and persisted["criteria"]["price_max"] is None
        )
        assert checks["database_session_reopen"]

    checks.update({
        "source_notice_number": "0372200172326000015",
        "source_report_sha256_unchanged": source_report_sha,
        "actual_official_pdfs_copied_to_remote": False,
        "actual_company_identity_registered_with_documentary_fields": True,
        "corporate_documents_offline_source_hashes": [
            x["source_sha256"] for x in profile["documents_offline_not_uploaded"]
        ],
        "licenses_verified": False,
        "go_permission": False, "etp_actions": False,
        "external_emails": False, "legal_bid_approval": False,
    })
    output = root / RECEIPT
    output.write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n")
    print("APR04_E2E_RESULT", json.dumps({
        k: checks[k] for k in (
            "ui_auth", "onboarding_no_auth", "customer_create", "duplicate_guard",
            "profile_reopened", "archived_eis_screen_http",
            "archived_eis_price_check", "qualification_check",
            "decision", "test_bound_nmck_status", "restored_profile_version",
            "synthetic_document_roundtrip", "cross_customer_document",
            "database_session_reopen",
        )
    }, ensure_ascii=False), flush=True)
    return 0


def evidence_inventory(root: Path) -> dict[str, str]:
    """Bounded original files only; no old database or uploaded documents."""
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Invalid historical source root")
    run = root / "runs" / RUN_ID
    if not run.is_dir() or run.is_symlink() or (root / "runs").is_symlink() or (root / "output").is_symlink():
        raise ValueError("Invalid historical source directories")
    members = list(run.rglob("*"))
    if len(members) > 128 or any(p.is_symlink() for p in members):
        raise ValueError("Unsafe saved run tree")
    paths = [root / "company-identity-private.json", root / RECEIPT] + [p for p in members if p.is_file()]
    if any(p.is_symlink() or not p.is_file() for p in paths) or sum(p.stat().st_size for p in paths) > 20_000_000:
        raise ValueError("Unsafe or oversize replay inputs")
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def verify_legacy(root: Path) -> dict[str, str]:
    inventory = evidence_inventory(root)
    prev = json.loads((root / RECEIPT).read_bytes())
    identity = json.loads((root / "company-identity-private.json").read_bytes())
    if (inventory.get(f"runs/{RUN_ID}/output/report.json") != prev.get("source_report_sha256_unchanged")
            or [v["source_sha256"] for v in identity["documents_offline_not_uploaded"]] != prev.get("corporate_documents_offline_source_hashes")
            or prev.get("actual_official_pdfs_copied_to_remote") is not False
            or prev.get("go_permission") is not False):
        raise ValueError("Historical receipt binding mismatch")
    return inventory


def main() -> int:
    try:
        before = verify_legacy(LEGACY_ROOT)
        with tempfile.TemporaryDirectory(prefix="ta-apr04-replay-", dir="/tmp") as tmp:
            root = Path(tmp)
            (root / "output").mkdir(mode=0o700)
            for relative, sha in before.items():
                if relative == RECEIPT:
                    continue
                target = root / relative
                target.parent.mkdir(mode=0o700, exist_ok=True, parents=True)
                shutil.copyfile(LEGACY_ROOT / relative, target)
                target.chmod(0o600)
                if hashlib.sha256(target.read_bytes()).hexdigest() != sha:
                    raise ValueError("Copied input digest mismatch")
            proc = subprocess.run([sys.executable, "-c",
                "from pathlib import Path; import sys; from scripts.acceptance.apr04_owner_company_isolated_e2e import _run; raise SystemExit(_run(Path(sys.argv[1])))", str(root)],
                check=False, capture_output=True, text=True, timeout=90)
            if proc.returncode:
                # Never print subprocess output: failed HTTP assertions can include private values.
                raise RuntimeError("Private isolated workflow failed")
            result = json.loads((root / RECEIPT).read_bytes())
            if (result.get("source_report_sha256_unchanged") != before[f"runs/{RUN_ID}/output/report.json"]
                    or result.get("go_permission") is not False
                    or not result.get("database_session_reopen")):
                raise ValueError("Replay receipt mismatch")
            for relative, sha in before.items():
                if relative != RECEIPT and hashlib.sha256((root / relative).read_bytes()).hexdigest() != sha:
                    raise ValueError("Replay input changed")
        if verify_legacy(LEGACY_ROOT) != before:
            raise ValueError("Historical source changed")
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError):
        print("APR04_DISPOSABLE_REPLAY_BLOCKED: private evidence or isolated workflow failed", file=sys.stderr)
        return 2
    safe_keys = ("ui_auth", "onboarding_no_auth", "customer_create", "duplicate_guard", "profile_reopened",
                 "archived_eis_screen_http", "archived_eis_price_check", "qualification_check", "decision",
                 "test_bound_nmck_status", "restored_profile_version", "synthetic_document_roundtrip",
                 "cross_customer_document", "database_session_reopen", "go_permission")
    print("APR04_DISPOSABLE_REPLAY_PASS", json.dumps({k: result[k] for k in safe_keys}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
