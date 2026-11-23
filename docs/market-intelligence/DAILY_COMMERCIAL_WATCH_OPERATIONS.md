# Tender Agent — daily commercial SIBUR + GEH watch

**Status as of 23 November 2026, after explicit Owner approval:** installed and tested on Mac mini with a **07:00 MSK ChatGPT digest**. GEH source capture now runs at 05:15 MSK; SIBUR public source capture and local report at 06:20 MSK; ChatGPT Scheduled Task delivers at 07:00 MSK; existing Daily Tender remains 08:00 MSK. The first actual future scheduled daily cycle is 24 November and still needs next-day acceptance. No portal submissions, model loads, server reboots or general Tender Agent release were performed.

## Inputs and output

1. Existing GEH source job `com.arvectum.tender-agent-geh-fresh-cycle` was shifted from **07:35 to 05:15 MSK** under user approval. The daily report selects the newest `geh-active-refresh-YYYYMMDDThhmmssZ` folder; if latest is incomplete, in-flight, future-dated, >36h old or has tampered page SHA, the report **blocks rather than falling back** to the last successful folder. Existing `com.arvectum.daily-tender-run` runs at 08:00 MSK and is not modified.
2. SIBUR source-only public capture uses the existing `scripts.research.capture_sibur_public_snapshot.collect` with strict first-party HTTPS, TLS verification, no redirects, no credentials, 40 pages maximum, 8-second per-request timeouts with bounded retries and rate-limiting. It obtains a **new private immutable directory**. A second source-scoped `flock` prevents overlapping same-runner SIBUR captures even across separate report output directories. Incomplete capture blocks publication.
3. `scripts.research.commercial_watch.compile_watch` verifies original source hashes and immutable GEH guarded-ingest proof. Only publicly reported title, role, price (when published), deadline and original source URL go in a source-grounded 14-per-source shortlist. It distinguishes SIBUR category-only matches, source date-only deadlines, GEH price inquiries and expired deadlines. **No SAP SRM bidder credentials, GO or submission claims.**
4. Reports are private local `runs/<UTC timestamp>/commercial-watch.json`, `commercial-watch.md`, `receipt.json` with SHA-256 proofs of sources and outputs. `last_attempt.json` always reports completed or blocked; `last_success.json` changes **only after full proof and publication**. A blocked run leaves old results for audit but **must not be presented as today's report**. The next run verifies the SHA-256 of prior report files before comparing shortlists. Differences in prior 14-card shortlist are marked **not closures of the underlying source procedures**. The source report itself detects SIBUR deadline changes against the dated existing curated watch.
5. Source capture and report generation operate privately on Mac mini, with no bids, ETP logins, models or production DB writes. Separate ChatGPT automation `6b03d6bd374c8191a4ef19cd4a5fcd17` reads only a freshly completed, source-SHA-verified report and sends a user-visible 07:00 MSK digest; if blocked, it reports that no current digest exists. Retention policy and verification of the first true scheduled day remain tracked in [issue #719](https://github.com/arvectum2/tender-agent/issues/719).

## Offline read-only rehearsal (no local output, no network)

From a **pinned protected checkout** with repository dependencies installed:

```sh
python -m scripts.research.daily_commercial_watch \
 --geh-root /Users/master/ArvectumSafe/runtime/ta-source-discovery-20261114/parallel-sources \
 --sibur-root /Users/master/ArvectumSafe/runtime/ta-source-discovery-20261114/sibur-sales-map-20261115 \
 --sibur-watch /Users/master/ArvectumSafe/runtime/ta-source-discovery-20261114/sibur-sales-map-20261115/sibur-current-commercial-watch-v18.json \
 --sibur-current-capture /Users/master/ArvectumSafe/runtime/ta-source-discovery-20261114/sibur-sales-map-20261115/current-commercial-20261122T192739Z
```

The pinned SIBUR folder is the exact saved **22-Nov** source used for reproducibility; it expires for *current* reporting after 36h. Use a newer fully verified source for subsequent rehearsals. The latest GEH folder may change concurrently; if it is currently in-flight, exit status 2 is expected and correct.

## Private report rehearsal (no source requests)

On an **isolated, trusted test directory**, opt into output writes with `--execute --sibur-current-capture <fully verified dir> --out-root <private-test-folder>`, without `--capture-sibur`. The runner checks disk space, folder permissions, state flags and original SHA, and writes only its private receipt/report. Do not run with shared output folders or production database paths. The existing daily Tender Agent infrastructure is **not** restarted or rewritten.

## Owner-authorized production installation (23 Nov 2026)

On Mac mini `Mac-mini-master.local`, deployed a clean pinned source-only checkout `/Users/master/ArvectumSafe/releases/mi-commercial-watch-71b28f550559` at exact main commit `71b28f550559a45c47056e7b1b0adb1d5eb51bdc`; `46/46` focused pytest PASS and Ruff PASS. This does **not** deploy the new Daily Tender core/backend or its Data Platform.

Actual `~/Library/LaunchAgents`:
- `com.arvectum.tender-agent-geh-fresh-cycle.plist`: existing job, schedule changed **07:35 → 05:15 MSK** only (source run time on 23 Nov was about 30 minutes end-to-end including admission).
- `com.arvectum.tender-agent-daily-commercial-watch.plist`: **new dedicated job at 06:20 MSK**, `RunAtLoad=false`, `KeepAlive=false`; pinned source-only first-party GET and deterministic private report.
- `com.arvectum.daily-tender-run.plist`: remains at 08:00 MSK unchanged.
- ChatGPT daily Scheduled Task `6b03d6bd374c8191a4ef19cd4a5fcd17`: **07:00 Europe/Moscow**, next `2026-11-24T07:00:00+03:00`, enabled (checked after creation). It validates same-day receipt/hash and delivers the user-facing shortlist; a failed/missing report produces an explicit failure message, never a stale one.

Source-run backup and rollback assets live privately at `/Users/master/ArvectumSafe/runtime/ta-source-discovery-20261114/commercial-watch-deploy-20261123/`: original GEH plist `com.arvectum.tender-agent-geh-fresh-cycle.plist.backup` SHA-256 `97923c9d47dfa16b1722020c1f78ce1664b87dd4cd287c543913a1027b1473c7`; deployed launchd payloads and deployment manifest. To roll back this source watch, only boot out `com.arvectum.tender-agent-daily-commercial-watch` and remove its dedicated plist. Restore **only** the original GEH plist backup and bootstrap its original job if source schedule rollback is required; do not touch `com.arvectum.daily-tender-run`, production DB, other LaunchAgents or resource governor. The ChatGPT delivery Scheduled Task must separately be paused if the source report is retired. No automatic rollback was performed.

### Live pre-schedule acceptance

23-Nov supervised one-time `launchctl kickstart` of **only the new source-watch label** finished with exit code **0**. Captured fresh public SIBUR **28/28 pages**, generated report with **54** SIBUR and **34** GEH relevant future-deadline public observations; last_attempt and last_success `completed` with the same run ID `20261123T060100011405Z`, verified private JSON/Markdown SHA-256 and five source-evidence SHA hashes. The report output directory is 0700, launchd plists are 0600. No extra Qwen, no unrelated DB changes or supplier action.

**Outstanding acceptance:** the *scheduled* source jobs at 05:15/06:20 and delivery at 07:00 have not yet occurred on 24-Nov. Keep [issue #719](https://github.com/arvectum2/tender-agent/issues/719) open for first scheduled 24-Nov proof, missed-run/fail-closed checks and longer-term retention policy. Avoid equating a successful manual canary with verified future delivery.

**Fail closed:** if GEH latest capture is incomplete, SIBUR public page count drifts, original SHA differs, source time is stale, source lock already held, disk space insufficient or prior report tampered, `last_attempt.status=blocked`; historical `last_success` is **not** today's delivery. No silent fallback or unsupported availability claims.
