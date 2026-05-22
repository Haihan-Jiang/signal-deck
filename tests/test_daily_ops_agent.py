from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from daily_ops_agent.company import (
    benchmark_cases,
    compare_against_single_agent,
    plan_one_person_company,
    run_benchmark,
    score_plan,
)


ROOT = Path(__file__).resolve().parents[1]


class DailyOpsAgentTests(unittest.TestCase):
    def test_plan_routes_complex_task_to_specialists(self) -> None:
        plan = plan_one_person_company(
            "设置一个 agent 公司来 research, build, test, monitor, and report safely."
        )
        role_ids = {assignment.role_id for assignment in plan.assignments}
        self.assertIn("ceo", role_ids)
        self.assertIn("research", role_ids)
        self.assertIn("builder", role_ids)
        self.assertIn("qa", role_ids)
        self.assertIn("ops", role_ids)
        self.assertEqual(plan.gaps, ())
        self.assertIn("verification", plan.covered_capabilities)

    def test_multi_agent_company_beats_single_agent_on_each_benchmark_case(self) -> None:
        for case in benchmark_cases():
            with self.subTest(case=case.id):
                result = compare_against_single_agent(case.task)
                self.assertGreater(result["scores"]["delta"], 0)
                self.assertGreater(result["faster_by_minutes"], 0)
                self.assertGreaterEqual(result["more_risk_checks"], 0)

    def test_benchmark_summary_is_repeatable_and_positive(self) -> None:
        first = run_benchmark()
        second = run_benchmark()
        self.assertEqual(first, second)
        self.assertTrue(first["all_cases_multi_agent_more_effective"])
        self.assertTrue(first["all_cases_multi_agent_faster"])
        self.assertGreater(first["average_effectiveness_delta"], 0)

    def test_single_agent_score_is_lower_for_complex_goal(self) -> None:
        task = (
            "Build a no-cost local automation, verify it with tests, guard API cost risks, "
            "and report how to run it daily."
        )
        result = compare_against_single_agent(task)
        solo = result["single_generalist"]
        company = result["one_person_company"]
        self.assertLess(solo["critical_path_minutes"], solo["total_person_minutes"] + 1)
        self.assertLess(company["critical_path_minutes"], solo["critical_path_minutes"])
        self.assertGreater(
            score_plan(plan_one_person_company(task)).overall,
            result["scores"]["single_generalist"]["overall"],
        )

    def test_cli_benchmark_json(self) -> None:
        output = subprocess.check_output(
            [sys.executable, "-m", "daily_ops_agent", "benchmark", "--json"],
            cwd=str(ROOT),
            text=True,
        )
        payload = json.loads(output)
        self.assertEqual(payload["case_count"], len(benchmark_cases()))
        self.assertTrue(payload["all_cases_multi_agent_more_effective"])


if __name__ == "__main__":
    unittest.main()
