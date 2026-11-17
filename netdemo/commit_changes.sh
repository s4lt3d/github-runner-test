#!/usr/bin/env bash
# Commits real config changes in netdemo/backups, one commit per device so each
# change is attributed to the user who made it. Files whose only changes are
# volatile lines (see ignore-patterns.txt) are reverted instead of committed.
set -euo pipefail
cd "$(dirname "$0")"
DIR=backups
SUFFIX="${COMMIT_SUFFIX:-}"

args=()
while IFS= read -r p; do
  [[ -z "$p" || "$p" == \#* ]] || args+=(-I "$p")
done < ignore-patterns.txt

# New devices: one baseline commit.
new=()
while IFS= read -r f; do new+=("$f"); done < <(git ls-files --others --exclude-standard -- "$DIR")
if (( ${#new[@]} )); then
  git add -- "${new[@]}"
  git commit -q -m "Baseline for ${#new[@]} new device(s)$SUFFIX" -- "${new[@]}"
  echo "baseline: ${#new[@]} new device(s)"
fi

changed=0 noise=0
while IFS= read -r f; do
  if git diff --quiet "${args[@]}" -- "$f"; then
    git checkout -q -- "$f"
    noise=$((noise + 1))
  else
    dev=$(basename "$f" .cfg)
    user=$(sed -n 's/^! Last configuration change at .* by \([^ ]*\)$/\1/p' "$f" | head -1)
    git add -- "$f"
    git commit -q -m "$dev changed by ${user:-unknown}$SUFFIX" -- "$f"
    echo "changed: $dev (by ${user:-unknown})"
    changed=$((changed + 1))
  fi
done < <(git diff --name-only --relative -- "$DIR")

echo "summary: $changed real change(s), $noise timestamp-only file(s) ignored"
