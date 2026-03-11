#!/bin/sh
set -eu

RUNTIME_ROOT="${RUNTIME_ROOT:-$HOME/.signal-deck/runtime}"
LOOP_INTERVAL="${SIGNAL_DECK_LOOP_INTERVAL:-5}"
JOB_PATH="$RUNTIME_ROOT/run_dryrun_job.sh"

if ! [ -x "$JOB_PATH" ]; then
  echo "dryrun daemon error: missing job wrapper at $JOB_PATH" >&2
  exit 1
fi

case "$LOOP_INTERVAL" in
  ''|*[!0-9.]*)
    echo "dryrun daemon error: invalid SIGNAL_DECK_LOOP_INTERVAL=$LOOP_INTERVAL" >&2
    exit 1
    ;;
esac

trap 'exit 0' INT TERM

while true; do
  /bin/sh "$JOB_PATH" || true
  sleep "$LOOP_INTERVAL"
done
