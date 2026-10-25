# MI-001: Offline normalized evidence snapshot contract

This is an internal, read-only, product-specific adapter boundary. It does **not** fetch a supplier URL or collect public historical tenders. See [end-to-end target](MARKET_INTELLIGENCE_V0.md).

Run from repo root with installed project dependencies:

```bash
python -m src.modules.market_intelligence.cli \
  --input /path/to/normalized_evidence.json \
  --json-out /path/to/reports/market.json \
  --md-out /path/to/reports/market.md
```

## Input shape

```json
{
  "as_of": "2026-10-24",
  "window_from": "2023-10-24",
  "window_to": "2026-10-24",
  "supplier": {
    "name": "Vendor Ltd",
    "products": [{"id": "statcom", "name": "СТАТКОМ", "synonyms": ["STATCOM", "SVG"]}]
  },
  "coverage": [
    {"source": "eis_44", "status": "partial", "notes": "Example: only target sample indexed"},
    {"source": "eis_223", "status": "not_checked", "notes": "Not ingested"},
    {"source": "commercial_etp", "status": "not_checked", "notes": "Coverage unknown"}
  ],
  "records": [
    {
      "regime": "223-fz", "source": "eis_223", "external_id": "external-event-id",
      "procurement_id": "official-notice-id", "lot_id": "1", "award_id": "contract-id",
      "project_id": "verified-project-id", "project_name": "Project name",
      "stage": "awarded", "scope": "epc", "event_on": "2025-09-01",
      "observed_on": "2026-10-23", "deadline_on": null,
      "buyer": {"name": "Customer", "inn": "7707083893"},
      "winner": {"name": "EPC contractor", "inn": "7710140679"},
      "participants": [], "price_basis": "contract",
      "value_rub": "100000000", "component_value_rub": "2000000",
      "dedicated_lot": false,
      "evidence": [
        {
          "url": "https://example.org/doc",
          "locator": "Приложение 5, таблица 8, строка 6",
          "excerpt": "Система СТАТКОМ ... (source excerpt)",
          "source_type": "contract_specification",
          "facts": [
            "buyer", "winner", "scope", "value", "price_basis:contract",
            "component_value", "component_basis:contract_line", "product:statcom"
          ]
        }
      ]
    }
  ]
}
```

All values/links/names above are **demonstration only**, not assertions about any Russian procurement. Real snapshots must carry real verified page/section citations, source document versions and acquisition logs upstream.

## Normalized fact rules

- Each `evidence` entry requires HTTP(S) URL, exact locator, source excerpt and granular `facts` tags. A `product:ID` tag is an upstream *reviewed technical correspondence*, **not** a keyword lookup result. Its accuracy must be separately benchmarked in MI-003. The current analyzer does not validate the semantic inference itself.
- `buyer`, `winner`, `participants`, `scope` and money are used only when a corresponding fact tag is present. Unsupported claims do not become report facts.
- Money is decimal RUB, nonnegative, normalized upstream with documented VAT/exchange basis. `price_basis:contract` or `price_basis:award` is required for `value_rub` to count as awarded scope. `price_basis:ceiling` records НМЦК separately in `nmck_rub` and never becomes awarded turnover.
- `component_value_rub` requires `component_value` and `component_basis:contract_line`. A value larger than contract scope is quarantined; unpriced equipment is **unknown**, not assumed to be a share of EPC total. Design-only contracts are excluded from confirmed equipment spend.
- For a dedicated single-category equipment supply award, `dedicated_lot=true` + `dedicated_lot` source proof allows entire award price to count. For mixed supply/EPC, count only explicit component line amounts.
- `event_on` is the report event date chosen by upstream contract/event reconciliation (award date for signed contracts, notice date for announced procedures). `observed_on` is when the source state was actually fetched. No event outside the selected report window contributes.
- An open opportunity requires `stage=open`, cited `deadline_on` (`deadline` proof), deadline not past as-of, observation no more than seven days old and no signed award in same lot. This is *local snapshot* freshness; live customer publication needs an additional on-demand status refresh.
- Dedup identifier is (regime, official notice ID, lot ID, award ID). Mirrored site records with the same canonical IDs merge; different awards even within the same lot remain distinct. Notice-only records are shadowed by finalized awards when counting currently open opportunities. Cross-source identity without stable identifiers is not inferred.
- Conflicting same-day price, buyer, winner, stage and scope facts are flagged, with unsafe values suppressed. Latest observed revision is used for active product evidence; older versions cannot silently restore removed equipment requirements.
- Company roles are scoped to evidenced winner+contract nature: EPC/design/supply/service. An entity may be an EPC on one contract and a bidder or supplier on another. Missing winners or bidders remain missing.
- `market_size_rub=null` and `INSUFFICIENT_COVERAGE` are intentional: no count of collected tenders can prove a complete Russian market across private 223-FZ and commercial spend.
- `accounts[].heuristic_priority_score` is a deterministic *uncalibrated sorting aid*. Business outreach requires analyst validation of relevance, buyer interests, active project and access route.

## Output shape

- `annual_observations`: evidence-bound *observed* year buckets, not calendar market size estimates.
- `observed_award_values_rub`: explicit dedicated supply and component contract lines, full EPC and total project envelopes **kept separate**.
- `procurements[]`: full detail, evidence refs, status freshness/quality flags and spend attribution.
- `observed_participants[]`, `accounts[]`: only primary-source-backed identities and roles; transparent reason/score.
- `coverage[]`, `limitations[]`: missing/unknown sources and analytical constraints; no estimated national TAM.

## Tests

`pytest -q tests/test_market_intelligence.py` validates dedup across mirrors, separate awards, temporal safety, latest-revision product validity, no-false-price, role and participant provenance, cancellation and stale open status. The fixture is entirely synthetic.

## Explicit non-goals of MI-001

No live 3-year ЕИС census; no commercial ЭТП backfill; no URL/PDF extraction; no automatic discovery from portfolio; no live CRM contact. These require MI-002..MI-005 and independently measured source coverage.
