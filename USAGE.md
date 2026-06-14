---
date: 2026-06-12
tags: [type/reference]
status: active
---

# 📖 Usage Guide

Quick reference for running this vault day-to-day. See [[Home]] for the map and [[README_HOME]] for structure.

## Daily flow
1. Open the vault folder in **Cursor** (indexes all `.md` for `@codebase`).
2. Start the day: new note from `templates/daily-log.md` in `Internship-Projects/`.
3. Log meetings as you go with `templates/meeting-note.md` → save in `meetings/`.
4. End of day: update `Internship-Projects/_context_internship_projects.md` (active task, blockers, next deadline).

## Creating a note
Use Obsidian's **Templates** core plugin (or Templater): Settings → Templates → set folder to `templates/`. Then `Cmd/Ctrl+P → Insert template`. Every template carries the frontmatter schema and a footer `Part of [[_context_<project>]] · [[Home]]` — replace `<project>` with the folder's context name (e.g. `[[_context_pull_healthcare_card]]`) so the note links into the graph. `[[Home]]` always resolves.

Pick the template by purpose: `daily-log`, `standup-note`, `meeting-note`, `project-note`, `lab-note`, `lecture-note`, `problem-set`.

## Starting a new internship project
1. Make a subfolder under `Internship-Projects/` (e.g. `Internship-Projects/payments-api/`).
2. Copy `templates/_context_TEMPLATE.md` into it, rename it to `_context_<folder>.md` (e.g. `_context_pull_healthcare_card.md`), and fill in current state, deliverable, deadline.
3. Add a link to it from the Active section of [[Home]].
4. Drop project notes alongside it using `project-note.md`.

Side projects work the same way under `projects/`.

## Frontmatter (every note)
```yaml
date: YYYY-MM-DD
tags: [area/internship, type/lab]
status: active | complete | archived
topic: ""
deadline: YYYY-MM-DD
related: []
```
Keep `status` and `deadline` current — that's what the Bases view filters on.

## Tags
`area/internship`, `area/projects` · `type/{daily-log,standup,meeting,project,lab,lecture,problem-set,reference}` · `status/{active,complete,archived}`. Always `category/subcategory` format.

## Linking
Use `[[wikilinks]]`, not file paths. Each folder's context file is `_context_<folder>.md` (unique names, so links are unambiguous). Link a note to its `[[_context_<folder>]]` and to related notes as you write. The right-pane **backlinks** show everything pointing at the current note. Graph view (`Cmd/Ctrl+G`) shows clusters — filter out `path:templates/` to keep it clean.

## Using Cursor
- **`@codebase`** — semantic search across the whole vault ("what did I note about the I2C ranger?").
- **`@file Internship-Projects/_context_internship_projects.md`** — prime a chat with current status without searching.
- **Rules apply automatically** by folder: working in `Internship-Projects/` loads `internship.mdc`; `projects/` loads `projects.mdc`; archived courses load their reference rules. No action needed.
- **Chat (Cmd+L)** to understand, **Composer (Cmd+I)** to make multi-file edits — don't mix.

## Dashboard
Run `cd dashboard && python app.py` (or double-click `dashboard/start.bat`) → http://localhost:5000.

- **Task list:** all vault notes with frontmatter, filterable by status / area / course, sortable by deadline, with live search. Overdue notes are red; due within 3 days are amber.
- **Folder gallery:** browse top-level sections; click a card to open its context file in a modal with subfolder drill-down. `?folder=` in the URL preserves the open folder.
- **Claude usage panel** (v1.3): reads `~/.claude/projects/**/*.jsonl` for token counts and shows today / all-time / cache-read totals, an estimated API cost, a 14-day bar chart, and a per-model breakdown. Message content is never read.
- **Chat & Evil Twin** (v1.6 router): one chat over backends — **Fast** runs locally on Ollama (no API cost), **Claude** runs on Claude in the cloud billed to your **subscription** (not API credits, via the Claude Code CLI). Toggle the tier; a status dot shows what's live. (The **Agents** view still uses the API `smart` tier — its tool use needs it.)
- **Agents** (v1.5): launch an agent against a task and watch it work. *Daily Summarizer* rolls recent daily-logs into a standup, *Project Scaffolder* turns a one-line brief into a project folder, *Research Agent* reads vault notes and writes a research note. Each run drives real vault tools through the model router and streams its steps live. Agents can read **and write** vault notes, so review what they produce.

`_context_*.md` and `README*.md` files are excluded from the task list — they are reference docs, not tasks.

## Bases (live tables)
`Internship-Projects/internship.base` (Obsidian 1.9+) shows every `area/internship` note as a sortable table with two views: all notes, and active-only sorted by deadline. Data comes from note frontmatter — just keep tags/status accurate and notes appear automatically.

## Archive
Finished courses live in `archive/courses/` (`status: archived`). Searchable for reference; their Cursor rules are marked inactive so they don't bleed into current work.

---

