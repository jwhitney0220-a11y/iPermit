# iPermit public API runtime image (S07-05, SAAS-07).
#
# Two-stage build: the first stage installs the Python deps into a virtual env
# inside a fat builder image (so wheels with C extensions get their headers);
# the runtime stage copies the venv + source onto a slim base, so the shipped
# image carries only what the API needs at runtime. Matches the iPermit deploy
# topology (ADR-0001): a container behind a load-balancer, talking to managed
# Postgres + PostGIS over the network.
#
# Built from the repo root so the monorepo's packages/services are reachable:
#   docker build -f services/api/Dockerfile -t ipermit/api:dev .

# --- Stage 1: build -----------------------------------------------------------
FROM python:3.11-slim-bookworm AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# libpq-dev + build tools cover psycopg / cryptography wheels that ship sdists.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY services/api/requirements.txt /tmp/requirements.txt

# Isolate dependencies in a venv that's copied verbatim to the runtime stage.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install -r /tmp/requirements.txt

# --- Stage 2: runtime ---------------------------------------------------------
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/services/api:/app/services/rules-engine:/app/services/gis-engine:/app/packages/persistence:/app/packages/rule-definitions:/app/packages/tenancy-models:/app/packages/regulatory-models:/app/packages/audit-models:/app/packages/jurisdiction-models"

# libpq5 is the runtime counterpart to libpq-dev (psycopg dynlink).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system ipermit \
    && useradd --system --gid ipermit --home /app --shell /bin/false ipermit

WORKDIR /app
COPY --from=build /opt/venv /opt/venv

# Source layout: copy only what the API service needs at runtime.
COPY services/api ./services/api
COPY services/rules-engine ./services/rules-engine
COPY services/gis-engine ./services/gis-engine
COPY packages ./packages
COPY rules ./rules
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini

USER ipermit
EXPOSE 8000

# Hand-off to uvicorn. Workers are configured by the orchestrator (e.g. ECS
# task def, k8s Deployment), not baked into the image, so the same image runs
# at any concurrency.
CMD ["uvicorn", "ipermit_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
