# Progress

Every agent updates this file in the same PR as its work.

**Current section:** C0 preparation (Martin)
**Next package for agents:** 1.1 (once C0 is complete)

## Checkpoints

| Checkpoint | Status | Note |
|---|---|---|
| C0 preparation | in progress | repo created, docs committed; remaining items below |
| C1 first deployment | open | |
| C2 daily-use test | open | |
| C3 wrap-up | open | reminder: make the repo private again |

## C0 – Martin's tasks (details: BUILDPLAN Part B)

- [x] 1a Create GitHub repo
- [ ] 1b Make repo public (until C3), agent access, auto-merge, branch protection for `main` (required check `ci-gate`), protect `release`
- [ ] 2 Display-name placeholder and subdomains (`famapp.cowflex.com`, `famapp-admin.cowflex.com`)
- [ ] 3 Create APK signing key, back it up twice, add as secret of GitHub Environment `release` (branch `release` only, reviewer Martin)
- [ ] 4 Firebase project (`com.cowflex.famapp`), commit `google-services.json`
- [ ] 5 (optional) Dev Firebase project
- [ ] 6 Google Cloud: Calendar API, OAuth client
- [ ] 7 Cloudflare: DNS, WAF skip, Access (note team domain + AUD tag)
- [ ] 8 Coolify: MariaDB, Compose resource on branch `release`, environment variables (incl. `CF_ACCESS_TEAM_DOMAIN`, `CF_ACCESS_AUD`)
- [ ] 9 Phones: allow installing unknown apps
- [ ] 10 Secure GitHub costs
- [ ] 11 Log in `gh` in code-server
- [ ] 12 Check ports 8000, 5000, 5173 through the tunnel

## Run 1: Foundation and backend core

| ID | Package | Status | PR |
|---|---|---|---|
| 1.1 | Repo scaffold | open | |
| 1.2 | CI | open | |
| 1.3 | Home-server dev environment | open | |
| 1.4 | Backend skeleton | open | |
| 1.5 | Expo project + empty engine module | open | |
| 1.6 | Sync spec | open | |
| 1.7 | Migrations | open | |
| 1.8 | Secret encryption | open | |
| 1.9 | Setup wizard (minimal) | open | |
| 1.10 | Device auth | open | |
| 1.11 | Sync endpoints | open | |

## Run 2: Engine, push, delivery

| ID | Package | Status | PR |
|---|---|---|---|
| 2.1 | Engine spec | open | |
| 2.2 | `engine-core` foundation | open | |
| 2.3 | Sync logic + Room | open | |
| 2.4 | Planner | open | |
| 2.5 | Display, receivers, WorkManager | open | |
| 2.6 | Bridge, pairing, setup flow | open | |
| 2.7 | Worker + locks | open | |
| 2.8 | FCM | open | |
| 2.9 | Watchdog, heartbeat | open | |
| 2.10 | "Delivery" complete | open | |
| 2.11 | Admin UI: delivery, devices | open | |
| 2.12 | Observation job | open | |
| 2.13 | C1 checklist | open | |

## Run 3: Todos, nagging, series

| ID | Package | Status | PR |
|---|---|---|---|
| 3.1 | Todo spec + test vectors | open | |
| 3.2 | Backend todos + conflicts | open | |
| 3.3 | Backend notifications | open | |
| 3.4 | Theme, components, navigation | open | |
| 3.5 | Engine: todo data | open | |
| 3.6 | Settings | open | |
| 3.7 | Todo UI | open | |
| 3.8 | Engine II (summaries, nagging) | open | |
| 3.9 | Watchdog for summaries | open | |
| 3.10 | Series | open | |
| 3.11 | Activity view | open | |
| 3.12 | Screenshots, C2 checklist | open | |

## Run 4: Calendar, web, admin

| ID | Package | Status | PR |
|---|---|---|---|
| 4.1 | Fake Google Calendar | open | |
| 4.2 | Calendar backend | open | |
| 4.3 | Calendar in wizard/admin | open | |
| 4.4 | Calendar UI | open | |
| 4.5 | Calendar notifications | open | |
| 4.6 | Add appointment → todo | open | |
| 4.7 | Web app | open | |
| 4.8 | Web login with in-app approval | open | |
| 4.9 | Admin UI complete | open | |
| 4.10 | Quick guide, C3 checklist | open | |
