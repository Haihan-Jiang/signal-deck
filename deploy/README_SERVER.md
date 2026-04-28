# Linux Server Deployment

This project can be packaged for a remote Linux server, but it should only be
used in an environment where Polymarket trading is actually permitted.

The deployment package keeps the repository safe by default:

- `dryrun` runs the conservative strategy loop
- `telegrambot` replies to Telegram commands
- `dashboard` serves the local web UI
- execution mode is expected to stay `armed` until you explicitly implement and
  enable a real live order path

## Conservative Strategy

The current runtime preset is:

- `time_left <= 180`
- `lead >= 7`
- `p in [0.82, 0.98]`
- `min_edge = 0.03`
- `max_buy = 0.89`
- `fee_total = 0.02`

## Files

- `install_linux_services.sh`: install `systemd --user` services
- `run_dashboard_server.sh`: dashboard wrapper
- `deploy/polymarket.env.example`: execution env template
- `deploy/telegram.env.example`: Telegram env template
- `deploy/OCI_STEP_BY_STEP.md`: step-by-step OCI deployment guide
- `deploy/GCP_COMPUTE_STEP_BY_STEP.md`: step-by-step Google Cloud Compute Engine deployment guide

## Suggested Server Setup

1. Install Python 3.9+ and required dependencies.
2. Copy the repo to the server.
3. Copy env templates into runtime:

```bash
mkdir -p ~/.signal-deck/runtime
cp deploy/polymarket.env.example ~/.signal-deck/runtime/polymarket.env
cp deploy/telegram.env.example ~/.signal-deck/runtime/telegram.env
```

4. Edit those files with real values.
5. Run the read-only probe:

```bash
python3 probe_polymarket_api.py --persist-api-creds
```

6. Install services:

```bash
SIGNAL_DECK_DASHBOARD_HOST=0.0.0.0 \
SIGNAL_DECK_DASHBOARD_PORT=8787 \
SIGNAL_DECK_LOOP_INTERVAL=5 \
./install_linux_services.sh
```

7. Verify:

```bash
systemctl --user status polymarket-autotrader-dryrun.service
systemctl --user status polymarket-autotrader-telegrambot.service
systemctl --user status polymarket-autotrader-dashboard.service
```

## Logs

- `~/.signal-deck/logs/dryrun_launchd.log`
- `~/.signal-deck/logs/telegram_bot.log`
- `~/.signal-deck/logs/polymarket_execution.csv`
- `~/.signal-deck/logs/polymarket_probe.json`

## Notes

- This installer uses `systemd --user`, not root services.
- If you want services to survive logout, you may also need:

```bash
loginctl enable-linger "$USER"
```

- The installer does not enable real Polymarket order submission.
- `armed` is the intended remote default until a compliant live order path is
  implemented and verified.
