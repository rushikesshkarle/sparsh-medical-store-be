# ---- Base Python Image ----
FROM python:3.11-slim

WORKDIR /app

# ---- Install Poetry ----
ENV POETRY_VERSION=1.8.5 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

# ---- Install Python dependencies (cached layer; re-runs only when deps change) ----
COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-ansi --no-root --only main

# ---- Copy source code ----
COPY . .

# ---- Run as an unprivileged user; media/ is the only writable path ----
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/media/products \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)" || exit 1

# --proxy-headers: trust X-Forwarded-* from the platform's load balancer.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--workers", "2"]
