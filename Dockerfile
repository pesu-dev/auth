# syntax=docker/dockerfile:1

FROM python:3.14-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_COMPILE_BYTECODE=1

WORKDIR /pesu-auth

COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY app/ ./app/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev && \
    python -m compileall -q app/

FROM python:3.14-slim-bookworm

WORKDIR /pesu-auth

ARG GIT_SHA=unknown
LABEL org.opencontainers.image.revision=${GIT_SHA} \
      org.opencontainers.image.source="https://github.com/pesu-dev/auth"

# Create an unprivileged non-root user and group
RUN groupadd -g 10001 app && \
    useradd -u 10001 -g app --no-create-home --shell /usr/sbin/nologin app

# Copy precompiled dependencies and code; files remain owned by root and read-only for UID 10001
COPY --from=builder /pesu-auth/.venv /pesu-auth/.venv
COPY --from=builder /pesu-auth/app ./app

ENV PATH="/pesu-auth/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER 10001:10001

CMD ["python", "-m", "app.app"]
