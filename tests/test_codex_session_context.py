from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools import codex_session_context


class CodexSessionContextTests(unittest.TestCase):
    def write_jsonl(self, path: Path, events: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n",
            encoding="utf-8",
        )

    def sample_events(self) -> list[dict[str, object]]:
        return [
            {
                "timestamp": "2026-05-24T10:00:00Z",
                "type": "session_meta",
                "payload": {
                    "id": "019e59a4-2d32-7812-9c6d-bc6481667997",
                    "timestamp": "2026-05-24T10:00:00Z",
                    "cwd": "/tmp/project",
                    "originator": "Codex Desktop",
                    "cli_version": "0.test",
                },
            },
            {
                "timestamp": "2026-05-24T10:00:01Z",
                "type": "turn_context",
                "payload": {
                    "turn_id": "turn-1",
                    "cwd": "/tmp/project",
                    "model": "gpt-test",
                    "approval_policy": "never",
                    "timezone": "America/Los_Angeles",
                },
            },
            {
                "timestamp": "2026-05-24T10:00:02Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "/goal preserve context"}],
                },
            },
            {
                "timestamp": "2026-05-24T10:00:03Z",
                "type": "event_msg",
                "payload": {
                    "type": "thread_goal_updated",
                    "goal": {
                        "objective": "preserve context",
                        "status": "active",
                        "tokensUsed": 100,
                        "timeUsedSeconds": 10,
                    },
                },
            },
            {
                "timestamp": "2026-05-24T10:00:04Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "arguments": json.dumps(
                        {
                            "cmd": "python3 -m unittest tests/test_codex_session_context.py",
                            "workdir": "/tmp/project",
                        }
                    ),
                    "call_id": "call-1",
                },
            },
            {
                "timestamp": "2026-05-24T10:00:05Z",
                "type": "event_msg",
                "payload": {
                    "type": "patch_apply_end",
                    "stdout": "Success. Updated the following files:\nM tools/codex_session_context.py\n",
                    "stderr": "",
                    "success": True,
                },
            },
            {
                "timestamp": "2026-05-24T10:00:06Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "phase": "final_answer",
                    "content": [{"type": "output_text", "text": "Implemented context scanner."}],
                },
            },
        ]

    def test_parse_session_file_extracts_resume_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "rollout-2026-05-24T10-00-00-019e59a4-2d32-7812-9c6d-bc6481667997.jsonl"
            self.write_jsonl(path, self.sample_events())

            snapshot = codex_session_context.parse_session_file(path)

            self.assertEqual(snapshot["session_id"], "019e59a4-2d32-7812-9c6d-bc6481667997")
            self.assertEqual(snapshot["cwd"], "/tmp/project")
            self.assertEqual(snapshot["goal"]["status"], "active")
            self.assertIn("preserve context", snapshot["goal"]["objective"])
            self.assertIn(
                "python3 -m unittest tests/test_codex_session_context.py",
                snapshot["verification_commands"],
            )
            self.assertIn("tools/codex_session_context.py", snapshot["touched_or_referenced_paths"])
            self.assertIn("Implemented context scanner.", snapshot["final_answer"])

    def test_scan_writes_latest_and_session_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sessions = root / "sessions"
            output = root / "context"
            path = sessions / "rollout-2026-05-24T10-00-00-019e59a4-2d32-7812-9c6d-bc6481667997.jsonl"
            self.write_jsonl(path, self.sample_events())

            result = codex_session_context.scan_sessions(
                output_root=output,
                roots=[sessions],
                days=None,
                max_sessions=10,
            )

            self.assertTrue(result["ok"])
            self.assertEqual(result["session_count"], 1)
            latest = output / "latest_resume.md"
            resume = output / "sessions" / "019e59a4-2d32-7812-9c6d-bc6481667997.md"
            self.assertTrue(latest.exists())
            self.assertTrue(resume.exists())
            self.assertIn("Codex Session Context Index", latest.read_text(encoding="utf-8"))
            self.assertIn("Read /Users/haihan/.codex/session-context/sessions", resume.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
