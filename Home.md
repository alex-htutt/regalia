---
date: 2026-05-30
tags: [type/reference, moc]
status: active
---

# 🏠 Home

Map of content for the **Regalia** vault. Start here.

## Regalia — the app

- `dashboard/` — **Regalia**, the self-hosted agentic workspace this vault powers: task list from note frontmatter, folder browser, Claude token-usage panel, a model-routed **Chat** (local Ollama / Anthropic API / Claude subscription), **Agents** that run real vault tools (summarize logs, scaffold projects, synthesize research, triage mail), and a drafts-only **Inbox**. See [[dashboard/_context_dashboard|Dashboard — Context]] and the repo-root `README.md`.
- Run: `cd dashboard && python app.py` → http://localhost:5000 (or `desktop.py` for a native window).

## Active areas

- [[projects/_context_projects|Projects]] — personal / side projects.
- [[research/_context_research|Research]] — self-directed learning (RAG, ML, etc.).
- [[meetings/_context_meetings|Meetings]] — meeting notes.
- [[ideas/_context_ideas|Ideas]] — unsorted ideas.

> Private areas (internships, coursework, personal projects) live only in the local copy of this vault — they are gitignored, so their links don't appear here. Add yours back locally as needed.

## Archive — finished RPI courses

- [[archive/courses/engr2350/_context_engr2350|ENGR-2350 — Embedded Control]]
- [[archive/courses/ecse2610/_context_ecse2610|ECSE-2610 — Digital Logic]]
- [[archive/courses/focs/_context_focs|CSCI-2200 — Foundations of CS]]
- [[archive/courses/phys/_context_phys|PHYS-1100/1110 — Physics]]
- [[archive/courses/writ/_context_writ|WRIT-2110 — Writing]]

## Reference

- [[USAGE]] — how to use the vault day-to-day.
- [[README_HOME]] — vault structure, context model, tag taxonomy.

> New notes: create from `templates/` so frontmatter and footer links come pre-filled, and link each note to its folder's `[[_context_<folder>]]`.
