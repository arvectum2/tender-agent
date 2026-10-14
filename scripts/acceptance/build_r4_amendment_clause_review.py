"""Original-bound revision-text leads, not a decision or legal interpretation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from src.modules.tender_operator_agent_demo.r4_amendment_clause_diff import (
    audit_changed_material,
)
from src.modules.tender_operator_agent_demo.r4_original_text_extract import (
    verified_document_text,
)


def _verified_source(root: Path, relative_name: str, expected_sha: str) -> bytes:
    relative = Path(relative_name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Only root-relative original source paths allowed")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file() or path.is_symlink():
        raise ValueError("Source location outside pinned private evidence")
    raw = path.read_bytes()
    if len(raw) > 30_000_000 or hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError("Original binary/extracted text SHA or size mismatch")
    return raw


def source_attested_revision(
    root: Path,
    pairs: list[dict],
    *,
    original_eis_inventory: dict,
    current_eis_inventory: dict,
    notice_number: str,
) -> dict:
    if not pairs or len(pairs) > 100:
        raise ValueError("At least one bounded source revision pair required")
    previous_cases = [
        row for row in original_eis_inventory["selected_original_notice_attachment_coverage"]["cases"]
        if row["registry_number"] == notice_number
    ]
    current_cases = [
        row for row in current_eis_inventory["cases"]
        if row["registry_number"] == notice_number
    ]
    if len(previous_cases) != 1 or len(current_cases) != 1 or not current_cases[0]["version_changed"]:
        raise ValueError("No source-verified prior and updated official notice pair")
    old_originals = {
        row["original_filename"]: row["original_document_sha256"]
        for row in previous_cases[0]["documents"]
    }
    new_originals = {
        row["filename"]: row["sha256"]
        for row in current_cases[0]["new_replaced_attachments"]
    }
    result = []
    seen = set()
    for pair in pairs:
        label = pair["source_pair_label"]
        if not label or label in seen:
            raise ValueError("Ambiguous source revision pair label")
        seen.add(label)
        if old_originals.get(pair["previous_official_filename"]) != pair["previous_original_binary_sha256"]:
            raise ValueError("Historic original filename/SHA differs from independently checked EIS inventory")
        if new_originals.get(pair["current_original_filename"]) != pair["current_original_binary_sha256"]:
            raise ValueError("Current original filename/SHA differs from live official EIS inventory")
        old = _verified_source(
            root, pair["previous_text_relpath"], pair["previous_extracted_text_sha256"],
        ).decode("utf8")
        binary = _verified_source(
            root, pair["current_original_relpath"], pair["current_original_binary_sha256"],
        )
        newest = verified_document_text(binary, pair["current_original_filename"])
        diff = audit_changed_material(
            old, newest,
            previous_original_sha256=pair["previous_original_binary_sha256"],
            current_original_sha256=pair["current_original_binary_sha256"],
            max_leads_per_topic=3,
        )
        result.append({
            "source_pair_label": label,
            "previous_official_filename": pair["previous_official_filename"],
            "current_official_filename": pair["current_original_filename"],
            **diff,
        })
    return {
        "review_state": "SOURCE_ATTESTED_UNSIGNED_LEXICAL_CHANGE_LEADS",
        "paired_distinct_originals": len(result),
        "pairs": result,
        "human_legal_expert_signed": False,
        "bid_ready": False,
    }


def human_report(result: dict) -> str:
    lines = [
        "# Изменения в документах ЕИС — вопросы для эксперта",
        "",
        "Текст извлечён из официальных оригиналов; совпадения проверены по SHA.",
        "**Ни одно найденное слово не является подтверждённым юридическим требованием.**",
        "",
        "Сопоставлено различных пар оригиналов: "
        + str(result["paired_distinct_originals"]) + ".",
    ]
    for item in result["pairs"]:
        lines.extend([
            "",
            "## " + item["source_pair_label"],
            "",
            "Ранее: " + item["previous_official_filename"],
            "Теперь: " + item["current_official_filename"],
            "SHA-256 прежнего оригинала: " + item["previous_original_binary_sha256"],
            "SHA-256 текущего оригинала: " + item["current_original_binary_sha256"],
            "Сходство последовательности текстовых строк: "
            + format(item["textual_sequence_similarity"], ".1%")
            + " (зависит от извлечения PDF/DOCX и НЕ является правовой схожестью).",
            "",
            "| Тема | Строк до | Строк после |",
            "|---|---:|---:|",
        ])
        for topic, count in item["topic_line_counts_old"].items():
            lines.append(
                "| " + topic + " | " + str(count) + " | "
                + str(item["topic_line_counts_current"][topic]) + " |"
            )
        lines.extend([
            "",
            ("Неподтверждённые сигналы в изменённых строках "
             "(первые примеры по темам, сверять в оригинале):"),
        ])
        for lead in item["changed_new_text_topical_leads"]:
            match = lead["bounded_source_leads"][0]
            lines.append(
                "- " + lead["topic"] + ": " + match["source_locator"]
                + ", SHA строки " + match["source_line_sha256"][:16]
                + ", текст: «" + match["short_source_excerpt"][:180] + "»"
            )
        lines.append(
            "Открытый вопрос: субъект условия, исключения/отрицания, "
            "срок, приоритет договора и ТЗ, применимость к участнику."
        )
    lines.extend([
        "",
        "**Заключения независимого юриста отсутствуют; bid_ready=false.**",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--private-manifest", type=Path, required=True)
    parser.add_argument("--old-public-inventory", type=Path, required=True)
    parser.add_argument("--current-public-inventory", type=Path, required=True)
    parser.add_argument("--notice-number", required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    args = parser.parse_args()
    pairs = json.loads(args.private_manifest.read_text("utf8"))
    output = source_attested_revision(
        args.private_root, pairs,
        original_eis_inventory=json.loads(args.old_public_inventory.read_text("utf8")),
        current_eis_inventory=json.loads(args.current_public_inventory.read_text("utf8")),
        notice_number=args.notice_number,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", "utf8")
    args.output_markdown.write_text(human_report(output), "utf8")
    print("ORIGINAL_SOURCE_DIFF_PAIRS", output["paired_distinct_originals"])


if __name__ == "__main__":
    main()
