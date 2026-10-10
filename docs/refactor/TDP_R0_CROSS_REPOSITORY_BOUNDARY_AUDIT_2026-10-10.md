# TDP R0: reproducible cross-repository ownership and boundary audit

Task: TDP-REFACTOR-20261009. Baseline date: 2026-10-10. Read-only AST inventory from isolated Mac mini worktrees, without importing services or reading procurement documents.

## Measured module inventory

- Tender Agent: **823** Python files. Largest areas: shared=80, modules/tender_operator_agent_demo=68, tender_research=52, modules/production_llm_analysis=23, modules/customer_pilot=14, modules/hermes_agent=13, modules/supplier_search=9, modules/daily_tender_run=8.
- Data Platform: **179** Python files. Largest areas: api=42, evaluation=36, connectors=11, engine=10, search=8, acquisition=7, documents=7, storage=7.
- Direct Tender Agent imports of Data Platform implementation: **0**.
- Tender Agent imports of consumer SDK outside src/shared/data_platform.py: **0**.
- Reverse Data Platform imports of Tender Agent business modules: **0**.

## Architectural ownership

| Responsibility | Canonical owner | Contract enforcement |
| --- | --- | --- |
| Generic acquisition, document and legacy Word extraction, OCR/VLM, chunks, source IDs, indexing/search | Data Platform | Versioned API/SDK, provenance, tenant isolation, no 44/223-FZ business rules |
| EIS SOAP and revision precedence, legal/procurement interpretation, supplier economics, preliminary GO/NO-GO | Tender Agent | Consumer SDK facade only, original-source fact evidence and explicit UNKNOWN |
| Operator workflow, attestation UI, procurement-specific PDF/DOCX reports and human approval | Tender Agent | Product-owned presentation, human gate and backwards-compatible entrypoints |

## Reproduce and gate

Run from the Tender Agent checkout, passing the separate Data Platform repository path:

```sh
python scripts/ops/audit_tdp_boundaries.py --strict --data-platform-root /path/to/data-platform
python -m pytest -q tests/test_tdp_architecture_audit.py
```

The JSON reports live per-area Python module counts and explicit violating file paths. CI must fail on direct product-platform implementation imports, consumer SDK facade bypass, or unreadable/invalid Python source. The audit includes static imports and constant-string importlib.import_module/__import__ calls.

## Remaining limitations and acceptance gates

This is static screening, not evidence of behavioral equivalence, absence of semantic duplicates, or correctness of legal facts. Dynamic import names constructed at runtime and HTTP/network dependencies require separate tests. Exact AST clones are inventoried by the existing audit_tdp_duplicate_functions.py but must not be deleted without compatibility tests. Next gates: R1 source-verified XML precedence and UNKNOWN; R2 chunk offsets and SDK compatibility; R3 legacy decomposition in tested slices; R4 truthful runtime LLM availability and fallback; R5 independent human review of at least 20 original-source procurements with owner acceptance. Until R5 passes, overall status stays in_progress.
