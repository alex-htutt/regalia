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

## Architecture (where things live)

- `app.py` — vault walk, frontmatter parsing, all routes (`/api/tasks`, `/browse`, `/usage`, `/project`, `/agents`, `/agent/run`, `/agent/run/<id>`, `/chat`, `/router/status`, `/twin/chat`). Project scaffolding extracted into `create_project_core()` (shared by the route and the agent tool). Holds the in-memory agent-run store + background-thread runner.
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
