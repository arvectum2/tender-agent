"""Read-only, source-locked R4 XML-field LLM benchmark, not human gold.

Original official getDocsIP ZIP files stay outside git. No Data Platform API writes,
procurement decisions, or LLM quality claims about original attachments.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from audit_r5_official_sources import audit_archive, local_name

REGISTRY = re.compile(r"[0-9]{19}\Z")
FIELDS = ("purchase_number", "notice_version", "deadline", "max_price_rub")
TAG_NAMES = ("purchaseNumber", "endDT", "maxPrice")


def _matching_notice(root: ET.Element, number: str, version: int) -> ET.Element:
    matches = []
    for node in root.iter():
        if not local_name(node.tag).startswith("epNotification"):
            continue
        numbers = {(child.text or "").strip() for child in node.iter()
                   if local_name(child.tag) == "purchaseNumber"}
        direct_versions = [(child.text or "").strip() for child in node
                           if local_name(child.tag) == "versionNumber"]
        if number in numbers and direct_versions == [str(version)]:
            matches.append(node)
    if len(matches) != 1:
        raise ValueError("ambiguous_or_missing_verified_notice")
    return matches[0]


def _source_fragments(archive_file: Path, *, xml_sha: str, number: str,
                      version: int) -> str:
    source = []
    with zipfile.ZipFile(archive_file) as archive:
        for member in archive.infolist():
            if member.filename.lower().endswith(".xml"):
                data = archive.read(member)
                if hashlib.sha256(data).hexdigest() == xml_sha:
                    source.append(data)
    if len(source) != 1:
        raise ValueError("nonunique_original_notice_xml")
    notice = _matching_notice(ET.fromstring(source[0]), number, version)
    relevant = [child for child in notice.iter() if local_name(child.tag) in TAG_NAMES]
    versions = [child for child in notice if local_name(child.tag) == "versionNumber"]
    if len(versions) != 1:
        raise ValueError("ambiguous_direct_version")
    relevant.append(versions[0])
    if len(relevant) > 80:
        raise ValueError("too_many_fact_nodes")
    # Fragments are reserialized nodes from the independently hashed original
    # official XML, not raw-byte exact citation offsets or semantic gold labels.
    excerpt = "\n".join(ET.tostring(node, encoding="unicode") for node in relevant)
    if len(excerpt) > 16000:
        raise ValueError("source_excerpt_too_long")
    return excerpt


def build_case(row: dict[str, str], archives: Path) -> dict:
    number = row["reg_number"]
    if not REGISTRY.fullmatch(number) or row["official_SOAP_status"] != "completed":
        raise ValueError("invalid_or_unavailable_eis_case")
    zip_file = archives / number / "documentation-archive.zip"
    audited = audit_archive(zip_file, number)
    if audited["zip_sha256"] != row["official_zip_sha256"]:
        raise ValueError("official_zip_sha_mismatch")
    latest = audited["highest"]
    if str(latest["version"]) != row["highest_official_archived_version"]:
        raise ValueError("official_archive_version_mismatch")
    if latest["endDT"] != (row["highest_archive_endDT"] or None):
        raise ValueError("official_deadline_mismatch")
    csv_amount = row["highest_archive_max_price_RUB"]
    if (Decimal(latest["maxPrice"]) if latest["maxPrice"] else None) != (
        Decimal(csv_amount) if csv_amount else None
    ):
        raise ValueError("official_price_mismatch")
    if latest["endDT_ambiguity"] or latest["maxPrice_ambiguity"]:
        raise ValueError("ambiguous_official_source_facts")
    return {
        "reg_number": number,
        "official_zip_sha256": audited["zip_sha256"],
        "original_notice_xml_sha256": latest["xml_sha256"],
        "source_excerpt": _source_fragments(zip_file, xml_sha=latest["xml_sha256"],
                                             number=number, version=latest["version"]),
        "oracle": {
            "purchase_number": number,
            "notice_version": latest["version"],
            "deadline": latest["endDT"],
            "max_price_rub": latest["maxPrice"],
        },
    }


def score(expected: dict, answer: object) -> dict:
    if not isinstance(answer, dict) or set(answer) != set(FIELDS):
        return {field: False for field in FIELDS}
    verdict = {}
    for field in FIELDS:
        actual, gold = answer[field], expected[field]
        if field == "max_price_rub" and actual is not None and gold is not None:
            try:
                verdict[field] = Decimal(str(actual)) == Decimal(str(gold))
            except (InvalidOperation, ValueError, TypeError):
                verdict[field] = False
        elif field == "notice_version":
            verdict[field] = type(actual) is int and actual == gold
        else:
            verdict[field] = actual == gold and (actual is None or isinstance(actual, str))
    return verdict


def ask_model(endpoint: str, model: str, fragments: str, timeout: int) -> tuple[object, float]:
    system = (
        "Extract four facts from this official Russian EIS notice XML. "
        "Output a single JSON object with exactly these keys: "
        "purchase_number (string or null), notice_version (integer or null), "
        "deadline (original ISO date-time string or null), "
        "max_price_rub (decimal string or null). "
        "Use only the supplied XML nodes; absent or conflicting values must be null. "
        "Do not infer legal compliance, current auction status, winner, or bid decision."
    )
    request_body = json.dumps({
        "model": model, "temperature": 0, "max_tokens": 420,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": fragments}],
    }).encode()
    request = Request(endpoint + "/v1/chat/completions", request_body,
                      headers={"Content-Type": "application/json"}, method="POST")
    started = time.monotonic()
    with urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    elapsed = time.monotonic() - started
    raw = payload["choices"][0]["message"]["content"]
    return json.loads(raw), round(elapsed, 2)


def run(rows: list[dict[str, str]], archives: Path, endpoint: str, model: str,
        timeout: int, limit: int, dry_run: bool) -> dict:
    if endpoint not in ("http://127.0.0.1:8081", "http://localhost:8081"):
        raise ValueError("non_loopback_or_unapproved_model_endpoint")
    if len(rows) != 20 or len({row["reg_number"] for row in rows}) != 20:
        raise ValueError("expected_exactly_20_unique_cases")
    selected = [row for row in rows if row["official_SOAP_status"] == "completed"]
    if len(selected) != 17 or sum(x["official_SOAP_status"] == "no_data" for x in rows) != 3:
        raise ValueError("unexpected_official_transport_distribution")
    if limit < 1 or limit > 17:
        raise ValueError("invalid_case_limit")
    output = {"scope": "SOURCE_LOCKED_AUTOMATED_XML_FIELDS_NOT_HUMAN_GOLD",
              "model": model, "live_dp_originals_verified": False,
              "human_gold_reviewed": False, "owner_signoffs": 0,
              "original_binary_eis_verified": False, "no_data_cases": 3,
              "cases": []}
    for row in selected[:limit]:
        case = build_case(row, archives)
        stored = {k: case[k] for k in ("reg_number", "official_zip_sha256",
                                      "original_notice_xml_sha256", "oracle")}
        if dry_run:
            stored["model_status"] = "not_called_dry_run"
        else:
            try:
                answer, duration = ask_model(endpoint, model, case["source_excerpt"], timeout)
                marks = score(case["oracle"], answer)
                stored.update(model_status="evaluated", seconds=duration,
                              correct_fields=sum(marks.values()), total_fields=len(FIELDS),
                              field_scores=marks, unsupported_null_ok=all(
                                  answer.get(k) is None for k, v in case["oracle"].items()
                                  if v is None) if isinstance(answer, dict) else False)
            except (HTTPError, URLError, TimeoutError, KeyError, ValueError, TypeError) as exc:
                stored.update(model_status="unavailable_or_invalid",
                              error_type=type(exc).__name__, correct_fields=0,
                              total_fields=len(FIELDS))
        output["cases"].append(stored)
    output["summary"] = {
        "official_archives_checked": len(output["cases"]),
        "evaluated": sum(x["model_status"] == "evaluated" for x in output["cases"]),
        "correct_fields": sum(x.get("correct_fields", 0) for x in output["cases"]),
        "total_fields": sum(x.get("total_fields", 0) for x in output["cases"]),
        "entire_cases_correct": sum(x.get("correct_fields") == len(FIELDS)
                                    for x in output["cases"]),
    }
    return output


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source-csv", required=True, type=Path)
    p.add_argument("--archive-dir", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--model", default="arvectum-gemma4-12b-it-qat-q4_0")
    p.add_argument("--endpoint", default="http://127.0.0.1:8081")
    p.add_argument("--timeout", type=int, default=75)
    p.add_argument("--limit", type=int, default=17)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    with a.source_csv.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    result = run(rows, a.archive_dir, a.endpoint, a.model,
                 a.timeout, a.limit, a.dry_run)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 0 if a.dry_run or result["summary"]["evaluated"] == len(result["cases"]) else 2


if __name__ == "__main__":
    sys.exit(main())
