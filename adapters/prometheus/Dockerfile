FROM python:3.13-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml .
RUN uv sync --no-dev --no-install-project

COPY tropek_prometheus/ tropek_prometheus/

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "tropek_prometheus.main:app", "--host", "0.0.0.0", "--port", "8080"]
