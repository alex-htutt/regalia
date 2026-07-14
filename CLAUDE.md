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

**Tag taxonomy:** `area/{internship,projects,schoolwork}` · `type/{daily-log,standup,meeting,project,lab,lecture,problem-set,reference}` · `status/{active,complete,archived}` · `course/<slug>` (schoolwork notes; lowercase slug matching the course folder name, e.g. `course/math1c`, `course/focs`). Always `category/subcategory` format.

## Planning coding projects (macro + micro)

When planning or scaffolding any coding project, split the plan into two parts:

- **Macro plan** — the conventional high-level plan: goals, horizon, scope/scale, milestones, and constraints. *What* is being built and *why*.
- **Micro plan** — the concrete build plan: the actual code components that will make it up (modules, files, functions/classes, data shapes, interfaces between parts, dependencies, and build order). *How* it gets built.

The micro plan exists so a building agent has a solid, component-level blueprint to work from rather than improvising structure. If problems arise during the build, revise the **micro plan** — adjust components, split or merge them, change interfaces — while keeping the macro plan stable unless the goals themselves change.

## Working rules (vault-wide)

- **Don't invent; say when unsure.** Never fabricate APIs, function signatures, benchmark numbers, citations, or capabilities. If you don't know, say so and offer to check. *Why:* false confidence is worse than a gap — a wrong API or made-up benchmark costs more to unwind than the honest "I don't know." (Generalized from the `research/` citation rules.)
- **Stay scoped.** Make the smallest change that satisfies the request; don't refactor, add abstractions, or build for hypothetical futures unasked. *Why:* unrequested scope creep is the most common way an agent introduces risk and review burden. Pairs with "don't create new files unless asked."
- **Pair every change with a way to verify it** (a test, a run command, a screenshot, a quoted result). If you can't verify it, say so rather than claiming it works. *Why:* "done" without evidence is just a guess.
- **Commits follow conventional-commit style** matching this repo's history: `type(scope): summary` (e.g. `feat(dashboard): …`, `fix(dashboard): …`, `docs: …`). Only commit when asked. *Why:* the agent should match the existing log automatically, not invent a new format.
- **Check for an applicable skill before changing the vault.** Before making any change to this vault, check the skills in `.claude/skills/` (each has a `SKILL.md` describing when it applies) and, if one covers the task, invoke it instead of improvising — even if the task looks simple enough to do by hand (e.g. `course-setup` for anything coursework-setup-shaped). *Why:* skills encode this vault's conventions end-to-end; improvising past one produces structure the skill would have gotten right, and drift between skill-made and hand-made files. Do not read every skill in-depth, and use file names to determine if skill may be used or not. Read each candidate skill for verification.
- **Rule files: completeness over brevity.** Keep `CLAUDE.md` / `.mdc` files focused, but there is **no hard line-count cutoff** — don't drop, truncate, or water down a genuinely useful rule just to make a file shorter. If a file grows long, prefer moving *reference* material (changelogs, long examples, history) into a linked note and keep the rules themselves intact. *Why:* a missing rule is more expensive than a long file; brevity is a tiebreaker, not a constraint.

## Cursor rules (auto-loaded by path)

- `.cursor/rules/global.mdc` — always on; vault-wide defaults
- `.cursor/rules/internship.mdc` — fires on `Internship-Projects/**`
- `.cursor/rules/projects.mdc` — fires on `projects/**`
- `.cursor/rules/research.mdc` — fires on `research/**`
- `.cursor/rules/python.mdc` — fires on `**/*.py` (backend-first Python conventions)
- `archive-*.mdc` — inactive reference rules for finished RPI courses

## Dashboard (`dashboard/`)

A local Flask web app that reads vault frontmatter and surfaces all notes as a task list. Architecture and run instructions live in `dashboard/CLAUDE.md` (loaded automatically when you work in that folder) — read it before changing dashboard code; the full v1–v1.23 version history is in `dashboard/VERSION_HISTORY.md`.
