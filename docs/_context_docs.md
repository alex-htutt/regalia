---
date: 2026-10-19
tags: [type/reference, moc]
status: active
topic: "Repo-level docs moved off the vault root"
deadline:
related: [Home]
---

# Docs — Context

Repo-level documentation that isn't a tool entry point. The vault root keeps only
`README.md`, `CLAUDE.md`, `AGENTS.md`, and `Home.md`; everything else of this kind
lives here (moved 2026-10-19).

## Contents
- [[USAGE]] — how to use the vault day-to-day.
- [[README_HOME]] — vault structure, context model, tag taxonomy.
- [[RELEASE]] — one-time steps before the repo goes public (git history scrub).

## Notes
- `USAGE.md` and `README_HOME.md` stay out of the dashboard task list through
  `IGNORE_FILES` in `dashboard/app.py`, which matches by file name, so moving
  them here needed no code change.
- App docs (`UI_STANDARDS.md`, `VERSION_HISTORY.md`, …) stay in `dashboard/`
  beside the code they describe.

---
↑ [[Home]]
