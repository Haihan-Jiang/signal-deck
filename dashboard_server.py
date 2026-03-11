#!/usr/bin/env python3
"""Local dashboard server for realtime signal experiments.

Run:
  python3 dashboard_server.py --host 127.0.0.1 --port 8787
Then open:
  http://127.0.0.1:8787
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse
from zoneinfo import ZoneInfo

from live_experiment_signal import get_espn_state, get_kalshi_prices, get_polymarket_prices
from signal_engine import compute_signal


ROOT = Path(__file__).resolve().parent
INDEX_HTML = ROOT / "web" / "index.html"
LOG_DIR = Path(os.environ.get("SIGNAL_DECK_LOG_DIR", str(Path.home() / ".signal-deck" / "logs"))).expanduser()
DRYRUN_CSV = LOG_DIR / "dryrun_signals.csv"
DRYRUN_TXT = LOG_DIR / "dryrun_latest.txt"
DRYRUN_CRON_LOG = LOG_DIR / "dryrun_cron.log"
DRYRUN_TRADE_CSV = LOG_DIR / "dryrun_trades.csv"
DRYRUN_TRADE_STATE = LOG_DIR / "dryrun_trade_state.json"
TELEGRAM_ENV_PATH = Path.home() / ".signal-deck" / "runtime" / "telegram.env"
TELEGRAM_DASHBOARD_ALERT_STATE = LOG_DIR / "telegram_dashboard_alert_state.json"
FIXED_TELEGRAM_ALERT_RULES = {
    "winner_max_time_left": 180.0,
    "winner_min_lead": 6.0,
    "winner_p_min": 0.80,
    "winner_p_max": 0.95,
    "winner_min_edge": 0.025,
    "winner_max_buy_price": 0.91,
}
HOTRELOAD_WATCH_FILES = (
    ROOT / "dashboard_server.py",
    ROOT / "live_experiment_signal.py",
    ROOT / "signal_engine.py",
    INDEX_HTML,
)

HISTORY_GATE_CACHE_TTL_SEC = 15 * 60
HISTORY_GATE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def file_signature(path: Path) -> str:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return f"{path.name}:missing"
    return f"{path.name}:{stat.st_mtime_ns}:{stat.st_size}"


def compute_reload_token(paths: tuple[Path, ...] = HOTRELOAD_WATCH_FILES) -> str:
    joined = "|".join(file_signature(path) for path in paths)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12]


def _load_shell_exports(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            out[key] = value
    return out


def _resolve_telegram_runtime_config() -> dict[str, Any]:
    env_file_values = _load_shell_exports(TELEGRAM_ENV_PATH)
    token = str(
        os.environ.get("SIGNAL_DECK_TELEGRAM_BOT_TOKEN")
        or env_file_values.get("SIGNAL_DECK_TELEGRAM_BOT_TOKEN")
        or ""
    ).strip()
    single_chat = str(
        os.environ.get("SIGNAL_DECK_TELEGRAM_CHAT_ID")
        or env_file_values.get("SIGNAL_DECK_TELEGRAM_CHAT_ID")
        or ""
    ).strip()
    raw_targets = str(
        os.environ.get("SIGNAL_DECK_TELEGRAM_CHAT_IDS")
        or env_file_values.get("SIGNAL_DECK_TELEGRAM_CHAT_IDS")
        or ""
    ).strip()
    chat_ids: list[str] = []
    seen: set[str] = set()
    for raw in [raw_targets, single_chat]:
        parts = [item.strip() for item in raw.replace("\n", ",").split(",")]
        for part in parts:
            if not part or part in seen:
                continue
            seen.add(part)
            chat_ids.append(part)
    return {
        "token": token,
        "chat_ids": chat_ids,
        "env_path": str(TELEGRAM_ENV_PATH),
    }


def _load_dashboard_alert_state() -> dict[str, Any]:
    if not TELEGRAM_DASHBOARD_ALERT_STATE.exists():
        return {"alerts": {}}
    try:
        payload = json.loads(TELEGRAM_DASHBOARD_ALERT_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"alerts": {}}
    if not isinstance(payload, dict):
        return {"alerts": {}}
    alerts = payload.get("alerts")
    if not isinstance(alerts, dict):
        payload["alerts"] = {}
    return payload


def _save_dashboard_alert_state(payload: dict[str, Any]) -> None:
    TELEGRAM_DASHBOARD_ALERT_STATE.parent.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
    TELEGRAM_DASHBOARD_ALERT_STATE.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _send_telegram_text(token: str, chat_ids: list[str], text: str, timeout: float = 8.0) -> dict[str, Any]:
    from urllib.request import Request, urlopen

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    sent = 0
    errors: list[str] = []
    for chat_id in chat_ids:
        body = urlencode(
            {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": "true",
            }
        ).encode("utf-8")
        request = Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
        reply = json.loads(raw)
        if not isinstance(reply, dict) or not reply.get("ok"):
            errors.append(f"{chat_id}: {raw}")
        else:
            sent += 1
    return {"sent": sent, "errors": errors}


def _fmt_alert_num(value: Any, digits: int = 4) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "-"


def build_dashboard_telegram_alert(payload: dict[str, Any]) -> dict[str, Any]:
    state_text = str(payload.get("state") or "").upper()
    if state_text != "GUESS":
        return {"ok": False, "skipped": True, "reason": f"state={state_text or '-'} is not GUESS"}

    config = _resolve_telegram_runtime_config()
    token = str(config.get("token") or "").strip()
    chat_ids = list(config.get("chat_ids") or [])
    if not token or not chat_ids:
        return {"ok": False, "skipped": True, "reason": "telegram targets not configured"}

    event_id = str(payload.get("espn_event_id") or payload.get("event_id") or "").strip()
    guess_side = str(payload.get("guess_side") or "").strip().lower()
    guess_team = str(payload.get("guess_team") or "").strip().upper()
    if not event_id or guess_side not in {"home", "away"}:
        return {"ok": False, "skipped": True, "reason": "missing event_id or guess_side"}

    for key in (
        "winner_max_time_left",
        "winner_min_lead",
        "winner_p_min",
        "winner_p_max",
        "winner_min_edge",
        "winner_max_buy_price",
    ):
        value = payload.get(key)
        if value is None:
            continue
        current = parse_float(value, FIXED_TELEGRAM_ALERT_RULES[key])
        if abs(current - FIXED_TELEGRAM_ALERT_RULES[key]) > 1e-9:
            return {
                "ok": False,
                "skipped": True,
                "reason": f"{key} mismatch",
                "expected": FIXED_TELEGRAM_ALERT_RULES[key],
                "received": current,
            }

    time_left = parse_float(payload.get("time_left"), -1.0)
    lead = parse_float(payload.get("lead"), -1.0)
    guess_prob = parse_float(payload.get("guess_prob"), -1.0)
    target_max_buy_price = parse_float(payload.get("target_max_buy_price"), -1.0)
    blockers: list[str] = []
    if time_left < 0 or time_left > FIXED_TELEGRAM_ALERT_RULES["winner_max_time_left"]:
        blockers.append(
            f"time_left {time_left:.0f}s > {FIXED_TELEGRAM_ALERT_RULES['winner_max_time_left']:.0f}s"
            if time_left >= 0
            else "missing time_left"
        )
    if lead < FIXED_TELEGRAM_ALERT_RULES["winner_min_lead"]:
        blockers.append(f"lead {lead:.0f} < {FIXED_TELEGRAM_ALERT_RULES['winner_min_lead']:.0f}")
    if not (
        FIXED_TELEGRAM_ALERT_RULES["winner_p_min"]
        <= guess_prob
        <= FIXED_TELEGRAM_ALERT_RULES["winner_p_max"]
    ):
        blockers.append(
            f"guess_prob {guess_prob:.4f} not in "
            f"[{FIXED_TELEGRAM_ALERT_RULES['winner_p_min']:.2f}, {FIXED_TELEGRAM_ALERT_RULES['winner_p_max']:.2f}]"
        )
    if target_max_buy_price < 0 or target_max_buy_price > FIXED_TELEGRAM_ALERT_RULES["winner_max_buy_price"]:
        blockers.append(
            f"target_max_buy {target_max_buy_price:.4f} > {FIXED_TELEGRAM_ALERT_RULES['winner_max_buy_price']:.4f}"
            if target_max_buy_price >= 0
            else "missing target_max_buy_price"
        )
    if blockers:
        return {
            "ok": False,
            "skipped": True,
            "reason": "; ".join(blockers),
            "rules": FIXED_TELEGRAM_ALERT_RULES,
        }

    dedupe_key = str(payload.get("dedupe_key") or f"{event_id}|{guess_side}|{guess_team}").strip()
    cooldown_sec = max(30, min(parse_int(payload.get("cooldown_sec"), 900), 24 * 3600))

    state_payload = _load_dashboard_alert_state()
    alerts = state_payload.get("alerts") if isinstance(state_payload.get("alerts"), dict) else {}
    now_ts = time.time()
    existing = alerts.get(dedupe_key)
    if isinstance(existing, dict):
        last_sent_ts = existing.get("last_sent_ts")
        try:
            last_sent = float(last_sent_ts)
        except (TypeError, ValueError):
            last_sent = None
        if last_sent is not None and now_ts - last_sent < cooldown_sec:
            return {
                "ok": True,
                "skipped": True,
                "reason": "cooldown",
                "cooldown_remaining_sec": max(0, int(cooldown_sec - (now_ts - last_sent))),
                "dedupe_key": dedupe_key,
            }

    rivalry = str(payload.get("rivalry") or event_id)
    reason = " ".join(str(payload.get("reason") or "").splitlines()).strip() or "-"
    text = "\n".join(
        [
            "PAGE SIGNAL",
            "source=dashboard_live",
            "strategy=max_profit_95",
            f"game={rivalry}",
            f"action=BUY {guess_team or '-'}",
            f"guess_prob={_fmt_alert_num(payload.get('guess_prob'), 4)}",
            f"lead={_fmt_alert_num(payload.get('lead'), 0)}",
            f"time_left={_fmt_alert_num(payload.get('time_left'), 0)}s",
            f"target_max_buy={_fmt_alert_num(payload.get('target_max_buy_price'), 4)}",
            f"reason={reason}",
        ]
    )
    delivery = _send_telegram_text(token, chat_ids, text, timeout=parse_float(payload.get("timeout"), 8.0))
    if delivery["errors"]:
        raise RuntimeError("Telegram sendMessage failed: " + " | ".join(delivery["errors"]))

    alerts[dedupe_key] = {
        "event_id": event_id,
        "guess_side": guess_side,
        "guess_team": guess_team,
        "last_sent_ts": now_ts,
        "rivalry": rivalry,
    }
    state_payload["alerts"] = alerts
    _save_dashboard_alert_state(state_payload)
    return {
        "ok": True,
        "sent": delivery["sent"],
        "chat_ids": chat_ids,
        "dedupe_key": dedupe_key,
        "cooldown_sec": cooldown_sec,
    }


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


def _read_competitors_from_competition(comp: dict[str, Any]) -> dict[str, Any]:
    competitors = comp.get("competitors")
    if not isinstance(competitors, list):
        competitors = []

    result: dict[str, Any] = {
        "home_name": "",
        "away_name": "",
        "home_abbr": "",
        "away_abbr": "",
        "home_score": None,
        "away_score": None,
        "home_winner": None,
        "away_winner": None,
    }

    for row in competitors:
        if not isinstance(row, dict):
            continue
        side = str(row.get("homeAway") or "").lower()
        team = row.get("team") if isinstance(row.get("team"), dict) else {}
        team_name = str(team.get("displayName") or team.get("shortDisplayName") or "").strip()
        team_abbr = str(team.get("abbreviation") or "").strip().upper()
        winner_raw = row.get("winner")
        winner = bool(winner_raw) if isinstance(winner_raw, bool) else None

        score: float | None = None
        raw_score = row.get("score")
        if raw_score is not None:
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                score = None

        if side == "home":
            result["home_name"] = team_name
            result["home_abbr"] = team_abbr
            result["home_score"] = score
            result["home_winner"] = winner
        elif side == "away":
            result["away_name"] = team_name
            result["away_abbr"] = team_abbr
            result["away_score"] = score
            result["away_winner"] = winner

    return result


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
        teams = _read_competitors_from_competition(comp) if isinstance(comp, dict) else {}
        final_winner = ""
        if teams.get("home_winner") is True:
            final_winner = "home"
        elif teams.get("away_winner") is True:
            final_winner = "away"
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
                "home_name": teams.get("home_name"),
                "away_name": teams.get("away_name"),
                "home_abbr": teams.get("home_abbr"),
                "away_abbr": teams.get("away_abbr"),
                "home_score": teams.get("home_score"),
                "away_score": teams.get("away_score"),
                "final_winner": final_winner,
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


def _parse_score_value(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_clock_display_to_seconds(display_clock: str) -> float | None:
    text = display_clock.strip()
    if not text:
        return None
    parts = text.split(":")
    try:
        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = float(parts[1])
            return minutes * 60.0 + seconds
        if len(parts) == 1:
            return float(parts[0])
    except ValueError:
        return None
    return None


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _estimate_home_probability_from_margin(margin: float, time_left: float, time_total: float) -> float:
    if abs(margin) < 1e-9:
        return 0.5
    if time_total <= 0:
        progress = 0.0
    else:
        progress = 1.0 - max(0.0, min(float(time_left) / float(time_total), 1.0))
    scale = 14.0 - 9.0 * progress
    scale = max(2.5, scale)
    z = margin / scale
    p = 1.0 / (1.0 + math.exp(-z))
    return _clamp01(max(0.01, min(0.99, p)))


def _compute_play_time_left(
    period: int,
    display_clock: str,
    period_seconds: float,
    regulation_periods: int,
    time_total: float,
) -> float:
    if period <= 0:
        period = 1
    clock_seconds = _parse_clock_display_to_seconds(display_clock)
    if clock_seconds is None:
        # If clock is missing, assume 0 for deterministic replay output.
        clock_seconds = 0.0
    if period <= regulation_periods:
        remaining_periods = max(0, regulation_periods - period)
        time_left = clock_seconds + remaining_periods * period_seconds
    else:
        # Overtime: keep same semantics as live mode.
        time_left = clock_seconds
    return max(0.0, min(time_left, time_total))


def _extract_summary_match_meta(summary: dict[str, Any], event_id: str) -> dict[str, Any]:
    competitions = summary.get("header", {}).get("competitions")
    if not isinstance(competitions, list) or not competitions:
        raise ValueError("ESPN summary missing competitions.")
    comp0 = competitions[0] if isinstance(competitions[0], dict) else {}
    teams = _read_competitors_from_competition(comp0)

    home_score = teams.get("home_score")
    away_score = teams.get("away_score")
    final_winner = ""
    if teams.get("home_winner") is True:
        final_winner = "home"
    elif teams.get("away_winner") is True:
        final_winner = "away"
    elif isinstance(home_score, (int, float)) and isinstance(away_score, (int, float)):
        if home_score > away_score:
            final_winner = "home"
        elif away_score > home_score:
            final_winner = "away"
        else:
            final_winner = "tie"

    status = comp0.get("status") if isinstance(comp0, dict) else {}
    status_type = status.get("type") if isinstance(status, dict) else {}
    state = str(status_type.get("state") or "").lower() if isinstance(status_type, dict) else ""
    short_detail = str(status_type.get("shortDetail") or "") if isinstance(status_type, dict) else ""

    home_abbr = str(teams.get("home_abbr") or "").upper()
    away_abbr = str(teams.get("away_abbr") or "").upper()
    rivalry = f"{away_abbr} @ {home_abbr}".strip(" @")

    return {
        "event_id": event_id,
        "state": state,
        "status": short_detail,
        "home_name": str(teams.get("home_name") or ""),
        "away_name": str(teams.get("away_name") or ""),
        "home_abbr": home_abbr,
        "away_abbr": away_abbr,
        "home_score": home_score,
        "away_score": away_score,
        "final_winner": final_winner,
        "rivalry": rivalry,
    }


def _sample_timeline(rows: list[dict[str, Any]], max_points: int) -> list[dict[str, Any]]:
    if max_points <= 0 or len(rows) <= max_points:
        return rows
    step = (len(rows) - 1) / float(max_points - 1)
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for i in range(max_points):
        idx = int(round(i * step))
        idx = max(0, min(len(rows) - 1, idx))
        if idx in seen:
            continue
        seen.add(idx)
        out.append(rows[idx])
    if out[-1] is not rows[-1]:
        out.append(rows[-1])
    return out


def build_history_replay(config: dict[str, Any]) -> dict[str, Any]:
    sport = str(config.get("espn_sport") or config.get("sport") or "basketball").strip() or "basketball"
    league = str(config.get("espn_league") or config.get("league") or "nba").strip() or "nba"
    event_id = str(config.get("espn_event_id") or config.get("event_id") or "").strip()
    if not event_id:
        raise ValueError("event_id is required.")

    timeout = parse_float(config.get("timeout"), 8.0)
    period_seconds = parse_float(config.get("period_seconds"), 720.0)
    regulation_periods = parse_int(config.get("regulation_periods"), 4)
    winner_max_time_left = parse_float(config.get("winner_max_time_left"), 360.0)
    winner_min_lead = parse_float(config.get("winner_min_lead"), 10.0)
    winner_p_min = parse_float(config.get("winner_p_min"), 0.80)
    winner_p_max = parse_float(config.get("winner_p_max"), 0.97)
    winner_min_edge = parse_float(config.get("winner_min_edge"), 0.025)
    fee_total = parse_float(config.get("fee_total"), 0.02)
    max_points = max(40, min(parse_int(config.get("max_points"), 220), 900))
    include_timeline = parse_bool(config.get("include_timeline"), True)

    if period_seconds <= 0:
        raise ValueError("period_seconds must be > 0.")
    if regulation_periods <= 0:
        raise ValueError("regulation_periods must be > 0.")
    if winner_max_time_left < 0:
        raise ValueError("winner_max_time_left must be >= 0.")
    if winner_min_lead < 0:
        raise ValueError("winner_min_lead must be >= 0.")
    if winner_min_edge < 0:
        raise ValueError("winner_min_edge must be >= 0.")
    if not (0 <= winner_p_min <= 1 and 0 <= winner_p_max <= 1 and winner_p_min <= winner_p_max):
        raise ValueError("winner_p_min/winner_p_max must satisfy 0 <= min <= max <= 1.")

    summary_url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/summary?event={event_id}"
    summary = fetch_json(summary_url, timeout=timeout)
    if not isinstance(summary, dict):
        raise ValueError("ESPN summary payload must be a JSON object.")

    match_meta = _extract_summary_match_meta(summary, event_id=event_id)
    plays = summary.get("plays")
    if not isinstance(plays, list) or not plays:
        raise ValueError("ESPN summary missing play-by-play data.")

    winprob_map: dict[str, float] = {}
    winprobability = summary.get("winprobability")
    if isinstance(winprobability, list):
        for row in winprobability:
            if not isinstance(row, dict):
                continue
            play_id = str(row.get("playId") or "").strip()
            if not play_id:
                continue
            value = row.get("homeWinPercentage")
            if value is None:
                continue
            try:
                p_home = float(value)
            except (TypeError, ValueError):
                continue
            if 0.0 <= p_home <= 1.0:
                winprob_map[play_id] = p_home

    time_total = float(period_seconds * regulation_periods)
    timeline: list[dict[str, Any]] = []
    signal_rows: list[dict[str, Any]] = []
    for idx, play in enumerate(plays):
        if not isinstance(play, dict):
            continue

        home_score = _parse_score_value(play.get("homeScore"))
        away_score = _parse_score_value(play.get("awayScore"))
        if home_score is None or away_score is None:
            continue

        period_obj = play.get("period") if isinstance(play.get("period"), dict) else {}
        period = parse_int(period_obj.get("number"), 1)
        clock_obj = play.get("clock") if isinstance(play.get("clock"), dict) else {}
        display_clock = str(clock_obj.get("displayValue") or "")
        time_left = _compute_play_time_left(
            period=period,
            display_clock=display_clock,
            period_seconds=period_seconds,
            regulation_periods=regulation_periods,
            time_total=time_total,
        )
        progress = 1.0 - (_clamp01(time_left / time_total) if time_total > 0 else 0.0)

        play_id = str(play.get("id") or play.get("sequenceNumber") or idx)
        p_home = winprob_map.get(play_id)
        probability_source = "winprobability"
        if p_home is None:
            p_home = _estimate_home_probability_from_margin(home_score - away_score, time_left=time_left, time_total=time_total)
            probability_source = "score_time_fallback"

        p_home = _clamp01(float(p_home))
        p_away = 1.0 - p_home
        margin = home_score - away_score
        lead = abs(margin)

        guess_side = "tie"
        guess_team = "TIE"
        guess_prob = 0.5
        action = None
        if margin > 0:
            guess_side = "home"
            guess_team = str(match_meta["home_abbr"] or match_meta["home_name"] or "HOME")
            guess_prob = p_home
            action = "BUY_HOME"
        elif margin < 0:
            guess_side = "away"
            guess_team = str(match_meta["away_abbr"] or match_meta["away_name"] or "AWAY")
            guess_prob = p_away
            action = "BUY_AWAY"

        time_ok = time_left <= winner_max_time_left
        lead_ok = lead >= winner_min_lead
        prob_ok = winner_p_min <= guess_prob <= winner_p_max if guess_side in {"home", "away"} else False
        break_even_buy_price = max(0.0, guess_prob - fee_total)
        recommended_max_buy_price = max(0.0, break_even_buy_price - winner_min_edge)
        pass_all = guess_side in {"home", "away"} and time_ok and lead_ok and prob_ok and recommended_max_buy_price > 0.0

        row = {
            "idx": idx,
            "play_id": play_id,
            "period": period,
            "clock": display_clock,
            "text": str(play.get("shortDescription") or play.get("text") or ""),
            "home_score": home_score,
            "away_score": away_score,
            "lead": lead,
            "lead_signed": margin,
            "time_left": time_left,
            "time_total": time_total,
            "progress": progress,
            "p_home": p_home,
            "p_away": p_away,
            "guess_side": guess_side,
            "guess_team": guess_team,
            "guess_prob": guess_prob,
            "action": action,
            "time_ok": time_ok,
            "lead_ok": lead_ok,
            "prob_ok": prob_ok,
            "pass_all": pass_all,
            "break_even_buy_price": break_even_buy_price,
            "recommended_max_buy_price": recommended_max_buy_price,
            "probability_source": probability_source,
        }
        timeline.append(row)
        if pass_all:
            signal_rows.append(row)

    if not timeline:
        raise ValueError("回放失败：比赛没有可用比分时间线。")

    final_winner = str(match_meta.get("final_winner") or "")
    signal_preview: list[dict[str, Any]] = []
    signal_hit_count = 0
    for row in signal_rows:
        hit = final_winner in {"home", "away"} and row["guess_side"] == final_winner
        if hit:
            signal_hit_count += 1
        signal_preview.append(
            {
                "period": row["period"],
                "clock": row["clock"],
                "time_left": row["time_left"],
                "lead": row["lead"],
                "guess_side": row["guess_side"],
                "guess_team": row["guess_team"],
                "guess_prob": row["guess_prob"],
                "action": row["action"],
                "recommended_max_buy_price": row["recommended_max_buy_price"],
                "break_even_buy_price": row["break_even_buy_price"],
                "hit": hit,
            }
        )

    signal_win_rate = signal_hit_count / len(signal_rows) if signal_rows else None
    first_signal = signal_preview[0] if signal_preview else None
    best_signal = max(signal_preview, key=lambda x: float(x["recommended_max_buy_price"])) if signal_preview else None
    recommendation: dict[str, Any]
    if first_signal is None:
        recommendation = {
            "status": "NO_SIGNAL",
            "reason": "该场比赛未触发你的三项过滤条件。",
        }
    else:
        recommendation = {
            "status": "BUY",
            "entry_style": "first_signal",
            "action": first_signal["action"],
            "team": first_signal["guess_team"],
            "team_side": first_signal["guess_side"],
            "guess_prob": first_signal["guess_prob"],
            "lead": first_signal["lead"],
            "time_left": first_signal["time_left"],
            "recommended_max_buy_price": first_signal["recommended_max_buy_price"],
            "break_even_buy_price": first_signal["break_even_buy_price"],
            "historical_result": "WIN" if first_signal["hit"] else "LOSE",
        }

    payload = {
        "event_id": event_id,
        "sport": sport,
        "league": league,
        "match": match_meta,
        "rules": {
            "winner_max_time_left": winner_max_time_left,
            "winner_min_lead": winner_min_lead,
            "winner_p_min": winner_p_min,
            "winner_p_max": winner_p_max,
            "winner_min_edge": winner_min_edge,
            "fee_total": fee_total,
        },
        "metrics": {
            "timeline_points": len(timeline),
            "signals": len(signal_rows),
            "signal_hits": signal_hit_count,
            "signal_win_rate": signal_win_rate,
            "first_signal": first_signal,
            "best_signal": best_signal,
        },
        "recommendation": recommendation,
    }
    if include_timeline:
        payload["timeline"] = _sample_timeline(timeline, max_points=max_points)
        payload["signals_preview"] = signal_preview[:20]
    else:
        payload["timeline"] = []
        payload["signals_preview"] = []
    return payload


def _history_gate_cache_key(payload: dict[str, Any]) -> str:
    compact = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha1(compact.encode("utf-8")).hexdigest()


def _recent_date_tokens(days: int, tz_name: str = "America/Los_Angeles") -> list[str]:
    now = datetime.now(ZoneInfo(tz_name))
    out: list[str] = []
    for offset in range(1, days + 1):
        token = (now - timedelta(days=offset)).strftime("%Y%m%d")
        out.append(token)
    return out


def build_history_gate(config: dict[str, Any]) -> dict[str, Any]:
    sport = str(config.get("espn_sport") or config.get("sport") or "basketball").strip() or "basketball"
    league = str(config.get("espn_league") or config.get("league") or "nba").strip() or "nba"
    timeout = parse_float(config.get("timeout"), 8.0)
    lookback_days = max(3, min(parse_int(config.get("lookback_days"), 30), 120))
    max_games = max(20, min(parse_int(config.get("max_games"), 300), 600))
    min_games = max(1, min(parse_int(config.get("min_games"), 80), 600))
    min_trigger_games = max(1, min(parse_int(config.get("min_trigger_games"), 20), 600))
    min_first_hit_rate = parse_float(config.get("min_first_hit_rate"), 0.93)
    use_cache = parse_bool(config.get("use_cache"), True)

    if not (0.0 <= min_first_hit_rate <= 1.0):
        raise ValueError("min_first_hit_rate must be in [0,1].")

    winner_max_time_left = parse_float(config.get("winner_max_time_left"), 360.0)
    winner_min_lead = parse_float(config.get("winner_min_lead"), 10.0)
    winner_p_min = parse_float(config.get("winner_p_min"), 0.80)
    winner_p_max = parse_float(config.get("winner_p_max"), 0.98)
    winner_min_edge = parse_float(config.get("winner_min_edge"), 0.025)
    fee_total = parse_float(config.get("fee_total"), 0.02)

    if not (0 <= winner_p_min <= 1 and 0 <= winner_p_max <= 1 and winner_p_min <= winner_p_max):
        raise ValueError("winner_p_min/winner_p_max must satisfy 0 <= min <= max <= 1.")

    gate_inputs = {
        "sport": sport,
        "league": league,
        "lookback_days": lookback_days,
        "max_games": max_games,
        "min_games": min_games,
        "min_trigger_games": min_trigger_games,
        "min_first_hit_rate": min_first_hit_rate,
        "winner_max_time_left": winner_max_time_left,
        "winner_min_lead": winner_min_lead,
        "winner_p_min": winner_p_min,
        "winner_p_max": winner_p_max,
        "winner_min_edge": winner_min_edge,
        "fee_total": fee_total,
    }
    cache_key = _history_gate_cache_key(gate_inputs)
    now_ts = time.time()
    if use_cache:
        cached = HISTORY_GATE_CACHE.get(cache_key)
        if cached is not None:
            cached_ts, cached_payload = cached
            age = max(0, int(now_ts - cached_ts))
            if age <= HISTORY_GATE_CACHE_TTL_SEC:
                payload = dict(cached_payload)
                payload["cache"] = {
                    "hit": True,
                    "age_seconds": age,
                    "ttl_seconds": HISTORY_GATE_CACHE_TTL_SEC,
                }
                return payload

    post_events: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for token in _recent_date_tokens(lookback_days):
        rows = discover_espn(
            sport=sport,
            league=league,
            date=token,
            state="post",
            query="",
            limit=50,
        )
        for row in rows:
            event_id = str(row.get("event_id") or "").strip()
            if not event_id or event_id in seen_ids:
                continue
            seen_ids.add(event_id)
            post_events.append(row)
            if len(post_events) >= max_games:
                break
        if len(post_events) >= max_games:
            break

    games_analyzed = 0
    trigger_games = 0
    signals_total = 0
    first_signal_total = 0
    first_signal_hits = 0
    errors = 0
    sample_first_signals: list[dict[str, Any]] = []

    for row in post_events:
        event_id = str(row.get("event_id") or "").strip()
        if not event_id:
            continue
        try:
            replay = build_history_replay(
                {
                    "sport": sport,
                    "league": league,
                    "event_id": event_id,
                    "timeout": timeout,
                    "winner_max_time_left": winner_max_time_left,
                    "winner_min_lead": winner_min_lead,
                    "winner_p_min": winner_p_min,
                    "winner_p_max": winner_p_max,
                    "winner_min_edge": winner_min_edge,
                    "fee_total": fee_total,
                    "max_points": 40,
                    "include_timeline": False,
                }
            )
        except Exception:
            errors += 1
            continue

        games_analyzed += 1
        metrics = replay.get("metrics") if isinstance(replay.get("metrics"), dict) else {}
        signal_count = parse_int(metrics.get("signals"), 0)
        signals_total += signal_count
        if signal_count > 0:
            trigger_games += 1

        first_signal = metrics.get("first_signal")
        if isinstance(first_signal, dict) and first_signal:
            first_signal_total += 1
            hit = bool(first_signal.get("hit"))
            if hit:
                first_signal_hits += 1
            if len(sample_first_signals) < 8:
                match = replay.get("match") if isinstance(replay.get("match"), dict) else {}
                sample_first_signals.append(
                    {
                        "event_id": event_id,
                        "rivalry": match.get("rivalry") or row.get("name") or event_id,
                        "time_left": first_signal.get("time_left"),
                        "lead": first_signal.get("lead"),
                        "guess_side": first_signal.get("guess_side"),
                        "guess_prob": first_signal.get("guess_prob"),
                        "recommended_max_buy_price": first_signal.get("recommended_max_buy_price"),
                        "hit": hit,
                    }
                )

    trigger_rate_game = trigger_games / games_analyzed if games_analyzed > 0 else 0.0
    first_signal_hit_rate = first_signal_hits / first_signal_total if first_signal_total > 0 else None

    reasons: list[str] = []
    if games_analyzed < min_games:
        reasons.append(f"样本不足：{games_analyzed} < min_games {min_games}")
    if trigger_games < min_trigger_games:
        reasons.append(f"触发场次不足：{trigger_games} < min_trigger_games {min_trigger_games}")
    if first_signal_hit_rate is None:
        reasons.append("历史窗口内没有触发首信号，无法评估命中率。")
    elif first_signal_hit_rate < min_first_hit_rate:
        reasons.append(
            f"首信号命中率不足：{first_signal_hit_rate:.4f} < min_first_hit_rate {min_first_hit_rate:.4f}"
        )

    passed = not reasons
    gate_message = "PASS：可启用历史稳健模式。" if passed else "BLOCK：未通过历史门控。"

    payload = {
        "mode": "robust_history_gate",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sport": sport,
        "league": league,
        "window": {
            "lookback_days": lookback_days,
            "max_games": max_games,
            "min_games": min_games,
        },
        "rules": {
            "winner_max_time_left": winner_max_time_left,
            "winner_min_lead": winner_min_lead,
            "winner_p_min": winner_p_min,
            "winner_p_max": winner_p_max,
            "winner_min_edge": winner_min_edge,
            "fee_total": fee_total,
        },
        "metrics": {
            "games_seen": len(post_events),
            "games_analyzed": games_analyzed,
            "errors": errors,
            "trigger_games": trigger_games,
            "trigger_rate_game": trigger_rate_game,
            "signals_total": signals_total,
            "first_signal_total": first_signal_total,
            "first_signal_hits": first_signal_hits,
            "first_signal_hit_rate": first_signal_hit_rate,
        },
        "gate": {
            "passed": passed,
            "message": gate_message,
            "reasons": reasons,
            "min_trigger_games": min_trigger_games,
            "min_first_hit_rate": min_first_hit_rate,
        },
        "samples": sample_first_signals,
        "cache": {
            "hit": False,
            "age_seconds": 0,
            "ttl_seconds": HISTORY_GATE_CACHE_TTL_SEC,
        },
    }

    if use_cache:
        # Keep cache payload immutable for future reuse.
        HISTORY_GATE_CACHE[cache_key] = (now_ts, dict(payload))
    return payload


def read_dryrun_latest(limit: int = 40) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    if DRYRUN_CSV.exists():
        with DRYRUN_CSV.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            rows = [dict(row) for row in reader]
    if limit > 0:
        rows = rows[-limit:]
    rows.reverse()

    txt = ""
    if DRYRUN_TXT.exists():
        txt = DRYRUN_TXT.read_text(encoding="utf-8")

    return {
        "txt": txt,
        "rows": rows,
        "trades": read_dryrun_trades(limit=max(1, min(limit, 100))),
        "csv_exists": DRYRUN_CSV.exists(),
        "txt_exists": DRYRUN_TXT.exists(),
        "csv_mtime": DRYRUN_CSV.stat().st_mtime if DRYRUN_CSV.exists() else None,
        "txt_mtime": DRYRUN_TXT.stat().st_mtime if DRYRUN_TXT.exists() else None,
        "csv_size": DRYRUN_CSV.stat().st_size if DRYRUN_CSV.exists() else 0,
        "txt_size": DRYRUN_TXT.stat().st_size if DRYRUN_TXT.exists() else 0,
        "trades_csv_exists": DRYRUN_TRADE_CSV.exists(),
        "trades_csv_mtime": DRYRUN_TRADE_CSV.stat().st_mtime if DRYRUN_TRADE_CSV.exists() else None,
        "trades_csv_size": DRYRUN_TRADE_CSV.stat().st_size if DRYRUN_TRADE_CSV.exists() else 0,
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


def _read_trade_state() -> dict[str, Any]:
    if not DRYRUN_TRADE_STATE.exists():
        return {}
    try:
        payload = json.loads(DRYRUN_TRADE_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _to_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def read_dryrun_trades(limit: int = 20) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    if DRYRUN_TRADE_CSV.exists():
        with DRYRUN_TRADE_CSV.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            rows = [dict(row) for row in reader]

    recent_rows = rows[-limit:] if limit > 0 else rows[:]
    recent_rows.reverse()

    closed_trades = 0
    wins = 0
    losses = 0
    voids = 0
    gross_profit = 0.0
    gross_loss = 0.0
    net_pnl = 0.0

    for row in rows:
        if str(row.get("trade_phase") or "").upper() != "CLOSE":
            continue
        closed_trades += 1
        result = str(row.get("result") or "").upper()
        if result == "WIN":
            wins += 1
        elif result == "LOSS":
            losses += 1
        elif result == "VOID":
            voids += 1
        total_pnl = _to_float_or_none(row.get("total_pnl")) or 0.0
        net_pnl += total_pnl
        if total_pnl > 0:
            gross_profit += total_pnl
        elif total_pnl < 0:
            gross_loss += total_pnl

    trade_state = _read_trade_state()
    raw_open_positions = trade_state.get("open_positions")
    open_positions = len(raw_open_positions) if isinstance(raw_open_positions, dict) else 0
    settings = trade_state.get("settings") if isinstance(trade_state.get("settings"), dict) else {}

    settled_decisions = wins + losses
    win_rate = wins / settled_decisions if settled_decisions > 0 else None
    avg_pnl = net_pnl / closed_trades if closed_trades > 0 else None

    return {
        "rows": recent_rows,
        "summary": {
            "closed_trades": closed_trades,
            "wins": wins,
            "losses": losses,
            "voids": voids,
            "open_positions": open_positions,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "net_pnl": net_pnl,
            "avg_pnl": avg_pnl,
            "win_rate": win_rate,
            "trade_budget": _to_float_or_none(settings.get("trade_budget")),
            "contracts": _to_float_or_none(settings.get("contracts")),
            "sizing_mode": str(settings.get("sizing_mode") or ""),
        },
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

    provider = str(config.get("provider") or "").strip()
    market_id = str(config.get("market") or "").strip()
    yes_team = str(config.get("yes_team") or "home").lower()
    if yes_team not in {"home", "away"}:
        raise ValueError("yes_team must be 'home' or 'away'.")

    timeout = parse_float(config.get("timeout"), 6.0)
    require_live = parse_bool(config.get("require_live"), True)
    period_seconds = parse_float(config.get("period_seconds"), 720.0)
    regulation_periods = parse_int(config.get("regulation_periods"), 4)
    winner_max_time_left = parse_float(config.get("winner_max_time_left"), 360.0)
    winner_min_lead = parse_float(config.get("winner_min_lead"), 10.0)
    winner_p_min = parse_float(config.get("winner_p_min"), 0.80)
    winner_p_max = parse_float(config.get("winner_p_max"), 0.97)
    winner_min_edge = parse_float(config.get("winner_min_edge"), 0.025)
    winner_max_buy_price = parse_float(config.get("winner_max_buy_price"), 0.91)
    fee_total = parse_float(config.get("fee_total"), 0.02)

    if winner_max_time_left < 0:
        raise ValueError("winner_max_time_left must be >= 0.")
    if winner_min_lead < 0:
        raise ValueError("winner_min_lead must be >= 0.")
    if winner_min_edge < 0:
        raise ValueError("winner_min_edge must be >= 0.")
    if not (0 <= winner_max_buy_price <= 1):
        raise ValueError("winner_max_buy_price must be in [0,1].")
    if fee_total < 0:
        raise ValueError("fee_total must be >= 0.")
    if not (0 <= winner_p_min <= 1 and 0 <= winner_p_max <= 1 and winner_p_min <= winner_p_max):
        raise ValueError("winner_p_min/winner_p_max must satisfy 0 <= min <= max <= 1.")

    espn = get_espn_state(
        sport=espn_sport,
        league=espn_league,
        event_id=espn_event_id,
        timeout=timeout,
        yes_team="home",
        period_seconds=period_seconds,
        regulation_periods=regulation_periods,
    )

    p_home = float(espn["home_probability"])
    p_away = 1.0 - p_home
    confidence = abs(p_home - 0.5) * 2.0

    home_score_raw = espn.get("home_score")
    away_score_raw = espn.get("away_score")
    home_score: float | None
    away_score: float | None
    if home_score_raw is None or away_score_raw is None:
        home_score = None
        away_score = None
    else:
        home_score = float(home_score_raw)
        away_score = float(away_score_raw)
    lead: float | None = None
    if home_score is not None and away_score is not None:
        lead = abs(home_score - away_score)

    common = {
        "espn_event_id": espn_event_id,
        "provider": provider,
        "market": market_id,
        "espn_status": espn["status_state"],
        "probability_mode": espn["probability_mode"],
        "p_home": p_home,
        "p_away": p_away,
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
        "lead": lead,
        "confidence": confidence,
        "winner_rules": {
            "max_time_left": winner_max_time_left,
            "min_lead": winner_min_lead,
            "p_min": winner_p_min,
            "p_max": winner_p_max,
            "min_edge": winner_min_edge,
            "max_buy_price": winner_max_buy_price,
            "fee_total": fee_total,
        },
    }

    if require_live and espn["status_state"] != "in":
        return {
            "state": "WAITING",
            **common,
        }

    if home_score is None or away_score is None:
        return {
            "state": "NO_TRADE",
            "reason": "ESPN 暂无比分，无法判断分差。",
            **common,
        }

    if home_score > away_score:
        guess_side = "home"
        guess_team = str(espn["home_abbr"] or espn["home_team"] or "HOME")
        guess_prob = p_home
    elif away_score > home_score:
        guess_side = "away"
        guess_team = str(espn["away_abbr"] or espn["away_team"] or "AWAY")
        guess_prob = p_away
    else:
        return {
            "state": "NO_TRADE",
            "reason": "当前平分，跳过。",
            "guess_side": "tie",
            "guess_team": "TOSS_UP",
            "guess_prob": p_home,
            "suggested_action": None,
            "break_even_buy_price": None,
            "recommended_max_buy_price": None,
            "target_max_buy_price": None,
            **common,
        }

    suggested_action = "BUY_HOME" if guess_side == "home" else "BUY_AWAY"
    break_even_buy_price = max(0.0, guess_prob - fee_total)
    recommended_max_buy_price = max(0.0, break_even_buy_price - winner_min_edge)
    target_max_buy_price = min(winner_max_buy_price, recommended_max_buy_price)

    blockers: list[str] = []
    if espn["time_left"] > winner_max_time_left:
        blockers.append(f"剩余时间 {espn['time_left']:.0f}s > 阈值 {winner_max_time_left:.0f}s")
    if lead is None or lead < winner_min_lead:
        blockers.append(f"分差 {0.0 if lead is None else lead:.0f} < 阈值 {winner_min_lead:.0f}")
    if not (winner_p_min <= guess_prob <= winner_p_max):
        blockers.append(f"领先方胜率 {guess_prob:.3f} 不在区间 [{winner_p_min:.3f}, {winner_p_max:.3f}]")

    market: dict[str, Any] | None = None
    market_error: str | None = None
    if provider and market_id:
        try:
            if provider == "kalshi_espn":
                market = get_kalshi_prices(market_id, timeout=timeout)
            elif provider == "polymarket_espn":
                market = get_polymarket_prices(market_id, timeout=timeout)
            else:
                market_error = "未知 provider，无法读取盘口价格。"
        except Exception as exc:
            market_error = str(exc)

    a_yes = None if market is None else market.get("a_yes")
    a_no = None if market is None else market.get("a_no")
    action = None
    entry_price = None
    edge = None
    if market is not None and isinstance(a_yes, (float, int)) and isinstance(a_no, (float, int)):
        if guess_side == yes_team:
            action = "BUY_YES"
            entry_price = float(a_yes)
        else:
            action = "BUY_NO"
            entry_price = float(a_no)
        if entry_price > winner_max_buy_price:
            blockers.append(f"买入价 {entry_price:.4f} > 上限 {winner_max_buy_price:.4f}")
        edge = guess_prob - entry_price
        if edge < winner_min_edge:
            blockers.append(f"边际 {edge:.4f} < 阈值 {winner_min_edge:.4f}")

    payload = {
        "guess_side": guess_side,
        "guess_team": guess_team,
        "guess_prob": guess_prob,
        "suggested_action": suggested_action,
        "action": action,
        "a_yes": a_yes,
        "a_no": a_no,
        "entry_price": entry_price,
        "edge": edge,
        "break_even_buy_price": break_even_buy_price,
        "recommended_max_buy_price": recommended_max_buy_price,
        "target_max_buy_price": target_max_buy_price,
        "market_error": market_error,
        **common,
    }
    if blockers:
        return {
            "state": "NO_TRADE",
            "reason": "; ".join(blockers),
            **payload,
        }
    return {
        "state": "GUESS",
        "reason": "通过末段过滤，可执行。",
        **payload,
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

    def _send_bytes(self, status: int, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
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

            if path == "/api/dryrun/latest":
                payload = read_dryrun_latest(
                    limit=max(1, min(parse_int(query_first(query, "limit", "30"), 30), 200))
                )
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "txt": payload["txt"],
                        "rows": payload["rows"],
                        "trades": payload["trades"],
                        "files": {
                            "csv": "/logs/dryrun_signals.csv",
                            "txt": "/logs/dryrun_latest.txt",
                            "cron_log": "/logs/dryrun_cron.log",
                            "trades_csv": "/logs/dryrun_trades.csv",
                        },
                        "meta": {
                            "csv_exists": payload["csv_exists"],
                            "txt_exists": payload["txt_exists"],
                            "csv_mtime": payload["csv_mtime"],
                            "txt_mtime": payload["txt_mtime"],
                            "csv_size": payload["csv_size"],
                            "txt_size": payload["txt_size"],
                            "trades_csv_exists": payload["trades_csv_exists"],
                            "trades_csv_mtime": payload["trades_csv_mtime"],
                            "trades_csv_size": payload["trades_csv_size"],
                        },
                    },
                )
                return

            if path == "/logs/dryrun_signals.csv":
                if not DRYRUN_CSV.exists():
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "dryrun_signals.csv not found"})
                    return
                self._send_bytes(HTTPStatus.OK, DRYRUN_CSV.read_bytes(), "text/csv; charset=utf-8")
                return

            if path == "/logs/dryrun_latest.txt":
                if not DRYRUN_TXT.exists():
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "dryrun_latest.txt not found"})
                    return
                self._send_bytes(HTTPStatus.OK, DRYRUN_TXT.read_bytes(), "text/plain; charset=utf-8")
                return

            if path == "/logs/dryrun_cron.log":
                if not DRYRUN_CRON_LOG.exists():
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "dryrun_cron.log not found"})
                    return
                self._send_bytes(HTTPStatus.OK, DRYRUN_CRON_LOG.read_bytes(), "text/plain; charset=utf-8")
                return

            if path == "/logs/dryrun_trades.csv":
                if not DRYRUN_TRADE_CSV.exists():
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "dryrun_trades.csv not found"})
                    return
                self._send_bytes(HTTPStatus.OK, DRYRUN_TRADE_CSV.read_bytes(), "text/csv; charset=utf-8")
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

            if path == "/api/history/replay":
                payload = build_history_replay(
                    {
                        "sport": query_first(query, "sport", "basketball"),
                        "league": query_first(query, "league", "nba"),
                        "event_id": query_first(query, "event_id", ""),
                        "timeout": parse_float(query_first(query, "timeout", "8"), 8.0),
                        "period_seconds": parse_float(query_first(query, "period_seconds", "720"), 720.0),
                        "regulation_periods": parse_int(query_first(query, "regulation_periods", "4"), 4),
                        "winner_max_time_left": parse_float(query_first(query, "winner_max_time_left", "360"), 360.0),
                        "winner_min_lead": parse_float(query_first(query, "winner_min_lead", "10"), 10.0),
                        "winner_p_min": parse_float(query_first(query, "winner_p_min", "0.80"), 0.80),
                        "winner_p_max": parse_float(query_first(query, "winner_p_max", "0.97"), 0.97),
                        "winner_min_edge": parse_float(query_first(query, "winner_min_edge", "0.025"), 0.025),
                        "fee_total": parse_float(query_first(query, "fee_total", "0.02"), 0.02),
                        "max_points": parse_int(query_first(query, "max_points", "220"), 220),
                        "include_timeline": parse_bool(query_first(query, "include_timeline", "1"), True),
                    }
                )
                self._send_json(HTTPStatus.OK, payload)
                return

            if path == "/api/history/gate":
                payload = build_history_gate(
                    {
                        "sport": query_first(query, "sport", "basketball"),
                        "league": query_first(query, "league", "nba"),
                        "timeout": parse_float(query_first(query, "timeout", "8"), 8.0),
                        "lookback_days": parse_int(query_first(query, "lookback_days", "30"), 30),
                        "max_games": parse_int(query_first(query, "max_games", "300"), 300),
                        "min_games": parse_int(query_first(query, "min_games", "80"), 80),
                        "min_trigger_games": parse_int(query_first(query, "min_trigger_games", "20"), 20),
                        "min_first_hit_rate": parse_float(query_first(query, "min_first_hit_rate", "0.93"), 0.93),
                        "winner_max_time_left": parse_float(query_first(query, "winner_max_time_left", "360"), 360.0),
                        "winner_min_lead": parse_float(query_first(query, "winner_min_lead", "10"), 10.0),
                        "winner_p_min": parse_float(query_first(query, "winner_p_min", "0.80"), 0.80),
                        "winner_p_max": parse_float(query_first(query, "winner_p_max", "0.98"), 0.98),
                        "winner_min_edge": parse_float(query_first(query, "winner_min_edge", "0.025"), 0.025),
                        "fee_total": parse_float(query_first(query, "fee_total", "0.02"), 0.02),
                        "use_cache": parse_bool(query_first(query, "use_cache", "1"), True),
                    }
                )
                self._send_json(HTTPStatus.OK, payload)
                return

            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/signal", "/api/winner", "/api/telegram/notify-signal"}:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        try:
            raw_len = self.headers.get("Content-Length", "0")
            content_len = max(0, int(raw_len))
            data = self.rfile.read(content_len) if content_len > 0 else b"{}"
            payload = json.loads(data.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object.")
            if parsed.path == "/api/telegram/notify-signal":
                result = build_dashboard_telegram_alert(payload)
            elif parsed.path == "/api/winner":
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
