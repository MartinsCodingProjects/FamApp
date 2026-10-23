# AGENTS.md – start here

You are working on a private household app for two people (Martin and his wife). **Core goal: notifications arrive reliably and on time, to the minute.** Everything else builds on that.

Language: code, identifiers, comments, docs, specs, commit messages, PRs and issues in **English**. User-facing text (app, web, notifications, admin UI) in **German**, all of it in `shared/strings/de.json`.

---

## 1. Read first, in this order

1. `docs/progress.md` – where the project stands, which work package is next
2. `BUILDPLAN.md` – Part A (rules, work locations A6, database A7) and your current run in Part B
3. `README.md` – architecture, behavior, data model
4. `docs/decisions.md` – what was decided and why (✅ = binding, 🟡 = proposal, valid until someone objects)
5. `docs/assumptions.md` – assumptions made by earlier agents
6. The spec for your package under `docs/spec-*.md`, if it exists

On contradictions: `docs/decisions.md` (✅) > `README.md` > `BUILDPLAN.md` > `docs/assumptions.md`. If you notice a contradiction, fix the lower-ranked document in the same PR.

---

## 2. How to work

1. Take the next open package from `docs/progress.md`. **Open GitHub issues labeled `bug` take priority.**
2. Larger package without a spec? Write the spec first under `docs/` (short, concrete, including edge cases). No approval needed.
3. Branch `pkg/<id>-<short-name>`, e.g. `pkg/1.7-migrations`.
4. The package's acceptance criterion becomes an **automated test**. Test first, then implementation, where it makes sense.
5. Check locally: `make lint && make test`.
6. For Android parts: push, trigger CI, read the result with `gh run watch` / `gh run view --log-failed`.
7. Open a PR (template below), enable auto-merge. Merging into `main` happens when the required check `ci-gate` is green.
8. Update `docs/progress.md` (in the same PR). Then go straight to the next package.

At the end of a run: write the checkpoint file `docs/checkpoint-cN.md`, ask Martin to move `release` (issue + note in `docs/progress.md`) and stop (see BUILDPLAN Part B). Never move `release` yourself.

### PR template

```
## Package
<ID and title>

## What
<short>

## Tests
<which tests cover the acceptance criterion>

## Assumptions
<new entries in docs/assumptions.md, or "none">

## For the next checkpoint
<what Martin should check on a real device / in production, or "nothing">
```

---

## 3. When to stop and ask

**Only** in these cases (open an issue labeled `question`, note it in progress, continue with independent packages if possible):

1. Access, an account or a secret is missing that only Martin can create.
2. User-visible behavior is not covered by the README or decisions.
3. Something irreversible is about to happen: package name, signing key, a migration that deletes data, changes to `release`.
4. CI stays red after several serious attempts, or an external service is down.
5. GitHub Actions free minutes are used up (only relevant once the repo is private again after C3) → do not stop; continue with home-server packages (backend, `engine-core`, web) and batch Android changes.

Decide everything else yourself and record it in `docs/assumptions.md` (date, package, assumption, reason).

---

## 4. Environment

Details: `BUILDPLAN.md` A6 and A7. Summary:

- **Home server (here):** code-server container, < 7 GB RAM, **no Docker, no KVM, no root**, localhost is free, internet access to package registries.
  - Python via `uv`, Node via `fnm`, JDK via SDKMAN (only for `engine-core`). **No Android SDK here.**
  - Database: SQLite (`DATABASE_URL` unset → `sqlite:///./dev.db`).
  - Gradle: `org.gradle.jvmargs=-Xmx1536m`, daemon with a short idle timeout.
- **GitHub Actions:** APK build, `engine-android`, Robolectric, emulator E2E, MariaDB tests, Docker image. The repo is **public until C3** (free minutes): emulator suite on every PR touching `app/`. Only `ci-gate` is a required check; use job-level conditions, not workflow-level `paths:` filters, for required jobs.
- **Ports Martin can see in his browser:** 8000 (API + web build), 5000 (admin UI), 5173 (Expo web dev). Reserve: 3000, 4173, 5174. Internal only: e.g. 9101 fake FCM, 9102 fake Google.

### Commands (Makefile, once created)

| Command | Purpose |
|---|---|
| `make setup` | install tools in user space |
| `make dev` | start backend, worker, admin, fakes locally |
| `make test` | all locally possible tests (Python, JS, `engine-core`, test vectors) |
| `make lint` | Ruff, ESLint, ktlint, string-key and token checks |
| `make tokens` | regenerate token files from `shared/design/tokens.json` |
| `make e2e` | Playwright against a local instance |
| `make apk` | CI only |

---

## 5. Fixed rules

### Architecture
- **The server is the source of truth.** The Android engine only keeps a mirror.
- **FCM never carries content**, only `{"t":"sync"}`. **High priority only when the device is expected to display something now**; everything else normal priority with a `collapse_key`.
- **The engine owns the local DB exclusively.** The UI (TypeScript) accesses data only through `data/repo.ts`, never a DB directly.
- **Native Android config only via Expo config plugins** (`app/plugins/`). Never edit the generated `android/` folder.
- **Room:** mirror tables may be dropped and re-synced on schema changes; outbox, auth and sync state only via real migrations.
- **Sync protocol changes keep the previous protocol version working** (protocol version header, minimum app version; clients ignore unknown fields).
- **Logic belongs in `engine-core`** (pure Kotlin). `engine-android` only connects to Android APIs.
- **Single-alarm planner:** always exactly one exact alarm for the next time.
- **Only the server creates recurring instances.**
- **Time only through the time provider** (backend and engine). Never call `datetime.now()`, `System.currentTimeMillis()` or similar directly in logic code.
- Rules that exist in several languages (levels, quiet hours, nag times, rotation, RRULE, conflicts) are tested against **`shared/test-vectors/`**. Add new edge cases there, not just in one language.

### Database (A7)
- Only portable SQLAlchemy types, custom UTC `DateTime` type.
- `rev` only via `next_rev()`, locks only via `db/locks.py`.
- Raw SQL only in `backend/app/db/dialects/`.
- Alembic with `render_as_batch=True`. Migrations are **additive** (expand/contract) so the previous image keeps running; the worker applies them on start. Never destructive migrations without asking.
- Concurrency tests marked `@pytest.mark.mariadb`.

### Security
- **Never request, create or commit production secrets.** No real keys in tests or fixtures.
- `google-services.json` may be committed; service account keys never.
- No todo content in logs.
- **The repo is public until C3:** no personal data, todo contents, real names beyond the docs, IPs or tokens in code, fixtures, issues, PRs or CI logs.
- The APK signing key exists only in the GitHub Environment `release`. Never change which branches or reviewers that environment allows.
- Admin host: requests without a valid Cloudflare Access JWT are rejected (only `FAMAPP_DEV=1` disables the check; never set it in deploy files).
- No public `/docs` or `/openapi.json` endpoints in production.

### Immutable
- Technical codename `famapp` and Android package name `com.cowflex.famapp` are never changed.
- Channel IDs only change by versioning (`urgent_v2`), never by renaming.
- The `release` branch is only touched by Martin (or by an agent on his explicit instruction).

### Design tokens (README 8.2)
- **Single source: `shared/design/tokens.json`.** Never edit `*.generated.*` files; run `make tokens`.
- Use **semantic** tokens only (`color.bg.surface`, `color.state.urgent`), never base tokens or hard-coded colors, spacing, radii or font sizes. Applies to the app, the admin UI CSS and Android resources alike.
- Need a value that does not exist? Add a semantic token in `tokens.json`; do not inline it.
- Only base components in `app/components/` combine tokens into styles. Screens compose base components.

### UI strings (README 8.4)
- **Single source: `shared/strings/de.json`.** Applies to app, web, engine notifications, server notifications and admin UI.
- Code uses keys via `t(key, params)` only. No German string literals in code (lint enforces it).
- Keys by area (`todo.action.done`). Counts use plural forms, never string concatenation.
- Server-generated notifications send a key plus parameters, not text.
- New key → add it to `de.json` in the same PR. Removed usage → remove the key.

### Branding
- Display name only from `branding.json`.

---

## 6. Users and terms

| Term | Meaning |
|---|---|
| User | one of the two app accounts (Martin, his wife). Martin is admin. |
| Person | someone a todo is for (Martin, his wife, their child, household). No login. |
| Assignee | a user or both (`NULL`) |
| Level | `long_term` / `mid_term` / `urgent` / `overdue`, **computed**, never stored |
| Kind | `scheduled` / `horizon` / `immediate` / `someday` |
| Nagging | repeated notification until "done" |
| Snooze / Postpone | pause nagging for a while / set a new target date |
| Quiet hours | per user, default 22:00–06:00 |
| Display key | stable ID of a display, e.g. `nag:<todo-id>` (README 3.5) |
| Checkpoint (C0–C3) | point where Martin has to do something himself |
| Run (1–4) | a sequence of work packages agents complete without Martin |
