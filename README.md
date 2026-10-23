# FamApp

> The display name lives in `branding.json` and can change at any time. `famapp` is the fixed technical codename (package name, modules, folders) and never changes.

A private, self-hosted household app for two people (a Flatastic clone).
**Core goal: reminders and notifications arrive reliably and on time, to the minute**, despite Doze, Samsung battery rules, reboots and dead zones.

Todos, calendar and everything else are features built on top of this notification engine.

Rationale for every decision: `docs/decisions.md`. Build order and development environment: `BUILDPLAN.md`. Entry point for AI agents: `AGENTS.md`.

---

## 1. Principles

1. **The server is the source of truth; the device executes.** All data lives in the server database (production: MariaDB). The Android app keeps a local mirror and creates notifications itself.
2. **Push is only a wake-up call.** FCM messages carry no content, only "sync". If a push is lost, local alarms, periodic sync and the server watchdog take over.
3. **Several independent safety nets.** No single component (FCM, WorkManager, alarm) decides delivery on its own.
4. **Delivery is observable.** Every notification has a per-device status (shown, acknowledged). Failures become visible.
5. **Idempotent.** Duplicate syncs, alarms or pushes never cause duplicate notifications (stable IDs).
6. **Offline-first on Android.** Reading, creating, editing, completing and reminding all work without a network.
7. **One UI codebase.** The same Expo app runs on Android and in the browser.

---

## 2. Overview

```
                    Cloudflare (DNS, proxy, WAF)
                      │                       │
      famapp.cowflex.com               famapp-admin.cowflex.com
      (proxied, WAF skip rule)         (proxied + Cloudflare Access, GitHub SSO)
                      │                       │
 ┌──────────────────── VPS / Coolify (Traefik, certificates) ────────────────────┐
 │                                                                               │
 │   ┌────────────── container "api" (FastAPI) ──────────────┐                   │
 │   │  /api/*      REST + sync for app and web              │                   │
 │   │  /           Expo web build (static files)            │                   │
 │   │  admin host  admin UI + setup wizard (Jinja/htmx)     │◄──► MariaDB       │
 │   └───────────────────────────────────────────────────────┘     (Coolify      │
 │   ┌────────────── container "worker" (same image) ────────┐      resource,    │
 │   │  APScheduler: watchdog, series instances,             │◄──►  not          │
 │   │  calendar fetch, heartbeat, FCM sending               │      public)      │
 │   └───────────────────────────────────────────────────────┘                   │
 └───────────────────────────────────────────────────────────────────────────────┘
                      │ FCM: data message "sync", high priority
                      ▼
 ┌──────────────────────── Android app ─────────────────────────┐
 │  UI (Expo, JavaScript) ──► data/repo.js ──► Kotlin engine    │
 │                                  engine-android + engine-core│
 │   Room DB · sync + outbox · planner · display · actions      │
 └──────────────────────────────────────────────────────────────┘

 Browser: same UI ──► data/repo.js ──► REST API (online only)
```

- **Two containers from one image:** `api` (any number of worker processes) and `worker` (exactly one instance, so scheduled jobs never run twice).
- **Web app and API on the same subdomain:** no CORS configuration, and a `SameSite=Strict` session cookie works without exceptions.
- **Admin UI on its own subdomain**, served by the same backend but only reachable via the admin host and additionally behind Cloudflare Access.

---

## 3. Core feature: notification engine

### 3.1 Notification classes

| Class | Source | Android channel | Behavior |
|---|---|---|---|
| **Summary** | Device, at configured times; content built at display time from local data | `summary`, high | Server watchdog expects an ack, otherwise wake-up after 15 min |
| **Urgent (explicit)** | Server, sent by a person | `urgent`, high, bypass Do Not Disturb (configurable) | Repeats every 15 min until done. Actions: Done, Snooze |
| **Urgent (time-based)** | Device, when a horizon todo becomes urgent | `due`, high | Repeats hourly until done or postponed. Actions: Done, Postpone |
| **Normal** | Server, on activity by the other person | `activity`, normal | Batched; collected during quiet hours |
| **Calendar** | Device, from calendar data | `calendar`, normal | Evening before, morning of, start time |
| **Login approval** | Server, on web login | `security`, high | Yes/No action, expires after 2 min |

All times, intervals and switches are **configurable per user in the app**.

### 3.2 Quiet hours (default 22:00–06:00)

- No normal notifications, no nagging, no summaries.
- Exception: an explicitly urgent todo that is **newly sent during quiet hours** appears **once** (high channel, without bypassing Do Not Disturb). Nagging only starts when quiet hours end.
- Normal notifications from quiet hours arrive at the start of active time as **one** combined notification ("Since 22:00: 4 changes").
- Calendar notifications (morning, start time) that fall into quiet hours are dropped. The evening-before notification remains.
- Login approvals are not affected by quiet hours (they are only triggered by the user's own action).

### 3.3 Nagging

- Explicitly urgent: every 15 min (configurable); time-based urgent: hourly (configurable).
- Does **not** stop when tapped, only when the todo is done, dismissed or (time-based) postponed.
- Sent to "both": if one person completes it, it stops for both.
- **Snooze** (default 30 min) pauses per user and is synced, so it pauses on all of that user's devices.
- Every repetition re-posts the notification with the **same ID** (with sound). No pile of identical notifications.
- When a todo is completed on one device, the server sends a wake-up to all other devices, which cancel the alarm. Without a network it keeps nagging until sync brings the new status.

### 3.4 Planner: a single alarm

Instead of one alarm per notification, the planner always keeps **exactly one exact alarm** set for the next due time.

1. The planner computes all future display times from the local DB (summaries, calendar, nag repetitions, scheduled server notifications), respecting quiet hours and snoozes.
2. It sets one alarm for the earliest time.
3. When the alarm fires, **everything due** is shown, then it re-plans.
4. It also re-plans after every sync, every local change, boot, time/time zone change and app update.

Benefits: Android's alarm limit does not matter, there is no reconciliation of many alarms, and the logic is testable in one place.

- Alarm type: `setAlarmClock()` when the next entry is high priority (not throttled in Doze, shows an alarm icon in the status bar), otherwise `setExactAndAllowWhileIdle()`.
- Permission `USE_EXACT_ALARM` (granted at install time because the app is not distributed via the Play Store).

### 3.5 Stable IDs

Every display has a fixed key from which the Android notification ID and the delivery status are derived:

| Kind | Key |
|---|---|
| Server notification | `notif:<uuid>` |
| Summary | `summary:<user>:<date>:<slot>` |
| Calendar | `cal:<event-id>:<evening/morning/start>` |
| Nag | `nag:<todo-id>` (same ID for every repetition) |

Because summary keys are deterministic, the server knows which acks to expect without the device announcing them.

### 3.6 Sync triggers

| Trigger | Purpose |
|---|---|
| FCM wake-up | Fast delivery on activity by the other person (target: < 10 s) |
| App start, return to foreground | Current state in the UI |
| Local change | Send outbox immediately (if online) |
| Network available again | Catch up after a dead zone |
| Boot, app update | Re-plan, catch up |
| Periodic WorkManager job (15 min) | Safety net for lost pushes |
| Server watchdog | Another wake-up when an expected ack is missing |

### 3.7 Delivery and watchdog

- When displaying, the device writes `shown_at` locally and puts an ack into the outbox.
- The server stores acks in `deliveries` (per display key and device).
- **Watchdog (worker, every minute):**
  - Server notifications without ack: another wake-up after 2, 10 and 60 min, then status "not delivered".
  - Summaries without ack 15 min after their scheduled time: wake-up, then status "late/missing".
  - Device without sync for > 6 h (outside quiet hours): notice to the other person and in the admin UI.
- **Catch-up on the device:** due entries that were never shown are shown immediately on the next sync and marked "late". Expired entries (`expires_at`) are discarded.

### 3.8 Reliability check in the app ("Delivery" screen)

Green/red status with a button that opens the matching system setting:

- Notifications allowed, all channels at the expected importance
- Exact alarms allowed
- Battery optimization off ("Unrestricted"); on Samsung also "Never sleeping"
- "Remove permissions if app is unused" off
- Do Not Disturb access (if bypass is enabled)
- FCM token registered, last sync, last wake-up
- Test notification in 10 seconds (local) and test wake-up via the server
- Delay statistics for the last 50 displays

---

## 4. Todos

### 4.1 Kinds and levels

| Kind | Time reference | Displayed level |
|---|---|---|
| `scheduled` | exact time (`due_at`) | scheduled; "today" on the day itself |
| `horizon` | target date, chosen as 1–4 weeks or 1–3 months | computed, see below |
| `immediate` | explicitly urgent, right now | urgent (nag every 15 min) |
| `someday` | none | someday |

**The level is never stored; it is computed from `target_date`:**

| Time left until target date | Level | Notification |
|---|---|---|
| > 4 weeks | `long_term` | – |
| 1–4 weeks | `mid_term` | – |
| < 1 week | `urgent` | hourly, not during quiet hours |
| past | `overdue` | hourly, not during quiet hours |

"Postpone" sets a new target date (1–4 weeks / 1–3 months from today). Thresholds are configurable centrally.

Level computation exists three times (Python on the server, Kotlin in `engine-core`, JavaScript in the UI). To keep them in sync there is **one shared test file**, `shared/test-vectors/levels.json`, that all three implementations are tested against.

### 4.2 Other properties

- **Assignee:** Martin, his wife, or both (`assignee_user_id` or `NULL`).
- **For whom:** any people (Martin, his wife, their child, household). People are not app users.
- **Category:** optional, created in the app (seed values with German display names: Wohnung/home, Soziales/social, Kalender/calendar, Besorgung/errands). Only the `calendar` category has special behavior.
- **Status:** `open`, `done`, `dismissed`.
- No subtasks.

### 4.3 Recurring todos

- The rule is stored as an RRULE and created in the app with simple pickers:
  - **Interval** ("every x days/weeks"): counts **from completion**. Completing creates the next instance immediately. There is always exactly one open instance.
  - **Calendar rule** ("the 15th of every 2nd month", "every 1st Monday"): fixed dates. If the old instance is still open, a new one is created anyway.
- **Assignee:** fixed (one person or both) or **rotating**: next up is whoever did **not** complete the last completed instance.
- Dismissed counts like done (the next instance is created) but does not count for rotation.
- **Only the server creates instances** (worker). This prevents duplicates from offline devices.

### 4.4 Category "calendar" (add appointment)

"New appointment" in the app does **not** write to Google. It creates a todo in the `calendar` category with the appointment data in `payload` (title, start, end, location, note, target calendar). The action "Open in calendar app" opens the calendar app with prefilled data (Android intent `ACTION_INSERT`); afterwards the todo is checked off.

---

## 5. Calendar

- Three sources, all accessible through Martin's Google account: his calendar, his wife's calendar, the shared one. Both users see all three.
- **Google Calendar API, read-only** (`calendar.readonly`). One OAuth login in the setup wizard. OAuth app set to "In production" without verification so refresh tokens do not expire after 7 days.
- The worker fetches incrementally every 5 min (`syncToken`), writes `calendar_events` (expanded recurrences, −1 to +12 months) and distributes them through the normal sync. The device keeps the next 14 days locally.
- **Who gets notified, per source:** Martin's calendar → Martin, his wife's → his wife, shared → both (configurable in the admin UI).
- Calendar notifications: evening before (19:00), morning of (07:00), start time. All-day events have no start-time notification. Anything falling into quiet hours is dropped.
- Backend interface `CalendarSource` with implementation `google_api`. Later `caldav` (e.g. Radicale on the VPS) without changes to the app or data model.

---

## 6. Data model (overview)

**Database:** MariaDB in production, SQLite for development and local tests, selected via `DATABASE_URL`. The code stays portable (rules in `BUILDPLAN.md`, section A7); CI tests everything on both databases.

All synced tables have `id` (UUID), `rev` (sequential number from `next_rev()`, backed by a counter table), `created_at`, `updated_at`, `deleted_at` (tombstone). Times in UTC, displayed in the user's time zone.

| Table | Content | Synced to app |
|---|---|---|
| `users` | accounts (2), role, time zone | own row + other user's name |
| `user_settings` | quiet hours, summary times per weekday, intervals, DND bypass, theme | yes (own) |
| `devices` | device, FCM token, app version, last sync | no |
| `device_tokens` | refresh token hashes, rotation | no |
| `web_sessions`, `login_approvals` | web sessions, pending login approvals | approvals yes |
| `people` | Martin, his wife, child, household | yes |
| `categories` | name, color, icon, sort order | yes |
| `todos` | see section 4, incl. field-group timestamps | yes |
| `todo_series` | rule, template, assignee mode | yes (read-only) |
| `todo_snoozes` | "Snooze" per todo and user | yes |
| `notifications` | server-created notifications (activity, explicit urgent, system) | yes (addressed to me) |
| `deliveries` | display key × device: planned, shown, opened, acknowledged | acks only device → server |
| `calendar_sources` | Google calendar ID, color, who gets notified | yes (without credentials) |
| `calendar_events` | cached events | yes (time window) |
| `secrets` | encrypted configuration | no |
| `rev_counter` | counter for `rev` | no |
| `audit_log`, `conflict_log`, `job_log` | traceability for the admin UI | no |

---

## 7. Sync protocol and conflicts

- **Delta by revision:** `GET /api/sync?since=<rev>&limit=500` returns all changes visible to the user across all synced tables, including tombstones, paginated. The client stores the highest rev. Clocks do not matter for this.
- **Outbox:** `POST /api/sync/push` accepts a list of operations (create, change field group, change status, delete, ack, snooze). Each operation has its own UUID; repeats have no effect.
- **Last-write-wins per field group** (content, status, deletion). Deletion always wins. Overwritten changes go to the conflict log.
- **Clock skew:** every response contains the server time. The device stores the offset and uses it to correct the timestamps of its outbox entries. On a tie, whatever reached the server first wins.
- The **web app** writes directly via REST; the server sets timestamps itself.
- Every push is followed by a delta fetch. Afterwards the local DB matches the server.

---

## 8. App architecture

### 8.1 Layers

```
app/                      Expo app (JavaScript)
├─ theme/                 ThemeProvider; reads generated tokens from shared/design
├─ i18n/                  t() helper; reads shared/strings
├─ components/            base components: Button, Card, Text, Input, Badge, ListItem …
├─ screens/               Todos, Calendar, Settings, Delivery, Pairing, Login
├─ data/
│  ├─ repo.js             shared interface (listTodos, saveTodo, completeTodo …)
│  ├─ repo.native.js      → Kotlin engine                     [Android]
│  └─ repo.web.js         → REST API                          [browser]
└─ modules/famapp-engine/     local Expo module (Kotlin)
   ├─ engine-core/        pure Kotlin, no Android:
   │                      planner, levels, quiet hours, nag times, sync and conflict logic
   └─ engine-android/     thin Android layer:
      ├─ db/              Room: mirror tables, outbox, sync state
      ├─ fcm/             FirebaseMessagingService → sync, onNewToken
      ├─ alarm/           set the one alarm (AlarmManager), WorkManager jobs
      ├─ display/         channels, content, batching, actions (Done/Snooze/Postpone/Login)
      ├─ receivers/       alarm, boot, time change, package update, notification actions
      └─ bridge/          functions and events for JavaScript
```

- **`engine-core` contains all logic** and builds and tests without the Android SDK. `engine-android` only connects it to the system.
- **The engine owns the local DB exclusively.** JavaScript reads and writes only through `repo`. On Android `repo.native.js` calls the module; in the browser `repo.web.js` calls the API. Screens do not know where they run.
- The engine works without a running UI: notification actions ("Done") write directly to the DB and the outbox.
- The engine notifies the UI about changes via events; the UI then reloads.

### 8.2 Design system

**Single source: `shared/design/tokens.json`.** Colors, spacing, radii, font sizes, font weights, shadows and durations, each color as a light and a dark value. Tokens have two layers:

- **Base tokens** (the palette): `color.blue.600`, `space.4`, `radius.md` …
- **Semantic tokens** (what components use): `color.bg.surface`, `color.text.muted`, `color.state.urgent`, `space.card.padding` … pointing at base tokens.

A redesign usually means changing base tokens or re-pointing semantic ones. Components only ever use semantic tokens.

A small generator script (`make tokens`, also run by CI and before every build) turns the JSON into the format each consumer needs:

| Consumer | Generated file | Uses |
|---|---|---|
| Expo app + web | `app/theme/tokens.generated.js` | `StyleSheet` via ThemeProvider |
| Admin UI | `backend/app/admin/static/tokens.generated.css` (CSS custom properties, light + dark via `prefers-color-scheme` and a toggle) | plain CSS |
| Android engine | `engine-android/res/values(-night)/colors_generated.xml` | notification accent color per channel (e.g. urgent = red), small-icon tint |
| App icon / splash | values read by `app.config.js` | icon background, splash color |

Generated files are committed so the home server and CI need no extra step to run, and CI fails if they are out of date.

- Components use semantic tokens only, never hard-coded values. A redesign touches `tokens.json` (and at most the base components).
- Theme follows the system by default and can be changed per user (System/Light/Dark); the choice is synced with the settings.
- Base components in `app/components/` are the only place where tokens are combined into styles. Screens compose base components and do not define their own colors or spacing.

### 8.3 Web

- The Expo web build (`npx expo export --platform web`) is served by the backend at `/`.
- Online only, no engine, no notifications. Areas such as "Delivery" are hidden.

### 8.4 Language and UI strings

- Development language (code, docs, commits, specs) is **English**.
- User-facing text is **German** and lives in **one place: `shared/strings/de.json`**. This covers every surface: app and web screens, notifications generated by the engine (summaries, nagging, calendar), notifications generated by the server (activity, login approval), and the admin UI.
- **Keys by area**, e.g. `todo.action.done`, `notification.summary.title`, `settings.quietHours.label`. Code contains keys only, never German text.
- **Placeholders and plurals:** `"{count} dringende Todos"` with `one`/`other` forms (selected via the language's plural rules), so "1 dringende Todos" cannot happen.
- **One small `t(key, params)` helper per language** (JavaScript, Kotlin, Python), a few dozen lines each, same behavior, tested against shared test vectors (`shared/test-vectors/strings.json`).
- **Server notifications carry a key plus parameters**, not finished text. The device renders them with the same strings file. Display keys and wording therefore stay consistent no matter where a notification originates.
- How each consumer gets the strings: the Expo app and Python import the JSON directly; the Kotlin engine gets it copied into its assets at build time.
- **CI checks:** every key used in code exists in `de.json`; unused keys are reported; placeholders match between usage and text; a lint rule rejects German string literals in UI code.
- Changing wording = edit `de.json`, then a new build/deploy (texts are bundled). Runtime overrides via the admin UI could be added later; not part of the MVP.
- Adding another language later = add `en.json` with the same keys; the helpers already take a locale.

---

## 9. Security

**Android app**
- Pairing via one-time code (valid 10 min), generated in the admin UI or on an already paired device.
- Access token 15 min; refresh token per device, rotating, stored in the Android Keystore. Reuse of an old refresh token locks the device.
- Devices can be revoked individually.

**Web app (both users)**
- Password (Argon2id) + **approval in the app**: all of the user's devices show "Approve browser login?" with a two-digit code that is also shown in the browser. Valid for 2 min.
- Fallback: recovery codes or a reset by the admin.
- Session cookie `HttpOnly`, `Secure`, `SameSite=Strict`, CSRF token, browser remembered for 30 days.

**Admin UI (Martin only)**
- Own subdomain behind Cloudflare Access (GitHub SSO), plus login with password + TOTP, role `admin`.

**General**
- Cloudflare proxy for both subdomains; WAF skip rule for the app subdomain (otherwise bot protection blocks the app).
- Rate limits and account lockout in the backend itself (the server is also reachable directly by IP). Real client IP from `CF-Connecting-IP` only for requests from Cloudflare IP ranges.
- OpenAPI/docs endpoints not public.
- Secrets encrypted in the DB (AES-GCM with `MASTER_KEY`). Only DB access, `MASTER_KEY` and `SETUP_TOKEN` live in Coolify environment variables.
- FCM messages carry no content.
- Audit log for logins, pairings, revocations, admin actions, secret changes.
- Pinned dependencies; `pip-audit` and `npm audit` in CI.

---

## 10. Operations

### Setup wizard
1. Set Coolify environment variables: `DATABASE_URL` (MariaDB), `MASTER_KEY`, `SETUP_TOKEN`.
2. First visit to the admin subdomain → wizard, only with `SETUP_TOKEN`.
3. Create admin account with password + TOTP.
4. Upload Firebase service account → test push to a test device.
5. Enter Google OAuth client → Google login → select and assign calendars → test fetch.
6. Second user account, people, time zone, default times.
7. Wizard locks itself. Changes afterwards via the admin UI; secrets are never shown in plain text again.

### Admin UI
Delivery (per display and device) · Devices (pairing, lock, token status) · Statistics (delivery rate, delay median/p95, completed todos) · Activity · Conflicts · Logs (errors, calendar, FCM, audit) · Settings (secrets, calendars, users, defaults, level thresholds) · Tools (test notification, wake-up).

### Backups
After the MVP: scheduled Coolify DB backup to external storage plus a restore test. Automatic backups are switched on at checkpoint C3.

### App distribution
Signed APK from CI, installed directly or via Firebase App Distribution; no Play Store.

---

## 11. Tech stack

| Area | Technology |
|---|---|
| App UI | Expo (managed workflow + development build), React Native, JavaScript, `StyleSheet`, React Navigation |
| Engine | Kotlin: `engine-core` (pure Kotlin), `engine-android` (Room, WorkManager, AlarmManager, Firebase Messaging), local Expo module |
| Web | Expo Web (same codebase) |
| Backend | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, APScheduler, `firebase-admin`, `google-api-python-client`, `python-dateutil` (RRULE), `argon2-cffi`, `pyotp`, `cryptography` |
| Admin UI | Jinja2 templates, HTML/CSS, htmx, a little vanilla JS |
| Database | Production: MariaDB ≥ 10.6 · development/tests: SQLite · selected via `DATABASE_URL` |
| Operations | Coolify (Docker Compose), Traefik, Cloudflare (DNS, proxy, WAF, Access) |
| Development | Home server (code-server, no Docker/KVM) for backend, web and `engine-core`; GitHub Actions for APK, Android tests, emulator, MariaDB tests (details: `BUILDPLAN.md`, A6/A7) |
| CI | GitHub Actions: tests on SQLite and MariaDB, engine/JS tests, emulator E2E, lint, audits, APK build |

---

## 12. Repository layout

```
famapp/
├─ README.md
├─ BUILDPLAN.md
├─ AGENTS.md                rules for AI agents (CLAUDE.md points here)
├─ Makefile                 setup, dev, test, lint, tokens, e2e, apk
├─ branding.json            display name, short name, icon color (single place)
├─ docker-compose.dev.yml   local environment for machines with Docker (notebook, CI)
├─ docs/                    decisions, specs, progress.md, assumptions.md, checkpoint lists
├─ shared/
│  ├─ strings/de.json       all user-facing text (single source, see 8.4)
│  ├─ design/tokens.json    all design tokens (single source, see 8.2)
│  └─ test-vectors/         shared test cases (levels, quiet hours, rotation, RRULE, conflicts, strings)
├─ tools/                   generators (tokens), string/key checks
├─ dev/
│  ├─ fake-fcm/
│  └─ fake-gcal/            with fixtures
├─ backend/
│  ├─ app/
│  │  ├─ api/               app and web endpoints
│  │  ├─ admin/             admin UI, setup wizard, templates
│  │  ├─ db/                session, types, next_rev(), locks, dialects/ (SQLite, MariaDB)
│  │  ├─ sync/              delta, push, conflict logic
│  │  ├─ domain/            todos, levels, series, notifications, quiet hours
│  │  ├─ calendar/          CalendarSource, google_api
│  │  ├─ jobs/              watchdog, series, calendar, heartbeat
│  │  ├─ fcm/               wake-up sending, token maintenance
│  │  └─ security/          auth, tokens, sessions, crypto, rate limits
│  ├─ migrations/
│  ├─ tests/
│  └─ Dockerfile
├─ app/                     Expo app incl. modules/famapp-engine (see 8.1)
├─ deploy/
│  ├─ docker-compose.yml    api + worker (MariaDB as Coolify resource)
│  └─ cloudflare.md         DNS, WAF and Access settings
└─ .github/
   ├─ workflows/            CI
   └─ ISSUE_TEMPLATE/       bug report
```

---

## 13. Known limitations

- **"Force stop"** in the app settings stops alarms and FCM until the app is opened again. No app can work around this. The server heartbeat makes it visible.
- Samsung may restrict background work despite settings. The reliability check, watchdog and heartbeat make this visible. Plan B: foreground service.
- `setAlarmClock()` shows an alarm icon in the status bar while a high-priority alarm is scheduled.
- Without a network, a todo completed on the other device may keep nagging until the network is back.
- Web login needs a paired phone (or a recovery code).

---

## 14. Features

| Feature | When |
|---|---|
| Notification engine, delivery, watchdog | MVP |
| Todos (kinds, levels, nagging, snooze/postpone) | MVP |
| Recurring todos with rotation | MVP |
| Read calendar + calendar notifications | MVP |
| Add appointment → todo in "calendar" category | MVP |
| Web app with in-app login approval | MVP |
| Admin UI + setup wizard | MVP |
| Backups + restore test | right after MVP |
| Shopping list | later |
| Notebook (Markdown) | later |
| Finances / household budget | later |
| CalDAV instead of Google, writing to calendars | later |
