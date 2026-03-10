#!/bin/sh
set -eu

RUNTIME_ROOT="${RUNTIME_ROOT:-$HOME/.signal-deck/runtime}"
LOG_DIR="${SIGNAL_DECK_LOG_DIR:-$HOME/.signal-deck/logs}"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"
SCRIPT_PATH="$RUNTIME_ROOT/dryrun_recorder.py"
TELEGRAM_ENV_PATH="${TELEGRAM_ENV_PATH:-$RUNTIME_ROOT/telegram.env}"

mkdir -p "$LOG_DIR"

# Local time window:
# - Weekdays: 15:00-23:59
# - Weekends: 10:00-23:59
WEEKDAY="$(date '+%u')"
HOUR="$(date '+%H')"

RUN_JOB=0
if [ "$WEEKDAY" -ge 1 ] && [ "$WEEKDAY" -le 5 ]; then
  if [ "$HOUR" -ge 15 ] && [ "$HOUR" -le 23 ]; then
    RUN_JOB=1
  fi
else
  if [ "$HOUR" -ge 10 ] && [ "$HOUR" -le 23 ]; then
    RUN_JOB=1
  fi
fi

if [ "$RUN_JOB" -ne 1 ]; then
  exit 0
fi

cd "$RUNTIME_ROOT"
export SIGNAL_DECK_LOG_DIR="$LOG_DIR"
if [ -f "$TELEGRAM_ENV_PATH" ]; then
  # shellcheck disable=SC1090
  . "$TELEGRAM_ENV_PATH"
fi

exec "$PYTHON_BIN" "$SCRIPT_PATH" \
  --disable-gate \
  --limit 20 \
  --timeout 6 \
  --winner-max-time-left 180 \
  --winner-min-lead 6 \
  --winner-p-min 0.80 \
  --winner-p-max 0.95 \
  --winner-min-edge 0.025 \
  --winner-max-buy-price 0.91 \
  --fee-total 0.02
