from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import iphone_agent


class IPhoneAgentTests(unittest.TestCase):
    def test_daily_schedule_runs_once_per_local_date(self) -> None:
        task = {
            "id": "daily",
            "enabled": True,
            "schedule": {"kind": "daily", "time": "17:00"},
        }
        state: dict[str, object] = {"tasks": {}}
        now = datetime(2026, 5, 22, 17, 1, tzinfo=ZoneInfo("America/Los_Angeles"))
        self.assertTrue(iphone_agent.is_task_due(task, state, now))
        state = {"tasks": {"daily": {"last_local_date": "2026-05-22"}}}
        self.assertFalse(iphone_agent.is_task_due(task, state, now))

    def test_interval_schedule_uses_last_finished_time(self) -> None:
        task = {
            "id": "interval",
            "enabled": True,
            "schedule": {"kind": "interval", "minutes": 30},
        }
        state = {"tasks": {"interval": {"last_finished_at": "2000-01-01T00:00:00+00:00"}}}
        now = datetime(2026, 5, 22, 12, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        self.assertTrue(iphone_agent.is_task_due(task, state, now))

    def test_run_task_records_state_and_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = {
                "timezone": "America/Los_Angeles",
                "state_path": str(root / "state.json"),
                "run_log_path": str(root / "runs.jsonl"),
                "tasks": [
                    {
                        "id": "hello",
                        "title": "Hello",
                        "enabled": True,
                        "schedule": {"kind": "manual"},
                        "action": {
                            "kind": "argv",
                            "cwd": str(root),
                            "timeout_seconds": 10,
                            "argv": [sys.executable, "-c", "print('hello iphone')"],
                        },
                    }
                ],
            }
            payload = iphone_agent.run_task(config, "hello")
            self.assertTrue(payload["result"]["ok"])
            self.assertIn("hello iphone", payload["result"]["stdout"])
            state = json.loads((root / "state.json").read_text(encoding="utf-8"))
            self.assertTrue(state["tasks"]["hello"]["last_ok"])
            logs = (root / "runs.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(logs), 1)

    def test_status_snapshot_counts_jsonl_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "items.jsonl"
            path.write_text('{"a":1}\n{"a":2}\n', encoding="utf-8")
            result = iphone_agent.run_status_snapshot({"paths": [str(path)]})
            self.assertTrue(result["ok"])
            self.assertEqual(result["files"][0]["row_count"], 2)

    def test_token_check_can_require_local_token(self) -> None:
        config = {"token_required": True, "token": "abc"}
        self.assertTrue(iphone_agent.check_token(config, "abc"))
        self.assertFalse(iphone_agent.check_token(config, "wrong"))

    def test_default_config_keeps_zero_cost_scheduler_enabled(self) -> None:
        config = iphone_agent.default_config()
        self.assertTrue(config["no_cost"])
        self.assertFalse(config["policy"]["allow_paid_services"])
        self.assertFalse(config["policy"]["allow_llm_api_calls"])
        self.assertTrue(config["scheduler"]["enabled"])
        status = iphone_agent.build_status(config)
        self.assertTrue(status["no_cost"])
        self.assertTrue(status["scheduler"]["enabled"])

    def test_existing_config_is_migrated_with_safe_defaults(self) -> None:
        config = iphone_agent.with_config_defaults(
            {
                "host": "127.0.0.1",
                "port": 9999,
                "token": "abc",
                "tasks": [],
            }
        )
        self.assertTrue(config["no_cost"])
        self.assertTrue(config["scheduler"]["enabled"])
        self.assertFalse(config["policy"]["allow_paid_services"])

    def test_migrate_task_schedules_keeps_slow_signal_manual(self) -> None:
        config = {
            "tasks": [
                {"id": "signal_snapshot", "schedule": {"kind": "interval", "minutes": 30}},
                {"id": "status_snapshot", "schedule": {"kind": "manual"}},
            ]
        }
        migrated = iphone_agent.migrate_task_schedules(config)
        self.assertEqual(migrated["tasks"][0]["schedule"], {"kind": "manual"})
        self.assertEqual(migrated["tasks"][1]["schedule"], {"kind": "interval", "minutes": 30})


if __name__ == "__main__":
    unittest.main()
