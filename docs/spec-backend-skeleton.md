# Spec: backend skeleton (package 1.4)

Sources: README 2, 9, 10; `docs/decisions.md` sections 3 and 10; BUILDPLAN 1.4, A7.

## Processes

One image, two commands (`deploy/docker-compose.yml`):

| Process | Command | Role |
|---|---|---|
| `api` | `uvicorn app.main:create_app --factory` (port 8000) | app API, web build (later), admin UI on the admin host |
| `worker` | `python -m app.worker` | migrations on start, then the scheduler; exactly one instance |

Dev (`make dev`): `api` on 8000 and the same app on 5000 for the admin UI, plus the worker and the fakes.

## Configuration (`app/config.py`)

Pydantic settings from environment variables.

| Variable | Required outside dev | Notes |
|---|---|---|
| `DATABASE_URL` | yes | dev default `sqlite:///./dev.db` |
| `MASTER_KEY` | yes | base64 of exactly 32 random bytes (`openssl rand -base64 32`); AES-GCM key for secrets in the DB (later packages) |
| `SETUP_TOKEN` | yes | at least 32 characters (`openssl rand -hex 32`) |
| `CF_ACCESS_TEAM_DOMAIN` | yes | e.g. `<team>.cloudflareaccess.com` (no scheme) |
| `CF_ACCESS_AUD` | yes | audience tag of the Access application |
| `FAMAPP_DEV` | – | `1` = dev mode: defaults for everything above, admin JWT check off, `/docs` on. Never set in deploy files |
| `APP_HOST` | – | default `famapp.cowflex.com` |
| `ADMIN_HOST` | – | default `famapp-admin.cowflex.com` |
| `ADMIN_DEV_PORT` | – | default `5000` |
| `LOG_LEVEL` | – | default `INFO` |

Outside dev, a missing or malformed required value stops the process at start with an error naming the variable (never its value).

## Surfaces and host separation

The ASGI entry point dispatches each request to one of two FastAPI apps:

- **Admin surface** if the `Host` header (without port) equals `ADMIN_HOST`; in dev mode instead if the request came in on `ADMIN_DEV_PORT`.
- **App surface** for everything else, including direct IP access and container health checks. The app surface is public anyway; only the admin surface needs the strict match.

The app surface never serves admin routes and vice versa (404). Outside dev: no `/docs`, `/redoc`, `/openapi.json` on either surface.

### Admin: Cloudflare Access check

Every admin-surface request needs a valid `Cf-Access-Jwt-Assertion` header, otherwise **404** (indistinguishable from a missing page):

- RS256 signature against the team keys from `https://<CF_ACCESS_TEAM_DOMAIN>/cdn-cgi/access/certs` (JWKS),
- `aud` contains `CF_ACCESS_AUD`, `iss` is `https://<CF_ACCESS_TEAM_DOMAIN>`,
- `exp` / `nbf` checked against the time provider with 60 s leeway.

Keys are cached for 1 h; an unknown `kid` triggers a refetch at most once per 60 s. If the key endpoint is unreachable and no cached key fits, the request gets 404 (fail closed). With `FAMAPP_DEV=1` the check is off.

## Health and schema check

`GET /api/health` (app surface):

- **200** `{"status": "ok", "schema": "head" | "newer"}` when the DB revision is the code's head, or a revision the code does not know (= newer, decisions section 10),
- **503** `{"status": "starting", "schema": "behind" | "empty" | "unreachable"}` otherwise.

Checked on every call (cheap), so a lost DB shows up.

## Worker start

1. Take the named lock `migrations` (timeout 10 min).
2. Read the DB revision: unknown → log a warning and skip; otherwise `alembic upgrade head`.
3. Release the lock, start the scheduler (no jobs yet), run until SIGTERM/SIGINT, then shut down cleanly.

## Logging

One JSON object per line on stdout: `ts`, `level`, `logger`, `msg`, `request_id` (when inside a request), plus extra fields. One access line per request: method, **path without query string**, status, `duration_ms`. Never request or response bodies, never query strings (no todo content in logs). The request ID comes from a valid incoming `X-Request-ID` (8–64 chars `[A-Za-z0-9-]`) or is generated, and is returned as `X-Request-ID`.

## Strings

`app/i18n.py`: `t(key, params=None, **kwargs)` over `shared/strings/de.json`, behavior fixed by `shared/test-vectors/strings/`. The image contains `shared/strings/`, `branding.json` and `app/version.json`.

## Admin base template

`app/admin/templates/base.html`: `lang="de"`, title from `branding.json`, `tokens.generated.css`, vendored htmx (`app/admin/static/htmx.min.js`, pinned), no CDN. The admin index page renders it.

## Edge cases

- Host header with port (`famapp-admin.cowflex.com:443`) or upper case → normalized before the match.
- Admin request with a valid JWT for a different audience → 404.
- `alembic_version` missing (fresh DB) → health 503 `empty` until the worker migrated.
- Two workers starting at once (rolling deploy) → the second waits for the lock, then finds head and does nothing.
