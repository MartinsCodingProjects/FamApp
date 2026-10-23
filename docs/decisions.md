# Decisions

Status: 2026-10-22, all planning questions resolved (translated to English and codename changed to `famapp` on 2026-10-23). Pre-development review on 2026-10-23 closed the remaining gaps (section 10); the nagging review on the same day reworked levels, nag times and snooze (section 11). This document records what was decided and why. README and BUILDPLAN build on it.

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
- ✅ **Every high-priority wake-up ends in a visible notification** (decided 2026-10-23, section 11): if the sync after a high-priority wake-up brings nothing new to show (typical case: watchdog retry for a display that was shown but whose ack got stuck), the engine silently re-posts the affected display with the same ID. Details: section 11.

## 5. Notifications

All times, intervals and switches in this section are **configurable per user in the app** (defaults in brackets).

### Quiet hours

- ✅ Per user, default 22:00–06:00. Since 2026-10-23 configurable **per weekday**, plus notification modes and a weekly mode schedule on top (section 12).
- ✅ **During quiet hours: no nagging and no normal notifications.**
- ✅ Only exception: an explicitly urgent todo that is **newly sent** during quiet hours appears **once**. Then it pauses; nagging starts when active time begins.
- 🟡 This one-time night notification uses the high channel but does not bypass Do Not Disturb.
- 🟡 Anything else that accumulates during quiet hours is delivered at the start of active time (see each class).
- ✅ **The day starts with the first summary** (decided 2026-10-23, section 11): nagging (explicit and overdue) only runs inside the **nag window**, from the day's first summary until quiet hours start. Between the end of quiet hours and the first summary the quiet-hours rules for nagging and activity notifications still apply. Weekends start later automatically because summaries are per weekday.

### Classes

| Class | Trigger | Channel | Behavior |
|---|---|---|---|
| **Summary** | local exact alarm at configured times; content built locally at display time | high | server watchdog checks the ack; wake-up after 15 min |
| **Urgent (explicit)** | immediately via FCM wake-up → sync → display | own channel, bypass DND (configurable) | repeats (every 15 min) until done. During quiet hours only once when newly created, no nagging. |
| **Scheduled reminder** | local alarm at `due_at` (optional lead time) | high | see "Scheduled todos" below |
| **Overdue (time-based)** | local alarm at the next overdue slot while a horizon todo is past `target_date` or a scheduled todo is past `due_at` | high | **one combined notification per user** for all overdue todos, at **4 overdue slots per day** inside the nag window (section 11). Todos that are only `due_soon` do not nag; they appear in summaries. |
| **Normal** | FCM wake-up, may be batched | normal | collected during quiet hours and until the first summary, then delivered as part of the first summary |
| **Calendar** | local alarms from calendar data | normal | evening before, morning of, start time (rules below) |

### Summaries

- ✅ Times configurable per user.
- 🟡 Configurable per weekday (e.g. Mon–Fri 07:00/12:30/19:00, Sat–Sun 09:00/13:00/19:00); each time can be disabled individually.
- ✅ Content: number of urgent todos with a mini preview, number of other todos, calendar events.
- 🟡 Mini preview: up to 3 todos (explicit urgent first, then overdue, then `due_soon`), the rest as "+ 2 more". Events: count for today, first event with time.
- ✅ (decided 2026-10-23, section 11) Summaries are the only notification that shows `due_soon` todos. The day's **first summary also carries the quiet-hours catch-up** ("Seit 22:00: 4 Änderungen"). If a day has no summary, the catch-up is its own notification at the end of quiet hours.
- 🟡 Tapping opens the "Urgent" view.

### Urgent and nagging

- ✅ Both users may send urgent todos to the other, to themselves or to both.
- ✅ **Does not stop when tapped, only when the todo is done.**
- ✅ Explicitly urgent: repeats every 15 min (configurable).
- ~~✅ Urgent through elapsed time: repeats once per hour (configurable).~~ Replaced 2026-10-23 (section 11): only **overdue** todos nag, at 4 overdue slots per day; `due_soon` does not nag.
- ✅ **Both kinds pause during quiet hours.** ~~Nagging resumes immediately when active time starts.~~ Changed 2026-10-23 (section 11): nagging resumes at the day's first summary.
- ✅ If an explicitly urgent todo is sent during the recipient's quiet hours, it appears once immediately (without nagging); nagging starts when their nag window begins (first summary, section 11). The sender sees "Ruhezeit bis 07:00, danach Erinnerungen alle 15 Min." in the app (time = recipient's next nag window start).
- ✅ Bypass Android Do Not Disturb: configurable per user. Only applies outside the user's own quiet hours.
- ✅ Sent to "both": once one completes it, nagging stops for both.
- ✅ **Snooze** for explicitly urgent todos: pauses nagging (default 30 min, configurable). Afterwards it continues until done. Extended 2026-10-23 (section 11): additionally "2 Std." and "Bis morgen", and snooze also exists for the combined overdue notification.
- 🟡 An explicitly urgent message is always a todo (kind `immediate`). Actions in the notification: "Done", "Mach ich" and "Snooze" (section 11).
- ✅ **Time-based nagging is combined** (decided 2026-10-23): all overdue todos of a user share **one** notification ("3 überfällige Todos: …", up to 3 titles, oldest first), re-posted at each overdue slot with the same ID. Tapping opens the list; "Done"/"Postpone" per todo happen in the app; the notification itself offers "Snooze 2 Std." / "Bis morgen". Explicitly urgent todos stay individual notifications (every 15 min, with "Done"/"Mach ich"/"Snooze").
- 🟡 Technically the planner includes the next nag time of every open nagging todo in its single alarm (respecting quiet hours and snooze). When it is completed on one device, an FCM wake-up goes to all other devices, which cancel the alarm. Without a network it keeps nagging until sync brings the status. Snooze applies per user (synced so it pauses on all of that user's devices).
- 🟡 DND bypass: own channel with `setBypassDnd(true)`. Android requires a one-time "Do Not Disturb access" grant; the app requests it in the setup flow.

### Normal

- 🟡 Normal notifications during quiet hours (and until the first summary) are collected and shown as **one** line in the day's first summary ("Since 22:00: 4 changes"); without a summary that day, as one notification at the end of quiet hours. The device builds this from the synced `notifications` rows, so it is a device-planned display covered by the summary watchdog.
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
- ✅ Long term automatically becomes mid term; mid term automatically becomes due soon (level renamed from "urgent" on 2026-10-23, section 11).
- ✅ No subtasks.
- ✅ Categories optional. Initial ideas: Wohnung (home), Soziales (social), Kalender (calendar), Besorgung (errands).
- ✅ Assignee: Martin, his wife, or both.
- ✅ "For whom": people, including their child.
- ✅ **Visibility** (decided 2026-10-23): both users see every todo, regardless of assignee. The list offers filters (mine / both / the other's). Sync therefore does not filter todos per user.
- ✅ **Undo** (decided 2026-10-23): after "Done" from a notification, the notification turns into "Erledigt – Rückgängig" for 30 s. Done and dismissed todos can be reopened from the app (status field group). Reopening a series instance removes the next instance the server created for it, as long as that one is still untouched; otherwise both stay open.

### Scheduled todos

- ✅ (decided 2026-10-23) A notification at `due_at`; optional lead time per todo (none / 15 min / 1 h / 1 day; default none) as an additional earlier notification.
- ✅ If not done at `due_at`, the todo becomes `overdue` and joins the combined overdue notification (at the overdue slots, section 11) until done or postponed.
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

todo_snoozes (todo_id, user_id, until)   -- "Snooze", per user; todo_id NULL = combined overdue notification (section 11)
todo_claims  (todo_id, user_id, claimed_at) -- "Mach ich" on an explicit urgent todo (section 11)
people       (id, name, user_id NULL)    -- Martin, wife, child, household
categories   (id, slug, name, color, icon, sort_order, active)
```

### Level computation

| Time left until `target_date` | Displayed level |
|---|---|
| > 4 weeks | `long_term` |
| 1 to 4 weeks | `mid_term` |
| < 1 week | `due_soon` (renamed from `urgent` 2026-10-23; shown in summaries, **no nagging**) |
| past | `overdue` (combined notification at the 4 overdue slots) |
| kind `immediate` | explicit urgent; after the recipient's next quiet-hours start it counts as `overdue` (section 11) |
| kind `someday` | someday (never changes) |
| kind `scheduled` | scheduled; "today" on the day itself; `overdue` after `due_at` |
| series instance | relative thresholds, see "Recurring todos" |

- 🟡 Thresholds configurable centrally (admin UI).
- 🟡 "Postpone" action: sets a new target date (1–4 weeks / 1–3 months from today), which also ends nagging. For scheduled todos see section 11.
- 🟡 Sort order: explicit urgent → overdue → due soon → scheduled today → mid term → long term → someday.

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
- 🟡 Every instance gets a `target_date` and moves through the levels (mid term → due soon → overdue). Whether a series creates horizon todos or scheduled todos (fixed time) is part of the template.
- ✅ **Relative thresholds for series instances** (decided 2026-10-23): with the absolute "< 1 week" rule, "every 2 weeks" would be due soon for a full week each cycle. (Since section 11, `due_soon` no longer nags, so this now only decides when an instance shows up as "due soon" in the list and summaries.) A series instance becomes `due_soon` only in the **last 25 % of its interval**, at least 1 day before `target_date`. 🟡 Capped at the normal 1-week threshold, so "every 6 months" does not nag for 6 weeks. Before that it is `mid_term` (or `long_term` if > 4 weeks away). Covered by `shared/test-vectors/levels.json`.
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

## 11. Nagging review (2026-10-23)

Review of the priority system against notification volume. Finding: the bigger risk is not lost notifications but too many. If the users mute the `due` channel, delivery reliability no longer matters. Decided by Martin; the earlier sections are marked where they changed.

### Levels and what nags

- ✅ **The computed level `urgent` is renamed `due_soon`** ("bald fällig"). "Urgent" now only means the explicit kind `immediate`. Levels: `long_term` / `mid_term` / `due_soon` / `overdue`.
- ✅ **`due_soon` does not nag.** It shows in the list (sorted high) and in summaries. That also takes care of short series intervals (daily, every 3 days): they are `due_soon` most of the time, which no longer causes notifications.
- ✅ **Only `overdue` nags**, as one combined notification per user, at **4 overdue slots per day** (replaces the hourly rhythm).

### Nag window and overdue slots

- ✅ **Nag window** = from the day's **first summary** until **quiet hours start**. Explicit and overdue nagging only happen inside it. Without a summary that day, the window starts at the end of quiet hours.
- ✅ Before the first summary, the quiet-hours rules apply to nagging and activity notifications (an explicit urgent todo that is sent then appears once, without DND bypass; activity is collected). Scheduled reminders, calendar notifications and login approvals are unaffected (the user chose those times, or triggered the approval).
- ✅ **Overdue slots are computed, not configured:** the nag window is cut at each summary time into gaps; while there are fewer than 4 gaps, the largest one is split in half; each slot is the midpoint of a gap, rounded to 5 min. Gaps shorter than 60 min get no slot (so every slot is ≥ 30 min from a summary). More than 4 gaps → the 4 largest get a slot.
  - Example (quiet hours 22–06, summaries 07:00 / 12:30 / 19:00): window 07:00–22:00 → gaps 07:00–12:30, 12:30–19:00 (split at 15:45), 19:00–22:00 → slots **09:45, 14:10, 17:25, 20:30**.
  - Without summaries that day: the window is split into 4 equal parts, slot = midpoint of each.
- 🟡 A todo that becomes overdue between slots waits for the next slot (a scheduled todo has just had its `due_at` reminder; a horizon todo becomes overdue at midnight).
- 🟡 Explicit urgent nagging stays every 15 min, counted from the time it was sent; outside the nag window it pauses, and at the window start the next 15-min step continues the rhythm.
- 🟡 Due date semantics: a horizon todo is `overdue` from 00:00 (user's time zone) on the day after `target_date`; a scheduled todo from `due_at`.

### Snooze

- ✅ **Snooze options "2 Std." and "Bis morgen"** for both explicit urgent notifications (in addition to the 30-min default) and the **combined overdue notification**.
- 🟡 "Bis morgen" = until the start of tomorrow's nag window.
- 🟡 Combined snooze is stored per user in `todo_snoozes` with `todo_id = NULL` (synced, so it applies to all of that user's devices). It also covers todos that become overdue during the snooze.
- 🟡 "2 Std." on the combined notification: all slots inside the snooze are skipped and replaced by **one** display at the snooze end (if it falls inside the nag window); if the next regular slot is less than 60 min after that, that slot is skipped too.

### Explicit urgent todos

- ✅ **Action "Mach ich"** (claim): the recipient confirms they are on it.
  - Nagging for the claiming user slows to hourly (configurable).
  - Sent to "both": the claimer takes over; nagging for the other user stops.
  - The sender gets an activity notification ("{name}: Mach ich").
  - Stored in `todo_claims`, synced; a later "Done" or "Dismiss" ends it as usual.
- ✅ **Delivery status visible to the sender:** the todo shows per recipient "Zugestellt {time}" (shown on at least one device, from `deliveries`) and "Mach ich {time}". The server derives this and syncs it with the todo to the sender (read-only fields, no extra table on the device).
- ✅ **End-of-day downgrade:** an open explicit urgent todo that has gone through the start of the recipient's quiet hours since it was sent counts as `overdue` from then on: it leaves the 15-min nag and joins the combined overdue notification. **Computed, not stored** (no write, no conflict); covered by the level vectors. A todo sent during quiet hours is only downgraded at the *next* quiet-hours start.

### Postpone

- ✅ Postpone also offers short options: **"Morgen"** and **"+3 Tage"**, in addition to 1–4 weeks / 1–3 months.
- 🟡 For scheduled todos, postpone moves `due_at` by the same amount and keeps the time of day (a new reminder at the new `due_at`); a lead time stays relative to it.

### Series

- ✅ **New per-series flag "Neue Instanz ersetzt die offene"** (`replace_open`, default **on** for calendar rules; irrelevant for interval series, which never have two open instances). When the worker creates a new instance and the previous one is still open, the previous one is set to `dismissed` by the system. Like any dismiss it does not count for rotation, and it does not trigger an activity notification (no person acted). Turned off, instances stack as before.
- 🟡 The relative thresholds stay but now only decide when an instance shows as `due_soon`. No extra rule for intervals ≤ 1 day is needed, because `due_soon` no longer nags.

### Several notifications at the same moment

- ✅ **One sound per alarm firing:** everything due at that minute is posted, but only the most important display plays a sound (explicit urgent > overdue > scheduled reminder > summary > calendar > activity > system); the rest post silently. This also avoids Android 15+ "notification cooldown" turning later ones down.

### Push and sync

- ✅ **Sync before display:** when the alarm fires and the device has network, the engine syncs first (timeout 5 s), then decides what to show. After the timeout it shows from local data. This stops nags for todos the other person already completed while the "cancel" wake-up (normal priority) is still held back by Doze.
  - To verify at C1: how much network access each alarm type gets in Doze (`setAlarmClock` brings the device out of idle; check `setExactAndAllowWhileIdle`). Part of the alarm-type decision.
- ✅ **Measure it** (decided 2026-10-23): the engine records every alarm firing (planned and actual time, alarm type, whether the device was idle/Doze, network available, sync result `ok` / `timeout` / `error` / `no_network`, sync duration) and sends it to the server through the outbox (operation `alarm_firing`, table `alarm_firings`, not synced back). The admin UI shows the share of firings whose sync finished within the timeout, per device and alarm type, split by idle/not idle.
  - 🟡 So that alarms fire in Doze before Run 3 (no summaries or nags yet), the observation job (BUILDPLAN 2.12) also creates **device-planned test displays** (a scheduled server notification the device shows via its own alarm), several times a day, preferably at times when the phone is likely idle.
  - **Decided at C1, together with the alarm type:**
    1. default alarm type (as before);
    2. if `setExactAndAllowWhileIdle()` wins but sync fails too often in Doze (🟡 threshold: under 95 % `ok` among idle firings with network): (a) `setAlarmClock()` only for alarms that show a nag or reminder, (b) accept occasional stale nags, or (c) a different timeout;
    3. whether the up-to-5-second display delay is acceptable (from the measured sync durations).
- ✅ **Re-post on high-priority wake-up:** if a high-priority wake-up leads to no new display (e.g. watchdog retry after the ack got stuck), the engine re-posts the affected display **silently** with the same ID. It picks the open display with a pending or just-sent ack; if there is none, the most recent active high-channel display. So every high-priority push is followed by a visible notification and FCM has no reason to deprioritize the app. FCM still carries only `{"t":"sync"}`.

### Nagging metrics

- ✅ **In the admin UI** (Statistics → "Nerv-Level"), not in the app: notifications per user and day by class, counts of snooze / postpone / "Mach ich" / Done-from-notification, and a warning when a channel was muted or set to a lower importance.
- 🟡 Counts come from `deliveries` (already one record per display) and the sync operations. The device reports app notification permission and channel importance with each sync (a small `device_status` field on `devices`); a change to "muted" is logged.
- 🟡 Checked at C2 together with the observation results. Rough target: no user gets more than ~10 nags on a normal day.

---

## 12. Notification modes, per-user settings, activity view (2026-10-23)

Decided by Martin. Builds on section 11.

### Three modes per user

| Mode | German label | What notifies |
|---|---|---|
| `remind` (default) | "Erinnern" | everything as described in sections 5 and 11 (full nagging) |
| `essentials` | "Nur Wichtiges" | summaries; activity notifications (new todo for me/both, completed/dismissed, "Mach ich"); explicit urgent **once** (no repetition); scheduled reminder and lead time **once**; calendar notifications; "Server nicht erreichbar"; login approvals. **No nagging:** no 15-min repeats, no overdue slots; overdue todos only appear in summaries |
| `dnd` | "Nicht stören" | **nothing**, except web login approvals (only triggered by the user's own action) |

- ✅ Modes are per user, synced, so they apply to all of that user's devices.
- ✅ **Quiet hours keep applying on top** in `remind` and `essentials` (night rules from section 5). In `dnd` they do not matter.
- ✅ **Manual switch with an end:** switching the mode by hand asks for the end: "1 Std." / "Bis morgen" (= start of tomorrow's nag window) / "Bis ich es ausschalte". The manual mode overrides the schedule until it ends.
- ✅ **Weekly mode schedule:** per user, slots of (weekdays, start, end, mode `essentials` or `dnd`), e.g. Mon–Fri 09:00–17:00 "Nur Wichtiges". Outside slots the mode is `remind`.
  - 🟡 Mode slots must not overlap each other (the app validates). They may overlap quiet hours; then both apply, and `dnd` beats everything.
  - 🟡 **Effective mode** at time *t* = active manual mode, otherwise the schedule slot covering *t*, otherwise `remind`. One pure function in all three languages, covered by `shared/test-vectors/modes.json`.
- ✅ **While not in `remind`, the app shows a permanent banner** ("Nicht stören bis 07:00", "Nur Wichtiges bis 17:00").
- ✅ **The sender sees the recipient's mode:** when sending an explicit urgent todo to someone in `essentials` or `dnd`, the app shows e.g. "Martin: Nicht stören bis 07:00 – erst danach" or "Martin: Nur Wichtiges – erscheint einmal, keine Wiederholungen". So both users sync each other's mode, mode end and schedule (not the rest of the settings).
- ✅ **End of `dnd`:** one catch-up notification with what happened in the meantime: activity, missed scheduled reminders (count), open explicit urgent and overdue count. If the end falls into quiet hours or before the first summary, this goes into the first summary instead. Explicit urgent todos that were sent during `dnd` and never shown then appear **once as their own notification**, and the rules of the new mode continue from there. Missed calendar notifications are dropped.
- 🟡 After an `essentials` or `dnd` period ends during the day, nagging resumes right away (the next 15-min step / the next overdue slot); the "first summary" start only applies to the start of the day. Overdue slots inside `essentials`/`dnd` periods are dropped, not moved.
- ✅ **"Bis ich es ausschalte" is allowed.** Risk: a forgotten `dnd` silences everything. Mitigation: the banner in the app, the other user sees the mode, and the admin UI shows it per user.
- 🟡 **Push priority by mode:** the server knows each user's effective mode. A wake-up for a display the recipient will not see now (`dnd`, or a repeat in `essentials`) goes out as **normal** priority; otherwise the priority rule from section 4 applies.
- 🟡 **Watchdog:** expected display keys depend on the effective mode at the planned time. Mode changes are stored with their timestamp (also in the activity view), so a change made offline corrects the "late/missing" status after the next sync instead of raising false alarms.

### All intervals adjustable per user

✅ Every user-facing time and interval is a per-user setting (`user_settings`, synced), with defaults set in the admin UI. The app's settings screen groups them:

| Group | Setting | Default | Range (🟡) |
|---|---|---|---|
| Quiet hours | start/end **per weekday** | 22:00–06:00 every day | any; crossing midnight belongs to the start day |
| Modes | weekly mode slots | none | see above |
| Summaries | times per weekday, each can be disabled | Mon–Fri 07:00/12:30/19:00, Sat–Sun 09:00/13:00/19:00 | – |
| Explicit urgent | repeat interval | 15 min | 5–60 min |
| | interval after "Mach ich" | 60 min | 15–240 min |
| | DND bypass | off | on/off |
| Overdue | slots per day (placement stays computed, section 11) | 4 | 1–6 |
| Snooze | short / long duration ("Bis morgen" is fixed) | 30 min / 2 h | 5–120 min / 1–8 h |
| Scheduled | default lead time for new todos | none | none / 15 min / 1 h / 1 day |
| Calendar | evening before, morning of, before start (each can be disabled) | 19:00 / 07:00 / at start | time / time / 0–60 min before |
| Activity | batching window | 2 min | 0–10 min |
| Theme | System / Light / Dark | System | – |

- ✅ **Not per user, on purpose:**
  - Level thresholds (`due_soon` < 1 week, series 25 %) stay central in the admin UI: both users see the same list, and a todo must not be "due soon" for one and "mid term" for the other.
  - System timings (watchdog 2/10/60 min and 15 min, periodic sync 15 min, "server unreachable" 3 h, heartbeat 6 h) are admin settings.
  - The 30 s undo stays fixed.
- 🟡 Every setting and range is part of the shared test vectors, where it affects planner output (quiet hours per weekday, slot count, intervals).

### Activity view (app, both users)

- ✅ A new **"Aktivität"** screen in the app (Android and web), visible to both users: a chronological list of what happened to todos. **Not** a list of notifications.
- ✅ **Events:** created (by whom, or "System" for series instances), done, dismissed (incl. "durch neue Instanz ersetzt"), reopened, edited (which field group, e.g. "Titel geändert", "Datum geändert"), deleted, snoozed (who, which todo or "alle überfälligen", duration), postponed (old → new date), "Mach ich", manual mode switches (mode and end; scheduled slots are not logged).
- 🟡 Filters: person (me / the other / system), event type, todo. Tapping an event opens the todo (unless deleted).
- 🟡 Stored server-side in a new synced table `activity_events` (id, rev, at, actor_user_id or NULL = system, todo_id, type, params JSON). Written wherever the action is applied: sync push, web REST, worker. `at` is the (clock-corrected) time of the action, so offline actions appear at the time they happened; they get a small "nachträglich synchronisiert" marker.
- 🟡 Deleted todos: the event keeps a title snapshot in `params` so the entry stays readable. (This is data in the DB, not a log; the rule "no todo content in logs" is about application logs.)
- 🟡 The device keeps the last 90 days locally (offline); older entries are loaded from the server page by page when online.
- 🟡 The admin UI "Activity" page reads the same table. `audit_log` stays separate (security events).

---

## Open questions

None. Not yet decided but not blocking: the app's display name, final categories.
