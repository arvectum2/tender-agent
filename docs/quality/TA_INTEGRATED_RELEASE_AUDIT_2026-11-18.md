# Integrated release audit — development candidate; production NO-GO

Main and actual admitted runtime 3b37fb6988dd996efeb55e69058016a22a2bd48f. Integrated stack at 846dece712f06ba9c23d891f7e10a5dbb8af7301 contains main and PR640 head 3afb5f82; 151 files changed. All three loopback health endpoints (DP, TA, embeddings) responded. Exact audit code 2c94f9a2c3f0da4273cd2d058bc965ac304a3177 includes additional input approval binding. No database migration, dependency lock or CI config changed relative to main. PR640–656 draft chain remains unmerged, registration-snapshot intermediate ancestry included. PR655 exact CI 19/19, PR656 17/19 latest observed. GitHub list request transient 502; individual exact PR reads succeeded. Historical green checks do not substitute for exact final candidate CI.

## Engineering test evidence

32 selected changed/related test files: 456 passed, 8 skipped, 48 warnings, exit 0; make check PASS. Changed Python lint: 84 files, only two existing BLE001 broad exception catches in prepare_service.py also present on main, not a new failure. New files lint and diff check PASS. No model workload, private blocked replay, deployment, merge, token or runtime mutation performed. This is targeted combined regression, not the full hosted suite or real application acceptance.

## Fixed audit finding

The reviewed checklist scope previously pinned source and scenario but not exact build inputs. Now the bridge requires a separate exact input digest over template bytes and reviewed mapping, selected claim codes, cost scenario and exact commercial/declaration terms, checked before and after assembly. This prevents accidental or unauthorized input changes relative to a separately retained approved digest. It does not authenticate an approver; selected claim codes do not pin current document versions or identity fact versions at approval time. Existing current-document checks during assembly remain. 25 focused tests pass, including new input-binding tests; included in combined run.

## Release verdict

- Candidate development regression: PASS with documented legacy lint findings.
- Full candidate CI, integration/merge to main: pending; consolidated review only, no merge authorization.
- Application workflow: internal Python entry points only; no integrated product API/UI or authenticated plan/inputs approval storage. Real form and statement mapping, current qualification and capacity, actual profile intake, immutable evidence approval, independent review and release acceptance unresolved.
- Real private checklist replay was denied by execution safety; no retry or bypass. Original source coverage is narrow, not general 44/223-FZ.
- Coordinated WSF07B live transition remains blocked; existing admitted runtime unchanged. Prior authorization specific to old release does not authorize new candidate. New coordinated release plan, fresh acceptance and approved deployment mechanism necessary.
- APR06 independent commercial gold, APR07 rolling production SLO, APR09 authorized commercial pilot still open. No release or GO claim.
- Priority: approved integration/release review first; authenticated approval and source/tenant binding, permitted actual-data acceptance and operational rollback checks before authorizing exposure. Preserve both safety blocks.

One consolidated draft targeting main can be reviewed as the entire candidate without sequential merges; previous PRs remain untouched. Not an executed release.
