#!/usr/bin/env bash
# Apply the Founder's Edition workflow into the vault root.
# Copies .cursor/rules/*, the area CLAUDE.md files, and the course-setup skill
# into place. Existing files are skipped unless --force is passed.
#
# Usage:  bash founders-edition/apply.sh [--force]
set -euo pipefail

force=0
[ "${1:-}" = "--force" ] && force=1

bundle="$(cd "$(dirname "$0")" && pwd)"
root="$(dirname "$bundle")"
copied=0; skipped=0

while IFS= read -r -d '' f; do
  rel="${f#"$bundle"/}"
  case "$rel" in README.md|apply.ps1|apply.sh) continue ;; esac
  dest="$root/$rel"
  if [ -e "$dest" ] && [ "$force" -eq 0 ]; then
    echo "skip  $rel (exists; --force to overwrite)"
    skipped=$((skipped + 1))
  else
    mkdir -p "$(dirname "$dest")"
    cp "$f" "$dest"
    echo "copy  $rel"
    copied=$((copied + 1))
  fi
done < <(find "$bundle" -type f -print0)

echo ""
echo "Done: $copied copied, $skipped skipped. Reload Cursor / Claude Code to pick up the rules and skill."
