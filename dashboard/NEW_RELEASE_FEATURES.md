# Dashboard — Unreleased Features (since the latest release)

**Purpose:** a running list of what has been added to the dashboard **since the
last cut release**, for other agents (and humans) to read without diffing git.
This is the staging ground for the *next* release's notes.

**Baseline release:** **v1.35** (Vertex AI tier, live activity timeline,
opportunity briefing). Everything added below is on top of v1.35 and is **not
yet in a released build**.

**When the next release is cut:** fold these entries into `VERSION_HISTORY.md`
under the new version heading, bump `version.py`, then clear this file back to
this template.

---

**Calendar view** — a new sidebar view laying vault notes onto a month grid.
Each note is drawn as a **bar running from its frontmatter `date:` (created)
through its `deadline:`**, rather than as a dot on the due date — so work that
is *currently open* appears on today's column instead of only on the day it
happens to be due. That was the point of the view: seeing what needs doing now,
not just what is landing later.

Prev / Today / Next navigation; the current day is ringed in the accent; overdue
notes take a red rule and completed ones strike through. The header reads
`N due · M open this month`. A bar crossing a week boundary is split into one
segment per week row, each keeping the same lane so it reads as one continuous
run, with the inset dropped and the radius flattened on any edge that continues
past the week. Weeks pack up to 4 lanes and show a `+N` marker per day beyond
that.

Deliberately **read-only and backend-free**: it reads the existing `/api/tasks`
(which already returned both `date` and `deadline`) off the same in-memory `all`
array the overview renders, and reuses `dlState()` for the overdue/soon
classification — no new endpoint, no new dependency, no external calendar
service. This is the "deadline/calendar view" from `PRODUCT_VISION.md` Theme ④.

*Implementation notes.* Two constraints are load-bearing and both are guarded by
smoke tests:

- **All date maths runs on integer day ordinals** from `Date.UTC(y, m, d)`, never
  by parsing a date string into a local `Date`. `new Date('2026-08-10')` is UTC
  midnight, so a local round trip drops every deadline one cell early for any
  user west of UTC. A value that isn't a plain ISO date is skipped, not guessed
  at; a note whose `date:` is missing — or later than its own deadline, i.e. bad
  frontmatter — collapses to a single day on the deadline rather than being
  dropped or drawn backwards.
- **A week is a CSS grid, not seven boxes with items nested inside**, because a
  nested item cannot cross its own cell. Day cells occupy `grid-row: 1 / -1` as
  the background, date numbers sit in row 1, and each bar spans
  `grid-column: start / span N` on a lane row beneath. A week with nothing
  scheduled emits only the number row — `repeat(0, …)` is invalid CSS and would
  silently drop the whole track list.

---

**Live vault sync** — an open Regalia now reflects vault edits on its own.
Marking an assignment complete, retitling a note, adding or deleting one used to
require closing and reopening the app (or hitting the manual Refresh added
just before this); the overview, stats, filter pills, calendar and Browse map
now update within a few seconds of the file changing on disk.

The client polls a **fingerprint**, not the data. `GET /api/vault-revision`
does one stat-only walk — no file reads, no YAML parsing — and returns two
hashes over `(relpath, mtime_ns, size)`:

- `notes` — every `.md` the task loader / recent-folders / calendar can see
- `tree` — every file the Browse map lists (`_browser_rel_allowed`)

Two hashes because the two expensive endpoints have different inputs, so
dropping a PNG into a folder re-maps Browse without making the overview refetch
tasks. Edits, adds, deletes and renames all move a hash; a pure read does not.
Measured on the development vault: the fingerprint is **~0.09 s** against
~0.14 s for `/api/tasks` and ~0.94 s for `/api/vault-map`, and a 1 s server-side
memo collapses several open tabs (browser + desktop window) into one walk.

Three things keep it from being a busy-loop, and each has a smoke test:

- **Polling stops entirely while the window is hidden** and checks immediately
  on the way back, so a backgrounded tab costs nothing yet is never stale when
  you look at it.
- **Browse is only re-mapped when it is the visible view.** `/api/vault-map` is
  an order of magnitude more expensive than the fingerprint, so a hidden Browse
  is flagged stale and remapped on the next visit instead.
- **A quiet vault causes zero refetches** — verified live: 13 s of polling on an
  unchanged vault issued 3 fingerprint requests and no data requests at all.
  This matters beyond cost: a spurious re-render would stomp the user's scroll,
  filters and graph selection.

Failed polls back off exponentially (to 30 s) rather than hammering a server
that is restarting. The manual Refresh buttons stay as a force path, and now
re-seed the poller so they don't cause a duplicate fetch.

*Fixed alongside:* `buildCoursePills()` hardcoded "All courses" as the selected
pill while `buildAreaPills()` mirrored live state. Because the pills are rebuilt
on every data load, an active course filter would keep filtering the list while
the pills claimed otherwise — visible on manual refresh before, and on every
automatic one now.

*Known limit:* the walk prunes hidden directories, so a note buried inside one
(`.github/notes.md`) is not watched, even though `load_tasks()`' `rglob` would
surface it. Pruning is what keeps `.git/` out of the walk, and the Browse map
already refuses to list those paths for the same reason.
