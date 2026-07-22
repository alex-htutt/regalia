# AGENTS.md

Project-wide guidance lives in `CLAUDE.md` (root) and `dashboard/CLAUDE.md` (the app).
Read those first — this file only adds Cursor Cloud specific setup/run caveats.

## Cursor Cloud specific instructions

Regalia is a single Flask web app in `dashboard/` (browser mode is `app.py`; the
native desktop shell is `desktop.py`). The repo root doubles as the example vault.

- **Use `python3`, not `python`.** Only `python3`/`pip` are on PATH in this
  environment; the docs' `python app.py` / `python -m unittest …` commands must be
  invoked as `python3 …`.
- **Run the app (browser, dev):** from `dashboard/`, `python3 app.py` → serves on
  `http://localhost:5000` in Flask debug mode (hot-reloads `app.py` + templates).
  Set `REGALIA_UPDATE_CHECK=0` to skip the startup GitHub release check (avoids a
  network call on boot; the smoke suite already sets this).
- **Desktop shell (`desktop.py`) needs a GUI/WebKit** and does not work in this
  headless VM — use the browser path (`app.py`) for all dev/testing here.
- **Tests / trust floor:** from `dashboard/`, `python3 -m unittest discover -s tests`
  (stdlib `unittest`, no runner dep). There is **no separate linter/type-checker** —
  the smoke suite is the trust floor; run it before and after changes to
  `app.py`/`agent.py`/`router.py`.
- **Vault root defaults to the repo root.** The public skeleton has no
  task-frontmatter notes, so `/api/tasks` is empty out of the box. To exercise the
  task dashboard / create-project flow without polluting the repo, point the app at
  a scratch vault: `REGALIA_VAULT=/tmp/demo_vault python3 app.py`.
- **Everything beyond the core dashboard is optional and needs external
  credentials/CLIs** (Ollama for `fast`, Anthropic/OpenAI keys for `smart`/`openai`,
  the `codex`/`claude` CLIs for those tiers, Gmail/Outlook OAuth for the inbox).
  The core dashboard, task list, project scaffolding, and smoke suite all run with
  **no configuration at all**.
- **Tailwind** (`static/tailwind.css`) is prebuilt and committed; you only need the
  gitignored `tools/tailwindcss.exe` binary if you change Tailwind utility classes
  (see `dashboard/CLAUDE.md`). Not required to run or test the app.
