# One image for api and worker (deploy/docker-compose.yml). Build context: repo root.
#   docker build -f backend/Dockerfile -t famapp-backend .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv

WORKDIR /srv/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project && rm /usr/local/bin/uv

# Same layout as the repo, so app/paths.py finds shared files next to backend/.
COPY shared/strings /srv/shared/strings
COPY branding.json /srv/branding.json
COPY app/version.json /srv/app/version.json
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/app ./app

RUN useradd --system --uid 10001 --no-create-home famapp
USER 10001

EXPOSE 8000
# api; the worker overrides the command with `python -m app.worker`.
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
