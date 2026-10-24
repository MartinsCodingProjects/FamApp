# Spec: sync protocol (package 1.6)

The contract between the server and every client that keeps a mirror (the Android engine). The web app does not sync; it calls REST endpoints and the server sets timestamps itself (README 7).

Sources: README 3.5–3.7, 6, 7; `docs/decisions.md` sections 3, 6, 8, 10, 11, 12. Implemented in 1.11 (server) and 2.3 (engine). Wire details that the decisions leave open are recorded in `docs/assumptions.md` (1.6).

**Protocol version described here: 1.**

## 1. Endpoints

All endpoints live on the app host under `/api`, take and return JSON (UTF-8), and need the device's access token.

| Method and path | Purpose |
|---|---|
| `GET /api/sync?since=<rev>&limit=<n>` | delta: all changes visible to this device's user with `rev > since` |
| `POST /api/sync/push` | apply a batch of outbox operations |
| `POST /api/devices/me/fcm-token` | register or replace this device's FCM token |

Pairing and token refresh are separate endpoints (1.10), outside the sync protocol, but they send and return the same headers (section 6).

### Request headers

| Header | Value |
|---|---|
| `Authorization` | `Bearer <access token>` (15 min, 1.10) |
| `X-Famapp-Protocol` | protocol version the client speaks, e.g. `1` |
| `X-Famapp-App-Version` | the app's `versionCode` (integer, from `app/version.json`) |
| `X-Request-ID` | optional, 8–64 chars `[A-Za-z0-9-]`, echoed back |

### Response envelope

Every response of the three endpoints, success or error, has a `meta` object:

```json
{
  "meta": {
    "protocol": 1,
    "server_time": "2026-11-02T14:15:03.120Z",
    "min_app_version": 3,
    "latest_app_version": {"name": "0.4.0", "code": 7},
    "worker_heartbeat_age_s": 42
  }
}
```

- `server_time`: UTC, millisecond precision, taken at the moment the response is built (clock-skew correction, section 4.4).
- `min_app_version` / `latest_app_version`: `versionCode`s (section 6).
- `worker_heartbeat_age_s`: seconds since the worker's last heartbeat, or `null` if there is none yet (README 3.7: the device warns when > 15 min outside quiet hours).

### `GET /api/sync`

Query: `since` (integer ≥ 0, default 0 = full sync), `limit` (1–1000, default 500).

```json
{
  "meta": {"…": "…"},
  "changes": [
    {"table": "todos", "id": "6f1c…", "rev": 1201, "deleted": false, "data": {"title": "…", "status": "open", "…": "…"}},
    {"table": "todos", "id": "9a0e…", "rev": 1202, "deleted": true, "data": {"deleted_at": "2026-11-02T14:10:00Z"}}
  ],
  "next_since": 1202,
  "has_more": false
}
```

### `POST /api/sync/push`

```json
{
  "ops": [
    {"op_id": "3b7e…", "type": "todo.set_status", "at": "2026-11-02T14:12:40.500Z",
     "payload": {"todo_id": "6f1c…", "status": "done"}}
  ]
}
```

At most 100 ops per request; the client sends its outbox in order, in batches. Response, one result per op in the same order:

```json
{
  "meta": {"…": "…"},
  "results": [
    {"op_id": "3b7e…", "status": "ok"},
    {"op_id": "a12f…", "status": "rejected", "code": "validation", "message": "title must not be empty"},
    {"op_id": "c9d0…", "status": "retry", "code": "not_processed"}
  ]
}
```

`status`: `ok` (applied, or a no-op that the server accepted, e.g. lost a conflict) · `rejected` (permanent, section 5.2) · `retry` (transient, section 5.2). `message` is for logs and the admin UI, never shown to users as is.

After every push the client runs a delta fetch (README 7); only that brings the authoritative state, including conflict outcomes.

### `POST /api/devices/me/fcm-token`

Body `{"token": "<FCM registration token>"}`; response `{"meta": …}` with 200. Replaces the device's previous token. An empty or overlong token (> 4096 chars) → 400 `validation`.

## 2. Delta

- **Order:** changes are ordered by `rev` ascending, across all synced tables. `rev` comes from the single counter `next_rev()` (1.7.1), assigned inside the writing transaction, so commit order equals `rev` order and a delta can never skip a row that commits late.
- **`since` is exclusive:** the response holds rows with `rev > since`.
- **Pagination:** at most `limit` changes. `next_since` is the highest `rev` the server **examined** for this page, not only the highest it returned, so rows invisible to this user do not stall paging. `has_more = true` → the client asks again with `since = next_since` right away. The client stores `next_since` only after it has applied the whole page locally (in one local transaction).
- **One row, one entry:** a row appears at most once per page, with its current state; intermediate states are not replayed.
- **Tombstones:** deleting sets `deleted_at` and a new `rev`; the change carries `"deleted": true` and only `id`, `deleted_at` in `data`. The client deletes its local row (or keeps a tombstone; its choice). Tombstones are never purged in the MVP. If purging is ever added, a `since` below the purge horizon gets `409 resync_required` (section 5).
- **Visibility per user** (README 6):

| Table | What a device of user U gets |
|---|---|
| `users` | own row in full; the other user's row projected to `id`, `name`, `next_nag_window_start` |
| `user_settings` | own row in full; the other user's row projected to `mode`, `mode_until`, `mode_schedule` |
| `todos`, `todo_series`, `todo_snoozes`, `todo_claims`, `people`, `categories`, `activity_events`, `calendar_sources` (without credentials), `calendar_events` (server window) | everything (both users see all todos, decisions section 6) |
| `notifications` | rows addressed to U |
| `login_approvals` | rows of U |
| `devices`, `device_tokens`, `deliveries`, `alarm_firings`, `secrets`, `audit_log`, … | never |

  A projection change (e.g. the other user's mode changes) bumps the row's `rev`, so it arrives as an ordinary change. A delta entry always carries the full projection for this user, never a diff.
- **Read-only server fields** (`urgent_downgrade_at`, delivery status per recipient, `next_nag_window_start`) are part of `data` like any other field; clients never send them.
- **Unknown tables and fields:** the client ignores tables it does not know and fields it does not know (section 6). The server only adds tables and fields; it never changes a field's meaning within a protocol version.
- **Calendar window:** `calendar_events` outside the server's window (−1 to +12 months) are sent as tombstones when they leave it; the device additionally keeps only −1 to +3 months locally (decisions section 7).

## 3. Operations

Every outbox entry is one operation:

| Field | Meaning |
|---|---|
| `op_id` | UUID generated on the device when the entry is created; never reused |
| `type` | operation type (below) |
| `at` | when the user acted, device time corrected by the clock offset (section 4.4), UTC |
| `payload` | type-specific object |

**Idempotency:** the server stores every applied `op_id` with its result in `processed_ops`. A repeated `op_id` is not applied again; the stored result is returned. So a lost response is harmless: the client simply sends the batch again.

**Order and atomicity:** ops are applied in request order, each in its own DB transaction. If one op gets `retry`, the server stops and returns `retry`/`not_processed` for all following ops of the request, so the client's order is kept (an op may depend on an earlier one, e.g. `todo.create` then `todo.set_status`). `rejected` does not stop the batch.

### Operation types (protocol 1)

| Type | Payload | Field group / effect |
|---|---|---|
| `todo.create` | `todo_id` (UUID chosen by the device), all content fields, optional `status` | creates the todo; `created_by` = user, content and status timestamps = `at` |
| `todo.update_content` | `todo_id`, **all** content fields (title, note, kind, `target_date`, `due_at`, `lead_time`, `category_id`, `assignee_user_id`, `for_people`, `payload`) | content group, last-write-wins on `content_changed_at` |
| `todo.set_status` | `todo_id`, `status` (`open`/`done`/`dismissed`) | status group (`status`, `completed_by`, `completed_at`); `completed_by` = user, `completed_at` = `at` for done/dismissed |
| `todo.delete` | `todo_id` | deletion; always wins |
| `ack` | `display_key` (base key + `@` + planned minute, README 3.5), `shown_at`, optional `opened_at`, `acked_at` | upserts `deliveries` for (key, device); never conflicts, later timestamps only fill empty fields |
| `snooze` | `todo_id` or `null` (= combined overdue notification), `until` | upserts `todo_snoozes` for (todo, user); last-write-wins on `at` |
| `claim` | `todo_id` | creates `todo_claims` for (todo, user) if missing ("Mach ich"); only for open explicit urgent todos, else `rejected`/`not_applicable` |
| `device_status` | `notifications_enabled`, `channels` (`{channel_id: importance}`), `app_version` (`versionCode`), optional `battery_optimization_ignored` | updates the device row; a change to muted/blocked is logged (decisions section 11) |
| `alarm_firing` | `planned_at`, `fired_at`, `alarm_type` (`alarm_clock`/`exact_idle`), `idle`, `network`, `sync_result` (`ok`/`timeout`/`error`/`no_network`), `sync_ms` | inserts into `alarm_firings` (device → server only) |

Later runs register more types with the same envelope and naming (`<area>.<verb>`), e.g. `settings.update`, `mode.set`, `category.create`, `todo.postpone` (a content change), `series.*`. Adding a type does not change the protocol version; a client only sends types the server it talks to supports, which follows from `min_app_version` (section 6).

### Validation (all types)

- Unknown payload fields are ignored (forward compatibility).
- Missing or malformed required fields → `rejected`/`validation`.
- An id that does not exist → `rejected`/`not_found`, except on a deleted row (section 4.2).
- `ack`, `device_status`, `alarm_firing` from a device only ever apply to that device.

## 4. Conflicts

### 4.1 Last-write-wins per field group

Each todo carries one timestamp per field group: `content_changed_at`/`_by`, `status_changed_at`/`_by` (decisions section 8). For an op on group G with time `at`:

- `at > G_changed_at` → apply, set `G_changed_at = at`, `G_changed_by = user`, new `rev`.
- `at < G_changed_at` → discard; result `ok` (the client learns the winning state from the next delta); write a `conflict_log` row (table, row id, field group, losing values, winning values, both timestamps, both users).
- **Tie** (`at == G_changed_at`): the change already stored (= the one that reached the server first) wins; treated as a lost conflict.

Groups are independent: a status change and a content change made offline on two devices both survive.

### 4.2 Deletion wins

- `todo.delete` on a live row: sets `deleted_at`, wins regardless of timestamps.
- Any other op on a deleted row: discarded, result `ok`, `conflict_log` row with reason `deleted`.
- `todo.delete` on an already deleted row: `ok`, no change.

### 4.3 Creates

`todo.create` with a `todo_id` that already exists (a different `op_id`, e.g. a reinstalled app replaying an old outbox): treated as `todo.update_content` plus, if given, `todo.set_status`, both with their timestamps. A `todo.create` for an id that only exists as a tombstone stays deleted (4.2).

### 4.4 Clock skew

- Each response carries `meta.server_time`. The client estimates `offset = server_time − (t_sent + t_received) / 2` from its own clock and keeps the latest estimate (with its age).
- The outbox stores the device's **raw** local time of the action. When sending, the client sets `at = raw + offset` using its current offset. (The offset drifts slowly; using the current one at send time is accurate enough for last-write-wins and the activity view.)
- The server clamps: `at` later than `server_now + 60 s` is set to `server_now`. There is no lower bound (weeks offline are legal); `activity_events` written from such ops get the "nachträglich synchronisiert" marker when `at` is more than 5 min before the push.
- Server-side logic that compares times (levels, watchdog, series) always uses the corrected `at`.

### 4.5 Conflict log

`conflict_log` (1.7.6) is written only by the server, never synced, shown in the admin UI → Conflicts. It never stores more todo content than the two competing values of the field group.

## 5. Error cases

### 5.1 Request level (HTTP)

Error responses have the envelope plus `{"error": {"code": "<code>", "message": "…"}}`.

| HTTP | `error.code` | Meaning | Client behavior |
|---|---|---|---|
| 400 | `validation` | malformed request (bad `since`, too many ops, invalid JSON) | bug: log, report in the next `device_status`, do not retry the same request blindly; outbox stays |
| 400 | `unsupported_protocol` | `X-Famapp-Protocol` missing or not current/previous | like `app_too_old` |
| 401 | `token_expired` | access token expired or invalid | refresh (1.10), retry once; refresh failure → see next rows |
| 401 | `device_locked` | device revoked or locked by the reuse rule | stop syncing, keep outbox and mirror, show the pairing screen with a notice |
| 409 | `resync_required` | `since` cannot be served (future: purged tombstones) | clear mirror tables and sync state, full sync from `since=0`; **outbox kept** |
| 426 | `app_too_old` | `X-Famapp-App-Version` below `min_app_version` | stop push and delta, keep outbox, show "update required" with the latest version |
| 429 | `rate_limited` | too many requests | wait `Retry-After` seconds |
| 5xx | `server_error` | server problem | retry with backoff |
| – | – | network error, timeout, DNS, TLS | retry with backoff; offline banner; after 3 h with network and outside quiet hours the "Server nicht erreichbar" notification (README 3.7) |

Backoff: 5 s, 15 s, 1 min, 5 min, then every 15 min (the periodic job); any trigger from README 3.6 (FCM wake-up, network back, app start) tries immediately.

### 5.2 Operation level

| `status` / `code` | Meaning | Client behavior |
|---|---|---|
| `ok` | applied, or accepted as a no-op (lost conflict, deleted row) | remove from outbox |
| `rejected` / `validation` | payload invalid | mark entry **failed**, continue with the next; the app offers "Erneut versuchen" / "Verwerfen" (decisions section 10) |
| `rejected` / `not_found` | referenced row does not exist | as `validation` |
| `rejected` / `forbidden` | user may not do this | as `validation` |
| `rejected` / `not_applicable` | op does not fit the row's state (e.g. claim on a non-urgent todo) | as `validation` |
| `retry` / `unknown_op` | the server does not know this op type (e.g. server rolled back to the previous image) | keep, retry later; never mark failed |
| `retry` / `busy` | transient (lock timeout, deadlock) | keep, retry with backoff |
| `retry` / `not_processed` | an earlier op of the batch got `retry` | keep, resend in order |

Failed entries never block the queue and are never deleted without the user's "Verwerfen". "Erneut versuchen" sends the same `op_id` again only if the server never stored a result for it; otherwise it creates a new op with a new `op_id` and the current `at`.

## 6. Versions

- **Protocol version** (`X-Famapp-Protocol`): an integer, raised only for incompatible changes (renamed or removed fields, changed meaning, changed envelope). Adding tables, fields or op types is compatible and does not raise it.
- **The server supports the current and the previous protocol version** (AGENTS.md section 5). Responses for a previous-version client are shaped for that version (e.g. without fields whose meaning changed). The version a response was shaped for is in `meta.protocol`.
- **Minimum app version:** a server setting (admin UI, default 1) holding a `versionCode`. Below it → `426 app_too_old`. Raised by Martin when a release drops support for an old protocol or op.
- **Latest app version:** read by the server from `app/version.json` of its own build (README 10); clients show "Update verfügbar" when `latest_app_version.code` > their own `versionCode`.
- **Unknown fields and tables are ignored by clients**; unknown request fields are ignored by the server. Unknown op types → `retry`/`unknown_op` (5.2), so a newer app talking to an older server never loses an outbox entry.
- **Room schema changes** on the device are independent of the protocol: mirror tables may be dropped and re-synced from `since=0`; outbox, auth and sync state are migrated (decisions section 10).

## 7. Test scenarios

Used by the server acceptance tests (1.11) and the engine sync tests (2.3). IDs are stable; tests reference them in their names or docstrings (`S07`).

| ID | Scenario | Expected |
|---|---|---|
| S01 | Full sync from `since=0` with more rows than `limit` | pages in `rev` order, `has_more` until the last page, no row missing or duplicated |
| S02 | Delta after changes in several tables | only rows with `rev > since`, ordered by `rev` across tables |
| S03 | Rows invisible to the user between visible ones | `next_since` advances past them; no empty-page loop |
| S04 | Deleted todo | tombstone with `deleted: true`; client removes the row |
| S05 | Other user's settings change mode | arrives as a projected `user_settings` change; other settings never leak |
| S06 | Push with a lost response, client resends the batch | same results, nothing applied twice |
| S07 | Status changed offline on A, title changed later on B | both changes survive (different field groups) |
| S08 | Content changed on A and B, B later | B wins, A's values in `conflict_log`, A's op result `ok` |
| S09 | Same timestamp on both | first to reach the server wins |
| S10 | Edit on a todo the other device deleted | stays deleted, op `ok`, conflict logged |
| S11 | Device clock 10 min ahead, offset applied | `at` corrected; a still-future `at` is clamped to server time |
| S12 | Op with invalid payload in the middle of a batch | that op `rejected`, the following ops applied |
| S13 | Op that hits a lock timeout in the middle of a batch | that op and all after it `retry`, order kept on resend |
| S14 | Unknown op type | `retry`/`unknown_op`, never `rejected` |
| S15 | Unknown fields in payload and in delta data | ignored on both sides |
| S16 | Previous protocol version header | still served (`meta.protocol` = previous) |
| S17 | Unsupported protocol version / app below minimum | `400 unsupported_protocol` / `426 app_too_old`, outbox kept |
| S18 | Expired access token | `401 token_expired`, refresh, retry succeeds |
| S19 | Revoked device | `401 device_locked`, sync stops, outbox kept |
| S20 | Two devices push concurrently (MariaDB) | every op applied once, `rev`s unique and in commit order, no lost update |
| S21 | Row committed with a lower `rev` after a delta read a higher one | impossible by construction (`next_rev()` in the writing transaction); test asserts commit order = `rev` order |
| S22 | `ack` twice for the same key and device | one `deliveries` row, first `shown_at` kept |
| S23 | `alarm_firing` and `device_status` | stored for that device only, never in any delta |
| S24 | Every response | carries `meta` with `server_time`, `min_app_version`, `latest_app_version`, `worker_heartbeat_age_s` |
| S25 | `todo.create` replayed after reinstall with a new `op_id` | treated as update, no duplicate todo |
