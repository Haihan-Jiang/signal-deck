#!/usr/bin/env python3
"""Dry-run recorder for the winner-only strategy.

This script does not place any orders. It snapshots the current NBA games,
evaluates the local winner strategy, and appends only changed rows into a CSV
that can be opened directly in Excel. A human-readable TXT snapshot is also
written on every run.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from dashboard_server import build_history_gate, build_winner_once, discover_espn
from live_experiment_signal import get_espn_state


ROOT = Path(__file__).resolve().parent
DEFAULT_LOG_DIR = Path(os.environ.get("SIGNAL_DECK_LOG_DIR", str(Path.home() / ".signal-deck" / "logs"))).expanduser()
DEFAULT_CSV_PATH = DEFAULT_LOG_DIR / "dryrun_signals.csv"
DEFAULT_TXT_PATH = DEFAULT_LOG_DIR / "dryrun_latest.txt"
DEFAULT_STATE_PATH = DEFAULT_LOG_DIR / "dryrun_state.json"
DEFAULT_TRADE_CSV_PATH = DEFAULT_LOG_DIR / "dryrun_trades.csv"
DEFAULT_TRADE_STATE_PATH = DEFAULT_LOG_DIR / "dryrun_trade_state.json"
DEFAULT_TRADE_BUDGET = 100.0

CSV_COLUMNS = [
    "run_ts",
    "row_type",
    "row_key",
    "sport",
    "league",
    "event_id",
    "rivalry",
    "espn_status",
    "state",
    "suggested_action",
    "action",
    "guess_side",
    "guess_team",
    "guess_prob",
    "lead",
    "time_left",
    "home_score",
    "away_score",
    "break_even_buy_price",
    "recommended_max_buy_price",
    "target_max_buy_price",
    "entry_price",
    "edge",
    "provider",
    "market",
    "reason",
    "gate_passed",
    "gate_trigger_rate_game",
    "gate_first_signal_hit_rate",
]

TRADE_COLUMNS = [
    "run_ts",
    "trade_phase",
    "event_id",
    "rivalry",
    "espn_status",
    "guess_side",
    "guess_team",
    "suggested_action",
    "contracts",
    "entry_price",
    "fee_total",
    "opened_at",
    "closed_at",
    "result",
    "final_winner",
    "home_score",
    "away_score",
    "pnl_per_contract",
    "total_pnl",
    "reason",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record dry-run winner signals to CSV/TXT.")
    parser.add_argument("--sport", default="basketball")
    parser.add_argument("--league", default="nba")
    parser.add_argument("--limit", type=int, default=20, help="Max ESPN events to inspect per run.")
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--require-live", dest="require_live", action="store_true")
    parser.add_argument("--no-require-live", dest="require_live", action="store_false")
    parser.add_argument("--fallback-pre", dest="fallback_pre", action="store_true")
    parser.add_argument("--no-fallback-pre", dest="fallback_pre", action="store_false")
    parser.add_argument("--winner-max-time-left", type=float, default=360.0)
    parser.add_argument("--winner-min-lead", type=float, default=10.0)
    parser.add_argument("--winner-p-min", type=float, default=0.80)
    parser.add_argument("--winner-p-max", type=float, default=0.98)
    parser.add_argument("--winner-min-edge", type=float, default=0.025)
    parser.add_argument("--winner-max-buy-price", type=float, default=0.91)
    parser.add_argument("--fee-total", type=float, default=0.02)
    parser.add_argument("--lookback-days", type=int, default=30)
    parser.add_argument("--min-games", type=int, default=80)
    parser.add_argument("--min-trigger-games", type=int, default=20)
    parser.add_argument("--min-hit-rate", type=float, default=0.93)
    parser.add_argument("--csv-path", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--txt-path", type=Path, default=DEFAULT_TXT_PATH)
    parser.add_argument("--state-path", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--trade-csv-path", type=Path, default=DEFAULT_TRADE_CSV_PATH)
    parser.add_argument("--trade-state-path", type=Path, default=DEFAULT_TRADE_STATE_PATH)
    parser.add_argument("--contracts", type=float, default=None, help="Fixed theoretical contracts per trade.")
    parser.add_argument("--trade-budget", type=float, default=DEFAULT_TRADE_BUDGET, help="Theoretical max loss budget per trade.")
    parser.add_argument("--telegram-bot-token", default=os.environ.get("SIGNAL_DECK_TELEGRAM_BOT_TOKEN", ""))
    parser.add_argument("--telegram-chat-id", default=os.environ.get("SIGNAL_DECK_TELEGRAM_CHAT_ID", ""))
    parser.add_argument("--telegram-chat-ids", default=os.environ.get("SIGNAL_DECK_TELEGRAM_CHAT_IDS", ""))
    parser.add_argument("--timezone", default="America/Los_Angeles")
    parser.add_argument("--disable-gate", action="store_true", help="Skip history gate and just record snapshots.")
    parser.set_defaults(require_live=True, fallback_pre=True)
    return parser


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def fmt_num(value: Any, digits: int = 4) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return ""


def now_local_iso(tz_name: str) -> str:
    return datetime.now(ZoneInfo(tz_name)).isoformat(timespec="seconds")


def normalize_reason(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).splitlines()).strip()


def display_action_label(action: Any, guess_team: Any) -> str:
    action_text = str(action or "").strip().upper()
    team_text = str(guess_team or "").strip().upper()
    if not action_text:
        return ""
    if action_text == "BUY_HOME" and team_text:
        return f"BUY {team_text}"
    if action_text == "BUY_AWAY" and team_text:
        return f"BUY {team_text}"
    return action_text


def make_signature(row: dict[str, str]) -> str:
    stable = {key: value for key, value in row.items() if key != "run_ts"}
    compact = json.dumps(stable, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha1(compact.encode("utf-8")).hexdigest()[:16]


def load_state(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    rows = payload.get("rows")
    if not isinstance(rows, dict):
        return {}
    return {str(key): str(value) for key, value in rows.items()}


def save_state(path: Path, rows: dict[str, str]) -> None:
    ensure_parent(path)
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "rows": rows,
    }
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def append_rows(csv_path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    ensure_parent(csv_path)
    write_header = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        if write_header:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


def append_trade_rows(csv_path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    ensure_parent(csv_path)
    write_header = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=TRADE_COLUMNS)
        if write_header:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_gate_row(run_ts: str, args: argparse.Namespace, gate: dict[str, Any]) -> dict[str, str]:
    metrics = gate.get("metrics") if isinstance(gate.get("metrics"), dict) else {}
    gate_info = gate.get("gate") if isinstance(gate.get("gate"), dict) else {}
    reasons = gate_info.get("reasons")
    reason_text = ""
    if isinstance(reasons, list) and reasons:
        reason_text = " | ".join(str(item) for item in reasons)
    else:
        reason_text = str(gate_info.get("message") or "")
    row = {
        "run_ts": run_ts,
        "row_type": "gate",
        "row_key": "gate:robust_history_gate",
        "sport": args.sport,
        "league": args.league,
        "event_id": "",
        "rivalry": "",
        "espn_status": "",
        "state": "PASS" if gate_info.get("passed") else "BLOCK",
        "suggested_action": "",
        "action": "",
        "guess_side": "",
        "guess_team": "",
        "guess_prob": "",
        "lead": "",
        "time_left": "",
        "home_score": "",
        "away_score": "",
        "break_even_buy_price": "",
        "recommended_max_buy_price": "",
        "target_max_buy_price": "",
        "entry_price": "",
        "edge": "",
        "provider": "",
        "market": "",
        "reason": reason_text,
        "gate_passed": "1" if gate_info.get("passed") else "0",
        "gate_trigger_rate_game": fmt_num(metrics.get("trigger_rate_game"), 4),
        "gate_first_signal_hit_rate": fmt_num(metrics.get("first_signal_hit_rate"), 4),
    }
    return row


def build_system_row(run_ts: str, args: argparse.Namespace, state_text: str, reason: str) -> dict[str, str]:
    return {
        "run_ts": run_ts,
        "row_type": "system",
        "row_key": f"system:{state_text}",
        "sport": args.sport,
        "league": args.league,
        "event_id": "",
        "rivalry": "",
        "espn_status": "",
        "state": state_text,
        "suggested_action": "",
        "action": "",
        "guess_side": "",
        "guess_team": "",
        "guess_prob": "",
        "lead": "",
        "time_left": "",
        "home_score": "",
        "away_score": "",
        "break_even_buy_price": "",
        "recommended_max_buy_price": "",
        "target_max_buy_price": "",
        "entry_price": "",
        "edge": "",
        "provider": "",
        "market": "",
        "reason": reason,
        "gate_passed": "",
        "gate_trigger_rate_game": "",
        "gate_first_signal_hit_rate": "",
    }


def build_game_row(
    run_ts: str,
    args: argparse.Namespace,
    result: dict[str, Any],
    gate: dict[str, Any] | None,
) -> dict[str, str]:
    metrics = gate.get("metrics") if isinstance(gate, dict) and isinstance(gate.get("metrics"), dict) else {}
    gate_info = gate.get("gate") if isinstance(gate, dict) and isinstance(gate.get("gate"), dict) else {}
    event_id = str(result.get("espn_event_id") or "")
    row = {
        "run_ts": run_ts,
        "row_type": "game",
        "row_key": f"game:{event_id}",
        "sport": args.sport,
        "league": args.league,
        "event_id": event_id,
        "rivalry": str(result.get("rivalry") or ""),
        "espn_status": str(result.get("espn_status") or ""),
        "state": str(result.get("state") or ""),
        "suggested_action": str(result.get("suggested_action") or ""),
        "action": str(result.get("action") or ""),
        "guess_side": str(result.get("guess_side") or ""),
        "guess_team": str(result.get("guess_team") or ""),
        "guess_prob": fmt_num(result.get("guess_prob"), 4),
        "lead": fmt_num(result.get("lead"), 0),
        "time_left": fmt_num(result.get("time_left"), 0),
        "home_score": fmt_num(result.get("home_score"), 0),
        "away_score": fmt_num(result.get("away_score"), 0),
        "break_even_buy_price": fmt_num(result.get("break_even_buy_price"), 4),
        "recommended_max_buy_price": fmt_num(result.get("recommended_max_buy_price"), 4),
        "target_max_buy_price": fmt_num(result.get("target_max_buy_price"), 4),
        "entry_price": fmt_num(result.get("entry_price"), 4),
        "edge": fmt_num(result.get("edge"), 4),
        "provider": str(result.get("provider") or ""),
        "market": str(result.get("market") or ""),
        "reason": normalize_reason(result.get("reason")),
        "gate_passed": "1" if gate_info.get("passed") else "0" if gate_info else "",
        "gate_trigger_rate_game": fmt_num(metrics.get("trigger_rate_game"), 4),
        "gate_first_signal_hit_rate": fmt_num(metrics.get("first_signal_hit_rate"), 4),
    }
    return row


def load_trade_state(path: Path) -> tuple[dict[str, dict[str, Any]], set[str]]:
    if not path.exists():
        return {}, set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}, set()
    if not isinstance(payload, dict):
        return {}, set()

    raw_open_positions = payload.get("open_positions")
    open_positions: dict[str, dict[str, Any]] = {}
    if isinstance(raw_open_positions, dict):
        for key, value in raw_open_positions.items():
            if isinstance(value, dict):
                open_positions[str(key)] = dict(value)

    raw_closed = payload.get("closed_event_ids")
    closed_event_ids: set[str] = set()
    if isinstance(raw_closed, list):
        for value in raw_closed:
            closed_event_ids.add(str(value))
    return open_positions, closed_event_ids


def save_trade_state(
    path: Path,
    open_positions: dict[str, dict[str, Any]],
    closed_event_ids: set[str],
    settings: dict[str, Any] | None = None,
) -> None:
    ensure_parent(path)
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "open_positions": open_positions,
        "closed_event_ids": sorted(closed_event_ids),
    }
    if settings:
        payload["settings"] = settings
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def resolve_final_winner(home_score: Any, away_score: Any) -> str:
    try:
        if home_score is None or away_score is None:
            return ""
        home = float(home_score)
        away = float(away_score)
    except (TypeError, ValueError):
        return ""
    if home > away:
        return "home"
    if away > home:
        return "away"
    return "tie"


def build_trade_open_row(run_ts: str, position: dict[str, Any]) -> dict[str, str]:
    return {
        "run_ts": run_ts,
        "trade_phase": "OPEN",
        "event_id": str(position.get("event_id") or ""),
        "rivalry": str(position.get("rivalry") or ""),
        "espn_status": str(position.get("espn_status") or ""),
        "guess_side": str(position.get("guess_side") or ""),
        "guess_team": str(position.get("guess_team") or ""),
        "suggested_action": str(position.get("suggested_action") or ""),
        "contracts": fmt_num(position.get("contracts"), 2),
        "entry_price": fmt_num(position.get("entry_price"), 4),
        "fee_total": fmt_num(position.get("fee_total"), 4),
        "opened_at": str(position.get("opened_at") or run_ts),
        "closed_at": "",
        "result": "OPEN",
        "final_winner": "",
        "home_score": fmt_num(position.get("home_score"), 0),
        "away_score": fmt_num(position.get("away_score"), 0),
        "pnl_per_contract": "",
        "total_pnl": "",
        "reason": "首个 GUESS 信号，按 target_max_buy_price 进行理论开仓。",
    }


def build_trade_close_row(
    run_ts: str,
    position: dict[str, Any],
    espn: dict[str, Any],
    result: str,
    pnl_per_contract: float,
    total_pnl: float,
) -> dict[str, str]:
    return {
        "run_ts": run_ts,
        "trade_phase": "CLOSE",
        "event_id": str(position.get("event_id") or ""),
        "rivalry": str(position.get("rivalry") or espn.get("rivalry") or ""),
        "espn_status": str(espn.get("status_state") or ""),
        "guess_side": str(position.get("guess_side") or ""),
        "guess_team": str(position.get("guess_team") or ""),
        "suggested_action": str(position.get("suggested_action") or ""),
        "contracts": fmt_num(position.get("contracts"), 2),
        "entry_price": fmt_num(position.get("entry_price"), 4),
        "fee_total": fmt_num(position.get("fee_total"), 4),
        "opened_at": str(position.get("opened_at") or ""),
        "closed_at": run_ts,
        "result": result,
        "final_winner": resolve_final_winner(espn.get("home_score"), espn.get("away_score")),
        "home_score": fmt_num(espn.get("home_score"), 0),
        "away_score": fmt_num(espn.get("away_score"), 0),
        "pnl_per_contract": fmt_num(pnl_per_contract, 4),
        "total_pnl": fmt_num(total_pnl, 4),
        "reason": "比赛结束，按终场比分进行理论结算。",
    }


def parse_telegram_targets(value: Any) -> list[str]:
    if value is None:
        return []
    text = str(value).replace("\n", ",")
    parts = [item.strip() for item in text.split(",")]
    return [item for item in parts if item]


def resolve_telegram_chat_ids(args: argparse.Namespace) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in [getattr(args, "telegram_chat_ids", ""), getattr(args, "telegram_chat_id", "")]:
        for item in parse_telegram_targets(raw):
            if item in seen:
                continue
            seen.add(item)
            out.append(item)
    return out


def telegram_enabled(args: argparse.Namespace) -> bool:
    return bool(str(args.telegram_bot_token).strip() and resolve_telegram_chat_ids(args))


def build_telegram_signal_text(run_ts: str, args: argparse.Namespace, result: dict[str, Any], contracts: float) -> str:
    rivalry = str(result.get("rivalry") or result.get("espn_event_id") or "-")
    score = f"{fmt_num(result.get('away_score'), 0) or '-'} - {fmt_num(result.get('home_score'), 0) or '-'}"
    action_label = display_action_label(result.get("suggested_action"), result.get("guess_team")) or "-"
    lines = [
        "Signal Deck Alert",
        "strategy=max_profit_95",
        f"game={rivalry}",
        f"state={result.get('state') or '-'}",
        f"action={action_label}",
        f"guess_team={result.get('guess_team') or '-'}",
        f"guess_prob={fmt_num(result.get('guess_prob'), 4) or '-'}",
        f"lead={fmt_num(result.get('lead'), 0) or '-'}",
        f"time_left={fmt_num(result.get('time_left'), 0) or '-'}s",
        f"score(away-home)={score}",
        f"target_max_buy={fmt_num(result.get('target_max_buy_price'), 4) or '-'}",
        f"contracts={fmt_num(contracts, 2) or '-'}",
        f"reason={normalize_reason(result.get('reason')) or '-'}",
        f"run_ts={run_ts}",
    ]
    return "\n".join(lines)


def send_telegram_message(args: argparse.Namespace, text: str) -> None:
    if not telegram_enabled(args):
        return
    token = str(args.telegram_bot_token).strip()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    errors: list[str] = []
    for chat_id in resolve_telegram_chat_ids(args):
        payload = urlencode(
            {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": "true",
            }
        ).encode("utf-8")
        request = Request(url, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urlopen(request, timeout=args.timeout) as response:
            raw = response.read().decode("utf-8")
        reply = json.loads(raw)
        if not isinstance(reply, dict) or not reply.get("ok"):
            errors.append(f"{chat_id}: {raw}")
    if errors:
        raise RuntimeError("Telegram sendMessage failed: " + " | ".join(errors))


def settle_open_positions(
    args: argparse.Namespace,
    run_ts: str,
    open_positions: dict[str, dict[str, Any]],
    closed_event_ids: set[str],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    to_close: list[str] = []
    for event_id, position in list(open_positions.items()):
        try:
            espn = get_espn_state(
                sport=args.sport,
                league=args.league,
                event_id=event_id,
                timeout=args.timeout,
                yes_team="home",
                period_seconds=720.0,
                regulation_periods=4,
            )
        except Exception:
            continue
        if str(espn.get("status_state") or "").lower() != "post":
            continue

        final_winner = resolve_final_winner(espn.get("home_score"), espn.get("away_score"))
        guess_side = str(position.get("guess_side") or "")
        entry_price = float(position.get("entry_price") or 0.0)
        fee_total = float(position.get("fee_total") or args.fee_total)
        contracts = float(position.get("contracts") or args.contracts)
        if final_winner in {"home", "away"}:
            trade_result = "WIN" if guess_side == final_winner else "LOSS"
            if trade_result == "WIN":
                pnl_per_contract = 1.0 - entry_price - fee_total
            else:
                pnl_per_contract = -entry_price - fee_total
        else:
            trade_result = "VOID"
            pnl_per_contract = 0.0
        total_pnl = pnl_per_contract * contracts
        rows.append(build_trade_close_row(run_ts, position, espn, trade_result, pnl_per_contract, total_pnl))
        to_close.append(event_id)
        closed_event_ids.add(event_id)

    for event_id in to_close:
        open_positions.pop(event_id, None)
    return rows


def open_new_positions(
    args: argparse.Namespace,
    run_ts: str,
    results: list[dict[str, Any]],
    open_positions: dict[str, dict[str, Any]],
    closed_event_ids: set[str],
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    rows: list[dict[str, str]] = []
    opened_signals: list[dict[str, Any]] = []
    for result in results:
        event_id = str(result.get("espn_event_id") or "").strip()
        if not event_id or event_id in open_positions or event_id in closed_event_ids:
            continue
        if str(result.get("state") or "").upper() != "GUESS":
            continue
        target_max_buy_price = result.get("target_max_buy_price")
        try:
            entry_price = float(target_max_buy_price)
        except (TypeError, ValueError):
            continue
        if entry_price <= 0:
            continue
        max_loss_per_contract = entry_price + args.fee_total
        if max_loss_per_contract <= 0:
            continue
        if args.contracts is not None:
            contracts = float(args.contracts)
        else:
            contracts = float(int(args.trade_budget // max_loss_per_contract))
        if contracts <= 0:
            continue

        position = {
            "event_id": event_id,
            "rivalry": str(result.get("rivalry") or ""),
            "espn_status": str(result.get("espn_status") or ""),
            "guess_side": str(result.get("guess_side") or ""),
            "guess_team": str(result.get("guess_team") or ""),
            "suggested_action": str(result.get("suggested_action") or ""),
            "contracts": contracts,
            "entry_price": entry_price,
            "fee_total": args.fee_total,
            "opened_at": run_ts,
            "home_score": result.get("home_score"),
            "away_score": result.get("away_score"),
        }
        open_positions[event_id] = position
        rows.append(build_trade_open_row(run_ts, position))
        opened_signals.append(
            {
                "position": position,
                "result": result,
            }
        )
    return rows, opened_signals


def discover_candidate_events(args: argparse.Namespace) -> tuple[list[dict[str, Any]], str]:
    live_items = discover_espn(
        sport=args.sport,
        league=args.league,
        date="",
        state="in",
        query="",
        limit=max(1, args.limit),
    )
    if live_items:
        return live_items, "in"
    if args.fallback_pre:
        pre_items = discover_espn(
            sport=args.sport,
            league=args.league,
            date="",
            state="pre",
            query="",
            limit=max(1, args.limit),
        )
        return pre_items, "pre"
    return [], "in"


def build_gate_payload(args: argparse.Namespace) -> dict[str, Any]:
    return build_history_gate(
        {
            "sport": args.sport,
            "league": args.league,
            "timeout": args.timeout,
            "lookback_days": args.lookback_days,
            "min_games": args.min_games,
            "min_trigger_games": args.min_trigger_games,
            "min_first_hit_rate": args.min_hit_rate,
            "winner_max_time_left": args.winner_max_time_left,
            "winner_min_lead": args.winner_min_lead,
            "winner_p_min": args.winner_p_min,
            "winner_p_max": args.winner_p_max,
            "winner_min_edge": args.winner_min_edge,
            "fee_total": args.fee_total,
            "use_cache": True,
        }
    )


def build_game_payload(args: argparse.Namespace, event_id: str) -> dict[str, Any]:
    return build_winner_once(
        {
            "espn_sport": args.sport,
            "espn_league": args.league,
            "espn_event_id": event_id,
            "provider": "",
            "market": "",
            "yes_team": "home",
            "require_live": args.require_live,
            "timeout": args.timeout,
            "winner_max_time_left": args.winner_max_time_left,
            "winner_min_lead": args.winner_min_lead,
            "winner_p_min": args.winner_p_min,
            "winner_p_max": args.winner_p_max,
            "winner_min_edge": args.winner_min_edge,
            "winner_max_buy_price": args.winner_max_buy_price,
            "fee_total": args.fee_total,
        }
    )


def write_snapshot_text(
    txt_path: Path,
    run_ts: str,
    args: argparse.Namespace,
    gate: dict[str, Any] | None,
    game_rows: list[dict[str, str]],
    event_state: str,
) -> None:
    ensure_parent(txt_path)
    lines: list[str] = []
    lines.append(f"Generated At: {run_ts}")
    lines.append(f"Strategy: winner-only dry-run ({args.sport}/{args.league})")
    lines.append(
        "Rules: "
        f"time_left<={args.winner_max_time_left:.0f}s, "
        f"lead>={args.winner_min_lead:.0f}, "
        f"p=[{args.winner_p_min:.2f},{args.winner_p_max:.2f}], "
        f"min_edge={args.winner_min_edge:.3f}, "
        f"fee_total={args.fee_total:.3f}, "
        f"max_buy={args.winner_max_buy_price:.3f}"
    )
    if gate is not None:
        metrics = gate.get("metrics") if isinstance(gate.get("metrics"), dict) else {}
        gate_info = gate.get("gate") if isinstance(gate.get("gate"), dict) else {}
        lines.append(
            "Gate: "
            f"{'PASS' if gate_info.get('passed') else 'BLOCK'} | "
            f"trigger_games={metrics.get('trigger_games', '-')}/{metrics.get('games_analyzed', '-')} | "
            f"trigger_rate={fmt_num(metrics.get('trigger_rate_game'), 4)} | "
            f"first_hit_rate={fmt_num(metrics.get('first_signal_hit_rate'), 4)}"
        )
        reasons = gate_info.get("reasons")
        if isinstance(reasons, list) and reasons:
            lines.append("Gate Reasons: " + " | ".join(str(item) for item in reasons))
    lines.append(f"Event Source: {event_state}")
    lines.append("")
    if not game_rows:
        lines.append("No current rows.")
    else:
        for row in game_rows:
            lines.append(
                f"{row['rivalry'] or row['event_id']} | "
                f"state={row['state']} | "
                f"suggested={display_action_label(row['suggested_action'], row['guess_team']) or '-'} | "
                f"guess_p={row['guess_prob'] or '-'} | "
                f"lead={row['lead'] or '-'} | "
                f"time_left={row['time_left'] or '-'} | "
                f"target_max_buy={row['target_max_buy_price'] or '-'} | "
                f"reason={row['reason'] or '-'}"
            )
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = build_parser().parse_args()
    if args.contracts is not None and args.contracts <= 0:
        raise ValueError("contracts must be > 0.")
    if args.trade_budget <= 0:
        raise ValueError("trade_budget must be > 0.")
    run_ts = now_local_iso(args.timezone)

    gate_payload: dict[str, Any] | None = None
    rows: list[dict[str, str]] = []
    trade_rows: list[dict[str, str]] = []
    event_state = "in"
    open_positions, closed_event_ids = load_trade_state(args.trade_state_path)
    trade_settings = {
        "sizing_mode": "fixed_contracts" if args.contracts is not None else "trade_budget",
        "contracts": args.contracts,
        "trade_budget": args.trade_budget,
        "fee_total": args.fee_total,
    }
    trade_rows.extend(settle_open_positions(args, run_ts, open_positions, closed_event_ids))

    if not args.disable_gate:
        gate_payload = build_gate_payload(args)
        rows.append(build_gate_row(run_ts, args, gate_payload))
        gate_info = gate_payload.get("gate") if isinstance(gate_payload.get("gate"), dict) else {}
        if not gate_info.get("passed"):
            write_snapshot_text(args.txt_path, run_ts, args, gate_payload, [], event_state="blocked")
            previous_rows = load_state(args.state_path)
            current_rows = {row["row_key"]: make_signature(row) for row in rows}
            changed_rows = [row for row in rows if previous_rows.get(row["row_key"]) != current_rows[row["row_key"]]]
            append_rows(args.csv_path, changed_rows)
            append_trade_rows(args.trade_csv_path, trade_rows)
            save_state(args.state_path, current_rows)
            save_trade_state(args.trade_state_path, open_positions, closed_event_ids, settings=trade_settings)
            print(
                f"[{run_ts}] gate blocked, wrote {len(changed_rows)} changed row(s), "
                f"trade_rows={len(trade_rows)}"
            )
            return 0

    events, event_state = discover_candidate_events(args)
    if not events:
        rows.append(build_system_row(run_ts, args, "NO_GAMES", "No live/pre games found."))
        write_snapshot_text(args.txt_path, run_ts, args, gate_payload, [], event_state)
    else:
        game_rows: list[dict[str, str]] = []
        game_results: list[dict[str, Any]] = []
        for item in events:
            event_id = str(item.get("event_id") or "").strip()
            if not event_id:
                continue
            try:
                result = build_game_payload(args, event_id)
            except Exception as exc:
                rows.append(build_system_row(run_ts, args, f"ERROR:{event_id}", str(exc)))
                continue
            row = build_game_row(run_ts, args, result, gate_payload)
            rows.append(row)
            game_rows.append(row)
            game_results.append(result)
        new_trade_rows, opened_signals = open_new_positions(args, run_ts, game_results, open_positions, closed_event_ids)
        trade_rows.extend(new_trade_rows)
        for item in opened_signals:
            position = item.get("position") if isinstance(item.get("position"), dict) else {}
            result = item.get("result") if isinstance(item.get("result"), dict) else {}
            try:
                send_telegram_message(
                    args,
                    build_telegram_signal_text(
                        run_ts,
                        args,
                        result,
                        float(position.get("contracts") or 0.0),
                    ),
                )
            except Exception as exc:
                rows.append(
                    build_system_row(
                        run_ts,
                        args,
                        f"TELEGRAM_ERROR:{position.get('event_id') or result.get('espn_event_id') or ''}",
                        str(exc),
                    )
                )
        write_snapshot_text(args.txt_path, run_ts, args, gate_payload, game_rows, event_state)

    previous_rows = load_state(args.state_path)
    current_rows = {row["row_key"]: make_signature(row) for row in rows}
    changed_rows = [row for row in rows if previous_rows.get(row["row_key"]) != current_rows[row["row_key"]]]
    append_rows(args.csv_path, changed_rows)
    append_trade_rows(args.trade_csv_path, trade_rows)
    save_state(args.state_path, current_rows)
    save_trade_state(args.trade_state_path, open_positions, closed_event_ids, settings=trade_settings)
    print(
        f"[{run_ts}] events={len(rows)} changed_rows={len(changed_rows)} "
        f"trade_rows={len(trade_rows)} csv={args.csv_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
