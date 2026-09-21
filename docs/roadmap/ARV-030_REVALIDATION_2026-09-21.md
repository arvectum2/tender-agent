# ARV-030 revalidation — 2026-09-21

## Historical target

ARV-030 asks for a standard marketplace connector layer for EIS, TEK-Torg, federal and commercial ETPs. This revalidation does not choose the next provider and does not access authenticated/private platform surfaces.

## Current evidence

- `RegistryNumberDiscovery` exposes one `DiscoveredRegistryNumber` / `DiscoveryResult` model and explicit source types for public 44-FZ and public 223-FZ.
- `Public44FzSearchProvider` and `Public223FzSearchProvider` are separate regime-aware providers. The 223-FZ path reuses bounded transport while preserving separate parsing/detail semantics and fail-closed behavior.
- `TenderResearchPipeline` dispatches detail acquisition by source/law type and preserves source-specific provenance.
- `SearchProvider` is a generic web-search abstraction; it is not a procurement marketplace adapter contract.

## Revalidated state

The repository already has reusable source identity, canonical discovery output, provider isolation, provenance and two public procurement-source implementations. ARV-030 is therefore **partially implemented**, not a blank-slate connector epic.

The concrete residual is the canonical standard adapter protocol/registry that future ETP providers can implement without adding provider-specific conditionals throughout discovery/pipeline code. No evidence in the roadmap authorizes choosing or connecting a specific authenticated/private ETP in this slice.

## Bounded successor candidate — not admitted

`ARV-030-MARKETPLACE-ADAPTER-CONTRACT-001`

Scope: extract the already-proven public-source seams into a versioned procurement marketplace adapter protocol/registry supporting source identity, search/discovery, detail/document acquisition capability declaration, provenance and explicit unsupported/fail-closed outcomes; adapt existing 44-FZ and 223-FZ public providers first. Do not add a new ETP, credentials, authenticated access, external writes or provider priority.

Candidate definition of done:

1. Existing 44-FZ and 223-FZ public paths implement the same procurement adapter contract without changing their regime-specific parsers.
2. Discovery/pipeline provider selection uses the registry/capability contract rather than law-specific conditionals at each call site.
3. Unsupported capabilities fail closed and retain source provenance.
4. Existing 44-FZ/223-FZ regressions remain green.
5. No new external provider, credentials, private data, procurement action or production mutation is introduced.

Status: `candidate_not_admitted`.
