---
name: codex-session-continuity
description: Preserve and resume Codex Desktop session context from the user's local session-context index. Use when the user asks to continue a previous Codex session, recover context after a context-window limit, reopen work in a new chat, inspect what happened in another session, refresh session handoff files, or says phrases like "恢复上下文", "继续上次", "session context", "context额度", "new chat继续", or "窗口上下文结束后继续".
---

# Codex Session Continuity

## Overview

Use the local context handoff generated under
`/Users/haihan/.codex/session-context` to resume prior Codex work with minimal
loss of context. Treat the handoff as a compact summary, not current-state
proof.

## Quick Workflow

1. Refresh the local index when the user wants the latest state:

```bash
python3 /Users/haihan/Documents/New\ project/tools/codex_session_context.py scan --days 30 --max-sessions 250
```

If the repo copy is unavailable, use the runtime copy:

```bash
python3 /Users/haihan/.codex/session-context/runtime/codex_session_context.py --output-root /Users/haihan/.codex/session-context scan --days 30 --max-sessions 250
```

2. Read the index:

```text
/Users/haihan/.codex/session-context/latest_resume.md
```

3. Select the most relevant session by cwd, goal, latest user request, or
workspace. Open the matching file under:

```text
/Users/haihan/.codex/session-context/sessions/
```

4. Before acting, verify live state from the referenced files, reports,
services, APIs, or git status. Do not present resume content as confirmed
current state unless verified in this turn.

5. Continue the task using the resume's `Goal`, `Resume Next`, `Files And
Artifacts`, `Verification Commands Seen`, and `Blockers Or Warnings` sections.

## How To Answer The User

For "后面该怎么用", give this simple user-facing instruction:

```text
新 chat 里直接说：
Use $codex-session-continuity to read /Users/haihan/.codex/session-context/latest_resume.md and continue the relevant session.
```

If they know the exact session, tell them to point to that resume file:

```text
Use $codex-session-continuity to resume from /Users/haihan/.codex/session-context/sessions/<session-id>.md.
```

## Maintenance Commands

Check generated context:

```bash
python3 /Users/haihan/Documents/New\ project/tools/codex_session_context.py doctor
```

Check the launchd refresher:

```bash
launchctl print gui/$(id -u)/com.haihan.codex.sessioncontext
```

Reinstall/update the 5-minute refresher after editing the scanner:

```bash
/Users/haihan/Documents/New\ project/install_codex_session_context_launchd.sh
```

The launchd job should normally show `last exit code = 0`; `state = not
running` is normal between interval runs.

## Boundaries

- Do not claim Codex Desktop automatically injects old full context into the
  new model window. The supported path is read `latest_resume.md`, then read
  the selected resume file.
- Do not store or expose extra private form answers, secrets, or credentials in
  new durable artifacts.
- Do not blindly continue risky external actions from a resume; re-check the
  user's current constraints and any supervised-action boundaries first.
