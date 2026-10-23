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
