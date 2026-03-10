#!/bin/sh
set -eu

ROOT="/Users/haihan/Documents/New project"
RUNTIME_ROOT="$HOME/.signal-deck/runtime"
SHARED_LOG_DIR="$HOME/.signal-deck/logs"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
LABEL="com.haihan.signaldeck.dryrun"
PLIST_PATH="$LAUNCH_AGENTS_DIR/$LABEL.plist"
WRAPPER_PATH="$RUNTIME_ROOT/run_dryrun_job.sh"
PYTHON_BIN="/usr/bin/python3"
UID_VALUE="$(id -u)"

mkdir -p "$RUNTIME_ROOT" "$SHARED_LOG_DIR" "$LAUNCH_AGENTS_DIR"

for file in dashboard_server.py dryrun_recorder.py live_experiment_signal.py signal_engine.py run_dryrun_job.sh; do
  cp "$ROOT/$file" "$RUNTIME_ROOT/$file"
done

chmod +x "$RUNTIME_ROOT/dryrun_recorder.py" "$RUNTIME_ROOT/live_experiment_signal.py" "$RUNTIME_ROOT/signal_engine.py" "$WRAPPER_PATH"

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
  <key>EnvironmentVariables</key>
  <dict>
    <key>RUNTIME_ROOT</key>
    <string>$RUNTIME_ROOT</string>
    <key>SIGNAL_DECK_LOG_DIR</key>
    <string>$SHARED_LOG_DIR</string>
    <key>PYTHON_BIN</key>
    <string>$PYTHON_BIN</string>
  </dict>
  <key>WorkingDirectory</key>
  <string>$RUNTIME_ROOT</string>
  <key>RunAtLoad</key>
  <true/>
  <key>StartInterval</key>
  <integer>120</integer>
  <key>StandardOutPath</key>
  <string>$SHARED_LOG_DIR/dryrun_launchd.log</string>
  <key>StandardErrorPath</key>
  <string>$SHARED_LOG_DIR/dryrun_launchd.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$UID_VALUE" "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID_VALUE" "$PLIST_PATH"
launchctl kickstart -k "gui/$UID_VALUE/$LABEL"

echo "Installed LaunchAgent: $LABEL"
echo "Plist: $PLIST_PATH"
echo "Runtime: $RUNTIME_ROOT"
echo "Logs: $SHARED_LOG_DIR"
