#!/usr/bin/env python3
"""Realtime signal runner using public market + game data sources.

Supported providers:
- kalshi_espn: market prices from Kalshi + probability/time from ESPN
- polymarket_espn: market prices from Polymarket + probability/time from ESPN

This tool emits signals only. It does NOT place orders.
"""

from __future__ import annotations

import argparse
import json
import math
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from signal_engine import compute_signal


def fetch_json(url: str, timeout: float, user_agent: str = "signal-engine/1.0") -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_float(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("Boolean value is not a valid numeric input.")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("Empty string is not a valid numeric input.")
        return float(text)
    raise ValueError(f"Unsupported numeric value type: {type(value).__name__}")


def cents_or_prob_to_prob(value: Any) -> float:
    number = parse_float(value)
    if number < 0:
        raise ValueError("Negative price/probability is invalid.")
    if number > 1:
        return number / 100.0
    return number


def midpoint(bid: float | None, ask: float | None, last: float | None) -> float:
    if bid is not None and ask is not None:
        return (bid + ask) / 2.0
    if ask is not None:
        return ask
    if bid is not None:
        return bid
    if last is not None:
        return last
    raise ValueError("No usable market price was found (bid/ask/last all missing).")


def normalize_outcomes(raw: Any) -> list[str]:
    if isinstance(raw, str):
        parsed = json.loads(raw)
    else:
        parsed = raw
    if not isinstance(parsed, list):
        raise ValueError("Polymarket outcomes must be a list.")
    return [str(item) for item in parsed]


def normalize_prices(raw: Any) -> list[float]:
    if isinstance(raw, str):
        parsed = json.loads(raw)
    else:
        parsed = raw
    if not isinstance(parsed, list):
        raise ValueError("Polymarket outcomePrices must be a list.")
    return [parse_float(item) for item in parsed]


def get_kalshi_prices(market_ticker: str, timeout: float) -> dict[str, float]:
    url = f"https://api.elections.kalshi.com/trade-api/v2/markets/{market_ticker}"
    payload = fetch_json(url, timeout=timeout)
    market = payload.get("market")
    if not isinstance(market, dict):
        raise ValueError("Kalshi response missing market object.")

    yes_bid = cents_or_prob_to_prob(market.get("yes_bid")) if market.get("yes_bid") is not None else None
    yes_ask = cents_or_prob_to_prob(market.get("yes_ask")) if market.get("yes_ask") is not None else None
    no_bid = cents_or_prob_to_prob(market.get("no_bid")) if market.get("no_bid") is not None else None
    no_ask = cents_or_prob_to_prob(market.get("no_ask")) if market.get("no_ask") is not None else None
    last = cents_or_prob_to_prob(market.get("last_price")) if market.get("last_price") is not None else None

    a_yes = midpoint(yes_bid, yes_ask, last)
    a_no = midpoint(no_bid, no_ask, None if last is None else 1.0 - last)

    return {
        "a_yes": a_yes,
        "a_no": a_no,
        "yes_bid": -1.0 if yes_bid is None else yes_bid,
        "yes_ask": -1.0 if yes_ask is None else yes_ask,
        "no_bid": -1.0 if no_bid is None else no_bid,
        "no_ask": -1.0 if no_ask is None else no_ask,
    }


def get_polymarket_prices(market_id: str, timeout: float) -> dict[str, float]:
    url = f"https://gamma-api.polymarket.com/markets/{market_id}"
    market = fetch_json(url, timeout=timeout, user_agent="Mozilla/5.0")
    if not isinstance(market, dict):
        raise ValueError("Polymarket response must be a JSON object.")

    outcomes = normalize_outcomes(market.get("outcomes"))
    outcome_prices = normalize_prices(market.get("outcomePrices"))

    if len(outcomes) != len(outcome_prices):
        raise ValueError("Polymarket outcomes and outcomePrices length mismatch.")

    index = {name.strip().lower(): idx for idx, name in enumerate(outcomes)}
    if "yes" not in index or "no" not in index:
        raise ValueError("Polymarket market does not expose Yes/No outcomes.")

    a_yes = outcome_prices[index["yes"]]
    a_no = outcome_prices[index["no"]]

    return {
        "a_yes": a_yes,
        "a_no": a_no,
        "yes_bid": parse_float(market.get("bestBid")) if market.get("bestBid") is not None else -1.0,
        "yes_ask": parse_float(market.get("bestAsk")) if market.get("bestAsk") is not None else -1.0,
        "no_bid": -1.0,
        "no_ask": -1.0,
    }


def parse_clock_to_seconds(display_clock: Any) -> float | None:
    if display_clock is None:
        return None
    text = str(display_clock).strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) == 2:
        minutes = int(parts[0])
        seconds = float(parts[1])
        return minutes * 60.0 + seconds
    if len(parts) == 1:
        return float(parts[0])
    return None


def parse_espn_competitors(summary: dict[str, Any]) -> dict[str, Any]:
    competitions = summary.get("header", {}).get("competitions")
    if not isinstance(competitions, list) or not competitions:
        return {
            "home_name": "",
            "away_name": "",
            "home_abbr": "",
            "away_abbr": "",
            "home_score": None,
            "away_score": None,
        }

    comp0 = competitions[0] if isinstance(competitions[0], dict) else {}
    competitors = comp0.get("competitors")
    if not isinstance(competitors, list):
        competitors = []

    result = {
        "home_name": "",
        "away_name": "",
        "home_abbr": "",
        "away_abbr": "",
        "home_score": None,
        "away_score": None,
    }

    for row in competitors:
        if not isinstance(row, dict):
            continue
        side = str(row.get("homeAway") or "").lower()
        team = row.get("team") if isinstance(row.get("team"), dict) else {}
        name = str(team.get("displayName") or team.get("shortDisplayName") or "").strip()
        abbr = str(team.get("abbreviation") or "").strip().upper()
        score = None
        raw_score = row.get("score")
        if raw_score is not None:
            try:
                score = parse_float(raw_score)
            except ValueError:
                score = None

        if side == "home":
            result["home_name"] = name
            result["home_abbr"] = abbr
            result["home_score"] = score
        elif side == "away":
            result["away_name"] = name
            result["away_abbr"] = abbr
            result["away_score"] = score

    return result


def find_latest_home_win_probability(winprobability: Any) -> float | None:
    if not isinstance(winprobability, list):
        return None
    for entry in reversed(winprobability):
        if not isinstance(entry, dict):
            continue
        value = entry.get("homeWinPercentage")
        if value is None:
            continue
        try:
            number = parse_float(value)
        except ValueError:
            continue
        if 0.0 <= number <= 1.0:
            return number
    return None


def compute_home_probability_from_score(summary: dict[str, Any]) -> float | None:
    teams = parse_espn_competitors(summary)
    home_score = teams.get("home_score")
    away_score = teams.get("away_score")

    if home_score is None or away_score is None:
        return None
    if home_score > away_score:
        return 1.0
    if home_score < away_score:
        return 0.0
    return 0.5


def compute_live_home_probability_from_score(summary: dict[str, Any], time_left: float, time_total: float) -> float | None:
    teams = parse_espn_competitors(summary)
    home_score = teams.get("home_score")
    away_score = teams.get("away_score")
    if home_score is None or away_score is None:
        return None

    margin = float(home_score) - float(away_score)
    if abs(margin) < 1e-9:
        return 0.5

    if time_total <= 0:
        progress = 0.0
    else:
        progress = 1.0 - max(0.0, min(float(time_left) / float(time_total), 1.0))

    # At the start, score margin should matter less; near the end, more.
    scale = 14.0 - 9.0 * progress
    scale = max(2.5, scale)
    z = margin / scale
    p = 1.0 / (1.0 + math.exp(-z))
    return max(0.01, min(0.99, p))


def get_espn_state(
    sport: str,
    league: str,
    event_id: str,
    timeout: float,
    yes_team: str,
    period_seconds: float,
    regulation_periods: int,
) -> dict[str, Any]:
    if period_seconds <= 0:
        raise ValueError("period_seconds must be > 0.")
    if regulation_periods <= 0:
        raise ValueError("regulation_periods must be > 0.")

    url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/summary?event={event_id}"
    summary = fetch_json(url, timeout=timeout)
    if not isinstance(summary, dict):
        raise ValueError("ESPN summary payload must be a JSON object.")

    competitions = summary.get("header", {}).get("competitions")
    if not isinstance(competitions, list) or not competitions:
        raise ValueError("ESPN summary missing competition status.")
    status = competitions[0].get("status")
    if not isinstance(status, dict):
        raise ValueError("ESPN summary missing status object.")

    status_type = status.get("type", {}) if isinstance(status.get("type"), dict) else {}
    completed = bool(status_type.get("completed"))
    status_state = str(status_type.get("state") or "").lower()

    period_raw = status.get("period")
    period = int(period_raw) if period_raw is not None else 0
    clock_raw = status.get("clock")
    if clock_raw is not None:
        clock_seconds = parse_float(clock_raw)
    else:
        clock_seconds = parse_clock_to_seconds(status.get("displayClock"))

    total_time = float(regulation_periods) * float(period_seconds)

    if completed:
        time_left = 0.0
    elif period <= 0:
        time_left = total_time
    else:
        if clock_seconds is None:
            raise ValueError("ESPN status has no clock for an in-progress event.")
        if period <= regulation_periods:
            remaining_periods = max(regulation_periods - period, 0)
            time_left = clock_seconds + remaining_periods * period_seconds
        else:
            # Overtime: keep time_left bounded by current overtime clock.
            time_left = clock_seconds

    time_left = max(0.0, min(time_left, total_time))
    teams = parse_espn_competitors(summary)

    probability_mode = "winprobability"
    home_probability = find_latest_home_win_probability(summary.get("winprobability"))
    if home_probability is None:
        if completed:
            home_probability = compute_home_probability_from_score(summary)
            probability_mode = "final_score_fallback"
        elif status_state == "in":
            # Live but no ESPN winprobability available: estimate from score + game progress.
            home_probability = compute_live_home_probability_from_score(summary, time_left=time_left, time_total=total_time)
            if home_probability is not None:
                probability_mode = "score_time_fallback_live"
        if home_probability is None:
            # Pre-game or unavailable model state: neutral baseline until live probability appears.
            home_probability = 0.5
            probability_mode = "neutral_pre_live"
    if home_probability is None:
        raise ValueError("Unable to derive ESPN home win probability from summary.")

    home_label = str(teams.get("home_abbr") or teams.get("home_name") or "HOME")
    away_label = str(teams.get("away_abbr") or teams.get("away_name") or "AWAY")
    p_live_yes = home_probability if yes_team == "home" else 1.0 - home_probability
    return {
        "p_live_yes": p_live_yes,
        "time_left": time_left,
        "time_total": total_time,
        "home_probability": home_probability,
        "period": float(period),
        "clock_seconds": 0.0 if clock_seconds is None else clock_seconds,
        "status_state": status_state,
        "probability_mode": probability_mode,
        "home_team": str(teams.get("home_name") or ""),
        "away_team": str(teams.get("away_name") or ""),
        "home_abbr": str(teams.get("home_abbr") or ""),
        "away_abbr": str(teams.get("away_abbr") or ""),
        "home_score": teams.get("home_score"),
        "away_score": teams.get("away_score"),
        "rivalry": f"{away_label} @ {home_label}",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Realtime signal runner using Kalshi/Polymarket market prices plus ESPN game state."
    )

    parser.add_argument("--provider", choices=["kalshi_espn", "polymarket_espn"], required=True)
    parser.add_argument("--market", required=True, help="Kalshi market ticker or Polymarket market id.")

    parser.add_argument("--espn-sport", default="basketball", help="ESPN sport slug, e.g. basketball.")
    parser.add_argument("--espn-league", default="nba", help="ESPN league slug, e.g. nba.")
    parser.add_argument("--espn-event-id", required=True, help="ESPN event id.")
    parser.add_argument("--yes-team", choices=["home", "away"], default="home", help="Which ESPN side maps to YES.")
    parser.add_argument("--period-seconds", type=float, default=720.0, help="Seconds per regulation period.")
    parser.add_argument("--regulation-periods", type=int, default=4, help="Count of regulation periods.")

    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds.")
    parser.add_argument("--timeout", type=float, default=6.0, help="HTTP timeout in seconds.")
    parser.add_argument("--max-iterations", type=int, default=None, help="Stop after N polls.")
    parser.add_argument("--require-live", action="store_true", help="Emit signals only when ESPN state is in-progress.")
    parser.add_argument("--changes-only", action="store_true", help="Only print when action changes.")
    parser.add_argument("--json", action="store_true", help="Print one JSON line per iteration.")

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
            if args.provider == "kalshi_espn":
                market = get_kalshi_prices(args.market, args.timeout)
            else:
                market = get_polymarket_prices(args.market, args.timeout)

            espn = get_espn_state(
                sport=args.espn_sport,
                league=args.espn_league,
                event_id=args.espn_event_id,
                timeout=args.timeout,
                yes_team=args.yes_team,
                period_seconds=args.period_seconds,
                regulation_periods=args.regulation_periods,
            )

            if args.require_live and espn["status_state"] != "in":
                wait_payload = {
                    "ts": timestamp,
                    "iteration": iteration,
                    "provider": args.provider,
                    "market": args.market,
                    "espn_event_id": args.espn_event_id,
                    "state": "WAITING",
                    "espn_status": espn["status_state"],
                    "probability_mode": espn["probability_mode"],
                }
                if args.json:
                    print(json.dumps(wait_payload, separators=(",", ":"), ensure_ascii=True), flush=True)
                else:
                    print(
                        f"[{timestamp}] WAITING espn_status={espn['status_state']} "
                        f"probability_mode={espn['probability_mode']}",
                        flush=True,
                    )
                time.sleep(args.interval)
                continue

            result = compute_signal(
                p_live=espn["p_live_yes"],
                time_left=espn["time_left"],
                time_total=espn["time_total"],
                a_yes=market["a_yes"],
                a_no=market["a_no"],
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
                "provider": args.provider,
                "market": args.market,
                "espn_event_id": args.espn_event_id,
                "action": result.action,
                "reason": result.reason,
                "p_live_yes": result.p_live,
                "p_home_espn": espn["home_probability"],
                "time_left": espn["time_left"],
                "time_total": espn["time_total"],
                "period": espn["period"],
                "clock_seconds": espn["clock_seconds"],
                "espn_status": espn["status_state"],
                "probability_mode": espn["probability_mode"],
                "a_yes": market["a_yes"],
                "a_no": market["a_no"],
                "ev_yes": result.ev_yes,
                "ev_no": result.ev_no,
                "best_ev": result.best_ev,
                "p_eff": result.p_eff,
                "required_exit_spread": result.required_exit_spread,
                "max_contracts": result.max_contracts,
            }

            if args.json:
                print(json.dumps(payload, separators=(",", ":"), ensure_ascii=True), flush=True)
            else:
                print(
                    f"[{timestamp}] {result.action} "
                    f"best_ev={result.best_ev:.4f} p_eff={result.p_eff:.4f} "
                    f"a_yes={market['a_yes']:.3f} a_no={market['a_no']:.3f} "
                    f"p_live_yes={result.p_live:.3f} t_left={espn['time_left']:.1f}s",
                    flush=True,
                )
        except (ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
            print(f"[{timestamp}] ERROR {exc}", flush=True)

        time.sleep(args.interval)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
