# Existing authenticated Tender Agent runtime - 2026-10-19

Status update, 19 Oct 2026 12:45 Moscow: **canonical PostgreSQL and source-bound Data Platform indexing are now working, 86/86/86 verified**. Separate real Gemma quality analysis is in progress, not yet accepted. No new EIS SOAP or Data Platform token required.

EIS document retrieval uses ZAKUPKI_GOV_RU_SOAP_TOKEN, which is already configured. Local document indexing uses AI_CORP_RAG_DATA_PLATFORM_API_KEY matching the existing protected Data Platform service ARVECTUM_DATA_INTERNAL_API_KEY. Both settings **currently match**, per read-only checks on the Mac mini.

Standalone Tender Agent lacks AI_CORP_DATABASE_URL (falls back to SQLite). Existing source intake shell runner expects a .env.local file missing in the base checkout. No new database or credentials are required.

New scripts/runtime/verified_procurement_runtime.py loads the **existing** owner config and Data Platform runtime config only in memory with mode0600/owner checks, validates canonical local PostgreSQL arvectum, rejects mismatched existing keys or foreign DB, then launches a fixed official analysis entrypoint with os.execvpe (no password in argv, git, stdout or new config).

## What changed after the original blocked checkpoint

Owner diagnostic showed PROD_DB_NAME is **not** arvectum despite role credentials being present. This was a false hard-coded requirement of the first bootstrap. The production profile belongs to a different service; leave its name and password unchanged.

Verified on Mac mini that PostgreSQL instance Docker container arvectum-postgres exposes the canonical database on loopback port 55432; owner role name matches. The production-profile password did not authenticate to this separate instance. The corrected bootstrap uses the **existing owner-operated container credential in memory** via local Docker operator access only, never printing it, putting it in argv/Git or creating a new credential. Read-only SQL of the canonical database and its Tender Research table succeeded (CANONICAL_DB_CONNECTED). Existing Data Platform key agreement and SOAP were not modified.

After derived DOCX packaging normalization, stable document identity legitimately blocked a different binary SHA. New strict compatibility verifier checks all uncompressed OOXML parts, private permissions, SHA of stored physical bytes, archived ZIP and XML source provenance, then **reuses** the old stored document hash (not a silent overwrite, no original changed). After two Remote Desktop session interruptions, authorized SSH from MacBook to Mac mini completed the exact source pipeline, with a full verified pg_dump custom backup SHA 163d3633fc5c8113a796e5f71b9256752bb979c0a2c41cc2b99f5f7e67dc8ad1.

Final first-party evidence: 6 original attachments unchanged, 5 original DOCX source-indexable, derived official XML NMC 497178.33 and deadline 30 October 2026 11:00 Moscow, 14 technical characteristics, criteria 30/70 and 80/20. **86 SQL chunks, 86 Data Platform resources, 86 embeddings**, status completed, readiness true, no blockers. Human gold = 0, current legal status not attested, BID_GO false.

One separate live Gemma 4 12B quality RAG run was started via authorized local SSH at approximately 12:32:54 Moscow, PID 41097, protected log under private/tender-agent/quality-benchmarks/gemma-rag-index-20261019/quality-ssh.log. It is **in progress until completion is actually verified**; do not start another quality process. After completion audit the distinct TenderAnalysisRun with source=source_quality_rerun, compare report source citations/elapsed to original 249.97s fast and 1610.40s source-only detailed benchmarks. Training gold, merger and ETP actions remain gated.

Operator commands on the authorized Mac mini, only after the protected environment allows execution:

    cd /Volumes/ArvectumSSD/Arvectum/worktrees/ta-protected-runtime-bootstrap-20261019
    PYTHONPATH=. /Volumes/ArvectumSSD/Arvectum/repos/tender-agent/.venv/bin/python -m scripts.runtime.verified_procurement_runtime --operation doctor
    PYTHONPATH=. /Volumes/ArvectumSSD/Arvectum/repos/tender-agent/.venv/bin/python -m scripts.runtime.verified_procurement_runtime --operation index
    PYTHONPATH=. /Volumes/ArvectumSSD/Arvectum/repos/tender-agent/.venv/bin/python -m scripts.runtime.verified_procurement_runtime --operation quality

Do not execute operations index and quality concurrently. Index uses existing backup and source-SHA gates; quality is a separate actual TenderAnalysisRun with source=source_quality_rerun, never a duplicate original completion or human gold.

Actual execution of --operation doctor was blocked by the protected remote tool before starting. No workaround or secret extraction attempted. Thus index and quality are NOT run. Existing evidence: 8 Smolensk documents, 72 old chunks, 121 learning observations, 46 original runs. SOAP and local Gemma llama.cpp are already configured. No new model downloaded, no ETP action, no merge or automated gold.

Once authorized operator execution succeeds, verify 6 unchanged source SHA files, two derived XML/criteria documents, fresh Data Platform chunks/embeddings, real new quality run/report SHA, then source-fact evaluation of NMC 497178.33, 30/70 and 80/20, 20 technical and 6 contractual questions against baseline 249.97s and direct-original 1610.40s.
