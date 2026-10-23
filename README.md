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
 │  UI (Expo, TypeScript) ──► data/repo.ts ──► Kotlin engine    │
 │                                  engine-android + engine-core│
 │   Room DB · sync + outbox · planner · display · actions      │
 └──────────────────────────────────────────────────────────────┘

 Browser: same UI ──► data/repo.ts ──► REST API (online only)
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
| **Scheduled reminder** | Device, at `due_at` (optional lead time: 15 min / 1 h / 1 day) | `due`, high | Once; if still open afterwards, the todo is overdue and joins the time-based nag |
| **Urgent (time-based)** | Device, when a horizon todo becomes urgent or a scheduled todo is overdue | `due`, high | **One combined notification per user** for all of them, re-posted hourly until none are left. Tapping opens the list |
| **Normal** | Server, when the other person creates a todo for me/both, or completes/dismisses one for me/both or created by me | `activity`, normal | Batched; collected during quiet hours |
| **Calendar** | Device, from calendar data | `calendar`, normal | Evening before, morning of, start time |
| **Login approval** | Server, on web login | `security`, high | Yes/No action, expires after 2 min |
| **System** | Device, e.g. network available but server unreachable for 3 h | `system`, normal | Once, again after 24 h |

All times, intervals and switches are **configurable per user in the app**.

### 3.2 Quiet hours (default 22:00–06:00)

- No normal notifications, no nagging, no summaries.
- Exception: an explicitly urgent todo that is **newly sent during quiet hours** appears **once** (high channel, without bypassing Do Not Disturb). Nagging only starts when quiet hours end.
- A scheduled reminder whose time falls into quiet hours is shown once (the user picked the time), without bypassing Do Not Disturb.
- Normal notifications from quiet hours arrive at the start of active time as **one** combined notification ("Since 22:00: 4 changes").
- Calendar notifications (morning, start time) that fall into quiet hours are dropped. The evening-before notification remains.
- Login approvals are not affected by quiet hours (they are only triggered by the user's own action).

### 3.3 Nagging

- Explicitly urgent: every 15 min (configurable), one notification per todo.
- Time-based urgent and overdue (horizon and scheduled): **one combined notification per user** ("3 fällige Todos: …", up to 3 titles, overdue first), hourly (configurable).
- Does **not** stop when tapped, only when the todo is done, dismissed or (time-based) postponed.
- Sent to "both": if one person completes it, it stops for both.
- **Snooze** (default 30 min) pauses per user and is synced, so it pauses on all of that user's devices.
- Every repetition re-posts the notification with the **same ID** (with sound). No pile of identical notifications.
- **Undo:** after "Done" from a notification it turns into "Erledigt – Rückgängig" for 30 s.
- When a todo is completed on one device, the server sends a wake-up to all other devices, which cancel the alarm. Without a network it keeps nagging until sync brings the new status.

### 3.4 Planner: a single alarm

Instead of one alarm per notification, the planner always keeps **exactly one exact alarm** set for the next due time.

1. The planner computes all future display times from the local DB (summaries, calendar, scheduled reminders, nag repetitions, scheduled server notifications), respecting quiet hours and snoozes.
2. It sets one alarm for the earliest time.
3. When the alarm fires, **everything due** is shown, then it re-plans.
4. It also re-plans after every sync, every local change, boot, time/time zone change and app update.

Benefits: Android's alarm limit does not matter, there is no reconciliation of many alarms, and the logic is testable in one place.

- Alarm type: both are implemented and switchable via an engine setting; **the default is decided at C1** (`docs/decisions.md` section 10).
  - `setAlarmClock()`: never delayed in Doze, but shows an alarm icon, becomes the system's "next alarm" (lock screen, watch) and ends DND schedules that stop "at the next alarm".
  - `setExactAndAllowWhileIdle()`: no side effects; in Doze at most about one alarm per 9 min, which the single-alarm planner rarely hits.
  - Until C1: `setAlarmClock()` for high-priority entries, otherwise `setExactAndAllowWhileIdle()`.
- Permission `USE_EXACT_ALARM` (granted at install time because the app is not distributed via the Play Store).

### 3.5 Stable IDs

Every display has a fixed key from which the Android notification ID and the delivery status are derived:

| Kind | Key |
|---|---|
| Server notification | `notif:<uuid>` |
| Summary | `summary:<user>:<date>:<slot>` |
| Calendar | `cal:<event-id>:<evening/morning/start>` |
| Nag (explicit urgent) | `nag:<todo-id>` (same ID for every repetition) |
| Nag (time-based, combined) | `nagdue:<user>` (same ID for every repetition) |
| Scheduled reminder | `due:<todo-id>:<lead/at>` |
| System | `sys:<kind>:<date>` |

Keys are deterministic, so the server knows which acks to expect without the device announcing them. The Android notification ID is derived from the key; delivery records add the planned minute for repeating displays (`nag:<todo-id>@2026-11-02T14:15Z`), so every repetition is tracked.

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
  - **Device-planned displays** (summaries, nags, scheduled reminders, calendar) without ack 15 min after their planned time: wake-up, then status "late/missing". The server computes the expected keys with the same rules as the engine (shared test vectors).
  - An explicit urgent todo (`nag:<todo-id>`) gets the 2/10/60 min schedule for its first display.
  - Device without sync for > 6 h (outside quiet hours): notice to the other person and in the admin UI.
- **Server unreachable:** if the device has network but sync fails for 3 h outside quiet hours, it shows a local system notification. No network (flight mode, dead zone) never triggers it.
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
| `scheduled` | exact time (`due_at`), optional lead time | scheduled; "today" on the day itself; `overdue` after `due_at` |
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

**Series instances use relative thresholds:** `urgent` only in the last 25 % of the series interval (at least 1 day, at most the normal 1 week before `target_date`), otherwise `mid_term`/`long_term` as above. So "every 2 weeks" is urgent 3.5 days before, not 7.

Level computation exists three times (Python on the server, Kotlin in `engine-core`, TypeScript in the UI). To keep them in sync there is **one shared test file**, `shared/test-vectors/levels.json`, that all three implementations are tested against.

### 4.2 Other properties

- **Assignee:** Martin, his wife, or both (`assignee_user_id` or `NULL`).
- **For whom:** any people (Martin, his wife, their child, household). People are not app users.
- **Category:** optional, created in the app (seed values with German display names: Wohnung/home, Soziales/social, Kalender/calendar, Besorgung/errands). Only the `calendar` category has special behavior.
- **Status:** `open`, `done`, `dismissed`. Done and dismissed todos can be reopened in the app.
- **Visibility:** both users see every todo; the list filters by mine / both / the other's.
- No subtasks.

### 4.3 Recurring todos

- The rule is stored as an RRULE and created in the app with simple pickers:
  - **Interval** ("every x days/weeks"): counts **from completion**. Completing creates the next instance immediately. There is always exactly one open instance.
  - **Calendar rule** ("the 15th of every 2nd month", "every 1st Monday"): fixed dates. If the old instance is still open, a new one is created anyway.
- **Assignee:** fixed (one person or both) or **rotating**: next up is whoever did **not** complete the last completed instance.
- Dismissed counts like done (the next instance is created) but does not count for rotation.
- **Only the server creates instances** (worker). This prevents duplicates from offline devices.
- **Reopening** an instance removes the next instance created for it, as long as that one is untouched.
- **Editing the series** applies to future instances and to the open instance unless it was edited individually. Pause stops new instances; delete asks whether the open instance goes too.

### 4.4 Category "calendar" (add appointment)

"New appointment" in the app does **not** write to Google. It creates a todo in the `calendar` category with the appointment data in `payload` (title, start, end, location, note, target calendar). The action "Open in calendar app" opens the calendar app with prefilled data (Android intent `ACTION_INSERT`); afterwards the todo is checked off.

---

## 5. Calendar

- Three sources, all accessible through Martin's Google account: his calendar, his wife's calendar, the shared one. Both users see all three.
- **Google Calendar API, read-only** (`calendar.readonly`). One OAuth login in the setup wizard. OAuth app set to "In production" without verification so refresh tokens do not expire after 7 days.
- The worker fetches incrementally every 5 min (`syncToken`), writes `calendar_events` (expanded recurrences, −1 to +12 months) and distributes them through the normal sync. Google does not allow `timeMin`/`timeMax` with `syncToken`, so the server applies the window itself. The device keeps **−1 to +3 months** locally, so all calendar views work offline; views stop at that window.
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
  - Entries **never expire** and are removed only after the server confirms them; they survive restarts, reboots, updates and schema changes.
  - An entry the server rejects permanently (validation error) is marked "failed" instead of blocking the queue or being deleted; the app offers "Erneut versuchen" / "Verwerfen".
  - Todos with unconfirmed changes show a **"Noch nicht gesendet"** marker; for an urgent todo sent to the other person it is prominent ("{name} wurde noch nicht benachrichtigt").
- **Last-write-wins per field group** (content, status, deletion). Deletion always wins. Overwritten changes go to the conflict log.
- **Clock skew:** every response contains the server time. The device stores the offset and uses it to correct the timestamps of its outbox entries. On a tie, whatever reached the server first wins.
- The **web app** writes directly via REST; the server sets timestamps itself.
- **Versions:** every request carries a protocol version header. The server supports the current and the previous protocol version, rejects app versions below a configured minimum with a clear error, and reports the latest app version so the app can show "Update verfügbar". Clients ignore unknown fields and tables.
- **Room schema changes on the device:** mirror tables may be dropped and re-synced; outbox, auth and sync state are migrated, never dropped.
- Every push is followed by a delta fetch. Afterwards the local DB matches the server.

---

## 8. App architecture

### 8.1 Layers

```
app/                      Expo app (TypeScript)
├─ theme/                 ThemeProvider; reads generated tokens from shared/design
├─ i18n/                  t() helper; reads shared/strings
├─ components/            base components: Button, Card, Text, Input, Badge, ListItem …
├─ screens/               Todos, Calendar, Settings, Delivery, Pairing, Login
├─ data/
│  ├─ repo.ts             shared interface and types (listTodos, saveTodo, completeTodo …)
│  ├─ repo.native.ts      → Kotlin engine                     [Android]
│  └─ repo.web.ts         → REST API                          [browser]
├─ plugins/               Expo config plugins (manifest, receivers, permissions, FCM service)
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
- **The engine owns the local DB exclusively.** The UI reads and writes only through `repo`. On Android `repo.native.ts` calls the module; in the browser `repo.web.ts` calls the API. Screens do not know where they run.
- **Native configuration only via config plugins** in `app/plugins/`. The generated `android/` folder is never edited by hand; prebuild overwrites it.
- **Plan B (not built unless needed):** a `specialUse` foreground service with a silent permanent notification, opt-in per device, if Samsung still stops background work. Specified in `docs/spec-engine.md`.
- The engine works without a running UI: notification actions ("Done") write directly to the DB and the outbox.
- The engine notifies the UI about changes via events; the UI then reloads.
- **Offline banner:** the engine also reports its sync status (`online` / `offline` / `server_unreachable`, number of unsent outbox entries) through `repo`. While the last sync attempt failed, every screen shows a small, non-dismissible banner ("Offline – Änderungen werden gespeichert und später synchronisiert", plus the count of unsent changes). It disappears after the next successful sync. On web the banner appears too, and editing is blocked until the server is reachable.

### 8.2 Design system

**Single source: `shared/design/tokens.json`.** Colors, spacing, radii, font sizes, font weights, shadows and durations, each color as a light and a dark value. Tokens have two layers:

- **Base tokens** (the palette): `color.blue.600`, `space.4`, `radius.md` …
- **Semantic tokens** (what components use): `color.bg.surface`, `color.text.muted`, `color.state.urgent`, `space.card.padding` … pointing at base tokens.

A redesign usually means changing base tokens or re-pointing semantic ones. Components only ever use semantic tokens.

A small generator script (`make tokens`, also run by CI and before every build) turns the JSON into the format each consumer needs:

| Consumer | Generated file | Uses |
|---|---|---|
| Expo app + web | `app/theme/tokens.generated.ts` | `StyleSheet` via ThemeProvider |
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
- If the server cannot be reached, the web app shows the offline banner and blocks editing (no outbox on web).

### 8.4 Language and UI strings

- Development language (code, docs, commits, specs) is **English**.
- User-facing text is **German** and lives in **one place: `shared/strings/de.json`**. This covers every surface: app and web screens, notifications generated by the engine (summaries, nagging, calendar), notifications generated by the server (activity, login approval), and the admin UI.
- **Keys by area**, e.g. `todo.action.done`, `notification.summary.title`, `settings.quietHours.label`. Code contains keys only, never German text.
- **Placeholders and plurals:** `"{count} dringende Todos"` with `one`/`other` forms (selected via the language's plural rules), so "1 dringende Todos" cannot happen.
- **One small `t(key, params)` helper per language** (TypeScript, Kotlin, Python), a few dozen lines each, same behavior, tested against shared test vectors (`shared/test-vectors/strings.json`).
- **Server notifications carry a key plus parameters**, not finished text. The device renders them with the same strings file. Display keys and wording therefore stay consistent no matter where a notification originates.
- How each consumer gets the strings: the Expo app and Python import the JSON directly; the Kotlin engine gets it copied into its assets at build time.
- **CI checks:** every key used in code exists in `de.json`; unused keys are reported; placeholders match between usage and text; a lint rule rejects German string literals in UI code.
- Changing wording = edit `de.json`, then a new build/deploy (texts are bundled). Runtime overrides via the admin UI could be added later; not part of the MVP.
- Adding another language later = add `en.json` with the same keys; the helpers already take a locale.

---

## 9. Security

**Android app**
- Pairing via one-time code (valid 10 min), generated in the admin UI or on an already paired device.
- Access token 15 min; refresh token per device, rotating, stored in the Android Keystore. Refresh tokens do not expire through inactivity.
- **Generous reuse rule:** after a rotation the previous token stays valid until the new one has been used once, so lost responses, dead zones and long flight mode never lock a device. Only an old token showing up **after** its successor was used locks the device (real theft signal).
- Devices can be revoked individually.

**Web app (both users)**
- Password (Argon2id) + **approval in the app**: all of the user's devices show "Approve browser login?" with a two-digit code that is also shown in the browser. Valid for 2 min.
- Fallback: recovery codes or a reset by the admin.
- Session cookie `HttpOnly`, `Secure`, `SameSite=Strict`, CSRF token, browser remembered for 30 days.

**Admin UI (Martin only)**
- Own subdomain behind Cloudflare Access (GitHub SSO), plus login with password + TOTP, role `admin`.
- **Access cannot be bypassed via the public VPS IP:** the backend validates the `Cf-Access-Jwt-Assertion` header (team keys, audience tag `CF_ACCESS_AUD`) on every admin-host request; missing or invalid → 404.

**General**
- Cloudflare proxy for both subdomains; WAF skip rule for the app subdomain (otherwise bot protection blocks the app).
- Rate limits and account lockout in the backend itself (the server is also reachable directly by IP). Client IP: the app trusts only Traefik and takes the rightmost `X-Forwarded-For` entry; if it is a Cloudflare address, the client IP is `CF-Connecting-IP`, otherwise that entry. The shared Traefik config is not changed.
- OpenAPI/docs endpoints not public.
- Secrets encrypted in the DB (AES-GCM with `MASTER_KEY`). Only DB access, `MASTER_KEY` and `SETUP_TOKEN` live in Coolify environment variables, plus the non-secret `CF_ACCESS_TEAM_DOMAIN` and `CF_ACCESS_AUD`.
- FCM messages carry no content.
- Audit log for logins, pairings, revocations, admin actions, secret changes.
- Pinned dependencies; `pip-audit` and `npm audit` in CI.

---

## 10. Operations

### Setup wizard
1. Set Coolify environment variables: `DATABASE_URL` (MariaDB), `MASTER_KEY`, `SETUP_TOKEN`, `CF_ACCESS_TEAM_DOMAIN`, `CF_ACCESS_AUD`.
2. First visit to the admin subdomain → wizard, only with `SETUP_TOKEN`.
3. Create admin account with password + TOTP.
4. Upload Firebase service account → test push to a test device.
5. Second user account, people, time zone, default times.
6. Wizard locks itself. Changes afterwards via the admin UI; secrets are never shown in plain text again.
7. Later (C3, admin UI → Settings): enter Google OAuth client → Google login → select and assign calendars → test fetch.

### Admin UI
Delivery (per display and device) · Devices (pairing, lock, token status) · Statistics (delivery rate, delay median/p95, completed todos) · Activity · Conflicts · Logs (errors, calendar, FCM, audit) · Settings (secrets, calendars, users, defaults, level thresholds) · Tools (test notification, wake-up).

### Deployment and migrations
- Coolify deploys only the `release` branch; only Martin moves it.
- On start the worker runs `alembic upgrade head` under a DB lock, then starts the scheduler. `api` answers `/api/health` with 503 until the schema matches its code.
- Migrations are additive (expand/contract), so a bad release can be rolled back by redeploying the previous image.

### Backups
After the MVP: scheduled Coolify DB backup to external storage plus a restore test. Automatic backups are switched on at checkpoint C3.

### App distribution
Signed APK from CI (signing only in the protected GitHub Environment `release`), installed directly or via Firebase App Distribution; no Play Store. No development builds on the phones. The app shows "Update verfügbar" when the server reports a newer version.

---

## 11. Tech stack

| Area | Technology |
|---|---|
| App UI | Expo (managed workflow + development build, config plugins), React Native, TypeScript, `StyleSheet`, React Navigation |
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
- Samsung may restrict background work despite settings. The reliability check, watchdog and heartbeat make this visible. Plan B: `specialUse` foreground service (see 8.1).
- `setAlarmClock()` shows an alarm icon and becomes the system's "next alarm" (default decided at C1, see 3.4).
- Nothing outside the phones watches the server: if the worker is down, devices notice only through failing syncs (system notification after 3 h).
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
