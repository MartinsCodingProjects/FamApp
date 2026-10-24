# Spec: setup wizard and admin login (package 1.9)

Sources: README 9, 10 (setup wizard); `docs/decisions.md` section 3 (setup wizard and secrets, admin UI). Everything here runs on the admin host, behind the Cloudflare Access check (1.4.7).

## Flow

```
/setup            → token form (only before the lock)
/setup/admin      → admin account: name, password (twice)
/setup/totp       → TOTP enrolment: QR code + secret, confirm with a 6-digit code
/setup/firebase   → Firebase service account: upload the JSON file
/setup/user       → second account: name; household time zone; default quiet hours
/setup/finish     → summary, "lock wizard" → redirect to /login
/login, /logout   → admin login with name + password + TOTP code
/                 → admin home (needs an admin session; before the lock it redirects to /setup)
```

The current step follows from the DB, so a reload or a crash mid-way resumes at the right step:

1. no admin user → `admin`
2. admin without confirmed TOTP → `totp`
3. no secret `firebase.service_account` → `firebase`
4. no second user → `user`
5. otherwise → `finish`

Requesting a later step than the current one redirects to the current one. Earlier steps cannot be redone inside the wizard (changes later via the admin UI, 2.11).

## Access

- **Before the lock:** every `/setup*` request needs the setup cookie. `POST /setup` with the right `SETUP_TOKEN` sets it. The token comparison is constant-time (`hmac.compare_digest`).
- Wrong tokens are rate limited: 5 attempts per 15 min per client IP, then 429 for the rest of the window. Each failure is written to the audit log (`setup.token_failed`, IP only).
- Cookie `famapp_setup` = HMAC-SHA256(`MASTER_KEY`, `"setup-session:" + SETUP_TOKEN`), `HttpOnly`, `SameSite=Strict`, `Path=/setup`, `Secure` outside dev. Valid until the lock; changing `SETUP_TOKEN` invalidates it.
- **After the lock** every `/setup*` path answers 404, with or without cookie.
- Every POST carries a CSRF token (hidden field): wizard = HMAC(`MASTER_KEY`, `"setup-csrf:" + cookie`), admin pages = the session's CSRF token. A missing or wrong token → 403.

## Steps

**Admin account.** Name 1–100 chars, password at least 12 chars, both password fields equal. Stored as Argon2id hash (argon2-cffi defaults), role `admin`, a `user_settings` row with defaults.

**TOTP.** A random base32 secret (160 bit) stored encrypted as secret `user.<id>.totp`. The page shows a QR code (SVG, rendered server-side, no external service) of `otpauth://totp/famapp:<name>?secret=…&issuer=<display name>` and the secret as text. A correct code (30 s steps, ±1 step) confirms it (`users.totp_confirmed_at`).

**Firebase.** File upload (`.json`, max 64 KB). Valid when it is JSON with `type == "service_account"`, non-empty `project_id`, `client_email`, and a `private_key` starting with `-----BEGIN PRIVATE KEY-----`. Stored encrypted as secret `firebase.service_account`; the page then shows only the `project_id` and `client_email`. The FCM dry run follows in 2.8.

**Second account.** Name (1–100 chars, different from the admin's), the **household time zone** (IANA name, select, default `Europe/Berlin`, applied to both users), **default quiet hours** start and end (default 22:00–06:00, applied to every weekday of both users). No password: the second user sets it later (2.11 / Run 4).

**Finish.** Shows what was set up (names, time zone, quiet hours, Firebase project ID). "Lock" stores `setup.completed_at` in `system_settings`, writes `setup.completed` to the audit log, and redirects to `/login`.

## Admin login

- Form: name, password, 6-digit code. Only users with role `admin` and a confirmed TOTP can log in. One generic error for every failure (no hint which field was wrong).
- A TOTP code is accepted at most once (the last used time step is stored, `users.totp_last_step`).
- Lockout: 5 failed logins for a user → that user is locked for 15 min (`users.locked_until`); failures and lockouts go to the audit log. Per-IP rate limits follow in 1.10.7.
- Session: random 32-byte token in cookie `famapp_admin` (`HttpOnly`, `SameSite=Strict`, `Secure` outside dev); only its SHA-256 is stored (`admin_sessions`). Expires after 12 h without use or 7 days in total. Logout deletes it.
- Audit log: `admin.login`, `admin.login_failed`, `admin.locked`, `admin.logout`.

## Data (migration 0003)

- `system_settings`: `key` (PK), `value` JSON, `updated_at` — server-wide settings (`setup.completed_at`, later `sync.min_app_version` etc.).
- `admin_sessions`: `id`, `user_id`, `token_hash` (unique), `csrf_token`, `created_at`, `last_seen_at`, `expires_at`.
- `users`: `totp_confirmed_at`, `totp_last_step`, `failed_logins`, `locked_until`.

## Texts

All in `de.json` under `admin.setup.*`, `admin.login.*`, `admin.error.*`. Wording is the agent's proposal (`docs/assumptions.md`), reviewed by Martin at C1 when he runs the wizard.

## Tests

- Python flow test (TestClient): token → admin → TOTP → Firebase → user → lock → login → logout, plus each guard (wrong token, rate limit, 404 after lock, step order, CSRF, invalid inputs, lockout, TOTP reuse).
- `make e2e`: Playwright runs the same flow in a browser against a dev server with a fresh SQLite DB (CI job `e2e`; the home server cannot run browsers, BUILDPLAN A6).
