"""Offline fail-closed provenance check: one first-party .ppt URL saved as OOXML."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

from scripts.research.acquire_sibur_documents import source_refs, valid_url
from scripts.research.audit_sibur_saved_documents import _references_fingerprint

SLIDESHOW_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.slideshow.main+xml"
LEGACY_MAGIC = bytes.fromhex("d0cf11e0a1b11ae1")
SLIDE_RE = re.compile(r"ppt/slides/slide[1-9][0-9]*\.xml")
SHA_RE = re.compile(r"[a-f0-9]{64}")


class SourceFormatError(ValueError):
    """No private URL, file path or source bytes in exception text."""


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SourceFormatError("duplicate_json_member")
        result[key] = value
    return result


def _safe_dir(path: Path):
    if not path.is_absolute() or path.is_symlink() or not path.is_dir() or path.resolve() != path:
        raise SourceFormatError("unsafe_source_directory")


def check_ooxml(path: Path, sha: str, size: int) -> dict:
    """Read one saved source blob only; never extract or execute its content."""
    if (not isinstance(sha, str) or SHA_RE.fullmatch(sha) is None
            or type(size) is not int or not 0 < size <= 25 * 1024 * 1024
            or path.is_symlink() or not path.is_file()
            or path.name != sha + ".pptx" or path.stat().st_size != size):
        raise SourceFormatError("saved_binary_identity_invalid")
    with path.open("rb") as stream:
        observed = hashlib.file_digest(stream, "sha256").hexdigest()
    if observed != sha:
        raise SourceFormatError("saved_binary_sha_changed")
    with path.open("rb") as stream:
        magic = stream.read(8)
    if magic.startswith(LEGACY_MAGIC) or magic[:2] != b"PK" or not zipfile.is_zipfile(path):
        raise SourceFormatError("not_ooxml_zip")
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > 1000 or sum(x.file_size for x in infos) > 50 * 1024 * 1024:
                raise SourceFormatError("zip_members_untrusted")
            names = {item.filename for item in infos}
            if "[Content_Types].xml" not in names or "ppt/presentation.xml" not in names:
                raise SourceFormatError("ooxml_presentation_missing")
            root = ET.fromstring(archive.read("[Content_Types].xml"))
            main = [x.attrib.get("ContentType") for x in root.iter()
                    if x.attrib.get("PartName") == "/ppt/presentation.xml"]
            slides = sum(bool(SLIDE_RE.fullmatch(name)) for name in names)
            if main != [SLIDESHOW_TYPE] or slides < 1 or archive.testzip() is not None:
                raise SourceFormatError("slideshow_main_part_unverified")
    except (zipfile.BadZipFile, ET.ParseError, RuntimeError) as exc:
        raise SourceFormatError("ooxml_package_invalid") from exc
    return {"sha256": observed, "bytes": size, "valid_zip": True,
            "ooxml_slideshow_main_part": True, "legacy_ppt_original": False,
            "slides": slides, "saved_filename_extension": ".pptx"}


def audit(snapshot: Path, saved: Path) -> dict:
    _safe_dir(snapshot)
    _safe_dir(saved)
    verified_refs = source_refs(snapshot)  # Complete 27-page saved SHA replay, no HTTP.
    suspects = []
    for url, original_links in verified_refs.items():
        if not isinstance(url, str) or not urlsplit(url).path.lower().endswith(".ppt"):
            continue
        if not valid_url(url):
            raise SourceFormatError("source_url_outside_first_party")
        token = hashlib.sha256(url.encode()).hexdigest()
        receipt = saved / (token + ".json")
        if (receipt.is_symlink() or not receipt.is_file()
                or not 0 < receipt.stat().st_size <= 64_000):
            raise SourceFormatError("source_receipt_missing_or_unsafe")
        data = json.loads(receipt.read_bytes(), object_pairs_hook=_unique_json)
        if data.get("file") != str(data.get("sha256", "")) + ".pptx":
            continue
        if (data.get("url") != url or data.get("status") != "captured"
                or data.get("source_extension") != ".ppt"
                or data.get("observed_format") != "pptx"
                or data.get("mime") != "application/vnd.ms-powerpoint"
                or _references_fingerprint(data.get("references"))
                != _references_fingerprint(original_links)):
            raise SourceFormatError("original_reference_or_receipt_mismatch")
        verified = check_ooxml(saved / data["file"], data["sha256"], data["bytes"])
        suspects.append({
            "source_url_sha256": token,
            "source_extension": ".ppt",
            "captured_mime": "application/vnd.ms-powerpoint",
            "source_reference_count": len(original_links),
            **verified,
        })
    if len(suspects) != 1:
        raise SourceFormatError("unexpected_suspect_count")
    return {
        "status": "needs_review",
        "source": "sibur_public_historical_saved",
        "suspect_count": 1,
        "suspect": suspects[0],
        "source_binary_original_ppt_verified": False,
        "source_latest_revision_verified": False,
        "cause": "UNKNOWN",
        "safe_original_promotion": False,
        "external_source_requests": 0,
        "database_mutations": 0,
        "production_mutations": 0,
    }


def save_private_once(output: Path, report: dict) -> None:
    if (not output.is_absolute() or output.is_symlink() or output.exists()
            or not output.parent.is_dir() or output.parent.is_symlink()):
        raise SourceFormatError("unsafe_or_existing_private_proof_path")
    fd, temp = tempfile.mkstemp(prefix=".sibur-source-format-", dir=output.parent)
    try:
        with os.fdopen(fd, "w") as target:
            json.dump(report, target, sort_keys=True, ensure_ascii=False, indent=2)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        os.chmod(temp, 0o600)
        os.link(temp, output)
    finally:
        Path(temp).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--saved-files", type=Path, required=True)
    parser.add_argument("--private-proof-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit(args.snapshot, args.saved_files)
        save_private_once(args.private_proof_output, result)
    except (SourceFormatError, ValueError, TypeError, KeyError, OSError):
        print(json.dumps({"status": "blocked", "error_code": "source_original_format_not_proven"}))
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
