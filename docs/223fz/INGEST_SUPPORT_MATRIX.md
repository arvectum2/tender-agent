# 223-FZ intake v1 support matrix

| Capability | v1 status | Fail-closed boundary |
|---|---|---|
| Public EIS search | Supported through a dedicated `fz223` provider/parser | Never invokes the 44-FZ result parser |
| Direct registry/card intake | Supported when an explicit 223-FZ card URL is available | Missing URL returns `UNSUPPORTED_LAYOUT`; no 44-FZ URL fallback |
| Registry number, title, dates | Supported when explicitly present in source markup | Missing values remain unknown |
| Customer role | Supported only when source explicitly labels `Заказчик` | Missing role sets `requires_review` / `customer_role_not_explicit` |
| Documents | Read-only discovery of explicit document/download/file/attachment links | No 44-FZ-only document endpoint synthesis |
| Revision state | Multiple explicit revision/version markers are detected | Ambiguity sets `requires_review` / `revision_state_ambiguous` |
| Decision/legal semantics | Not supported in this increment | Reserved for REVIEW task `223FZ-DECISION-V1-001` |
| External procurement actions | Not supported | Read-only acquisition only |

Fixtures in `tests/tender_research/test_public_223fz_provider.py` are synthetic because no repository-owned real 223-FZ HTML fixture is currently available. They validate the parser contract without claiming undocumented EIS layout semantics.
