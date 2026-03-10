#!/bin/sh
set -eu

RUNTIME_ROOT="${RUNTIME_ROOT:-$HOME/.signal-deck/runtime}"
LOG_DIR="${SIGNAL_DECK_LOG_DIR:-$HOME/.signal-deck/logs}"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"
SCRIPT_PATH="$RUNTIME_ROOT/telegram_bot_service.py"
TELEGRAM_ENV_PATH="${TELEGRAM_ENV_PATH:-$RUNTIME_ROOT/telegram.env}"

mkdir -p "$LOG_DIR"

cd "$RUNTIME_ROOT"
export SIGNAL_DECK_LOG_DIR="$LOG_DIR"
export PYTHONPATH="$RUNTIME_ROOT${PYTHONPATH:+:$PYTHONPATH}"

if [ -f "$TELEGRAM_ENV_PATH" ]; then
  # shellcheck disable=SC1090
  . "$TELEGRAM_ENV_PATH"
fi

exec "$PYTHON_BIN" "$SCRIPT_PATH"
