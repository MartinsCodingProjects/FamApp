# Session history

Archive of every `docs/last-session.md`, newest first. Written only by `tools/session-end.sh`; agents do not need to read it.

<!-- entries below, newest first -->

## Session 2026-10-24 05:35 – Run 1: foundation and backend core

**Run / section:** Run 1
**Finished:** 1.1 (#2, #4), 1.2 (#5, #6), 1.3 (#7), 1.4 (#8), 1.5 (#9), 1.6 (#10), 1.7 (#11), 1.8 (#12), 1.9 (#13), 1.10 (#14), 1.11 (#15); Run 1 ticked
**In progress:** –
**Stopped because:** run done
**Next:** Agents: Run 2, sub-task 2.1.1 (new session, `/next`). Martin: M1 before 2.8 (#16); reviews below.

### Summary

- Repo scaffold, Makefile, lint (Ruff, ESLint, ktlint, actionlint+shellcheck, token/string/architecture checks), CI with change detection and `ci-gate`; emulator, MariaDB, image smoke, Playwright and APK jobs all green.
- Backend: config, JSON logs, host-separated app/admin surfaces, Cloudflare Access check, health + schema check, worker with migrations under lock, Alembic migrations 0001–0005, `next_rev()`, AES-GCM secret store, setup wizard + admin login (TOTP), device auth with the reuse rule, sync endpoints per `docs/spec-sync.md`.
- App: Expo SDK 58 project, local engine module (`engine-core` sources compiled into `engine-android`), `t()`, ThemeProvider, start screen; Maestro E2E in the emulator.
- Specs written: `docs/spec-backend-skeleton.md`, `docs/spec-sync.md`, `docs/spec-setup-wizard.md`, `docs/spec-device-auth.md`; `docs/release-signing.md` (input for M3), `deploy/cloudflare.md` (input for M4).
- 75 new rows in `docs/assumptions.md` (all dated 2026-10-24).

### Needs Martin (review / decision)

- **PATH:** `make`, `java` and `fnm` are installed in `~/.local/bin` (`tools/install-user-tools.sh`); the agent was not allowed to edit `~/.bashrc`, so please add `export PATH="$HOME/.local/bin:$PATH"` yourself.
- **M1** (Firebase, `app/google-services.json`) before Run 2 reaches 2.8: #16.
- Review the assumption rows of 2026-10-24, especially: wizard texts (`admin.*` in `de.json`, 1.9), the dated npm audit exceptions in `tools/audit-allowlist.txt` (node-forge, zod via `@expo/cli`, expire 2027-01-24), the sync wire format (1.6), placeholder branding "FamApp".
- Still open from the planning session: sub-tasks 1.2.7, 1.2.10, 1.4.12, C0.3 were kept and are now built.
- M3/M4/M5 can start: `docs/release-signing.md`, `deploy/cloudflare.md`, formats for `MASTER_KEY`/`SETUP_TOKEN` in M5.

### Went wrong / watch out

- The home server cannot run Playwright browsers (missing system libraries, no root): `make e2e` only runs in CI/notebook; there is a pytest flow test for fast local feedback.
- Alembic autogenerate writes `drop_index` before `drop_table` in downgrades; MariaDB refuses that for FK indexes. Downgrades drop the tables only (see migrations 0002–0005).
- Ruff needs `known-first-party = ["app"]` because the Expo folder at the repo root is also called `app/`.
- Starlette recommends `httpx2`; the backend uses it instead of `httpx`.
- `make` exists only in `~/.local/bin`; agents prefix commands with `export PATH="$HOME/.local/bin:$PATH"` until Martin sets it.

### Open blockers

| Since | Item | Blocked by | Issue |
|---|---|---|---|
| 2026-10-24 | 2.8 (FCM) | M1: Firebase project, `google-services.json` | #16 |

---

## Session 2026-10-23 18:00 – planning: pre-Run-1 review and decisions

**Run / section:** C0 preparation (no code yet)
**Finished:** final docs review; four decisions applied (no package or sub-task of Runs 1–4 started)
**In progress:** –
**Stopped because:** planning done, waiting for C0
**Next:** Martin: C0.1b, C0.2 (then M1, due before 2.8) · Agents: sub-task 1.1.1 once C0.1b and C0.2 are ticked

### Summary

- Stale wording aligned (notification actions, FCM priority, "active time", heartbeat vs. "device without sync", calendar quiet-hours rule, test-vector list, README 12 layout).
- Order fixes: `alarm_firings` table/handler moved to 1.7.5 / 1.11.3; own `user_settings` mirrored in 2.3.8; `next_rev()` inside the writing transaction (1.7.1).
- Decided by Martin (decisions 10/11/12): private on GitHub Free after C3 (signing key → repo secret, agents merge only on green `ci-gate`); `/api/health` treats an unknown Alembic revision as newer; app version in `app/version.json`, bumped at run end; shown/delivery state per key + planned minute; server-computed `urgent_downgrade_at`; "worker down" shown in `essentials`.
- README 6 lists the remaining tables (`pairing_codes`, `recovery_codes`, `processed_ops`, `mode_changes`, `worker_heartbeat`).

### Needs Martin (review / decision)

- none new (still open: review of the assumptions rows, sub-tasks 1.2.7, 1.2.10, 1.4.12, C0.3)

### Went wrong / watch out

- none

### Open blockers

| Since | Item | Blocked by | Issue |
|---|---|---|---|
| 2026-10-23 | Run 1 | C0.1b, C0.2 | – |

---

## Session 2026-10-23 16:30 – planning: final consistency review

**Run / section:** C0 preparation (no code yet)
**Finished:** consistency review of AGENTS, README, BUILDPLAN, decisions, assumptions (no package or sub-task of Runs 1–4 started)
**In progress:** –
**Stopped because:** planning done, waiting for C0
**Next:** Martin: C0.1b (repo is still private; ruleset with 0 required approvals), C0.2 (then M1, due before 2.8) · Agents: sub-task 1.1.1 once C0.1b and C0.2 are ticked

### Summary

- Stale wording in decisions sections 5/6/9 aligned with sections 11/12; README, BUILDPLAN and AGENTS aligned with decisions. BUILDPLAN A5 now points to README 12 instead of duplicating it.
- AGENTS precedence split: behavior → decisions ✅ > README > decisions 🟡 > BUILDPLAN; process/sequence/status → BUILDPLAN first. End-of-run behavior follows the run lines in BUILDPLAN; 🚧 claims via draft PRs.
- Decided by Martin today: wizard checks Firebase with an FCM dry run (real test push via admin Tools, 2.11.5); worker heartbeat in sync responses + device notification (2.7.5, 2.9.6); server computes the recipient's next nag window start for the sender hint; explicit urgent todos cannot be postponed; watchdog retries that lead to a late display use high priority; session cookie `SameSite=Lax`.
- New sub-tasks: 1.10.10 / 2.6.7 (pairing code from a paired device), 2.9.5 (quiet-hours function moved forward), 3.13 (apply the C1 alarm-type decision); 1.2.9 extended (versionCode, single app version, GitHub Release).
- Agent choices recorded in `docs/assumptions.md` (10 entries dated 2026-10-23, package "planning review").

### Needs Martin (review / decision)

- Review the 10 new rows in `docs/assumptions.md`.
- Still open from the previous session: new sub-tasks 1.2.7, 1.2.10, 1.4.12, C0.3 – drop any you don't want.

### Went wrong / watch out

- none

### Open blockers

| Since | Item | Blocked by | Issue |
|---|---|---|---|
| 2026-10-23 | Run 1 | C0.1b, C0.2 | – |

---

## Session 2026-10-23 14:53 – planning: tracking and session handover

**Run / section:** C0 preparation (no code yet)
**Finished:** build plan restructured (no package or sub-task of Runs 1–4 started)
**In progress:** –
**Stopped because:** planning done, waiting for C0
**Next:** Martin: C0.1b, C0.2 (then M1, due before 2.8) · Agents: sub-task 1.1.1 once C0.1b and C0.2 are ticked

### Summary

- C0 reduced to what blocks Run 1; everything else moved to M-tasks M1–M9, done in parallel.
- BUILDPLAN Part B: checkboxes for every step; Runs 1 and 2 broken into sub-tasks; Runs 3 and 4 get theirs in 3.0 / 4.0.
- Status lives only in the BUILDPLAN checkboxes. `docs/progress.md` replaced by this file + `docs/session-history.md` (`tools/session-end.sh`).

### Needs Martin (review / decision)

- New sub-tasks not in the old tables: 1.2.7 architecture checks, 1.2.10 `docs/release-signing.md`, 1.4.12 `deploy/cloudflare.md`, C0.3 agent confirms repo access. Drop any you don't want.

### Went wrong / watch out

- none

### Open blockers

| Since | Item | Blocked by | Issue |
|---|---|---|---|
| 2026-10-23 | Run 1 | C0.1b, C0.2 | – |

---
