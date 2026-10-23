# Session history

Archive of every `docs/last-session.md`, newest first. Written only by `tools/session-end.sh`; agents do not need to read it.

<!-- entries below, newest first -->

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
