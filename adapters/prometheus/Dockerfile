FROM python:3.13-slim

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1

COPY pyproject.toml README.md ./
RUN uv sync --no-dev --no-install-project

COPY tropek_prometheus/ tropek_prometheus/
RUN uv sync --no-dev

EXPOSE 8080
CMD ["uv", "run", "uvicorn", "tropek_prometheus.main:app", "--host", "0.0.0.0", "--port", "8080"]
