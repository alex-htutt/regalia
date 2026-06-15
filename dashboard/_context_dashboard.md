---
date: 2026-06-14
tags: [area/projects, type/reference]
status: active
topic: "Self-hosted agentic workspace built on the vault dashboard (Odysseus-inspired)"
deadline:
related: ["[[dashboard/PRODUCT_VISION.md]]"]
---

# Dashboard — Context

> Dense, manually maintained snapshot of the `dashboard/` project. Prime any chat with `@file dashboard/_context_dashboard.md`.
> Build/run details and agent rules live in [[dashboard/CLAUDE.md|CLAUDE.md]]; the vault-root `CLAUDE.md` holds the full v1.x feature log.

## Overall goal

Grow the Flask `dashboard/` from a read-only vault viewer into a **self-hosted, agentic workspace** — a personal cockpit that reads the vault, chats across local + cloud models, and runs agents against task notes. Borrow *architecture shapes* from **Odysseus** (https://github.com/pewdiepie-archdaemon/odysseus), not its code (AGPL, different stack). Single-user, personal tool; may ship to GitHub later, no pressure.

**Guiding decisions:**
- **Build solo (Path C):** keep extending Flask + vanilla JS. Do not fork or run Odysseus alongside.
- **Hybrid models (three tiers):** local Ollama = `fast` (cheap/private); Claude Code CLI = `claude` (subscription-billed, powers Chat + Twin); Anthropic API = `smart` (API-credit billed, powers the Agents view's tool use). See v1.6 below.
- **Vault is the database:** markdown + YAML frontmatter is the source of truth. Defer a vector DB until retrieval actually hurts. Skip Docker / auth / multi-user.

## Current state

- **Viewer (v1–v1.4):** task list from frontmatter, stat cards, filters, course pills, folder browser, Claude token-usage panel, desktop shell (`desktop.py`/pywebview). See vault-root `CLAUDE.md` for the feature log.
- **Stage 1 — cockpit shell ✅:** sidebar/views layout (Overview / Projects / Browse / Chat / Agents). Real `POST /api/project` (folder scaffold + frontmatter + Home.md link).
- **Stage 2 — model router ✅:** `router.py` exposes `chat(messages, tier, system=, max_tokens=, model=)` raising `RouterError(message, status)`. `tier="smart"`→Anthropic, `tier="fast"`→Ollama via stdlib `urllib` (no new deps). Twin now routes through `router.chat(tier="smart")`. New `GET /api/router/status` and `POST /api/chat`; new **Chat** view with a Fast/Smart toggle + live status dot.
- **Stage 3 — agent loop ✅ (v1.5, 2026-06-13):** the stub is gone — agents now run for real. `router.py` adds `chat_tools(messages, tools, tier, …)`: one normalized tool-use step (Anthropic native tool use; Ollama tool-calling via canonical→Ollama message/tool translation). New `agent.py` holds vault-confined, traversal-safe tools (`search_vault`, `read_note`, `list_notes`, `list_folder`, `write_note`, `create_project`), an `AGENTS` registry (Daily Summarizer / Project Scaffolder / Research Agent = system prompt + allowed tools + default tier), and `run_agent(agent_id, task, tier, emit, max_steps=8)` driving model→tools→results→repeat with a per-step `emit` event. `POST /api/agent/run` spawns a background-threaded run → returns `run_id`; `GET /api/agent/run/<id>` polls status + streamed steps (in-memory store, capped 50). The Agents view streams each step live and renders the final reply. Verified on **both** tiers (local llama3.2 genuinely called `list_notes` and produced a standup).
- **v1.6 (2026-06-14) — subscription-billed chat:** new `claude` router tier shells out to the Claude Code CLI (`claude -p --output-format json`, prompt piped via stdin) so **Chat** and **Evil Twin** run on your Claude subscription, **not** API credits. `router.py` adds `_claude_code_chat()` + `_claude_cli_path()` + `_flatten_conversation()`, a `claude` entry in `status()`, and the tier branch in `chat()`; the subprocess env strips `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` so it always uses subscription (OAuth) auth. Chat's cloud pill and the Twin default to this tier (pill relabeled "✨ Claude · plan"); `fast`/Ollama unchanged. The **Agents view stays on the `smart` API tier** — its loop needs native Anthropic `tool_use` blocks the CLI doesn't expose this way. Env knobs: `CLAUDE_CLI`, `CLAUDE_CLI_MODEL` (default = plan default), `CLAUDE_CLI_TIMEOUT`. No new Python deps. Verified end-to-end on Windows (`claude.cmd` via `shutil.which`, multi-turn context preserved); 18/18 smoke tests pass.
- **v1.8–v1.11 (2026-06-14):** home-page **daily briefing** (`/api/news` — tech RSS + Bluesky/blog feeds + Greenhouse/Lever jobs, stdlib-only, TTL-cached, sources in `news_sources.py`); **Hyperstudio dark redesign** (obsidian canvas, Amber Whisper accent, Inter/JetBrains type — `Assets/DESIGN.md`); **Tailwind v4** via the standalone CLI binary (first build step, CSS only — `static/tailwind.css`); **chat file attachments** (`POST /api/chat/upload`, per-tier handling).
- **v1.12–v1.14 (2026-06-14) — landing page + Regalia rebrand:** the app is now **Regalia** (branding only; on-disk path still `Work_Vault`/`VAULT_ROOT`). `/` opens on a full-viewport **ASCII-dither hero** (`static/ascii-dither-background.js`, the lone third-party JS, self-mounting, no deps) + a vanilla **parallax-scroll** section *above* the dashboard — scroll down lands in the overview. The parallax ("What should we work on?") lists recently-worked folders from new **`/api/recent-folders`** (notes grouped by project = first two path segments, ranked by newest mtime, top 6, `_rel_time()` human ago). Ambient amber **beams** (fixed SVG `.beams` waves) sit behind the dashboard; overview surfaces are translucent **liquid glass** (`--glass*` + `backdrop-filter`) so the beams blur through. Hero canvases pinned to `object-fit:fill` (cover broke the script's mouse→grid mapping + clipped the glow). All hand-edited `templates/index.html` CSS/JS; 18/18 smoke tests pass.
- **v1.15 (2026-06-14) — pinned scrollytelling + spotlight:** the landing was reworked from parallax-drift into **pinned scrollytelling** — one tall `.scrolly` track; the inner stage pins (`position:sticky`) while a single rAF driver (`window.__scrollyUpdate`) animates in place: title **"Regalia."** shrinks/fades → recent-folder tiles assemble (staggered) → release into the dashboard (static-stack fallback under reduced-motion / ≤640px). Added an Aceternity **Spotlight** port (amber `feGaussianBlur` ellipse, fades+scales in top-left). The ASCII asset workflow is now `Assets/ascii_js.js` → **`sync-ascii.bat`** → `static/ascii-dither-background.js` (served copy doesn't auto-update). 18/18 smoke tests pass.
- **v1.7 (2026-06-14) — vault-aware local chat:** the `fast` (Ollama) tier in **Chat** was blind — `/api/chat` called plain `router.chat()` with no tools, so the weak local model never saw the vault. It now gets the live vault structure injected into its system prompt. `app.py` adds `_vault_outline()` (a hard-capped 250-line indented folder+note tree, honoring `IGNORE_DIRS`/dotfile skips, read fresh per request) and `_vault_chat_system()` (preamble + outline + any caller system); `api_chat` applies them **only when `tier == "fast"`**. The model can now answer "what's in my vault / where does X live" grounded in real structure, and is told it can see the structure but **not** note contents (reading files is the cloud/agent path — `chat_tools`, not this). `smart`/`claude` tiers untouched (they read files themselves). No new deps; 18/18 smoke tests pass. This is the intended role of the local tier: cheap, private, vault-structure Q&A.

## Architecture (where things live)

- `app.py` — vault walk, frontmatter parsing, all routes (`/api/tasks`, `/browse`, `/recent-folders`, `/usage`, `/news`, `/project`, `/agents`, `/agent/run`, `/agent/run/<id>`, `/chat`, `/chat/upload`, `/router/status`, `/twin/chat`). Project scaffolding extracted into `create_project_core()` (shared by the route and the agent tool). Holds the in-memory agent-run store + background-thread runner, `_vault_outline()`/`_vault_chat_system()` (v1.7, fast-tier chat grounding), and `_rel_time()`/`api_recent_folders` (v1.14, landing parallax).
- `static/ascii-dither-background.js` — self-contained third-party ASCII-dither + WebGL hero background (copied from `Assets/ascii_js.js`); auto-mounts into `[data-ascii-dither-bg]`. Only third-party JS; no build, no deps.
- `router.py` — the model-routing primitive. Every model call goes through `chat()` / `chat_tools()`; new backends = one more branch here. Three tiers: `fast` (Ollama/urllib), `smart` (Anthropic SDK), `claude` (Claude Code CLI subprocess, subscription-billed). `chat_tools()` is `smart`/`fast` only — the CLI tier is plain-chat (no structured tool use).
- `agent.py` — the agent loop: vault tools (confined + traversal-safe), the `AGENTS` registry, and `run_agent()`. Imports `app` **lazily** (inside tool fns) to dodge a circular import (app imports agent at top).
- `templates/index.html` — single-page UI (inline CSS + vanilla JS), no build step. Agents view streams run steps via polling.
- `desktop.py` — pywebview native-window shell over the same Flask app.

## Active deliverable(s) / next steps

- **Stage 4 — automations (next):** scheduler (APScheduler in-process, or Windows Task Scheduler → endpoint) running agents on a cron, e.g. "every morning, summarize yesterday's daily-logs into a standup note." Reuses stages 2–3 (`run_agent`).
- **Stage 5 — memory/embeddings:** only if stage 3/4 agents start fumbling context. Then add a vector store. Not before.

## Open questions

- Which local model to standardize on for the `fast` tier (default is `llama3.2`, now installed and working)?
- ~~Agent run model~~ → resolved: background thread + `run_id` polling (`/api/agent/run` returns immediately, `/api/agent/run/<id>` streams steps).
- How much agent autonomy on `write_note` — currently **free rein** inside the vault (any `.md`, traversal-safe). Revisit a confirm-before-write gate when wiring stage 4 automations (unattended runs raise the stakes).

## Key resources

- **Ollama installed and working** (`fast` tier runs genuine local tool-using loops). Config via env: `OLLAMA_HOST`, `OLLAMA_MODEL` (default `llama3.2`), `ANTHROPIC_MODEL`.
- **`claude` tier** needs the Claude Code CLI installed and signed in to a Claude subscription (Pro/Max) — powers Chat + Twin, billed to the plan not API credits. Config via env: `CLAUDE_CLI` (default `claude`), `CLAUDE_CLI_MODEL` (default = plan default; the Twin pins `claude-opus-4-8`), `CLAUDE_CLI_TIMEOUT` (default 180s).
- **`smart` tier** needs `ANTHROPIC_API_KEY` in the environment (powers the Agents view's tool-using loop; API-credit billed). No longer used by the twin/chat after v1.6.
- Run: `python app.py` → http://localhost:5000 (or `start.bat`); desktop window via `desktop.py` / `desktop.bat`.

## Next deadline

- None — open-ended personal project, paced by interest.
