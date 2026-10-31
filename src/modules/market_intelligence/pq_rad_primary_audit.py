"""Verify first-party RAD 223-FZ original archives and their reviewed protocol.

Only original publicly listed source URLs, immutable local SHA receipts and
archive-native DOCX bytes establish this evidence level. A commission instruction
to contract is NEVER a signed contract, supplier appointment or payment.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

MAX_CARD = 1_000_000
MAX_ARCHIVE = 20_000_000
MAX_DOCX = 2_000_000
EXPECTED_KINDS = frozenset({
    "notice-approval", "technical-documentation",
    "application-review", "final-protocol",
})


def _sha(path: Path, limit: int) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError("Missing, symlinked or oversized original")
    digest = hashlib.sha256()
    with path.open("rb") as inp:
        for block in iter(lambda: inp.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _rad_download(url: str) -> str:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.netloc != "tender.lot-online.ru"
            or parsed.path != "/etp/downloadppf" or parsed.fragment):
        raise ValueError("Untrusted RAD download URL")
    params = parse_qs(parsed.query)
    if set(params) != {"uuid"} or len(params["uuid"]) != 1:
        raise ValueError("Unbound RAD document URL")
    uid = params["uuid"][0]
    if not re.fullmatch(r"dbfile[a-z0-9]{20,80}", uid):
        raise ValueError("Unrecognized official RAD file reference")
    return uid


def _rar_docx(archive: Path) -> tuple[bytes, str]:
    """Extract one DOCX from a bounded source RAR without extracting arbitrary paths."""
    listing = subprocess.run(["bsdtar", "-tf", str(archive)],
                             capture_output=True, timeout=15, check=True)
    names = listing.stdout.decode("utf-8", errors="strict").splitlines()
    if len(names) > 50:
        raise ValueError("Too many source archive members")
    choices = [
        name for name in names
        if name.lower().endswith(".docx") and not name.startswith("/")
        and all(part not in (".", "..") for part in name.split("/"))
    ]
    if len(choices) != 1:
        raise ValueError("Expected one exact original commission DOCX")
    process = subprocess.Popen(
        ["bsdtar", "-xOf", str(archive), choices[0]],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None
    data = process.stdout.read(MAX_DOCX + 1)
    if len(data) > MAX_DOCX:
        process.kill()
        process.communicate(timeout=2)
        raise ValueError("Oversized original commission DOCX")
    process.communicate(timeout=15)
    if process.returncode != 0 or not data.startswith(b"PK\x03\x04"):
        raise ValueError("Original RAD DOCX could not be extracted")
    return data, choices[0]


def verify(*, root: Path, queue: Path, extractor=_rar_docx,
           max_cases: int = 30) -> dict:
    if root.is_symlink() or not root.is_dir() or not 1 <= max_cases <= 100:
        raise ValueError("Unsafe RAD source root")
    records = []
    cases = sorted(x for x in root.iterdir() if x.is_dir()
                   and not x.is_symlink()
                   and re.fullmatch(r"[0-9]{11}", x.name)
                   and (x / "original-source-manifest.json").is_file())
    if len(cases) > max_cases:
        raise ValueError("RAD source budget would truncate results")
    for case in cases:
        manifest_file = case / "original-source-manifest.json"
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        if (manifest.get("schema_version") != "pq-rad-original-source-provenance/1"
                or manifest.get("registry_number") != case.name
                or not re.fullmatch(r"RAD[0-9]{9}", str(manifest.get("native_etp_id") or ""))):
            raise ValueError("RAD source notice/ETP identity mismatch")
        page = case / "original-rad-tender-card.html"
        page_sha = _sha(page, MAX_CARD)
        if page_sha != manifest.get("source_card_sha256"):
            raise ValueError("RAD original first-party card SHA mismatch")
        card = page.read_bytes()
        if (case.name.encode() not in card
                or manifest["native_etp_id"].encode() not in card):
            raise ValueError("RAD official card does not identify procurement")
        source_page = urlsplit(manifest.get("source_card_url") or "")
        if (source_page.scheme != "https"
                or source_page.netloc != "tender.lot-online.ru"
                or source_page.path != "/etp/app/OfferCard/page"
                or not source_page.query.startswith("OfferCard.offerUUID=")):
            raise ValueError("RAD original card URL not allowed")
        origins = manifest.get("originals")
        if not isinstance(origins, list) or not 1 <= len(origins) <= 4:
            raise ValueError("Invalid number of RAD originals")
        validated = []
        for original in origins:
            kind = original.get("kind")
            name = original.get("stored_name")
            if (kind not in EXPECTED_KINDS or name != kind + ".rar"
                    or original.get("direct_live_binary_sha_verified") is not True):
                raise ValueError("Unverified first-party RAD original")
            uid = _rad_download(original.get("source_url") or "")
            if uid.encode() not in card:
                raise ValueError("RAD original file reference absent from first-party page")
            archive = case / name
            digest = _sha(archive, MAX_ARCHIVE)
            if (digest != original.get("sha256")
                    or archive.stat().st_size != original.get("bytes")
                    or not archive.open("rb").read(8).startswith(b"Rar!\x1a\x07")):
                raise ValueError("RAD original archive SHA or magic mismatch")
            validated.append({"kind": kind, "sha256": digest,
                              "source_url": original["source_url"]})
        if len({r["kind"] for r in validated}) != len(validated):
            raise ValueError("Repeated RAD original type")
        final = case / "final-protocol.rar"
        docx_sha = None
        reviewed_queue_id = None
        if "final-protocol" in {r["kind"] for r in validated}:
            binary, _member = extractor(final)
            if len(binary) > MAX_DOCX:
                raise ValueError("Oversized original protocol DOCX")
            docx_sha = hashlib.sha256(binary).hexdigest()
            for record in sorted(queue.glob(case.name + "-*.json")):
                if record.is_symlink():
                    continue
                d = json.loads(record.read_text(encoding="utf-8"))
                if (d.get("schema_version") != "pq-review-queue/1"
                        or d.get("state") != "reviewed"
                        or d.get("packet", {}).get("registry_number") != case.name
                        or d.get("review", {}).get("classification") != "relevant"):
                    continue
                source = next((x for x in d["packet"]["documents"]
                               if x.get("sha256") == docx_sha), None)
                if source is None:
                    continue
                if not any(
                    e.get("sha256") == docx_sha
                    and " ".join(str(e.get("quote", "")).split())
                    in " ".join(source.get("text", "").split())
                    for e in d["review"]["evidence"]
                ):
                    continue
                reviewed_queue_id = d["id"]
                break
        records.append({
            "procedure_id": case.name,
            "native_etp_id": manifest["native_etp_id"],
            "first_party_card_sha256": page_sha,
            "source_card_url": manifest["source_card_url"],
            "source_level": "rad_etp_original_public_223_archives_sha_verified",
            "original_archive_count": len(validated),
            "source_archives": validated,
            "final_protocol_docx_sha256": docx_sha,
            "reviewed_final_protocol_queue_id": reviewed_queue_id,
            "commission_source_verified": reviewed_queue_id is not None,
            "signed_contract_verified": False,
            "supplier_of_signed_contract_verified": False,
            "pq_equipment_only_price_rub": None,
        })
    return {
        "schema_version": "pq-rad-primary-audit/1",
        "first_party_223_notice_cases": len(records),
        "reviewed_original_commission_protocol_cases": sum(
            x["commission_source_verified"] for x in records),
        "verified_signed_contracts": 0,
        "records": records,
    }
