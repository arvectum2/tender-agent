# ARV-006 revalidation — 2026-09-21

Task: `ARV-006-REVALIDATION-001`  
Base: `b3cf30241b7ca4acdb7be88a4891f0d163155e1a`

## Canonical target

Historical ARV-006 asks for full 223-FZ breadth: search, registry number, lots, positions, documents, changes, clarifications, protocols and statuses.

This revalidation preserves the immutable historical snapshot and compares that target with the two already merged 223-FZ foundations.

## Merged foundation

### Read-only intake

`223FZ-INGEST-V1-001`, merged as `dc87a0bf4a8ad870d8e611e2e83d736c7c7a3609`, provides:

- dedicated public `fz223` search/parser;
- registry-number/card intake through the 223-FZ source path;
- source-bound title, publication date and deadline when explicitly present;
- customer only when the source explicitly labels the customer role;
- read-only discovery of explicit document/file/attachment links;
- revision/version marker detection with fail-closed review on ambiguity;
- isolated 223-FZ pipeline dispatch and idempotent persistence;
- no fallback to 44-FZ-only detail routes or parser semantics.

The repository support matrix explicitly states that fixtures are synthetic because there is no repository-owned real 223-FZ HTML fixture yet.

### Decision boundary

`223FZ-DECISION-V1-001`, merged as `f603c9f62859b49287456069d7be98ac1c8ce1dd`, provides regime-aware Decision Core behavior:

- normalized `223fz` regime is preserved into decision/customer projection;
- source-bound shared facts may be KNOWN without implying GO;
- unsupported 223-FZ deadline/risk/contract semantics fail closed to `NEEDS_REVIEW`;
- 44-FZ hard blockers are not silently projected into 223-FZ;
- external action remains disabled and human control remains mandatory.

## Capability reconciliation

| Canonical ARV-006 capability | Current state |
|---|---|
| Public search | Implemented in dedicated 223-FZ provider |
| Registry-number/card intake | Implemented when an explicit 223-FZ card URL/source path is available |
| Basic title/dates/customer facts | Implemented when explicitly source-bound |
| Documents | Implemented as read-only explicit-link discovery |
| Revision awareness | Partial: ambiguity detection exists, but not a full revision/change history model |
| Lots | Not established by current 223-FZ provider/support matrix |
| Positions/items | Not established |
| Changes/revisions as structured lifecycle | Not established |
| Clarifications | Not established |
| Protocols | Not established |
| Normalized procedure/status lifecycle | Not established |
| 223-FZ legal/procedural positive GO rules | Intentionally not established; remains REVIEW without an independently frozen source basis |

## Concrete residual

ARV-006 is therefore **not** complete. The merged v1 foundation covers safe acquisition and fail-closed decision boundaries, but the canonical breadth target still lacks source-backed lots/positions and lifecycle artifacts (changes, clarifications, protocols, normalized statuses).

No authenticated/private platform access or external procurement action is required to state this gap.

## Bounded successor candidate

Candidate only; **not admitted for implementation by this revalidation**:

`ARV-006-223FZ-BREADTH-V2-001 — Source-bound 223-FZ lots, positions and lifecycle breadth`

Bounded scope:

1. freeze a repository-owned sanitized/public fixture/capability matrix for the supported 223-FZ layouts before parser tuning;
2. extend the existing dedicated 223-FZ read-only adapter to source-bind lots/positions and explicit change/clarification/protocol/status artifacts that are actually present in the frozen source evidence;
3. keep unsupported or ambiguous layouts explicit `UNKNOWN/NEEDS_REVIEW`;
4. preserve separate 223-FZ semantics and prohibit 44-FZ fallback;
5. do not add authenticated/private ETP actions or new legal decision rules in this slice.

This candidate is directly traceable to the historical ARV-006 `next_result` and does not choose a new marketplace/provider priority.
