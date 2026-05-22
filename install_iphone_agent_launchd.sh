#!/bin/sh
set -eu

ROOT="$(cd "$(dirname "$0")" && pwd)"
RUNTIME_ROOT="$HOME/.signal-deck/runtime"
RUNTIME_APP_ROOT="$RUNTIME_ROOT/iphone_agent_app"
LOG_DIR="$HOME/.signal-deck/logs"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
LABEL="com.haihan.signaldeck.iphoneagent"
PLIST_PATH="$LAUNCH_AGENTS_DIR/$LABEL.plist"
WRAPPER_PATH="$RUNTIME_ROOT/run_iphone_agent.sh"
CONFIG_PATH="${IPHONE_AGENT_CONFIG:-$RUNTIME_ROOT/iphone_agent_config.json}"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"
HOST="${IPHONE_AGENT_HOST:-0.0.0.0}"
PORT="${IPHONE_AGENT_PORT:-8797}"
UID_VALUE="$(id -u)"

mkdir -p "$RUNTIME_ROOT" "$RUNTIME_APP_ROOT" "$LOG_DIR" "$LAUNCH_AGENTS_DIR"

for file in \
  iphone_agent.py \
  dryrun_recorder.py \
  dashboard_server.py \
  discover_sources.py \
  live_experiment_signal.py \
  signal_engine.py \
  telegram_bot_service.py \
  stock_paper_trader.py
do
  if [ -f "$ROOT/$file" ]; then
    cp "$ROOT/$file" "$RUNTIME_APP_ROOT/$file"
  fi
done

for dir in job_apply_agent daily_ops_agent; do
  if [ -d "$ROOT/$dir" ]; then
    rm -rf "$RUNTIME_APP_ROOT/$dir"
    cp -R "$ROOT/$dir" "$RUNTIME_APP_ROOT/$dir"
  fi
done

if [ ! -f "$CONFIG_PATH" ]; then
  "$PYTHON_BIN" "$RUNTIME_APP_ROOT/iphone_agent.py" --config "$CONFIG_PATH" init --host "$HOST" --port "$PORT"
else
  "$PYTHON_BIN" "$RUNTIME_APP_ROOT/iphone_agent.py" --config "$CONFIG_PATH" migrate-config
fi

cat > "$WRAPPER_PATH" <<EOF
#!/bin/sh
set -eu

RUNTIME_APP_ROOT="$RUNTIME_APP_ROOT"
CONFIG_PATH="$CONFIG_PATH"
PYTHON_BIN="$PYTHON_BIN"

cd "\$RUNTIME_APP_ROOT"
exec "\$PYTHON_BIN" "\$RUNTIME_APP_ROOT/iphone_agent.py" --config "\$CONFIG_PATH" serve
EOF

chmod +x "$WRAPPER_PATH"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/sh</string>
    <string>$WRAPPER_PATH</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$RUNTIME_APP_ROOT</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/iphone_agent.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/iphone_agent.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$UID_VALUE" "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID_VALUE" "$PLIST_PATH"
launchctl kickstart -k "gui/$UID_VALUE/$LABEL"

echo "Installed LaunchAgent: $LABEL"
echo "Plist: $PLIST_PATH"
echo "Runtime app: $RUNTIME_APP_ROOT"
echo "Config: $CONFIG_PATH"
echo "Logs: $LOG_DIR/iphone_agent.log"
echo "Use this command to print a same-Wi-Fi iPhone Shortcut URL:"
echo "  $PYTHON_BIN \"$RUNTIME_APP_ROOT/iphone_agent.py\" --config \"$CONFIG_PATH\" shortcut-url"
