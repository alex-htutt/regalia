# Regalia — UI Micro-Standards

**Who this is for:** any agent about to add or change UI in `dashboard/templates/index.html`.

**Where it sits.** `CLAUDE.md` is the architecture (what the modules are, how they
wire together). `Assets/DESIGN.md` is the Hyperstudio *visual language* (the brand
tokens, type scale, and component specs, written for design work). **This file is
the micro layer between them** — the concrete rules for making new UI look like it
was always part of Regalia, and the reusable pieces you must use instead of
rolling your own.

**The one-line version:** before you write a component, search this file, then
search `index.html` for something that already does it. Regalia is *one* 6,500-line
template with a hand-written stylesheet; new markup that invents its own dropdown,
its own breakpoint, or its own blue is instantly visible as bolted-on.

> Every rule below carries a **Why**. If a rule blocks something the task genuinely
> needs, the *why* tells you whether you're hitting the intent or just the letter —
> in which case say so in your summary rather than silently diverging.

---

## 0. The five that get violated most

1. **Links use the accent, never UA blue** → §1.2
2. **Write a plain `<select>`; never hand-roll a dropdown** → §2.1
3. **Flex rows wrap, they don't squeeze** (`min-width: 0` is a loaded gun) → §3.2
4. **Card grids use the `minmax(min(100%, Npx), 1fr)` idiom, not media queries** → §3.1
5. **Every interpolated value goes through `esc()`** → §6.1

---

## 1. Color

### 1.1 Use tokens. Never a raw hex in a component rule.

Both themes are defined as the *same token names* on `:root` and
`:root[data-theme="light"]` (`index.html`, top of the `<style>` block), so a
component that only reads tokens follows the light theme for free. A raw hex
doesn't, and the light theme is where it shows up as a black-on-black bug.

| Token | Use for |
|---|---|
| `--bg` | page canvas; also the inset background of inputs/textareas |
| `--surface` | card / panel background |
| `--elevated` | hover + raised surface |
| `--border` / `--border-hover` | hairlines; `-hover` doubles as the focus border |
| `--text` / `--muted` / `--faint` | primary copy / secondary copy / captions + timestamps |
| `--accent` / `--accent-fg` | **high-emphasis fills** — the white (dark theme) or near-black (light theme) button. *Not a chromatic color.* |
| `--amber` / `--amber-fg` | the **sole chromatic accent**. `--amber` for fills/borders, `--amber-fg` for text on a normal background |
| `--red` / `--green` | overdue signal / status dot. Not decoration |
| `--*-bg` / `--*-fg` pairs | tag chips only (`--blue-*`, `--green-*`, `--purple-*`, `--amber-*`, `--gray-*`) |

**Accent economy is a real constraint, not a preference.** Amber is the only
chromatic accent in the product. If your new component "needs" a second color to
be legible, it usually needs hierarchy (weight, size, `--muted`) instead.

**`--amber` vs `--amber-fg`:** identical values today, different jobs. Use
`--amber-fg` wherever the amber is *text*, `--amber` where it's a fill, border, or
glow. That way, if the pair ever has to diverge for contrast, every call site is
already labelled correctly.

**Accent is user-configurable.** The boot script (`index.html`, `<head>`) repoints
`--amber`, `--amber-fg`, and `--amber-bg` at whatever the user picked in
Settings → Appearance. Read the tokens and you inherit that; hard-code `#e7c59a`
and you've pinned one user's choice into the product.

### 1.2 Links

There is a base rule near the top of the stylesheet:

```css
a { color: var(--amber-fg); text-decoration: none; }
a:hover { text-decoration: underline; }
a:focus-visible { outline: 2px solid var(--amber-fg); outline-offset: 2px; border-radius: 3px; }
```

**Just write `<a href="…">`.** Do not add a per-component color rule for it.

*Why this rule exists:* for a long time there was **no base `a` rule at all**, so
every anchor in the app — the briefing footer, the Connections help text, release
notes, rendered chat markdown — came out **browser-blue and underlined** on the
obsidian canvas. It got patched once, locally, as `.bento-card a { color: … }`,
which fixed exactly one panel and hid the real problem. One base rule, no local
copies.

Override only when a link genuinely isn't accent-colored — e.g. `.news-item a` is
a headline that happens to be clickable, so it's `--text` and turns
`--purple-fg` on hover. Those overrides win on specificity; you don't need
`!important`.

External links carry `target="_blank" rel="noopener"`. In-app navigation is
`<a href="#" onclick="setView('settings'); return false;">`.

---

## 2. Use the components that exist

### 2.1 Dropdowns — write a native `<select>` and stop

Regalia has a custom dropdown (the Aceternity navbar-menu port, the `.acx-*`
block). **You never construct it.** An IIFE at the bottom of `index.html` runs
`acxEnhance()` over every `<select>` on the page, and a `MutationObserver` on
`document.body` catches any select added later by a re-render. The native select
stays in the DOM (hidden, `tabIndex -1`); a trigger button and a floating glass
panel replace only the presentation.

```html
<!-- this is the whole job -->
<select id="tier-x" class="agent-tier-select" title="Which backend runs this agent"
        onchange="somethingChanged('x')">
  <option value="fast">⚡ fast · local</option>
</select>
```

What that buys you, and what you break by hand-rolling:

- `getElementById(...).value` reads **and writes** keep working — there's an
  instance-level `value` interceptor that re-syncs the trigger on assignment.
- Inline `onchange` handlers keep firing.
- A `MutationObserver` per select re-syncs the label when you repopulate
  `<option>`s, or toggle `disabled` / `style.display` from app code.
- `title` on the select is copied onto the trigger, so the tooltip survives.
- The trigger is `type="button"` — it can sit inside `.np-form` without submitting.

**Consequences to respect:** the visible control is `.acx-trigger`, a *sibling* of
the select — so when you measure or lay out the row, the select itself is ~1px
wide and the trigger is the real box. Style the trigger alongside the select in
your selector list (the codebase already does this: `.np-form input, .np-form
select, …, .np-form .acx-trigger`), and use `:focus-visible` for the trigger since
it's a button, not a form control.

### 2.2 The rest of the kit

Reach for these before writing new CSS:

| Need | Use | Notes |
|---|---|---|
| Secondary / toggle button | `.pill` | `.pill.on` for the active state, `.pill.compact` for dense rows |
| Primary submit | `.np-submit` | fills with `--accent` |
| Form panel | `.np-form` + `.np-row` + `<label>` | label text is the uppercase micro-label; the control goes inside the label |
| Settings card | `.bento-card` (+ `.bento-head` / `.bento-title` / `.bento-sub` / `.bento-body`) | |
| Inline status message | `.np-msg`, plus `.ok` / `.err` | already colored `--green-fg` / `--red`; give it an id and set `textContent` |
| Empty state | `.empty-sm` | `--faint`, 12.5px — every list has one |
| Section label | `.activity-head` / `.proj-list-head` | uppercase, `--muted`, 11px |
| Tag chip | `.tag` + `.a0`/`.a1`/`.a2`/`.course` | uses the `--*-bg` / `--*-fg` pairs |
| Glass surface | `.glass` | `--glass` + `--glass-blur`; see §5 |

Field styling inside `.np-form` / `.bento-card` / `.dispatch-form` / `.inbox-bar`
is already defined for `input, select, textarea, .acx-trigger` as a group — put
your new field in one of those containers and it inherits the look. If you're
adding a *new* container, extend those existing selector lists rather than writing
a fresh set of field rules.

---

## 3. Scaling and layout

Regalia has no JS layout code and almost no breakpoints. Both are deliberate.

### 3.1 Card grids: one idiom

```css
grid-template-columns: repeat(auto-fill, minmax(min(100%, 258px), 1fr));
```

Used by `.agent-grid`, `.gallery`, `.usage-cards`, `.news-cols`,
`.custom-agent-list`, the bento grid, and the dispatch grids — only the px floor
changes (138 / 210 / 220 / 230 / 240 / 258 depending on how much the card holds).

- `min(100%, Npx)` is the load-bearing part: without it the track can't go below
  `Npx` and the grid overflows its container on narrow screens.
- `auto-fill` keeps empty tracks (stable column rhythm); `auto-fit` collapses them
  so few items stretch wide. Pick deliberately.
- **This replaces a media query.** Don't add a `@media` breakpoint to change a
  column count.

### 3.2 Flex rows: wrap, don't squeeze

The reference implementation is `.np-row`:

```css
.np-row { display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; min-width: 0; }
.np-row > label { flex: 1 1 min(280px, 100%); }
```

`flex-wrap: wrap` plus a **real flex-basis** means items drop to a new line when
they stop fitting, instead of one item absorbing all the shrink.

**`min-width: 0` on a flex item is a loaded gun.** It removes the min-content
floor, so that item becomes the one thing that collapses. Use it only when the
item is *supposed* to truncate (with `overflow: hidden` / `text-overflow: ellipsis`
so the text actually clips), and never on the only shrinkable item in a row that
also holds fixed-size controls.

*This is not hypothetical.* `.agent-name` was `flex: 1; min-width: 0` — basis 0
and the only shrinkable item in the header. On agent cards showing two model
pickers, the pickers ate the whole 268px row, the name box collapsed to **19px
holding 77px of text**, and with nothing clipping it the name painted straight
over the pickers. The fix was `flex-wrap: wrap` on the row, `flex: 1 1 auto` on
the name, and leaving `min-width` at `auto` (min-content) so it can't be crushed —
plus `overflow-wrap: anywhere` for a name longer than the card.

Rules of thumb:
- Text that must stay readable → `flex: 1 1 auto`, leave `min-width: auto`.
- Text that may ellipsis → `min-width: 0` **and** `overflow: hidden; text-overflow: ellipsis`.
- Fixed controls (dots, icons, buttons) → `flex-shrink: 0`.

### 3.3 Cards in a row should agree

Grid cards stretch to a shared height, but their contents don't align on their
own. If a card has a footer action (a Run button, a submit row), push it down with
`margin-top: auto` on that row so the footers share a baseline regardless of how
many lines the title or description took.

### 3.4 Fluid sizing with `clamp()`, not breakpoints

`--page-pad: clamp(14px, 2.6vw, 24px)` and `--panel-pad: clamp(14px, 2vw, 18px)`
are the standard paddings — **use the tokens** rather than a fixed px value. The
same idiom sizes the sidebar (`clamp(156px, 16vw, 188px)`), the detail rail
(`clamp(290px, 28vw, 360px)`), and the landing type (`clamp(40px, 8vw, 88px)`).

Media queries are reserved for genuine *layout mode* changes — collapsing a
two-column split to one, or swapping the pinned landing for a static stack.

**Reuse an existing breakpoint.** The set has already drifted — `max-width` is
currently used at **560, 620, 640, 700, 720, 760, 850, 860, and 900px**, which is
nine values doing roughly four jobs. Pick the nearest one that fits instead of
adding a tenth, and prefer §3.1/§3.2 (which need no breakpoint at all) over any
of them.

### 3.5 Verify at width, don't eyeball it

Before claiming a layout change works, measure it. Set the container width across
a range and assert nothing overflows:

```js
for (const w of [1600, 1100, 820, 620, 420]) {
  el.style.width = w + 'px'; el.offsetHeight;  // force sync layout
  // assert: node.scrollWidth <= Math.ceil(node.getBoundingClientRect().width)
}
```

(`requestAnimationFrame` is throttled in a background tab — read `offsetHeight` to
force layout instead of awaiting a frame.)

---

## 4. Motion

Every decorative animation is gated on the resolved motion preference, **not** on
the media query directly:

```css
:root[data-motion="reduced"] .your-thing { animation: none; }
```

The boot script resolves `Settings → Appearance → Motion` *and*
`prefers-reduced-motion` into one `data-motion="full" | "reduced"` attribute on
`<html>` before first paint; JS reads
`document.documentElement.dataset.motion === 'reduced'`.

**Do not write a bare `@media (prefers-reduced-motion: reduce)` block.** It can't
be overridden from inside the app, which is the entire reason the setting exists:
Windows derives that flag from a single coarse "animation effects" checkbox, so
users who only meant to stop window animations were silently losing the ambient
beams and the landing hero with no way to get them back.

The one legitimate exception is a rule that is genuinely about *screen size*
(the landing's no-pin fallback keeps a separate `@media (max-width: 640px)` copy —
small screens stay unpinned no matter what the motion setting says).

Timings in use: `0.1s` for pill hovers, `0.15s` for menu item transitions, `0.25s`
for the chevron, `~0.3s` for panel enter/exit. Match them.

---

## 5. Surfaces and the background

A fixed `.beams` SVG layer sits at `z-index: 0` behind the dashboard. Overview
surfaces are translucent glass so it reads through:

```css
background: var(--glass);
backdrop-filter: var(--glass-blur);
-webkit-backdrop-filter: var(--glass-blur);
border: 1px solid var(--glass-border);
```

or just add `.glass`. Use `--glass-inset` for a mini-card sitting on glass, and
`--glass-elev` for its hover state.

**Glass vs solid is a decision, not a default.** Chrome (header, sidebar) and
dense working views are solid `--surface` so text stays crisp; the ambient
overview panels are glass. Copy whichever neighbour your component sits next to.
Anything that must occlude the beams entirely (the landing stage) uses an opaque
`var(--bg)`.

---

## 6. Markup and JS conventions

### 6.1 Escaping is not optional

The whole UI is rendered with JS template literals into `innerHTML`. **Every
interpolated value goes through `esc()`** — including values that "come from our
own API", because they come from vault files the user (or an agent) wrote.

```js
`<div class="agent-card" id="card-${esc(a.id)}">${esc(a.name)}</div>`
```

### 6.2 Tailwind classes next to `${}` need a space

```js
`... leading-[1] ${warn ? 'text-overdue' : ''}`   // ✅ scanner sees leading-[1]
`... leading-[1]${warn ? '…' : ''}`               // ❌ silently never compiled
```

Purge is content-driven: a class only lands in `static/tailwind.css` if it appears
literally in a scanned template. Add classes → **rebuild** (`build-css.bat`) →
hard-refresh. A utility that "does nothing" almost always means you skipped the
rebuild. See `CLAUDE.md` → Tailwind for the full contract, including why the
hand-written `<style>` block (unlayered) always beats Tailwind utilities.

### 6.3 Where CSS goes

The hand-written `<style>` block in `index.html`, in the section for the view
you're touching (`/* ── Agents ── */`, `/* ── Inbox view ── */`, …). Not inline
`style=` attributes, except for genuinely per-instance values the CSS can't know
(an `animation-delay` per element, a computed offset).

### 6.4 Comment the non-obvious constraint, not the obvious code

This stylesheet's comments explain *why a rule is the way it is* — which is what
stops the next agent from "simplifying" it back into a bug. Follow that. If you
fixed a layout bug, the comment should say what broke.

### 6.5 Accessibility floor

`aria-hidden="true"` on decorative layers (beams, spotlight, hero canvas).
`title` on icon-only controls. Keep `:focus-visible` styling when you restyle
anything focusable — several components define focus separately from hover
because the trigger is a `<button>`.

---

## 7. Before you say it's done

- [ ] New color goes through a token; nothing hard-codes `#e7c59a`.
- [ ] Checked it in **both themes** (Settings → Appearance → Theme). The light
      theme is where token violations surface.
- [ ] Checked it with **Motion: Always animate** and **Reduced**.
- [ ] Measured at narrow and wide (§3.5) — no overflow, no overlap.
- [ ] Any new `<select>` renders as an `.acx-trigger`, and its `.value` round-trips.
- [ ] Rebuilt Tailwind if you touched utility classes.
- [ ] `python -m unittest discover -s tests` passes.
- [ ] Ran it and looked at it. A screenshot or a measured assertion — "should
      work" is not evidence (root `CLAUDE.md`: pair every change with a way to
      verify it).
