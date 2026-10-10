# R3 presentation extraction — legacy Operator (2026-10-10)

This staged compatibility change extracts two high-volume presentation-only
functions from Tender Agent's legacy upload orchestration:

- Historical HTML renderer: 394 source lines moved to
  `operator_legacy_html_renderer.py`. Original `_render_report_html`
  signature remains; document inventory, supply title and local file location
  are injected so the presentation module does not own collection/runtime IO.
- Step view projector: 336 source lines moved to `operator_step_projection.py`.
  Original `_build_steps_from_outputs` signature remains; the new module only
  transforms report payloads into typed step/detail sections.

No change to official notice source precedence, Data Platform SDK or JSON
evidence locators; no PDF/LLM automatic confidence promotion. The changes
reduce the uploader by roughly 730 lines without deleting existing consumers.
This does NOT claim full legacy removal or complete semantic duplicate cleanup.

Validation: 66 focused UI/report/export/source regressions, two dedicated
facade delegation tests, and full Tender Agent 3469 passed / 238 skipped.
Uses internal Mac mini worktree with Python 3.12 and PostgreSQL 16 client on
PATH to match the R9 disposable test database. The working owner preview
port 18083 is unchanged.
