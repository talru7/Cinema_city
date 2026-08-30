FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm AS runtime
RUN useradd --create-home --uid 10001 cinema
WORKDIR /app
COPY --from=builder --chown=cinema:cinema /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" APP_ENV=production HOST=0.0.0.0 PORT=8080
USER cinema
EXPOSE 8080
CMD ["cinema-web"]
