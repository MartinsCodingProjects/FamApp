---
name: next
description: Start an autonomous agent session on famapp – pick up the next sub-task, work on your own per AGENTS.md, stop at run end or when Martin must decide
argument-hint: "[optional scope or extra instructions, e.g. 'only 1.1.3–1.1.5']"
---

You are starting a work session on famapp. Work on your own; Martin is not watching and will not answer questions mid-session.

Extra instructions from Martin for this session (narrow the scope, never widen the stop rules): $ARGUMENTS

## 1. Orient

1. Read `AGENTS.md` fully and follow its reading order (section 1). Do not skip `docs/last-session.md`.
2. Pre-flight; if one fails, fix it first or stop (section 4 below):
   - `git status` is clean, `main` is up to date (`git pull`).
   - `gh auth status` works and `git push --dry-run` to a scratch ref succeeds.
   - Once the Makefile exists: `make lint && make test` are green on `main`. If `main` is red, fixing it is the first task.
3. Pick the work, in this order:
   1. open issues labeled `bug` (`gh issue list --label bug --state open`),
   2. your own unfinished PRs: ready PRs waiting for CI or merge, branches that need `gh pr update-branch`, conflicts,
   3. `docs/last-session.md` **Next**, checked against the first unticked sub-task in BUILDPLAN Part B (the checkboxes win).
   Check `gh pr list --draft` first: a 🚧 claim on someone else's branch is not yours.
4. Say in one line which sub-task you take and why, then start.

## 2. Work

Follow AGENTS.md section 2 exactly (branch, 🚧 claim in the first commit, draft PR, test first, `make lint && make test`, CI, ready + auto-merge, ticks in the same PR). Then go straight to the next sub-task. Do not ask for confirmation between sub-tasks or packages.

## 3. Decisions

Resolve every decision in this order:

1. **The docs decide.** Use the precedence in AGENTS.md section 1 (behavior: `decisions.md` ✅ > README > `decisions.md` 🟡 > BUILDPLAN > `assumptions.md`). If docs contradict each other, fix the lower-ranked one in the same PR.
2. **Not in the docs and not a Martin decision** (see 4.1): decide yourself. Pick the simplest option that fits the architecture rules, is easy to change later and does not block later packages. Record it in `docs/assumptions.md` (date, package, assumption, reason).
3. **Structural decisions** must be made visible, not just recorded. Structural means anything later packages build on: module or directory layout beyond README 12, new dependencies or tools, data model or table shape, API or sync payload shape, protocol versioning, test infrastructure, CI layout, cross-language rules. For each one:
   - entry in `docs/assumptions.md` marked **[structural]**,
   - listed in the PR description under **Assumptions**,
   - listed in `docs/last-session.md` under **Structural decisions**,
   - listed in your final chat report.

## 4. When to stop

### 4.1 Martin must decide → stop and wait

Stop the session (do not continue with other sub-tasks) when a decision is important enough that a wrong guess is expensive:

- user-visible behavior not covered by README or decisions (wording, flows, what a notification does, defaults Martin will notice),
- anything irreversible: package name, signing key, channel IDs, data-deleting migrations, `release`, repo settings, secrets,
- going against a ✅ decision or the README, or a 🟡 decision that turns out to be wrong,
- a structural decision that would be hard to undo once later packages depend on it **and** the docs give no direction (e.g. replacing a planned library or service, changing the sync protocol contract, a new external service, anything with cost or privacy impact),
- anything touching security, auth, or what data leaves the server.

How: open an issue labeled `question` with the options and your recommendation, mark the sub-task ⏸ in BUILDPLAN, add it to **Open blockers** and **Needs Martin**, push and leave your current work in a clean state (green, committed, draft PR), then end the session (section 5).

### 4.2 Blocked on something else → park and continue

Missing access/account/secret that only Martin can create (e.g. M1), CI red after several serious attempts, external service down: open a `question` issue, mark the sub-task ⏸, note it under **Open blockers**, and continue with independent sub-tasks. Stop only when nothing independent is left.

### 4.3 Run end → stop

Stop when the current run is done (its run line in BUILDPLAN Part B can be ticked), after the run's end steps (checkpoint file, `versionCode` bump, `release` request where BUILDPLAN says so). Do not start the next run in the same session.

### 4.4 Context running low → stop cleanly

Stop at the next sub-task boundary before context runs out. Never leave a half-done sub-task without describing exactly how far it got under **In progress**.

### Never

Move or push `release`, change repo settings, rulesets or environments, create or commit secrets, force-push to `main`, delete data, or put personal data or todo content in the public repo.

## 5. End the session

1. Follow AGENTS.md "Ending a session" (`docs/last-session.md`, `tools/session-end.sh`, commit in the last PR or a `session/<date>` PR).
2. Final chat report to Martin, short:
   - **Done:** sub-tasks / PRs (with links), CI state
   - **Stopped because:** run end / Martin decision / blocked / context
   - **Structural decisions:** one line each, with the `assumptions.md` reference
   - **Needs Martin:** decisions, reviews, M-tasks that are now due, issue links
   - **Next:** what the next `/next` will pick up
