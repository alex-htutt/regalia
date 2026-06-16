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

**v1.6 (2026-06-14)**
- Subscription-billed chat: a third router tier, `claude`, shells out to the Claude Code CLI (`claude -p --output-format json`, prompt piped via stdin) so the **Chat** and **Evil Twin** panels run on your Claude subscription instead of API credits. `router.py` adds `_claude_code_chat()` (with `_claude_cli_path()` + `_flatten_conversation()`), a `claude` entry in `status()`, and the tier branch in `chat()`; the subprocess env has `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` stripped so it always uses subscription (OAuth) auth. Chat's cloud button and the Twin both now default to this tier (cloud pill relabeled "✨ Claude · plan"); `fast` (local Ollama) is unchanged. The **Agents view keeps using the `smart` API tier** — its tool-use loop needs native Anthropic tool calls, which the CLI doesn't expose this way. Configurable via `CLAUDE_CLI`, `CLAUDE_CLI_MODEL` (default: plan default), `CLAUDE_CLI_TIMEOUT`. No new Python deps.

**v1.7 (2026-06-14)**
- Vault-aware local chat: the `fast` (local Ollama) tier in the Chat panel was blind — `/api/chat` called `router.chat()` with no tools, so the weak local model never saw the vault. It now gets the live vault structure injected into its system prompt: `app.py` adds `_vault_outline()` (a hard-capped, indented folder+note tree honoring `IGNORE_DIRS`/dotfile skips, read fresh per request) and `_vault_chat_system()` (preamble + outline + any caller system), applied in `api_chat` only when `tier == "fast"`. The model can now answer "what's in my vault / where does X live" questions grounded in real structure; it's told it can see the structure but not note contents (no tool calls — that's the cloud/agent path). The `smart`/`claude` tiers are untouched (they can read files themselves). No new deps.

**v1.8 (2026-06-14)**
- Home-page daily briefing: a panel under the usage panel aggregating tech-news RSS (HN, TechCrunch, The Verge, Ars Technica), Bluesky founder feeds + blog RSS, and live job openings (Greenhouse/Lever public JSON). Backed by `/api/news`. All fetching is stdlib-only (`urllib` + `xml.etree` + `json`, namespace-agnostic RSS/Atom parser) — no API keys, no new deps. Results are held in an in-process TTL cache (`NEWS_TTL`, default 30 min) — the cache *is* the refresh routine; the first request after expiry refetches, `?refresh=1` forces it. Every source is wrapped so one dead feed degrades to a skipped section (collected in `errors`), never a 500. Sources are configured in `dashboard/news_sources.py` (feed list, Bluesky handles, board slugs). Links open in the system browser in both browser and desktop modes.

**v1.9 (2026-06-14)**
- Hyperstudio dark redesign: the whole UI was re-skinned from the original light theme to the "designer's midnight gallery" dark design system speced in `dashboard/Assets/DESIGN.md` (near-monochrome obsidian canvas `#101010`, flat gray surface stack `#181818`→`#212121`, onyx `#2a2a2a` hairlines, frost text, **Amber Whisper `#e7c59a` as the sole chromatic accent**). All changes live in the single `templates/index.html` — no new endpoints, no Python changes, no build step. The existing CSS referenced design tokens by variable *name* (`--bg`, `--surface`, `--border`, …), so remapping the `:root` block cascaded across every component; only hardcoded light values (error surfaces, modal shadow/backdrop, archived dot, the 7 `color:#fff`-on-accent spots) needed individual edits. Typography moved to **Inter** (Aeonik substitute) + **JetBrains Mono** (Input substitute) via Google Fonts (system fallback offline), body tracking `-0.011em`, and the brand's signature **whisper-weight 400** display type on the big stat/usage numbers and view headings (was bold 700). Header gained the `Regalia_Icon.png` crown-spade logo (served from `/static/logo.png`, also the favicon) + wordmark + mono tagline. Per the system's "no drop shadows" rule, depth now comes from grays + hairlines (gallery card hover lifts to the elevated surface; modal uses a border + deep void backdrop); bright tag chips desaturated to translucent dark; functional status colors (overdue red, due-soon, green dot) kept but muted; dark custom scrollbars; radii on the 8/20/99 system. Active nav/pills/CTAs invert to the white-fill button with `--accent-fg` dark text. All 18 smoke tests pass; no new deps.

**v1.10 (2026-06-14)**
- Tailwind build pipeline (standalone CLI, no Node): added compiled Tailwind v4 so the frontend can adopt utility classes and paste plain-HTML Tailwind components. Uses the **standalone binary** `dashboard/tools/tailwindcss.exe` (~108MB, **gitignored**; re-fetch via `get-tailwind.bat`) — no `npm`/`node_modules`, no new Python dep. `tailwind.input.css` imports only the theme + utilities layers (**preflight intentionally omitted** — its base reset would break the hand-written UI, e.g. markdown list bullets) and declares our Hyperstudio tokens as a v4 `@theme` (`bg-obsidian-canvas`, `text-amber-whisper`, `rounded-cards`, `font-aeonik`, …). Compiles to `static/tailwind.css` (committed, ~5KB minified, served by Flask, linked in `index.html` before the hand-written `<style>`). Build with `build-css.bat` (one-off) or `watch-css.bat` (live). Cascade is safe-by-construction: Tailwind utilities are in `@layer utilities` while the existing `<style>` is unlayered, so unlayered rules always win — utilities can't regress the current look and apply cleanly to new/pasted markup (use `bg-red-500!` to override an existing element). This is the project's first build step (the prior "no build step" rule was relaxed for CSS only, with user sign-off); the Python/Flask path is unchanged. All 18 smoke tests pass. See `dashboard/CLAUDE.md` "Tailwind" for the full workflow.

**v1.11 (2026-06-14)**
- Chat file attachments: the **Chat** panel can now attach images, PDFs, and text files (📎 next to the composer). New `POST /api/chat/upload` validates by extension (images/pdf/txt/md/csv/json/log/py) + size (25 MB), stores each file under a randomized name in `dashboard/.chat_attachments/` (gitignored; inside the vault tree so the `claude` CLI can read it, but under `dashboard/` which the vault walk ignores, so uploads never surface as notes), and returns a handle; old uploads are pruned after 24h. `/api/chat` takes an `attachments` list (handles resolved traversal-safe back to paths via `_resolve_attachments`) and `router.chat()` gained an `attachments` param applied to the latest user turn per tier: the **`claude`** tier is told the file paths and reads them with its own Read tool (enabled non-interactively via `--allowedTools Read` only when files are attached — handles every type); the **`fast`** (Ollama) tier inlines image attachments as base64 for vision models and names non-image files it can't read; the **`smart`** (Anthropic) tier builds native image/document content blocks (parity, not used by the chat panel). Frontend uploads each picked file immediately (staged chips with ⏳→📄, removable), blocks send until uploads finish, allows attachment-only turns, and renders attachment chips on the sent user bubble. Stdlib only (`base64`, `mimetypes`) — no new deps. All 18 smoke tests pass. (Twin reuses the same backend if its UI adds a picker later.)

**v1.12 (2026-06-14)**
- Background beams + liquid glass. An ambient amber "waves" layer and frosted surfaces on the overview. A fixed full-viewport SVG (`.beams`) renders ~9 curved bézier paths with a traveling amber dash (animated `stroke-dashoffset` keyframes — a dependency-free reimplementation of Aceternity's *Background Beams*, recolored to the sole Amber Whisper accent per `Assets/DESIGN.md`), sitting at `z-index:0` behind `.app` (raised to `z-index:1`) so it shows through the transparent canvas gaps; honors `prefers-reduced-motion`. The overview surfaces (stat cards, usage panel + mini-cards, news panel, folder-gallery cards, task cards) became translucent **liquid glass** via new `--glass*` tokens (`rgba` fill + `backdrop-filter: blur+saturate` + lit `--glass-border`), so the beams blur through them. Pure `templates/index.html` CSS — no Python, no Tailwind utilities, no rebuild. All 18 smoke tests pass.

**v1.13 (2026-06-14)**
- Landing page (ASCII hero + parallax), merged as the **entry point**. `/` now opens on a full-viewport hero whose background is a self-contained third-party ASCII-dither + WebGL effect (`dashboard/Assets/ascii_js.js`, copied verbatim to `static/ascii-dither-background.js`; it auto-mounts into `[data-ascii-dither-bg]`) — **the project's first third-party JS asset**, still no build step / no new deps. Below it sits a vanilla port of Aceternity's **Parallax Scroll**: a 3-column grid where columns 1 & 3 drift up and column 2 drifts down, driven by scroll progress mapped to `translate3d` on a `requestAnimationFrame` tick, disabled under `prefers-reduced-motion`. Hero + parallax live **above** the existing dashboard in the one `index.html`; scrolling past them slides the sticky header up and lands in the overview (`#dashboard` anchor). The hero canvases are CSS-overridden to `object-fit:fill` so the WebGL glow fills the hero without edge-clipping on resize **and** the script's linear mouse→grid mapping stays correct (the earlier `cover` cropped the content and offset the hover). No separate route — a brief standalone `/landing` page was folded in and removed. All 18 smoke tests pass.

**v1.14 (2026-06-14)**
- Renamed **Work Vault → Regalia** (branding only — the on-disk folder and `VAULT_ROOT` path are unchanged to avoid breaking git, the vault walk, and the Claude memory store): browser title, header wordmark, desktop window title, docstrings, and `.bat` comments. Hero copy is now a posh greeting ("Salutations."); the logo, tagline, and Enter button were removed. The parallax "in-between" section dropped the marketing copy — it now asks **"What should we work on?"** and lists the folders worked in most recently, backed by new `GET /api/recent-folders` (groups notes by project folder = the first two path segments, so vendored/resource subtrees roll up into their project; ranks by newest note mtime; returns the top 6 with a human "time ago" via a stdlib `_rel_time()` helper + note count). Tiles render into the parallax columns and open that folder in the browse modal on click. The amber beams were trialed on the landing, judged cluttered, and pulled back to the dashboard only (hero + parallax kept opaque). All 18 smoke tests pass.

**v1.15 (2026-06-14)**
- Landing reworked into **pinned scrollytelling** + a **Spotlight**, and the hero title changed to **"Regalia."** (was "Salutations."). The hero + parallax merged into one tall `.scrolly` track whose inner stage **pins** (`position: sticky`) and stays in place while scroll progress drives an *in-place* animation: the title shrinks/fades/rises, then the "What should we work on?" heading + recent-folder tiles assemble over it (staggered), then the stage releases into the dashboard. The earlier parallax-drift script was replaced by one rAF-throttled scroll driver (exposed as `window.__scrollyUpdate` so `renderRecentFolders` re-applies the start state once tiles load); it bails to a static stack under `prefers-reduced-motion` / ≤640px. Added a vanilla port of Aceternity's **Spotlight** — a large skewed ellipse blurred with `feGaussianBlur stdDeviation="151"` that fades + scales in from the top-left, recolored to the amber accent (16% opacity), layered above the ASCII background and below the title (hidden in the static fallback). The ASCII hero background is served from `static/ascii-dither-background.js`, a **copy** of `Assets/ascii_js.js`; new **`dashboard/sync-ascii.bat`** re-copies it after a re-export (the served file doesn't auto-update). All 18 smoke tests pass.

**v1.16 (2026-06-15)**
- Local chat can now read note *contents*, not just the outline. The `fast` (local Ollama) tier of the **Chat** panel was previously grounded only with the vault folder/file outline (v1.7) and was explicitly told it couldn't read note bodies. `/api/chat` now routes the fast tier through a new **read-only tool loop**, `agent.chat_vault()`, which exposes `search_vault` / `read_note` / `list_notes` / `list_folder` (the write/scaffold tools are deliberately withheld — a chat turn must never silently mutate the vault) and drives the model→tools→results cycle (step cap 6) over the full conversation, returning the final prose in `router.chat()`'s shape so it's a drop-in. The vault outline is still injected into that loop's system prompt to target reads. Requires a **tool-capable** local model; if the model can't do tool calls (or any other fast-tier `RouterError`), it gracefully **falls back** to the old outline-only chat. Attachment turns bypass the loop (no `chat_tools` attachment path yet) and keep the image-inlining path. `smart`/`claude` tiers unchanged. All 18 smoke tests pass; no new deps.

**v1.17 (2026-06-15)**
- Chat can now **write to the vault** ("Edit mode"), and the **Smart (Anthropic API) tier** is now selectable in the Chat panel (was fast/claude only). A ✏️ Edit toggle in the chat tier-bar (default off = read-only, unchanged) unlocks writes on **all three tiers**, each by its own path. **fast/smart**: `agent.chat_vault()` gained `allow_write` — when on it adds the existing vault-confined `write_note` / `create_project` tools (`CHAT_WRITE_TOOLS`) to the read-only set plus edit-mode guidance (`CHAT_WRITE_RULES`: read-before-overwrite since `write_note` replaces whole files, act only on explicit requests, report what changed), and bumps the step cap to 8; `/api/chat` routes fast always through the loop and smart through it only when Edit mode is on (otherwise smart takes the plain cloud path). These writes are **`.md`-only, traversal-guarded, vault-confined by construction**. **claude**: `router.chat(allow_write=...)` threads to `_claude_code_chat`, which grants the CLI `--allowedTools Read,Edit,Write,Glob,Grep` + `--permission-mode acceptEdits` (auto-accepts so the headless subprocess never blocks on a permission prompt — there's no terminal to answer one); **Bash is never granted**. The claude path uses real Claude Code `Edit`/`Write` — confined to the vault working dir (`cwd`) but **not** restricted to `.md`, so it's the broader-blast-radius path (git is the safety net). Edit defaults off everywhere; the Twin (also `claude`) is untouched (defaults `allow_write=False`). All 18 smoke tests pass; CLI flags verified; live claude write confirmed; no new deps.

**Planned / backlog**
- Click a card to open the note in the default editor
- Inline status toggle (mark complete without leaving the dashboard)
- Create new task/note from dashboard (writes a file with correct frontmatter)
- Group-by view (group by area or type instead of flat sorted list)
- Tag-based filtering beyond area (type, course, etc.)
- Persistent filter state (URL params or localStorage)
