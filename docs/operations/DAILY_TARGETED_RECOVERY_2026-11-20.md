# Targeted daily recovery: operator preflight

The existing daily CLI resumes runs and starts a new discovery; it is not a
selective historical repair command. The new read-only planner accepts exact
run ID, registry number, existing deal ID and full source fingerprint. It
rejects ambiguous identities, changed sibling revisions/deals, human decisions,
active runs, prior/orphan analysis history and missing or archived deals.
It excludes already completed identical deal/fingerprint siblings.

Run the read-only planner from the approved pinned environment:
`python -m scripts.ops.plan_daily_tender_recovery --run RUN --registry NUMBER --deal DEAL --fingerprint FULL_SHA256`.
The command explicitly sets PostgreSQL transaction READ ONLY. It never writes
or creates an intake, runs analysis, downloads documents or sends notifications.

Acceptance on the existing November 19/20 failed-item inventory: 9 candidates,
2 already completed. No live data changes.

Before adding the apply path: require exact source revision and collection
identity, verify individual existing chunk evidence against Data Platform,
retain current deal and failed-run provenance, verified production backup +
mandatory MI/PITR prewrite acceptance and shared fresh lease, no broad discovery,
post-decision automation or external submission. Reconcile any interrupted
analysis history rather than starting a duplicate. Do not use this planner as
a write authorization. Actual repair remains a separate reviewed operation.

## Exact index reconciliation
The pure reconciliation helper compares canonical tender-chunk URI and SHA-256
of original text against resource, document and projected chunk hashes; it
checks provider/model/dimension against the collection contract. Duplicate,
unknown, mismatched, or partially indexed existing resource identities block
automatic treatment as absent. Production read-only verification of the five
incident collections found 563 expected, 20 present with matching three hashes
and embedding contract, 543 absent resources, zero unexpected/conflicting
identities. This is not a completed ingestion receipt.

## Bounded index-only operator command

After independent review and deployment of this exact release, run from its
immutable source directory with its own venv:
`venv/bin/python -m scripts.ops.recover_daily_index --run RUN --registry NUMBER --deal DEAL --fingerprint FULL_SHA256`
(use the actual absolute interpreter path from the deployed release). Default
is read-only; result contains the exact release/target/collection/chunk/model
identity SHA and current missing-resource counts. Apply mode additionally
requires explicit `--apply --confirm-release EXACT_ACTIVE_SHA --expected-identity-sha PLAN_SHA`.

The launcher checks that the source and Python venv belong to the active
release, uses the existing daily preflight and daily lock, uses read-only
PostgreSQL transactions and independently validates actual stored text hashes,
owner, unversioned collection, resource/extraction status, vector dimensions
and embedding contract. Before each bounded batch, existing host resource,
fresh priority, mutation and backup leases must be available. The current
MI verifier, independently archived backup identity and fresh durable PITR
restore point must pass. A paused/stale monitor, maintenance/STOP, competing
lease, changed target, active RAG job or receipt discrepancy refuses work.
Normal/reduced limits are 10/3. Existing indexes are not rebuilt, only absent
canonical chunk resources use the supported Data Platform ingest API.
The private append-only attempt journal stores prewrite proof and request/
response markers before each API action and a final independent verification.
A missing verified end marker prevents automatic repeat. Never delete or
modify a pending journal to force a retry; reconcile it with independent
Data Platform evidence and operator review first.

The scope is index-only, not the four missing-document cases or analysis/
manager-ready transitions. This does not create a second procurement database,
change tender status, submit an application, or trigger notifications. Existing
legacy/manual ingestion endpoints are not claimed to be universally protected
by these host leases; ensure no competing manual repair for the target during
the reviewed canary. The operator must not use unreviewed source or weaken
prewrite gates. Actual live apply acceptance remains outstanding.

Validation: 54 focused tests passed, including interrupted journals and
competing leases. New operator planning core replay against all five real
production collections returned 543 absent and 20 matching resources;
all nine original recovery candidates and two excluded completed siblings
were revalidated. The MI gate passed in the exact operator subprocess
environment; read-only PITR readiness also passed. No live business writes.
