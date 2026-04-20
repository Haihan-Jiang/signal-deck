#!/bin/sh
set -eu

RUNTIME_ROOT="${RUNTIME_ROOT:-$HOME/.signal-deck/runtime}"
LOG_DIR="${SIGNAL_DECK_LOG_DIR:-$HOME/.signal-deck/logs}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SCRIPT_PATH="$RUNTIME_ROOT/dashboard_server.py"
TELEGRAM_ENV_PATH="${TELEGRAM_ENV_PATH:-$RUNTIME_ROOT/telegram.env}"
POLYMARKET_ENV_PATH="${POLYMARKET_ENV_PATH:-$RUNTIME_ROOT/polymarket.env}"
HOST="${SIGNAL_DECK_DASHBOARD_HOST:-127.0.0.1}"
PORT="${SIGNAL_DECK_DASHBOARD_PORT:-8787}"

mkdir -p "$LOG_DIR"

cd "$RUNTIME_ROOT"
export SIGNAL_DECK_LOG_DIR="$LOG_DIR"
export PYTHONPATH="$RUNTIME_ROOT${PYTHONPATH:+:$PYTHONPATH}"

if [ -f "$TELEGRAM_ENV_PATH" ]; then
  # shellcheck disable=SC1090
  . "$TELEGRAM_ENV_PATH"
fi

if [ -f "$POLYMARKET_ENV_PATH" ]; then
  # shellcheck disable=SC1090
  . "$POLYMARKET_ENV_PATH"
fi

exec "$PYTHON_BIN" "$SCRIPT_PATH" --host "$HOST" --port "$PORT"
