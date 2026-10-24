# Cloudflare setup (M4)

Input for Martin's M-task M4. Decisions: `docs/decisions.md` section 3 (Cloudflare). Both subdomains point at the VPS through the Cloudflare proxy; Coolify's Traefik terminates TLS and routes both hosts to the `api` service (port 8000).

| Host | Proxy | Protection |
|---|---|---|
| `famapp.cowflex.com` (app + web) | proxied | WAF skip rule (no challenges for the app) |
| `famapp-admin.cowflex.com` (admin UI) | proxied | Cloudflare Access (GitHub SSO) + backend JWT check + admin login |

## 1. DNS

DNS → Records → add two records, both **Proxied** (orange cloud):

- `A` `famapp` → VPS IPv4 (plus `AAAA` if the VPS has IPv6)
- `A` `famapp-admin` → VPS IPv4 (plus `AAAA`)

SSL/TLS mode for the zone stays as it is for the other projects; it must be **Full (strict)** or **Full** so Cloudflare talks HTTPS to Traefik (Coolify issues the certificates).

## 2. WAF skip rule for the app subdomain

The app talks to the API from the background (sync, FCM-triggered requests); a challenge page would silently break it.

Security → WAF → Custom rules → **Create rule**:

- Name: `famapp app: skip`
- If: *Hostname* *equals* `famapp.cowflex.com`
- Then: **Skip**, and tick everything offered: all remaining custom rules, rate limiting rules, managed rules, Browser Integrity Check, Security Level, User Agent Blocking, and Super Bot Fight Mode if listed
- Place it first.

**Bot Fight Mode** (the free one, Security → Bots) **cannot be skipped per hostname**. If it is on for `cowflex.com`, switch it off for the zone, or the app's requests get challenged. (Super Bot Fight Mode on paid plans can be skipped with the rule above.)

The backend has its own rate limits and lockouts (decisions section 3), so skipping Cloudflare's does not leave the API unprotected.

## 3. Cloudflare Access for the admin subdomain

Zero Trust → Access → Applications → **Add an application** → **Self-hosted**:

- Name: `famapp admin`
- Domain: `famapp-admin.cowflex.com` (whole host, no path)
- Identity provider: **GitHub** (the same one as for `coolify.cowflex.com`)
- Policy: **Allow**, *Emails* = Martin's GitHub e-mail (only his)
- Session duration: as for Coolify (e.g. 24 h)

Then note two **non-secret** values for Coolify (M5):

| Coolify variable | Where to find it |
|---|---|
| `CF_ACCESS_TEAM_DOMAIN` | Zero Trust → Settings → Custom pages (or the login URL): `<team>.cloudflareaccess.com`, without `https://` |
| `CF_ACCESS_AUD` | the application → Overview / Basic information → **Application Audience (AUD) Tag** |

The backend checks the `Cf-Access-Jwt-Assertion` header on every admin request against `https://<team>.cloudflareaccess.com/cdn-cgi/access/certs` and this audience tag; missing or invalid → 404. That is what makes Access impossible to bypass via the public VPS IP.

## 4. Check after C1

- `https://famapp.cowflex.com/api/health` → `{"status":"ok",…}` without any challenge (also with `curl`, which has no browser).
- `https://famapp-admin.cowflex.com/` → GitHub login first, then the admin page.
- `curl -k -H 'Host: famapp-admin.cowflex.com' https://<VPS-IP>/` → 404 (no Access JWT).
