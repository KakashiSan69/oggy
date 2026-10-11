# =============================================================================
# Base Stage
# =============================================================================
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libpq-dev \
    gcc \
    curl \
    ca-certificates \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

# =============================================================================
# Development Stage
# =============================================================================
FROM base AS development

RUN pip install --no-cache-dir -e ".[dev]"

COPY src/ ./src/
COPY scripts/ ./scripts/
COPY tests/ ./tests/

RUN mkdir -p /app/data /app/logs /app/temp

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["python", "-m", "src.main"]

# =============================================================================
# Production Stage
# =============================================================================
FROM base AS production

COPY src/ ./src/
COPY scripts/ ./scripts/

RUN mkdir -p /app/data /app/logs /app/temp

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "src.main"]