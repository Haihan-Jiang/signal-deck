#!/bin/sh
set -eu

ROOT="/Users/haihan/Documents/New project"
PYTHON_BIN="/usr/bin/python3"
SCRIPT_PATH="$ROOT/dryrun_recorder.py"
LOG_PATH="$ROOT/logs/dryrun_cron.log"
TAG_BEGIN="# signal-deck-dryrun:begin"
TAG_END="# signal-deck-dryrun:end"
if [ "$#" -gt 0 ]; then
  SCHEDULE_LINES="$1"
else
  SCHEDULE_LINES="$(cat <<'EOF'
*/2 15-23 * * 1-5
*/2 10-23 * * 0,6
EOF
)"
fi

TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT

if crontab -l >/dev/null 2>&1; then
  crontab -l | awk -v begin="$TAG_BEGIN" -v end="$TAG_END" '
    $0 == begin { skip = 1; next }
    $0 == end { skip = 0; next }
    skip != 1 { print }
  ' > "$TMP_FILE"
else
  : > "$TMP_FILE"
fi

{
  echo "$TAG_BEGIN"
  printf '%s\n' "$SCHEDULE_LINES" | while IFS= read -r schedule; do
    [ -n "$schedule" ] || continue
    echo "$schedule cd \"$ROOT\" && \"$PYTHON_BIN\" \"$SCRIPT_PATH\" >> \"$LOG_PATH\" 2>&1"
  done
  echo "$TAG_END"
} >> "$TMP_FILE"

crontab "$TMP_FILE"
echo "Installed dry-run cron schedules:"
printf '%s\n' "$SCHEDULE_LINES"
