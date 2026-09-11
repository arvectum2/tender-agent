FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY alembic.ini ./
COPY src ./src
COPY scripts ./scripts
COPY docs ./docs
COPY demo_data ./demo_data
COPY migrations ./migrations
COPY arvectum-landing/public/assets ./arvectum-landing/public/assets

# wvHtml converts legacy OLE Word (.doc) tables into structure-preserving HTML
# for the document text extractor. No LibreOffice or other converters needed.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends wv \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
