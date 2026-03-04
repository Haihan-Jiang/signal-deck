#!/usr/bin/env python3
"""Local dashboard server for realtime signal experiments.

Run:
  python3 dashboard_server.py --host 127.0.0.1 --port 8787
Then open:
  http://127.0.0.1:8787
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from live_experiment_signal import get_espn_state, get_kalshi_prices, get_polymarket_prices
from signal_engine import compute_signal


ROOT = Path(__file__).resolve().parent
INDEX_HTML = ROOT / "web" / "index.html"
HOTRELOAD_WATCH_FILES = (
    ROOT / "dashboard_server.py",
    ROOT / "live_experiment_signal.py",
    ROOT / "signal_engine.py",
    INDEX_HTML,
)


def file_signature(path: Path) -> str:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return f"{path.name}:missing"
    return f"{path.name}:{stat.st_mtime_ns}:{stat.st_size}"


def compute_reload_token(paths: tuple[Path, ...] = HOTRELOAD_WATCH_FILES) -> str:
    joined = "|".join(file_signature(path) for path in paths)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12]


def terminate_process(child: subprocess.Popen[Any], timeout: float = 3.0) -> None:
    if child.poll() is not None:
        return
    child.terminate()
    try:
        child.wait(timeout=timeout)
        return
    except subprocess.TimeoutExpired:
        pass
    child.kill()
    try:
        child.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        pass


def parse_int(value: Any, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError("Invalid boolean for integer field.")
    return int(value)


def parse_float(value: Any, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError("Invalid boolean for numeric field.")
    return float(value)


def parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def query_first(query: dict[str, list[str]], key: str, default: str = "") -> str:
    values = query.get(key)
    if not values:
        return default
    return values[0]


def contains_query(text: str, query: str) -> bool:
    if not query:
        return True
    return query.lower() in text.lower()


NBA_MARKET_TERMS = [
    "nba",
    "nba finals",
    "atlanta hawks",
    "boston celtics",
    "brooklyn nets",
    "charlotte hornets",
    "chicago bulls",
    "cleveland cavaliers",
    "dallas mavericks",
    "denver nuggets",
    "detroit pistons",
    "golden state warriors",
    "houston rockets",
    "indiana pacers",
    "los angeles clippers",
    "los angeles lakers",
    "memphis grizzlies",
    "miami heat",
    "milwaukee bucks",
    "minnesota timberwolves",
    "new orleans pelicans",
    "new york knicks",
    "oklahoma city thunder",
    "orlando magic",
    "philadelphia 76ers",
    "phoenix suns",
    "portland trail blazers",
    "sacramento kings",
    "san antonio spurs",
    "toronto raptors",
    "utah jazz",
    "washington wizards",
]

KALSHI_ABBR_ALIASES: dict[str, tuple[str, ...]] = {
    "NO": ("NOP",),
    "NOP": ("NO",),
    "NY": ("NYK",),
    "NYK": ("NY",),
    "GS": ("GSW",),
    "GSW": ("GS",),
    "SA": ("SAS",),
    "SAS": ("SA",),
    "WSH": ("WAS",),
    "WAS": ("WSH",),
}


def nba_abbr_aliases(abbr: str) -> list[str]:
    key = str(abbr or "").strip().upper()
    if not key:
        return []
    aliases = [key]
    for alt in KALSHI_ABBR_ALIASES.get(key, ()):
        if alt not in aliases:
            aliases.append(alt)
    return aliases


def is_nba_polymarket(market: dict[str, Any]) -> bool:
    texts: list[str] = []
    for key in ("question", "slug", "groupItemTitle"):
        value = market.get(key)
        if isinstance(value, str):
            texts.append(value.lower())
    events = market.get("events")
    if isinstance(events, list):
        for event in events:
            if not isinstance(event, dict):
                continue
            for key in ("title", "slug", "ticker", "description"):
                value = event.get(key)
                if isinstance(value, str):
                    texts.append(value.lower())
    haystack = " ".join(texts)
    return any(term in haystack for term in NBA_MARKET_TERMS)


def fetch_json(url: str, timeout: float = 8.0, user_agent: str = "signal-dashboard/1.0") -> Any:
    from urllib.request import Request, urlopen

    request = Request(url, headers={"User-Agent": user_agent})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def discover_espn(sport: str, league: str, date: str, state: str, query: str, limit: int) -> list[dict[str, Any]]:
    url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard"
    if date:
        url = f"{url}?dates={date}"
    payload = fetch_json(url)
    events = payload.get("events")
    if not isinstance(events, list):
        raise ValueError("ESPN response missing events.")

    results: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        name = str(event.get("name") or event.get("shortName") or "")
        if not contains_query(name, query):
            continue
        event_id = str(event.get("id") or "")
        comp = (event.get("competitions") or [{}])[0]
        status = comp.get("status") if isinstance(comp, dict) else {}
        status_type = status.get("type") if isinstance(status, dict) else {}
        state_raw = str(status_type.get("state") or "").lower() if isinstance(status_type, dict) else ""
        if state != "all" and state_raw != state:
            continue
        results.append(
            {
                "event_id": event_id,
                "name": name,
                "date": str(event.get("date") or ""),
                "state": state_raw,
                "status": status_type.get("shortDetail") if isinstance(status_type, dict) else "",
                "period": status.get("period") if isinstance(status, dict) else None,
                "display_clock": status.get("displayClock") if isinstance(status, dict) else None,
            }
        )
        if len(results) >= limit:
            break
    return results


def discover_kalshi(
    query: str,
    limit: int,
    pair_filter: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    fetch_limit = min(max(limit * 50, 200), 1000)
    url = f"https://api.elections.kalshi.com/trade-api/v2/markets?status=open&limit={fetch_limit}"
    payload = fetch_json(url)
    markets = payload.get("markets")
    if not isinstance(markets, list):
        raise ValueError("Kalshi response missing markets.")

    if pair_filter is not None:
        home_abbr = str(pair_filter.get("home_abbr") or "").upper()
        away_abbr = str(pair_filter.get("away_abbr") or "").upper()
        home_aliases = nba_abbr_aliases(home_abbr)
        away_aliases = nba_abbr_aliases(away_abbr)
        if not home_aliases or not away_aliases:
            raise ValueError("Invalid pair_filter: missing home/away abbreviations.")
        combos = {f"{a}{h}" for a in away_aliases for h in home_aliases}
        combos.update({f"{h}{a}" for h in home_aliases for a in away_aliases})

        candidate_tickers: list[str] = []
        seen: set[str] = set()
        for market in markets:
            if not isinstance(market, dict):
                continue
            ticker = str(market.get("ticker") or "")
            subtitle = str(market.get("subtitle") or "")
            title = str(market.get("title") or "")
            custom_text = json.dumps(market.get("custom_strike"), ensure_ascii=True)
            source_haystack = f"{ticker} {title} {subtitle} {custom_text}"

            raw_candidates = [ticker]
            raw_candidates.extend(_read_associated_markets(market))
            for cand in raw_candidates:
                cand = str(cand).strip()
                if not cand or cand in seen:
                    continue
                upper = cand.upper()
                if not upper.startswith("KXNBA"):
                    continue
                if not any(combo in upper for combo in combos):
                    continue
                seen.add(cand)
                candidate_tickers.append(cand)

        results: list[dict[str, Any]] = []
        for cand in candidate_tickers:
            if len(results) >= limit:
                break
            try:
                detail = fetch_json(f"https://api.elections.kalshi.com/trade-api/v2/markets/{cand}")
                mk = detail.get("market")
                if not isinstance(mk, dict):
                    continue
                detail_haystack = " ".join(
                    [
                        cand,
                        str(mk.get("title") or ""),
                        str(mk.get("subtitle") or ""),
                        str(mk.get("yes_sub_title") or ""),
                        str(mk.get("no_sub_title") or ""),
                    ]
                )
                if not contains_query(detail_haystack, query):
                    continue
                results.append(
                    {
                        "ticker": cand,
                        "title": str(mk.get("title") or ""),
                        "subtitle": str(mk.get("subtitle") or ""),
                        "status": mk.get("status"),
                        "associated_markets": [],
                        "yes_bid": mk.get("yes_bid"),
                        "yes_ask": mk.get("yes_ask"),
                        "no_bid": mk.get("no_bid"),
                        "no_ask": mk.get("no_ask"),
                    }
                )
            except Exception:
                continue
        return results

    results: list[dict[str, Any]] = []
    for market in markets:
        if not isinstance(market, dict):
            continue
        ticker = str(market.get("ticker") or "")
        subtitle = str(market.get("subtitle") or "")
        title = str(market.get("title") or "")
        custom_text = json.dumps(market.get("custom_strike"), ensure_ascii=True)
        haystack = f"{ticker} {title} {subtitle} {custom_text}"
        if not contains_query(haystack, query):
            continue
        if not matches_pair_text(haystack, pair_filter):
            continue

        associated: list[str] = []
        custom = market.get("custom_strike")
        if isinstance(custom, dict):
            raw_associated = custom.get("Associated Markets")
            if isinstance(raw_associated, str) and raw_associated.strip():
                associated = [item.strip() for item in raw_associated.split(",") if item.strip()][:10]

        results.append(
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
            }
        )
        if len(results) >= limit:
            break
    return results


def discover_polymarket(
    query: str,
    limit: int,
    nba_only: bool = True,
    pair_filter: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    fetch_limit = min(max(limit * 50, 200), 1000)
    url = f"https://gamma-api.polymarket.com/markets?active=true&closed=false&limit={fetch_limit}"
    payload = fetch_json(url, user_agent="Mozilla/5.0")
    if not isinstance(payload, list):
        raise ValueError("Polymarket response must be a list.")

    results: list[dict[str, Any]] = []
    for market in payload:
        if not isinstance(market, dict):
            continue
        if nba_only and not is_nba_polymarket(market):
            continue
        question = str(market.get("question") or "")
        slug = str(market.get("slug") or "")
        texts = [question, slug, str(market.get("groupItemTitle") or "")]
        events = market.get("events")
        if isinstance(events, list):
            for event in events:
                if not isinstance(event, dict):
                    continue
                for key in ("title", "slug", "description", "ticker"):
                    value = event.get(key)
                    if isinstance(value, str):
                        texts.append(value)
        haystack = " ".join(texts)
        if not contains_query(haystack, query):
            continue
        if not matches_pair_text(haystack, pair_filter):
            continue
        results.append(
            {
                "id": str(market.get("id")),
                "question": question,
                "slug": slug,
                "outcomePrices": market.get("outcomePrices"),
                "bestBid": market.get("bestBid"),
                "bestAsk": market.get("bestAsk"),
                "endDate": market.get("endDate"),
            }
        )
        if len(results) >= limit:
            break
    return results


def _coerce_espn_date(iso_value: str) -> datetime:
    text = iso_value.strip()
    if not text:
        raise ValueError("ESPN event date is missing.")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"Unsupported ESPN date format: {iso_value}") from exc


def _abbr_from_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", name).strip()
    if not cleaned:
        return ""
    words = [w for w in cleaned.split() if w]
    if len(words) >= 2:
        return (words[0][:1] + words[-1][:2]).upper()
    return words[0][:3].upper()


def _team_terms(name: str) -> list[str]:
    raw = re.findall(r"[A-Za-z0-9]+", name.lower())
    stop = {"fc", "cf", "sc", "the", "at", "club", "team"}
    terms = [w for w in raw if w not in stop and len(w) >= 3]
    # Prefer more specific terms first.
    return sorted(set(terms), key=len, reverse=True)[:3]


def get_espn_event_meta(sport: str, league: str, event_id: str) -> dict[str, Any]:
    url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/summary?event={event_id}"
    payload = fetch_json(url)
    if not isinstance(payload, dict):
        raise ValueError("ESPN summary payload must be a JSON object.")
    competitions = payload.get("header", {}).get("competitions")
    if not isinstance(competitions, list) or not competitions:
        raise ValueError("ESPN summary missing competitions.")
    comp = competitions[0]
    if not isinstance(comp, dict):
        raise ValueError("ESPN competition payload malformed.")

    event_date = str(comp.get("date") or "")
    event_dt = _coerce_espn_date(event_date)
    et = ZoneInfo("America/New_York")
    date_tokens: list[str] = []
    for dt in [event_dt.astimezone(et), event_dt]:
        token = dt.strftime("%y%b%d").upper()
        if token not in date_tokens:
            date_tokens.append(token)

    competitors = comp.get("competitors")
    if not isinstance(competitors, list) or not competitors:
        raise ValueError("ESPN competition missing competitors.")

    home_name = ""
    away_name = ""
    home_abbr = ""
    away_abbr = ""
    for team_row in competitors:
        if not isinstance(team_row, dict):
            continue
        side = str(team_row.get("homeAway") or "").lower()
        team_obj = team_row.get("team") if isinstance(team_row.get("team"), dict) else {}
        name = str(team_obj.get("displayName") or team_obj.get("shortDisplayName") or "").strip()
        abbr = str(team_obj.get("abbreviation") or "").strip().upper()
        if not abbr:
            abbr = _abbr_from_name(name)
        if side == "home":
            home_name, home_abbr = name, abbr
        elif side == "away":
            away_name, away_abbr = name, abbr

    if not home_abbr or not away_abbr:
        raise ValueError("Could not determine home/away team abbreviations from ESPN.")

    return {
        "event_id": event_id,
        "event_date_utc": event_dt.isoformat(),
        "date_tokens": date_tokens,
        "home_name": home_name,
        "away_name": away_name,
        "home_abbr": home_abbr,
        "away_abbr": away_abbr,
    }


def build_pair_filter(event_meta: dict[str, Any]) -> dict[str, Any]:
    home_terms = set(_team_terms(event_meta["home_name"]))
    away_terms = set(_team_terms(event_meta["away_name"]))
    for alias in nba_abbr_aliases(str(event_meta["home_abbr"])):
        home_terms.add(alias.lower())
    for alias in nba_abbr_aliases(str(event_meta["away_abbr"])):
        away_terms.add(alias.lower())
    return {
        "home_terms": sorted(home_terms),
        "away_terms": sorted(away_terms),
        "home_abbr": str(event_meta["home_abbr"]).upper(),
        "away_abbr": str(event_meta["away_abbr"]).upper(),
    }


def matches_pair_text(text: str, pair_filter: dict[str, Any] | None) -> bool:
    if pair_filter is None:
        return True
    haystack = text.lower()
    home_terms = pair_filter.get("home_terms") or []
    away_terms = pair_filter.get("away_terms") or []
    home_hit = any(term and term in haystack for term in home_terms)
    away_hit = any(term and term in haystack for term in away_terms)
    return home_hit and away_hit


def _read_associated_markets(market: dict[str, Any]) -> list[str]:
    custom = market.get("custom_strike")
    if not isinstance(custom, dict):
        return []
    raw_associated = custom.get("Associated Markets")
    if not isinstance(raw_associated, str):
        return []
    return [item.strip() for item in raw_associated.split(",") if item.strip()]


def _kalshi_ticker_exists(ticker: str) -> bool:
    url = f"https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}"
    try:
        payload = fetch_json(url)
    except Exception:
        return False
    return isinstance(payload, dict) and isinstance(payload.get("market"), dict)


def autofill_kalshi_market(event_meta: dict[str, Any], yes_team: str, timeout: float) -> dict[str, Any]:
    yes_abbr = event_meta["home_abbr"] if yes_team == "home" else event_meta["away_abbr"]
    yes_aliases = nba_abbr_aliases(yes_abbr)
    home_aliases = nba_abbr_aliases(str(event_meta["home_abbr"]))
    away_aliases = nba_abbr_aliases(str(event_meta["away_abbr"]))
    combos: list[str] = []
    for away in away_aliases:
        for home in home_aliases:
            pair1 = f"{away}{home}"
            pair2 = f"{home}{away}"
            if pair1 not in combos:
                combos.append(pair1)
            if pair2 not in combos:
                combos.append(pair2)

    base_prefixes: list[str] = []
    preferred_tickers: list[str] = []
    for token in event_meta["date_tokens"]:
        for combo in combos:
            base = f"KXNBAGAME-{token}{combo}"
            if base not in base_prefixes:
                base_prefixes.append(base)
            for yes_alias in yes_aliases:
                preferred_ticker = f"{base}-{yes_alias}"
                if preferred_ticker not in preferred_tickers:
                    preferred_tickers.append(preferred_ticker)

    for ticker in preferred_tickers:
        if _kalshi_ticker_exists(ticker):
            return {
                "matched": True,
                "market": ticker,
                "source": "direct_guess",
                "candidates": [ticker],
                "message": f"Matched {ticker}",
            }

    fetch_limit = 1000
    url = f"https://api.elections.kalshi.com/trade-api/v2/markets?status=open&limit={fetch_limit}"
    payload = fetch_json(url, timeout=timeout)
    markets = payload.get("markets")
    if not isinstance(markets, list):
        raise ValueError("Kalshi open markets response malformed.")

    collected: list[str] = []
    seen: set[str] = set()
    for market in markets:
        if not isinstance(market, dict):
            continue
        candidates = []
        ticker = str(market.get("ticker") or "").strip()
        if ticker:
            candidates.append(ticker)
        candidates.extend(_read_associated_markets(market))
        for cand in candidates:
            if cand in seen:
                continue
            if any(cand.startswith(prefix) for prefix in base_prefixes):
                seen.add(cand)
                collected.append(cand)

    preferred_suffixes = {f"-{abbr}" for abbr in yes_aliases}
    best = next((c for c in collected if any(c.endswith(sfx) for sfx in preferred_suffixes)), None)
    if best is None and collected:
        best = collected[0]

    if best:
        return {
            "matched": True,
            "market": best,
            "source": "open_markets_scan",
            "candidates": collected[:20],
            "message": f"Matched {best}",
        }

    return {
        "matched": False,
        "market": "",
        "source": "no_match",
        "candidates": [],
        "message": "No matching Kalshi NBA market found for this ESPN event.",
    }


def autofill_polymarket_market(event_meta: dict[str, Any], timeout: float) -> dict[str, Any]:
    fetch_limit = 1000
    url = f"https://gamma-api.polymarket.com/markets?active=true&closed=false&limit={fetch_limit}"
    payload = fetch_json(url, timeout=timeout, user_agent="Mozilla/5.0")
    if not isinstance(payload, list):
        raise ValueError("Polymarket response malformed.")

    home_terms = _team_terms(event_meta["home_name"]) or [event_meta["home_abbr"].lower()]
    away_terms = _team_terms(event_meta["away_name"]) or [event_meta["away_abbr"].lower()]
    matches: list[dict[str, str]] = []
    for market in payload:
        if not isinstance(market, dict):
            continue
        question = str(market.get("question") or "")
        hay = question.lower()
        if not any(t in hay for t in home_terms):
            continue
        if not any(t in hay for t in away_terms):
            continue
        matches.append(
            {
                "id": str(market.get("id") or ""),
                "question": question,
            }
        )
        if len(matches) >= 20:
            break

    if matches:
        return {
            "matched": True,
            "market": matches[0]["id"],
            "source": "question_match",
            "candidates": matches,
            "message": f"Matched Polymarket id {matches[0]['id']}",
        }

    return {
        "matched": False,
        "market": "",
        "source": "no_match",
        "candidates": [],
        "message": "No Polymarket market matched both team names.",
    }


def autofill_market(provider: str, sport: str, league: str, event_id: str, yes_team: str, timeout: float) -> dict[str, Any]:
    if provider not in {"kalshi_espn", "polymarket_espn"}:
        raise ValueError("provider must be 'kalshi_espn' or 'polymarket_espn'.")
    if yes_team not in {"home", "away"}:
        raise ValueError("yes_team must be 'home' or 'away'.")
    if not event_id.strip():
        raise ValueError("event_id is required.")

    event_meta = get_espn_event_meta(sport=sport, league=league, event_id=event_id)
    if provider == "kalshi_espn":
        result = autofill_kalshi_market(event_meta=event_meta, yes_team=yes_team, timeout=timeout)
        result["suggested_provider"] = "kalshi_espn"
        return {"provider": provider, "event": event_meta, **result}

    result = autofill_polymarket_market(event_meta=event_meta, timeout=timeout)
    suggested_provider = "polymarket_espn" if result["matched"] else "kalshi_espn"
    if not result["matched"]:
        result["message"] = f"{result['message']} You can switch to kalshi_espn for NBA game markets."
    result["suggested_provider"] = suggested_provider
    return {"provider": provider, "event": event_meta, **result}


def build_signal_once(config: dict[str, Any]) -> dict[str, Any]:
    provider = str(config.get("provider") or "kalshi_espn")
    if provider not in {"kalshi_espn", "polymarket_espn"}:
        raise ValueError("provider must be 'kalshi_espn' or 'polymarket_espn'.")

    market_id = str(config.get("market") or "").strip()
    if not market_id:
        raise ValueError("market is required.")

    espn_sport = str(config.get("espn_sport") or "basketball")
    espn_league = str(config.get("espn_league") or "nba")
    espn_event_id = str(config.get("espn_event_id") or "").strip()
    if not espn_event_id:
        raise ValueError("espn_event_id is required.")

    yes_team = str(config.get("yes_team") or "home").lower()
    if yes_team not in {"home", "away"}:
        raise ValueError("yes_team must be 'home' or 'away'.")

    timeout = parse_float(config.get("timeout"), 6.0)
    require_live = parse_bool(config.get("require_live"), True)

    period_seconds = parse_float(config.get("period_seconds"), 720.0)
    regulation_periods = parse_int(config.get("regulation_periods"), 4)

    if provider == "kalshi_espn":
        market = get_kalshi_prices(market_id, timeout=timeout)
    else:
        market = get_polymarket_prices(market_id, timeout=timeout)

    espn = get_espn_state(
        sport=espn_sport,
        league=espn_league,
        event_id=espn_event_id,
        timeout=timeout,
        yes_team=yes_team,
        period_seconds=period_seconds,
        regulation_periods=regulation_periods,
    )

    if require_live and espn["status_state"] != "in":
        return {
            "provider": provider,
            "market": market_id,
            "espn_event_id": espn_event_id,
            "state": "WAITING",
            "espn_status": espn["status_state"],
            "probability_mode": espn["probability_mode"],
            "a_yes": market["a_yes"],
            "a_no": market["a_no"],
            "p_live_yes": espn["p_live_yes"],
            "time_left": espn["time_left"],
            "time_total": espn["time_total"],
            "home_team": espn["home_team"],
            "away_team": espn["away_team"],
            "home_abbr": espn["home_abbr"],
            "away_abbr": espn["away_abbr"],
            "home_score": espn["home_score"],
            "away_score": espn["away_score"],
            "rivalry": espn["rivalry"],
        }

    result = compute_signal(
        p_live=espn["p_live_yes"],
        time_left=espn["time_left"],
        time_total=espn["time_total"],
        a_yes=market["a_yes"],
        a_no=market["a_no"],
        fee_open=parse_float(config.get("fee_open"), 0.01),
        min_ev=parse_float(config.get("min_ev"), 0.03),
        alpha=parse_float(config.get("alpha"), 0.7),
        roundtrip_cost=parse_float(config.get("roundtrip_cost"), 0.04),
        spread_buffer=parse_float(config.get("spread_buffer"), 0.02),
        account_equity=parse_float(config.get("account_equity"), None) if config.get("account_equity") not in {"", None} else None,
        per_trade_risk_pct=parse_float(config.get("per_trade_risk_pct"), 0.0025),
        daily_stop_pct=parse_float(config.get("daily_stop_pct"), 0.01),
    )

    return {
        "provider": provider,
        "market": market_id,
        "espn_event_id": espn_event_id,
        "state": "SIGNAL",
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
        "home_team": espn["home_team"],
        "away_team": espn["away_team"],
        "home_abbr": espn["home_abbr"],
        "away_abbr": espn["away_abbr"],
        "home_score": espn["home_score"],
        "away_score": espn["away_score"],
        "rivalry": espn["rivalry"],
        "a_yes": market["a_yes"],
        "a_no": market["a_no"],
        "ev_yes": result.ev_yes,
        "ev_no": result.ev_no,
        "best_ev": result.best_ev,
        "p_eff": result.p_eff,
        "required_exit_spread": result.required_exit_spread,
        "max_contracts": result.max_contracts,
    }


def build_winner_once(config: dict[str, Any]) -> dict[str, Any]:
    espn_sport = str(config.get("espn_sport") or "basketball")
    espn_league = str(config.get("espn_league") or "nba")
    espn_event_id = str(config.get("espn_event_id") or "").strip()
    if not espn_event_id:
        raise ValueError("espn_event_id is required.")

    timeout = parse_float(config.get("timeout"), 6.0)
    require_live = parse_bool(config.get("require_live"), True)
    period_seconds = parse_float(config.get("period_seconds"), 720.0)
    regulation_periods = parse_int(config.get("regulation_periods"), 4)

    espn = get_espn_state(
        sport=espn_sport,
        league=espn_league,
        event_id=espn_event_id,
        timeout=timeout,
        yes_team="home",
        period_seconds=period_seconds,
        regulation_periods=regulation_periods,
    )

    if require_live and espn["status_state"] != "in":
        return {
            "espn_event_id": espn_event_id,
            "state": "WAITING",
            "espn_status": espn["status_state"],
            "probability_mode": espn["probability_mode"],
            "p_home": espn["home_probability"],
            "p_away": 1.0 - espn["home_probability"],
            "time_left": espn["time_left"],
            "time_total": espn["time_total"],
            "period": espn["period"],
            "clock_seconds": espn["clock_seconds"],
            "home_team": espn["home_team"],
            "away_team": espn["away_team"],
            "home_abbr": espn["home_abbr"],
            "away_abbr": espn["away_abbr"],
            "home_score": espn["home_score"],
            "away_score": espn["away_score"],
            "rivalry": espn["rivalry"],
        }

    p_home = float(espn["home_probability"])
    p_away = 1.0 - p_home
    if p_home > p_away:
        guess_side = "home"
        guess_team = str(espn["home_abbr"] or espn["home_team"] or "HOME")
        guess_prob = p_home
    elif p_away > p_home:
        guess_side = "away"
        guess_team = str(espn["away_abbr"] or espn["away_team"] or "AWAY")
        guess_prob = p_away
    else:
        guess_side = "tie"
        guess_team = "TOSS_UP"
        guess_prob = p_home

    confidence = abs(p_home - 0.5) * 2.0

    return {
        "espn_event_id": espn_event_id,
        "state": "GUESS",
        "guess_side": guess_side,
        "guess_team": guess_team,
        "guess_prob": guess_prob,
        "confidence": confidence,
        "p_home": p_home,
        "p_away": p_away,
        "espn_status": espn["status_state"],
        "probability_mode": espn["probability_mode"],
        "time_left": espn["time_left"],
        "time_total": espn["time_total"],
        "period": espn["period"],
        "clock_seconds": espn["clock_seconds"],
        "home_team": espn["home_team"],
        "away_team": espn["away_team"],
        "home_abbr": espn["home_abbr"],
        "away_abbr": espn["away_abbr"],
        "home_score": espn["home_score"],
        "away_score": espn["away_score"],
        "rivalry": espn["rivalry"],
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "SignalDashboard/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep local server logs concise.
        print(f"{self.address_string()} - {fmt % args}")

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status: int, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query, keep_blank_values=True)

        try:
            if path == "/":
                if not INDEX_HTML.exists():
                    self._send_html(HTTPStatus.NOT_FOUND, "index.html not found")
                    return
                self._send_html(HTTPStatus.OK, INDEX_HTML.read_text(encoding="utf-8"))
                return

            if path == "/api/health":
                self._send_json(HTTPStatus.OK, {"ok": True})
                return

            if path == "/api/dev/reload-token":
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "token": compute_reload_token(),
                        "files": [path.name for path in HOTRELOAD_WATCH_FILES],
                    },
                )
                return

            if path == "/api/discover/espn":
                payload = {
                    "items": discover_espn(
                        sport=query_first(query, "sport", "basketball"),
                        league=query_first(query, "league", "nba"),
                        date=query_first(query, "date", ""),
                        state=query_first(query, "state", "all"),
                        query=query_first(query, "query", ""),
                        limit=max(1, min(parse_int(query_first(query, "limit", "10"), 10), 50)),
                    )
                }
                self._send_json(HTTPStatus.OK, payload)
                return

            if path == "/api/discover/kalshi":
                pair_only = parse_bool(query_first(query, "pair_only", "0"), False)
                pair_filter = None
                if pair_only:
                    sport = query_first(query, "sport", "basketball")
                    league = query_first(query, "league", "nba")
                    event_id = query_first(query, "event_id", "").strip()
                    if not event_id:
                        raise ValueError("event_id is required when pair_only=1.")
                    pair_filter = build_pair_filter(
                        get_espn_event_meta(sport=sport, league=league, event_id=event_id)
                    )
                payload = {
                    "items": discover_kalshi(
                        query=query_first(query, "query", ""),
                        limit=max(1, min(parse_int(query_first(query, "limit", "10"), 10), 50)),
                        pair_filter=pair_filter,
                    )
                }
                self._send_json(HTTPStatus.OK, payload)
                return

            if path == "/api/discover/polymarket":
                pair_only = parse_bool(query_first(query, "pair_only", "0"), False)
                pair_filter = None
                if pair_only:
                    sport = query_first(query, "sport", "basketball")
                    league = query_first(query, "league", "nba")
                    event_id = query_first(query, "event_id", "").strip()
                    if not event_id:
                        raise ValueError("event_id is required when pair_only=1.")
                    pair_filter = build_pair_filter(
                        get_espn_event_meta(sport=sport, league=league, event_id=event_id)
                    )
                payload = {
                    "items": discover_polymarket(
                        query=query_first(query, "query", ""),
                        limit=max(1, min(parse_int(query_first(query, "limit", "10"), 10), 50)),
                        nba_only=parse_bool(query_first(query, "nba_only", "1"), True),
                        pair_filter=pair_filter,
                    )
                }
                self._send_json(HTTPStatus.OK, payload)
                return

            if path == "/api/autofill":
                payload = autofill_market(
                    provider=query_first(query, "provider", "kalshi_espn"),
                    sport=query_first(query, "sport", "basketball"),
                    league=query_first(query, "league", "nba"),
                    event_id=query_first(query, "event_id", ""),
                    yes_team=query_first(query, "yes_team", "home"),
                    timeout=parse_float(query_first(query, "timeout", "8"), 8.0),
                )
                self._send_json(HTTPStatus.OK, payload)
                return

            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/signal", "/api/winner"}:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        try:
            raw_len = self.headers.get("Content-Length", "0")
            content_len = max(0, int(raw_len))
            data = self.rfile.read(content_len) if content_len > 0 else b"{}"
            payload = json.loads(data.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object.")
            if parsed.path == "/api/winner":
                result = build_winner_once(payload)
            else:
                result = build_signal_once(payload)
            result["ts"] = payload.get("ts") or ""
            self._send_json(HTTPStatus.OK, result)
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local signal dashboard web server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--hotreload", action="store_true", help="Restart server automatically when watched files change.")
    parser.add_argument("--hotreload-interval", type=float, default=1.0, help="Hotreload polling interval in seconds.")
    args = parser.parse_args()

    if args.port <= 0 or args.port > 65535:
        raise SystemExit("Input error: --port must be in 1..65535")
    if args.hotreload_interval <= 0:
        raise SystemExit("Input error: --hotreload-interval must be > 0")

    if not args.hotreload:
        server = ThreadingHTTPServer((args.host, args.port), Handler)
        print(f"Dashboard running on http://{args.host}:{args.port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0

    child_cmd = [
        sys.executable,
        str((ROOT / "dashboard_server.py").resolve()),
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    last_token = compute_reload_token()
    print(
        f"Dashboard hotreload supervisor on http://{args.host}:{args.port} "
        f"(interval={args.hotreload_interval:.1f}s)",
        flush=True,
    )
    while True:
        child: subprocess.Popen[Any] | None = None
        try:
            child = subprocess.Popen(child_cmd)
            print(f"[hotreload] started child pid={child.pid}", flush=True)
            while True:
                time.sleep(args.hotreload_interval)
                current_token = compute_reload_token()
                if current_token != last_token:
                    last_token = current_token
                    print("[hotreload] file change detected; restarting child...", flush=True)
                    terminate_process(child)
                    break
                code = child.poll()
                if code is not None:
                    print(f"[hotreload] child exited with code={code}; restarting...", flush=True)
                    break
        except Exception as exc:
            print(f"[hotreload] supervisor error: {exc}; restarting loop...", flush=True)
            time.sleep(max(args.hotreload_interval, 0.2))
        except KeyboardInterrupt:
            if child is not None:
                terminate_process(child)
            print("")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
