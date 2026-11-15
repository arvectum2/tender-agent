FROM python:3.11-slim AS runtime
ARG REVISION=unknown
ARG VERSION=unreleased
LABEL org.opencontainers.image.revision=$REVISION org.opencontainers.image.version=$VERSION org.opencontainers.image.source="https://github.com/arutyunoveth/ai-corporation" org.arvectum.release-baseline="c0e7c7dbfb65765e5a918318d784115b00b4ce06"
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core libmagic1 && rm -rf /var/lib/apt/lists/* && useradd --create-home --uid 10001 app
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY config/daily_tender_profiles ./config/daily_tender_profiles
COPY scripts ./scripts
COPY docs/agents/company ./docs/agents/company
COPY docs/roadmap/price01_aksay_original_protocol_baseline_2026-10-17.json docs/roadmap/price01_website_cohort_official_2026-10-18.json docs/roadmap/price01_workload_normalization_2026-10-18.json docs/roadmap/source_pipeline_policy_v1.json docs/roadmap/b2b_oct18_three_new_eis_originals.json docs/roadmap/b2bcenter_six_primary_oct18.json docs/roadmap/b2b_oct18_b2bcenter_4643484_firstparty.json ./docs/roadmap/
COPY demo_data/tender_operator_agent ./demo_data/tender_operator_agent
COPY migrations ./migrations
COPY alembic.ini ./
RUN pip install --no-cache-dir . && mkdir -p /app/data /app/artifacts /app/eis-archives && chown -R app:app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
