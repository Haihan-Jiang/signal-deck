# Signal Deck

Signal Deck is a local signal-analysis toolkit for event contracts.

It combines:
- market prices (Kalshi / Polymarket)
- live game state from ESPN
- a simple signal model based on live probability + time remaining

It is **signal-only** and does **not** place orders.

The repository also includes a separate lowest-cost stock paper-trading runner
for Alpaca paper accounts. That stock runner is isolated from the event-contract
signal tools and refuses to use Alpaca's live endpoint.

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
- `stock_paper_trader.py`: lowest-cost Alpaca stock paper-trading runner using free IEX data
- `dryrun_recorder.py`: scheduled dry-run recorder and Telegram alert sender
- `discover_sources.py`: discover ESPN/Kalshi/Polymarket IDs
- `dashboard_server.py`: local web API + dashboard host
- `web/index.html`: dashboard UI

## Lowest-Cost Stock Paper Trading

This path uses:

- Alpaca paper trading API for simulated order submission
- Alpaca's free IEX stock data feed by default
- Python standard library only; no paid data subscription or package install
- dry-run mode by default

Create `~/.signal-deck/runtime/alpaca.env`:

```bash
export APCA_API_KEY_ID="<YOUR_ALPACA_PAPER_KEY>"
export APCA_API_SECRET_KEY="<YOUR_ALPACA_PAPER_SECRET>"
export ALPACA_PAPER_BASE_URL="https://paper-api.alpaca.markets"
export ALPACA_DATA_FEED="iex"
```

Evaluate one symbol without placing any paper order:

```bash
python3 stock_paper_trader.py --symbol SPY --max-notional 10
```

Submit simulated paper orders when the strategy has a BUY or SELL signal:

```bash
python3 stock_paper_trader.py --symbol SPY --mode paper --max-notional 10
```

Run a simple polling loop:

```bash
python3 stock_paper_trader.py \
  --symbol SPY \
  --mode paper \
  --max-notional 10 \
  --loop \
  --interval 60
```

Use Alpaca's IEX WebSocket stream instead of REST polling:

```bash
python3 stock_paper_trader.py \
  --symbol SPY \
  --data-mode stream \
  --max-notional 10
```

Stream mode evaluates on Alpaca's live `1Min` bar events and keeps the latest
quote from the same WebSocket connection for spread checks.

Run the WebSocket stream continuously and submit simulated paper orders:

```bash
python3 stock_paper_trader.py \
  --symbol SPY \
  --data-mode stream \
  --mode paper \
  --max-notional 10 \
  --loop
```

The default strategy is intentionally small: it buys with up to `--max-notional`
when the short moving average is above the long moving average, sells the current
paper position when the short moving average falls below the long moving average,
skips wide spreads, skips duplicate open orders, and does not submit while the
market is closed unless `--allow-closed-market` is set.

JSONL audit logs are written to:

```text
~/.signal-deck/logs/stock_paper_trades.jsonl
```

Each log row includes timing fields for the market event timestamp, account-state
checks, signal computation, and paper order submission response time.

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
4. Start polling.

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

- This repository is for analysis/experimentation.
- Validate API data quality and costs before any real-world use.
