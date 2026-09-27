# ARV-036 revalidation — B2B-Center evidence

Date: 2026-09-27  
Task: `ARV-036-REVALIDATION-001`  
Authority: AUTO, repository and explicitly public read-only evidence only

## Canonical question

The immutable ARV-036 snapshot asks whether B2B-Center adds commercial/corporate procurement outside EIS and whether an API and usable documentation path exist. This slice records current evidence; it does not select the platform or authorize an integration.

## Evidence matrix

| Claim | Current evidence | Result |
|---|---|---|
| Tender Agent already has a B2B-Center provider | Default-branch searches for `B2B-Center`, `b2b-center`, and `b2bcenter` returned no indexed implementation or research artifact. Existing marketplace source seams remain public EIS 44-FZ/223-FZ. | Not evidenced |
| An operator-described API exists | B2B-Center's official 2025-07-29 notice says client IT systems can work with the platform and modules through an API. Official ETP Plus material advertises API data transfer and an embeddable web service. | Public claim evidenced |
| Public method contract is available anonymously | The official API notice says method listings, consolidated documentation, and XML examples are in the Personal Account. It also says each method card displays the tariff under which the method functions. This run did not authenticate. | Not publicly verified |
| Commercial procurement exists outside the EIS-only surface | The current official regulation describes a `Commercial Procurement` section under the Civil Code and a separate `223-FZ Procurement` section. | Operator scope evidenced |
| Access is interchangeable across sections | The regulation says section rights are controlled by separate agreements/tariffs and access to one section does not grant access to the other without the applicable tariff. | Refuted |
| Public tariffs establish API entitlement and cost | The public tariff overview lists standard, preferential, 30-day, 90-day, and one-procedure options. It does not, in the evidence reviewed here, establish which API methods are included or provide an anonymous API entitlement suitable for ingestion. | Unverified |
| B2B-Center has data that is incrementally unique for Tender Agent | Operator material advertises a large supplier pool and commercial/corporate functionality. No frozen comparison corpus against EIS or other platforms, duplicate/unique procedure counts, document delta, latency method, or access-rights matrix exists in the repository. | Not established |
| Connector feasibility is proven | No credentials, WSDL/OpenAPI/schema bundle, method inventory, rate limit, pagination contract, stable identifiers, revision semantics, licensing permission, sample payload, or deterministic fixture was obtained. | Not established |

## Public sources

- Official API documentation update, 29 July 2025: <https://www.b2b-center.ru/news/?id=520>
- Current official system regulation page and downloadable regulation dated 24 February 2026: <https://www.b2b-center.ru/help/Регламент_Системы_B2B-Center/>
- Official tariff overview: <https://www.b2b-center.ru/members/tariffs.html>
- Official ETP Plus integration description: <https://www.b2b-center.ru/plus/>

## Interpretation

The public evidence supports a narrow conclusion: B2B-Center describes a real API and both commercial and 223-FZ procurement sections, but API method documentation/examples are account-gated and tariff-associated. It does not establish an anonymous read-only contract, extraction permission, API completeness, or incremental unique value for Tender Agent.

Marketing counts and feature statements are retained as operator claims. They are not substituted for a frozen procedure/document comparison corpus.

## Residual gap

Before any connector implementation can be considered, a separately admitted, public/read-only research slice would need to freeze:

1. public commercial/223-FZ search surfaces and access boundaries;
2. a sample of procedure identifiers, cards, lots, documents, changes and protocols;
3. duplicate/unique coverage against EIS and already-evaluated platforms;
4. latency and revision/dedup observations;
5. official API method/documentation access prerequisites, tariffs and licensing terms;
6. stable identifier, pagination, rate-limit and payload/schema evidence that can be obtained without accepting a commercial commitment.

## Bounded successor candidate

`ARV-036-B2B-CENTER-PUBLIC-VALUE-MATRIX-001` — `candidate_not_admitted`.

Allowed scope would be a frozen public read-only value/access dossier using official sources and anonymously accessible procedure evidence. It must stop before login, registration, operator contact, acceptance of terms, payment, electronic signature, private/authenticated data, connector implementation, provider selection, or any production/procurement/external effect.

## Decision

ARV-036 is `revalidated_residual_gap`. The platform's advertised API and commercial-procurement scope are evidenced, but usable documentation/access, licensing and incremental unique-data value remain unproven. No integration is admitted by this result.
