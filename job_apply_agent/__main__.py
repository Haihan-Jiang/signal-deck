from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .core import (
    add_synthetic_answers_for_blockers,
    attach_final_answer_blocker_notification_result,
    apply_critical_input_answers,
    apply_learning_task_answers,
    build_answer_gap_report,
    build_application_draft,
    build_application_research,
    build_final_answer_intake_update,
    build_final_answer_intake_template,
    build_final_answer_reply_intake,
    build_position_readiness_report,
    build_synthetic_learning_state,
    final_answer_fake_marker_rows_from_updates,
    final_answer_reply_text_from_file,
    import_candidate_observations,
    load_candidate_rows,
    learn_answers,
    load_answer_memory,
    load_closed_jobs,
    load_jobs,
    load_profile,
    load_submissions_jsonl,
    notify_telegram_for_final_answer_blockers,
    notify_telegram_for_submissions,
    open_apply_urls_in_browser,
    record_closed_job,
    render_final_answer_blocker_report_html,
    render_final_answer_blocker_report_markdown,
    render_critical_input_answer_workflow_markdown,
    render_final_answer_intake_template_html,
    refresh_closed_jobs_from_live_pages,
    run_pipeline,
    save_final_answer_intake_payload,
    unresolved_final_answer_aliases_from_blocker_report,
    write_answer_gap_report,
    write_apply_run_audit,
    write_apply_queue_autofill_packet,
    write_apply_queue_handoff,
    write_apply_queue_readiness,
    write_application_playbook,
    write_application_research_report,
    write_automation_handoff_report,
    write_autofill_batch_plan,
    write_browser_action_manifest,
    write_browser_review_queue_audit,
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
    write_critical_input_unblocker_final_update,
    write_critical_input_unblocker_packet,
    write_critical_input_updates_readiness,
    write_form_fill_plan,
    write_fake_learning_probe,
    write_fake_critical_input_probe,
    write_fake_position_rehearsal,
    write_final_answer_intake_template,
    write_final_answer_intake_update,
    write_final_answer_blocker_report,
    write_final_answer_revision_user_input_file,
    write_final_answer_user_input_file,
    write_final_answer_reply_intake,
    build_synthetic_final_answer_reply_text,
    build_synthetic_unblocker_compact_updates,
    write_goal_readiness_audit,
    write_critical_input_suggestion_packet,
    write_learning_approval_pack,
    write_learning_task_template,
    write_critical_input_answer_template,
    write_critical_input_status_report,
    write_pre_submit_review,
    write_question_export,
    write_position_readiness_report,
    write_platform_question_playbook,
    write_position_execution_audit,
    write_research_coverage_gate,
    write_selected_final_answer_dependency_report,
    write_synthetic_unblocker_proof,
    write_submission_safety_audit,
    write_synthetic_apply_execution,
    write_synthetic_application_simulation,
    write_synthetic_browser_action_execution,
)


DEFAULT_PROFILE = Path(__file__).with_name("sample_profile.json")
DEFAULT_JOBS = Path(__file__).with_name("sample_jobs.json")
DEFAULT_OUTBOX = Path(__file__).with_name("outbox") / "dry_run_submissions.jsonl"
DEFAULT_MEMORY = Path(__file__).with_name("outbox") / "answer_memory.json"
DEFAULT_REVIEW_LOG = Path(__file__).with_name("outbox") / "browser_review_queue.jsonl"
DEFAULT_REVIEW_QUEUE_AUDIT_JSON = Path(__file__).with_name("outbox") / "browser_review_queue_audit_latest.json"
DEFAULT_REVIEW_QUEUE_AUDIT_MARKDOWN = Path(__file__).with_name("outbox") / "browser_review_queue_audit_latest.md"
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
DEFAULT_APPLY_QUEUE_JSON = Path(__file__).with_name("outbox") / "apply_queue_readiness_latest.json"
DEFAULT_APPLY_QUEUE_MARKDOWN = Path(__file__).with_name("outbox") / "apply_queue_readiness_latest.md"
DEFAULT_APPLY_QUEUE_HTML = Path(__file__).with_name("outbox") / "apply_queue_readiness_latest.html"
DEFAULT_APPLY_QUEUE_LIVE_CHECK_JOBS = Path(__file__).with_name("outbox") / "apply_queue_live_check_jobs_latest.json"
DEFAULT_APPLY_QUEUE_HANDOFF_JSON = Path(__file__).with_name("outbox") / "apply_queue_handoff_latest.json"
DEFAULT_APPLY_QUEUE_HANDOFF_MARKDOWN = Path(__file__).with_name("outbox") / "apply_queue_handoff_latest.md"
DEFAULT_APPLY_QUEUE_HANDOFF_HTML = Path(__file__).with_name("outbox") / "apply_queue_handoff_latest.html"
DEFAULT_APPLY_QUEUE_OPEN_READY_JOBS = Path(__file__).with_name("outbox") / "apply_queue_open_ready_jobs_latest.json"
DEFAULT_APPLY_QUEUE_MANUAL_LIVE_CHECK_JSON = (
    Path(__file__).with_name("outbox") / "apply_queue_manual_live_check_latest.json"
)
DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_JSON = (
    Path(__file__).with_name("outbox") / "apply_queue_autofill_packet_latest.json"
)
DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_MARKDOWN = (
    Path(__file__).with_name("outbox") / "apply_queue_autofill_packet_latest.md"
)
DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_HTML = (
    Path(__file__).with_name("outbox") / "apply_queue_autofill_packet_latest.html"
)
DEFAULT_APPLY_QUEUE_REFRESH_JSON = Path(__file__).with_name("outbox") / "apply_queue_refresh_latest.json"
DEFAULT_APPLY_QUEUE_REFRESH_MARKDOWN = Path(__file__).with_name("outbox") / "apply_queue_refresh_latest.md"
DEFAULT_AUTOMATION_HANDOFF_JSON = Path(__file__).with_name("outbox") / "automation_handoff_latest.json"
DEFAULT_AUTOMATION_HANDOFF_MARKDOWN = Path(__file__).with_name("outbox") / "automation_handoff_latest.md"
DEFAULT_AUTOMATION_HANDOFF_HTML = Path(__file__).with_name("outbox") / "automation_handoff_latest.html"
DEFAULT_POST_ANSWER_PIPELINE_JSON = Path(__file__).with_name("outbox") / "post_answer_pipeline_latest.json"
DEFAULT_POST_ANSWER_PIPELINE_MARKDOWN = Path(__file__).with_name("outbox") / "post_answer_pipeline_latest.md"
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
DEFAULT_CRITICAL_INPUT_UPDATES_READINESS_JSON = (
    Path(__file__).with_name("outbox") / "critical_input_updates_readiness_latest.json"
)
DEFAULT_CRITICAL_INPUT_UPDATES_READINESS_MARKDOWN = (
    Path(__file__).with_name("outbox") / "critical_input_updates_readiness_latest.md"
)
DEFAULT_CRITICAL_INPUT_IMPACT_JSON = Path(__file__).with_name("outbox") / "critical_input_impact_latest.json"
DEFAULT_CRITICAL_INPUT_IMPACT_MARKDOWN = Path(__file__).with_name("outbox") / "critical_input_impact_latest.md"
DEFAULT_CRITICAL_INPUT_IMPACT_HTML = Path(__file__).with_name("outbox") / "critical_input_impact_latest.html"
DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_JSON = Path(__file__).with_name("outbox") / "critical_input_questionnaire_latest.json"
DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_MARKDOWN = Path(__file__).with_name("outbox") / "critical_input_questionnaire_latest.md"
DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_HTML = Path(__file__).with_name("outbox") / "critical_input_questionnaire_latest.html"
DEFAULT_CRITICAL_INPUT_UNBLOCKERS_JSON = Path(__file__).with_name("outbox") / "critical_input_unblockers_latest.json"
DEFAULT_CRITICAL_INPUT_UNBLOCKERS_MARKDOWN = Path(__file__).with_name("outbox") / "critical_input_unblockers_latest.md"
DEFAULT_CRITICAL_INPUT_UNBLOCKERS_HTML = Path(__file__).with_name("outbox") / "critical_input_unblockers_latest.html"
DEFAULT_CRITICAL_INPUT_UNBLOCKERS_UPDATES_JSON = (
    Path(__file__).with_name("outbox") / "critical_input_unblockers_updates_template.json"
)
DEFAULT_CRITICAL_INPUT_FULL_UPDATES_JSON = (
    Path(__file__).with_name("outbox") / "critical_input_full_updates_template.json"
)
DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_JSON = (
    Path(__file__).with_name("outbox") / "critical_input_confirmed_updates_latest.json"
)
DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_REPORT_JSON = (
    Path(__file__).with_name("outbox") / "critical_input_confirmed_updates_report_latest.json"
)
DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_REPORT_MARKDOWN = (
    Path(__file__).with_name("outbox") / "critical_input_confirmed_updates_report_latest.md"
)
DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_JSON = (
    Path(__file__).with_name("outbox") / "final_answer_intake_template_latest.json"
)
DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_MARKDOWN = (
    Path(__file__).with_name("outbox") / "final_answer_intake_template_latest.md"
)
DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_HTML = (
    Path(__file__).with_name("outbox") / "final_answer_intake_template_latest.html"
)
DEFAULT_FINAL_ANSWER_INTAKE_REPORT_JSON = (
    Path(__file__).with_name("outbox") / "final_answer_intake_update_latest.json"
)
DEFAULT_FINAL_ANSWER_INTAKE_REPORT_MARKDOWN = (
    Path(__file__).with_name("outbox") / "final_answer_intake_update_latest.md"
)
DEFAULT_FINAL_ANSWER_BLOCKERS_JSON = (
    Path(__file__).with_name("outbox") / "final_answer_blockers_latest.json"
)
DEFAULT_FINAL_ANSWER_BLOCKERS_MARKDOWN = (
    Path(__file__).with_name("outbox") / "final_answer_blockers_latest.md"
)
DEFAULT_FINAL_ANSWER_BLOCKERS_HTML = (
    Path(__file__).with_name("outbox") / "final_answer_blockers_latest.html"
)
DEFAULT_FINAL_ANSWER_BLOCKERS_XLSX = (
    Path(__file__).with_name("outbox") / "final_answer_blockers_latest.xlsx"
)
DEFAULT_FINAL_ANSWER_REPLY_TEMPLATE_TEXT = (
    Path(__file__).with_name("outbox") / "final_answer_reply_template_latest.txt"
)
DEFAULT_FINAL_ANSWER_USER_INPUT_TEXT = (
    Path(__file__).with_name("outbox") / "final_answer_user_input_needed.txt"
)
DEFAULT_FINAL_ANSWER_USER_INPUT_XLSX = (
    Path(__file__).with_name("outbox") / "final_answer_user_input_needed.xlsx"
)
DEFAULT_FINAL_ANSWER_AUTOPILOT_JSON = (
    Path(__file__).with_name("outbox") / "final_answer_autopilot_latest.json"
)
DEFAULT_FINAL_ANSWER_AUTOPILOT_MARKDOWN = (
    Path(__file__).with_name("outbox") / "final_answer_autopilot_latest.md"
)
DEFAULT_FINAL_ANSWER_REVISION_MARKDOWN = (
    Path(__file__).with_name("outbox") / "final_answer_revision_needed.md"
)
DEFAULT_FINAL_ANSWER_REVISION_USER_INPUT_TEXT = (
    Path(__file__).with_name("outbox") / "final_answer_revision_user_input_needed.txt"
)
DEFAULT_FINAL_ANSWER_REVISION_USER_INPUT_XLSX = (
    Path(__file__).with_name("outbox") / "final_answer_revision_user_input_needed.xlsx"
)
DEFAULT_FINAL_ANSWER_REPLY_JSON = (
    Path(__file__).with_name("outbox") / "final_answer_reply_intake_latest.json"
)
DEFAULT_FINAL_ANSWER_REPLY_MARKDOWN = (
    Path(__file__).with_name("outbox") / "final_answer_reply_intake_latest.md"
)
DEFAULT_FINAL_ANSWER_REPLY_PAYLOAD_JSON = (
    Path(__file__).with_name("outbox") / "final_answer_reply_payload_latest.json"
)
DEFAULT_FINAL_ANSWER_REPLY_SYNTHETIC_JSON = (
    Path(__file__).with_name("outbox") / "final_answer_reply_synthetic_intake_latest.json"
)
DEFAULT_FINAL_ANSWER_REPLY_SYNTHETIC_MARKDOWN = (
    Path(__file__).with_name("outbox") / "final_answer_reply_synthetic_intake_latest.md"
)
DEFAULT_FINAL_ANSWER_REPLY_SYNTHETIC_PAYLOAD_JSON = (
    Path(__file__).with_name("outbox") / "final_answer_reply_synthetic_payload_latest.json"
)
DEFAULT_FINAL_ANSWER_REPLY_SYNTHETIC_INTAKE_REPORT_JSON = (
    Path(__file__).with_name("outbox") / "final_answer_reply_synthetic_intake_report_latest.json"
)
DEFAULT_FINAL_ANSWER_REPLY_SYNTHETIC_INTAKE_REPORT_MARKDOWN = (
    Path(__file__).with_name("outbox") / "final_answer_reply_synthetic_intake_report_latest.md"
)
DEFAULT_POST_ANSWER_SYNTHETIC_COMPACT_UPDATES_JSON = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_unblockers_updates_latest.json"
)
DEFAULT_POST_ANSWER_SYNTHETIC_CONFIRMED_UPDATES_JSON = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_confirmed_updates_latest.json"
)
DEFAULT_POST_ANSWER_SYNTHETIC_CONFIRMED_UPDATES_REPORT_JSON = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_confirmed_updates_report_latest.json"
)
DEFAULT_POST_ANSWER_SYNTHETIC_CONFIRMED_UPDATES_REPORT_MARKDOWN = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_confirmed_updates_report_latest.md"
)
DEFAULT_POST_ANSWER_SYNTHETIC_ANSWERS_JSON = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_critical_input_answers_latest.json"
)
DEFAULT_POST_ANSWER_SYNTHETIC_ANSWERS_MARKDOWN = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_critical_input_answers_latest.md"
)
DEFAULT_POST_ANSWER_SYNTHETIC_PROFILE_JSON = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_profile_latest.json"
)
DEFAULT_POST_ANSWER_SYNTHETIC_MEMORY_JSON = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_answer_memory_latest.json"
)
DEFAULT_POST_ANSWER_SYNTHETIC_WORKFLOW_JSON = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_workflow_latest.json"
)
DEFAULT_POST_ANSWER_SYNTHETIC_WORKFLOW_MARKDOWN = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_workflow_latest.md"
)
DEFAULT_POST_ANSWER_SYNTHETIC_UPDATE_JSON = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_update_latest.json"
)
DEFAULT_POST_ANSWER_SYNTHETIC_UPDATE_MARKDOWN = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_update_latest.md"
)
DEFAULT_POST_ANSWER_SYNTHETIC_STATUS_JSON = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_status_latest.json"
)
DEFAULT_POST_ANSWER_SYNTHETIC_STATUS_MARKDOWN = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_status_latest.md"
)
DEFAULT_POST_ANSWER_SYNTHETIC_UPDATES_READINESS_JSON = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_updates_readiness_latest.json"
)
DEFAULT_POST_ANSWER_SYNTHETIC_UPDATES_READINESS_MARKDOWN = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_updates_readiness_latest.md"
)
DEFAULT_POST_ANSWER_SYNTHETIC_APPLY_QUEUE_JSON = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_apply_queue_latest.json"
)
DEFAULT_POST_ANSWER_SYNTHETIC_APPLY_QUEUE_MARKDOWN = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_apply_queue_latest.md"
)
DEFAULT_POST_ANSWER_SYNTHETIC_APPLY_QUEUE_HTML = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_apply_queue_latest.html"
)
DEFAULT_POST_ANSWER_SYNTHETIC_APPLY_QUEUE_LIVE_CHECK_JOBS = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_apply_queue_live_check_jobs_latest.json"
)
DEFAULT_POST_ANSWER_SYNTHETIC_HANDOFF_JSON = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_handoff_latest.json"
)
DEFAULT_POST_ANSWER_SYNTHETIC_HANDOFF_MARKDOWN = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_handoff_latest.md"
)
DEFAULT_POST_ANSWER_SYNTHETIC_HANDOFF_HTML = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_handoff_latest.html"
)
DEFAULT_POST_ANSWER_SYNTHETIC_OPEN_READY_JOBS = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_open_ready_jobs_latest.json"
)
DEFAULT_POST_ANSWER_SYNTHETIC_AUTOFILL_PACKET_JSON = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_autofill_packet_latest.json"
)
DEFAULT_POST_ANSWER_SYNTHETIC_AUTOFILL_PACKET_MARKDOWN = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_autofill_packet_latest.md"
)
DEFAULT_POST_ANSWER_SYNTHETIC_AUTOFILL_PACKET_HTML = (
    Path(__file__).with_name("outbox") / "post_answer_pipeline_synthetic_autofill_packet_latest.html"
)
DEFAULT_SYNTHETIC_UNBLOCKER_PROOF_JSON = Path(__file__).with_name("outbox") / "synthetic_unblocker_proof_latest.json"
DEFAULT_SYNTHETIC_UNBLOCKER_PROOF_MARKDOWN = (
    Path(__file__).with_name("outbox") / "synthetic_unblocker_proof_latest.md"
)
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
DEFAULT_PLATFORM_QUESTION_PLAYBOOK_JSON = (
    Path(__file__).with_name("outbox") / "platform_question_playbook_latest.json"
)
DEFAULT_PLATFORM_QUESTION_PLAYBOOK_MARKDOWN = (
    Path(__file__).with_name("outbox") / "platform_question_playbook_latest.md"
)
DEFAULT_PLATFORM_QUESTION_PLAYBOOK_HTML = (
    Path(__file__).with_name("outbox") / "platform_question_playbook_latest.html"
)
DEFAULT_GOAL_AUDIT_JSON = Path(__file__).with_name("outbox") / "goal_readiness_audit_latest.json"
DEFAULT_GOAL_AUDIT_MARKDOWN = Path(__file__).with_name("outbox") / "goal_readiness_audit_latest.md"
DEFAULT_POSITION_EXECUTION_AUDIT_JSON = (
    Path(__file__).with_name("outbox") / "position_execution_audit_latest.json"
)
DEFAULT_POSITION_EXECUTION_AUDIT_MARKDOWN = (
    Path(__file__).with_name("outbox") / "position_execution_audit_latest.md"
)
DEFAULT_POSITION_EXECUTION_AUDIT_HTML = (
    Path(__file__).with_name("outbox") / "position_execution_audit_latest.html"
)
DEFAULT_SELECTED_ANSWER_DEPENDENCIES_JSON = (
    Path(__file__).with_name("outbox") / "selected_answer_dependencies_latest.json"
)
DEFAULT_SELECTED_ANSWER_DEPENDENCIES_MARKDOWN = (
    Path(__file__).with_name("outbox") / "selected_answer_dependencies_latest.md"
)
DEFAULT_SELECTED_ANSWER_DEPENDENCIES_HTML = (
    Path(__file__).with_name("outbox") / "selected_answer_dependencies_latest.html"
)
DEFAULT_SUBMISSION_SAFETY_AUDIT_JSON = (
    Path(__file__).with_name("outbox") / "submission_safety_audit_latest.json"
)
DEFAULT_SUBMISSION_SAFETY_AUDIT_MARKDOWN = (
    Path(__file__).with_name("outbox") / "submission_safety_audit_latest.md"
)
DEFAULT_PERSONAL_PROFILE = Path(__file__).with_name("outbox") / "alan_jiang_profile.json"


def _live_skip_reasons_from_checks(live_result: dict[str, object] | None) -> dict[str, str]:
    if not isinstance(live_result, dict):
        return {}
    skip_reasons: dict[str, str] = {}
    for check in live_result.get("checks") or []:
        if not isinstance(check, dict) or not check.get("skip_for_open"):
            continue
        key = str(check.get("key") or "").strip()
        if not key:
            continue
        skip_reasons[key] = str(check.get("reason") or "live page identity was not verified")
    return skip_reasons


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

    review_queue_audit_parser = subparsers.add_parser(
        "review-queue-audit",
        help="audit browser review queue JSONL for sparse non-sensitive records",
    )
    review_queue_audit_parser.add_argument("--review-log", default=str(DEFAULT_REVIEW_LOG))
    review_queue_audit_parser.add_argument("--json-output", default=str(DEFAULT_REVIEW_QUEUE_AUDIT_JSON))
    review_queue_audit_parser.add_argument("--markdown-output", default=str(DEFAULT_REVIEW_QUEUE_AUDIT_MARKDOWN))
    review_queue_audit_parser.add_argument(
        "--fail-on-unsafe",
        action="store_true",
        help="exit non-zero if the review queue contains sensitive fields, answers, tokens, tracking URLs, or submitted rows",
    )

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
    autofill_batch_parser.add_argument(
        "--avoid-unresolved-final-answers",
        action="store_true",
        help="exclude positions whose prompts require currently unresolved final-answer aliases",
    )
    autofill_batch_parser.add_argument("--final-answer-blockers-json", default=str(DEFAULT_FINAL_ANSWER_BLOCKERS_JSON))
    autofill_batch_parser.add_argument("--json-output", default=str(DEFAULT_AUTOFILL_BATCH_JSON))
    autofill_batch_parser.add_argument("--markdown-output", default=str(DEFAULT_AUTOFILL_BATCH_MARKDOWN))
    autofill_batch_parser.add_argument("--html-output", default=str(DEFAULT_AUTOFILL_BATCH_HTML))

    apply_queue_parser = subparsers.add_parser(
        "apply-queue",
        help="turn the selected 100-position autofill batch into a go/no-go queue with live-check jobs",
    )
    apply_queue_parser.add_argument("--autofill-batch-json", default=str(DEFAULT_AUTOFILL_BATCH_JSON))
    apply_queue_parser.add_argument(
        "--critical-input-updates-readiness-json",
        default=str(DEFAULT_CRITICAL_INPUT_UPDATES_READINESS_JSON),
    )
    apply_queue_parser.add_argument("--goal-audit-json", default=str(DEFAULT_GOAL_AUDIT_JSON))
    apply_queue_parser.add_argument("--closed-jobs-json", default=str(DEFAULT_CLOSED_JOBS))
    apply_queue_parser.add_argument("--json-output", default=str(DEFAULT_APPLY_QUEUE_JSON))
    apply_queue_parser.add_argument("--markdown-output", default=str(DEFAULT_APPLY_QUEUE_MARKDOWN))
    apply_queue_parser.add_argument("--html-output", default=str(DEFAULT_APPLY_QUEUE_HTML))
    apply_queue_parser.add_argument("--live-check-jobs-output", default=str(DEFAULT_APPLY_QUEUE_LIVE_CHECK_JOBS))

    apply_queue_handoff_parser = subparsers.add_parser(
        "apply-queue-handoff",
        help="combine apply queue and closed preflight into an open-ready supervised handoff",
    )
    apply_queue_handoff_parser.add_argument("--apply-queue-json", default=str(DEFAULT_APPLY_QUEUE_JSON))
    apply_queue_handoff_parser.add_argument("--closed-preflight-json", default=str(DEFAULT_CLOSED_PREFLIGHT_JSON))
    apply_queue_handoff_parser.add_argument("--json-output", default=str(DEFAULT_APPLY_QUEUE_HANDOFF_JSON))
    apply_queue_handoff_parser.add_argument("--markdown-output", default=str(DEFAULT_APPLY_QUEUE_HANDOFF_MARKDOWN))
    apply_queue_handoff_parser.add_argument("--html-output", default=str(DEFAULT_APPLY_QUEUE_HANDOFF_HTML))
    apply_queue_handoff_parser.add_argument(
        "--open-ready-jobs-output",
        default=str(DEFAULT_APPLY_QUEUE_OPEN_READY_JOBS),
    )
    apply_queue_handoff_parser.add_argument(
        "--supplemental-closed-preflight-json",
        action="append",
        default=[],
        help="additional closed-preflight JSON to merge, with open/closed checks overriding earlier uncertainty",
    )
    apply_queue_handoff_parser.add_argument(
        "--skip-default-supplemental-preflight",
        action="store_true",
        help="do not auto-merge apply_queue_manual_live_check_latest.json when present",
    )
    apply_queue_handoff_parser.add_argument("--open-browser", action="store_true")
    apply_queue_handoff_parser.add_argument("--open-limit", type=int, default=5)
    apply_queue_handoff_parser.add_argument("--review-log", default=str(DEFAULT_REVIEW_LOG))

    apply_queue_autofill_parser = subparsers.add_parser(
        "apply-queue-autofill-packet",
        help="build the supervised browser-action packet for the live-checked apply queue",
    )
    apply_queue_autofill_parser.add_argument("--research-json", default=str(DEFAULT_RESEARCH_JSON))
    apply_queue_autofill_parser.add_argument("--apply-queue-handoff-json", default=str(DEFAULT_APPLY_QUEUE_HANDOFF_JSON))
    apply_queue_autofill_parser.add_argument(
        "--profile",
        default=str(DEFAULT_PERSONAL_PROFILE if DEFAULT_PERSONAL_PROFILE.exists() else DEFAULT_PROFILE),
    )
    apply_queue_autofill_parser.add_argument("--memory", default=str(DEFAULT_MEMORY))
    apply_queue_autofill_parser.add_argument("--closed-jobs", default=str(DEFAULT_CLOSED_JOBS))
    apply_queue_autofill_parser.add_argument("--limit", type=int, default=100)
    apply_queue_autofill_parser.add_argument("--target-count", type=int, default=100)
    apply_queue_autofill_parser.add_argument("--include-values", action="store_true")
    apply_queue_autofill_parser.add_argument(
        "--omit-manifest-actions",
        action="store_true",
        help="write only per-position summaries, not browser action details",
    )
    apply_queue_autofill_parser.add_argument("--json-output", default=str(DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_JSON))
    apply_queue_autofill_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_MARKDOWN),
    )
    apply_queue_autofill_parser.add_argument("--html-output", default=str(DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_HTML))

    refresh_apply_queue_parser = subparsers.add_parser(
        "refresh-apply-queue",
        help="rebuild, live-check, and top up the 100-position supervised apply queue",
    )
    refresh_apply_queue_parser.add_argument("--max-rounds", type=int, default=2)
    refresh_apply_queue_parser.add_argument("--live-check-limit", type=int, default=100)
    refresh_apply_queue_parser.add_argument("--live-check-timeout", type=float, default=15.0)
    refresh_apply_queue_parser.add_argument(
        "--skip-live-check",
        action="store_true",
        help="reuse the latest closed-preflight artifact instead of fetching live pages",
    )
    refresh_apply_queue_parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="rebuild the autofill batch before the first live-check round",
    )
    refresh_apply_queue_parser.add_argument("--include-values", action="store_true")
    refresh_apply_queue_parser.add_argument("--json-output", default=str(DEFAULT_APPLY_QUEUE_REFRESH_JSON))
    refresh_apply_queue_parser.add_argument("--markdown-output", default=str(DEFAULT_APPLY_QUEUE_REFRESH_MARKDOWN))

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
    automation_handoff_parser.add_argument(
        "--critical-input-updates-readiness-json",
        default=str(DEFAULT_CRITICAL_INPUT_UPDATES_READINESS_JSON),
    )
    automation_handoff_parser.add_argument(
        "--final-answer-intake-template-json",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_JSON),
    )
    automation_handoff_parser.add_argument(
        "--final-answer-intake-template-html",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_HTML),
    )
    automation_handoff_parser.add_argument(
        "--final-answer-intake-report-json",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_REPORT_JSON),
    )
    automation_handoff_parser.add_argument(
        "--final-answer-blockers-json",
        default=str(DEFAULT_FINAL_ANSWER_BLOCKERS_JSON),
    )
    automation_handoff_parser.add_argument(
        "--final-answer-blockers-markdown",
        default=str(DEFAULT_FINAL_ANSWER_BLOCKERS_MARKDOWN),
    )
    automation_handoff_parser.add_argument("--autofill-batch-json", default=str(DEFAULT_AUTOFILL_BATCH_JSON))
    automation_handoff_parser.add_argument("--apply-queue-handoff-json", default=str(DEFAULT_APPLY_QUEUE_HANDOFF_JSON))
    automation_handoff_parser.add_argument(
        "--apply-queue-autofill-packet-json",
        default=str(DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_JSON),
    )
    automation_handoff_parser.add_argument("--apply-queue-refresh-json", default=str(DEFAULT_APPLY_QUEUE_REFRESH_JSON))
    automation_handoff_parser.add_argument(
        "--position-execution-audit-json",
        default=str(DEFAULT_POSITION_EXECUTION_AUDIT_JSON),
    )
    automation_handoff_parser.add_argument(
        "--position-execution-audit-html",
        default=str(DEFAULT_POSITION_EXECUTION_AUDIT_HTML),
    )
    automation_handoff_parser.add_argument(
        "--selected-answer-dependencies-json",
        default=str(DEFAULT_SELECTED_ANSWER_DEPENDENCIES_JSON),
    )
    automation_handoff_parser.add_argument(
        "--selected-answer-dependencies-markdown",
        default=str(DEFAULT_SELECTED_ANSWER_DEPENDENCIES_MARKDOWN),
    )
    automation_handoff_parser.add_argument(
        "--selected-answer-dependencies-html",
        default=str(DEFAULT_SELECTED_ANSWER_DEPENDENCIES_HTML),
    )
    automation_handoff_parser.add_argument(
        "--review-queue-audit-json",
        default=str(DEFAULT_REVIEW_QUEUE_AUDIT_JSON),
    )
    automation_handoff_parser.add_argument(
        "--review-queue-audit-markdown",
        default=str(DEFAULT_REVIEW_QUEUE_AUDIT_MARKDOWN),
    )
    automation_handoff_parser.add_argument(
        "--submission-safety-audit-json",
        default=str(DEFAULT_SUBMISSION_SAFETY_AUDIT_JSON),
    )
    automation_handoff_parser.add_argument(
        "--submission-safety-audit-markdown",
        default=str(DEFAULT_SUBMISSION_SAFETY_AUDIT_MARKDOWN),
    )
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

    critical_inputs_unblockers_parser = subparsers.add_parser(
        "critical-input-unblockers",
        help="write a focused form for only critical inputs with no draft suggestion",
    )
    critical_inputs_unblockers_parser.add_argument(
        "--suggestions",
        default=str(DEFAULT_CRITICAL_INPUT_SUGGESTIONS_JSON),
    )
    critical_inputs_unblockers_parser.add_argument(
        "--impact",
        default=str(DEFAULT_CRITICAL_INPUT_IMPACT_JSON),
    )
    critical_inputs_unblockers_parser.add_argument("--json-output", default=str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_JSON))
    critical_inputs_unblockers_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_MARKDOWN),
    )
    critical_inputs_unblockers_parser.add_argument("--html-output", default=str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_HTML))
    critical_inputs_unblockers_parser.add_argument(
        "--updates-template-output",
        default=str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_UPDATES_JSON),
    )
    critical_inputs_unblockers_parser.add_argument(
        "--full-updates-template-output",
        default=str(DEFAULT_CRITICAL_INPUT_FULL_UPDATES_JSON),
    )

    critical_inputs_unblockers_finalize_parser = subparsers.add_parser(
        "critical-input-unblockers-finalize",
        help="merge the six confirmed unblocker answers into the full one-shot critical-input updates file",
    )
    critical_inputs_unblockers_finalize_parser.add_argument(
        "--compact-updates",
        default=str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_UPDATES_JSON),
    )
    critical_inputs_unblockers_finalize_parser.add_argument(
        "--full-template",
        default=str(DEFAULT_CRITICAL_INPUT_FULL_UPDATES_JSON),
    )
    critical_inputs_unblockers_finalize_parser.add_argument(
        "--unblockers",
        default=str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_JSON),
    )
    critical_inputs_unblockers_finalize_parser.add_argument(
        "--updates-output",
        default=str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_JSON),
    )
    critical_inputs_unblockers_finalize_parser.add_argument(
        "--json-output",
        default=str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_REPORT_JSON),
    )
    critical_inputs_unblockers_finalize_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_REPORT_MARKDOWN),
    )
    critical_inputs_unblockers_finalize_parser.add_argument(
        "--fail-on-not-ready",
        action="store_true",
        help="exit non-zero when any final answer is blank, unconfirmed, or unknown",
    )

    final_answer_intake_parser = subparsers.add_parser(
        "final-answer-intake",
        help="convert a simple six-answer intake JSON into post-answer compact updates",
    )
    final_answer_intake_parser.add_argument(
        "--unblockers",
        default=str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_JSON),
    )
    final_answer_intake_parser.add_argument(
        "--answers",
        help="JSON with an answers object keyed by aliases from the generated template",
    )
    final_answer_intake_parser.add_argument(
        "--template-output",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_JSON),
    )
    final_answer_intake_parser.add_argument(
        "--template-markdown-output",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_MARKDOWN),
    )
    final_answer_intake_parser.add_argument(
        "--template-html-output",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_HTML),
    )
    final_answer_intake_parser.add_argument(
        "--compact-updates-output",
        default=str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_UPDATES_JSON),
    )
    final_answer_intake_parser.add_argument(
        "--full-template",
        default=str(DEFAULT_CRITICAL_INPUT_FULL_UPDATES_JSON),
    )
    final_answer_intake_parser.add_argument(
        "--confirmed-updates-output",
        default=str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_JSON),
    )
    final_answer_intake_parser.add_argument(
        "--confirmed-report-json-output",
        default=str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_REPORT_JSON),
    )
    final_answer_intake_parser.add_argument(
        "--confirmed-report-markdown-output",
        default=str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_REPORT_MARKDOWN),
    )
    final_answer_intake_parser.add_argument(
        "--json-output",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_REPORT_JSON),
    )
    final_answer_intake_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_REPORT_MARKDOWN),
    )
    final_answer_intake_parser.add_argument(
        "--confirm-high-risk",
        action="store_true",
        help="treat all supplied high-risk answer text as explicitly user-confirmed",
    )
    final_answer_intake_parser.add_argument(
        "--finalize",
        action="store_true",
        help="also merge compact answers into the full confirmed updates file",
    )
    final_answer_intake_parser.add_argument(
        "--fail-on-not-ready",
        action="store_true",
        help="exit non-zero when answers are missing, high-risk confirmations are absent, or unknown keys exist",
    )

    final_answer_intake_server_parser = subparsers.add_parser(
        "final-answer-intake-server",
        help="serve a local form that saves and validates the six final answers",
    )
    final_answer_intake_server_parser.add_argument("--unblockers", default=str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_JSON))
    final_answer_intake_server_parser.add_argument("--template-output", default=str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_JSON))
    final_answer_intake_server_parser.add_argument(
        "--template-markdown-output",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_MARKDOWN),
    )
    final_answer_intake_server_parser.add_argument(
        "--template-html-output",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_HTML),
    )
    final_answer_intake_server_parser.add_argument(
        "--compact-updates-output",
        default=str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_UPDATES_JSON),
    )
    final_answer_intake_server_parser.add_argument("--json-output", default=str(DEFAULT_FINAL_ANSWER_INTAKE_REPORT_JSON))
    final_answer_intake_server_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_REPORT_MARKDOWN),
    )
    final_answer_intake_server_parser.add_argument("--full-template", default=str(DEFAULT_CRITICAL_INPUT_FULL_UPDATES_JSON))
    final_answer_intake_server_parser.add_argument(
        "--confirmed-updates-output",
        default=str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_JSON),
    )
    final_answer_intake_server_parser.add_argument(
        "--confirmed-report-json-output",
        default=str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_REPORT_JSON),
    )
    final_answer_intake_server_parser.add_argument(
        "--confirmed-report-markdown-output",
        default=str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_REPORT_MARKDOWN),
    )
    final_answer_intake_server_parser.add_argument("--host", default="127.0.0.1")
    final_answer_intake_server_parser.add_argument("--port", type=int, default=8765)
    final_answer_intake_server_parser.add_argument("--open-browser", action="store_true")
    final_answer_intake_server_parser.add_argument("--once", action="store_true")
    final_answer_intake_server_parser.add_argument("--finalize", action="store_true")
    final_answer_intake_server_parser.add_argument("--confirm-high-risk", action="store_true")
    final_answer_intake_server_parser.add_argument(
        "--run-post-answer-pipeline",
        action="store_true",
        help="after a ready save, run post-answer-pipeline with the saved intake JSON",
    )
    final_answer_intake_server_parser.add_argument(
        "--post-answer-apply",
        action="store_true",
        help="with --run-post-answer-pipeline, write approved answers to local profile/memory",
    )
    final_answer_intake_server_parser.add_argument(
        "--post-answer-live-check",
        action="store_true",
        help="with --post-answer-apply, live-check apply pages before rebuilding the handoff",
    )
    final_answer_intake_server_parser.add_argument("--post-answer-live-check-limit", type=int, default=100)
    final_answer_intake_server_parser.add_argument("--post-answer-live-check-timeout", type=float, default=25.0)
    final_answer_intake_server_parser.add_argument(
        "--post-answer-include-values",
        action="store_true",
        help="with --post-answer-apply, include actual values in the supervised autofill packet",
    )
    final_answer_intake_server_parser.add_argument(
        "--post-answer-open-browser",
        action="store_true",
        help="with --post-answer-live-check, open the refreshed open-ready job URLs for review",
    )
    final_answer_intake_server_parser.add_argument("--post-answer-open-limit", type=int, default=100)
    final_answer_intake_server_parser.add_argument("--review-log", default=str(DEFAULT_REVIEW_LOG))
    final_answer_intake_server_parser.add_argument(
        "--post-answer-json-output",
        default=str(DEFAULT_POST_ANSWER_PIPELINE_JSON),
    )
    final_answer_intake_server_parser.add_argument(
        "--post-answer-markdown-output",
        default=str(DEFAULT_POST_ANSWER_PIPELINE_MARKDOWN),
    )

    final_answer_blockers_parser = subparsers.add_parser(
        "final-answer-blockers",
        help="write or Telegram-send a compact reminder for the final truthful answers still blocking the 100-job queue",
    )
    final_answer_blockers_parser.add_argument(
        "--template",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_JSON),
    )
    final_answer_blockers_parser.add_argument(
        "--goal-audit",
        default=str(DEFAULT_GOAL_AUDIT_JSON),
    )
    final_answer_blockers_parser.add_argument("--json-output", default=str(DEFAULT_FINAL_ANSWER_BLOCKERS_JSON))
    final_answer_blockers_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_FINAL_ANSWER_BLOCKERS_MARKDOWN),
    )
    final_answer_blockers_parser.add_argument(
        "--html-output",
        default=str(DEFAULT_FINAL_ANSWER_BLOCKERS_HTML),
    )
    final_answer_blockers_parser.add_argument(
        "--xlsx-output",
        default=str(DEFAULT_FINAL_ANSWER_BLOCKERS_XLSX),
    )
    final_answer_blockers_parser.add_argument(
        "--reply-template-output",
        default=str(DEFAULT_FINAL_ANSWER_REPLY_TEMPLATE_TEXT),
    )
    final_answer_blockers_parser.add_argument(
        "--user-input-output",
        default=str(DEFAULT_FINAL_ANSWER_USER_INPUT_TEXT),
    )
    final_answer_blockers_parser.add_argument(
        "--user-input-xlsx-output",
        default=str(DEFAULT_FINAL_ANSWER_USER_INPUT_XLSX),
    )
    final_answer_blockers_parser.add_argument("--notify-telegram", action="store_true")
    final_answer_blockers_parser.add_argument("--telegram-env", default=None)
    final_answer_blockers_parser.add_argument("--telegram-dry-run", action="store_true")
    final_answer_blockers_parser.add_argument("--limit", type=int, default=6)
    final_answer_blockers_parser.add_argument(
        "--print-minimal-reply",
        action="store_true",
        help="print only the shortest fill-in reply shape to stdout after writing reports",
    )

    final_answer_user_input_parser = subparsers.add_parser(
        "final-answer-user-input",
        help="write the shortest local fill-in file for the final truthful answers still blocking the 100-job queue",
    )
    final_answer_user_input_parser.add_argument(
        "--template",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_JSON),
    )
    final_answer_user_input_parser.add_argument(
        "--goal-audit",
        default=str(DEFAULT_GOAL_AUDIT_JSON),
    )
    final_answer_user_input_parser.add_argument(
        "--output",
        default=str(DEFAULT_FINAL_ANSWER_USER_INPUT_TEXT),
    )
    final_answer_user_input_parser.add_argument(
        "--xlsx-output",
        default=str(DEFAULT_FINAL_ANSWER_USER_INPUT_XLSX),
    )

    final_answer_revision_user_input_parser = subparsers.add_parser(
        "final-answer-revision-user-input",
        help="write a compact fill-in file for only the final-answer aliases that failed latest validation",
    )
    final_answer_revision_user_input_parser.add_argument(
        "--autopilot-json",
        default=str(DEFAULT_FINAL_ANSWER_AUTOPILOT_JSON),
    )
    final_answer_revision_user_input_parser.add_argument(
        "--template",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_JSON),
    )
    final_answer_revision_user_input_parser.add_argument(
        "--base-reply-file",
        default=None,
        help="existing filled reply file to merge before applying these revisions; defaults to the latest autopilot reply file",
    )
    final_answer_revision_user_input_parser.add_argument(
        "--output",
        default=str(DEFAULT_FINAL_ANSWER_REVISION_USER_INPUT_TEXT),
    )
    final_answer_revision_user_input_parser.add_argument(
        "--xlsx-output",
        default=str(DEFAULT_FINAL_ANSWER_REVISION_USER_INPUT_XLSX),
    )

    final_answer_reply_parser = subparsers.add_parser(
        "final-answer-reply",
        help="parse a plain-text final-answer reply into the local final-answer intake JSON and validation report",
    )
    final_answer_reply_parser.add_argument(
        "--template",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_JSON),
    )
    final_answer_reply_parser.add_argument(
        "--unblockers",
        default=str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_JSON),
    )
    final_answer_reply_parser.add_argument("--reply-text", default=None)
    final_answer_reply_parser.add_argument("--reply-file", default=None)
    final_answer_reply_parser.add_argument(
        "--reply-stdin",
        action="store_true",
        help="read filled final-answer lines from stdin",
    )
    final_answer_reply_parser.add_argument("--json-output", default=str(DEFAULT_FINAL_ANSWER_REPLY_JSON))
    final_answer_reply_parser.add_argument("--markdown-output", default=str(DEFAULT_FINAL_ANSWER_REPLY_MARKDOWN))
    final_answer_reply_parser.add_argument("--intake-output", default=str(DEFAULT_FINAL_ANSWER_REPLY_PAYLOAD_JSON))
    final_answer_reply_parser.add_argument(
        "--compact-updates-output",
        default=str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_UPDATES_JSON),
    )
    final_answer_reply_parser.add_argument("--final-answer-intake-report-json", default=str(DEFAULT_FINAL_ANSWER_INTAKE_REPORT_JSON))
    final_answer_reply_parser.add_argument(
        "--final-answer-intake-report-markdown",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_REPORT_MARKDOWN),
    )
    final_answer_reply_parser.add_argument(
        "--full-template",
        default=str(DEFAULT_CRITICAL_INPUT_FULL_UPDATES_JSON),
    )
    final_answer_reply_parser.add_argument(
        "--confirmed-updates-output",
        default=str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_JSON),
    )
    final_answer_reply_parser.add_argument(
        "--confirmed-report-json-output",
        default=str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_REPORT_JSON),
    )
    final_answer_reply_parser.add_argument(
        "--confirmed-report-markdown-output",
        default=str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_REPORT_MARKDOWN),
    )
    final_answer_reply_parser.add_argument("--confirm-high-risk", action="store_true")
    final_answer_reply_parser.add_argument("--finalize", action="store_true")
    final_answer_reply_parser.add_argument(
        "--run-post-answer-pipeline",
        action="store_true",
        help="after parsing and validation, run post-answer-pipeline using the parsed intake payload",
    )
    final_answer_reply_parser.add_argument(
        "--validate-only",
        action="store_true",
        help="parse and validate the reply without writing output files or running post-answer steps",
    )
    final_answer_reply_parser.add_argument(
        "--synthetic-rehearse-queue",
        action="store_true",
        help="parse the reply and run the 100-job queue rehearsal with fake local profile/memory only",
    )
    final_answer_reply_parser.add_argument("--post-answer-apply", action="store_true")
    final_answer_reply_parser.add_argument("--post-answer-live-check", action="store_true")
    final_answer_reply_parser.add_argument("--post-answer-live-check-limit", type=int, default=100)
    final_answer_reply_parser.add_argument("--post-answer-live-check-timeout", type=float, default=25.0)
    final_answer_reply_parser.add_argument("--post-answer-include-values", action="store_true")
    final_answer_reply_parser.add_argument("--post-answer-open-browser", action="store_true")
    final_answer_reply_parser.add_argument("--post-answer-open-limit", type=int, default=100)
    final_answer_reply_parser.add_argument("--review-log", default=str(DEFAULT_REVIEW_LOG))
    final_answer_reply_parser.add_argument("--post-answer-json-output", default=str(DEFAULT_POST_ANSWER_PIPELINE_JSON))
    final_answer_reply_parser.add_argument(
        "--post-answer-markdown-output",
        default=str(DEFAULT_POST_ANSWER_PIPELINE_MARKDOWN),
    )
    final_answer_reply_parser.add_argument("--fail-on-not-ready", action="store_true")

    final_answer_autopilot_parser = subparsers.add_parser(
        "final-answer-autopilot",
        help="watch or check the final-answer reply file and run the post-answer pipeline once it is filled",
    )
    final_answer_autopilot_parser.add_argument(
        "--reply-file",
        default=str(DEFAULT_FINAL_ANSWER_USER_INPUT_XLSX),
    )
    final_answer_autopilot_parser.add_argument(
        "--base-reply-file",
        default=None,
        help="merge this existing filled reply before --reply-file; aliases in --reply-file override the base",
    )
    final_answer_autopilot_parser.add_argument(
        "--reply-text",
        default=None,
        help="filled final-answer lines; when provided, it is used instead of --reply-file and is not stored in reports",
    )
    final_answer_autopilot_parser.add_argument(
        "--reply-stdin",
        action="store_true",
        help="read filled final-answer lines from stdin instead of --reply-file",
    )
    final_answer_autopilot_parser.add_argument(
        "--template",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_JSON),
    )
    final_answer_autopilot_parser.add_argument(
        "--unblockers",
        default=str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_JSON),
    )
    final_answer_autopilot_parser.add_argument("--watch", action="store_true")
    final_answer_autopilot_parser.add_argument("--interval", type=float, default=5.0)
    final_answer_autopilot_parser.add_argument(
        "--timeout",
        type=float,
        default=0.0,
        help="seconds to wait in watch mode; 0 waits indefinitely",
    )
    final_answer_autopilot_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate readiness and write the autopilot report without running the pipeline",
    )
    final_answer_autopilot_parser.add_argument(
        "--no-run-post-answer-pipeline",
        action="store_true",
        help="only validate the filled reply file; do not run the post-answer pipeline",
    )
    final_answer_autopilot_parser.add_argument("--apply", action="store_true")
    final_answer_autopilot_parser.add_argument("--live-check", action="store_true")
    final_answer_autopilot_parser.add_argument("--live-check-limit", type=int, default=100)
    final_answer_autopilot_parser.add_argument("--live-check-timeout", type=float, default=25.0)
    final_answer_autopilot_parser.add_argument("--include-values", action="store_true")
    final_answer_autopilot_parser.add_argument("--open-browser", action="store_true")
    final_answer_autopilot_parser.add_argument("--open-limit", type=int, default=100)
    final_answer_autopilot_parser.add_argument("--review-log", default=str(DEFAULT_REVIEW_LOG))
    final_answer_autopilot_parser.add_argument("--json-output", default=str(DEFAULT_FINAL_ANSWER_AUTOPILOT_JSON))
    final_answer_autopilot_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_FINAL_ANSWER_AUTOPILOT_MARKDOWN),
    )
    final_answer_autopilot_parser.add_argument(
        "--revision-markdown-output",
        default=str(DEFAULT_FINAL_ANSWER_REVISION_MARKDOWN),
    )
    final_answer_autopilot_parser.add_argument(
        "--skip-final-audits",
        action="store_true",
        help="after a successful pipeline run, skip position/goal/safety/handoff audit refresh",
    )
    final_answer_autopilot_parser.add_argument("--fail-on-not-ready", action="store_true")

    resume_after_answers_parser = subparsers.add_parser(
        "resume-after-answers",
        help="after filling the default final-answer user input file, apply confirmed answers, live-check, and rebuild the 100-job supervised autofill packet",
    )
    resume_after_answers_parser.add_argument(
        "--reply-file",
        default=str(DEFAULT_FINAL_ANSWER_USER_INPUT_XLSX),
    )
    resume_after_answers_parser.add_argument(
        "--base-reply-file",
        default=None,
        help="merge this existing filled reply before --reply-file; aliases in --reply-file override the base",
    )
    resume_after_answers_parser.add_argument(
        "--reply-text",
        default=None,
        help="filled final-answer lines; when provided, it is used instead of --reply-file",
    )
    resume_after_answers_parser.add_argument(
        "--reply-stdin",
        action="store_true",
        help="read filled final-answer lines from stdin instead of --reply-file",
    )
    resume_after_answers_parser.add_argument(
        "--template",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_JSON),
    )
    resume_after_answers_parser.add_argument(
        "--unblockers",
        default=str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_JSON),
    )
    resume_after_answers_parser.add_argument("--live-check-limit", type=int, default=100)
    resume_after_answers_parser.add_argument("--live-check-timeout", type=float, default=25.0)
    resume_after_answers_parser.add_argument("--open-browser", action="store_true")
    resume_after_answers_parser.add_argument("--open-limit", type=int, default=100)
    resume_after_answers_parser.add_argument("--review-log", default=str(DEFAULT_REVIEW_LOG))
    resume_after_answers_parser.add_argument(
        "--validate-only",
        action="store_true",
        help="validate the filled reply without writing output files, applying answers, live-checking, or opening pages",
    )

    rehearse_after_answers_parser = subparsers.add_parser(
        "rehearse-after-answers",
        help="run the fake-answer 100-job queue rehearsal without writing real profile/memory, live-checking, opening pages, or submitting",
    )
    rehearse_after_answers_parser.add_argument("--json-output", default=str(DEFAULT_POST_ANSWER_PIPELINE_JSON))
    rehearse_after_answers_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_POST_ANSWER_PIPELINE_MARKDOWN),
    )

    post_answer_pipeline_parser = subparsers.add_parser(
        "post-answer-pipeline",
        help="validate final answers, optionally apply them, refresh the 100-job queue, and prepare supervised autofill",
    )
    post_answer_pipeline_parser.add_argument(
        "--compact-updates",
        default=str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_UPDATES_JSON),
    )
    post_answer_pipeline_parser.add_argument(
        "--full-template",
        default=str(DEFAULT_CRITICAL_INPUT_FULL_UPDATES_JSON),
    )
    post_answer_pipeline_parser.add_argument(
        "--unblockers",
        default=str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_JSON),
    )
    post_answer_pipeline_parser.add_argument(
        "--confirmed-updates-output",
        default=str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_JSON),
    )
    post_answer_pipeline_parser.add_argument(
        "--confirmed-report-json-output",
        default=str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_REPORT_JSON),
    )
    post_answer_pipeline_parser.add_argument(
        "--confirmed-report-markdown-output",
        default=str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_REPORT_MARKDOWN),
    )
    post_answer_pipeline_parser.add_argument(
        "--final-answer-intake-json",
        help="optional filled final-answer intake JSON to convert before running the post-answer pipeline",
    )
    post_answer_pipeline_parser.add_argument(
        "--final-answer-intake-report-json",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_REPORT_JSON),
    )
    post_answer_pipeline_parser.add_argument(
        "--final-answer-intake-report-markdown",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_REPORT_MARKDOWN),
    )
    post_answer_pipeline_parser.add_argument(
        "--confirm-high-risk",
        action="store_true",
        help="with --final-answer-intake-json, treat supplied high-risk text as explicitly confirmed",
    )
    post_answer_pipeline_parser.add_argument(
        "--synthetic-final-answers",
        action="store_true",
        help=(
            "use fake final answers for local rehearsal only; cannot be combined "
            "with --apply, --live-check, or --open-browser"
        ),
    )
    post_answer_pipeline_parser.add_argument(
        "--synthetic-rehearse-queue",
        action="store_true",
        help=(
            "with --synthetic-final-answers, run the post-answer 100-job queue and "
            "autofill packet rehearsal using fake local data only"
        ),
    )
    post_answer_pipeline_parser.add_argument(
        "--apply",
        action="store_true",
        help="write approved answers to the local profile and answer memory, then refresh reports",
    )
    post_answer_pipeline_parser.add_argument(
        "--live-check",
        action="store_true",
        help="after apply/refresh, recheck current apply pages before rebuilding open-ready handoff",
    )
    post_answer_pipeline_parser.add_argument("--live-check-limit", type=int, default=100)
    post_answer_pipeline_parser.add_argument("--live-check-timeout", type=float, default=25.0)
    post_answer_pipeline_parser.add_argument(
        "--include-values",
        action="store_true",
        help="include actual values in the supervised autofill packet after --apply",
    )
    post_answer_pipeline_parser.add_argument("--open-browser", action="store_true")
    post_answer_pipeline_parser.add_argument("--open-limit", type=int, default=100)
    post_answer_pipeline_parser.add_argument("--review-log", default=str(DEFAULT_REVIEW_LOG))
    post_answer_pipeline_parser.add_argument("--json-output", default=str(DEFAULT_POST_ANSWER_PIPELINE_JSON))
    post_answer_pipeline_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_POST_ANSWER_PIPELINE_MARKDOWN),
    )
    post_answer_pipeline_parser.add_argument(
        "--fail-on-not-ready",
        action="store_true",
        help="exit non-zero when final answers are not ready for workflow",
    )

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

    critical_inputs_readiness_parser = subparsers.add_parser(
        "critical-inputs-readiness",
        help="validate confirmed critical-input updates before writing profile or answer memory",
    )
    critical_inputs_readiness_parser.add_argument("--approval-pack", default=str(DEFAULT_LEARNING_APPROVAL_PACK_JSON))
    critical_inputs_readiness_parser.add_argument("--answers", default=str(DEFAULT_CRITICAL_INPUT_ANSWERS_JSON))
    critical_inputs_readiness_parser.add_argument("--updates", default=str(DEFAULT_CRITICAL_INPUT_FULL_UPDATES_JSON))
    critical_inputs_readiness_parser.add_argument("--research-json", default=str(DEFAULT_RESEARCH_JSON))
    critical_inputs_readiness_parser.add_argument(
        "--profile",
        default=str(DEFAULT_PERSONAL_PROFILE if DEFAULT_PERSONAL_PROFILE.exists() else DEFAULT_PROFILE),
    )
    critical_inputs_readiness_parser.add_argument("--memory", default=str(DEFAULT_MEMORY))
    critical_inputs_readiness_parser.add_argument("--closed-jobs", default=str(DEFAULT_CLOSED_JOBS))
    critical_inputs_readiness_parser.add_argument("--json-output", default=str(DEFAULT_CRITICAL_INPUT_UPDATES_READINESS_JSON))
    critical_inputs_readiness_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_CRITICAL_INPUT_UPDATES_READINESS_MARKDOWN),
    )
    critical_inputs_readiness_parser.add_argument(
        "--fail-on-not-ready",
        action="store_true",
        help="exit non-zero when the updates are not ready to apply",
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
    critical_inputs_impact_parser.add_argument(
        "--individual-limit",
        type=int,
        default=10,
        help="number of individual input impact rows to rank; use -1 for all",
    )

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
        "--allow-partial-apply",
        action="store_true",
        help="intentionally persist only the currently ready critical inputs even when other critical inputs are still waiting",
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

    synthetic_unblocker_proof_parser = subparsers.add_parser(
        "synthetic-unblocker-proof",
        help="prove final critical unblockers with synthetic answers in a temp-only dry run",
    )
    synthetic_unblocker_proof_parser.add_argument(
        "--approval-pack",
        default=str(DEFAULT_LEARNING_APPROVAL_PACK_JSON),
    )
    synthetic_unblocker_proof_parser.add_argument(
        "--answers",
        default=str(DEFAULT_CRITICAL_INPUT_ANSWERS_JSON),
    )
    synthetic_unblocker_proof_parser.add_argument(
        "--unblockers",
        default=str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_JSON),
    )
    synthetic_unblocker_proof_parser.add_argument("--research-json", default=str(DEFAULT_RESEARCH_JSON))
    synthetic_unblocker_proof_parser.add_argument(
        "--profile",
        default=str(DEFAULT_PERSONAL_PROFILE if DEFAULT_PERSONAL_PROFILE.exists() else DEFAULT_PROFILE),
    )
    synthetic_unblocker_proof_parser.add_argument("--memory", default=str(DEFAULT_MEMORY))
    synthetic_unblocker_proof_parser.add_argument("--closed-jobs", default=str(DEFAULT_CLOSED_JOBS))
    synthetic_unblocker_proof_parser.add_argument("--autofill-batch", default=str(DEFAULT_AUTOFILL_BATCH_JSON))
    synthetic_unblocker_proof_parser.add_argument(
        "--json-output",
        default=str(DEFAULT_SYNTHETIC_UNBLOCKER_PROOF_JSON),
    )
    synthetic_unblocker_proof_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_SYNTHETIC_UNBLOCKER_PROOF_MARKDOWN),
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
        "--synthetic-unblocker-proof-json",
        default=str(DEFAULT_SYNTHETIC_UNBLOCKER_PROOF_JSON),
    )
    export_questions_parser.add_argument(
        "--critical-input-full-updates-json",
        default=str(DEFAULT_CRITICAL_INPUT_FULL_UPDATES_JSON),
    )
    export_questions_parser.add_argument(
        "--critical-input-confirmed-updates-json",
        default=str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_JSON),
    )
    export_questions_parser.add_argument(
        "--critical-input-confirmed-updates-report-json",
        default=str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_REPORT_JSON),
    )
    export_questions_parser.add_argument(
        "--critical-input-updates-readiness-json",
        default=str(DEFAULT_CRITICAL_INPUT_UPDATES_READINESS_JSON),
    )
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
    export_questions_parser.add_argument("--apply-queue-json", default=str(DEFAULT_APPLY_QUEUE_JSON))
    export_questions_parser.add_argument("--apply-queue-html", default=str(DEFAULT_APPLY_QUEUE_HTML))
    export_questions_parser.add_argument(
        "--apply-queue-live-check-jobs-json",
        default=str(DEFAULT_APPLY_QUEUE_LIVE_CHECK_JOBS),
    )
    export_questions_parser.add_argument("--apply-queue-handoff-json", default=str(DEFAULT_APPLY_QUEUE_HANDOFF_JSON))
    export_questions_parser.add_argument("--apply-queue-handoff-html", default=str(DEFAULT_APPLY_QUEUE_HANDOFF_HTML))
    export_questions_parser.add_argument(
        "--apply-queue-open-ready-jobs-json",
        default=str(DEFAULT_APPLY_QUEUE_OPEN_READY_JOBS),
    )
    export_questions_parser.add_argument(
        "--apply-queue-autofill-packet-json",
        default=str(DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_JSON),
    )
    export_questions_parser.add_argument(
        "--apply-queue-autofill-packet-html",
        default=str(DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_HTML),
    )
    export_questions_parser.add_argument("--apply-queue-refresh-json", default=str(DEFAULT_APPLY_QUEUE_REFRESH_JSON))
    export_questions_parser.add_argument(
        "--apply-queue-refresh-markdown",
        default=str(DEFAULT_APPLY_QUEUE_REFRESH_MARKDOWN),
    )
    export_questions_parser.add_argument(
        "--position-execution-audit-json",
        default=str(DEFAULT_POSITION_EXECUTION_AUDIT_JSON),
    )
    export_questions_parser.add_argument(
        "--position-execution-audit-html",
        default=str(DEFAULT_POSITION_EXECUTION_AUDIT_HTML),
    )
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
    export_questions_parser.add_argument(
        "--critical-input-unblockers-json",
        default=str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_JSON),
    )
    export_questions_parser.add_argument(
        "--critical-input-unblockers-html",
        default=str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_HTML),
    )
    export_questions_parser.add_argument(
        "--final-answer-intake-template-json",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_JSON),
    )
    export_questions_parser.add_argument(
        "--final-answer-intake-template-markdown",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_MARKDOWN),
    )
    export_questions_parser.add_argument(
        "--final-answer-intake-template-html",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_HTML),
    )
    export_questions_parser.add_argument(
        "--final-answer-intake-report-json",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_REPORT_JSON),
    )
    export_questions_parser.add_argument(
        "--final-answer-intake-report-markdown",
        default=str(DEFAULT_FINAL_ANSWER_INTAKE_REPORT_MARKDOWN),
    )
    export_questions_parser.add_argument(
        "--final-answer-blockers-json",
        default=str(DEFAULT_FINAL_ANSWER_BLOCKERS_JSON),
    )
    export_questions_parser.add_argument(
        "--final-answer-blockers-markdown",
        default=str(DEFAULT_FINAL_ANSWER_BLOCKERS_MARKDOWN),
    )
    export_questions_parser.add_argument(
        "--final-answer-blockers-html",
        default=str(DEFAULT_FINAL_ANSWER_BLOCKERS_HTML),
    )
    export_questions_parser.add_argument(
        "--final-answer-blockers-xlsx",
        default=str(DEFAULT_FINAL_ANSWER_BLOCKERS_XLSX),
    )
    export_questions_parser.add_argument(
        "--post-answer-pipeline-json",
        default=str(DEFAULT_POST_ANSWER_PIPELINE_JSON),
    )
    export_questions_parser.add_argument(
        "--post-answer-pipeline-markdown",
        default=str(DEFAULT_POST_ANSWER_PIPELINE_MARKDOWN),
    )
    export_questions_parser.add_argument(
        "--submission-safety-audit-json",
        default=str(DEFAULT_SUBMISSION_SAFETY_AUDIT_JSON),
    )
    export_questions_parser.add_argument(
        "--submission-safety-audit-markdown",
        default=str(DEFAULT_SUBMISSION_SAFETY_AUDIT_MARKDOWN),
    )
    export_questions_parser.add_argument("--xlsx-output", default=str(DEFAULT_QUESTION_EXPORT_XLSX))
    export_questions_parser.add_argument("--html-output", default=str(DEFAULT_QUESTION_EXPORT_HTML))

    platform_playbook_parser = subparsers.add_parser(
        "platform-question-playbook",
        help="summarize per-platform question handling and 100-position rehearsal evidence",
    )
    platform_playbook_parser.add_argument("--research-json", default=str(DEFAULT_RESEARCH_JSON))
    platform_playbook_parser.add_argument("--autofill-batch-json", default=str(DEFAULT_AUTOFILL_BATCH_JSON))
    platform_playbook_parser.add_argument(
        "--fake-position-rehearsal-json",
        default=str(DEFAULT_FAKE_POSITION_REHEARSAL_JSON),
    )
    platform_playbook_parser.add_argument("--automation-handoff-json", default=str(DEFAULT_AUTOMATION_HANDOFF_JSON))
    platform_playbook_parser.add_argument("--closed-jobs-json", default=str(DEFAULT_CLOSED_JOBS))
    platform_playbook_parser.add_argument("--json-output", default=str(DEFAULT_PLATFORM_QUESTION_PLAYBOOK_JSON))
    platform_playbook_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_PLATFORM_QUESTION_PLAYBOOK_MARKDOWN),
    )
    platform_playbook_parser.add_argument("--html-output", default=str(DEFAULT_PLATFORM_QUESTION_PLAYBOOK_HTML))

    position_execution_audit_parser = subparsers.add_parser(
        "position-execution-audit",
        help="write a per-position execution ledger for the selected 100-position queue",
    )
    position_execution_audit_parser.add_argument(
        "--autofill-packet-json",
        default=str(DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_JSON),
    )
    position_execution_audit_parser.add_argument(
        "--synthetic-autofill-packet-json",
        default=str(DEFAULT_POST_ANSWER_SYNTHETIC_AUTOFILL_PACKET_JSON),
    )
    position_execution_audit_parser.add_argument(
        "--platform-question-playbook-json",
        default=str(DEFAULT_PLATFORM_QUESTION_PLAYBOOK_JSON),
    )
    position_execution_audit_parser.add_argument("--goal-audit-json", default=str(DEFAULT_GOAL_AUDIT_JSON))
    position_execution_audit_parser.add_argument("--target-count", type=int, default=100)
    position_execution_audit_parser.add_argument("--json-output", default=str(DEFAULT_POSITION_EXECUTION_AUDIT_JSON))
    position_execution_audit_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_POSITION_EXECUTION_AUDIT_MARKDOWN),
    )
    position_execution_audit_parser.add_argument("--html-output", default=str(DEFAULT_POSITION_EXECUTION_AUDIT_HTML))

    selected_answer_dependencies_parser = subparsers.add_parser(
        "selected-answer-dependencies",
        help="map unresolved final-answer blockers to the selected 100-position queue",
    )
    selected_answer_dependencies_parser.add_argument("--research-json", default=str(DEFAULT_RESEARCH_JSON))
    selected_answer_dependencies_parser.add_argument(
        "--position-execution-audit-json",
        default=str(DEFAULT_POSITION_EXECUTION_AUDIT_JSON),
    )
    selected_answer_dependencies_parser.add_argument(
        "--final-answer-blockers-json",
        default=str(DEFAULT_FINAL_ANSWER_BLOCKERS_JSON),
    )
    selected_answer_dependencies_parser.add_argument("--target-count", type=int, default=100)
    selected_answer_dependencies_parser.add_argument(
        "--json-output",
        default=str(DEFAULT_SELECTED_ANSWER_DEPENDENCIES_JSON),
    )
    selected_answer_dependencies_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_SELECTED_ANSWER_DEPENDENCIES_MARKDOWN),
    )
    selected_answer_dependencies_parser.add_argument(
        "--html-output",
        default=str(DEFAULT_SELECTED_ANSWER_DEPENDENCIES_HTML),
    )

    submission_safety_audit_parser = subparsers.add_parser(
        "submission-safety-audit",
        help="aggregate proof that fake rehearsals and autofill packets did not submit to real employers",
    )
    submission_safety_audit_parser.add_argument(
        "--fake-position-rehearsal-json",
        default=str(DEFAULT_FAKE_POSITION_REHEARSAL_JSON),
    )
    submission_safety_audit_parser.add_argument(
        "--post-answer-pipeline-json",
        default=str(DEFAULT_POST_ANSWER_PIPELINE_JSON),
    )
    submission_safety_audit_parser.add_argument(
        "--apply-queue-autofill-packet-json",
        default=str(DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_JSON),
    )
    submission_safety_audit_parser.add_argument(
        "--browser-review-queue-audit-json",
        default=str(DEFAULT_REVIEW_QUEUE_AUDIT_JSON),
    )
    submission_safety_audit_parser.add_argument(
        "--pre-submit-review-json",
        default=str(DEFAULT_PRE_SUBMIT_REVIEW_JSON),
    )
    submission_safety_audit_parser.add_argument("--goal-audit-json", default=str(DEFAULT_GOAL_AUDIT_JSON))
    submission_safety_audit_parser.add_argument(
        "--final-answer-reply-json",
        default=str(DEFAULT_FINAL_ANSWER_REPLY_JSON),
    )
    submission_safety_audit_parser.add_argument(
        "--synthetic-final-answer-reply-json",
        default=str(DEFAULT_FINAL_ANSWER_REPLY_SYNTHETIC_JSON),
    )
    submission_safety_audit_parser.add_argument("--json-output", default=str(DEFAULT_SUBMISSION_SAFETY_AUDIT_JSON))
    submission_safety_audit_parser.add_argument(
        "--markdown-output",
        default=str(DEFAULT_SUBMISSION_SAFETY_AUDIT_MARKDOWN),
    )

    goal_audit_parser = subparsers.add_parser(
        "goal-audit",
        help="audit current evidence against the 100-position automation goal",
    )
    goal_audit_parser.add_argument("--coverage-gate-json", default=str(DEFAULT_COVERAGE_GATE_JSON))
    goal_audit_parser.add_argument("--gaps-json", default=str(DEFAULT_GAPS_JSON))
    goal_audit_parser.add_argument("--readiness-json", default=str(DEFAULT_READINESS_JSON))
    goal_audit_parser.add_argument("--critical-input-status-json", default=str(DEFAULT_CRITICAL_INPUT_STATUS_JSON))
    goal_audit_parser.add_argument(
        "--critical-input-updates-readiness-json",
        default=str(DEFAULT_CRITICAL_INPUT_UPDATES_READINESS_JSON),
    )
    goal_audit_parser.add_argument("--fake-learning-probe-json", default=str(DEFAULT_FAKE_LEARNING_PROBE_JSON))
    goal_audit_parser.add_argument(
        "--fake-critical-input-probe-json",
        default=str(DEFAULT_FAKE_CRITICAL_INPUT_PROBE_JSON),
    )
    goal_audit_parser.add_argument(
        "--fake-position-rehearsal-json",
        default=str(DEFAULT_FAKE_POSITION_REHEARSAL_JSON),
    )
    goal_audit_parser.add_argument("--autofill-batch-json", default=str(DEFAULT_AUTOFILL_BATCH_JSON))
    goal_audit_parser.add_argument(
        "--synthetic-unblocker-proof-json",
        default=str(DEFAULT_SYNTHETIC_UNBLOCKER_PROOF_JSON),
    )
    goal_audit_parser.add_argument("--post-answer-pipeline-json", default=str(DEFAULT_POST_ANSWER_PIPELINE_JSON))
    goal_audit_parser.add_argument(
        "--final-answer-autopilot-json",
        default=str(DEFAULT_FINAL_ANSWER_AUTOPILOT_JSON),
    )
    goal_audit_parser.add_argument("--closed-preflight-json", default=str(DEFAULT_CLOSED_PREFLIGHT_JSON))
    goal_audit_parser.add_argument("--closed-jobs-json", default=str(DEFAULT_CLOSED_JOBS))
    goal_audit_parser.add_argument(
        "--platform-question-playbook-json",
        default=str(DEFAULT_PLATFORM_QUESTION_PLAYBOOK_JSON),
    )
    goal_audit_parser.add_argument(
        "--position-execution-audit-json",
        default=str(DEFAULT_POSITION_EXECUTION_AUDIT_JSON),
    )
    goal_audit_parser.add_argument(
        "--selected-answer-dependencies-json",
        default=str(DEFAULT_SELECTED_ANSWER_DEPENDENCIES_JSON),
    )
    goal_audit_parser.add_argument(
        "--submission-safety-audit-json",
        default=str(DEFAULT_SUBMISSION_SAFETY_AUDIT_JSON),
    )
    goal_audit_parser.add_argument("--json-output", default=str(DEFAULT_GOAL_AUDIT_JSON))
    goal_audit_parser.add_argument("--markdown-output", default=str(DEFAULT_GOAL_AUDIT_MARKDOWN))
    goal_audit_parser.add_argument(
        "--fail-on-incomplete",
        action="store_true",
        help="exit non-zero unless the goal audit proves completion",
    )

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

    if args.command == "review-queue-audit":
        audit = write_browser_review_queue_audit(
            args.review_log,
            args.json_output,
            args.markdown_output,
        )
        print(f"Wrote browser review queue audit JSON to {args.json_output}")
        print(f"Wrote browser review queue audit Markdown to {args.markdown_output}")
        print(f"Rows: {audit.get('row_count', 0)}")
        print(f"Safe: {str(bool(audit.get('safe'))).lower()}")
        print(f"Disallowed fields: {audit.get('disallowed_field_count', 0)}")
        print(f"Sensitive fields: {audit.get('sensitive_field_count', 0)}")
        print(f"Sensitive values: {audit.get('sensitive_value_count', 0)}")
        print(f"Tracking URLs: {audit.get('tracking_url_count', 0)}")
        print(f"Real platform submissions: {audit.get('real_platform_submission_true_count', 0)}")
        if args.fail_on_unsafe and not audit.get("safe"):
            return 2
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
                    "Synthetic unblocker proof": args.synthetic_unblocker_proof_json,
                    "Critical input full updates template": args.critical_input_full_updates_json,
                    "Critical input confirmed updates": args.critical_input_confirmed_updates_json,
                    "Critical input confirmed updates report": args.critical_input_confirmed_updates_report_json,
                    "Critical input updates readiness": args.critical_input_updates_readiness_json,
                    "Learning approval pack": args.learning_approval_pack_json,
                    "Answer memory": args.answer_memory_json,
                    "Closed postings": args.closed_jobs_json,
                    "Candidate profile": args.profile_json,
                    "Goal readiness audit": args.goal_audit_json,
                    "Autofill batch": args.autofill_batch_json,
                    "Autofill batch HTML": args.autofill_batch_html,
                    "Automation handoff": args.automation_handoff_json,
                    "Automation handoff HTML": args.automation_handoff_html,
                    "Apply queue": args.apply_queue_json,
                    "Apply queue HTML": args.apply_queue_html,
                    "Apply queue live-check jobs": args.apply_queue_live_check_jobs_json,
                    "Apply queue handoff": args.apply_queue_handoff_json,
                    "Apply queue handoff HTML": args.apply_queue_handoff_html,
                    "Apply queue open-ready jobs": args.apply_queue_open_ready_jobs_json,
                    "Apply queue autofill packet": args.apply_queue_autofill_packet_json,
                    "Apply queue autofill packet HTML": args.apply_queue_autofill_packet_html,
                    "Apply queue refresh": args.apply_queue_refresh_json,
                    "Apply queue refresh Markdown": args.apply_queue_refresh_markdown,
                    "Position execution audit": args.position_execution_audit_json,
                    "Position execution audit HTML": args.position_execution_audit_html,
                    "Critical input suggestions": args.critical_input_suggestions_json,
                    "Critical input questionnaire": args.critical_input_questionnaire_json,
                    "Critical input questionnaire HTML": args.critical_input_questionnaire_html,
                    "Critical input preflight": args.critical_input_preflight_json,
                    "Critical input preflight HTML": args.critical_input_preflight_html,
                    "Critical input impact": args.critical_input_impact_json,
                    "Critical input impact HTML": args.critical_input_impact_html,
                    "Critical input final unblockers": args.critical_input_unblockers_json,
                    "Critical input final unblockers HTML": args.critical_input_unblockers_html,
                    "Final answer intake template": args.final_answer_intake_template_json,
                    "Final answer intake template Markdown": args.final_answer_intake_template_markdown,
                    "Final answer intake template HTML": args.final_answer_intake_template_html,
                    "Final answer intake report": args.final_answer_intake_report_json,
                    "Final answer intake report Markdown": args.final_answer_intake_report_markdown,
                    "Final answer blockers": args.final_answer_blockers_json,
                    "Final answer blockers Markdown": args.final_answer_blockers_markdown,
                    "Final answer blockers HTML": args.final_answer_blockers_html,
                    "Final answer blockers XLSX": args.final_answer_blockers_xlsx,
                    "Post-answer pipeline": args.post_answer_pipeline_json,
                    "Post-answer pipeline Markdown": args.post_answer_pipeline_markdown,
                    "Submission safety audit": args.submission_safety_audit_json,
                    "Submission safety audit Markdown": args.submission_safety_audit_markdown,
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
            critical_input_unblockers=_load_optional_json(args.critical_input_unblockers_json),
            final_answer_intake_template=_load_optional_json(args.final_answer_intake_template_json),
            final_answer_intake_update=_load_optional_json(args.final_answer_intake_report_json),
            post_answer_pipeline=_load_optional_json(args.post_answer_pipeline_json),
            autofill_batch=_load_optional_json(args.autofill_batch_json),
            apply_queue_handoff=_load_optional_json(args.apply_queue_handoff_json),
            apply_queue_refresh=_load_optional_json(args.apply_queue_refresh_json),
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

    if args.command == "platform-question-playbook":
        report = write_platform_question_playbook(
            json.loads(Path(args.research_json).read_text(encoding="utf-8")),
            args.json_output,
            args.markdown_output,
            args.html_output,
            autofill_batch=_load_optional_json(args.autofill_batch_json),
            fake_position_rehearsal=_load_optional_json(args.fake_position_rehearsal_json),
            automation_handoff=_load_optional_json(args.automation_handoff_json),
            closed_jobs=_load_optional_json(args.closed_jobs_json),
        )
        summary = report.get("summary") or {}
        print(f"Wrote platform question playbook JSON to {args.json_output}")
        print(f"Wrote platform question playbook Markdown to {args.markdown_output}")
        print(f"Wrote platform question playbook HTML to {args.html_output}")
        print(f"Observed positions: {summary.get('observed_position_count', 0)}")
        print(f"Selected positions: {summary.get('selected_position_count', 0)}")
        print(f"Local synthetic submits: {summary.get('selected_local_synthetic_submit_count', 0)}")
        print(f"Final answers missing: {summary.get('final_answer_missing_count', 0)}")
        return 0

    if args.command == "position-execution-audit":
        report = write_position_execution_audit(
            args.autofill_packet_json,
            args.synthetic_autofill_packet_json,
            args.platform_question_playbook_json,
            args.goal_audit_json,
            args.json_output,
            args.markdown_output,
            args.html_output,
            target_count=args.target_count,
        )
        summary = report.get("summary") or {}
        print(f"Wrote position execution audit JSON to {args.json_output}")
        print(f"Wrote position execution audit Markdown to {args.markdown_output}")
        print(f"Wrote position execution audit HTML to {args.html_output}")
        print(f"Status: {report.get('status')}")
        print(f"Positions audited: {summary.get('position_count', 0)} / {summary.get('target_count', 0)}")
        print(f"Local synthetic submits: {summary.get('local_synthetic_submit_position_count', 0)}")
        print(f"Selector miss positions: {summary.get('selector_miss_position_count', 0)}")
        print(f"Final submit stop positions: {summary.get('final_submit_stop_position_count', 0)}")
        print(f"Remaining user answers: {summary.get('remaining_user_answer_count', 0)}")
        return 0

    if args.command == "selected-answer-dependencies":
        report = write_selected_final_answer_dependency_report(
            args.research_json,
            args.position_execution_audit_json,
            args.final_answer_blockers_json,
            args.json_output,
            args.markdown_output,
            args.html_output,
            target_count=args.target_count,
        )
        summary = report.get("summary") or {}
        print(f"Wrote selected answer dependency JSON to {args.json_output}")
        print(f"Wrote selected answer dependency Markdown to {args.markdown_output}")
        print(f"Wrote selected answer dependency HTML to {args.html_output}")
        print(f"Status: {report.get('status')}")
        print(f"Selected positions: {summary.get('selected_position_count', 0)} / {summary.get('target_count', 0)}")
        print(
            "Positions with direct answer dependencies: "
            f"{summary.get('positions_with_final_answer_dependencies', 0)}"
        )
        print(f"Known unresolved aliases: {summary.get('known_unresolved_alias_count', 0)}")
        print(
            "Ready after truthful answers: "
            f"{summary.get('ready_after_truthful_answers_count', 0)}"
        )
        return 0

    if args.command == "submission-safety-audit":
        audit = write_submission_safety_audit(
            args.json_output,
            args.markdown_output,
            fake_position_rehearsal=_load_optional_json(args.fake_position_rehearsal_json),
            post_answer_pipeline=_load_optional_json(args.post_answer_pipeline_json),
            apply_queue_autofill_packet=_load_optional_json(args.apply_queue_autofill_packet_json),
            browser_review_queue_audit=_load_optional_json(args.browser_review_queue_audit_json),
            pre_submit_review=_load_optional_json(args.pre_submit_review_json),
            goal_readiness_audit=_load_optional_json(args.goal_audit_json),
            final_answer_reply_intake=_load_optional_json(args.final_answer_reply_json),
            synthetic_final_answer_reply_intake=_load_optional_json(args.synthetic_final_answer_reply_json),
        )
        summary = audit.get("summary") or {}
        print(f"Wrote submission safety audit JSON to {args.json_output}")
        print(f"Wrote submission safety audit Markdown to {args.markdown_output}")
        print(f"Status: {audit.get('status')}")
        print(f"Issues: {audit.get('issue_count', 0)}")
        print(f"Warnings: {audit.get('warning_count', 0)}")
        print(f"Fake local synthetic submits: {summary.get('fake_position_local_synthetic_submit_count', 0)}")
        print(f"Apply packet selected: {summary.get('apply_packet_selected_count', 0)}")
        print(f"Final-submit stops: {summary.get('apply_packet_final_submit_stop_count', 0)}")
        print(f"Final-answer blanks: {summary.get('final_answer_waiting_count_after_drafts', 0)}")
        return 0

    if args.command == "goal-audit":
        audit = write_goal_readiness_audit(
            json.loads(Path(args.coverage_gate_json).read_text(encoding="utf-8")),
            json.loads(Path(args.gaps_json).read_text(encoding="utf-8")),
            json.loads(Path(args.readiness_json).read_text(encoding="utf-8")),
            args.json_output,
            args.markdown_output,
            critical_input_status=_load_optional_json(args.critical_input_status_json),
            critical_input_updates_readiness=_load_optional_json(args.critical_input_updates_readiness_json),
            fake_learning_probe=_load_optional_json(args.fake_learning_probe_json),
            fake_critical_input_probe=_load_optional_json(args.fake_critical_input_probe_json),
            fake_position_rehearsal=_load_optional_json(args.fake_position_rehearsal_json),
            autofill_batch_plan=_load_optional_json(args.autofill_batch_json),
            synthetic_unblocker_proof=_load_optional_json(args.synthetic_unblocker_proof_json),
            post_answer_pipeline=_load_optional_json(args.post_answer_pipeline_json),
            closed_preflight=_load_optional_json(args.closed_preflight_json),
            closed_jobs=_load_optional_json(args.closed_jobs_json),
            platform_question_playbook=_load_optional_json(args.platform_question_playbook_json),
            position_execution_audit=_load_optional_json(args.position_execution_audit_json),
            selected_answer_dependencies=_load_optional_json(args.selected_answer_dependencies_json),
            submission_safety_audit=_load_optional_json(args.submission_safety_audit_json),
            final_answer_autopilot=_load_optional_json(args.final_answer_autopilot_json),
        )
        print(f"Wrote goal audit JSON to {args.json_output}")
        print(f"Wrote goal audit Markdown to {args.markdown_output}")
        print(f"Status: {audit.get('status')}")
        verdict = audit.get("completion_verdict") if isinstance(audit.get("completion_verdict"), dict) else {}
        print(f"Completion verdict: {verdict.get('status', '')}")
        blocking_ids = verdict.get("blocking_requirement_ids") if isinstance(verdict.get("blocking_requirement_ids"), list) else []
        if blocking_ids:
            print(f"Blocking requirement IDs: {', '.join(str(item) for item in blocking_ids)}")
        print(f"Missing requirements: {audit.get('missing_requirement_count', 0)}")
        summary = audit.get("blocker_summary") or {}
        print(f"Final answer blanks after drafts: {summary.get('final_answer_waiting_count_after_drafts', 0)}")
        print(
            "Final answer high-risk blanks: "
            f"{summary.get('final_answer_waiting_high_risk_count_after_drafts', 0)}"
        )
        latest_validation = (
            audit.get("latest_final_answer_validation")
            if isinstance(audit.get("latest_final_answer_validation"), dict)
            else {}
        )
        missing_aliases = [
            str(row.get("alias") or row.get("input_id") or "").strip()
            for row in audit.get("final_answer_waiting_rows") or []
            if str(row.get("alias") or row.get("input_id") or "").strip()
        ]
        if missing_aliases:
            label = (
                "Draft final-answer aliases still waiting before latest validation"
                if latest_validation
                else "Missing final answer aliases"
            )
            print(f"{label}: {', '.join(missing_aliases[:12])}")
        if latest_validation:
            print(
                "Latest final-answer validation: "
                f"answers={latest_validation.get('answer_input_count', 0)} "
                f"ready={latest_validation.get('ready_alias_count', 0)} "
                f"missing={latest_validation.get('missing_alias_count', 0)} "
                f"specificity={latest_validation.get('needs_more_specific_alias_count', 0)} "
                f"safe_to_resume={str(bool(latest_validation.get('safe_to_resume_after_answers'))).lower()}"
            )
            problem_aliases = []
            for key in [
                "missing_aliases",
                "unconfirmed_high_risk_aliases",
                "needs_more_specific_aliases",
                "unknown_answer_keys",
            ]:
                for alias in latest_validation.get(key) or []:
                    alias_text = str(alias).strip()
                    if alias_text and alias_text not in problem_aliases:
                        problem_aliases.append(alias_text)
            if problem_aliases:
                print(f"Latest final-answer problem aliases: {', '.join(problem_aliases[:12])}")
            if latest_validation.get("revision_markdown_output"):
                print(f"Latest final-answer revision file: {latest_validation.get('revision_markdown_output')}")
        print(
            "Draft data blockers after updates: "
            f"{summary.get('draft_data_blocking_prompt_count_after_updates', 0)}"
        )
        print(f"Goal complete: {str(bool(audit.get('goal_complete'))).lower()}")
        if args.fail_on_incomplete and not audit.get("goal_complete"):
            return 2
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
        avoid_aliases: list[str] = []
        if args.avoid_unresolved_final_answers:
            if not Path(args.final_answer_blockers_json).exists():
                raise FileNotFoundError(f"final-answer blockers report not found: {args.final_answer_blockers_json}")
            avoid_aliases = unresolved_final_answer_aliases_from_blocker_report(
                json.loads(Path(args.final_answer_blockers_json).read_text(encoding="utf-8"))
            )
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
            avoid_final_answer_aliases=avoid_aliases,
        )
        print(f"Wrote autofill batch JSON to {args.json_output}")
        print(f"Wrote autofill batch Markdown to {args.markdown_output}")
        print(f"Wrote autofill batch HTML to {args.html_output}")
        print(f"Selected: {report.get('selected_count', 0)} / {report.get('requested_count', 0)}")
        print(f"Autofill allowed: {report.get('selected_autofill_allowed_count', 0)}")
        print(
            "Excluded unresolved final-answer positions: "
            f"{report.get('excluded_unresolved_final_answer_position_count', 0)}"
        )
        print(f"No-apply-URL skipped: {report.get('skipped_no_apply_url_position_count', 0)}")
        print(f"Browser actions: {report.get('browser_action_count', 0)}")
        print(f"Selector misses: {report.get('selector_miss_count', 0)}")
        print(f"Would submit: {report.get('would_submit_count', 0)}")
        return 0

    if args.command == "apply-queue":
        for label, path_value in [
            ("autofill batch", args.autofill_batch_json),
            ("critical input updates readiness", args.critical_input_updates_readiness_json),
            ("goal audit", args.goal_audit_json),
            ("closed jobs", args.closed_jobs_json),
        ]:
            if not Path(path_value).exists():
                raise FileNotFoundError(f"{label} not found: {path_value}")
        report = write_apply_queue_readiness(
            args.autofill_batch_json,
            args.critical_input_updates_readiness_json,
            args.goal_audit_json,
            args.closed_jobs_json,
            args.json_output,
            args.markdown_output,
            args.html_output,
            args.live_check_jobs_output,
        )
        summary = report.get("summary") or {}
        print(f"Wrote apply queue JSON to {args.json_output}")
        print(f"Wrote apply queue Markdown to {args.markdown_output}")
        print(f"Wrote apply queue HTML to {args.html_output}")
        print(f"Wrote live-check jobs to {args.live_check_jobs_output}")
        print(f"Status: {report.get('status')}")
        print(f"Positions: {report.get('position_count', 0)}")
        print(f"Live-check jobs: {report.get('live_check_job_count', 0)}")
        print(f"Ready for supervised autofill: {str(bool(report.get('ready_for_supervised_autofill'))).lower()}")
        print(f"Critical updates ready: {str(bool(summary.get('updates_ready_for_apply'))).lower()}")
        return 0

    if args.command == "apply-queue-handoff":
        for label, path_value in [
            ("apply queue", args.apply_queue_json),
            ("closed preflight", args.closed_preflight_json),
        ]:
            if not Path(path_value).exists():
                raise FileNotFoundError(f"{label} not found: {path_value}")
        supplemental_preflights = list(args.supplemental_closed_preflight_json or [])
        if (
            not args.skip_default_supplemental_preflight
            and DEFAULT_APPLY_QUEUE_MANUAL_LIVE_CHECK_JSON.exists()
            and str(DEFAULT_APPLY_QUEUE_MANUAL_LIVE_CHECK_JSON) not in supplemental_preflights
        ):
            supplemental_preflights.append(str(DEFAULT_APPLY_QUEUE_MANUAL_LIVE_CHECK_JSON))
        report = write_apply_queue_handoff(
            args.apply_queue_json,
            args.closed_preflight_json,
            args.json_output,
            args.markdown_output,
            args.html_output,
            args.open_ready_jobs_output,
            supplemental_preflight_paths=supplemental_preflights,
        )
        print(f"Wrote apply queue handoff JSON to {args.json_output}")
        print(f"Wrote apply queue handoff Markdown to {args.markdown_output}")
        print(f"Wrote apply queue handoff HTML to {args.html_output}")
        print(f"Wrote open-ready jobs to {args.open_ready_jobs_output}")
        print(f"Status: {report.get('status')}")
        print(f"Open ready now: {report.get('open_ready_count', 0)}")
        print(f"Open after answers: {report.get('open_after_answers_count', 0)}")
        print(f"Manual live checks: {report.get('manual_live_check_count', 0)}")
        if supplemental_preflights:
            print(f"Supplemental preflights: {len(supplemental_preflights)}")
        if args.open_browser:
            if not report.get("ready_for_supervised_open_batch"):
                print("Open skipped: apply queue handoff is not ready for supervised open batch")
            else:
                opened_urls = open_apply_urls_in_browser(
                    report.get("open_ready_jobs") or [],
                    max_items=args.open_limit,
                    record_path=args.review_log,
                    source="apply_queue_handoff",
                    closed_jobs={"version": 1, "jobs": []},
                )
                print(f"Opened {len(opened_urls)} apply URL(s) in browser")
                print(f"Recorded browser review queue in {args.review_log}")
        return 0

    if args.command == "apply-queue-autofill-packet":
        for label, path_value in [
            ("research", args.research_json),
            ("apply queue handoff", args.apply_queue_handoff_json),
            ("profile", args.profile),
            ("answer memory", args.memory),
            ("closed jobs", args.closed_jobs),
        ]:
            if not Path(path_value).exists():
                raise FileNotFoundError(f"{label} not found: {path_value}")
        report = write_apply_queue_autofill_packet(
            args.research_json,
            args.apply_queue_handoff_json,
            args.profile,
            args.memory,
            args.closed_jobs,
            args.json_output,
            args.markdown_output,
            args.html_output,
            limit=args.limit,
            target_count=args.target_count,
            include_values=args.include_values,
            include_manifest_actions=not args.omit_manifest_actions,
        )
        summary = report.get("summary") or {}
        print(f"Wrote apply queue autofill packet JSON to {args.json_output}")
        print(f"Wrote apply queue autofill packet Markdown to {args.markdown_output}")
        print(f"Wrote apply queue autofill packet HTML to {args.html_output}")
        print(f"Status: {report.get('status')}")
        print(f"Selected: {report.get('selected_count', 0)} / {report.get('target_count', 0)}")
        print(f"Browser actions: {summary.get('browser_action_count', 0)}")
        print(f"Final-submit stops: {summary.get('final_submit_stop_count', 0)}")
        print(f"Selector misses: {summary.get('selector_miss_count', 0)}")
        print(f"Local synthetic submits: {summary.get('local_synthetic_submit_count', 0)}")
        return 0

    if args.command == "refresh-apply-queue":
        report = _run_apply_queue_refresh(args)
        final = report.get("final") or {}
        print(f"Wrote apply queue refresh JSON to {args.json_output}")
        print(f"Wrote apply queue refresh Markdown to {args.markdown_output}")
        print(f"Status: {report.get('status')}")
        print(f"Rounds: {len(report.get('rounds') or [])}")
        print(f"Live open after answers: {final.get('live_open_after_answers_count', 0)}")
        print(f"Top-up required: {final.get('top_up_required_count', 0)}")
        print(f"Manual live checks: {final.get('manual_live_check_count', 0)}")
        print(f"Goal complete: {str(bool(final.get('goal_complete'))).lower()}")
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
            critical_input_updates_readiness=_load_optional_json(args.critical_input_updates_readiness_json),
            final_answer_intake_template=_load_optional_json(args.final_answer_intake_template_json),
            final_answer_intake_update=_load_optional_json(args.final_answer_intake_report_json),
            apply_queue_handoff=_load_optional_json(args.apply_queue_handoff_json),
            apply_queue_autofill_packet=_load_optional_json(args.apply_queue_autofill_packet_json),
            apply_queue_refresh=_load_optional_json(args.apply_queue_refresh_json),
            position_execution_audit=_load_optional_json(args.position_execution_audit_json),
            selected_answer_dependencies=_load_optional_json(args.selected_answer_dependencies_json),
            submission_safety_audit=_load_optional_json(args.submission_safety_audit_json),
            source_artifacts=_question_export_source_artifacts(
                {
                    "Goal readiness audit": args.goal_audit_json,
                    "Critical input questionnaire": args.critical_input_questionnaire_json,
                    "Critical input impact": args.critical_input_impact_json,
                    "Critical input updates readiness": args.critical_input_updates_readiness_json,
                    "Autofill batch": args.autofill_batch_json,
                    "Critical input confirmed updates": str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_JSON),
                    "Critical input confirmed updates report": str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_REPORT_JSON),
                    "Final answer intake template": args.final_answer_intake_template_json,
                    "Final answer intake template HTML": args.final_answer_intake_template_html,
                    "Final answer intake report": args.final_answer_intake_report_json,
                    "Final answer blockers": args.final_answer_blockers_json,
                    "Final answer blockers Markdown": args.final_answer_blockers_markdown,
                    "Apply queue handoff": args.apply_queue_handoff_json,
                    "Apply queue autofill packet": args.apply_queue_autofill_packet_json,
                    "Apply queue refresh": args.apply_queue_refresh_json,
                    "Position execution audit": args.position_execution_audit_json,
                    "Position execution audit HTML": args.position_execution_audit_html,
                    "Selected answer dependencies": args.selected_answer_dependencies_json,
                    "Selected answer dependencies Markdown": args.selected_answer_dependencies_markdown,
                    "Selected answer dependencies HTML": args.selected_answer_dependencies_html,
                    "Browser review queue audit": args.review_queue_audit_json,
                    "Browser review queue audit Markdown": args.review_queue_audit_markdown,
                    "Submission safety audit": args.submission_safety_audit_json,
                    "Submission safety audit Markdown": args.submission_safety_audit_markdown,
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
        print(f"Final answer blanks: {summary.get('updates_waiting_after_update_count', 0)}")
        print(f"Open after answers: {summary.get('apply_queue_open_after_answers_count', 0)}")
        print(f"Queue refresh: {summary.get('apply_queue_refresh_status') or 'missing'}")
        print(f"Refresh top-up required: {summary.get('apply_queue_refresh_top_up_required_count', 0)}")
        print(f"Autofill packet: {summary.get('autofill_packet_status') or 'missing'}")
        print(f"Autofill selected: {summary.get('autofill_selected_count', 0)}")
        print(f"Position execution audit: {summary.get('position_execution_status') or 'missing'}")
        print(f"Positions audited: {summary.get('position_execution_audited_count', 0)}")
        print(f"Answer dependency map: {summary.get('selected_answer_dependency_status') or 'missing'}")
        print(
            "Answer dependency selected: "
            f"{summary.get('selected_answer_dependency_selected_count', 0)}"
        )
        print(f"Submission safety: {summary.get('submission_safety_status') or 'missing'}")
        print(f"Submission safety issues: {summary.get('submission_safety_issue_count', 0)}")
        print(
            "Final-answer fake markers: real "
            f"{summary.get('submission_safety_real_final_answer_fake_marker_count', 0)}, "
            f"synthetic {summary.get('submission_safety_synthetic_final_answer_fake_marker_count', 0)}"
        )
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
            existing_answers_payload=_load_optional_json(args.json_output),
        )
        print(f"Wrote critical input answer JSON to {args.json_output}")
        print(f"Wrote critical input answer Markdown to {args.markdown_output}")
        print(f"Answers needed: {template.get('answer_count', 0)}")
        print(f"Preserved answers: {template.get('preserved_answer_count', 0)}")
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

    if args.command == "critical-input-unblockers":
        suggestions_path = Path(args.suggestions)
        if not suggestions_path.exists():
            raise FileNotFoundError(f"critical input suggestions not found: {args.suggestions}")
        packet = write_critical_input_unblocker_packet(
            json.loads(suggestions_path.read_text(encoding="utf-8")),
            args.json_output,
            args.markdown_output,
            args.html_output,
            impact_payload=_load_optional_json(args.impact),
        )
        updates_path = Path(args.updates_template_output)
        updates_path.parent.mkdir(parents=True, exist_ok=True)
        updates_path.write_text(
            json.dumps(packet.get("compact_updates_template", {}), ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        full_updates_path = Path(args.full_updates_template_output)
        full_updates_path.parent.mkdir(parents=True, exist_ok=True)
        full_updates_path.write_text(
            json.dumps(packet.get("full_updates_template", {}), ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote critical input unblockers JSON to {args.json_output}")
        print(f"Wrote critical input unblockers Markdown to {args.markdown_output}")
        print(f"Wrote critical input unblockers HTML to {args.html_output}")
        print(f"Wrote critical input unblocker updates template to {args.updates_template_output}")
        print(f"Wrote critical input full updates template to {args.full_updates_template_output}")
        print(f"Inputs: {packet.get('input_count', 0)}")
        print(f"High risk: {packet.get('high_risk_count', 0)}")
        print(f"Full update entries: {packet.get('full_update_count', 0)}")
        return 0

    if args.command == "critical-input-unblockers-finalize":
        for label, path_value in [
            ("compact updates", args.compact_updates),
            ("full updates template", args.full_template),
            ("critical input unblockers", args.unblockers),
        ]:
            if not Path(path_value).exists():
                raise FileNotFoundError(f"{label} not found: {path_value}")
        report = write_critical_input_unblocker_final_update(
            args.compact_updates,
            args.full_template,
            args.unblockers,
            args.updates_output,
            args.json_output,
            args.markdown_output,
        )
        summary = report.get("summary") or {}
        print(f"Wrote confirmed updates JSON to {args.updates_output}")
        print(f"Wrote confirmed updates report JSON to {args.json_output}")
        print(f"Wrote confirmed updates report Markdown to {args.markdown_output}")
        print(f"Ready for workflow: {str(bool(report.get('ready_for_workflow'))).lower()}")
        print(f"Merged updates: {summary.get('merged_update_count', 0)}")
        print(f"Missing unblockers: {summary.get('missing_unblocker_count', 0)}")
        print(f"High-risk confirmations missing: {summary.get('unconfirmed_high_risk_count', 0)}")
        print(f"Unknown compact updates: {summary.get('unknown_compact_update_count', 0)}")
        if args.fail_on_not_ready and not report.get("ready_for_workflow"):
            return 2
        return 0

    if args.command == "final-answer-intake":
        unblockers_path = Path(args.unblockers)
        if not unblockers_path.exists():
            raise FileNotFoundError(f"critical input unblockers not found: {args.unblockers}")
        unblockers = json.loads(unblockers_path.read_text(encoding="utf-8"))
        template = write_final_answer_intake_template(
            unblockers,
            args.template_output,
            args.template_markdown_output,
            args.template_html_output,
            existing_intake_payload=_load_optional_json(args.template_output),
        )
        print(f"Wrote final answer intake template JSON to {args.template_output}")
        print(f"Wrote final answer intake template Markdown to {args.template_markdown_output}")
        print(f"Wrote final answer intake template HTML to {args.template_html_output}")
        print(f"Answers required: {template.get('answer_count', 0)}")
        print(f"High risk: {template.get('high_risk_count', 0)}")
        if not args.answers:
            if args.fail_on_not_ready:
                return 2
            return 0
        answers_path = Path(args.answers)
        if not answers_path.exists():
            raise FileNotFoundError(f"final answer intake not found: {args.answers}")
        report = write_final_answer_intake_update(
            unblockers,
            json.loads(answers_path.read_text(encoding="utf-8")),
            args.compact_updates_output,
            args.json_output,
            args.markdown_output,
            confirm_high_risk=args.confirm_high_risk,
        )
        summary = report.get("summary") or {}
        print(f"Wrote compact final-answer updates to {args.compact_updates_output}")
        print(f"Wrote final answer intake report JSON to {args.json_output}")
        print(f"Wrote final answer intake report Markdown to {args.markdown_output}")
        print(f"Ready for finalize: {str(bool(report.get('ready_for_finalize'))).lower()}")
        print(f"Missing unblockers: {summary.get('missing_unblocker_count', 0)}")
        print(f"High-risk confirmations missing: {summary.get('unconfirmed_high_risk_count', 0)}")
        print(f"Unknown answers: {summary.get('unknown_answer_count', 0)}")
        _print_final_answer_intake_problem_aliases(report)
        if args.finalize:
            final_report = write_critical_input_unblocker_final_update(
                args.compact_updates_output,
                args.full_template,
                args.unblockers,
                args.confirmed_updates_output,
                args.confirmed_report_json_output,
                args.confirmed_report_markdown_output,
            )
            final_summary = final_report.get("summary") or {}
            print(f"Wrote confirmed updates JSON to {args.confirmed_updates_output}")
            print(
                "Confirmed updates ready for workflow: "
                f"{str(bool(final_report.get('ready_for_workflow'))).lower()}"
            )
            print(f"Confirmed missing unblockers: {final_summary.get('missing_unblocker_count', 0)}")
            print(
                "Confirmed high-risk confirmations missing: "
                f"{final_summary.get('unconfirmed_high_risk_count', 0)}"
            )
            if args.fail_on_not_ready and not final_report.get("ready_for_workflow"):
                return 2
        if args.fail_on_not_ready and not report.get("ready_for_finalize"):
            return 2
        return 0

    if args.command == "final-answer-intake-server":
        return _run_final_answer_intake_server(args)

    if args.command == "final-answer-blockers":
        template_path = Path(args.template)
        if not template_path.exists():
            raise FileNotFoundError(f"final answer intake template not found: {args.template}")
        report = write_final_answer_blocker_report(
            json.loads(template_path.read_text(encoding="utf-8")),
            _load_optional_json(args.goal_audit),
            args.json_output,
            args.markdown_output,
            args.reply_template_output,
            args.html_output,
            args.xlsx_output,
            args.user_input_output,
            args.user_input_xlsx_output,
        )
        summary = report.get("summary") or {}
        print(f"Wrote final answer blockers JSON to {args.json_output}")
        print(f"Wrote final answer blockers Markdown to {args.markdown_output}")
        print(f"Wrote final answer blockers HTML to {args.html_output}")
        print(f"Wrote final answer blockers XLSX to {args.xlsx_output}")
        print(f"Wrote final answer reply template to {args.reply_template_output}")
        print(f"Wrote final answer user input file to {args.user_input_output}")
        print(f"Wrote final answer user input Excel to {args.user_input_xlsx_output}")
        print(f"Blockers: {summary.get('blocker_count', 0)}")
        print(f"Missing answers: {summary.get('missing_answer_count', 0)}")
        print(f"Unconfirmed high-risk: {summary.get('unconfirmed_high_risk_count', 0)}")
        if args.print_minimal_reply:
            minimal_reply = str(report.get("minimal_reply_prompt") or "").strip()
            print("Minimal final-answer reply:")
            print(minimal_reply or "No final-answer blockers remain.")
        if args.notify_telegram:
            result = notify_telegram_for_final_answer_blockers(
                report,
                env_path=args.telegram_env,
                dry_run=args.telegram_dry_run,
                max_items=args.limit,
            )
            report = attach_final_answer_blocker_notification_result(report, result)
            Path(args.json_output).write_text(
                json.dumps(report, ensure_ascii=True, indent=2) + "\n",
                encoding="utf-8",
            )
            Path(args.markdown_output).write_text(
                render_final_answer_blocker_report_markdown(report),
                encoding="utf-8",
            )
            Path(args.html_output).write_text(
                render_final_answer_blocker_report_html(report),
                encoding="utf-8",
            )
            if result.get("skipped"):
                print(f"Telegram notification skipped: {result.get('reason')}")
            else:
                print(f"Sent Telegram notification to {result.get('chat_count', 0)} chat(s)")
            if args.telegram_dry_run:
                print(result["message"])
        return 0

    if args.command == "final-answer-user-input":
        template_path = Path(args.template)
        if not template_path.exists():
            raise FileNotFoundError(f"final answer intake template not found: {args.template}")
        report = write_final_answer_user_input_file(
            json.loads(template_path.read_text(encoding="utf-8")),
            _load_optional_json(args.goal_audit),
            args.output,
            args.xlsx_output,
        )
        print(f"Wrote final answer user input file to {report['output']}")
        if report.get("xlsx_output"):
            print(f"Wrote final answer user input Excel to {report['xlsx_output']}")
        print(f"Placeholders: {report.get('placeholder_count', 0)}")
        aliases = report.get("placeholder_aliases") if isinstance(report.get("placeholder_aliases"), list) else []
        if aliases:
            print("Placeholder aliases: " + ", ".join(str(alias) for alias in aliases))
        print("Validate after filling:")
        print(report.get("xlsx_validate_command") or report.get("validate_command", ""))
        return 0

    if args.command == "final-answer-revision-user-input":
        autopilot_path = Path(args.autopilot_json)
        if not autopilot_path.exists():
            raise FileNotFoundError(f"final answer autopilot report not found: {args.autopilot_json}")
        template_path = Path(args.template)
        template = {}
        if template_path.exists():
            template = json.loads(template_path.read_text(encoding="utf-8"))
        report = write_final_answer_revision_user_input_file(
            json.loads(autopilot_path.read_text(encoding="utf-8")),
            template,
            args.output,
            args.xlsx_output,
            base_reply_file=args.base_reply_file,
        )
        print(f"Wrote final answer revision input file to {report['output']}")
        if report.get("xlsx_output"):
            print(f"Wrote final answer revision input Excel to {report['xlsx_output']}")
        print(f"Revision placeholders: {report.get('placeholder_count', 0)}")
        aliases = report.get("placeholder_aliases") if isinstance(report.get("placeholder_aliases"), list) else []
        if aliases:
            print("Revision aliases: " + ", ".join(str(alias) for alias in aliases))
        if report.get("base_reply_file"):
            print(f"Base reply file: {report.get('base_reply_file')}")
        print("Validate after filling:")
        print(report.get("validate_command", ""))
        return 0

    if args.command == "resume-after-answers":
        if bool(getattr(args, "reply_stdin", False)) and args.reply_text is not None:
            raise ValueError("--reply-stdin cannot be combined with --reply-text")
        resume_reply_text = getattr(args, "reply_text", None)
        resume_reply_from_stdin = bool(getattr(args, "reply_stdin", False))
        if bool(getattr(args, "reply_stdin", False)):
            resume_reply_text = sys.stdin.read()
        resume_reply_file = None if (resume_reply_text is not None or resume_reply_from_stdin) else args.reply_file
        resume_validate_only = bool(getattr(args, "validate_only", False))
        placeholder_source = (
            "<inline reply text redacted>"
            if resume_reply_text is not None and not resume_reply_from_stdin
            else "<stdin reply text redacted>"
            if resume_reply_from_stdin
            else str(resume_reply_file)
        )
        resume_base_reply_file = str(getattr(args, "base_reply_file", "") or "").strip()
        temp_revision_dir: tempfile.TemporaryDirectory[str] | None = None
        try:
            if resume_reply_text is not None:
                placeholder_reply_text = str(resume_reply_text)
            else:
                placeholder_path = Path(str(resume_reply_file))
                if not placeholder_path.exists():
                    print("Resume after answers: waiting_for_reply_file")
                    print(f"Reply file: {placeholder_path}")
                    return 2
                try:
                    placeholder_reply_text = final_answer_reply_text_from_file(placeholder_path)
                except Exception as exc:
                    print("Resume after answers: invalid_reply_file")
                    print(f"Reply file: {placeholder_path}")
                    print(f"Reason: {exc}")
                    return 2
            revision_placeholder_count = _final_answer_reply_placeholder_count(
                placeholder_reply_text
            )
            if revision_placeholder_count:
                placeholder_aliases = _final_answer_reply_placeholder_aliases(
                    placeholder_reply_text
                )
                print("Resume after answers: waiting_for_filled_reply")
                print(f"Reply source: {placeholder_source}")
                print(f"Placeholder lines remaining: {revision_placeholder_count}")
                if placeholder_aliases:
                    print("Placeholder aliases: " + ", ".join(placeholder_aliases))
                return 2
            if resume_base_reply_file:
                if not Path(resume_base_reply_file).exists():
                    print("Resume after answers: waiting_for_base_reply_file")
                    print(f"Base reply file: {resume_base_reply_file}")
                    return 2
                if resume_reply_text is not None:
                    temp_revision_dir = tempfile.TemporaryDirectory(
                        prefix="job_apply_resume_revision_"
                    )
                    revision_path = Path(temp_revision_dir.name) / "revision.txt"
                    revision_path.write_text(str(resume_reply_text), encoding="utf-8")
                else:
                    revision_path = Path(str(resume_reply_file))
                try:
                    template_payload = json.loads(
                        Path(args.template).read_text(encoding="utf-8")
                    )
                    reply_context = _final_answer_autopilot_reply_context(
                        args,
                        revision_path,
                        template_payload,
                    )
                except Exception as exc:
                    print("Resume after answers: invalid_merged_reply")
                    print(f"Base reply file: {resume_base_reply_file}")
                    print(f"Revision reply source: {placeholder_source}")
                    print(f"Reason: {exc}")
                    return 2
                if int(reply_context.get("parser_error_count") or 0):
                    print("Resume after answers: invalid_merged_reply")
                    print(f"Base reply file: {resume_base_reply_file}")
                    print(f"Revision reply source: {placeholder_source}")
                    print(
                        "Parser errors: "
                        f"{int(reply_context.get('parser_error_count') or 0)}"
                    )
                    return 2
                placeholder_reply_text = str(reply_context.get("reply_text") or "")
                resume_reply_text = placeholder_reply_text
                resume_reply_file = None
                resume_reply_from_stdin = False
                placeholder_source = (
                    f"merged reply from {resume_base_reply_file} + {placeholder_source}"
                )
        finally:
            if temp_revision_dir is not None:
                temp_revision_dir.cleanup()
        placeholder_count = _final_answer_reply_placeholder_count(placeholder_reply_text)
        if placeholder_count:
            placeholder_aliases = _final_answer_reply_placeholder_aliases(placeholder_reply_text)
            print("Resume after answers: waiting_for_filled_reply")
            print(f"Reply source: {placeholder_source}")
            print(f"Placeholder lines remaining: {placeholder_count}")
            if placeholder_aliases:
                print("Placeholder aliases: " + ", ".join(placeholder_aliases))
            return 2
        args.command = "final-answer-reply"
        args.template = str(args.template)
        args.unblockers = str(args.unblockers)
        args.reply_text = resume_reply_text
        args.reply_file = resume_reply_file
        args.reply_stdin = False
        args.json_output = str(DEFAULT_FINAL_ANSWER_REPLY_JSON)
        args.markdown_output = str(DEFAULT_FINAL_ANSWER_REPLY_MARKDOWN)
        args.intake_output = str(DEFAULT_FINAL_ANSWER_REPLY_PAYLOAD_JSON)
        args.compact_updates_output = str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_UPDATES_JSON)
        args.final_answer_intake_report_json = str(DEFAULT_FINAL_ANSWER_INTAKE_REPORT_JSON)
        args.final_answer_intake_report_markdown = str(DEFAULT_FINAL_ANSWER_INTAKE_REPORT_MARKDOWN)
        args.full_template = str(DEFAULT_CRITICAL_INPUT_FULL_UPDATES_JSON)
        args.confirmed_updates_output = str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_JSON)
        args.confirmed_report_json_output = str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_REPORT_JSON)
        args.confirmed_report_markdown_output = str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_REPORT_MARKDOWN)
        args.confirm_high_risk = False
        args.finalize = False
        args.run_post_answer_pipeline = not resume_validate_only
        args.validate_only = resume_validate_only
        args.synthetic_rehearse_queue = False
        args.post_answer_apply = not resume_validate_only
        args.post_answer_live_check = not resume_validate_only
        args.post_answer_live_check_limit = args.live_check_limit
        args.post_answer_live_check_timeout = args.live_check_timeout
        args.post_answer_include_values = not resume_validate_only
        args.post_answer_open_browser = bool(args.open_browser) and not resume_validate_only
        args.post_answer_open_limit = args.open_limit
        args.post_answer_json_output = str(DEFAULT_POST_ANSWER_PIPELINE_JSON)
        args.post_answer_markdown_output = str(DEFAULT_POST_ANSWER_PIPELINE_MARKDOWN)
        args.fail_on_not_ready = True

    if args.command == "rehearse-after-answers":
        post_answer_json_output = args.json_output
        post_answer_markdown_output = args.markdown_output
        template_path = Path(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_JSON)
        if not template_path.exists():
            raise FileNotFoundError(f"final answer intake template not found: {template_path}")
        args.command = "final-answer-reply"
        args.template = str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_JSON)
        args.full_template = str(DEFAULT_CRITICAL_INPUT_FULL_UPDATES_JSON)
        args.unblockers = str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_JSON)
        args.reply_text = build_synthetic_final_answer_reply_text(
            json.loads(template_path.read_text(encoding="utf-8"))
        )
        args.reply_file = None
        args.reply_stdin = False
        args.json_output = str(DEFAULT_FINAL_ANSWER_REPLY_JSON)
        args.markdown_output = str(DEFAULT_FINAL_ANSWER_REPLY_MARKDOWN)
        args.intake_output = str(DEFAULT_FINAL_ANSWER_REPLY_PAYLOAD_JSON)
        args.compact_updates_output = str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_UPDATES_JSON)
        args.confirmed_updates_output = str(DEFAULT_POST_ANSWER_SYNTHETIC_CONFIRMED_UPDATES_JSON)
        args.confirmed_report_json_output = str(DEFAULT_POST_ANSWER_SYNTHETIC_CONFIRMED_UPDATES_REPORT_JSON)
        args.confirmed_report_markdown_output = str(DEFAULT_POST_ANSWER_SYNTHETIC_CONFIRMED_UPDATES_REPORT_MARKDOWN)
        args.final_answer_intake_report_json = str(DEFAULT_FINAL_ANSWER_REPLY_SYNTHETIC_INTAKE_REPORT_JSON)
        args.final_answer_intake_report_markdown = str(DEFAULT_FINAL_ANSWER_REPLY_SYNTHETIC_INTAKE_REPORT_MARKDOWN)
        args.confirm_high_risk = False
        args.finalize = False
        args.run_post_answer_pipeline = False
        args.validate_only = False
        args.synthetic_rehearse_queue = True
        args.post_answer_apply = False
        args.post_answer_live_check = False
        args.post_answer_live_check_limit = 100
        args.post_answer_live_check_timeout = 25.0
        args.post_answer_include_values = False
        args.post_answer_open_browser = False
        args.post_answer_open_limit = 100
        args.review_log = str(DEFAULT_REVIEW_LOG)
        args.post_answer_json_output = post_answer_json_output
        args.post_answer_markdown_output = post_answer_markdown_output
        args.fail_on_not_ready = True

    if args.command == "final-answer-autopilot":
        return _run_final_answer_autopilot(args)

    if args.command == "final-answer-reply":
        reply_source_count = (
            int(args.reply_text is not None)
            + int(bool(args.reply_file))
            + int(bool(getattr(args, "reply_stdin", False)))
        )
        if reply_source_count != 1:
            raise ValueError("provide exactly one of --reply-text, --reply-file, or --reply-stdin")
        _validate_final_answer_intake_server_post_answer_args(args)
        synthetic_reply_rehearsal = bool(args.synthetic_rehearse_queue)
        reply_json_output = _synthetic_default_path(
            args.json_output,
            DEFAULT_FINAL_ANSWER_REPLY_JSON,
            DEFAULT_FINAL_ANSWER_REPLY_SYNTHETIC_JSON,
            synthetic_reply_rehearsal,
        )
        reply_markdown_output = _synthetic_default_path(
            args.markdown_output,
            DEFAULT_FINAL_ANSWER_REPLY_MARKDOWN,
            DEFAULT_FINAL_ANSWER_REPLY_SYNTHETIC_MARKDOWN,
            synthetic_reply_rehearsal,
        )
        intake_output = _synthetic_default_path(
            args.intake_output,
            DEFAULT_FINAL_ANSWER_REPLY_PAYLOAD_JSON,
            DEFAULT_FINAL_ANSWER_REPLY_SYNTHETIC_PAYLOAD_JSON,
            synthetic_reply_rehearsal,
        )
        compact_updates_output = _synthetic_default_path(
            args.compact_updates_output,
            DEFAULT_CRITICAL_INPUT_UNBLOCKERS_UPDATES_JSON,
            DEFAULT_POST_ANSWER_SYNTHETIC_COMPACT_UPDATES_JSON,
            synthetic_reply_rehearsal,
        )
        intake_report_json_output = _synthetic_default_path(
            args.final_answer_intake_report_json,
            DEFAULT_FINAL_ANSWER_INTAKE_REPORT_JSON,
            DEFAULT_FINAL_ANSWER_REPLY_SYNTHETIC_INTAKE_REPORT_JSON,
            synthetic_reply_rehearsal,
        )
        intake_report_markdown_output = _synthetic_default_path(
            args.final_answer_intake_report_markdown,
            DEFAULT_FINAL_ANSWER_INTAKE_REPORT_MARKDOWN,
            DEFAULT_FINAL_ANSWER_REPLY_SYNTHETIC_INTAKE_REPORT_MARKDOWN,
            synthetic_reply_rehearsal,
        )
        confirmed_updates_output = _synthetic_default_path(
            args.confirmed_updates_output,
            DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_JSON,
            DEFAULT_POST_ANSWER_SYNTHETIC_CONFIRMED_UPDATES_JSON,
            synthetic_reply_rehearsal,
        )
        confirmed_report_json_output = _synthetic_default_path(
            args.confirmed_report_json_output,
            DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_REPORT_JSON,
            DEFAULT_POST_ANSWER_SYNTHETIC_CONFIRMED_UPDATES_REPORT_JSON,
            synthetic_reply_rehearsal,
        )
        confirmed_report_markdown_output = _synthetic_default_path(
            args.confirmed_report_markdown_output,
            DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_REPORT_MARKDOWN,
            DEFAULT_POST_ANSWER_SYNTHETIC_CONFIRMED_UPDATES_REPORT_MARKDOWN,
            synthetic_reply_rehearsal,
        )
        template_path = Path(args.template)
        if not template_path.exists():
            raise FileNotFoundError(f"final answer intake template not found: {args.template}")
        reply_text = args.reply_text
        if bool(getattr(args, "reply_stdin", False)):
            reply_text = sys.stdin.read()
        elif args.reply_file:
            reply_path = Path(args.reply_file)
            if not reply_path.exists():
                raise FileNotFoundError(f"final answer reply file not found: {args.reply_file}")
            reply_text = final_answer_reply_text_from_file(reply_path)
        unblockers_path = Path(args.unblockers)
        if not unblockers_path.exists():
            raise FileNotFoundError(f"critical input unblockers not found: {args.unblockers}")
        template_payload = json.loads(template_path.read_text(encoding="utf-8"))
        unblockers_payload = json.loads(unblockers_path.read_text(encoding="utf-8"))
        if args.validate_only:
            report = build_final_answer_reply_intake(
                template_payload,
                str(reply_text or ""),
                confirm_high_risk=args.confirm_high_risk,
                allow_synthetic_values=synthetic_reply_rehearsal,
            )
            intake_payload = report.get("intake_payload") if isinstance(report.get("intake_payload"), dict) else {}
            intake_report = build_final_answer_intake_update(
                unblockers_payload,
                intake_payload,
                confirm_high_risk=args.confirm_high_risk,
            )
            intake_summary = intake_report.get("summary") or {}
            print("Validated final answer reply without writing files.")
            print(f"Parsed answers: {report.get('answer_count', 0)}")
            print(f"Unknown keys: {report.get('unknown_key_count', 0)}")
            print(f"Duplicate keys: {report.get('duplicate_key_count', 0)}")
            print(f"Fake/test markers: {report.get('fake_marker_count', 0)}")
            print(f"Ready for finalize: {str(bool(intake_report.get('ready_for_finalize'))).lower()}")
            print(f"Missing unblockers: {intake_summary.get('missing_unblocker_count', 0)}")
            print(f"High-risk confirmations missing: {intake_summary.get('unconfirmed_high_risk_count', 0)}")
            print(f"Needs more specificity: {intake_summary.get('needs_more_specific_answer_count', 0)}")
            print(f"Unknown answers: {intake_summary.get('unknown_answer_count', 0)}")
            _print_final_answer_reply_problem_aliases(report)
            _print_final_answer_intake_problem_aliases(intake_report)
            parser_has_errors = bool(
                int(report.get("unknown_key_count") or 0)
                or int(report.get("duplicate_key_count") or 0)
                or (
                    int(report.get("fake_marker_count") or 0)
                    and not synthetic_reply_rehearsal
                )
            )
            if args.fail_on_not_ready and (not intake_report.get("ready_for_finalize") or parser_has_errors):
                return 2
            return 0
        report = write_final_answer_reply_intake(
            template_payload,
            str(reply_text or ""),
            reply_json_output,
            reply_markdown_output,
            confirm_high_risk=args.confirm_high_risk,
            allow_synthetic_values=synthetic_reply_rehearsal,
        )
        print(f"Wrote final answer reply intake JSON to {reply_json_output}")
        print(f"Wrote final answer reply intake Markdown to {reply_markdown_output}")
        print(f"Parsed answers: {report.get('answer_count', 0)}")
        print(f"Unknown keys: {report.get('unknown_key_count', 0)}")
        print(f"Duplicate keys: {report.get('duplicate_key_count', 0)}")
        print(f"Fake/test markers: {report.get('fake_marker_count', 0)}")
        intake_payload = report.get("intake_payload") if isinstance(report.get("intake_payload"), dict) else {}
        intake_output_path = Path(intake_output)
        intake_output_path.parent.mkdir(parents=True, exist_ok=True)
        intake_output_path.write_text(
            json.dumps(intake_payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote final answer intake payload JSON to {intake_output}")
        intake_report = write_final_answer_intake_update(
            unblockers_payload,
            intake_payload,
            compact_updates_output,
            intake_report_json_output,
            intake_report_markdown_output,
            confirm_high_risk=args.confirm_high_risk,
        )
        intake_summary = intake_report.get("summary") or {}
        print(f"Wrote compact final-answer updates to {compact_updates_output}")
        print(f"Wrote final answer intake report JSON to {intake_report_json_output}")
        print(f"Ready for finalize: {str(bool(intake_report.get('ready_for_finalize'))).lower()}")
        print(f"Missing unblockers: {intake_summary.get('missing_unblocker_count', 0)}")
        print(f"High-risk confirmations missing: {intake_summary.get('unconfirmed_high_risk_count', 0)}")
        print(f"Needs more specificity: {intake_summary.get('needs_more_specific_answer_count', 0)}")
        print(f"Unknown answers: {intake_summary.get('unknown_answer_count', 0)}")
        _print_final_answer_reply_problem_aliases(report)
        _print_final_answer_intake_problem_aliases(intake_report)
        if args.finalize:
            final_report = write_critical_input_unblocker_final_update(
                compact_updates_output,
                args.full_template,
                args.unblockers,
                confirmed_updates_output,
                confirmed_report_json_output,
                confirmed_report_markdown_output,
            )
            final_summary = final_report.get("summary") or {}
            print(f"Wrote confirmed updates JSON to {confirmed_updates_output}")
            print(
                "Confirmed updates ready for workflow: "
                f"{str(bool(final_report.get('ready_for_workflow'))).lower()}"
            )
            print(f"Confirmed missing unblockers: {final_summary.get('missing_unblocker_count', 0)}")
            print(
                "Confirmed high-risk confirmations missing: "
                f"{final_summary.get('unconfirmed_high_risk_count', 0)}"
            )
            if args.fail_on_not_ready and not final_report.get("ready_for_workflow"):
                return 2
        parser_has_errors = bool(
            int(report.get("unknown_key_count") or 0)
            or int(report.get("duplicate_key_count") or 0)
            or (
                int(report.get("fake_marker_count") or 0)
                and not synthetic_reply_rehearsal
            )
        )
        if synthetic_reply_rehearsal:
            if not intake_report.get("ready_for_finalize") or parser_has_errors:
                print("Synthetic queue rehearsal skipped: final answer reply is not ready.")
                if args.fail_on_not_ready:
                    return 2
                return 0
            final_report = write_critical_input_unblocker_final_update(
                compact_updates_output,
                args.full_template,
                args.unblockers,
                confirmed_updates_output,
                confirmed_report_json_output,
                confirmed_report_markdown_output,
            )
            synthetic_steps: list[dict[str, object]] = [
                {
                    "name": "final_answer_reply_intake",
                    "status": "ready",
                    "details": {
                        "answers": intake_summary.get("answer_input_count", 0),
                        "compact_updates": intake_summary.get("compact_update_count", 0),
                    },
                },
                {
                    "name": "finalize_synthetic_confirmed_updates",
                    "status": "ready" if final_report.get("ready_for_workflow") else "waiting_for_answers",
                    "details": (final_report.get("summary") or {}),
                },
            ]
            synthetic_queue_rehearsal = (
                _run_synthetic_post_answer_queue_rehearsal(confirmed_updates_output, synthetic_steps)
                if final_report.get("ready_for_workflow")
                else {}
            )
            rehearsal_ready = bool(
                final_report.get("ready_for_workflow")
                and synthetic_queue_rehearsal.get("ready_for_supervised_browser_autofill")
            )
            synthetic_report = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source": "final_answer_reply_synthetic_rehearsal",
                "status": (
                    "synthetic_queue_rehearsal_ready"
                    if rehearsal_ready
                    else "synthetic_queue_rehearsal_not_ready"
                ),
                "ready_for_workflow": bool(final_report.get("ready_for_workflow")),
                "apply_requested": False,
                "live_check_requested": False,
                "open_browser_requested": False,
                "include_values": False,
                "synthetic_final_answers": True,
                "synthetic_queue_rehearsal_requested": True,
                "final_answer_intake_json": str(intake_output),
                "final_answer_intake_report_outputs": {
                    "json": str(intake_report_json_output),
                    "markdown": str(intake_report_markdown_output),
                },
                "final_answer_intake_report": {
                    key: value for key, value in intake_report.items() if key != "compact_updates"
                },
                "confirmed_updates_output": str(confirmed_updates_output),
                "final_update_report_outputs": {
                    "json": str(confirmed_report_json_output),
                    "markdown": str(confirmed_report_markdown_output),
                },
                "final_update_report": {
                    key: value for key, value in final_report.items() if key != "merged_updates"
                },
                "synthetic_queue_rehearsal": synthetic_queue_rehearsal,
                "steps": synthetic_steps,
                "policy": {
                    "submits_real_applications": False,
                    "writes_real_profile_or_memory": False,
                    "opens_browser": False,
                    "runs_live_check": False,
                    "final_submit_remains_supervised": True,
                    "synthetic_queue_rehearsal_uses_fake_local_profile_and_memory": True,
                },
            }
            _write_post_answer_pipeline_report(
                synthetic_report,
                args.post_answer_json_output,
                args.post_answer_markdown_output,
            )
            print(f"Wrote synthetic reply rehearsal JSON to {args.post_answer_json_output}")
            print(f"Wrote synthetic reply rehearsal Markdown to {args.post_answer_markdown_output}")
            print(f"Synthetic queue rehearsal: {synthetic_queue_rehearsal.get('status') or 'not_built'}")
            print(f"Synthetic selected: {synthetic_queue_rehearsal.get('autofill_packet_selected', 0)}")
            print(f"Synthetic selector misses: {synthetic_queue_rehearsal.get('autofill_packet_selector_misses', 0)}")
            print(f"Synthetic final-submit stops: {synthetic_queue_rehearsal.get('autofill_packet_final_submit_stops', 0)}")
            if args.fail_on_not_ready and not rehearsal_ready:
                return 2
            return 0
        if args.run_post_answer_pipeline:
            if not intake_report.get("ready_for_finalize") or parser_has_errors:
                print("Post-answer pipeline skipped: final answer reply is not ready.")
                if args.fail_on_not_ready:
                    return 2
                return 0
            pipeline_args = argparse.Namespace(
                compact_updates=compact_updates_output,
                full_template=args.full_template,
                unblockers=args.unblockers,
                confirmed_updates_output=confirmed_updates_output,
                confirmed_report_json_output=confirmed_report_json_output,
                confirmed_report_markdown_output=confirmed_report_markdown_output,
                final_answer_intake_json=intake_output,
                final_answer_intake_report_json=intake_report_json_output,
                final_answer_intake_report_markdown=intake_report_markdown_output,
                confirm_high_risk=args.confirm_high_risk,
                synthetic_final_answers=False,
                synthetic_rehearse_queue=False,
                apply=args.post_answer_apply,
                live_check=args.post_answer_live_check,
                live_check_limit=args.post_answer_live_check_limit,
                live_check_timeout=args.post_answer_live_check_timeout,
                include_values=args.post_answer_include_values,
                open_browser=args.post_answer_open_browser,
                open_limit=args.post_answer_open_limit,
                review_log=args.review_log,
                json_output=args.post_answer_json_output,
                markdown_output=args.post_answer_markdown_output,
                fail_on_not_ready=args.fail_on_not_ready,
            )
            return _run_post_answer_pipeline(pipeline_args)
        if args.fail_on_not_ready and (
            not intake_report.get("ready_for_finalize")
            or parser_has_errors
        ):
            return 2
        return 0

    if args.command == "post-answer-pipeline":
        return _run_post_answer_pipeline(args)

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
        print(f"High-risk confirmations updated: {summary.get('high_risk_confirmation_updated_count', 0)}")
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

    if args.command == "critical-inputs-readiness":
        for label, path_value in [
            ("approval pack", args.approval_pack),
            ("critical input answers", args.answers),
            ("critical input updates", args.updates),
            ("research report", args.research_json),
            ("profile", args.profile),
        ]:
            if not Path(path_value).exists():
                raise FileNotFoundError(f"{label} not found: {path_value}")
        report = write_critical_input_updates_readiness(
            args.approval_pack,
            args.answers,
            args.updates,
            args.research_json,
            args.profile,
            args.memory,
            args.json_output,
            args.markdown_output,
            closed_jobs=_load_optional_json(args.closed_jobs),
        )
        summary = report.get("summary") or {}
        print(f"Wrote critical input updates readiness JSON to {args.json_output}")
        print(f"Wrote critical input updates readiness Markdown to {args.markdown_output}")
        print(f"Ready for apply: {str(bool(report.get('ready_for_apply'))).lower()}")
        print(f"Waiting after update: {summary.get('waiting_after_update_count', 0)}")
        print(f"High-risk confirmations missing: {summary.get('high_risk_unconfirmed_count', 0)}")
        print(f"Unknown updates: {summary.get('unknown_updates', 0)}")
        print(f"Data-blocking prompts after: {summary.get('data_blocking_prompts_after', 0)}")
        if args.fail_on_not_ready and not report.get("ready_for_apply"):
            return 2
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
            individual_impact_limit=None if args.individual_limit < 0 else args.individual_limit,
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
            allow_partial_apply=args.allow_partial_apply,
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

    if args.command == "synthetic-unblocker-proof":
        for label, path_value in [
            ("approval pack", args.approval_pack),
            ("critical input answers", args.answers),
            ("critical input unblockers", args.unblockers),
            ("research report", args.research_json),
            ("profile", args.profile),
        ]:
            if not Path(path_value).exists():
                raise FileNotFoundError(f"{label} not found: {path_value}")
        proof = write_synthetic_unblocker_proof(
            args.approval_pack,
            args.answers,
            args.unblockers,
            args.research_json,
            args.profile,
            args.memory,
            args.json_output,
            args.markdown_output,
            closed_jobs=_load_optional_json(args.closed_jobs),
            autofill_batch=_load_optional_json(args.autofill_batch),
        )
        summary = proof.get("summary") or {}
        print(f"Wrote synthetic unblocker proof JSON to {args.json_output}")
        print(f"Wrote synthetic unblocker proof Markdown to {args.markdown_output}")
        print(f"Synthetic final unblockers: {summary.get('synthetic_final_unblocker_update_count', 0)}")
        print(
            "Data-blocking prompts: "
            f"{summary.get('data_blocking_prompts_before', 0)} -> "
            f"{summary.get('data_blocking_prompts_after', 0)}"
        )
        print(f"Local 100 synthetic path ready: {str(bool(summary.get('local_100_synthetic_apply_path_ready'))).lower()}")
        print(f"Proof complete: {str(bool(summary.get('proof_complete'))).lower()}")
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
        live_skip_reasons: dict[str, str] = {}
        if args.live_check:
            live_result = refresh_closed_jobs_from_live_pages(
                submissions,
                args.closed_jobs,
                max_checks=args.live_check_limit,
                timeout=args.live_check_timeout,
            )
            closed_jobs = live_result["closed_jobs"]
            live_skip_reasons = _live_skip_reasons_from_checks(live_result)
            closed_count = sum(1 for check in live_result["checks"] if check.get("closed"))
            error_count = sum(1 for check in live_result["checks"] if check.get("error"))
            unverified_count = sum(1 for check in live_result["checks"] if check.get("skip_for_open"))
            print(
                f"Live checked {len(live_result['checks'])} page(s); "
                f"recorded {closed_count} closed; unverified={unverified_count}; errors={error_count}"
            )
        result = notify_telegram_for_submissions(
            submissions,
            env_path=args.telegram_env,
            dry_run=args.telegram_dry_run,
            closed_jobs=closed_jobs,
            max_items=args.limit,
            live_skip_reasons=live_skip_reasons,
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
                live_skip_reasons=live_skip_reasons,
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

    live_skip_reasons: dict[str, str] = {}
    if args.live_check:
        live_result = refresh_closed_jobs_from_live_pages(
            submissions,
            args.closed_jobs,
            max_checks=args.live_check_limit,
            timeout=args.live_check_timeout,
        )
        closed_jobs = live_result["closed_jobs"]
        live_skip_reasons = _live_skip_reasons_from_checks(live_result)
        closed_count = sum(1 for check in live_result["checks"] if check.get("closed"))
        error_count = sum(1 for check in live_result["checks"] if check.get("error"))
        unverified_count = sum(1 for check in live_result["checks"] if check.get("skip_for_open"))
        print(
            f"Live checked {len(live_result['checks'])} page(s); "
            f"recorded {closed_count} closed; unverified={unverified_count}; errors={error_count}"
        )

    if args.notify_telegram:
        result = notify_telegram_for_submissions(
            submissions,
            env_path=args.telegram_env,
            dry_run=args.telegram_dry_run,
            closed_jobs=closed_jobs,
            max_items=args.limit,
            live_skip_reasons=live_skip_reasons,
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
            live_skip_reasons=live_skip_reasons,
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


def _final_answer_reply_placeholder_count(reply_text: str) -> int:
    count = 0
    for line in reply_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "<fill>" in stripped:
            count += 1
    return count


def _final_answer_reply_placeholder_aliases(reply_text: str) -> list[str]:
    aliases: list[str] = []
    seen: set[str] = set()
    for line in reply_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "<fill>" not in stripped:
            continue
        alias = _final_answer_reply_placeholder_alias(stripped)
        if alias and alias not in seen:
            aliases.append(alias)
            seen.add(alias)
    return aliases


def _final_answer_reply_placeholder_alias(line: str) -> str:
    prefix = str(line or "").split("<fill>", 1)[0].strip()
    for separator in ["\uff1a", ":"]:
        if separator in prefix:
            prefix = prefix.split(separator, 1)[0].strip()
            break
    return prefix.strip("`* ")


def _final_answer_autopilot_validate_command(
    args: argparse.Namespace,
    reply_file: str | Path | None = None,
) -> list[str]:
    return [
        sys.executable,
        "-m",
        "job_apply_agent",
        "final-answer-reply",
        "--reply-file",
        str(reply_file or args.reply_file),
        "--template",
        str(args.template),
        "--unblockers",
        str(args.unblockers),
        "--validate-only",
        "--fail-on-not-ready",
    ]


def _final_answer_autopilot_pipeline_command(
    args: argparse.Namespace,
    reply_file: str | Path | None = None,
) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "job_apply_agent",
        "final-answer-reply",
        "--reply-file",
        str(reply_file or args.reply_file),
        "--template",
        str(args.template),
        "--unblockers",
        str(args.unblockers),
        "--run-post-answer-pipeline",
        "--fail-on-not-ready",
    ]
    if args.apply:
        command.append("--post-answer-apply")
    if args.live_check:
        command.extend(
            [
                "--post-answer-live-check",
                "--post-answer-live-check-limit",
                str(args.live_check_limit),
                "--post-answer-live-check-timeout",
                str(args.live_check_timeout),
            ]
        )
    if args.include_values:
        command.append("--post-answer-include-values")
    if args.open_browser:
        command.extend(["--post-answer-open-browser", "--post-answer-open-limit", str(args.open_limit)])
    if args.review_log:
        command.extend(["--review-log", str(args.review_log)])
    return command


def _final_answer_autopilot_audit_commands() -> list[tuple[str, list[str]]]:
    return [
        ("position_execution_audit", [sys.executable, "-m", "job_apply_agent", "position-execution-audit"]),
        ("selected_answer_dependencies", [sys.executable, "-m", "job_apply_agent", "selected-answer-dependencies"]),
        ("submission_safety_audit", [sys.executable, "-m", "job_apply_agent", "submission-safety-audit"]),
        ("goal_audit", [sys.executable, "-m", "job_apply_agent", "goal-audit"]),
        ("automation_handoff", [sys.executable, "-m", "job_apply_agent", "automation-handoff"]),
    ]


def _final_answer_autopilot_audit_command_rows() -> list[dict[str, str]]:
    return [
        {"name": name, "command": shlex.join(command)}
        for name, command in _final_answer_autopilot_audit_commands()
    ]


def _write_final_answer_autopilot_report(
    report: dict[str, object],
    json_output: str | Path,
    markdown_output: str | Path,
) -> None:
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_final_answer_autopilot_markdown(report), encoding="utf-8")


def _write_final_answer_revision_markdown(
    report: dict[str, object],
    markdown_output: str | Path,
) -> bool:
    validation_receipt = (
        report.get("validation_receipt")
        if isinstance(report.get("validation_receipt"), dict)
        else {}
    )
    problem_fields = (
        validation_receipt.get("problem_fields")
        if isinstance(validation_receipt.get("problem_fields"), list)
        else []
    )
    if not problem_fields:
        return False
    markdown_path = Path(markdown_output)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        _render_final_answer_revision_markdown(report, problem_fields),
        encoding="utf-8",
    )
    return True


def _render_final_answer_revision_markdown(
    report: dict[str, object],
    problem_fields: list[object],
) -> str:
    lines = [
        "# Final Answer Revision Needed",
        "",
        f"Generated: {report.get('generated_at')}",
        f"Validation status: `{report.get('status')}`",
        f"Reply source: `{report.get('reply_source', '')}`",
        f"Reply file: `{report.get('reply_file', '')}`",
        "",
        "This file intentionally redacts answer text. Revise only the rows below.",
        "",
        "| Alias | Status | Reason | What to add | Expected shape |",
        "| --- | --- | --- | --- | --- |",
    ]
    for raw_field in problem_fields:
        if not isinstance(raw_field, dict):
            continue
        alias = str(raw_field.get("alias") or "")
        status = str(raw_field.get("status") or "")
        reason = str(raw_field.get("specificity_reason") or "")
        hint = str(raw_field.get("hint") or "")
        expected_shape = str(raw_field.get("expected_shape") or "")
        lines.append(
            "| "
            + " | ".join(
                _final_answer_markdown_cell(value)
                for value in [alias, status, reason or "n/a", hint or "Use a specific reusable answer.", expected_shape or "n/a"]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "After editing, rerun:",
            "",
            "```bash",
            str(report.get("validate_command") or ""),
            "```",
            "",
            "The validation report and this revision prompt do not store answer text.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _final_answer_markdown_cell(value: object) -> str:
    text = str(value or "")
    text = text.replace("\n", " ").replace("|", "\\|")
    return text


def _final_answer_reply_parser_error_count(report: dict[str, object]) -> int:
    return (
        int(report.get("unknown_key_count") or 0)
        + int(report.get("duplicate_key_count") or 0)
        + int(report.get("fake_marker_count") or 0)
    )


def _final_answer_reply_text_from_answer_payload(
    template_payload: dict[str, object],
    answers: dict[str, object],
) -> str:
    lines: list[str] = []
    for field in template_payload.get("fields") or []:
        if not isinstance(field, dict):
            continue
        alias = str(field.get("alias") or "").strip()
        input_id = str(field.get("input_id") or "").strip()
        if not alias:
            continue
        value = answers.get(alias)
        if value is None and input_id:
            value = answers.get(input_id)
        if isinstance(value, dict):
            answer_text = str(value.get("answer") or value.get("user_answer") or "").strip()
            confirmed = bool(value.get("high_risk_user_confirmed"))
        else:
            answer_text = str(value or "").strip()
            confirmed = False
        if not answer_text:
            continue
        lines.append(f"{alias}\uff1a{answer_text}")
        if bool(field.get("high_risk")) and confirmed:
            lines.append(f"{alias}_confirmed\uff1a\u786e\u8ba4")
    return "\n".join(lines).rstrip() + "\n"


def _final_answer_autopilot_reply_context(
    args: argparse.Namespace,
    reply_path: Path,
    template_payload: dict[str, object],
) -> dict[str, object]:
    revision_text = final_answer_reply_text_from_file(reply_path)
    base_reply_file = str(getattr(args, "base_reply_file", "") or "").strip()
    if not base_reply_file:
        return {
            "reply_text": revision_text,
            "base_reply_file": "",
            "revision_reply_file": str(reply_path),
            "merged_with_base": False,
            "parser_error_count": 0,
        }

    base_path = Path(base_reply_file)
    if not base_path.exists():
        raise FileNotFoundError(f"base reply file does not exist: {base_reply_file}")
    base_text = final_answer_reply_text_from_file(base_path)
    base_report = build_final_answer_reply_intake(
        template_payload,
        base_text,
        confirm_high_risk=False,
        allow_synthetic_values=False,
    )
    revision_report = build_final_answer_reply_intake(
        template_payload,
        revision_text,
        confirm_high_risk=False,
        allow_synthetic_values=False,
    )
    base_payload = (
        base_report.get("intake_payload")
        if isinstance(base_report.get("intake_payload"), dict)
        else {}
    )
    revision_payload = (
        revision_report.get("intake_payload")
        if isinstance(revision_report.get("intake_payload"), dict)
        else {}
    )
    merged_answers = json.loads(
        json.dumps(base_payload.get("answers") or {}, ensure_ascii=True)
    )
    revision_answers = revision_payload.get("answers") if isinstance(revision_payload.get("answers"), dict) else {}
    for alias in revision_report.get("parsed_aliases") or []:
        if alias in revision_answers:
            merged_answers[str(alias)] = revision_answers[alias]
    merged_text = _final_answer_reply_text_from_answer_payload(template_payload, merged_answers)
    return {
        "reply_text": merged_text,
        "base_reply_file": str(base_path),
        "revision_reply_file": str(reply_path),
        "merged_with_base": True,
        "base_reply_summary": {
            "answer_count": int(base_report.get("answer_count") or 0),
            "unknown_key_count": int(base_report.get("unknown_key_count") or 0),
            "duplicate_key_count": int(base_report.get("duplicate_key_count") or 0),
            "fake_marker_count": int(base_report.get("fake_marker_count") or 0),
            "parsed_aliases": base_report.get("parsed_aliases") or [],
        },
        "revision_reply_summary": {
            "answer_count": int(revision_report.get("answer_count") or 0),
            "unknown_key_count": int(revision_report.get("unknown_key_count") or 0),
            "duplicate_key_count": int(revision_report.get("duplicate_key_count") or 0),
            "fake_marker_count": int(revision_report.get("fake_marker_count") or 0),
            "parsed_aliases": revision_report.get("parsed_aliases") or [],
        },
        "parser_error_count": _final_answer_reply_parser_error_count(base_report)
        + _final_answer_reply_parser_error_count(revision_report),
    }


def _final_answer_autopilot_validation_receipt(
    args: argparse.Namespace,
    reply_path: Path,
    reply_text: str | None = None,
) -> dict[str, object]:
    try:
        if not reply_path.exists():
            return {
                "available": False,
                "reason": "reply file does not exist",
                "stores_answer_text": False,
                "submits_real_applications": False,
            }
        template_path = Path(args.template)
        unblockers_path = Path(args.unblockers)
        if not template_path.exists():
            return {
                "available": False,
                "reason": f"template file does not exist: {template_path}",
                "stores_answer_text": False,
                "submits_real_applications": False,
            }
        if not unblockers_path.exists():
            return {
                "available": False,
                "reason": f"unblockers file does not exist: {unblockers_path}",
                "stores_answer_text": False,
                "submits_real_applications": False,
            }
        template_payload = json.loads(template_path.read_text(encoding="utf-8"))
        unblockers_payload = json.loads(unblockers_path.read_text(encoding="utf-8"))
        reply_context = _final_answer_autopilot_reply_context(args, reply_path, template_payload)
        if reply_text is None:
            reply_text = str(reply_context.get("reply_text") or "")
        reply_report = build_final_answer_reply_intake(
            template_payload,
            reply_text,
            confirm_high_risk=False,
            allow_synthetic_values=False,
        )
        intake_payload = (
            reply_report.get("intake_payload")
            if isinstance(reply_report.get("intake_payload"), dict)
            else {}
        )
        intake_report = build_final_answer_intake_update(
            unblockers_payload,
            intake_payload,
            confirm_high_risk=False,
        )
        template_fields = {
            str(field.get("alias") or "").strip(): field
            for field in template_payload.get("fields") or []
            if isinstance(field, dict) and str(field.get("alias") or "").strip()
        }
        problem_fields: list[dict[str, object]] = []
        for field in intake_report.get("fields") or []:
            if not isinstance(field, dict) or field.get("status") == "ready":
                continue
            alias = str(field.get("alias") or "").strip()
            template_field = template_fields.get(alias, {})
            problem_fields.append(
                {
                    "alias": alias,
                    "status": str(field.get("status") or ""),
                    "high_risk": bool(field.get("high_risk")),
                    "specificity_reason": str(field.get("specificity_reason") or ""),
                    "question": str(template_field.get("question") or ""),
                    "hint": str(
                        template_field.get("answer_specificity_hint")
                        or template_field.get("answer_format_hint")
                        or ""
                    ),
                    "expected_shape": str(template_field.get("answer_example_shape") or ""),
                    "observed_prompt": str(
                        (template_field.get("observed_prompt_examples") or [""])[0]
                        if isinstance(template_field.get("observed_prompt_examples"), list)
                        else ""
                    ),
                }
            )
        parser_has_errors = bool(
            int(reply_report.get("unknown_key_count") or 0)
            or int(reply_report.get("duplicate_key_count") or 0)
            or int(reply_report.get("fake_marker_count") or 0)
            or int(reply_context.get("parser_error_count") or 0)
        )
        return {
            "available": True,
            "ready_for_finalize": bool(intake_report.get("ready_for_finalize"))
            and not parser_has_errors,
            "parser_has_errors": parser_has_errors,
            "merged_with_base_reply": bool(reply_context.get("merged_with_base")),
            "base_reply_file": str(reply_context.get("base_reply_file") or ""),
            "revision_reply_file": str(reply_context.get("revision_reply_file") or ""),
            "answer_receipt": intake_report.get("answer_receipt") or {},
            "reply_summary": {
                "parsed_line_count": int(reply_report.get("parsed_line_count") or 0),
                "answer_count": int(reply_report.get("answer_count") or 0),
                "unknown_key_count": int(reply_report.get("unknown_key_count") or 0),
                "duplicate_key_count": int(reply_report.get("duplicate_key_count") or 0),
                "fake_marker_count": int(reply_report.get("fake_marker_count") or 0),
                "parsed_aliases": reply_report.get("parsed_aliases") or [],
                "confirmed_high_risk_aliases": reply_report.get("confirmed_high_risk_aliases") or [],
                "fake_marker_aliases": reply_report.get("fake_marker_aliases") or [],
                "base_answer_count": int(
                    (reply_context.get("base_reply_summary") or {}).get("answer_count")
                    if isinstance(reply_context.get("base_reply_summary"), dict)
                    else 0
                ),
                "revision_answer_count": int(
                    (reply_context.get("revision_reply_summary") or {}).get("answer_count")
                    if isinstance(reply_context.get("revision_reply_summary"), dict)
                    else 0
                ),
            },
            "intake_summary": intake_report.get("summary") or {},
            "problem_fields": problem_fields,
            "policy": {
                "stores_answer_text": False,
                "markdown_redacts_answer_text": True,
                "submits_real_applications": False,
                "blocks_fake_or_synthetic_values_for_real_apply": True,
            },
        }
    except Exception as exc:  # pragma: no cover - defensive report path
        return {
            "available": False,
            "reason": str(exc),
            "stores_answer_text": False,
            "submits_real_applications": False,
        }


def _append_final_answer_aliases(
    lines: list[str],
    label: str,
    aliases: object,
) -> None:
    safe_aliases = (
        [str(alias) for alias in aliases or [] if str(alias).strip()]
        if isinstance(aliases, list)
        else []
    )
    if safe_aliases:
        lines.append(f"- {label}: {', '.join(safe_aliases)}")
    else:
        lines.append(f"- {label}: none")


def _render_final_answer_autopilot_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Final Answer Autopilot",
        "",
        f"Generated: {report.get('generated_at')}",
        f"Status: {report.get('status')}",
        f"Reply source: {report.get('reply_source', 'reply_file')}",
        f"Reply file: `{report.get('reply_file')}`",
        f"Base reply file: `{report.get('base_reply_file', '')}`",
        f"Attempts: {report.get('attempt_count', 0)}",
        f"Placeholder lines remaining: {report.get('placeholder_line_count', 0)}",
        f"Placeholder aliases remaining: {report.get('placeholder_alias_count', 0)}",
        f"Validate exit code: {report.get('validate_exit_code', '')}",
        f"Pipeline exit code: {report.get('pipeline_exit_code', '')}",
        "",
    ]
    placeholder_aliases = (
        report.get("placeholder_aliases")
        if isinstance(report.get("placeholder_aliases"), list)
        else []
    )
    if placeholder_aliases:
        lines.extend(["## Placeholder Aliases", ""])
        for alias in placeholder_aliases:
            lines.append(f"- {alias}")
        lines.append("")
    validation_receipt = (
        report.get("validation_receipt")
        if isinstance(report.get("validation_receipt"), dict)
        else {}
    )
    if validation_receipt:
        answer_receipt = (
            validation_receipt.get("answer_receipt")
            if isinstance(validation_receipt.get("answer_receipt"), dict)
            else {}
        )
        reply_summary = (
            validation_receipt.get("reply_summary")
            if isinstance(validation_receipt.get("reply_summary"), dict)
            else {}
        )
        intake_summary = (
            validation_receipt.get("intake_summary")
            if isinstance(validation_receipt.get("intake_summary"), dict)
            else {}
        )
        lines.extend(
            [
                "## Validation Receipt",
                "",
                f"- available: {str(bool(validation_receipt.get('available'))).lower()}",
                f"- ready for finalize: {str(bool(validation_receipt.get('ready_for_finalize'))).lower()}",
                f"- parser has errors: {str(bool(validation_receipt.get('parser_has_errors'))).lower()}",
                f"- parsed answers: {reply_summary.get('answer_count', 0)}",
                f"- unknown keys: {reply_summary.get('unknown_key_count', 0)}",
                f"- duplicate keys: {reply_summary.get('duplicate_key_count', 0)}",
                f"- fake/test markers: {reply_summary.get('fake_marker_count', 0)}",
                f"- missing unblockers: {intake_summary.get('missing_unblocker_count', 0)}",
                f"- high-risk confirmations missing: {intake_summary.get('unconfirmed_high_risk_count', 0)}",
                f"- needs more specificity: {intake_summary.get('needs_more_specific_answer_count', 0)}",
                f"- unknown answers: {intake_summary.get('unknown_answer_count', 0)}",
            ]
        )
        if validation_receipt.get("reason"):
            lines.append(f"- reason: {validation_receipt.get('reason')}")
        _append_final_answer_aliases(lines, "ready aliases", answer_receipt.get("ready_aliases"))
        _append_final_answer_aliases(lines, "missing aliases", answer_receipt.get("missing_aliases"))
        _append_final_answer_aliases(
            lines,
            "unconfirmed high-risk aliases",
            answer_receipt.get("unconfirmed_high_risk_aliases"),
        )
        _append_final_answer_aliases(
            lines,
            "needs more specific aliases",
            answer_receipt.get("needs_more_specific_aliases"),
        )
        _append_final_answer_aliases(
            lines,
            "fake/test marker aliases",
            reply_summary.get("fake_marker_aliases"),
        )
        lines.append("")
    lines.extend(
        [
            "## Commands",
            "",
            f"- validate: `{report.get('validate_command', '')}`",
            f"- pipeline: `{report.get('pipeline_command', '')}`",
            f"- revision prompt: `{report.get('revision_markdown_output', '')}`",
            "",
            "## Final Audits",
            "",
            f"- requested: {str(bool(report.get('final_audits_requested'))).lower()}",
        ]
    )
    audit_rows = report.get("final_audits") if isinstance(report.get("final_audits"), list) else []
    if audit_rows:
        for row in audit_rows:
            if isinstance(row, dict):
                lines.append(
                    f"- {row.get('name')}: {row.get('status')} (exit {row.get('exit_code')})"
                )
    else:
        lines.append("- no audit commands ran")
    audit_command_rows = (
        report.get("final_audit_commands")
        if isinstance(report.get("final_audit_commands"), list)
        else []
    )
    if audit_command_rows:
        lines.extend(["", "Audit commands:"])
        for row in audit_command_rows:
            if isinstance(row, dict):
                lines.append(f"- {row.get('name')}: `{row.get('command')}`")
    lines.extend(
        [
            "",
            "## Policy",
            "",
            "- answer text stored in report: false",
            "- Telegram answer text sent: false",
            f"- real applications submitted: {str(bool(report.get('submits_real_applications'))).lower()}",
            "- final submit remains supervised: true",
        ]
    )
    return "\n".join(lines) + "\n"


def _final_answer_autopilot_base_report(
    args: argparse.Namespace,
    *,
    status: str,
    attempt_count: int,
    placeholder_line_count: int,
    validate_command: list[str],
    pipeline_command: list[str],
    validate_exit_code: int | None = None,
    pipeline_exit_code: int | None = None,
    final_audits: list[dict[str, object]] | None = None,
    placeholder_aliases: list[str] | None = None,
    reason: str = "",
    reply_source: str = "reply_file",
    reply_file_for_report: str | Path | None = None,
    validation_receipt: dict[str, object] | None = None,
) -> dict[str, object]:
    safe_placeholder_aliases = [str(alias) for alias in placeholder_aliases or [] if str(alias).strip()]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "final_answer_autopilot",
        "status": status,
        "reason": reason,
        "reply_source": reply_source,
        "reply_file": str(reply_file_for_report or args.reply_file),
        "base_reply_file": str(getattr(args, "base_reply_file", "") or ""),
        "watch": bool(args.watch),
        "dry_run": bool(args.dry_run),
        "run_post_answer_pipeline": not bool(args.no_run_post_answer_pipeline),
        "apply_requested": bool(args.apply),
        "live_check_requested": bool(args.live_check),
        "include_values": bool(args.include_values),
        "open_browser_requested": bool(args.open_browser),
        "attempt_count": attempt_count,
        "placeholder_line_count": placeholder_line_count,
        "placeholder_alias_count": len(safe_placeholder_aliases),
        "placeholder_aliases": safe_placeholder_aliases,
        "validation_receipt": validation_receipt or {},
        "revision_markdown_output": str(getattr(args, "revision_markdown_output", "")),
        "validate_command": shlex.join(validate_command),
        "pipeline_command": shlex.join(pipeline_command),
        "final_audits_requested": not bool(args.skip_final_audits),
        "final_audit_commands": _final_answer_autopilot_audit_command_rows(),
        "final_audits": final_audits or [],
        "validate_exit_code": validate_exit_code,
        "pipeline_exit_code": pipeline_exit_code,
        "stores_answer_text_in_report": False,
        "sends_answer_text_to_telegram": False,
        "submits_real_applications": False,
        "final_submit_remains_supervised": True,
    }


def _run_final_answer_autopilot_final_audits() -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for name, command in _final_answer_autopilot_audit_commands():
        result = subprocess.run(
            command,
            cwd=Path.cwd(),
            check=False,
            text=True,
            capture_output=True,
        )
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        results.append(
            {
                "name": name,
                "status": "ok" if result.returncode == 0 else "failed",
                "exit_code": result.returncode,
                "command": shlex.join(command),
            }
        )
    return results


def _run_final_answer_autopilot(args: argparse.Namespace) -> int:
    if args.reply_text is not None and bool(getattr(args, "reply_stdin", False)):
        raise ValueError("--reply-stdin cannot be combined with --reply-text")
    if args.reply_text is not None:
        if args.watch:
            raise ValueError("--reply-text cannot be combined with --watch")
        with tempfile.TemporaryDirectory(prefix="job_apply_final_answers_") as temp_dir:
            reply_path = Path(temp_dir) / "reply.txt"
            reply_path.write_text(str(args.reply_text), encoding="utf-8")
            return _run_final_answer_autopilot_for_reply_path(
                args,
                reply_path,
                reply_source="reply_text",
                reply_file_for_report="<inline reply text redacted>",
            )
    if bool(getattr(args, "reply_stdin", False)):
        if args.watch:
            raise ValueError("--reply-stdin cannot be combined with --watch")
        with tempfile.TemporaryDirectory(prefix="job_apply_final_answers_") as temp_dir:
            reply_path = Path(temp_dir) / "reply.txt"
            reply_path.write_text(sys.stdin.read(), encoding="utf-8")
            return _run_final_answer_autopilot_for_reply_path(
                args,
                reply_path,
                reply_source="reply_stdin",
                reply_file_for_report="<stdin reply text redacted>",
            )
    return _run_final_answer_autopilot_for_reply_path(
        args,
        Path(args.reply_file),
        reply_source="reply_file",
        reply_file_for_report=args.reply_file,
    )


def _final_answer_autopilot_effective_reply_path(
    args: argparse.Namespace,
    reply_path: Path,
    temp_dir: Path,
) -> tuple[Path, str]:
    base_reply_file = str(getattr(args, "base_reply_file", "") or "").strip()
    if not base_reply_file:
        return reply_path, final_answer_reply_text_from_file(reply_path)
    try:
        template_payload = json.loads(Path(args.template).read_text(encoding="utf-8"))
        reply_context = _final_answer_autopilot_reply_context(args, reply_path, template_payload)
        reply_text = str(reply_context.get("reply_text") or "")
    except Exception:
        return reply_path, final_answer_reply_text_from_file(reply_path)
    effective_path = temp_dir / "merged_final_answer_reply.txt"
    effective_path.write_text(reply_text, encoding="utf-8")
    return effective_path, reply_text


def _run_final_answer_autopilot_for_reply_path(
    args: argparse.Namespace,
    reply_path: Path,
    *,
    reply_source: str,
    reply_file_for_report: str | Path,
) -> int:
    start = time.monotonic()
    attempt_count = 0
    interval = max(float(args.interval or 0), 0.25)
    timeout = max(float(args.timeout or 0), 0.0)
    with tempfile.TemporaryDirectory(prefix="job_apply_final_answers_merge_") as merge_temp_dir:
        merge_temp_path = Path(merge_temp_dir)
        while True:
            attempt_count += 1
            validate_command = _final_answer_autopilot_validate_command(args, reply_path)
            pipeline_command = _final_answer_autopilot_pipeline_command(args, reply_path)
            if not reply_path.exists():
                validation_receipt = _final_answer_autopilot_validation_receipt(args, reply_path)
                report = _final_answer_autopilot_base_report(
                    args,
                    status="waiting_for_reply_file",
                    attempt_count=attempt_count,
                    placeholder_line_count=0,
                    validate_command=validate_command,
                    pipeline_command=pipeline_command,
                    reason="reply file does not exist",
                    reply_source=reply_source,
                    reply_file_for_report=reply_file_for_report,
                    validation_receipt=validation_receipt,
                )
                _write_final_answer_autopilot_report(report, args.json_output, args.markdown_output)
                if not args.watch:
                    print(f"Final answer autopilot: {report['status']}")
                    return 2 if args.fail_on_not_ready else 0
            else:
                effective_reply_path, reply_text = _final_answer_autopilot_effective_reply_path(
                    args,
                    reply_path,
                    merge_temp_path,
                )
                validate_command = _final_answer_autopilot_validate_command(args, effective_reply_path)
                pipeline_command = _final_answer_autopilot_pipeline_command(args, effective_reply_path)
                placeholder_count = _final_answer_reply_placeholder_count(reply_text)
                placeholder_aliases = _final_answer_reply_placeholder_aliases(reply_text)
                if placeholder_count:
                    validation_receipt = _final_answer_autopilot_validation_receipt(
                        args,
                        reply_path,
                        reply_text=reply_text,
                    )
                    report = _final_answer_autopilot_base_report(
                        args,
                        status="waiting_for_filled_reply",
                        attempt_count=attempt_count,
                        placeholder_line_count=placeholder_count,
                        placeholder_aliases=placeholder_aliases,
                        validate_command=validate_command,
                        pipeline_command=pipeline_command,
                        reason="reply file still contains <fill> placeholders",
                        reply_source=reply_source,
                        reply_file_for_report=reply_file_for_report,
                        validation_receipt=validation_receipt,
                    )
                    _write_final_answer_autopilot_report(report, args.json_output, args.markdown_output)
                    if not args.watch:
                        print(f"Final answer autopilot: {report['status']}")
                        print(f"Placeholder lines remaining: {placeholder_count}")
                        if placeholder_aliases:
                            print("Placeholder aliases: " + ", ".join(placeholder_aliases))
                        return 2 if args.fail_on_not_ready else 0
                validation_receipt = _final_answer_autopilot_validation_receipt(
                    args,
                    reply_path,
                    reply_text=reply_text,
                )
                validate_result = subprocess.run(
                    validate_command,
                    cwd=Path.cwd(),
                    check=False,
                    text=True,
                    capture_output=True,
                )
                if validate_result.stdout:
                    print(validate_result.stdout, end="")
                if validate_result.stderr:
                    print(validate_result.stderr, end="", file=sys.stderr)
                validation_ready = bool(validation_receipt.get("ready_for_finalize"))
                if validate_result.returncode != 0 or not validation_ready:
                    validate_exit_code = validate_result.returncode or 2
                    report = _final_answer_autopilot_base_report(
                        args,
                        status="validation_failed",
                        attempt_count=attempt_count,
                        placeholder_line_count=0,
                        validate_command=validate_command,
                        pipeline_command=pipeline_command,
                        validate_exit_code=validate_exit_code,
                        reason="filled reply did not pass final-answer validation",
                        reply_source=reply_source,
                        reply_file_for_report=reply_file_for_report,
                        validation_receipt=validation_receipt,
                    )
                    _write_final_answer_autopilot_report(report, args.json_output, args.markdown_output)
                    if _write_final_answer_revision_markdown(
                        report,
                        args.revision_markdown_output,
                    ):
                        print(f"Wrote final answer revision prompt to {args.revision_markdown_output}")
                    print(f"Final answer autopilot: {report['status']}")
                    return validate_exit_code if args.fail_on_not_ready else 0
                if args.dry_run or args.no_run_post_answer_pipeline:
                    report = _final_answer_autopilot_base_report(
                        args,
                        status="validated_ready",
                        attempt_count=attempt_count,
                        placeholder_line_count=0,
                        validate_command=validate_command,
                        pipeline_command=pipeline_command,
                        validate_exit_code=validate_result.returncode,
                        reason="dry run or pipeline disabled",
                        reply_source=reply_source,
                        reply_file_for_report=reply_file_for_report,
                        validation_receipt=validation_receipt,
                    )
                    _write_final_answer_autopilot_report(report, args.json_output, args.markdown_output)
                    print(f"Final answer autopilot: {report['status']}")
                    return 0
                pipeline_result = subprocess.run(
                    pipeline_command,
                    cwd=Path.cwd(),
                    check=False,
                    text=True,
                    capture_output=True,
                )
                if pipeline_result.stdout:
                    print(pipeline_result.stdout, end="")
                if pipeline_result.stderr:
                    print(pipeline_result.stderr, end="", file=sys.stderr)
                final_audits: list[dict[str, object]] = []
                if pipeline_result.returncode == 0 and not args.skip_final_audits:
                    final_audits = _run_final_answer_autopilot_final_audits()
                final_audit_failed = any(row.get("exit_code") for row in final_audits)
                report = _final_answer_autopilot_base_report(
                    args,
                    status=(
                        "pipeline_complete"
                        if pipeline_result.returncode == 0 and not final_audit_failed
                        else "pipeline_complete_audit_failed"
                        if pipeline_result.returncode == 0
                        else "pipeline_failed"
                    ),
                    attempt_count=attempt_count,
                    placeholder_line_count=0,
                    validate_command=validate_command,
                    pipeline_command=pipeline_command,
                    validate_exit_code=validate_result.returncode,
                    pipeline_exit_code=pipeline_result.returncode,
                    final_audits=final_audits,
                    reason="pipeline command finished",
                    reply_source=reply_source,
                    reply_file_for_report=reply_file_for_report,
                    validation_receipt=validation_receipt,
                )
                _write_final_answer_autopilot_report(report, args.json_output, args.markdown_output)
                print(f"Final answer autopilot: {report['status']}")
                if args.fail_on_not_ready and final_audit_failed:
                    return 2
                return pipeline_result.returncode if args.fail_on_not_ready else 0
            if not args.watch:
                return 2 if args.fail_on_not_ready else 0
            if timeout and time.monotonic() - start >= timeout:
                print("Final answer autopilot: timed out waiting for filled reply")
                return 2 if args.fail_on_not_ready else 0
            time.sleep(interval)


def _run_post_answer_pipeline(args: argparse.Namespace) -> int:
    synthetic_final_answers = bool(args.synthetic_final_answers)
    intake_path = Path(args.final_answer_intake_json) if args.final_answer_intake_json else None
    if synthetic_final_answers and (args.apply or args.live_check or args.open_browser):
        raise ValueError("synthetic final answers cannot be combined with --apply, --live-check, or --open-browser")
    if synthetic_final_answers and intake_path:
        raise ValueError("synthetic final answers cannot be combined with --final-answer-intake-json")
    if args.synthetic_rehearse_queue and not synthetic_final_answers:
        raise ValueError("synthetic queue rehearsal requires --synthetic-final-answers")

    required_paths = [
        ("full updates template", args.full_template),
        ("critical input unblockers", args.unblockers),
    ]
    if intake_path:
        required_paths.insert(0, ("final answer intake", intake_path))
    elif not synthetic_final_answers:
        required_paths.insert(0, ("compact updates", args.compact_updates))
    for label, path_value in required_paths:
        if not Path(path_value).exists():
            raise FileNotFoundError(f"{label} not found: {path_value}")

    compact_updates_path = Path(args.compact_updates)
    confirmed_updates_output = Path(args.confirmed_updates_output)
    final_report_json = Path(args.confirmed_report_json_output)
    final_report_markdown = Path(args.confirmed_report_markdown_output)
    synthetic_compact_updates_output = None
    intake_report = None
    if intake_path:
        unblockers_payload = json.loads(Path(args.unblockers).read_text(encoding="utf-8"))
        intake_report = write_final_answer_intake_update(
            unblockers_payload,
            json.loads(intake_path.read_text(encoding="utf-8")),
            compact_updates_path,
            args.final_answer_intake_report_json,
            args.final_answer_intake_report_markdown,
            confirm_high_risk=args.confirm_high_risk,
        )
    if synthetic_final_answers:
        unblockers_payload = json.loads(Path(args.unblockers).read_text(encoding="utf-8"))
        synthetic_compact_updates = build_synthetic_unblocker_compact_updates(unblockers_payload)
        compact_updates_path = DEFAULT_POST_ANSWER_SYNTHETIC_COMPACT_UPDATES_JSON
        compact_updates_path.parent.mkdir(parents=True, exist_ok=True)
        compact_updates_path.write_text(
            json.dumps(synthetic_compact_updates, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        synthetic_compact_updates_output = str(compact_updates_path)
        if _same_path(args.confirmed_updates_output, DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_JSON):
            confirmed_updates_output = DEFAULT_POST_ANSWER_SYNTHETIC_CONFIRMED_UPDATES_JSON
        final_report_json = DEFAULT_POST_ANSWER_SYNTHETIC_CONFIRMED_UPDATES_REPORT_JSON
        final_report_markdown = DEFAULT_POST_ANSWER_SYNTHETIC_CONFIRMED_UPDATES_REPORT_MARKDOWN

    steps: list[dict[str, object]] = []
    if intake_report:
        intake_summary = intake_report.get("summary") or {}
        steps.append(
            {
                "name": "final_answer_intake",
                "status": "ready" if intake_report.get("ready_for_finalize") else "waiting_for_answers",
                "details": {
                    "answers": intake_summary.get("answer_input_count", 0),
                    "compact_updates": intake_summary.get("compact_update_count", 0),
                    "missing_unblockers": intake_summary.get("missing_unblocker_count", 0),
                    "unconfirmed_high_risk": intake_summary.get("unconfirmed_high_risk_count", 0),
                    "unknown_answers": intake_summary.get("unknown_answer_count", 0),
                },
            }
        )
    compact_update_fake_marker_rows: list[dict[str, str]] = []
    if not synthetic_final_answers:
        compact_updates_payload = json.loads(compact_updates_path.read_text(encoding="utf-8"))
        compact_update_fake_marker_rows = final_answer_fake_marker_rows_from_updates(
            compact_updates_payload if isinstance(compact_updates_payload, dict) else {}
        )
    if compact_update_fake_marker_rows:
        final_report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "post_answer_pipeline_fake_marker_guard",
            "ready_for_workflow": False,
            "writes_profile_or_memory": False,
            "submits_real_applications": False,
            "summary": {
                "compact_update_fake_marker_count": len(compact_update_fake_marker_rows),
                "missing_unblocker_count": 0,
                "unconfirmed_high_risk_count": 0,
                "unknown_compact_update_count": 0,
            },
            "fake_marker_rows": compact_update_fake_marker_rows,
            "policy": {
                "blocks_fake_or_synthetic_values_for_real_apply": True,
                "does_not_write_confirmed_updates": True,
            },
        }
        final_report_json.parent.mkdir(parents=True, exist_ok=True)
        final_report_markdown.parent.mkdir(parents=True, exist_ok=True)
        final_report_json.write_text(
            json.dumps(final_report, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        final_report_markdown.write_text(
            "# Critical Input Confirmed Updates\n\n"
            "Ready for workflow: false\n"
            "Blocked: fake/test/synthetic value markers were found in compact updates.\n",
            encoding="utf-8",
        )
    else:
        final_report = write_critical_input_unblocker_final_update(
            compact_updates_path,
            args.full_template,
            args.unblockers,
            confirmed_updates_output,
            final_report_json,
            final_report_markdown,
        )
    final_summary = final_report.get("summary") or {}
    steps.append(
        {
            "name": "finalize_confirmed_updates",
            "status": (
                "blocked_fake_or_test_values"
                if compact_update_fake_marker_rows
                else "ready"
                if final_report.get("ready_for_workflow")
                else "waiting_for_answers"
            ),
            "details": {
                "merged_updates": final_summary.get("merged_update_count", 0),
                "missing_unblockers": final_summary.get("missing_unblocker_count", 0),
                "unconfirmed_high_risk": final_summary.get("unconfirmed_high_risk_count", 0),
                "unknown_compact_updates": final_summary.get("unknown_compact_update_count", 0),
                "fake_marker_count": len(compact_update_fake_marker_rows),
            },
        }
    )

    workflow = None
    refresh = None
    live_check = None
    handoff = None
    packet = None
    submission_safety_audit = None
    submission_safety_blocked = False
    synthetic_queue_rehearsal = None
    opened_count = 0
    status = "waiting_for_confirmed_answers"
    if compact_update_fake_marker_rows:
        status = "blocked_fake_or_test_final_answer_values"
    elif final_report.get("ready_for_workflow"):
        status = "ready_for_apply" if not args.apply else "applying_confirmed_answers"
        if args.apply:
            workflow = write_critical_input_answer_workflow(
                DEFAULT_LEARNING_APPROVAL_PACK_JSON,
                DEFAULT_CRITICAL_INPUT_ANSWERS_JSON,
                json.loads(Path(confirmed_updates_output).read_text(encoding="utf-8")),
                DEFAULT_PERSONAL_PROFILE if DEFAULT_PERSONAL_PROFILE.exists() else DEFAULT_PROFILE,
                DEFAULT_MEMORY,
                DEFAULT_CRITICAL_INPUT_WORKFLOW_JSON,
                DEFAULT_CRITICAL_INPUT_WORKFLOW_MARKDOWN,
                DEFAULT_CRITICAL_INPUT_UPDATE_JSON,
                DEFAULT_CRITICAL_INPUT_UPDATE_MARKDOWN,
                DEFAULT_CRITICAL_INPUT_STATUS_JSON,
                DEFAULT_CRITICAL_INPUT_STATUS_MARKDOWN,
                answers_markdown_output=DEFAULT_CRITICAL_INPUT_ANSWERS_MARKDOWN,
                approve=True,
                approve_high_risk=True,
                apply_confirmed=True,
                allow_partial_apply=False,
                source="post_answer_pipeline",
            )
            workflow_summary = workflow.get("summary") or {}
            steps.append(
                {
                    "name": "apply_confirmed_answers",
                    "status": "applied",
                    "details": {
                        "matched_updates": workflow_summary.get("matched_updates", 0),
                        "applied_profile_updates": workflow_summary.get("applied_profile_updates", 0),
                        "applied_resume_fact_updates": workflow_summary.get("applied_resume_fact_updates", 0),
                        "applied_answer_memory_updates": workflow_summary.get("applied_answer_memory_updates", 0),
                    },
                }
            )
            refresh = _refresh_application_automation_reports()
            steps.append(
                {
                    "name": "refresh_reports",
                    "status": "refreshed",
                    "details": refresh,
                }
            )
            if args.live_check:
                jobs_payload = json.loads(DEFAULT_APPLY_QUEUE_LIVE_CHECK_JOBS.read_text(encoding="utf-8"))
                jobs = jobs_payload.get("jobs") if isinstance(jobs_payload, dict) else jobs_payload
                if not isinstance(jobs, list):
                    jobs = []
                live_check = write_closed_posting_preflight(
                    jobs,
                    DEFAULT_CLOSED_JOBS,
                    DEFAULT_CLOSED_PREFLIGHT_JSON,
                    DEFAULT_CLOSED_PREFLIGHT_MARKDOWN,
                    max_checks=args.live_check_limit,
                    timeout=args.live_check_timeout,
                    source="post_answer_pipeline",
                )
                steps.append(
                    {
                        "name": "live_closed_preflight",
                        "status": "checked",
                        "details": {
                            "live_checked": live_check.get("live_checked_count", 0),
                            "open_eligible": live_check.get("open_eligible_count", 0),
                            "closed": live_check.get("closed_count", 0),
                            "uncertain": live_check.get("uncertain_count", 0),
                        },
                    }
                )
            supplemental_preflights = (
                [DEFAULT_APPLY_QUEUE_MANUAL_LIVE_CHECK_JSON]
                if DEFAULT_APPLY_QUEUE_MANUAL_LIVE_CHECK_JSON.exists()
                else []
            )
            if DEFAULT_CLOSED_PREFLIGHT_JSON.exists():
                handoff = write_apply_queue_handoff(
                    DEFAULT_APPLY_QUEUE_JSON,
                    DEFAULT_CLOSED_PREFLIGHT_JSON,
                    DEFAULT_APPLY_QUEUE_HANDOFF_JSON,
                    DEFAULT_APPLY_QUEUE_HANDOFF_MARKDOWN,
                    DEFAULT_APPLY_QUEUE_HANDOFF_HTML,
                    DEFAULT_APPLY_QUEUE_OPEN_READY_JOBS,
                    supplemental_preflight_paths=supplemental_preflights,
                )
                steps.append(
                    {
                        "name": "apply_queue_handoff",
                        "status": handoff.get("status"),
                        "details": {
                            "open_ready": handoff.get("open_ready_count", 0),
                            "open_after_answers": handoff.get("open_after_answers_count", 0),
                            "manual_live_checks": handoff.get("manual_live_check_count", 0),
                        },
                    }
                )
                packet = write_apply_queue_autofill_packet(
                    DEFAULT_RESEARCH_JSON,
                    DEFAULT_APPLY_QUEUE_HANDOFF_JSON,
                    DEFAULT_PERSONAL_PROFILE if DEFAULT_PERSONAL_PROFILE.exists() else DEFAULT_PROFILE,
                    DEFAULT_MEMORY,
                    DEFAULT_CLOSED_JOBS,
                    DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_JSON,
                    DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_MARKDOWN,
                    DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_HTML,
                    limit=100,
                    target_count=100,
                    include_values=args.include_values,
                )
                packet_summary = packet.get("summary") or {}
                steps.append(
                    {
                        "name": "supervised_autofill_packet",
                        "status": packet.get("status"),
                        "details": {
                            "selected": packet.get("selected_count", 0),
                            "browser_actions": packet_summary.get("browser_action_count", 0),
                            "selector_misses": packet_summary.get("selector_miss_count", 0),
                            "final_submit_stops": packet_summary.get("final_submit_stop_count", 0),
                            "include_values": bool(args.include_values),
                        },
                    }
                )
                submission_safety_audit = _write_post_answer_submission_safety_audit(
                    args,
                    status,
                    steps,
                    packet,
                    synthetic_final_answers=synthetic_final_answers,
                    synthetic_queue_rehearsal=synthetic_queue_rehearsal,
                )
                safety_status = _post_answer_open_browser_safety_status(submission_safety_audit)
                submission_safety_blocked = safety_status == "blocked_by_submission_safety_audit"
                steps.append(
                    {
                        "name": "submission_safety_audit",
                        "status": safety_status,
                        "details": {
                            "audit_status": submission_safety_audit.get("status"),
                            "safe": bool(submission_safety_audit.get("safe")),
                            "issues": submission_safety_audit.get("issue_count", 0),
                            "warnings": submission_safety_audit.get("warning_count", 0),
                            "json": str(DEFAULT_SUBMISSION_SAFETY_AUDIT_JSON),
                            "markdown": str(DEFAULT_SUBMISSION_SAFETY_AUDIT_MARKDOWN),
                        },
                    }
                )
                if args.open_browser:
                    if submission_safety_blocked:
                        steps.append(
                            {
                                "name": "open_browser",
                                "status": "skipped_submission_safety_audit",
                                "details": {
                                    "reason": "submission-safety-audit is unsafe",
                                    "issues": submission_safety_audit.get("issue_count", 0),
                                },
                            }
                        )
                    elif not handoff.get("ready_for_supervised_open_batch"):
                        steps.append(
                            {
                                "name": "open_browser",
                                "status": "skipped_not_open_ready",
                                "details": {"reason": "handoff is not ready for supervised open batch"},
                            }
                        )
                    else:
                        opened_urls = open_apply_urls_in_browser(
                            handoff.get("open_ready_jobs") or [],
                            max_items=args.open_limit,
                            record_path=args.review_log,
                            source="post_answer_pipeline",
                            closed_jobs={"version": 1, "jobs": []},
                        )
                        opened_count = len(opened_urls)
                        steps.append(
                            {
                                "name": "open_browser",
                                "status": "opened",
                                "details": {
                                    "opened_count": opened_count,
                                    "review_log": args.review_log,
                                },
                            }
                        )
            status = "ready_for_supervised_autofill" if (packet or {}).get("ready_for_supervised_browser_autofill") else "applied_refresh_complete"
        elif args.synthetic_rehearse_queue:
            synthetic_queue_rehearsal = _run_synthetic_post_answer_queue_rehearsal(
                confirmed_updates_output,
                steps,
            )
            status = (
                "synthetic_queue_rehearsal_ready"
                if synthetic_queue_rehearsal.get("ready_for_supervised_browser_autofill")
                else "synthetic_queue_rehearsal_not_ready"
            )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "post_answer_pipeline",
        "status": status,
        "ready_for_workflow": bool(final_report.get("ready_for_workflow")),
        "apply_requested": bool(args.apply),
        "live_check_requested": bool(args.live_check),
        "open_browser_requested": bool(args.open_browser),
        "include_values": bool(args.include_values),
        "synthetic_final_answers": synthetic_final_answers,
        "synthetic_queue_rehearsal_requested": bool(args.synthetic_rehearse_queue),
        "final_answer_intake_json": str(intake_path) if intake_path else "",
        "final_answer_intake_report_outputs": {
            "json": str(args.final_answer_intake_report_json) if intake_path else "",
            "markdown": str(args.final_answer_intake_report_markdown) if intake_path else "",
        },
        "final_answer_intake_report": (
            {key: value for key, value in intake_report.items() if key != "compact_updates"}
            if isinstance(intake_report, dict)
            else {}
        ),
        "synthetic_compact_updates_output": synthetic_compact_updates_output,
        "confirmed_updates_output": str(confirmed_updates_output),
        "final_update_report_outputs": {
            "json": str(final_report_json),
            "markdown": str(final_report_markdown),
        },
        "final_update_report": {
            key: value for key, value in final_report.items() if key != "merged_updates"
        },
        "compact_update_fake_marker_count": len(compact_update_fake_marker_rows),
        "compact_update_fake_marker_keys": [row.get("key") for row in compact_update_fake_marker_rows],
        "workflow_summary": (workflow or {}).get("summary") or {},
        "refresh": refresh or {},
        "live_check_summary": {
            "live_checked": (live_check or {}).get("live_checked_count", 0),
            "open_eligible": (live_check or {}).get("open_eligible_count", 0),
            "closed": (live_check or {}).get("closed_count", 0),
            "uncertain": (live_check or {}).get("uncertain_count", 0),
        },
        "submission_safety_audit": {
            "status": (submission_safety_audit or {}).get("status"),
            "safe": bool((submission_safety_audit or {}).get("safe")),
            "issue_count": (submission_safety_audit or {}).get("issue_count", 0),
            "warning_count": (submission_safety_audit or {}).get("warning_count", 0),
            "json": str(DEFAULT_SUBMISSION_SAFETY_AUDIT_JSON) if submission_safety_audit else "",
            "markdown": str(DEFAULT_SUBMISSION_SAFETY_AUDIT_MARKDOWN) if submission_safety_audit else "",
        },
        "handoff_status": (handoff or {}).get("status"),
        "handoff_open_ready": (handoff or {}).get("open_ready_count", 0),
        "autofill_packet_status": (packet or {}).get("status"),
        "autofill_packet_selected": (packet or {}).get("selected_count", 0),
        "synthetic_queue_rehearsal": synthetic_queue_rehearsal or {},
        "opened_count": opened_count,
        "steps": steps,
        "policy": {
            "submits_real_applications": False,
            "writes_profile_or_memory_requires_apply": True,
            "live_page_check_requires_live_check": True,
            "open_browser_requires_open_browser": True,
            "open_browser_requires_submission_safety_audit": True,
            "final_submit_remains_supervised": True,
            "final_answer_intake_writes_profile_or_memory": False,
            "final_answer_intake_submits_real_applications": False,
            "synthetic_answers_never_written_to_real_profile_or_memory": True,
            "synthetic_answers_forbid_apply_live_check_and_open_browser": True,
            "synthetic_queue_rehearsal_uses_fake_local_profile_and_memory": True,
        },
    }
    _write_post_answer_pipeline_report(report, args.json_output, args.markdown_output)
    print(f"Wrote post-answer pipeline JSON to {args.json_output}")
    print(f"Wrote post-answer pipeline Markdown to {args.markdown_output}")
    print(f"Status: {report.get('status')}")
    print(f"Ready for workflow: {str(bool(report.get('ready_for_workflow'))).lower()}")
    print(f"Final answer intake: {str(bool(intake_path)).lower()}")
    print(f"Synthetic final answers: {str(synthetic_final_answers).lower()}")
    print(f"Synthetic queue rehearsal: {(synthetic_queue_rehearsal or {}).get('status') or 'not_built'}")
    if synthetic_queue_rehearsal:
        print(f"Synthetic selected: {synthetic_queue_rehearsal.get('autofill_packet_selected', 0)}")
        print(f"Synthetic selector misses: {synthetic_queue_rehearsal.get('autofill_packet_selector_misses', 0)}")
        print(f"Synthetic final-submit stops: {synthetic_queue_rehearsal.get('autofill_packet_final_submit_stops', 0)}")
    print(f"Apply requested: {str(bool(args.apply)).lower()}")
    print(f"Live check requested: {str(bool(args.live_check)).lower()}")
    print(f"Open browser requested: {str(bool(args.open_browser)).lower()}")
    if submission_safety_audit:
        print(f"Submission safety: {submission_safety_audit.get('status')}")
        print(f"Submission safety issues: {submission_safety_audit.get('issue_count', 0)}")
    autofill_packet_status = report.get("autofill_packet_status") or (
        synthetic_queue_rehearsal or {}
    ).get("autofill_packet_status")
    print(f"Autofill packet: {autofill_packet_status or 'not_built'}")
    if args.fail_on_not_ready and not report.get("ready_for_workflow"):
        return 2
    if args.fail_on_not_ready and compact_update_fake_marker_rows:
        return 2
    if args.fail_on_not_ready and submission_safety_blocked:
        return 2
    return 0


def _write_post_answer_submission_safety_audit(
    args: argparse.Namespace,
    status: str,
    steps: list[dict[str, object]],
    packet: dict[str, object],
    *,
    synthetic_final_answers: bool,
    synthetic_queue_rehearsal: dict[str, object] | None = None,
) -> dict[str, object]:
    post_answer_context = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "post_answer_pipeline_pre_open_safety_context",
        "status": status,
        "ready_for_workflow": True,
        "apply_requested": bool(args.apply),
        "live_check_requested": bool(args.live_check),
        "open_browser_requested": bool(args.open_browser),
        "include_values": bool(args.include_values),
        "synthetic_final_answers": bool(synthetic_final_answers),
        "synthetic_queue_rehearsal": synthetic_queue_rehearsal or {},
        "steps": list(steps),
        "policy": {
            "submits_real_applications": False,
            "writes_profile_or_memory_requires_apply": True,
            "live_page_check_requires_live_check": True,
            "open_browser_requires_open_browser": True,
            "open_browser_requires_submission_safety_audit": True,
            "final_submit_remains_supervised": True,
            "final_answer_intake_writes_profile_or_memory": False,
            "final_answer_intake_submits_real_applications": False,
            "synthetic_answers_never_written_to_real_profile_or_memory": True,
            "synthetic_answers_forbid_apply_live_check_and_open_browser": True,
            "synthetic_queue_rehearsal_uses_fake_local_profile_and_memory": True,
        },
    }
    return write_submission_safety_audit(
        DEFAULT_SUBMISSION_SAFETY_AUDIT_JSON,
        DEFAULT_SUBMISSION_SAFETY_AUDIT_MARKDOWN,
        fake_position_rehearsal=_load_optional_json(str(DEFAULT_FAKE_POSITION_REHEARSAL_JSON)),
        post_answer_pipeline=post_answer_context,
        apply_queue_autofill_packet=packet,
        browser_review_queue_audit=_load_optional_json(str(DEFAULT_REVIEW_QUEUE_AUDIT_JSON)),
        pre_submit_review=_load_optional_json(str(DEFAULT_PRE_SUBMIT_REVIEW_JSON)),
        goal_readiness_audit=_load_optional_json(str(DEFAULT_GOAL_AUDIT_JSON)),
        final_answer_reply_intake=_load_optional_json(str(DEFAULT_FINAL_ANSWER_REPLY_JSON)),
        synthetic_final_answer_reply_intake=_load_optional_json(str(DEFAULT_FINAL_ANSWER_REPLY_SYNTHETIC_JSON)),
    )


def _post_answer_open_browser_safety_status(audit: dict[str, object] | None) -> str:
    if not audit:
        return "missing_submission_safety_audit"
    if bool(audit.get("safe")) and int(audit.get("issue_count") or 0) == 0:
        return "safe"
    return "blocked_by_submission_safety_audit"


def _run_synthetic_post_answer_queue_rehearsal(
    confirmed_updates_output: str | Path,
    steps: list[dict[str, object]],
) -> dict[str, object]:
    learning_tasks = json.loads(DEFAULT_LEARNING_TASKS_JSON.read_text(encoding="utf-8"))
    synthetic_state = build_synthetic_learning_state(learning_tasks)
    profile_payload = synthetic_state.get("profile") or {}
    memory_payload = synthetic_state.get("answer_memory") or {"version": 1, "answers": []}
    DEFAULT_POST_ANSWER_SYNTHETIC_PROFILE_JSON.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_POST_ANSWER_SYNTHETIC_PROFILE_JSON.write_text(
        json.dumps(profile_payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    DEFAULT_POST_ANSWER_SYNTHETIC_MEMORY_JSON.write_text(
        json.dumps(memory_payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    answers_payload = json.loads(DEFAULT_CRITICAL_INPUT_ANSWERS_JSON.read_text(encoding="utf-8"))
    DEFAULT_POST_ANSWER_SYNTHETIC_ANSWERS_JSON.write_text(
        json.dumps(answers_payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    confirmed_updates = json.loads(Path(confirmed_updates_output).read_text(encoding="utf-8"))
    workflow = write_critical_input_answer_workflow(
        DEFAULT_LEARNING_APPROVAL_PACK_JSON,
        DEFAULT_POST_ANSWER_SYNTHETIC_ANSWERS_JSON,
        confirmed_updates,
        DEFAULT_POST_ANSWER_SYNTHETIC_PROFILE_JSON,
        DEFAULT_POST_ANSWER_SYNTHETIC_MEMORY_JSON,
        DEFAULT_POST_ANSWER_SYNTHETIC_WORKFLOW_JSON,
        DEFAULT_POST_ANSWER_SYNTHETIC_WORKFLOW_MARKDOWN,
        DEFAULT_POST_ANSWER_SYNTHETIC_UPDATE_JSON,
        DEFAULT_POST_ANSWER_SYNTHETIC_UPDATE_MARKDOWN,
        DEFAULT_POST_ANSWER_SYNTHETIC_STATUS_JSON,
        DEFAULT_POST_ANSWER_SYNTHETIC_STATUS_MARKDOWN,
        answers_markdown_output=DEFAULT_POST_ANSWER_SYNTHETIC_ANSWERS_MARKDOWN,
        approve=True,
        approve_high_risk=True,
        apply_confirmed=True,
        allow_partial_apply=False,
        source="post_answer_pipeline_synthetic_rehearsal",
    )
    workflow_summary = workflow.get("summary") or {}
    synthetic_state_summary = synthetic_state.get("summary") or {}
    steps.append(
        {
            "name": "synthetic_apply_confirmed_answers",
            "status": "applied_to_fake_local_profile",
            "details": {
                "fake_memory_entries": len((memory_payload or {}).get("answers", [])),
                "fake_profile_updates": synthetic_state_summary.get("profile_update_count", 0),
                "matched_updates": workflow_summary.get("matched_updates", 0),
                "applied_profile_updates": workflow_summary.get("applied_profile_updates", 0),
                "applied_answer_memory_updates": workflow_summary.get("applied_answer_memory_updates", 0),
            },
        }
    )
    readiness = write_critical_input_updates_readiness(
        DEFAULT_LEARNING_APPROVAL_PACK_JSON,
        DEFAULT_POST_ANSWER_SYNTHETIC_ANSWERS_JSON,
        confirmed_updates_output,
        DEFAULT_RESEARCH_JSON,
        DEFAULT_POST_ANSWER_SYNTHETIC_PROFILE_JSON,
        DEFAULT_POST_ANSWER_SYNTHETIC_MEMORY_JSON,
        DEFAULT_POST_ANSWER_SYNTHETIC_UPDATES_READINESS_JSON,
        DEFAULT_POST_ANSWER_SYNTHETIC_UPDATES_READINESS_MARKDOWN,
        closed_jobs=_load_optional_json(str(DEFAULT_CLOSED_JOBS)),
    )
    readiness_summary = readiness.get("summary") or {}
    if not readiness.get("ready_for_apply") and readiness.get("remaining_data_blockers"):
        current_memory = json.loads(DEFAULT_POST_ANSWER_SYNTHETIC_MEMORY_JSON.read_text(encoding="utf-8"))
        blocker_patch = add_synthetic_answers_for_blockers(
            current_memory,
            readiness.get("remaining_data_blockers") or [],
            source="post_answer_pipeline_synthetic_rehearsal",
        )
        DEFAULT_POST_ANSWER_SYNTHETIC_MEMORY_JSON.write_text(
            json.dumps(blocker_patch.get("answer_memory") or {}, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        steps.append(
            {
                "name": "synthetic_fill_remaining_data_blockers",
                "status": "added_fake_memory_answers",
                "details": {
                    "added": blocker_patch.get("added_count", 0),
                    "remaining_before": readiness_summary.get("data_blocking_prompts_after", 0),
                },
            }
        )
        readiness = write_critical_input_updates_readiness(
            DEFAULT_LEARNING_APPROVAL_PACK_JSON,
            DEFAULT_POST_ANSWER_SYNTHETIC_ANSWERS_JSON,
            confirmed_updates_output,
            DEFAULT_RESEARCH_JSON,
            DEFAULT_POST_ANSWER_SYNTHETIC_PROFILE_JSON,
            DEFAULT_POST_ANSWER_SYNTHETIC_MEMORY_JSON,
            DEFAULT_POST_ANSWER_SYNTHETIC_UPDATES_READINESS_JSON,
            DEFAULT_POST_ANSWER_SYNTHETIC_UPDATES_READINESS_MARKDOWN,
            closed_jobs=_load_optional_json(str(DEFAULT_CLOSED_JOBS)),
        )
        readiness_summary = readiness.get("summary") or {}
    steps.append(
        {
            "name": "synthetic_critical_updates_readiness",
            "status": "ready" if readiness.get("ready_for_apply") else "not_ready",
            "details": {
                "waiting_after_update": readiness_summary.get("waiting_after_update_count", 0),
                "data_blockers_after": readiness_summary.get("data_blocking_prompts_after", 0),
                "unknown_updates": readiness_summary.get("unknown_updates", 0),
            },
        }
    )
    apply_queue = write_apply_queue_readiness(
        DEFAULT_AUTOFILL_BATCH_JSON,
        DEFAULT_POST_ANSWER_SYNTHETIC_UPDATES_READINESS_JSON,
        DEFAULT_GOAL_AUDIT_JSON,
        DEFAULT_CLOSED_JOBS,
        DEFAULT_POST_ANSWER_SYNTHETIC_APPLY_QUEUE_JSON,
        DEFAULT_POST_ANSWER_SYNTHETIC_APPLY_QUEUE_MARKDOWN,
        DEFAULT_POST_ANSWER_SYNTHETIC_APPLY_QUEUE_HTML,
        DEFAULT_POST_ANSWER_SYNTHETIC_APPLY_QUEUE_LIVE_CHECK_JOBS,
    )
    steps.append(
        {
            "name": "synthetic_apply_queue",
            "status": apply_queue.get("status"),
            "details": {
                "positions": apply_queue.get("position_count", 0),
                "live_check_jobs": apply_queue.get("live_check_job_count", 0),
                "ready_for_supervised_autofill": bool(apply_queue.get("ready_for_supervised_autofill")),
            },
        }
    )
    handoff = None
    packet = None
    if DEFAULT_CLOSED_PREFLIGHT_JSON.exists():
        supplemental_preflights = (
            [DEFAULT_APPLY_QUEUE_MANUAL_LIVE_CHECK_JSON]
            if DEFAULT_APPLY_QUEUE_MANUAL_LIVE_CHECK_JSON.exists()
            else []
        )
        handoff = write_apply_queue_handoff(
            DEFAULT_POST_ANSWER_SYNTHETIC_APPLY_QUEUE_JSON,
            DEFAULT_CLOSED_PREFLIGHT_JSON,
            DEFAULT_POST_ANSWER_SYNTHETIC_HANDOFF_JSON,
            DEFAULT_POST_ANSWER_SYNTHETIC_HANDOFF_MARKDOWN,
            DEFAULT_POST_ANSWER_SYNTHETIC_HANDOFF_HTML,
            DEFAULT_POST_ANSWER_SYNTHETIC_OPEN_READY_JOBS,
            supplemental_preflight_paths=supplemental_preflights,
        )
        steps.append(
            {
                "name": "synthetic_apply_queue_handoff",
                "status": handoff.get("status"),
                "details": {
                    "open_ready": handoff.get("open_ready_count", 0),
                    "manual_live_checks": handoff.get("manual_live_check_count", 0),
                    "closed_or_skipped": handoff.get("closed_or_skipped_count", 0),
                },
            }
        )
        packet = write_apply_queue_autofill_packet(
            DEFAULT_RESEARCH_JSON,
            DEFAULT_POST_ANSWER_SYNTHETIC_HANDOFF_JSON,
            DEFAULT_POST_ANSWER_SYNTHETIC_PROFILE_JSON,
            DEFAULT_POST_ANSWER_SYNTHETIC_MEMORY_JSON,
            DEFAULT_CLOSED_JOBS,
            DEFAULT_POST_ANSWER_SYNTHETIC_AUTOFILL_PACKET_JSON,
            DEFAULT_POST_ANSWER_SYNTHETIC_AUTOFILL_PACKET_MARKDOWN,
            DEFAULT_POST_ANSWER_SYNTHETIC_AUTOFILL_PACKET_HTML,
            limit=100,
            target_count=100,
            include_values=False,
        )
        packet_summary = packet.get("summary") or {}
        steps.append(
            {
                "name": "synthetic_supervised_autofill_packet",
                "status": packet.get("status"),
                "details": {
                    "selected": packet.get("selected_count", 0),
                    "browser_actions": packet_summary.get("browser_action_count", 0),
                    "selector_misses": packet_summary.get("selector_miss_count", 0),
                    "final_submit_stops": packet_summary.get("final_submit_stop_count", 0),
                },
            }
        )
    packet_summary = (packet or {}).get("summary") or {}
    final_synthetic_memory = json.loads(DEFAULT_POST_ANSWER_SYNTHETIC_MEMORY_JSON.read_text(encoding="utf-8"))
    ready = bool((packet or {}).get("ready_for_supervised_browser_autofill"))
    return {
        "status": "ready_for_supervised_browser_autofill" if ready else "not_ready",
        "ready_for_supervised_browser_autofill": ready,
        "writes_real_profile_or_memory": False,
        "submits_real_applications": False,
        "opens_browser": False,
        "runs_live_check": False,
        "fake_learning_answer_memory_entries": len((final_synthetic_memory or {}).get("answers", [])),
        "critical_updates_ready": bool(readiness.get("ready_for_apply")),
        "apply_queue_status": apply_queue.get("status"),
        "apply_queue_ready_for_supervised_autofill": bool(apply_queue.get("ready_for_supervised_autofill")),
        "handoff_status": (handoff or {}).get("status"),
        "handoff_open_ready": (handoff or {}).get("open_ready_count", 0),
        "autofill_packet_status": (packet or {}).get("status"),
        "autofill_packet_selected": (packet or {}).get("selected_count", 0),
        "autofill_packet_browser_actions": packet_summary.get("browser_action_count", 0),
        "autofill_packet_selector_misses": packet_summary.get("selector_miss_count", 0),
        "autofill_packet_final_submit_stops": packet_summary.get("final_submit_stop_count", 0),
        "outputs": {
            "profile": str(DEFAULT_POST_ANSWER_SYNTHETIC_PROFILE_JSON),
            "memory": str(DEFAULT_POST_ANSWER_SYNTHETIC_MEMORY_JSON),
            "workflow": str(DEFAULT_POST_ANSWER_SYNTHETIC_WORKFLOW_JSON),
            "updates_readiness": str(DEFAULT_POST_ANSWER_SYNTHETIC_UPDATES_READINESS_JSON),
            "apply_queue": str(DEFAULT_POST_ANSWER_SYNTHETIC_APPLY_QUEUE_JSON),
            "handoff": str(DEFAULT_POST_ANSWER_SYNTHETIC_HANDOFF_JSON),
            "autofill_packet": str(DEFAULT_POST_ANSWER_SYNTHETIC_AUTOFILL_PACKET_JSON),
        },
    }


def _write_post_answer_pipeline_report(
    report: dict[str, object],
    json_output: str | Path,
    markdown_output: str | Path,
) -> None:
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_post_answer_pipeline_markdown(report), encoding="utf-8")


def _render_post_answer_pipeline_markdown(report: dict[str, object]) -> str:
    final_report = report.get("final_update_report") if isinstance(report.get("final_update_report"), dict) else {}
    final_summary = final_report.get("summary") if isinstance(final_report, dict) else {}
    final_summary = final_summary if isinstance(final_summary, dict) else {}
    intake_report = (
        report.get("final_answer_intake_report")
        if isinstance(report.get("final_answer_intake_report"), dict)
        else {}
    )
    intake_summary = intake_report.get("summary") if isinstance(intake_report, dict) else {}
    intake_summary = intake_summary if isinstance(intake_summary, dict) else {}
    lines = [
        "# Post-Answer Pipeline",
        "",
        f"Generated: {report.get('generated_at')}",
        f"Status: {report.get('status')}",
        f"Ready for workflow: {str(bool(report.get('ready_for_workflow'))).lower()}",
        f"Synthetic final answers: {str(bool(report.get('synthetic_final_answers'))).lower()}",
        f"Synthetic queue rehearsal: {str(bool(report.get('synthetic_queue_rehearsal_requested'))).lower()}",
        f"Apply requested: {str(bool(report.get('apply_requested'))).lower()}",
        f"Live check requested: {str(bool(report.get('live_check_requested'))).lower()}",
        f"Open browser requested: {str(bool(report.get('open_browser_requested'))).lower()}",
        f"Final answer intake JSON: {report.get('final_answer_intake_json') or ''}",
        f"Confirmed updates output: {report.get('confirmed_updates_output')}",
        "",
        "## Final Answer Intake",
        "",
        f"- ready for finalize: {str(bool(intake_report.get('ready_for_finalize'))).lower()}",
        f"- answer inputs: {intake_summary.get('answer_input_count', 0)}",
        f"- compact updates: {intake_summary.get('compact_update_count', 0)}",
        f"- missing unblockers: {intake_summary.get('missing_unblocker_count', 0)}",
        f"- unconfirmed high-risk answers: {intake_summary.get('unconfirmed_high_risk_count', 0)}",
        f"- unknown answers: {intake_summary.get('unknown_answer_count', 0)}",
        "",
        "## Final Answer Gate",
        "",
        f"- merged updates: {final_summary.get('merged_update_count', 0)}",
        f"- missing unblockers: {final_summary.get('missing_unblocker_count', 0)}",
        f"- unconfirmed high-risk answers: {final_summary.get('unconfirmed_high_risk_count', 0)}",
        f"- unknown compact updates: {final_summary.get('unknown_compact_update_count', 0)}",
        f"- fake/test markers in compact updates: {report.get('compact_update_fake_marker_count', 0)}",
        "",
        "## Submission Safety Audit",
        "",
    ]
    safety = (
        report.get("submission_safety_audit")
        if isinstance(report.get("submission_safety_audit"), dict)
        else {}
    )
    if safety:
        lines.extend(
            [
                f"- status: {safety.get('status') or 'missing'}",
                f"- safe: {str(bool(safety.get('safe'))).lower()}",
                f"- issues: {safety.get('issue_count', 0)}",
                f"- warnings: {safety.get('warning_count', 0)}",
                f"- json: {safety.get('json') or ''}",
                f"- markdown: {safety.get('markdown') or ''}",
            ]
        )
    else:
        lines.append("- not built")
    lines.extend(
        [
            "",
            "## Synthetic Queue Rehearsal",
            "",
        ]
    )
    synthetic_rehearsal = (
        report.get("synthetic_queue_rehearsal")
        if isinstance(report.get("synthetic_queue_rehearsal"), dict)
        else {}
    )
    if synthetic_rehearsal:
        lines.extend(
            [
                f"- status: {synthetic_rehearsal.get('status')}",
                f"- ready for supervised browser autofill: {str(bool(synthetic_rehearsal.get('ready_for_supervised_browser_autofill'))).lower()}",
                f"- apply queue status: {synthetic_rehearsal.get('apply_queue_status')}",
                f"- handoff open ready: {synthetic_rehearsal.get('handoff_open_ready', 0)}",
                f"- autofill packet: {synthetic_rehearsal.get('autofill_packet_status')}",
                f"- selected: {synthetic_rehearsal.get('autofill_packet_selected', 0)}",
                f"- selector misses: {synthetic_rehearsal.get('autofill_packet_selector_misses', 0)}",
                f"- final-submit stops: {synthetic_rehearsal.get('autofill_packet_final_submit_stops', 0)}",
            ]
        )
    else:
        lines.append("- not built")
    lines.extend(
        [
            "",
            "## Steps",
            "",
            "| Step | Status | Details |",
            "| --- | --- | --- |",
        ]
    )
    for step in report.get("steps") or []:
        if not isinstance(step, dict):
            continue
        details = step.get("details") if isinstance(step.get("details"), dict) else {}
        detail_text = "; ".join(f"{key}={value}" for key, value in details.items())
        lines.append(f"| {step.get('name')} | {step.get('status')} | {detail_text} |")
    lines.extend(
        [
            "",
            "## Policy",
            "",
            "- This pipeline never submits real employer applications.",
            "- Profile and answer-memory writes require `--apply`.",
            "- Live page checks require `--live-check`.",
            "- Browser opening requires `--open-browser` and still stops before final submit.",
            "- Synthetic final answers cannot be applied, live-checked, or opened in browser.",
            "- Synthetic queue rehearsal uses fake local profile and memory artifacts.",
        ]
    )
    return "\n".join(lines) + "\n"


def _load_optional_json(path_value: str | None) -> dict | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _print_final_answer_intake_problem_aliases(report: dict) -> None:
    status_labels = [
        ("Missing answer aliases", "missing"),
        ("High-risk confirmation aliases", "high_risk_unconfirmed"),
        ("Needs specificity aliases", "needs_more_specific_answer"),
    ]
    fields = [row for row in report.get("fields") or [] if isinstance(row, dict)]
    for label, status in status_labels:
        aliases = [
            str(row.get("alias") or row.get("input_id") or "").strip()
            for row in fields
            if row.get("status") == status and str(row.get("alias") or row.get("input_id") or "").strip()
        ]
        if aliases:
            print(f"{label}: {', '.join(aliases[:12])}")
    unknown_ids = [
        str(item).strip()
        for item in report.get("unknown_answer_ids") or []
        if str(item).strip()
    ]
    if unknown_ids:
        print(f"Unknown answer keys: {', '.join(unknown_ids[:12])}")


def _print_final_answer_reply_problem_aliases(report: dict) -> None:
    fake_aliases = [
        str(alias).strip()
        for alias in report.get("fake_marker_aliases") or []
        if str(alias).strip()
    ]
    if fake_aliases:
        print(f"Fake/test marker aliases: {', '.join(fake_aliases[:12])}")


def _load_jobs_payload(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    jobs = payload.get("jobs") if isinstance(payload, dict) else payload
    if not isinstance(jobs, list):
        return []
    return [job for job in jobs if isinstance(job, dict)]


def _run_apply_queue_refresh(args: argparse.Namespace) -> dict:
    profile_path = DEFAULT_PERSONAL_PROFILE if DEFAULT_PERSONAL_PROFILE.exists() else DEFAULT_PROFILE
    max_rounds = max(1, int(args.max_rounds or 1))
    rounds: list[dict] = []
    needs_rebuild = bool(args.force_rebuild or not DEFAULT_AUTOFILL_BATCH_JSON.exists())
    final_handoff: dict = {}
    final_packet: dict = {}
    final_goal: dict | None = None
    if not DEFAULT_RESEARCH_JSON.exists() or not DEFAULT_READINESS_JSON.exists():
        _refresh_application_automation_reports()

    for round_index in range(1, max_rounds + 1):
        rebuilt_autofill = False
        if needs_rebuild:
            research = json.loads(DEFAULT_RESEARCH_JSON.read_text(encoding="utf-8"))
            readiness = json.loads(DEFAULT_READINESS_JSON.read_text(encoding="utf-8"))
            profile = load_profile(profile_path) if profile_path.exists() else None
            answer_memory = load_answer_memory(DEFAULT_MEMORY)
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
                include_values=bool(args.include_values),
            )
            rebuilt_autofill = True

        if not DEFAULT_CRITICAL_INPUT_UPDATES_READINESS_JSON.exists() or not DEFAULT_GOAL_AUDIT_JSON.exists():
            _refresh_application_automation_reports()
        apply_queue = write_apply_queue_readiness(
            DEFAULT_AUTOFILL_BATCH_JSON,
            DEFAULT_CRITICAL_INPUT_UPDATES_READINESS_JSON,
            DEFAULT_GOAL_AUDIT_JSON,
            DEFAULT_CLOSED_JOBS,
            DEFAULT_APPLY_QUEUE_JSON,
            DEFAULT_APPLY_QUEUE_MARKDOWN,
            DEFAULT_APPLY_QUEUE_HTML,
            DEFAULT_APPLY_QUEUE_LIVE_CHECK_JOBS,
        )
        jobs = _load_jobs_payload(DEFAULT_APPLY_QUEUE_LIVE_CHECK_JOBS)
        if args.skip_live_check:
            if DEFAULT_CLOSED_PREFLIGHT_JSON.exists():
                live_check = _load_optional_json(str(DEFAULT_CLOSED_PREFLIGHT_JSON)) or {}
                live_check_status = "reused"
            else:
                live_check = write_closed_posting_preflight(
                    jobs,
                    DEFAULT_CLOSED_JOBS,
                    DEFAULT_CLOSED_PREFLIGHT_JSON,
                    DEFAULT_CLOSED_PREFLIGHT_MARKDOWN,
                    max_checks=0,
                    timeout=args.live_check_timeout,
                    source="apply_queue_refresh_skipped",
                )
                live_check_status = "skipped_generated_unchecked_preflight"
        else:
            live_check = write_closed_posting_preflight(
                jobs,
                DEFAULT_CLOSED_JOBS,
                DEFAULT_CLOSED_PREFLIGHT_JSON,
                DEFAULT_CLOSED_PREFLIGHT_MARKDOWN,
                max_checks=args.live_check_limit,
                timeout=args.live_check_timeout,
                source="apply_queue_refresh",
            )
            live_check_status = "checked"

        supplemental_preflights = (
            [DEFAULT_APPLY_QUEUE_MANUAL_LIVE_CHECK_JSON]
            if DEFAULT_APPLY_QUEUE_MANUAL_LIVE_CHECK_JSON.exists()
            else []
        )
        final_handoff = write_apply_queue_handoff(
            DEFAULT_APPLY_QUEUE_JSON,
            DEFAULT_CLOSED_PREFLIGHT_JSON,
            DEFAULT_APPLY_QUEUE_HANDOFF_JSON,
            DEFAULT_APPLY_QUEUE_HANDOFF_MARKDOWN,
            DEFAULT_APPLY_QUEUE_HANDOFF_HTML,
            DEFAULT_APPLY_QUEUE_OPEN_READY_JOBS,
            supplemental_preflight_paths=supplemental_preflights,
        )
        final_packet = write_apply_queue_autofill_packet(
            DEFAULT_RESEARCH_JSON,
            DEFAULT_APPLY_QUEUE_HANDOFF_JSON,
            profile_path,
            DEFAULT_MEMORY,
            DEFAULT_CLOSED_JOBS,
            DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_JSON,
            DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_MARKDOWN,
            DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_HTML,
            limit=100,
            target_count=100,
            include_values=bool(args.include_values),
        )
        top_up_required = int(final_handoff.get("top_up_required_count") or 0)
        rounds.append(
            {
                "round": round_index,
                "rebuilt_autofill_batch": rebuilt_autofill,
                "apply_queue_status": apply_queue.get("status"),
                "apply_queue_positions": apply_queue.get("position_count", 0),
                "live_check_status": live_check_status,
                "live_checked": live_check.get("live_checked_count", 0),
                "live_open_eligible": live_check.get("open_eligible_count", 0),
                "live_closed": live_check.get("closed_count", 0),
                "live_uncertain": live_check.get("uncertain_count", 0),
                "handoff_status": final_handoff.get("status"),
                "live_open_after_answers": final_handoff.get("live_open_after_answers_count", 0),
                "manual_live_checks": final_handoff.get("manual_live_check_count", 0),
                "top_up_required": top_up_required,
                "packet_status": final_packet.get("status"),
                "packet_selected": final_packet.get("selected_count", 0),
            }
        )
        needs_rebuild = top_up_required > 0
        if not needs_rebuild:
            break

    platform_playbook = None
    position_execution = None
    selected_answer_dependencies = None
    if DEFAULT_RESEARCH_JSON.exists():
        platform_playbook = write_platform_question_playbook(
            json.loads(DEFAULT_RESEARCH_JSON.read_text(encoding="utf-8")),
            DEFAULT_PLATFORM_QUESTION_PLAYBOOK_JSON,
            DEFAULT_PLATFORM_QUESTION_PLAYBOOK_MARKDOWN,
            DEFAULT_PLATFORM_QUESTION_PLAYBOOK_HTML,
            autofill_batch=_load_optional_json(str(DEFAULT_AUTOFILL_BATCH_JSON)),
            fake_position_rehearsal=_load_optional_json(str(DEFAULT_FAKE_POSITION_REHEARSAL_JSON)),
            automation_handoff=_load_optional_json(str(DEFAULT_AUTOMATION_HANDOFF_JSON)),
            closed_jobs=_load_optional_json(str(DEFAULT_CLOSED_JOBS)),
        )
    if (
        DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_JSON.exists()
        and DEFAULT_POST_ANSWER_SYNTHETIC_AUTOFILL_PACKET_JSON.exists()
        and DEFAULT_PLATFORM_QUESTION_PLAYBOOK_JSON.exists()
        and DEFAULT_GOAL_AUDIT_JSON.exists()
    ):
        position_execution = write_position_execution_audit(
            DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_JSON,
            DEFAULT_POST_ANSWER_SYNTHETIC_AUTOFILL_PACKET_JSON,
            DEFAULT_PLATFORM_QUESTION_PLAYBOOK_JSON,
            DEFAULT_GOAL_AUDIT_JSON,
            DEFAULT_POSITION_EXECUTION_AUDIT_JSON,
            DEFAULT_POSITION_EXECUTION_AUDIT_MARKDOWN,
            DEFAULT_POSITION_EXECUTION_AUDIT_HTML,
            target_count=100,
        )
        if DEFAULT_RESEARCH_JSON.exists() and DEFAULT_FINAL_ANSWER_BLOCKERS_JSON.exists():
            selected_answer_dependencies = write_selected_final_answer_dependency_report(
                DEFAULT_RESEARCH_JSON,
                DEFAULT_POSITION_EXECUTION_AUDIT_JSON,
                DEFAULT_FINAL_ANSWER_BLOCKERS_JSON,
                DEFAULT_SELECTED_ANSWER_DEPENDENCIES_JSON,
                DEFAULT_SELECTED_ANSWER_DEPENDENCIES_MARKDOWN,
                DEFAULT_SELECTED_ANSWER_DEPENDENCIES_HTML,
                target_count=100,
            )
    coverage = _load_optional_json(str(DEFAULT_COVERAGE_GATE_JSON))
    gaps = _load_optional_json(str(DEFAULT_GAPS_JSON))
    readiness = _load_optional_json(str(DEFAULT_READINESS_JSON))
    if coverage and gaps and readiness:
        final_goal = write_goal_readiness_audit(
            coverage,
            gaps,
            readiness,
            DEFAULT_GOAL_AUDIT_JSON,
            DEFAULT_GOAL_AUDIT_MARKDOWN,
            critical_input_status=_load_optional_json(str(DEFAULT_CRITICAL_INPUT_STATUS_JSON)),
            critical_input_updates_readiness=_load_optional_json(str(DEFAULT_CRITICAL_INPUT_UPDATES_READINESS_JSON)),
            fake_learning_probe=_load_optional_json(str(DEFAULT_FAKE_LEARNING_PROBE_JSON)),
            fake_critical_input_probe=_load_optional_json(str(DEFAULT_FAKE_CRITICAL_INPUT_PROBE_JSON)),
            fake_position_rehearsal=_load_optional_json(str(DEFAULT_FAKE_POSITION_REHEARSAL_JSON)),
            autofill_batch_plan=_load_optional_json(str(DEFAULT_AUTOFILL_BATCH_JSON)),
            synthetic_unblocker_proof=_load_optional_json(str(DEFAULT_SYNTHETIC_UNBLOCKER_PROOF_JSON)),
            post_answer_pipeline=_load_optional_json(str(DEFAULT_POST_ANSWER_PIPELINE_JSON)),
            closed_preflight=_load_optional_json(str(DEFAULT_CLOSED_PREFLIGHT_JSON)),
            closed_jobs=_load_optional_json(str(DEFAULT_CLOSED_JOBS)),
            platform_question_playbook=platform_playbook or _load_optional_json(str(DEFAULT_PLATFORM_QUESTION_PLAYBOOK_JSON)),
            position_execution_audit=position_execution or _load_optional_json(str(DEFAULT_POSITION_EXECUTION_AUDIT_JSON)),
            selected_answer_dependencies=(
                selected_answer_dependencies
                or _load_optional_json(str(DEFAULT_SELECTED_ANSWER_DEPENDENCIES_JSON))
            ),
            submission_safety_audit=_load_optional_json(str(DEFAULT_SUBMISSION_SAFETY_AUDIT_JSON)),
        )

    final_summary = {
        "handoff_status": final_handoff.get("status"),
        "target_count": final_handoff.get("target_count", 100),
        "live_open_after_answers_count": final_handoff.get("live_open_after_answers_count", 0),
        "top_up_required_count": final_handoff.get("top_up_required_count", 0),
        "manual_live_check_count": final_handoff.get("manual_live_check_count", 0),
        "closed_or_skipped_count": final_handoff.get("closed_or_skipped_count", 0),
        "packet_status": final_packet.get("status"),
        "packet_selected_count": final_packet.get("selected_count", 0),
        "goal_status": (final_goal or {}).get("status"),
        "goal_complete": bool((final_goal or {}).get("goal_complete")),
    }
    status = "needs_top_up"
    if int(final_summary["top_up_required_count"] or 0) <= 0:
        status = "needs_manual_live_check" if int(final_summary["manual_live_check_count"] or 0) else "queue_refreshed"
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "apply_queue_refresh",
        "status": status,
        "skip_live_check": bool(args.skip_live_check),
        "include_values": bool(args.include_values),
        "max_rounds": max_rounds,
        "rounds": rounds,
        "final": final_summary,
        "outputs": {
            "json": str(args.json_output),
            "markdown": str(args.markdown_output),
            "apply_queue": str(DEFAULT_APPLY_QUEUE_JSON),
            "closed_preflight": str(DEFAULT_CLOSED_PREFLIGHT_JSON),
            "handoff": str(DEFAULT_APPLY_QUEUE_HANDOFF_JSON),
            "autofill_packet": str(DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_JSON),
            "position_execution_audit": str(DEFAULT_POSITION_EXECUTION_AUDIT_JSON),
            "selected_answer_dependencies": str(DEFAULT_SELECTED_ANSWER_DEPENDENCIES_JSON),
            "goal_audit": str(DEFAULT_GOAL_AUDIT_JSON),
        },
        "policy": {
            "live_check_before_open": not bool(args.skip_live_check),
            "stop_on_no_longer_accepting": True,
            "persist_closed_postings": True,
            "real_platform_submission": False,
            "final_submit_remains_supervised": True,
        },
    }
    _write_apply_queue_refresh_report(report, Path(args.json_output), Path(args.markdown_output))
    return report


def _write_apply_queue_refresh_report(report: dict, json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_apply_queue_refresh_markdown(report), encoding="utf-8")


def _render_apply_queue_refresh_markdown(report: dict) -> str:
    final = report.get("final") or {}
    lines = [
        "# Apply Queue Refresh",
        "",
        f"Generated: {report.get('generated_at')}",
        f"Status: {report.get('status')}",
        f"Skip live check: {str(bool(report.get('skip_live_check'))).lower()}",
        f"Include values: {str(bool(report.get('include_values'))).lower()}",
        "",
        "## Final",
        "",
        f"- handoff status: {final.get('handoff_status')}",
        f"- target count: {final.get('target_count', 100)}",
        f"- live open after answers: {final.get('live_open_after_answers_count', 0)}",
        f"- top-up required: {final.get('top_up_required_count', 0)}",
        f"- manual live checks: {final.get('manual_live_check_count', 0)}",
        f"- closed or skipped: {final.get('closed_or_skipped_count', 0)}",
        f"- packet status: {final.get('packet_status')}",
        f"- packet selected: {final.get('packet_selected_count', 0)}",
        f"- goal status: {final.get('goal_status')}",
        f"- goal complete: {str(bool(final.get('goal_complete'))).lower()}",
        "",
        "## Rounds",
        "",
    ]
    for row in report.get("rounds") or []:
        lines.append(
            "- round {round}: rebuild={rebuilt}; live={live}; checked={checked}; open={open}; closed={closed}; "
            "uncertain={uncertain}; after_answers={after}; top_up={topup}; packet={packet}".format(
                round=row.get("round"),
                rebuilt=str(bool(row.get("rebuilt_autofill_batch"))).lower(),
                live=row.get("live_check_status"),
                checked=row.get("live_checked", 0),
                open=row.get("live_open_eligible", 0),
                closed=row.get("live_closed", 0),
                uncertain=row.get("live_uncertain", 0),
                after=row.get("live_open_after_answers", 0),
                topup=row.get("top_up_required", 0),
                packet=row.get("packet_status"),
            )
        )
    lines.extend(["", "## Policy", ""])
    for key, value in sorted((report.get("policy") or {}).items()):
        lines.append(f"- {key}: {str(value).lower() if isinstance(value, bool) else value}")
    return "\n".join(lines) + "\n"


def _validate_final_answer_intake_server_post_answer_args(args: argparse.Namespace) -> None:
    if getattr(args, "synthetic_rehearse_queue", False) and getattr(args, "run_post_answer_pipeline", False):
        raise ValueError("--synthetic-rehearse-queue cannot be combined with --run-post-answer-pipeline")
    if not args.run_post_answer_pipeline:
        for flag_name in [
            "post_answer_apply",
            "post_answer_live_check",
            "post_answer_include_values",
            "post_answer_open_browser",
        ]:
            if getattr(args, flag_name):
                raise ValueError(f"--{flag_name.replace('_', '-')} requires --run-post-answer-pipeline")
        return
    if (args.post_answer_live_check or args.post_answer_include_values) and not args.post_answer_apply:
        raise ValueError("--post-answer-live-check and --post-answer-include-values require --post-answer-apply")
    if args.post_answer_open_browser and not args.post_answer_live_check:
        raise ValueError("--post-answer-open-browser requires --post-answer-live-check")


def _synthetic_default_path(
    path_value: str | Path,
    default_path: str | Path,
    synthetic_path: str | Path,
    use_synthetic: bool,
) -> str:
    if use_synthetic and _same_path(path_value, default_path):
        return str(synthetic_path)
    return str(path_value)


def _post_answer_pipeline_summary(report: dict | None) -> dict[str, object]:
    if not isinstance(report, dict):
        return {}
    return {
        "status": report.get("status"),
        "ready_for_workflow": bool(report.get("ready_for_workflow")),
        "apply_requested": bool(report.get("apply_requested")),
        "live_check_requested": bool(report.get("live_check_requested")),
        "open_browser_requested": bool(report.get("open_browser_requested")),
        "handoff_status": report.get("handoff_status"),
        "handoff_open_ready": report.get("handoff_open_ready", 0),
        "autofill_packet_status": report.get("autofill_packet_status"),
        "autofill_packet_selected": report.get("autofill_packet_selected", 0),
        "opened_count": report.get("opened_count", 0),
        "policy": report.get("policy") or {},
    }


def _run_post_answer_pipeline_from_intake_server(args: argparse.Namespace) -> dict[str, object]:
    pipeline_args = argparse.Namespace(
        compact_updates=args.compact_updates_output,
        full_template=args.full_template,
        unblockers=args.unblockers,
        confirmed_updates_output=args.confirmed_updates_output,
        confirmed_report_json_output=args.confirmed_report_json_output,
        confirmed_report_markdown_output=args.confirmed_report_markdown_output,
        final_answer_intake_json=args.template_output,
        final_answer_intake_report_json=args.json_output,
        final_answer_intake_report_markdown=args.markdown_output,
        confirm_high_risk=args.confirm_high_risk,
        synthetic_final_answers=False,
        synthetic_rehearse_queue=False,
        apply=args.post_answer_apply,
        live_check=args.post_answer_live_check,
        live_check_limit=args.post_answer_live_check_limit,
        live_check_timeout=args.post_answer_live_check_timeout,
        include_values=args.post_answer_include_values,
        open_browser=args.post_answer_open_browser,
        open_limit=args.post_answer_open_limit,
        review_log=args.review_log,
        json_output=args.post_answer_json_output,
        markdown_output=args.post_answer_markdown_output,
        fail_on_not_ready=True,
    )
    exit_code = _run_post_answer_pipeline(pipeline_args)
    report = _load_optional_json(args.post_answer_json_output) or {}
    return {
        "ran": True,
        "exit_code": exit_code,
        "json_output": str(args.post_answer_json_output),
        "markdown_output": str(args.post_answer_markdown_output),
        "summary": _post_answer_pipeline_summary(report),
    }


def _run_final_answer_intake_server(args: argparse.Namespace) -> int:
    _validate_final_answer_intake_server_post_answer_args(args)
    unblockers_path = Path(args.unblockers)
    if not unblockers_path.exists():
        raise FileNotFoundError(f"critical input unblockers not found: {args.unblockers}")
    unblockers = json.loads(unblockers_path.read_text(encoding="utf-8"))
    if not isinstance(unblockers, dict):
        raise ValueError(f"critical input unblockers must be a JSON object: {args.unblockers}")

    def current_template() -> dict:
        return build_final_answer_intake_template(
            unblockers,
            existing_intake_payload=_load_optional_json(args.template_output),
        )

    def write_server_html(template: dict) -> str:
        html = render_final_answer_intake_template_html(template, save_endpoint="/save")
        html_path = Path(args.template_html_output)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, encoding="utf-8")
        return html

    def write_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=True, indent=2).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    server_ref: dict[str, ThreadingHTTPServer] = {}

    class IntakeHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *values: object) -> None:  # noqa: A002
            return

        def do_GET(self) -> None:
            request_path = self.path.split("?", 1)[0]
            if request_path not in {"/", "/index.html"}:
                write_response(self, 404, {"error": "not_found"})
                return
            template = current_template()
            html = write_server_html(template)
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            request_path = self.path.split("?", 1)[0]
            if request_path != "/save":
                write_response(self, 404, {"error": "not_found"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size <= 0 or size > 1_000_000:
                    raise ValueError("request body must be between 1 byte and 1 MB")
                payload = json.loads(self.rfile.read(size).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("request body must be a JSON object")
                result = save_final_answer_intake_payload(
                    unblockers,
                    payload,
                    args.template_output,
                    args.template_markdown_output,
                    args.template_html_output,
                    args.compact_updates_output,
                    args.json_output,
                    args.markdown_output,
                    unblockers_path=args.unblockers,
                    confirm_high_risk=args.confirm_high_risk,
                    finalize=args.finalize,
                    full_template=args.full_template,
                    confirmed_updates_output=args.confirmed_updates_output,
                    confirmed_report_json_output=args.confirmed_report_json_output,
                    confirmed_report_markdown_output=args.confirmed_report_markdown_output,
                )
                write_server_html(current_template())
                if args.run_post_answer_pipeline:
                    if result.get("ready_for_finalize"):
                        result["post_answer_pipeline"] = _run_post_answer_pipeline_from_intake_server(args)
                    else:
                        result["post_answer_pipeline"] = {
                            "ran": False,
                            "reason": "intake_not_ready",
                        }
                write_response(self, 200, result)
                if args.once and result.get("ready_for_finalize"):
                    threading.Thread(target=server_ref["server"].shutdown, daemon=True).start()
            except Exception as exc:  # pragma: no cover - exercised through manual local server use
                write_response(self, 400, {"error": str(exc)})

    write_final_answer_intake_template(
        unblockers,
        args.template_output,
        args.template_markdown_output,
        args.template_html_output,
        existing_intake_payload=_load_optional_json(args.template_output),
    )
    write_server_html(current_template())
    server = ThreadingHTTPServer((args.host, args.port), IntakeHandler)
    server_ref["server"] = server
    host, port = server.server_address
    url = f"http://{host}:{port}/"
    print(f"Serving final answer intake form at {url}")
    print("Writes profile or memory: false")
    print("Submits real applications: false")
    if args.open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _same_path(path_value: str | Path, other_path: str | Path) -> bool:
    return Path(path_value).expanduser().resolve() == Path(other_path).expanduser().resolve()


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
    learning_tasks = write_learning_task_template(
        readiness,
        DEFAULT_LEARNING_TASKS_JSON,
        DEFAULT_LEARNING_TASKS_MARKDOWN,
        profile=profile,
        answer_memory=answer_memory,
    )
    approval_pack = write_learning_approval_pack(
        learning_tasks,
        readiness,
        DEFAULT_LEARNING_APPROVAL_PACK_JSON,
        DEFAULT_LEARNING_APPROVAL_PACK_MARKDOWN,
    )
    existing_answers_payload = _load_optional_json(str(DEFAULT_CRITICAL_INPUT_ANSWERS_JSON))
    answers_payload = write_critical_input_answer_template(
        approval_pack,
        DEFAULT_CRITICAL_INPUT_ANSWERS_JSON,
        DEFAULT_CRITICAL_INPUT_ANSWERS_MARKDOWN,
        existing_answers_payload=existing_answers_payload,
    )
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
        unblockers = write_critical_input_unblocker_packet(
            _load_optional_json(str(DEFAULT_CRITICAL_INPUT_SUGGESTIONS_JSON)) or {},
            DEFAULT_CRITICAL_INPUT_UNBLOCKERS_JSON,
            DEFAULT_CRITICAL_INPUT_UNBLOCKERS_MARKDOWN,
            DEFAULT_CRITICAL_INPUT_UNBLOCKERS_HTML,
            impact_payload=critical_input_impact,
        )
        DEFAULT_CRITICAL_INPUT_UNBLOCKERS_UPDATES_JSON.write_text(
            json.dumps(unblockers.get("compact_updates_template", {}), ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        DEFAULT_CRITICAL_INPUT_FULL_UPDATES_JSON.write_text(
            json.dumps(unblockers.get("full_updates_template", {}), ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        write_critical_input_unblocker_final_update(
            DEFAULT_CRITICAL_INPUT_UNBLOCKERS_UPDATES_JSON,
            DEFAULT_CRITICAL_INPUT_FULL_UPDATES_JSON,
            DEFAULT_CRITICAL_INPUT_UNBLOCKERS_JSON,
            DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_JSON,
            DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_REPORT_JSON,
            DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_REPORT_MARKDOWN,
        )
        write_critical_input_updates_readiness(
            DEFAULT_LEARNING_APPROVAL_PACK_JSON,
            DEFAULT_CRITICAL_INPUT_ANSWERS_JSON,
            DEFAULT_CRITICAL_INPUT_FULL_UPDATES_JSON,
            DEFAULT_RESEARCH_JSON,
            profile_path,
            DEFAULT_MEMORY,
            DEFAULT_CRITICAL_INPUT_UPDATES_READINESS_JSON,
            DEFAULT_CRITICAL_INPUT_UPDATES_READINESS_MARKDOWN,
            closed_jobs=load_closed_jobs(DEFAULT_CLOSED_JOBS),
        )
    if DEFAULT_CRITICAL_INPUT_UNBLOCKERS_JSON.exists():
        write_final_answer_intake_template(
            _load_optional_json(str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_JSON)) or {},
            DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_JSON,
            DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_MARKDOWN,
            DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_HTML,
            existing_intake_payload=_load_optional_json(str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_JSON)),
        )
    write_browser_review_queue_audit(
        DEFAULT_REVIEW_LOG,
        DEFAULT_REVIEW_QUEUE_AUDIT_JSON,
        DEFAULT_REVIEW_QUEUE_AUDIT_MARKDOWN,
    )
    autofill_batch = write_autofill_batch_plan(
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
    if answers_payload and DEFAULT_CRITICAL_INPUT_UNBLOCKERS_JSON.exists():
        write_synthetic_unblocker_proof(
            DEFAULT_LEARNING_APPROVAL_PACK_JSON,
            DEFAULT_CRITICAL_INPUT_ANSWERS_JSON,
            DEFAULT_CRITICAL_INPUT_UNBLOCKERS_JSON,
            DEFAULT_RESEARCH_JSON,
            profile_path,
            DEFAULT_MEMORY,
            DEFAULT_SYNTHETIC_UNBLOCKER_PROOF_JSON,
            DEFAULT_SYNTHETIC_UNBLOCKER_PROOF_MARKDOWN,
            closed_jobs=load_closed_jobs(DEFAULT_CLOSED_JOBS),
            autofill_batch=autofill_batch,
        )
    goal = write_goal_readiness_audit(
        coverage,
        gaps,
        readiness,
        DEFAULT_GOAL_AUDIT_JSON,
        DEFAULT_GOAL_AUDIT_MARKDOWN,
        critical_input_status=critical_status,
        critical_input_updates_readiness=_load_optional_json(str(DEFAULT_CRITICAL_INPUT_UPDATES_READINESS_JSON)),
        fake_learning_probe=_load_optional_json(str(DEFAULT_FAKE_LEARNING_PROBE_JSON)),
        fake_critical_input_probe=_load_optional_json(str(DEFAULT_FAKE_CRITICAL_INPUT_PROBE_JSON)),
        fake_position_rehearsal=_load_optional_json(str(DEFAULT_FAKE_POSITION_REHEARSAL_JSON)),
        autofill_batch_plan=_load_optional_json(str(DEFAULT_AUTOFILL_BATCH_JSON)),
        synthetic_unblocker_proof=_load_optional_json(str(DEFAULT_SYNTHETIC_UNBLOCKER_PROOF_JSON)),
        post_answer_pipeline=_load_optional_json(str(DEFAULT_POST_ANSWER_PIPELINE_JSON)),
        closed_preflight=_load_optional_json(str(DEFAULT_CLOSED_PREFLIGHT_JSON)),
        closed_jobs=_load_optional_json(str(DEFAULT_CLOSED_JOBS)),
        platform_question_playbook=_load_optional_json(str(DEFAULT_PLATFORM_QUESTION_PLAYBOOK_JSON)),
        position_execution_audit=_load_optional_json(str(DEFAULT_POSITION_EXECUTION_AUDIT_JSON)),
        selected_answer_dependencies=_load_optional_json(str(DEFAULT_SELECTED_ANSWER_DEPENDENCIES_JSON)),
        submission_safety_audit=_load_optional_json(str(DEFAULT_SUBMISSION_SAFETY_AUDIT_JSON)),
    )
    if DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_JSON.exists():
        write_final_answer_blocker_report(
            _load_optional_json(str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_JSON)) or {},
            goal,
            DEFAULT_FINAL_ANSWER_BLOCKERS_JSON,
            DEFAULT_FINAL_ANSWER_BLOCKERS_MARKDOWN,
            DEFAULT_FINAL_ANSWER_REPLY_TEMPLATE_TEXT,
            DEFAULT_FINAL_ANSWER_BLOCKERS_HTML,
            DEFAULT_FINAL_ANSWER_BLOCKERS_XLSX,
        )
    apply_queue = write_apply_queue_readiness(
        DEFAULT_AUTOFILL_BATCH_JSON,
        DEFAULT_CRITICAL_INPUT_UPDATES_READINESS_JSON,
        DEFAULT_GOAL_AUDIT_JSON,
        DEFAULT_CLOSED_JOBS,
        DEFAULT_APPLY_QUEUE_JSON,
        DEFAULT_APPLY_QUEUE_MARKDOWN,
        DEFAULT_APPLY_QUEUE_HTML,
        DEFAULT_APPLY_QUEUE_LIVE_CHECK_JOBS,
    )
    apply_queue_handoff = None
    if DEFAULT_CLOSED_PREFLIGHT_JSON.exists():
        supplemental_preflights = (
            [DEFAULT_APPLY_QUEUE_MANUAL_LIVE_CHECK_JSON]
            if DEFAULT_APPLY_QUEUE_MANUAL_LIVE_CHECK_JSON.exists()
            else []
        )
        apply_queue_handoff = write_apply_queue_handoff(
            DEFAULT_APPLY_QUEUE_JSON,
            DEFAULT_CLOSED_PREFLIGHT_JSON,
            DEFAULT_APPLY_QUEUE_HANDOFF_JSON,
            DEFAULT_APPLY_QUEUE_HANDOFF_MARKDOWN,
            DEFAULT_APPLY_QUEUE_HANDOFF_HTML,
            DEFAULT_APPLY_QUEUE_OPEN_READY_JOBS,
            supplemental_preflight_paths=supplemental_preflights,
        )
    apply_queue_autofill_packet = None
    if apply_queue_handoff:
        apply_queue_autofill_packet = write_apply_queue_autofill_packet(
            DEFAULT_RESEARCH_JSON,
            DEFAULT_APPLY_QUEUE_HANDOFF_JSON,
            profile_path,
            DEFAULT_MEMORY,
            DEFAULT_CLOSED_JOBS,
            DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_JSON,
            DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_MARKDOWN,
            DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_HTML,
            limit=100,
            target_count=100,
            include_values=False,
        )
    position_execution_audit = None
    selected_answer_dependencies = None
    if (
        apply_queue_autofill_packet
        and DEFAULT_PLATFORM_QUESTION_PLAYBOOK_JSON.exists()
        and DEFAULT_POST_ANSWER_SYNTHETIC_AUTOFILL_PACKET_JSON.exists()
    ):
        position_execution_audit = write_position_execution_audit(
            DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_JSON,
            DEFAULT_POST_ANSWER_SYNTHETIC_AUTOFILL_PACKET_JSON,
            DEFAULT_PLATFORM_QUESTION_PLAYBOOK_JSON,
            DEFAULT_GOAL_AUDIT_JSON,
            DEFAULT_POSITION_EXECUTION_AUDIT_JSON,
            DEFAULT_POSITION_EXECUTION_AUDIT_MARKDOWN,
            DEFAULT_POSITION_EXECUTION_AUDIT_HTML,
            target_count=100,
        )
        if DEFAULT_RESEARCH_JSON.exists() and DEFAULT_FINAL_ANSWER_BLOCKERS_JSON.exists():
            selected_answer_dependencies = write_selected_final_answer_dependency_report(
                DEFAULT_RESEARCH_JSON,
                DEFAULT_POSITION_EXECUTION_AUDIT_JSON,
                DEFAULT_FINAL_ANSWER_BLOCKERS_JSON,
                DEFAULT_SELECTED_ANSWER_DEPENDENCIES_JSON,
                DEFAULT_SELECTED_ANSWER_DEPENDENCIES_MARKDOWN,
                DEFAULT_SELECTED_ANSWER_DEPENDENCIES_HTML,
                target_count=100,
            )
        goal = write_goal_readiness_audit(
            coverage,
            gaps,
            readiness,
            DEFAULT_GOAL_AUDIT_JSON,
            DEFAULT_GOAL_AUDIT_MARKDOWN,
            critical_input_status=critical_status,
            critical_input_updates_readiness=_load_optional_json(str(DEFAULT_CRITICAL_INPUT_UPDATES_READINESS_JSON)),
            fake_learning_probe=_load_optional_json(str(DEFAULT_FAKE_LEARNING_PROBE_JSON)),
            fake_critical_input_probe=_load_optional_json(str(DEFAULT_FAKE_CRITICAL_INPUT_PROBE_JSON)),
            fake_position_rehearsal=_load_optional_json(str(DEFAULT_FAKE_POSITION_REHEARSAL_JSON)),
            autofill_batch_plan=_load_optional_json(str(DEFAULT_AUTOFILL_BATCH_JSON)),
            synthetic_unblocker_proof=_load_optional_json(str(DEFAULT_SYNTHETIC_UNBLOCKER_PROOF_JSON)),
            post_answer_pipeline=_load_optional_json(str(DEFAULT_POST_ANSWER_PIPELINE_JSON)),
            closed_preflight=_load_optional_json(str(DEFAULT_CLOSED_PREFLIGHT_JSON)),
            closed_jobs=_load_optional_json(str(DEFAULT_CLOSED_JOBS)),
            platform_question_playbook=_load_optional_json(str(DEFAULT_PLATFORM_QUESTION_PLAYBOOK_JSON)),
            position_execution_audit=position_execution_audit,
            selected_answer_dependencies=(
                selected_answer_dependencies
                or _load_optional_json(str(DEFAULT_SELECTED_ANSWER_DEPENDENCIES_JSON))
            ),
            submission_safety_audit=_load_optional_json(str(DEFAULT_SUBMISSION_SAFETY_AUDIT_JSON)),
        )
    submission_safety_audit = write_submission_safety_audit(
        DEFAULT_SUBMISSION_SAFETY_AUDIT_JSON,
        DEFAULT_SUBMISSION_SAFETY_AUDIT_MARKDOWN,
        fake_position_rehearsal=_load_optional_json(str(DEFAULT_FAKE_POSITION_REHEARSAL_JSON)),
        post_answer_pipeline=_load_optional_json(str(DEFAULT_POST_ANSWER_PIPELINE_JSON)),
        apply_queue_autofill_packet=apply_queue_autofill_packet
        or _load_optional_json(str(DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_JSON)),
        browser_review_queue_audit=_load_optional_json(str(DEFAULT_REVIEW_QUEUE_AUDIT_JSON)),
        pre_submit_review=_load_optional_json(str(DEFAULT_PRE_SUBMIT_REVIEW_JSON)),
        goal_readiness_audit=goal,
    )
    goal = write_goal_readiness_audit(
        coverage,
        gaps,
        readiness,
        DEFAULT_GOAL_AUDIT_JSON,
        DEFAULT_GOAL_AUDIT_MARKDOWN,
        critical_input_status=critical_status,
        critical_input_updates_readiness=_load_optional_json(str(DEFAULT_CRITICAL_INPUT_UPDATES_READINESS_JSON)),
        fake_learning_probe=_load_optional_json(str(DEFAULT_FAKE_LEARNING_PROBE_JSON)),
        fake_critical_input_probe=_load_optional_json(str(DEFAULT_FAKE_CRITICAL_INPUT_PROBE_JSON)),
        fake_position_rehearsal=_load_optional_json(str(DEFAULT_FAKE_POSITION_REHEARSAL_JSON)),
        autofill_batch_plan=_load_optional_json(str(DEFAULT_AUTOFILL_BATCH_JSON)),
        synthetic_unblocker_proof=_load_optional_json(str(DEFAULT_SYNTHETIC_UNBLOCKER_PROOF_JSON)),
        post_answer_pipeline=_load_optional_json(str(DEFAULT_POST_ANSWER_PIPELINE_JSON)),
        closed_preflight=_load_optional_json(str(DEFAULT_CLOSED_PREFLIGHT_JSON)),
        closed_jobs=_load_optional_json(str(DEFAULT_CLOSED_JOBS)),
        platform_question_playbook=_load_optional_json(str(DEFAULT_PLATFORM_QUESTION_PLAYBOOK_JSON)),
        position_execution_audit=position_execution_audit
        or _load_optional_json(str(DEFAULT_POSITION_EXECUTION_AUDIT_JSON)),
        selected_answer_dependencies=(
            selected_answer_dependencies
            or _load_optional_json(str(DEFAULT_SELECTED_ANSWER_DEPENDENCIES_JSON))
        ),
        submission_safety_audit=submission_safety_audit,
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
        critical_input_updates_readiness=_load_optional_json(str(DEFAULT_CRITICAL_INPUT_UPDATES_READINESS_JSON)),
        final_answer_intake_template=_load_optional_json(str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_JSON)),
        final_answer_intake_update=_load_optional_json(str(DEFAULT_FINAL_ANSWER_INTAKE_REPORT_JSON)),
        apply_queue_handoff=apply_queue_handoff,
        apply_queue_autofill_packet=apply_queue_autofill_packet,
        apply_queue_refresh=_load_optional_json(str(DEFAULT_APPLY_QUEUE_REFRESH_JSON)),
        position_execution_audit=position_execution_audit,
        selected_answer_dependencies=(
            selected_answer_dependencies
            or _load_optional_json(str(DEFAULT_SELECTED_ANSWER_DEPENDENCIES_JSON))
        ),
        submission_safety_audit=submission_safety_audit,
        source_artifacts=_question_export_source_artifacts(
            {
                "Goal readiness audit": str(DEFAULT_GOAL_AUDIT_JSON),
                "Critical input questionnaire": str(DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_JSON),
                "Critical input impact": str(DEFAULT_CRITICAL_INPUT_IMPACT_JSON),
                "Autofill batch": str(DEFAULT_AUTOFILL_BATCH_JSON),
                "Synthetic unblocker proof": str(DEFAULT_SYNTHETIC_UNBLOCKER_PROOF_JSON),
                "Critical input full updates template": str(DEFAULT_CRITICAL_INPUT_FULL_UPDATES_JSON),
                "Critical input confirmed updates": str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_JSON),
                "Critical input confirmed updates report": str(DEFAULT_CRITICAL_INPUT_CONFIRMED_UPDATES_REPORT_JSON),
                "Critical input updates readiness": str(DEFAULT_CRITICAL_INPUT_UPDATES_READINESS_JSON),
                "Final answer intake template": str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_JSON),
                "Final answer intake template Markdown": str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_MARKDOWN),
                "Final answer intake template HTML": str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_HTML),
                "Final answer intake report": str(DEFAULT_FINAL_ANSWER_INTAKE_REPORT_JSON),
                "Final answer intake report Markdown": str(DEFAULT_FINAL_ANSWER_INTAKE_REPORT_MARKDOWN),
                "Final answer blockers": str(DEFAULT_FINAL_ANSWER_BLOCKERS_JSON),
                "Final answer blockers Markdown": str(DEFAULT_FINAL_ANSWER_BLOCKERS_MARKDOWN),
                "Final answer blockers HTML": str(DEFAULT_FINAL_ANSWER_BLOCKERS_HTML),
                "Final answer blockers XLSX": str(DEFAULT_FINAL_ANSWER_BLOCKERS_XLSX),
                "Final answer reply template": str(DEFAULT_FINAL_ANSWER_REPLY_TEMPLATE_TEXT),
                "Apply queue": str(DEFAULT_APPLY_QUEUE_JSON),
                "Apply queue HTML": str(DEFAULT_APPLY_QUEUE_HTML),
                "Apply queue live-check jobs": str(DEFAULT_APPLY_QUEUE_LIVE_CHECK_JOBS),
                "Apply queue handoff": str(DEFAULT_APPLY_QUEUE_HANDOFF_JSON),
                "Apply queue handoff HTML": str(DEFAULT_APPLY_QUEUE_HANDOFF_HTML),
                "Apply queue open-ready jobs": str(DEFAULT_APPLY_QUEUE_OPEN_READY_JOBS),
                "Apply queue autofill packet": str(DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_JSON),
                "Apply queue autofill packet HTML": str(DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_HTML),
                "Apply queue refresh": str(DEFAULT_APPLY_QUEUE_REFRESH_JSON),
                "Apply queue refresh Markdown": str(DEFAULT_APPLY_QUEUE_REFRESH_MARKDOWN),
                "Position execution audit": str(DEFAULT_POSITION_EXECUTION_AUDIT_JSON),
                "Position execution audit HTML": str(DEFAULT_POSITION_EXECUTION_AUDIT_HTML),
                "Selected answer dependencies": str(DEFAULT_SELECTED_ANSWER_DEPENDENCIES_JSON),
                "Selected answer dependencies Markdown": str(DEFAULT_SELECTED_ANSWER_DEPENDENCIES_MARKDOWN),
                "Selected answer dependencies HTML": str(DEFAULT_SELECTED_ANSWER_DEPENDENCIES_HTML),
                "Browser review queue audit": str(DEFAULT_REVIEW_QUEUE_AUDIT_JSON),
                "Browser review queue audit Markdown": str(DEFAULT_REVIEW_QUEUE_AUDIT_MARKDOWN),
                "Submission safety audit": str(DEFAULT_SUBMISSION_SAFETY_AUDIT_JSON),
                "Submission safety audit Markdown": str(DEFAULT_SUBMISSION_SAFETY_AUDIT_MARKDOWN),
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
                    "Apply queue": str(DEFAULT_APPLY_QUEUE_JSON),
                    "Apply queue HTML": str(DEFAULT_APPLY_QUEUE_HTML),
                    "Apply queue live-check jobs": str(DEFAULT_APPLY_QUEUE_LIVE_CHECK_JOBS),
                    "Apply queue handoff": str(DEFAULT_APPLY_QUEUE_HANDOFF_JSON),
                    "Apply queue handoff HTML": str(DEFAULT_APPLY_QUEUE_HANDOFF_HTML),
                    "Apply queue open-ready jobs": str(DEFAULT_APPLY_QUEUE_OPEN_READY_JOBS),
                    "Apply queue autofill packet": str(DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_JSON),
                    "Apply queue autofill packet HTML": str(DEFAULT_APPLY_QUEUE_AUTOFILL_PACKET_HTML),
                    "Apply queue refresh": str(DEFAULT_APPLY_QUEUE_REFRESH_JSON),
                    "Apply queue refresh Markdown": str(DEFAULT_APPLY_QUEUE_REFRESH_MARKDOWN),
                    "Position execution audit": str(DEFAULT_POSITION_EXECUTION_AUDIT_JSON),
                    "Position execution audit HTML": str(DEFAULT_POSITION_EXECUTION_AUDIT_HTML),
                    "Browser review queue audit": str(DEFAULT_REVIEW_QUEUE_AUDIT_JSON),
                    "Browser review queue audit Markdown": str(DEFAULT_REVIEW_QUEUE_AUDIT_MARKDOWN),
                    "Submission safety audit": str(DEFAULT_SUBMISSION_SAFETY_AUDIT_JSON),
                    "Submission safety audit Markdown": str(DEFAULT_SUBMISSION_SAFETY_AUDIT_MARKDOWN),
                    "Critical input suggestions": str(DEFAULT_CRITICAL_INPUT_SUGGESTIONS_JSON),
                    "Critical input questionnaire": str(DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_JSON),
                    "Critical input questionnaire HTML": str(DEFAULT_CRITICAL_INPUT_QUESTIONNAIRE_HTML),
                    "Critical input preflight": str(DEFAULT_CRITICAL_INPUT_PREFLIGHT_JSON),
                    "Critical input preflight HTML": str(DEFAULT_CRITICAL_INPUT_PREFLIGHT_HTML),
                    "Critical input impact": str(DEFAULT_CRITICAL_INPUT_IMPACT_JSON),
                    "Critical input impact HTML": str(DEFAULT_CRITICAL_INPUT_IMPACT_HTML),
                    "Synthetic unblocker proof": str(DEFAULT_SYNTHETIC_UNBLOCKER_PROOF_JSON),
                    "Critical input full updates template": str(DEFAULT_CRITICAL_INPUT_FULL_UPDATES_JSON),
                    "Critical input updates readiness": str(DEFAULT_CRITICAL_INPUT_UPDATES_READINESS_JSON),
                    "Final answer intake template": str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_JSON),
                    "Final answer intake template Markdown": str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_MARKDOWN),
                    "Final answer intake template HTML": str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_HTML),
                    "Final answer intake report": str(DEFAULT_FINAL_ANSWER_INTAKE_REPORT_JSON),
                    "Final answer intake report Markdown": str(DEFAULT_FINAL_ANSWER_INTAKE_REPORT_MARKDOWN),
                    "Final answer blockers": str(DEFAULT_FINAL_ANSWER_BLOCKERS_JSON),
                    "Final answer blockers Markdown": str(DEFAULT_FINAL_ANSWER_BLOCKERS_MARKDOWN),
                    "Final answer blockers HTML": str(DEFAULT_FINAL_ANSWER_BLOCKERS_HTML),
                    "Final answer blockers XLSX": str(DEFAULT_FINAL_ANSWER_BLOCKERS_XLSX),
                    "Final answer reply template": str(DEFAULT_FINAL_ANSWER_REPLY_TEMPLATE_TEXT),
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
            critical_input_unblockers=_load_optional_json(str(DEFAULT_CRITICAL_INPUT_UNBLOCKERS_JSON)),
            final_answer_intake_template=_load_optional_json(str(DEFAULT_FINAL_ANSWER_INTAKE_TEMPLATE_JSON)),
            final_answer_intake_update=_load_optional_json(str(DEFAULT_FINAL_ANSWER_INTAKE_REPORT_JSON)),
            autofill_batch=_load_optional_json(str(DEFAULT_AUTOFILL_BATCH_JSON)),
            apply_queue_handoff=apply_queue_handoff,
            apply_queue_refresh=_load_optional_json(str(DEFAULT_APPLY_QUEUE_REFRESH_JSON)),
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
            "learning-template",
            "learning-approval-pack",
            "critical-inputs-template",
            "critical-inputs-status",
            "critical-input-suggestions",
            "critical-inputs-questionnaire",
            "critical-inputs-impact",
            "autofill-batch",
            "synthetic-unblocker-proof",
            "critical-inputs-readiness",
            "goal-audit",
            "apply-queue",
            "apply-queue-handoff" if apply_queue_handoff else "apply-queue-handoff-skipped",
            "apply-queue-autofill-packet" if apply_queue_autofill_packet else "apply-queue-autofill-packet-skipped",
            "submission-safety-audit",
            "automation-handoff",
            "export-questions",
        ],
        "goal_status": goal.get("status"),
        "goal_complete": bool(goal.get("goal_complete")),
        "apply_queue_status": apply_queue.get("status"),
        "apply_queue_live_check_jobs": apply_queue.get("live_check_job_count", 0),
        "apply_queue_handoff_status": (apply_queue_handoff or {}).get("status"),
        "apply_queue_open_ready": (apply_queue_handoff or {}).get("open_ready_count", 0),
        "apply_queue_autofill_packet_status": (apply_queue_autofill_packet or {}).get("status"),
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
