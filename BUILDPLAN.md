# FamApp build plan

The plan is organized for **autonomous work by AI agents**. Martin only steps in at a few checkpoints, where something has to come from him: accounts and access, real phones, production secrets, acceptance.

```
👤 C0 prep ─► 🤖 Run 1 ─► 🤖 Run 2 ─► 👤 C1 first deploy ─► 🤖 Run 3 ─► 👤 C2 daily-use test ─► 🤖 Run 4 ─► 👤 C3 wrap-up
  (3–4 h)      backend      engine        (2–3 h)               todos,       (1–2 h, runs in          calendar,     (2–3 h)
               core         + push                              series       parallel with Run 4)     web, admin
```

👤 = Martin · 🤖 = agent · Afterwards: bug loop via GitHub issues.

---

## Part A: Rules for autonomous work

### A1. What lets agents make progress without Martin

1. **Everything testable locally, without real services.** The dev environment needs neither Firebase, Google nor Cloudflare:
   - **Fake FCM:** accepts wake-ups and records them (tests check "was it woken?")
   - **Fake Google Calendar:** serves events from fixture files, including `syncToken` and `410 Gone`
   - **Controllable clock:** backend and engine get the time only through a time provider. Tests can set "now" and fast-forward (required for quiet hours, nag intervals, levels, DST).
2. **One command per task** (`Makefile`): `make setup`, `make dev`, `make test`, `make lint`, `make tokens`, `make e2e`, `make apk`. Agents and CI use the same commands.
3. **Android tested automatically in an emulator.** CI starts an emulator and checks, among other things, Doze (`adb shell dumpsys deviceidle force-idle`), reboot, time and time zone changes, network off, app process killed, notification actions. CI covers most of the test matrix this way. Only what needs real hardware is left for Martin.
4. **Shared test vectors** in `shared/test-vectors/` (levels, quiet hours, modes, nag times, rotation, RRULE, conflicts). Python, Kotlin and TypeScript test against the same files.
5. **Spec before code.** Every larger package starts with a short spec under `docs/`. Agents write it themselves based on the README and `docs/decisions.md`. No approval needed.
6. **`AGENTS.md` in the repo root** (`CLAUDE.md` points to it): project goal, commands, conventions, definition of done, stop rules, where things live. Every agent reads it first.

### A2. Definition of done per work package

- CI green (tests, lint, audits, APK build, emulator tests where relevant)
- The package's acceptance criterion exists as an **automated test**
- Spec and docs up to date; new assumptions in `docs/assumptions.md`
- Pull request with a **"For the next checkpoint"** section: what Martin should check on a real device or in production
- `docs/progress.md` updated (package checked off, next package)

### A3. When an agent stops and asks

An agent stops **only** if:

1. access, an account or a secret is missing that only Martin can create,
2. a decision is needed that changes user-visible behavior and is not covered by the README or decisions,
3. something irreversible is about to happen (package name, a migration that deletes data, signing key),
4. CI stays red after several serious attempts, or an external service is down.

Everything else the agent decides itself and records in `docs/assumptions.md`. Martin can review the assumptions at the next checkpoint and have them corrected.

### A4. Branches, deployment, secrets

- Agents work on feature branches, one PR per work package. **Auto-merge into `main` when CI is green.** (Martin can merge every PR himself instead, at the cost of autonomy.)
- **Coolify deploys only the `release` branch.** **Only Martin moves it** to the current `main` at checkpoints. At the end of a run the agent asks him (issue + note in `docs/progress.md`). Nothing reaches production unchecked.
- **Agents never get production secrets.** The APK signing key lives only in the GitHub Environment `release` (restricted to the `release` branch, Martin as required reviewer); PR and `main` builds are debug-signed. Optionally a separate dev Firebase project.
- **One required check `ci-gate`:** an always-running job that depends on all other jobs and accepts skipped ones. Branch protection requires only this job, so path filters never block a merge.
- Progress is visible in the repo: `docs/progress.md` plus PR history.

### A5. Additions to the repository layout (README section 12)

```
├─ AGENTS.md                rules for agents (CLAUDE.md points here)
├─ Makefile                 setup, dev, test, lint, e2e, apk
├─ docker-compose.dev.yml   local environment for machines with Docker
├─ dev/
│  ├─ fake-fcm/
│  └─ fake-gcal/            with fixtures
├─ docs/
│  ├─ progress.md           status of the work packages
│  ├─ assumptions.md        decisions made by agents
│  ├─ decisions.md          decision log with rationale
│  └─ spec-*.md             specifications
└─ .github/
   ├─ workflows/            CI incl. emulator tests, APK build
   └─ ISSUE_TEMPLATE/       bug report for the bug loop
```

### A6. Where work happens: home server, CI, notebook

Fixed constraints (will not change): home server VM with < 7 GB RAM → container → code-server → Cloudflare Tunnel. Inside the container: localhost freely usable, no Docker access, no KVM, no root, internet access to package registries. From outside (Martin's browser) only the configured `DEV_PORTS` are reachable.

Work is split across three levels:

| Level | Where | What runs there | Feedback |
|---|---|---|---|
| **1. Home server** | agents in the code-server container | backend, worker, admin UI, fakes, SQLite (see A7), all Python tests, JS unit tests, `engine-core` tests (pure Kotlin), test vectors in all three languages, Expo web dev server | seconds |
| **2. GitHub Actions** | hosted Linux runners | build Docker image and smoke test, build and sign APK, Robolectric, **emulator E2E** (KVM is available on the standard runners), Playwright E2E, MariaDB tests, audits | minutes; agent pushes and reads results via `gh run watch` |
| **3. Notebook** | only when needed, by Martin | debug the emulator interactively if CI shows something inexplicable; development build with live reload **in the emulator only** (no development builds on the phones); optionally a self-hosted runner | – |

The phones are reserved for the checkpoints.

**Architectural consequence: split the engine in two.**

- `engine-core`: pure Kotlin without Android dependencies. Planner, levels, quiet hours, nag times, conflict rules, sync protocol (against an HTTP interface), test vectors. Builds and tests on the home server with little RAM.
- `engine-android`: thin layer for Room, AlarmManager, WorkManager, NotificationManager, FCM, receivers, JS bridge. Built and tested only in CI.

Most engine logic is therefore developed in the fast local loop; only the Android glue needs the slower CI loop.

**Home server setup (done by agent package 1.3, without root):**

- Database: an SQLite file in the working directory (not committed), nothing to install.
- Python via `uv`, Node via `fnm`, JDK via SDKMAN (only for `engine-core`).
- Gradle with `org.gradle.jvmargs=-Xmx1536m`; daemon stops after 10 min idle.
- No Android SDK on the home server.

**Ports:** internally all ports are free. The `DEV_PORTS` are only needed so **Martin** can look at things in the browser:

| Port | Service | Visible to Martin |
|---|---|---|
| 8000 | API + built web app | yes |
| 5000 | admin UI (on its own port in dev instead of its own subdomain) | yes |
| 5173 | Expo web dev server with live reload | yes |
| 3000, 4173, 5174 | reserve | if needed |
| 9101, 9102 | fake FCM, fake Google (internal only) | no |

**CI minutes:** the repo is **public during development** (decided 2026-10-23), so standard runners are free and the emulator suite runs on every PR touching `app/`. **It is made private again at C3.** No secrets, personal data or todo contents in the repo, issues or logs. After going private: 2,000 Actions minutes per month on GitHub Free, 3,000 on Pro; an emulator run costs 15–25 minutes, so the rules below apply again.

**No spending (set up in C0):**

- Do not add a payment method to the GitHub account. Without one nothing can be billed; once the free minutes are used up, runs no longer start until the next month.
- If a payment method is on file anyway (e.g. for Copilot or Pro): under *Billing → Budgets and alerts*, create a budget for **Actions** of $0 with **"Stop usage when budget limit is reached"**.
- Enable notifications at 75/90/100 % of the included minutes.
- When minutes run out, agents keep working on the home server (backend, `engine-core`, web) and batch Android changes until CI runs again. This is noted in `docs/progress.md`.

To make the minutes last (once the repo is private again):

- Emulator E2E only when something under `app/` changed, and batched (agents collect several changes before pushing).
- Full emulator suite nightly or before moving `release`.
- If minutes get tight: make the repo public (no secrets in the repo; standard runners are free for public repos) or register the notebook as a self-hosted runner (also free; only runs while the notebook is on).

### A7. Database: SQLite in development, MariaDB in production

The database is selected via `DATABASE_URL`:

- **Home server and local tests:** `sqlite:///./dev.db` (default when unset). Tests each use a fresh SQLite database.
- **CI:** an additional job runs the full backend test suite against **MariaDB** (service container). Costs a few minutes, only on changes under `backend/`.
- **Coolify (production):** `mysql+pymysql://…` pointing at the MariaDB resource. The first run against MariaDB on the server happens at C1. By then CI has already checked every migration and test against MariaDB.

So that both databases really behave the same, these rules apply (also in `AGENTS.md`):

| Topic | Difference | Solution |
|---|---|---|
| `rev` numbers | SQLite has no `SEQUENCE` | Counter table `rev_counter` behind a function `next_rev()` with one implementation per database (MariaDB: `LAST_INSERT_ID(value+1)`, atomic; SQLite: `UPDATE … RETURNING`, single writer) |
| Locks (worker jobs, pairing code) | SQLite has no `SELECT … FOR UPDATE` or `GET_LOCK` | Module `db/locks.py` with one implementation per database; for SQLite the file lock is enough because only one process writes |
| Data types | SQLite barely checks lengths and types | Only portable SQLAlchemy types (`Uuid`, `JSON`, a custom UTC `DateTime` type), length validation in Pydantic |
| Time zones | SQLite stores text | One type for all timestamps: always UTC, made timezone-aware on read |
| Migrations | SQLite has limited `ALTER` | Alembic with `render_as_batch=True`; every migration runs up and down on both databases in CI. Production: the worker migrates on start under a DB lock; migrations are **additive** (expand/contract) so the previous image keeps working |
| Case and sorting | different collations | Comparisons that depend on it are explicit in code; collation `utf8mb4_unicode_ci` set in MariaDB |
| Raw SQL | dialects differ | Only through SQLAlchemy; raw SQL exclusively in `backend/app/db/dialects/` (checked in CI) |
| Concurrency | SQLite serializes all writes | Tests for concurrent writes are marked `@pytest.mark.mariadb` and run only in the MariaDB CI job |

If something shows up only on MariaDB, add a test case so CI catches it in the future.

---

## Part B: Sequence

### 👤 C0: Preparation (once, about 3–4 h)

Everything that needs accounts, access or clicks in third-party UIs is bundled here. After this, Runs 1 to 4 can proceed without further account work.

| # | Task | Result for the agents |
|---|---|---|
| 1 | Create GitHub repo, **make it public** (until C3), grant agent access, enable auto-merge and branch protection for `main` (required check: `ci-gate`); protect `release` (only Martin may push) | repo access |
| 2 | Decide a display-name placeholder and subdomains (e.g. `famapp.cowflex.com`, `famapp-admin.cowflex.com`) | values for `branding.json` and docs |
| 3 | Create the **APK signing key** (one file, keep it safe!, back it up twice) and add it as a secret of the GitHub Environment `release` (deployment branch: `release` only, required reviewer: Martin). Updates can only be installed if they are signed with the same key. | signed APKs from CI |
| 4 | Create the **Firebase project** (package name `com.cowflex.famapp`), put `google-services.json` in the repo (not a secret), keep the service account key **locally with Martin** (it goes into the wizard at C1) | app can integrate FCM |
| 5 | Optional: a second **dev Firebase project**, key as GitHub secret | agents can test real FCM delivery in the emulator |
| 6 | **Google Cloud:** enable the Calendar API, OAuth consent screen "External", status "In production", scope `calendar.readonly`, OAuth client (web) with redirect `https://<admin-subdomain>/setup/google/callback`. Keep client ID/secret locally (they go into the admin UI at C3) | calendar integration prepared for Run 4 |
| 7 | **Cloudflare:** DNS records for both subdomains (proxied), WAF skip rule for the app subdomain, Cloudflare Access (GitHub SSO) for the admin subdomain; note the team domain and the application's **audience (AUD) tag** | reachability |
| 8 | **Coolify:** MariaDB resource (not public), Docker Compose resource from the repo, branch `release`, auto-deploy on push, environment variables `DATABASE_URL`, `MASTER_KEY`, `SETUP_TOKEN` (generate both randomly and store them safely), `CF_ACCESS_TEAM_DOMAIN`, `CF_ACCESS_AUD` (from item 7) | deployment |
| 9 | On both phones allow "Install unknown apps" for the browser/file manager | APK installation at C1 |
| 10 | **Secure GitHub costs:** no payment method, or Actions budget $0 with "Stop usage"; alerts at 75/90/100 % (see A6) | no costs |
| 11 | In the code-server container: log in the GitHub CLI (`gh`) so agents can trigger and read CI runs | CI feedback for agents |
| 12 | Cloudflare Tunnel: check that ports 8000, 5000 and 5173 are reachable for Martin | browser preview |

**Done when:** the agent confirms it has repo access and can see the CI secrets. The Coolify resource may still fail because there is no code yet.

---

### 🤖 Run 1: Foundation and backend core

| ID | Work package | Automated acceptance criterion |
|---|---|---|
| 1.1 | Repo scaffold: structure, `Makefile`, lint (Ruff, ESLint, ktlint), `branding.json`, issue template; keep `AGENTS.md` and README in sync with the actual layout. **Central strings and tokens:** `shared/strings/de.json` (first keys), `shared/design/tokens.json` (base + semantic, light/dark, initial neutral palette), `tools/` with token generator (JS, CSS, Android XML) and string checks (missing/unused keys, placeholders, German literals in code), string test vectors | `make lint` and `make tokens` run; checks fail on a deliberately broken key or stale generated file |
| 1.2 | CI: backend tests on SQLite **and** MariaDB (service container, see A7), lint, `pip-audit`, `npm audit`, APK build (debug-signed on PRs/`main`, release-signed only in Environment `release`), emulator job (empty at first), `ci-gate` job | CI green on the empty project; a PR that skips path-filtered jobs still merges |
| 1.3 | Dev environment on the home server without Docker and without root (see A6): SQLite, `uv`, `fnm`, fake FCM, time provider in the backend, database layer with dialect modules (A7). Additionally `docker-compose.dev.yml` for machines with Docker (notebook, CI) | `make dev` starts on the home server; fake FCM accepts calls |
| 1.4 | Backend skeleton: FastAPI, `/api/health` (503 until the schema matches), worker runs migrations under a DB lock on start, JSON logging, configuration, Dockerfile, `deploy/docker-compose.yml` (api + worker), app/admin host separation, Cloudflare Access JWT check on the admin host (off only with `FAMAPP_DEV=1`), Python `t()` helper reading `shared/strings`, admin base template using `tokens.generated.css` | health test; `t()` passes string vectors; image builds |
| 1.5 | Expo project (**TypeScript**) with an empty local module `famapp-engine`, package name, native config only via config plugins in `app/plugins/`, `branding.json` wired in, TS `t()` helper and ThemeProvider reading the shared strings and generated tokens; Gradle step copying `de.json` into engine assets | APK builds; emulator starts the app and shows a string from `de.json` |
| 1.6 | Spec `docs/spec-sync.md` | file exists, covers endpoints, operations, conflicts, error cases, protocol version header, minimum/latest app version, unknown fields |
| 1.7 | Migrations: `users`, `user_settings`, `devices`, `device_tokens`, `notifications`, `deliveries`, `secrets`, `audit_log`, `conflict_log`, `job_log`, `rev_counter` with `next_rev()` | migration up/down on SQLite and MariaDB in CI |
| 1.8 | Secret encryption (AES-GCM, `MASTER_KEY`) | round-trip and tampering tests |
| 1.9 | Setup wizard (minimal): `SETUP_TOKEN`, admin account with password + TOTP, upload Firebase key, second account, lock | E2E test of the wizard against the dev DB |
| 1.10 | Device auth: pairing code, pairing, access/refresh with rotation, generous reuse rule (decisions section 3), revocation, rate limits, client-IP rule (rightmost `X-Forwarded-For` → Cloudflare check → `CF-Connecting-IP`), audit log | tests: lost refresh response + retry, weeks offline, real token theft locks; spoofed `CF-Connecting-IP` from a non-Cloudflare address is ignored |
| 1.11 | Sync: `GET /api/sync`, `POST /api/sync/push`, acks, server time, protocol version + minimum app version, `POST /api/devices/me/fcm-token`, admin CLI "test notification" | delta across several tables, pagination, tombstones, idempotency, concurrency, old protocol version still served, too-old app rejected |

**Run done when:** all packages checked off, CI green. No checkpoint needed; Run 2 starts directly.

---

### 🤖 Run 2: Engine, push and delivery

| ID | Work package | Automated acceptance criterion |
|---|---|---|
| 2.1 | Spec `docs/spec-engine.md` (Room schema and migration policy, planner, both alarm types, display keys, channels, actions, bridge, plan B `specialUse` foreground service) | file exists |
| 2.2 | Module `engine-core` (pure Kotlin, see A6): time provider, test-vector loader, Kotlin `t()` helper (string vectors), Gradle build with little RAM. In CI additionally the Robolectric setup for `engine-android` | sample vector runs locally on the home server |
| 2.3 | `engine-core`: sync logic (outbox, delta, clock skew, backoff, protocol version, "update available") against an HTTP interface; sync status (`online` / `offline` / `server_unreachable`, unsent count) as an event for the UI; outbox entries never expire, removed only after server confirmation, permanent rejections marked "failed" without blocking the queue. `engine-android`: Room schema (mirror re-synced on schema change, outbox/auth/sync state migrated), token storage in the Keystore, wiring to `engine-core` | `engine-core` tests locally against the real dev backend; `engine-android` in CI incl. a schema change that keeps the outbox; tests: outbox survives a simulated week without server and a restart, a rejected entry does not block the following ones |
| 2.4 | **Planner** in `engine-core` (next time, everything due, catch-up, expiry). Setting the alarm in `engine-android`: both `setAlarmClock` and `setExactAndAllowWhileIdle`, switchable via engine setting (default decided at C1) | planner vectors incl. DST and time zones, locally |
| 2.5 | Display: channels, stable IDs, `shown_at` + ack, receivers (alarm, boot, time change, update), WorkManager jobs, **sync before display** when the alarm fires (5 s timeout), **one sound per alarm firing**, report notification permission and channel importance with each sync (`device_status`), **record every alarm firing** (alarm type, idle, network, sync result and duration) and send it via the outbox (`alarm_firing`) | emulator: display after forced Doze, after reboot, after time zone change, without network |
| 2.6 | JS bridge, pairing screen, raw "Delivery" screen, setup flow (permissions, battery, Samsung hints, check `USE_EXACT_ALARM`) | emulator: pairing against dev backend, status visible |
| 2.7 | Worker with APScheduler, DB lock against double execution, job log | two worker instances in a test, job runs once |
| 2.8 | FCM sending (data message, TTL, priority rule: high only when a display is expected now, otherwise normal + `collapse_key`), token maintenance; app: `FirebaseMessagingService` → sync, `onNewToken`, **silent re-post** when a high-priority wake-up brings nothing new to show | fake FCM records the wake-up; optionally real delivery in the emulator via dev Firebase |
| 2.9 | Watchdog (2/10/60 min, "not delivered"), heartbeat (> 6 h); engine: "server unreachable" system notification (network available, sync failing for 3 h; extra sentence if urgent todos are waiting in the outbox) | time-controlled backend tests with a fast-forwarded clock; engine-core test: no notification while offline |
| 2.10 | "Delivery" complete (all checks, buttons to system settings, local and server test), delay statistics | emulator test of the checks |
| 2.11 | First admin UI pages: delivery, devices (generate pairing code, lock) | page tests (htmx endpoints) |
| 2.12 | **Observation job** in the worker: sends test notifications to both users several times a day and creates **device-planned test displays** (shown via the device's own alarm, also at times the phone is likely idle), can be switched off; `alarm_firings` table; evaluation in the admin UI incl. **pre-display sync success per device, alarm type and idle state** and sync duration (median/p95) | job test with fast-forwarded clock; backend test: `alarm_firing` ops stored and aggregated |
| 2.13 | Checklist `docs/checkpoint-c1.md`: exactly what Martin does at C1, step by step | file exists |

**Run done when:** all packages checked off, CI green (incl. emulator tests). The agent asks Martin to move `release` to `main` and stops for C1.

---

### 👤 C1: First deployment (about 2–3 h + one week in the background)

The agent provides an exact step-by-step guide in `docs/checkpoint-c1.md`. Contents:

1. Check that Coolify has deployed the `release` state and `/api/health` responds.
2. **Setup wizard** on the admin subdomain: admin account + TOTP, upload Firebase service account, test push, create second account.
3. **Install the APK on both phones**, pair with a pairing code, go through the setup flow (incl. Samsung battery settings).
4. "Delivery" on both devices: everything green?
5. **Hardware tests** the emulator does not cover (list in the checkpoint document), among them:
   - natural Doze: leave the phone untouched for 2 h
   - Samsung-specific behavior, app reinstalled
   - real FCM latency on mobile networks
   - **decide the alarm type**: run a few days with each (`setAlarmClock` vs `setExactAndAllowWhileIdle`), check the status-bar icon, lock screen/watch "next alarm" and DND schedules, and the **pre-display sync success** in the admin UI (idle firings with network: target ≥ 95 % `ok`). After the observation week set the default; if `setExactAndAllowWhileIdle` wins but misses the sync target, choose a fallback (decisions section 11: `setAlarmClock` only for nag/reminder alarms, accept stale nags, or change the timeout)
6. **Switch on the observation job.** It runs for a week while Run 3 is already working. Martin only checks the admin UI now and then.
7. File anything unusual as a GitHub issue (template provided); review the assumptions in `docs/assumptions.md`.

**Done when:** both phones are paired, hardware tests done or filed as issues, observation running. Run 3 can start.

---

### 🤖 Run 3: Todos, nagging, series

Open issues from C1 take priority over new packages.

| ID | Work package | Automated acceptance criterion |
|---|---|---|
| 3.1 | Spec `docs/spec-todos.md`, test vectors for levels (incl. `due_soon`, end-of-day downgrade of explicit urgent), quiet hours per weekday, **modes** (effective mode, manual end, schedule, `dnd` catch-up), per-user intervals, nag window, overdue slots, snooze (2 Std./Bis morgen, combined), nag times, rotation, RRULE, conflicts | vectors exist and load in all three languages |
| 3.2 | Backend: migrations (`people`, `categories`, `todos`, `todo_series` incl. `replace_open`, `todo_snoozes` incl. combined snooze, `todo_claims`, `activity_events`; `user_settings` extended with mode, mode end, mode schedule and all per-user intervals), seed data, **activity events written for every todo action** (push, REST, worker), sync operations, conflict logic per field group, conflict log | conflict scenarios (completed offline + title changed, delete vs. edit, clock skew) |
| 3.3 | Backend: activity notifications (only: new todo for me/both; completed/dismissed for me/both or created by me; "Mach ich" on my urgent todo) with batching and collection until the first summary, explicit urgent incl. the night special case, claims, per-recipient delivery status for the sender, wake-up on status change of nagging todos, **mode-aware** sending (no display expected → normal priority) | tests with fast-forwarded clock; edits/deletions do not notify |
| 3.4 | Design system: final semantic token set in `shared/design/tokens.json` (light/dark), base components, navigation, `repo.ts` + `repo.native.ts`; a hidden "design preview" screen showing all base components and tokens | component tests, screenshot tests in the emulator (light/dark) |
| 3.5 | Engine: Room tables and sync for todos, people, categories, series, snoozes, settings; bridge functions | JVM tests |
| 3.6 | App: settings (quiet hours per weekday, summary times per weekday, **all per-user intervals** with ranges, DND bypass, theme), **mode switch** with end (1 Std. / Bis morgen / Bis ich es ausschalte), **weekly mode schedule**, mode banner, recipient's mode shown when sending urgent | emulator: change a setting → second test client sees it |
| 3.7 | App: todo list (all todos visible, filters mine/both/other's), detail, create/edit (scheduled with optional lead time), complete, dismiss, reopen, postpone (incl. "Morgen"/"+3 Tage", scheduled todos), "send urgent" with delivery status ("Zugestellt"/"Mach ich"), level computation in TS; **offline banner** on every screen while sync fails (base component, text from `de.json`, unsent count); **"Noch nicht gesendet" marker** on todos with unconfirmed changes (prominent for urgent todos sent to the other person); "failed" state with retry/discard | E2E in the emulator: backend stopped → banner visible while editing, change kept; backend back → change synced, banner and marker gone; urgent todo sent while backend is down shows the prominent marker |
| 3.8 | **Engine II:** summaries (incl. `due_soon` and the quiet-hours catch-up in the first summary), scheduled reminders (lead time, at `due_at`), nagging (explicit per todo incl. "Mach ich"; overdue as **one combined notification per user** at the 4 computed slots), nag window, quiet hours, **modes** (`remind` / `essentials` / `dnd`, schedule, `dnd` catch-up), snooze (30 min / 2 Std. / Bis morgen, combined), DND bypass, actions from the notification incl. 30 s undo | planner vectors; emulator: "Done" action without the app open stops nagging, undo restores it |
| 3.9 | Watchdog for all device-planned displays (summaries, nags, scheduled reminders; calendar in 4.5): server computes expected keys with the shared vectors (mode-aware, using the mode valid at the planned time), delivery records per repetition | backend test with fast-forwarded clock |
| 3.10 | Series: UI with pickers, RRULE in the client, validation and instance creation in the worker, rotation, dismissed rule, `replace_open` (default on for calendar rules), relative level thresholds, reopen removes untouched next instance, edit/pause/delete rules | vectors (incl. relative thresholds); "every 2 weeks, rotating" and "every 1st Monday" as E2E |
| 3.11 | **Activity view** "Aktivität": list, filters (person, type, todo), tap opens todo, "nachträglich synchronisiert" marker, 90-day local window + server paging; engine: Room table and sync for `activity_events` | E2E: complete, snooze, postpone on device A → events with actor and time on device B; offline action shows the marker after sync |
| 3.12 | Screenshots of all screens (light and dark) as CI artifact, checklist `docs/checkpoint-c2.md` | artifact exists |

**Run done when:** all packages checked off, CI green. The agent asks Martin to move `release` to `main` and reports C2. **It does not stop** but starts Run 4 right away (C2 blocks nothing).

---

### 👤 C2: Daily-use test and design review (about 1–2 h, in parallel with Run 4)

1. Install the app update on both phones.
2. Review the **design** from the screenshots, the design preview screen and on the device; review the **wording** in `shared/strings/de.json`. File change requests as issues ("colors", "spacing", "wording" …), or edit the two files directly. Usually nothing else is affected.
3. **Test together with his wife** (list in `docs/checkpoint-c2.md`):
   - send urgent todos back and forth, nagging, "Snooze", "Done" on one device stops the other
   - send to "both"
   - send in the evening → one notification, nagging from the first summary
   - "Mach ich", snooze "2 Std." / "Bis morgen", sender sees "Zugestellt"
   - modes: "Nur Wichtiges" (urgent shows once), "Nicht stören" until a time (nothing, then one catch-up), a weekly mode slot; sender sees the recipient's mode
   - activity view: actions of the other person appear with name and time
   - check the "Nerv-Level" statistics in the admin UI: notifications per day feel right, no channel muted
   - watch the summaries for a few days
   - one recurring task with rotation
4. Check the result of the observation week in the admin UI: target 100 % shown, 95 % within 60 s.
5. File problems as issues.

---

### 🤖 Run 4: Calendar, web, admin, wrap-up

Issues from C2 take priority.

| ID | Work package | Automated acceptance criterion |
|---|---|---|
| 4.1 | Fake Google Calendar with fixtures (recurring, all-day, changed, deleted events, `410 Gone`) | fake runs in `make dev` |
| 4.2 | `CalendarSource` + `google_api` (incremental, rebuild; window applied server-side because `syncToken` excludes `timeMin`/`timeMax`), fetch job, `calendar_sources`, `calendar_events`, rev sync (device window −1 to +3 months) | tests against the fake |
| 4.3 | Wizard/admin: enter OAuth client, Google login, choose calendars, color, "notify: user A/B", test fetch, warning on expired token | E2E against the fake (OAuth flow mocked) |
| 4.4 | App: agenda, week and month views, toggle sources | emulator E2E |
| 4.5 | Engine: calendar notifications (evening before, morning, start, all-day, quiet-hours rule), events in summaries; watchdog for calendar keys | planner vectors; backend watchdog test |
| 4.6 | Add appointment → todo in "calendar" category, action "Open in calendar app" | emulator: intent is fired |
| 4.7 | Web: `repo.web.ts`, REST endpoints, hide native areas, offline banner + edit lock when the server is unreachable, build into the backend image | Playwright E2E against dev backend, incl. backend stopped → banner, editing blocked |
| 4.8 | Web login: password → approval in the app (code + yes/no) → session, recovery codes, admin reset, CSRF, 30 days, session list | E2E: browser (Playwright) + emulator approves |
| 4.9 | Admin UI complete (activity page reads `activity_events`; current mode per user): statistics (incl. "Nerv-Level": notifications per user/day by class, snooze/postpone/claim counts, muted-channel warning from `device_status`), activity, conflicts, logs, settings, tools; admin login with TOTP | page tests |
| 4.10 | One-page quick guide for Martin's wife (German), checklist `docs/checkpoint-c3.md` | files exist |

**Run done when:** all packages checked off, CI green. The agent asks Martin to move `release` to `main` and stops for C3.

---

### 👤 C3: Wrap-up (about 2–3 h)

1. Install the app update on both phones.
2. **Google integration in the admin UI:** enter OAuth client ID/secret, sign in with Martin's Google account, select and assign the three calendars (Martin's → Martin, his wife's → his wife, shared → both), test fetch.
3. Check events on both phones; change an event in Google → arrives within 5 min.
4. Set up and test **web login** for both (approval on the phone); store recovery codes safely.
5. Full pass through the hardware test matrix (list in the checkpoint document).
6. **Switch on Coolify DB backups.**
7. Go through the quick guide with his wife; switch off the observation job.
8. **Make the GitHub repo private again** (Settings → General → Danger Zone). Then check Actions usage and the minute-saving rules in A6.

**MVP done when:** two weeks of daily use without a lost notification.

---

### 🔁 Afterwards: bug loop and more features

- Martin files bugs or wishes as GitHub issues (template: what happened, what was expected, which device, approximate time). An agent works through issues one by one under the same rules (Part A).
- Martin moves `release` when he wants an update.
- More features, each as its own run with a short checkpoint:
  1. Backups: retention, external copy, **restore test** (Martin, because it involves production data)
  2. Shopping list
  3. Notebook
  4. Finances / household budget
  5. CalDAV instead of Google, incl. writing

---

## Part C: What agents cannot do (and why it is Martin's job)

| Area | Why manual |
|---|---|
| Creating accounts (Firebase, Google Cloud, Cloudflare, Coolify) | sign-ins, payment/consent dialogs, access to Martin's accounts |
| Entering production secrets | agents must never see them |
| Creating and storing the signing key | losing it means no more installable updates |
| Real phones | Samsung behavior, natural Doze, mobile networks, sound and vibration can only partly be reproduced in an emulator |
| Google login with Martin's account | OAuth consent by Martin |
| Restore test | works with production data |
| Acceptance with his wife | only they can judge whether it works in daily life |

---

## Part D: Effort

| Section | Martin's time | Agents |
|---|---|---|
| C0 preparation | 3–4 h | – |
| Run 1 + 2 | – | biggest block (backend core, engine) |
| C1 | 2–3 h + observation week in the background | – |
| Run 3 | – | large block (todos, engine II, series) |
| C2 | 1–2 h + daily use | Run 4 runs in parallel |
| Run 4 | – | medium block |
| C3 | 2–3 h | – |
| **Total for Martin** | **about 10–14 h** plus daily-use tests | |

How long the runs take depends on how long an agent can work in one go. Work packages are sized so each fits in one session, and the next agent continues seamlessly from `docs/progress.md`.

---

## Part E: Risks

| Risk | Mitigation |
|---|---|
| Emulator tests do not reproduce Samsung or real Doze | hardware list at C1/C3, observation job, watchdog, heartbeat; plan B foreground service |
| Doze throttles `setExactAndAllowWhileIdle` (about once per 9 min per app) | single-alarm planner, `setAlarmClock` for high priority |
| An agent makes an assumption Martin wants differently | `docs/assumptions.md`, review at every checkpoint, correction via issue |
| Agent code drifts from the architecture | `AGENTS.md`, specs before code, CI with architecture checks (e.g. no DB access from JS) |
| Logic diverges across three languages | shared test vectors |
| A broken state reaches production | deploy only from `release`, which Martin moves at checkpoints |
| Signing key lost | back it up twice at C0 (e.g. password manager + offline copy) |
| Expo/React Native updates break the module | update the SDK deliberately only, as its own issue |
| Google token expires | warning in the admin UI + notification to Martin, re-login via the admin UI |
| CI minutes run out | home-server packages first, batch Android work; public repo or self-hosted runner as fallback |
| Data loss before the backup phase | Coolify backups at C3 (accepted: C2/Run 4 data unprotected until then) |
| Device locked by refresh-token rotation | generous reuse rule: previous token valid until the new one is used |
| FCM deprioritizes high-priority messages without visible notifications | high priority only when a display is expected |
| Server/worker down unnoticed | device shows "server unreachable" after 3 h of failing syncs with network |
| New server breaks old app versions | protocol version header, previous version supported, minimum app version, update notice |
| Cloudflare Access bypassed via public VPS IP | backend validates the Access JWT on the admin host |
| Repo forgotten as public | reminder in the C3 checklist |
