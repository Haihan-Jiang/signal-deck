#!/bin/sh
set -eu

ROOT="$(cd "$(dirname "$0")" && pwd)"
RUNTIME_ROOT="$HOME/.codex/session-context/runtime"
CONTEXT_ROOT="$HOME/.codex/session-context"
LOG_DIR="$CONTEXT_ROOT/logs"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
LABEL="com.haihan.codex.sessioncontext"
PLIST_PATH="$LAUNCH_AGENTS_DIR/$LABEL.plist"
WRAPPER_PATH="$RUNTIME_ROOT/run_codex_session_context.sh"
TOOL_PATH="$RUNTIME_ROOT/codex_session_context.py"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"
INTERVAL_SECONDS="${CODEX_SESSION_CONTEXT_INTERVAL:-300}"
DAYS="${CODEX_SESSION_CONTEXT_DAYS:-30}"
MAX_SESSIONS="${CODEX_SESSION_CONTEXT_MAX_SESSIONS:-250}"
UID_VALUE="$(id -u)"

mkdir -p "$RUNTIME_ROOT" "$CONTEXT_ROOT" "$LOG_DIR" "$LAUNCH_AGENTS_DIR"
cp "$ROOT/tools/codex_session_context.py" "$TOOL_PATH"
chmod +x "$TOOL_PATH"

cat > "$WRAPPER_PATH" <<EOF
#!/bin/sh
set -eu

exec "$PYTHON_BIN" "$TOOL_PATH" --output-root "$CONTEXT_ROOT" scan --days "$DAYS" --max-sessions "$MAX_SESSIONS"
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
  <string>$RUNTIME_ROOT</string>
  <key>RunAtLoad</key>
  <true/>
  <key>StartInterval</key>
  <integer>$INTERVAL_SECONDS</integer>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/launchd.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/launchd.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$UID_VALUE" "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID_VALUE" "$PLIST_PATH"
launchctl kickstart -k "gui/$UID_VALUE/$LABEL"

echo "Installed LaunchAgent: $LABEL"
echo "Plist: $PLIST_PATH"
echo "Runtime tool: $TOOL_PATH"
echo "Context root: $CONTEXT_ROOT"
echo "Latest resume: $CONTEXT_ROOT/latest_resume.md"
echo "Logs: $LOG_DIR/launchd.log"
echo "IntervalSeconds: $INTERVAL_SECONDS"
