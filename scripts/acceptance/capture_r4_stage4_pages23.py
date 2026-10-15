"""Read-only capture of registered stage4 page 2/3 HTML before selecting any ID."""
from __future__ import annotations

import argparse
import hashlib
import json
import ssl
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from src.modules.benchmark_pipeline.contract import canonical_sha256
from src.modules.tender_operator_agent_demo.r4_stage3_crossvendor_cards import (
    MOS,
    SYNAPS,
)

SOURCE_ORDER = (
    SYNAPS+"?page=2",
    SYNAPS+"?page=3",
    MOS+"?page=2",
    MOS+"?page=3",
)


def validate_stage4_intent(intent: dict) -> None:
    digest = canonical_sha256({k:v for k,v in intent.items() if k!="immutable_intent_sha256"})
    if intent.get("immutable_intent_sha256") != digest:
        raise ValueError("Stage4 immutable source intent changed")
    if intent.get("fixed_order_source_urls") != list(SOURCE_ORDER):
        raise ValueError("Stage4 URL and rank order different from preregistration")
    if intent.get("planned_max_source_candidate_ids") != 12:
        raise ValueError("Stage4 maximum candidate count cannot change")
    if (
        intent.get("sut_inference_authorized") is not False
        or intent.get("gold_labels_authorized") is not False
        or len(intent.get("predecessor_blind_source_lock_shas",[]))!=3
    ):
        raise ValueError("Stage4 cannot use model or omitted prior locks")
    at=datetime.fromisoformat(intent["registered_at_utc"])
    if at.tzinfo is None or at > datetime.now(UTC):
        raise ValueError("Stage4 registration must precede source captures")


def capture_stage4_html(intent: dict, dest: Path) -> dict:
    validate_stage4_intent(intent)
    if dest.exists() and any(dest.iterdir()):
        raise ValueError("Cannot overwrite a prior first-party HTML capture")
    dest.mkdir(parents=True,exist_ok=True)
    status=[]
    for source_rank,url in enumerate(SOURCE_ORDER,1):
        rec={
            "source_rank":source_rank,"url":url,
            "capture_started_at_utc":datetime.now(UTC).isoformat(timespec="seconds"),
            "status":"SOURCE_UNAVAILABLE","relative_html":None,"sha256":None,
        }
        parsed=urlsplit(url)
        if parsed.scheme!="https" or parsed.hostname not in {"synapsenet.ru","mos-tenders.ru"}:
            raise ValueError("Invalid cross-vendor stage4 URL")
        try:
            req=Request(url,headers={"User-Agent":"Arvectum/1.0 firstparty-source-only"})
            with urlopen(req,context=ssl.create_default_context(),timeout=18) as response:
                if response.status!=200 or response.geturl()!=url:
                    raise ValueError("Stage4 source redirect or invalid HTTP")
                if "html" not in (response.headers.get("Content-Type") or "").lower():
                    raise ValueError("Stage4 response content not HTML")
                data=response.read(8_000_001)
                if not 100<=len(data)<=8_000_000:
                    raise ValueError("Stage4 source outside maximum safe size")
                rel=f"original-page-{source_rank}.html"
                (dest/rel).write_bytes(data)
                rec.update(status="TLS_ORIGINAL_SHA_ATTESTED_NOT_SELECTED",
                           relative_html=rel,sha256=hashlib.sha256(data).hexdigest())
        except (OSError,ValueError,HTTPError,URLError,TimeoutError) as exc:
            rec["error_class"]=type(exc).__name__
        status.append(rec)
    result={
        "intent_sha256":intent["immutable_intent_sha256"],
        "source_pages":status,
        "successful_raw_sources":sum(s["status"].startswith("TLS_ORIGINAL") for s in status),
        "sut_predictions_seen":False,
        "human_gold_seen":False,
    }
    (dest/"private-source-capture-receipt.json").write_text(
        json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n",
    )
    return result


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--immutable-intent",type=Path,required=True)
    ap.add_argument("--private-original-html-root",type=Path,required=True)
    x=ap.parse_args()
    out=capture_stage4_html(json.loads(x.immutable_intent.read_text()),x.private_original_html_root)
    print("PREREG_STAGE4_HTML_CAPTURED",out["successful_raw_sources"],"OF",len(SOURCE_ORDER))
    for x in out["source_pages"]:
        print("SOURCE_RANK",x["source_rank"],x["status"],x.get("error_class","NONE"))


if __name__=="__main__":
    main()
