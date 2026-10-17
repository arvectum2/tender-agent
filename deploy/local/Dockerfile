# One existing private Mac mini operator UI; do not keep a stale wizard overlay.
ARG BASE_IMAGE=arvectum/tender-agent:00df43958674a9eebee2bbd54e7f4116bb87173f
FROM $BASE_IMAGE
ARG REVISION=unknown
ARG VERSION=local-unreleased
USER root
RUN rm -rf /app/src /app/scripts /app/migrations
COPY --chown=app:app src /app/src
COPY --chown=app:app scripts /app/scripts
COPY --chown=app:app migrations /app/migrations
USER app
LABEL org.opencontainers.image.revision="$REVISION" \
      org.opencontainers.image.version="$VERSION" \
      org.arvectum.local-overlay="true"
