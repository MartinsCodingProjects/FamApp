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
- ~60 new rows in `docs/assumptions.md` (all dated 2026-10-24).

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
