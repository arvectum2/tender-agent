# Bounded existing daily document recovery

Scope: existing exact EIS 44-FZ cards with verified active revision and DOCX
or signed DOCX ZIP sources. No discovery, deal creation, automatic submissions
or overwrite of an original. Plan requires exact run, notice, deal, full
fingerprint, complete source link identity and revision. Each write uses the
active immutable release, existing daily/run/host gates, and durable journal.
One invocation registers an empty inventory, downloads one missing DOCX,
projects one stored document, or creates one verified final collection.
Original downloads are bounded to 32 MiB and restricted to official HTTPS;
ZIP package entries and total expansion are checked. Original file identity
uses document UUID and exclusive creation. Already stored ZIP hash/member
validation does not verify cryptographic signatures. Existing projection is
checked against local file and chunk hashes; the processing API returns a
transient projection, not necessarily a persisted DP collection. Final index
must independently verify actual resources and embedding contract using the
existing recover_daily_index operator. No unverified journal is silently
replayed. Different source revision, incomplete extraction, orphan file,
unknown identity or changed plan requires reconciliation.

After reviewed release deployment, run:
`python -m scripts.ops.recover_daily_documents --run RUN --registry NUMBER --deal DEAL --fingerprint FULL_SHA256`
(default read-only). For exactly the reported next step add
`--apply --confirm-release ACTIVE_SHA --expected-identity-sha PLAN_SHA`.
Re-plan after each verified step. At ready_for_index use existing index
operator, then independently verify collection readiness and use the reviewed
analysis operator. No live document writes yet: 56 focused tests passed;
four production read-only next-step plans valid; all 18 original bytes or
stored signed ZIPs validated read-only. Never treat the test as live apply.
