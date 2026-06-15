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
- Fast-tier chat grounding (v1.7): `/api/chat` injects the live vault structure (`_vault_outline()` → `_vault_chat_system()` in `app.py`) into the system prompt **only for `tier == "fast"`** — the local model can see the vault's folder/file layout but not note contents (reading files is the agent/`chat_tools` path). `smart`/`claude` tiers are untouched.
- Frontend: a **single** `templates/index.html` — all markup, the hand-written CSS, and vanilla JS in one file, no JS framework. The whole UI (landing hero + parallax, task list, folder gallery, usage panel, chat, twin, agents view) is client-side rendering against the JSON endpoints. CSS is the hand-written `<style>` block plus a compiled Tailwind utility sheet (see Tailwind below). The product name is **Regalia** (v1.14); the on-disk folder is still `Work_Vault` / `VAULT_ROOT` — don't rename the path (it's wired into git, the vault walk, and the Claude memory store).
- Landing page (v1.13, reworked v1.15): the top of `index.html` is a **pinned-scrollytelling** stage *above* the dashboard — scroll down lands in the overview (`#dashboard`). One tall `.scrolly` track; the inner `.scrolly-stage` pins (`position: sticky`) while a single rAF scroll driver (`window.__scrollyUpdate`) animates in place: title "Regalia." shrinks/fades → "What should we work on?" heading + recent-folder tiles assemble (staggered) → release into the dashboard. Bails to a static stack under reduced-motion / ≤640px (CSS authoritative). The hero background is a self-contained third-party effect, `static/ascii-dither-background.js` (**a copy of `Assets/ascii_js.js`** — re-sync with `sync-ascii.bat` after re-export; auto-mounts into `[data-ascii-dither-bg]`), the only third-party JS, no build/deps. An Aceternity **Spotlight** port (amber `feGaussianBlur` ellipse) fades in above the ASCII bg / below the title. The parallax columns are populated from `/api/recent-folders`. Beams/glass: a fixed `.beams` SVG waves layer (`z-index:0`) sits behind the dashboard; overview surfaces are translucent `--glass*` so they blur it through. Hero canvases are pinned to `object-fit:fill` (NOT cover — cover offsets the script's linear mouse→grid mapping and clips the glow on resize).
- Desktop shell: `desktop.py` (pywebview) — runs Flask in a daemon thread, opens a native window. No effect on the browser path.
- Data source: walks `VAULT_ROOT` (parent of this folder), parses YAML frontmatter
- API: `/api/tasks`, `/api/browse`, `/api/recent-folders` (recently-worked folders for the landing parallax), `/api/usage`, `/api/news` (daily briefing; `?refresh=1` forces refetch), `/api/chat`, `/api/chat/upload`, `/api/router/status`, `/api/ollama/models`, `/api/project`, `/api/twin/chat`, `/api/agents`, `/api/agent/run` (POST → run_id), `/api/agent/run/<id>` (poll)
- Briefing (v1.8): `/api/news` aggregates tech-news RSS + Bluesky/blog feeds + Greenhouse/Lever job postings, all stdlib-only (`urllib`+`xml.etree`+`json`), held in an in-process TTL cache (`NEWS_TTL`, default 30 min). Sources live in `news_sources.py`. Per-source failures degrade gracefully (collected in `errors`), never 500.

## Behavior in this folder

**Read `app.py` first** before suggesting any change — the vault walk, ignore lists, and frontmatter parsing are tightly coupled. Breaking the walk silently breaks everything.

**No new dependencies** without asking. The Python footprint should stay minimal (Flask, PyYAML, anthropic, pywebview, and stdlib). `pywebview` is only needed for the desktop window — the browser path (`app.py`) still runs on Flask + PyYAML + stdlib alone. The Tailwind toolchain (below) adds **no Python dep** — it's a single standalone binary, not a `pip`/`npm` package.

**Frontend changes:** Markup and the hand-written CSS/JS live in the one `templates/index.html`, served directly. There is now **one build artifact**: `static/tailwind.css` (compiled from `tailwind.input.css`). If you add/change Tailwind utility classes in the markup, rebuild it (see Tailwind). Editing only the hand-written `<style>` block or the JS needs no rebuild. Test in-browser after any change.

**ASCII hero asset:** `static/ascii-dither-background.js` is a **copy** of `Assets/ascii_js.js` (the served artifact) — it does **not** auto-update. After re-exporting the ASCII art, run **`sync-ascii.bat`** (copies Assets → static) and hard-refresh. As long as the export keeps the `data-ascii-dither-bg` mount, no HTML/CSS changes are needed.

## Tailwind (compiled, standalone CLI)

Tailwind v4 is compiled by the **standalone CLI binary** (`tools/tailwindcss.exe`, ~108MB) — no Node, no `npm`, no `node_modules`. The binary is **gitignored**; re-fetch it with `get-tailwind.bat`.

- **Input:** `tailwind.input.css` — imports the theme + utilities layers, our Hyperstudio design tokens as a v4 `@theme` (so `bg-obsidian-canvas`, `text-frost-text`, `text-amber-whisper`, `rounded-cards`, `font-aeonik`, … exist), and `@source "./templates/**/*.html"` for purge.
- **Output:** `static/tailwind.css` (committed, ~5KB minified; Flask serves it; linked in `index.html` *before* the hand-written `<style>`).
- **Build:** `build-css.bat` (one-off, minified) or `watch-css.bat` (live rebuild while editing markup). Manual: `tools\tailwindcss.exe -i tailwind.input.css -o static\tailwind.css --minify`.
- **Preflight is intentionally NOT imported** — Tailwind's base reset would break the hand-written UI (e.g. markdown list bullets). We pull in only `theme` + `utilities`.
- **Cascade:** utilities live in `@layer utilities`; the page's existing `<style>` is **unlayered**, so unlayered rules always win. This means Tailwind cannot regress the existing look, and utilities apply cleanly to **new/pasted** markup. To override an existing styled element with a utility, use the important modifier (`bg-red-500!`).
- **Workflow gotcha:** purge is content-driven — a utility class only lands in `static/tailwind.css` if it appears in a scanned template (or the `@source inline(...)` safelist in `tailwind.input.css`). Add classes → rebuild → hard-refresh. A class that "does nothing" usually means you forgot to rebuild.
- **Template-literal gotcha (bit us once):** the UI is rendered with JS template strings, so a class glued directly to a `${...}` interpolation is invisible to Tailwind's scanner — `leading-[1]${warn?...}` won't compile the `leading-[1]`. Always leave a space before the interpolation: `... leading-[1] ${warn ? 'text-overdue' : ''}`. Conditional classes inside the `${}` must be plain, space-bounded literals so they're statically detectable.
- **Converted so far:** the overview stat cards (`#stats` container + the cards built in `render()`) are pure Tailwind utilities (the old `.stat`/`.stats` CSS was deleted) — use them as the reference pattern for converting other panels. Everything else is still hand-written CSS.

**Tier gotcha — three tiers, but not everywhere:** `chat()` supports `fast`/`smart`/`claude`, but the **Agents view (`/api/agent/run`) only accepts `fast` or `smart`** — it silently coerces anything else, because `run_agent()` → `chat_tools()` needs native tool use, which the `claude` CLI backend doesn't expose. Default tiers per surface: Chat → `fast` (cloud button switches to `claude`), Twin → `claude`, Agents → each agent's own default (`fast`/`smart` per the registry). Don't route the Agents loop through `claude`.

**Circular import:** `app.py` imports `agent` at top; `agent.py` imports `app` **lazily inside tool functions** to break the cycle. Keep agent's module-level imports to stdlib + `router`.

**Privacy:** `app.py` reads token usage from `~/.claude/projects/**/*.jsonl` but intentionally skips message content. Don't add any code that reads or logs message content.

**Version history matters:** See CLAUDE.md at vault root for the v1 / v1.1 / v1.2 / v1.3 feature log. Check it before adding features that might already exist.

**Dev server:** `python app.py` — Flask runs in debug mode. Changes to `app.py` hot-reload automatically; template changes do too.

**Tests:** `python -m unittest discover -s tests` (from this folder). Stdlib `unittest` only — no test-runner dependency. The smoke suite (`tests/test_smoke.py`) covers read-endpoint 200s + JSON shape and agent-tool / browser path-traversal safety. Run it before and after any change to `app.py`, `agent.py`, or `router.py`; it's the trust floor for the Stage-4 unattended automation (see `PRODUCT_VISION.md`).
