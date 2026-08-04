# Dashboard — Unreleased Features (since the latest release)

**Purpose:** a running list of what has been added to the dashboard **since the
last cut release**, for other agents (and humans) to read without diffing git.
This is the staging ground for the *next* release's notes.

**Baseline release:** **v1.34** (Gemini access + agent/file workflow upgrades).
Everything added below is on top of v1.34 and is **not yet in a released build**.

**When the next release is cut:** fold these entries into `VERSION_HISTORY.md`
under the new version heading, bump `version.py`, then clear this file back to
this template.

---

## Manual vault refresh

- The Overview now has a **Refresh** action that re-reads tasks and recent-folder
  tiles from disk without reloading Regalia.
- Browse gained its own **Refresh** action. It remaps the vault and file tree
  with cache bypassing while preserving expanded folders and the selected file
  when those nodes still exist.
- Both controls show refreshing, success, and retry states. The initial Overview
  load uses the same refresh path, so manual and startup behavior cannot drift.
