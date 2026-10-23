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
