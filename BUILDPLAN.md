# FamApp build plan

The plan is organized for **autonomous work by AI agents**. Martin only steps in at a few checkpoints, where something has to come from him: accounts and access, real phones, production secrets, acceptance.

```
👤 C0 prep ─► 🤖 Run 1 ─► 🤖 Run 2 ─► 👤 C1 first deploy ─► 🤖 Run 3 ─► 👤 C2 daily-use test ─► 🤖 Run 4 ─► 👤 C3 wrap-up
  (30 min)     backend      engine        (2–3 h)               todos,       (1–2 h, runs in          calendar,     (2–3 h)
               core         + push                              series       parallel with Run 4)     web, admin
                  ▲            ▲             ▲                                                                     ▲
👤 M-tasks ───────┴─ M1 ───────┴─ M3–M6 ─────┘ ─────────────────────────────────────────────────── M8, M9 ──────────┘
   (in parallel, about 3 h)
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
4. **Shared test vectors** in `shared/test-vectors/` (levels, quiet hours, modes, nag times, planner, rotation, RRULE, conflicts, strings). Python, Kotlin and TypeScript test against the same files.
5. **Spec before code.** Every larger package starts with a short spec under `docs/`. Agents write it themselves based on the README and `docs/decisions.md`. No approval needed.
6. **`AGENTS.md` in the repo root** (`CLAUDE.md` points to it): project goal, commands, conventions, definition of done, stop rules, where things live. Every agent reads it first.

### A2. Definition of done per work package

- CI green (tests, lint, audits, APK build, emulator tests where relevant)
- The package's acceptance criterion exists as an **automated test**
- Spec and docs up to date; new assumptions in `docs/assumptions.md`
- Pull request with a **"For the next checkpoint"** section: what Martin should check on a real device or in production
- Checkboxes in Part B ticked (sub-tasks, package line with PR number); `docs/last-session.md` written and archived at the end of the session (`AGENTS.md`, "Ending a session")

### A3. When an agent stops and asks

An agent stops and asks **only** in the cases listed in `AGENTS.md` section 3. In short: it **stops and waits** when Martin must decide (user-visible behavior not covered by README or decisions; something irreversible such as package name, a migration that deletes data, signing key, changes to `release`; going against a ✅ decision; a hard-to-undo decision the docs give no direction on). It **parks the sub-task and continues** with independent work when access, an account or a secret is missing, or CI stays red / an external service is down. Every run also ends the session.

Not a reason to stop: GitHub Actions minutes used up (only possible once the repo is private again after C3); see A6.

Everything else the agent decides itself and records in `docs/assumptions.md`. Martin can review the assumptions at the next checkpoint and have them corrected.

### A4. Branches, deployment, secrets

- Agents work on feature branches, one PR per work package. **Auto-merge into `main` when CI is green.** (Martin can merge every PR himself instead, at the cost of autonomy.) After C3 the repo is private on GitHub Free, which has no rulesets: agents then wait for `ci-gate` (`gh pr checks --watch`) and merge only when it is green (`docs/decisions.md` section 10).
- **Coolify deploys only the `release` branch.** **Only Martin moves it** to the current `main` at checkpoints. At the end of a run the agent asks him (issue + note in `docs/last-session.md`). Nothing reaches production unchecked.
- **Agents never get production secrets.** The APK signing key lives only in the GitHub Environment `release` (restricted to the `release` branch, Martin as required reviewer) and, after C3, in a repo secret read only by the release workflow; PR and `main` builds are debug-signed. Optionally a separate dev Firebase project.
- **One required check `ci-gate`:** an always-running job that depends on all other jobs and accepts skipped ones. Branch protection requires only this job, so path filters never block a merge.
- Progress is visible in the repo: checkboxes in Part B (status), `docs/last-session.md` (handover from the previous session, blockers), `docs/session-history.md` (archive) plus PR history.

### A5. Repository layout

One place only: README section 12 (incl. `AGENTS.md`, `Makefile`, `dev/` fakes, `docs/` files, `.github/`). Keep it in sync with the actual layout (sub-task 1.1.12).

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
- Python via `uv`, Node via `fnm`, JDK (Temurin tarball, for ktlint and `engine-core`) and GNU `make` via `tools/install-user-tools.sh` into `~/.local` (the image has no `make` and no `unzip`, which SDKMAN needs).
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

**No spending (M-task M9, at the latest before the repo goes private at C3):**

- Do not add a payment method to the GitHub account. Without one nothing can be billed; once the free minutes are used up, runs no longer start until the next month.
- If a payment method is on file anyway (e.g. for Copilot or Pro): under *Billing → Budgets and alerts*, create a budget for **Actions** of $0 with **"Stop usage when budget limit is reached"**.
- Enable notifications at 75/90/100 % of the included minutes.
- When minutes run out, agents keep working on the home server (backend, `engine-core`, web) and batch Android changes until CI runs again. This is noted in `docs/last-session.md` (Open blockers).

To make the minutes last (once the repo is private again):

- Emulator E2E only when something under `app/` changed, and batched (agents collect several changes before pushing).
- Full emulator suite nightly or before moving `release`.
- If minutes get tight: make the repo public (no secrets in the repo; standard runners are free for public repos) or register the notebook as a self-hosted runner (also free; only runs while the notebook is on). **Never both:** a self-hosted runner on a public repo runs code from anyone's PRs.

### A7. Database: SQLite in development, MariaDB in production

The database is selected via `DATABASE_URL`:

- **Home server and local tests:** `sqlite:///./dev.db` (default when unset). Tests each use a fresh SQLite database.
- **CI:** an additional job runs the full backend test suite against **MariaDB** (service container). Costs a few minutes, only on changes under `backend/`.
- **Coolify (production):** `mysql+pymysql://…` pointing at the MariaDB resource. The first run against MariaDB on the server happens at C1. By then CI has already checked every migration and test against MariaDB.

So that both databases really behave the same, these rules apply (also in `AGENTS.md`):

| Topic | Difference | Solution |
|---|---|---|
| `rev` numbers | SQLite has no `SEQUENCE` | Counter table `rev_counter` behind a function `next_rev()` with one implementation per database (MariaDB: `LAST_INSERT_ID(value+1)`, atomic; SQLite: `UPDATE … RETURNING`, single writer) |
| Locks (worker jobs, pairing code) | SQLite has no `SELECT … FOR UPDATE` or `GET_LOCK` | Module `db/locks.py` with one implementation per database; for SQLite an OS file lock, which also works across processes (api and worker both write in dev) |
| Data types | SQLite barely checks lengths and types | Only portable SQLAlchemy types (`Uuid`, `JSON`, a custom UTC `DateTime` type), length validation in Pydantic |
| Time zones | SQLite stores text | One type for all timestamps: always UTC, made timezone-aware on read |
| Migrations | SQLite has limited `ALTER` | Alembic with `render_as_batch=True`; every migration runs up and down on both databases in CI. Production: the worker migrates on start under a DB lock; migrations are **additive** (expand/contract) so the previous image keeps working |
| Case and sorting | different collations | Comparisons that depend on it are explicit in code; collation `utf8mb4_unicode_ci` set in MariaDB |
| Raw SQL | dialects differ | Only through SQLAlchemy; raw SQL exclusively in `backend/app/db/dialects/` (checked in CI) |
| Concurrency | SQLite serializes all writes | Tests for concurrent writes are marked `@pytest.mark.mariadb` and run only in the MariaDB CI job |

If something shows up only on MariaDB, add a test case so CI catches it in the future.

---

## Part B: Sequence

### How progress is tracked

**The checkboxes in this part are the single place where status lives.** Agents and Martin tick them as they go; `docs/last-session.md` is the handover note between sessions (where the last one stopped, what needs Martin, open blockers).

| Marker | Meaning |
|---|---|
| `- [ ]` | open |
| `- [ ] 🚧` | in progress (add your branch: `🚧 pkg/1.4-backend-skeleton`); remove 🚧 when ticking. `main` only changes through PRs, so set the marker in the branch's first commit and open the PR as a **draft** right away; the draft PR is what makes the claim visible |
| `- [x]` | done; packages also get the PR number (`· PR #12`) |
| `- [ ] ⏸` | blocked; the reason is in `docs/last-session.md` → Open blockers |

Rules:

- **Sub-tasks (`1.4.3`) are separable.** Each one leaves the repo green (`make lint && make test`), is one or a few commits, and can be picked up by a new agent from the checkbox alone. Work them in order unless a sub-task says otherwise.
- **One PR per package by default.** A large package may be split into several PRs along sub-task boundaries (branch `pkg/1.4.1-1.4.5-backend-skeleton`); each PR ticks only the sub-tasks it completes.
- Tick sub-tasks **in the same PR** that completes them. Tick the package line (`**1.4 done**`) only when every sub-task is ticked, the acceptance test is green in CI and A2 is satisfied.
- Tick the run line when every package is ticked.
- Found work that is missing? Add a sub-task with the next free number (`1.4.13`) in the same PR and note why in the PR description. Never renumber existing sub-tasks.
- Runs 3 and 4 have packages only. **The first package of each run breaks the remaining packages into sub-tasks** the same way (sub-task `3.0` / `4.0`).

### Overview

- [ ] 👤 C0 preparation (blocks Run 1)
- [ ] 👤 M-tasks (Martin, in parallel, each due before the step that needs it)
- [ ] 🤖 Run 1: Foundation and backend core
- [ ] 🤖 Run 2: Engine, push and delivery
- [ ] 👤 C1 first deployment
- [ ] 🤖 Run 3: Todos, nagging, series
- [ ] 👤 C2 daily-use test and design review
- [ ] 🤖 Run 4: Calendar, web, admin, wrap-up
- [ ] 👤 C3 wrap-up → MVP done after two weeks of daily use without a lost notification

---

### 👤 C0: Preparation (only what blocks Run 1, about 30 min)

C0 contains **only** what Run 1 cannot start without. Everything else Martin does in parallel while the agents work (M-tasks below), each due before the step that really needs it.

Not needed: subdomains are decided (`docs/decisions.md`); the display name is open but not blocking, so 1.1 uses a placeholder in `branding.json` and records it in `docs/assumptions.md`.

- [x] **C0.1a** Create GitHub repo
- [x] **C0.1b** GitHub repo: **make it public** (until C3), enable auto-merge, protect `main` via a **ruleset** (require PR with **0 required approvals**, since agents open PRs under Martin's account and nobody else can approve; required status check `ci-gate`, entered by name; it does not exist until the first PR)
  *Blocks:* 1.2 CI incl. emulator job needs free minutes; auto-merge needs a required check.
- [x] **C0.2** In the code-server container: `gh` logged in with a token of Martin's account (fine-grained, limited to this repo; `docs/decisions.md` section 10) that can push and open PRs: Contents, Pull requests, Issues, **Workflows** (to push `.github/workflows/`) and Actions (read/write)
  *Blocks:* every package needs PRs; 1.2 needs to push workflows and read CI runs.
- [x] **C0.3** (agent) Confirmed: the agent pushed a branch with a workflow file, opened a PR and read its CI run. Done as part of 1.1.

**Done when:** C0.1b and C0.2 are ticked; then Run 1 starts. C0.3 is ticked by the agent in 1.1.2 and is not a precondition.

### 👤 M-tasks: Martin, in parallel with the runs

Martin ticks these. An agent may tick one if it can verify the result itself (e.g. `google-services.json` is in the repo).

- [ ] **M1** Create the **Firebase project** (package name `com.cowflex.famapp`), put `google-services.json` in the repo (not a secret), keep the service account key **locally with Martin** (it goes into the wizard at C1)
  *Due before:* **Run 2** (2.8 FCM) · *Result:* app can integrate FCM
- [ ] **M2** Optional: a second **dev Firebase project**, key as GitHub secret
  *Due before:* Run 2 (2.8, optional) · *Result:* agents can test real FCM delivery in the emulator
- [ ] **M3** Create the **APK signing key** (one file, keep it safe!, back it up twice) and add it as a secret of the GitHub Environment `release` (deployment branch: `release` only, required reviewer: Martin) under the secret names the agent defines in 1.2 (`docs/release-signing.md`). Protect `release` (only Martin may push). At C3 the secrets move to repo secrets (C3.8). Updates can only be installed if they are signed with the same key.
  *Due before:* C1 · *Result:* signed APKs from CI
- [ ] **M4** **Cloudflare:** DNS records for both subdomains (proxied), WAF skip rule for the app subdomain, Cloudflare Access (GitHub SSO) for the admin subdomain; note the team domain and the application's **audience (AUD) tag** (guide: `deploy/cloudflare.md`, written in 1.4)
  *Due before:* C1 · *Result:* reachability
- [ ] **M5** **Coolify:** MariaDB resource (not public), Docker Compose resource from the repo, branch `release`, auto-deploy on push, environment variables `DATABASE_URL`, `MASTER_KEY`, `SETUP_TOKEN` (generate both randomly and store them safely), `CF_ACCESS_TEAM_DOMAIN`, `CF_ACCESS_AUD` (from M4). The resource may fail until `release` has code.
  *Due before:* C1 · *Result:* deployment
- [ ] **M6** On both phones allow "Install unknown apps" for the browser/file manager
  *Due before:* C1 · *Result:* APK installation
- [ ] **M7** Cloudflare Tunnel: check that ports 8000, 5000 and 5173 are reachable for Martin
  *Due before:* whenever Martin wants a browser preview · *Result:* browser preview
- [ ] **M8** **Google Cloud:** enable the Calendar API, OAuth consent screen "External", status "In production", scope `calendar.readonly`, OAuth client (web) with redirect `https://<admin-subdomain>/setup/google/callback`. Keep client ID/secret locally (they go into the admin UI at C3)
  *Due before:* C3 (Run 4 works against the fake) · *Result:* calendar integration
- [ ] **M9** **Secure GitHub costs:** no payment method, or Actions budget $0 with "Stop usage"; alerts at 75/90/100 % (see A6)
  *Due before:* C3 (repo goes private; public repos use free standard runners) · *Result:* no costs

Run 1 notes M1 under Open blockers in `docs/last-session.md` if it is still missing; at the end of Run 1 the agent opens a `question` issue if M1 is not done. Run 2 can do 2.1–2.7 without it and only stops at 2.8.

---

### 🤖 Run 1: Foundation and backend core

- [ ] **Run 1 done:** all packages ticked, CI green. No checkpoint needed; the session ends and Martin starts Run 2 with a new session (`/next`).

#### 1.1 Repo scaffold

*Acceptance (automated):* `make lint` and `make tokens` run; checks fail on a deliberately broken key or stale generated file.

- [ ] 🚧 `pkg/1.1-scaffold-rest` 1.1.1 Directory skeleton per README 12 (`backend/`, `app/`, `shared/`, `tools/`, `dev/`, `deploy/`, `docs/`), `.gitignore` (`dev.db`, build output, key/keystore patterns), `.editorconfig`
- [x] 1.1.2 Minimal CI workflow `.github/workflows/ci.yml` with a lint job and the `ci-gate` job, so this first PR can satisfy the required check (1.2 extends it); confirms C0.3
- [ ] 1.1.3 `branding.json` with a placeholder display name, short name, icon color; placeholder recorded in `docs/assumptions.md`
- [ ] 1.1.4 `Makefile` with all targets from `AGENTS.md` (`setup`, `dev`, `test`, `lint`, `tokens`, `e2e`, `apk`); targets that are not built yet print which package adds them
- [ ] 1.1.5 Lint configs: Ruff, ESLint (flat config), ktlint; all wired into `make lint` (install the tools in user space here; 1.3.1 folds them into `make setup`)
- [ ] 1.1.6 `shared/strings/de.json` with the first keys and the key naming convention (by area, plural forms) documented in a comment file or README section
- [ ] 1.1.7 `shared/design/tokens.json`: base + semantic tokens, light/dark, initial neutral palette (incl. `color.state.urgent`, `color.state.offline`)
- [ ] 1.1.8 Token generator in `tools/` → TS (`tokens.generated.ts`), CSS (`tokens.generated.css`), Android XML (`colors_generated.xml`); `make tokens`; a check mode that fails on stale generated files, run by `make lint`
- [ ] 1.1.9 String checks in `tools/`: missing/unused keys, placeholder mismatch, German literals in code; run by `make lint`
- [ ] 1.1.10 String test vectors in `shared/test-vectors/strings/` (placeholders, plurals, missing key behavior), used by the `t()` helpers in 1.4, 1.5 and 2.2
- [ ] 1.1.11 Issue templates (bug report per the bug loop, question) and labels `bug`, `question`
- [ ] 1.1.12 `AGENTS.md` and README section 12 match the actual layout
- [ ] 1.1.13 Acceptance tests for the tools: a broken key, a placeholder mismatch and a stale generated file each make the check fail
- [ ] **1.1 done** · PR:

#### 1.2 CI

*Acceptance (automated):* CI green on the empty project; a PR that skips path-filtered jobs still merges.

- [ ] 1.2.1 Change-detection job (outputs per area: `backend`, `app`, `shared`, `tools`, `docs`); all other jobs use job-level `if:` conditions, no workflow-level `paths:`
- [ ] 1.2.2 Lint job running `make lint` (incl. token staleness and string checks)
- [ ] 1.2.3 Backend test job on SQLite (`uv`, pytest; a placeholder test until 1.3)
- [ ] 1.2.4 Backend test job on **MariaDB** (service container, collation `utf8mb4_unicode_ci`, `DATABASE_URL=mysql+pymysql://…`), also runs `@pytest.mark.mariadb` tests (A7)
- [ ] 1.2.5 JS unit test job (skipped until `app/` has code)
- [ ] 1.2.6 Audits: `pip-audit`, `npm audit` (fail level recorded in `docs/assumptions.md`)
- [ ] 1.2.7 Architecture checks in `tools/`, run by `make lint`: raw SQL only in `backend/app/db/dialects/`, no direct clock calls in logic code, no DB access from JS
- [ ] 1.2.8 APK build job: debug-signed on PRs and `main`, APK as CI artifact (skipped until 1.5 creates the Expo project)
- [ ] 1.2.9 Release-signing workflow: runs only on push to `release`, inside Environment `release` (after C3: same secret names as repo secrets, no Environment; one switch documented in 1.2.10); defines the signing secret names; fork PRs never get secrets; app version in `app/version.json` (name + `versionCode`), read by the APK build and the backend (= "latest app version", README 7, 10); the workflow fails if `versionCode` is not higher than the last GitHub Release's; signed APK attached to a GitHub Release
- [ ] 1.2.10 `docs/release-signing.md`: how Martin creates the key, backs it up twice and adds the secrets (input for M3), and the C3 switch to repo secrets (input for C3.8)
- [ ] 1.2.11 Emulator job (KVM on standard runners), empty suite, only when `app/` changed
- [ ] 1.2.12 `ci-gate` job: `if: always()`, needs every job, fails on `failure`/`cancelled`, accepts `skipped`
- [ ] 1.2.13 Acceptance: a docs-only PR skips the path-filtered jobs and still merges; a full run on the empty project is green (both PR links noted in this PR)
- [ ] **1.2 done** · PR:

#### 1.3 Dev environment on the home server

*Acceptance (automated):* `make dev` starts on the home server; fake FCM accepts calls.

- [ ] 1.3.1 `make setup`: `uv`, pinned Python, `fnm` + pinned Node, JDK and `make` via `tools/install-user-tools.sh`; user space only, idempotent, no root
- [ ] 1.3.2 Backend project: `backend/pyproject.toml`, `uv` lockfile with pinned dependencies, pytest config incl. the `mariadb` marker
- [ ] 1.3.3 Time provider: `Clock` interface, system clock, controllable fake clock (set "now", fast-forward) as a pytest fixture
- [ ] 1.3.4 Database layer: engine/session from `DATABASE_URL` (default `sqlite:///./dev.db`), custom UTC `DateTime` type, portable types only (A7)
- [ ] 1.3.5 Dialect modules `backend/app/db/dialects/` (SQLite, MariaDB) and `db/locks.py` with one implementation per database (file lock / `GET_LOCK`)
- [ ] 1.3.6 Test fixtures: fresh SQLite DB per test; same suite runs against MariaDB in CI
- [ ] 1.3.7 Fake FCM in `dev/fake-fcm/` (port 9101): accepts the FCM v1 send shape, records messages, endpoints to query and reset them for tests
- [ ] 1.3.8 `make dev` starts every service that exists (one process list; 1.4 adds api/worker/admin), `make test` runs the backend tests
- [ ] 1.3.9 `docker-compose.dev.yml` (MariaDB + services) for machines with Docker (notebook, CI)
- [ ] 1.3.10 Acceptance tests: `make dev` smoke test hits fake FCM; UTC round-trip and lock tests on SQLite (and MariaDB in CI)
- [ ] **1.3 done** · PR:

#### 1.4 Backend skeleton

*Acceptance (automated):* health test; `t()` passes string vectors; image builds.

- [ ] 1.4.1 Configuration (Pydantic settings): `DATABASE_URL`, `MASTER_KEY`, `SETUP_TOKEN`, `CF_ACCESS_TEAM_DOMAIN`, `CF_ACCESS_AUD`, `FAMAPP_DEV`, host names; fail fast on missing values outside dev
- [ ] 1.4.2 JSON logging with request ID; no todo content in logs
- [ ] 1.4.3 FastAPI app factory with app/admin **host separation** (dev: admin on port 5000); no `/docs` or `/openapi.json` in production
- [ ] 1.4.4 Alembic (`render_as_batch=True`, empty baseline) and a schema check: DB at the code's head revision or at a revision the code does not know (= newer; so the previous image keeps running after a migration, decisions section 10)
- [ ] 1.4.5 `/api/health`: 503 until the schema check from 1.4.4 passes, 200 afterwards
- [ ] 1.4.6 Worker entrypoint: runs migrations under the DB lock on start (skips with a warning if the DB is at a revision the code does not know), then starts the (still empty) scheduler; test: an older code version starts against a newer schema
- [ ] 1.4.7 Cloudflare Access JWT check on the admin host (team keys fetched and cached, audience tag checked, 404 on missing/invalid; off only with `FAMAPP_DEV=1`); tests with locally signed tokens and a fake key set
- [ ] 1.4.8 Python `t()` helper reading `shared/strings`, passing the string vectors
- [ ] 1.4.9 Admin base template (Jinja2) using `tokens.generated.css`, htmx vendored
- [ ] 1.4.10 Dockerfile (one non-root image for api and worker), `deploy/docker-compose.yml` (api + worker, env vars, health check)
- [ ] 1.4.11 CI job: build the image and smoke-test it (container starts, `/api/health` returns 200)
- [ ] 1.4.12 `deploy/cloudflare.md`: DNS, WAF skip and Access settings (input for M4)
- [ ] **1.4 done** · PR:

#### 1.5 Expo project and empty engine module

*Acceptance (automated):* APK builds; emulator starts the app and shows a string from `de.json`.

- [ ] 1.5.1 Expo project in `app/` (**TypeScript**, SDK pinned), package name `com.cowflex.famapp`, React Navigation shell
- [ ] 1.5.2 `branding.json` wired into the app config (name, short name, icon color)
- [ ] 1.5.3 Config plugin folder `app/plugins/`; generated `android/` is git-ignored and only produced by prebuild
- [ ] 1.5.4 Local module `app/modules/famapp-engine` with `engine-core` and `engine-android` folders and one trivial bridge function
- [ ] 1.5.5 Gradle step copying `de.json` into the engine assets
- [ ] 1.5.6 TS `t()` helper (`app/i18n/`) passing the string vectors (Jest)
- [ ] 1.5.7 ThemeProvider (`app/theme/`) reading the generated tokens, light/dark
- [ ] 1.5.8 Start screen showing a string from `de.json` via `t()`
- [ ] 1.5.9 APK job from 1.2.8 builds the real app
- [ ] 1.5.10 Emulator E2E: the app starts and shows the string (E2E tool choice recorded in `docs/assumptions.md`)
- [ ] **1.5 done** · PR:

#### 1.6 Sync spec `docs/spec-sync.md`

*Acceptance (automated):* file exists and covers endpoints, operations, conflicts, error cases, protocol version header, minimum/latest app version, unknown fields (a doc test checks the required sections).

- [ ] 1.6.1 Endpoints, auth headers, request/response shapes (`GET /api/sync`, `POST /api/sync/push`, `POST /api/devices/me/fcm-token`)
- [ ] 1.6.2 Delta: `since`/`limit`, ordering by `rev`, per-user visibility, tombstones, pagination
- [ ] 1.6.3 Operations: create, change field group, change status, delete, ack, snooze, `device_status`, `alarm_firing`; op UUID and idempotency
- [ ] 1.6.4 Conflicts: last-write-wins per field group, deletion wins, clock-skew correction, tie rule, conflict log
- [ ] 1.6.5 Error cases: permanent rejection vs. retry, auth failures, too-old app, server errors; client behavior for each
- [ ] 1.6.6 Versions: protocol version header, current + previous supported, minimum/latest app version, unknown fields and tables ignored
- [ ] 1.6.7 Test scenario list used by 1.11 and 2.3; doc test for the required sections
- [ ] **1.6 done** · PR:

#### 1.7 Migrations

*Acceptance (automated):* migration up/down on SQLite and MariaDB in CI.

- [ ] 1.7.1 `rev_counter` and `next_rev()` per dialect (MariaDB `LAST_INSERT_ID(value+1)`, SQLite `UPDATE … RETURNING`), always called inside the writing transaction so the counter row lock makes commit order equal `rev` order (otherwise a delta sync can skip a row committed late); concurrency test marked `mariadb`
- [ ] 1.7.2 Common columns for synced tables (`id`, `rev`, `created_at`, `updated_at`, `deleted_at`)
- [ ] 1.7.3 `users` (incl. time zone), `user_settings` (base fields incl. quiet hours per weekday, needed by 2.9; 3.2 extends them)
- [ ] 1.7.4 `devices` (incl. app version, last sync, `device_status`), `device_tokens`
- [ ] 1.7.5 `notifications`, `deliveries`, `alarm_firings` (the engine sends `alarm_firing` ops from 2.5.7 on)
- [ ] 1.7.6 `secrets`, `audit_log`, `conflict_log`, `job_log`
- [ ] 1.7.7 Up/down test for every migration on both databases (down is never run in production); check that flags destructive operations (A7: additive only)
- [ ] **1.7 done** · PR:

#### 1.8 Secret encryption

*Acceptance (automated):* round-trip and tampering tests.

- [ ] 1.8.1 AES-GCM module with `MASTER_KEY` (key format, random nonce, secret name as associated data, versioned ciphertext format)
- [ ] 1.8.2 Secret store on `secrets`: set, get, exists; values never rendered in plain text; audit log entry on change
- [ ] 1.8.3 Tests: round-trip, tampered ciphertext/nonce, swapped associated data, wrong key, missing `MASTER_KEY`
- [ ] **1.8 done** · PR:

#### 1.9 Setup wizard (minimal)

*Acceptance (automated):* E2E test of the wizard against the dev DB.

- [ ] 1.9.1 Wizard state and access: only with `SETUP_TOKEN` (constant-time compare, rate limited), unreachable after lock
- [ ] 1.9.2 Step admin account: password (Argon2id) + TOTP enrolment with confirmation code
- [ ] 1.9.3 Step Firebase service account: upload, validate JSON, store encrypted (the FCM dry-run check follows in 2.8)
- [ ] 1.9.4 Step second account: name, time zone, default times
- [ ] 1.9.5 Lock the wizard; admin login with password + TOTP
- [ ] 1.9.6 All texts in `de.json`, templates use semantic tokens only
- [ ] 1.9.7 E2E test of the full wizard flow against the dev DB (`make e2e`)
- [ ] **1.9 done** · PR:

#### 1.10 Device auth

*Acceptance (automated):* tests: lost refresh response + retry, weeks offline, real token theft locks; spoofed `CF-Connecting-IP` from a non-Cloudflare address is ignored.

- [ ] 1.10.1 Pairing codes: one-time, valid 10 min, stored hashed, bound to one user; created via admin CLI for now (admin UI page in 2.11, on a paired device in 1.10.10 / 2.6.7)
- [ ] 1.10.2 Pairing endpoint: creates the device, returns refresh + access token
- [ ] 1.10.3 Access token (15 min) and the auth dependency for app endpoints
- [ ] 1.10.4 Refresh rotation with the **generous reuse rule** (decisions section 3): previous token valid until the successor is used; an old token after that locks the device
- [ ] 1.10.5 Revocation: lock a single device
- [ ] 1.10.6 Client-IP rule: trust only Traefik, rightmost `X-Forwarded-For`, Cloudflare ranges → `CF-Connecting-IP`
- [ ] 1.10.7 Rate limits and lockout on pairing, refresh and login, keyed by client IP
- [ ] 1.10.8 Audit log for pairing, rotation anomalies, revocation
- [ ] 1.10.9 Acceptance tests: lost response + retry, weeks offline, theft locks, spoofed header ignored
- [ ] 1.10.10 Endpoint for a paired device to create a pairing code for its own user (README 9; rate limited, audit log)
- [ ] **1.10 done** · PR:

#### 1.11 Sync endpoints

*Acceptance (automated):* delta across several tables, pagination, tombstones, idempotency, concurrency, old protocol version still served, too-old app rejected.

- [ ] 1.11.1 Protocol layer: version header (current + previous), minimum app version with a clear error, latest app version and server time in every response
- [ ] 1.11.2 `GET /api/sync`: delta across all synced tables by `rev`, per-user visibility, tombstones, pagination
- [ ] 1.11.3 `POST /api/sync/push`: operation dispatcher, idempotency by op UUID, per-op result (ok / rejected / retry), timestamps corrected by clock skew; handlers for `ack` (→ `deliveries`), `device_status` and `alarm_firing` (→ `alarm_firings`); later runs register more operations
- [ ] 1.11.4 `POST /api/devices/me/fcm-token`
- [ ] 1.11.5 Admin CLI "test notification" (creates a notification; the FCM wake-up follows in 2.8)
- [ ] 1.11.6 Acceptance tests incl. concurrent pushes (`mariadb` marker)
- [ ] **1.11 done** · PR:

---

### 🤖 Run 2: Engine, push and delivery

- [ ] **Run 2 done:** all packages ticked, CI green (incl. emulator tests).
- [ ] Agent asked Martin to move `release` to `main` (issue + note in `docs/last-session.md`) and stopped for C1.

#### 2.1 Engine spec `docs/spec-engine.md`

*Acceptance (automated):* file exists (a doc test checks the required sections).

- [ ] 2.1.1 Room schema and migration policy (mirror tables dropped and re-synced; outbox, auth, sync state migrated)
- [ ] 2.1.2 Planner: sources, next-time computation, catch-up, expiry, re-plan triggers
- [ ] 2.1.3 Both alarm types, the engine setting, default until C1
- [ ] 2.1.4 Display keys → Android notification IDs; channels (versioned IDs, importance); actions
- [ ] 2.1.5 Receivers, WorkManager jobs, sync before display, one sound per firing, `alarm_firing` recording
- [ ] 2.1.6 Bridge API (functions, events, sync status) and how `repo.native.ts` uses it
- [ ] 2.1.7 Plan B `specialUse` foreground service (specified only)
- [ ] 2.1.8 Test strategy: what runs in `engine-core`, Robolectric and emulator; doc test for the required sections
- [ ] **2.1 done** · PR:

#### 2.2 `engine-core` foundation

*Acceptance (automated):* sample vector runs locally on the home server.

- [ ] 2.2.1 Gradle build for `engine-core` (pure Kotlin/JVM, `org.gradle.jvmargs=-Xmx1536m`, short daemon idle timeout), ktlint
- [ ] 2.2.2 Time provider interface and fake clock
- [ ] 2.2.3 Test-vector loader for `shared/test-vectors/` and one sample vector
- [ ] 2.2.4 Kotlin `t()` helper passing the string vectors
- [ ] 2.2.5 `make test` runs `engine-core`; CI job for `engine-core`
- [ ] 2.2.6 `engine-android` Gradle module with Robolectric in CI (one smoke test)
- [ ] **2.2 done** · PR:

#### 2.3 Sync logic and Room

*Acceptance (automated):* `engine-core` tests locally against the real dev backend; `engine-android` in CI incl. a schema change that keeps the outbox; tests: outbox survives a simulated week without server and a restart, a rejected entry does not block the following ones.

- [ ] 2.3.1 core: `SyncApi` HTTP interface and an in-memory fake for tests
- [ ] 2.3.2 core: outbox (never expires, removed only after confirmation, permanent rejection → "failed" without blocking the queue)
- [ ] 2.3.3 core: delta apply (pagination, tombstones, rev cursor); push always followed by a fetch
- [ ] 2.3.4 core: clock-skew offset and timestamp correction
- [ ] 2.3.5 core: backoff, protocol version, too-old app error, "update available"
- [ ] 2.3.6 core: sync status event (`online` / `offline` / `server_unreachable`, unsent count)
- [ ] 2.3.7 core: integration test against the real dev backend (`make dev`)
- [ ] 2.3.8 android: Room database (mirror tables incl. own `users`/`user_settings` rows, needed for quiet hours in 2.9.3 and 2.9.6; outbox, auth, sync state) with the migration policy from 2.1.1
- [ ] 2.3.9 android: token storage in the Keystore, refresh flow
- [ ] 2.3.10 android: wiring `engine-core` to Room and HTTP
- [ ] 2.3.11 Acceptance tests: week without server + restart, rejected entry does not block, schema change keeps the outbox (CI)
- [ ] **2.3 done** · PR:

#### 2.4 Planner

*Acceptance (automated):* planner vectors incl. DST and time zones, locally.

- [ ] 2.4.1 core: display entry model, stable keys (README 3.5), notification ID derivation; shown state per key + planned minute (a display moved to a new time is shown again)
- [ ] 2.4.2 core: next time over all sources present so far (scheduled server notifications, test displays; later runs add sources)
- [ ] 2.4.3 core: everything due, catch-up marked "late", expired entries discarded
- [ ] 2.4.4 Planner vectors in `shared/test-vectors/` incl. DST and time-zone changes
- [ ] 2.4.5 android: alarm scheduler with `setAlarmClock` and `setExactAndAllowWhileIdle`, switchable via engine setting (changeable on a real phone without a rebuild, needed for the C1 comparison); until C1: `setAlarmClock` for high priority, otherwise `setExactAndAllowWhileIdle`
- [ ] **2.4 done** · PR:

#### 2.5 Display, receivers, WorkManager

*Acceptance (automated):* emulator: display after forced Doze, after reboot, after time zone change, without network.

- [ ] 2.5.1 Channels with versioned IDs and importances, created on start
- [ ] 2.5.2 Posting displays by key, `shown_at` stored, ack into the outbox
- [ ] 2.5.3 Alarm receiver: **sync before display** (5 s timeout) → show everything due → re-plan
- [ ] 2.5.4 **One sound per alarm firing** (priority order README 3.3), the rest silent
- [ ] 2.5.5 Boot, time/time zone change and app update receivers → re-plan and catch up
- [ ] 2.5.6 WorkManager periodic sync (15 min)
- [ ] 2.5.7 Record every alarm firing (alarm type, idle, network, sync result and duration) → outbox op `alarm_firing`
- [ ] 2.5.8 Report notification permission and channel importance with each sync (`device_status`)
- [ ] 2.5.9 Config plugins: receivers and permissions (`USE_EXACT_ALARM`, `POST_NOTIFICATIONS`, `RECEIVE_BOOT_COMPLETED`; plus `SCHEDULE_EXACT_ALARM` with `maxSdkVersion` 32 if `minSdk` < 33)
- [ ] 2.5.10 Emulator tests: forced Doze, reboot, time zone change, no network
- [ ] **2.5 done** · PR:

#### 2.6 Bridge, pairing, setup flow

*Acceptance (automated):* emulator: pairing against dev backend, status visible.

- [ ] 2.6.1 Bridge functions and events (pair, sync status, delivery status) and `data/repo.ts` + `repo.native.ts` for them
- [ ] 2.6.2 Pairing screen
- [ ] 2.6.3 Raw "Delivery" screen (status list)
- [ ] 2.6.4 Setup flow: notification permission, exact alarms (`USE_EXACT_ALARM`), battery optimization, Samsung hints, auto-revoke
- [ ] 2.6.5 All texts in `de.json`; screens use base components and semantic tokens
- [ ] 2.6.6 Emulator test: pairing against the dev backend, status visible
- [ ] 2.6.7 Show a pairing code for a new device of the same user (endpoint 1.10.10)
- [ ] **2.6 done** · PR:

#### 2.7 Worker and job locks

*Acceptance (automated):* two worker instances in a test, job runs once.

- [ ] 2.7.1 APScheduler in the worker with a job registry
- [ ] 2.7.2 DB lock per job via `db/locks.py` against double execution
- [ ] 2.7.3 `job_log` entries (start, end, duration, error)
- [ ] 2.7.4 Acceptance test: two worker instances, job runs once (SQLite locally, MariaDB in CI)
- [ ] 2.7.5 Worker heartbeat (every minute); its age in every sync response
- [ ] **2.7 done** · PR:

#### 2.8 FCM (needs M1)

*Acceptance (automated):* fake FCM records the wake-up; optionally real delivery in the emulator via dev Firebase (M2).

- [ ] 2.8.1 Sender interface: real (`firebase-admin`, service account from the secret store) and fake (`dev/fake-fcm`)
- [ ] 2.8.2 Data message `{"t":"sync"}`, TTL, **priority rule** as a pure function (high only when a display is expected now, incl. watchdog retries that lead to a late display; otherwise normal + `collapse_key`) with tests
- [ ] 2.8.3 Token maintenance: invalid/unregistered tokens marked, devices without a valid token visible
- [ ] 2.8.4 Wake-ups on new notifications and status changes; FCM dry-run credential check in the wizard (1.9.3); real test push via admin CLI (1.11.5) and admin UI → Tools (2.11.5)
- [ ] 2.8.5 App: `google-services.json`, FCM config plugin, `FirebaseMessagingService` → sync, `onNewToken` → `POST /api/devices/me/fcm-token`
- [ ] 2.8.6 **Silent re-post** when a high-priority wake-up brings nothing new (logic in `engine-core`, posting in `engine-android`)
- [ ] 2.8.7 Acceptance tests with fake FCM; optional real delivery via dev Firebase
- [ ] **2.8 done** · PR:

#### 2.9 Watchdog and heartbeat

*Acceptance (automated):* time-controlled backend tests with a fast-forwarded clock; engine-core test: no notification while offline.

Do 2.9.5 (quiet-hours function) first; 2.9.2 and 2.9.3 depend on it.

- [ ] 2.9.1 Watchdog job (every minute): server notifications without ack → wake-ups after 2, 10, 60 min, then "not delivered"
- [ ] 2.9.2 Device without sync for > 6 h outside quiet hours → notice to the other person and in the admin UI (needs the quiet-hours function from 2.9.5)
- [ ] 2.9.3 Engine: "Server nicht erreichbar" system notification (network available, sync failing for 3 h outside quiet hours, once then after 24 h; the extra sentence about urgent todos in the outbox follows in 3.8, when todos exist)
- [ ] 2.9.4 Acceptance tests: backend with fast-forwarded clock; `engine-core`: no notification while offline
- [ ] 2.9.5 Quiet-hours function (per weekday, crossing midnight belongs to the start day) in Python and `engine-core`, with first vectors in `shared/test-vectors/`; 3.1 extends the vectors, 3.7 adds TS
- [ ] 2.9.6 Engine: "worker down" system notification when the heartbeat age in sync responses is > 15 min outside quiet hours (once, then after 24 h); acceptance test with fake clock
- [ ] **2.9 done** · PR:

#### 2.10 "Delivery" screen complete

*Acceptance (automated):* emulator test of the checks.

- [ ] 2.10.1 All checks from README 3.8 via the bridge
- [ ] 2.10.2 Buttons that open the matching system settings
- [ ] 2.10.3 Local test notification in 10 s and server test wake-up
- [ ] 2.10.4 Delay statistics for the last 50 displays
- [ ] 2.10.5 Emulator test of the checks
- [ ] **2.10 done** · PR:

#### 2.11 Admin UI: delivery, devices

*Acceptance (automated):* page tests (htmx endpoints).

- [ ] 2.11.1 Admin layout and navigation on top of the 1.9 login
- [ ] 2.11.2 Devices page: last sync, app version, FCM token status, generate pairing code, lock device
- [ ] 2.11.3 Delivery page: status per notification and device, delay, watchdog retries
- [ ] 2.11.4 Page tests for the htmx endpoints
- [ ] 2.11.5 Tools page: test push / test notification to a chosen device
- [ ] **2.11 done** · PR:

#### 2.12 Observation job

*Acceptance (automated):* job test with fast-forwarded clock; backend test: `alarm_firing` ops stored and aggregated.

- [ ] 2.12.1 Aggregation queries over `alarm_firings` (table and op handler exist since 1.7.5 / 1.11.3)
- [ ] 2.12.2 Observation job: test notifications to both users several times a day; on/off switch
- [ ] 2.12.3 **Device-planned test displays** (scheduled server notifications shown via the device's own alarm, also at likely-idle times)
- [ ] 2.12.4 Admin evaluation: delivery rate, delay median/p95, **pre-display sync success per device, alarm type and idle state**, sync duration median/p95
- [ ] 2.12.5 Acceptance tests
- [ ] **2.12 done** · PR:

#### 2.13 Checklist `docs/checkpoint-c1.md`

*Acceptance (automated):* file exists.

- [ ] 2.13.1 Step-by-step guide for C1 (below), written as checkboxes, incl. the hardware test list and the alarm-type decision criteria
- [ ] 2.13.2 Bump `app/version.json`; open the issue asking Martin to move `release`
- [ ] **2.13 done** · PR:

---

### 👤 C1: First deployment (about 2–3 h + one week in the background)

The agent provides an exact step-by-step guide in `docs/checkpoint-c1.md`.

- [ ] C1.1 Coolify has deployed the `release` state and `/api/health` responds
- [ ] C1.2 **Setup wizard** on the admin subdomain: admin account + TOTP, upload Firebase service account (dry-run check), create second account
- [ ] C1.3 **APK installed on both phones**, paired with a pairing code, setup flow done (incl. Samsung battery settings)
- [ ] C1.4 Test push from admin UI → Tools to both phones arrives; "Delivery" on both devices: everything green
- [ ] C1.5 **Hardware tests** the emulator does not cover (list in the checkpoint document), among them:
  - [ ] natural Doze: phone untouched for 2 h
  - [ ] Samsung-specific behavior, app reinstalled
  - [ ] real FCM latency on mobile networks
  - [ ] **alarm type decided**: a few days with each (`setAlarmClock` vs `setExactAndAllowWhileIdle`), status-bar icon, lock screen/watch "next alarm" and DND schedules checked, **pre-display sync success** in the admin UI (idle firings with network: target ≥ 95 % `ok`). Default set after the observation week; if `setExactAndAllowWhileIdle` wins but misses the sync target, fallback chosen (decisions section 11: `setAlarmClock` only for nag/reminder alarms, accept stale nags, or change the timeout)
- [ ] C1.6 **Observation job switched on.** It runs for a week while Run 3 is already working; Martin checks the admin UI now and then
- [ ] C1.7 Anything unusual filed as a GitHub issue; assumptions in `docs/assumptions.md` reviewed

**Done when:** both phones are paired, hardware tests done or filed as issues, observation running. Run 3 can start.

---

### 🤖 Run 3: Todos, nagging, series

Open issues from C1 take priority over new packages.

- [ ] **Run 3 done:** all packages ticked, CI green.
- [ ] Agent asked Martin to move `release` to `main` and reported C2. The session ends; Martin starts Run 4 with a new session (`/next`) whenever he likes (C2 blocks nothing).

- [ ] **3.0** Break 3.1–3.13 into sub-tasks in this file (same format as Runs 1 and 2)
- [ ] **3.1** Spec `docs/spec-todos.md`, test vectors for levels (incl. `due_soon`, end-of-day downgrade of explicit urgent via `urgent_downgrade_at`, also for "both"), quiet hours per weekday, **modes** (effective mode, manual end, schedule, `dnd` catch-up), per-user intervals, nag window, overdue slots, snooze (2 Std./Bis morgen, combined), nag times, rotation, RRULE, conflicts; edge cases: level boundaries (exactly 1 / 4 weeks), the "interval" of calendar-rule series for relative thresholds; display keys for batched activity, quiet-hours catch-up without summary and `dnd` catch-up (added to README 3.5) · PR:
  *Acceptance:* vectors exist and load in all three languages
- [ ] **3.2** Backend: migrations (`people`, `categories`, `todos` incl. `lead_time`, `urgent_sent_at` and server-computed `urgent_downgrade_at`, `mode_changes`, `todo_series` incl. `replace_open`, `todo_snoozes` incl. combined snooze, `todo_claims`, `activity_events`; `user_settings` extended with mode, mode end, mode schedule and all per-user intervals), seed data, **activity events written for every todo action** (push, REST, worker), sync operations, conflict logic per field group, conflict log · PR:
  *Acceptance:* conflict scenarios (completed offline + title changed, delete vs. edit, clock skew)
- [ ] **3.3** Backend: activity notifications (only: new todo for me/both; completed/dismissed for me/both or created by me; "Mach ich" on my urgent todo) with batching and collection until the first summary, explicit urgent incl. the night special case, claims, per-recipient delivery status for the sender, each user's next nag window start computed and synced to the other user (sender hint), wake-up on status change of nagging todos, **mode-aware** sending (no display expected → normal priority) · PR:
  *Acceptance:* tests with fast-forwarded clock; edits/deletions do not notify
- [ ] **3.4** Design system: final semantic token set in `shared/design/tokens.json` (light/dark), base components, navigation, `repo.ts` + `repo.native.ts`; a hidden "design preview" screen showing all base components and tokens · PR:
  *Acceptance:* component tests, screenshot tests in the emulator (light/dark)
- [ ] **3.5** Engine: Room tables and sync for todos, people, categories, series, snoozes, settings; bridge functions · PR:
  *Acceptance:* JVM tests
- [ ] **3.6** App: settings (quiet hours per weekday, summary times per weekday, **all per-user intervals** with ranges, DND bypass, theme), **mode switch** with end (1 Std. / Bis morgen / Bis ich es ausschalte), **weekly mode schedule**, mode banner, recipient's mode and quiet-hours hint ("Ruhezeit bis …") shown when sending urgent · PR:
  *Acceptance:* emulator: change a setting → second test client sees it
- [ ] **3.7** App: todo list (all todos visible, filters mine/both/other's), detail, create/edit (scheduled with optional lead time), complete, dismiss, reopen, postpone (incl. "Morgen"/"+3 Tage", scheduled todos; not offered for explicit urgent), "send urgent" with delivery status ("Zugestellt"/"Mach ich"), level computation in TS; **offline banner** on every screen while sync fails (base component, text from `de.json`, unsent count); **"Noch nicht gesendet" marker** on todos with unconfirmed changes (prominent for urgent todos sent to the other person); "failed" state with retry/discard · PR:
  *Acceptance:* E2E in the emulator: backend stopped → banner visible while editing, change kept; backend back → change synced, banner and marker gone; urgent todo sent while backend is down shows the prominent marker
- [ ] **3.8** **Engine II:** summaries (incl. `due_soon` and the quiet-hours catch-up in the first summary), scheduled reminders (lead time, at `due_at`), nagging (explicit per todo incl. "Mach ich"; overdue as **one combined notification per user** at the computed slots), nag window, quiet hours, **modes** (`remind` / `essentials` / `dnd`, schedule, `dnd` catch-up), snooze (30 min / 2 Std. / Bis morgen, combined), DND bypass (second urgent channel), "Server nicht erreichbar" extra sentence for urgent todos in the outbox, actions from the notification incl. 30 s undo · PR:
  *Acceptance:* planner vectors; emulator: "Done" action without the app open stops nagging, undo restores it
- [ ] **3.9** Watchdog for all device-planned displays (summaries, nags, scheduled reminders; calendar in 4.5): server computes expected keys with the shared vectors (mode-aware, using the mode valid at the planned time), delivery records per key + planned minute, server notifications expected only when the device will display them (not while batched, collected for the first summary or suppressed by the mode), retries with high priority when a late display follows (decisions section 4) · PR:
  *Acceptance:* backend test with fast-forwarded clock
- [ ] **3.10** Series: UI with pickers, RRULE in the client, validation and instance creation in the worker, rotation, dismissed rule, `replace_open` (default on for calendar rules), relative level thresholds, reopen removes untouched next instance, edit/pause/delete rules · PR:
  *Acceptance:* vectors (incl. relative thresholds); "every 2 weeks, rotating" and "every 1st Monday" as E2E
- [ ] **3.11** **Activity view** "Aktivität": list, filters (person, type, todo), tap opens todo, "nachträglich synchronisiert" marker, 90-day local window + server paging; engine: Room table and sync for `activity_events` · PR:
  *Acceptance:* E2E: complete, snooze, postpone on device A → events with actor and time on device B; offline action shows the marker after sync
- [ ] **3.12** Screenshots of all screens (light and dark) as CI artifact, checklist `docs/checkpoint-c2.md`, bump `app/version.json` · PR:
  *Acceptance:* artifact exists
- [ ] **3.13** Apply the alarm-type decision from C1 (default and, if chosen, the fallback from decisions section 11) in the engine setting; remove the interim rule · PR:
  *Acceptance:* engine test for the chosen default; if C1 is not decided yet, mark ⏸ and continue

---

### 👤 C2: Daily-use test and design review (about 1–2 h, in parallel with Run 4)

- [ ] C2.1 App update installed on both phones
- [ ] C2.2 **Design** reviewed from the screenshots, the design preview screen and on the device; **wording** in `shared/strings/de.json` reviewed. Change requests filed as issues ("colors", "spacing", "wording" …) or the two files edited directly
- [ ] C2.3 **Tested together with his wife** (list in `docs/checkpoint-c2.md`):
  - [ ] urgent todos back and forth, nagging, "Snooze", "Done" on one device stops the other
  - [ ] send to "both"
  - [ ] send in the evening → one notification, nagging from the first summary
  - [ ] "Mach ich", snooze "2 Std." / "Bis morgen", sender sees "Zugestellt"
  - [ ] modes: "Nur Wichtiges" (urgent shows once), "Nicht stören" until a time (nothing, then one catch-up), a weekly mode slot; sender sees the recipient's mode
  - [ ] activity view: actions of the other person appear with name and time
  - [ ] "Nerv-Level" statistics in the admin UI: notifications per day feel right, no channel muted
  - [ ] summaries watched for a few days
  - [ ] one recurring task with rotation
- [ ] C2.4 Observation week result checked in the admin UI: target 100 % shown, 95 % within 60 s
- [ ] C2.5 Problems filed as issues

---

### 🤖 Run 4: Calendar, web, admin, wrap-up

Issues from C2 take priority.

- [ ] **Run 4 done:** all packages ticked, CI green.
- [ ] Agent asked Martin to move `release` to `main` and stopped for C3.

- [ ] **4.0** Break 4.1–4.10 into sub-tasks in this file (same format as Runs 1 and 2)
- [ ] **4.1** Fake Google Calendar with fixtures (recurring, all-day, changed, deleted events, `410 Gone`) · PR:
  *Acceptance:* fake runs in `make dev`
- [ ] **4.2** `CalendarSource` + `google_api` (incremental, rebuild; window applied server-side because `syncToken` excludes `timeMin`/`timeMax`), fetch job, `calendar_sources`, `calendar_events`, rev sync (device window −1 to +3 months) · PR:
  *Acceptance:* tests against the fake
- [ ] **4.3** Admin UI → Settings (not the wizard, which is locked by then): enter OAuth client, Google login, choose calendars, color, "notify: user A/B", test fetch, warning on expired token · PR:
  *Acceptance:* E2E against the fake (OAuth flow mocked)
- [ ] **4.4** App: agenda, week and month views, toggle sources · PR:
  *Acceptance:* emulator E2E
- [ ] **4.5** Engine: calendar notifications (evening before, morning, start, all-day, quiet-hours rule), events in summaries; watchdog for calendar keys · PR:
  *Acceptance:* planner vectors; backend watchdog test
- [ ] **4.6** Add appointment → todo in "calendar" category, action "Open in calendar app" · PR:
  *Acceptance:* emulator: intent is fired
- [ ] **4.7** Web: `repo.web.ts`, REST endpoints, hide native areas, offline banner + edit lock when the server is unreachable, build into the backend image · PR:
  *Acceptance:* Playwright E2E against dev backend, incl. backend stopped → banner, editing blocked
- [ ] **4.8** Web login: password → approval in the app (code + yes/no) → session, recovery codes, admin reset, CSRF, `SameSite=Lax` cookie, 30 days, session list · PR:
  *Acceptance:* E2E: browser (Playwright) + emulator approves
- [ ] **4.9** Admin UI complete (activity page reads `activity_events`; current mode per user): statistics (incl. "Nerv-Level": notifications per user/day by class, snooze/postpone/claim counts, muted-channel warning from `device_status`), activity, conflicts, logs, settings (incl. per-user defaults and level thresholds), tools · PR:
  *Acceptance:* page tests
- [ ] **4.10** One-page quick guide for Martin's wife (German), checklist `docs/checkpoint-c3.md`, bump `app/version.json` · PR:
  *Acceptance:* files exist

---

### 👤 C3: Wrap-up (about 2–3 h)

- [ ] C3.1 App update installed on both phones
- [ ] C3.2 **Google integration in the admin UI:** OAuth client ID/secret entered, signed in with Martin's Google account, the three calendars selected and assigned (Martin's → Martin, his wife's → his wife, shared → both), test fetch done
- [ ] C3.3 Events checked on both phones; an event changed in Google arrives within 5 min
- [ ] C3.4 **Web login** set up and tested for both (approval on the phone); recovery codes stored safely
- [ ] C3.5 Full pass through the hardware test matrix (list in the checkpoint document)
- [ ] C3.6 **Coolify DB backups switched on**
- [ ] C3.7 Quick guide gone through with his wife; observation job switched off
- [ ] C3.8 **GitHub repo made private again** (Settings → General → Danger Zone); signing secrets moved to repo secrets and the release workflow switched (`docs/release-signing.md`); the agent rule "merge only when `ci-gate` is green" applies from now on (A4); Actions usage and the minute-saving rules in A6 checked. **Going private on Free silently switches off** (nothing to undo by hand, but know it): the `main` ruleset (still listed, no longer enforced, incl. its squash-only rule), the Environment `release` with its required reviewer, secret-scanning push protection, and auto-merge (agents wait for `ci-gate` instead). Check that Settings → General → Pull Requests allows **only squash merging**, so squash-only survives without the ruleset.
- [ ] **MVP done:** two weeks of daily use without a lost notification

---

### 🔁 Afterwards: bug loop and more features

- Martin files bugs or wishes as GitHub issues (template: what happened, what was expected, which device, approximate time). An agent works through issues one by one under the same rules (Part A).
- Martin moves `release` when he wants an update; the agent bumps `app/version.json` in a PR first.
- More features, each as its own run with a short checkpoint, tracked here with checkboxes and sub-tasks like Runs 1 and 2:
  - [ ] Backups: retention, external copy, **restore test** (Martin, because it involves production data)
  - [ ] Shopping list
  - [ ] Notebook
  - [ ] Finances / household budget
  - [ ] CalDAV instead of Google, incl. writing

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
| C0 preparation | 30 min | – |
| M-tasks (in parallel with Runs 1–4) | about 3 h | – |
| Run 1 + 2 | – | biggest block (backend core, engine) |
| C1 | 2–3 h + observation week in the background | – |
| Run 3 | – | large block (todos, engine II, series) |
| C2 | 1–2 h + daily use | Run 4 runs in parallel |
| Run 4 | – | medium block |
| C3 | 2–3 h | – |
| **Total for Martin** | **about 10–14 h** plus daily-use tests | |

How long the runs take depends on how long an agent can work in one go. Work packages are sized so each fits in one session, sub-tasks so each fits in a fraction of one, and the next agent continues seamlessly from the first unticked sub-task (handover in `docs/last-session.md`).

---

## Part E: Risks

| Risk | Mitigation |
|---|---|
| Emulator tests do not reproduce Samsung or real Doze | hardware list at C1/C3, observation job, watchdog, "device without sync" notice; plan B foreground service |
| Doze throttles `setExactAndAllowWhileIdle` (about once per 9 min per app) | single-alarm planner, `setAlarmClock` for high priority |
| An agent makes an assumption Martin wants differently | `docs/assumptions.md`, review at every checkpoint, correction via issue |
| Agent code drifts from the architecture | `AGENTS.md`, specs before code, CI with architecture checks (e.g. no DB access from JS) |
| Logic diverges across three languages | shared test vectors |
| A broken state reaches production | deploy only from `release`, which Martin moves at checkpoints |
| Signing key lost | back it up twice when creating it (M3, e.g. password manager + offline copy) |
| Expo/React Native updates break the module | update the SDK deliberately only, as its own issue |
| Google token expires | warning in the admin UI + notification to Martin, re-login via the admin UI |
| CI minutes run out | home-server packages first, batch Android work; public repo or self-hosted runner as fallback |
| Data loss before the backup phase | Coolify backups at C3 (accepted: C2/Run 4 data unprotected until then) |
| Device locked by refresh-token rotation | generous reuse rule: previous token valid until the new one is used |
| FCM deprioritizes high-priority messages without visible notifications | high priority only when a display is expected |
| Server down unnoticed | device shows "server unreachable" after 3 h of failing syncs with network |
| Worker down while the API runs | worker heartbeat in sync responses, device notification after 15 min (2.9.6) |
| New server breaks old app versions | protocol version header, previous version supported, minimum app version, update notice |
| Cloudflare Access bypassed via public VPS IP | backend validates the Access JWT on the admin host |
| Repo forgotten as public | reminder in the C3 checklist |
| After C3 no GitHub-enforced protection (private repo on Free) | agents merge only on green `ci-gate` (`AGENTS.md`); release workflow triggers only on `release` |
| Release built without a version bump | release workflow fails unless `versionCode` is higher than the last release |
