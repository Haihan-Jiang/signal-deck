from __future__ import annotations

import argparse
import json
from typing import Optional, Sequence

from .company import (
    compare_against_single_agent,
    plan_one_person_company,
    render_benchmark,
    render_plan,
    run_benchmark,
)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m daily_ops_agent",
        description="Plan and benchmark a deterministic one-person-company agent team.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="Create a multi-agent plan for a task.")
    plan_parser.add_argument("--task", required=True, help="Task to route through the agent company.")
    plan_parser.add_argument("--json", action="store_true", help="Print structured JSON.")
    plan_parser.add_argument(
        "--compare-single",
        action="store_true",
        help="Also include the single-generalist baseline and score delta.",
    )

    bench_parser = subparsers.add_parser("benchmark", help="Run the deterministic effectiveness benchmark.")
    bench_parser.add_argument("--json", action="store_true", help="Print structured JSON.")

    args = parser.parse_args(argv)
    if args.command == "plan":
        if args.compare_single:
            payload = compare_against_single_agent(args.task)
            if args.json:
                print(json.dumps(payload, indent=2, ensure_ascii=True))
            else:
                print(render_plan(plan_one_person_company(args.task)))
                print("")
                print(f"Effectiveness delta vs single agent: {payload['scores']['delta']}")
            return 0
        plan = plan_one_person_company(args.task)
        print(plan.to_json() if args.json else render_plan(plan))
        return 0

    if args.command == "benchmark":
        summary = run_benchmark()
        print(json.dumps(summary, indent=2, ensure_ascii=True) if args.json else render_benchmark(summary))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
