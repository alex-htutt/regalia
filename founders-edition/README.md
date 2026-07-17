# Founder's Edition — the creator's personal workflow

Regalia ships **workflow-agnostic**: the default vault carries no opinion about how *you*
organize internships, side projects, research, or coursework. When Regalia is pointed at a
connected external folder it reads *that folder's* own conventions (its `CLAUDE.md`,
`AGENTS.md`, `.cursor/rules`, or `README`) instead of imposing any structure.

This directory is the **opt-in** counterpart: the personal workflow the creator actually
uses, packaged so you can adopt it if you want to mimic that setup. It is **not** loaded by
default and nothing here is required to run Regalia.

## What's inside

```
founders-edition/
  .cursor/rules/           internship / projects / research area rules (Cursor auto-loads by path)
  projects/CLAUDE.md       conventions for a personal side-projects area
  research/CLAUDE.md       conventions for a self-directed research area (three action tiers)
  .claude/skills/          the `course-setup` skill (scaffold a college course + study materials)
```

Example course/school names in the `course-setup` skill have been genericized (e.g.
"State University"); swap in your own. The creator's finished-course archive rules and
internship-specific rules are intentionally **not** included — they're personal and
non-reusable.

## How to adopt it

Copy the contents into your vault root, then reload Cursor / Claude Code so the rules and
skill register:

- **Windows (PowerShell):** `./founders-edition/apply.ps1`
- **macOS / Linux:** `bash founders-edition/apply.sh`

Both scripts copy `.cursor/rules/*`, the area `CLAUDE.md` files, and the `course-setup`
skill into place. They **do not overwrite** an existing file unless you pass `-Force` /
`--force`. Review each file and edit the conventions to match how you actually work — this
is a starting point, not a mandate.
