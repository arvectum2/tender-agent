# EIS daily discovery coverage — candidate, 27 November 2026

## Evidence and scope
- Deployed baseline 90170bb3b95d779b41fc2d35d19b028659fc743e uses 44-FZ-only profile v2, excluding standalone site support. Daily log: 60 discovered, 27 duplicate, 27 screened out, 5 reviewed, 1 failed. No whole-market coverage implied.
- Official getDocsIP read-only 0187300017826000089 / PRIZ and 32616614845 / RI223 both returned completed plus archive link; no claim that those archives were downloaded or latest revision/protocol verified.
- Public search for обслуживание сайта, 24–27 Nov, application stage: 44-FZ explicit zero, 223-FZ one card 32616630657 (5,312,000.04 RUB). Exact 223 lookup returned title/card URL. Candidate only; no eligibility, deadline precision, cost or GO verification.
- Live browser fallback from Python 3.15 parent to independent Python 3.12 worker, simulated primary timeout, returned actual matching 223 card. Chrome installed; no use of authenticated profiles or CAPTCHA bypass.

## Candidate changes
44-FZ profile v3 adds six website support queries. Website support titles are eligible for deep review, not automatic GO; license/equipment/security exclusions remain. New independent arvectum-it-223 profile v1, initial cap five analyses per run to bound load. Explicit 223 intake is routed to the 223 provider and RI223, not legacy 44 fallback. One scheduled runner can include both profiles sequentially, in separate DB sessions; previous errors retain nonzero exit and do not prevent the next profile.

## Deployment gate
Existing production, schedule, database and protected releases unchanged. Do not edit running release. After exact protected CI and coordinated release admission, provision dedicated Python 3.12 environment using hash lock, verify installed Chrome and browser fallback. Set ARVECTUM_EIS_PLAYWRIGHT_PYTHON to absolute approved worker interpreter in runtime configuration. Browser fallback opt-in; never retry explicit block, CAPTCHA or TLS failure. Extend the existing one daily command with --include-profile arvectum-it-223 (no duplicate launch job). Verify both profiles in independent logs, total duration/resource caps, official current-law evidence, and no loss of historical error status. Roll back release/config on failure. Do not automatically replay archived failures; existing targeted recovery admission remains separate (TA-DTR-IMMUTABLE-PREWRITE-20261125 and TA-DP coordinated release gates).
