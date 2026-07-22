# Dashboard — Unreleased Features (since the latest release)

**Purpose:** a running list of what has been added to the dashboard **since the
last cut release**, for other agents (and humans) to read so they know the
current state without diffing git. This is the staging ground for the *next*
release's notes.

**Baseline release:** **v1.31** (Windows installer + first-run onboarding wizard).
Everything below is on top of v1.31 and is **not yet in a released build**.

**When the next release is cut:** fold these entries into `VERSION_HISTORY.md`
under the new version heading, bump `version.py`, then clear this file back to an
empty template. Keep `VERSION_HISTORY.md` as the permanent log; this file only
ever describes the gap between the latest release and `main`/working tree.

---

## Agent Dispatch workspace
*Status: implemented in the working tree; not yet committed or released.*

The Agents tab now supports reusable custom agents, one-off quick dispatches,
and conversational group dispatches for larger work. Every dispatch requires a
**Fast / Balanced / Best** choice. Group planning asks for missing deliverables,
boundaries, and must-pass checks, then proposes an editable 2-8 worker DAG with
automatic complexity-based tier/model assignments and per-worker overrides. The
user reviews that plan before launch.

Dispatches and definitions persist in SQLite (`.dispatches.sqlite3`, ignored),
with durable event history and interrupted-run recovery. Workers can use vault,
generic code/file, approved-check, public-web, and inbox capabilities. Model
targets include local Ollama, Anthropic/OpenAI APIs, Claude Code subscription,
and the ChatGPT-account Codex CLI; launch validates that every assigned backend
is actually connected.

Filesystem writers run in `.dispatch_work/` isolation. Git scopes use detached
worktrees and binary patches; non-Git scopes use copied baselines with hash-based
conflict detection. Independent DAG nodes run concurrently, dependent workers
receive prior patches, and final integration stays review-only until Apply.
Email draft proposals use the same gate and are not saved to a mailbox before
Apply. Results include a synthesis plus each worker's detailed output, model,
status, files, and patch/draft preview. Fast runs allow more parallelism; Best
runs use stronger model suggestions, lower parallelism, and a second review.

New backend modules: `dispatches.py` (SQLite store), `dispatch_engine.py`
(planning/orchestration), and `dispatch_workspace.py` (isolation/integration).
New APIs: `/api/agent-definitions`, `/api/agent/models`, `/api/dispatches`,
dispatch messages/plan/events, and launch/resume/cancel/apply/discard actions.
The focused dispatch tests bring the suite to 145 passing tests (2 skipped).

---

## Automatic ChatGPT account-login detection
*Status: implemented in the working tree; not yet committed or released.*

The dashboard now distinguishes a usable **ChatGPT account login** from merely
having Codex installed. Opening Chat/Settings automatically runs the targeted
`codex login status` check when the cached result is missing or older than 30
seconds, and selecting the ChatGPT tier forces a fresh check. The result is
single-flight in the browser, so concurrent views do not spawn duplicate checks.

`router.py` exposes structured `auth_state`, `auth_reason`, and
`auth_checked_at` fields for the ChatGPT tier. Detection recognizes explicit
ChatGPT login, signed-out output, API-key/access-token login (not valid for the
account tier), timeout, unavailable CLI, and unknown CLI output. Unknown
successful output is treated conservatively instead of being assumed to mean a
ChatGPT login. A successful forced ChatGPT run also refreshes the same status
cache. The Chat tier status line renders these states directly and rechecks after
a terminal login without requiring an app restart.

---

## Per-conversation / per-run model selection for Claude & ChatGPT
*Status: implemented in the working tree; not yet committed or released.*

Chat conversations and Agents runs can now choose **which model** runs on the
account-CLI tiers — **Claude** and **ChatGPT/Codex**. Blank
= the plan/account default, i.e. today's behavior is unchanged unless the user
picks a model. Fast keeps its existing Ollama model picker; Smart/OpenAI keep the
Settings-configured model.

**What the user sees**
- **Chat:** a model box in the tier bar next to the tier pills. On the **Claude**
  tier it's a free-text input with `opus`/`sonnet`/`haiku` suggestions
  (placeholder "plan default"); on the **ChatGPT** tier a free-text input
  (placeholder "account default"). The choice is stored **per conversation and
  per tier** so switching tiers never crosses a model name between backends. It
  persists across reloads and is reflected in the tier-status line and the
  thinking label.
- **Agents:** each agent card shows a Claude model box, visible **only when that
  agent's tier dropdown is set to `claude`**.

**Design choice:** free-text inputs with a datalist of suggestions (not a fixed
dropdown) — consistent with the existing free-text model fields in Settings, and
it avoids hardcoding model lists that go stale. Empty always means "use the
default".

**Touch points**
- `router.py` — no change needed: `chat()`, `claude_code_chat_stream()`,
  `claude_code_stream()`, and the codex/claude chat paths already accepted a
  per-call `model` (falling back to `_claude_cli_model()` / `_codex_cli_model()`).
- `app.py`
  - `/api/chat` — the model override is now honored for tiers `fast`, `chatgpt`,
    and `claude` (was fast-only). Still **guarded**: Smart/OpenAI never receive a
    request model, so an Ollama model name can't reach Anthropic.
  - `/api/chat/stream` — reads `model` from the request and threads it into
    `_chat_stream_worker` (was hardcoded `None`). Claude-tier only path.
  - `/api/agent/run` — reads `model`, threads it through `_run_worker` →
    `agent.run_agent(model=…)`.
- `agent.py` — `run_agent()` gained a `model=""` param; the `claude` tier passes
  it to `_run_agent_claude(req_model=…)`, which forwards `model=req_model or None`
  to `router.claude_code_stream()`. (The param is named `req_model` because the
  function already has a local `model` var tracking the model the CLI reports as
  actually used — do not merge the two.)
- `templates/index.html`
  - Chat: per-conversation `cliModel {claude, chatgpt}` map (persisted via
    `saveChat`/loaded in `switchChat`; `chats.py` round-trips arbitrary chat
    fields, so no store schema change was needed). New `#cli-model` input +
    `#cli-model-list` datalist; `syncChatControls` shows the right control per
    tier; `setCliModel()` persists; `chatSendModel()` picks the model for the
    blocking `/api/chat` send (fast→Ollama, chatgpt→override); the stream send
    passes `model` for claude.
  - Agents: per-agent `#model-<id>` input + shared `#agent-model-list` datalist;
    `agentTierChanged()` toggles its visibility with the tier dropdown; `runAgent`
    includes `model` in the payload.

**Verification:** 131 smoke tests pass; rendered inline JS passes `node --check`;
model thread-through was checked end-to-end by stubbing the router (chatgpt→model
forwarded, smart→guarded to None, claude chat-stream and claude agent→model
forwarded, no-override→None).

---

## Accent-colored hyperlinks + Aceternity-style dropdowns (all selects)
*Status: implemented in the working tree; not yet committed or released.*

Two visual upgrades, both confined to `templates/index.html` (hand-written CSS/JS
only — no Tailwind rebuild, no backend change).

**Accent hyperlinks.** Link text now follows the user's Regalia accent color
instead of fixed palette colors: markdown-rendered links (`.md a`, was
`--blue-fg`) and all Settings links (new `.bento-card a` rule — install links,
OAuth setup links, release notes, external-folder "context") use `var(--amber)`,
which the Settings accent picker overrides at boot and on save. Default stays
amber `#e7c59a` (dark) / `#a06a24` (light).

**Dropdowns.** Every native `<select>` is upgraded to a vanilla port of
[Aceternity's navbar-menu](https://aceternity.sveltekit.io/components/navbar-menu)
dropdown — same approach as the Spotlight port, since the app has no JS
framework. Look: frosted-glass panel (`--glass-elev` + `--glass-blur`
backdrop-blur, `--glass-border` hairline, 16px radius, deep shadow), selected
option in the accent, muted→text hover. Motion: the svelte-motion spring
(mass .5, damping 11.5, stiffness 100) approximated with an overshoot
`cubic-bezier(0.34, 1.56, 0.64, 1)` on opacity/scale; chevron rotates;
reduced-motion fallback.

**How it stays compatible** (`acxEnhance()` IIFE at the end of the boot script +
the `.acx-*` CSS block):
- The native select **stays in the DOM**, hidden (`.acx-native`) but fully
  functional — all existing `getElementById(...).value` reads/writes, inline
  `onchange` handlers, and option repopulation keep working untouched. The
  trigger button + fixed-position panel replace only the presentation.
- Sync back from app code: an instance-level `value` setter interceptor (catches
  programmatic writes, e.g. settings load) + a per-select MutationObserver
  (disabled/`display` toggles, option repopulation).
- A document-level MutationObserver auto-enhances selects added by re-renders
  (agent cards, inbox accounts, Ollama models) — nothing to call per render.
- Panel is viewport-clamped and flips upward near the bottom edge; closes on
  outside click / scroll / resize; Esc + arrow-key navigation.
- Triggers inherit each spot's native-select styling (the `.np-form` /
  `.bento-card` / `.inbox-bar` selector lists were extended to `.acx-trigger`).

**Covers:** Settings Theme + default-tier, Chat local-model picker, Inbox
account, Projects Area, and the per-agent tier / preset / folder selects.
Free-text model inputs (datalist-backed) are deliberately not converted.

**Verification:** exercised live in the browser — Settings and agent-card panels
open with the glass look and synced labels; Projects Area confirmed the inline
`onchange` fires (choosing "New area…" revealed the new-area field); dynamic
population and in-panel scrolling work; no console errors. Known pre-existing
quirk (not a regression): claude-tier agent cards' top row (title + tier select
+ model input) was already wider than narrow cards before this change.

---

## CI: workflow actions bumped to latest majors
*Status: committed on `main` (`fe6f7a6`); infra only, not user-facing.*

`.github/workflows/release.yml` and `tests.yml` moved to the current action
majors (all on Node 24), clearing the Node 20 deprecation warnings:
`actions/checkout` v4→v7, `setup-python` v5→v7, `upload-artifact` v4→v7,
`download-artifact` v4→v8, `softprops/action-gh-release` v2→v3. All inputs the
workflows use are unchanged in the new majors. Validated via a `workflow_dispatch`
run of `release.yml` (build jobs green; `publish` skipped since it's gated on a
`v*` tag).

---

## Home-centered vault graph browser
*Status: implemented on `main`; not yet released.*

Browse is now a read-only vault map instead of a top-level card gallery. The
main surface is an organic force graph rooted at the actual `Home.md`; folder
containment forms the dependable branching skeleton, while wikilinks and local
Markdown links appear as a subtler second edge type. The initial view shows
Home plus top-level branches and progressively reveals children as folders are
selected, avoiding an unreadable all-at-once graph.

A dedicated right rail shows the complete eligible folder/file hierarchy,
including non-Markdown files, with folders first, search, synchronized
selection, and responsive drawer behavior. A floating inspector provides
metadata plus bounded read-only text/Markdown previews and safe raster-image
thumbnails. It has no editing, rename, delete, or external-open path.

New read-only APIs are `GET /api/vault-map` and
`GET /api/vault-preview?path=...`. Both retain the existing hidden/cache/app
exclusions and traversal confinement; previews only serve approved text and
raster-image types. D3 7.9.0 is pinned locally so the graph remains offline.
`GET /api/vault-activity` now overlays live classic-agent and dispatch-worker
activity on that map. Running scopes and actively edited files use the user's
accent color in both graph and tree; bottom-left provider badges distinguish
Anthropic and OpenAI work, while local Ollama work uses an unbranded accent dot.
The poll is read-only and exact edit paths remain vault-confined.

Folder nodes now use open/closed folder icons and toggle their branch directly
when clicked; file nodes retain the read-only inspector. The graph and right
file tree share one expansion state, so opening or collapsing a folder in
either surface immediately updates the other. The mapping overlay now truly
hides after load (its authored CSS previously overrode the HTML `hidden`
attribute), and a stalled map request times out with an actionable message.
