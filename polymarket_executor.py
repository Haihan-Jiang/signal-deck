#!/usr/bin/env python3
"""Polymarket execution skeleton with paper / armed / live modes.

This module keeps execution logic server-side and records every order intent.
The default mode is paper: record the intent, but never send a real order.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_LOG_DIR = Path(os.environ.get("SIGNAL_DECK_LOG_DIR", str(Path.home() / ".signal-deck" / "logs"))).expanduser()
DEFAULT_RUNTIME_DIR = Path.home() / ".signal-deck" / "runtime"
DEFAULT_ENV_PATH = DEFAULT_RUNTIME_DIR / "polymarket.env"
DEFAULT_EXECUTION_CSV_PATH = DEFAULT_LOG_DIR / "polymarket_execution.csv"
DEFAULT_EXECUTION_STATE_PATH = DEFAULT_LOG_DIR / "polymarket_execution_state.json"
DEFAULT_PROBE_STATE_PATH = DEFAULT_LOG_DIR / "polymarket_probe.json"
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


def _parse_int(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return default


def _load_runtime_values(env_path: Path | None = None, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    env_path = env_path or DEFAULT_ENV_PATH
    file_values = _load_shell_exports(env_path)
    merged: dict[str, Any] = {}
    merged.update(file_values)
    if overrides:
        merged.update({k: v for k, v in overrides.items() if v is not None})

    def pick(key: str, default: str = "") -> str:
        return str(os.environ.get(key) or merged.get(key) or default).strip()

    return {
        "mode": _parse_mode(
            pick("SIGNAL_DECK_EXECUTION_MODE") or pick("POLYMARKET_EXECUTION_MODE") or DEFAULT_MODE
        ),
        "env_path": env_path,
        "csv_path_raw": pick("SIGNAL_DECK_EXECUTION_CSV_PATH") or pick("POLYMARKET_EXECUTION_CSV_PATH"),
        "state_path_raw": pick("SIGNAL_DECK_EXECUTION_STATE_PATH") or pick("POLYMARKET_EXECUTION_STATE_PATH"),
        "private_key": pick("POLYMARKET_PRIVATE_KEY"),
        "proxy_address": pick("POLYMARKET_PROXY_ADDRESS") or pick("POLYMARKET_FUNDER"),
        "api_key": pick("POLYMARKET_API_KEY"),
        "api_secret": pick("POLYMARKET_API_SECRET"),
        "api_passphrase": pick("POLYMARKET_API_PASSPHRASE"),
        "clob_host": pick("POLYMARKET_CLOB_HOST", "https://clob.polymarket.com"),
        "chain_id": _parse_int(pick("POLYMARKET_CHAIN_ID", "137"), 137),
        "signature_type": _parse_int(pick("POLYMARKET_SIGNATURE_TYPE", "0"), 0),
        "relayer_host": pick("POLYMARKET_RELAYER_HOST", "https://relayer-v2.polymarket.com"),
        "relayer_api_key": pick("POLYMARKET_RELAYER_API_KEY"),
        "relayer_api_key_address": pick("POLYMARKET_RELAYER_API_KEY_ADDRESS"),
    }


def load_runtime_config(env_path: Path | None = None, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    values = _load_runtime_values(env_path=env_path, overrides=overrides)

    creds_present = bool(
        values["private_key"]
        and values["proxy_address"]
        and values["api_key"]
        and values["api_secret"]
        and values["api_passphrase"]
    )

    return {
        "mode": values["mode"],
        "env_path": str(values["env_path"]),
        "csv_path": Path(values["csv_path_raw"]).expanduser() if values["csv_path_raw"] else DEFAULT_EXECUTION_CSV_PATH,
        "state_path": Path(values["state_path_raw"]).expanduser() if values["state_path_raw"] else DEFAULT_EXECUTION_STATE_PATH,
        "probe_state_path": DEFAULT_PROBE_STATE_PATH,
        "clob_host": values["clob_host"],
        "chain_id": values["chain_id"],
        "signature_type": values["signature_type"],
        "relayer_host": values["relayer_host"],
        "private_key_present": bool(values["private_key"]),
        "proxy_address_present": bool(values["proxy_address"]),
        "api_key_present": bool(values["api_key"]),
        "api_secret_present": bool(values["api_secret"]),
        "api_passphrase_present": bool(values["api_passphrase"]),
        "relayer_api_key_present": bool(values["relayer_api_key"]),
        "relayer_api_key_address_present": bool(values["relayer_api_key_address"]),
        "creds_present": creds_present,
    }


def _mask_secret(value: str, *, keep_left: int = 6, keep_right: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= keep_left + keep_right:
        return value
    return f"{value[:keep_left]}...{value[-keep_right:]}"


def _write_shell_exports(path: Path, values: dict[str, str]) -> None:
    _ensure_parent(path)
    lines = ["# Managed by probe_polymarket_api.py"]
    for key in sorted(values):
        lines.append(f"export {key}={json.dumps(str(values[key]))}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _persist_api_creds(env_path: Path, api_key: str, api_secret: str, api_passphrase: str) -> None:
    values = _load_shell_exports(env_path)
    values["POLYMARKET_API_KEY"] = api_key
    values["POLYMARKET_API_SECRET"] = api_secret
    values["POLYMARKET_API_PASSPHRASE"] = api_passphrase
    _write_shell_exports(env_path, values)


def probe_polymarket_connection(
    *,
    env_path: Path | None = None,
    overrides: dict[str, Any] | None = None,
    persist_api_creds: bool = False,
) -> dict[str, Any]:
    values = _load_runtime_values(env_path=env_path, overrides=overrides)
    config = load_runtime_config(env_path=env_path, overrides=overrides)
    checked_at = datetime.now().isoformat(timespec="seconds")
    result: dict[str, Any] = {
        "ok": False,
        "checked_at": checked_at,
        "python": sys.version.split()[0],
        "config": {
            "env_path": str(values["env_path"]),
            "clob_host": values["clob_host"],
            "chain_id": values["chain_id"],
            "signature_type": values["signature_type"],
            "relayer_host": values["relayer_host"],
            "private_key_present": config["private_key_present"],
            "proxy_address_present": config["proxy_address_present"],
            "api_key_present": config["api_key_present"],
            "api_secret_present": config["api_secret_present"],
            "api_passphrase_present": config["api_passphrase_present"],
            "relayer_api_key_present": config["relayer_api_key_present"],
            "relayer_api_key_address_present": config["relayer_api_key_address_present"],
        },
        "clob": {},
        "relayer": {},
        "errors": [],
    }

    private_key = values["private_key"]
    if not private_key:
        result["errors"].append("POLYMARKET_PRIVATE_KEY missing")
        _write_execution_state(config["probe_state_path"], result)
        return result

    try:
        from eth_account import Account
        from py_clob_client.client import ClobClient
    except Exception as exc:
        result["errors"].append(
            f"Polymarket SDK unavailable: {exc}. Use Python >= 3.9.10 with py-clob-client installed."
        )
        _write_execution_state(config["probe_state_path"], result)
        return result

    signer_address = Account.from_key(private_key).address
    funder = values["proxy_address"] or signer_address
    result["clob"]["signer_address"] = signer_address
    result["clob"]["funder_address"] = funder

    try:
        l1 = ClobClient(
            values["clob_host"],
            chain_id=values["chain_id"],
            key=private_key,
            signature_type=values["signature_type"],
            funder=funder,
        )
        result["clob"]["get_ok"] = l1.get_ok()
        result["clob"]["server_time"] = l1.get_server_time()
        creds = l1.create_or_derive_api_creds()
        result["clob"]["derived_api_key"] = _mask_secret(str(creds.api_key), keep_left=8, keep_right=6)
        if persist_api_creds:
            _persist_api_creds(
                Path(values["env_path"]),
                api_key=str(creds.api_key),
                api_secret=str(creds.api_secret),
                api_passphrase=str(creds.api_passphrase),
            )
            result["clob"]["persisted_api_creds"] = True
        l2 = ClobClient(
            values["clob_host"],
            chain_id=values["chain_id"],
            key=private_key,
            creds=creds,
            signature_type=values["signature_type"],
            funder=funder,
        )
        api_keys_payload = l2.get_api_keys()
        api_keys = api_keys_payload.get("apiKeys") if isinstance(api_keys_payload, dict) else []
        orders_payload = l2.get_orders()
        open_orders_count = len(orders_payload) if isinstance(orders_payload, list) else 0
        result["clob"]["api_keys_count"] = len(api_keys or [])
        result["clob"]["open_orders_count"] = open_orders_count
        result["clob"]["status"] = "ok"
    except Exception as exc:
        result["clob"]["status"] = "error"
        result["errors"].append(f"CLOB probe failed: {exc}")

    relayer_api_key = values["relayer_api_key"]
    relayer_api_key_address = values["relayer_api_key_address"]
    if relayer_api_key and relayer_api_key_address:
        url = values["relayer_host"].rstrip("/") + "/relayer/api/keys"
        request = Request(
            url,
            headers={
                "RELAYER_API_KEY": relayer_api_key,
                "RELAYER_API_KEY_ADDRESS": relayer_api_key_address,
                "User-Agent": "PolymarketAutoTrader/1.0",
                "Accept": "application/json,text/plain,*/*",
            },
        )
        try:
            with urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
            keys = payload if isinstance(payload, list) else []
            result["relayer"] = {
                "status": "ok",
                "keys_count": len(keys),
                "key_address": relayer_api_key_address,
                "api_key": _mask_secret(relayer_api_key, keep_left=8, keep_right=6),
            }
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            result["relayer"] = {"status": "error", "http_status": exc.code}
            result["errors"].append(f"Relayer probe failed: HTTP {exc.code}: {body[:180]}")
        except URLError as exc:
            result["relayer"] = {"status": "error"}
            result["errors"].append(f"Relayer probe failed: {exc}")
    else:
        result["relayer"] = {"status": "skipped"}

    result["ok"] = result["clob"].get("status") == "ok" and result["relayer"].get("status") in {"ok", "skipped"}
    _write_execution_state(config["probe_state_path"], result)
    return result


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
    probe_state_path: Path = config["probe_state_path"]
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

    probe_state: dict[str, Any] = {}
    if probe_state_path.exists():
        try:
            probe_state = json.loads(probe_state_path.read_text(encoding="utf-8"))
        except Exception:
            probe_state = {}

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
        "probe": probe_state,
        "meta": {
            "csv_exists": csv_path.exists(),
            "csv_mtime": csv_path.stat().st_mtime if csv_path.exists() else None,
            "csv_size": csv_path.stat().st_size if csv_path.exists() else 0,
            "state_exists": state_path.exists(),
            "state_mtime": state_path.stat().st_mtime if state_path.exists() else None,
            "probe_exists": probe_state_path.exists(),
            "probe_mtime": probe_state_path.stat().st_mtime if probe_state_path.exists() else None,
        },
    }
