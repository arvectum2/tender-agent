# Tender Operator Site Deployment

## Short Answer

Yes, the Tender Operator pilot can be attached to the website and deployed, but
not as a plain static/PHP page only.

The working production shape is:

1. the existing marketing site stays static/PHP;
2. the Tender Operator pilot runs as a separate FastAPI service;
3. the website domain reverse-proxies pilot routes into that FastAPI service.

This keeps the current UI and API paths working without browser-side CORS work:

- `/demo/tender-agent`
- `/pilot/tender-agent`
- `/api/demo/tender-agent/*`

## Recommended Deployment Shape

Use the same public domain and proxy the pilot routes to the Python service.

Example public flow:

- `https://arvectum.com/` -> static/PHP site
- `https://arvectum.com/cases/tender-operator-demo.html` -> marketing demo-case
- `https://arvectum.com/pilot/tender-agent` -> live controlled pilot UI

## Why This Shape Is Preferred

- the pilot frontend already uses same-origin relative URLs;
- no CORS is required for the common same-domain setup;
- the existing website can stay on its current hosting model;
- backend rollout is isolated from the static site rollout;
- human-review and access controls stay on the pilot side.

## Minimum Production Controls

Do not publish the live pilot as a fully open anonymous public tool.

Minimum controls for a controlled pilot:

- enable HTTP Basic Auth on pilot routes;
- restrict `Host` headers with `AI_CORP_ALLOWED_HOSTS`;
- keep `AI_CORP_LLM_ALLOW_RAW_PARTNER_DATA=false`;
- keep `AI_CORP_LLM_STORE_RAW_RESPONSE=false` unless explicitly needed;
- keep human review in the workflow and do not enable external actions;
- keep real tokens and API keys only in deployment secrets.

## Environment Example

```dotenv
AI_CORP_DATABASE_URL=sqlite:///./ai_corporation.db
AI_CORP_DEBUG=false
AI_CORP_ALLOWED_HOSTS=arvectum.com,www.arvectum.com,127.0.0.1,localhost
AI_CORP_CORS_ALLOW_ORIGINS=
AI_CORP_TENDER_PILOT_BASIC_AUTH_ENABLED=true
AI_CORP_TENDER_PILOT_BASIC_AUTH_USERNAME=pilot_operator
AI_CORP_TENDER_PILOT_BASIC_AUTH_PASSWORD=replace_me_in_secret_store

AI_CORP_LLM_PROVIDER=stub
AI_CORP_LLM_ALLOW_RAW_PARTNER_DATA=false
AI_CORP_LLM_STORE_RAW_RESPONSE=false
```

For a cross-origin frontend setup, set:

```dotenv
AI_CORP_CORS_ALLOW_ORIGINS=https://arvectum.com,https://www.arvectum.com
```

## Container Build

Build the application image from the Tender Agent repository root:

```bash
docker build -t ai-corporation-tender-pilot .
```

The runtime image is self-contained and does not require a sibling checkout of
`arvectum-landing`. The pilot UI assets required by the FastAPI application live
inside this repository under `src/` and are copied by the normal application
build.

Run it locally:

```bash
docker run --rm -p 8000:8000 --env-file .env.local ai-corporation-tender-pilot
```

## Unified Local Preview

The marketing site is a separate repository. To preview that site and the live
pilot behind one local entrypoint, explicitly point Compose at the marketing
site's `public` directory instead of relying on a sibling-directory layout:

```bash
export ARVECTUM_LANDING_PUBLIC_DIR=/absolute/path/to/arvectum-landing/public
docker compose -f docker-compose.site-pilot.yml up --build
```

`docker-compose.site-pilot.yml` fails fast when
`ARVECTUM_LANDING_PUBLIC_DIR` is missing or empty. This keeps the optional local
marketing-site dependency explicit while the Tender Agent image itself remains
clean-checkout reproducible.

Local URLs:

- `http://127.0.0.1:8081/`
- `http://127.0.0.1:8081/cases/tender-operator-demo.html`
- `http://127.0.0.1:8081/pilot/tender-agent`
- `http://127.0.0.1:8081/demo/tender-agent`

This stack serves the Arvectum static site from Nginx and proxies the Tender
Operator pilot routes into the FastAPI container.

If `8081` is busy, override the port while keeping the explicit landing path:

```bash
ARVECTUM_LANDING_PUBLIC_DIR=/absolute/path/to/arvectum-landing/public \
ARVECTUM_SITE_PORT=8090 \
docker compose -f docker-compose.site-pilot.yml up --build
```

## Pure Python Same-Port Preview

If you want the external static site and the pilot on one local port without
Nginx, set `AI_CORP_SITE_PUBLIC_ROOT` explicitly and run the main FastAPI app
directly:

```bash
AI_CORP_SITE_PUBLIC_ROOT=/absolute/path/to/arvectum-landing/public \
./.venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8090
```

`AI_CORP_SITE_PUBLIC_ROOT` is optional. When it is unset, FastAPI runs normally
without marketing-site files. When it is set, the configured directory must
contain `index.html` for the optional static-site mount to activate.

This mode is useful for local demos and quick operator preview. It serves the
static site from the filesystem and keeps the pilot routes on the same origin.

Note:

- it serves static files only;
- it does not execute the PHP handlers from the marketing site;
- for production on the existing site hosting model, prefer the reverse-proxy shape.

## Reverse Proxy

An example Nginx config is provided in:

- `ops/nginx/arvectum-tender-pilot.conf.example`
- `ops/nginx/arvectum-site-pilot.local.conf`

Proxy these route groups to the FastAPI service:

- `/demo/tender-agent`
- `/pilot/tender-agent`
- `/api/demo/tender-agent/`

Optional health endpoint:

- `/health/tender-agent` -> upstream `/health`

## Readiness Notes

This deployment shape is suitable for a controlled pilot or protected live demo.

It is not yet a full public SaaS launch because the repository still assumes:

- manual review;
- single-tenant or operator-controlled usage;
- local or bounded filesystem outputs;
- no autonomous external execution.
