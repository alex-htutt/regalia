---
name: course-setup
description: >-
  Scaffold and maintain a college/university course inside this Obsidian vault, and generate study
  materials from its syllabus and lecture notes. Use this whenever the user starts, adds, or sets up a
  class or course ("set up Math 1C", "new class at Foothill", "make a project for this course"), uploads a
  syllabus or lecture PDF for a class, asks for a problem set / study guide / practice quiz / practice exam
  built from course material, or wants course deadlines (exams, assignments, learning checks) on their calendar —
  even if they don't say the word "skill" or spell out every step. It follows the vault's own conventions
  (per-folder context files, the frontmatter schema, the tag taxonomy, wikilinks) and respects each
  course's academic-integrity / AI policy. Prefer this skill for anything coursework-setup-shaped rather
  than improvising folder structure.
---

# Course Setup (Obsidian vault)

Set up a new course as a first-class project in this vault and keep it useful over the term: a clean folder
matching the vault's conventions, a dense context file, materials extracted from the real syllabus and
lecture notes, generated study aids, and deadlines on the calendar. The aim is that the course's
`_context_<slug>.md` becomes the single source of truth a future chat can be primed with.

This SKILL.md holds the shared workflow. The depth for each aspect lives in `references/` — read only the
one you need so context stays lean.

## Before you touch anything: load the conventions
Don't guess how this vault is organized — it tells you. Read, in order:

1. `CLAUDE.md` at the vault root — vault-wide rules (frontmatter schema, tag taxonomy, "don't create files unless asked", wikilinks-not-paths, verification expectations).
2. The nearest `_context_<folder>.md` and `templates/_context_TEMPLATE.md` (the master to copy).
3. An existing course's context file as a style reference, if one exists.

Why: the value of this vault is its consistency. A course that ignores the schema/tags/linking is worse than none — it quietly breaks the dashboard, the tag views, and future context-priming.

## 1. Scaffold the course folder (the spine)
- **Location:** active coursework lives under `schoolwork/<slug>/` (never `archive/`, which is finished/reference-only). Confirm only if genuinely ambiguous.
- **Slug:** lowercase, department+number smashed together, matching existing slugs (e.g. `math1c`, `ecse2610`). The tag is `course/<slug>`.
- **Subfolders:** default `notes/`, `problem-sets/`, `exams/`, `research/` for a class (adapt — e.g. `code/` for CS). Keep empty folders in git with a `.gitkeep`.
- **Context file:** copy the template to `schoolwork/<slug>/_context_<slug>.md`. Fill what you know; mark the rest `_TBD (syllabus)_`. Use the required frontmatter (`date`, `tags: [course/<slug>, type/reference, status/active]`, `status`, `topic`, `deadline`, `related`).
- **Register it:** add a `[[wikilink]]` from `Home.md` under an active/schoolwork section, per the vault's new-project convention.

## 2. Then handle the specific aspect — read the matching reference
Read only the file for the task in front of you:

- **Filling the context file from an uploaded syllabus / lecture PDF** → `references/syllabus-intake.md`
- **Problem sets, study guides, practice quizzes** → `references/study-materials.md`
- **Practice exams** (topic-by-topic: prerequisites → mini-checks → exam-level) → `references/practice-exams.md`
- **Putting course deadlines on the user's calendar** → `references/calendar.md`

A single "set up my class" request usually means: scaffold (above) → syllabus intake → then offer study materials + calendar.

## Conventions to honor (all aspects)
- Use `[[wikilinks]]`, never relative paths.
- Make the smallest change that satisfies the request; don't refactor the vault or create extra files unasked (a *requested* study aid is the request, not scope creep).
- Pair every change with a way to verify it (file tree, balanced-`$` check, links resolve, `git status`). Don't claim it renders without checking.
- Don't commit to git unless asked; when you do, match the repo's conventional-commit style.

## Guardrails (all aspects)
- **Academic integrity:** if the course's AI policy restricts AI on submissions (common), keep help to studying and concepts — explanations, original practice problems, worked examples — and do not produce answers to submit for graded work (Learning Checks, exams, graded homework). Sample/practice material is fine.
- **Don't invent** APIs, dates, citations, or course facts; say when unsure and offer to check.

## Example
Input: "set up my new class, ECON 1A at De Anza — here's the syllabus" (PDF attached)
Action: load vault `CLAUDE.md` + template → scaffold `schoolwork/econ1a/` with subfolders + `_context_econ1a.md` (tag `course/econ1a`) → link from `Home.md` → read `references/syllabus-intake.md` and fill the context file → offer study materials (`references/study-materials.md`) and calendar dates (`references/calendar.md`).
