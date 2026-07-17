<p align="center">
  <img src="dashboard/Assets/Regalia_Icon.png" alt="Regalia" width="96">
</p>

<h1 align="center">Regalia</h1>

<p align="center"><b>A self-hosted, agentic workspace over an Obsidian vault.</b><br>
Your notes are the database. Local + cloud models do the work. Everything runs on your machine.</p>

---

Regalia is a single-user cockpit for a Markdown knowledge vault. It reads YAML frontmatter straight off your notes — no importer, no sync, no separate database — and turns the vault into a live task dashboard, a grounded chat surface, and a set of agents that do real work inside it.

## Features

- **Overview dashboard** — every note with frontmatter becomes a task: stat cards (active / overdue / complete), filters by status · area · course, live search, deadline highlighting.
- **Landing page** — an ASCII-dither WebGL hero with pinned scrollytelling that lands you in your recently-worked folders.
- **Chat, grounded in your vault** — multi-conversation chat that can search, open, and quote your actual notes; an opt-in ✏️ Edit mode lets it write them.
- **Three model tiers, one router** — `fast` (local Ollama, private and free), `smart` (Anthropic API), `claude` (Claude Code CLI, billed to your Claude subscription instead of API credits). Pick per conversation, per agent.
- **Agents** — a real tool-use loop with streamed steps: Daily Summarizer, Project Scaffolder, Research Agent, and Inbox Triage. Vault-confined, traversal-safe tools.
- **Inbox (drafts-only, by construction)** — connect Gmail and Outlook, read mail, and save drafts. There is deliberately **no send path anywhere in the codebase** — you review and send from your mail client.
- **Daily briefing** — tech-news RSS, a profile-ranked job board scan, and an important-mail panel on the home page.
- **Claude usage panel** — your Claude Code token usage (today / all-time / per-model, 14-day chart) read from local JSONL metadata. Message content is never read.
- **Desktop or browser** — `python app.py` for the browser, `python desktop.py` for a native window (pywebview).

## Quick start (from source)

```bash
git clone https://github.com/alex-htutt/work-vault.git regalia
cd regalia/dashboard
pip install -r requirements.txt
python app.py          # → http://localhost:5000
# or: python desktop.py  → native desktop window
```

The dashboard indexes the vault it lives inside (the repo root). Point Obsidian at the repo root to edit the same notes, or just start dropping `.md` files with the frontmatter schema (see [USAGE.md](USAGE.md)).

Downloadable installers (no Python required) are planned via GitHub Releases — see [RELEASE.md](RELEASE.md).

## Model tiers

| Tier | Backend | Needs | Billing |
|---|---|---|---|
| `fast` | Ollama (local) | `ollama pull llama3.2` | Free / private |
| `smart` | Anthropic API | `ANTHROPIC_API_KEY` | API credits |
| `claude` | Claude Code CLI | `claude` CLI signed in to a Claude subscription | Your subscription |

Every model call goes through `dashboard/router.py`; adding a backend is one more branch there.

## Configuration

Copy `.env.example` and set what you use — every knob is documented there. Nothing is required for the core dashboard; tiers and the inbox light up as you configure them. Email OAuth tokens, chat transcripts, and attachments live in gitignored per-machine stores.

## Privacy stance

- Runs entirely on localhost; no telemetry, no cloud storage.
- The Claude usage panel reads token *counts* only — never message content.
- Email is read + draft only; the Microsoft Graph token is requested **without** `Mail.Send`, the Gmail send endpoint is never called, and no send function exists. Smoke tests assert all three.
- Secrets stay out of the repo: OAuth client creds come from env, per-account tokens live in a gitignored store, and tests guard against tokens leaking into API responses.

## The vault

The repo doubles as a working example of the vault conventions Regalia expects: per-folder `_context_*.md` status files, a small frontmatter schema, a `category/subcategory` tag taxonomy, and note templates. Start at [Home.md](Home.md); day-to-day usage is in [USAGE.md](USAGE.md); structure and conventions in [README_HOME.md](README_HOME.md). Private areas (internships, coursework) are gitignored — only the skeleton is public.

## Development

```bash
cd dashboard
python -m unittest discover -s tests   # smoke suite — the trust floor; run before & after changes
```

Architecture notes live in `dashboard/CLAUDE.md`, the dense project snapshot in `dashboard/_context_dashboard.md`, the roadmap in `dashboard/PRODUCT_VISION.md`, and the full v1 → v1.23 feature log in `dashboard/VERSION_HISTORY.md`.

## License

[MIT](LICENSE)
