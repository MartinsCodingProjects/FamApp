# Decisions

Status: 2026-10-22, all planning questions resolved (translated to English and codename changed to `famapp` on 2026-10-23). This document records what was decided and why. README and BUILDPLAN build on it.

Legend: ✅ decided by Martin · 🟡 proposal; implemented this way unless someone objects

---

## 1. Platform and devices

- ✅ Both devices are Android: one Samsung, one Pixel.
- ✅ Devices get replaced now and then. All state lives on the server. A new device is registered with a pairing code, fetches everything via sync and re-plans its alarms. Old devices can be signed out (token revoked).
- ✅ No iOS support planned, but the architecture does not rule it out.
- ✅ Additional **web access** from the same codebase (Expo Web), without native features, **for both users**.

## 2. Frontend

- ✅ Expo (managed workflow with development build), JavaScript instead of TypeScript to start with.
- ✅ Styling via `StyleSheet`, no CSS.
- ✅ **Design must be easy to change; design tokens adjustable in one place.**
  - 🟡 `theme/tokens.js` (colors, spacing, radii, font sizes, shadows) as the single source. Components never use hard-coded values, only tokens.
  - 🟡 Small set of own base components (`Button`, `Card`, `Text`, `Input`, `Badge`) that use tokens only. A redesign only touches tokens and these components.
- ✅ **Light and dark:** follows the system by default, changeable per user in the app (System / Light / Dark). Technically two token sets via a theme provider; the choice is synced with the user settings.
- ✅ **App name not decided yet.** Hence two levels:
  - **Display name** (what users see: app icon, title, notifications, web, admin UI) lives in **one** place: `branding.json` in the repo root. Expo (`app.config.js`), backend, admin templates and texts read it from there. Renaming = change one line and rebuild.
  - **Technical identifiers** (Android package `com.cowflex.famapp`, module names, folders, DB names, channel IDs) use the fixed codename `famapp` and are **never** changed. The package name cannot change after installation without Android treating it as a new app (data lost, re-pairing), and `google-services.json` is bound to it.
- ✅ **Notification engine and local data storage as a native Kotlin module** (local Expo module). See "App architecture".
- ✅ **Expo Web:** the same app runs in the browser.
  - 🟡 Native parts (engine, alarms, push, offline) are missing on web. The app checks `Platform.OS` and hides those areas (e.g. "Delivery").
  - 🟡 Web needs a password login. The Android app keeps pairing code + device token.
  - 🟡 Web is online only.
- ✅ **Language:** development (code, docs, specs, commits) in English (decided 2026-10-23).
  - 🟡 User-facing text in app, web and admin UI stays German, kept in one strings file per surface.

## 3. Backend and operations

- ✅ FastAPI, Python 3.12+, SQLAlchemy 2 + Alembic, Pydantic v2, APScheduler, `firebase-admin`.
- ✅ **Database:** MariaDB in production. **SQLite for development** and the first test runs on the home server; switching via `DATABASE_URL`. CI additionally runs all backend tests against MariaDB. Portability rules: BUILDPLAN A7.
- ✅ Deployment via Coolify (Docker Compose resource; Traefik and certificates from Coolify). MariaDB as a Coolify resource, not publicly reachable.
- ✅ Backups and restore test: **after the MVP**. (Automatic Coolify backups get switched on at C3 anyway.)

### Development environment

- ✅ Development runs on a home server: VM (< 7 GB RAM) → container → code-server → Cloudflare Tunnel. Cannot change. No Docker access, no KVM, no root; localhost is free; internet access to package registries works. Only a few ports are exposed to Martin's browser.
- ✅ Consequence: backend, web and pure Kotlin logic (`engine-core`) are developed on the home server; APK, Android layer, emulator and MariaDB tests run in GitHub Actions; the notebook is only a fallback. Details: BUILDPLAN A6.
- ✅ GitHub Actions must never cost money (no payment method, or a $0 budget with "stop usage").

### Cloudflare

- ✅ Domain `cowflex.com` managed at Cloudflare, no tunnel for production.
- ✅ `coolify.cowflex.com`: proxied, password + Cloudflare Access (GitHub SSO). Stays as is.
- ✅ Not all other projects run through the Cloudflare proxy, so the VPS IP is public anyway. **No origin restriction to Cloudflare IP ranges**, because it would cut off the other projects.
- ✅ Two new subdomains:
  - **API + web app** (`famapp.cowflex.com`): **proxied**.
  - **Admin UI** (`famapp-admin.cowflex.com`): proxied with Cloudflare Access (GitHub SSO), like Coolify. Plus its own admin login in the backend.
- ✅ WAF rule "Skip" for the app subdomain (Bot Fight Mode and challenges off), otherwise Cloudflare blocks the app. Real client IP from `CF-Connecting-IP`, trusted only for requests from Cloudflare IP ranges.

### Security

- **App (Android):** pairing code (one-time, valid 10 min, generated in the admin UI or on a paired device) → refresh token per device in the Android Keystore, short-lived access token (15 min). Refresh tokens rotate. If an old token is reused, the device is locked.
- **Web (both users):** password (Argon2id) plus second factor.
  - ✅ **Second factor = approval in the app:** after the password, all of the user's paired devices show "Approve browser login?" with Yes/No (via FCM wake-up, so it works with the app closed). The browser waits up to 2 min.
  - 🟡 The notification shows the browser, approximate location (from the IP) and a two-digit code that is also shown in the browser, so nobody approves a stranger's attempt by accident.
  - 🟡 Fallback when no phone is at hand: one-time recovery codes, or Martin as admin resets the login.
  - 🟡 Browser remembered for 30 days.
  - 🟡 Martin as admin additionally uses TOTP (admin UI); the app approval only applies to the regular web app.
- Session as `HttpOnly`/`Secure`/`SameSite=Strict` cookie, CSRF protection.
- **Admin UI:** ✅ Martin only. Role `admin` belongs only to his account. Login with password + TOTP (mandatory), additionally behind Cloudflare Access.
- Rate limits on login, pairing and token refresh. Account lockout after failed attempts.
- Because the origin is directly reachable: rate limits and lockouts in the backend itself, not only at Cloudflare. No public `/docs` or `/openapi.json` endpoints.
- Audit log: logins, pairings, token revocations, admin actions, secret changes.
- FCM messages carry no content, only "sync".
- Pinned dependencies, `pip-audit` and `npm audit` in CI.

### Setup wizard and secrets

- ✅ Secrets are configured through a web wizard instead of `.env` in Coolify.
- ✅ **Technical limit:** three values stay in Coolify environment variables because the app needs them before it can access the DB:
  1. DB credentials (`DATABASE_URL`)
  2. `MASTER_KEY` (encrypts all other secrets in the DB)
  3. `SETUP_TOKEN` (only for the first wizard run, useless afterwards)
- 🟡 **Everything else via the wizard**, encrypted in the DB (AES-GCM with `MASTER_KEY`): Firebase service account (JSON upload), Google OAuth client, Google calendar connection (OAuth login in the wizard), user accounts, time zone, default notification times.
- 🟡 Flow: first start → wizard reachable only with `SETUP_TOKEN` → create admin account → enter and test secrets (test push, test calendar fetch) → wizard locks itself. Secrets can be changed later in the admin UI but are never shown in plain text again.

### Admin UI

- ✅ Martin only. Management, control, logs, activity overview, statistics.
- 🟡 **Separate server-rendered UI in the FastAPI backend** (Jinja templates, real HTML/CSS, vanilla JS or htmx) on its own subdomain behind Cloudflare Access.
- 🟡 Contents:
  - **Delivery:** status per notification and device (planned, shown, acknowledged, not delivered), delay, watchdog retries
  - **Devices:** last sync, app version, FCM token status, generate pairing code, lock device
  - **Statistics:** delivery rate, delay (median, p95), completed todos per person/category
  - **Activity:** chronological, who created/completed what
  - **Conflicts:** changes overwritten by last-write-wins
  - **Logs:** errors, calendar fetches, FCM responses, audit log
  - **Settings:** secrets, calendar sources and assignment, users, defaults
  - **Tools:** test notification to a device, manual sync wake-up

## 4. Push

- ✅ FCM only as a wake-up call (data message without content, high priority).

## 5. Notifications

All times, intervals and switches in this section are **configurable per user in the app** (defaults in brackets).

### Quiet hours

- ✅ Per user, default 22:00–06:00.
- ✅ **During quiet hours: no nagging and no normal notifications.**
- ✅ Only exception: an explicitly urgent todo that is **newly sent** during quiet hours appears **once**. Then it pauses; nagging starts when active time begins.
- 🟡 This one-time night notification uses the high channel but does not bypass Do Not Disturb.
- 🟡 Anything else that accumulates during quiet hours is delivered at the start of active time (see each class).

### Classes

| Class | Trigger | Channel | Behavior |
|---|---|---|---|
| **Summary** | local exact alarm at configured times; content built locally at display time | high | server watchdog checks the ack; wake-up after 15 min |
| **Urgent (explicit)** | immediately via FCM wake-up → sync → display | own channel, bypass DND (configurable) | repeats (every 15 min) until done. During quiet hours only once when newly created, no nagging. |
| **Urgent (time-based)** | local alarm when a horizon todo becomes "urgent" | high | repeats (hourly) until done or postponed. Not during quiet hours. |
| **Normal** | FCM wake-up, may be batched | normal | collected during quiet hours, then delivered as one notification |
| **Calendar** | local alarms from calendar data | normal | evening before, morning of, start time (rules below) |

### Summaries

- ✅ Times configurable per user.
- 🟡 Configurable per weekday (e.g. Mon–Fri 07:00/12:30/19:00, Sat–Sun 09:00/13:00/19:00); each time can be disabled individually.
- ✅ Content: number of urgent todos with a mini preview, number of other todos, calendar events.
- 🟡 Mini preview: up to 3 urgent todos (overdue first), the rest as "+ 2 more". Events: count for today, first event with time.
- 🟡 Tapping opens the "Urgent" view.

### Urgent and nagging

- ✅ Both users may send urgent todos to the other, to themselves or to both.
- ✅ **Does not stop when tapped, only when the todo is done.**
- ✅ Explicitly urgent: repeats every 15 min (configurable).
- ✅ Urgent through elapsed time: repeats once per hour (configurable).
- ✅ **Both kinds pause during quiet hours.** Nagging resumes immediately when active time starts.
- ✅ If an explicitly urgent todo is sent during the recipient's quiet hours, it appears once immediately (without nagging); nagging starts when their active time begins. The sender sees "Quiet hours until 06:00, then reminders every 15 min" in the app.
- ✅ Bypass Android Do Not Disturb: configurable per user. Only applies outside the user's own quiet hours.
- ✅ Sent to "both": once one completes it, nagging stops for both.
- ✅ **Snooze** for explicitly urgent todos: pauses nagging (default 30 min, configurable). Afterwards it continues until done.
- 🟡 An explicitly urgent message is always a todo (kind `immediate`). Actions in the notification: "Done" and "Snooze"; for time-based ones "Done" and "Postpone".
- 🟡 Technically the engine sets the next exact alarm for every open nagging todo (respecting quiet hours and snooze). When it is completed on one device, an FCM wake-up goes to all other devices, which cancel the alarm. Without a network it keeps nagging until sync brings the status. Snooze applies per user (synced so it pauses on all of that user's devices).
- 🟡 DND bypass: own channel with `setBypassDnd(true)`. Android requires a one-time "Do Not Disturb access" grant; the app requests it in the setup flow.

### Normal

- 🟡 Normal notifications during quiet hours are collected and shown as **one** notification at the start of active time ("Since 22:00: 4 changes").
- 🟡 Outside quiet hours: several changes by the same person within 2 min are batched.

### Calendar

- ✅ Separate notifications, normal priority.
- ✅ Times: evening before, morning of, start time (not for all-day events).
- ✅ **If the morning or start-time notification falls into quiet hours** (e.g. a flight at 05:30), it is dropped. Only the evening-before notification remains.
- ✅ **Who gets notified:** Martin's calendar → Martin only. His wife's calendar → her only. Shared calendar → both. (Both can see all three calendars.)
- 🟡 Technically each calendar source has a "notify: user A / user B" list in the admin UI.
- 🟡 Default times: evening before 19:00, morning 07:00 (configurable per user).

## 6. Todos

### Decided

- ✅ Kinds: **scheduled** (exact time), **horizon** (mid/long term), **immediate/urgent**, **someday**.
- ✅ Mid term: 1, 2, 3 or 4 weeks. Long term: 1, 2 or 3 months.
- ✅ Long term automatically becomes mid term; mid term automatically becomes urgent.
- ✅ No subtasks.
- ✅ Categories optional. Initial ideas: Wohnung (home), Soziales (social), Kalender (calendar), Besorgung (errands).
- ✅ Assignee: Martin, his wife, or both.
- ✅ "For whom": people, including their child.

### Data model

The level is **not stored but computed from `target_date`.** "Mid term, 3 weeks" sets `target_date = today + 3 weeks`.

```
todos
  id UUID, rev
  title, note
  kind              : 'scheduled' | 'horizon' | 'immediate' | 'someday'
  due_at            : for kind=scheduled
  target_date       : for kind=horizon
  category_id       : optional
  assignee_user_id  : user id or NULL (= both)
  for_people        : list of person ids
  status            : open | done | dismissed
  completed_by, completed_at
  series_id         : optional
  payload           : JSON (e.g. appointment data for the "calendar" category)
  created_by, created_at, deleted_at
  -- conflict fields, see section 8:
  content_changed_at, content_changed_by
  status_changed_at, status_changed_by

todo_snoozes (todo_id, user_id, until)   -- "Snooze", per user
people       (id, name, user_id NULL)    -- Martin, wife, child, household
categories   (id, slug, name, color, icon, sort_order, active)
```

### Level computation

| Time left until `target_date` | Displayed level |
|---|---|
| > 4 weeks | `long_term` |
| 1 to 4 weeks | `mid_term` |
| < 1 week | `urgent` (time-based, nags hourly) |
| past | `overdue` (keeps nagging hourly) |
| kind `someday` | someday (never changes) |
| kind `scheduled` | scheduled; "today" on the day itself |

- 🟡 Thresholds configurable centrally (admin UI).
- 🟡 "Postpone" action: sets a new target date (1–4 weeks / 1–3 months from today), which also ends nagging.
- 🟡 Sort order: overdue → urgent → scheduled today → mid term → long term → someday.

### Recurring todos

- ✅ Two assignee modes: **fixed** (one person or both) and **rotating**.
- ✅ **Rotating:** the next instance goes to the person who did **not** complete the last instance. If someone stepped in, the other one is next.
- ✅ Two rhythm types:
  - **Interval:** every x days or x weeks
  - **Calendar rule:** e.g. "the 15th of every 2nd month" or "every 1st Monday of the month"
- 🟡 Both stored as RRULE (iCalendar standard). The app offers simple pickers; nobody types RRULE.

```
todo_series
  id, active
  template          : title, note, category, people, kind, horizon/time
  rrule             : RRULE
  rule_type         : 'interval' | 'calendar'
  assignee_mode     : 'fixed' | 'rotating'
  assignee_user_id  : user id or NULL (when fixed)
  last_completed_by : user id (when rotating; decides the next person)
  next_due
```

- ✅ **Interval counts from completion.** On completion the server immediately creates the next instance, due `completed_at + interval`. An interval series never has more than one open instance.
- ✅ **Calendar rules have fixed dates.** If the previous instance is still open on the next date, a new instance is created anyway (the old one stays open as overdue).
- 🟡 Rotating with stacked calendar-rule instances: the new instance goes to the person who did not complete the last **completed** instance.
- 🟡 Dismissing an instance counts like completing it (the next instance is created) but does not count for rotation.
- 🟡 Only the server creates instances. If completed offline, the next instance is created on the next sync, based on the corrected completion time.
- 🟡 Every instance gets a `target_date` and moves through the normal levels (mid term → urgent → overdue). Whether a series creates horizon todos or scheduled todos (fixed time) is part of the template.

### Categories

- 🟡 Categories are records (can be created in the app), not hard-coded.
- 🟡 Only `calendar` has special behavior (appointment data in `payload`, action "Open in calendar app").

## 7. Calendar

- ✅ Sources: Martin's calendar, his wife's calendar, a shared one. All reachable through Martin's Google account.
- ✅ Both see all three calendars.
- ✅ MVP: read only. "Add appointment" creates a todo in the "calendar" category.
- ✅ Moving away from Google later should be possible (CalDAV).
- ✅ Google Calendar API, read only (`calendar.readonly`), one OAuth login with Martin's account in the setup wizard. OAuth app set to "In production" without verification (otherwise tokens expire after 7 days).
- ✅ Backend interface `CalendarSource` (`google_api`, later `caldav`). The app only knows `calendar_events`.
- 🟡 Incremental fetch every 5 min via `syncToken`. Calendar events go through the normal rev sync.

## 8. Offline and conflicts

- ✅ The Android app works offline: read, create, edit and complete todos. Sync runs once the network is back.
- ✅ No real-time sync needed.
- ✅ Conflicts: last-write-wins.

### Conflict logic

Plain last-write-wins per row has an unpleasant consequence: if she completes a todo offline and Martin later only changes its title online, the todo would be open again. Hence **last-write-wins per field group**:

| Field group | Fields | Timestamp |
|---|---|---|
| Content | title, note, kind, target date, due time, category, assignee, people, payload | `content_changed_at` |
| Status | status, completed by/at | `status_changed_at` |
| Deletion | `deleted_at` | always wins (tombstone) |

Flow:

1. Every change on the device goes into the local DB and the **outbox**, with timestamp and affected field group.
2. On sync the device sends the outbox to `POST /api/sync/push`.
3. The server compares per field group: the newer timestamp wins; the older change is discarded and recorded in the conflict log (admin UI).
4. The device then fetches the cleaned-up state via `GET /api/sync?since=<rev>` and overwrites locally.

Device clocks can drift. The device therefore measures its offset from server time on every sync and corrects its timestamps. On a tie, the change that reached the server first wins.

Recurring todos: only the server creates new instances, so no duplicates arise offline.

## 9. App architecture

**Consequence of "works offline":** the UI cannot just talk to the API; it needs a local database. At the same time the engine must access the same data in the background (without a running UI): build summaries, store "Done" from a notification, sync after an FCM wake-up.

🟡 **The Kotlin engine owns the local database and sync exclusively.** The UI reads and writes through engine functions. Only one piece of code writes to the DB; there are no competing schemas and migrations between JS and Kotlin.

```
UI (Expo, JavaScript)
  └─ data/repo.js          ← shared interface: listTodos(), saveTodo(), completeTodo() …
        ├─ repo.native.js  → Kotlin engine (local DB, outbox, sync)        [Android]
        └─ repo.web.js     → REST API directly                             [browser]

Kotlin engine "famapp-engine"
  ├─ engine-core (pure Kotlin): planner, levels, quiet hours, nag times, sync and conflict logic
  └─ engine-android:
       ├─ Room DB: todos, series (read-only), categories, people, calendar_events (14 days),
       │           notifications, deliveries, settings, todo_snoozes, outbox, sync_state
       ├─ alarm: the one exact alarm, WorkManager jobs
       ├─ display: channels, batching, actions "Done"/"Snooze"/"Postpone"
       └─ events to the UI: "data changed" → UI reloads
```

- The UI does not know whether it runs on Android or in the browser; only the `repo` implementation differs.
- Estimated size of the Kotlin engine: 1,500–2,000 lines.

---

## Open questions

None. Not yet decided but not blocking: the app's display name, final categories.
