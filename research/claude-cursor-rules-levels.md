---
date: 2026-06-22
tags: [area/research, type/reference]
status: active
topic: "Claude Code & Cursor rule mechanisms and the scope levels each can target"
deadline:
related: ["[[_context_research]]", "[[_context_internship_projects]]", "[[_context_dashboard]]"]
---

# Claude & Cursor Rules — Mechanisms and Levels

## Overview
This note catalogs the rule/configuration mechanisms available in **Cursor** and **Claude Code**, and the **scope level** each one can be applied at in this vault. "Level" = how wide the rule's reach is, from broadest to narrowest:

1. **User / global** — every project on this machine (lives in `~/.claude/`, outside the vault).
2. **Vault root** — whole vault (`CLAUDE.md`, `.cursor/rules/*` with `alwaysApply`).
3. **Folder / path-scoped** — fires only inside a subtree (nested `CLAUDE.md`, glob-scoped `.mdc`).
4. **File-pattern** — fires when a matching file is touched/referenced (glob rules).
5. **On-demand / manual** — pulled in only when invoked (agent-requested rules, skills, `@mentions`).

The vault already uses a **layered** setup: a root [[CLAUDE]], per-folder agent-rule `CLAUDE.md` files, and a `.cursor/rules/` set spanning all four Cursor rule types. The findings below map what exists and what levels are still unused.

---

## Cursor rules — types and the level each targets
Cursor reads `.mdc` files from `.cursor/rules/`. The frontmatter fields (`alwaysApply`, `globs`, `description`) select the **rule type**, and each type maps to a level:

| Rule type | Frontmatter trigger | Level | Vault example |
|---|---|---|---|
| **Always** | `alwaysApply: true` | Vault root (every chat) | `.cursor/rules/global.mdc` |
| **Auto Attached** | `globs: <pattern>` | Folder / file-pattern | `internship.mdc` (`Internship-Projects/**`), `projects.mdc`, `research.mdc`, `archive-*.mdc` |
| **Agent Requested** | `description:` set, no globs, `alwaysApply` off | On-demand (model decides from description) | *not currently used* |
| **Manual** | none of the above; invoked via `@ruleName` | On-demand (explicit) | *not currently used* |

Additional Cursor levels available but unused here:
- **Nested rule directories** — a `.cursor/rules/` folder placed *inside* a subdirectory scopes rules to that subtree without needing globs. Could put Cursor rules next to a specific internship project.
- **`@file` includes** — a rule can pull another file into context (e.g. `@templates/daily-log.md`), letting a rule reference templates instead of restating them. The [[_context_research]] note already documents the `@file` priming convention for chats.
- **Legacy `.cursorrules`** — single root file, deprecated in favor of `.cursor/rules/`; avoid.

**Current coverage:** the vault uses *Always* (1) + *Auto Attached* (3 active + 5 archived). The two on-demand types (*Agent Requested*, *Manual*) and nested rule dirs are unused.

---

## Claude Code rules — mechanisms and the level each targets
Claude Code has a wider mechanism set than Cursor. Memory/instruction files and `settings.json` form two parallel hierarchies.

### A. Instruction memory (`CLAUDE.md`) — cascading levels
Loaded top-down; deeper files add to (don't replace) shallower ones.

| Level | File | Vault state |
|---|---|---|
| User / global | `~/.claude/CLAUDE.md` | **Not present** — no machine-wide Claude instructions exist yet |
| Vault root | `./CLAUDE.md` | Present — vault conventions, taxonomy, planning rules |
| Folder | `<folder>/CLAUDE.md` | Present in `research/`, `Internship-Projects/`, `projects/`, `dashboard/` |
| Personal (gitignored) | `CLAUDE.local.md` | Not used (deprecated; prefer `@import` of a private file) |
| Import | `@path/to/file` inside any `CLAUDE.md` | Not used — could DRY up repeated convention blocks |

The folder-level files are true **agent-rule** files (e.g. [[_context_internship_projects]]'s sibling `Internship-Projects/CLAUDE.md` enforces backend-Python + patient-data privacy; `research/CLAUDE.md` enforces citations + the three action tiers).

### B. Settings (`settings.json`) — cascading levels
Separate hierarchy from `CLAUDE.md`; controls permissions, hooks, env, model.

| Level | File | Precedence |
|---|---|---|
| Enterprise / managed | OS-managed policy path | Highest (overrides all) |
| User / global | `~/.claude/settings.json` | — |
| Project shared | `.claude/settings.json` (checked in) | — |
| Project local | `.claude/settings.local.json` (gitignored) | Highest non-managed |

**Vault state:** only `.claude/settings.local.json` exists — a large personal **permissions allowlist** (dashboard run commands, ollama/curl probes, git/gh, Roblox MCP tools). No shared `.claude/settings.json`, so none of these conventions are committed for collaborators/other machines.

### C. Other Claude-side rule mechanisms (each with its own level)
- **Permissions** (`allow` / `deny` / `ask` arrays) — level = whichever settings file holds them. Currently all in the *local* file; a `deny` rule (e.g. never touch patient data paths) could live at *project shared* level to be enforceable and committed.
- **Hooks** (`PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Stop`, etc.) — programmatic enforcement the model can't skip. Level = settings file. **Unused.** Strong fit for the [[_context_internship_projects]] privacy rule (a `PreToolUse` hook blocking reads/writes of claim-data files beats a prose instruction).
- **Subagents** (`.claude/agents/*.md`) — scoped agents with their own tools/instructions. Level = user (`~/.claude/agents/`) or project (`.claude/agents/`). **Unused** in-repo (the Research/Explore/Plan agents here are harness built-ins).
- **Skills** (`.claude/skills/`) — invokable workflows. Level = user or project. **Unused** in-repo.
- **MCP config** (`.mcp.json` project-level vs user-level) — declares MCP servers. Roblox Studio + Google/Notion servers are currently wired at the *user/client* level, not committed to the vault.
- **Output styles / status line** — cosmetic/behavioral, user-level (`statusline-command.sh` exists under `~/.claude/`).

---

## Mapping: what level each *intent* should live at
Practical guidance for this vault, matching a desired rule to the right mechanism + level:

- **"Applies to everything, always"** → root `CLAUDE.md` (Claude) + `global.mdc` `alwaysApply` (Cursor). *Already done.*
- **"Only inside this folder/project"** → nested `CLAUDE.md` (Claude) + glob `.mdc` (Cursor). *Already done for the 3 active areas.*
- **"Only when a specific filetype is edited"** → glob rule (`globs: **/*.py`) — currently globs are folder-shaped, not filetype-shaped; a `*.py` rule could centralize the backend-Python convention.
- **"Hard guarantee, not a suggestion"** → permissions `deny` + `PreToolUse` hook (Claude). *Not used — biggest gap for the privacy requirement.*
- **"Shared with the team / survives a reclone"** → move from `settings.local.json` to committed `.claude/settings.json`.
- **"Pulled in only when relevant"** → Cursor *Agent Requested* rule or a Claude *skill*. *Not used.*
- **"Same machine, all projects"** → `~/.claude/CLAUDE.md` + `~/.claude/settings.json`. *Not used — no global Claude layer.*

---

## Community-sourced rules worth adopting (web research, 2026-06-22)
A scan of widely-used Claude Code / Cursor rule collections and best-practice guides. Each entry: the rule, *why* it works, **where in the vault** it fits, and a source. Rules are filtered to ones that plausibly improve agent performance on *some tier* of this vault (root / folder / file / on-demand).

### From Claude Code best-practice guides (Anthropic + community)
- **Keep each `CLAUDE.md` short (target <~200 lines; rules start dropping past ~80).** Long instruction files get partially ignored because key rules are lost in noise. *Where:* the root [[CLAUDE]] and the larger folder files (`dashboard/CLAUDE.md` carries a full v1–v1.18 changelog) — move history/reference out into linked notes and keep the rule file lean. (maketocreate 2026 guide; TECHSY "9 Rules for 2026.")
- **Lead with the exact commands (test / build / lint / run) before any prose rules** — highest-ROI section. *Where:* `dashboard/CLAUDE.md` should open with the precise run/test invocations; the vault root has none because it's notes-only, which is correct. (Anthropic best-practices; maketocreate.)
- **Only include what the agent can't infer from the code/README; never restate a linter/formatter.** LLMs are slow and unreliable at deterministic style jobs. *Where:* trim any style guidance from folder rules that a formatter already enforces (the dashboard's Python). (maketocreate; DEV Community.)
- **Attach a *reason* to every rule.** "Server components by default — we hit 8s LCP from over-clienting" generalizes; a bare rule gets dropped when context shifts. *Where:* the privacy rule in [[_context_internship_projects]] and the citation rules in `research/CLAUDE.md` already do this; apply the same to the taxonomy rules in root [[CLAUDE]]. (maketocreate; Anthropic.)
- **Enforce critical/irreversible rules with hooks, not prose** ("don't push to main," "don't touch production/patient data"). 70% prose compliance = an eventual incident; a hook makes the bad action structurally impossible. *Where:* directly confirms this note's existing top open question — a `PreToolUse` hook + `deny` rule for Ambusun/Essex claim-data paths. (maketocreate; Anthropic.)
- **Always pair a change with a verification (test, script, screenshot); "if you can't verify it, don't ship it."** *Where:* fits the `research/` "Basic execution" tier and any `dashboard/` change — add a "verify with" line to those folder rules. (maketocreate; Anthropic best-practices.)
- **Maintain a dogfooded, copyable `.claude/` setup (settings, hooks, agents) checked into the repo.** *Where:* reinforces this note's gap — promote conventions from `settings.local.json` into a committed `.claude/settings.json`. (shanraisshan/claude-code-best-practice; MuhammadUsmanGM/claude-code-best-practices.)

### From Cursor rule collections (awesome-cursorrules et al.)
- **Add an explicit anti-sycophancy / honesty block** — directives forbidding hallucinated APIs, invented function signatures, and false-confidence validation. *Where:* strong fit at vault root and especially `research/CLAUDE.md`, whose "no hallucinated benchmarks / citations matter" rules are the same instinct — generalize them into a vault-wide "don't invent, say when unsure" rule. (PatrickJS/awesome-cursorrules.)
- **Add an anti-over-engineering rule: keep changes scoped, simple, tied directly to the request.** *Where:* root [[CLAUDE]] — complements the existing "don't create new files unless asked" rule. (PatrickJS/awesome-cursorrules.)
- **State local architecture, preferred libraries, and common methods so suggestions fit on the first pass.** *Where:* `dashboard/CLAUDE.md` already does this; extend the pattern to internship project folders. (PatrickJS/awesome-cursorrules; dotcursorrules.com.)
- **Adopt conventional-commit message standards as a rule.** *Where:* this vault already follows `feat(dashboard): …` / `fix(dashboard): …` in git history — codifying it in a rule makes the agent match it automatically. (PatrickJS/awesome-cursorrules.)
- **A dedicated PR/code-review rule with severity ranking, file:line citations, and separate angles (security, performance, tests, architecture).** *Where:* on-demand tier — a Cursor *Agent Requested* rule or a `research/`-style reference, useful once dashboard work has external contributors. (PatrickJS/awesome-cursorrules.)
- **Filetype-globbed rules (e.g. `globs: **/*.py`) for language conventions rather than folder-shaped globs.** *Where:* directly answers this note's existing question about centralizing the "backend-first Python" convention across folders. (awesome-cursorrules frontmatter conventions.)

### Net new for this vault (highest value first)
1. **Privacy hook** — `PreToolUse` deny on Ambusun/Essex claim-data paths (already this note's #1 open question; community consensus confirms hooks > prose).
2. **Vault-wide honesty rule** — generalize `research/`'s no-hallucination stance to root [[CLAUDE]] (cheap, broad win).
3. **Trim + front-load `dashboard/CLAUDE.md`** — commands first, move the v1–v1.18 changelog to a linked note.
4. **Filetype `*.py` Cursor rule** — DRY the Python convention.
5. **Commit a shared `.claude/settings.json`** — promote conventions out of the local-only file.

---

## Open questions
- Should the privacy guarantee for Ambusun/Essex data become an enforced `PreToolUse` hook + `deny` permission rather than prose in [[_context_internship_projects]]? (Highest-value upgrade.)
- Are any conventions in `settings.local.json` worth promoting to a committed `.claude/settings.json` so they're shared and version-controlled?
- Is a filetype-scoped Cursor rule (`globs: **/*.py`) cleaner than repeating "backend-first Python" across folder rules?
- Worth a user-level `~/.claude/CLAUDE.md` for cross-project habits (since the [[_context_dashboard]] work and the workspace direction span beyond this vault)?
- Should Cursor *Agent Requested* rules be added for niche-but-recurring tasks (e.g. LaTeX problem-set formatting from the archived course rules) so they load only on demand?
- Is an explicit anti-sycophancy/honesty block worth promoting from `research/` up to vault root, or does that over-broaden a folder-specific concern?

---

## Sources (web research, 2026-06-22)
- Anthropic — *Best practices for Claude Code*: https://code.claude.com/docs/en/best-practices
- maketocreate — *CLAUDE.md Best Practices: The Complete 2026 Guide*: https://maketocreate.com/claude-md-best-practices-the-complete-2026-guide/
- DEV Community (nishilbhave) — *CLAUDE.md Best Practices: The Complete 2026 Guide*: https://dev.to/nishilbhave/claudemd-best-practices-the-complete-2026-guide-435j
- TECHSY — *CLAUDE.md Best Practices: 9 Rules for 2026*: https://techsy.io/en/blog/claude-md-best-practices
- shanraisshan — *claude-code-best-practice*: https://github.com/shanraisshan/claude-code-best-practice
- MuhammadUsmanGM — *claude-code-best-practices*: https://github.com/MuhammadUsmanGM/claude-code-best-practices
- PatrickJS — *awesome-cursorrules*: https://github.com/PatrickJS/awesome-cursorrules
- dotcursorrules — *.cursorrules directory*: https://dotcursorrules.com/
