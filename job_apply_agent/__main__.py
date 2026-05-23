from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .core import (
    apply_critical_input_answers,
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
    render_critical_input_answer_workflow_markdown,
    refresh_closed_jobs_from_live_pages,
    run_pipeline,
    write_answer_gap_report,
    write_apply_run_audit,
    write_application_playbook,
    write_application_research_report,
    write_automation_handoff_report,
    write_autofill_batch_plan,
    write_browser_action_manifest,
    write_candidate_observation_report,
    write_candidate_discovery_report,
    write_candidate_topup_selection_report,
    write_browser_dom_harness,
    write_closed_posting_preflight,
    write_collection_plan,
    write_critical_input_answer_workflow,
    write_critical_input_answer_update,
    write_critical_input_impact_report,
    write_critical_input_preflight,
    write_critical_input_questionnaire,
    write_form_fill_plan,
    write_fake_learning_probe,
    write_fake_critical_input_probe,
    write_fake_position_rehearsal,
    write_goal_readiness_audit,
    write_critical_input_suggestion_packet,
    write_learning_approval_pack,
    write_learning_task_template,
    write_critical_input_answer_template,
    write_critical_input_status_report,
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
DEFAULT_AUTOFILL_BATCH_JSON = Path(__file__).with_name("outbox") / "autofill_batch_latest.json"
DEFAULT_AUTOFILL_BATCH_MARKDOWN = Path(__file__).with_name("outbox") / "autofill_batch_latest.md"
DEFAULT_AUTOFILL_BATCH_HTML = Path(__file__).with_name("outbox") / "autofill_batch_latest.html"
DEFAULT_AUTOMATION_HANDOFF_JSON = Path(__file__).with_name("outbox") / "automation_handoff_latest.json"
DEFAULT_AUTOMATION_HANDOFF_MARKDOWN = Path(__file__).with_name("outbox") / "automation_handoff_latest.md"
DEFAULT_AUTOMATION_HANDOFF_HTML = Path(__file__).with_name("outbox") / "automation_handoff_latest.html"
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
DEFAULT_LEARNING_APPROVAL_PACK_JSON = Path(__file__).with_name("outbox") / "learning_approval_pack_latest.json"
DEFAULT_LEARNING_APPROVAL_PACK_MARKDOWN = Path(__file__).with_name("outbox") / "learning_approval_pack_latest.md"
DEFAULT_CRITICAL_INPUT_ANSWERS_JSON = Path(__file__).with_name("outbox") / "critical_input_answers_latest.json"
DEFAULT_CRITICAL_INPUT_ANSWERS_MARKDOWN = Path(__file__).with_name("outbox") / "critical_input_answers_latest.md"
DEFAULT_CRITICAL_INPUT_STATUS_JSON = Path(__file__).with_name("outbox") / "critical_input_status_latest.json"
DEFAULT_CRITICAL_INPUT_STATUS_MARKDOWN = Path(__file__).with_name("outbox") / "critical_input_status_latest.md"
DEFAULT_CRITICAL_INPUT_SUGGESTIONS_JSON = Path(__file__).with_name("outbox") / "critical_input_suggestions_latest.json"
DEFAULT_CRITICAL_INPUT_SUGGESTIONS_MARKDOWN = Path(__file__).with_name("outbox") / "critical_input_suggestions_latest.md"
DEFAULT_CRITICAL_INPUT_UPDATE_JSON = Path(__file__).with_name("outbox") / "critical_input_update_latest.json"
DEFAULT_CRITICAL_INPUT_UPDATE_MARKDOWN = Path(__file__).with_name("outbox") / "critical_input_update_latest.md"
DEFAULT_CRITICAL_INPUT_WORKFLOW_JSON = Path(__file__).with_name("outbox") / "critical_input_workflow_latest.json"
DEFAULT_CRITICAL_INPUT_WORKFLOW_MARKDOWN = Path(__file__).with_name("outbox") / "critical_input_workflow_latest.md"
DEFAULT_CRITICAL_INPUT_PREFLIGHT_JSON = Path(__file__).with_name("outbox") / "critical_input_preflight_latest.json"
DEFAULT_CRITICAL_INPUT_PREFLIGHT_MARKDOWN = Path(__file__).with_name("outbox") / "critical_input_preflight_latest.md"
DEFAULT_CRITICAL_INPUT_PREFLIGHT_HTML = Path(__file__).with_name("outbox") / "critical_input_preflight_latest.html"
DEFAULT_CRITICAL_INPUT_IMPACT_JSON = Path(__file__).with_name("outbox") / "critical_input_impact_latest.json"
DEFAULT_CRITICAL_INPUT_IMPACT_MARKDOWN = Path(__file__).with_name("outbox") / "critical_input_impact_latest.md"
DEFAULT_CRITICAL_INPUT_IMPACT_HTML = Path(__file__).with_name("outbox") / "critical_input_impact_latest.html"
DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_JSON = Path(__file__).with_name("outbox") / "critical_input_questionnaire_latest.json"
DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_MARKDOWN = Path(__file__).with_name("outbox") / "critical_input_questionnaire_latest.md"
DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_HTML = Path(__file__).with_name("outbox") / "critical_input_questionnaire_latest.html"
DEFAULT_FAKE_CRITICAL_INPUT_PROBE_JSON = Path(__file__).with_name("outbox") / "fake_critical_input_probe_latest.json"
DEFAULT_FAKE_CRITICAL_INPUT_PROBE_MARKDOWN = Path(__file__).with_name("outbox") / "fake_critical_input_probe_latest.md"
DEFAULT_FAKE_CRITICAL_INPUT_ANSWERS_JSON = Path(__file__).with_name("outbox") / "fake_critical_input_answers_latest.json"
DEFAULT_FAKE_CRITICAL_INPUT_ANSWERS_MARKDOWN = Path(__file__).with_name("outbox") / "fake_critical_input_answers_latest.md"
DEFAULT_FAKE_LEARNING_PROBE_JSON = Path(__file__).with_name("outbox") / "fake_learning_probe_latest.json"
DEFAULT_FAKE_LEARNING_PROBE_MARKDOWN = Path(__file__).with_name("outbox") / "fake_learning_probe_latest.md"
DEFAULT_FAKE_POSITION_REHEARSAL_JSON = Path(__file__).with_name("outbox") / "fake_position_rehearsal_latest.json"
DEFAULT_FAKE_POSITION_REHEARSAL_MARKDOWN = Path(__file__).with_name("outbox") / "fake_position_rehearsal_latest.md"
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
DEFAULT_GOAL_AUDIT_JSON = Path(__file__).with_name("outbox") / "goal_readiness_audit_latest.json"
DEFAULT_GOAL_AUDIT_MARKDOWN = Path(__file__).with_name("outbox") / "goal_readiness_audit_latest.md"
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

    autofill_batch_parser = subparsers.add_parser(
        "autofill-batch",
        help="select a 100-position autofill queue and verify local browser action manifests",
    )
    autofill_batch_parser.add_argument("--research-json", default=str(DEFAULT_RESEARCH_JSON))
    autofill_batch_parser.add_argument("--readiness-json", default=str(DEFAULT_READINESS_JSON))
    autofill_batch_parser.add_argument(
        "--profile",
        default=str(DEFAULT_PERSONAL_PROFILE if DEFAULT_PERSONAL_PROFILE.exists() else DEFAULT_PROFILE),
    )
    autofill_batch_parser.add_argument("--memory", default=str(DEFAULT_MEMORY))
    autofill_batch_parser.add_argument("--closed-jobs", default=str(DEFAULT_CLOSED_JOBS))
    autofill_batch_parser.add_argument("--limit", type=int, default=100)
    autofill_batch_parser.add_argument("--include-values", action="store_true")
    autofill_batch_parser.add_argument("--json-output", default=str(DEFAULT_AUTOFILL_BATCH_JSON))
    autofill_batch_parser.add_argument("--markdown-output", default=str(DEFAULT_AUTOFILL_BATCH_MARKDOWN))
    autofill_batch_parser.add_argument("--html-output", default=str(DEFAULT_AUTOFILL_BATCH_HTML))

    automation_handoff_parser = subparsers.add_parser(
        "automation-handoff",
        help="write a handoff dashboard for confirmed answers, stop actions, and supervised gates",
    )
    automation_handoff_parser.add_argument("--goal-audit-json", default=str(DEFAULT_GOAL_AUDIT_JSON))
    automation_handoff_parser.add_argument(
        "--critical-input-questionnaire-json",
        default=str(DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_JSON),
    )
    automation_handoff_parser.add_argument(
        "--critical-input-impact-json",
        default=str(DEFAULT_CRITICAL_INPUT_IMPACT_JSON),
    )
    automation_handoff_parser.add_argument("--autofill-batch-json", default=str(DEFAULT_AUTOFILL_BATCH_JSON))
    automation_handoff_parser.add_argument("--answer-memory-json", default=str(DEFAULT_MEMORY))
    automation_handoff_parser.add_argument("--closed-jobs-json", default=str(DEFAULT_CLOSED_JOBS))
    automation_handoff_parser.add_argument("--json-output", default=str(DEFAULT_AUTOMATION_HANDOFF_JSON))
    automation_handoff_parser.add_argument("--markdown-output", default=str(DEFAULT_AUTOMATION_HANDOFF_MARKDOWN))
    automation_handoff_parser.add_argument("--html-output", default=str(DEFAULT_AUTOMATION_HANDOFF_HTML))

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
    learning_template_parser.add_argument("--profile", default=str(DEFAULT_PERSONAL_PROFILE))
    learning_template_parser.add_argument("--memory", default=str(DEFAULT_MEMORY))
    learning_template_parser.add_argument("--json-output", default=str(DEFAULT_LEARNING_TASKS_JSON))
    learning_template_parser.add_argument("--markdown-output", default=str(DEFAULT_LEARNING_TASKS_MARKDOWN))

    learning_approval_pack_parser = subparsers.add_parser(
        "learning-approval-pack",
        help="group remaining learning tasks into approval buckets for full automation readiness",
    )
    learning_approval_pack_parser.add_argument("--learning-tasks-json", default=str(DEFAULT_LEARNING_TASKS_JSON))
    learning_approval_pack_parser.add_argument("--readiness-json", default=str(DEFAULT_READINESS_JSON))
    learning_approval_pack_parser.add_argument("--json-output", default=str(DEFAULT_LEARNING_APPROVAL_PACK_JSON))
    learning_approval_pack_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_LEARNING_APPROVAL_PACK_MARKDOWN),
    )

    critical_inputs_template_parser = subparsers.add_parser(
        "critical-inputs-template",
        help="write a small fill-in answer template for critical application inputs",
    )
    critical_inputs_template_parser.add_argument("--approval-pack", default=str(DEFAULT_LEARNING_APPROVAL_PACK_JSON))
    critical_inputs_template_parser.add_argument("--json-output", default=str(DEFAULT_CRITICAL_INPUT_ANSWERS_JSON))
    critical_inputs_template_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_CRITICAL_INPUT_ANSWERS_MARKDOWN),
    )

    critical_inputs_status_parser = subparsers.add_parser(
        "critical-inputs-status",
        help="summarize which critical inputs are ready, waiting, or supervised-only",
    )
    critical_inputs_status_parser.add_argument("--approval-pack", default=str(DEFAULT_LEARNING_APPROVAL_PACK_JSON))
    critical_inputs_status_parser.add_argument("--answers", default=str(DEFAULT_CRITICAL_INPUT_ANSWERS_JSON))
    critical_inputs_status_parser.add_argument("--json-output", default=str(DEFAULT_CRITICAL_INPUT_STATUS_JSON))
    critical_inputs_status_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_CRITICAL_INPUT_STATUS_MARKDOWN),
    )

    critical_inputs_suggestions_parser = subparsers.add_parser(
        "critical-input-suggestions",
        help="draft a review packet with suggested answers and exact-confirmation notes",
    )
    critical_inputs_suggestions_parser.add_argument("--answers", default=str(DEFAULT_CRITICAL_INPUT_ANSWERS_JSON))
    critical_inputs_suggestions_parser.add_argument("--profile", default=str(DEFAULT_PERSONAL_PROFILE))
    critical_inputs_suggestions_parser.add_argument("--memory", default=str(DEFAULT_MEMORY))
    critical_inputs_suggestions_parser.add_argument("--json-output", default=str(DEFAULT_CRITICAL_INPUT_SUGGESTIONS_JSON))
    critical_inputs_suggestions_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_CRITICAL_INPUT_SUGGESTIONS_MARKDOWN),
    )

    critical_inputs_questionnaire_parser = subparsers.add_parser(
        "critical-inputs-questionnaire",
        help="write a compact confirmed-answer questionnaire for the remaining critical inputs",
    )
    critical_inputs_questionnaire_parser.add_argument("--answers", default=str(DEFAULT_CRITICAL_INPUT_ANSWERS_JSON))
    critical_inputs_questionnaire_parser.add_argument(
        "--suggestions",
        default=str(DEFAULT_CRITICAL_INPUT_SUGGESTIONS_JSON),
    )
    critical_inputs_questionnaire_parser.add_argument(
        "--impact",
        default=str(DEFAULT_CRITICAL_INPUT_IMPACT_JSON),
    )
    critical_inputs_questionnaire_parser.add_argument("--json-output", default=str(DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_JSON))
    critical_inputs_questionnaire_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_MARKDOWN),
    )
    critical_inputs_questionnaire_parser.add_argument("--html-output", default=str(DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_HTML))

    critical_inputs_update_parser = subparsers.add_parser(
        "critical-inputs-update",
        help="merge a compact JSON answer map into the critical input answer file",
    )
    critical_inputs_update_parser.add_argument("--answers", default=str(DEFAULT_CRITICAL_INPUT_ANSWERS_JSON))
    critical_inputs_update_parser.add_argument(
        "--answers-markdown-output",
        default=str(DEFAULT_CRITICAL_INPUT_ANSWERS_MARKDOWN),
    )
    critical_inputs_update_parser.add_argument("--updates", required=True)
    critical_inputs_update_parser.add_argument("--json-output", default=str(DEFAULT_CRITICAL_INPUT_UPDATE_JSON))
    critical_inputs_update_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_CRITICAL_INPUT_UPDATE_MARKDOWN),
    )
    critical_inputs_update_parser.add_argument(
        "--approve",
        action="store_true",
        help="approve non-high-risk rows while merging supplied answers",
    )
    critical_inputs_update_parser.add_argument(
        "--approve-high-risk",
        action="store_true",
        help="also approve high-risk rows supplied in this update",
    )

    critical_inputs_preflight_parser = subparsers.add_parser(
        "critical-inputs-preflight",
        help="simulate compact critical answers in a temp workspace and report automation impact",
    )
    critical_inputs_preflight_parser.add_argument("--approval-pack", default=str(DEFAULT_LEARNING_APPROVAL_PACK_JSON))
    critical_inputs_preflight_parser.add_argument("--answers", default=str(DEFAULT_CRITICAL_INPUT_ANSWERS_JSON))
    critical_inputs_preflight_parser.add_argument("--updates", required=True)
    critical_inputs_preflight_parser.add_argument("--research-json", default=str(DEFAULT_RESEARCH_JSON))
    critical_inputs_preflight_parser.add_argument(
        "--profile",
        default=str(DEFAULT_PERSONAL_PROFILE if DEFAULT_PERSONAL_PROFILE.exists() else DEFAULT_PROFILE),
    )
    critical_inputs_preflight_parser.add_argument("--memory", default=str(DEFAULT_MEMORY))
    critical_inputs_preflight_parser.add_argument("--closed-jobs", default=str(DEFAULT_CLOSED_JOBS))
    critical_inputs_preflight_parser.add_argument("--source", default="critical_input_preflight")
    critical_inputs_preflight_parser.add_argument("--json-output", default=str(DEFAULT_CRITICAL_INPUT_PREFLIGHT_JSON))
    critical_inputs_preflight_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_CRITICAL_INPUT_PREFLIGHT_MARKDOWN),
    )
    critical_inputs_preflight_parser.add_argument("--html-output", default=str(DEFAULT_CRITICAL_INPUT_PREFLIGHT_HTML))
    critical_inputs_preflight_parser.add_argument(
        "--approve",
        action="store_true",
        help="approve non-high-risk rows while simulating supplied answers",
    )
    critical_inputs_preflight_parser.add_argument(
        "--approve-high-risk",
        action="store_true",
        help="also approve high-risk rows supplied in this preflight",
    )

    critical_inputs_impact_parser = subparsers.add_parser(
        "critical-inputs-impact",
        help="rank remaining critical inputs by simulated blocker reduction",
    )
    critical_inputs_impact_parser.add_argument("--approval-pack", default=str(DEFAULT_LEARNING_APPROVAL_PACK_JSON))
    critical_inputs_impact_parser.add_argument("--answers", default=str(DEFAULT_CRITICAL_INPUT_ANSWERS_JSON))
    critical_inputs_impact_parser.add_argument("--research-json", default=str(DEFAULT_RESEARCH_JSON))
    critical_inputs_impact_parser.add_argument(
        "--profile",
        default=str(DEFAULT_PERSONAL_PROFILE if DEFAULT_PERSONAL_PROFILE.exists() else DEFAULT_PROFILE),
    )
    critical_inputs_impact_parser.add_argument("--memory", default=str(DEFAULT_MEMORY))
    critical_inputs_impact_parser.add_argument("--closed-jobs", default=str(DEFAULT_CLOSED_JOBS))
    critical_inputs_impact_parser.add_argument("--json-output", default=str(DEFAULT_CRITICAL_INPUT_IMPACT_JSON))
    critical_inputs_impact_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_CRITICAL_INPUT_IMPACT_MARKDOWN),
    )
    critical_inputs_impact_parser.add_argument("--html-output", default=str(DEFAULT_CRITICAL_INPUT_IMPACT_HTML))

    critical_inputs_workflow_parser = subparsers.add_parser(
        "critical-inputs-workflow",
        help="merge confirmed critical answers, dry-run apply, optionally apply, then refresh reports",
    )
    critical_inputs_workflow_parser.add_argument("--approval-pack", default=str(DEFAULT_LEARNING_APPROVAL_PACK_JSON))
    critical_inputs_workflow_parser.add_argument("--answers", default=str(DEFAULT_CRITICAL_INPUT_ANSWERS_JSON))
    critical_inputs_workflow_parser.add_argument(
        "--answers-markdown-output",
        default=str(DEFAULT_CRITICAL_INPUT_ANSWERS_MARKDOWN),
    )
    critical_inputs_workflow_parser.add_argument("--updates", required=True)
    critical_inputs_workflow_parser.add_argument(
        "--profile",
        default=str(DEFAULT_PERSONAL_PROFILE if DEFAULT_PERSONAL_PROFILE.exists() else DEFAULT_PROFILE),
    )
    critical_inputs_workflow_parser.add_argument("--memory", default=str(DEFAULT_MEMORY))
    critical_inputs_workflow_parser.add_argument("--source", default="confirmed_critical_inputs")
    critical_inputs_workflow_parser.add_argument("--json-output", default=str(DEFAULT_CRITICAL_INPUT_WORKFLOW_JSON))
    critical_inputs_workflow_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_CRITICAL_INPUT_WORKFLOW_MARKDOWN),
    )
    critical_inputs_workflow_parser.add_argument("--update-json-output", default=str(DEFAULT_CRITICAL_INPUT_UPDATE_JSON))
    critical_inputs_workflow_parser.add_argument(
        "--update-markdown-output",
        default=str(DEFAULT_CRITICAL_INPUT_UPDATE_MARKDOWN),
    )
    critical_inputs_workflow_parser.add_argument("--status-json-output", default=str(DEFAULT_CRITICAL_INPUT_STATUS_JSON))
    critical_inputs_workflow_parser.add_argument(
        "--status-markdown-output",
        default=str(DEFAULT_CRITICAL_INPUT_STATUS_MARKDOWN),
    )
    critical_inputs_workflow_parser.add_argument("--approve", action="store_true")
    critical_inputs_workflow_parser.add_argument("--approve-high-risk", action="store_true")
    critical_inputs_workflow_parser.add_argument(
        "--apply",
        action="store_true",
        help="write confirmed values to profile and answer memory after dry-run",
    )
    critical_inputs_workflow_parser.add_argument(
        "--skip-refresh",
        action="store_true",
        help="skip regenerating gaps/readiness/coverage/audit/export after applying",
    )

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

    apply_critical_inputs_parser = subparsers.add_parser(
        "apply-critical-inputs",
        help="apply approved critical input answers from the learning approval pack",
    )
    apply_critical_inputs_parser.add_argument("--approval-pack", default=str(DEFAULT_LEARNING_APPROVAL_PACK_JSON))
    apply_critical_inputs_parser.add_argument("--answers", default=None)
    apply_critical_inputs_parser.add_argument(
        "--profile",
        default=str(DEFAULT_PERSONAL_PROFILE if DEFAULT_PERSONAL_PROFILE.exists() else DEFAULT_PROFILE),
    )
    apply_critical_inputs_parser.add_argument("--memory", default=str(DEFAULT_MEMORY))
    apply_critical_inputs_parser.add_argument("--source", default="critical_inputs")
    apply_critical_inputs_parser.add_argument("--dry-run", action="store_true")

    fake_critical_inputs_parser = subparsers.add_parser(
        "fake-critical-input-probe",
        help="fill critical inputs with fake candidate answers for dry-run verification only",
    )
    fake_critical_inputs_parser.add_argument("--approval-pack", default=str(DEFAULT_LEARNING_APPROVAL_PACK_JSON))
    fake_critical_inputs_parser.add_argument("--json-output", default=str(DEFAULT_FAKE_CRITICAL_INPUT_PROBE_JSON))
    fake_critical_inputs_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_FAKE_CRITICAL_INPUT_PROBE_MARKDOWN),
    )
    fake_critical_inputs_parser.add_argument(
        "--answers-json-output",
        default=str(DEFAULT_FAKE_CRITICAL_INPUT_ANSWERS_JSON),
    )
    fake_critical_inputs_parser.add_argument(
        "--answers-markdown-output",
        default=str(DEFAULT_FAKE_CRITICAL_INPUT_ANSWERS_MARKDOWN),
    )

    fake_learning_probe_parser = subparsers.add_parser(
        "fake-learning-probe",
        help="apply fake non-user learning answers in memory and report remaining blockers",
    )
    fake_learning_probe_parser.add_argument("--research-json", default=str(DEFAULT_RESEARCH_JSON))
    fake_learning_probe_parser.add_argument("--learning-tasks-json", default=str(DEFAULT_LEARNING_TASKS_JSON))
    fake_learning_probe_parser.add_argument("--baseline-gaps-json", default=str(DEFAULT_GAPS_JSON))
    fake_learning_probe_parser.add_argument("--json-output", default=str(DEFAULT_FAKE_LEARNING_PROBE_JSON))
    fake_learning_probe_parser.add_argument("--markdown-output", default=str(DEFAULT_FAKE_LEARNING_PROBE_MARKDOWN))

    fake_position_rehearsal_parser = subparsers.add_parser(
        "fake-position-rehearsal",
        help="run observed-position fake form rehearsals locally without real submissions",
    )
    fake_position_rehearsal_parser.add_argument("--research-json", default=str(DEFAULT_RESEARCH_JSON))
    fake_position_rehearsal_parser.add_argument("--learning-tasks-json", default=str(DEFAULT_LEARNING_TASKS_JSON))
    fake_position_rehearsal_parser.add_argument("--closed-jobs", default=str(DEFAULT_CLOSED_JOBS))
    fake_position_rehearsal_parser.add_argument("--limit", type=int, default=100)
    fake_position_rehearsal_parser.add_argument(
        "--per-platform-role-target",
        type=int,
        default=None,
        help="run this many observed positions for each target platform and role-family pair",
    )
    fake_position_rehearsal_parser.add_argument("--include-values", action="store_true")
    fake_position_rehearsal_parser.add_argument(
        "--allow-local-synthetic-submit",
        action="store_true",
        help="click final submit only inside local fake forms when all other gates are clear",
    )
    fake_position_rehearsal_parser.add_argument("--json-output", default=str(DEFAULT_FAKE_POSITION_REHEARSAL_JSON))
    fake_position_rehearsal_parser.add_argument("--markdown-output", default=str(DEFAULT_FAKE_POSITION_REHEARSAL_MARKDOWN))

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
    synthetic_browser_exec_parser.add_argument(
        "--allow-local-synthetic-submit",
        action="store_true",
        help="allow final submit only inside the local fake-form executor when no other stop gate is present",
    )
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
    export_questions_parser.add_argument(
        "--synthetic-browser-exec-json",
        default=str(DEFAULT_SYNTHETIC_BROWSER_EXEC_JSON),
    )
    export_questions_parser.add_argument("--fake-learning-probe-json", default=str(DEFAULT_FAKE_LEARNING_PROBE_JSON))
    export_questions_parser.add_argument(
        "--fake-critical-input-probe-json",
        default=str(DEFAULT_FAKE_CRITICAL_INPUT_PROBE_JSON),
    )
    export_questions_parser.add_argument(
        "--fake-critical-input-answers-json",
        default=str(DEFAULT_FAKE_CRITICAL_INPUT_ANSWERS_JSON),
    )
    export_questions_parser.add_argument("--fake-position-rehearsal-json", default=str(DEFAULT_FAKE_POSITION_REHEARSAL_JSON))
    export_questions_parser.add_argument(
        "--learning-approval-pack-json",
        default=str(DEFAULT_LEARNING_APPROVAL_PACK_JSON),
    )
    export_questions_parser.add_argument("--answer-memory-json", default=str(DEFAULT_MEMORY))
    export_questions_parser.add_argument("--closed-jobs-json", default=str(DEFAULT_CLOSED_JOBS))
    export_questions_parser.add_argument(
        "--profile-json",
        default=str(DEFAULT_PERSONAL_PROFILE if DEFAULT_PERSONAL_PROFILE.exists() else DEFAULT_PROFILE),
    )
    export_questions_parser.add_argument("--goal-audit-json", default=str(DEFAULT_GOAL_AUDIT_JSON))
    export_questions_parser.add_argument("--autofill-batch-json", default=str(DEFAULT_AUTOFILL_BATCH_JSON))
    export_questions_parser.add_argument("--autofill-batch-html", default=str(DEFAULT_AUTOFILL_BATCH_HTML))
    export_questions_parser.add_argument("--automation-handoff-json", default=str(DEFAULT_AUTOMATION_HANDOFF_JSON))
    export_questions_parser.add_argument("--automation-handoff-html", default=str(DEFAULT_AUTOMATION_HANDOFF_HTML))
    export_questions_parser.add_argument(
        "--critical-input-suggestions-json",
        default=str(DEFAULT_CRITICAL_INPUT_SUGGESTIONS_JSON),
    )
    export_questions_parser.add_argument(
        "--critical-input-questionnaire-json",
        default=str(DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_JSON),
    )
    export_questions_parser.add_argument(
        "--critical-input-questionnaire-html",
        default=str(DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_HTML),
    )
    export_questions_parser.add_argument(
        "--critical-input-preflight-json",
        default=str(DEFAULT_CRITICAL_INPUT_PREFLIGHT_JSON),
    )
    export_questions_parser.add_argument(
        "--critical-input-preflight-html",
        default=str(DEFAULT_CRITICAL_INPUT_PREFLIGHT_HTML),
    )
    export_questions_parser.add_argument(
        "--critical-input-impact-json",
        default=str(DEFAULT_CRITICAL_INPUT_IMPACT_JSON),
    )
    export_questions_parser.add_argument(
        "--critical-input-impact-html",
        default=str(DEFAULT_CRITICAL_INPUT_IMPACT_HTML),
    )
    export_questions_parser.add_argument("--xlsx-output", default=str(DEFAULT_QUESTION_EXPORT_XLSX))
    export_questions_parser.add_argument("--html-output", default=str(DEFAULT_QUESTION_EXPORT_HTML))

    goal_audit_parser = subparsers.add_parser(
        "goal-audit",
        help="audit current evidence against the 100-position automation goal",
    )
    goal_audit_parser.add_argument("--coverage-gate-json", default=str(DEFAULT_COVERAGE_GATE_JSON))
    goal_audit_parser.add_argument("--gaps-json", default=str(DEFAULT_GAPS_JSON))
    goal_audit_parser.add_argument("--readiness-json", default=str(DEFAULT_READINESS_JSON))
    goal_audit_parser.add_argument("--critical-input-status-json", default=str(DEFAULT_CRITICAL_INPUT_STATUS_JSON))
    goal_audit_parser.add_argument(
        "--fake-critical-input-probe-json",
        default=str(DEFAULT_FAKE_CRITICAL_INPUT_PROBE_JSON),
    )
    goal_audit_parser.add_argument(
        "--fake-position-rehearsal-json",
        default=str(DEFAULT_FAKE_POSITION_REHEARSAL_JSON),
    )
    goal_audit_parser.add_argument("--autofill-batch-json", default=str(DEFAULT_AUTOFILL_BATCH_JSON))
    goal_audit_parser.add_argument("--closed-jobs-json", default=str(DEFAULT_CLOSED_JOBS))
    goal_audit_parser.add_argument("--json-output", default=str(DEFAULT_GOAL_AUDIT_JSON))
    goal_audit_parser.add_argument("--markdown-output", default=str(DEFAULT_GOAL_AUDIT_MARKDOWN))

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
            source_artifacts=_question_export_source_artifacts(
                {
                    "Answer gaps": args.gaps_json,
                    "Automation readiness": args.readiness_json,
                    "Research coverage gate": args.coverage_gate_json,
                    "Collection plan": args.collection_plan_json,
                    "Learning tasks": args.learning_tasks_json,
                    "Synthetic browser execution": args.synthetic_browser_exec_json,
                    "Fake learning probe": args.fake_learning_probe_json,
                    "Fake critical input probe": args.fake_critical_input_probe_json,
                    "Fake critical input answers": args.fake_critical_input_answers_json,
                    "Fake position rehearsal": args.fake_position_rehearsal_json,
                    "Learning approval pack": args.learning_approval_pack_json,
                    "Answer memory": args.answer_memory_json,
                    "Closed postings": args.closed_jobs_json,
                    "Candidate profile": args.profile_json,
                    "Goal readiness audit": args.goal_audit_json,
                    "Autofill batch": args.autofill_batch_json,
                    "Autofill batch HTML": args.autofill_batch_html,
                    "Automation handoff": args.automation_handoff_json,
                    "Automation handoff HTML": args.automation_handoff_html,
                    "Critical input suggestions": args.critical_input_suggestions_json,
                    "Critical input questionnaire": args.critical_input_questionnaire_json,
                    "Critical input questionnaire HTML": args.critical_input_questionnaire_html,
                    "Critical input preflight": args.critical_input_preflight_json,
                    "Critical input preflight HTML": args.critical_input_preflight_html,
                    "Critical input impact": args.critical_input_impact_json,
                    "Critical input impact HTML": args.critical_input_impact_html,
                }
            ),
            synthetic_browser_execution=_load_optional_json(args.synthetic_browser_exec_json),
            fake_learning_probe=_load_optional_json(args.fake_learning_probe_json),
            fake_critical_input_probe=_load_optional_json(args.fake_critical_input_probe_json),
            fake_position_rehearsal=_load_optional_json(args.fake_position_rehearsal_json),
            goal_readiness_audit=_load_optional_json(args.goal_audit_json),
            critical_input_suggestions=_load_optional_json(args.critical_input_suggestions_json),
            critical_input_questionnaire=_load_optional_json(args.critical_input_questionnaire_json),
            critical_input_preflight=_load_optional_json(args.critical_input_preflight_json),
            critical_input_impact=_load_optional_json(args.critical_input_impact_json),
            autofill_batch=_load_optional_json(args.autofill_batch_json),
            automation_handoff=_load_optional_json(args.automation_handoff_json),
            learning_approval_pack=_load_optional_json(args.learning_approval_pack_json),
            answer_memory=_load_optional_json(args.answer_memory_json),
            closed_jobs=_load_optional_json(args.closed_jobs_json),
            profile=_load_optional_json(args.profile_json),
        )
        print(f"Wrote question Excel to {args.xlsx_output}")
        print(f"Wrote question HTML to {args.html_output}")
        print(f"Questions: {len(export.get('question_rows', []))}")
        print(f"Blocking prompts: {len(export.get('blocker_rows', []))}")
        print(f"Learning tasks: {len(export.get('user_questions', []))}")
        print(f"Critical inputs: {export.get('summary', {}).get('critical_input_count', 0)}")
        return 0

    if args.command == "goal-audit":
        audit = write_goal_readiness_audit(
            json.loads(Path(args.coverage_gate_json).read_text(encoding="utf-8")),
            json.loads(Path(args.gaps_json).read_text(encoding="utf-8")),
            json.loads(Path(args.readiness_json).read_text(encoding="utf-8")),
            args.json_output,
            args.markdown_output,
            critical_input_status=_load_optional_json(args.critical_input_status_json),
            fake_critical_input_probe=_load_optional_json(args.fake_critical_input_probe_json),
            fake_position_rehearsal=_load_optional_json(args.fake_position_rehearsal_json),
            autofill_batch_plan=_load_optional_json(args.autofill_batch_json),
            closed_jobs=_load_optional_json(args.closed_jobs_json),
        )
        print(f"Wrote goal audit JSON to {args.json_output}")
        print(f"Wrote goal audit Markdown to {args.markdown_output}")
        print(f"Status: {audit.get('status')}")
        print(f"Missing requirements: {audit.get('missing_requirement_count', 0)}")
        print(f"Goal complete: {str(bool(audit.get('goal_complete'))).lower()}")
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

    if args.command == "autofill-batch":
        if not Path(args.research_json).exists():
            raise FileNotFoundError(f"research report not found: {args.research_json}")
        if not Path(args.readiness_json).exists():
            raise FileNotFoundError(f"readiness report not found: {args.readiness_json}")
        profile = load_profile(args.profile) if args.profile and Path(args.profile).exists() else None
        answer_memory = load_answer_memory(args.memory) if args.memory else None
        report = write_autofill_batch_plan(
            json.loads(Path(args.research_json).read_text(encoding="utf-8")),
            json.loads(Path(args.readiness_json).read_text(encoding="utf-8")),
            args.json_output,
            args.markdown_output,
            args.html_output,
            profile=profile,
            answer_memory=answer_memory,
            closed_jobs=load_closed_jobs(args.closed_jobs),
            limit=args.limit,
            include_values=args.include_values,
        )
        print(f"Wrote autofill batch JSON to {args.json_output}")
        print(f"Wrote autofill batch Markdown to {args.markdown_output}")
        print(f"Wrote autofill batch HTML to {args.html_output}")
        print(f"Selected: {report.get('selected_count', 0)} / {report.get('requested_count', 0)}")
        print(f"Autofill allowed: {report.get('selected_autofill_allowed_count', 0)}")
        print(f"Browser actions: {report.get('browser_action_count', 0)}")
        print(f"Selector misses: {report.get('selector_miss_count', 0)}")
        print(f"Would submit: {report.get('would_submit_count', 0)}")
        return 0

    if args.command == "automation-handoff":
        report = write_automation_handoff_report(
            _load_optional_json(args.goal_audit_json),
            _load_optional_json(args.critical_input_questionnaire_json),
            _load_optional_json(args.critical_input_impact_json),
            _load_optional_json(args.autofill_batch_json),
            args.json_output,
            args.markdown_output,
            args.html_output,
            answer_memory=_load_optional_json(args.answer_memory_json),
            closed_jobs=_load_optional_json(args.closed_jobs_json),
            source_artifacts=_question_export_source_artifacts(
                {
                    "Goal readiness audit": args.goal_audit_json,
                    "Critical input questionnaire": args.critical_input_questionnaire_json,
                    "Critical input impact": args.critical_input_impact_json,
                    "Autofill batch": args.autofill_batch_json,
                    "Answer memory": args.answer_memory_json,
                    "Closed postings": args.closed_jobs_json,
                }
            ),
        )
        summary = report.get("summary") or {}
        print(f"Wrote automation handoff JSON to {args.json_output}")
        print(f"Wrote automation handoff Markdown to {args.markdown_output}")
        print(f"Wrote automation handoff HTML to {args.html_output}")
        print(f"Status: {report.get('status')}")
        print(f"Data blockers: {summary.get('data_blocking_prompt_count', 0)}")
        print(f"Critical waiting: {summary.get('critical_waiting_count', 0)}")
        print(f"Autofill selected: {summary.get('autofill_selected_count', 0)}")
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
        profile = load_profile(args.profile) if Path(args.profile).exists() else None
        memory = _load_optional_json(args.memory)
        template = write_learning_task_template(
            readiness,
            args.json_output,
            args.markdown_output,
            profile=profile,
            answer_memory=memory,
        )
        print(f"Wrote learning task JSON to {args.json_output}")
        print(f"Wrote learning task Markdown to {args.markdown_output}")
        print(f"Tasks: {template.get('task_count', 0)}")
        return 0

    if args.command == "learning-approval-pack":
        tasks_path = Path(args.learning_tasks_json)
        readiness_path = Path(args.readiness_json)
        if not tasks_path.exists():
            raise FileNotFoundError(f"learning tasks not found: {args.learning_tasks_json}")
        if not readiness_path.exists():
            raise FileNotFoundError(f"readiness report not found: {args.readiness_json}")
        pack = write_learning_approval_pack(
            json.loads(tasks_path.read_text(encoding="utf-8")),
            json.loads(readiness_path.read_text(encoding="utf-8")),
            args.json_output,
            args.markdown_output,
        )
        summary = pack.get("summary") or {}
        print(f"Wrote learning approval pack JSON to {args.json_output}")
        print(f"Wrote learning approval pack Markdown to {args.markdown_output}")
        print(f"Tasks: {summary.get('task_count', 0)}")
        print(f"Critical inputs: {summary.get('critical_input_count', 0)}")
        print(f"Draft answers: {summary.get('draft_answer_count', 0)}")
        print(f"Missing user answers: {summary.get('missing_user_answer_count', 0)}")
        print(f"Exact confirmations: {summary.get('exact_user_confirmation_count', 0)}")
        print(f"Manual gates: {summary.get('manual_gate_count', 0)}")
        return 0

    if args.command == "critical-inputs-template":
        approval_pack_path = Path(args.approval_pack)
        if not approval_pack_path.exists():
            raise FileNotFoundError(f"approval pack not found: {args.approval_pack}")
        template = write_critical_input_answer_template(
            json.loads(approval_pack_path.read_text(encoding="utf-8")),
            args.json_output,
            args.markdown_output,
        )
        print(f"Wrote critical input answer JSON to {args.json_output}")
        print(f"Wrote critical input answer Markdown to {args.markdown_output}")
        print(f"Answers needed: {template.get('answer_count', 0)}")
        return 0

    if args.command == "critical-inputs-status":
        approval_pack_path = Path(args.approval_pack)
        if not approval_pack_path.exists():
            raise FileNotFoundError(f"approval pack not found: {args.approval_pack}")
        answers_path = Path(args.answers) if args.answers else None
        answers_payload = (
            json.loads(answers_path.read_text(encoding="utf-8"))
            if answers_path and answers_path.exists()
            else None
        )
        report = write_critical_input_status_report(
            json.loads(approval_pack_path.read_text(encoding="utf-8")),
            args.json_output,
            args.markdown_output,
            answers_payload=answers_payload,
        )
        summary = report.get("summary") or {}
        print(f"Wrote critical input status JSON to {args.json_output}")
        print(f"Wrote critical input status Markdown to {args.markdown_output}")
        print(f"Inputs: {summary.get('input_count', 0)}")
        print(f"Ready to apply: {summary.get('ready_to_apply_count', 0)}")
        print(f"Waiting: {summary.get('waiting_count', 0)}")
        print(f"Supervised only: {summary.get('supervised_only_count', 0)}")
        print(f"Ready for autofill recheck: {str(bool(summary.get('ready_for_autofill_recheck'))).lower()}")
        return 0

    if args.command == "critical-input-suggestions":
        answers_path = Path(args.answers)
        if not answers_path.exists():
            raise FileNotFoundError(f"critical input answers not found: {args.answers}")
        packet = write_critical_input_suggestion_packet(
            json.loads(answers_path.read_text(encoding="utf-8")),
            args.json_output,
            args.markdown_output,
            profile=load_profile(args.profile) if Path(args.profile).exists() else None,
            answer_memory=load_answer_memory(args.memory) if Path(args.memory).exists() else None,
        )
        print(f"Wrote critical input suggestions JSON to {args.json_output}")
        print(f"Wrote critical input suggestions Markdown to {args.markdown_output}")
        print(f"Inputs: {packet.get('input_count', 0)}")
        print(f"Direct suggestions: {packet.get('direct_suggestion_count', 0)}")
        print(f"Exact user answers required: {packet.get('exact_user_answer_required_count', 0)}")
        print(f"Supervised only: {packet.get('supervised_only_count', 0)}")
        return 0

    if args.command == "critical-inputs-questionnaire":
        answers_path = Path(args.answers)
        if not answers_path.exists():
            raise FileNotFoundError(f"critical input answers not found: {args.answers}")
        questionnaire = write_critical_input_questionnaire(
            json.loads(answers_path.read_text(encoding="utf-8")),
            args.json_output,
            args.markdown_output,
            args.html_output,
            suggestions_payload=_load_optional_json(args.suggestions),
            impact_payload=_load_optional_json(args.impact),
        )
        print(f"Wrote critical input questionnaire JSON to {args.json_output}")
        print(f"Wrote critical input questionnaire Markdown to {args.markdown_output}")
        print(f"Wrote critical input questionnaire HTML to {args.html_output}")
        print(f"Questions: {questionnaire.get('question_count', 0)}")
        print(f"Answerable: {questionnaire.get('answerable_question_count', 0)}")
        print(f"High risk: {questionnaire.get('high_risk_question_count', 0)}")
        print(f"Supervised only: {questionnaire.get('supervised_only_count', 0)}")
        return 0

    if args.command == "critical-inputs-update":
        answers_path = Path(args.answers)
        updates_path = Path(args.updates)
        if not answers_path.exists():
            raise FileNotFoundError(f"critical input answers not found: {args.answers}")
        if not updates_path.exists():
            raise FileNotFoundError(f"critical input updates not found: {args.updates}")
        report = write_critical_input_answer_update(
            answers_path,
            json.loads(updates_path.read_text(encoding="utf-8")),
            args.json_output,
            args.markdown_output,
            answers_markdown_output=args.answers_markdown_output,
            approve=args.approve,
            approve_high_risk=args.approve_high_risk,
        )
        summary = report.get("summary") or {}
        print(f"Updated critical input answers at {args.answers}")
        print(f"Wrote critical input update JSON to {args.json_output}")
        print(f"Wrote critical input update Markdown to {args.markdown_output}")
        print(f"Matched updates: {summary.get('matched_update_count', 0)}")
        print(f"Answers updated: {summary.get('answer_updated_count', 0)}")
        print(f"Approvals updated: {summary.get('approval_updated_count', 0)}")
        print(f"High-risk approvals blocked: {summary.get('high_risk_approval_blocked_count', 0)}")
        print(f"Supervised skipped: {summary.get('supervised_skipped_count', 0)}")
        print(f"Unknown updates: {summary.get('unknown_update_count', 0)}")
        print(f"Ready after update: {summary.get('ready_after_update_count', 0)}")
        print(f"Waiting after update: {summary.get('waiting_after_update_count', 0)}")
        return 0

    if args.command == "critical-inputs-preflight":
        updates_path = Path(args.updates)
        if not Path(args.approval_pack).exists():
            raise FileNotFoundError(f"approval pack not found: {args.approval_pack}")
        if not Path(args.answers).exists():
            raise FileNotFoundError(f"critical input answers not found: {args.answers}")
        if not updates_path.exists():
            raise FileNotFoundError(f"critical input updates not found: {args.updates}")
        if not Path(args.research_json).exists():
            raise FileNotFoundError(f"research report not found: {args.research_json}")
        if not Path(args.profile).exists():
            raise FileNotFoundError(f"profile not found: {args.profile}")
        preflight = write_critical_input_preflight(
            args.approval_pack,
            args.answers,
            json.loads(updates_path.read_text(encoding="utf-8")),
            args.research_json,
            args.profile,
            args.memory,
            args.json_output,
            args.markdown_output,
            args.html_output,
            closed_jobs=_load_optional_json(args.closed_jobs),
            approve=args.approve,
            approve_high_risk=args.approve_high_risk,
            source=args.source,
        )
        summary = preflight.get("summary") or {}
        print(f"Wrote critical input preflight JSON to {args.json_output}")
        print(f"Wrote critical input preflight Markdown to {args.markdown_output}")
        print(f"Wrote critical input preflight HTML to {args.html_output}")
        print(f"Matched updates: {summary.get('matched_updates', 0)}")
        print(f"Unknown updates: {summary.get('unknown_updates', 0)}")
        print(f"High-risk approvals blocked: {summary.get('high_risk_approval_blocked', 0)}")
        print(
            "Data-blocking prompts: "
            f"{summary.get('data_blocking_prompts_before', 0)} -> "
            f"{summary.get('data_blocking_prompts_after', 0)}"
        )
        print(
            "Positions ready for autofill: "
            f"{summary.get('positions_ready_for_autofill_before', 0)} -> "
            f"{summary.get('positions_ready_for_autofill_after', 0)}"
        )
        return 0

    if args.command == "critical-inputs-impact":
        for label, path_value in [
            ("approval pack", args.approval_pack),
            ("critical input answers", args.answers),
            ("research report", args.research_json),
            ("profile", args.profile),
        ]:
            if not Path(path_value).exists():
                raise FileNotFoundError(f"{label} not found: {path_value}")
        report = write_critical_input_impact_report(
            json.loads(Path(args.approval_pack).read_text(encoding="utf-8")),
            json.loads(Path(args.answers).read_text(encoding="utf-8")),
            json.loads(Path(args.research_json).read_text(encoding="utf-8")),
            json.loads(Path(args.profile).read_text(encoding="utf-8")),
            args.json_output,
            args.markdown_output,
            args.html_output,
            answer_memory=load_answer_memory(args.memory),
            closed_jobs=load_closed_jobs(args.closed_jobs),
        )
        summary = report.get("summary") or {}
        print(f"Wrote critical input impact JSON to {args.json_output}")
        print(f"Wrote critical input impact Markdown to {args.markdown_output}")
        print(f"Wrote critical input impact HTML to {args.html_output}")
        print(f"Inputs: {report.get('input_count', 0)}")
        print(f"Baseline data blockers: {summary.get('baseline_data_blocking_prompts', 0)}")
        print(f"After all simulated answers: {summary.get('combined_data_blocking_prompts_after', 0)}")
        print(f"Combined blocker delta: {summary.get('combined_data_blocking_prompts_delta', 0)}")
        print(f"Top input: {summary.get('top_input_id', '')}")
        return 0

    if args.command == "critical-inputs-workflow":
        updates_path = Path(args.updates)
        if not Path(args.approval_pack).exists():
            raise FileNotFoundError(f"approval pack not found: {args.approval_pack}")
        if not Path(args.answers).exists():
            raise FileNotFoundError(f"critical input answers not found: {args.answers}")
        if not updates_path.exists():
            raise FileNotFoundError(f"critical input updates not found: {args.updates}")
        workflow = write_critical_input_answer_workflow(
            args.approval_pack,
            args.answers,
            json.loads(updates_path.read_text(encoding="utf-8")),
            args.profile,
            args.memory,
            args.json_output,
            args.markdown_output,
            args.update_json_output,
            args.update_markdown_output,
            args.status_json_output,
            args.status_markdown_output,
            answers_markdown_output=args.answers_markdown_output,
            approve=args.approve,
            approve_high_risk=args.approve_high_risk,
            apply_confirmed=args.apply,
            source=args.source,
        )
        refresh = None
        if args.apply and not args.skip_refresh:
            refresh = _refresh_application_automation_reports()
            workflow["refresh"] = refresh
            Path(args.json_output).write_text(
                json.dumps(workflow, ensure_ascii=True, indent=2) + "\n",
                encoding="utf-8",
            )
            Path(args.markdown_output).write_text(
                render_critical_input_answer_workflow_markdown(workflow),
                encoding="utf-8",
            )
        summary = workflow.get("summary") or {}
        print(f"Wrote critical input workflow JSON to {args.json_output}")
        print(f"Wrote critical input workflow Markdown to {args.markdown_output}")
        print(f"Apply executed: {str(bool(args.apply)).lower()}")
        print(f"Matched updates: {summary.get('matched_updates', 0)}")
        print(f"Ready to apply: {summary.get('ready_to_apply', 0)}")
        print(f"Waiting: {summary.get('waiting', 0)}")
        print(f"Dry-run approved inputs: {summary.get('dry_run_approved_inputs', 0)}")
        print(f"High-risk approvals blocked: {summary.get('high_risk_approval_blocked', 0)}")
        if refresh:
            print(f"Refreshed reports: {', '.join(refresh.get('refreshed', []))}")
            print(f"Goal status: {refresh.get('goal_status')}")
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

    if args.command == "apply-critical-inputs":
        result = apply_critical_input_answers(
            args.approval_pack,
            args.profile,
            args.memory,
            answers_path=args.answers,
            source=args.source,
            dry_run=args.dry_run,
        )
        print(f"Dry run: {str(bool(result.get('dry_run'))).lower()}")
        print(f"Critical inputs: {result.get('critical_input_count', 0)}")
        print(f"Approved inputs: {result.get('approved_input_count', 0)}")
        print(f"Profile updates: {len(result.get('profile_updates', []))}")
        print(f"Resume fact updates: {len(result.get('resume_fact_updates', []))}")
        print(f"Answer memory updates: {len(result.get('answer_memory_updates', []))}")
        print(f"Skipped inputs: {result.get('skipped_input_count', 0)}")
        print(f"Skipped writes: {len(result.get('skipped', []))}")
        return 0

    if args.command == "fake-critical-input-probe":
        approval_pack_path = Path(args.approval_pack)
        if not approval_pack_path.exists():
            raise FileNotFoundError(f"approval pack not found: {args.approval_pack}")
        report = write_fake_critical_input_probe(
            json.loads(approval_pack_path.read_text(encoding="utf-8")),
            args.json_output,
            args.markdown_output,
            args.answers_json_output,
            args.answers_markdown_output,
        )
        print(f"Wrote fake critical input probe JSON to {args.json_output}")
        print(f"Wrote fake critical input probe Markdown to {args.markdown_output}")
        print(f"Wrote fake critical input answers JSON to {args.answers_json_output}")
        print(f"Wrote fake critical input answers Markdown to {args.answers_markdown_output}")
        print(f"Fake answered: {report.get('fake_answered_count', 0)}")
        print(f"Ready to apply: {report.get('ready_to_apply_count', 0)}")
        print(f"Waiting: {report.get('waiting_count', 0)}")
        print(f"Supervised only: {report.get('supervised_only_count', 0)}")
        return 0

    if args.command == "fake-learning-probe":
        research_path = Path(args.research_json)
        tasks_path = Path(args.learning_tasks_json)
        if not research_path.exists():
            raise FileNotFoundError(f"research report not found: {args.research_json}")
        if not tasks_path.exists():
            raise FileNotFoundError(f"learning tasks not found: {args.learning_tasks_json}")
        report = write_fake_learning_probe(
            json.loads(research_path.read_text(encoding="utf-8")),
            json.loads(tasks_path.read_text(encoding="utf-8")),
            _load_optional_json(args.baseline_gaps_json),
            args.json_output,
            args.markdown_output,
        )
        print(f"Wrote fake learning probe JSON to {args.json_output}")
        print(f"Wrote fake learning probe Markdown to {args.markdown_output}")
        print(f"Fake answered tasks: {report.get('fake_answered_task_count', 0)}")
        print(f"Remaining learning blockers: {report.get('remaining_learning_blocker_count', 0)}")
        print(f"Remaining manual gates: {report.get('remaining_manual_gate_count', 0)}")
        return 0

    if args.command == "fake-position-rehearsal":
        research_path = Path(args.research_json)
        tasks_path = Path(args.learning_tasks_json)
        if not research_path.exists():
            raise FileNotFoundError(f"research report not found: {args.research_json}")
        if not tasks_path.exists():
            raise FileNotFoundError(f"learning tasks not found: {args.learning_tasks_json}")
        report = write_fake_position_rehearsal(
            json.loads(research_path.read_text(encoding="utf-8")),
            json.loads(tasks_path.read_text(encoding="utf-8")),
            args.json_output,
            args.markdown_output,
            limit=args.limit,
            closed_jobs=load_closed_jobs(args.closed_jobs),
            include_values=args.include_values,
            allow_local_synthetic_submit=args.allow_local_synthetic_submit,
            per_platform_role_target=args.per_platform_role_target,
        )
        print(f"Wrote fake position rehearsal JSON to {args.json_output}")
        print(f"Wrote fake position rehearsal Markdown to {args.markdown_output}")
        print(f"Runs: {report.get('run_count', 0)} / {report.get('requested_count', 0)}")
        print(f"Per-platform-role target: {report.get('per_platform_role_target', 0)}")
        print(f"Platform-role target achieved: {str(bool(report.get('platform_role_target_achieved'))).lower()}")
        print(f"Local synthetic submits: {report.get('actual_submit_count', 0)}")
        print(f"Eligible submit achieved: {str(bool(report.get('eligible_submit_achieved'))).lower()}")
        print(f"Pre-synthetic missing inputs: {report.get('pre_synthetic_missing_input_count', 0)}")
        print(f"Selector misses: {report.get('selector_miss_count', 0)}")
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
            allow_local_synthetic_submit=args.allow_local_synthetic_submit,
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


def _refresh_application_automation_reports() -> dict[str, object]:
    outbox_dir = Path(__file__).with_name("outbox")
    if DEFAULT_RESEARCH_JSON.exists():
        research = json.loads(DEFAULT_RESEARCH_JSON.read_text(encoding="utf-8"))
    else:
        research = write_application_research_report(
            outbox_dir,
            DEFAULT_RESEARCH_JSON,
            DEFAULT_RESEARCH_MARKDOWN,
            position_target=100,
        )
    profile_path = DEFAULT_PERSONAL_PROFILE if DEFAULT_PERSONAL_PROFILE.exists() else DEFAULT_PROFILE
    profile = load_profile(profile_path) if profile_path.exists() else None
    answer_memory = load_answer_memory(DEFAULT_MEMORY)
    gaps = write_answer_gap_report(
        research,
        DEFAULT_GAPS_JSON,
        DEFAULT_GAPS_MARKDOWN,
        profile=profile,
        answer_memory=answer_memory,
    )
    readiness = write_position_readiness_report(
        research,
        gaps,
        DEFAULT_READINESS_JSON,
        DEFAULT_READINESS_MARKDOWN,
        closed_jobs=load_closed_jobs(DEFAULT_CLOSED_JOBS),
    )
    coverage = write_research_coverage_gate(
        research,
        _load_optional_json(str(DEFAULT_SYNTHETIC_BROWSER_EXEC_JSON)),
        gaps,
        DEFAULT_COVERAGE_GATE_JSON,
        DEFAULT_COVERAGE_GATE_MARKDOWN,
        position_target=100,
    )
    approval_pack = _load_optional_json(str(DEFAULT_LEARNING_APPROVAL_PACK_JSON)) or {}
    answers_payload = _load_optional_json(str(DEFAULT_CRITICAL_INPUT_ANSWERS_JSON))
    critical_status = write_critical_input_status_report(
        approval_pack,
        DEFAULT_CRITICAL_INPUT_STATUS_JSON,
        DEFAULT_CRITICAL_INPUT_STATUS_MARKDOWN,
        answers_payload=answers_payload,
    )
    if answers_payload:
        write_critical_input_suggestion_packet(
            answers_payload,
            DEFAULT_CRITICAL_INPUT_SUGGESTIONS_JSON,
            DEFAULT_CRITICAL_INPUT_SUGGESTIONS_MARKDOWN,
            profile=profile,
            answer_memory=answer_memory,
        )
        critical_input_impact = write_critical_input_impact_report(
            approval_pack,
            answers_payload,
            research,
            json.loads(profile_path.read_text(encoding="utf-8")) if profile_path.exists() else {},
            DEFAULT_CRITICAL_INPUT_IMPACT_JSON,
            DEFAULT_CRITICAL_INPUT_IMPACT_MARKDOWN,
            DEFAULT_CRITICAL_INPUT_IMPACT_HTML,
            answer_memory=answer_memory,
            closed_jobs=load_closed_jobs(DEFAULT_CLOSED_JOBS),
        )
        write_critical_input_questionnaire(
            answers_payload,
            DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_JSON,
            DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_MARKDOWN,
            DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_HTML,
            suggestions_payload=_load_optional_json(str(DEFAULT_CRITICAL_INPUT_SUGGESTIONS_JSON)),
            impact_payload=critical_input_impact,
        )
    write_autofill_batch_plan(
        research,
        readiness,
        DEFAULT_AUTOFILL_BATCH_JSON,
        DEFAULT_AUTOFILL_BATCH_MARKDOWN,
        DEFAULT_AUTOFILL_BATCH_HTML,
        profile=profile,
        answer_memory=answer_memory,
        closed_jobs=load_closed_jobs(DEFAULT_CLOSED_JOBS),
        limit=100,
    )
    goal = write_goal_readiness_audit(
        coverage,
        gaps,
        readiness,
        DEFAULT_GOAL_AUDIT_JSON,
        DEFAULT_GOAL_AUDIT_MARKDOWN,
        critical_input_status=critical_status,
        fake_critical_input_probe=_load_optional_json(str(DEFAULT_FAKE_CRITICAL_INPUT_PROBE_JSON)),
        fake_position_rehearsal=_load_optional_json(str(DEFAULT_FAKE_POSITION_REHEARSAL_JSON)),
        autofill_batch_plan=_load_optional_json(str(DEFAULT_AUTOFILL_BATCH_JSON)),
        closed_jobs=_load_optional_json(str(DEFAULT_CLOSED_JOBS)),
    )
    automation_handoff = write_automation_handoff_report(
        goal,
        _load_optional_json(str(DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_JSON)),
        _load_optional_json(str(DEFAULT_CRITICAL_INPUT_IMPACT_JSON)),
        _load_optional_json(str(DEFAULT_AUTOFILL_BATCH_JSON)),
        DEFAULT_AUTOMATION_HANDOFF_JSON,
        DEFAULT_AUTOMATION_HANDOFF_MARKDOWN,
        DEFAULT_AUTOMATION_HANDOFF_HTML,
        answer_memory=_load_optional_json(str(DEFAULT_MEMORY)),
        closed_jobs=_load_optional_json(str(DEFAULT_CLOSED_JOBS)),
        source_artifacts=_question_export_source_artifacts(
            {
                "Goal readiness audit": str(DEFAULT_GOAL_AUDIT_JSON),
                "Critical input questionnaire": str(DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_JSON),
                "Critical input impact": str(DEFAULT_CRITICAL_INPUT_IMPACT_JSON),
                "Autofill batch": str(DEFAULT_AUTOFILL_BATCH_JSON),
                "Answer memory": str(DEFAULT_MEMORY),
                "Closed postings": str(DEFAULT_CLOSED_JOBS),
            }
        ),
    )
    if DEFAULT_COLLECTION_PLAN_JSON.exists() and DEFAULT_LEARNING_TASKS_JSON.exists():
        write_question_export(
            gaps,
            readiness,
            coverage,
            json.loads(DEFAULT_COLLECTION_PLAN_JSON.read_text(encoding="utf-8")),
            json.loads(DEFAULT_LEARNING_TASKS_JSON.read_text(encoding="utf-8")),
            DEFAULT_QUESTION_EXPORT_XLSX,
            DEFAULT_QUESTION_EXPORT_HTML,
            source_artifacts=_question_export_source_artifacts(
                {
                    "Answer gaps": str(DEFAULT_GAPS_JSON),
                    "Automation readiness": str(DEFAULT_READINESS_JSON),
                    "Research coverage gate": str(DEFAULT_COVERAGE_GATE_JSON),
                    "Collection plan": str(DEFAULT_COLLECTION_PLAN_JSON),
                    "Learning tasks": str(DEFAULT_LEARNING_TASKS_JSON),
                    "Synthetic browser execution": str(DEFAULT_SYNTHETIC_BROWSER_EXEC_JSON),
                    "Fake learning probe": str(DEFAULT_FAKE_LEARNING_PROBE_JSON),
                    "Fake critical input probe": str(DEFAULT_FAKE_CRITICAL_INPUT_PROBE_JSON),
                    "Fake critical input answers": str(DEFAULT_FAKE_CRITICAL_INPUT_ANSWERS_JSON),
                    "Fake position rehearsal": str(DEFAULT_FAKE_POSITION_REHEARSAL_JSON),
                    "Learning approval pack": str(DEFAULT_LEARNING_APPROVAL_PACK_JSON),
                    "Answer memory": str(DEFAULT_MEMORY),
                    "Closed postings": str(DEFAULT_CLOSED_JOBS),
                    "Goal readiness audit": str(DEFAULT_GOAL_AUDIT_JSON),
                    "Autofill batch": str(DEFAULT_AUTOFILL_BATCH_JSON),
                    "Autofill batch HTML": str(DEFAULT_AUTOFILL_BATCH_HTML),
                    "Automation handoff": str(DEFAULT_AUTOMATION_HANDOFF_JSON),
                    "Automation handoff HTML": str(DEFAULT_AUTOMATION_HANDOFF_HTML),
                    "Critical input suggestions": str(DEFAULT_CRITICAL_INPUT_SUGGESTIONS_JSON),
                    "Critical input questionnaire": str(DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_JSON),
                    "Critical input questionnaire HTML": str(DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_HTML),
                    "Critical input preflight": str(DEFAULT_CRITICAL_INPUT_PREFLIGHT_JSON),
                    "Critical input preflight HTML": str(DEFAULT_CRITICAL_INPUT_PREFLIGHT_HTML),
                    "Critical input impact": str(DEFAULT_CRITICAL_INPUT_IMPACT_JSON),
                    "Critical input impact HTML": str(DEFAULT_CRITICAL_INPUT_IMPACT_HTML),
                }
            ),
            synthetic_browser_execution=_load_optional_json(str(DEFAULT_SYNTHETIC_BROWSER_EXEC_JSON)),
            fake_learning_probe=_load_optional_json(str(DEFAULT_FAKE_LEARNING_PROBE_JSON)),
            fake_critical_input_probe=_load_optional_json(str(DEFAULT_FAKE_CRITICAL_INPUT_PROBE_JSON)),
            fake_position_rehearsal=_load_optional_json(str(DEFAULT_FAKE_POSITION_REHEARSAL_JSON)),
            goal_readiness_audit=goal,
            critical_input_suggestions=_load_optional_json(str(DEFAULT_CRITICAL_INPUT_SUGGESTIONS_JSON)),
            critical_input_questionnaire=_load_optional_json(str(DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_JSON)),
            critical_input_preflight=_load_optional_json(str(DEFAULT_CRITICAL_INPUT_PREFLIGHT_JSON)),
            critical_input_impact=_load_optional_json(str(DEFAULT_CRITICAL_INPUT_IMPACT_JSON)),
            autofill_batch=_load_optional_json(str(DEFAULT_AUTOFILL_BATCH_JSON)),
            automation_handoff=automation_handoff,
            learning_approval_pack=approval_pack,
            answer_memory=_load_optional_json(str(DEFAULT_MEMORY)),
            closed_jobs=_load_optional_json(str(DEFAULT_CLOSED_JOBS)),
        )
    return {
        "refreshed": [
            "gaps",
            "readiness",
            "coverage-gate",
            "critical-inputs-status",
            "critical-input-suggestions",
            "critical-inputs-questionnaire",
            "critical-inputs-impact",
            "autofill-batch",
            "goal-audit",
            "automation-handoff",
            "export-questions",
        ],
        "goal_status": goal.get("status"),
        "goal_complete": bool(goal.get("goal_complete")),
        "blocking_prompts": gaps.get("blocking_prompt_count", 0),
        "critical_waiting": (critical_status.get("summary") or {}).get("waiting_count", 0),
    }


def _question_export_source_artifacts(paths: dict[str, str]) -> list[dict[str, object]]:
    artifacts: list[dict[str, object]] = []
    for name, path_value in paths.items():
        path = Path(path_value)
        exists = path.exists()
        stat = path.stat() if exists else None
        artifacts.append(
            {
                "name": name,
                "path": str(path.resolve()),
                "exists": exists,
                "size_bytes": stat.st_size if stat else 0,
                "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
                if stat
                else "",
            }
        )
    return artifacts


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
