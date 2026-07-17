---
date: 2026-05-30
tags: [type/reference]
status: active
---

# Regalia — the vault

This document describes the **vault** (the Obsidian knowledge base + Cursor context system) that the Regalia app runs on. For the app itself — features, install, configuration — see the repo-root `README.md`.

The vault is a single home for all work: active projects and self-directed research, with finished coursework archived for reference. Private areas (internships, classes, personal projects) are **gitignored** — the public repo carries only this skeleton; add your own folders locally.

## Layout
- `dashboard/` — **the Regalia app** (Flask). See root `README.md` and `dashboard/_context_dashboard.md`.
- `projects/` — personal/side projects.
- `research/` — self-directed learning (RAG pipelines, ML, etc.). One subfolder per subject; add `_context_<subject>.md` when a topic gets dense.
- `archive/courses/` — finished RPI courses (engr2350, ecse2610, focs, phys, writ). Reference-only.
- `meetings/`, `ideas/`, `attachments/` — cross-cutting.
- *(local-only, gitignored)* `Internship-Projects/`, `schoolwork/`, and similar private areas — one subfolder per project, each with its own `_context_<project>.md`.
- `templates/` — note templates (point Obsidian's Templates/Templater plugin here).
- `.cursor/rules/` — Cursor `.mdc` rules. `global.mdc` always applies; `internship.mdc` and `projects.mdc` scope by path; `archive-*.mdc` are inactive references.
- `.cursorignore` — keeps `.obsidian/`, `attachments/`, `templates/`, and view files (`*.base`, `*.canvas`) out of Cursor's index.

## Context model (3 layers)
1. **Rules** (`.mdc`) — ambient, auto-loaded by file path. Keep lightweight.
2. **`_context_<folder>.md`** — dense per-folder status file (named after its folder, e.g. `_context_payments_api.md`). Prime a chat with `@file <area>/<project>/_context_<project>.md`.
3. **`@file`** — surgical, single-note context.

## Frontmatter schema
```yaml
date: YYYY-MM-DD
tags: [area/internship, type/lab]
status: active | complete | archived
topic: ""
deadline: YYYY-MM-DD
related: []
```

## Tag taxonomy
`area/internship`, `area/projects`, `area/schoolwork` · `course/<slug>` (e.g. `course/math1c`; archived: `course/{engr2350,ecse2610,focs,phys,writ}`) · `type/{lecture,lab,problem-set,exam-prep,meeting,standup,daily-log,project,reference}` · `status/{active,complete,archived}`

## Getting started in Cursor
1. Open this folder as a Cursor workspace → it indexes all `.md` files.
2. `@codebase` for semantic search across the vault; `@file` for a specific note.
3. Rules apply automatically based on the folder you're working in.
4. Optional: install the "Open in Cursor" Obsidian community plugin.

## Dashboard
`dashboard/` is a local Flask cockpit over the vault — it started as a read-only task dashboard and is growing into a self-hosted, agentic workspace. Full feature log in the vault-root `CLAUDE.md`; dense project snapshot in `dashboard/_context_dashboard.md`.

**Run:** `cd dashboard && python app.py` → http://localhost:5000, or double-click `dashboard/start.bat`. Native window: `dashboard/desktop.py` / `desktop.bat`.

Features as of v1.19 (2026-06-20):
- **Landing page:** `/` opens on an ASCII-dither hero with a spotlight on the **"Regalia."** title; scrolling drives a pinned animation where the title gives way to a **"What should we work on?"** panel of your recently-worked folders, then releases into the dashboard
- **Overview:** stat cards (Active / Overdue / Complete / Total), filter by status / area / course, live search, deadline highlighting — over a dark "Hyperstudio" theme with ambient amber **beams** behind translucent **liquid-glass** surfaces
- **Folder gallery:** card grid of top-level sections with context-file excerpts and subfolder drill-down
- **Daily briefing:** tech-news RSS, founder feeds, and live job openings aggregated on the home page
- **Claude token-usage panel:** aggregates `~/.claude/projects/**/*.jsonl` for today's tokens, all-time total, cache reads, estimated API cost, a 14-day chart, and a per-model breakdown (token counts + timestamps only — never message content)
- **Chat & Evil Twin:** chat over the model router (`router.py`) — **Fast** = local Ollama (no API cost), **Smart** = Anthropic API, **Claude** = Claude in the cloud billed to your **subscription** (via the Claude Code CLI, not API credits). The local Fast tier reads and quotes real note **contents** via a read-only tool loop (v1.16); an opt-in **Edit mode** lets Chat write to the vault (v1.17)
- **Inbox (Gmail + Outlook):** connect multiple inboxes, read mail in a list + reading pane, and **save drafts** — drafts are **never sent** (you review and send in your mail client). One-time connect via `python connect_email.py gmail|outlook`; mail I/O is stdlib `urllib`+`json` over the Gmail API / Microsoft Graph, OAuth handled by `google-auth-oauthlib` + `msal` (v1.19)
- **Agents:** model-driven agents that run real, vault-confined tools (search/read/list/write notes, scaffold projects) in a tool-use loop (`agent.py`), streaming each step live. Built-ins: Daily Summarizer, Project Scaffolder, Research Agent, and **Inbox Triage** (summarizes unread mail and drafts replies). Agents can write notes/drafts — review their output. Runs on the `fast`/`smart`/`claude` tier (picker per agent; v1.18)

Needs the Claude Code CLI signed in to a Claude subscription for the `claude` tier (Chat + Twin); `ANTHROPIC_API_KEY` for the `smart` tier (Agents); Ollama (`ollama pull llama3.2`) for the `fast` tier. For the **Inbox**: `pip install -r dashboard/requirements.txt`, register OAuth clients (Google Cloud "Desktop app" → `GMAIL_OAUTH_CLIENT`; Azure public client → `MS_OAUTH_CLIENT_ID`, `MS_OAUTH_TENANT=consumers` for personal Outlook), then run `connect_email.py` once per account.

**Further steps:** Stage 4 automations (an in-process scheduler running agents on a cron — e.g. a morning standup or inbox triage), run-history persistence + a write-confirm gate (the trust floor for unattended runs), then optional send-with-confirm for email. Full roadmap in `dashboard/PRODUCT_VISION.md`.

## Bases
Obsidian 1.9+ `.base` files give live table views over note frontmatter (e.g. filter all `area/projects` notes, sort by deadline). Data lives in the notes' frontmatter, not the `.base` file — keep tags/status accurate and the tables stay current.
