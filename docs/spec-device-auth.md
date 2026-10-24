# Spec: device auth (package 1.10)

Sources: README 9; `docs/decisions.md` section 3 (security, Cloudflare, client IP). Endpoints on the app host; error body `{"error": {"code", "message"}}` (the sync `meta` envelope is added in 1.11).

## Pairing codes

- 8 characters from `23456789ABCDEFGHJKMNPQRSTVWXYZ` (no 0/O/1/I/L/U), shown as `ABCD-EFGH`; input is case-insensitive, spaces and hyphens ignored. About 39 bits; brute force is stopped by the rate limit.
- Stored only as HMAC-SHA256(`MASTER_KEY`-derived key, normalized code) in `pairing_codes`, bound to one user, valid **10 min**, usable **once**.
- Created by the admin CLI (`python -m app.cli pairing-code <user name>`) or by a paired device for its own user (`POST /api/devices/me/pairing-codes`, 1.10.10). The admin UI page follows in 2.11.

## Endpoints

| Endpoint | Body | Response |
|---|---|---|
| `POST /api/pair` | `{"code", "device_name"}` | `201 {"device_id", "user_id", "access_token", "access_expires_at", "refresh_token"}` |
| `POST /api/auth/refresh` | `{"refresh_token"}` | `200` same shape (new access and refresh token) |
| `POST /api/devices/me/pairing-codes` | – (access token) | `201 {"code", "expires_at"}` |

Errors: `400 validation`, `401 pairing_failed` (unknown, expired or used code — one code for all), `401 invalid_token`, `401 token_expired`, `401 device_locked`, `429 rate_limited` (with `Retry-After`).

## Access tokens

JWT (HS256) with a key derived from `MASTER_KEY` (HKDF-SHA256, info `famapp access token v1`); claims `sub` (device id), `uid`, `iat`, `exp` = 15 min, `typ: "access"`. Checked against the time provider. Every authenticated request also loads the device: locked → `401 device_locked`. The auth dependency gives endpoints the device and user.

## Refresh tokens: the generous reuse rule

Refresh tokens are 32 random bytes (URL-safe base64). Only SHA-256 hashes are stored (`device_tokens`), each with a link to the token it replaced. They never expire.

Presenting token **T** at `/api/auth/refresh` (inside one transaction, device row locked):

| Situation | Result |
|---|---|
| T unknown | `401 invalid_token` |
| device locked | `401 device_locked` |
| T is the newest token (no successor) | mark T used, issue successor S |
| T has successors, **none used yet** (response lost, retry) | issue one more successor; T stays valid |
| T is a successor used for the first time | mark it used; its unused siblings are revoked; issue its successor |
| T has a successor that **was already used** (old token after rotation) | **lock the device** (`token_reuse`), audit, `401 device_locked` |
| T was revoked because a sibling was used (a second chain) | **lock the device** (`token_reuse`), audit, `401 device_locked` |

So lost responses, dead zones and weeks offline never lock a device: the last token the device stored stays valid until its successor is used. The engine serializes refreshes (one at a time) so it never creates two chains itself.

## Revocation

`python -m app.cli lock-device <device id>` (admin UI in 2.11): sets `locked_at` / `locked_reason = "admin"`, revokes all its tokens, audit `device.locked`. A locked device gets `401 device_locked` on every request; pairing again creates a new device.

## Client IP (decisions section 3)

1. Peer address not in `TRUSTED_PROXIES` (default: private and loopback ranges, where Coolify's Traefik lives) → the peer is the client. Forwarding headers are ignored.
2. Otherwise take the **rightmost** `X-Forwarded-For` entry (the address that connected to Traefik).
3. If that address is in Cloudflare's published ranges and `CF-Connecting-IP` is a valid IP → that is the client; otherwise the rightmost entry is.

A `CF-Connecting-IP` header from anyone not coming through Cloudflare is ignored. The Cloudflare ranges are a list in the code (`app/security/client_ip.py`, from cloudflare.com/ips), updated by hand.

## Rate limits (per client IP, per api process)

| Action | Limit |
|---|---|
| `POST /api/pair` failures | 10 per 15 min |
| `POST /api/auth/refresh` | 30 per 15 min |
| `POST /api/devices/me/pairing-codes` | 5 per hour (also per device) |
| admin login failures | 10 per 15 min (plus the per-user lockout from 1.9) |
| setup token failures | 5 per 15 min (1.9) |

## Audit log

`device.paired`, `pairing.failed`, `pairing_code.created`, `token.reuse_locked`, `device.locked`, `rate_limited` (action + IP).
