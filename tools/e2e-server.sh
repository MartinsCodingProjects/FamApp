#!/usr/bin/env bash
# Backend for `make e2e` (Playwright): a fresh SQLite DB, migrated, admin UI on port 5174
# (reserve port, BUILDPLAN A6), dev mode (no Cloudflare Access). Started by e2e/playwright.config.ts.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
db_dir="$(mktemp -d)"
trap 'rm -rf "$db_dir"' EXIT
export FAMAPP_DEV=1
export DATABASE_URL="sqlite:///$db_dir/e2e.db"
export ADMIN_DEV_PORT="${E2E_PORT:-5174}"
export SETUP_TOKEN="e2e-setup-token-0123456789abcdef0123"

cd "$root/backend"
uv run --quiet python -c "from app.db.session import make_engine; from app.db.migrations import upgrade; upgrade(make_engine())"
exec uv run --quiet uvicorn app.main:create_app --factory --host 127.0.0.1 --port "$ADMIN_DEV_PORT"
