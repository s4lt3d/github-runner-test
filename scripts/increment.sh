#!/usr/bin/env bash
# Bumps the run counter and "last ran" date inside README.md's runner-stats block.
set -euo pipefail

README="${1:-README.md}"
START="<!-- runner-stats:start -->"
END="<!-- runner-stats:end -->"

count=$(grep -Eo 'Run count: \*\*[0-9]+\*\*' "$README" | grep -Eo '[0-9]+' || echo 0)
count=$((count + 1))
now=$(date -u '+%Y-%m-%d %H:%M:%S UTC')
sha="${GITHUB_SHA:-local}"

block="$START
- Run count: **$count**
- Last ran: **$now**
- Triggered by commit: \`${sha:0:7}\`
$END"

tmp=$(mktemp)
BLOCK="$block" awk -v start="$START" -v end="$END" '
  $0 == start { print ENVIRON["BLOCK"]; skip = 1; next }
  $0 == end   { skip = 0; next }
  !skip       { print }
' "$README" > "$tmp"
mv "$tmp" "$README"

echo "Run #$count at $now (commit ${sha:0:7})"
