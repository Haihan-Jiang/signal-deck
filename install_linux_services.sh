#!/bin/sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
RUNTIME_ROOT="${RUNTIME_ROOT:-$HOME/.signal-deck/runtime}"
SHARED_LOG_DIR="${SIGNAL_DECK_LOG_DIR:-$HOME/.signal-deck/logs}"
SYSTEMD_USER_DIR="${SYSTEMD_USER_DIR:-$HOME/.config/systemd/user}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
LOOP_INTERVAL="${SIGNAL_DECK_LOOP_INTERVAL:-5}"
DASHBOARD_HOST="${SIGNAL_DECK_DASHBOARD_HOST:-127.0.0.1}"
DASHBOARD_PORT="${SIGNAL_DECK_DASHBOARD_PORT:-8787}"
RUN_TZ="${SIGNAL_DECK_RUN_TZ:-America/Los_Angeles}"

mkdir -p "$RUNTIME_ROOT" "$SHARED_LOG_DIR" "$SYSTEMD_USER_DIR" "$RUNTIME_ROOT/web"

for file in \
  dashboard_server.py \
  dryrun_recorder.py \
  live_experiment_signal.py \
  polymarket_executor.py \
  probe_polymarket_api.py \
  run_dashboard_server.sh \
  run_dryrun_daemon.sh \
  run_dryrun_job.sh \
  run_telegram_bot.sh \
  signal_engine.py \
  telegram_bot_service.py; do
  cp "$ROOT/$file" "$RUNTIME_ROOT/$file"
done

cp "$ROOT/web/index.html" "$RUNTIME_ROOT/web/index.html"

chmod +x \
  "$RUNTIME_ROOT/dryrun_recorder.py" \
  "$RUNTIME_ROOT/live_experiment_signal.py" \
  "$RUNTIME_ROOT/probe_polymarket_api.py" \
  "$RUNTIME_ROOT/run_dashboard_server.sh" \
  "$RUNTIME_ROOT/run_dryrun_daemon.sh" \
  "$RUNTIME_ROOT/run_dryrun_job.sh" \
  "$RUNTIME_ROOT/run_telegram_bot.sh" \
  "$RUNTIME_ROOT/signal_engine.py" \
  "$RUNTIME_ROOT/telegram_bot_service.py"

cat > "$SYSTEMD_USER_DIR/polymarket-autotrader-dryrun.service" <<EOF
[Unit]
Description=Polymarket Auto Trader dryrun daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$RUNTIME_ROOT
ExecStart=/bin/sh $RUNTIME_ROOT/run_dryrun_daemon.sh
Restart=always
RestartSec=2
Environment=RUNTIME_ROOT=$RUNTIME_ROOT
Environment=SIGNAL_DECK_LOG_DIR=$SHARED_LOG_DIR
Environment=PYTHON_BIN=$PYTHON_BIN
Environment=SIGNAL_DECK_LOOP_INTERVAL=$LOOP_INTERVAL
Environment=SIGNAL_DECK_RUN_TZ=$RUN_TZ

[Install]
WantedBy=default.target
EOF

cat > "$SYSTEMD_USER_DIR/polymarket-autotrader-telegrambot.service" <<EOF
[Unit]
Description=Polymarket Auto Trader Telegram bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$RUNTIME_ROOT
ExecStart=/bin/sh $RUNTIME_ROOT/run_telegram_bot.sh
Restart=always
RestartSec=2
Environment=RUNTIME_ROOT=$RUNTIME_ROOT
Environment=SIGNAL_DECK_LOG_DIR=$SHARED_LOG_DIR
Environment=PYTHON_BIN=$PYTHON_BIN

[Install]
WantedBy=default.target
EOF

cat > "$SYSTEMD_USER_DIR/polymarket-autotrader-dashboard.service" <<EOF
[Unit]
Description=Polymarket Auto Trader dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$RUNTIME_ROOT
ExecStart=/bin/sh $RUNTIME_ROOT/run_dashboard_server.sh
Restart=always
RestartSec=2
Environment=RUNTIME_ROOT=$RUNTIME_ROOT
Environment=SIGNAL_DECK_LOG_DIR=$SHARED_LOG_DIR
Environment=PYTHON_BIN=$PYTHON_BIN
Environment=SIGNAL_DECK_DASHBOARD_HOST=$DASHBOARD_HOST
Environment=SIGNAL_DECK_DASHBOARD_PORT=$DASHBOARD_PORT

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now \
  polymarket-autotrader-dryrun.service \
  polymarket-autotrader-telegrambot.service \
  polymarket-autotrader-dashboard.service

echo "Installed systemd user services:"
echo "  polymarket-autotrader-dryrun.service"
echo "  polymarket-autotrader-telegrambot.service"
echo "  polymarket-autotrader-dashboard.service"
echo "Runtime: $RUNTIME_ROOT"
echo "Logs: $SHARED_LOG_DIR"
echo "Dashboard: http://$DASHBOARD_HOST:$DASHBOARD_PORT"
echo "Dryrun loop interval: ${LOOP_INTERVAL}s"
echo "Dryrun run timezone: ${RUN_TZ}"
