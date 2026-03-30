FROM python:3.13-slim

# Install promtool for TSDB backfill
ARG PROMETHEUS_VERSION=2.51.0
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -sSL "https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz" \
       | tar -xz --strip-components=1 -C /usr/local/bin \
           "prometheus-${PROMETHEUS_VERSION}.linux-amd64/promtool" \
    && apt-get remove -y curl && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src/ src/
ENV UV_CACHE_DIR=/tmp/.cache/uv
RUN chown -R nobody:nogroup /app
USER nobody
RUN uv sync --frozen --all-extras --no-dev

ENTRYPOINT ["uv", "run", "slo-generate"]
