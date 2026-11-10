# Relay backend image: one image, three roles (selected by the command).
#   relay-api                 HTTP API (uvicorn)
#   relay-worker              outbox / Procrastinate worker (also runs periodic tasks)
#   alembic upgrade head      migrations (owner role; run once per release)
FROM ghcr.io/astral-sh/uv:0.12.18 AS uv

FROM python:3.14-slim AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev

FROM python:3.14-slim
# Patch OS packages and drop the image's pip/setuptools (and their vendored urllib3/msgpack):
# the runtime only uses the app's own virtualenv.
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*  && python -m pip uninstall -y pip setuptools wheel 2>/dev/null;     rm -rf /usr/local/lib/python3.14/site-packages/pip* /usr/local/lib/python3.14/site-packages/setuptools*            /usr/local/lib/python3.14/ensurepip
RUN useradd --system --uid 10001 --no-create-home relay
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/src /app/src
COPY alembic.ini ./
COPY migrations ./migrations
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    RELAY_API_HOST=0.0.0.0 \
    RELAY_API_PORT=8000
USER relay
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2).status == 200 else 1)"]
CMD ["relay-api"]
