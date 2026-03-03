# Signal Deck

Signal Deck is a local signal-analysis toolkit for event contracts.

It combines:
- market prices (Kalshi / Polymarket)
- live game state from ESPN
- a simple signal model based on live probability + time remaining

It is **signal-only** and does **not** place orders.

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

## Main Files

- `signal_engine.py`: core signal computation
- `realtime_signal.py`: generic JSON endpoint polling signal runner
- `live_experiment_signal.py`: provider-specific realtime runner (`kalshi_espn`, `polymarket_espn`)
- `discover_sources.py`: discover ESPN/Kalshi/Polymarket IDs
- `dashboard_server.py`: local web API + dashboard host
- `web/index.html`: dashboard UI

## Common Workflow

1. In dashboard, load/select an ESPN event.
2. Autofill market for the selected provider.
3. Keep `Require Live` enabled if you only want in-game signals.
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
