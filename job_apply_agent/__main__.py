from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import (
    apply_learning_task_answers,
    build_answer_gap_report,
    build_application_draft,
    build_application_research,
    build_position_readiness_report,
    learn_answers,
    load_answer_memory,
    load_closed_jobs,
    load_jobs,
    load_profile,
    load_submissions_jsonl,
    notify_telegram_for_submissions,
    open_apply_urls_in_browser,
    record_closed_job,
    refresh_closed_jobs_from_live_pages,
    run_pipeline,
    write_answer_gap_report,
    write_apply_run_audit,
    write_application_playbook,
    write_application_research_report,
    write_form_fill_plan,
    write_learning_task_template,
    write_position_readiness_report,
    write_synthetic_apply_execution,
    write_synthetic_application_simulation,
)


DEFAULT_PROFILE = Path(__file__).with_name("sample_profile.json")
DEFAULT_JOBS = Path(__file__).with_name("sample_jobs.json")
DEFAULT_OUTBOX = Path(__file__).with_name("outbox") / "dry_run_submissions.jsonl"
DEFAULT_MEMORY = Path(__file__).with_name("outbox") / "answer_memory.json"
DEFAULT_REVIEW_LOG = Path(__file__).with_name("outbox") / "browser_review_queue.jsonl"
DEFAULT_CLOSED_JOBS = Path(__file__).with_name("outbox") / "closed_jobs.json"
DEFAULT_RESEARCH_JSON = Path(__file__).with_name("outbox") / "application_research_latest.json"
DEFAULT_RESEARCH_MARKDOWN = Path(__file__).with_name("outbox") / "application_research_latest.md"
DEFAULT_GAPS_JSON = Path(__file__).with_name("outbox") / "answer_gaps_latest.json"
DEFAULT_GAPS_MARKDOWN = Path(__file__).with_name("outbox") / "answer_gaps_latest.md"
DEFAULT_READINESS_JSON = Path(__file__).with_name("outbox") / "automation_readiness_latest.json"
DEFAULT_READINESS_MARKDOWN = Path(__file__).with_name("outbox") / "automation_readiness_latest.md"
DEFAULT_FILL_PLAN_JSON = Path(__file__).with_name("outbox") / "form_fill_plan_latest.json"
DEFAULT_FILL_PLAN_MARKDOWN = Path(__file__).with_name("outbox") / "form_fill_plan_latest.md"
DEFAULT_APPLY_AUDIT_JSON = Path(__file__).with_name("outbox") / "apply_run_audit_latest.json"
DEFAULT_APPLY_AUDIT_MARKDOWN = Path(__file__).with_name("outbox") / "apply_run_audit_latest.md"
DEFAULT_LEARNING_TASKS_JSON = Path(__file__).with_name("outbox") / "learning_tasks_latest.json"
DEFAULT_LEARNING_TASKS_MARKDOWN = Path(__file__).with_name("outbox") / "learning_tasks_latest.md"
DEFAULT_SYNTHETIC_JSON = Path(__file__).with_name("outbox") / "synthetic_100_run_latest.json"
DEFAULT_SYNTHETIC_MARKDOWN = Path(__file__).with_name("outbox") / "synthetic_100_run_latest.md"
DEFAULT_SYNTHETIC_EXEC_JSON = Path(__file__).with_name("outbox") / "synthetic_apply_execution_latest.json"
DEFAULT_SYNTHETIC_EXEC_MARKDOWN = Path(__file__).with_name("outbox") / "synthetic_apply_execution_latest.md"
DEFAULT_PLAYBOOK_JSON = Path(__file__).with_name("outbox") / "application_playbook_latest.json"
DEFAULT_PLAYBOOK_MARKDOWN = Path(__file__).with_name("outbox") / "application_playbook_latest.md"
DEFAULT_PERSONAL_PROFILE = Path(__file__).with_name("outbox") / "alan_jiang_profile.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run job application assistant")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="score jobs and simulate applications")
    run_parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    run_parser.add_argument("--jobs", default=str(DEFAULT_JOBS))
    run_parser.add_argument("--outbox", default=str(DEFAULT_OUTBOX))
    run_parser.add_argument("--memory", default=None, help="approved answer memory JSON")
    run_parser.add_argument("--limit", type=int, default=3)
    run_parser.add_argument(
        "--allow-unattended-submit",
        action="store_true",
        help="mark submissions eligible for unattended submit when policy checks pass",
    )
    run_parser.add_argument(
        "--notify-telegram",
        action="store_true",
        help="send a Telegram notification for the generated dry-run submissions",
    )
    run_parser.add_argument(
        "--telegram-env",
        default=None,
        help="env file with Telegram bot token and chat id",
    )
    run_parser.add_argument(
        "--telegram-dry-run",
        action="store_true",
        help="build the Telegram message without sending it",
    )
    run_parser.add_argument(
        "--open-browser",
        action="store_true",
        help="open apply URLs for generated submissions in the local browser",
    )
    run_parser.add_argument(
        "--review-log",
        default=str(DEFAULT_REVIEW_LOG),
        help="JSONL review queue written when --open-browser is used",
    )
    run_parser.add_argument("--closed-jobs", default=str(DEFAULT_CLOSED_JOBS))
    run_parser.add_argument(
        "--live-check",
        action="store_true",
        help="fetch current apply pages and record closed postings before notify/open",
    )
    run_parser.add_argument("--live-check-limit", type=int, default=25)
    run_parser.add_argument("--live-check-timeout", type=float, default=15.0)
    run_parser.add_argument("--json", action="store_true", help="print full JSON submissions")

    score_parser = subparsers.add_parser("score", help="preview scores and answers only")
    score_parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    score_parser.add_argument("--jobs", default=str(DEFAULT_JOBS))
    score_parser.add_argument("--memory", default=None, help="approved answer memory JSON")
    score_parser.add_argument("--closed-jobs", default=str(DEFAULT_CLOSED_JOBS))

    learn_parser = subparsers.add_parser(
        "learn",
        help="record manually approved answers for future autofill",
    )
    learn_parser.add_argument("--job", required=True, help="single-job JSON or jobs JSON")
    learn_parser.add_argument("--answers", required=True, help="question-to-answer JSON")
    learn_parser.add_argument("--memory", default=str(DEFAULT_MEMORY))
    learn_parser.add_argument("--source", default="manual_submission")

    notify_parser = subparsers.add_parser(
        "notify",
        help="send a Telegram notification for existing dry-run submissions",
    )
    notify_parser.add_argument("--submissions", default=str(DEFAULT_OUTBOX))
    notify_parser.add_argument("--limit", type=int, default=5)
    notify_parser.add_argument("--telegram-env", default=None)
    notify_parser.add_argument("--telegram-dry-run", action="store_true")
    notify_parser.add_argument("--open-browser", action="store_true")
    notify_parser.add_argument("--review-log", default=str(DEFAULT_REVIEW_LOG))
    notify_parser.add_argument("--closed-jobs", default=str(DEFAULT_CLOSED_JOBS))
    notify_parser.add_argument("--live-check", action="store_true")
    notify_parser.add_argument("--live-check-limit", type=int, default=25)
    notify_parser.add_argument("--live-check-timeout", type=float, default=15.0)

    close_parser = subparsers.add_parser(
        "close",
        help="record a job as closed so future notifications skip it",
    )
    close_parser.add_argument("--url", required=True)
    close_parser.add_argument("--company", default=None)
    close_parser.add_argument("--title", default=None)
    close_parser.add_argument("--platform", default=None)
    close_parser.add_argument("--job-id", default=None)
    close_parser.add_argument("--reason", default="No longer accepting applications")
    close_parser.add_argument("--source", default="manual")
    close_parser.add_argument("--closed-jobs", default=str(DEFAULT_CLOSED_JOBS))

    research_parser = subparsers.add_parser(
        "research",
        help="summarize observed application questions and automation actions",
    )
    research_parser.add_argument(
        "--outbox-dir",
        default=str(Path(__file__).with_name("outbox")),
    )
    research_parser.add_argument("--position-target", type=int, default=100)
    research_parser.add_argument("--max-items", type=int, default=None)
    research_parser.add_argument("--json-output", default=str(DEFAULT_RESEARCH_JSON))
    research_parser.add_argument("--markdown-output", default=str(DEFAULT_RESEARCH_MARKDOWN))

    gaps_parser = subparsers.add_parser(
        "gaps",
        help="summarize which observed prompts still need approved answers or profile data",
    )
    gaps_parser.add_argument("--research-json", default=str(DEFAULT_RESEARCH_JSON))
    gaps_parser.add_argument(
        "--outbox-dir",
        default=str(Path(__file__).with_name("outbox")),
        help="used to build research if --research-json does not exist",
    )
    gaps_parser.add_argument(
        "--profile",
        default=str(DEFAULT_PERSONAL_PROFILE if DEFAULT_PERSONAL_PROFILE.exists() else DEFAULT_PROFILE),
    )
    gaps_parser.add_argument("--memory", default=str(DEFAULT_MEMORY))
    gaps_parser.add_argument("--json-output", default=str(DEFAULT_GAPS_JSON))
    gaps_parser.add_argument("--markdown-output", default=str(DEFAULT_GAPS_MARKDOWN))

    readiness_parser = subparsers.add_parser(
        "readiness",
        help="summarize per-position automation readiness and learning queue",
    )
    readiness_parser.add_argument("--research-json", default=str(DEFAULT_RESEARCH_JSON))
    readiness_parser.add_argument("--gaps-json", default=str(DEFAULT_GAPS_JSON))
    readiness_parser.add_argument(
        "--outbox-dir",
        default=str(Path(__file__).with_name("outbox")),
        help="used to build research if --research-json does not exist",
    )
    readiness_parser.add_argument(
        "--profile",
        default=str(DEFAULT_PERSONAL_PROFILE if DEFAULT_PERSONAL_PROFILE.exists() else DEFAULT_PROFILE),
    )
    readiness_parser.add_argument("--memory", default=str(DEFAULT_MEMORY))
    readiness_parser.add_argument("--closed-jobs", default=str(DEFAULT_CLOSED_JOBS))
    readiness_parser.add_argument("--json-output", default=str(DEFAULT_READINESS_JSON))
    readiness_parser.add_argument("--markdown-output", default=str(DEFAULT_READINESS_MARKDOWN))

    fill_plan_parser = subparsers.add_parser(
        "fill-plan",
        help="build an offline field-by-field plan for a captured application form snapshot",
    )
    fill_plan_parser.add_argument("--snapshot", required=True)
    fill_plan_parser.add_argument(
        "--profile",
        default=str(DEFAULT_PERSONAL_PROFILE if DEFAULT_PERSONAL_PROFILE.exists() else DEFAULT_PROFILE),
    )
    fill_plan_parser.add_argument("--memory", default=str(DEFAULT_MEMORY))
    fill_plan_parser.add_argument("--include-values", action="store_true")
    fill_plan_parser.add_argument("--json-output", default=str(DEFAULT_FILL_PLAN_JSON))
    fill_plan_parser.add_argument("--markdown-output", default=str(DEFAULT_FILL_PLAN_MARKDOWN))

    apply_audit_parser = subparsers.add_parser(
        "apply-audit",
        help="audit a fill plan before any browser automation or final submit",
    )
    apply_audit_parser.add_argument("--plan", default=str(DEFAULT_FILL_PLAN_JSON))
    apply_audit_parser.add_argument("--page-text", default="")
    apply_audit_parser.add_argument("--page-text-file", default=None)
    apply_audit_parser.add_argument("--closed-jobs", default=str(DEFAULT_CLOSED_JOBS))
    apply_audit_parser.add_argument("--json-output", default=str(DEFAULT_APPLY_AUDIT_JSON))
    apply_audit_parser.add_argument("--markdown-output", default=str(DEFAULT_APPLY_AUDIT_MARKDOWN))

    learning_template_parser = subparsers.add_parser(
        "learning-template",
        help="write a reusable answer/material template from readiness blockers",
    )
    learning_template_parser.add_argument("--readiness-json", default=str(DEFAULT_READINESS_JSON))
    learning_template_parser.add_argument("--json-output", default=str(DEFAULT_LEARNING_TASKS_JSON))
    learning_template_parser.add_argument("--markdown-output", default=str(DEFAULT_LEARNING_TASKS_MARKDOWN))

    apply_learning_parser = subparsers.add_parser(
        "apply-learning",
        help="apply approved learning-template answers to profile and answer memory",
    )
    apply_learning_parser.add_argument("--tasks", default=str(DEFAULT_LEARNING_TASKS_JSON))
    apply_learning_parser.add_argument(
        "--profile",
        default=str(DEFAULT_PERSONAL_PROFILE if DEFAULT_PERSONAL_PROFILE.exists() else DEFAULT_PROFILE),
    )
    apply_learning_parser.add_argument("--memory", default=str(DEFAULT_MEMORY))
    apply_learning_parser.add_argument("--source", default="learning_task_template")
    apply_learning_parser.add_argument("--dry-run", action="store_true")

    synthetic_parser = subparsers.add_parser(
        "synthetic-run",
        help="run offline fake-candidate application simulations without real submissions",
    )
    synthetic_parser.add_argument("--count", type=int, default=100)
    synthetic_parser.add_argument("--include-values", action="store_true")
    synthetic_parser.add_argument("--json-output", default=str(DEFAULT_SYNTHETIC_JSON))
    synthetic_parser.add_argument("--markdown-output", default=str(DEFAULT_SYNTHETIC_MARKDOWN))

    synthetic_exec_parser = subparsers.add_parser(
        "synthetic-exec",
        help="execute synthetic applications through the offline apply state machine",
    )
    synthetic_exec_parser.add_argument("--count", type=int, default=100)
    synthetic_exec_parser.add_argument(
        "--per-platform-target",
        type=int,
        default=None,
        help="run this many synthetic applications for each synthetic platform",
    )
    synthetic_exec_parser.add_argument("--include-values", action="store_true")
    synthetic_exec_parser.add_argument("--json-output", default=str(DEFAULT_SYNTHETIC_EXEC_JSON))
    synthetic_exec_parser.add_argument("--markdown-output", default=str(DEFAULT_SYNTHETIC_EXEC_MARKDOWN))

    playbook_parser = subparsers.add_parser(
        "playbook",
        help="summarize platform-specific automation rules, blockers, and learning tasks",
    )
    playbook_parser.add_argument("--research-json", default=str(DEFAULT_RESEARCH_JSON))
    playbook_parser.add_argument("--gaps-json", default=str(DEFAULT_GAPS_JSON))
    playbook_parser.add_argument("--readiness-json", default=str(DEFAULT_READINESS_JSON))
    playbook_parser.add_argument("--synthetic-json", default=str(DEFAULT_SYNTHETIC_JSON))
    playbook_parser.add_argument("--json-output", default=str(DEFAULT_PLAYBOOK_JSON))
    playbook_parser.add_argument("--markdown-output", default=str(DEFAULT_PLAYBOOK_MARKDOWN))

    args = parser.parse_args()

    if args.command == "learn":
        jobs = load_jobs(args.job)
        if len(jobs) != 1:
            raise ValueError("--job must contain exactly one job")
        answers = json.loads(Path(args.answers).read_text(encoding="utf-8"))
        if not isinstance(answers, dict):
            raise ValueError("--answers must be a JSON object mapping questions to answers")
        memory = learn_answers(args.memory, jobs[0], answers, source=args.source)
        print(f"Recorded {len(answers)} approved answer(s) in {args.memory}")
        print(f"Answer memory now has {len(memory.get('answers', []))} entry/entries")
        return 0

    if args.command == "close":
        record = record_closed_job(
            args.closed_jobs,
            {
                "apply_url": args.url,
                "company": args.company,
                "title": args.title,
                "platform": args.platform,
                "job_id": args.job_id,
            },
            reason=args.reason,
            source=args.source,
        )
        print(
            f"Recorded closed job {record.get('key')} in {args.closed_jobs}: "
            f"{record.get('company') or ''} {record.get('title') or ''}".strip()
        )
        return 0

    if args.command == "research":
        if args.json_output or args.markdown_output:
            research = write_application_research_report(
                args.outbox_dir,
                args.json_output,
                args.markdown_output,
                position_target=args.position_target,
                max_items=args.max_items,
            )
            print(f"Wrote application research JSON to {args.json_output}")
            print(f"Wrote application research Markdown to {args.markdown_output}")
        else:
            research = build_application_research(
                args.outbox_dir,
                position_target=args.position_target,
                max_items=args.max_items,
            )
        print(f"Observed {research['positions_observed_total']} unique position(s)")
        for platform, payload in research.get("platforms", {}).items():
            print(
                f"{platform}: {payload['positions_observed']} observed, "
                f"{payload['positions_remaining_to_target']} remaining to target"
            )
        return 0

    if args.command == "gaps":
        research_path = Path(args.research_json)
        if research_path.exists():
            research = json.loads(research_path.read_text(encoding="utf-8"))
        else:
            research = build_application_research(args.outbox_dir)
        profile = load_profile(args.profile) if args.profile and Path(args.profile).exists() else None
        answer_memory = load_answer_memory(args.memory) if args.memory else None
        if args.json_output or args.markdown_output:
            report = write_answer_gap_report(
                research,
                args.json_output,
                args.markdown_output,
                profile=profile,
                answer_memory=answer_memory,
            )
            print(f"Wrote answer gap JSON to {args.json_output}")
            print(f"Wrote answer gap Markdown to {args.markdown_output}")
        else:
            report = build_answer_gap_report(
                research,
                profile=profile,
                answer_memory=answer_memory,
            )
        print(
            f"Observed {report['unique_prompts_observed']} unique prompt(s); "
            f"{report['blocking_prompt_count']} blocking prompt(s)"
        )
        for status, count in report.get("coverage_counts", {}).items():
            print(f"{status}: {count}")
        return 0

    if args.command == "readiness":
        research_path = Path(args.research_json)
        if research_path.exists():
            research = json.loads(research_path.read_text(encoding="utf-8"))
        else:
            research = build_application_research(args.outbox_dir)
        gaps_path = Path(args.gaps_json)
        if gaps_path.exists():
            gaps = json.loads(gaps_path.read_text(encoding="utf-8"))
        else:
            profile = load_profile(args.profile) if args.profile and Path(args.profile).exists() else None
            answer_memory = load_answer_memory(args.memory) if args.memory else None
            gaps = build_answer_gap_report(
                research,
                profile=profile,
                answer_memory=answer_memory,
            )
        closed_jobs = load_closed_jobs(args.closed_jobs)
        if args.json_output or args.markdown_output:
            report = write_position_readiness_report(
                research,
                gaps,
                args.json_output,
                args.markdown_output,
                closed_jobs=closed_jobs,
            )
            print(f"Wrote readiness JSON to {args.json_output}")
            print(f"Wrote readiness Markdown to {args.markdown_output}")
        else:
            report = build_position_readiness_report(
                research,
                gaps,
                closed_jobs=closed_jobs,
            )
        print(f"Observed {report['positions_observed_total']} position(s)")
        for readiness, count in report.get("readiness_counts", {}).items():
            print(f"{readiness}: {count}")
        print(f"Learning queue items: {report.get('learning_queue_count', 0)}")
        print(f"Minimal learning tasks: {report.get('minimal_learning_task_count', 0)}")
        print(f"Manual gate types: {report.get('manual_gate_count', 0)}")
        return 0

    if args.command == "fill-plan":
        profile = load_profile(args.profile) if args.profile and Path(args.profile).exists() else None
        answer_memory = load_answer_memory(args.memory) if args.memory else None
        plan = write_form_fill_plan(
            args.snapshot,
            args.json_output,
            args.markdown_output,
            profile=profile,
            answer_memory=answer_memory,
            include_values=args.include_values,
        )
        print(f"Wrote form fill plan JSON to {args.json_output}")
        print(f"Wrote form fill plan Markdown to {args.markdown_output}")
        print(
            f"Planned {plan['step_count']} step(s); "
            f"{plan['blocking_step_count']} blocking step(s)"
        )
        for status, count in plan.get("status_counts", {}).items():
            print(f"{status}: {count}")
        return 0

    if args.command == "apply-audit":
        page_text = args.page_text
        if args.page_text_file:
            page_text = Path(args.page_text_file).read_text(encoding="utf-8")
        closed_jobs = load_closed_jobs(args.closed_jobs)
        audit = write_apply_run_audit(
            args.plan,
            args.json_output,
            args.markdown_output,
            page_text=page_text,
            closed_jobs=closed_jobs,
        )
        print(f"Wrote apply run audit JSON to {args.json_output}")
        print(f"Wrote apply run audit Markdown to {args.markdown_output}")
        print(f"Status: {audit.get('status')}")
        print(f"Autofill allowed: {str(bool(audit.get('autofill_allowed'))).lower()}")
        print(f"Would submit: {str(bool(audit.get('would_submit'))).lower()}")
        return 0

    if args.command == "learning-template":
        readiness_path = Path(args.readiness_json)
        if not readiness_path.exists():
            raise FileNotFoundError(f"readiness report not found: {args.readiness_json}")
        readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
        template = write_learning_task_template(
            readiness,
            args.json_output,
            args.markdown_output,
        )
        print(f"Wrote learning task JSON to {args.json_output}")
        print(f"Wrote learning task Markdown to {args.markdown_output}")
        print(f"Tasks: {template.get('task_count', 0)}")
        return 0

    if args.command == "apply-learning":
        result = apply_learning_task_answers(
            args.tasks,
            args.profile,
            args.memory,
            source=args.source,
            dry_run=args.dry_run,
        )
        print(f"Dry run: {str(bool(result.get('dry_run'))).lower()}")
        print(f"Profile updates: {len(result.get('profile_updates', []))}")
        print(f"Answer memory updates: {len(result.get('answer_memory_updates', []))}")
        print(f"Skipped: {len(result.get('skipped', []))}")
        return 0

    if args.command == "synthetic-run":
        report = write_synthetic_application_simulation(
            args.json_output,
            args.markdown_output,
            count=args.count,
            include_values=args.include_values,
        )
        print(f"Wrote synthetic simulation JSON to {args.json_output}")
        print(f"Wrote synthetic simulation Markdown to {args.markdown_output}")
        print(f"Runs: {report.get('run_count', 0)}")
        for status, count in report.get("status_counts", {}).items():
            print(f"{status}: {count}")
        return 0

    if args.command == "synthetic-exec":
        report = write_synthetic_apply_execution(
            args.json_output,
            args.markdown_output,
            count=args.count,
            include_values=args.include_values,
            per_platform_target=args.per_platform_target,
        )
        print(f"Wrote synthetic apply execution JSON to {args.json_output}")
        print(f"Wrote synthetic apply execution Markdown to {args.markdown_output}")
        print(f"Runs: {report.get('run_count', 0)}")
        if report.get("per_platform_target"):
            print(
                f"Per-platform target: {report.get('per_platform_target')} "
                f"achieved={str(bool(report.get('platform_target_achieved'))).lower()}"
            )
        print(f"Actual submit count: {report.get('actual_submit_count', 0)}")
        for outcome, count in report.get("outcome_counts", {}).items():
            print(f"{outcome}: {count}")
        return 0

    if args.command == "playbook":
        research_path = Path(args.research_json)
        if not research_path.exists():
            raise FileNotFoundError(f"research report not found: {args.research_json}")
        research = json.loads(research_path.read_text(encoding="utf-8"))
        gaps = _load_optional_json(args.gaps_json)
        readiness = _load_optional_json(args.readiness_json)
        synthetic = _load_optional_json(args.synthetic_json)
        playbook = write_application_playbook(
            research,
            gaps,
            readiness,
            synthetic,
            args.json_output,
            args.markdown_output,
        )
        print(f"Wrote application playbook JSON to {args.json_output}")
        print(f"Wrote application playbook Markdown to {args.markdown_output}")
        print(f"Platforms: {playbook.get('platform_count', 0)}")
        return 0

    if args.command == "notify":
        submissions = load_submissions_jsonl(args.submissions, limit=None)
        closed_jobs = load_closed_jobs(args.closed_jobs)
        if args.live_check:
            live_result = refresh_closed_jobs_from_live_pages(
                submissions,
                args.closed_jobs,
                max_checks=args.live_check_limit,
                timeout=args.live_check_timeout,
            )
            closed_jobs = live_result["closed_jobs"]
            closed_count = sum(1 for check in live_result["checks"] if check.get("closed"))
            error_count = sum(1 for check in live_result["checks"] if check.get("error"))
            print(
                f"Live checked {len(live_result['checks'])} page(s); "
                f"recorded {closed_count} closed; errors={error_count}"
            )
        result = notify_telegram_for_submissions(
            submissions,
            env_path=args.telegram_env,
            dry_run=args.telegram_dry_run,
            closed_jobs=closed_jobs,
            max_items=args.limit,
        )
        if result.get("skipped"):
            print(f"Telegram notification skipped: {result.get('reason')}")
        else:
            print(f"Sent Telegram notification to {result.get('chat_count', 0)} chat(s)")
        if args.telegram_dry_run:
            print(result["message"])
        if args.open_browser:
            opened_urls = open_apply_urls_in_browser(
                submissions,
                max_items=args.limit,
                record_path=args.review_log,
                source="notify_open_browser",
                closed_jobs=closed_jobs,
            )
            print(f"Opened {len(opened_urls)} apply URL(s) in browser")
            print(f"Recorded browser review queue in {args.review_log}")
        return 0

    profile = load_profile(args.profile)
    jobs = load_jobs(args.jobs)
    answer_memory = load_answer_memory(args.memory) if args.memory else None
    closed_jobs = load_closed_jobs(args.closed_jobs)

    if args.command == "score":
        for job in jobs:
            draft = build_application_draft(
                profile,
                job,
                answer_memory=answer_memory,
                closed_jobs=closed_jobs,
            )
            print(
                f"{draft.score.score:3d} matched={str(draft.score.matched).lower()} "
                f"{job.get('company')} - {job.get('title')}"
            )
            print(f"    reasons: {', '.join(draft.score.reasons) or 'none'}")
            print(f"    automation: {draft.automation['mode']}")
            if draft.missing_facts:
                print(f"    missing facts: {', '.join(draft.missing_facts)}")
        return 0

    submissions = run_pipeline(
        profile,
        jobs,
        args.outbox,
        limit=args.limit,
        answer_memory=answer_memory,
        allow_unattended_submit=args.allow_unattended_submit,
        closed_jobs=closed_jobs,
    )
    if args.json:
        print(json.dumps(submissions, ensure_ascii=False, indent=2))
        return 0

    if not submissions:
        print("No jobs met the minimum score threshold. No dry-run submissions were written.")
        return 0

    if args.live_check:
        live_result = refresh_closed_jobs_from_live_pages(
            submissions,
            args.closed_jobs,
            max_checks=args.live_check_limit,
            timeout=args.live_check_timeout,
        )
        closed_jobs = live_result["closed_jobs"]
        closed_count = sum(1 for check in live_result["checks"] if check.get("closed"))
        error_count = sum(1 for check in live_result["checks"] if check.get("error"))
        print(
            f"Live checked {len(live_result['checks'])} page(s); "
            f"recorded {closed_count} closed; errors={error_count}"
        )

    if args.notify_telegram:
        result = notify_telegram_for_submissions(
            submissions,
            env_path=args.telegram_env,
            dry_run=args.telegram_dry_run,
            closed_jobs=closed_jobs,
            max_items=args.limit,
        )
        if result.get("skipped"):
            print(f"Telegram notification skipped: {result.get('reason')}")
        else:
            print(f"Sent Telegram notification to {result.get('chat_count', 0)} chat(s)")
        if args.telegram_dry_run:
            print(result["message"])

    if args.open_browser:
        opened_urls = open_apply_urls_in_browser(
            submissions,
            max_items=args.limit,
            record_path=args.review_log,
            source="run_open_browser",
            closed_jobs=closed_jobs,
        )
        print(f"Opened {len(opened_urls)} apply URL(s) in browser")
        print(f"Recorded browser review queue in {args.review_log}")

    print(f"Wrote {len(submissions)} dry-run submission(s) to {args.outbox}")
    for index, submission in enumerate(submissions, start=1):
        print(
            f"{index}. {submission['company']} - {submission['title']} "
            f"score={submission['score']} id={submission['submission_id']}"
        )
    return 0


def _load_optional_json(path_value: str | None) -> dict | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


if __name__ == "__main__":
    raise SystemExit(main())
