# Mac mini APR-05 fast local-only image overlay.
# Parent is already-built developer image. Production uses deploy/pilot/Dockerfile.
ARG BASE_IMAGE=arvectum/tender-agent:00df43958674a9eebee2bbd54e7f4116bb87173f
FROM ${BASE_IMAGE}
ARG REVISION=unknown
ARG VERSION=local-unreleased
COPY --chown=app:app src /app/src
COPY --chown=app:app migrations /app/migrations
LABEL org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.version="${VERSION}" \
      org.arvectum.local-overlay="true"
