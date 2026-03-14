#!/usr/bin/env python3
"""Polymarket execution skeleton with paper / armed / live modes.

This module keeps execution logic server-side and records every order intent.
The default mode is paper: record the intent, but never send a real order.
"""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_LOG_DIR = Path(os.environ.get("SIGNAL_DECK_LOG_DIR", str(Path.home() / ".signal-deck" / "logs"))).expanduser()
DEFAULT_RUNTIME_DIR = Path.home() / ".signal-deck" / "runtime"
DEFAULT_ENV_PATH = DEFAULT_RUNTIME_DIR / "polymarket.env"
DEFAULT_EXECUTION_CSV_PATH = DEFAULT_LOG_DIR / "polymarket_execution.csv"
DEFAULT_EXECUTION_STATE_PATH = DEFAULT_LOG_DIR / "polymarket_execution_state.json"
DEFAULT_MODE = "paper"

EXECUTION_COLUMNS = [
    "run_ts",
    "mode",
    "source",
    "event_id",
    "rivalry",
    "market_id",
    "market_source",
    "question",
    "side",
    "team",
    "guess_prob",
    "lead",
    "time_left",
    "price_limit",
    "contracts",
    "stake_amount",
    "intent_status",
    "execution_status",
    "external_order_id",
    "reason",
    "payload_json",
]


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _load_shell_exports(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
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


def _parse_mode(value: Any) -> str:
    mode = str(value or DEFAULT_MODE).strip().lower()
    if mode not in {"paper", "armed", "live"}:
        return DEFAULT_MODE
    return mode


def load_runtime_config(env_path: Path | None = None, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    env_path = env_path or DEFAULT_ENV_PATH
    file_values = _load_shell_exports(env_path)
    merged: dict[str, Any] = {}
    merged.update(file_values)
    if overrides:
        merged.update({k: v for k, v in overrides.items() if v is not None})

    def pick(key: str, default: str = "") -> str:
        return str(os.environ.get(key) or merged.get(key) or default).strip()

    mode = _parse_mode(
        pick("SIGNAL_DECK_EXECUTION_MODE") or pick("POLYMARKET_EXECUTION_MODE") or DEFAULT_MODE
    )
    csv_path_raw = pick("SIGNAL_DECK_EXECUTION_CSV_PATH") or pick("POLYMARKET_EXECUTION_CSV_PATH")
    state_path_raw = pick("SIGNAL_DECK_EXECUTION_STATE_PATH") or pick("POLYMARKET_EXECUTION_STATE_PATH")

    private_key = pick("POLYMARKET_PRIVATE_KEY")
    proxy_address = pick("POLYMARKET_PROXY_ADDRESS") or pick("POLYMARKET_FUNDER")
    api_key = pick("POLYMARKET_API_KEY")
    api_secret = pick("POLYMARKET_API_SECRET")
    api_passphrase = pick("POLYMARKET_API_PASSPHRASE")
    clob_host = pick("POLYMARKET_CLOB_HOST", "https://clob.polymarket.com")
    chain_id = pick("POLYMARKET_CHAIN_ID", "137")

    creds_present = bool(private_key and proxy_address and api_key and api_secret and api_passphrase)

    return {
        "mode": mode,
        "env_path": str(env_path),
        "csv_path": Path(csv_path_raw).expanduser() if csv_path_raw else DEFAULT_EXECUTION_CSV_PATH,
        "state_path": Path(state_path_raw).expanduser() if state_path_raw else DEFAULT_EXECUTION_STATE_PATH,
        "clob_host": clob_host,
        "chain_id": chain_id,
        "private_key_present": bool(private_key),
        "proxy_address_present": bool(proxy_address),
        "api_key_present": bool(api_key),
        "api_secret_present": bool(api_secret),
        "api_passphrase_present": bool(api_passphrase),
        "creds_present": creds_present,
    }


def _append_execution_row(csv_path: Path, row: dict[str, str]) -> None:
    _ensure_parent(csv_path)
    write_header = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=EXECUTION_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def _write_execution_state(state_path: Path, payload: dict[str, Any]) -> None:
    _ensure_parent(state_path)
    state_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def build_order_intent(
    *,
    run_ts: str,
    source: str,
    signal: dict[str, Any],
    contracts: float,
    stake_amount: float,
    market_id: str = "",
    market_source: str = "",
    question: str = "",
) -> dict[str, Any]:
    event_id = str(signal.get("espn_event_id") or signal.get("event_id") or "").strip()
    return {
        "run_ts": run_ts,
        "source": str(source or "signal"),
        "event_id": event_id,
        "rivalry": str(signal.get("rivalry") or ""),
        "market_id": str(market_id or ""),
        "market_source": str(market_source or ""),
        "question": str(question or ""),
        "side": str(signal.get("guess_side") or "").upper(),
        "team": str(signal.get("guess_team") or ""),
        "guess_prob": signal.get("guess_prob"),
        "lead": signal.get("lead"),
        "time_left": signal.get("time_left"),
        "price_limit": signal.get("target_max_buy_price"),
        "contracts": contracts,
        "stake_amount": stake_amount,
        "raw_signal": signal,
    }


def _fmt_num(value: Any, digits: int = 4) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return ""


def _fmt_amount(value: Any, digits: int = 2) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return ""


def _build_row(intent: dict[str, Any], mode: str, intent_status: str, execution_status: str, reason: str, external_order_id: str = "") -> dict[str, str]:
    payload_json = json.dumps(
        {
            "event_id": intent.get("event_id"),
            "market_id": intent.get("market_id"),
            "side": intent.get("side"),
            "team": intent.get("team"),
            "price_limit": intent.get("price_limit"),
            "contracts": intent.get("contracts"),
            "stake_amount": intent.get("stake_amount"),
            "market_source": intent.get("market_source"),
            "source": intent.get("source"),
        },
        ensure_ascii=True,
        sort_keys=True,
    )
    return {
        "run_ts": str(intent.get("run_ts") or datetime.now().isoformat(timespec="seconds")),
        "mode": mode,
        "source": str(intent.get("source") or ""),
        "event_id": str(intent.get("event_id") or ""),
        "rivalry": str(intent.get("rivalry") or ""),
        "market_id": str(intent.get("market_id") or ""),
        "market_source": str(intent.get("market_source") or ""),
        "question": str(intent.get("question") or ""),
        "side": str(intent.get("side") or ""),
        "team": str(intent.get("team") or ""),
        "guess_prob": _fmt_num(intent.get("guess_prob"), 4),
        "lead": _fmt_num(intent.get("lead"), 0),
        "time_left": _fmt_num(intent.get("time_left"), 1),
        "price_limit": _fmt_num(intent.get("price_limit"), 4),
        "contracts": _fmt_amount(intent.get("contracts"), 2),
        "stake_amount": _fmt_amount(intent.get("stake_amount"), 2),
        "intent_status": intent_status,
        "execution_status": execution_status,
        "external_order_id": external_order_id,
        "reason": str(reason or ""),
        "payload_json": payload_json,
    }


def execute_order_intent(
    intent: dict[str, Any],
    *,
    env_path: Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = load_runtime_config(env_path=env_path, overrides=overrides)
    mode = str(config["mode"])
    market_id = str(intent.get("market_id") or "").strip()
    price_limit = intent.get("price_limit")
    contracts = intent.get("contracts")

    reason = ""
    intent_status = "accepted"
    execution_status = "queued"
    external_order_id = ""

    if not market_id:
        intent_status = "rejected"
        execution_status = "no_market"
        reason = "No Polymarket market id resolved for this event."
    elif price_limit is None:
        intent_status = "rejected"
        execution_status = "no_price_limit"
        reason = "Signal has no target_max_buy_price."
    elif contracts is None or float(contracts) <= 0:
        intent_status = "rejected"
        execution_status = "no_contracts"
        reason = "Contracts <= 0."
    elif mode == "paper":
        execution_status = "paper_recorded"
        reason = "Paper mode: recorded intent only."
    elif mode == "armed":
        execution_status = "armed_ready"
        reason = "Armed mode: intent validated and recorded, but live order not sent."
    else:
        if not config["creds_present"]:
            intent_status = "rejected"
            execution_status = "live_blocked_missing_creds"
            reason = "Live mode requested, but Polymarket credentials are incomplete."
        else:
            intent_status = "blocked"
            execution_status = "live_not_implemented"
            reason = "Live execution skeleton is present, but order placement is not wired yet."

    row = _build_row(intent, mode, intent_status, execution_status, reason, external_order_id=external_order_id)
    _append_execution_row(config["csv_path"], row)
    _write_execution_state(
        config["state_path"],
        {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "mode": mode,
            "last_row": row,
            "config": {
                "env_path": config["env_path"],
                "csv_path": str(config["csv_path"]),
                "state_path": str(config["state_path"]),
                "clob_host": config["clob_host"],
                "chain_id": config["chain_id"],
                "creds_present": config["creds_present"],
            },
        },
    )
    return {
        "ok": intent_status == "accepted" and execution_status in {"paper_recorded", "armed_ready"},
        "mode": mode,
        "row": row,
        "config": {
            "env_path": config["env_path"],
            "csv_path": str(config["csv_path"]),
            "state_path": str(config["state_path"]),
            "clob_host": config["clob_host"],
            "chain_id": config["chain_id"],
            "creds_present": config["creds_present"],
        },
    }


def read_execution_latest(limit: int = 40, *, env_path: Path | None = None, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    config = load_runtime_config(env_path=env_path, overrides=overrides)
    csv_path: Path = config["csv_path"]
    state_path: Path = config["state_path"]
    rows: list[dict[str, str]] = []
    if csv_path.exists():
        with csv_path.open("r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
    rows = rows[-max(1, min(int(limit), 200)) :]

    summary = {
        "total_rows": len(rows),
        "paper_recorded": sum(1 for row in rows if str(row.get("execution_status") or "") == "paper_recorded"),
        "armed_ready": sum(1 for row in rows if str(row.get("execution_status") or "") == "armed_ready"),
        "rejected": sum(1 for row in rows if str(row.get("intent_status") or "") == "rejected"),
        "mode": config["mode"],
    }

    latest_state: dict[str, Any] = {}
    if state_path.exists():
        try:
            latest_state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            latest_state = {}

    return {
        "rows": rows,
        "summary": summary,
        "config": {
            "mode": config["mode"],
            "env_path": config["env_path"],
            "csv_path": str(csv_path),
            "state_path": str(state_path),
            "clob_host": config["clob_host"],
            "chain_id": config["chain_id"],
            "creds_present": config["creds_present"],
        },
        "state": latest_state,
        "meta": {
            "csv_exists": csv_path.exists(),
            "csv_mtime": csv_path.stat().st_mtime if csv_path.exists() else None,
            "csv_size": csv_path.stat().st_size if csv_path.exists() else 0,
            "state_exists": state_path.exists(),
            "state_mtime": state_path.stat().st_mtime if state_path.exists() else None,
        },
    }
