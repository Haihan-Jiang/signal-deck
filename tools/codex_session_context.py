#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_ROOT = Path.home() / ".codex" / "session-context"
DEFAULT_SESSION_ROOTS = [
    Path.home() / ".codex" / "sessions",
    Path.home() / ".codex" / "archived_sessions",
]
MAX_TEXT = 1600
MAX_LONG_TEXT = 3200
SESSION_ID_RE = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
)
VERIFY_COMMAND_RE = re.compile(
    r"\b(pytest|unittest|test|doctor|verify|lint|tsc|py_compile|json\.tool|"
    r"npm\s+test|cargo\s+test|go\s+test)\b",
    re.IGNORECASE,
)
BLOCKER_RE = re.compile(
    r"\b(blocked|blocker|failed|failure|error|traceback|permission denied|"
    r"do_not_promote|waiting|cannot|can't)\b|阻塞|失败|错误|无法|等待",
    re.IGNORECASE,
)
STRICT_BLOCKER_RE = re.compile(
    r"\b(traceback|permission denied|do_not_promote|waiting_for|blocked_by|"
    r"process exited with code [1-9][0-9]*|error:|failed:)\b|阻塞|失败|错误|无法",
    re.IGNORECASE,
)
PATH_RE = re.compile(
    r"(?P<path>(?:/Users/[^\s)'\",<>]+|[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.@+-]+)+)"
    r"(?:\.[A-Za-z0-9_+-]+)?)"
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def compact_text(value: str, limit: int = MAX_TEXT) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 20].rstrip() + " ... [truncated]"


def block_text(value: str, limit: int = MAX_LONG_TEXT) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 20].rstrip() + "\n...[truncated]"


def stable_unique(values: list[str], limit: int | None = None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = value.strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
        if limit is not None and len(result) >= limit:
            break
    return result


def content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    chunks: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        text = item.get("text") or item.get("input_text") or item.get("output_text")
        if isinstance(text, str):
            chunks.append(text)
    return "\n".join(chunks)


def parse_json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def session_id_from_path(path: Path) -> str:
    match = SESSION_ID_RE.search(path.stem)
    if match:
        return match.group(1)
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:16]
    return f"unknown-{digest}"


def safe_slug(value: str, fallback: str = "unknown") -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-")
    return slug[:100] or fallback


def extract_paths(*texts: str) -> list[str]:
    paths: list[str] = []
    for text in texts:
        for match in PATH_RE.finditer(text):
            path = match.group("path").rstrip(".,:;")
            if path.startswith("http"):
                continue
            if len(path) < 4:
                continue
            paths.append(path)
    return stable_unique(paths, limit=40)


def extract_patch_paths(stdout: str) -> list[str]:
    paths: list[str] = []
    for line in stdout.splitlines():
        line = line.strip()
        match = re.match(r"^[AMD]\s+(.+)$", line)
        if match:
            paths.append(match.group(1).strip())
        elif line.startswith("Success. Updated the following files:"):
            remainder = line.split(":", 1)[1]
            for item in re.finditer(r"\b[AMD]\s+([^\s].*?)(?=\s+[AMD]\s+|$)", remainder):
                paths.append(item.group(1).strip())
    return stable_unique(paths)


def parse_session_file(path: Path) -> dict[str, Any]:
    session_id = session_id_from_path(path)
    stat = path.stat()
    meta: dict[str, Any] = {}
    latest_turn: dict[str, Any] = {}
    goals: list[dict[str, Any]] = []
    user_messages: list[str] = []
    assistant_messages: list[dict[str, str]] = []
    tool_calls: list[dict[str, Any]] = []
    commands: list[str] = []
    verification: list[str] = []
    blockers: list[str] = []
    patch_paths: list[str] = []
    plan_items: list[dict[str, str]] = []
    task_complete_message = ""

    def remember_blocker(text: str, strict: bool = False) -> None:
        pattern = STRICT_BLOCKER_RE if strict else BLOCKER_RE
        if pattern.search(text):
            blockers.append(compact_text(text, 500))

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = item.get("payload")
            if not isinstance(payload, dict):
                continue
            item_type = item.get("type")
            payload_type = payload.get("type")

            if item_type == "session_meta":
                meta.update(payload)
                if isinstance(payload.get("id"), str):
                    session_id = payload["id"]
                continue

            if item_type == "turn_context":
                latest_turn = payload
                continue

            if item_type == "event_msg":
                if payload_type == "thread_goal_updated":
                    goal = payload.get("goal")
                    if isinstance(goal, dict):
                        goals.append(goal)
                elif payload_type == "user_message":
                    message = payload.get("message")
                    if isinstance(message, str):
                        user_messages.append(message)
                elif payload_type == "agent_message":
                    message = payload.get("message")
                    if isinstance(message, str):
                        phase = str(payload.get("phase") or "event")
                        assistant_messages.append({"phase": phase, "text": message})
                        remember_blocker(message)
                elif payload_type == "patch_apply_end":
                    stdout = str(payload.get("stdout") or "")
                    patch_paths.extend(extract_patch_paths(stdout))
                    if not payload.get("success"):
                        remember_blocker(stdout + "\n" + str(payload.get("stderr") or ""), strict=True)
                elif payload_type == "task_complete":
                    task_complete_message = str(payload.get("last_agent_message") or "")
                continue

            if item_type != "response_item":
                continue

            if payload_type == "message":
                role = payload.get("role")
                text = content_to_text(payload.get("content"))
                if not text:
                    continue
                if role == "user":
                    if "<environment_context>" not in text:
                        user_messages.append(text)
                elif role == "assistant":
                    phase = str(payload.get("phase") or "message")
                    assistant_messages.append({"phase": phase, "text": text})
                    remember_blocker(text)
                continue

            if payload_type == "function_call":
                name = str(payload.get("name") or "")
                args = parse_json_object(payload.get("arguments"))
                call = {
                    "name": name,
                    "arguments": args,
                    "call_id": payload.get("call_id"),
                }
                tool_calls.append(call)
                if name == "exec_command":
                    cmd = str(args.get("cmd") or "")
                    if cmd:
                        commands.append(cmd)
                        if VERIFY_COMMAND_RE.search(cmd):
                            verification.append(cmd)
                elif name == "update_plan":
                    raw_plan = args.get("plan")
                    if isinstance(raw_plan, list):
                        plan_items = []
                        for plan_item in raw_plan:
                            if isinstance(plan_item, dict):
                                step = str(plan_item.get("step") or "")
                                status = str(plan_item.get("status") or "")
                                if step:
                                    plan_items.append({"step": step, "status": status})
                continue

            if payload_type == "function_call_output":
                output = str(payload.get("output") or "")
                remember_blocker(output, strict=True)
                continue

    latest_goal = goals[-1] if goals else {}
    final_messages = [
        message["text"]
        for message in assistant_messages
        if message.get("phase") in {"final", "final_answer"}
    ]
    if task_complete_message and task_complete_message not in final_messages:
        final_messages.append(task_complete_message)
    commentary_messages = [
        message["text"]
        for message in assistant_messages
        if message.get("phase") in {"commentary", "event"}
    ]
    all_commands_text = "\n".join(commands)
    all_message_text = "\n".join(user_messages + [m["text"] for m in assistant_messages])
    mentioned_paths = extract_paths(all_commands_text, all_message_text)
    touched_paths = stable_unique(patch_paths + mentioned_paths, limit=60)

    latest_user = ""
    for message in reversed(user_messages):
        if "<environment_context>" not in message:
            latest_user = compact_text(message, 1000)
            break

    next_steps = derive_next_steps(latest_goal, plan_items, final_messages, commentary_messages)
    started_at = str(meta.get("timestamp") or "")
    updated_at = dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).isoformat(
        timespec="seconds"
    )
    cwd = str(latest_turn.get("cwd") or meta.get("cwd") or "")

    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "session_id": session_id,
        "source_path": str(path),
        "source_mtime_ns": stat.st_mtime_ns,
        "source_size": stat.st_size,
        "started_at": started_at,
        "updated_at": updated_at,
        "cwd": cwd,
        "originator": meta.get("originator"),
        "cli_version": meta.get("cli_version"),
        "model": latest_turn.get("model") or meta.get("model"),
        "approval_policy": latest_turn.get("approval_policy"),
        "timezone": latest_turn.get("timezone"),
        "goal": {
            "objective": latest_goal.get("objective"),
            "status": latest_goal.get("status"),
            "tokens_used": latest_goal.get("tokensUsed"),
            "time_used_seconds": latest_goal.get("timeUsedSeconds"),
        },
        "latest_user_message": latest_user,
        "recent_user_messages": [compact_text(x, 700) for x in stable_unique(user_messages)[-8:]],
        "final_answer": block_text(final_messages[-1], 2600) if final_messages else "",
        "recent_agent_updates": [
            compact_text(x, 700) for x in stable_unique(commentary_messages)[-8:]
        ],
        "commands": stable_unique(commands, limit=40),
        "verification_commands": stable_unique(verification, limit=20),
        "touched_or_referenced_paths": touched_paths,
        "blockers_or_warnings": stable_unique(blockers, limit=12),
        "plan_items": plan_items[-20:],
        "next_steps": next_steps,
    }


def derive_next_steps(
    latest_goal: dict[str, Any],
    plan_items: list[dict[str, str]],
    final_messages: list[str],
    commentary_messages: list[str],
) -> list[str]:
    steps: list[str] = []
    status = str(latest_goal.get("status") or "")
    objective = latest_goal.get("objective")
    if status == "active" and objective:
        steps.append("Continue the active goal; do not treat the previous window as complete.")
    elif status == "blocked":
        steps.append("Resume only after the blocker in the goal state is resolved.")
    elif status == "complete":
        steps.append("Goal was marked complete; use this context mainly as historical evidence.")

    for item in plan_items:
        if item.get("status") in {"pending", "in_progress"}:
            steps.append(f"{item.get('status')}: {item.get('step')}")

    candidates = "\n".join(final_messages[-2:] + commentary_messages[-3:])
    for line in candidates.splitlines():
        stripped = line.strip(" -\t")
        if not stripped:
            continue
        if re.search(r"next|下一步|remaining|仍需|blocked|阻塞|follow", stripped, re.I):
            steps.append(stripped)

    return stable_unique([compact_text(step, 500) for step in steps], limit=10)


def render_session_markdown(snapshot: dict[str, Any]) -> str:
    session_id = str(snapshot["session_id"])
    goal = snapshot.get("goal") or {}
    lines: list[str] = [
        f"# Codex Session Resume: {session_id}",
        "",
        "## New-chat bootstrap",
        "",
        "Paste or ask this in a fresh Codex chat when you want continuity:",
        "",
        "```text",
        f"Read /Users/haihan/.codex/session-context/sessions/{session_id}.md first, then continue the same work. Verify current files/runtime before acting.",
        "```",
        "",
        "## Session",
        "",
        f"- Session ID: `{session_id}`",
        f"- Source log: `{snapshot.get('source_path')}`",
        f"- CWD: `{snapshot.get('cwd') or 'unknown'}`",
        f"- Started: `{snapshot.get('started_at') or 'unknown'}`",
        f"- Last updated: `{snapshot.get('updated_at') or 'unknown'}`",
        f"- Model: `{snapshot.get('model') or 'unknown'}`",
        f"- Goal status: `{goal.get('status') or 'unknown'}`",
        "",
    ]

    if goal.get("objective"):
        lines.extend(["## Goal", "", str(goal["objective"]).strip(), ""])
    if snapshot.get("latest_user_message"):
        lines.extend(["## Latest User Request", "", snapshot["latest_user_message"], ""])
    if snapshot.get("final_answer"):
        lines.extend(["## Last Final Answer", "", snapshot["final_answer"], ""])

    next_steps = snapshot.get("next_steps") or []
    if next_steps:
        lines.extend(["## Resume Next", ""])
        lines.extend([f"- {step}" for step in next_steps])
        lines.append("")

    blockers = snapshot.get("blockers_or_warnings") or []
    if blockers:
        lines.extend(["## Blockers Or Warnings", ""])
        lines.extend([f"- {item}" for item in blockers[:8]])
        lines.append("")

    paths = snapshot.get("touched_or_referenced_paths") or []
    if paths:
        lines.extend(["## Files And Artifacts", ""])
        lines.extend([f"- `{path}`" for path in paths[:30]])
        lines.append("")

    verification = snapshot.get("verification_commands") or []
    if verification:
        lines.extend(["## Verification Commands Seen", ""])
        lines.extend([f"- `{cmd}`" for cmd in verification[:15]])
        lines.append("")

    updates = snapshot.get("recent_agent_updates") or []
    if updates:
        lines.extend(["## Recent Agent Updates", ""])
        lines.extend([f"- {item}" for item in updates[-6:]])
        lines.append("")

    user_messages = snapshot.get("recent_user_messages") or []
    if user_messages:
        lines.extend(["## Recent User Messages", ""])
        lines.extend([f"- {item}" for item in user_messages[-5:]])
        lines.append("")

    lines.extend(
        [
            "## Resume Rules",
            "",
            "- Treat this file as compact context, not proof that the current filesystem or remote services still match it.",
            "- Before claiming current state, inspect referenced files, generated reports, services, or APIs again.",
            "- Preserve explicit user constraints and supervised-action boundaries from the prior session.",
            "",
            f"_Generated at {snapshot.get('generated_at')}._",
            "",
        ]
    )
    return "\n".join(lines)


def render_latest_markdown(snapshots: list[dict[str, Any]], output_root: Path) -> str:
    sorted_snapshots = sorted(
        snapshots, key=lambda item: str(item.get("updated_at") or ""), reverse=True
    )
    lines = [
        "# Codex Session Context Index",
        "",
        "## New-chat bootstrap",
        "",
        "At the start of a fresh Codex chat that needs continuity, read this file first, then open the matching session resume under `sessions/`.",
        "",
        f"- Context root: `{output_root}`",
        f"- Generated at: `{utc_now()}`",
        "",
        "## Most Recent Sessions",
        "",
    ]
    if not sorted_snapshots:
        lines.append("No Codex sessions indexed yet.")
        lines.append("")
        return "\n".join(lines)

    for snapshot in sorted_snapshots[:20]:
        session_id = snapshot["session_id"]
        goal = snapshot.get("goal") or {}
        objective = compact_text(str(goal.get("objective") or snapshot.get("latest_user_message") or ""), 220)
        status = goal.get("status") or "unknown"
        lines.extend(
            [
                f"### {session_id}",
                "",
                f"- Resume file: `{output_root / 'sessions' / (session_id + '.md')}`",
                f"- Updated: `{snapshot.get('updated_at')}`",
                f"- CWD: `{snapshot.get('cwd') or 'unknown'}`",
                f"- Goal status: `{status}`",
                f"- Objective/request: {objective or 'unknown'}",
                "",
            ]
        )

    latest_by_cwd: dict[str, dict[str, Any]] = {}
    for snapshot in sorted_snapshots:
        cwd = str(snapshot.get("cwd") or "unknown")
        if cwd not in latest_by_cwd:
            latest_by_cwd[cwd] = snapshot
    lines.extend(["## Latest By Workspace", ""])
    for cwd, snapshot in list(latest_by_cwd.items())[:20]:
        session_id = snapshot["session_id"]
        lines.append(f"- `{cwd}` -> `{output_root / 'sessions' / (session_id + '.md')}`")
    lines.append("")
    return "\n".join(lines)


def discover_session_files(roots: list[Path], days: int | None, max_sessions: int) -> list[Path]:
    cutoff: float | None = None
    if days is not None and days > 0:
        cutoff = time.time() - days * 86400
    paths: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("rollout-*.jsonl"):
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue
            if cutoff is not None and stat.st_mtime < cutoff:
                continue
            paths.append(path)
    paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return paths[:max_sessions]


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"sources": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"sources": {}}
    if not isinstance(data, dict):
        return {"sources": {}}
    data.setdefault("sources", {})
    return data


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def scan_sessions(
    output_root: Path,
    roots: list[Path],
    days: int | None,
    max_sessions: int,
    force: bool = False,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    sessions_dir = output_root / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_root / "state.json"
    state = load_state(state_path)
    sources_state: dict[str, Any] = state.setdefault("sources", {})
    snapshots: list[dict[str, Any]] = []
    parsed = 0
    reused = 0

    for source_path in discover_session_files(roots, days, max_sessions):
        stat = source_path.stat()
        source_key = str(source_path)
        cached = sources_state.get(source_key) if isinstance(sources_state, dict) else None
        snapshot: dict[str, Any] | None = None
        if isinstance(cached, dict) and not force:
            cached_json = cached.get("snapshot_json")
            if (
                cached.get("mtime_ns") == stat.st_mtime_ns
                and cached.get("size") == stat.st_size
                and isinstance(cached_json, str)
                and Path(cached_json).exists()
            ):
                try:
                    snapshot = json.loads(Path(cached_json).read_text(encoding="utf-8"))
                    reused += 1
                except (json.JSONDecodeError, OSError):
                    snapshot = None

        if snapshot is None:
            snapshot = parse_session_file(source_path)
            parsed += 1
            session_id = snapshot["session_id"]
            json_path = sessions_dir / f"{session_id}.json"
            md_path = sessions_dir / f"{session_id}.md"
            snapshot["resume_path"] = str(md_path)
            save_json(json_path, snapshot)
            write_text(md_path, render_session_markdown(snapshot))
            sources_state[source_key] = {
                "session_id": session_id,
                "mtime_ns": stat.st_mtime_ns,
                "size": stat.st_size,
                "snapshot_json": str(json_path),
                "resume_path": str(md_path),
                "updated_at": snapshot.get("updated_at"),
            }
        snapshots.append(snapshot)

    snapshots.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    save_json(output_root / "latest_index.json", {"generated_at": utc_now(), "sessions": snapshots})
    write_text(output_root / "latest_resume.md", render_latest_markdown(snapshots, output_root))
    state["generated_at"] = utc_now()
    save_json(state_path, state)
    return {
        "ok": True,
        "output_root": str(output_root),
        "session_count": len(snapshots),
        "parsed": parsed,
        "reused": reused,
        "latest_resume": str(output_root / "latest_resume.md"),
    }


def doctor(output_root: Path) -> dict[str, Any]:
    latest = output_root / "latest_resume.md"
    index = output_root / "latest_index.json"
    errors: list[str] = []
    if not latest.exists():
        errors.append(f"missing {latest}")
    if not index.exists():
        errors.append(f"missing {index}")
    session_count = 0
    if index.exists():
        try:
            data = json.loads(index.read_text(encoding="utf-8"))
            session_count = len(data.get("sessions") or [])
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"cannot read index: {exc}")
    return {
        "ok": not errors,
        "output_root": str(output_root),
        "latest_resume": str(latest),
        "session_count": session_count,
        "errors": errors,
    }


def parse_roots(values: list[str] | None) -> list[Path]:
    if not values:
        return DEFAULT_SESSION_ROOTS
    roots: list[Path] = []
    for value in values:
        for part in value.split(os.pathsep):
            if part.strip():
                roots.append(Path(part).expanduser())
    return roots


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build compact resume context files from Codex session JSONL logs."
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Where resume context files are written.",
    )
    parser.add_argument(
        "--session-root",
        action="append",
        help="Codex session root to scan. Can be passed multiple times.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Scan sessions once and write resume files.")
    scan.add_argument("--days", type=int, default=30)
    scan.add_argument("--max-sessions", type=int, default=250)
    scan.add_argument("--force", action="store_true")

    watch = subparsers.add_parser("watch", help="Repeatedly scan sessions.")
    watch.add_argument("--days", type=int, default=30)
    watch.add_argument("--max-sessions", type=int, default=250)
    watch.add_argument("--interval-seconds", type=int, default=300)
    watch.add_argument("--force", action="store_true")

    subparsers.add_parser("doctor", help="Check generated context files.")
    subparsers.add_parser("print-latest", help="Print the latest resume path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_root = Path(args.output_root).expanduser()
    roots = parse_roots(args.session_root)

    if args.command == "scan":
        result = scan_sessions(
            output_root=output_root,
            roots=roots,
            days=args.days,
            max_sessions=args.max_sessions,
            force=args.force,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1

    if args.command == "watch":
        while True:
            result = scan_sessions(
                output_root=output_root,
                roots=roots,
                days=args.days,
                max_sessions=args.max_sessions,
                force=args.force,
            )
            print(json.dumps(result, ensure_ascii=False), flush=True)
            time.sleep(max(args.interval_seconds, 30))

    if args.command == "doctor":
        result = doctor(output_root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1

    if args.command == "print-latest":
        print(output_root / "latest_resume.md")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
