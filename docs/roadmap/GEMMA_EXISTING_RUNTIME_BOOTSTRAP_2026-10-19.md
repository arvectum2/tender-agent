# Existing authenticated Tender Agent runtime - 2026-10-19

Status: **blocked until a protected operator process can execute.** No new EIS SOAP token or Data Platform API key needed.

EIS document retrieval uses ZAKUPKI_GOV_RU_SOAP_TOKEN, which is already configured. Local document indexing uses AI_CORP_RAG_DATA_PLATFORM_API_KEY matching the existing protected Data Platform service ARVECTUM_DATA_INTERNAL_API_KEY. Both settings **currently match**, per read-only checks on the Mac mini.

Standalone Tender Agent lacks AI_CORP_DATABASE_URL (falls back to SQLite). Existing source intake shell runner expects a .env.local file missing in the base checkout. No new database or credentials are required.

New scripts/runtime/verified_procurement_runtime.py loads the **existing** owner config and Data Platform runtime config only in memory with mode0600/owner checks, validates canonical local PostgreSQL arvectum, rejects mismatched existing keys or foreign DB, then launches a fixed official analysis entrypoint with os.execvpe (no password in argv, git, stdout or new config).

Operator commands on the authorized Mac mini, only after the protected environment allows execution:

    cd /Volumes/ArvectumSSD/Arvectum/worktrees/ta-protected-runtime-bootstrap-20261019
    PYTHONPATH=. /Volumes/ArvectumSSD/Arvectum/repos/tender-agent/.venv/bin/python -m scripts.runtime.verified_procurement_runtime --operation doctor
    PYTHONPATH=. /Volumes/ArvectumSSD/Arvectum/repos/tender-agent/.venv/bin/python -m scripts.runtime.verified_procurement_runtime --operation index
    PYTHONPATH=. /Volumes/ArvectumSSD/Arvectum/repos/tender-agent/.venv/bin/python -m scripts.runtime.verified_procurement_runtime --operation quality

Do not execute operations index and quality concurrently. Index uses existing backup and source-SHA gates; quality is a separate actual TenderAnalysisRun with source=source_quality_rerun, never a duplicate original completion or human gold.

Actual execution of --operation doctor was blocked by the protected remote tool before starting. No workaround or secret extraction attempted. Thus index and quality are NOT run. Existing evidence: 8 Smolensk documents, 72 old chunks, 121 learning observations, 46 original runs. SOAP and local Gemma llama.cpp are already configured. No new model downloaded, no ETP action, no merge or automated gold.

Once authorized operator execution succeeds, verify 6 unchanged source SHA files, two derived XML/criteria documents, fresh Data Platform chunks/embeddings, real new quality run/report SHA, then source-fact evaluation of NMC 497178.33, 30/70 and 80/20, 20 technical and 6 contractual questions against baseline 249.97s and direct-original 1610.40s.
