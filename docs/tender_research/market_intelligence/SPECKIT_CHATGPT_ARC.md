# ChatGPT × ARC × Spec Kit — Power Quality execution

**Mode:** Spec Kit 1.2.4 integration `none`; no Hermes/Codex or model API dependency.

1. Read authoritative AES-001, relevant Arvectum governance, `AGENTS.md`, S0–S11 protocol and existing `.agent/checkpoints/TA-MI-AUTONOMY-20261027.yaml`.
2. Reconcile `specs/001-power-quality-evidence-closure/{spec,plan,tasks}.md` with the actual current code and verified source-grade runtime evidence. Their task status is supplemental; canonical sequencing remains in the existing roadmap/checkpoint.
3. ChatGPT uses ARC to read/write in a dedicated branch/worktree, runs actual source-safe commands/tests and records evidence. No automatic `/speckit.*` command dispatch exists in the ChatGPT session; manually follow its repository templates/stages.
4. The research continues S0–S11 within the **existing** Market Intelligence modules and approved source/data boundaries. A reviewed evidence record is not itself a signed contract, and a failed download is not a zero-demand record.
5. Run tests and independent cross-review. Spec Kit converged only means spec implementation checks have no detected gaps; it does not authorize ETP submissions, model training/gold, production mutation or release and does not override AES-001 canonical closure.
6. Keep exactly one Tender Agent Watchdog; never change its existing task ID, cadence or unrelated `.agent/current-task.yaml` without separate owner authorization.

### Useful checks

~~~sh
export PATH="$HOME/.local/bin:$PATH"
specify version
specify integration status
./.venv/bin/python -m pytest -q tests/test_pq_verified_market_report.py
git diff --check
~~~

The local `.venv/` may exist only in the main worktree; use its Python executable explicitly or the project's locked environment for isolated worktrees. Real original source bytes and generated report snapshots remain outside Git.

**First pilot step:** fix and regression-test the stale numeric warnings. **Next research step:** original commercial-ETP protocols and signed contract outcomes, with source-quoted SHA evidence. Neither the count fix nor scaffold closes the broader market study.
