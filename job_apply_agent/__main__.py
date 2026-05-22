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
    import_candidate_observations,
    load_candidate_rows,
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
    write_browser_action_manifest,
    write_candidate_observation_report,
    write_candidate_discovery_report,
    write_candidate_topup_selection_report,
    write_browser_dom_harness,
    write_closed_posting_preflight,
    write_collection_plan,
    write_form_fill_plan,
    write_learning_task_template,
    write_pre_submit_review,
    write_question_export,
    write_position_readiness_report,
    write_research_coverage_gate,
    write_synthetic_apply_execution,
    write_synthetic_application_simulation,
    write_synthetic_browser_action_execution,
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
DEFAULT_BROWSER_ACTIONS_JSON = Path(__file__).with_name("outbox") / "browser_action_manifest_latest.json"
DEFAULT_BROWSER_ACTIONS_MARKDOWN = Path(__file__).with_name("outbox") / "browser_action_manifest_latest.md"
DEFAULT_CLOSED_PREFLIGHT_JSON = Path(__file__).with_name("outbox") / "closed_posting_preflight_latest.json"
DEFAULT_CLOSED_PREFLIGHT_MARKDOWN = Path(__file__).with_name("outbox") / "closed_posting_preflight_latest.md"
DEFAULT_DOM_HARNESS_HTML = Path(__file__).with_name("outbox") / "browser_dom_harness_latest.html"
DEFAULT_DOM_HARNESS_SCRIPT = Path(__file__).with_name("outbox") / "browser_dom_runner_latest.js"
DEFAULT_DOM_HARNESS_JSON = Path(__file__).with_name("outbox") / "browser_dom_execution_plan_latest.json"
DEFAULT_DOM_HARNESS_MARKDOWN = Path(__file__).with_name("outbox") / "browser_dom_execution_plan_latest.md"
DEFAULT_PRE_SUBMIT_REVIEW_JSON = Path(__file__).with_name("outbox") / "pre_submit_review_latest.json"
DEFAULT_PRE_SUBMIT_REVIEW_MARKDOWN = Path(__file__).with_name("outbox") / "pre_submit_review_latest.md"
DEFAULT_LEARNING_TASKS_JSON = Path(__file__).with_name("outbox") / "learning_tasks_latest.json"
DEFAULT_LEARNING_TASKS_MARKDOWN = Path(__file__).with_name("outbox") / "learning_tasks_latest.md"
DEFAULT_SYNTHETIC_JSON = Path(__file__).with_name("outbox") / "synthetic_100_run_latest.json"
DEFAULT_SYNTHETIC_MARKDOWN = Path(__file__).with_name("outbox") / "synthetic_100_run_latest.md"
DEFAULT_SYNTHETIC_EXEC_JSON = Path(__file__).with_name("outbox") / "synthetic_apply_execution_latest.json"
DEFAULT_SYNTHETIC_EXEC_MARKDOWN = Path(__file__).with_name("outbox") / "synthetic_apply_execution_latest.md"
DEFAULT_SYNTHETIC_BROWSER_EXEC_JSON = Path(__file__).with_name("outbox") / "synthetic_browser_action_execution_latest.json"
DEFAULT_SYNTHETIC_BROWSER_EXEC_MARKDOWN = Path(__file__).with_name("outbox") / "synthetic_browser_action_execution_latest.md"
DEFAULT_PLAYBOOK_JSON = Path(__file__).with_name("outbox") / "application_playbook_latest.json"
DEFAULT_PLAYBOOK_MARKDOWN = Path(__file__).with_name("outbox") / "application_playbook_latest.md"
DEFAULT_COVERAGE_GATE_JSON = Path(__file__).with_name("outbox") / "research_coverage_gate_latest.json"
DEFAULT_COVERAGE_GATE_MARKDOWN = Path(__file__).with_name("outbox") / "research_coverage_gate_latest.md"
DEFAULT_COLLECTION_PLAN_JSON = Path(__file__).with_name("outbox") / "collection_plan_latest.json"
DEFAULT_COLLECTION_PLAN_MARKDOWN = Path(__file__).with_name("outbox") / "collection_plan_latest.md"
DEFAULT_DISCOVERED_CANDIDATES_JSON = Path(__file__).with_name("outbox") / "discovered_candidates_latest.json"
DEFAULT_DISCOVERED_CANDIDATES_MARKDOWN = Path(__file__).with_name("outbox") / "discovered_candidates_latest.md"
DEFAULT_TOPUP_CANDIDATES_JSON = Path(__file__).with_name("outbox") / "topup_candidates_latest.json"
DEFAULT_TOPUP_CANDIDATES_MARKDOWN = Path(__file__).with_name("outbox") / "topup_candidates_latest.md"
DEFAULT_OBSERVED_CANDIDATES = Path(__file__).with_name("outbox") / "observed_candidates.jsonl"
DEFAULT_CANDIDATE_OBSERVATION_JSON = Path(__file__).with_name("outbox") / "candidate_observation_latest.json"
DEFAULT_CANDIDATE_OBSERVATION_MARKDOWN = Path(__file__).with_name("outbox") / "candidate_observation_latest.md"
DEFAULT_QUESTION_EXPORT_XLSX = Path(__file__).with_name("outbox") / "application_questions_latest.xlsx"
DEFAULT_QUESTION_EXPORT_HTML = Path(__file__).with_name("outbox") / "application_questions_latest.html"
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

    closed_preflight_parser = subparsers.add_parser(
        "closed-preflight",
        help="batch-check candidate apply pages and write an open/closed/uncertain report",
    )
    closed_preflight_parser.add_argument("--submissions", default=str(DEFAULT_OUTBOX))
    closed_preflight_parser.add_argument("--jobs", default=None)
    closed_preflight_parser.add_argument("--limit", type=int, default=-1)
    closed_preflight_parser.add_argument("--closed-jobs", default=str(DEFAULT_CLOSED_JOBS))
    closed_preflight_parser.add_argument("--live-check-limit", type=int, default=25)
    closed_preflight_parser.add_argument("--live-check-timeout", type=float, default=15.0)
    closed_preflight_parser.add_argument("--json-output", default=str(DEFAULT_CLOSED_PREFLIGHT_JSON))
    closed_preflight_parser.add_argument("--markdown-output", default=str(DEFAULT_CLOSED_PREFLIGHT_MARKDOWN))

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

    browser_actions_parser = subparsers.add_parser(
        "browser-actions",
        help="turn a fill plan into a guarded browser action manifest",
    )
    browser_actions_parser.add_argument("--plan", default=str(DEFAULT_FILL_PLAN_JSON))
    browser_actions_parser.add_argument("--page-text", default="")
    browser_actions_parser.add_argument("--page-text-file", default=None)
    browser_actions_parser.add_argument("--closed-jobs", default=str(DEFAULT_CLOSED_JOBS))
    browser_actions_parser.add_argument("--include-values", action="store_true")
    browser_actions_parser.add_argument("--json-output", default=str(DEFAULT_BROWSER_ACTIONS_JSON))
    browser_actions_parser.add_argument("--markdown-output", default=str(DEFAULT_BROWSER_ACTIONS_MARKDOWN))

    dom_harness_parser = subparsers.add_parser(
        "dom-harness",
        help="write a local HTML/JS harness for a browser action manifest and captured snapshot",
    )
    dom_harness_parser.add_argument("--manifest", default=str(DEFAULT_BROWSER_ACTIONS_JSON))
    dom_harness_parser.add_argument("--snapshot", required=True)
    dom_harness_parser.add_argument("--html-output", default=str(DEFAULT_DOM_HARNESS_HTML))
    dom_harness_parser.add_argument("--script-output", default=str(DEFAULT_DOM_HARNESS_SCRIPT))
    dom_harness_parser.add_argument("--json-output", default=str(DEFAULT_DOM_HARNESS_JSON))
    dom_harness_parser.add_argument("--markdown-output", default=str(DEFAULT_DOM_HARNESS_MARKDOWN))

    pre_submit_parser = subparsers.add_parser(
        "pre-submit-review",
        help="aggregate browser manifests and learning gaps into a user confirmation checklist",
    )
    pre_submit_parser.add_argument(
        "--manifest",
        action="append",
        default=None,
        help="browser action manifest JSON; may be passed more than once",
    )
    pre_submit_parser.add_argument(
        "--outbox-dir",
        default=str(Path(__file__).with_name("outbox")),
        help="used to discover *_browser_actions_latest.json when --manifest is omitted",
    )
    pre_submit_parser.add_argument("--readiness-json", default=str(DEFAULT_READINESS_JSON))
    pre_submit_parser.add_argument("--gaps-json", default=str(DEFAULT_GAPS_JSON))
    pre_submit_parser.add_argument("--learning-tasks-json", default=str(DEFAULT_LEARNING_TASKS_JSON))
    pre_submit_parser.add_argument("--synthetic-json", default=str(DEFAULT_SYNTHETIC_EXEC_JSON))
    pre_submit_parser.add_argument("--json-output", default=str(DEFAULT_PRE_SUBMIT_REVIEW_JSON))
    pre_submit_parser.add_argument("--markdown-output", default=str(DEFAULT_PRE_SUBMIT_REVIEW_MARKDOWN))

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
    synthetic_exec_parser.add_argument(
        "--per-platform-role-target",
        type=int,
        default=None,
        help="run this many synthetic applications for each platform and role-title pair",
    )
    synthetic_exec_parser.add_argument("--include-values", action="store_true")
    synthetic_exec_parser.add_argument("--json-output", default=str(DEFAULT_SYNTHETIC_EXEC_JSON))
    synthetic_exec_parser.add_argument("--markdown-output", default=str(DEFAULT_SYNTHETIC_EXEC_MARKDOWN))

    synthetic_browser_exec_parser = subparsers.add_parser(
        "synthetic-browser-exec",
        help="execute synthetic browser action manifests against local fake forms",
    )
    synthetic_browser_exec_parser.add_argument("--count", type=int, default=100)
    synthetic_browser_exec_parser.add_argument(
        "--per-platform-target",
        type=int,
        default=None,
        help="run this many synthetic browser executions for each synthetic platform",
    )
    synthetic_browser_exec_parser.add_argument(
        "--per-platform-role-target",
        type=int,
        default=None,
        help="run this many synthetic browser executions for each platform and role-title pair",
    )
    synthetic_browser_exec_parser.add_argument("--include-values", action="store_true")
    synthetic_browser_exec_parser.add_argument("--json-output", default=str(DEFAULT_SYNTHETIC_BROWSER_EXEC_JSON))
    synthetic_browser_exec_parser.add_argument("--markdown-output", default=str(DEFAULT_SYNTHETIC_BROWSER_EXEC_MARKDOWN))

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

    coverage_gate_parser = subparsers.add_parser(
        "coverage-gate",
        help="compare real observed coverage against synthetic platform/role execution evidence",
    )
    coverage_gate_parser.add_argument("--research-json", default=str(DEFAULT_RESEARCH_JSON))
    coverage_gate_parser.add_argument("--gaps-json", default=str(DEFAULT_GAPS_JSON))
    coverage_gate_parser.add_argument("--synthetic-json", default=str(DEFAULT_SYNTHETIC_BROWSER_EXEC_JSON))
    coverage_gate_parser.add_argument("--position-target", type=int, default=100)
    coverage_gate_parser.add_argument("--json-output", default=str(DEFAULT_COVERAGE_GATE_JSON))
    coverage_gate_parser.add_argument("--markdown-output", default=str(DEFAULT_COVERAGE_GATE_MARKDOWN))

    collection_plan_parser = subparsers.add_parser(
        "collection-plan",
        help="turn coverage shortfalls into platform/role collection tasks",
    )
    collection_plan_parser.add_argument("--coverage-gate-json", default=str(DEFAULT_COVERAGE_GATE_JSON))
    collection_plan_parser.add_argument("--max-targets", type=int, default=20)
    collection_plan_parser.add_argument("--batch-size", type=int, default=25)
    collection_plan_parser.add_argument("--json-output", default=str(DEFAULT_COLLECTION_PLAN_JSON))
    collection_plan_parser.add_argument("--markdown-output", default=str(DEFAULT_COLLECTION_PLAN_MARKDOWN))

    discover_candidates_parser = subparsers.add_parser(
        "discover-candidates",
        help="fetch collection-plan search pages and extract candidate apply URLs",
    )
    discover_candidates_parser.add_argument("--collection-plan-json", default=str(DEFAULT_COLLECTION_PLAN_JSON))
    discover_candidates_parser.add_argument("--max-tasks", type=int, default=4)
    discover_candidates_parser.add_argument("--per-task-limit", type=int, default=10)
    discover_candidates_parser.add_argument("--search-pages-per-task", type=int, default=2)
    discover_candidates_parser.add_argument(
        "--seed-candidates",
        action="append",
        default=[],
        help="existing candidate JSON/JSONL files whose ATS company boards should be expanded",
    )
    discover_candidates_parser.add_argument("--board-fetch-limit", type=int, default=20)
    discover_candidates_parser.add_argument("--max-rate-limit-errors-per-task", type=int, default=2)
    discover_candidates_parser.add_argument("--timeout", type=float, default=15.0)
    discover_candidates_parser.add_argument("--json-output", default=str(DEFAULT_DISCOVERED_CANDIDATES_JSON))
    discover_candidates_parser.add_argument("--markdown-output", default=str(DEFAULT_DISCOVERED_CANDIDATES_MARKDOWN))

    import_candidates_parser = subparsers.add_parser(
        "import-candidates",
        help="append externally collected candidate jobs as normalized observed positions",
    )
    import_candidates_parser.add_argument("--input", required=True)
    import_candidates_parser.add_argument("--output", default=str(DEFAULT_OBSERVED_CANDIDATES))
    import_candidates_parser.add_argument("--source", default="manual_collection")

    observe_candidates_parser = subparsers.add_parser(
        "observe-candidates",
        help="live-check candidate URLs, persist closed pages, and import open observed positions",
    )
    observe_candidates_parser.add_argument("--input", required=True)
    observe_candidates_parser.add_argument("--limit", type=int, default=-1)
    observe_candidates_parser.add_argument("--output", default=str(DEFAULT_OBSERVED_CANDIDATES))
    observe_candidates_parser.add_argument("--closed-jobs", default=str(DEFAULT_CLOSED_JOBS))
    observe_candidates_parser.add_argument("--live-check-limit", type=int, default=25)
    observe_candidates_parser.add_argument("--live-check-timeout", type=float, default=15.0)
    observe_candidates_parser.add_argument("--json-output", default=str(DEFAULT_CANDIDATE_OBSERVATION_JSON))
    observe_candidates_parser.add_argument("--markdown-output", default=str(DEFAULT_CANDIDATE_OBSERVATION_MARKDOWN))
    observe_candidates_parser.add_argument("--source", default="live_candidate_observation")
    observe_candidates_parser.add_argument(
        "--refresh-existing",
        action="store_true",
        help="append a fresh observation even when this job was already recorded",
    )

    select_topup_parser = subparsers.add_parser(
        "select-topup-candidates",
        help="select unobserved candidates that best reduce current platform-role coverage gaps",
    )
    select_topup_parser.add_argument("--candidates", required=True)
    select_topup_parser.add_argument("--coverage-gate-json", default=str(DEFAULT_COVERAGE_GATE_JSON))
    select_topup_parser.add_argument("--observed-candidates", default=str(DEFAULT_OBSERVED_CANDIDATES))
    select_topup_parser.add_argument("--closed-jobs", default=str(DEFAULT_CLOSED_JOBS))
    select_topup_parser.add_argument("--limit", type=int, default=100)
    select_topup_parser.add_argument("--per-pair-limit", type=int, default=35)
    select_topup_parser.add_argument("--json-output", default=str(DEFAULT_TOPUP_CANDIDATES_JSON))
    select_topup_parser.add_argument("--markdown-output", default=str(DEFAULT_TOPUP_CANDIDATES_MARKDOWN))

    export_questions_parser = subparsers.add_parser(
        "export-questions",
        help="write an Excel question workbook and HTML dashboard from latest research reports",
    )
    export_questions_parser.add_argument("--gaps-json", default=str(DEFAULT_GAPS_JSON))
    export_questions_parser.add_argument("--readiness-json", default=str(DEFAULT_READINESS_JSON))
    export_questions_parser.add_argument("--coverage-gate-json", default=str(DEFAULT_COVERAGE_GATE_JSON))
    export_questions_parser.add_argument("--collection-plan-json", default=str(DEFAULT_COLLECTION_PLAN_JSON))
    export_questions_parser.add_argument("--learning-tasks-json", default=str(DEFAULT_LEARNING_TASKS_JSON))
    export_questions_parser.add_argument("--xlsx-output", default=str(DEFAULT_QUESTION_EXPORT_XLSX))
    export_questions_parser.add_argument("--html-output", default=str(DEFAULT_QUESTION_EXPORT_HTML))

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

    if args.command == "closed-preflight":
        if args.jobs:
            candidates = load_jobs(args.jobs)
            if args.limit is not None and args.limit >= 0:
                candidates = candidates[: args.limit]
        else:
            candidates = load_submissions_jsonl(args.submissions, limit=args.limit)
        report = write_closed_posting_preflight(
            candidates,
            args.closed_jobs,
            args.json_output,
            args.markdown_output,
            max_checks=args.live_check_limit,
            timeout=args.live_check_timeout,
        )
        print(f"Wrote closed-posting preflight JSON to {args.json_output}")
        print(f"Wrote closed-posting preflight Markdown to {args.markdown_output}")
        print(f"Candidates: {report.get('candidate_count', 0)}")
        print(f"Live checked: {report.get('live_checked_count', 0)}")
        print(f"Closed: {report.get('closed_count', 0)}")
        print(f"Open eligible: {report.get('open_eligible_count', 0)}")
        print(f"Uncertain: {report.get('uncertain_count', 0)}")
        return 0

    if args.command == "observe-candidates":
        candidates = load_candidate_rows(args.input)
        if args.limit is not None and args.limit >= 0:
            candidates = candidates[: args.limit]
        report = write_candidate_observation_report(
            candidates,
            args.output,
            args.closed_jobs,
            args.json_output,
            args.markdown_output,
            max_checks=args.live_check_limit,
            timeout=args.live_check_timeout,
            source=args.source,
            refresh_existing=args.refresh_existing,
        )
        print(f"Wrote candidate observation JSON to {args.json_output}")
        print(f"Wrote candidate observation Markdown to {args.markdown_output}")
        print(f"Candidates: {report.get('candidate_count', 0)}")
        print(f"Live checked: {report.get('live_checked_count', 0)}")
        print(f"Observed open: {report.get('observed_count', 0)}")
        print(f"Closed: {report.get('closed_count', 0)}")
        print(f"Uncertain: {report.get('uncertain_count', 0)}")
        return 0

    if args.command == "select-topup-candidates":
        candidates = load_candidate_rows(args.candidates)
        coverage_gate = json.loads(Path(args.coverage_gate_json).read_text(encoding="utf-8"))
        observed_candidates = (
            load_candidate_rows(args.observed_candidates)
            if Path(args.observed_candidates).exists()
            else []
        )
        closed_jobs = load_closed_jobs(args.closed_jobs) if Path(args.closed_jobs).exists() else None
        report = write_candidate_topup_selection_report(
            candidates,
            coverage_gate,
            observed_candidates,
            closed_jobs,
            args.json_output,
            args.markdown_output,
            limit=args.limit,
            per_pair_limit=args.per_pair_limit,
        )
        print(f"Wrote top-up candidate JSON to {args.json_output}")
        print(f"Wrote top-up candidate Markdown to {args.markdown_output}")
        print(f"Candidates considered: {report.get('candidate_count', 0)}")
        print(f"Selected: {report.get('selected_count', 0)}")
        for pair, count in sorted((report.get("per_pair_counts") or {}).items()):
            print(f"{pair}: {count}")
        return 0

    if args.command == "export-questions":
        gaps = json.loads(Path(args.gaps_json).read_text(encoding="utf-8"))
        readiness = json.loads(Path(args.readiness_json).read_text(encoding="utf-8"))
        coverage_gate = json.loads(Path(args.coverage_gate_json).read_text(encoding="utf-8"))
        collection_plan = json.loads(Path(args.collection_plan_json).read_text(encoding="utf-8"))
        learning_tasks = json.loads(Path(args.learning_tasks_json).read_text(encoding="utf-8"))
        export = write_question_export(
            gaps,
            readiness,
            coverage_gate,
            collection_plan,
            learning_tasks,
            args.xlsx_output,
            args.html_output,
        )
        print(f"Wrote question Excel to {args.xlsx_output}")
        print(f"Wrote question HTML to {args.html_output}")
        print(f"Questions: {len(export.get('question_rows', []))}")
        print(f"Blocking prompts: {len(export.get('blocker_rows', []))}")
        print(f"Learning tasks: {len(export.get('user_questions', []))}")
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

    if args.command == "browser-actions":
        page_text = args.page_text
        if args.page_text_file:
            page_text = Path(args.page_text_file).read_text(encoding="utf-8")
        closed_jobs = load_closed_jobs(args.closed_jobs)
        manifest = write_browser_action_manifest(
            args.plan,
            args.json_output,
            args.markdown_output,
            page_text=page_text,
            closed_jobs=closed_jobs,
            include_values=args.include_values,
        )
        print(f"Wrote browser action manifest JSON to {args.json_output}")
        print(f"Wrote browser action manifest Markdown to {args.markdown_output}")
        print(f"Status: {manifest.get('status')}")
        print(f"Browser actions: {manifest.get('action_count', 0)}")
        print(f"Stop actions: {manifest.get('stop_action_count', 0)}")
        print(f"Would submit: {str(bool(manifest.get('would_submit'))).lower()}")
        return 0

    if args.command == "dom-harness":
        plan = write_browser_dom_harness(
            args.manifest,
            args.snapshot,
            args.html_output,
            args.script_output,
            args.json_output,
            args.markdown_output,
        )
        print(f"Wrote browser DOM harness HTML to {args.html_output}")
        print(f"Wrote browser DOM runner script to {args.script_output}")
        print(f"Wrote browser DOM execution JSON to {args.json_output}")
        print(f"Wrote browser DOM execution Markdown to {args.markdown_output}")
        print(f"Execution allowed: {str(bool(plan.get('execution_allowed'))).lower()}")
        print(f"Safety status: {plan.get('safety_status')}")
        print(f"Browser actions: {plan.get('browser_action_count', 0)}")
        print(f"Would submit: {str(bool(plan.get('would_submit'))).lower()}")
        return 0

    if args.command == "pre-submit-review":
        manifest_paths = (
            [Path(value) for value in args.manifest]
            if args.manifest
            else _discover_browser_action_manifests(args.outbox_dir)
        )
        if not manifest_paths:
            raise FileNotFoundError("no browser action manifests found; pass --manifest or run browser-actions first")
        review = write_pre_submit_review(
            manifest_paths,
            args.json_output,
            args.markdown_output,
            readiness=_load_optional_json(args.readiness_json),
            gaps=_load_optional_json(args.gaps_json),
            learning_tasks=_load_optional_json(args.learning_tasks_json),
            synthetic=_load_optional_json(args.synthetic_json),
        )
        print(f"Wrote pre-submit review JSON to {args.json_output}")
        print(f"Wrote pre-submit review Markdown to {args.markdown_output}")
        print(f"Manifests: {review.get('manifest_count', 0)}")
        print(f"Browser actions: {review.get('total_action_count', 0)}")
        print(f"Confirmation items: {review.get('confirmation_item_count', 0)}")
        print(f"Actual submit count: {review.get('actual_submit_count', 0)}")
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
            per_platform_role_target=args.per_platform_role_target,
        )
        print(f"Wrote synthetic apply execution JSON to {args.json_output}")
        print(f"Wrote synthetic apply execution Markdown to {args.markdown_output}")
        print(f"Runs: {report.get('run_count', 0)}")
        if report.get("per_platform_target"):
            print(
                f"Per-platform target: {report.get('per_platform_target')} "
                f"achieved={str(bool(report.get('platform_target_achieved'))).lower()}"
            )
        if report.get("per_platform_role_target"):
            print(
                f"Per-platform-role target: {report.get('per_platform_role_target')} "
                f"achieved={str(bool(report.get('platform_role_target_achieved'))).lower()}"
            )
        print(f"Actual submit count: {report.get('actual_submit_count', 0)}")
        for outcome, count in report.get("outcome_counts", {}).items():
            print(f"{outcome}: {count}")
        return 0

    if args.command == "synthetic-browser-exec":
        report = write_synthetic_browser_action_execution(
            args.json_output,
            args.markdown_output,
            count=args.count,
            include_values=args.include_values,
            per_platform_target=args.per_platform_target,
            per_platform_role_target=args.per_platform_role_target,
        )
        print(f"Wrote synthetic browser action execution JSON to {args.json_output}")
        print(f"Wrote synthetic browser action execution Markdown to {args.markdown_output}")
        print(f"Runs: {report.get('run_count', 0)}")
        if report.get("per_platform_target"):
            print(
                f"Per-platform target: {report.get('per_platform_target')} "
                f"achieved={str(bool(report.get('platform_target_achieved'))).lower()}"
            )
        if report.get("per_platform_role_target"):
            print(
                f"Per-platform-role target: {report.get('per_platform_role_target')} "
                f"achieved={str(bool(report.get('platform_role_target_achieved'))).lower()}"
            )
        print(f"Actual submit count: {report.get('actual_submit_count', 0)}")
        print(f"Selector misses: {report.get('selector_miss_count', 0)}")
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

    if args.command == "coverage-gate":
        research_path = Path(args.research_json)
        if not research_path.exists():
            raise FileNotFoundError(f"research report not found: {args.research_json}")
        research = json.loads(research_path.read_text(encoding="utf-8"))
        gate = write_research_coverage_gate(
            research,
            _load_optional_json(args.synthetic_json),
            _load_optional_json(args.gaps_json),
            args.json_output,
            args.markdown_output,
            position_target=args.position_target,
        )
        print(f"Wrote research coverage gate JSON to {args.json_output}")
        print(f"Wrote research coverage gate Markdown to {args.markdown_output}")
        print(
            "Real platform-role target achieved: "
            f"{str(bool(gate.get('real_platform_role_target_achieved'))).lower()}"
        )
        print(
            "Synthetic platform-role target achieved: "
            f"{str(bool((gate.get('synthetic') or {}).get('platform_role_target_achieved'))).lower()}"
        )
        print(f"Next collection targets: {len(gate.get('next_collection_targets', []))}")
        return 0

    if args.command == "collection-plan":
        gate_path = Path(args.coverage_gate_json)
        if not gate_path.exists():
            raise FileNotFoundError(f"coverage gate not found: {args.coverage_gate_json}")
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
        plan = write_collection_plan(
            gate,
            args.json_output,
            args.markdown_output,
            max_targets=args.max_targets,
            batch_size=args.batch_size,
        )
        print(f"Wrote collection plan JSON to {args.json_output}")
        print(f"Wrote collection plan Markdown to {args.markdown_output}")
        print(f"Tasks: {plan.get('task_count', 0)}")
        return 0

    if args.command == "discover-candidates":
        collection_plan_path = Path(args.collection_plan_json)
        if not collection_plan_path.exists():
            raise FileNotFoundError(f"collection plan not found: {args.collection_plan_json}")
        collection_plan = json.loads(collection_plan_path.read_text(encoding="utf-8"))
        seed_candidates = []
        for seed_path in args.seed_candidates:
            seed_candidates.extend(load_candidate_rows(seed_path))
        report = write_candidate_discovery_report(
            collection_plan,
            args.json_output,
            args.markdown_output,
            max_tasks=args.max_tasks,
            per_task_limit=args.per_task_limit,
            search_pages_per_task=args.search_pages_per_task,
            timeout=args.timeout,
            seed_candidates=seed_candidates,
            board_fetch_limit=args.board_fetch_limit,
            max_rate_limit_errors_per_task=args.max_rate_limit_errors_per_task,
        )
        print(f"Wrote discovered candidates JSON to {args.json_output}")
        print(f"Wrote discovered candidates Markdown to {args.markdown_output}")
        print(f"Tasks searched: {report.get('task_count', 0)}")
        print(f"Search pages fetched: {report.get('search_page_count', 0)}")
        print(f"Rate-limited tasks: {report.get('rate_limited_task_count', 0)}")
        print(f"Seed candidates: {report.get('seed_candidate_count', 0)}")
        print(f"Direct seed candidates: {report.get('direct_seed_candidate_count', 0)}")
        print(f"ATS boards fetched: {report.get('board_fetch_count', 0)}")
        print(f"Board candidates: {report.get('board_candidate_count', 0)}")
        print(f"Candidates: {report.get('candidate_count', 0)}")
        print(f"Errors: {report.get('error_count', 0)}")
        return 0

    if args.command == "import-candidates":
        result = import_candidate_observations(
            args.input,
            args.output,
            source=args.source,
        )
        print(f"Imported candidates to {args.output}")
        print(f"Input candidates: {result.get('candidate_count', 0)}")
        print(f"Imported: {result.get('imported_count', 0)}")
        print(f"Skipped: {result.get('skipped_count', 0)}")
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


def _discover_browser_action_manifests(outbox_dir: str | Path) -> list[Path]:
    outbox = Path(outbox_dir)
    paths: list[Path] = []
    if outbox.exists():
        paths.extend(sorted(outbox.glob("*_browser_actions_latest.json")))
    if DEFAULT_BROWSER_ACTIONS_JSON.exists():
        paths.append(DEFAULT_BROWSER_ACTIONS_JSON)
    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(path)
    return deduped


if __name__ == "__main__":
    raise SystemExit(main())
