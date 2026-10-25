# MI-010 — source-proven Power Quality notices and original protocol variants

**Status: evidence-normalization implementation, 25 October 2026. This is NOT an award register or historical national TAM.**

## Verified original EIS 223-FZ examples

Independent authenticated, TLS-verified `getDocsByReestrNumber` responses were obtained for two **previously surfaced Power Quality leads**. Both ZIPs contain two source XML notice revisions and one original source protocol. Original ZIP + each XML SHA-256 remains in the protected Mac mini runtime and the non-sensitive source proof JSON records their digests.

| Number | Official buyer | Official buyer INN | Original notice lot subject | Initial lot sum |
|---|---|---|---|---:|
| **32313008364** | ПАО «ФСК — Россети» | 4716016979 | Сервисное обслуживание системы охлаждения блоков СТАТКОМ на ПС 220 кВ Могоча | **6,795,960 RUB** |
| **32615969197** | ООО «Башкирские распределительные электрические сети» | 0277071467 | Проектно-изыскательские работы по установке УКРМ 10 кВ, ПС 35 кВ Пионерская | **518,960 RUB** |

**Price field:** `purchaseNotice*Data/lots/lot/lotData/initialSum`, with original `currency/code = RUB`. These are **initial lot sums**, not signed contract prices, contractor revenues or installed-equipment costs. Do not count both revisions as separate procurements. The notice versions for the second procurement differ slightly in scope wording but agree on the price.

- №32313008364: two `purchaseNoticeZKESMBO` XMLs + one `purchaseProtocolSummingupZKESMBO` XML, one application observed in this particular original protocol.
- №32615969197: two `purchaseNoticeZPESMBO` XMLs + one `purchaseProtocolRZ1ZPESMBO` XML; this protocol does not expose an application list in the normalized source structure.

**Winner verified: false for both.** A provider application, `accepted=true`, a raw `contractSigned` flag and an offered `price` are not the same as an official contract-register source proving winning party/INN and final signed contract price. EPC, designer and equipment supplier roles remain unverified.

Versioned non-sensitive evidence: `data/market_intelligence/power_quality/official_primary_proofs_20261025.v1.json`. Original source archives, byte-level SHA and full technical annex bytes remain outside Git on Mac mini.

## Generic source normalization

`eis_source_ledger.py` now supports the real 223-FZ document variants `purchaseNoticeZKESMBO`, `purchaseNoticeZPESMBO`, `purchaseProtocolSummingupZKESMBO` and `purchaseProtocolRZ1ZPESMBO`, **in addition to** the prior generic 223-FZ `purchaseNotice` / `purchaseProtocol` and 44-FZ XML types. It links notices/protocols by exact original registered number and preserves every distinct XML SHA as a source revision.

Original buyer legal names, correctly formatted INNs, lot subject excerpts, declared initial sums and currency codes are extracted from explicit XML paths. An absent or invalid numeric value is **null**, not guessed, and no external enrichment is silently merged. The generic Data Platform remains responsible for cross-document lexical/semantic retrieval and ranking; this module only normalizes source facts.

## Official technical attachment reference manifest

`eis_attachment_manifest.py` inspects **only source-SHA-qualified XML** and identifies file references from both government formats:

- `/223/filestore/public/1.0/download/fz223/file.html?uid=...`
- `/223/purchase/public/download/download.html?id=...` (older 223-FZ)
- `/44fz/filestore/public/1.0/download/priz/file.html?uid=...`

HTTPS hostname is restricted to `zakupki.gov.ru`, official fixed paths and strictly validated opaque numeric/hex IDs. No arbitrary redirects, off-domain attachment fetch, or network request is carried out. Output gives original archive/XML hash, original XML member locator, file extension and a **hash of the official download URL**, not the URL itself.

Real read-only source manifest acceptance:

| Primary archive | Safe original attachment references | Formats observed |
|---|---:|---|
| 223-FZ №32313008364 | **14** | DOC, DOCX, XLSX, ZIP |
| 223-FZ №32615969197 | **4** | ZIP, PDF, HTML |
| Unrelated 44-FZ format validation №0373200026426000249 | **28** | DOCX, PDF, XLSX |

The manifest only proves the **references exist in original XML**, not that their technical documents have been downloaded, parsed or indexed.

### Objective attachment access blocker

On the authorized Mac mini, direct **trusted-TLS GET** and HEAD/range probes of several original public EIS filestore URLs returned **HTTP 404**, including both modern and legacy 223-FZ download paths and the 44-FZ filestore path. Do not silently substitute an aggregator attachment, disable SSL verification, infer document text or mark Data Platform technical-annex ingestion successful. A separate official access-path resolution or EIS response verification is required.

## Next steps

- Verify official attachments from a source-backed working download route, preserve byte SHA and link to original EIS XML; safely extract PDF/DOCX/XLSX and index into Data Platform's authorized source collections. Only then run domain-agnostic ontology search for STATCOM/УКРМ, harmonic filters and buried EPC modernization scope.
- Match original procurement protocol decisions against signed-contract or official register XML and INN evidence to establish winners, genuine EPC/designer/supplier roles and prices.
- Expand historical national EIS corpus beyond 21 confirmed source-day cells in the initial 2-region pilot; extend commercial ETPs with independent original source evidence and de-dup.
