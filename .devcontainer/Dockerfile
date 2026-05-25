# Dev container image for the iPermit monorepo (T01-12).
#
# Provides a consistent local/cloud development environment matching ADR-0001:
#   - Python 3.11+ (FastAPI backend services + tooling)
#   - Node.js 20 LTS (TypeScript/React frontends — see .nvmrc)
#   - PostgreSQL/PostGIS *client* tools (psql + GDAL/ogr2ogr) for talking to a
#     Postgres 16 + PostGIS database. The database itself runs as a separate
#     service/container (T05-01), not inside this image.
#
# Base: the Microsoft devcontainers Python image already ships a non-root
# `vscode` user, common build tooling, and a sane shell.
FROM mcr.microsoft.com/devcontainers/python:3.11-bookworm

ENV DEBIAN_FRONTEND=noninteractive

# --- System packages: PostGIS client tooling + geospatial CLI ----------------
# postgresql-client  -> psql for ad-hoc queries against the PostGIS database
# gdal-bin / proj     -> ogr2ogr + projection tools for shapefile/KMZ workflows
#                        (EPIC-05 GIS engine), matching the Python geospatial stack
# libpq-dev           -> headers for building psycopg if a service needs it
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        gdal-bin \
        proj-bin \
        libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# --- Node.js 20 LTS (matches .nvmrc) -----------------------------------------
# Installed via the official NodeSource setup so the version is pinned and not
# tied to whatever Debian ships.
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# --- Python tooling ----------------------------------------------------------
# Pin Ruff to the same version as .pre-commit-config.yaml so the container,
# pre-commit, and CI all agree. pre-commit manages the git hooks.
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir "ruff==0.15.8" "pre-commit>=3.5"

# Drop back to the non-root user provided by the base image for day-to-day work.
USER vscode
