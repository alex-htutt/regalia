# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

An Obsidian knowledge vault and active workspace for a summer internship and personal side projects. Most files are Markdown notes. Each project has its own `CLAUDE.md` with project-specific details.

## Vault conventions

**Do not create new files unless explicitly asked.** Answer from existing vault content first.

**Linking:** use `[[wikilinks]]`, never relative paths. Each folder has a `_context_<folder>.md` — read the nearest one before working in that folder.

**New project folder:** copy `templates/_context_TEMPLATE.md` → rename to `_context_<folder>.md` → add link in `Home.md`. Layout under each project: `code/`, `data/`, `notes/`, `research/`.

**Frontmatter schema** (required on every note):
```yaml
date: YYYY-MM-DD
tags: [area/internship, type/lab]
status: active | complete | archived
topic: ""
deadline: YYYY-MM-DD
related: []
```

**Tag taxonomy:** `area/{internship,projects}` · `type/{daily-log,standup,meeting,project,lab,lecture,problem-set,reference}` · `status/{active,complete,archived}` · `course/<slug>` (school-year notes; lowercase slug matching the course folder name, e.g. `course/ecse2610`, `course/focs`). Always `category/subcategory` format.

## Cursor rules (auto-loaded by path)

- `.cursor/rules/global.mdc` — always on; vault-wide defaults
- `.cursor/rules/internship.mdc` — fires on `Internship-Projects/**`
- `.cursor/rules/projects.mdc` — fires on `projects/**`
- `archive-*.mdc` — inactive reference rules for finished RPI courses

## Dashboard (`dashboard/`)

A local Flask web app that reads vault frontmatter and surfaces all notes as a task list.

**Run:**
```bash
cd dashboard
pip install -r requirements.txt
python app.py
# → http://localhost:5000
```
Or double-click `dashboard/start.bat` — it starts the server and opens the browser automatically.

**How it works:** `app.py` walks the vault recursively, parses YAML frontmatter from every `.md` file (skipping `templates/`, `.obsidian/`, `dashboard/`, etc.), and serves the results as JSON at `/api/tasks`. The frontend polls that endpoint and renders the task list client-side.

**v1 features (2026-06-10)**
- Stat cards: Active / Overdue / Complete / Total counts
- Filter by status (All / Active / Complete / Archived) and area (Internship / Projects / Research)
- Deadline highlighting: overdue in red, due within 3 days in amber
- Sort by deadline ascending; no-deadline items sink to the bottom
- Live search by title or topic
- File path shown on each card for quick reference

**v1.1 (2026-06-10)**
- Course-aware: `course/<id>` tags surface as a `course` field in `/api/tasks`, an amber chip on each card, and a course filter row (pills are built dynamically from whatever courses exist in the vault — hidden when there are none)

**v1.2 (2026-06-11)**
- Folder gallery on the homepage: a card grid of the top-level sections (projects, research, …), each card showing the folder name, an excerpt from its `_context_*.md` (frontmatter `topic` first, else first body line), and folder/note counts. Clicking a card opens the context file rendered in a modal, with subfolder chips for drill-down, breadcrumb navigation, Esc/backdrop close. Backed by `/api/browse?path=` (vault-rooted, traversal-safe). Open folder persists in the URL as `?folder=`.
- `_context_*.md` and `README*.md` files are excluded from the task list (reference docs and folder stubs, not tasks).

**v1.3 (2026-06-12)**
- Claude token-usage panel: aggregates Claude Code session transcripts from `~/.claude/projects/**/*.jsonl` and surfaces a usage panel under the stat cards. Shows today's tokens, all-time total, cache reads, and an estimated API cost, plus a 14-day token bar chart and a per-model breakdown. Backed by `/api/usage`. The parser reads only token counts, model, and timestamp (never message content), dedupes by `message.id`+`requestId`, and estimates cost from public API list prices (opus/sonnet/haiku families; unknown models count tokens but $0 cost). Renders an empty state when no logs exist.

**v1.4 (2026-06-13)**
- Desktop app shell: `dashboard/desktop.py` (pywebview) wraps the existing Flask app in a native OS window — same code, same UI, no browser tab. Runs Flask in a daemon thread on an OS-assigned free port, waits for it to come up, then opens the window; `desktop.bat` double-click-launches it. External http/https links are routed to the system browser via a small `js_api` bridge (so future web-search result links don't get trapped in the window). The browser path (`python app.py` / `start.bat`) is unchanged and needs no new deps; only the desktop window requires `pywebview`.

**v1.5 (2026-06-13)**
- Real agent loop (workspace stage 3): the stubbed Agents view now runs genuine model-driven, tool-using agents over the vault. `router.py` adds `chat_tools()` — a tier-aware single-step tool-use call (Anthropic native tool use; Ollama tool-calling via message/tool translation). New `agent.py` holds the vault tools (`search_vault`, `read_note`, `list_notes`, `list_folder`, `write_note`, `create_project` — all vault-confined and traversal-safe), an `AGENTS` registry (Daily Summarizer / Project Scaffolder / Research Agent, each = system prompt + allowed tools + default tier), and `run_agent()` which drives the model→tools→results→repeat cycle (step cap 8) emitting a per-step event. `POST /api/agent/run` launches a background-threaded run and returns a `run_id`; `GET /api/agent/run/<id>` polls status + streamed steps (in-memory store, capped). The Agents view streams each step (think / tool call / result) live and renders the final answer. Project-creation logic is now shared via `create_project_core()`. Works on both tiers (local Ollama `fast` and Claude `smart`).

**Planned / backlog**
- Click a card to open the note in the default editor
- Inline status toggle (mark complete without leaving the dashboard)
- Create new task/note from dashboard (writes a file with correct frontmatter)
- Group-by view (group by area or type instead of flat sorted list)
- Tag-based filtering beyond area (type, course, etc.)
- Persistent filter state (URL params or localStorage)
