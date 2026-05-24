# Codex Session Context Preservation

This is a local, zero-service context handoff layer for Codex desktop sessions.
It scans Codex rollout JSONL logs and writes compact resume files under:

```text
/Users/haihan/.codex/session-context
```

The main entry point for a fresh chat is:

```text
/Users/haihan/.codex/session-context/latest_resume.md
```

## What It Preserves

- session id, source JSONL path, cwd, model, and timestamps
- active or completed goal state when present
- latest user request and recent user constraints
- final answer or latest agent updates
- touched or referenced files and artifacts
- verification commands seen in the session
- blockers, warnings, pending plan steps, and resume hints

It does not replace live verification. A new chat should read the relevant
resume file, then inspect current files, services, reports, or APIs before
claiming the current state.

## Manual Commands

Generate context once:

```bash
python3 tools/codex_session_context.py scan
```

Check generated context:

```bash
python3 tools/codex_session_context.py doctor
```

Print the entry file path:

```bash
python3 tools/codex_session_context.py print-latest
```

## LaunchAgent

Install the automatic refresher:

```bash
./install_codex_session_context_launchd.sh
```

By default it runs every 300 seconds and indexes the latest 30 days, up to 250
session logs. Override before installing if needed:

```bash
CODEX_SESSION_CONTEXT_INTERVAL=120 CODEX_SESSION_CONTEXT_DAYS=14 ./install_codex_session_context_launchd.sh
```

The LaunchAgent writes logs to:

```text
/Users/haihan/.codex/session-context/logs/launchd.log
```

## Fresh Chat Habit

In a new Codex chat, ask:

```text
Read /Users/haihan/.codex/session-context/latest_resume.md first, then continue the relevant session.
```

The root `AGENTS.md` in this workspace also points Codex to this context entry
when a conversation is a continuation or goal-backed resume.
