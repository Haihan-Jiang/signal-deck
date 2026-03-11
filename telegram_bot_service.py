#!/usr/bin/env python3
"""Lightweight Telegram bot command service for Signal Deck."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dashboard_server import read_dryrun_latest


DEFAULT_LOG_DIR = Path(
    os.environ.get("SIGNAL_DECK_LOG_DIR", str(Path.home() / ".signal-deck" / "logs"))
).expanduser()
DEFAULT_STATE_PATH = DEFAULT_LOG_DIR / "telegram_bot_state.json"
DRYRUN_LOG_PATH = DEFAULT_LOG_DIR / "dryrun_launchd.log"
TELEGRAM_LOG_PATH = DEFAULT_LOG_DIR / "telegram_bot.log"
DEFAULT_POLL_TIMEOUT = 25
DEFAULT_IDLE_SLEEP = 1.0
SERVICE_LABELS = {
    "dryrun": "com.haihan.signaldeck.dryrun",
    "telegrambot": "com.haihan.signaldeck.telegrambot",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Telegram bot command service for Signal Deck.")
    parser.add_argument("--bot-token", default=os.environ.get("SIGNAL_DECK_TELEGRAM_BOT_TOKEN", ""))
    parser.add_argument("--bot-username", default=os.environ.get("SIGNAL_DECK_TELEGRAM_BOT_USERNAME", ""))
    parser.add_argument("--state-path", type=Path, default=DEFAULT_STATE_PATH)
    parser.add_argument("--poll-timeout", type=int, default=DEFAULT_POLL_TIMEOUT)
    parser.add_argument("--idle-sleep", type=float, default=DEFAULT_IDLE_SLEEP)
    parser.add_argument("--once", action="store_true", help="Process available updates once and exit.")
    return parser


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def save_state(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def telegram_api(token: str, method: str, data: dict[str, Any] | None = None, timeout: float = 30.0) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{token}/{method}"
    body = None
    headers = {"User-Agent": "signal-deck-telegram/1.0"}
    if data is not None:
        body = urlencode({k: str(v) for k, v in data.items()}).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = Request(url, data=body, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not payload.get("ok"):
        raise RuntimeError(f"Telegram API {method} failed: {raw}")
    result = payload.get("result")
    return result if isinstance(result, dict) else {"result": result}


def telegram_get_me(token: str) -> dict[str, Any]:
    result = telegram_api(token, "getMe")
    return result.get("result", result) if "result" in result else result


def telegram_get_updates(token: str, offset: int | None, poll_timeout: int) -> list[dict[str, Any]]:
    data: dict[str, Any] = {"timeout": max(1, poll_timeout)}
    if offset is not None:
        data["offset"] = offset
    result = telegram_api(token, "getUpdates", data=data, timeout=poll_timeout + 5)
    if "result" in result and isinstance(result["result"], list):
        return result["result"]
    if isinstance(result, list):
        return result
    return []


def telegram_send_message(token: str, chat_id: Any, text: str, reply_to_message_id: Any | None = None) -> None:
    data: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "true",
    }
    if reply_to_message_id is not None:
        data["reply_to_message_id"] = reply_to_message_id
    telegram_api(token, "sendMessage", data=data)


def coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt_num(value: Any, digits: int = 4) -> str:
    number = coerce_float(value)
    if number is None:
        return "-"
    return f"{number:.{digits}f}"


def fmt_money(value: Any) -> str:
    number = coerce_float(value)
    if number is None:
        return "-"
    return f"${number:.2f}"


def latest_game_row(rows: list[dict[str, Any]], state_filter: str | None = None) -> dict[str, Any] | None:
    for row in rows:
        if str(row.get("row_type") or "").lower() != "game":
            continue
        if state_filter is not None and str(row.get("state") or "").upper() != state_filter.upper():
            continue
        return row
    return None


def parse_rules_line(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("Rules:"):
            return line.removeprefix("Rules:").strip()
    return "time_left<=180s, lead>=6, p=[0.80,0.95], min_edge=0.025, fee_total=0.020, max_buy=0.910"


def parse_generated_at(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("Generated At:"):
            return line.removeprefix("Generated At:").strip()
    return "-"


def build_start_text(bot_username: str) -> str:
    handle = f"@{bot_username}" if bot_username else "@your_bot"
    return "\n".join(
        [
            "Signal Deck bot is online.",
            "Commands:",
            f"/status or /status{handle}",
            f"/lastsignal or /lastsignal{handle}",
            f"/botstatus or /botstatus{handle}",
            f"/chatid or /chatid{handle}",
            f"/help or /help{handle}",
        ]
    )


def build_status_text() -> str:
    latest = read_dryrun_latest(limit=40)
    rows = latest.get("rows") if isinstance(latest.get("rows"), list) else []
    txt = str(latest.get("txt") or "")
    trades = latest.get("trades") if isinstance(latest.get("trades"), dict) else {}
    summary = trades.get("summary") if isinstance(trades.get("summary"), dict) else {}
    signal_row = latest_game_row(rows, state_filter="GUESS")
    if signal_row is None:
        signal_row = latest_game_row(rows)

    lines = [
        "Signal Deck status",
        "strategy=max_profit_95",
        f"rules={parse_rules_line(txt)}",
        f"snapshot={parse_generated_at(txt)}",
        f"net_pnl={fmt_money(summary.get('net_pnl'))}",
        f"wins={summary.get('wins', '-')} losses={summary.get('losses', '-')} open={summary.get('open_positions', '-')}",
    ]
    if signal_row is not None:
        lines.extend(
            [
                f"latest_game={signal_row.get('rivalry') or signal_row.get('event_id') or '-'}",
                f"latest_state={signal_row.get('state') or '-'}",
                f"latest_action={signal_row.get('guess_team') or signal_row.get('suggested_action') or '-'}",
                f"latest_p={fmt_num(signal_row.get('guess_prob'), 4)}",
                f"latest_time_left={fmt_num(signal_row.get('time_left'), 0)}s",
            ]
        )
    else:
        lines.append("latest_game=-")
    return "\n".join(lines)


def build_lastsignal_text() -> str:
    latest = read_dryrun_latest(limit=100)
    rows = latest.get("rows") if isinstance(latest.get("rows"), list) else []
    signal_row = latest_game_row(rows, state_filter="GUESS")
    if signal_row is None:
        return "No recent GUESS signal."
    return "\n".join(
        [
            "Last signal",
            f"game={signal_row.get('rivalry') or signal_row.get('event_id') or '-'}",
            f"state={signal_row.get('state') or '-'}",
            f"action=BUY {signal_row.get('guess_team') or '-'}",
            f"guess_prob={fmt_num(signal_row.get('guess_prob'), 4)}",
            f"lead={fmt_num(signal_row.get('lead'), 0)}",
            f"time_left={fmt_num(signal_row.get('time_left'), 0)}s",
            f"target_max_buy={fmt_num(signal_row.get('target_max_buy_price'), 4)}",
            f"reason={str(signal_row.get('reason') or '-')}",
            f"run_ts={signal_row.get('run_ts') or '-'}",
        ]
    )


def tail_last_nonempty_line(path: Path) -> str:
    if not path.exists():
        return "-"
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return "-"
    for line in reversed(lines):
        text = line.strip()
        if text:
            return text
    return "-"


def launchctl_snapshot(label: str) -> dict[str, str]:
    target = f"gui/{os.getuid()}/{label}"
    try:
        result = subprocess.run(
            ["launchctl", "print", target],
            check=False,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        return {"loaded": "0", "error": str(exc)}

    if result.returncode != 0:
        return {
            "loaded": "0",
            "error": (result.stderr or result.stdout or f"launchctl exit {result.returncode}").strip(),
        }

    snapshot = {"loaded": "1"}
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if line.startswith("state ="):
            snapshot["state"] = line.split("=", 1)[1].strip()
        elif line.startswith("pid ="):
            snapshot["pid"] = line.split("=", 1)[1].strip()
        elif line.startswith("last exit code ="):
            snapshot["last_exit_code"] = line.split("=", 1)[1].strip()
        elif line.startswith("runs ="):
            snapshot["runs"] = line.split("=", 1)[1].strip()
        elif line.startswith("run interval ="):
            snapshot["run_interval"] = line.split("=", 1)[1].strip()
        elif "SIGNAL_DECK_LOOP_INTERVAL =>" in line:
            snapshot["loop_interval"] = line.split("=>", 1)[1].strip()
    return snapshot


def build_botstatus_text() -> str:
    dryrun = launchctl_snapshot(SERVICE_LABELS["dryrun"])
    telegrambot = launchctl_snapshot(SERVICE_LABELS["telegrambot"])
    dryrun_log = tail_last_nonempty_line(DRYRUN_LOG_PATH)
    telegram_log = tail_last_nonempty_line(TELEGRAM_LOG_PATH)

    lines = [
        "Signal Deck botstatus",
        (
            f"dryrun: loaded={dryrun.get('loaded', '0')} "
            f"state={dryrun.get('state', '-')} "
            f"runs={dryrun.get('runs', '-')} "
            f"last_exit={dryrun.get('last_exit_code', '-')}"
        ),
        (
            f"dryrun_interval={dryrun.get('loop_interval', dryrun.get('run_interval', '-'))}"
        ),
        f"dryrun_last_log={dryrun_log}",
        (
            f"telegrambot: loaded={telegrambot.get('loaded', '0')} "
            f"state={telegrambot.get('state', '-')} "
            f"pid={telegrambot.get('pid', '-')} "
            f"runs={telegrambot.get('runs', '-')} "
            f"last_exit={telegrambot.get('last_exit_code', '-')}"
        ),
        f"telegram_last_log={telegram_log}",
    ]

    if dryrun.get("error"):
        lines.append(f"dryrun_error={dryrun['error']}")
    if telegrambot.get("error"):
        lines.append(f"telegram_error={telegrambot['error']}")
    return "\n".join(lines)


def build_chatid_text(message: dict[str, Any]) -> str:
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    return "\n".join(
        [
            "Signal Deck chatid",
            f"chat_id={chat.get('id') if chat.get('id') is not None else '-'}",
            f"chat_type={chat.get('type') or '-'}",
            f"chat_title={chat.get('title') or chat.get('username') or chat.get('first_name') or '-'}",
        ]
    )


def normalize_command(text: str, bot_username: str) -> str:
    command = text.strip().split()[0] if text.strip() else ""
    if not command.startswith("/"):
        return ""
    lowered = command.lower()
    if "@" in lowered:
        base, _, suffix = lowered.partition("@")
        if bot_username and suffix != bot_username.lower():
            return ""
        return base
    return lowered


def extract_message(update: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("message", "edited_message"):
        value = update.get(key)
        if isinstance(value, dict):
            return value
    return None


def handle_command(message: dict[str, Any], bot_username: str) -> str | None:
    text = str(message.get("text") or "")
    command = normalize_command(text, bot_username)
    if command in {"/start", "/help"}:
        return build_start_text(bot_username)
    if command == "/status":
        return build_status_text()
    if command == "/lastsignal":
        return build_lastsignal_text()
    if command == "/botstatus":
        return build_botstatus_text()
    if command == "/chatid":
        return build_chatid_text(message)
    return None


def process_updates(token: str, bot_username: str, state_path: Path, poll_timeout: int) -> int:
    state = load_state(state_path)
    offset = state.get("offset")
    try:
        offset_value = int(offset) if offset is not None else None
    except (TypeError, ValueError):
        offset_value = None

    updates = telegram_get_updates(token, offset_value, poll_timeout)
    max_update_id = offset_value - 1 if isinstance(offset_value, int) else -1
    handled = 0

    for update in updates:
        if not isinstance(update, dict):
            continue
        update_id = update.get("update_id")
        if isinstance(update_id, int) and update_id > max_update_id:
            max_update_id = update_id
        message = extract_message(update)
        if not isinstance(message, dict):
            continue
        reply = handle_command(message, bot_username)
        if reply is None:
            continue
        chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
        chat_id = chat.get("id")
        if chat_id is None:
            continue
        telegram_send_message(token, chat_id, reply, reply_to_message_id=message.get("message_id"))
        handled += 1

    payload = {
        "offset": max_update_id + 1 if max_update_id >= 0 else offset_value,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "handled_messages": handled,
    }
    save_state(state_path, payload)
    return handled


def main() -> int:
    args = build_parser().parse_args()
    token = str(args.bot_token or "").strip()
    if not token:
        raise ValueError("Missing Telegram bot token.")

    bot_username = str(args.bot_username or "").strip()
    if not bot_username:
        me = telegram_get_me(token)
        bot_username = str(me.get("username") or "").strip()

    while True:
        try:
            process_updates(token, bot_username, args.state_path, args.poll_timeout)
        except KeyboardInterrupt:
            return 0
        except Exception as exc:
            print(f"[telegram-bot] error: {exc}", flush=True)
            time.sleep(max(1.0, args.idle_sleep))
        if args.once:
            return 0
        time.sleep(max(0.2, args.idle_sleep))


if __name__ == "__main__":
    raise SystemExit(main())
