# ARV-037 revalidation — Tender.Pro evidence

Date: 2026-09-27  
Task: `ARV-037-REVALIDATION-001`  
Authority: AUTO, repository and explicitly public read-only evidence only

## Canonical question

The immutable ARV-037 snapshot asks whether Tender.Pro has incrementally unique procedures/documents, a usable API, searchable public evidence, and integration conditions worth a connector. This slice records current evidence; it does not select the platform or authorize integration.

## Evidence matrix

| Claim | Current evidence | Result |
|---|---|---|
| Tender Agent already has a Tender.Pro provider | Default-branch searches for `Tender-Pro`, `tender-pro`, `tenderpro`, and `ТендерПро` returned no indexed implementation or research artifact. Existing marketplace source seams remain public EIS 44-FZ/223-FZ. | Not evidenced |
| An operator-described API exists | Official Tender.Pro help describes integrations with ERP, CRM, MDM, BI, SAP and 1C. It states that arbitrary API selections return JSON. | Public claim evidenced |
| A complete technical contract is anonymously retrievable | The official integration page links detailed documentation at `https://www.tender.pro/api/docs/smd`; direct anonymous retrieval returned HTTP 403 in this run. No method inventory, authentication contract, schema version, pagination, rate limit or sample payload was obtained. | Not publicly verified |
| Integration is self-service | Official help says that after choosing an integration level, the customer should contact Tender.Pro and form a joint working group to refine the technical exchange protocol and statement of work. | Refuted |
| Tender feed and documents have the same anonymous access boundary | Official FAQ search evidence says the tender feed is viewable without registration, while tender documentation becomes available after registration. The FAQ page itself returned HTTP 403 to direct retrieval. | Refuted |
| Public tariffs establish integration entitlement | The official tariff page exposes paid participant and organizer plans; organizer corporate-system integration is tariff-associated. The evidence does not establish anonymous extraction rights or a reusable read-only ingestion license. | Not established |
| Tender.Pro adds procedures/documents unique versus EIS, B2B-Center or Fabrikant | No frozen cross-platform corpus, duplicate/unique procedure count, document delta, latency method, revision comparison or access-rights matrix exists in the repository. | Not established |
| Connector feasibility is proven | No credentials, detailed method contract, documented read-only entitlement, stable identifiers, pagination/rate limits, revision semantics, licensing permission, fixture or measured reliability evidence was obtained. | Not established |

## Public sources

- Official integration overview: <https://help.tender.pro/integraciya_api.html>
- Official system integration overview: <https://system.help.tender.pro/integration.html>
- Official detailed-documentation target observed returning HTTP 403: <https://www.tender.pro/api/docs/smd>
- Official FAQ search result and direct target: <https://www.tender.pro/api/faq>
- Official tariffs: <https://help.tender.pro/tarif.html>

## Interpretation

The public evidence supports a narrow conclusion: Tender.Pro describes a JSON API and an anonymously viewable tender feed, but detailed documentation is not anonymously retrievable in this run, document access is registration-gated, and integration is presented as a coordinated operator/customer project.

This does not prove API withdrawal or universal denial. HTTP 403 is recorded only as the direct anonymous retrieval result. It also does not establish incremental unique value, extraction permission, or connector feasibility.

## Residual gap

Before any connector implementation can be considered, a separately admitted public/read-only research slice would need to freeze:

1. anonymously accessible search/feed fields, query filters and result limits;
2. a sample of procedure identifiers, cards, lots, documents, changes and protocols;
3. duplicate/unique coverage against EIS, B2B-Center and Fabrikant;
4. document-access boundaries before and after registration without crossing the registration gate;
5. latency, revision and dedup observations;
6. official API prerequisites, tariff/license conditions, stable identifiers, pagination, rate limits and payload/schema evidence obtainable without contacting the operator or accepting a commercial commitment.

## Bounded successor candidate

`ARV-037-TENDERPRO-PUBLIC-VALUE-MATRIX-001` — `candidate_not_admitted`.

Allowed scope would be a frozen public read-only search/access and incremental-value dossier using official sources and anonymously accessible tender-feed evidence. It must stop before login, registration, operator contact, terms acceptance, payment, electronic signature, private/authenticated data, connector implementation, provider selection, or any production/procurement/external effect.

## Decision

ARV-037 is `revalidated_residual_gap`. The advertised JSON API and anonymous tender-feed boundary are evidenced, but detailed documentation, document access, licensing, method coverage, search limits and incremental unique-data value remain unproven. No integration is admitted by this result.
