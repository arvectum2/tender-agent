# One existing private Mac mini operator UI; do not keep a stale wizard overlay.
ARG BASE_IMAGE=arvectum/tender-agent:00df43958674a9eebee2bbd54e7f4116bb87173f
FROM $BASE_IMAGE
ARG REVISION=unknown
ARG VERSION=local-unreleased
USER root
COPY pyproject.toml /tmp/overlay-pyproject.toml
RUN python -c "import tomllib; from pathlib import Path; base=tomllib.loads(Path('/app/pyproject.toml').read_text()); target=tomllib.loads(Path('/tmp/overlay-pyproject.toml').read_text()); raise SystemExit(0 if base['project']['dependencies']==target['project']['dependencies'] and base['project']['requires-python']==target['project']['requires-python'] else 'Overlay dependency mismatch: rebuild full pilot base')" \
    && python -m pip check && rm /tmp/overlay-pyproject.toml
RUN rm -rf /app/src /app/scripts /app/migrations
COPY --chown=app:app src /app/src
COPY --chown=app:app scripts /app/scripts
COPY --chown=app:app migrations /app/migrations
COPY --chown=app:app docs/roadmap/price01_aksay_original_protocol_baseline_2026-10-17.json docs/roadmap/price01_website_cohort_official_2026-10-18.json docs/roadmap/price01_workload_normalization_2026-10-18.json docs/roadmap/source_pipeline_policy_v1.json docs/roadmap/b2b_oct18_three_new_eis_originals.json docs/roadmap/b2bcenter_six_primary_oct18.json docs/roadmap/b2b_oct18_b2bcenter_4643484_firstparty.json /app/docs/roadmap/
USER app
LABEL org.opencontainers.image.revision="$REVISION" \
      org.opencontainers.image.version="$VERSION" \
      org.arvectum.local-overlay="true"
