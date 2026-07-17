# Releasing Regalia publicly

This repo's *working tree* is clean of personal data, but its **git history is not** —
and pushing this history to a public repo republishes everything in it. Do the history
step below **once, yourself, before the repo goes public**. It is destructive and cannot
be automated safely from inside a session.

## What's still in history (as of 2026-07-17)

- `Resume/**` in every commit since the initial one — full legal name, home address,
  phone number, personal email, resume PDFs, and an internship writeup naming employers.
- `.claude/settings.local.json` in commits `d905942` and `b49517b` — a machine username
  and local paths.
- Commit message `d905942` names employers and private projects.
- All commits carry your git author identity (`name <email>`) — fine if you're publishing
  under that identity; rewrite if not.

## Option 1 — fresh public baseline (recommended, simplest)

Publish the current tree as a single clean commit in a **new** public repo, keeping this
repo as your private working copy with full history:

```bash
# from a clean checkout of the release branch
git checkout --orphan public-release
git add -A
git commit -m "feat: Regalia v1.23 — initial public release"
git remote add public git@github.com:<you>/regalia.git
git push public public-release:main
```

Nothing sensitive can survive this — history *is* the one commit you just made.

## Option 2 — rewrite this repo's history in place

Only if the existing repo itself must become public. Use
[git-filter-repo](https://github.com/newren/git-filter-repo) (not `filter-branch`):

```bash
pip install git-filter-repo
git filter-repo \
  --path Resume --path .claude/settings.local.json \
  --path research/RAG-pipelines/resources/ai-system-design-guide-main \
  --invert-paths
# optionally also rewrite messages/authors:
#   git filter-repo --message-callback '...' --mailmap <file>
git push --force --all && git push --force --tags
```

Then on GitHub: contact support or use the UI to clear cached views, and treat any
previously-pushed secrets/PII as public regardless.

## Verify before pushing anywhere public

```bash
# tree: no PII / employer names / vendored corpus. Build the pattern yourself from
# your real name, personal email, employer names — don't commit the filled-in version.
PII='<employer1>|<employer2>|<legal-name>|<personal-email>'
git ls-files | grep -iE 'resume|ai-system-design-guide' ; \
git grep -iE "$PII" -- ':!LICENSE'
# history (Option 2 only): both must print nothing
git log --all --oneline -- Resume .claude/settings.local.json
git log --all --format=%s | grep -iE "$PII"
```

## Cutting a version release

1. Make sure the smoke suite is green (`cd dashboard && python -m unittest discover -s tests`)
   — the tests workflow also runs it on every push.
2. Tag and push: `git tag v1.24 && git push origin v1.24`.
3. The `release` workflow (`.github/workflows/release.yml`) builds the standalone desktop
   app on Windows + macOS with PyInstaller (`dashboard/regalia.spec`) and attaches
   `Regalia-windows.zip` / `Regalia-macos.zip` to the GitHub Release for the tag.
   (It can also be run manually via workflow_dispatch to test the build.)
4. Local build for testing: `dashboard/build.bat` (Windows) or `dashboard/build.sh`
   (macOS/Linux) → `dashboard/dist/Regalia/`.

Packaged-build behavior worth knowing: per-user state (settings, chats, email tokens,
uploads) moves to the OS user-data dir (`dashboard/paths.py`); the vault defaults to
`~/RegaliaVault` until changed in Settings; chat attachments can't be read by the
`claude` CLI tier when packaged (they live outside the vault tree — the other tiers
inline them).
