#!/usr/bin/env python3
"""Discover useful IDs from ESPN, Kalshi, and Polymarket for experiments."""

from __future__ import annotations

import argparse
import json
import urllib.request
from typing import Any


def fetch_json(url: str, user_agent: str = "signal-engine/1.0") -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def contains_query(text: str, query: str) -> bool:
    if not query:
        return True
    return query.lower() in text.lower()


def run_espn(args: argparse.Namespace) -> int:
    url = f"https://site.api.espn.com/apis/site/v2/sports/{args.sport}/{args.league}/scoreboard"
    if args.date:
        url = f"{url}?dates={args.date}"
    payload = fetch_json(url)
    events = payload.get("events")
    if not isinstance(events, list):
        raise SystemExit("ESPN response missing events.")

    count = 0
    for event in events:
        if not isinstance(event, dict):
            continue
        name = str(event.get("name") or event.get("shortName") or "")
        if not contains_query(name, args.query):
            continue

        event_id = str(event.get("id") or "")
        comp = (event.get("competitions") or [{}])[0]
        status = comp.get("status") if isinstance(comp, dict) else {}
        status_type = status.get("type") if isinstance(status, dict) else {}
        short_detail = status_type.get("shortDetail") if isinstance(status_type, dict) else ""
        state = str(status_type.get("state") or "").lower() if isinstance(status_type, dict) else ""
        if args.state != "all" and state != args.state:
            continue
        period = status.get("period") if isinstance(status, dict) else None
        display_clock = status.get("displayClock") if isinstance(status, dict) else None
        date = str(event.get("date") or "")

        print(
            json.dumps(
                {
                    "event_id": event_id,
                    "name": name,
                    "date": date,
                    "state": state,
                    "status": short_detail,
                    "period": period,
                    "display_clock": display_clock,
                },
                ensure_ascii=True,
            )
        )
        count += 1
        if count >= args.limit:
            break

    return 0


def run_kalshi(args: argparse.Namespace) -> int:
    fetch_limit = min(max(args.limit * 50, 200), 1000)
    url = f"https://api.elections.kalshi.com/trade-api/v2/markets?status=open&limit={fetch_limit}"
    payload = fetch_json(url)
    markets = payload.get("markets")
    if not isinstance(markets, list):
        raise SystemExit("Kalshi response missing markets.")

    count = 0
    for market in markets:
        if not isinstance(market, dict):
            continue
        ticker = str(market.get("ticker") or "")
        subtitle = str(market.get("subtitle") or "")
        title = str(market.get("title") or "")
        custom_text = json.dumps(market.get("custom_strike"), ensure_ascii=True)
        haystack = f"{ticker} {title} {subtitle} {custom_text}"
        if not contains_query(haystack, args.query):
            continue
        associated = []
        custom = market.get("custom_strike")
        if isinstance(custom, dict):
            raw_associated = custom.get("Associated Markets")
            if isinstance(raw_associated, str) and raw_associated.strip():
                associated = [item.strip() for item in raw_associated.split(",") if item.strip()][:10]

        print(
            json.dumps(
                {
                    "ticker": ticker,
                    "title": title,
                    "subtitle": subtitle,
                    "status": market.get("status"),
                    "associated_markets": associated,
                    "yes_bid": market.get("yes_bid"),
                    "yes_ask": market.get("yes_ask"),
                    "no_bid": market.get("no_bid"),
                    "no_ask": market.get("no_ask"),
                },
                ensure_ascii=True,
            )
        )
        count += 1
        if count >= args.limit:
            break

    return 0


def run_polymarket(args: argparse.Namespace) -> int:
    fetch_limit = min(max(args.limit * 50, 200), 1000)
    url = f"https://gamma-api.polymarket.com/markets?active=true&closed=false&limit={fetch_limit}"
    payload = fetch_json(url, user_agent="Mozilla/5.0")
    if not isinstance(payload, list):
        raise SystemExit("Polymarket response must be a list.")

    count = 0
    for market in payload:
        if not isinstance(market, dict):
            continue
        question = str(market.get("question") or "")
        slug = str(market.get("slug") or "")
        if not contains_query(f"{question} {slug}", args.query):
            continue

        print(
            json.dumps(
                {
                    "id": str(market.get("id")),
                    "question": question,
                    "slug": slug,
                    "outcomePrices": market.get("outcomePrices"),
                    "bestBid": market.get("bestBid"),
                    "bestAsk": market.get("bestAsk"),
                    "endDate": market.get("endDate"),
                },
                ensure_ascii=True,
            )
        )
        count += 1
        if count >= args.limit:
            break

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Discover source IDs for live experiments.")
    sub = parser.add_subparsers(dest="command", required=True)

    espn = sub.add_parser("espn", help="List ESPN events.")
    espn.add_argument("--sport", default="basketball")
    espn.add_argument("--league", default="nba")
    espn.add_argument("--date", default="", help="Optional date in YYYYMMDD.")
    espn.add_argument("--query", default="")
    espn.add_argument("--state", choices=["all", "pre", "in", "post"], default="all")
    espn.add_argument("--limit", type=int, default=10)
    espn.set_defaults(func=run_espn)

    kalshi = sub.add_parser("kalshi", help="List open Kalshi markets.")
    kalshi.add_argument("--query", default="GAME")
    kalshi.add_argument("--limit", type=int, default=10)
    kalshi.set_defaults(func=run_kalshi)

    poly = sub.add_parser("polymarket", help="List active Polymarket markets.")
    poly.add_argument("--query", default="win")
    poly.add_argument("--limit", type=int, default=10)
    poly.set_defaults(func=run_polymarket)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.limit <= 0:
        raise SystemExit("Input error: --limit must be > 0.")
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
