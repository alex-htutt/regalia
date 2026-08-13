# Regalia — UI Micro-Standards

**For:** any agent adding or changing UI in `dashboard/templates/index.html`.

**Where it sits:** `CLAUDE.md` = architecture. `Assets/DESIGN.md` = the Hyperstudio
visual language. **This file = the micro layer** — what to reuse instead of rolling
your own. Before writing a component, search here, then search `index.html` for
something that already does it.

Regalia is *one* ~7,000-line template with a hand-written stylesheet and no
component framework. Nothing structurally stops new markup from inventing a second
dropdown, a second breakpoint, or a second blue — hence these rules.

Each rule carries a **why**, usually the bug that caused it. If a rule blocks what
the task genuinely needs, the why tells you whether you're hitting the intent or
just the letter — then say so in your summary rather than diverging silently.

---

## 0. The seven violated most

1. Links use the accent, never UA blue → §1.2
2. Write a plain `<select>`; never hand-roll a dropdown → §2.1
3. Flex rows wrap, they don't squeeze (`min-width: 0` is a loaded gun) → §3.2
4. Card grids use `minmax(min(100%, Npx), 1fr)`, not media queries → §3.1
5. Every interpolated value goes through `esc()` → §6.1
6. No paragraphs of explanatory prose in the UI → §7
7. Vault-reading UI stays live; no expensive endpoint on a timer → §8

---

## 1. Color

### 1.1 Use tokens. Never a raw hex in a component rule.

Both themes define the *same token names* (`:root` and `:root[data-theme="light"]`,
top of the `<style>` block), so a token-only component follows the light theme for
free. A raw hex doesn't — and the light theme is where it surfaces as black-on-black.

| Token | Use for |
|---|---|
| `--bg` | page canvas; also the inset background of inputs/textareas |
| `--surface` | card / panel background |
| `--elevated` | hover + raised surface |
| `--border` / `--border-hover` | hairlines; `-hover` doubles as the focus border |
| `--text` / `--muted` / `--faint` | primary copy / secondary copy / captions + timestamps |
| `--accent` / `--accent-fg` | **high-emphasis fills** — the white (dark) or near-black (light) button. *Not a chromatic color.* |
| `--amber` / `--amber-fg` | the **sole chromatic accent**. `--amber` for fills/borders, `--amber-fg` for text |
| `--red` / `--green` | overdue signal / status dot. Not decoration |
| `--*-bg` / `--*-fg` pairs | tag chips only (`--blue-*`, `--green-*`, `--purple-*`, `--amber-*`, `--gray-*`) |

- **Accent economy is a constraint, not a preference.** A component that "needs" a
  second chromatic color usually needs hierarchy (weight, size, `--muted`) instead.
- **`--amber` vs `--amber-fg`:** identical values today, different jobs — use `-fg`
  where the amber is *text*, so call sites are already correct if the pair diverges.
- **Accent is user-configurable.** The boot script repoints `--amber*` at the user's
  Settings → Appearance choice. Hard-coding `#e7c59a` pins one user's pick.

### 1.2 Links

A base rule already exists — **just write `<a href="…">`**, no per-component color:

```css
a { color: var(--amber-fg); text-decoration: none; }
a:hover { text-decoration: underline; }
a:focus-visible { outline: 2px solid var(--amber-fg); outline-offset: 2px; border-radius: 3px; }
```

*Why:* there was no base `a` rule for a long time, so anchors across the briefing
footer, Connections help, release notes, and chat markdown all rendered
browser-blue. It got patched as `.bento-card a {…}` — fixing one panel and hiding
the real problem. One base rule, no local copies.

Override only when a link genuinely isn't accent-colored (`.news-item a` is a
headline, so `--text` → `--purple-fg` on hover). Specificity wins; no `!important`.

External: `target="_blank" rel="noopener"`. In-app: `<a href="#" onclick="setView('settings'); return false;">`.

---

## 2. Use the components that exist

### 2.1 Dropdowns — write a native `<select>` and stop

**Never construct the custom dropdown** (the `.acx-*` Aceternity port). An IIFE runs
`acxEnhance()` over every `<select>`, and a `MutationObserver` on `document.body`
catches selects added by later re-renders. The native select stays in the DOM
(hidden, `tabIndex -1`); a trigger button + floating panel replace only presentation.

```html
<select id="tier-x" class="agent-tier-select" title="Which backend runs this agent"
        onchange="somethingChanged('x')">
  <option value="fast">⚡ fast · local</option>
</select>
```

Hand-rolling silently breaks: `.value` reads **and writes** (an interceptor re-syncs
the trigger on assignment), inline `onchange`, label re-sync when you repopulate
`<option>`s or toggle `disabled`/`display`, the `title` → trigger copy, and
`type="button"` (so it can sit in `.np-form` without submitting).

**Consequence:** the visible control is `.acx-trigger`, a *sibling* — the select
itself is ~1px wide, so it's the trigger you measure and lay out. Style the trigger
alongside the select in selector lists (as `.np-form input, …, .np-form .acx-trigger`
already does), and use `:focus-visible` on it since it's a button.

### 2.2 The rest of the kit

| Need | Use | Notes |
|---|---|---|
| Secondary / toggle button | `.pill` | `.pill.on` active, `.pill.compact` dense |
| Primary submit | `.np-submit` | fills with `--accent` |
| Form panel | `.np-form` + `.np-row` + `<label>` | uppercase micro-label; control goes inside the label |
| Settings card | `.bento-card` (+ `.bento-head`/`-title`/`-sub`/`-body`) | |
| Inline status | `.np-msg` + `.ok`/`.err` | already `--green-fg`/`--red`; give it an id, set `textContent` |
| Empty state | `.empty-sm` | `--faint`, 12.5px — every list has one |
| Section label | `.activity-head` / `.proj-list-head` | uppercase, `--muted`, 11px |
| Tag chip | `.tag` + `.a0`/`.a1`/`.a2`/`.course` | uses the `--*-bg`/`--*-fg` pairs |
| Glass surface | `.glass` | see §5 |

Field styling in `.np-form` / `.bento-card` / `.dispatch-form` / `.inbox-bar` is
defined for `input, select, textarea, .acx-trigger` as a group — put your field in
one of those and it inherits. Adding a *new* container? Extend those selector lists
rather than writing fresh field rules.

---

## 3. Scaling and layout

No JS layout code and almost no breakpoints. Both deliberate.

### 3.1 Card grids: one idiom

```css
grid-template-columns: repeat(auto-fill, minmax(min(100%, 258px), 1fr));
```

Used by `.agent-grid`, `.gallery`, `.usage-cards`, `.news-cols`, `.custom-agent-list`,
the bento grid, and the dispatch grids — only the px floor changes (138–258, by how
much the card holds).

- `min(100%, Npx)` is load-bearing: without it the track can't go below `Npx` and the
  grid overflows on narrow screens.
- `auto-fill` keeps empty tracks (stable rhythm); `auto-fit` collapses them so few
  items stretch wide. Pick deliberately.
- **This replaces a media query.** Never add a breakpoint to change column count.

### 3.2 Flex rows: wrap, don't squeeze

```css
.np-row { display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; min-width: 0; }
.np-row > label { flex: 1 1 min(280px, 100%); }
```

`flex-wrap: wrap` plus a **real flex-basis** = items drop to a new line instead of one
item absorbing all the shrink.

**`min-width: 0` is a loaded gun.** It removes the min-content floor, making that item
the one thing that collapses. Use it only where the item is *supposed* to truncate
(with `overflow: hidden; text-overflow: ellipsis`), never on the only shrinkable item
in a row that also holds fixed controls. *Why:* `.agent-name` was `flex: 1; min-width: 0`
— on cards with two model pickers it collapsed to **19px holding 77px of text** and,
with nothing clipping it, painted straight over the pickers.

- Text that must stay readable → `flex: 1 1 auto`, leave `min-width: auto`.
- Text that may ellipsis → `min-width: 0` **and** `overflow: hidden; text-overflow: ellipsis`.
- Fixed controls (dots, icons, buttons) → `flex-shrink: 0`.
- A string with no spaces that can exceed its box → `overflow-wrap: anywhere`.

### 3.3 Cards in a row should agree

Grid cards share a height; their contents don't align on their own. Push footer
actions down with `margin-top: auto` so footers share a baseline regardless of how
many lines the title took.

### 3.4 Fluid sizing with `clamp()`, not breakpoints

Use the tokens `--page-pad: clamp(14px, 2.6vw, 24px)` and `--panel-pad: clamp(14px, 2vw, 18px)`
rather than fixed px. Same idiom sizes the sidebar (`clamp(156px, 16vw, 188px)`),
detail rail (`clamp(290px, 28vw, 360px)`), landing type (`clamp(40px, 8vw, 88px)`).

Media queries are for genuine *layout mode* changes only — two columns → one, pinned
landing → static stack. **Reuse an existing breakpoint:** `max-width` already appears
at 560, 620, 640, 700, 720, 760, 850, 860, and 900px — nine values doing ~four jobs.
Take the nearest, and prefer §3.1/§3.2 (no breakpoint at all) over any of them.

### 3.5 Verify at width, don't eyeball it

```js
for (const w of [1600, 1100, 820, 620, 420]) {
  el.style.width = w + 'px'; el.offsetHeight;  // force sync layout
  // assert: node.scrollWidth <= Math.ceil(node.getBoundingClientRect().width)
}
```

(`requestAnimationFrame` is throttled in a background tab — read `offsetHeight`
instead of awaiting a frame.)

---

## 4. Motion

Gate every decorative animation on the resolved preference, **not** the media query:

```css
:root[data-motion="reduced"] .your-thing { animation: none; }
```

The boot script resolves Settings → Appearance → Motion *and* `prefers-reduced-motion`
into one `data-motion="full" | "reduced"` on `<html>` before first paint; JS reads
`document.documentElement.dataset.motion === 'reduced'`.

**Never write a bare `@media (prefers-reduced-motion: reduce)`.** It can't be
overridden from inside the app, which is the whole point of the setting: Windows
derives that flag from one coarse "animation effects" checkbox, so users who only
meant to stop window animations silently lost the beams and the landing hero with no
way back. Sole exception: rules genuinely about *screen size* (the landing's no-pin
fallback keeps its own `@media (max-width: 640px)`).

Timings: `0.1s` pill hovers, `0.15s` menu items, `0.25s` chevron, `~0.3s` panel
enter/exit. Match them.

---

## 5. Surfaces and the background

A fixed `.beams` SVG layer sits at `z-index: 0` behind the dashboard; overview
surfaces are translucent so it reads through. Add `.glass`, or:

```css
background: var(--glass);
backdrop-filter: var(--glass-blur);
-webkit-backdrop-filter: var(--glass-blur);
border: 1px solid var(--glass-border);
```

`--glass-inset` for a mini-card on glass, `--glass-elev` for its hover.

**Glass vs solid is a decision, not a default.** Chrome (header, sidebar) and dense
working views are solid `--surface` so text stays crisp; ambient overview panels are
glass. Copy whichever neighbour you sit next to. Anything that must fully occlude the
beams (the landing stage) uses opaque `var(--bg)`.

---

## 6. Markup and JS conventions

**6.1 Escaping is not optional.** The UI renders template literals into `innerHTML`.
**Every interpolated value goes through `esc()`** — including values from "our own
API", because those come from vault files a user or agent wrote.

```js
`<div class="agent-card" id="card-${esc(a.id)}">${esc(a.name)}</div>`
```

**6.2 Tailwind classes next to `${}` need a space.**

```js
`... leading-[1] ${warn ? 'text-overdue' : ''}`   // ✅ scanner sees leading-[1]
`... leading-[1]${warn ? '…' : ''}`               // ❌ silently never compiled
```

Purge is content-driven: a class only lands in `static/tailwind.css` if it appears
literally in a scanned template. Add classes → **rebuild** (`build-css.bat`) →
hard-refresh. A utility that "does nothing" is almost always a skipped rebuild. See
`CLAUDE.md` → Tailwind for why the unlayered `<style>` block always wins.

**6.3 Where CSS goes.** The hand-written `<style>` block, in the section for the view
you're touching (`/* ── Agents ── */`, …). Not inline `style=`, except per-instance
values CSS can't know (a computed offset, a per-element `animation-delay`).

**6.4 Comment the non-obvious constraint, not the obvious code.** Explain *why a rule
is the way it is* — that's what stops the next agent simplifying it back into a bug.
If you fixed a layout bug, say what broke.

**6.5 Accessibility floor.** `aria-hidden="true"` on decorative layers (beams,
spotlight, hero canvas). `title` on icon-only controls. Keep `:focus-visible` when
restyling anything focusable — several components define focus separately from hover
because the trigger is a `<button>`.

---

## 7. Copy

The UI should be intuitive without a paragraph explaining it. **Feature rationale,
billing models, storage/precedence semantics, trust guarantees, and setup background
belong in `README.md`, not on screen.** A wall of small grey text in the product is a
design failure being patched with prose.

### 7.1 Length budgets by slot

| Slot | Budget | Job |
|---|---|---|
| View header `<p>` (under the `<h2>`) | **≤ 8 words**, one clause | Orient, don't explain. "Appearance, backends, and connections." |
| `.bento-sub` | one short sentence | What this card configures |
| `.stg-p-hint` | one clause | The non-obvious format or empty-value default |
| Static `.np-msg` help | one clause + a link | Only where a setup step can't be inferred |
| `.empty-sm` / `.chat-empty` | one sentence | What to do next, not why the feature exists |
| `.usage-foot` | one caveat | The single thing that would otherwise mislead |
| `.wiz-p` (onboarding) | one sentence | More license than the app — still one sentence |

Over budget? The answer is a better control, a better label, or a README section —
not a longer string.

### 7.2 Don't restate the control

Check the labels, placeholders, and option text first. The Chat header once carried a
45-word paragraph explaining that Fast runs locally and Claude bills your plan —
directly above pills reading `⚡ Fast · local` and `✨ Claude · plan`. Pure
duplication. Same trap: a placeholder of `(from your credentials)` already says what
an empty Project field does.

### 7.3 Put the fact next to the control it constrains

The Settings header used to warn that the vault path needs a restart, while the vault
field's own footer (`#stg-vault-now`) said it in context, where someone changing it
would actually read it. Header prose duplicating in-place messaging is the first cut.

### 7.4 What still earns words

Three cases, each capped at a clause:

- **Un-inferable setup steps** — `gcloud auth application-default login`, which OAuth
  client type to create. Prefer a link over a description.
- **Trust guarantees where they matter** — "Read mail and save drafts — nothing is
  ever sent" belongs on the Inbox header; that's a promise needed *before* connecting.
- **Caveats on numbers** — "Cost is estimated from list prices."

Everything else goes in the README.

### 7.5 Voice

Sentence case. No exclamation marks. Imperative for actions ("Create a project
folder"), noun phrase for descriptions ("Notes with deadlines, by month"). Em dashes
are fine; two in one string means it's too long.

---

## 8. Live data

**A view that reads the vault must stay current on its own.** The vault is edited from
outside Regalia constantly — Obsidian, agent runs, dispatch workers — so a view that
loads once is stale immediately. *Why this is rule 7 despite being newest:* the whole
app violated it until v1.36; marking an assignment complete did nothing visible and
the only fix was restarting. A manual **Refresh** button came first, which made
staleness fixable but left noticing it to the user. Assume nobody presses it.

### 8.1 Watch the fingerprint, not the data

`GET /api/vault-revision` is a stat-only walk (~0.09s, vs ~0.14s `/api/tasks` and
~0.94s `/api/vault-map`) returning two hashes over `(relpath, mtime_ns, size)`. The
`vaultSync` poller already polls it. **Hook into it — don't add a second poller, and
never put an expensive endpoint on a `setInterval`.**

| Your view reads | Watch | Hook |
|---|---|---|
| `/api/tasks`, `/api/recent-folders` | `notes` | add your render call in `loadOverviewData()` |
| `/api/vault-map`, `/api/vault-preview` | `tree` | the `treeStale` path in `vaultSyncTick()` |
| anything else vault-derived | the narrower hash | extend `vaultSyncTick()`'s `work` array |

Two hashes exist so the expensive endpoints stay independent: dropping a PNG in a
folder must re-map Browse **without** making the overview refetch tasks. Adding a
third source? Decide which hash actually constrains it instead of refetching on both.

Edits, adds, deletes, and renames move a hash; a pure read doesn't. Need something
detected that doesn't touch mtime or size? That's a backend change to
`_scan_vault_revision()`, not a client workaround.

### 8.2 A re-render must preserve live state

Anything rebuilt on a data load must read current state, not hardcode a default — it
now reruns every few seconds under the user's hands. *Why:* `buildCoursePills()`
hardcoded `class="pill on"` on "All courses" while `buildAreaPills()` mirrored
`filters.course`. Under manual loads that was an occasional wrong-looking pill; once
refreshes became automatic it meant the list could filter by a course while the pills
denied it. Same class of bug as `vaultLoadMap()` resetting expansion to Home.

Preserve: active filter/pill state, scroll position, the value **and focus** of text
inputs, expanded/selected tree or graph nodes, and whether a detail panel is open (on
what). If the selection no longer exists, close cleanly — no stale inspector. Prefer
rendering from one state object over reading state back out of the DOM you're replacing.

### 8.3 Idle when hidden, defer when invisible

Two gates, both required:

```js
if (document.hidden) return;                     // scheduler: stop polling
if (vaultSync.busy || document.hidden) return;   // tick: refuse to run
```

A backgrounded tab or closed desktop window must cost nothing, and must catch up on
`visibilitychange`/`focus` so it's never stale when looked at. Separately, **rebuild
only what's on screen**: Browse is flagged `vaultSync.treeStale` while hidden and
remapped when `setView('browse')` opens it — rebuilding a 3,400-node graph nobody is
looking at buys nothing. Any view with a costly rebuild gets the same treatment.

### 8.4 Degrade quietly

A failed poll backs off exponentially to a 30s ceiling and retries without surfacing
an error — the server restarting (debug autoreload does this on every save) is the
common case, not an incident. Confirmation of a successful live update reuses the
Refresh button's label rather than adding chrome; a live view should feel like it was
always right, not announce itself.

### 8.5 Verify liveness by counting requests

"It updates" and "it doesn't thrash" are two claims, both needing evidence:

```js
const counts = {}; const orig = window.fetch;
window.fetch = function (u, ...rest) {
  const k = String(typeof u === 'string' ? u : u.url).replace(location.origin, '').split('?')[0];
  counts[k] = (counts[k] || 0) + 1;
  return orig.call(this, u, ...rest);
};
await new Promise(r => setTimeout(r, 13000));
window.fetch = orig; JSON.stringify(counts);
```

**A quiet vault must show fingerprint polls and zero data refetches** — a refetch with
no change behind it re-renders over the user for nothing. Then change a file on disk
and confirm the view updates with no interaction.

(Automation caveat: a tool-driven tab usually reports `document.hidden === true`, so
the poller correctly idles and nothing appears to work. Verify the hidden gate on its
own, then override `document.hidden`/`visibilityState` to exercise the visible path.)

### 8.6 Chat richness and Edit mode are provider-neutral

Every chat tier uses the same live response shell: working presence, ordered activity,
readable tool arguments/results, Markdown answers, model labels, background completion,
and the same compact/expanded behavior. New backends route through `/api/chat/stream`
and the shared `think` / `text` / `status` / `tool` / `tool_result` vocabulary. Show the
richest safe events the provider exposes, but never manufacture progress or surface
hidden chain-of-thought.

Edit mode is one promise across providers. A managed host may refuse to make an account
CLI's filesystem mount writable even when the CLI requests it. Keep that model read-only
and require a strict structured edit response; Regalia must validate every relative path
against the vault root before applying an operation itself. Never bypass approvals and
sandboxing globally just to make the toggle work. Verify an effective file change, not
only command argumentsâ€”a writable label without a write is a broken control.

---

## 9. Before you say it's done

- [ ] New color goes through a token; nothing hard-codes `#e7c59a`.
- [ ] Checked in **both themes** — light is where token violations surface.
- [ ] Checked with Motion **Always animate** *and* **Reduced**.
- [ ] Measured at narrow and wide (§3.5) — no overflow, no overlap.
- [ ] If it reads the vault: updates without a manual refresh, and a quiet vault
      causes **zero** data refetches — counted, not assumed (§8.5).
- [ ] Any new `<select>` renders as an `.acx-trigger`, and its `.value` round-trips.
- [ ] Every new string is inside its §7.1 budget and says something the surrounding
      labels don't. Explanation went to the README.
- [ ] Rebuilt Tailwind if you touched utility classes.
- [ ] `python -m unittest discover -s tests` passes.
- [ ] Ran it and looked at it. A screenshot or a measured assertion — "should work"
      is not evidence (root `CLAUDE.md`: pair every change with a way to verify it).
