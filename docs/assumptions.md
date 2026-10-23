# Assumptions

Decisions agents made without asking. Martin reviews them at every checkpoint. Anything he wants changed is filed as an issue.

| Date | Package | Assumption | Reason | Reviewed |
|---|---|---|---|---|
| 2026-10-23 | planning review | Two urgent channels (with and without DND bypass); the engine picks one per display | Android apps cannot change a channel's bypass flag after creation, but bypass is a per-user toggle and the quiet-hours exception must not bypass | |
| 2026-10-23 | planning review | `/api/health` is ready when the DB is at the code's head revision or a descendant of it | Otherwise the previous image reports 503 after a migration, which breaks rollback by redeploy (decisions section 10) | 2026-10-23: replaced by decisions 10 (unknown revision = newer) |
| 2026-10-23 | planning review | Pairing codes are bound to one user; a paired device creates codes only for its own user (1.10.10, 2.6.7) | README 9 allows codes from a paired device; device replacement is the use case | |
| 2026-10-23 | planning review | App version defined once in the repo, read by the release APK build and by the backend as "latest app version"; `versionCode` strictly increasing; signed APK attached to a GitHub Release (1.2.9) | Server and APK are built from the same `release` commit; updates need a higher `versionCode` | 2026-10-23: replaced by decisions 10 (`app/version.json`) |
| 2026-10-23 | planning review | 🚧 claims are made visible by opening a draft PR right after the first commit | `main` only changes through PRs, so a marker on a branch is invisible otherwise | |
| 2026-10-23 | planning review | Quiet-hours function and first vectors move forward to Run 2 (2.9.5); `user_settings` gets quiet hours in 1.7.3 | Heartbeat and "Server nicht erreichbar" (2.9) depend on quiet hours | |
| 2026-10-23 | planning review | `todos.urgent_sent_at` and `todos.lead_time` columns | 15-min rhythm and end-of-day downgrade count from the send time, which can differ from `created_at`; lead time is per todo | |
| 2026-10-23 | planning review | Google OAuth client and calendar login live in admin UI → Settings (C3), not in the wizard | The wizard locks at C1; README 10, M8 and 4.3 already planned it this way | |
| 2026-10-23 | planning review | Overdue slot midpoints are rounded half up to 5 min | Required by the worked example (14:07:30 → 14:10, 17:22:30 → 17:25) | |
| 2026-10-23 | planning review | String vectors live in the folder `shared/test-vectors/strings/` | BUILDPLAN 1.1.10 wins over README 8.4 (`strings.json`) | |
