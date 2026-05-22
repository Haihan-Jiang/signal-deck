#!/usr/bin/env python3
"""Zero-cost iPhone control surface for local automations.

This module intentionally avoids paid AI/API dependencies. It exposes a small
local HTTP app that iPhone Shortcuts can call, plus a rule-based scheduler that
dispatches only explicitly configured local actions.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, time as local_time, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - Python 3.8 fallback only.
    ZoneInfo = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parent
DEFAULT_RUNTIME_DIR = Path.home() / ".signal-deck" / "runtime"
DEFAULT_LOG_DIR = Path.home() / ".signal-deck" / "logs"
DEFAULT_CONFIG_PATH = DEFAULT_RUNTIME_DIR / "iphone_agent_config.json"
DEFAULT_STATE_PATH = DEFAULT_LOG_DIR / "iphone_agent_state.json"
DEFAULT_RUN_LOG_PATH = DEFAULT_LOG_DIR / "iphone_agent_runs.jsonl"
MAX_CAPTURE_CHARS = 6000
TASK_RUN_LOCK = threading.RLock()
RUN_DUE_LOCK = threading.Lock()


class SafeFormatDict(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat(timespec="seconds")


def local_now(config: dict[str, Any]) -> datetime:
    tz_name = str(config.get("timezone") or "America/Los_Angeles")
    if ZoneInfo is None:
        return datetime.now()
    try:
        return datetime.now(ZoneInfo(tz_name))
    except Exception:
        return datetime.now()


def parse_hhmm(value: Any) -> local_time:
    text = str(value or "00:00").strip()
    hour_text, minute_text = text.split(":", 1)
    return local_time(hour=int(hour_text), minute=int(minute_text[:2]))


def parse_iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def truncate_text(value: str, limit: int = MAX_CAPTURE_CHARS) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n[truncated {len(value) - limit} chars]"


def expand_path(value: Any, base: Path = ROOT) -> Path:
    text = str(value or "").strip()
    if not text:
        return base
    path = Path(text.format_map(template_vars()))
    if not path.is_absolute():
        path = base / path
    return path.expanduser()


def template_vars() -> SafeFormatDict:
    return SafeFormatDict(
        {
            "python": sys.executable,
            "repo": str(ROOT),
            "home": str(Path.home()),
            "runtime": str(DEFAULT_RUNTIME_DIR),
            "logs": str(DEFAULT_LOG_DIR),
        }
    )


def render_template(value: Any) -> Any:
    if isinstance(value, str):
        return value.format_map(template_vars())
    if isinstance(value, list):
        return [render_template(item) for item in value]
    if isinstance(value, dict):
        return {str(key): render_template(item) for key, item in value.items()}
    return value


def default_config(host: str = "127.0.0.1", port: int = 8797) -> dict[str, Any]:
    return {
        "version": 1,
        "name": "Zero-Cost iPhone Autopilot",
        "timezone": "America/Los_Angeles",
        "host": host,
        "port": port,
        "token": secrets.token_urlsafe(24),
        "token_required": True,
        "no_cost": True,
        "policy": {
            "allow_paid_services": False,
            "allow_llm_api_calls": False,
            "external_submit_requires_explicit_confirmation": True,
        },
        "scheduler": {
            "enabled": True,
            "tick_seconds": 60,
        },
        "state_path": str(DEFAULT_STATE_PATH),
        "run_log_path": str(DEFAULT_RUN_LOG_PATH),
        "tasks": [
            {
                "id": "job_drafts_daily",
                "title": "Daily job drafts and Telegram alert",
                "enabled": True,
                "unattended": True,
                "schedule": {"kind": "daily", "time": "17:00"},
                "ios_boundary": (
                    "Fully unattended for scoring, draft generation, closed-posting checks, "
                    "local outbox writes, and Telegram notification. It does not submit real "
                    "applications; employer forms, CAPTCHAs, logins, and legal attestations "
                    "still require human consent."
                ),
                "action": {
                    "kind": "argv",
                    "cwd": "{repo}",
                    "timeout_seconds": 300,
                    "argv": [
                        "{python}",
                        "-m",
                        "job_apply_agent",
                        "run",
                        "--profile",
                        "job_apply_agent/outbox/alan_jiang_profile.json",
                        "--jobs",
                        "job_apply_agent/outbox/linkedin_visible_jobs.json",
                        "--memory",
                        "job_apply_agent/outbox/answer_memory.json",
                        "--limit",
                        "5",
                        "--notify-telegram",
                        "--live-check",
                    ],
                },
            },
            {
                "id": "signal_snapshot",
                "title": "Signal Deck dry-run snapshot",
                "enabled": True,
                "unattended": True,
                "schedule": {"kind": "manual"},
                "ios_boundary": (
                    "Manual iPhone trigger by default because this task depends on external "
                    "sports/market network calls. It remains dry-run research output only and "
                    "does not place live event-contract orders. Use the existing dry-run daemon "
                    "or change this schedule to interval if you want it in the Mac scheduler."
                ),
                "action": {
                    "kind": "argv",
                    "cwd": "{repo}",
                    "timeout_seconds": 120,
                    "env_files": ["{home}/.signal-deck/runtime/telegram.env"],
                    "argv": [
                        "{python}",
                        "dryrun_recorder.py",
                        "--limit",
                        "20",
                    ],
                },
            },
            {
                "id": "status_snapshot",
                "title": "Phone status summary",
                "enabled": True,
                "unattended": True,
                "schedule": {"kind": "interval", "minutes": 30},
                "ios_boundary": (
                    "Fully unattended read-only status heartbeat from local logs and outbox files."
                ),
                "action": {
                    "kind": "status_snapshot",
                    "paths": [
                        "{home}/.signal-deck/logs/dryrun_latest.txt",
                        "{repo}/job_apply_agent/outbox/dry_run_submissions.jsonl",
                        "{repo}/job_apply_agent/outbox/browser_review_queue.jsonl",
                    ],
                },
            },
        ],
    }


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_config()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Config must be a JSON object: {path}")
    return with_config_defaults(payload)


def save_config(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def with_config_defaults(config: dict[str, Any]) -> dict[str, Any]:
    merged = dict(config)
    defaults = default_config(
        host=str(merged.get("host") or "0.0.0.0"),
        port=int(merged.get("port") or 8797),
    )
    for key in ["no_cost", "policy", "scheduler", "state_path", "run_log_path"]:
        if key not in merged:
            merged[key] = defaults[key]
    if "token_required" not in merged:
        merged["token_required"] = True
    if "tasks" not in merged:
        merged["tasks"] = defaults["tasks"]
    return merged


def migrate_task_schedules(config: dict[str, Any]) -> dict[str, Any]:
    tasks = config.get("tasks")
    if not isinstance(tasks, list):
        return config
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = str(task.get("id") or "")
        schedule = task.get("schedule") if isinstance(task.get("schedule"), dict) else {}
        if task_id == "signal_snapshot" and schedule.get("kind") == "interval":
            task["schedule"] = {"kind": "manual"}
            task["ios_boundary"] = (
                "Manual iPhone trigger by default because this task depends on external "
                "sports/market network calls. It remains dry-run research output only and "
                "does not place live event-contract orders. Use the existing dry-run daemon "
                "or change this schedule to interval if you want it in the Mac scheduler."
            )
        if task_id == "status_snapshot" and schedule.get("kind") == "manual":
            task["schedule"] = {"kind": "interval", "minutes": 30}
            task["ios_boundary"] = "Fully unattended read-only status heartbeat from local logs and outbox files."
    return config


def state_path(config: dict[str, Any]) -> Path:
    return expand_path(config.get("state_path") or DEFAULT_STATE_PATH)


def run_log_path(config: dict[str, Any]) -> Path:
    return expand_path(config.get("run_log_path") or DEFAULT_RUN_LOG_PATH)


def load_state(config: dict[str, Any]) -> dict[str, Any]:
    path = state_path(config)
    if not path.exists():
        return {"tasks": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"tasks": {}}
    if not isinstance(payload, dict):
        return {"tasks": {}}
    payload.setdefault("tasks", {})
    return payload


def save_state(config: dict[str, Any], state: dict[str, Any]) -> None:
    path = state_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def append_run_log(config: dict[str, Any], row: dict[str, Any]) -> None:
    path = run_log_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def task_by_id(config: dict[str, Any], task_id: str) -> dict[str, Any]:
    for task in config.get("tasks", []):
        if str(task.get("id")) == task_id:
            return task
    raise KeyError(f"Unknown task: {task_id}")


def task_state(state: dict[str, Any], task_id: str) -> dict[str, Any]:
    tasks = state.setdefault("tasks", {})
    item = tasks.setdefault(task_id, {})
    if not isinstance(item, dict):
        item = {}
        tasks[task_id] = item
    return item


def is_task_due(task: dict[str, Any], state: dict[str, Any], now: datetime) -> bool:
    if not task.get("enabled", True):
        return False
    schedule = task.get("schedule") if isinstance(task.get("schedule"), dict) else {}
    kind = str(schedule.get("kind") or "manual").lower()
    previous = task_state(state, str(task.get("id") or ""))
    if kind == "manual":
        return False
    if kind == "daily":
        scheduled = parse_hhmm(schedule.get("time") or "00:00")
        if now.time() < scheduled:
            return False
        return str(previous.get("last_local_date") or "") != now.date().isoformat()
    if kind == "interval":
        minutes = float(schedule.get("minutes") or 60)
        last_finished = parse_iso_datetime(previous.get("last_finished_at"))
        if last_finished is None:
            return True
        return (utc_now() - last_finished.astimezone(timezone.utc)).total_seconds() >= minutes * 60
    return False


def load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            values[key] = value
    return values


def build_action_env(action: dict[str, Any]) -> dict[str, str]:
    env = os.environ.copy()
    for item in action.get("env_files") or []:
        env.update(load_env_file(expand_path(item)))
    explicit_env = action.get("env") if isinstance(action.get("env"), dict) else {}
    for key, value in explicit_env.items():
        env[str(key)] = str(render_template(value))
    env.setdefault("PYTHONPATH", str(ROOT))
    return env


def run_argv_action(action: dict[str, Any]) -> dict[str, Any]:
    argv = render_template(action.get("argv") or [])
    if not isinstance(argv, list) or not argv:
        raise ValueError("argv action requires a non-empty argv list")
    cwd = expand_path(action.get("cwd") or ROOT)
    timeout = float(action.get("timeout_seconds") or 120)
    started = time.monotonic()
    completed = subprocess.run(
        [str(item) for item in argv],
        cwd=str(cwd),
        env=build_action_env(action),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    return {
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "elapsed_ms": elapsed_ms,
        "stdout": truncate_text(completed.stdout or ""),
        "stderr": truncate_text(completed.stderr or ""),
        "argv": [str(item) for item in argv],
        "cwd": str(cwd),
    }


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def read_tail(path: Path, limit: int = 3000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= limit:
        return text
    return text[-limit:]


def run_status_snapshot(action: dict[str, Any]) -> dict[str, Any]:
    paths = [expand_path(item) for item in action.get("paths") or []]
    files: list[dict[str, Any]] = []
    for path in paths:
        item: dict[str, Any] = {
            "path": str(path),
            "exists": path.exists(),
        }
        if path.suffix == ".jsonl":
            item["row_count"] = count_jsonl(path)
            item["tail"] = read_tail(path, limit=1200)
        elif path.exists():
            item["tail"] = read_tail(path)
        files.append(item)
    summary_lines = []
    for item in files:
        label = Path(str(item["path"])).name
        if item.get("row_count") is not None:
            summary_lines.append(f"{label}: exists={str(item['exists']).lower()} rows={item['row_count']}")
        else:
            summary_lines.append(f"{label}: exists={str(item['exists']).lower()}")
    return {
        "ok": True,
        "exit_code": 0,
        "elapsed_ms": 0,
        "files": files,
        "stdout": "\n".join(summary_lines),
        "stderr": "",
    }


def run_action(action: dict[str, Any]) -> dict[str, Any]:
    kind = str(action.get("kind") or "").lower()
    if kind == "argv":
        return run_argv_action(action)
    if kind == "status_snapshot":
        return run_status_snapshot(action)
    if kind == "sequence":
        results = []
        ok = True
        for child in action.get("actions") or []:
            if not isinstance(child, dict):
                raise ValueError("sequence actions must be objects")
            result = run_action(child)
            results.append(result)
            ok = ok and bool(result.get("ok"))
            if not result.get("ok") and action.get("stop_on_error", True):
                break
        return {
            "ok": ok,
            "exit_code": 0 if ok else 1,
            "elapsed_ms": sum(int(item.get("elapsed_ms") or 0) for item in results),
            "results": results,
            "stdout": json.dumps(results, ensure_ascii=True, indent=2),
            "stderr": "",
        }
    raise ValueError(f"Unsupported action kind: {kind}")


def run_task(config: dict[str, Any], task_id: str, reason: str = "manual") -> dict[str, Any]:
    with TASK_RUN_LOCK:
        return _run_task_locked(config, task_id, reason=reason)


def _run_task_locked(config: dict[str, Any], task_id: str, reason: str = "manual") -> dict[str, Any]:
    state = load_state(config)
    task = task_by_id(config, task_id)
    now_local = local_now(config)
    started_at = iso_now()
    current_state = task_state(state, task_id)
    current_state.update(
        {
            "last_started_at": started_at,
            "last_reason": reason,
            "last_title": task.get("title") or task_id,
        }
    )
    save_state(config, state)
    try:
        result = run_action(task.get("action") if isinstance(task.get("action"), dict) else {})
    except subprocess.TimeoutExpired as exc:
        result = {
            "ok": False,
            "exit_code": 124,
            "elapsed_ms": 0,
            "stdout": truncate_text(exc.stdout or ""),
            "stderr": truncate_text(exc.stderr or f"Timed out after {exc.timeout} seconds"),
        }
    except Exception as exc:
        result = {
            "ok": False,
            "exit_code": 1,
            "elapsed_ms": 0,
            "stdout": "",
            "stderr": str(exc),
        }
    finished_at = iso_now()
    state = load_state(config)
    current_state = task_state(state, task_id)
    current_state.update(
        {
            "last_finished_at": finished_at,
            "last_local_date": now_local.date().isoformat(),
            "last_ok": bool(result.get("ok")),
            "last_exit_code": int(result.get("exit_code") or 0),
            "last_elapsed_ms": int(result.get("elapsed_ms") or 0),
            "last_stdout_tail": truncate_text(str(result.get("stdout") or ""), 1200),
            "last_stderr_tail": truncate_text(str(result.get("stderr") or ""), 1200),
        }
    )
    save_state(config, state)
    log_row = {
        "task_id": task_id,
        "title": task.get("title") or task_id,
        "reason": reason,
        "started_at": started_at,
        "finished_at": finished_at,
        "ok": bool(result.get("ok")),
        "exit_code": int(result.get("exit_code") or 0),
        "elapsed_ms": int(result.get("elapsed_ms") or 0),
    }
    append_run_log(config, log_row)
    return {"task": public_task(task, state), "result": result, "log": log_row}


def run_due(config: dict[str, Any], reason: str = "scheduled_tick") -> dict[str, Any]:
    if not RUN_DUE_LOCK.acquire(blocking=False):
        return {
            "ok": True,
            "checked_at": iso_now(),
            "due_count": 0,
            "skipped": True,
            "reason": "another_run_due_in_progress",
            "results": [],
        }
    try:
        return _run_due_locked(config, reason=reason)
    finally:
        RUN_DUE_LOCK.release()


def _run_due_locked(config: dict[str, Any], reason: str = "scheduled_tick") -> dict[str, Any]:
    state = load_state(config)
    now = local_now(config)
    due_tasks = [
        task
        for task in config.get("tasks", [])
        if isinstance(task, dict) and is_task_due(task, state, now)
    ]
    results = [run_task(config, str(task.get("id")), reason=reason) for task in due_tasks]
    return {
        "ok": all(item["result"].get("ok") for item in results),
        "checked_at": iso_now(),
        "due_count": len(due_tasks),
        "results": results,
    }


def public_task(task: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    task_id = str(task.get("id") or "")
    current = task_state(state, task_id)
    return {
        "id": task_id,
        "title": task.get("title") or task_id,
        "enabled": bool(task.get("enabled", True)),
        "unattended": bool(task.get("unattended", False)),
        "schedule": task.get("schedule") or {"kind": "manual"},
        "ios_boundary": task.get("ios_boundary") or "",
        "last": current,
    }


def build_status(config: dict[str, Any]) -> dict[str, Any]:
    state = load_state(config)
    now = local_now(config)
    tasks = []
    for task in config.get("tasks", []):
        if not isinstance(task, dict):
            continue
        item = public_task(task, state)
        item["due_now"] = is_task_due(task, state, now)
        tasks.append(item)
    return {
        "ok": True,
        "name": config.get("name") or "iPhone Autopilot",
        "server_time": iso_now(),
        "local_time": now.isoformat(timespec="seconds"),
        "timezone": config.get("timezone") or "America/Los_Angeles",
        "no_cost": True,
        "policy": config.get("policy") or {},
        "scheduler": scheduler_settings(config),
        "tasks": tasks,
    }


def scheduler_settings(config: dict[str, Any]) -> dict[str, Any]:
    raw = config.get("scheduler") if isinstance(config.get("scheduler"), dict) else {}
    return {
        "enabled": bool(raw.get("enabled", True)),
        "tick_seconds": max(15, int(raw.get("tick_seconds") or 60)),
    }


def scheduler_loop(config_path: Path, stop_event: threading.Event) -> None:
    while not stop_event.wait(2.0):
        break
    while not stop_event.is_set():
        try:
            config = load_config(config_path)
            settings = scheduler_settings(config)
            if settings["enabled"]:
                payload = run_due(config, reason="mac_scheduler")
                if payload.get("due_count") or payload.get("skipped"):
                    append_run_log(
                        config,
                        {
                            "task_id": "__scheduler__",
                            "title": "Mac scheduler tick",
                            "reason": "mac_scheduler",
                            "started_at": payload.get("checked_at") or iso_now(),
                            "finished_at": iso_now(),
                            "ok": bool(payload.get("ok", True)),
                            "exit_code": 0 if payload.get("ok", True) else 1,
                            "elapsed_ms": 0,
                            "due_count": payload.get("due_count", 0),
                            "skipped": bool(payload.get("skipped")),
                            "skip_reason": payload.get("reason"),
                        },
                    )
            wait_seconds = settings["tick_seconds"]
        except Exception as exc:
            try:
                append_run_log(
                    load_config(config_path),
                    {
                        "task_id": "__scheduler__",
                        "title": "Mac scheduler tick",
                        "reason": "mac_scheduler_error",
                        "started_at": iso_now(),
                        "finished_at": iso_now(),
                        "ok": False,
                        "exit_code": 1,
                        "elapsed_ms": 0,
                        "stderr": str(exc),
                    },
                )
            except Exception:
                pass
            wait_seconds = 60
        stop_event.wait(wait_seconds)


def token_from_request(parsed: Any, body: dict[str, Any] | None = None) -> str:
    query = parse_qs(parsed.query or "")
    if query.get("token"):
        return query["token"][0]
    if body and body.get("token"):
        return str(body["token"])
    return ""


def token_is_required(config: dict[str, Any]) -> bool:
    return bool(config.get("token_required", True) and str(config.get("token") or "").strip())


def check_token(config: dict[str, Any], provided: str) -> bool:
    if not token_is_required(config):
        return True
    return secrets.compare_digest(str(config.get("token") or ""), provided)


def response_json(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def response_text(
    handler: BaseHTTPRequestHandler, status: int, body: str, content_type: str = "text/html; charset=utf-8"
) -> None:
    data = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def parse_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or "0")
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def shortcut_text(payload: dict[str, Any]) -> str:
    if "results" in payload:
        lines = [f"checked={payload.get('checked_at')} due={payload.get('due_count')}"]
        for item in payload.get("results") or []:
            task = item.get("task") or {}
            result = item.get("result") or {}
            lines.append(
                f"{task.get('id')}: ok={str(result.get('ok')).lower()} exit={result.get('exit_code')}"
            )
        return "\n".join(lines)
    task = payload.get("task") or {}
    result = payload.get("result") or {}
    stdout = str(result.get("stdout") or "").strip()
    stderr = str(result.get("stderr") or "").strip()
    lines = [f"{task.get('id')}: ok={str(result.get('ok')).lower()} exit={result.get('exit_code')}"]
    if stdout:
        lines.append(stdout[-1200:])
    if stderr:
        lines.append("stderr: " + stderr[-1200:])
    return "\n".join(lines)


def render_index(config: dict[str, Any]) -> str:
    status = build_status(config)
    rows = []
    for task in status["tasks"]:
        last = task.get("last") or {}
        rows.append(
            f"""
            <section class="task">
              <div class="task-head">
                <div>
                  <h2>{html.escape(task["title"])}</h2>
                  <p>{html.escape(str(task["id"]))}</p>
                </div>
                <button data-task="{html.escape(str(task["id"]))}">Run</button>
              </div>
              <dl>
                <div><dt>Schedule</dt><dd>{html.escape(json.dumps(task["schedule"]))}</dd></div>
                <div><dt>Due</dt><dd>{str(task["due_now"]).lower()}</dd></div>
                <div><dt>Last</dt><dd>{html.escape(str(last.get("last_finished_at") or "never"))}</dd></div>
                <div><dt>Result</dt><dd>{html.escape(str(last.get("last_ok") if "last_ok" in last else "-"))}</dd></div>
              </dl>
              <p class="boundary">{html.escape(str(task["ios_boundary"] or ""))}</p>
            </section>
            """
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-title" content="Autopilot">
  <link rel="manifest" href="/manifest.webmanifest">
  <title>{html.escape(str(status["name"]))}</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #f7f8fa;
      --fg: #111318;
      --muted: #667085;
      --line: #d9dee7;
      --surface: #ffffff;
      --accent: #156f8f;
      --ok: #18794e;
      --bad: #b42318;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #101114;
        --fg: #f5f7fb;
        --muted: #a2aab8;
        --line: #30343b;
        --surface: #181a1f;
        --accent: #5db8d6;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--fg);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }}
    main {{
      width: min(980px, 100%);
      margin: 0 auto;
      padding: 18px 14px 36px;
    }}
    header {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      padding: 8px 2px 16px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{ font-size: 24px; line-height: 1.16; margin: 0 0 6px; }}
    h2 {{ font-size: 17px; line-height: 1.25; margin: 0; }}
    p {{ margin: 0; color: var(--muted); line-height: 1.45; }}
    button {{
      min-height: 42px;
      padding: 0 14px;
      border: 1px solid var(--accent);
      border-radius: 8px;
      background: var(--accent);
      color: white;
      font: inherit;
      font-weight: 600;
    }}
    button.secondary {{
      background: transparent;
      color: var(--accent);
    }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }}
    .task {{
      margin-top: 14px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
    }}
    .task-head {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
    }}
    dl {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin: 14px 0;
    }}
    dl div {{
      min-width: 0;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
    }}
    dt {{ font-size: 12px; color: var(--muted); margin-bottom: 4px; }}
    dd {{ margin: 0; overflow-wrap: anywhere; font-size: 14px; }}
    .boundary {{
      padding-top: 10px;
      border-top: 1px solid var(--line);
      font-size: 13px;
    }}
    pre {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      padding: 12px;
      min-height: 80px;
      font-size: 12px;
    }}
    @media (max-width: 560px) {{
      header {{ display: block; }}
      .actions {{ justify-content: stretch; margin-top: 12px; }}
      button {{ flex: 1 1 auto; }}
      dl {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>{html.escape(str(status["name"]))}</h1>
        <p>No paid AI/API calls. Mac scheduler runs supported tasks; iPhone controls status and manual triggers.</p>
      </div>
      <div class="actions">
        <button id="tick">Run Due</button>
        <button id="refresh" class="secondary">Refresh</button>
      </div>
    </header>
    <div id="tasks">{''.join(rows)}</div>
    <pre id="output">Ready. Local time: {html.escape(str(status["local_time"]))}</pre>
  </main>
  <script>
    const params = new URLSearchParams(location.search);
    const queryToken = params.get("token");
    if (queryToken) localStorage.setItem("iphone_agent_token", queryToken);
    const token = localStorage.getItem("iphone_agent_token") || "";
    const output = document.querySelector("#output");
    function url(path, extra) {{
      const q = new URLSearchParams(extra || {{}});
      if (token) q.set("token", token);
      return path + "?" + q.toString();
    }}
    async function call(path, extra) {{
      output.textContent = "Running...";
      const res = await fetch(url(path, extra), {{ cache: "no-store" }});
      const text = await res.text();
      try {{
        const data = JSON.parse(text);
        output.textContent = JSON.stringify(data, null, 2);
      }} catch {{
        output.textContent = text;
      }}
    }}
    document.querySelector("#tick").addEventListener("click", () => call("/api/tick", {{}}));
    document.querySelector("#refresh").addEventListener("click", () => location.reload());
    document.querySelectorAll("button[data-task]").forEach((button) => {{
      button.addEventListener("click", () => call("/api/run", {{ task: button.dataset.task }}));
    }});
  </script>
</body>
</html>
"""


def manifest_json(config: dict[str, Any]) -> str:
    return json.dumps(
        {
            "name": config.get("name") or "iPhone Autopilot",
            "short_name": "Autopilot",
            "display": "standalone",
            "start_url": "/",
            "background_color": "#f7f8fa",
            "theme_color": "#156f8f",
        },
        ensure_ascii=False,
    )


def make_handler(config_path: Path) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "IPhoneAutopilot/1.0"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), format % args))

        def current_config(self) -> dict[str, Any]:
            return load_config(config_path)

        def ensure_authorized(self, config: dict[str, Any], parsed: Any, body: dict[str, Any] | None = None) -> bool:
            if check_token(config, token_from_request(parsed, body)):
                return True
            response_json(self, HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "invalid token"})
            return False

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            config = self.current_config()
            if parsed.path in {"/", "/index.html"}:
                response_text(self, HTTPStatus.OK, render_index(config))
                return
            if parsed.path == "/manifest.webmanifest":
                response_text(
                    self,
                    HTTPStatus.OK,
                    manifest_json(config),
                    content_type="application/manifest+json; charset=utf-8",
                )
                return
            if parsed.path == "/api/status":
                if not self.ensure_authorized(config, parsed):
                    return
                response_json(self, HTTPStatus.OK, build_status(config))
                return
            if parsed.path == "/api/tick":
                if not self.ensure_authorized(config, parsed):
                    return
                response_json(self, HTTPStatus.OK, run_due(config))
                return
            if parsed.path == "/api/run":
                if not self.ensure_authorized(config, parsed):
                    return
                query = parse_qs(parsed.query)
                task_id = str((query.get("task") or query.get("task_id") or [""])[0])
                if not task_id:
                    response_json(self, HTTPStatus.BAD_REQUEST, {"ok": False, "error": "missing task"})
                    return
                response_json(self, HTTPStatus.OK, run_task(config, task_id, reason="http_get"))
                return
            if parsed.path == "/shortcut":
                if not self.ensure_authorized(config, parsed):
                    return
                query = parse_qs(parsed.query)
                task_id = str((query.get("task") or query.get("task_id") or [""])[0])
                payload = run_due(config) if task_id in {"", "tick", "due"} else run_task(config, task_id, reason="shortcut")
                response_text(self, HTTPStatus.OK, shortcut_text(payload), content_type="text/plain; charset=utf-8")
                return
            response_json(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            config = self.current_config()
            body = parse_json_body(self)
            if parsed.path == "/api/tick":
                if not self.ensure_authorized(config, parsed, body):
                    return
                response_json(self, HTTPStatus.OK, run_due(config))
                return
            if parsed.path == "/api/run":
                if not self.ensure_authorized(config, parsed, body):
                    return
                task_id = str(body.get("task") or body.get("task_id") or "")
                if not task_id:
                    response_json(self, HTTPStatus.BAD_REQUEST, {"ok": False, "error": "missing task"})
                    return
                response_json(self, HTTPStatus.OK, run_task(config, task_id, reason="http_post"))
                return
            response_json(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    return Handler


def local_ip_hint() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        value = sock.getsockname()[0]
        sock.close()
        return value
    except Exception:
        return "127.0.0.1"


def probe_status(config: dict[str, Any], timeout: float = 5.0) -> dict[str, Any]:
    import urllib.error
    import urllib.request

    port = int(config.get("port") or 8797)
    token = str(config.get("token") or "")
    url = f"http://127.0.0.1:{port}/api/status?{urlencode({'token': token})}"
    started = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return {
            "ok": bool(payload.get("ok")),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "task_count": len(payload.get("tasks", [])),
            "no_cost": bool(payload.get("no_cost")),
        }
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "error": str(exc),
        }


def launchagent_status(label: str = "com.haihan.signaldeck.iphoneagent") -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    output = completed.stdout + completed.stderr
    return {
        "ok": completed.returncode == 0 and "state = running" in output,
        "exit_code": completed.returncode,
        "running": "state = running" in output,
        "loaded": completed.returncode == 0,
    }


def doctor_payload(config_path: Path) -> dict[str, Any]:
    config = load_config(config_path)
    tasks = [task for task in config.get("tasks", []) if isinstance(task, dict)]
    checks = {
        "config_exists": {"ok": config_path.exists(), "path": str(config_path)},
        "zero_cost_policy": {
            "ok": bool(
                config.get("no_cost", True)
                and not (config.get("policy") or {}).get("allow_paid_services", False)
                and not (config.get("policy") or {}).get("allow_llm_api_calls", False)
            ),
            "no_cost": bool(config.get("no_cost", True)),
        },
        "token_required": {
            "ok": bool(config.get("token_required", True) and str(config.get("token") or "")),
        },
        "scheduler_enabled": {
            "ok": scheduler_settings(config)["enabled"],
            **scheduler_settings(config),
        },
        "tasks_configured": {
            "ok": len(tasks) > 0,
            "task_count": len(tasks),
        },
        "task_boundaries": {
            "ok": all(str(task.get("ios_boundary") or "").strip() for task in tasks),
            "missing": [task.get("id") for task in tasks if not str(task.get("ios_boundary") or "").strip()],
        },
        "runtime_app": {
            "ok": Path(__file__).exists(),
            "path": str(Path(__file__).resolve()),
        },
        "launchagent": launchagent_status(),
        "http_status": probe_status(config),
    }
    return {
        "ok": all(bool(item.get("ok")) for item in checks.values()),
        "checked_at": iso_now(),
        "checks": checks,
    }


def init_config(args: argparse.Namespace) -> int:
    path = Path(args.config).expanduser()
    if path.exists() and not args.force:
        print(f"Config already exists: {path}")
        return 0
    config = default_config(host=args.host, port=args.port)
    save_config(path, config)
    print(f"Wrote config: {path}")
    print(f"Local URL: http://127.0.0.1:{args.port}/?token={config['token']}")
    print(f"iPhone URL on same Wi-Fi: http://{local_ip_hint()}:{args.port}/?token={config['token']}")
    return 0


def migrate_config(args: argparse.Namespace) -> int:
    path = Path(args.config).expanduser()
    config = migrate_task_schedules(load_config(path))
    save_config(path, config)
    print(f"Updated config defaults: {path}")
    return 0


def serve(args: argparse.Namespace) -> int:
    config_path = Path(args.config).expanduser()
    config = load_config(config_path)
    host = args.host or str(config.get("host") or "127.0.0.1")
    port = int(args.port or config.get("port") or 8797)
    server = ThreadingHTTPServer((host, port), make_handler(config_path))
    stop_event = threading.Event()
    scheduler_thread: threading.Thread | None = None
    if scheduler_settings(config)["enabled"]:
        scheduler_thread = threading.Thread(
            target=scheduler_loop,
            args=(config_path, stop_event),
            name="iphone-agent-scheduler",
            daemon=True,
        )
        scheduler_thread.start()
    print(f"Serving iPhone Autopilot on http://{host}:{port}")
    if scheduler_thread is not None:
        print(f"Mac scheduler enabled every {scheduler_settings(config)['tick_seconds']}s")
    if host in {"0.0.0.0", "::"}:
        print(f"Same-Wi-Fi iPhone URL hint: http://{local_ip_hint()}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        stop_event.set()
        server.server_close()
    return 0


def print_status(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config).expanduser())
    print(json.dumps(build_status(config), ensure_ascii=False, indent=2))
    return 0


def cli_run_task(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config).expanduser())
    payload = run_task(config, args.task, reason="cli")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["result"].get("ok") else 1


def cli_tick(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config).expanduser())
    payload = run_due(config)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") else 1


def cli_doctor(args: argparse.Namespace) -> int:
    payload = doctor_payload(Path(args.config).expanduser())
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") else 1


def shortcut_url(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config).expanduser())
    host = args.host or local_ip_hint()
    port = int(args.port or config.get("port") or 8797)
    params = {"token": str(config.get("token") or "")}
    if args.task:
        params["task"] = args.task
    else:
        params["task"] = "tick"
    print(f"http://{host}:{port}/shortcut?{urlencode(params)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Zero-cost iPhone local automation surface")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="write a local config with a random token")
    init_parser.add_argument("--host", default="0.0.0.0")
    init_parser.add_argument("--port", type=int, default=8797)
    init_parser.add_argument("--force", action="store_true")
    init_parser.set_defaults(func=init_config)

    migrate_parser = subparsers.add_parser("migrate-config", help="add missing safe defaults to an existing config")
    migrate_parser.set_defaults(func=migrate_config)

    serve_parser = subparsers.add_parser("serve", help="serve the iPhone web app and Shortcut endpoints")
    serve_parser.add_argument("--host", default=None)
    serve_parser.add_argument("--port", type=int, default=None)
    serve_parser.set_defaults(func=serve)

    status_parser = subparsers.add_parser("status", help="print public status JSON")
    status_parser.set_defaults(func=print_status)

    run_parser = subparsers.add_parser("run", help="run one configured task")
    run_parser.add_argument("task")
    run_parser.set_defaults(func=cli_run_task)

    tick_parser = subparsers.add_parser("tick", help="run due scheduled tasks")
    tick_parser.set_defaults(func=cli_tick)

    doctor_parser = subparsers.add_parser("doctor", help="verify zero-cost iPhone workflow readiness")
    doctor_parser.set_defaults(func=cli_doctor)

    url_parser = subparsers.add_parser("shortcut-url", help="print an iPhone Shortcuts URL")
    url_parser.add_argument("--host", default=None)
    url_parser.add_argument("--port", type=int, default=None)
    url_parser.add_argument("--task", default=None)
    url_parser.set_defaults(func=shortcut_url)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
