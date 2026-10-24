# AGENTS.md – start here

You are working on a private household app for two people (Martin and his wife). **Core goal: notifications arrive reliably and on time, to the minute.** Everything else builds on that.

Language: code, identifiers, comments, docs, specs, commit messages, PRs and issues in **English**. User-facing text (app, web, notifications, admin UI) in **German**, all of it in `shared/strings/de.json`.

---

## 1. Read first, in this order

1. `docs/last-session.md` – where the previous session left off: what was finished, what is half done, next sub-task, open blockers, what needs Martin. (`docs/session-history.md` is the archive; you do not need to read it.)
2. `BUILDPLAN.md` – Part A (rules, work locations A6, database A7) and your current run in Part B. **The checkboxes in Part B are the project status** (legend and rules: Part B, "How progress is tracked")
3. `README.md` – architecture, behavior, data model
4. `docs/decisions.md` – what was decided and why (✅ = binding, 🟡 = proposal, valid until someone objects)
5. `docs/assumptions.md` – assumptions made by earlier agents
6. The spec for your package under `docs/spec-*.md`, if it exists

On contradictions:

- **Behavior** (what the app, server and engine do): `docs/decisions.md` ✅ > `README.md` > `docs/decisions.md` 🟡 > `BUILDPLAN.md` > `docs/assumptions.md`.
- **Process, sequence, status, environment** (how and in which order we build, CI, checkpoints, tracking): `BUILDPLAN.md` > `AGENTS.md` > everything else.

If you notice a contradiction, fix the lower-ranked document in the same PR.

---

## 2. How to work

1. Take the **Next** item from `docs/last-session.md` (or the first unticked sub-task in BUILDPLAN Part B, if it disagrees with the checkboxes). Check open draft PRs first: a 🚧 claim lives on its branch and is only visible through the draft PR. **Open GitHub issues labeled `bug` take priority.**
2. Larger package without a spec? Write the spec first under `docs/` (short, concrete, including edge cases). No approval needed.
3. Branch `pkg/<id>-<short-name>`, e.g. `pkg/1.7-migrations`. Mark the sub-task 🚧 with the branch name in the first commit and open the PR as a draft right away.
4. The package's acceptance criterion becomes an **automated test**. Test first, then implementation, where it makes sense.
5. Check locally: `make lint && make test`.
6. For Android parts: push, trigger CI, read the result with `gh run watch` / `gh run view --log-failed`.
7. Mark the PR ready for review (template below), enable auto-merge. Merging into `main` happens when the required check `ci-gate` is green. **After C3** (private repo on GitHub Free, no rulesets): wait with `gh pr checks --watch` and merge only when `ci-gate` is green.
8. In the same PR: tick the finished sub-tasks in BUILDPLAN Part B, tick the package line with the PR number once all its sub-tasks are done. Then go straight to the next sub-task.

At the end of a run, follow that run's lines in BUILDPLAN Part B: after Runs 2 and 4 write the checkpoint file `docs/checkpoint-cN.md` (it is the run's last package), bump `app/version.json` (`versionCode` + 1); after Runs 2, 3 and 4 ask Martin to move `release` (issue + note under **Needs Martin** in `docs/last-session.md`). **Every run ends the session**: stop after the run's end steps and do not start the next run; Martin starts it with a new session (`/next`). Never move `release` yourself.

### Ending a session

Whenever you stop and wait for a new prompt (run done, blocked, context running out, task finished):

1. Overwrite `docs/last-session.md` with the fields below. Refer to sub-task IDs; do not repeat the checkbox status in prose.
2. Run `tools/session-end.sh`. It copies the file to the top of `docs/session-history.md` and skips it if it is already there.
3. Commit both files in the session's last PR before it merges. If there is none, or it already merged (e.g. you stopped blocked), open a docs-only PR `session/<date>` with auto-merge.

```
## Session <YYYY-MM-DD HH:MM> – <short title>        ← unique; the script keys on this line

**Run / section:** <e.g. Run 1>
**Finished:** <sub-task / package IDs, with PR numbers>
**In progress:** <IDs marked 🚧 and how far they got, or "–">
**Stopped because:** <run done / blocked / context limit / waiting for Martin>
**Next:** <the next sub-task ID for the next agent; next step for Martin if any>

### Summary
<3–6 bullets: what was done, notable choices (link assumptions.md entries)>

### Structural decisions
<one line each with the assumptions.md entry; "none">

### Needs Martin (review / decision)
<optional: what to review, which decision, issue links; "none">

### Went wrong / watch out
<optional: failures, flaky tests, workarounds, things the next agent must know; "none">

### Open blockers
<table: Since | Item | Blocked by | Issue — carry over every unresolved row from the previous file>
```

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

Work on your own; nobody answers questions mid-session. In every case below: open an issue labeled `question` (options + your recommendation), mark the sub-task ⏸ in BUILDPLAN, add it under **Open blockers** in `docs/last-session.md`.

**Stop and wait** (leave the work green and committed, end the session) when Martin must decide:

1. User-visible behavior is not covered by the README or decisions.
2. Something irreversible is about to happen: package name, signing key, channel IDs, a migration that deletes data, changes to `release`, repo settings.
3. Going against a ✅ decision or the README.
4. A structural decision that is hard to undo once later packages depend on it and the docs give no direction (e.g. replacing a planned library or service, changing the sync protocol contract, a new external service, cost or privacy impact, security/auth).

**Park and continue** with independent sub-tasks (stop only when none are left):

5. Access, an account or a secret is missing that only Martin can create.
6. CI stays red after several serious attempts, or an external service is down.

Also stop at the end of a run (section 2) and before context runs out (at a sub-task boundary).

Not a reason to stop: GitHub Actions free minutes used up (only possible once the repo is private again after C3). Continue with home-server packages (backend, `engine-core`, web), batch Android changes and note it under **Open blockers**.

Decide everything else yourself (docs first, then the simplest option that is easy to change later) and record it in `docs/assumptions.md` (date, package, assumption, reason). Mark **structural** decisions (anything later packages build on: layout beyond README 12, new dependencies or tools, data model, API or sync payload shape, test or CI infrastructure, cross-language rules) with **[structural]** and also list them in the PR description and under **Structural decisions** in `docs/last-session.md`, so Martin sees them.

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
- Rules that exist in several languages (levels, quiet hours, modes, nag times, planner, rotation, RRULE, conflicts, strings) are tested against **`shared/test-vectors/`**. Add new edge cases there, not just in one language.

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
- The APK signing key exists only in the GitHub Environment `release` (after C3: a repo secret read only by the release workflow). Never change which branches or reviewers that environment allows, and never use the signing secrets in any other workflow.
- Admin host: requests without a valid Cloudflare Access JWT are rejected (only `FAMAPP_DEV=1` disables the check; never set it in deploy files).
- No public `/docs` or `/openapi.json` endpoints in production.

### Immutable
- Technical codename `famapp` and Android package name `com.cowflex.famapp` are never changed.
- Channel IDs only change by versioning (`urgent_v2`), never by renaming.
- The `release` branch is only touched by Martin (or by an agent on his explicit instruction).

### Design tokens (README 8.2)
- **Single source: `shared/design/tokens.json`.** Never edit generated files (`*.generated.*`, Android `*_generated.xml`); run `make tokens`.
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
| Level | `long_term` / `mid_term` / `due_soon` / `overdue`, **computed**, never stored. "Urgent" only means the explicit kind `immediate` |
| Kind | `scheduled` / `horizon` / `immediate` / `someday` |
| Nagging | repeated notification until "done": explicit urgent every 15 min, overdue as one combined notification at the overdue slots (default 4 per day). `due_soon` never nags |
| Nag window | from the day's first summary until quiet hours start; nagging only happens inside it |
| Claim ("Mach ich") | recipient confirms an explicit urgent todo; nagging slows to hourly, the sender is told |
| Snooze / Postpone | pause nagging (30 min / 2 Std. / Bis morgen; per todo, or for the combined overdue notification) / set a new target date or `due_at` |
| Quiet hours | per user and weekday, default 22:00–06:00 |
| Mode | per user: `remind` (full) / `essentials` (no nagging, everything once) / `dnd` (nothing); manual with an end, or from the weekly mode schedule |
| Activity view | in-app list of todo events (created, done, snoozed …), table `activity_events`; not a notification list |
| Display key | stable ID of a display, e.g. `nag:<todo-id>` (README 3.5) |
| Checkpoint (C0–C3) | point where Martin has to do something himself |
| Run (1–4) | a sequence of work packages agents complete without Martin |
