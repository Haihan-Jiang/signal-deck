#!/usr/bin/env python3
"""Signal-only engine for event contract trading.

This script does NOT place orders. It only computes a directional signal from:
- live win probability
- remaining time
- current yes/no prices
- cost assumptions
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass


@dataclass
class SignalResult:
    action: str
    reason: str
    p_live: float
    remaining_ratio: float
    p_eff: float
    ev_yes: float
    ev_no: float
    best_ev: float
    min_required_ev: float
    required_exit_spread: float
    risk_budget_per_trade: float | None
    daily_risk_budget: float | None
    max_contracts: int | None


@dataclass
class ProbabilityResolution:
    p_live: float
    source: str
    devig_applied: bool
    p_yes_raw: float | None
    p_no_raw: float | None


def normalize_probability(raw_value: float) -> float:
    """Accept 0..1 or 0..100 input and normalize to 0..1."""
    if raw_value < 0:
        raise ValueError("Probability cannot be negative.")
    if raw_value <= 1:
        return raw_value
    if raw_value <= 100:
        return raw_value / 100.0
    raise ValueError("Probability must be in [0,1] or [0,100].")


def validate_price(name: str, value: float) -> float:
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be in [0, 1], got {value}.")
    return value


def compute_p_eff(p_live: float, remaining_ratio: float, alpha: float) -> float:
    # Early-game live odds are noisy; shrink toward 50% while much time remains.
    return 0.5 + (p_live - 0.5) * ((1 - remaining_ratio) ** alpha)


def odds_to_probability(odds: float, odds_format: str) -> float:
    """Convert decimal or American odds into implied probability."""
    if odds_format == "decimal":
        if odds <= 1:
            raise ValueError("Decimal odds must be > 1.")
        return 1.0 / odds

    if odds_format == "american":
        if odds == 0 or abs(odds) < 100:
            raise ValueError("American odds must be <= -100 or >= +100.")
        if odds > 0:
            return 100.0 / (odds + 100.0)
        abs_odds = abs(odds)
        return abs_odds / (abs_odds + 100.0)

    raise ValueError(f"Unsupported odds_format: {odds_format}")


def resolve_probability_values(
    p_live: float | None,
    yes_odds: float | None,
    no_odds: float | None,
    odds_format: str,
) -> ProbabilityResolution:
    """Resolve p_live from direct probability or odds values."""
    has_p_live = p_live is not None
    has_yes_odds = yes_odds is not None
    has_no_odds = no_odds is not None

    if has_p_live and (has_yes_odds or has_no_odds):
        raise ValueError("Use either p_live OR odds inputs, not both.")

    if has_no_odds and not has_yes_odds:
        raise ValueError("no_odds requires yes_odds.")

    if has_p_live:
        return ProbabilityResolution(
            p_live=normalize_probability(p_live),
            source="direct_probability",
            devig_applied=False,
            p_yes_raw=None,
            p_no_raw=None,
        )

    if not has_yes_odds:
        raise ValueError("Provide p_live or yes_odds.")

    p_yes_raw = odds_to_probability(yes_odds, odds_format)
    if has_no_odds:
        p_no_raw = odds_to_probability(no_odds, odds_format)
        denom = p_yes_raw + p_no_raw
        if denom <= 0:
            raise ValueError("Invalid odds: implied probabilities sum to zero.")
        p_live_from_odds = p_yes_raw / denom
        return ProbabilityResolution(
            p_live=p_live_from_odds,
            source=f"odds_{odds_format}",
            devig_applied=True,
            p_yes_raw=p_yes_raw,
            p_no_raw=p_no_raw,
        )

    return ProbabilityResolution(
        p_live=p_yes_raw,
        source=f"odds_{odds_format}",
        devig_applied=False,
        p_yes_raw=p_yes_raw,
        p_no_raw=None,
    )


def resolve_probability_input(args: argparse.Namespace) -> ProbabilityResolution:
    """Resolve p_live from direct probability or odds inputs."""
    try:
        return resolve_probability_values(
            p_live=args.p_live,
            yes_odds=args.yes_odds,
            no_odds=args.no_odds,
            odds_format=args.odds_format,
        )
    except ValueError as exc:
        message = (
            str(exc)
            .replace("p_live", "--p-live")
            .replace("yes_odds", "--yes-odds")
            .replace("no_odds", "--no-odds")
        )
        raise ValueError(message) from exc


def compute_signal(
    p_live: float,
    time_left: float,
    time_total: float,
    a_yes: float,
    a_no: float,
    fee_open: float,
    min_ev: float,
    alpha: float,
    roundtrip_cost: float,
    spread_buffer: float,
    account_equity: float | None,
    per_trade_risk_pct: float,
    daily_stop_pct: float,
) -> SignalResult:
    if time_total <= 0:
        raise ValueError("time_total must be > 0.")
    if not 0 <= time_left <= time_total:
        raise ValueError("time_left must be within [0, time_total].")
    if fee_open < 0:
        raise ValueError("fee_open cannot be negative.")
    if roundtrip_cost < 0:
        raise ValueError("roundtrip_cost cannot be negative.")
    if spread_buffer < 0:
        raise ValueError("spread_buffer cannot be negative.")
    if not 0 <= per_trade_risk_pct <= 1:
        raise ValueError("per_trade_risk_pct must be in [0,1].")
    if not 0 <= daily_stop_pct <= 1:
        raise ValueError("daily_stop_pct must be in [0,1].")

    p_live = normalize_probability(p_live)
    a_yes = validate_price("a_yes", a_yes)
    a_no = validate_price("a_no", a_no)

    remaining_ratio = time_left / time_total
    p_eff = compute_p_eff(p_live, remaining_ratio, alpha)

    ev_yes = p_eff - a_yes - fee_open
    ev_no = (1 - p_eff) - a_no - fee_open
    best_ev = max(ev_yes, ev_no)

    if best_ev < min_ev:
        action = "NO_TRADE"
        reason = "No side exceeds the minimum EV threshold."
    elif ev_yes >= ev_no:
        action = "BUY_YES"
        reason = "YES side has the higher EV and clears threshold."
    else:
        action = "BUY_NO"
        reason = "NO side has the higher EV and clears threshold."

    required_exit_spread = roundtrip_cost + spread_buffer

    risk_budget_per_trade = None
    daily_risk_budget = None
    max_contracts = None

    if account_equity is not None:
        if account_equity <= 0:
            raise ValueError("account_equity must be > 0 if provided.")
        risk_budget_per_trade = account_equity * per_trade_risk_pct
        daily_risk_budget = account_equity * daily_stop_pct

        if action == "BUY_YES":
            max_loss_per_contract = a_yes
        elif action == "BUY_NO":
            max_loss_per_contract = a_no
        else:
            max_loss_per_contract = max(a_yes, a_no)

        if max_loss_per_contract > 0:
            max_contracts = math.floor(risk_budget_per_trade / max_loss_per_contract)
        else:
            max_contracts = 0

    return SignalResult(
        action=action,
        reason=reason,
        p_live=p_live,
        remaining_ratio=remaining_ratio,
        p_eff=p_eff,
        ev_yes=ev_yes,
        ev_no=ev_no,
        best_ev=best_ev,
        min_required_ev=min_ev,
        required_exit_spread=required_exit_spread,
        risk_budget_per_trade=risk_budget_per_trade,
        daily_risk_budget=daily_risk_budget,
        max_contracts=max_contracts,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Signal-only tool for event contracts. No order placement is performed."
        )
    )
    parser.add_argument("--p-live", type=float, default=None, help="Live YES probability (0..1 or 0..100).")
    parser.add_argument("--yes-odds", type=float, default=None, help="Live YES odds.")
    parser.add_argument("--no-odds", type=float, default=None, help="Live NO odds (enables two-way devig).")
    parser.add_argument(
        "--odds-format",
        choices=["decimal", "american"],
        default="decimal",
        help="Odds format used by --yes-odds / --no-odds.",
    )
    parser.add_argument("--time-left", type=float, required=True, help="Time remaining (same unit as --time-total).")
    parser.add_argument("--time-total", type=float, required=True, help="Total match/event time.")
    parser.add_argument("--a-yes", type=float, required=True, help="Current YES price (0..1).")
    parser.add_argument("--a-no", type=float, required=True, help="Current NO price (0..1).")

    parser.add_argument("--fee-open", type=float, default=0.01, help="Estimated open cost in dollars/contract.")
    parser.add_argument("--min-ev", type=float, default=0.03, help="Minimum EV edge required to trade.")
    parser.add_argument("--alpha", type=float, default=0.7, help="Time-shrink exponent for P_eff.")

    parser.add_argument("--roundtrip-cost", type=float, default=0.04, help="Estimated all-in roundtrip cost.")
    parser.add_argument("--spread-buffer", type=float, default=0.02, help="Extra spread buffer above costs.")

    parser.add_argument("--account-equity", type=float, default=None, help="Account equity for risk sizing.")
    parser.add_argument("--per-trade-risk-pct", type=float, default=0.0025, help="Max risk per trade as fraction of account.")
    parser.add_argument("--daily-stop-pct", type=float, default=0.01, help="Daily stop as fraction of account.")

    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        prob = resolve_probability_input(args)
        result = compute_signal(
            p_live=prob.p_live,
            time_left=args.time_left,
            time_total=args.time_total,
            a_yes=args.a_yes,
            a_no=args.a_no,
            fee_open=args.fee_open,
            min_ev=args.min_ev,
            alpha=args.alpha,
            roundtrip_cost=args.roundtrip_cost,
            spread_buffer=args.spread_buffer,
            account_equity=args.account_equity,
            per_trade_risk_pct=args.per_trade_risk_pct,
            daily_stop_pct=args.daily_stop_pct,
        )
    except ValueError as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2

    payload = asdict(result)
    payload.update(
        {
            "probability_source": prob.source,
            "devig_applied": prob.devig_applied,
            "p_yes_raw_from_odds": prob.p_yes_raw,
            "p_no_raw_from_odds": prob.p_no_raw,
        }
    )

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    print(f"Action: {result.action}")
    print(f"Reason: {result.reason}")
    print(f"P_live: {result.p_live:.4f}")
    print(f"Probability source: {prob.source}")
    print(f"Devig applied: {prob.devig_applied}")
    if prob.p_yes_raw is not None:
        print(f"P_yes raw from odds: {prob.p_yes_raw:.4f}")
    if prob.p_no_raw is not None:
        print(f"P_no raw from odds: {prob.p_no_raw:.4f}")
    print(f"Remaining ratio: {result.remaining_ratio:.4f}")
    print(f"P_eff: {result.p_eff:.4f}")
    print(f"EV_yes: {result.ev_yes:.4f}")
    print(f"EV_no: {result.ev_no:.4f}")
    print(f"Best EV: {result.best_ev:.4f} (threshold {result.min_required_ev:.4f})")
    print(f"Required exit spread: {result.required_exit_spread:.4f}")

    if result.risk_budget_per_trade is not None:
        print(f"Risk budget/trade: {result.risk_budget_per_trade:.2f}")
        print(f"Daily stop budget: {result.daily_risk_budget:.2f}")
        print(f"Max contracts (risk cap): {result.max_contracts}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
