#!/usr/bin/env python3
"""Read-only Mac mini readiness and one exact public EIS-card screen.

Neither this diagnostic nor onboarding's source lookup authorizes EIS mutation.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--customer", required=True)
    parser.add_argument("--reference", default="0372200172326000015")
    parser.add_argument("--getdocs", action="store_true", help="Read-only EIS SOAP document-intake acceptance")
    args = parser.parse_args()
    env = {}
    for line in args.env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            env[key] = value
    auth = (env["AI_CORP_PILOT_AUTH_USERNAME"], env["AI_CORP_PILOT_AUTH_PASSWORD"])
    with httpx.Client(base_url="http://127.0.0.1:18082", auth=auth, timeout=90.0) as client:
        ready = client.get("/health/ready")
        print("READINESS HTTP:", ready.status_code)
        if ready.status_code != 200:
            return 1
        data = ready.json()
        print("READINESS:", data.get("status"),
              "REDIS:", data.get("redis", {}).get("status"),
              "CUSTOMER PILOT:", data.get("feature_readiness", {}).get("customer_pilot_run_start"))
        print("DATA WRITABLE:", data.get("data_writable"))
        print("STORAGE STATUS:", {k: v for k, v in data.get("storage", {}).items()
              if k in ("ingestion_allowed", "gate_reason", "status", "reason", "free_gb", "free_bytes", "used_ratio", "capacity_state")})
        live = client.post(
            f"/api/onboarding/customers/{args.customer}/screen",
            json={"reference": args.reference},
        )
        print("LIVE EIS SCREEN HTTP:", live.status_code)
        if live.status_code == 200:
            body = live.json()
            tender = body["tender"]
            print("LIVE EIS SOURCE:", tender.get("source_status"),
                  "SUBJECT:", tender.get("subject", {}).get("status"),
                  "NMCK:", body.get("profile_checks", {}).get("nmck", {}).get("status"),
                  "CONTROL:", body["decision"])
        else:
            print("LIVE EIS SCREEN FAILED SAFELY; reason category:", live.status_code)
        if args.getdocs:
            docs = client.post("/api/demo/tender-agent/runs/from-eis-docs-archive", json={
                "reestr_number": args.reference, "law": "44fz",
                "subsystem_type": "PRIZ", "download_archive": True,
                "analyze_after_download": False,
            }, timeout=210.0)
            print("LIVE GETDOCS HTTP:", docs.status_code)
            if docs.status_code == 200:
                item = docs.json()
                print("LIVE GETDOCS STATE:", item.get("status"),
                      "RUN:", item.get("run_id"),
                      "FILES:", item.get("downloaded_files_count"))
                if item.get("status") == "ready_to_analyze" and item.get("run_id"):
                    analyze = client.post("/api/demo/tender-agent/runs/" + item["run_id"] + "/analyze", timeout=210.0)
                    print("LIVE DOCUMENT ANALYSIS HTTP:", analyze.status_code)
                    if analyze.status_code == 200:
                        print("LIVE DOCUMENT ANALYSIS STATUS:", analyze.json().get("status"))
            else:
                print("LIVE GETDOCS failed safely, no procurement write:", docs.status_code)
        return 0 if data.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
