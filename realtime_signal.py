#!/usr/bin/env python3
"""Realtime signal polling for event-contract style markets.

This tool only emits trading signals. It does NOT place orders.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime

from signal_engine import compute_signal, resolve_probability_values


def parse_number(value: object, field: str) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError(f"Field '{field}' is empty.")
        if text.endswith("%"):
            return float(text[:-1].strip()) / 100.0
        return float(text)
    raise ValueError(f"Field '{field}' must be numeric, got {type(value).__name__}.")


def get_nested(data: object, path: str) -> object:
    current = data
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            raise KeyError(path)
        current = current[key]
    return current


def get_required(data: object, path: str) -> object:
    try:
        return get_nested(data, path)
    except KeyError as exc:
        raise ValueError(f"Required field '{path}' was not found in snapshot JSON.") from exc


def get_optional(data: object, path: str) -> object | None:
    try:
        return get_nested(data, path)
    except KeyError:
        return None


def fetch_snapshot(url: str, timeout: float) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "signal-engine/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Snapshot payload must be a JSON object.")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Poll a JSON endpoint and emit realtime BUY_YES/BUY_NO/NO_TRADE signals."
    )

    parser.add_argument("--url", required=True, help="Snapshot JSON endpoint URL.")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds.")
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout in seconds.")
    parser.add_argument("--max-iterations", type=int, default=None, help="Stop after N polls.")
    parser.add_argument(
        "--changes-only",
        action="store_true",
        help="Only print when signal action changes.",
    )
    parser.add_argument("--json", action="store_true", help="Print one JSON line per signal.")

    parser.add_argument("--p-live-key", default="p_live", help="JSON key path for direct probability.")
    parser.add_argument("--yes-odds-key", default="yes_odds", help="JSON key path for YES odds.")
    parser.add_argument("--no-odds-key", default="no_odds", help="JSON key path for NO odds.")
    parser.add_argument(
        "--odds-format",
        choices=["decimal", "american"],
        default="decimal",
        help="Default odds format used by yes/no odds.",
    )
    parser.add_argument(
        "--odds-format-key",
        default=None,
        help="Optional JSON key path that overrides odds format per snapshot.",
    )

    parser.add_argument("--time-left-key", default="time_left", help="JSON key path for remaining time.")
    parser.add_argument("--time-total-key", default="time_total", help="JSON key path for total time.")
    parser.add_argument("--a-yes-key", default="a_yes", help="JSON key path for YES price.")
    parser.add_argument("--a-no-key", default="a_no", help="JSON key path for NO price.")

    parser.add_argument("--fee-open", type=float, default=0.01, help="Estimated open cost in dollars/contract.")
    parser.add_argument("--min-ev", type=float, default=0.03, help="Minimum EV edge required to trade.")
    parser.add_argument("--alpha", type=float, default=0.7, help="Time-shrink exponent for P_eff.")
    parser.add_argument("--roundtrip-cost", type=float, default=0.04, help="Estimated all-in roundtrip cost.")
    parser.add_argument("--spread-buffer", type=float, default=0.02, help="Extra spread buffer above costs.")

    parser.add_argument("--account-equity", type=float, default=None, help="Account equity for risk sizing.")
    parser.add_argument("--per-trade-risk-pct", type=float, default=0.0025, help="Max risk per trade as fraction of account.")
    parser.add_argument("--daily-stop-pct", type=float, default=0.01, help="Daily stop as fraction of account.")

    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.interval <= 0:
        raise SystemExit("Input error: --interval must be > 0.")
    if args.timeout <= 0:
        raise SystemExit("Input error: --timeout must be > 0.")
    if args.max_iterations is not None and args.max_iterations <= 0:
        raise SystemExit("Input error: --max-iterations must be > 0.")

    iteration = 0
    last_action: str | None = None

    while True:
        if args.max_iterations is not None and iteration >= args.max_iterations:
            break
        iteration += 1

        timestamp = datetime.now().isoformat(timespec="seconds")

        try:
            snapshot = fetch_snapshot(args.url, args.timeout)

            odds_format = args.odds_format
            if args.odds_format_key:
                raw_odds_format = get_optional(snapshot, args.odds_format_key)
                if raw_odds_format is not None:
                    odds_format = str(raw_odds_format).strip().lower()

            if odds_format not in {"decimal", "american"}:
                raise ValueError(
                    f"odds_format must be 'decimal' or 'american', got '{odds_format}'."
                )

            p_live_raw = get_optional(snapshot, args.p_live_key)
            yes_odds_raw = get_optional(snapshot, args.yes_odds_key)
            no_odds_raw = get_optional(snapshot, args.no_odds_key)

            p_live = None if p_live_raw is None else parse_number(p_live_raw, args.p_live_key)
            yes_odds = None if yes_odds_raw is None else parse_number(yes_odds_raw, args.yes_odds_key)
            no_odds = None if no_odds_raw is None else parse_number(no_odds_raw, args.no_odds_key)

            time_left = parse_number(get_required(snapshot, args.time_left_key), args.time_left_key)
            time_total = parse_number(get_required(snapshot, args.time_total_key), args.time_total_key)
            a_yes = parse_number(get_required(snapshot, args.a_yes_key), args.a_yes_key)
            a_no = parse_number(get_required(snapshot, args.a_no_key), args.a_no_key)

            prob = resolve_probability_values(
                p_live=p_live,
                yes_odds=yes_odds,
                no_odds=no_odds,
                odds_format=odds_format,
            )

            result = compute_signal(
                p_live=prob.p_live,
                time_left=time_left,
                time_total=time_total,
                a_yes=a_yes,
                a_no=a_no,
                fee_open=args.fee_open,
                min_ev=args.min_ev,
                alpha=args.alpha,
                roundtrip_cost=args.roundtrip_cost,
                spread_buffer=args.spread_buffer,
                account_equity=args.account_equity,
                per_trade_risk_pct=args.per_trade_risk_pct,
                daily_stop_pct=args.daily_stop_pct,
            )

            if args.changes_only and result.action == last_action:
                time.sleep(args.interval)
                continue

            last_action = result.action
            payload = {
                "ts": timestamp,
                "iteration": iteration,
                "action": result.action,
                "reason": result.reason,
                "p_live": result.p_live,
                "p_eff": result.p_eff,
                "ev_yes": result.ev_yes,
                "ev_no": result.ev_no,
                "best_ev": result.best_ev,
                "min_required_ev": result.min_required_ev,
                "remaining_ratio": result.remaining_ratio,
                "probability_source": prob.source,
                "devig_applied": prob.devig_applied,
                "p_yes_raw_from_odds": prob.p_yes_raw,
                "p_no_raw_from_odds": prob.p_no_raw,
                "required_exit_spread": result.required_exit_spread,
                "max_contracts": result.max_contracts,
            }

            if args.json:
                print(json.dumps(payload, separators=(",", ":"), ensure_ascii=True), flush=True)
            else:
                print(
                    f"[{timestamp}] {result.action} "
                    f"best_ev={result.best_ev:.4f} p_eff={result.p_eff:.4f} "
                    f"ev_yes={result.ev_yes:.4f} ev_no={result.ev_no:.4f} "
                    f"src={prob.source} devig={prob.devig_applied}",
                    flush=True,
                )

        except (ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
            print(f"[{timestamp}] ERROR {exc}", flush=True)

        time.sleep(args.interval)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
