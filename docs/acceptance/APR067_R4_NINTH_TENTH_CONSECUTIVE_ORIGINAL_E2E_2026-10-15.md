# APR-06/07: ninth and tenth consecutive authentic 44-FZ E2Es

At protocol creation: original source stages accepted for analysis, live LLM queue in progress. Results are not asserted until the original receipts exist.

| Separate case | Original EIS | Original inputs | Document distinction |
|---|---|---:|---|
| Ninth 0360600005326000018 | v2 epNotificationEF2020 from Oct09 saved getDocsIP ZIP | 8 XML + 4 restored UID/name/bytes/SHA-bounded originals = 12 | An actual legacy Word DOC technical specification alongside original DOCX contract and price justification |
| Tenth 0895100000126000897 | v1 epNotificationEF2020 from Oct09 saved getDocsIP ZIP | 7 XML + 6 restored UID/name/bytes/SHA-bounded originals = 13 | Original DOCX concerning national regime/import restriction PP1875 and participant requirements |

Four and six recovered first-party attachments respectively were frozen to individual signed-off source receipts from Oct14. Neither case was fetched from live EIS. The source binding admits only the selected official XML revision, exact filestore UID, filename, byte size and SHA. Both native source stages return ready_to_analyze without bypass. Source manifests live in docs/quality/APR067_R4_ORIGINAL_{REGISTRY}_SHA_PINNED_SOURCES_2026-10-15.json.

A single serial process PID69976 runs the ninth REAL local Gemma4-12B original-source flow, then launches tenth only after successful ninth completion. The first command attempt failed closed on the strict source identity allowlist before any model invocation. It was fixed by enumerating exactly these two known historical original IDs. Neither native SHA/UID guard was weakened. 23 focused source/adversarial tests passed. Full suite and actual model receipts/exact-head CI pending.

These cases are for DEVELOPMENT E2E under Owner delegation of source-grounded ChatGPT expert review, not current EIS validity, commercial GO, payments, ETP bids, detached electronic signature verification or production deployment.


## Ninth case — observed true model result, before PR exact-head CI

The original saved ninth local Gemma4 source-bound E2E completed successfully
exactly once. Registry **0360600005326000018**, original archived v2 EIS
notice, official saved ZIP + 8 historical XML, 4 restored original DOC/DOCX
(first-party exact UID, declared size, document type and SHA). Real
`arvectum-gemma4-12b-it-qat-q4_0` four calls, **457.90 seconds**,
HTTP200, 12/12 original file SHA and extracted text, no unsupported/fallback,
with the legacy Word technical specification actually extracted.

Source selector `pinned_latest_archived_notice_revision` and 3 source
attested `eis-xml:` HTML citations cover VR content for museum
exhibitions, archived submission deadline **06.04.2026 10:00 +04:00**,
NMCK **2,700,000 RUB**. Original HTML SHA-256
`4b31d05f1a18eb42080113d70625823b983882affb14f0c3743f09eba76d5072`.
Report, history and read-only registry HTTP200, unauth workspace401,
archived PDF/DOCX exports409; `manual_review_required`.
Model correctly states the genuine contract draft is present, not missing.
Five contract-risk hypotheses remain labeled unverified, including English
text; these cannot be treated as verified legal clauses or commercial GO.

The second independent model call was automatically launched **only after**
the first exited 0 and its original source/LLM receipt had been persisted.
Ninth evidence is not reused for tenth. Original SHA-pinned bytes and model
outputs were never rewritten.

## Tenth case — observed true model result, before PR exact-head CI

Registry **0895100000126000897**, original v1 EIS and 6 real DOCX.
Contains a distinct source appendix justifying applicability of PP РФ
№1875 national-regime prohibition (not an externally validated conclusion
about the actual regulation). Original XML reports NMCK **10,138,500 RUB**
and archived deadline **19.06.2026 09:00 +03:00**. One genuine local Gemma4-12B execution completed automatically after the
ninth successful exit: **4 calls / 338.62 seconds**, HTTP200,
`llm_tender_operator_provider`, no fallback. Preserved and extracted
**13/13 original first-party SHA**: seven official EIS XML and six
original DOCX sources, zero failed/unsupported. Three original EIS XML
source citations anchor the official works developing the Federal
Treasury portal "Legal Work" subsystem, archived submission deadline
**19.06.2026 09:00 +03:00**, and **10,138,500 RUB** NMCK.
Original saved HTML SHA-256
`a9f4102f5bb23284d2807a885b34f1ee4796113d001124990f9a2bfb330447e1`.

Authenticated report/history/source evidence HTTP200, unauthorized access
401, archived export both PDF and DOCX 409, decision
`manual_review_required` (not actual bid GO). Model's five generated
contract risks are explicitly marked hypotheses and in part English;
contract draft is **present**, not declared missing. The documentary note
on applicability of PP РФ №1875 is an original legal-source record,
but its operative legal conclusion is **NOT attested** by this
development check. Actual model, input files and original report
remain private; neither case was rerun to generate these observations.

Full post-change local regression (including two new bounded source
manifests, and old E2E guards): **4187 passed, 238 skipped, 0 failed**,
328 known warnings, completed in 480.25s during severe unrelated iOS
Simulator load. Source/UID/size/receipt anti-tamper focused **23 PASS**;
Ruff PASS. GitHub exact-head CI pending until branch PR is created.


## Final acceptance and exact substantive-head CI

PR445 original code commit bd8414bd52ed539c76ef38780fbc317efeb7b873
verified by GitHub Actions CI run38795527804: 9/9 jobs SUCCESS,
matching the source-tested code. Mac mini 4187 PASS/238 SKIP,
23 anti-tamper source tests PASS and Ruff PASS. Both ninth and tenth
single real original-source Gemma4 model receipts passed; private output
and original first-party bytes remain immutable. Both case checkpoints
now COMPLETED. This is the delegated DEVELOPMENT technical gate; it
is not business bidding GO, legal signoff or production SLO.
