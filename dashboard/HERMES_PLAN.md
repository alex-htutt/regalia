---
date: 2026-06-27
tags: [area/projects, type/project]
status: active
topic: "Switch Inbox Triage + Research agents onto the Hermes agent runtime (account-token auth)"
deadline:
related: ["[[dashboard/_context_dashboard.md]]", "[[dashboard/PRODUCT_VISION.md]]", "[[dashboard/CLAUDE.md]]"]
---

# Hermes Agent-Runtime Switch — Build Plan

> Macro + micro plan (per the vault planning rule) for routing the **Inbox Triage** and
> **Research** agents onto **Hermes** (Nous Research, github.com/NousResearch/hermes-agent, MIT),
> and moving **inbox retrieval** off the Google/Graph APIs onto Hermes's email skills.
> Decision record + context lives in [[dashboard/_context_dashboard.md]]; this is the build blueprint.

---

## MACRO PLAN — *what & why*

**Goal.** Run two of the dashboard's agents on the **Hermes** agent runtime instead of the
in-process Anthropic-API loop, and route **all email retrieval** (for both the Inbox UI and the
triage agent) through Hermes's email skills rather than direct Gmail-API / Microsoft-Graph calls.

**Why.**
- **Account tokens, not API cost.** Hermes runs on the **Nous Portal** (`hermes setup --portal`,
  `--provider nous`) — subscription credits, no per-request API keys. Matches the `claude` tier's
  billing model.
- **Avoid the Google API + Azure dynamics** (user's stated reason). Moving retrieval to Hermes
  removes the Google Cloud "Desktop app" client secret, the Azure app registration, the
  `GMAIL_OAUTH_CLIENT` / `MS_OAUTH_CLIENT_ID` / `MS_OAUTH_TENANT` env, and the
  `google-auth-oauthlib` + `msal` deps. One `hermes setup` email connection replaces all of it.
- **More capability.** Hermes brings web research (Firecrawl), a browser, and Gmail/Outlook email
  skills under one runtime + one auth.

**Scope.**
- *In:* a new `hermes` router tier; a Hermes agent runner in `agent.py`; routing `researcher` and
  `inbox_triage` to it; swapping `mailbox.py`'s **provider internals** to a Hermes-backed
  retrieval; a **send-after-review** path (human gate + deterministic lint); docs + smoke tests.
- *Out:* `router.py`'s fast/smart/claude tiers; the vault tools; the Inbox **UI shell** (kept);
  the scheduler / unattended automation (later stage).

**Governing constraints.**
- **`mailbox.py` keeps its UI contract** — the `/api/inboxes`, `/api/inbox/<id>`, `/api/email/...`
  routes and the message dict shapes the Inbox view renders are frozen; only the retrieval guts
  change underneath.
- **Send-after-review.** Agent drafts → human **Review & Send** in the UI → deterministic pre-send
  lint (recipients present, no leftover placeholder/`[TODO]` text, warn on reply-all / empty
  subject). **No reviewer agent** (reserve only for future unattended cron sends).
- **Tool bypass accepted** — Hermes uses its own tools, like the `claude` tier.
- Smoke suite stays green; no secrets logged.

**Milestones.** M0 spike ✅ → M1 `hermes` router tier → M2 Hermes agent runner + route the two
agents → M3 `mailbox.py` retrieval → Hermes (UI unchanged) → M4 send-after-review (lint + button)
→ M5 docs + tests + dep cleanup.

---

## MICRO PLAN — *how (components & build order)*

### Verified in M0 (step-0 spike)
- **Identity/license:** Hermes = Nous Research agent CLI, Python 3.11, MIT.
- **Headless seam:** `hermes -z "<task>"` prints **only** the final reply to stdout (clean capture);
  per-run override via `--provider` / `--model` or `HERMES_INFERENCE_MODEL`.
- **Auth:** `hermes setup --portal` + `--provider nous` → Portal subscription credits, no API keys.
- **Email retrieval is structured JSON** (Google Workspace skill):
  - `$GAPI gmail search "is:unread" --max 10` → JSON `{id, threadId, from, to, subject, date, snippet, labels}`
  - `$GAPI gmail get <id>` → adds `body`
  - `$GAPI gmail reply <id> --body "..."` → `{status, id, threadId}`, auto-threads
  - Outlook/others via the **Himalaya** IMAP/SMTP skill.
  - **Note:** the skill exposes `reply`/`send`, not a server-side draft object — fine: the "draft"
    is the pending reply text held in the dashboard UI until the human clicks **Send**, which then
    calls `$GAPI gmail reply`. The lint runs immediately before that send call.

### Component 1 — `hermes` router tier (`router.py`)  ← FIRST BUILD
Mirror the `claude` CLI tier.
- Env: `HERMES_CLI` (default `hermes`), `HERMES_PROVIDER` (default `nous`), `HERMES_MODEL`
  (default `""` = provider default), `HERMES_TIMEOUT` (default 180).
- `_hermes_cli_path()` → `shutil.which(HERMES_CLI)`.
- `_hermes_chat(messages, system, max_tokens, model)` → subprocess `hermes -z <prompt>
  --provider <p> [--model <m>]`, capture stdout as the reply; raise `RouterError` (503 not
  installed / 504 timeout / 502 failure) like the claude tier.
- Wire-up: add `"hermes"` to `TIERS`, a branch in `chat()`, and a `status()` entry
  (`available = _hermes_cli_path() is not None`).

### Component 2 — Hermes agent runner (`agent.py`)
- `_run_agent_hermes(spec, task, emit)` mirroring `_run_agent_claude`: drive `hermes -z` (or a
  streamed mode if available), map output → the `start/think/tool/final` step vocab.
- `run_agent()` routes `tier == "hermes"` here (as it does for `claude`).
- Route the `researcher` and `inbox_triage` specs' default tier → `hermes`.

### Component 3 — `mailbox.py` retrieval → Hermes (UI unchanged)
- Keep public fns + shapes: `accounts_overview`, `fetch_inbox`, `search_messages`, `read_message`.
- Replace `_gmail_*` / `_graph_*` / `_api` / token layer with a Hermes call: run
  `$GAPI gmail search/get` (Gmail) or Himalaya (Outlook/IMAP) via the `hermes` tier, parse the
  returned JSON, map to the existing message dicts (derive `unread` from `labels`).
- Retire `GMAIL_OAUTH_CLIENT` / `MS_OAUTH_*`, `google-auth-oauthlib`, `msal`, `.email_tokens/`,
  and `connect_email.py` once Hermes is the sole email path.

### Component 4 — Send-after-review (`mailbox.py` + Inbox UI)
- New `send_reply(account_id, msg_id, body)` → `$GAPI gmail reply` via Hermes; only called after
  the human clicks **Send**.
- `lint_outgoing(draft) -> [warnings]` — pure, deterministic; runs before send.
- Inbox view: show the agent's proposed reply with a **Review & Send** button + surfaced lint
  warnings.

### Component 5 — Docs + tests + dep cleanup
- Smoke tests: `hermes` tier in `router.status()`; mock the Hermes subprocess at the
  `_hermes_chat` seam for retrieval-shape + lint tests.
- Update `dashboard/CLAUDE.md` (tiers, deps), `_context_dashboard.md`, `PRODUCT_VISION.md`.
- Drop the retired email deps from `requirements.txt`.

### Build order (each step shippable)
0. **M0 spike** ✅ (this doc's "Verified" section).
1. **`hermes` router tier** + `status()` ✅ (`router.py`: `TIERS`, `_hermes_chat`, `status()`).
2. Hermes agent runner ✅ (`agent.py: _run_agent_hermes`); `researcher` ✅ **and** `inbox_triage` ✅
   now default to `hermes` (the triage prompt forbids send/reply skills — sending waits for step 4).
3. `mailbox.py` retrieval → Hermes behind the frozen UI shapes. ← *in progress*
   - **Done:** backend selector `email_sources.MAILBOX_BACKEND` (`api` default | `hermes`); the
     Hermes provider in `mailbox.py` (`_extract_json`, `_hermes_msg`, `_hermes_skill`,
     `_hermes_list/_hermes_read`, `_hermes_account`); `fetch_inbox` / `read_message` /
     `search_messages` / `list_accounts` / `accounts_overview` branch on the flag (default path
     untouched); 10 smoke tests over the mappers + routing (mock the `_hermes_skill` seam).
   - **Left:** verify `$GAPI` returns raw JSON from a live `hermes -z` (the open risk); real unread
     counts under the `hermes` backend; then retire the OAuth path + deps (folds into step 5).
4. Send-after-review (lint + button) for `inbox_triage`.
5. Docs + dep cleanup.

### Open risks / to-verify during build
- **Invoking `$GAPI` deterministically** — confirm the dashboard can get raw skill JSON out of
  Hermes (a direct skill-passthrough, or a `-z` prompt that returns only the JSON) rather than
  scraping prose.
- **argv length** — `hermes -z "<prompt>"` is positional; large prompts may need a stdin/file path
  on Windows (~32k argv cap). Check for a stdin mode.
- **Outlook** path via Himalaya needs its own one-time IMAP/SMTP credential setup.
- Hermes prerequisites (Python 3.11, `uv`, ripgrep, etc.) must be installed alongside the app.

---

## Sources
- Hermes site / install: https://hermes-agent.nousresearch.com/
- Hermes repo (MIT): https://github.com/NousResearch/hermes-agent
- Hermes CLI reference (`-z`, `chat -q`, `--provider`): https://hermes-agent.nousresearch.com/docs/reference/cli-commands
- Gmail skill JSON output: https://hermes-agent.nousresearch.com/docs/user-guide/skills/google-workspace
- Himalaya (IMAP/SMTP) skill: https://hermes-agent.nousresearch.com/docs/user-guide/skills/bundled/email/email-himalaya
