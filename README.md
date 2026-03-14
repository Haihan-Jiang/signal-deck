# Polymarket Auto Trader

Polymarket Auto Trader is a local trading and signal-analysis toolkit for event contracts.

It combines:
- market prices (Kalshi / Polymarket)
- live game state from ESPN
- a simple signal model based on live probability + time remaining

Execution is server-side and mode-gated:
- `paper`: record order intents only, never place real orders
- `armed`: validate and record intents, but still block real orders
- `live`: reserved for real order placement; currently scaffolded but intentionally blocked until execution wiring is implemented

## Features

- Realtime signal engine (`BUY_YES` / `BUY_NO` / `NO_TRADE` / `WAITING`)
- Odds-to-probability conversion (decimal / American)
- Web dashboard for configuration and monitoring
- One-click market autofill from ESPN event
- Team-pair filtering for market discovery

## Requirements

- Python 3.9+
- Internet access for market/sports APIs

## Quick Start

```bash
cd "/Users/haihan/Documents/New project"
python3 dashboard_server.py --host 127.0.0.1 --port 8787
```

Open: <http://127.0.0.1:8787>

Hotreload (dev):

```bash
cd "/Users/haihan/Documents/New project"
python3 dashboard_server.py --host 127.0.0.1 --port 8787 --hotreload
```

With `--hotreload`, backend files and `web/index.html` changes trigger auto-restart, and the page auto-refreshes on localhost.

## Main Files

- `signal_engine.py`: core signal computation
- `realtime_signal.py`: generic JSON endpoint polling signal runner
- `live_experiment_signal.py`: provider-specific realtime runner (`kalshi_espn`, `polymarket_espn`)
- `dryrun_recorder.py`: scheduled dry-run recorder and Telegram alert sender
- `polymarket_executor.py`: server-side execution logger with `paper / armed / live` modes
- `discover_sources.py`: discover ESPN/Kalshi/Polymarket IDs
- `dashboard_server.py`: local web API + dashboard host
- `web/index.html`: dashboard UI

## Common Workflow

1. In dashboard, load/select an ESPN event.
2. Autofill market for the selected provider.
3. Keep `Require Live` enabled if you only want in-game signals.

## Telegram Alerts

The scheduled runner can send phone alerts through Telegram Bot when a new
`GUESS` signal opens under the current strategy preset.

Setup:

1. Create a bot with `@BotFather` and get the bot token.
2. Send `/start` to the bot from the Telegram account that should receive alerts.
3. Get your `chat_id` with:

```bash
curl "https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates"
```

4. Put the credentials into `~/.signal-deck/runtime/telegram.env`:

```bash
export SIGNAL_DECK_TELEGRAM_BOT_TOKEN="<YOUR_TOKEN>"
export SIGNAL_DECK_TELEGRAM_CHAT_ID="<YOUR_CHAT_ID>"
export SIGNAL_DECK_TELEGRAM_CHAT_IDS="<PERSONAL_OR_GROUP_IDS_COMMA_SEPARATED>"
```

The launchd dry-run wrapper reads that file automatically.

The scheduled alert interval is controlled by `install_dryrun_launchd.sh`.
It runs as a persistent background loop. Default is `5s`, and you can override it
when reinstalling:

```bash
SIGNAL_DECK_LOOP_INTERVAL=10 ./install_dryrun_launchd.sh
```

## Execution Modes

The backend execution skeleton reads `~/.signal-deck/runtime/polymarket.env`.

Example:

```bash
export SIGNAL_DECK_EXECUTION_MODE="paper"
export POLYMARKET_CLOB_HOST="https://clob.polymarket.com"
export POLYMARKET_CHAIN_ID="137"
```

Optional live credentials are read from the same file:

```bash
export POLYMARKET_PRIVATE_KEY="..."
export POLYMARKET_PROXY_ADDRESS="..."
export POLYMARKET_API_KEY="..."
export POLYMARKET_API_SECRET="..."
export POLYMARKET_API_PASSPHRASE="..."
```

Current behavior:

- `paper`: writes a row to `~/.signal-deck/logs/polymarket_execution.csv`
- `armed`: writes a validated intent row, but still does not transmit an order
- `live`: checks that credentials exist, then hard-blocks with `live_not_implemented`

Execution rows are available over:

- `GET /api/execution/latest`
- `GET /logs/polymarket_execution.csv`

## Telegram Commands

There is also a separate Telegram bot command service for group/private chat
replies. It supports:

- `/start`
- `/help`
- `/status`
- `/lastsignal`
- `/botstatus`
- `/chatid`

Install or refresh the bot service with:

```bash
./install_telegram_bot_launchd.sh
```

The bot service reads the same `~/.signal-deck/runtime/telegram.env` file and
replies from groups or private chats through Telegram `getUpdates`.
## CLI Examples

Single-shot signal with direct probability:

```bash
./signal_engine.py \
  --p-live 62 \
  --time-left 28 \
  --time-total 90 \
  --a-yes 0.55 \
  --a-no 0.47
```

Realtime from custom JSON endpoint:

```bash
./realtime_signal.py \
  --url "https://your-source/snapshot" \
  --interval 2 \
  --json
```

## Notes

- The current repository is safe-by-default because execution defaults to `paper`.
- Validate API data quality, market mapping, fees, and execution costs before enabling any live path.
