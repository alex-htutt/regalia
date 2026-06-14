---
date: 2026-05-30
tags: [type/reference]
status: active
---

# Work Vault

Obsidian knowledge vault + Cursor context system. Single home for all work: the summer internship (active) and side projects, with finished RPI coursework archived for reference.

## Layout
- `Internship-Projects/` — active work. One subfolder per assigned project, each with its own `_context_<project>.md`. Area-level status in `Internship-Projects/_context_internship_projects.md`.
- `projects/` — personal/side projects (competitive programming, algo trading, embedded).
- `research/` — self-directed learning outside classwork (RAG pipelines, ML, etc.). One subfolder per subject; add `_context_<subject>.md` when a topic gets dense.
- `archive/courses/` — finished RPI courses (engr2350, ecse2610, focs, phys, writ). Reference-only.
- `meetings/`, `ideas/`, `attachments/` — cross-cutting.
- `templates/` — note templates (point Obsidian's Templates/Templater plugin here).
- `.cursor/rules/` — Cursor `.mdc` rules. `global.mdc` always applies; `internship.mdc` and `projects.mdc` scope by path; `archive-*.mdc` are inactive references.
- `.cursorignore` — keeps `.obsidian/`, `attachments/`, `templates/`, and view files (`*.base`, `*.canvas`) out of Cursor's index.

## Context model (3 layers)
1. **Rules** (`.mdc`) — ambient, auto-loaded by file path. Keep lightweight.
2. **`_context_<folder>.md`** — dense per-folder status file (named after its folder, e.g. `_context_pull_healthcare_card.md`). Prime a chat with `@file Internship-Projects/<project>/_context_<project>.md`.
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
`area/internship`, `area/projects` · `course/{engr2350,ecse2610,focs,phys,writ}` · `type/{lecture,lab,problem-set,exam-prep,meeting,standup,daily-log,project,reference}` · `status/{active,complete,archived}`

## Getting started in Cursor
1. Open this folder as a Cursor workspace → it indexes all `.md` files.
2. `@codebase` for semantic search across the vault; `@file` for a specific note.
3. Rules apply automatically based on the folder you're working in.
4. Optional: install the "Open in Cursor" Obsidian community plugin.

## Dashboard
`dashboard/` is a local Flask cockpit over the vault — it started as a read-only task dashboard and is growing into a self-hosted, agentic workspace. Full feature log in the vault-root `CLAUDE.md`; dense project snapshot in `dashboard/_context_dashboard.md`.

**Run:** `cd dashboard && python app.py` → http://localhost:5000, or double-click `dashboard/start.bat`. Native window: `dashboard/desktop.py` / `desktop.bat`.

Features as of v1.6 (2026-06-14):
- **Overview:** stat cards (Active / Overdue / Complete / Total), filter by status / area / course, live search, deadline highlighting
- **Folder gallery:** card grid of top-level sections with context-file excerpts and subfolder drill-down
- **Claude token-usage panel:** aggregates `~/.claude/projects/**/*.jsonl` for today's tokens, all-time total, cache reads, estimated API cost, a 14-day chart, and a per-model breakdown (token counts + timestamps only — never message content)
- **Chat & Evil Twin:** chat over the model router (`router.py`) — **Fast** = local Ollama (no API cost), **Claude** = Claude in the cloud billed to your **subscription** (via the Claude Code CLI, not API credits)
- **Agents:** model-driven agents that run real, vault-confined tools (search/read/list/write notes, scaffold projects) in a tool-use loop (`agent.py`), streaming each step live. Built-ins: Daily Summarizer, Project Scaffolder, Research Agent. Agents can write notes — review their output. (Uses the API `smart` tier for tool use.)

Needs the Claude Code CLI signed in to a Claude subscription for the `claude` tier (Chat + Twin); `ANTHROPIC_API_KEY` for the `smart` tier (Agents); Ollama (`ollama pull llama3.2`) for the `fast` tier.

## Bases
`Internship-Projects/internship.base` is a live table view (Obsidian 1.9+) filtering all `area/internship` notes — data lives in note frontmatter, not the `.base` file.
