#!/bin/sh
set -eu

ROOT="/Users/haihan/Documents/New project"
PYTHON_BIN="/usr/bin/python3"
RUNTIME_ROOT="$HOME/.signal-deck/runtime"
SHARED_LOG_DIR="$HOME/.signal-deck/logs"
SCRIPT_PATH="$RUNTIME_ROOT/dryrun_recorder.py"
LOG_PATH="$SHARED_LOG_DIR/dryrun_cron.log"
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

mkdir -p "$RUNTIME_ROOT" "$SHARED_LOG_DIR"

for file in dashboard_server.py dryrun_recorder.py live_experiment_signal.py signal_engine.py; do
  cp "$ROOT/$file" "$RUNTIME_ROOT/$file"
done

mkdir -p "$ROOT/logs"
for file in dryrun_signals.csv dryrun_latest.txt dryrun_state.json dryrun_cron.log dryrun_trades.csv dryrun_trade_state.json; do
  if [ -f "$ROOT/logs/$file" ] && [ ! -f "$SHARED_LOG_DIR/$file" ]; then
    cp "$ROOT/logs/$file" "$SHARED_LOG_DIR/$file"
  fi
done

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
    echo "$schedule cd \"$RUNTIME_ROOT\" && SIGNAL_DECK_LOG_DIR=\"$SHARED_LOG_DIR\" \"$PYTHON_BIN\" \"$SCRIPT_PATH\" >> \"$LOG_PATH\" 2>&1"
  done
  echo "$TAG_END"
} >> "$TMP_FILE"

crontab "$TMP_FILE"
echo "Installed dry-run cron schedules:"
printf '%s\n' "$SCHEDULE_LINES"
