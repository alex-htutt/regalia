# Dashboard — Agent Rules

## Context
Local Flask web app that reads vault frontmatter and surfaces notes as a task dashboard.

Two ways to run the **same** app:
- **Browser:** `python app.py` (or `start.bat`) → `http://localhost:5000`.
- **Desktop window:** `python desktop.py` (or `desktop.bat`) → native pywebview window wrapping the Flask app on an OS-assigned port. Same code, same UI; just a different shell. External (http/https) links open in the system browser instead of inside the window.

## Stack
- Backend: Python / Flask (`app.py`)
- Model router: `router.py` — `chat(messages, tier)` and `chat_tools(messages, tools, tier)` over three backends: `fast`=Ollama local, `smart`=Anthropic cloud API (API-credit billed; used by the Agents view for tool use), `claude`=Claude Code CLI subprocess (bills your Claude subscription, not API credits; used by Chat + Twin). Every model call goes through here. The `claude` backend strips `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` from the subprocess env so it always uses subscription (OAuth) auth, never API billing.
- Agent loop: `agent.py` — vault tools + `AGENTS` registry + `run_agent()`; drives the model→tools→results cycle for the Agents view. Imports `app` lazily (inside tool fns) to avoid a circular import.
- Frontend: vanilla JS + HTML in `templates/`
- Desktop shell: `desktop.py` (pywebview) — runs Flask in a daemon thread, opens a native window. No effect on the browser path.
- Data source: walks `VAULT_ROOT` (parent of this folder), parses YAML frontmatter
- API: `/api/tasks`, `/api/browse`, `/api/usage`, `/api/chat`, `/api/router/status`, `/api/project`, `/api/twin/chat`, `/api/agents`, `/api/agent/run` (POST → run_id), `/api/agent/run/<id>` (poll)

## Behavior in this folder

**Read `app.py` first** before suggesting any change — the vault walk, ignore lists, and frontmatter parsing are tightly coupled. Breaking the walk silently breaks everything.

**No new dependencies** without asking. The install footprint should stay minimal (Flask, PyYAML, anthropic, pywebview, and stdlib). `pywebview` is only needed for the desktop window — the browser path (`app.py`) still runs on Flask + PyYAML + stdlib alone.

**Frontend changes:** Edit files in `templates/`. The app serves them directly — no build step. Test in-browser after any JS or CSS change.

**Privacy:** `app.py` reads token usage from `~/.claude/projects/**/*.jsonl` but intentionally skips message content. Don't add any code that reads or logs message content.

**Version history matters:** See CLAUDE.md at vault root for the v1 / v1.1 / v1.2 / v1.3 feature log. Check it before adding features that might already exist.

**Dev server:** `python app.py` — Flask runs in debug mode. Changes to `app.py` hot-reload automatically; template changes do too.

**Tests:** `python -m unittest discover -s tests` (from this folder). Stdlib `unittest` only — no test-runner dependency. The smoke suite (`tests/test_smoke.py`) covers read-endpoint 200s + JSON shape and agent-tool / browser path-traversal safety. Run it before and after any change to `app.py`, `agent.py`, or `router.py`; it's the trust floor for the Stage-4 unattended automation (see `PRODUCT_VISION.md`).
