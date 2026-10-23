# Decisions

Status: 2026-10-22, all planning questions resolved (translated to English and codename changed to `famapp` on 2026-10-23). Pre-development review on 2026-10-23 closed the remaining gaps (section 10). This document records what was decided and why. README and BUILDPLAN build on it.

Legend: ✅ decided by Martin · 🟡 proposal; implemented this way unless someone objects

---

## 1. Platform and devices

- ✅ Both devices are Android: one Samsung, one Pixel.
- ✅ Devices get replaced now and then. All state lives on the server. A new device is registered with a pairing code, fetches everything via sync and re-plans its alarms. Old devices can be signed out (token revoked).
- ✅ No iOS support planned, but the architecture does not rule it out.
- ✅ Additional **web access** from the same codebase (Expo Web), without native features, **for both users**.

## 2. Frontend

- ✅ Expo (managed workflow with development build), **TypeScript** (changed from JavaScript on 2026-10-23: types catch mistakes at the `repo` ↔ Kotlin bridge, switching later would be expensive).
- ✅ Native Android configuration (manifest entries, receivers, permissions, `FirebaseMessagingService`, Gradle plugins) only via **Expo config plugins**. The generated `android/` folder is never edited by hand (prebuild overwrites it).
- ✅ Styling via `StyleSheet`, no CSS.
- ✅ **Design system and design tokens managed centrally** (decided 2026-10-23): one source for every surface.
  - ✅ `shared/design/tokens.json` with base tokens (palette) and semantic tokens (what components use). A generator produces the files for the Expo app, the admin UI (CSS custom properties) and Android resources (notification colors). Details: README 8.2.
  - 🟡 Small set of own base components (`Button`, `Card`, `Text`, `Input`, `Badge`) as the only place where tokens become styles. Screens compose them. A redesign touches `tokens.json` and at most these components.
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
  - ✅ User-facing text stays German.
  - ✅ **All UI strings in one central place** (decided 2026-10-23): `shared/strings/de.json`, used by the app, the Kotlin engine (notifications), the backend (server notifications, admin UI). Keys instead of text in code, placeholders and plural forms, a small `t()` helper per language, CI checks for missing/unused keys. Server notifications carry key + parameters. Details: README 8.4.
  - 🟡 Wording changes need a new build/deploy; runtime overrides via the admin UI are a possible later addition.

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
- ✅ **Client IP behind Traefik** (decided 2026-10-23): the request chain is Cloudflare → Coolify's Traefik → app, so the app sees Traefik's address. The app trusts only Traefik, takes the **rightmost** `X-Forwarded-For` entry (the address that connected to Traefik); if it lies in Cloudflare's IP ranges, the client IP is `CF-Connecting-IP`, otherwise that entry. The shared Traefik config stays untouched.
- ✅ **Cloudflare Access must not be bypassable** (decided 2026-10-23): because the VPS IP is public, anyone could reach the admin host directly. The backend therefore validates the `Cf-Access-Jwt-Assertion` header (signature against the team's public keys, audience tag) on every admin-host request; missing or invalid → 404. Then password + TOTP as before.

### Security

- **App (Android):** pairing code (one-time, valid 10 min, generated in the admin UI or on a paired device) → refresh token per device in the Android Keystore, short-lived access token (15 min). Refresh tokens rotate.
  - ✅ **Generous reuse rule** (decided 2026-10-23): a device must never lock itself out through lost connections, dead zones or long flight mode. Refresh tokens do **not** expire through inactivity. After a rotation the **previous token stays valid until the new one has been used once** (no time limit), so a lost refresh response is simply retried. The device is locked only if an old token shows up **after** its successor was already used (two diverging token chains = real theft signal). Tests cover: lost response + retry, weeks offline, true theft.
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
- ✅ Plus two **non-secret** values, needed before the wizard can be protected: `CF_ACCESS_TEAM_DOMAIN` and `CF_ACCESS_AUD` (audience tag of the Access application). Without them the admin host refuses every request, unless the dev flag `FAMAPP_DEV=1` is set (never in production).
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

- ✅ FCM only as a wake-up call (data message without content).
- ✅ **Priority rule** (decided 2026-10-23): FCM may downgrade apps whose high-priority messages do not lead to visible notifications. Therefore **high priority only when the device is expected to show something now**: explicit urgent (new), login approval, activity notification due now, and watchdog retries for those. Everything else (status change → cancel nagging, settings/calendar changes, watchdog retries for summaries, heartbeat, test wake-ups without display) goes out as **normal priority** with a `collapse_key`.

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
| **Scheduled reminder** | local alarm at `due_at` (optional lead time) | high | see "Scheduled todos" below |
| **Urgent (time-based)** | local alarm when a horizon todo becomes "urgent", or a scheduled todo is past `due_at` | high | **one combined notification per user** for all time-based urgent/overdue todos, re-posted hourly until none are left. Not during quiet hours. |
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
- ✅ **Time-based nagging is combined** (decided 2026-10-23): all time-based urgent and overdue todos of a user share **one** notification ("3 fällige Todos: …", up to 3 titles, overdue first), re-posted hourly with the same ID. Actions open the list; "Done"/"Postpone" per todo happen in the app. Explicitly urgent todos stay individual notifications (every 15 min, with "Done"/"Snooze").
- 🟡 Technically the planner includes the next nag time of every open nagging todo in its single alarm (respecting quiet hours and snooze). When it is completed on one device, an FCM wake-up goes to all other devices, which cancel the alarm. Without a network it keeps nagging until sync brings the status. Snooze applies per user (synced so it pauses on all of that user's devices).
- 🟡 DND bypass: own channel with `setBypassDnd(true)`. Android requires a one-time "Do Not Disturb access" grant; the app requests it in the setup flow.

### Normal

- 🟡 Normal notifications during quiet hours are collected and shown as **one** notification at the start of active time ("Since 22:00: 4 changes").
- 🟡 Outside quiet hours: several changes by the same person within 2 min are batched.
- ✅ **Triggers** (decided 2026-10-23): only two actions of the other person create an activity notification for me:
  1. a new todo assigned to me or to both,
  2. a todo assigned to me or to both, or created by me, is completed or dismissed.
  Edits and deletions do not notify (visible in the list and the admin activity log).

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
- ✅ **Visibility** (decided 2026-10-23): both users see every todo, regardless of assignee. The list offers filters (mine / both / the other's). Sync therefore does not filter todos per user.
- ✅ **Undo** (decided 2026-10-23): after "Done" from a notification, the notification turns into "Erledigt – Rückgängig" for 30 s. Done and dismissed todos can be reopened from the app (status field group). Reopening a series instance removes the next instance the server created for it, as long as that one is still untouched; otherwise both stay open.

### Scheduled todos

- ✅ (decided 2026-10-23) A notification at `due_at`; optional lead time per todo (none / 15 min / 1 h / 1 day; default none) as an additional earlier notification.
- ✅ If not done at `due_at`, the todo becomes `overdue` and joins the combined time-based nag notification (hourly) until done or postponed.
- 🟡 A `due_at` or lead time inside quiet hours: the reminder is still shown once at that time (the user picked the time explicitly), without DND bypass; nagging only starts when active time begins.

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
| kind `scheduled` | scheduled; "today" on the day itself; `overdue` after `due_at` |
| series instance | relative thresholds, see "Recurring todos" |

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
- 🟡 Every instance gets a `target_date` and moves through the levels (mid term → urgent → overdue). Whether a series creates horizon todos or scheduled todos (fixed time) is part of the template.
- ✅ **Relative thresholds for series instances** (decided 2026-10-23): with the absolute "< 1 week" rule, "every 2 weeks" would nag for a full week each cycle. A series instance becomes `urgent` only in the **last 25 % of its interval**, at least 1 day before `target_date`. 🟡 Capped at the normal 1-week threshold, so "every 6 months" does not nag for 6 weeks. Before that it is `mid_term` (or `long_term` if > 4 weeks away). Covered by `shared/test-vectors/levels.json`.
- ✅ **Editing a series** (decided 2026-10-23): template changes apply to future instances and to the open instance, unless that instance was edited individually. Pause: no new instances, the open one stays. Delete: the app asks whether the open instance should be deleted too.

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
- 🟡 Incremental fetch every 5 min via `syncToken`. Calendar events go through the normal rev sync. (Google does not allow `timeMin`/`timeMax` together with `syncToken`; the server applies its time window itself.)
- ✅ **Local window on the phone** (decided 2026-10-23): −1 to +3 months, so agenda, week and month views work fully offline. The server keeps −1 to +12 months. Views do not navigate beyond the local window in the MVP.

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
UI (Expo, TypeScript)
  └─ data/repo.ts          ← shared interface: listTodos(), saveTodo(), completeTodo() …
        ├─ repo.native.ts  → Kotlin engine (local DB, outbox, sync)        [Android]
        └─ repo.web.ts     → REST API directly                             [browser]

Kotlin engine "famapp-engine"
  ├─ engine-core (pure Kotlin): planner, levels, quiet hours, nag times, sync and conflict logic
  └─ engine-android:
       ├─ Room DB: todos, series (read-only), categories, people, calendar_events (−1 to +3 months),
       │           notifications, deliveries, settings, todo_snoozes, outbox, sync_state
       ├─ alarm: the one exact alarm, WorkManager jobs
       ├─ display: channels, batching, actions "Done"/"Snooze"/"Postpone"
       └─ events to the UI: "data changed" → UI reloads
```

- The UI does not know whether it runs on Android or in the browser; only the `repo` implementation differs.
- Estimated size of the Kotlin engine: 4,000–6,000 lines (sync, Room, planner, display, receivers, bridge). Work packages are sized accordingly.

---

## 10. Pre-development review (2026-10-23)

Gaps found before development started, decided by Martin. Decisions that change an earlier section are recorded there as well.

### Delivery and reliability

- ✅ **Watchdog covers all classes.** The server computes the expected display keys not only for summaries but also for nags (explicit and combined time-based), scheduled reminders and calendar notifications, with the same rules as the engine (shared test vectors). Missing ack → wake-up, then "late/missing". An explicit urgent todo is displayed under `nag:<todo-id>`; its first display gets the 2/10/60 min retry schedule. This makes "no lost notification" measurable.
  - 🟡 Delivery records are kept per repetition: the Android notification ID comes from the base key (`nag:<todo-id>`), the delivery key adds the planned minute (`nag:<todo-id>@2026-11-02T14:15Z`).
- ✅ **Server monitoring: device-side only.** No external monitoring service. If the device **has network but sync fails** for 3 h outside quiet hours, the engine shows a local notification "Server nicht erreichbar" (once, then again after 24 h). Flight mode or dead zones (no network) never trigger it.
- ✅ **Offline banner in the app** (decided 2026-10-23): whenever the app cannot reach the server, a small banner is visible on every screen, including while creating or editing todos, so it is clear that changes are only stored on the phone for now.
  - Shown as soon as the last sync attempt failed (no network **or** server unreachable), hidden after the next successful sync. No delay, no 3 h threshold (that applies only to the system notification).
  - Text (German, in `de.json`): "Offline – Änderungen werden gespeichert und später synchronisiert", plus the number of unsent changes if there are any ("3 Änderungen noch nicht synchronisiert").
  - 🟡 Two wordings: no network → "Offline"; network available but server unreachable → "Server nicht erreichbar". Same banner, same behavior.
  - 🟡 Not dismissible; small and unobtrusive (one line, semantic token `color.state.offline`), does not block editing.
  - Web (online only): the same banner, but there editing is blocked until the server is reachable again, because the web app has no outbox.
- ✅ **The outbox never loses changes** (decided 2026-10-23): outbox entries never expire and are never dropped, however long the server is unreachable. They are only removed after the server has confirmed them. They survive app restarts, reboots, app updates and Room schema changes.
  - 🟡 If the server **rejects** an entry permanently (validation error, not a network error), it is not retried forever and not silently deleted: it is marked "failed", the queue continues with the next entry, and the app shows the affected todo with "Änderung konnte nicht gespeichert werden" plus "Erneut versuchen" / "Verwerfen". Failures are also logged in the admin UI.
- ✅ **"Noch nicht gesendet" marker** (decided 2026-10-23): a todo whose changes are still in the outbox shows a small marker in the list and the detail view. For an explicitly urgent todo sent to the other person the marker is prominent ("Noch nicht gesendet – {name} wurde noch nicht benachrichtigt"), so the sender knows to call instead. The marker disappears once the server has confirmed the change.
  - The "Server nicht erreichbar" system notification adds: "Dringende Todos werden erst zugestellt, wenn der Server wieder erreichbar ist." if urgent todos are waiting in the outbox.
- ✅ **Alarm type: decided at C1.** The engine implements both `setAlarmClock()` (never delayed, but status-bar icon, becomes the system's "next alarm" and ends DND schedules early) and `setExactAndAllowWhileIdle()` (no side effects, at most about one alarm per 9 min in Doze, which the single-alarm planner rarely hits). Switchable via an engine setting. Default until C1: `setAlarmClock()` for high-priority entries. At C1 Martin picks the default after the observation week.
- ✅ **Plan B foreground service: specify now, build only if needed.** Documented in `docs/spec-engine.md` as a `specialUse` foreground service (allowed outside the Play Store; `dataSync` is limited to 6 h per day since Android 15) with a silent permanent notification, opt-in per device. Built only if C1 or the observation week shows misses.
- ✅ **Backups stay at C3** (unchanged). Accepted risk: data from daily use during C2/Run 4 is unprotected until then.

### Deployment and versions

- ✅ **Migrations: the worker migrates, forward-only.** On start the worker runs `alembic upgrade head` under a DB lock before starting the scheduler. `api` reports `/api/health` as "not ready" (503) until the schema matches its code. Migrations are **additive** (expand/contract: add first, remove in a later release), so a bad release can be rolled back by redeploying the previous image. Destructive steps still need Martin's approval.
- ✅ **App/server version compatibility:**
  - every app request carries a protocol version header; the server supports the current and the previous protocol version,
  - the client ignores unknown fields and tables,
  - the server knows a minimum supported app version and refuses older ones with a clear error shown in the app,
  - the server knows the latest app version (from the `release` build) and the app shows "Update verfügbar" (also visible in the admin UI per device).
- ✅ **Room schema on the phone:** mirror tables may be dropped and fully re-synced on a schema change. Outbox, auth and sync-state tables only get real migrations and are never dropped. Tested in CI.
- ✅ **No development builds on the phones.** The phones only run signed release APKs. Live reload only in the emulator (notebook) or Expo web. No separate `.dev` app ID.
- ✅ **Only Martin moves `release`.** At the end of a run the agent writes the checkpoint file and asks Martin (issue + note in `docs/progress.md`) to move `release`.

### CI and GitHub

- ✅ **The repository is public during development** so GitHub Actions minutes are free and the emulator suite can run on every PR that touches `app/`. **Reminder: make it private again at C3** (item in the C3 checklist). Consequences: no secrets, personal data or todo contents in the repo, issues or logs; `google-services.json` is public (acceptable, the key is restricted to the package).
- ✅ **One required check:** an always-running job `ci-gate` that depends on all other jobs and treats skipped jobs as OK. Branch protection requires only `ci-gate`, so path filters never block a merge.
- ✅ **Signing key only in a GitHub Environment `release`**, restricted to the `release` branch, with Martin as required reviewer. PR and `main` builds are debug-signed and only exist as CI artifacts. Workflows from forks never get secrets.
- ✅ Agents use **Martin's `gh` login** in code-server (no separate token). Accepted risk: agents technically have Martin's GitHub rights; the rules in `AGENTS.md` (never touch `release`, branch protection or other repos) apply.

---

## Open questions

None. Not yet decided but not blocking: the app's display name, final categories.
