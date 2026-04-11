FROM python:3.13-slim

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1

COPY pyproject.toml .
RUN uv sync --no-dev --no-install-project

COPY tropek_mock/ tropek_mock/
RUN uv sync --no-dev

EXPOSE 8082
CMD ["uv", "run", "uvicorn", "tropek_mock.main:app", "--host", "0.0.0.0", "--port", "8082"]
