# syntax=docker/dockerfile:1

# -- Base stage ---------------------------------------------------------------
FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# -- Dev stage ----------------------------------------------------------------
FROM base AS dev

RUN uv sync --frozen

# Copy source (overridden by volume mounts in dev compose)
COPY app/ app/
COPY main.py .

# -- Prod stage ---------------------------------------------------------------
FROM base AS prod

RUN uv sync --frozen --no-dev

COPY app/ app/
COPY main.py .

# Put venv on PATH so we don't need `uv run` at runtime
ENV PATH="/app/.venv/bin:$PATH"

# Run as non-root in production
RUN useradd -m -u 1000 appuser
USER appuser
