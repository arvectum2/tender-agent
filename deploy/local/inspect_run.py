"""Inspect existing bounded Tender Agent run metadata; never reveal document contents."""
import argparse
from pathlib import Path

import httpx


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True)
    p.add_argument("--env-file", type=Path, required=True)
    args = p.parse_args()
    settings = {}
    for raw in args.env_file.read_text().splitlines():
        if "=" in raw and not raw.startswith("#"):
            key, value = raw.split("=", 1)
            settings[key] = value
    auth = (settings["AI_CORP_PILOT_AUTH_USERNAME"], settings["AI_CORP_PILOT_AUTH_PASSWORD"])
    base = "http://127.0.0.1:18082/api/demo/tender-agent/runs/" + args.run
    with httpx.Client(auth=auth, timeout=30) as client:
        for label, ending in [("run",""),("report","/report"),("preanalysis","/pre-analysis"),("events","/events")]:
            response = client.get(base + ending)
            print(label, "HTTP", response.status_code)
            if response.status_code != 200:
                continue
            data = response.json()
            if label == "run":
                names = ["status","analysis_mode","procurement_source","procurement_notice_number","procurement_law","archive_downloaded","archive_download_status","documents_extracted_count","downloaded_files_count","attachments_status"]
                print({name:data.get(name) for name in names})
                print("warning_count", len(data.get("warnings", [])))
                for warning in data.get("warnings", [])[:5]:
                    print("warning", str(warning)[:200])
            elif label == "report":
                core = data.get("decision_core") or {}
                print("report_keys", list(data)[:18])
                print("decision_regime", core.get("procurement_regime"), "unknowns",len(core.get("unknowns",[])),"blockers",len(core.get("blockers",[])))
            elif label == "preanalysis":
                print({key:data.get(key) for key in ["status","decision","human_control_required","external_action_allowed"]})
            else:
                print("event_types",[item.get("event_type") for item in data[-8:]])
if __name__=="__main__":
    main()
