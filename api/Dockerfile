FROM python:3.13-slim

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1

# --- Dependency layer (cached unless pyproject.toml changes) ---
COPY pyproject.toml README.md ./
RUN uv sync --no-dev --no-install-project

# --- Source layer ---
COPY tropek/ tropek/
COPY alembic/ alembic/
COPY alembic.ini ./
RUN uv sync --no-dev

EXPOSE 8080
CMD ["uv", "run", "uvicorn", "tropek.main:app", "--host", "0.0.0.0", "--port", "8080"]
