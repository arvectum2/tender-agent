"""Build a source-rechecked partial PQ market-evidence snapshot, not a market estimate."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from .pq_commission_fact_audit import verify as verify_commission
from .pq_contract_outcome_audit import audit as audit_contract
from .pq_contract_xml_index import scan as scan_contract_xml
from .pq_primary_etp_audit import verify as verify_etp

DIRECT_CAPACITOR_CATEGORIES = frozenset({
    "filter_capacitor_supply", "capacitor_bank_component_supply",
})


def source_receipts(root: Path, *, max_cases: int = 100) -> list[dict]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Missing public EIS original source directory")
    cases = sorted(p for p in root.iterdir() if p.is_dir()
                   and not p.is_symlink() and re.fullmatch(r"[0-9]{11}", p.name)
                   and (p / "public-page-receipt.json").is_file())
    if len(cases) > max_cases:
        raise ValueError("EIS evidence source-case budget exceeded")
    result = []
    for case in cases:
        receipt = case / "public-page-receipt.json"
        if receipt.is_symlink():
            raise ValueError("Symlinked receipt")
        data = json.loads(receipt.read_text(encoding="utf-8"))
        if (data.get("schema_version") != "pq-223-public-page-download/1"
                or data.get("registry_number") != case.name):
            raise ValueError("Source identity mismatch")
        files = data.get("files", [])
        if len(files) > 100:
            raise ValueError("Original file budget exceeded")
        count = 0
        for f in files:
            name, digest = f.get("filename"), f.get("sha256")
            if (not isinstance(name, str) or Path(name).name != name
                    or not isinstance(digest, str)
                    or not re.fullmatch(r"[a-f0-9]{64}", digest)):
                raise ValueError("Invalid original file receipt")
            path = case / name
            if (path.is_symlink() or not path.is_file()
                    or path.stat().st_size > 70_000_000):
                raise ValueError("Missing/oversized original file")
            sha = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    sha.update(block)
            if sha.hexdigest() != digest:
                raise ValueError("Original file SHA-256 changed")
            count += 1
        result.append({"registry_number": case.name,
                       "verified_file_instances": count,
                       "status": data.get("status"),
                       "source_page_sha256": data.get("public_page_sha256")})
    return result



def exact_filestore_sha_receipts(root: Path) -> list[dict]:
    """Verify original filestore bytes independently of EIS public page HTML."""
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Missing exact-SHA EIS source directory")
    result = []
    for case in sorted(root.iterdir()):
        if not case.is_dir() or case.is_symlink() or not re.fullmatch(r"[0-9]{11}", case.name):
            continue
        receipt = case / "official-sha-receipt.json"
        if not receipt.is_file() or receipt.is_symlink():
            continue
        data = json.loads(receipt.read_text(encoding="utf-8"))
        if (data.get("schema_version") != "pq-official-filestore-sha-receipt/1"
                or data.get("registry_number") != case.name
                or len(data.get("verified", [])) > 30):
            raise ValueError("Invalid official EIS direct SHA receipt")
        files = data["verified"]
        for record in files:
            name = record.get("stored_name")
            digest = record.get("sha256")
            if (not isinstance(name, str) or Path(name).name != name
                    or not isinstance(digest, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", digest)):
                raise ValueError("Unsafe original URL-SHA receipt")
            path = case / name
            if (path.is_symlink() or not path.is_file()
                    or path.stat().st_size > 70_000_000
                    or hashlib.sha256(path.read_bytes()).hexdigest() != digest):
                raise ValueError("Official EIS direct original SHA mismatch")
        result.append({
            "registry_number": case.name,
            "verified_file_instances": len(files),
            "status": "official_filestore_exact_sha_verified",
            "source_page_sha256": None,
        })
    return result


def summarize(*, leads: list[dict], eis: list[dict],
              commissions: dict, etp: dict, contracts: dict) -> dict:
    numbered_rows = [
        x for x in leads if re.fullmatch(
            r"[0-9]{11}", str(x.get("procedure_id") or ""))
    ]
    ids = {str(x.get("procedure_id")) for x in numbered_rows}
    nonstandard_rows = len(leads) - len(numbered_rows)
    covered = {r["registry_number"]: r for r in eis if r["registry_number"] in ids}
    offers = [r for r in commissions["records"]
              if r.get("market_category") in DIRECT_CAPACITOR_CATEGORIES
              and r.get("price_kind", "").endswith("vat_included")]
    sample_total = sum((Decimal(x["bid_price_rub"]) for x in offers), Decimal(0))
    return {
        "schema_version": "pq-verified-partial-market/1",
        "completeness": "partial_do_not_extrapolate",
        "period": "2024-01-01 through 2026-10-28",
        "v29_candidate_leads": len(leads),
        "source_number_223_leads": len(ids),
        "source_223_lot_candidate_rows": len(numbered_rows),
        "source_223_extra_lot_rows_sharing_notice": len(numbered_rows) - len(ids),
        "non_223_or_nonstandard_leads": nonstandard_rows,
        "primary_eis_receipt_cases": len(covered),
        "primary_eis_cases_with_files": sum(x["verified_file_instances"] > 0 for x in covered.values()),
        "primary_eis_original_file_download_instances": sum(x["verified_file_instances"] for x in covered.values()),
        "primary_eis_no_document_cases": sorted(x["registry_number"] for x in covered.values()
                                                if not x["verified_file_instances"]),
        "additional_eis_receipts_outside_v29": len(eis) - len(covered),
        "primary_etp_cases_verified": etp["original_etp_cases_verified"],
        "commission_facts_verified": commissions["facts_accepted"],
        "public_223_contract_register_lots": contracts["distinct_contract_lots_matched"],
        "public_223_register_lots_with_rub_price": contracts["contract_lots_with_rub_price"],
        "direct_capacitor_supply_bid_sample_cases": len(offers),
        "direct_capacitor_supply_bid_sample_vat_included_rub": str(sample_total),
        "sample_is_commission_bid_prices_not_signed_contracts": True,
        "pq_equipment_market_value_rub": None,
        "verified_signed_contract_suppliers": 0,
        "commission": commissions["records"],
        "etp": etp["records"],
        "contracts": contracts["records"],
        "source_cases": eis,
        "warnings": [
            f"{len(leads)} candidate leads are not an exhaustive census of Russian PQ tenders",
            (
                f"{nonstandard_rows} non-223/nonstandard "
                f"{'lead is' if nonstandard_rows == 1 else 'leads are'} "
                "not covered by this EIS 223 source pass"
            ),
            "committee decisions and offered prices are not payment, delivery or signed contract evidence",
            "mixed EPC cost is not equivalent to the separate PQ equipment price",
            "2024 Khani EPC lot 2 mentions SCRM only in the wider project title; PQ scope in this lot is not proved",
            "public 223 FZ contract registry withholds signed supplier/copy details under Rule 1132 paragraph 19",
        ],
    }


def _rub(text: str | None) -> str:
    if text is None:
        return "не подтверждена"
    return f"{Decimal(text):,.2f}".replace(",", " ") + " ₽"


def markdown(report: dict) -> str:
    lines = [
        "# Power Quality (РФ): проверенный срез на 28 октября 2026 года",
        "",
        "Исследование неполное. Приведённые данные не являются оценкой всего рынка.",
        "",
        "## Охват",
        "",
        (
            f"- Кандидаты из v29: {report['v29_candidate_leads']}; номеров 223-ФЗ: "
            f"{report['source_number_223_leads']} уникальных извещений "
            f"({report['source_223_lot_candidate_rows']} лотовых записей); "
            f"прочие коммерческие/нестандартные: "
            f"{report['non_223_or_nonstandard_leads']}."
        ),
        (
            f"- Извещений с проверенными первичными файлами ЕИС: "
            f"{report['primary_eis_cases_with_files']}."
        ),
        f"- Исходных первичных карточек Bidzaar: {report['primary_etp_cases_verified']}.",
        f"- Проверенных решений комиссий: {report['commission_facts_verified']}.",
        f"- Записей публичного реестра договоров: {report['public_223_contract_register_lots']}.",
        "",
        "## Первичные решения комиссий (не подписанные договоры)",
        "",
        "| Извещение | Участник по протоколу | Категория | Цена предложения | НМЦ |",
        "|---|---|---|---:|---:|",
    ]
    for item in report["commission"]:
        lines.append(
            f"| {item['procedure_id']} | {item['committee_participant'].replace('|',' ')} | "
            f"{item['market_category'].replace('_',' ')} | "
            f"{_rub(item['bid_price_rub'])} | {_rub(item['initial_price_rub'])} |")
    lines += [
        "",
        (
            "Ставки НДС, стадии тендеров и типы работ различаются; суммы разных "
            "категорий не складываются."
        ),
        "",
        (
            f"Три цены предложений по прямым поставкам конденсаторов/компонентов "
            f"(с НДС): {_rub(report['direct_capacitor_supply_bid_sample_vat_included_rub'])}. "
            "Это лишь наблюдаемые предложения выбранных комиссией участников, "
            "не реализованные продажи, не подписанные договоры и не объём рынка."
        ),
        "",
        "## Оригинальные коммерческие карточки",
        "",
        "| Bidzaar № | Предмет | Установленный уровень |",
        "|---|---|---|",
    ]
    for item in report["etp"]:
        lines.append(
            f"| [{item['procedure_id']}]({item['source_url']}) | {item['source_quote'].replace('|', ' ')} | "
            f"{item['scope'].replace('_',' ')}; нет верифицированной цены/победителя |")
    lines += [
        "",
        "## Публичные записи реестра договоров 223-ФЗ (не проверка подписанных экземпляров)",
        "",
        "| Извещение | Реестровый номер | Заказчик | Цена по XML | Подтверждённый поставщик |",
        "|---|---|---|---:|---|",
    ]
    for item in report["contracts"]:
        lines.append(
            f"| {item['procedure_id']} | {item['register_number']} | "
            f"{(item.get('buyer') or 'не указано').replace('|',' ')} | "
            f"{_rub(item.get('registry_rub_price'))} | не подтверждён |")
    lines += [
        "",
        "## Ограничения",
        "",
        (
            "Не установлена ни полная рыночная стоимость оборудования PQ, ни "
            "сумма исполненных договоров по этой выборке. "
            "Необходимо первично подтвердить исходы коммерческих ЭТП и "
            "отделить расходы на УКРМ/фильтры/СТАТКОМ от общих EPC-проектов."
        ),
        "",
    ]
    return "\n".join(lines)


def run(*, leads: Path, eis_originals: Path,
        commission_facts: Path, review_queue: Path,
        etp_facts: Path, etp_originals: Path,
        contract_root: Path, day_scan: Path | None = None,
        official_filestore_root: Path | None = None) -> dict:
    corpus = json.loads(leads.read_text(encoding="utf-8"))["records"]
    eis = source_receipts(eis_originals)
    if official_filestore_root is not None:
        existing = {x["registry_number"]: x for x in eis}
        for source in exact_filestore_sha_receipts(official_filestore_root):
            matched = existing.get(source["registry_number"])
            if matched is not None:
                matched["verified_file_instances"] += source["verified_file_instances"]
                matched["status"] = "public_page_plus_original_sha_url"
            else:
                eis.append(source)
    commission = verify_commission(facts=commission_facts, queue=review_queue)
    etp = verify_etp(facts=etp_facts, source_root=etp_originals)
    with TemporaryDirectory(prefix="pq-market-source-") as temporary:
        index = scan_contract_xml(contract_root, leads)
        path = Path(temporary) / "contract-source-index.json"
        path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
        contracts = audit_contract(leads_path=leads, contracts_path=path,
                                   contract_root=contract_root, day_scan_path=day_scan)
    return summarize(leads=corpus, eis=eis, commissions=commission,
                     etp=etp, contracts=contracts)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--leads", type=Path, required=True)
    p.add_argument("--eis-originals", type=Path, required=True)
    p.add_argument("--commission-facts", type=Path, required=True)
    p.add_argument("--queue", type=Path, required=True)
    p.add_argument("--etp-facts", type=Path, required=True)
    p.add_argument("--etp-originals", type=Path, required=True)
    p.add_argument("--contract-root", type=Path, required=True)
    p.add_argument("--day-scan", type=Path)
    p.add_argument("--official-filestore-originals", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--markdown", type=Path)
    args = p.parse_args()
    result = run(leads=args.leads, eis_originals=args.eis_originals,
                 commission_facts=args.commission_facts, review_queue=args.queue,
                 etp_facts=args.etp_facts, etp_originals=args.etp_originals,
                 contract_root=args.contract_root, day_scan=args.day_scan,
                 official_filestore_root=args.official_filestore_originals)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown(result), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ("commission", "etp", "contracts", "source_cases", "warnings")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
