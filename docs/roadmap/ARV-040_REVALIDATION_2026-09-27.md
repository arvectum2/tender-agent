# ARV-040 revalidation — search indexing and technical SEO evidence

Date: 2026-09-27  
Task: `ARV-040-REVALIDATION-001`  
Authority: AUTO, repository-only read

## Canonical question

ARV-040 asks for sitemap, robots, canonical metadata, structured data, webmaster-console registration and product landing pages. This slice checks the actual landing repository and separates implemented technical SEO from credentialed console/indexing evidence.

Supporting repository: `arvectum2/arvectum-landing`  
Verified main head: `ff790c74c8d2b2ae3dd44fc4913554f055f17449`

## Evidence matrix

| Canonical result | Current repository evidence | Result |
|---|---|---|
| Sitemap | `public/sitemap.xml` contains 35 canonical public URLs, including `/services/ai-tender-agent.html`, procurement solution pages, demo case, diagnostics, security and materials. | Implemented |
| Robots policy | `public/robots.txt` allows the public surface, excludes health/favicon-preview/thank-you/API paths and declares `https://arvectum.com/sitemap.xml`. | Implemented |
| Canonical metadata | Homepage and Tender Agent page both carry explicit canonical URLs and `index,follow`. | Implemented |
| Hreflang | Homepage and Tender Agent page declare `ru`, `en` and `x-default` alternates. | Implemented |
| Structured data | Homepage includes WebSite, Organization and Service JSON-LD. Tender Agent page includes Organization, BreadcrumbList, Service and FAQPage JSON-LD. | Implemented |
| Product landing pages | Current tree and sitemap contain the Tender Agent service page plus procurement cluster, RFQ/TKP, contract-risk, demo, diagnostics and security pages. | Implemented |
| Repository checks | `SEO_RELEASE_REPORT.md` records lint, static and production checks passing. | Recorded complete |
| Google Search Console | The release report lists sitemap submission and later index checks as manual owner steps; no attributable completion artifact is present. | Not evidenced |
| Yandex Webmaster | The release report lists sitemap submission and later index checks as manual owner steps; no attributable completion artifact is present. | Not evidenced |
| Current index coverage/search appearance | Neither repository contains current console exports/screenshots, ownership evidence, indexed/excluded counts, crawl errors or dated search-result evidence. | Not evidenced |

## Deterministic artifact assertions

- landing main head resolved;
- robots declares the canonical sitemap;
- sitemap URL count: **35**;
- Tender Agent canonical URL is present in sitemap;
- homepage canonical, WebSite, Organization and Service markers are present;
- Tender Agent canonical, BreadcrumbList, Service and FAQPage markers are present.

All assertions passed.

## Interpretation

Repository-side technical SEO is materially implemented. The absence of console evidence does not prove that sitemap submission or indexing never occurred; it means the watchdog cannot claim it from attributable repository evidence.

Search-console ownership, credentialed submission and current index-coverage inspection are human/account actions. They cannot be inferred from a sitemap file or from a historical production-check pass.

## Bounded successor candidate

`ARV-040-WEBMASTER-INDEXING-EVIDENCE-001` — `candidate_not_admitted`, HUMAN-gated.

Allowed scope would accept attributable owner-provided Google Search Console and Yandex Webmaster evidence, record sitemap submission/coverage dates and reconcile crawl/index status. It must not extract credentials, automate login, change ownership, submit indexing requests, deploy the site, edit public claims or mutate production.

## Decision

ARV-040 is `revalidated_residual_gap`: sitemap, robots, canonical/hreflang, structured data, product pages and repository release checks are implemented; current Google/Yandex webmaster submission and indexing evidence remain unverified and HUMAN-gated.
