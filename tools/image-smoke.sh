#!/usr/bin/env bash
# Image smoke test (BUILDPLAN 1.4.11): build the backend image, start deploy/docker-compose.yml
# with a MariaDB, and check that /api/health turns 200 (the worker migrated), the API docs are
# off and the admin host needs Cloudflare Access. Needs Docker (CI, notebook).
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
compose=(docker compose -p famapp-smoke -f deploy/docker-compose.yml -f tools/ci/docker-compose.smoke.yml)
export DATABASE_URL="mysql+pymysql://famapp:famapp@mariadb:3306/famapp"
MASTER_KEY="$(head -c 32 /dev/urandom | base64)"
export MASTER_KEY
export SETUP_TOKEN="smoke-test-setup-token-0123456789abcdef"
export CF_ACCESS_TEAM_DOMAIN="famapp-smoke.cloudflareaccess.com"
export CF_ACCESS_AUD="smoke-aud"

cleanup() {
  status=$?
  if [ "$status" -ne 0 ]; then "${compose[@]}" logs --no-color || true; fi
  "${compose[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  exit "$status"
}
trap cleanup EXIT

"${compose[@]}" build
uid="$("${compose[@]}" run --rm --no-deps api id -u | tr -d "\r")"
[ "$uid" != "0" ] || { echo "image runs as root"; exit 1; }

"${compose[@]}" up -d --wait --wait-timeout 180
curl -sSf http://127.0.0.1:8000/api/health | tee /dev/stderr | grep -q '"status":"ok"'
echo
for path in /docs /openapi.json; do
  code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:8000$path")"
  [ "$code" = 404 ] || { echo "$path returned $code, expected 404"; exit 1; }
done
code="$(curl -s -o /dev/null -w '%{http_code}' -H 'Host: famapp-admin.cowflex.com' http://127.0.0.1:8000/)"
[ "$code" = 404 ] || { echo "admin host without Access JWT returned $code, expected 404"; exit 1; }
echo "image smoke test passed"
