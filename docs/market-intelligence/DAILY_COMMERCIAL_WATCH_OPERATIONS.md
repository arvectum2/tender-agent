# Tender Agent — daily commercial SIBUR + GEH watch

**Status as of 23 November 2026:** source-only runner implemented and offline-tested. **NOT INSTALLED OR SCHEDULED ON THE MAC MINI.** No production database, apps, model server or bidder portal is changed by this PR.

## Inputs and output

1. Existing GEH source job runs at **07:35 MSK**, as confirmed from Mac mini `com.arvectum.tender-agent-geh-fresh-cycle`. The daily report selects the newest `geh-active-refresh-YYYYMMDDThhmmssZ` folder; if latest is incomplete, in-flight, future-dated, >36h old or has tampered page SHA, the report **blocks rather than falling back** to the last successful folder. Existing `com.arvectum.daily-tender-run` runs at 08:00 MSK and is not modified.
2. SIBUR source-only public capture uses the existing `scripts.research.capture_sibur_public_snapshot.collect` with strict first-party HTTPS, TLS verification, no redirects, no credentials, 40 pages maximum, 8-second per-request timeouts with bounded retries and rate-limiting. It obtains a **new private immutable directory**. A second source-scoped `flock` prevents overlapping same-runner SIBUR captures even across separate report output directories. Incomplete capture blocks publication.
3. `scripts.research.commercial_watch.compile_watch` verifies original source hashes and immutable GEH guarded-ingest proof. Only publicly reported title, role, price (when published), deadline and original source URL go in a source-grounded 14-per-source shortlist. It distinguishes SIBUR category-only matches, source date-only deadlines, GEH price inquiries and expired deadlines. **No SAP SRM bidder credentials, GO or submission claims.**
4. Reports are private local `runs/<UTC timestamp>/commercial-watch.json`, `commercial-watch.md`, `receipt.json` with SHA-256 proofs of sources and outputs. `last_attempt.json` always reports completed or blocked; `last_success.json` changes **only after full proof and publication**. A blocked run leaves old results for audit but **must not be presented as today's report**. The next run verifies the SHA-256 of prior report files before comparing shortlists. Differences in prior 14-card shortlist are marked **not closures of the underlying source procedures**. The source report itself detects SIBUR deadline changes against the dated existing curated watch.
5. Source data and reports do not leave Mac mini. No messages, notification integrations, bids or production writes are performed. External delivery and retention policy are additional acceptance items in [issue #719](https://github.com/arvectum2/tender-agent/issues/719).

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

## Future production installation — requires separate Owner approval

Template: `deploy/launchd/com.arvectum.tender-agent-daily-commercial-watch.plist.template`. It is intentionally **not installed** and contains a `@PINNED_RELEASE_CHECKOUT@` placeholder. Proposed local schedule **08:35 MSK** — after GEH 07:35 and the existing Tender Agent 08:00 cycle; can be changed on review. Installation must use a clean, independently verified and pinned protected checkout, not any dirty or advancing working tree. Confirm effective root mode 0700, file mode 0600 and available SSD space; use exact dedicated LaunchAgent label and named log files. Run one supervised read-only/source-only first success, validate both source original hashes, receipts, no database writes, no collisions with existing GEH or core runs, and ability to disable **only this new LaunchAgent**. Never install with `RunAtLoad=true`, `KeepAlive=true`, broad restarts or additional Qwen. Stop and require Owner approval before writing `~/Library/LaunchAgents`, changing launchctl state, or configuring any outbound delivery.

**Fail closed:** if the next GEH folder is incomplete, SIBUR public page count drifts, original SHA differs, source time is stale, lock already held, disk space insufficient or prior report tampered, `last_attempt.status=blocked`; `last_success` remains audit history, not a new delivery. No retries or old-data substitution without investigation.
