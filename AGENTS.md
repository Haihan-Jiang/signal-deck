# Workspace Continuity

When a new Codex chat in this workspace is a continuation, resume, or
goal-backed follow-up, use `$codex-session-continuity` first. If the skill is
not listed in the current chat yet, use its manual fallback and read:

```text
/Users/haihan/.codex/session-context/latest_resume.md
```

Then open the matching session resume file under
`/Users/haihan/.codex/session-context/sessions/` before answering or editing.
Treat those files as compact handoff context, and verify current files,
reports, services, or APIs before claiming the current state.
