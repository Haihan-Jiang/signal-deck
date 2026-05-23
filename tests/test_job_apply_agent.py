from __future__ import annotations

import json
import argparse
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from job_apply_agent.core import (
    CandidateProfile,
    DEFAULT_QUESTIONS,
    add_synthetic_answers_for_blockers,
    apply_critical_input_answers,
    apply_learning_task_answers,
    build_answer_gap_report,
    build_apply_queue_autofill_packet,
    build_apply_queue_handoff,
    build_apply_queue_readiness,
    build_apply_run_audit,
    build_application_draft,
    build_application_playbook,
    build_application_research,
    build_automation_handoff_report,
    build_autofill_batch_plan,
    build_collection_plan_from_coverage_gate,
    build_critical_input_answer_template,
    build_critical_input_answer_update,
    build_critical_input_impact_report,
    build_critical_input_preflight,
    build_critical_input_questionnaire,
    build_critical_input_suggestion_packet,
    build_critical_input_status_report,
    build_critical_input_unblocker_final_update,
    build_critical_input_unblocker_packet,
    build_critical_input_updates_readiness,
    build_synthetic_unblocker_proof,
    build_question_export,
    build_browser_action_manifest,
    build_browser_review_queue_audit,
    build_closed_posting_preflight,
    build_browser_dom_execution_plan,
    build_browser_dom_runner_script,
    build_browser_review_record,
    build_form_fill_plan,
    build_fake_learning_probe,
    build_fake_critical_input_probe,
    build_fake_position_rehearsal,
    build_final_answer_blocker_report,
    build_final_answer_reply_intake,
    build_final_answer_intake_template,
    build_final_answer_intake_update,
    build_goal_readiness_audit,
    build_learning_approval_pack,
    build_platform_question_playbook,
    build_position_execution_audit,
    build_learning_task_template,
    build_pre_submit_review,
    build_position_readiness_report,
    build_research_coverage_gate,
    build_telegram_final_answer_blocker_alert,
    build_telegram_job_alert,
    build_synthetic_learning_state,
    build_synthetic_unblocker_compact_updates,
    build_submission_safety_audit,
    classify_application_prompt,
    closed_application_match,
    closed_application_reason,
    closed_application_phrase,
    discover_candidates_from_collection_plan,
    execute_browser_action_manifest_locally,
    execute_form_plan_offline,
    extract_application_prompts_from_html,
    extract_live_job_page_metadata,
    extract_linkedin_job_id,
    find_learned_answer,
    import_candidate_observations,
    job_registry_key,
    is_safe_browser_execution_target,
    is_job_closed,
    learn_answers,
    load_answer_memory,
    load_candidate_rows,
    load_closed_jobs,
    load_jobs,
    load_profile,
    load_submissions_jsonl,
    load_telegram_config,
    notify_telegram_for_final_answer_blockers,
    notify_telegram_for_submissions,
    observe_candidate_pages,
    open_apply_urls_in_browser,
    record_closed_job,
    refresh_closed_jobs_from_live_pages,
    render_answer_gap_markdown,
    render_apply_queue_autofill_packet_html,
    render_apply_queue_autofill_packet_markdown,
    render_apply_queue_handoff_html,
    render_apply_queue_handoff_markdown,
    render_apply_queue_readiness_html,
    render_apply_queue_readiness_markdown,
    render_apply_run_audit_markdown,
    render_application_playbook_markdown,
    render_automation_handoff_html,
    render_automation_handoff_markdown,
    render_autofill_batch_plan_html,
    render_autofill_batch_plan_markdown,
    render_candidate_observation_markdown,
    render_candidate_discovery_markdown,
    render_question_export_html,
    render_application_research_markdown,
    render_collection_plan_markdown,
    render_browser_action_manifest_markdown,
    render_browser_review_queue_audit_markdown,
    render_closed_posting_preflight_markdown,
    render_critical_input_answer_template_markdown,
    render_critical_input_answer_workflow_markdown,
    render_critical_input_answer_update_markdown,
    render_critical_input_impact_html,
    render_critical_input_impact_markdown,
    render_critical_input_preflight_html,
    render_critical_input_preflight_markdown,
    render_critical_input_questionnaire_html,
    render_critical_input_questionnaire_markdown,
    render_critical_input_suggestions_markdown,
    render_critical_input_status_markdown,
    render_critical_input_unblocker_final_update_markdown,
    render_critical_input_unblocker_html,
    render_critical_input_unblocker_markdown,
    render_critical_input_updates_readiness_markdown,
    render_synthetic_unblocker_proof_markdown,
    render_submission_safety_audit_markdown,
    render_browser_dom_execution_plan_markdown,
    render_form_fill_plan_markdown,
    render_fake_learning_probe_markdown,
    render_fake_critical_input_probe_markdown,
    render_fake_position_rehearsal_markdown,
    render_final_answer_intake_template_html,
    render_final_answer_intake_template_markdown,
    render_final_answer_intake_update_markdown,
    render_final_answer_blocker_report_markdown,
    render_final_answer_reply_intake_markdown,
    render_final_answer_reply_template_text,
    render_goal_readiness_audit_markdown,
    render_learning_approval_pack_markdown,
    render_learning_task_template_markdown,
    render_pre_submit_review_markdown,
    render_position_readiness_markdown,
    render_platform_question_playbook_html,
    render_platform_question_playbook_markdown,
    render_research_coverage_gate_markdown,
    render_synthetic_apply_execution_markdown,
    render_synthetic_browser_action_execution_markdown,
    render_synthetic_application_html,
    run_synthetic_application_simulation,
    run_synthetic_apply_execution,
    run_synthetic_browser_action_execution,
    run_pipeline,
    save_final_answer_intake_payload,
    score_job,
    select_candidate_topup,
    shorten_apply_url,
    write_answer_gap_report,
    write_apply_queue_autofill_packet,
    write_apply_queue_handoff,
    write_apply_queue_readiness,
    write_apply_run_audit,
    write_application_playbook,
    write_application_research_report,
    write_automation_handoff_report,
    write_autofill_batch_plan,
    write_browser_action_manifest,
    write_browser_review_queue_audit,
    write_candidate_observation_report,
    write_candidate_discovery_report,
    write_candidate_topup_selection_report,
    write_closed_posting_preflight,
    write_collection_plan,
    write_critical_input_answer_template,
    write_critical_input_answer_workflow,
    write_critical_input_answer_update,
    write_critical_input_impact_report,
    write_critical_input_preflight,
    write_critical_input_questionnaire,
    write_critical_input_suggestion_packet,
    write_critical_input_status_report,
    write_critical_input_unblocker_final_update,
    write_critical_input_unblocker_packet,
    write_critical_input_updates_readiness,
    write_synthetic_unblocker_proof,
    write_submission_safety_audit,
    write_question_export,
    write_browser_dom_harness,
    write_form_fill_plan,
    write_fake_learning_probe,
    write_fake_critical_input_probe,
    write_fake_position_rehearsal,
    write_final_answer_intake_template,
    write_final_answer_intake_update,
    write_final_answer_blocker_report,
    write_final_answer_reply_intake,
    write_goal_readiness_audit,
    write_learning_approval_pack,
    write_learning_task_template,
    write_pre_submit_review,
    write_position_readiness_report,
    write_platform_question_playbook,
    write_position_execution_audit,
    write_research_coverage_gate,
    write_synthetic_apply_execution,
    write_synthetic_application_simulation,
    write_synthetic_browser_action_execution,
)
from job_apply_agent.__main__ import (
    _post_answer_pipeline_summary,
    _validate_final_answer_intake_server_post_answer_args,
)


ROOT = Path(__file__).resolve().parents[1]


class JobApplyAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = load_profile(ROOT / "job_apply_agent" / "sample_profile.json")
        self.jobs = load_jobs(ROOT / "job_apply_agent" / "sample_jobs.json")

    def test_scores_matching_job_above_blocked_job(self) -> None:
        matching = score_job(self.profile, self.jobs[0])
        blocked = score_job(self.profile, self.jobs[2])
        self.assertTrue(matching.matched)
        self.assertGreater(matching.score, blocked.score)
        self.assertFalse(blocked.matched)

    def test_closed_job_is_not_matched(self) -> None:
        job = {
            "company": "Example",
            "title": "Site Reliability Engineer",
            "location": "Remote",
            "description": "Python Kubernetes reliability role.",
            "page_excerpt": ["No longer accepting applications"],
        }
        score = score_job(self.profile, job)
        self.assertFalse(score.matched)
        self.assertEqual(score.score, 0)
        self.assertIn("closed:no_longer_accepting_applications", score.reasons)
        self.assertTrue(is_job_closed(job))
        self.assertEqual(
            closed_application_reason(job),
            "closed:no_longer_accepting_applications",
        )
        self.assertEqual(closed_application_phrase(job), "no longer accepting applications")
        match = closed_application_match(job)
        self.assertIsNotNone(match)
        self.assertEqual(match.source_field, "page_excerpt")
        self.assertIn("No longer accepting applications", match.snippet)

    def test_pipeline_skips_closed_jobs(self) -> None:
        closed_job = dict(self.jobs[0])
        closed_job["page_excerpt"] = ["No longer accepting applications"]
        with tempfile.TemporaryDirectory() as temp_dir:
            outbox = Path(temp_dir) / "submissions.jsonl"
            submissions = run_pipeline(self.profile, [closed_job, self.jobs[0]], outbox, limit=5)
            self.assertEqual(len(submissions), 1)
            self.assertEqual(submissions[0]["company"], self.jobs[0]["company"])

    def test_closed_registry_skips_job_without_page_text(self) -> None:
        job = {
            "platform": "LinkedIn",
            "job_id": "4415508499",
            "company": "Tesla",
            "title": "SRE",
            "apply_url": "https://www.linkedin.com/jobs/view/4415508499/?trk=search",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            closed_path = Path(temp_dir) / "closed_jobs.json"
            record = record_closed_job(
                closed_path,
                job,
                reason="No longer accepting applications",
                source="test",
            )
            self.assertEqual(record["key"], "linkedin:4415508499")
            closed_jobs = load_closed_jobs(closed_path)
            score = score_job(self.profile, job, closed_jobs=closed_jobs)
            self.assertFalse(score.matched)
            self.assertEqual(score.reasons, ["closed:no_longer_accepting_applications"])

    def test_linkedin_job_registry_key_uses_job_id(self) -> None:
        job = {
            "apply_url": "https://www.linkedin.com/jobs/view/4415508499/?trackingId=x",
        }
        self.assertEqual(extract_linkedin_job_id(job["apply_url"]), "4415508499")
        self.assertEqual(job_registry_key(job), "linkedin:4415508499")
        slug_job = {
            "apply_url": "https://www.linkedin.com/jobs/view/site-reliability-engineer-at-clay-4338540053?position=1",
        }
        self.assertEqual(extract_linkedin_job_id(slug_job["apply_url"]), "4338540053")
        self.assertEqual(job_registry_key(slug_job), "linkedin:4338540053")

    def test_ats_job_registry_key_canonicalizes_tracking_and_trailing_slash(self) -> None:
        ashby_a = {
            "apply_url": "https://jobs.ashbyhq.com/scribe/ccafdcaf-3249-4a85-adb0-7c865dbd045b/?src=LinkedIn",
        }
        ashby_b = {
            "apply_url": "https://jobs.ashbyhq.com/scribe/ccafdcaf-3249-4a85-adb0-7c865dbd045b",
        }
        self.assertEqual(job_registry_key(ashby_a), job_registry_key(ashby_b))
        self.assertEqual(
            shorten_apply_url(ashby_a["apply_url"]),
            "https://jobs.ashbyhq.com/scribe/ccafdcaf-3249-4a85-adb0-7c865dbd045b",
        )

    def test_answer_generation_uses_known_profile_facts(self) -> None:
        draft = build_application_draft(self.profile, self.jobs[0])
        why_answer = draft.answers["Why are you interested in this role?"]
        self.assertIn("backend and automation engineer", why_answer)
        self.assertEqual(draft.missing_facts, [])

    def test_direct_answers_handle_common_form_questions(self) -> None:
        draft = build_application_draft(self.profile, self.jobs[0])
        self.assertEqual(
            draft.answers["Are you authorized to work in the United States?"],
            "PLACEHOLDER: I am authorized to work in the United States.",
        )

        profile = CandidateProfile(
            name="Alan Jiang",
            email="alan@example.com",
            phone="555-0100",
            location="Bellevue, WA",
            target_titles=["Site Reliability Engineer"],
            target_locations=["United States"],
            remote_ok=True,
            keywords=["sre"],
            blocklist=[],
            min_score=1,
            resume_facts={"professional_summary": "SRE"},
            question_answers={
                "start_date": "I can start in about two months.",
                "ai_application_disclosure": "Yes",
                "compensation_currency": "USD",
                "policy_acknowledgement": "Yes, I acknowledge.",
                "referral_contact": "N/A - no specific employee referral.",
            },
        )
        job = {
            **self.jobs[0],
            "questions": [
                "How many weeks after accepting an offer could you start?",
                "What is your earliest possible starting date?",
                "Did AI complete or submit this application?",
                "Are you actively looking for a job, or just exploring future opportunities?",
                "When would you like to hear back from us regarding potential opportunities?",
                "If someone at SEON referred you, who should we thank?",
                "If someone referred you, please add note their name below",
                "I acknowledge SEON's Recruitment Privacy Notice and understand how my data will be used for recruitment.",
                "This role does not require active security clearance at the time of hiring, but candidates must be eligible and willing to obtain company-sponsored security clearance after starting. Are you willing and able to meet this requirement?",
                "What aspects of startup culture resonate with you, and how do you believe they align with your working style?",
                "What aspects of the cryptocurrency industry appeal to you, and how do they align with your career goals?",
            ],
        }
        draft = build_application_draft(profile, job)
        self.assertEqual(
            draft.answers["How many weeks after accepting an offer could you start?"],
            "About 8 weeks after offer acceptance.",
        )
        self.assertEqual(
            draft.answers["What is your earliest possible starting date?"],
            "I can start in about two months.",
        )
        self.assertEqual(
            draft.answers["Did AI complete or submit this application?"],
            "Yes",
        )
        self.assertEqual(
            draft.answers["Are you actively looking for a job, or just exploring future opportunities?"],
            "I am actively looking for the right role. I can start in about two months.",
        )
        self.assertEqual(
            draft.answers["When would you like to hear back from us regarding potential opportunities?"],
            "As soon as convenient for the recruiting team.",
        )
        self.assertEqual(
            draft.answers["If someone at SEON referred you, who should we thank?"],
            "N/A - no specific employee referral.",
        )
        self.assertEqual(
            draft.answers["If someone referred you, please add note their name below"],
            "N/A - no specific employee referral.",
        )
        self.assertEqual(
            draft.answers[
                "I acknowledge SEON's Recruitment Privacy Notice and understand how my data will be used for recruitment."
            ],
            "Yes, I acknowledge.",
        )
        self.assertNotEqual(
            draft.answers[
                "This role does not require active security clearance at the time of hiring, but candidates must be eligible and willing to obtain company-sponsored security clearance after starting. Are you willing and able to meet this requirement?"
            ],
            "Yes, I will now or in the future require visa sponsorship or a visa transfer.",
        )
        self.assertNotEqual(
            draft.answers[
                "What aspects of startup culture resonate with you, and how do you believe they align with your working style?"
            ],
            "I can start in about two months.",
        )
        self.assertNotEqual(
            draft.answers[
                "What aspects of the cryptocurrency industry appeal to you, and how do they align with your career goals?"
            ],
            "USD",
        )

    def test_pipeline_writes_dry_run_submission(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            outbox = Path(temp_dir) / "submissions.jsonl"
            submissions = run_pipeline(self.profile, self.jobs, outbox, limit=1)
            self.assertEqual(len(submissions), 1)
            row = json.loads(outbox.read_text(encoding="utf-8").strip())
            self.assertTrue(row["dry_run"])
            self.assertEqual(row["status"], "SIMULATED_SUBMITTED")
            self.assertFalse(row["safety"]["real_platform_submission"])

    def test_load_submissions_jsonl_limits_to_latest_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            outbox = Path(temp_dir) / "submissions.jsonl"
            run_pipeline(self.profile, self.jobs, outbox, limit=2)
            rows = load_submissions_jsonl(outbox, limit=1)
            self.assertEqual(len(rows), 1)
            self.assertIn("submission_id", rows[0])

    def test_missing_facts_are_reported_instead_of_invented(self) -> None:
        thin_profile = CandidateProfile(
            name="PLACEHOLDER",
            email="placeholder@example.com",
            phone="PLACEHOLDER",
            location="Remote",
            target_titles=["AI Engineer"],
            target_locations=["Remote"],
            remote_ok=True,
            keywords=["python"],
            blocklist=[],
            min_score=1,
            resume_facts={},
            question_answers={},
        )
        draft = build_application_draft(thin_profile, self.jobs[0])
        self.assertIn("professional_summary", draft.missing_facts)
        self.assertIn("PLACEHOLDER_PROFESSIONAL_SUMMARY", draft.cover_note)

    def test_gcp_question_requires_verified_fact(self) -> None:
        job = {
            "title": "Site Reliability Engineer",
            "company": "Example",
            "questions": ["Do you have 1+ years of Google Cloud Platform experience?"],
        }
        draft = build_application_draft(self.profile, job)
        self.assertIn("gcp_experience", draft.missing_facts)
        self.assertIn("should not claim", next(iter(draft.answers.values())))

    def test_learns_and_reuses_approved_answers(self) -> None:
        job = {
            "platform": "LinkedIn",
            "company": "Example",
            "title": "Site Reliability Engineer",
            "job_id": "1",
            "questions": ["How many years of Kubernetes operations experience do you have?"],
        }
        answers = {
            "How many years of Kubernetes operations experience do you have?": "3 years"
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "memory.json"
            memory = learn_answers(memory_path, job, answers)
            self.assertEqual(len(memory["answers"]), 1)
            loaded = load_answer_memory(memory_path)
            match = find_learned_answer(
                loaded, "How many years of Kubernetes operations experience do you have?"
            )
            self.assertIsNotNone(match)
            self.assertEqual(match.answer, "3 years")

            draft = build_application_draft(self.profile, job, answer_memory=loaded)
            self.assertEqual(
                draft.answers["How many years of Kubernetes operations experience do you have?"],
                "3 years",
            )
            self.assertIn("learned", draft.answer_sources[next(iter(draft.answer_sources))])

    def test_category_default_policy_learning_covers_new_prompt_variants(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = Path(temp_dir) / "learning_tasks.json"
            profile_path = Path(temp_dir) / "profile.json"
            memory_path = Path(temp_dir) / "answer_memory.json"
            template_path.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "group_key": "answer_memory:employment_history:default_policy",
                                "question": "Should automation answer no to prior employer questions?",
                                "recommended_storage": "answer_memory",
                                "labels": ["Have you previously worked for Acme?"],
                                "approved": True,
                                "answer": "No",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            profile_path.write_text(
                json.dumps(
                    {
                        "candidate": {"name": "Test User"},
                        "preferences": {},
                        "resume_facts": {},
                        "question_answers": {},
                    }
                ),
                encoding="utf-8",
            )

            result = apply_learning_task_answers(template_path, profile_path, memory_path)

            self.assertEqual(result["category_policy_updates"], ["employment_history"])
            memory = load_answer_memory(memory_path)
            category_entries = [
                entry
                for entry in memory["answers"]
                if entry.get("match_scope") == "category_default_policy"
            ]
            self.assertEqual(len(category_entries), 1)
            match = find_learned_answer(memory, "Have you ever interviewed at Stripe?")
            self.assertIsNotNone(match)
            self.assertEqual(match.answer, "No")
            self.assertIn("learned_category_policy", match.source)

    def test_category_default_policy_keeps_sensitive_prompts_uncovered(self) -> None:
        memory = {
            "answers": [
                {
                    "normalized_question": "category default policy conflict_of_interest",
                    "sample_question": "Default policy for conflict_of_interest",
                    "answer": "No",
                    "approved_count": 1,
                    "source": "test",
                    "match_scope": "category_default_policy",
                    "category": "conflict_of_interest",
                    "group_key": "answer_memory:conflict_of_interest:default_policy",
                }
            ]
        }

        self.assertIsNone(find_learned_answer(memory, "Gender"))

    def test_category_default_policy_covers_human_review_prompt_as_review_required(self) -> None:
        memory = {
            "answers": [
                {
                    "normalized_question": "category default policy conflict_of_interest",
                    "sample_question": "Default policy for conflict_of_interest",
                    "answer": "No",
                    "approved_count": 1,
                    "source": "test",
                    "match_scope": "category_default_policy",
                    "category": "conflict_of_interest",
                    "group_key": "answer_memory:conflict_of_interest:default_policy",
                }
            ]
        }
        research = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "positions_observed_total": 1,
            "items": [
                {
                    "label": "Do you know anyone currently at Glean?",
                    "normalized_label": "do you know anyone currently at glean",
                    "category": "conflict_of_interest",
                    "automation_action": "human_review_required",
                    "sensitivity": "policy",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "glean.json",
                }
            ],
        }

        report = build_answer_gap_report(research, self.profile, memory)
        status = report["prompt_statuses"][0]

        self.assertEqual(status["coverage_status"], "covered_requires_review")
        self.assertEqual(status["answer_source"], "learned_category_policy:test")
        self.assertEqual(report["blocking_prompt_count"], 0)

    def test_unattended_submit_requires_explicit_flag_and_no_missing_facts(self) -> None:
        job = self.jobs[0]
        profile = CandidateProfile(
            name="Alan Jiang",
            email="alan@example.com",
            phone="555-0100",
            location="Bellevue, WA",
            target_titles=["AI Engineer"],
            target_locations=["Remote"],
            remote_ok=True,
            keywords=["python", "automation", "agents", "backend", "llm"],
            blocklist=[],
            min_score=50,
            resume_facts={
                "professional_summary": "SRE and automation engineer",
                "strongest_skills": "Python, automation, agents, and backend systems",
                "impact_example": "Built production automation for reliability workflows",
            },
            question_answers={
                "authorization": "I am authorized to work in the United States.",
                "compensation": "I am open based on role scope and total package.",
            },
        )
        supervised = build_application_draft(profile, job)
        self.assertTrue(supervised.automation["ready_for_autofill"])
        self.assertFalse(supervised.automation["ready_for_unattended_submit"])

        unattended = build_application_draft(
            profile, job, allow_unattended_submit=True
        )
        self.assertTrue(unattended.automation["ready_for_unattended_submit"])

    def test_years_experience_question_uses_standard_answer(self) -> None:
        profile = CandidateProfile(
            name="Alan Jiang",
            email="alan@example.com",
            phone="555-0100",
            location="Bellevue, WA",
            target_titles=["Site Reliability Engineer"],
            target_locations=["United States"],
            remote_ok=True,
            keywords=["sre"],
            blocklist=[],
            min_score=1,
            resume_facts={},
            question_answers={"years_experience": "4 years or less."},
        )
        job = {
            "title": "Site Reliability Engineer",
            "company": "Example",
            "questions": ["How many years of Python experience do you have?"],
        }
        draft = build_application_draft(profile, job)
        self.assertEqual(
            draft.answers["How many years of Python experience do you have?"],
            "4 years or less.",
        )

    def test_telegram_config_reuses_existing_signal_deck_env_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / "telegram.env"
            env_path.write_text(
                "\n".join(
                    [
                        'export SIGNAL_DECK_TELEGRAM_BOT_TOKEN="token-123"',
                        'export SIGNAL_DECK_TELEGRAM_CHAT_IDS="111,222"',
                    ]
                ),
                encoding="utf-8",
            )
            config = load_telegram_config(env_path, environ={})
            self.assertTrue(config["configured"])
            self.assertEqual(config["bot_token"], "token-123")
            self.assertEqual(config["chat_ids"], ["111", "222"])

    def test_telegram_dry_run_builds_notification_without_pii(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            outbox = Path(temp_dir) / "submissions.jsonl"
            env_path = Path(temp_dir) / "telegram.env"
            env_path.write_text(
                'export SIGNAL_DECK_TELEGRAM_BOT_TOKEN="token-123"\n'
                'export SIGNAL_DECK_TELEGRAM_CHAT_ID="111"\n',
                encoding="utf-8",
            )
            submissions = run_pipeline(self.profile, self.jobs, outbox, limit=1)
            result = notify_telegram_for_submissions(
                submissions,
                env_path=env_path,
                dry_run=True,
            )
            self.assertTrue(result["ok"])
            self.assertTrue(result["skipped"])
            self.assertIn("🚀 Job application drafts are ready", result["message"])
            self.assertNotIn(self.profile.email, result["message"])

    def test_telegram_alert_lists_top_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            outbox = Path(temp_dir) / "submissions.jsonl"
            submissions = run_pipeline(self.profile, self.jobs, outbox, limit=1)
            text = build_telegram_job_alert(submissions)
            self.assertIn("Candidates: 1", text)
            self.assertIn("🎯 score=", text)
            self.assertIn(str(submissions[0]["company"]), text)

    def test_shortens_linkedin_tracking_url(self) -> None:
        shortened = shorten_apply_url(
            "https://www.linkedin.com/jobs/view/4415090263/?eBP=abc&trk=search&trackingId=xyz"
        )
        self.assertEqual(shortened, "https://www.linkedin.com/jobs/view/4415090263/")
        slug_shortened = shorten_apply_url(
            "https://www.linkedin.com/jobs/view/site-reliability-engineer-at-clay-4338540053?position=1&pageNum=0"
        )
        self.assertEqual(slug_shortened, "https://www.linkedin.com/jobs/view/4338540053/")

    def test_telegram_alert_uses_short_apply_url(self) -> None:
        submission = {
            "company": "Example",
            "title": "SRE",
            "score": 100,
            "apply_url": "https://www.linkedin.com/jobs/view/4415090263/?eBP=abc&trk=search",
            "automation": {"mode": "supervised_review"},
            "safety": {"human_review_required_before_real_submit": True},
        }
        text = build_telegram_job_alert([submission])
        self.assertIn("https://www.linkedin.com/jobs/view/4415090263/", text)
        self.assertNotIn("eBP=abc", text)

    def test_telegram_alert_skips_closed_jobs(self) -> None:
        open_submission = {
            "company": "Open",
            "title": "SRE",
            "score": 100,
            "apply_url": "https://www.linkedin.com/jobs/view/1/",
            "automation": {"mode": "supervised_review"},
            "safety": {"human_review_required_before_real_submit": True},
        }
        closed_submission = {
            "company": "Closed",
            "title": "SRE",
            "score": 100,
            "apply_url": "https://www.linkedin.com/jobs/view/2/",
            "page_excerpt": ["No longer accepting applications"],
        }
        text = build_telegram_job_alert([closed_submission, open_submission])
        self.assertIn("Candidates: 1", text)
        self.assertIn("Skipped closed postings: 1", text)
        self.assertIn("Open - SRE", text)
        self.assertNotIn("Closed - SRE", text)

    def test_telegram_alert_skips_closed_registry_jobs(self) -> None:
        submissions = [
            {
                "platform": "LinkedIn",
                "job_id": "4415508499",
                "company": "Tesla",
                "title": "SRE",
                "score": 100,
                "apply_url": "https://www.linkedin.com/jobs/view/4415508499/",
            },
            {
                "platform": "LinkedIn",
                "job_id": "1",
                "company": "Open",
                "title": "SRE",
                "score": 100,
                "apply_url": "https://www.linkedin.com/jobs/view/1/",
            },
        ]
        closed_jobs = {
            "version": 1,
            "jobs": [
                {
                    "key": "linkedin:4415508499",
                    "status": "CLOSED",
                    "reason": "No longer accepting applications",
                }
            ],
        }
        text = build_telegram_job_alert(submissions, closed_jobs=closed_jobs)
        self.assertIn("Candidates: 1", text)
        self.assertNotIn("Tesla - SRE", text)
        self.assertIn("Open - SRE", text)

    def test_open_browser_uses_short_urls_and_limit(self) -> None:
        submissions = [
            {
                "apply_url": "https://www.linkedin.com/jobs/view/1/?trk=search",
                "job_id": "1",
            },
            {
                "apply_url": "https://jobs.ashbyhq.com/company/abc?src=LinkedIn",
            },
        ]
        opened: list[str] = []
        result = open_apply_urls_in_browser(submissions, max_items=1, opener=opened.append)
        self.assertEqual(result, ["https://www.linkedin.com/jobs/view/1/"])
        self.assertEqual(opened, ["https://www.linkedin.com/jobs/view/1/"])

    def test_open_browser_records_review_queue(self) -> None:
        submissions = [
            {
                "submission_id": "sub-1",
                "platform": "LinkedIn",
                "job_id": "1",
                "company": "Example",
                "title": "SRE",
                "score": 100,
                "apply_url": "https://www.linkedin.com/jobs/view/1/?trk=search",
                "automation": {"mode": "supervised_review"},
                "applicant": {"email": self.profile.email, "phone": self.profile.phone},
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            review_log = Path(temp_dir) / "browser_review_queue.jsonl"
            opened: list[str] = []
            result = open_apply_urls_in_browser(
                submissions,
                max_items=5,
                opener=opened.append,
                record_path=review_log,
                source="test_open",
            )
            self.assertEqual(result, ["https://www.linkedin.com/jobs/view/1/"])
            row = json.loads(review_log.read_text(encoding="utf-8"))
            self.assertEqual(row["status"], "OPENED_FOR_REVIEW")
            self.assertEqual(row["source"], "test_open")
            self.assertEqual(row["company"], "Example")
            self.assertEqual(row["short_apply_url"], "https://www.linkedin.com/jobs/view/1/")
            self.assertNotIn("applicant", row)
            recorded_text = review_log.read_text(encoding="utf-8")
            self.assertNotIn(self.profile.email, recorded_text)
            self.assertNotIn("trk=search", recorded_text)

    def test_browser_review_queue_audit_blocks_sensitive_review_records(self) -> None:
        safe_record = build_browser_review_record(
            {
                "submission_id": "sub-1",
                "platform": "LinkedIn",
                "job_id": "1",
                "company": "Example",
                "title": "SRE",
                "score": 100,
                "automation": {"mode": "supervised_review"},
                "missing_facts": [],
            },
            "https://www.linkedin.com/jobs/view/1/",
        )
        unsafe_record = {
            **safe_record,
            "applicant": {"email": "person@example.com"},
            "answer": "I can start immediately.",
            "short_apply_url": "https://www.linkedin.com/jobs/view/2/?trk=feed&utm_source=x",
            "real_platform_submission": True,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            review_log = Path(temp_dir) / "browser_review_queue.jsonl"
            review_log.write_text(
                json.dumps(safe_record) + "\n" + json.dumps(unsafe_record) + "\n",
                encoding="utf-8",
            )
            audit = build_browser_review_queue_audit(review_log)
            markdown = render_browser_review_queue_audit_markdown(audit)

            self.assertFalse(audit["safe"])
            self.assertEqual(audit["row_count"], 2)
            self.assertGreaterEqual(audit["disallowed_field_count"], 2)
            self.assertGreaterEqual(audit["sensitive_field_count"], 2)
            self.assertGreaterEqual(audit["sensitive_value_count"], 1)
            self.assertGreaterEqual(audit["tracking_url_count"], 1)
            self.assertEqual(audit["real_platform_submission_true_count"], 1)
            self.assertIn("Browser Review Queue Audit", markdown)
            self.assertIn("tracking query keys", markdown)

            json_output = Path(temp_dir) / "audit.json"
            markdown_output = Path(temp_dir) / "audit.md"
            written = write_browser_review_queue_audit(review_log, json_output, markdown_output)
            self.assertFalse(written["safe"])
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())

    def test_browser_review_queue_audit_accepts_sparse_review_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            review_log = Path(temp_dir) / "browser_review_queue.jsonl"
            safe_record = build_browser_review_record(
                {
                    "submission_id": "sub-1",
                    "platform": "LinkedIn",
                    "job_id": "1",
                    "company": "Example",
                    "title": "SRE",
                    "score": 100,
                    "automation": {"mode": "supervised_review"},
                    "missing_facts": [],
                },
                "https://www.linkedin.com/jobs/view/1/",
            )
            review_log.write_text(json.dumps(safe_record) + "\n", encoding="utf-8")
            audit = build_browser_review_queue_audit(review_log)
            self.assertTrue(audit["safe"])
            self.assertEqual(audit["row_count"], 1)
            self.assertEqual(audit["disallowed_field_count"], 0)
            self.assertEqual(audit["sensitive_field_count"], 0)
            self.assertEqual(audit["tracking_url_count"], 0)

    def test_submission_safety_audit_accepts_local_fake_rehearsal_evidence(self) -> None:
        fake_rehearsal = {
            "source": "fake_position_rehearsal",
            "run_count": 1589,
            "real_platform_submission": False,
            "local_synthetic_submit_allowed": True,
            "actual_submit_count": 1589,
            "eligible_submit_count": 1589,
            "selector_miss_count": 0,
            "policy": {
                "real_platform_submission": False,
                "fake_data_real_submission_allowed": False,
                "remote_employer_final_submit_blocked": True,
            },
        }
        post_answer = {
            "status": "synthetic_queue_rehearsal_ready",
            "synthetic_final_answers": True,
            "apply_requested": False,
            "live_check_requested": False,
            "open_browser_requested": False,
            "policy": {
                "submits_real_applications": False,
                "synthetic_answers_never_written_to_real_profile_or_memory": True,
            },
            "synthetic_queue_rehearsal": {
                "writes_real_profile_or_memory": False,
                "submits_real_applications": False,
                "opens_browser": False,
                "runs_live_check": False,
                "autofill_packet_selected": 100,
                "autofill_packet_final_submit_stops": 100,
                "autofill_packet_selector_misses": 0,
            },
        }
        packet = {
            "status": "waiting_for_confirmed_answers",
            "selected_count": 100,
            "target_count": 100,
            "real_platform_submission": False,
            "ready_for_unattended_real_submit": False,
            "summary": {
                "selected_count": 100,
                "final_submit_stop_count": 100,
                "selector_miss_count": 0,
                "local_synthetic_submit_count": 100,
            },
            "positions": [
                {
                    "real_platform_submission": False,
                    "final_submit_allowed": False,
                    "would_submit": False,
                    "stop_actions": [{"category": "final_submit", "status": "final_submit_confirmation"}],
                }
            ],
        }
        browser_audit = {
            "safe": True,
            "row_count": 49,
            "real_platform_submission_true_count": 0,
            "parse_error_count": 0,
        }
        pre_submit = {
            "generated_at": "2026-05-23T01:58:08+00:00",
            "real_platform_submission": False,
            "final_submit_allowed": False,
            "would_submit": False,
            "actual_submit_count": 0,
        }
        goal_audit = {
            "status": "needs_user_answers",
            "blocker_summary": {
                "final_answer_waiting_count_after_drafts": 6,
                "final_answer_waiting_high_risk_count_after_drafts": 5,
            },
        }

        audit = build_submission_safety_audit(
            fake_position_rehearsal=fake_rehearsal,
            post_answer_pipeline=post_answer,
            apply_queue_autofill_packet=packet,
            browser_review_queue_audit=browser_audit,
            pre_submit_review=pre_submit,
            goal_readiness_audit=goal_audit,
        )
        markdown = render_submission_safety_audit_markdown(audit)

        self.assertTrue(audit["safe"])
        self.assertEqual(audit["issue_count"], 0)
        self.assertEqual(audit["summary"]["fake_position_local_synthetic_submit_count"], 1589)
        self.assertEqual(audit["summary"]["apply_packet_final_submit_stop_count"], 100)
        self.assertIn("goal_needs_user_answers", [row["id"] for row in audit["warnings"]])
        self.assertIn("Submission Safety Audit", markdown)
        self.assertIn("fake data local only", markdown)
        self.assertIn("real employer final submit", markdown)

        with tempfile.TemporaryDirectory() as temp_dir:
            json_output = Path(temp_dir) / "submission_safety.json"
            markdown_output = Path(temp_dir) / "submission_safety.md"
            written = write_submission_safety_audit(
                json_output,
                markdown_output,
                fake_position_rehearsal=fake_rehearsal,
                post_answer_pipeline=post_answer,
                apply_queue_autofill_packet=packet,
                browser_review_queue_audit=browser_audit,
                pre_submit_review=pre_submit,
                goal_readiness_audit=goal_audit,
            )
            self.assertTrue(written["safe"])
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())

    def test_submission_safety_audit_blocks_unattended_real_submit_path(self) -> None:
        audit = build_submission_safety_audit(
            fake_position_rehearsal={
                "real_platform_submission": False,
                "policy": {"real_platform_submission": False, "fake_data_real_submission_allowed": False},
            },
            post_answer_pipeline={
                "synthetic_final_answers": True,
                "apply_requested": False,
                "live_check_requested": False,
                "open_browser_requested": False,
                "policy": {
                    "submits_real_applications": False,
                    "synthetic_answers_never_written_to_real_profile_or_memory": True,
                },
                "synthetic_queue_rehearsal": {
                    "writes_real_profile_or_memory": False,
                    "submits_real_applications": False,
                    "opens_browser": False,
                    "runs_live_check": False,
                },
            },
            apply_queue_autofill_packet={
                "selected_count": 1,
                "real_platform_submission": False,
                "ready_for_unattended_real_submit": True,
                "summary": {"final_submit_stop_count": 0},
                "positions": [{"would_submit": True, "final_submit_allowed": True}],
            },
            browser_review_queue_audit={
                "safe": True,
                "real_platform_submission_true_count": 0,
            },
        )

        self.assertFalse(audit["safe"])
        self.assertGreaterEqual(audit["issue_count"], 1)
        self.assertIn("apply_queue_no_unattended_real_submit", [row["id"] for row in audit["issues"]])
        self.assertIn("apply_queue_final_submit_stop_coverage", [row["id"] for row in audit["issues"]])

    def test_open_browser_skips_closed_jobs(self) -> None:
        submissions = [
            {
                "company": "Closed",
                "apply_url": "https://www.linkedin.com/jobs/view/1/",
                "page_excerpt": ["No longer accepting applications"],
            },
            {
                "company": "Open",
                "apply_url": "https://www.linkedin.com/jobs/view/2/?trk=search",
            },
        ]
        opened: list[str] = []
        result = open_apply_urls_in_browser(submissions, max_items=5, opener=opened.append)
        self.assertEqual(result, ["https://www.linkedin.com/jobs/view/2/"])
        self.assertEqual(opened, ["https://www.linkedin.com/jobs/view/2/"])

    def test_open_browser_skips_closed_registry_jobs_and_fills_limit(self) -> None:
        submissions = [
            {
                "platform": "LinkedIn",
                "job_id": "1",
                "apply_url": "https://www.linkedin.com/jobs/view/1/",
            },
            {
                "platform": "LinkedIn",
                "job_id": "2",
                "apply_url": "https://www.linkedin.com/jobs/view/2/",
            },
            {
                "platform": "LinkedIn",
                "job_id": "3",
                "apply_url": "https://www.linkedin.com/jobs/view/3/",
            },
        ]
        closed_jobs = {
            "version": 1,
            "jobs": [{"key": "linkedin:2", "status": "CLOSED", "reason": "closed"}],
        }
        opened: list[str] = []
        result = open_apply_urls_in_browser(
            submissions,
            max_items=2,
            opener=opened.append,
            closed_jobs=closed_jobs,
        )
        self.assertEqual(
            result,
            [
                "https://www.linkedin.com/jobs/view/1/",
                "https://www.linkedin.com/jobs/view/3/",
            ],
        )

    def test_live_check_records_closed_pages(self) -> None:
        submissions = [
            {
                "platform": "LinkedIn",
                "job_id": "1",
                "company": "ClosedCo",
                "title": "SRE",
                "apply_url": "https://www.linkedin.com/jobs/view/1/?trk=search",
            },
            {
                "platform": "LinkedIn",
                "job_id": "2",
                "company": "OpenCo",
                "title": "SRE",
                "apply_url": "https://www.linkedin.com/jobs/view/2/",
            },
        ]

        def fake_fetcher(url: str, timeout: float) -> str:
            if url.endswith("/1/"):
                return "<figcaption>No longer accepting applications</figcaption>"
            return "<html>Apply now</html>"

        with tempfile.TemporaryDirectory() as temp_dir:
            closed_path = Path(temp_dir) / "closed_jobs.json"
            result = refresh_closed_jobs_from_live_pages(
                submissions,
                closed_path,
                fetcher=fake_fetcher,
            )
            self.assertEqual(len(result["checks"]), 2)
            self.assertTrue(result["checks"][0]["closed"])
            self.assertFalse(result["checks"][1]["closed"])
            closed_jobs = load_closed_jobs(closed_path)
            self.assertTrue(is_job_closed(submissions[0], closed_jobs))
            self.assertFalse(is_job_closed(submissions[1], closed_jobs))

    def test_live_check_errors_do_not_close_job(self) -> None:
        submissions = [
            {
                "platform": "LinkedIn",
                "job_id": "1",
                "company": "Example",
                "title": "SRE",
                "apply_url": "https://www.linkedin.com/jobs/view/1/",
            }
        ]

        def failing_fetcher(url: str, timeout: float) -> str:
            raise TimeoutError("timed out")

        with tempfile.TemporaryDirectory() as temp_dir:
            closed_path = Path(temp_dir) / "closed_jobs.json"
            result = refresh_closed_jobs_from_live_pages(
                submissions,
                closed_path,
                fetcher=failing_fetcher,
            )
            self.assertEqual(result["checks"][0]["error"], "timed out")
            self.assertEqual(result["checks"][0]["attempt_count"], 2)
            self.assertEqual(result["checks"][0]["fetch_errors"], ["timed out", "timed out"])
            self.assertFalse(is_job_closed(submissions[0], result["closed_jobs"]))

    def test_live_check_retries_transient_errors_before_notifying(self) -> None:
        submissions = [
            {
                "platform": "LinkedIn",
                "job_id": "1",
                "company": "RetryCo",
                "title": "SRE",
                "apply_url": "https://www.linkedin.com/jobs/view/1/",
            }
        ]
        calls = {"count": 0}

        def flaky_fetcher(url: str, timeout: float) -> str:
            calls["count"] += 1
            if calls["count"] == 1:
                raise TimeoutError("temporary timeout")
            return "<html>Apply now</html>"

        with tempfile.TemporaryDirectory() as temp_dir:
            closed_path = Path(temp_dir) / "closed_jobs.json"
            result = refresh_closed_jobs_from_live_pages(
                submissions,
                closed_path,
                fetcher=flaky_fetcher,
            )
            self.assertEqual(calls["count"], 2)
            self.assertFalse(result["checks"][0]["closed"])
            self.assertNotIn("error", result["checks"][0])
            self.assertEqual(result["checks"][0]["attempt_count"], 2)
            self.assertEqual(result["checks"][0]["fetch_errors"], ["temporary timeout"])

    def test_live_check_404_records_closed_job(self) -> None:
        submissions = [
            {
                "platform": "Lever",
                "company": "Example",
                "title": "SRE",
                "apply_url": "https://jobs.lever.co/example/closed",
            }
        ]

        def not_found_fetcher(url: str, timeout: float) -> str:
            raise urllib.error.HTTPError(url, 404, "Not Found", hdrs=None, fp=None)

        with tempfile.TemporaryDirectory() as temp_dir:
            closed_path = Path(temp_dir) / "closed_jobs.json"
            result = refresh_closed_jobs_from_live_pages(
                submissions,
                closed_path,
                fetcher=not_found_fetcher,
            )

            self.assertTrue(result["checks"][0]["closed"])
            self.assertIn("HTTP 404", result["checks"][0]["reason"])
            self.assertTrue(is_job_closed(submissions[0], result["closed_jobs"]))

    def test_closed_application_phrase_handles_common_ats_variants(self) -> None:
        self.assertEqual(
            closed_application_phrase(
                {"page_text": "Applications for this job are no longer being accepted."}
            ),
            "applications for this job are no longer being accepted",
        )
        self.assertEqual(
            closed_application_phrase({"page_text": "This job posting has expired."}),
            "this job posting has expired",
        )
        self.assertEqual(
            closed_application_phrase({"page_text": "This position is no longer available."}),
            "this position is no longer available",
        )
        self.assertEqual(
            closed_application_phrase(
                {"rendered_text": "We're sorry, this role is no longer open."}
            ),
            "this role is no longer open",
        )
        self.assertEqual(
            closed_application_phrase(
                {"visible_text": "We are no longer accepting candidates for this job."}
            ),
            "no longer accepting candidates",
        )
        self.assertEqual(
            closed_application_phrase({"page_text": "This job posting is closed."}),
            "job posting is closed",
        )
        self.assertEqual(
            closed_application_phrase({"page_text": "Sorry, this requisition has been closed."}),
            "this requisition has been closed",
        )
        self.assertEqual(
            closed_application_phrase({"page_text": "This opening has been removed by the employer."}),
            "this opening has been removed",
        )
        self.assertEqual(
            closed_application_phrase({"page_text": "This posting has been archived."}),
            "this posting has been archived",
        )
        self.assertEqual(
            closed_application_phrase({"page_text": "The application deadline has passed."}),
            "application deadline has passed",
        )
        self.assertEqual(
            closed_application_phrase({"page_text": "This job is unavailable."}),
            "this job is unavailable",
        )
        self.assertEqual(
            closed_application_phrase({"page_text": "We are no longer taking applications."}),
            "no longer taking applications",
        )
        self.assertEqual(
            closed_application_phrase({"page_text": "This requisition has been canceled."}),
            "this requisition has been canceled",
        )
        self.assertIsNone(
            closed_application_phrase(
                {
                    "page_text": (
                        "The application window is expected to close on 06/12/2026. "
                        "Job posting may be removed earlier if the position is filled."
                    )
                }
            )
        )
        self.assertIsNone(
            closed_application_phrase(
                {
                    "page_text": (
                        "The application deadline is 06/12/2026, and we review applications "
                        "on a rolling basis."
                    )
                }
            )
        )

    def test_closed_preflight_reports_phrase_source_and_snippet(self) -> None:
        candidates = [
            {
                "company": "RenderedClosed",
                "title": "SRE",
                "apply_url": "https://www.linkedin.com/jobs/view/20/",
                "rendered_text": "Company\nSRE\nNo longer accepting new applications\nAbout the job",
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            closed_path = Path(temp_dir) / "closed_jobs.json"
            report = build_closed_posting_preflight(
                candidates,
                closed_path,
                max_checks=1,
            )
            self.assertEqual(report["status_counts"]["closed_embedded_text"], 1)
            check = report["checks"][0]
            self.assertEqual(check["closed_phrase"], "no longer accepting new applications")
            self.assertEqual(check["closed_source_field"], "rendered_text")
            self.assertIn("No longer accepting new applications", check["closed_snippet"])

    def test_closed_posting_preflight_splits_open_closed_and_uncertain(self) -> None:
        candidates = [
            {
                "platform": "LinkedIn",
                "job_id": "10",
                "company": "RegistryClosed",
                "title": "SRE",
                "apply_url": "https://www.linkedin.com/jobs/view/10/?trk=search",
            },
            {
                "platform": "LinkedIn",
                "job_id": "11",
                "company": "LiveClosed",
                "title": "SRE",
                "apply_url": "https://www.linkedin.com/jobs/view/11/",
            },
            {
                "platform": "Greenhouse",
                "job_id": "12",
                "company": "OpenCo",
                "title": "Infrastructure Engineer",
                "apply_url": "https://job-boards.greenhouse.io/open/jobs/12?src=LinkedIn",
            },
            {
                "platform": "Ashby",
                "job_id": "13",
                "company": "ErrorCo",
                "title": "Production Engineer",
                "apply_url": "https://jobs.ashbyhq.com/error/13?src=LinkedIn",
            },
        ]

        def fake_fetcher(url: str, timeout: float) -> str:
            if url.endswith("/11/"):
                return "<html>This position is no longer available.</html>"
            if "/open/jobs/12" in url:
                return "<html>Apply now</html>"
            raise TimeoutError("timed out")

        with tempfile.TemporaryDirectory() as temp_dir:
            closed_path = Path(temp_dir) / "closed_jobs.json"
            record_closed_job(
                closed_path,
                candidates[0],
                reason="No longer accepting applications",
                source="test",
            )
            json_output = Path(temp_dir) / "closed_preflight.json"
            markdown_output = Path(temp_dir) / "closed_preflight.md"

            report = write_closed_posting_preflight(
                candidates,
                closed_path,
                json_output,
                markdown_output,
                fetcher=fake_fetcher,
                max_checks=3,
            )

            self.assertEqual(report["candidate_count"], 4)
            self.assertEqual(report["live_checked_count"], 3)
            self.assertEqual(report["closed_count"], 2)
            self.assertEqual(report["newly_closed_count"], 1)
            self.assertEqual(report["open_eligible_count"], 1)
            self.assertEqual(report["uncertain_count"], 1)
            self.assertEqual(report["status_counts"]["closed_registry"], 1)
            self.assertEqual(report["status_counts"]["closed_live_text"], 1)
            self.assertEqual(report["status_counts"]["open_live_checked"], 1)
            self.assertEqual(report["status_counts"]["check_error"], 1)
            self.assertEqual(report["retry_attempts"], 1)
            self.assertEqual(report["fetch_attempt_count"], 4)
            self.assertEqual(report["checks"][3]["attempt_count"], 2)
            self.assertTrue(is_job_closed(candidates[1], load_closed_jobs(closed_path)))
            self.assertEqual(report["open_candidates"][0]["company"], "OpenCo")
            self.assertTrue(json_output.exists())
            markdown = markdown_output.read_text(encoding="utf-8")
            self.assertIn("Closed Posting Preflight", markdown)
            self.assertIn("Retry attempts: 1", markdown)
            self.assertIn("OpenCo", markdown)
            self.assertIn("LiveClosed", markdown)
            self.assertIn("timed out", markdown)
            self.assertIn("closed_live_text", render_closed_posting_preflight_markdown(report))

    def test_closed_preflight_retries_transient_errors_before_marking_uncertain(self) -> None:
        candidates = [
            {
                "platform": "Lever",
                "job_id": "retry",
                "company": "RetryCo",
                "title": "Platform Engineer",
                "apply_url": "https://jobs.lever.co/retry/1",
            }
        ]
        calls = {"count": 0}

        def flaky_fetcher(url: str, timeout: float) -> str:
            calls["count"] += 1
            if calls["count"] == 1:
                raise TimeoutError("temporary timeout")
            return "<html>Apply now</html>"

        with tempfile.TemporaryDirectory() as temp_dir:
            closed_path = Path(temp_dir) / "closed_jobs.json"
            report = build_closed_posting_preflight(
                candidates,
                closed_path,
                fetcher=flaky_fetcher,
                max_checks=1,
            )
            self.assertEqual(calls["count"], 2)
            self.assertEqual(report["open_eligible_count"], 1)
            self.assertEqual(report["uncertain_count"], 0)
            self.assertEqual(report["checks"][0]["status"], "open_live_checked")
            self.assertEqual(report["checks"][0]["attempt_count"], 2)
            self.assertEqual(report["checks"][0]["fetch_errors"], ["temporary timeout"])

    def test_browser_review_record_has_next_action(self) -> None:
        record = build_browser_review_record(
            {"company": "Example", "title": "SRE"},
            "https://example.com/job",
        )
        self.assertEqual(record["next_action"], "human_review_then_apply_or_skip")
        self.assertFalse(record["real_platform_submission"])

    def test_classifies_application_prompts_by_automation_action(self) -> None:
        self.assertEqual(
            classify_application_prompt("Are you legally authorized to work in the US?")
            .automation_action,
            "auto_answer_from_memory",
        )
        self.assertEqual(
            classify_application_prompt("Gender").automation_action,
            "do_not_store_sensitive",
        )
        self.assertEqual(
            classify_application_prompt("", {"name": "g-recaptcha-response"}).category,
            "security_verification",
        )
        self.assertEqual(
            classify_application_prompt("Cover Letter").automation_action,
            "generate_custom_material",
        )
        self.assertEqual(
            classify_application_prompt(
                "Outline your practical Python software engineering experience"
            ).automation_action,
            "generate_custom_material",
        )
        self.assertEqual(
            classify_application_prompt("Please indicate your nationality").automation_action,
            "do_not_store_sensitive",
        )
        self.assertEqual(
            classify_application_prompt("Most Recent Employer").automation_action,
            "auto_fill_from_profile",
        )
        self.assertEqual(
            classify_application_prompt("What state will you work remotely from?").category,
            "profile_identity",
        )
        self.assertEqual(
            classify_application_prompt("What company and position are you currently in?").category,
            "employment_history",
        )
        self.assertEqual(
            classify_application_prompt(
                "Describe your knowledge of low-level Linux container and security primitives such as cgroups, namespaces, LSMs, and SECCOMP"
            ).category,
            "role_specific_free_text",
        )
        self.assertEqual(
            classify_application_prompt("Where are you presently located?").category,
            "profile_identity",
        )
        self.assertEqual(
            classify_application_prompt(
                "Which programming languages do you feel most confident using (Choose up to three)?"
            ).category,
            "skills_experience",
        )
        self.assertEqual(
            classify_application_prompt("Are you a fluent Japanese speaker?").category,
            "language_ability",
        )
        self.assertEqual(
            classify_application_prompt("Which language(s) can you speak and write professionally?").category,
            "language_ability",
        )
        self.assertEqual(
            classify_application_prompt("Are you within commuting distance of Riyadh, Saudi Arabia?").category,
            "location_constraint",
        )
        self.assertEqual(
            classify_application_prompt(
                "If you are in a commutable distance from our Cork office, are you able to work a hybrid schedule?"
            ).category,
            "location_constraint",
        )
        self.assertEqual(
            classify_application_prompt("Resume").category,
            "resume_upload",
        )
        self.assertEqual(
            classify_application_prompt("Submit application").category,
            "final_submit",
        )
        self.assertEqual(
            classify_application_prompt("Name").category,
            "profile_identity",
        )
        self.assertEqual(
            classify_application_prompt("Zip Code").category,
            "profile_identity",
        )
        self.assertEqual(
            classify_application_prompt("Current or last company you worked for").category,
            "employment_history",
        )
        self.assertEqual(
            classify_application_prompt("X Profile").category,
            "profile_link",
        )
        self.assertEqual(
            classify_application_prompt("What exceptional work have you done?").category,
            "role_specific_free_text",
        )
        self.assertEqual(
            classify_application_prompt(
                "By selecting Yes, I am consenting to the use of AI for evaluating my candidacy."
            ).category,
            "policy_acknowledgement",
        )
        self.assertEqual(
            classify_application_prompt(
                "Please indicate your understanding and agreement with this approach by selecting Yes below."
            ).category,
            "policy_acknowledgement",
        )
        self.assertEqual(
            classify_application_prompt("Future Contact Consent").category,
            "communication_consent",
        )
        self.assertEqual(
            classify_application_prompt(
                "Our HQ is in San Mateo and this role is not remote. Are you able to come onsite as required for this role?"
            ).category,
            "location_constraint",
        )
        self.assertEqual(
            classify_application_prompt("Have you worked with us before?").category,
            "employment_history",
        )
        self.assertEqual(
            classify_application_prompt("Are you at least 18 years of age?").category,
            "legal_age",
        )
        self.assertEqual(
            classify_application_prompt("Currency").category,
            "compensation_currency",
        )
        self.assertEqual(
            classify_application_prompt("Did AI complete this application?").category,
            "ai_application_disclosure",
        )
        self.assertEqual(
            classify_application_prompt("Did AI complete or submit this application?").category,
            "ai_application_disclosure",
        )
        self.assertNotEqual(
            classify_application_prompt(
                "Do you have experience working in an AI Assisted Development Environment?"
            ).category,
            "ai_application_disclosure",
        )
        self.assertEqual(
            classify_application_prompt("How many weeks after accepting an offer could you start?").category,
            "availability",
        )
        self.assertEqual(
            classify_application_prompt("How did you hear about this job?").category,
            "referral_source",
        )
        self.assertEqual(
            classify_application_prompt("If you were referred by someone at Later, please let us know!").category,
            "referral_contact",
        )
        self.assertEqual(
            classify_application_prompt("If someone at SEON referred you, who should we thank?").category,
            "referral_contact",
        )
        self.assertEqual(
            classify_application_prompt("Where are you currently based?").category,
            "profile_identity",
        )
        self.assertEqual(
            classify_application_prompt("Title").category,
            "employment_history",
        )
        self.assertEqual(
            classify_application_prompt("How remote-friendly are you?").category,
            "remote_preference",
        )
        self.assertEqual(
            classify_application_prompt("How would you evaluate your English Level?").category,
            "language_ability",
        )
        self.assertEqual(
            classify_application_prompt("Google Scholar").category,
            "profile_link",
        )
        self.assertEqual(
            classify_application_prompt("Optional: link to a blog post or other public writing; leave blank if none.").category,
            "profile_link",
        )
        self.assertEqual(
            classify_application_prompt("Are you comfortable using your own computer running Ubuntu?").category,
            "device_policy",
        )
        self.assertEqual(
            classify_application_prompt("Are you Eligible to work in the US for any employer ?").category,
            "work_authorization",
        )
        self.assertEqual(
            classify_application_prompt("CV/Resume (please submit your file in English)").category,
            "resume_upload",
        )
        self.assertEqual(
            classify_application_prompt("Mobile Number").category,
            "profile_identity",
        )
        self.assertEqual(
            classify_application_prompt("Terms & Conditions").category,
            "policy_acknowledgement",
        )
        self.assertEqual(
            classify_application_prompt("Which companies do you think are innovating best in web design?").category,
            "role_specific_free_text",
        )
        self.assertEqual(
            classify_application_prompt(
                "What is your favorite AI Agentic technology for IaC authoring?"
            ).automation_action,
            "generate_custom_material",
        )
        self.assertEqual(
            classify_application_prompt("Are you a U.S. Citizen?").category,
            "citizenship_status",
        )
        self.assertEqual(
            classify_application_prompt("Do you currently hold an active security clearance?").category,
            "security_clearance",
        )
        self.assertEqual(
            classify_application_prompt(
                "This role does not require active security clearance at the time of hiring, but candidates must be eligible and willing to obtain company-sponsored security clearance after starting. Are you willing and able to meet this requirement?"
            ).category,
            "security_clearance",
        )
        self.assertEqual(
            classify_application_prompt("What is the Sponsoring Agency of your Security Clearnance").category,
            "security_clearance",
        )
        self.assertEqual(
            classify_application_prompt("Do you know anyone currently at Glean?").category,
            "conflict_of_interest",
        )
        self.assertEqual(
            classify_application_prompt("May we record and analyze your interview?").category,
            "interview_recording_consent",
        )
        self.assertEqual(
            classify_application_prompt("Where did you find this job posting?").category,
            "referral_source",
        )
        self.assertEqual(
            classify_application_prompt("What age range do you fall within?").automation_action,
            "do_not_store_sensitive",
        )
        self.assertEqual(
            classify_application_prompt("Gênero - Qual gênero você se identifica?").automation_action,
            "do_not_store_sensitive",
        )
        self.assertEqual(
            classify_application_prompt("Tenho uma deficiência auditiva").automation_action,
            "do_not_store_sensitive",
        )
        self.assertEqual(
            classify_application_prompt("Amarela").automation_action,
            "do_not_store_sensitive",
        )
        self.assertEqual(
            classify_application_prompt("Black or African American").automation_action,
            "do_not_store_sensitive",
        )
        self.assertEqual(
            classify_application_prompt("Female").automation_action,
            "do_not_store_sensitive",
        )
        self.assertEqual(
            classify_application_prompt("Middle Eastern or North African").automation_action,
            "do_not_store_sensitive",
        )
        self.assertEqual(
            classify_application_prompt("White / Caucasian").automation_action,
            "do_not_store_sensitive",
        )
        self.assertEqual(
            classify_application_prompt("Non-binary").automation_action,
            "do_not_store_sensitive",
        )
        self.assertEqual(
            classify_application_prompt("Do you identify as an Indigenous person?").category,
            "eeoc_sensitive",
        )
        self.assertEqual(
            classify_application_prompt("Indigenous person").automation_action,
            "do_not_store_sensitive",
        )
        self.assertEqual(
            classify_application_prompt("Do you speak English fluently?").category,
            "language_ability",
        )
        self.assertEqual(
            classify_application_prompt("💰 Combien tu vas gagner chez SFEIR ?").category,
            "compensation",
        )
        self.assertEqual(
            classify_application_prompt("Are you willing to undergo a background check?").category,
            "background_or_export_control",
        )
        self.assertEqual(
            classify_application_prompt(
                "Are you open to significant travel (80-100%) to Toulouse, France?"
            ).category,
            "location_constraint",
        )
        self.assertEqual(
            classify_application_prompt("Yes, I can legally work and live in the UAE").category,
            "country_work_permit",
        )
        self.assertEqual(
            classify_application_prompt("When do you graduate?").category,
            "education_date",
        )
        self.assertEqual(
            classify_application_prompt("What is your GPA?").category,
            "education_grading",
        )
        self.assertEqual(
            classify_application_prompt(
                "A data scientist proposes a complex ensemble model. What is the most appropriate response?"
            ).category,
            "assessment_question",
        )
        self.assertEqual(
            classify_application_prompt(
                "A data scientist proposes a complex ensemble model. What is the most appropriate response?"
            ).automation_action,
            "generate_custom_material",
        )
        self.assertEqual(
            classify_application_prompt("Do you have blockchain/crypto experience?").category,
            "domain_experience",
        )
        self.assertEqual(
            classify_application_prompt(
                "Are you currently or were you previously a U.S. Government civilian or military employee?"
            ).category,
            "government_employment",
        )
        self.assertEqual(
            classify_application_prompt("Work Eligibility Status").category,
            "work_authorization",
        )
        self.assertEqual(
            classify_application_prompt("Do you have 8+ years expertise in C#?").category,
            "experience_years",
        )
        self.assertEqual(
            classify_application_prompt(
                "If successful, how soon are you able to commence in this role with Envoy Global?"
            ).category,
            "availability",
        )
        self.assertEqual(
            classify_application_prompt("What is your earliest possible starting date?").category,
            "availability",
        )
        self.assertEqual(
            classify_application_prompt("Stack Overflow Jobs").category,
            "referral_source",
        )
        self.assertEqual(
            classify_application_prompt("Middle Name").category,
            "profile_identity",
        )
        self.assertEqual(
            classify_application_prompt("Candidate Personal Data Disclosure").category,
            "policy_acknowledgement",
        )
        self.assertEqual(
            classify_application_prompt(
                "Have you ever been charged or convicted of a misdemeanor or felony?"
            ).category,
            "background_or_export_control",
        )
        self.assertEqual(
            classify_application_prompt(
                "Do you have any contractual obligations, agreements, relationships, or commitments to another person or entity that would impact, impede or interfere with your ability to join Axon?"
            ).category,
            "conflict_of_interest",
        )
        self.assertEqual(
            classify_application_prompt(
                "EXPORT CONTROLS - This position requires access to information and technology that is subject to U.S. export controls."
            ).category,
            "background_or_export_control",
        )
        self.assertEqual(
            classify_application_prompt(
                "Government Employment: In the last 5 years, have you been an employee of a U.S. federal, state, or local government?"
            ).category,
            "government_employment",
        )
        self.assertEqual(
            classify_application_prompt(
                "Please indicate which ethnic group(s) you identify with. Please select all that apply."
            ).automation_action,
            "do_not_store_sensitive",
        )
        self.assertEqual(
            classify_application_prompt(
                "As a requirement of the role you will be required to attend in-person meetings at our clients' worksites."
            ).category,
            "location_constraint",
        )
        self.assertEqual(
            classify_application_prompt("Are you able to meet a fully vaccinated against COVID-19 requirement?").category,
            "health_requirement",
        )
        self.assertEqual(
            classify_application_prompt("What design patterns have you implemented in a production service?").category,
            "skills_experience",
        )
        self.assertEqual(
            classify_application_prompt("What is your overall experience/proficiency with Python?").category,
            "skills_experience",
        )
        self.assertEqual(
            classify_application_prompt("Do you have experience against nation state level adversaries?").category,
            "domain_experience",
        )
        self.assertEqual(
            classify_application_prompt("When building a customer-facing feature, how do you typically approach it?").category,
            "role_specific_free_text",
        )
        self.assertEqual(
            classify_application_prompt("Which of the following most influenced your decision to apply?").category,
            "role_specific_free_text",
        )
        self.assertEqual(
            classify_application_prompt("X (Twitter) account").category,
            "profile_link",
        )
        self.assertEqual(
            classify_application_prompt("Are you legally entitled to work in Australia?").category,
            "country_work_permit",
        )
        self.assertEqual(
            classify_application_prompt("When would you like to hear back from us regarding potential opportunities?").category,
            "availability",
        )

    def test_application_research_summarizes_form_snapshots_and_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            outbox = Path(temp_dir)
            (outbox / "greenhouse_form_snapshot.json").write_text(
                json.dumps(
                    {
                        "title": "Example Application",
                        "url": "https://job-boards.greenhouse.io/example/jobs/1",
                        "fields": [
                            {"label": "First Name*", "required": True, "tag": "INPUT"},
                            {
                                "label": "Are you legally authorized to work in the United States?*",
                                "required": True,
                                "tag": "INPUT",
                            },
                            {
                                "label": "Will you now require immigration sponsorship?",
                                "required": True,
                                "tag": "INPUT",
                            },
                            {"label": "Gender", "required": False, "tag": "INPUT"},
                            {"label": "", "name": "g-recaptcha-response", "tag": "TEXTAREA"},
                        ],
                        "buttons": [{"text": "Submit application", "tag": "BUTTON"}],
                    }
                ),
                encoding="utf-8",
            )
            (outbox / "submissions.jsonl").write_text(
                json.dumps(
                    {
                        "platform": "LinkedIn",
                        "job_id": "123",
                        "company": "Example",
                        "title": "SRE",
                        "apply_url": "https://www.linkedin.com/jobs/view/123/",
                        "answers": {
                            "What is your expected compensation range?": "$100,000+",
                            "Why are you interested in this role?": "Because...",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            research = build_application_research(outbox, position_target=100)

            self.assertEqual(research["positions_observed_total"], 2)
            self.assertEqual(research["platforms"]["Greenhouse"]["positions_observed"], 1)
            self.assertEqual(research["platforms"]["LinkedIn"]["positions_observed"], 1)
            self.assertIn("LinkedIn::Site Reliability", research["coverage_groups"])
            self.assertGreaterEqual(research["category_counts"]["work_authorization"], 1)
            self.assertGreaterEqual(research["category_counts"]["sponsorship"], 1)
            self.assertGreaterEqual(research["category_counts"]["eeoc_sensitive"], 1)
            self.assertGreaterEqual(research["category_counts"]["security_verification"], 1)
            self.assertGreaterEqual(
                research["automation_action_counts"]["auto_answer_from_memory"], 2
            )
            self.assertGreaterEqual(
                research["automation_action_counts"]["do_not_store_sensitive"], 1
            )
            markdown = render_application_research_markdown(research)
            self.assertIn("Application Research Baseline", markdown)
            self.assertIn("Greenhouse", markdown)

    def test_write_application_research_report_outputs_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            outbox = Path(temp_dir) / "outbox"
            outbox.mkdir()
            (outbox / "browser_review_queue.jsonl").write_text(
                json.dumps(
                    {
                        "status": "OPENED_FOR_REVIEW",
                        "platform": "LinkedIn",
                        "job_id": "1",
                        "company": "Example",
                        "title": "SRE",
                        "short_apply_url": "https://www.linkedin.com/jobs/view/1/",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            json_output = Path(temp_dir) / "research.json"
            markdown_output = Path(temp_dir) / "research.md"

            research = write_application_research_report(
                outbox,
                json_output,
                markdown_output,
                position_target=100,
            )

            self.assertEqual(research["positions_observed_total"], 1)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertIn("Application Research Baseline", markdown_output.read_text())

    def test_answer_gap_report_tracks_covered_and_blocking_prompts(self) -> None:
        profile = CandidateProfile(
            name="Alan Jiang",
            email="alan@example.com",
            phone="555-0100",
            location="Bellevue, WA",
            target_titles=["Site Reliability Engineer"],
            target_locations=["United States"],
            remote_ok=True,
            keywords=["sre"],
            blocklist=[],
            min_score=1,
            resume_facts={
                "professional_summary": "SRE and automation engineer",
                "strongest_skills": "Python, reliability, and automation",
                "impact_example": "Reduced incident mitigation time.",
                "education": "MS Computer Science",
            },
            question_answers={"authorization": "Yes"},
        )
        research = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "positions_observed_total": 1,
            "items": [
                {
                    "label": "Are you authorized to work in the United States?",
                    "normalized_label": "authorized work united states",
                    "category": "work_authorization",
                    "automation_action": "auto_answer_from_memory",
                    "sensitivity": "standard_preference",
                    "required": True,
                    "platform": "LinkedIn",
                    "source_file": "submissions.jsonl",
                },
                {
                    "label": "Resume",
                    "normalized_label": "resume",
                    "category": "resume_upload",
                    "automation_action": "auto_fill_from_profile",
                    "sensitivity": "document",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "form.json",
                },
                {
                    "label": "Why are you interested in this role?",
                    "normalized_label": "why interested role",
                    "category": "role_specific_free_text",
                    "automation_action": "generate_custom_material",
                    "sensitivity": "custom_material",
                    "required": True,
                    "platform": "LinkedIn",
                    "source_file": "submissions.jsonl",
                },
                {
                    "label": "Gender",
                    "normalized_label": "gender",
                    "category": "eeoc_sensitive",
                    "automation_action": "do_not_store_sensitive",
                    "sensitivity": "protected_class",
                    "required": False,
                    "platform": "Greenhouse",
                    "source_file": "form.json",
                },
            ],
        }

        report = build_answer_gap_report(research, profile=profile, answer_memory=None)

        self.assertEqual(report["coverage_counts"]["covered_auto_answer"], 1)
        self.assertEqual(report["coverage_counts"]["covered_generation"], 1)
        self.assertEqual(report["coverage_counts"]["needs_profile_material"], 1)
        self.assertEqual(report["coverage_counts"]["sensitive_not_stored"], 1)
        self.assertEqual(report["blocking_prompt_count"], 2)
        markdown = render_answer_gap_markdown(report)
        self.assertIn("Application Answer Gap Report", markdown)
        self.assertIn("needs_profile_material", markdown)

    def test_answer_gap_report_covers_skill_questions_from_resume_facts(self) -> None:
        profile = CandidateProfile(
            name="Alan Jiang",
            email="alan@example.com",
            phone="555-0100",
            location="Bellevue, WA",
            target_titles=["Site Reliability Engineer"],
            target_locations=["United States"],
            remote_ok=True,
            keywords=["sre"],
            blocklist=[],
            min_score=1,
            resume_facts={
                "professional_summary": "SRE and automation engineer",
                "kubernetes_oncall_experience": (
                    "Operated Kubernetes-equivalent production services and handled "
                    "on-call incident response for critical infrastructure."
                ),
                "cloud_experience": "Resume shows Azure and AWS infrastructure experience.",
            },
            question_answers={},
        )
        research = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "positions_observed_total": 1,
            "items": [
                {
                    "label": "Do you have experience with Kubernetes operations and on-call practices?",
                    "normalized_label": "experience kubernetes operations on call practices",
                    "category": "skills_experience",
                    "automation_action": "auto_answer_from_memory",
                    "sensitivity": "standard_preference",
                    "required": True,
                    "platform": "LinkedIn",
                    "source_file": "submissions.jsonl",
                },
                {
                    "label": "Do you have experience with Google Cloud Platform?",
                    "normalized_label": "experience google cloud platform",
                    "category": "skills_experience",
                    "automation_action": "auto_answer_from_memory",
                    "sensitivity": "standard_preference",
                    "required": True,
                    "platform": "LinkedIn",
                    "source_file": "submissions.jsonl",
                },
            ],
        }

        report = build_answer_gap_report(research, profile=profile, answer_memory=None)
        statuses = {
            item["label"]: item["coverage_status"]
            for item in report["prompt_statuses"]
        }

        self.assertEqual(
            statuses["Do you have experience with Kubernetes operations and on-call practices?"],
            "covered_auto_answer",
        )
        self.assertEqual(
            statuses["Do you have experience with Google Cloud Platform?"],
            "needs_answer_memory",
        )

    def test_answer_gap_report_uses_cloud_provider_standard_answer(self) -> None:
        profile = CandidateProfile(
            name="Alan Jiang",
            email="alan@example.com",
            phone="555-0100",
            location="Bellevue, WA",
            target_titles=["Site Reliability Engineer"],
            target_locations=["United States"],
            remote_ok=True,
            keywords=["sre"],
            blocklist=[],
            min_score=1,
            resume_facts={"professional_summary": "SRE and automation engineer"},
            question_answers={
                "cloud_provider_general": (
                    "I am open to roles using GCP, AWS, or Azure. My resume "
                    "specifically shows Azure experience and AWS in skills; I "
                    "should only claim specific GCP years if verified."
                )
            },
        )
        research = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "positions_observed_total": 1,
            "items": [
                {
                    "label": "Do you have experience with Google Cloud Platform?",
                    "normalized_label": "experience google cloud platform",
                    "category": "skills_experience",
                    "automation_action": "auto_answer_from_memory",
                    "sensitivity": "standard_preference",
                    "required": True,
                    "platform": "LinkedIn",
                    "source_file": "submissions.jsonl",
                },
            ],
        }

        report = build_answer_gap_report(research, profile=profile, answer_memory=None)

        self.assertEqual(report["blocking_prompt_count"], 0)
        self.assertEqual(
            report["prompt_statuses"][0]["coverage_status"],
            "covered_auto_answer",
        )
        self.assertEqual(
            report["prompt_statuses"][0]["answer_source"],
            "profile.question_answers",
        )

    def test_answer_gap_report_uses_standard_notice_and_immigration_answers(self) -> None:
        profile = CandidateProfile(
            name="Alan Jiang",
            email="alan@example.com",
            phone="555-0100",
            location="Bellevue, WA",
            target_titles=["Site Reliability Engineer"],
            target_locations=["United States"],
            remote_ok=True,
            keywords=["sre"],
            blocklist=[],
            min_score=1,
            resume_facts={},
            question_answers={
                "start_date": "I can start in about two months.",
                "sponsorship": "Yes, I will now or in the future require visa sponsorship or a visa transfer.",
                "authorization": "I am authorized to work in the United States.",
                "years_experience": "4 years or less, depending on the specific skill or domain asked.",
            },
        )
        research = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "positions_observed_total": 1,
            "items": [
                {
                    "label": "What is your notice period?",
                    "normalized_label": "what notice period",
                    "category": "availability",
                    "automation_action": "auto_answer_from_memory",
                    "sensitivity": "standard_preference",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "form.json",
                },
                {
                    "label": "If successful, how soon are you able to commence in this role with Envoy Global?",
                    "normalized_label": "if successful how soon able commence role envoy global",
                    "category": "availability",
                    "automation_action": "auto_answer_from_memory",
                    "sensitivity": "standard_preference",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "form.json",
                },
                {
                    "label": "Do you have 8+ years expertise in C#?",
                    "normalized_label": "8 years expertise c",
                    "category": "experience_years",
                    "automation_action": "auto_answer_from_memory",
                    "sensitivity": "standard_preference",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "form.json",
                },
                {
                    "label": "Now or in the future will you need immigration assistance?",
                    "normalized_label": "future need immigration assistance",
                    "category": "sponsorship",
                    "automation_action": "auto_answer_from_memory",
                    "sensitivity": "standard_preference",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "form.json",
                },
                {
                    "label": "Do you currently have the legal right to work in one of these locations?",
                    "normalized_label": "currently have legal right work one these locations",
                    "category": "work_authorization",
                    "automation_action": "auto_answer_from_memory",
                    "sensitivity": "standard_preference",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "form.json",
                },
                {
                    "label": "How many weeks after accepting an offer could you start?",
                    "normalized_label": "how many weeks after accepting offer could start",
                    "category": "unknown",
                    "automation_action": "human_review_required",
                    "sensitivity": "general",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "old_snapshot.json",
                },
                {
                    "label": "Are you actively looking for a job, or just exploring future opportunities?",
                    "normalized_label": "actively looking job just exploring future opportunities",
                    "category": "unknown",
                    "automation_action": "human_review_required",
                    "sensitivity": "general",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "old_snapshot.json",
                },
                {
                    "label": "When would you like to hear back from us regarding potential opportunities?",
                    "normalized_label": "when would like hear back us regarding potential opportunities",
                    "category": "unknown",
                    "automation_action": "human_review_required",
                    "sensitivity": "general",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "old_snapshot.json",
                },
            ],
        }

        report = build_answer_gap_report(research, profile=profile, answer_memory=None)

        self.assertEqual(report["blocking_prompt_count"], 0)
        self.assertEqual(report["coverage_counts"]["covered_auto_answer"], 8)
        start_prompt = next(
            item
            for item in report["prompt_statuses"]
            if item["label"] == "How many weeks after accepting an offer could you start?"
        )
        self.assertEqual(start_prompt["category"], "availability")
        self.assertEqual(start_prompt["coverage_status"], "covered_auto_answer")
        active_prompt = next(
            item
            for item in report["prompt_statuses"]
            if item["label"] == "Are you actively looking for a job, or just exploring future opportunities?"
        )
        self.assertEqual(active_prompt["category"], "availability")
        self.assertEqual(active_prompt["coverage_status"], "covered_auto_answer")
        followup_prompt = next(
            item
            for item in report["prompt_statuses"]
            if item["label"] == "When would you like to hear back from us regarding potential opportunities?"
        )
        self.assertEqual(followup_prompt["category"], "availability")
        self.assertEqual(followup_prompt["coverage_status"], "covered_auto_answer")

    def test_answer_gap_report_uses_standard_source_disclosure_and_age_answers(self) -> None:
        profile = CandidateProfile(
            name="Alan Jiang",
            email="alan@example.com",
            phone="555-0100",
            location="Bellevue, WA",
            target_titles=["Site Reliability Engineer"],
            target_locations=["United States"],
            remote_ok=True,
            keywords=["sre"],
            blocklist=[],
            min_score=1,
            resume_facts={},
            question_answers={
                "referral_source": "LinkedIn",
                "referral_contact": "N/A - no specific employee referral.",
                "age_over_18": "Yes",
                "ai_application_disclosure": "Yes",
                "compensation_currency": "USD",
                "communication_consent": "Yes",
                "english_level": "Professional working proficiency in English.",
            },
        )
        research = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "positions_observed_total": 1,
            "items": [
                {
                    "label": "How did you hear about this job?",
                    "normalized_label": "how did hear about this job",
                    "category": "referral_source",
                    "automation_action": "auto_answer_from_memory",
                    "sensitivity": "standard_preference",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "form.json",
                },
                {
                    "label": "Stack Overflow Jobs",
                    "normalized_label": "stack overflow jobs",
                    "category": "referral_source",
                    "automation_action": "auto_answer_from_memory",
                    "sensitivity": "standard_preference",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "form.json",
                },
                {
                    "label": "If you were referred by someone at Later, please let us know!",
                    "normalized_label": "if referred by someone later please let us know",
                    "category": "referral_contact",
                    "automation_action": "auto_answer_from_memory",
                    "sensitivity": "standard_preference",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "form.json",
                },
                {
                    "label": "Are you at least 18 years of age?",
                    "normalized_label": "at least 18 years age",
                    "category": "legal_age",
                    "automation_action": "auto_answer_from_memory",
                    "sensitivity": "standard_preference",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "form.json",
                },
                {
                    "label": "Did AI complete or submit this application?",
                    "normalized_label": "did ai complete or submit this application",
                    "category": "unknown",
                    "automation_action": "human_review_required",
                    "sensitivity": "general",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "old_snapshot.json",
                },
                {
                    "label": "Currency",
                    "normalized_label": "currency",
                    "category": "compensation_currency",
                    "automation_action": "auto_answer_from_memory",
                    "sensitivity": "standard_preference",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "form.json",
                },
                {
                    "label": "Future Contact Consent",
                    "normalized_label": "future contact consent",
                    "category": "communication_consent",
                    "automation_action": "auto_answer_from_memory",
                    "sensitivity": "consent",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "form.json",
                },
                {
                    "label": "Do you speak English fluently?",
                    "normalized_label": "do speak english fluently",
                    "category": "language_ability",
                    "automation_action": "auto_answer_from_memory",
                    "sensitivity": "candidate_preference",
                    "required": True,
                    "platform": "Lever",
                    "source_file": "form.json",
                },
            ],
        }

        report = build_answer_gap_report(research, profile=profile, answer_memory=None)

        self.assertEqual(report["blocking_prompt_count"], 0)
        self.assertEqual(report["coverage_counts"]["covered_auto_answer"], 8)
        ai_prompt = next(
            item
            for item in report["prompt_statuses"]
            if item["label"] == "Did AI complete or submit this application?"
        )
        self.assertEqual(ai_prompt["category"], "ai_application_disclosure")
        self.assertEqual(ai_prompt["coverage_status"], "covered_auto_answer")

    def test_answer_gap_report_uses_policy_and_english_profile_answers(self) -> None:
        profile = CandidateProfile(
            name="Alan Jiang",
            email="alan@example.com",
            phone="555-0100",
            location="Bellevue, WA",
            target_titles=["Site Reliability Engineer"],
            target_locations=["United States"],
            remote_ok=True,
            keywords=["sre"],
            blocklist=[],
            min_score=1,
            resume_facts={},
            question_answers={
                "policy_acknowledgement": "Yes, I acknowledge.",
                "english_level": "Professional working proficiency in English.",
            },
        )
        research = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "positions_observed_total": 1,
            "items": [
                {
                    "label": "I understand my application will be processed in accordance with the Candidate Privacy Policy.",
                    "normalized_label": "understand application processed accordance candidate privacy policy",
                    "category": "policy_acknowledgement",
                    "automation_action": "human_review_required",
                    "sensitivity": "policy",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "form.json",
                },
                {
                    "label": "How would you evaluate your English Level?",
                    "normalized_label": "how evaluate english level",
                    "category": "language_ability",
                    "automation_action": "auto_answer_from_memory",
                    "sensitivity": "standard_preference",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "form.json",
                },
            ],
        }

        report = build_answer_gap_report(research, profile=profile, answer_memory=None)
        statuses = {item["label"]: item["coverage_status"] for item in report["prompt_statuses"]}

        self.assertEqual(
            statuses[
                "I understand my application will be processed in accordance with the Candidate Privacy Policy."
            ],
            "covered_requires_review",
        )
        self.assertEqual(
            statuses["How would you evaluate your English Level?"],
            "covered_auto_answer",
        )

    def test_answer_gap_report_prefills_reviewed_location_and_domain_answers(self) -> None:
        profile = CandidateProfile(
            name="Alan Jiang",
            email="alan@example.com",
            phone="555-0100",
            location="Bellevue, WA",
            target_titles=["Site Reliability Engineer"],
            target_locations=["United States", "San Francisco Bay Area"],
            remote_ok=True,
            keywords=["sre"],
            blocklist=[],
            min_score=1,
            resume_facts={
                "professional_summary": "SRE and production engineer",
                "strongest_skills": "Python, Go, C++, Linux, SQL, Hive, and reliability automation",
                "cloud_experience": "Resume shows Azure and AWS infrastructure experience.",
            },
            question_answers={
                "onsite_hybrid": "Yes, I am open to onsite or hybrid work for the right role.",
                "relocation": "Yes, I am open to relocation for the right role.",
            },
        )
        research = {
            "generated_at": "2026-05-23T00:00:00+00:00",
            "positions_observed_total": 1,
            "items": [
                {
                    "label": "Are there any circumstances preventing you from traveling internationally to a week-long team offsite?",
                    "normalized_label": "circumstances preventing traveling internationally week long team offsite",
                    "category": "location_constraint",
                    "automation_action": "human_review_required",
                    "sensitivity": "candidate_preference",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "form.json",
                },
                {
                    "label": "Are you currently based in the greater San Francisco / Bay Area?",
                    "normalized_label": "currently based greater san francisco bay area",
                    "category": "location_constraint",
                    "automation_action": "human_review_required",
                    "sensitivity": "candidate_preference",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "form.json",
                },
                {
                    "label": "Do you have hands on experience with Go or C++?",
                    "normalized_label": "hands on experience go c",
                    "category": "domain_experience",
                    "automation_action": "human_review_required",
                    "sensitivity": "resume_fact",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "form.json",
                },
            ],
        }

        report = build_answer_gap_report(research, profile=profile, answer_memory=None)
        statuses = {item["label"]: item for item in report["prompt_statuses"]}

        self.assertEqual(report["blocking_prompt_count"], 0)
        self.assertEqual(
            statuses[
                "Are there any circumstances preventing you from traveling internationally to a week-long team offsite?"
            ]["coverage_status"],
            "covered_requires_review",
        )
        self.assertEqual(
            statuses[
                "Are you currently based in the greater San Francisco / Bay Area?"
            ]["coverage_status"],
            "covered_requires_review",
        )
        self.assertEqual(
            statuses["Do you have hands on experience with Go or C++?"]["answer_source"],
            "profile.resume_facts",
        )

    def test_profile_identity_uses_specific_location_parts(self) -> None:
        profile = CandidateProfile(
            name="Alan Jiang",
            email="alan@example.com",
            phone="555-0100",
            location="Bellevue, WA",
            target_titles=["Site Reliability Engineer"],
            target_locations=["United States"],
            remote_ok=True,
            keywords=["sre"],
            blocklist=[],
            min_score=1,
            resume_facts={},
            question_answers={},
        )
        snapshot = {
            "title": "Example Application",
            "url": "https://job-boards.greenhouse.io/example/jobs/1",
            "platform": "Greenhouse",
            "fields": [
                {"i": 1, "label": "City", "tag": "INPUT", "required": True},
                {"i": 2, "label": "State", "tag": "INPUT", "required": True},
                {"i": 3, "label": "Country", "tag": "INPUT", "required": True},
                {"i": 4, "label": "Zip Code", "tag": "INPUT", "required": True},
            ],
        }

        plan = build_form_fill_plan(snapshot, profile=profile, include_values=True)
        values = {step["label"]: step.get("value") for step in plan["steps"]}
        statuses = {step["label"]: step["status"] for step in plan["steps"]}

        self.assertEqual(values["City"], "Bellevue")
        self.assertEqual(values["State"], "WA")
        self.assertEqual(values["Country"], "United States")
        self.assertEqual(statuses["Zip Code"], "missing_profile_value")

    def test_education_date_uses_resume_fact_but_gpa_remains_missing(self) -> None:
        profile = CandidateProfile(
            name="Alan Jiang",
            email="alan@example.com",
            phone="555-0100",
            location="Bellevue, WA",
            target_titles=["Site Reliability Engineer"],
            target_locations=["United States"],
            remote_ok=True,
            keywords=["sre"],
            blocklist=[],
            min_score=1,
            resume_facts={"graduation_date": "Dec 2024"},
            question_answers={},
        )
        snapshot = {
            "title": "Example Application",
            "url": "https://job-boards.greenhouse.io/example/jobs/1",
            "platform": "Greenhouse",
            "fields": [
                {"i": 1, "label": "When do you graduate?", "tag": "INPUT", "required": True},
                {"i": 2, "label": "What is your GPA?", "tag": "INPUT", "required": True},
            ],
        }

        plan = build_form_fill_plan(snapshot, profile=profile, include_values=True)

        self.assertEqual(plan["steps"][0]["status"], "ready")
        self.assertEqual(plan["steps"][0]["value"], "Dec 2024")
        self.assertEqual(plan["steps"][1]["status"], "missing_profile_value")

    def test_employment_date_fields_use_specific_resume_facts(self) -> None:
        profile = CandidateProfile(
            name="Alan Jiang",
            email="alan@example.com",
            phone="555-0100",
            location="Bellevue, WA",
            target_titles=["Site Reliability Engineer"],
            target_locations=["United States"],
            remote_ok=True,
            keywords=["sre"],
            blocklist=[],
            min_score=1,
            resume_facts={
                "employment_dates": "Current role: Jan 2026-Present",
                "current_role_end_month": "Present",
                "current_role_end_year": "Present",
            },
            question_answers={},
        )
        snapshot = {
            "title": "Example Application",
            "url": "https://job-boards.greenhouse.io/example/jobs/1",
            "platform": "Greenhouse",
            "fields": [
                {"i": 1, "label": "End date month", "tag": "INPUT", "required": True},
                {"i": 2, "label": "End date year", "tag": "INPUT", "required": True},
            ],
        }

        plan = build_form_fill_plan(snapshot, profile=profile, include_values=True)

        self.assertEqual(plan["steps"][0]["status"], "ready")
        self.assertEqual(plan["steps"][0]["value"], "Present")
        self.assertEqual(plan["steps"][1]["value"], "Present")

    def test_profile_link_fields_require_matching_link_type(self) -> None:
        profile = CandidateProfile(
            name="Alan Jiang",
            email="alan@example.com",
            phone="555-0100",
            location="Bellevue, WA",
            target_titles=["Site Reliability Engineer"],
            target_locations=["United States"],
            remote_ok=True,
            keywords=["sre"],
            blocklist=[],
            min_score=1,
            resume_facts={},
            question_answers={"linkedin_profile": "https://www.linkedin.com/in/example/"},
        )
        snapshot = {
            "title": "Example Application",
            "url": "https://job-boards.greenhouse.io/example/jobs/1",
            "platform": "Greenhouse",
            "fields": [
                {"i": 1, "label": "LinkedIn Profile", "tag": "INPUT", "required": True},
                {"i": 2, "label": "Google Scholar", "tag": "INPUT", "required": False},
            ],
        }

        plan = build_form_fill_plan(snapshot, profile=profile, include_values=True)

        self.assertEqual(plan["steps"][0]["status"], "ready")
        self.assertEqual(plan["steps"][0]["value"], "https://www.linkedin.com/in/example/")
        self.assertEqual(plan["steps"][1]["status"], "missing_profile_value")
        self.assertEqual(plan["steps"][1]["value_source"], "profile.question_answers.google_scholar")

    def test_optional_profile_links_from_question_lists_do_not_block_readiness(self) -> None:
        profile = CandidateProfile(
            name="Alan Jiang",
            email="alan@example.com",
            phone="555-0100",
            location="Bellevue, WA",
            target_titles=["Site Reliability Engineer"],
            target_locations=["United States"],
            remote_ok=True,
            keywords=["sre"],
            blocklist=[],
            min_score=1,
            resume_facts={},
            question_answers={"linkedin_profile": "https://www.linkedin.com/in/example/"},
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            observed = Path(temp_dir) / "observed_candidates.jsonl"
            row = {
                "status": "OBSERVED_CANDIDATE",
                "platform": "Greenhouse",
                "company": "Example",
                "title": "Site Reliability Engineer",
                "apply_url": "https://job-boards.greenhouse.io/example/jobs/1",
                "questions": [
                    "First Name",
                    "Middle Name",
                    "Last Name",
                    "Email",
                    "LinkedIn Profile",
                    "Website",
                    "If other, please specify",
                    "Optional: link to a blog post or other public writing; leave blank if none.",
                ],
            }
            observed.write_text(json.dumps(row) + "\n", encoding="utf-8")

            research = build_application_research(temp_dir, position_target=100)
            required_by_label = {item["label"]: item["required"] for item in research["items"]}
            self.assertFalse(required_by_label["Middle Name"])
            self.assertFalse(required_by_label["Website"])
            self.assertFalse(
                required_by_label[
                    "Optional: link to a blog post or other public writing; leave blank if none."
                ]
            )
            gaps = build_answer_gap_report(research, profile=profile, answer_memory=None)
            statuses = {item["label"]: item["coverage_status"] for item in gaps["prompt_statuses"]}
            self.assertEqual(statuses["Middle Name"], "optional_missing_profile")
            self.assertEqual(statuses["Website"], "optional_missing_profile")
            self.assertEqual(statuses["If other, please specify"], "optional_missing_answer")

            readiness = build_position_readiness_report(research, gaps)

            self.assertEqual(readiness["readiness_counts"], {"autofill_ready": 1})
            self.assertEqual(readiness["minimal_learning_task_count"], 0)

    def test_application_research_skips_linkedin_ai_advice_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            observed = Path(temp_dir) / "observed_candidates.jsonl"
            rows = [
                {
                    "status": "OBSERVED_CANDIDATE",
                    "platform": "LinkedIn",
                    "company": "Cisco",
                    "title": "Platform Engineer",
                    "apply_url": "https://www.linkedin.com/jobs/view/1/",
                    "questions": [
                        "Am I a good fit for this job?",
                        "Tailor my resume",
                        "WHAT’S IN IT FOR YOU?",
                        "Ready to accelerate your career?",
                        "Why Cisco?",
                    ],
                }
            ]
            observed.write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )

            research = build_application_research(temp_dir, position_target=100)
            labels = {item["label"] for item in research["items"]}

            self.assertNotIn("Am I a good fit for this job?", labels)
            self.assertNotIn("Tailor my resume", labels)
            self.assertNotIn("WHAT’S IN IT FOR YOU?", labels)
            self.assertNotIn("Ready to accelerate your career?", labels)
            self.assertIn("Why Cisco?", labels)

    def test_application_research_skips_low_signal_skill_filter_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            observed = Path(temp_dir) / "observed_candidates.jsonl"
            observed.write_text(
                json.dumps(
                    {
                        "status": "OBSERVED_CANDIDATE",
                        "platform": "LinkedIn",
                        "company": "Example",
                        "title": "SRE",
                        "apply_url": "https://www.linkedin.com/jobs/view/2/",
                        "questions": [
                            "Docker",
                            "SQL",
                            "Great, do my skills fit?",
                            "Claude",
                            "1 week per month",
                            "Are You A Fit?",
                            "ARM/Bicep",
                            "He/him",
                            "TS/SCI with CI Poly",
                            "Use name only",
                            "btn clear filters",
                            "Prêt·e à passer au niveau supérieur sans renoncer à tes valeurs ?",
                            "Anytime/as needed",
                            "N/A",
                            "Não",
                            "Sim",
                            "Recruiter Outreach",
                            "SHPE Conference",
                            "Event, Media Interview, or other PR",
                            "Advanced",
                            "Beginner",
                            "Expert",
                            "Built In",
                            "Glassdoor",
                            "Grafana",
                            "Linux environment",
                            "Outra",
                            "Outro",
                            "You’ve Got This?",
                            "Human Factors, Safety & Sociotechnical Systems",
                            "Indigenous Peoples, First Nations, Native American, or Alaska Native",
                            "Do you have blockchain/crypto experience?",
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            research = build_application_research(temp_dir, position_target=100)
            labels = {item["label"] for item in research["items"]}

            self.assertNotIn("Docker", labels)
            self.assertNotIn("SQL", labels)
            self.assertNotIn("Great, do my skills fit?", labels)
            self.assertNotIn("Claude", labels)
            self.assertNotIn("1 week per month", labels)
            self.assertNotIn("Are You A Fit?", labels)
            self.assertNotIn("ARM/Bicep", labels)
            self.assertNotIn("He/him", labels)
            self.assertNotIn("TS/SCI with CI Poly", labels)
            self.assertNotIn("Use name only", labels)
            self.assertNotIn("btn clear filters", labels)
            self.assertNotIn("Prêt·e à passer au niveau supérieur sans renoncer à tes valeurs ?", labels)
            self.assertNotIn("Anytime/as needed", labels)
            self.assertNotIn("N/A", labels)
            self.assertNotIn("Não", labels)
            self.assertNotIn("Sim", labels)
            self.assertNotIn("Recruiter Outreach", labels)
            self.assertNotIn("SHPE Conference", labels)
            self.assertNotIn("Event, Media Interview, or other PR", labels)
            self.assertNotIn("Advanced", labels)
            self.assertNotIn("Beginner", labels)
            self.assertNotIn("Expert", labels)
            self.assertNotIn("Built In", labels)
            self.assertNotIn("Glassdoor", labels)
            self.assertNotIn("Grafana", labels)
            self.assertNotIn("Linux environment", labels)
            self.assertNotIn("Outra", labels)
            self.assertNotIn("Outro", labels)
            self.assertNotIn("You’ve Got This?", labels)
            self.assertNotIn("Human Factors, Safety & Sociotechnical Systems", labels)
            self.assertNotIn("Indigenous Peoples, First Nations, Native American, or Alaska Native", labels)
            self.assertIn("Do you have blockchain/crypto experience?", labels)

    def test_question_export_xlsx_strips_invalid_xml_control_characters(self) -> None:
        bad_label = "Question with vertical tab \x0b from a scraped page"
        prompt = {
            "coverage_status": "needs_user_confirmation",
            "label": bad_label,
            "category": "unknown",
            "automation_action": "human_review_required",
            "sensitivity": "unknown",
            "required_count": 1,
            "observed_count": 1,
            "platforms": ["Greenhouse"],
            "source_files": ["bad.json"],
            "coverage_reason": "test",
            "next_action": "inspect",
        }
        gaps = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "research_generated_at": "2026-05-22T00:00:00+00:00",
            "positions_observed_total": 1,
            "unique_prompts_observed": 1,
            "ready_prompt_count": 0,
            "blocking_prompt_count": 1,
            "coverage_counts": {"needs_user_confirmation": 1},
            "prompt_statuses": [prompt],
            "blocking_prompts": [prompt],
        }
        readiness = {
            "readiness_counts": {"needs_learning": 1},
            "manual_gate_count": 0,
            "manual_gates": [],
            "positions": [
                {
                    "readiness": "needs_learning",
                    "platform": "Greenhouse",
                    "company": "Example",
                    "title": bad_label,
                    "role_family": "Site Reliability",
                    "apply_url": "https://example.test/job",
                    "learning_blockers": [prompt],
                    "manual_gates": [],
                }
            ],
        }
        coverage_gate = {"synthetic": {"platform_role_target_achieved": True}}
        collection_plan = {"tasks": []}
        learning_tasks = {"task_count": 1, "tasks": []}

        with tempfile.TemporaryDirectory() as temp_dir:
            xlsx_path = Path(temp_dir) / "questions.xlsx"
            html_path = Path(temp_dir) / "questions.html"

            write_question_export(
                gaps,
                readiness,
                coverage_gate,
                collection_plan,
                learning_tasks,
                xlsx_path,
                html_path,
            )

            with zipfile.ZipFile(xlsx_path) as archive:
                for name in archive.namelist():
                    if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                        ET.fromstring(archive.read(name))

    def test_write_answer_gap_report_outputs_json_and_markdown(self) -> None:
        research = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "positions_observed_total": 1,
            "items": [
                {
                    "label": "LinkedIn Profile",
                    "normalized_label": "linkedin profile",
                    "category": "profile_link",
                    "automation_action": "auto_fill_from_profile",
                    "sensitivity": "profile",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "form.json",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            json_output = Path(temp_dir) / "gaps.json"
            markdown_output = Path(temp_dir) / "gaps.md"
            report = write_answer_gap_report(research, json_output, markdown_output)

            self.assertEqual(report["coverage_counts"]["needs_profile_field"], 1)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertIn("Application Answer Gap Report", markdown_output.read_text())

    def test_position_readiness_report_separates_learning_and_manual_gates(self) -> None:
        research = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "positions": [
                {
                    "position_key": "linkedin:1",
                    "platform": "LinkedIn",
                    "company": "ReadyCo",
                    "title": "SRE",
                    "role_family": "Site Reliability",
                },
                {
                    "position_key": "greenhouse:2",
                    "platform": "Greenhouse",
                    "company": "NeedsCo",
                    "title": "Platform Engineer",
                    "role_family": "Platform Infrastructure",
                },
            ],
            "items": [
                {
                    "position_key": "linkedin:1",
                    "label": "Are you authorized to work in the United States?",
                    "normalized_label": "authorized work united states",
                    "category": "work_authorization",
                    "required": True,
                },
                {
                    "position_key": "greenhouse:2",
                    "label": "Resume",
                    "normalized_label": "resume",
                    "category": "resume_upload",
                    "required": True,
                },
                {
                    "position_key": "greenhouse:2",
                    "label": "Gender",
                    "normalized_label": "gender",
                    "category": "eeoc_sensitive",
                    "required": False,
                },
            ],
        }
        gaps = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "prompt_statuses": [
                {
                    "label": "Are you authorized to work in the United States?",
                    "normalized_label": "authorized work united states",
                    "category": "work_authorization",
                    "coverage_status": "covered_auto_answer",
                    "observed_count": 1,
                    "required_count": 1,
                    "platforms": ["LinkedIn"],
                    "source_files": ["x.jsonl"],
                    "next_action": "autofill",
                },
                {
                    "label": "Resume",
                    "normalized_label": "resume",
                    "category": "resume_upload",
                    "coverage_status": "needs_profile_material",
                    "observed_count": 1,
                    "required_count": 1,
                    "platforms": ["Greenhouse"],
                    "source_files": ["form.json"],
                    "next_action": "record resume path",
                },
                {
                    "label": "Gender",
                    "normalized_label": "gender",
                    "category": "eeoc_sensitive",
                    "coverage_status": "sensitive_not_stored",
                    "observed_count": 1,
                    "required_count": 0,
                    "platforms": ["Greenhouse"],
                    "source_files": ["form.json"],
                    "next_action": "ask during supervised flow",
                },
            ],
        }

        report = build_position_readiness_report(research, gaps)

        self.assertEqual(report["readiness_counts"]["autofill_ready"], 1)
        self.assertEqual(report["readiness_counts"]["needs_learning"], 1)
        self.assertEqual(report["learning_queue_count"], 1)
        self.assertEqual(report["minimal_learning_task_count"], 1)
        self.assertEqual(report["manual_gate_count"], 1)
        self.assertEqual(report["learning_queue"][0]["recommended_storage"], "local_material")
        markdown = render_position_readiness_markdown(report)
        self.assertIn("Application Automation Readiness", markdown)
        self.assertIn("needs_learning", markdown)

    def test_position_readiness_groups_repeated_confirmation_prompts(self) -> None:
        research = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "positions": [{"position_key": "greenhouse:1", "platform": "Greenhouse"}],
            "items": [],
        }
        gaps = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "prompt_statuses": [
                {
                    "label": "Have you worked with us before?",
                    "normalized_label": "have worked with us before",
                    "category": "employment_history",
                    "coverage_status": "needs_user_confirmation",
                    "observed_count": 3,
                    "required_count": 3,
                    "platforms": ["Greenhouse"],
                    "next_action": "ask user",
                },
                {
                    "label": "Have you previously worked at Natera?",
                    "normalized_label": "have previously worked at natera",
                    "category": "employment_history",
                    "coverage_status": "needs_user_confirmation",
                    "observed_count": 2,
                    "required_count": 2,
                    "platforms": ["Greenhouse"],
                    "next_action": "ask user",
                },
                {
                    "label": "Do you know anyone currently at Glean?",
                    "normalized_label": "do know anyone currently at glean",
                    "category": "conflict_of_interest",
                    "coverage_status": "needs_user_confirmation",
                    "observed_count": 4,
                    "required_count": 4,
                    "platforms": ["Greenhouse"],
                    "next_action": "ask user",
                },
                {
                    "label": "Do you currently have a relative employed with Verisign?",
                    "normalized_label": "do currently have relative employed with verisign",
                    "category": "conflict_of_interest",
                    "coverage_status": "needs_user_confirmation",
                    "observed_count": 1,
                    "required_count": 1,
                    "platforms": ["Greenhouse"],
                    "next_action": "ask user",
                },
                {
                    "label": "Candidate Personal Data Disclosure",
                    "normalized_label": "candidate personal data disclosure",
                    "category": "policy_acknowledgement",
                    "coverage_status": "needs_user_confirmation",
                    "observed_count": 4,
                    "required_count": 4,
                    "platforms": ["Greenhouse"],
                    "next_action": "ask user",
                },
            ],
        }

        report = build_position_readiness_report(research, gaps)
        tasks = {task["group_key"]: task for task in report["minimal_learning_tasks"]}

        self.assertEqual(report["learning_queue_count"], 5)
        self.assertEqual(report["minimal_learning_task_count"], 3)
        self.assertEqual(tasks["answer_memory:employment_history:default_policy"]["related_prompt_count"], 2)
        self.assertEqual(tasks["answer_memory:conflict_of_interest:default_policy"]["related_prompt_count"], 2)
        self.assertEqual(
            tasks["answer_memory:policy_acknowledgement:candidate personal data disclosure"]["question"],
            "Candidate Personal Data Disclosure",
        )
        self.assertIn("prior-employer", tasks["answer_memory:employment_history:default_policy"]["question"])
        self.assertIn("conflict-of-interest", tasks["answer_memory:conflict_of_interest:default_policy"]["question"])
        template = build_learning_task_template(report)
        template_tasks = {task["group_key"]: task for task in template["tasks"]}
        self.assertEqual(
            template_tasks["answer_memory:employment_history:default_policy"]["answer_scope"],
            "category_default_policy",
        )
        self.assertIn(
            "keep human review",
            template_tasks["answer_memory:employment_history:default_policy"]["automation_behavior"],
        )
        self.assertEqual(
            template_tasks["answer_memory:employment_history:default_policy"]["suggested_answer_source"],
            "category_default_policy_template",
        )
        self.assertIn(
            "unless a specific employer",
            template_tasks["answer_memory:employment_history:default_policy"]["suggested_answer"],
        )
        self.assertEqual(
            template_tasks["answer_memory:policy_acknowledgement:candidate personal data disclosure"]["answer_scope"],
            "exact_prompt_labels",
        )
        self.assertEqual(
            template_tasks["answer_memory:policy_acknowledgement:candidate personal data disclosure"]["suggested_answer"],
            "Yes, I acknowledge.",
        )
        self.assertEqual(
            template_tasks["answer_memory:employment_history:default_policy"]["related_prompt_count"],
            2,
        )
        self.assertEqual(
            template_tasks["answer_memory:employment_history:default_policy"]["observed_count"],
            5,
        )

    def test_learning_task_template_suggests_from_profile_and_memory(self) -> None:
        readiness = {
            "minimal_learning_tasks": [
                {
                    "group_key": "local_material:resume_file",
                    "question": "Which approved resume file should automation upload?",
                    "recommended_storage": "local_material",
                    "labels": ["Resume"],
                    "platforms": ["Ashby"],
                },
                {
                    "group_key": "answer_memory:needs_user_confirmation:expected compensation",
                    "question": "What is your expected compensation?",
                    "recommended_storage": "answer_memory",
                    "labels": ["What is your expected compensation?"],
                    "platforms": ["Greenhouse"],
                },
                {
                    "group_key": "answer_memory:citizenship_status:default_policy",
                    "question": "What citizenship answers should automation use?",
                    "recommended_storage": "answer_memory",
                    "labels": ["Are you a U.S. citizen?"],
                    "platforms": ["Greenhouse"],
                },
            ]
        }
        memory = {
            "answers": [
                {
                    "normalized_question": "what expected compensation",
                    "sample_question": "What is your expected compensation?",
                    "answer": "$100,000+",
                    "approved_count": 1,
                    "source": "test",
                }
            ]
        }
        profile = CandidateProfile(
            name=self.profile.name,
            email=self.profile.email,
            phone=self.profile.phone,
            location=self.profile.location,
            target_titles=self.profile.target_titles,
            target_locations=self.profile.target_locations,
            remote_ok=self.profile.remote_ok,
            keywords=self.profile.keywords,
            blocklist=self.profile.blocklist,
            min_score=self.profile.min_score,
            resume_facts=self.profile.resume_facts,
            question_answers={**self.profile.question_answers, "resume_path": "/tmp/resume.pdf"},
        )

        template = build_learning_task_template(readiness, profile=profile, answer_memory=memory)
        tasks = {task["group_key"]: task for task in template["tasks"]}

        self.assertEqual(
            tasks["local_material:resume_file"]["suggested_answer"],
            "/tmp/resume.pdf",
        )
        self.assertEqual(
            tasks["answer_memory:needs_user_confirmation:expected compensation"]["suggested_answer"],
            "$100,000+",
        )
        self.assertEqual(
            tasks["answer_memory:citizenship_status:default_policy"]["suggested_answer_source"],
            "requires_exact_user_confirmation",
        )
        self.assertEqual(
            tasks["answer_memory:citizenship_status:default_policy"]["approval_risk"],
            "high",
        )

    def test_learning_task_template_drafts_resume_based_exact_prompt_answers(self) -> None:
        readiness = {
            "minimal_learning_tasks": [
                {
                    "group_key": "answer_memory:needs_user_confirmation:linux",
                    "question": "Describe your experience working with Linux on desktops and embedded devices",
                    "recommended_storage": "answer_memory",
                    "labels": [
                        "Describe your experience working with Linux on desktops and embedded devices"
                    ],
                    "platforms": ["Ashby"],
                    "related_prompt_count": 1,
                    "observed_count": 4,
                    "required_count": 4,
                },
                {
                    "group_key": "answer_memory:needs_user_confirmation:crypto",
                    "question": "Do you have blockchain/crypto experience?",
                    "recommended_storage": "answer_memory",
                    "labels": ["Do you have blockchain/crypto experience?"],
                    "platforms": ["Greenhouse"],
                    "related_prompt_count": 1,
                    "observed_count": 10,
                    "required_count": 10,
                },
                {
                    "group_key": "answer_memory:needs_user_confirmation:tools",
                    "question": "Please select the tools and technologies you have proficiency with using in your day-to-day work.",
                    "recommended_storage": "answer_memory",
                    "labels": [
                        "Please select the tools and technologies you have proficiency with using in your day-to-day work."
                    ],
                    "platforms": ["Lever"],
                    "related_prompt_count": 1,
                    "observed_count": 8,
                    "required_count": 8,
                },
                {
                    "group_key": "answer_memory:needs_user_confirmation:fedramp",
                    "question": "Do you have hands-on experience supporting FedRAMP High and/or DoD IL5 environments?",
                    "recommended_storage": "answer_memory",
                    "labels": [
                        "Do you have hands-on experience supporting FedRAMP High and/or DoD IL5 environments?"
                    ],
                    "platforms": ["Ashby"],
                    "related_prompt_count": 1,
                    "observed_count": 2,
                    "required_count": 2,
                },
                {
                    "group_key": "answer_memory:needs_user_confirmation:oncall",
                    "question": "This role includes an on-call rotation. Is this something you are comfortable with?",
                    "recommended_storage": "answer_memory",
                    "labels": [
                        "This role includes an on-call rotation. Is this something you are comfortable with?"
                    ],
                    "platforms": ["Lever"],
                    "related_prompt_count": 1,
                    "observed_count": 2,
                    "required_count": 2,
                },
                {
                    "group_key": "answer_memory:needs_user_confirmation:event",
                    "question": "If you attended an on-campus or virtual event, which did you attend?",
                    "recommended_storage": "answer_memory",
                    "labels": ["If you attended an on-campus or virtual event, which did you attend?"],
                    "platforms": ["Greenhouse"],
                    "related_prompt_count": 1,
                    "observed_count": 3,
                    "required_count": 3,
                },
                {
                    "group_key": "answer_memory:needs_user_confirmation:certification",
                    "question": "Do you possess any of these certifications?",
                    "recommended_storage": "answer_memory",
                    "labels": ["Do you possess any of these certifications?"],
                    "platforms": ["Ashby"],
                    "related_prompt_count": 1,
                    "observed_count": 2,
                    "required_count": 2,
                },
                {
                    "group_key": "answer_memory:needs_user_confirmation:perimeter",
                    "question": "What can you tell us about our infrastructure by examining our system’s perimeter? (URLs, DNS records, etc)",
                    "recommended_storage": "answer_memory",
                    "labels": [
                        "What can you tell us about our infrastructure by examining our system’s perimeter? (URLs, DNS records, etc)"
                    ],
                    "platforms": ["Lever"],
                    "related_prompt_count": 1,
                    "observed_count": 4,
                    "required_count": 4,
                },
                {
                    "group_key": "answer_memory:needs_user_confirmation:earliest_start",
                    "question": "What is your earliest possible starting date?",
                    "recommended_storage": "answer_memory",
                    "labels": ["What is your earliest possible starting date?"],
                    "platforms": ["Ashby"],
                    "related_prompt_count": 1,
                    "observed_count": 1,
                    "required_count": 1,
                },
                {
                    "group_key": "resume_facts:education_grading",
                    "question": "What GPA, grading system, ACT/SAT score, or 'not applicable' answer should automation use for education grading fields?",
                    "recommended_storage": "resume_facts",
                    "labels": ["What is your GPA?"],
                    "platforms": ["Greenhouse"],
                    "related_prompt_count": 1,
                    "observed_count": 8,
                    "required_count": 8,
                },
                {
                    "group_key": "answer_memory:needs_user_confirmation:startup_environment",
                    "question": "Have you worked in a startup environment in the past 5 years?",
                    "recommended_storage": "answer_memory",
                    "labels": ["Have you worked in a startup environment in the past 5 years?"],
                    "platforms": ["Greenhouse"],
                    "related_prompt_count": 1,
                    "observed_count": 2,
                    "required_count": 2,
                },
                {
                    "group_key": "answer_memory:needs_user_confirmation:startup_culture",
                    "question": "What aspects of startup culture resonate with you, and how do you believe they align with your working style?",
                    "recommended_storage": "answer_memory",
                    "labels": [
                        "What aspects of startup culture resonate with you, and how do you believe they align with your working style?"
                    ],
                    "platforms": ["Ashby"],
                    "related_prompt_count": 1,
                    "observed_count": 2,
                    "required_count": 2,
                },
                {
                    "group_key": "answer_memory:needs_user_confirmation:crypto_motivation",
                    "question": "What aspects of the cryptocurrency industry appeal to you, and how do they align with your career goals?",
                    "recommended_storage": "answer_memory",
                    "labels": [
                        "What aspects of the cryptocurrency industry appeal to you, and how do they align with your career goals?"
                    ],
                    "platforms": ["Ashby"],
                    "related_prompt_count": 1,
                    "observed_count": 2,
                    "required_count": 2,
                },
                {
                    "group_key": "answer_memory:needs_user_confirmation:platform_big_impact",
                    "question": "Are you a Platform Engineer looking to make a big impact on a mission-driven company? Do you enjoy architecting software that shapes an entire engineering organization? Do you thrive in high-autonomy startup environments?",
                    "recommended_storage": "answer_memory",
                    "labels": [
                        "Are you a Platform Engineer looking to make a big impact on a mission-driven company? Do you enjoy architecting software that shapes an entire engineering organization? Do you thrive in high-autonomy startup environments?"
                    ],
                    "platforms": ["LinkedIn"],
                    "related_prompt_count": 1,
                    "observed_count": 2,
                    "required_count": 2,
                },
                {
                    "group_key": "answer_memory:needs_user_confirmation:define_infra",
                    "question": "Do you want to define the infrastructure that powers one of the fastest-growing startups in history?",
                    "recommended_storage": "answer_memory",
                    "labels": [
                        "Do you want to define the infrastructure that powers one of the fastest-growing startups in history?"
                    ],
                    "platforms": ["LinkedIn"],
                    "related_prompt_count": 1,
                    "observed_count": 1,
                    "required_count": 1,
                },
                {
                    "group_key": "answer_memory:needs_user_confirmation:current_c2c",
                    "question": "What is your current C2C?",
                    "recommended_storage": "answer_memory",
                    "labels": ["What is your current C2C?"],
                    "platforms": ["Greenhouse"],
                    "related_prompt_count": 1,
                    "observed_count": 2,
                    "required_count": 2,
                },
                {
                    "group_key": "answer_memory:needs_user_confirmation:favorite_junk_food",
                    "question": "What's your favorite junk food?",
                    "recommended_storage": "answer_memory",
                    "labels": ["What's your favorite junk food?"],
                    "platforms": ["Ashby"],
                    "related_prompt_count": 1,
                    "observed_count": 2,
                    "required_count": 2,
                },
                {
                    "group_key": "answer_memory:needs_user_confirmation:favorite_restaurant",
                    "question": "What is your favorite restaurant?",
                    "recommended_storage": "answer_memory",
                    "labels": ["What is your favorite restaurant?"],
                    "platforms": ["Lever"],
                    "related_prompt_count": 1,
                    "observed_count": 1,
                    "required_count": 1,
                },
            ]
        }

        profile = CandidateProfile(
            name=self.profile.name,
            email=self.profile.email,
            phone=self.profile.phone,
            location=self.profile.location,
            target_titles=self.profile.target_titles,
            target_locations=self.profile.target_locations,
            remote_ok=self.profile.remote_ok,
            keywords=self.profile.keywords,
            blocklist=self.profile.blocklist,
            min_score=self.profile.min_score,
            resume_facts={
                **self.profile.resume_facts,
                "strongest_skills": "Python, Linux, Azure, SQL, Redis, MongoDB, and automation tooling",
                "current_role": "Operating Rocky Linux migration and Azure VM reliability work",
                "education": "MS in Computer Science and Software Engineering; BS in Computer Science",
            },
            question_answers={
                **self.profile.question_answers,
                "start_date": "I can start in about two months.",
                "compensation": "My expected compensation is $100,000+ base salary.",
            },
        )

        template = build_learning_task_template(readiness, profile=profile)
        tasks = {task["group_key"]: task for task in template["tasks"]}

        self.assertIn(
            "Current resume facts support",
            tasks["answer_memory:needs_user_confirmation:linux"]["suggested_answer"],
        )
        self.assertEqual(
            tasks["answer_memory:needs_user_confirmation:linux"]["suggested_answer_source"],
            "profile.resume_facts",
        )
        self.assertIn(
            "No confirmed blockchain or crypto experience",
            tasks["answer_memory:needs_user_confirmation:crypto"]["suggested_answer"],
        )
        self.assertEqual(
            tasks["answer_memory:needs_user_confirmation:crypto"]["suggested_answer_source"],
            "profile.resume_facts_absence",
        )
        self.assertIn(
            "Python",
            tasks["answer_memory:needs_user_confirmation:tools"]["suggested_answer"],
        )
        self.assertIn(
            "Linux",
            tasks["answer_memory:needs_user_confirmation:tools"]["suggested_answer"],
        )
        self.assertEqual(
            tasks["answer_memory:needs_user_confirmation:tools"]["suggested_answer_source"],
            "profile.resume_facts_skill_inventory",
        )
        self.assertIn(
            "No confirmed FedRAMP or DoD IL5 experience",
            tasks["answer_memory:needs_user_confirmation:fedramp"]["suggested_answer"],
        )
        self.assertIn(
            "Current resume facts support",
            tasks["answer_memory:needs_user_confirmation:oncall"]["suggested_answer"],
        )
        self.assertIn(
            "no specific campus or virtual event",
            tasks["answer_memory:needs_user_confirmation:event"]["suggested_answer"],
        )
        self.assertIn(
            "No confirmed relevant certification",
            tasks["answer_memory:needs_user_confirmation:certification"]["suggested_answer"],
        )
        self.assertIn(
            "public, non-invasive signals",
            tasks["answer_memory:needs_user_confirmation:perimeter"]["suggested_answer"],
        )
        self.assertEqual(
            tasks["answer_memory:needs_user_confirmation:earliest_start"]["suggested_answer"],
            "I can start in about two months.",
        )
        self.assertIn(
            "GPA/test scores are not included",
            tasks["resume_facts:education_grading"]["suggested_answer"],
        )
        self.assertIn(
            "No confirmed startup environment",
            tasks["answer_memory:needs_user_confirmation:startup_environment"]["suggested_answer"],
        )
        self.assertIn(
            "ownership",
            tasks["answer_memory:needs_user_confirmation:startup_culture"]["suggested_answer"].lower(),
        )
        self.assertIn(
            "infrastructure and reliability challenges",
            tasks["answer_memory:needs_user_confirmation:crypto_motivation"]["suggested_answer"],
        )
        self.assertIn(
            "platform reliability",
            tasks["answer_memory:needs_user_confirmation:platform_big_impact"]["suggested_answer"],
        )
        self.assertIn(
            "defining and operating infrastructure",
            tasks["answer_memory:needs_user_confirmation:define_infra"]["suggested_answer"],
        )
        self.assertIn(
            "prefer not to disclose current compensation",
            tasks["answer_memory:needs_user_confirmation:current_c2c"]["suggested_answer"],
        )
        self.assertIn(
            "$100,000+",
            tasks["answer_memory:needs_user_confirmation:current_c2c"]["suggested_answer"],
        )
        self.assertEqual(
            tasks["answer_memory:needs_user_confirmation:favorite_junk_food"]["suggested_answer"],
            "No strong preference.",
        )
        self.assertEqual(
            tasks["answer_memory:needs_user_confirmation:favorite_restaurant"]["suggested_answer"],
            "No strong preference.",
        )

    def test_direct_answers_cover_localized_compensation_and_years_questions(self) -> None:
        gaps = build_answer_gap_report(
            {
                "generated_at": "2026-05-23T00:00:00+00:00",
                "positions_observed_total": 1,
                "items": [
                    {
                        "label": "💰 Combien tu vas gagner chez SFEIR ?",
                        "normalized_label": "combien tu vas gagner chez sfeir",
                        "category": "compensation",
                        "automation_action": "auto_answer_from_memory",
                        "sensitivity": "standard_preference",
                        "required": True,
                        "platform": "Lever",
                        "source_file": "test.json",
                    },
                    {
                        "label": "Have you previously designed, deployed and maintained cloud infrastructure? If so, for how many years?",
                        "normalized_label": "have you previously designed deployed and maintained cloud infrastructure if so for how many years",
                        "category": "experience_years",
                        "automation_action": "auto_answer_from_memory",
                        "sensitivity": "standard_preference",
                        "required": True,
                        "platform": "Lever",
                        "source_file": "test.json",
                    },
                ],
            },
            profile=CandidateProfile(
                name=self.profile.name,
                email=self.profile.email,
                phone=self.profile.phone,
                location=self.profile.location,
                target_titles=self.profile.target_titles,
                target_locations=self.profile.target_locations,
                remote_ok=self.profile.remote_ok,
                keywords=self.profile.keywords,
                blocklist=self.profile.blocklist,
                min_score=self.profile.min_score,
                resume_facts=self.profile.resume_facts,
                question_answers={
                    **self.profile.question_answers,
                    "compensation": "$100,000+",
                    "years_experience": "4 years or less",
                },
            ),
        )

        self.assertEqual(gaps["coverage_counts"], {"covered_auto_answer": 2})

    def test_learning_approval_pack_groups_tasks_by_review_action(self) -> None:
        learning_tasks = {
            "task_count": 4,
            "tasks": [
                {
                    "group_key": "answer_memory:employment_history:default_policy",
                    "question": "Should automation answer no to prior-employer questions?",
                    "recommended_storage": "answer_memory",
                    "answer_scope": "category_default_policy",
                    "suggested_answer": "No unless an exception is confirmed.",
                    "suggested_answer_source": "category_default_policy_template",
                    "suggestion_confidence": "medium",
                    "approval_risk": "medium",
                    "labels": ["Have you worked with us before?"],
                    "platforms": ["Greenhouse"],
                    "related_prompt_count": 2,
                    "observed_count": 5,
                    "required_count": 5,
                    "persist_allowed": True,
                },
                {
                    "group_key": "profile:zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "recommended_storage": "profile",
                    "answer_scope": "profile_field",
                    "suggested_answer": "",
                    "suggested_answer_source": "needs_user",
                    "approval_risk": "needs_review",
                    "labels": ["Zip Code"],
                    "platforms": ["Ashby"],
                    "related_prompt_count": 1,
                    "observed_count": 3,
                    "required_count": 3,
                    "persist_allowed": True,
                },
                {
                    "group_key": "answer_memory:citizenship_status:default_policy",
                    "question": "What citizenship answers should automation use?",
                    "recommended_storage": "answer_memory",
                    "answer_scope": "category_default_policy",
                    "suggested_answer_source": "requires_exact_user_confirmation",
                    "approval_risk": "high",
                    "labels": ["Are you a U.S. citizen?"],
                    "platforms": ["Greenhouse"],
                    "related_prompt_count": 1,
                    "observed_count": 2,
                    "required_count": 2,
                    "persist_allowed": True,
                },
                {
                    "group_key": "supervised_confirmation:policy_acknowledgement",
                    "question": "May automation mark applicant privacy acknowledgement?",
                    "recommended_storage": "supervised_confirmation",
                    "answer_scope": "supervised_only",
                    "suggested_answer": "",
                    "approval_risk": "needs_review",
                    "labels": ["Privacy policy"],
                    "platforms": ["Lever"],
                    "related_prompt_count": 1,
                    "observed_count": 1,
                    "required_count": 1,
                    "persist_allowed": False,
                },
            ],
        }
        readiness = {
            "readiness_counts": {"needs_learning": 2, "supervised_ready": 1},
            "learning_queue_count": 10,
            "manual_gates": [
                {
                    "coverage_status": "final_submit_confirmation",
                    "label": "Submit application",
                    "category": "final_submit",
                    "platforms": ["Greenhouse"],
                    "observed_count": 7,
                    "required_count": 0,
                    "recommended_storage": "do_not_automate",
                    "next_action": "human must approve final submit",
                }
            ],
        }

        pack = build_learning_approval_pack(learning_tasks, readiness)
        buckets = {row["bucket"]: row for row in pack["buckets"]}

        self.assertEqual(pack["summary"]["task_count"], 4)
        self.assertEqual(pack["summary"]["critical_input_count"], 4)
        self.assertEqual(pack["summary"]["critical_persistable_input_count"], 3)
        self.assertEqual(pack["summary"]["critical_supervised_only_count"], 1)
        self.assertEqual(pack["summary"]["draft_answer_count"], 1)
        self.assertEqual(pack["summary"]["missing_user_answer_count"], 3)
        self.assertEqual(pack["summary"]["exact_user_confirmation_count"], 1)
        self.assertEqual(pack["summary"]["manual_gate_count"], 1)
        self.assertEqual(
            [row["input_type"] for row in pack["critical_inputs"]],
            [
                "default_policy_review",
                "profile_or_resume_fact",
                "high_risk_exact_confirmation",
                "supervised_browser_review_only",
            ],
        )
        self.assertEqual(pack["critical_inputs"][0]["draft_answer"], "No unless an exception is confirmed.")
        self.assertEqual(buckets["default_policy_review"]["task_count"], 1)
        self.assertEqual(buckets["profile_or_resume_fact"]["task_count"], 1)
        self.assertEqual(buckets["exact_user_confirmation"]["task_count"], 1)
        self.assertEqual(buckets["supervised_only"]["task_count"], 1)
        markdown = render_learning_approval_pack_markdown(pack)
        self.assertIn("Learning Approval Pack", markdown)
        self.assertIn("Review reusable default policies", markdown)
        self.assertIn("Missing Critical Inputs", markdown)
        self.assertIn("user answer:", markdown)

        with tempfile.TemporaryDirectory() as temp_dir:
            json_output = Path(temp_dir) / "approval.json"
            markdown_output = Path(temp_dir) / "approval.md"
            written = write_learning_approval_pack(learning_tasks, readiness, json_output, markdown_output)

            self.assertEqual(written["summary"]["task_count"], 4)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertIn("Learning Approval Pack", markdown_output.read_text())

    def test_write_position_readiness_report_outputs_json_and_markdown(self) -> None:
        research = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "positions": [{"position_key": "linkedin:1", "platform": "LinkedIn"}],
            "items": [],
        }
        gaps = {"generated_at": "2026-05-22T00:00:00+00:00", "prompt_statuses": []}
        with tempfile.TemporaryDirectory() as temp_dir:
            json_output = Path(temp_dir) / "readiness.json"
            markdown_output = Path(temp_dir) / "readiness.md"

            report = write_position_readiness_report(research, gaps, json_output, markdown_output)

            self.assertEqual(report["readiness_counts"]["needs_research"], 1)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertIn("Application Automation Readiness", markdown_output.read_text())

    def test_position_readiness_skips_closed_registry_jobs(self) -> None:
        research = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "positions": [
                {
                    "position_key": "linkedin:2",
                    "platform": "LinkedIn",
                    "job_id": "2",
                    "company": "ClosedCo",
                    "title": "SRE",
                    "apply_url": "https://www.linkedin.com/jobs/view/2/",
                }
            ],
            "items": [
                {
                    "position_key": "linkedin:2",
                    "label": "Are you authorized to work in the United States?",
                    "normalized_label": "authorized work united states",
                    "category": "work_authorization",
                    "required": True,
                }
            ],
        }
        gaps = {
            "prompt_statuses": [
                {
                    "label": "Are you authorized to work in the United States?",
                    "normalized_label": "authorized work united states",
                    "coverage_status": "covered_auto_answer",
                    "observed_count": 1,
                    "required_count": 1,
                }
            ]
        }
        closed_jobs = {
            "jobs": [
                {
                    "key": "linkedin:2",
                    "status": "CLOSED",
                    "reason": "No longer accepting applications",
                }
            ]
        }

        report = build_position_readiness_report(research, gaps, closed_jobs=closed_jobs)

        self.assertEqual(report["readiness_counts"]["closed_skip"], 1)
        self.assertEqual(report["positions"][0]["readiness"], "closed_skip")
        self.assertFalse(report["positions"][0]["ready_for_autofill"])

    def test_form_fill_plan_maps_fields_to_actions_without_values_by_default(self) -> None:
        profile = CandidateProfile(
            name="Alan Jiang",
            email="alan@example.com",
            phone="555-0100",
            location="Bellevue, WA",
            target_titles=["SRE"],
            target_locations=["United States"],
            remote_ok=True,
            keywords=[],
            blocklist=[],
            min_score=1,
            resume_facts={
                "professional_summary": "SRE",
                "strongest_skills": "Python",
                "impact_example": "Automation",
                "education": "MS Computer Science",
            },
            question_answers={"authorization": "Yes"},
        )
        snapshot = {
            "title": "Application",
            "url": "https://jobs.ashbyhq.com/example/1",
            "fields": [
                {"i": 1, "label": "Legal Name", "tag": "INPUT", "required": True},
                {"i": 2, "label": "Email", "tag": "INPUT", "required": True},
                {"i": 3, "label": "Resume", "tag": "INPUT", "type": "file", "required": True},
                {
                    "i": 4,
                    "label": "Are you authorized to work in the United States?",
                    "tag": "INPUT",
                    "required": True,
                },
                {"i": 5, "label": "Gender", "tag": "INPUT", "required": False},
                {"i": 6, "name": "g-recaptcha-response", "tag": "TEXTAREA"},
            ],
            "buttons": [{"i": 7, "text": "Submit application", "tag": "BUTTON"}],
        }

        plan = build_form_fill_plan(snapshot, profile=profile, answer_memory=None)

        self.assertEqual(plan["status_counts"]["ready"], 3)
        self.assertEqual(plan["status_counts"]["missing_local_material"], 1)
        self.assertEqual(plan["status_counts"]["sensitive_not_stored"], 1)
        self.assertEqual(plan["status_counts"]["manual_security_step"], 1)
        self.assertEqual(plan["status_counts"]["final_submit_confirmation"], 1)
        self.assertNotIn("value", plan["steps"][0])
        markdown = render_form_fill_plan_markdown(plan)
        self.assertIn("Form Fill Plan", markdown)

    def test_write_form_fill_plan_outputs_json_and_markdown(self) -> None:
        snapshot = {
            "title": "Application",
            "url": "https://job-boards.greenhouse.io/example/jobs/1",
            "fields": [{"i": 1, "label": "Email", "tag": "INPUT", "required": True}],
            "buttons": [],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_path = Path(temp_dir) / "snapshot.json"
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
            json_output = Path(temp_dir) / "plan.json"
            markdown_output = Path(temp_dir) / "plan.md"

            plan = write_form_fill_plan(snapshot_path, json_output, markdown_output)

            self.assertEqual(plan["step_count"], 1)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertIn("Form Fill Plan", markdown_output.read_text())

    def test_apply_run_audit_stops_before_submit_and_security_steps(self) -> None:
        plan = {
            "title": "Application",
            "url": "https://jobs.ashbyhq.com/example/1",
            "platform": "Ashby",
            "steps": [
                {
                    "field_index": 1,
                    "item_type": "field",
                    "action": "fill",
                    "status": "ready",
                    "label": "Email",
                    "category": "profile_identity",
                    "value_source": "profile.email",
                },
                {
                    "field_index": 2,
                    "item_type": "field",
                    "action": "manual_security",
                    "status": "manual_security_step",
                    "label": "g-recaptcha-response",
                    "category": "security_verification",
                },
                {
                    "field_index": 3,
                    "item_type": "button",
                    "action": "submit_gate",
                    "status": "final_submit_confirmation",
                    "label": "Submit application",
                    "category": "final_submit",
                },
            ],
        }

        audit = build_apply_run_audit(plan)

        self.assertEqual(audit["status"], "autofill_ready_with_supervised_gates")
        self.assertTrue(audit["autofill_allowed"])
        self.assertFalse(audit["final_submit_allowed"])
        self.assertFalse(audit["would_submit"])
        self.assertEqual(audit["automation_step_count"], 1)
        self.assertEqual(audit["manual_gate_count"], 2)
        markdown = render_apply_run_audit_markdown(audit)
        self.assertIn("Apply Run Audit", markdown)
        self.assertIn("final_submit_confirmation", markdown)

    def test_apply_run_audit_skips_closed_page_text(self) -> None:
        plan = {
            "title": "Closed role",
            "url": "https://www.linkedin.com/jobs/view/123/",
            "platform": "LinkedIn",
            "steps": [
                {
                    "field_index": 1,
                    "item_type": "field",
                    "action": "fill",
                    "status": "ready",
                    "label": "Email",
                    "category": "profile_identity",
                }
            ],
        }

        audit = build_apply_run_audit(plan, page_text="No longer accepting applications")

        self.assertEqual(audit["status"], "closed_skip")
        self.assertFalse(audit["autofill_allowed"])
        self.assertEqual(audit["automation_step_count"], 0)
        self.assertEqual(audit["closed_reason"], "closed:no_longer_accepting_applications")

    def test_write_apply_run_audit_outputs_json_and_markdown(self) -> None:
        plan = {
            "title": "Application",
            "url": "https://job-boards.greenhouse.io/example/jobs/1",
            "platform": "Greenhouse",
            "steps": [
                {
                    "field_index": 1,
                    "item_type": "field",
                    "action": "answer",
                    "status": "missing_answer",
                    "label": "Have you worked here before?",
                    "category": "employment_history",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            plan_path = Path(temp_dir) / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            json_output = Path(temp_dir) / "audit.json"
            markdown_output = Path(temp_dir) / "audit.md"

            audit = write_apply_run_audit(plan_path, json_output, markdown_output)

            self.assertEqual(audit["status"], "blocked_missing_inputs")
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertIn("Apply Run Audit", markdown_output.read_text())

    def test_browser_action_manifest_builds_safe_actions_and_stops(self) -> None:
        plan = {
            "title": "Application",
            "url": "https://job-boards.greenhouse.io/example/jobs/1",
            "platform": "Greenhouse",
            "steps": [
                {
                    "field_index": 1,
                    "item_type": "field",
                    "tag": "INPUT",
                    "type": "email",
                    "name": "email",
                    "id": "email",
                    "action": "fill",
                    "status": "ready",
                    "label": "Email",
                    "required": True,
                    "category": "profile_identity",
                    "value_source": "profile.email",
                },
                {
                    "field_index": 2,
                    "item_type": "field",
                    "tag": "INPUT",
                    "type": "file",
                    "name": "resume",
                    "action": "upload",
                    "status": "ready",
                    "label": "Resume",
                    "required": True,
                    "category": "resume_upload",
                    "value_source": "profile.question_answers.resume_path",
                },
                {
                    "field_index": 3,
                    "item_type": "button",
                    "tag": "BUTTON",
                    "action": "submit_gate",
                    "status": "final_submit_confirmation",
                    "label": "Submit application",
                    "category": "final_submit",
                },
                {
                    "field_index": 4,
                    "item_type": "field",
                    "tag": "SELECT",
                    "action": "manual_sensitive",
                    "status": "sensitive_not_stored",
                    "label": "Race/Ethnicity",
                    "category": "protected_class",
                },
            ],
        }

        manifest = build_browser_action_manifest(plan)

        self.assertEqual(manifest["status"], "autofill_ready_with_supervised_gates")
        self.assertFalse(manifest["real_platform_submission"])
        self.assertFalse(manifest["final_submit_allowed"])
        self.assertFalse(manifest["would_submit"])
        self.assertEqual(manifest["action_count"], 2)
        self.assertEqual(manifest["stop_action_count"], 2)
        actions = manifest["browser_actions"]
        self.assertEqual(actions[0]["browser_action"], "fill")
        self.assertIn(
            "#email",
            [candidate["selector"] for candidate in actions[0]["selector_candidates"]],
        )
        self.assertEqual(actions[1]["browser_action"], "upload_file")
        self.assertTrue(actions[1]["requires_file"])
        self.assertIn(
            'input[name="resume"]',
            [candidate["selector"] for candidate in actions[1]["selector_candidates"]],
        )
        self.assertNotIn(
            "submit_gate",
            [action["plan_action"] for action in manifest["browser_actions"]],
        )
        markdown = render_browser_action_manifest_markdown(manifest)
        self.assertIn("Browser Action Manifest", markdown)
        self.assertIn("final_submit_confirmation", markdown)

    def test_browser_action_manifest_skips_closed_page_text(self) -> None:
        plan = {
            "title": "Closed role",
            "url": "https://www.linkedin.com/jobs/view/123/",
            "platform": "LinkedIn",
            "steps": [
                {
                    "field_index": 1,
                    "item_type": "field",
                    "tag": "INPUT",
                    "type": "email",
                    "id": "email",
                    "action": "fill",
                    "status": "ready",
                    "label": "Email",
                    "category": "profile_identity",
                }
            ],
        }

        manifest = build_browser_action_manifest(
            plan,
            page_text="No longer accepting applications",
        )

        self.assertEqual(manifest["status"], "closed_skip")
        self.assertEqual(manifest["action_count"], 0)
        self.assertEqual(manifest["stop_action_count"], 1)
        self.assertEqual(manifest["stop_actions"][0]["status"], "closed_skip")

    def test_autofill_batch_plan_selects_ready_positions_without_real_submit(self) -> None:
        profile = CandidateProfile(
            name="Alan Jiang",
            email="alan@example.com",
            phone="555-0100",
            location="Bellevue, WA",
            target_titles=["SRE"],
            target_locations=["United States"],
            remote_ok=True,
            keywords=[],
            blocklist=[],
            min_score=1,
            resume_facts={"professional_summary": "SRE"},
            question_answers={"authorization": "Yes"},
        )
        research = {
            "positions": [
                {
                    "position_key": "ashby:example:1",
                    "platform": "Ashby",
                    "company": "Example",
                    "title": "Site Reliability Engineer",
                    "role_family": "SRE",
                    "apply_url": "https://jobs.ashbyhq.com/example/1",
                },
                {
                    "position_key": "greenhouse:closed:1",
                    "platform": "Greenhouse",
                    "company": "Closed Co",
                    "title": "Platform Engineer",
                    "role_family": "Platform",
                    "apply_url": "https://job-boards.greenhouse.io/closed/jobs/1",
                },
            ],
            "items": [
                {
                    "position_key": "ashby:example:1",
                    "label": "Email",
                    "normalized_label": "email",
                    "category": "profile_identity",
                    "automation_action": "auto_fill_from_profile",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "test",
                },
                {
                    "position_key": "ashby:example:1",
                    "label": "Submit application",
                    "normalized_label": "submit application",
                    "category": "final_submit",
                    "automation_action": "submit_gate",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "test",
                },
                {
                    "position_key": "greenhouse:closed:1",
                    "label": "Email",
                    "normalized_label": "email",
                    "category": "profile_identity",
                    "automation_action": "auto_fill_from_profile",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "test",
                },
            ],
        }
        readiness = {
            "positions": [
                {
                    **research["positions"][0],
                    "readiness": "supervised_ready",
                    "ready_for_autofill": True,
                    "required_prompt_count": 2,
                    "covered_prompt_count": 1,
                },
                {
                    **research["positions"][1],
                    "readiness": "closed_skip",
                    "ready_for_autofill": True,
                    "required_prompt_count": 1,
                    "covered_prompt_count": 1,
                },
                {
                    "position_key": "lever:blocked:1",
                    "platform": "Lever",
                    "company": "Blocked Co",
                    "title": "DevOps Engineer",
                    "role_family": "DevOps",
                    "apply_url": "https://jobs.lever.co/blocked/1",
                    "readiness": "needs_learning",
                    "ready_for_autofill": False,
                },
            ]
        }
        closed_jobs = {
            "version": 1,
            "jobs": [
                {
                    "status": "CLOSED",
                    "key": "url:https://job-boards.greenhouse.io/closed/jobs/1",
                    "apply_url": "https://job-boards.greenhouse.io/closed/jobs/1",
                    "reason": "No longer accepting applications",
                }
            ],
        }

        report = build_autofill_batch_plan(
            research,
            readiness,
            profile=profile,
            answer_memory={"version": 1, "answers": []},
            closed_jobs=closed_jobs,
            limit=10,
        )

        self.assertEqual(report["selected_count"], 1)
        self.assertEqual(report["selected_autofill_allowed_count"], 1)
        self.assertEqual(report["excluded_closed_position_count"], 1)
        self.assertEqual(report["skipped_not_ready_position_count"], 1)
        self.assertEqual(report["would_submit_count"], 0)
        self.assertFalse(report["real_platform_submission"])
        self.assertEqual(report["local_synthetic_submit_count"], 1)
        self.assertTrue(report["local_synthetic_submit_achieved"])
        self.assertEqual(report["local_synthetic_submit_selector_miss_count"], 0)
        self.assertEqual(report["positions"][0]["manifest_status"], "autofill_ready_with_supervised_gates")
        self.assertEqual(report["positions"][0]["local_synthetic_submit_count"], 1)
        self.assertEqual(report["positions"][0]["local_synthetic_submit_outcome"], "submitted_local_synthetic")
        self.assertEqual(report["positions"][0]["stop_action_summaries"][0]["status"], "final_submit_confirmation")
        self.assertEqual(report["selected_stop_actions"][0]["label"], "Submit application")
        self.assertEqual(report["selected_stop_action_counts"]["final_submit_confirmation | Submit application"], 1)
        self.assertIn("Autofill Batch Plan", render_autofill_batch_plan_markdown(report))
        self.assertIn("Selected Stop Actions", render_autofill_batch_plan_markdown(report))
        self.assertIn("Local synthetic submit achieved: true", render_autofill_batch_plan_markdown(report))
        self.assertIn("Autofill Batch Plan", render_autofill_batch_plan_html(report))
        self.assertIn("Selected Stop Actions", render_autofill_batch_plan_html(report))

        with tempfile.TemporaryDirectory() as temp_dir:
            json_output = Path(temp_dir) / "autofill_batch.json"
            markdown_output = Path(temp_dir) / "autofill_batch.md"
            html_output = Path(temp_dir) / "autofill_batch.html"
            written = write_autofill_batch_plan(
                research,
                readiness,
                json_output,
                markdown_output,
                html_output,
                profile=profile,
                answer_memory={"version": 1, "answers": []},
                closed_jobs=closed_jobs,
            )
            self.assertEqual(written["selected_count"], 1)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertTrue(html_output.exists())

    def test_autofill_batch_prefers_lower_stop_positions_inside_group(self) -> None:
        profile = CandidateProfile(
            name="Alan Jiang",
            email="alan@example.com",
            phone="555-0100",
            location="Bellevue, WA",
            target_titles=["SRE"],
            target_locations=["United States"],
            remote_ok=True,
            keywords=[],
            blocklist=[],
            min_score=1,
            resume_facts={"professional_summary": "SRE"},
            question_answers={},
        )
        positions = [
            {
                "position_key": "ashby:extra-stop:1",
                "platform": "Ashby",
                "company": "A Co",
                "title": "Site Reliability Engineer",
                "role_family": "SRE",
                "apply_url": "https://jobs.ashbyhq.com/a/1",
            },
            {
                "position_key": "ashby:clean:1",
                "platform": "Ashby",
                "company": "B Co",
                "title": "Site Reliability Engineer",
                "role_family": "SRE",
                "apply_url": "https://jobs.ashbyhq.com/b/1",
            },
        ]
        research = {
            "positions": positions,
            "items": [
                {
                    "position_key": "ashby:extra-stop:1",
                    "label": "Email",
                    "category": "profile_identity",
                    "automation_action": "auto_fill_from_profile",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "test",
                },
                {
                    "position_key": "ashby:extra-stop:1",
                    "label": "Gender",
                    "category": "protected_class_self_id",
                    "automation_action": "do_not_store_sensitive",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "test",
                },
                {
                    "position_key": "ashby:extra-stop:1",
                    "label": "Submit application",
                    "category": "final_submit",
                    "automation_action": "submit_gate",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "test",
                },
                {
                    "position_key": "ashby:clean:1",
                    "label": "Email",
                    "category": "profile_identity",
                    "automation_action": "auto_fill_from_profile",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "test",
                },
                {
                    "position_key": "ashby:clean:1",
                    "label": "Submit application",
                    "category": "final_submit",
                    "automation_action": "submit_gate",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "test",
                },
            ],
        }
        readiness = {
            "positions": [
                {
                    **positions[0],
                    "readiness": "supervised_ready",
                    "ready_for_autofill": True,
                    "required_prompt_count": 3,
                    "covered_prompt_count": 2,
                },
                {
                    **positions[1],
                    "readiness": "supervised_ready",
                    "ready_for_autofill": True,
                    "required_prompt_count": 2,
                    "covered_prompt_count": 1,
                },
            ]
        }

        report = build_autofill_batch_plan(
            research,
            readiness,
            profile=profile,
            answer_memory={"version": 1, "answers": []},
            closed_jobs={"version": 1, "jobs": []},
            limit=1,
        )

        self.assertEqual(report["selected_count"], 1)
        self.assertEqual(report["positions"][0]["position_key"], "ashby:clean:1")
        self.assertEqual(report["stop_action_count"], 1)
        self.assertEqual(report["local_synthetic_submit_count"], 1)
        self.assertEqual(report["selected_stop_actions"][0]["status"], "final_submit_confirmation")

    def test_autofill_batch_prefers_clean_group_when_limit_is_tight(self) -> None:
        profile = CandidateProfile(
            name="Alan Jiang",
            email="alan@example.com",
            phone="555-0100",
            location="Bellevue, WA",
            target_titles=["SRE"],
            target_locations=["United States"],
            remote_ok=True,
            keywords=[],
            blocklist=[],
            min_score=1,
            resume_facts={"professional_summary": "SRE"},
            question_answers={},
        )
        positions = [
            {
                "position_key": "ashby:dirty:1",
                "platform": "Ashby",
                "company": "A Co",
                "title": "Site Reliability Engineer",
                "role_family": "SRE",
                "apply_url": "https://jobs.ashbyhq.com/a/1",
            },
            {
                "position_key": "lever:clean:1",
                "platform": "Lever",
                "company": "B Co",
                "title": "Platform Engineer",
                "role_family": "Platform",
                "apply_url": "https://jobs.lever.co/b/1",
            },
        ]
        research = {
            "positions": positions,
            "items": [
                {
                    "position_key": "ashby:dirty:1",
                    "label": "Email",
                    "category": "profile_identity",
                    "automation_action": "auto_fill_from_profile",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "test",
                },
                {
                    "position_key": "ashby:dirty:1",
                    "label": "Gender",
                    "category": "protected_class_self_id",
                    "automation_action": "do_not_store_sensitive",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "test",
                },
                {
                    "position_key": "ashby:dirty:1",
                    "label": "Submit application",
                    "category": "final_submit",
                    "automation_action": "submit_gate",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "test",
                },
                {
                    "position_key": "lever:clean:1",
                    "label": "Email",
                    "category": "profile_identity",
                    "automation_action": "auto_fill_from_profile",
                    "required": True,
                    "platform": "Lever",
                    "source_file": "test",
                },
                {
                    "position_key": "lever:clean:1",
                    "label": "Submit application",
                    "category": "final_submit",
                    "automation_action": "submit_gate",
                    "required": True,
                    "platform": "Lever",
                    "source_file": "test",
                },
            ],
        }
        readiness = {
            "positions": [
                {
                    **positions[0],
                    "readiness": "supervised_ready",
                    "ready_for_autofill": True,
                    "required_prompt_count": 3,
                    "covered_prompt_count": 2,
                },
                {
                    **positions[1],
                    "readiness": "supervised_ready",
                    "ready_for_autofill": True,
                    "required_prompt_count": 2,
                    "covered_prompt_count": 1,
                },
            ]
        }

        report = build_autofill_batch_plan(
            research,
            readiness,
            profile=profile,
            answer_memory={"version": 1, "answers": []},
            closed_jobs={"version": 1, "jobs": []},
            limit=1,
        )

        self.assertEqual(report["selected_count"], 1)
        self.assertEqual(report["positions"][0]["position_key"], "lever:clean:1")
        self.assertEqual(report["stop_action_count"], 1)

    def test_autofill_batch_can_exclude_unresolved_final_answer_positions(self) -> None:
        profile = CandidateProfile(
            name="Alan Jiang",
            email="alan@example.com",
            phone="555-0100",
            location="Bellevue, WA",
            target_titles=["SRE"],
            target_locations=["United States"],
            remote_ok=True,
            keywords=[],
            blocklist=[],
            min_score=1,
            resume_facts={"professional_summary": "SRE"},
            question_answers={},
        )
        positions = [
            {
                "position_key": "ashby:citizenship:1",
                "platform": "Ashby",
                "company": "A Co",
                "title": "Site Reliability Engineer",
                "role_family": "SRE",
                "apply_url": "https://jobs.ashbyhq.com/a/1",
            },
            {
                "position_key": "greenhouse:zip:1",
                "platform": "Greenhouse",
                "company": "B Co",
                "title": "Platform Engineer",
                "role_family": "Platform",
                "apply_url": "https://job-boards.greenhouse.io/b/jobs/1",
            },
            {
                "position_key": "lever:clean:1",
                "platform": "Lever",
                "company": "C Co",
                "title": "DevOps Engineer",
                "role_family": "DevOps",
                "apply_url": "https://jobs.lever.co/c/1",
            },
        ]
        research = {
            "positions": positions,
            "items": [
                {
                    "position_key": "ashby:citizenship:1",
                    "label": "Are you a U.S. Citizen?",
                    "category": "citizenship_status",
                    "automation_action": "human_review_required",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "test",
                },
                {
                    "position_key": "ashby:citizenship:1",
                    "label": "Submit application",
                    "category": "final_submit",
                    "automation_action": "submit_gate",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "test",
                },
                {
                    "position_key": "greenhouse:zip:1",
                    "label": "Zip Code",
                    "category": "profile_identity",
                    "automation_action": "auto_fill_from_profile",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "test",
                },
                {
                    "position_key": "greenhouse:zip:1",
                    "label": "Submit application",
                    "category": "final_submit",
                    "automation_action": "submit_gate",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "test",
                },
                {
                    "position_key": "lever:clean:1",
                    "label": "Email",
                    "category": "profile_identity",
                    "automation_action": "auto_fill_from_profile",
                    "required": True,
                    "platform": "Lever",
                    "source_file": "test",
                },
                {
                    "position_key": "lever:clean:1",
                    "label": "Submit application",
                    "category": "final_submit",
                    "automation_action": "submit_gate",
                    "required": True,
                    "platform": "Lever",
                    "source_file": "test",
                },
            ],
        }
        readiness = {
            "positions": [
                {
                    **position,
                    "readiness": "supervised_ready",
                    "ready_for_autofill": True,
                    "required_prompt_count": 2,
                    "covered_prompt_count": 1,
                }
                for position in positions
            ]
        }

        report = build_autofill_batch_plan(
            research,
            readiness,
            profile=profile,
            answer_memory={"version": 1, "answers": []},
            closed_jobs={"version": 1, "jobs": []},
            limit=2,
            avoid_final_answer_aliases=["citizenship_status", "zip_or_postal_code"],
        )

        self.assertEqual(report["requested_count"], 2)
        self.assertEqual(report["selected_count"], 1)
        self.assertEqual(report["positions"][0]["position_key"], "lever:clean:1")
        self.assertEqual(report["excluded_unresolved_final_answer_position_count"], 2)
        self.assertEqual(
            report["excluded_unresolved_final_answer_alias_counts"],
            {"citizenship_status": 1, "zip_or_postal_code": 1},
        )
        self.assertEqual(
            {
                row["position_key"]
                for row in report["excluded_unresolved_final_answer_positions"]
            },
            {"ashby:citizenship:1", "greenhouse:zip:1"},
        )
        self.assertIn("Unresolved final-answer positions excluded: 2", render_autofill_batch_plan_markdown(report))

    def test_write_browser_action_manifest_outputs_reports(self) -> None:
        plan = {
            "title": "Application",
            "url": "https://jobs.ashbyhq.com/example/1",
            "platform": "Ashby",
            "steps": [
                {
                    "field_index": 1,
                    "item_type": "field",
                    "tag": "INPUT",
                    "type": "text",
                    "name": "name",
                    "action": "fill",
                    "status": "ready",
                    "label": "Legal Name",
                    "category": "profile_identity",
                    "value_source": "profile.name",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            plan_path = Path(temp_dir) / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            json_output = Path(temp_dir) / "manifest.json"
            markdown_output = Path(temp_dir) / "manifest.md"

            manifest = write_browser_action_manifest(plan_path, json_output, markdown_output)

            self.assertEqual(manifest["action_count"], 1)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertIn("Browser Action Manifest", markdown_output.read_text())

    def test_browser_dom_execution_plan_blocks_remote_targets(self) -> None:
        manifest = {
            "title": "Application",
            "url": "https://www.linkedin.com/jobs/view/123/",
            "platform": "LinkedIn",
            "status": "autofill_ready",
            "browser_actions": [
                {
                    "browser_action": "fill",
                    "label": "Email",
                    "safe_to_execute": True,
                }
            ],
            "stop_actions": [],
        }

        plan = build_browser_dom_execution_plan(
            manifest,
            "https://www.linkedin.com/jobs/view/123/",
        )

        self.assertFalse(is_safe_browser_execution_target("https://www.linkedin.com/jobs/view/123/"))
        self.assertTrue(is_safe_browser_execution_target("file:///tmp/application.html"))
        self.assertTrue(is_safe_browser_execution_target("http://localhost:8000/application.html"))
        self.assertFalse(plan["execution_allowed"])
        self.assertEqual(plan["safety_status"], "blocked_nonlocal_target")
        self.assertEqual(plan["browser_action_count"], 0)
        self.assertEqual(plan["stop_actions"][0]["status"], "safety_block")
        self.assertFalse(plan["would_submit"])
        markdown = render_browser_dom_execution_plan_markdown(plan)
        self.assertIn("Browser DOM Execution Plan", markdown)
        self.assertIn("blocked_nonlocal_target", markdown)

    def test_write_browser_dom_harness_outputs_local_html_and_runner(self) -> None:
        snapshot = {
            "title": "Application",
            "url": "https://job-boards.greenhouse.io/example/jobs/1",
            "page_text": "Apply locally",
            "fields": [
                {"i": 1, "tag": "INPUT", "type": "email", "id": "email", "label": "Email"},
                {"i": 2, "tag": "INPUT", "type": "file", "name": "resume", "label": "Resume"},
            ],
            "buttons": [{"i": 99, "tag": "BUTTON", "text": "Submit application"}],
        }
        plan = {
            "title": snapshot["title"],
            "url": snapshot["url"],
            "platform": "Greenhouse",
            "steps": [
                {
                    "field_index": 1,
                    "item_type": "field",
                    "tag": "INPUT",
                    "type": "email",
                    "id": "email",
                    "action": "fill",
                    "status": "ready",
                    "label": "Email",
                    "category": "profile_identity",
                    "value_source": "profile.email",
                },
                {
                    "field_index": 2,
                    "item_type": "field",
                    "tag": "INPUT",
                    "type": "file",
                    "name": "resume",
                    "action": "upload",
                    "status": "ready",
                    "label": "Resume",
                    "category": "resume_upload",
                    "value_source": "profile.question_answers.resume_path",
                },
                {
                    "field_index": 99,
                    "item_type": "button",
                    "tag": "BUTTON",
                    "action": "submit_gate",
                    "status": "final_submit_confirmation",
                    "label": "Submit application",
                    "category": "final_submit",
                },
            ],
        }
        manifest = build_browser_action_manifest(plan)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "manifest.json"
            snapshot_path = root / "snapshot.json"
            html_output = root / "harness.html"
            script_output = root / "runner.js"
            json_output = root / "dom_plan.json"
            markdown_output = root / "dom_plan.md"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

            dom_plan = write_browser_dom_harness(
                manifest_path,
                snapshot_path,
                html_output,
                script_output,
                json_output,
                markdown_output,
            )

            self.assertTrue(dom_plan["execution_allowed"])
            self.assertEqual(dom_plan["safety_status"], "allowed_local_target")
            self.assertEqual(dom_plan["browser_action_count"], 2)
            self.assertFalse(dom_plan["would_submit"])
            html_text = html_output.read_text(encoding="utf-8")
            script_text = script_output.read_text(encoding="utf-8")
            self.assertIn('data-field-index="1"', html_text)
            self.assertIn('data-item-type="field"', html_text)
            self.assertIn('data-item-type="button"', html_text)
            self.assertIn('data-label="Submit application"', html_text)
            self.assertIn("window.__JOB_APPLY_RUNNER_RESULT__", html_text)
            self.assertIn("actualSubmitCount: 0", script_text)
            self.assertNotIn(".submit(", script_text)
            self.assertIn("Browser DOM Execution Plan", markdown_output.read_text(encoding="utf-8"))

    def test_synthetic_application_html_and_runner_script_are_safe(self) -> None:
        snapshot = {
            "title": "Local test",
            "fields": [
                {"i": 1, "tag": "INPUT", "type": "email", "id": "email", "label": "Email"},
            ],
            "buttons": [{"i": 99, "tag": "BUTTON", "text": "Submit application"}],
        }
        manifest = {
            "status": "autofill_ready",
            "browser_actions": [
                {
                    "browser_action": "fill",
                    "field_index": 1,
                    "label": "Email",
                    "selector_candidates": [{"strategy": "css", "selector": "#email"}],
                    "value_source": "profile.email",
                    "safe_to_execute": True,
                }
            ],
            "stop_actions": [{"status": "final_submit_confirmation", "label": "Submit application"}],
        }

        script = build_browser_dom_runner_script(manifest)
        html_text = render_synthetic_application_html(snapshot, runner_script=script)

        self.assertIn("<form", html_text)
        self.assertIn("#email", html_text)
        self.assertIn("actualSubmitCount: 0", script)
        self.assertNotIn(".submit(", script)

    def test_pre_submit_review_aggregates_manifests_and_confirmation_items(self) -> None:
        manifest = {
            "title": "Application",
            "url": "https://job-boards.greenhouse.io/example/jobs/1",
            "platform": "Greenhouse",
            "status": "autofill_ready_with_supervised_gates",
            "autofill_allowed": True,
            "would_submit": False,
            "action_count": 2,
            "stop_action_count": 2,
            "stop_actions": [
                {
                    "status": "needs_human_review",
                    "label": "Have you worked here before?",
                    "category": "employment_history",
                    "handling": "stop and ask user in supervised flow",
                },
                {
                    "status": "final_submit_confirmation",
                    "label": "Submit application",
                    "category": "final_submit",
                    "handling": "stop before final submit and wait for explicit approval",
                },
            ],
        }
        gaps = {
            "unique_prompts_observed": 2,
            "blocking_prompt_count": 1,
            "coverage_counts": {"needs_answer_memory": 1},
            "blocking_prompts": [
                {
                    "coverage_status": "needs_answer_memory",
                    "label": "Do you have GCP experience?",
                    "category": "skills_experience",
                    "platforms": ["LinkedIn"],
                    "required_count": 1,
                    "observed_count": 1,
                    "next_action": "ask once, then save approved answer memory",
                }
            ],
        }
        learning_tasks = {
            "tasks": [
                {
                    "question": "Do you have GCP experience?",
                    "recommended_storage": "answer_memory",
                    "platforms": ["LinkedIn"],
                    "approved": False,
                    "persist_allowed": True,
                }
            ]
        }
        synthetic = {
            "run_count": 400,
            "per_platform_target": 100,
            "platform_target_achieved": True,
            "actual_submit_count": 0,
            "policy_stop_counts": {"final_submit_confirmation": 100},
        }

        review = build_pre_submit_review(
            [manifest],
            gaps=gaps,
            learning_tasks=learning_tasks,
            synthetic=synthetic,
        )

        self.assertEqual(review["manifest_count"], 1)
        self.assertEqual(review["total_action_count"], 2)
        self.assertEqual(review["total_stop_action_count"], 2)
        self.assertEqual(review["actual_submit_count"], 0)
        self.assertFalse(review["would_submit"])
        self.assertEqual(review["question_to_confirm_count"], 2)
        self.assertEqual(review["confirmation_status_counts"]["final_submit_confirmation"], 1)
        self.assertIn("needs_answer_memory", review["confirmation_status_counts"])
        labels = [item["label"] for item in review["questions_to_confirm"]]
        self.assertEqual(labels.count("Do you have GCP experience?"), 1)
        markdown = render_pre_submit_review_markdown(review)
        self.assertIn("Pre-Submit Review", markdown)
        self.assertIn("Questions To Confirm", markdown)
        self.assertIn("Do you have GCP experience?", markdown)

    def test_write_pre_submit_review_outputs_reports(self) -> None:
        manifest = {
            "title": "Application",
            "url": "https://jobs.ashbyhq.com/example/1",
            "platform": "Ashby",
            "status": "autofill_ready",
            "autofill_allowed": True,
            "would_submit": False,
            "action_count": 1,
            "stop_action_count": 0,
            "stop_actions": [],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            json_output = Path(temp_dir) / "review.json"
            markdown_output = Path(temp_dir) / "review.md"

            review = write_pre_submit_review(
                [manifest_path],
                json_output,
                markdown_output,
            )

            self.assertEqual(review["manifest_count"], 1)
            self.assertEqual(review["autofill_ready_position_count"], 1)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertIn("Pre-Submit Review", markdown_output.read_text())

    def test_offline_apply_executor_runs_ready_steps_then_stops(self) -> None:
        plan = {
            "title": "Application",
            "url": "https://jobs.ashbyhq.com/example/1",
            "platform": "Ashby",
            "steps": [
                {
                    "field_index": 1,
                    "item_type": "field",
                    "action": "fill",
                    "status": "ready",
                    "label": "Email",
                    "category": "profile_identity",
                    "value_source": "profile.email",
                },
                {
                    "field_index": 2,
                    "item_type": "button",
                    "action": "submit_gate",
                    "status": "final_submit_confirmation",
                    "label": "Submit application",
                    "category": "final_submit",
                },
            ],
        }

        execution = execute_form_plan_offline(plan)

        self.assertEqual(execution["outcome"], "executed_to_policy_stop")
        self.assertEqual(execution["policy_stop"], "final_submit_confirmation")
        self.assertEqual(execution["executed_step_count"], 1)
        self.assertEqual(execution["actual_submit_count"], 0)
        self.assertFalse(execution["would_submit"])

    def test_offline_apply_executor_does_not_fill_closed_postings(self) -> None:
        plan = {
            "title": "Closed role",
            "url": "https://www.linkedin.com/jobs/view/123/",
            "platform": "LinkedIn",
            "steps": [
                {
                    "field_index": 1,
                    "item_type": "field",
                    "action": "fill",
                    "status": "ready",
                    "label": "Email",
                    "category": "profile_identity",
                    "value_source": "profile.email",
                }
            ],
        }

        execution = execute_form_plan_offline(
            plan,
            page_text="No longer accepting applications",
        )

        self.assertEqual(execution["outcome"], "closed_skip")
        self.assertEqual(execution["policy_stop"], "closed_posting")
        self.assertEqual(execution["executed_step_count"], 0)
        self.assertEqual(execution["stop_steps"][0]["status"], "closed_skip")

    def test_local_browser_manifest_executor_resolves_selectors_and_stops(self) -> None:
        snapshot = {
            "title": "Application",
            "url": "https://job-boards.greenhouse.io/example/jobs/1",
            "fields": [
                {"i": 1, "tag": "INPUT", "type": "email", "id": "email", "label": "Email"},
                {"i": 2, "tag": "INPUT", "type": "file", "name": "resume", "label": "Resume"},
            ],
        }
        plan = {
            "title": snapshot["title"],
            "url": snapshot["url"],
            "platform": "Greenhouse",
            "steps": [
                {
                    "field_index": 1,
                    "item_type": "field",
                    "tag": "INPUT",
                    "type": "email",
                    "id": "email",
                    "action": "fill",
                    "status": "ready",
                    "label": "Email",
                    "category": "profile_identity",
                    "value_source": "profile.email",
                },
                {
                    "field_index": 2,
                    "item_type": "field",
                    "tag": "INPUT",
                    "type": "file",
                    "name": "resume",
                    "action": "upload",
                    "status": "ready",
                    "label": "Resume",
                    "category": "resume_upload",
                    "value_source": "profile.question_answers.resume_path",
                },
                {
                    "field_index": 3,
                    "item_type": "button",
                    "action": "submit_gate",
                    "status": "final_submit_confirmation",
                    "label": "Submit application",
                    "category": "final_submit",
                },
            ],
        }
        manifest = build_browser_action_manifest(plan)

        execution = execute_browser_action_manifest_locally(manifest, snapshot)

        self.assertEqual(execution["outcome"], "executed_to_policy_stop")
        self.assertEqual(execution["policy_stop"], "final_submit_confirmation")
        self.assertEqual(execution["executed_action_count"], 2)
        self.assertEqual(execution["selector_miss_count"], 0)
        self.assertEqual(execution["actual_submit_count"], 0)
        self.assertFalse(execution["would_submit"])
        self.assertEqual(execution["executed_actions"][0]["selector"], "#email")

    def test_local_browser_manifest_executor_can_submit_local_synthetic_only(self) -> None:
        snapshot = {
            "title": "Application",
            "url": "https://www.linkedin.com/jobs/view/900001/",
            "fields": [
                {"i": 1, "tag": "INPUT", "type": "email", "id": "email", "label": "Email"},
            ],
            "buttons": [
                {"i": 99, "tag": "BUTTON", "text": "Submit application"},
            ],
        }
        plan = {
            "title": snapshot["title"],
            "url": snapshot["url"],
            "platform": "LinkedIn",
            "steps": [
                {
                    "field_index": 1,
                    "item_type": "field",
                    "tag": "INPUT",
                    "type": "email",
                    "id": "email",
                    "action": "fill",
                    "status": "ready",
                    "label": "Email",
                    "category": "profile_identity",
                    "value_source": "profile.email",
                },
                {
                    "field_index": 99,
                    "item_type": "button",
                    "tag": "BUTTON",
                    "action": "submit_gate",
                    "status": "final_submit_confirmation",
                    "label": "Submit application",
                    "category": "final_submit",
                },
            ],
        }
        manifest = build_browser_action_manifest(plan)

        execution = execute_browser_action_manifest_locally(
            manifest,
            snapshot,
            allow_local_synthetic_submit=True,
        )

        self.assertEqual(execution["outcome"], "submitted_local_synthetic")
        self.assertEqual(execution["policy_stop"], "local_synthetic_submit_allowed")
        self.assertEqual(execution["actual_submit_count"], 1)
        self.assertTrue(execution["would_submit"])
        self.assertFalse(execution["real_platform_submission"])
        self.assertEqual(execution["executed_actions"][-1]["browser_action"], "click_submit")

    def test_local_synthetic_submit_does_not_bypass_security_gates(self) -> None:
        snapshot = {
            "title": "Application",
            "url": "https://www.linkedin.com/jobs/view/900001/",
            "fields": [
                {"i": 1, "tag": "INPUT", "type": "email", "id": "email", "label": "Email"},
                {"i": 2, "tag": "TEXTAREA", "name": "g-recaptcha-response", "label": "g-recaptcha-response"},
            ],
            "buttons": [{"i": 99, "tag": "BUTTON", "text": "Submit application"}],
        }
        plan = {
            "title": snapshot["title"],
            "url": snapshot["url"],
            "platform": "LinkedIn",
            "steps": [
                {
                    "field_index": 1,
                    "item_type": "field",
                    "tag": "INPUT",
                    "type": "email",
                    "id": "email",
                    "action": "fill",
                    "status": "ready",
                    "label": "Email",
                    "category": "profile_identity",
                    "value_source": "profile.email",
                },
                {
                    "field_index": 2,
                    "item_type": "field",
                    "tag": "TEXTAREA",
                    "name": "g-recaptcha-response",
                    "action": "manual_security",
                    "status": "manual_security_step",
                    "label": "g-recaptcha-response",
                    "category": "security_verification",
                },
                {
                    "field_index": 99,
                    "item_type": "button",
                    "tag": "BUTTON",
                    "action": "submit_gate",
                    "status": "final_submit_confirmation",
                    "label": "Submit application",
                    "category": "final_submit",
                },
            ],
        }
        manifest = build_browser_action_manifest(plan)

        execution = execute_browser_action_manifest_locally(
            manifest,
            snapshot,
            allow_local_synthetic_submit=True,
        )

        self.assertEqual(execution["outcome"], "executed_to_policy_stop")
        self.assertEqual(execution["policy_stop"], "manual_security_step")
        self.assertEqual(execution["actual_submit_count"], 0)
        self.assertFalse(execution["would_submit"])

    def test_local_synthetic_submit_fills_fake_review_and_sensitive_gates(self) -> None:
        snapshot = {
            "title": "Application",
            "url": "https://job-boards.greenhouse.io/example/jobs/1",
            "fields": [
                {"i": 1, "tag": "INPUT", "type": "checkbox", "label": "I acknowledge the privacy policy."},
                {"i": 2, "tag": "SELECT", "label": "Gender"},
                {"i": 3, "tag": "SELECT", "label": "How did you hear about this role?"},
            ],
            "buttons": [{"i": 99, "tag": "BUTTON", "text": "Submit application"}],
        }
        plan = {
            "title": snapshot["title"],
            "url": snapshot["url"],
            "platform": "Greenhouse",
            "steps": [
                {
                    "field_index": 1,
                    "item_type": "field",
                    "tag": "INPUT",
                    "type": "checkbox",
                    "action": "manual_review",
                    "status": "needs_human_review",
                    "label": "I acknowledge the privacy policy.",
                    "category": "policy_acknowledgement",
                },
                {
                    "field_index": 2,
                    "item_type": "field",
                    "tag": "SELECT",
                    "action": "manual_sensitive",
                    "status": "sensitive_not_stored",
                    "label": "Gender",
                    "category": "eeoc_sensitive",
                },
                {
                    "field_index": 3,
                    "item_type": "field",
                    "tag": "SELECT",
                    "action": "answer",
                    "status": "missing_answer",
                    "label": "How did you hear about this role?",
                    "category": "referral_source",
                },
                {
                    "field_index": 99,
                    "item_type": "button",
                    "tag": "BUTTON",
                    "action": "submit_gate",
                    "status": "final_submit_confirmation",
                    "label": "Submit application",
                    "category": "final_submit",
                },
            ],
        }
        manifest = build_browser_action_manifest(plan)

        execution = execute_browser_action_manifest_locally(
            manifest,
            snapshot,
            allow_local_synthetic_submit=True,
        )

        self.assertEqual(execution["outcome"], "submitted_local_synthetic")
        self.assertEqual(execution["actual_submit_count"], 1)
        self.assertEqual(execution["synthetic_gate_answer_count"], 3)
        self.assertEqual(execution["remaining_stop_action_count"], 1)
        self.assertFalse(execution["real_platform_submission"])

    def test_local_browser_manifest_executor_does_not_fill_closed_postings(self) -> None:
        snapshot = {
            "title": "Closed role",
            "url": "https://www.linkedin.com/jobs/view/123/",
            "page_text": "No longer accepting applications",
            "fields": [
                {"i": 1, "tag": "INPUT", "type": "email", "id": "email", "label": "Email"},
            ],
        }
        plan = {
            "title": snapshot["title"],
            "url": snapshot["url"],
            "platform": "LinkedIn",
            "steps": [
                {
                    "field_index": 1,
                    "item_type": "field",
                    "tag": "INPUT",
                    "type": "email",
                    "id": "email",
                    "action": "fill",
                    "status": "ready",
                    "label": "Email",
                    "category": "profile_identity",
                    "value_source": "profile.email",
                }
            ],
        }
        manifest = build_browser_action_manifest(
            plan,
            page_text=str(snapshot["page_text"]),
        )

        execution = execute_browser_action_manifest_locally(manifest, snapshot)

        self.assertEqual(execution["outcome"], "closed_skip")
        self.assertEqual(execution["executed_action_count"], 0)
        self.assertEqual(execution["selector_miss_count"], 0)

    def test_synthetic_apply_execution_runs_hundred_without_real_submit(self) -> None:
        report = run_synthetic_apply_execution(count=20)

        self.assertEqual(report["run_count"], 20)
        self.assertFalse(report["real_platform_submission"])
        self.assertEqual(report["actual_submit_count"], 0)
        self.assertEqual(report["outcome_counts"]["closed_skip"], 1)
        self.assertGreater(report["outcome_counts"]["executed_to_policy_stop"], 0)
        self.assertGreater(report["executed_step_count"], 0)
        markdown = render_synthetic_apply_execution_markdown(report)
        self.assertIn("Synthetic Apply Execution", markdown)
        self.assertIn("Actual submit count: 0", markdown)

    def test_synthetic_apply_execution_can_target_each_platform(self) -> None:
        report = run_synthetic_apply_execution(per_platform_target=3)

        self.assertEqual(report["run_count"], 12)
        self.assertEqual(report["per_platform_target"], 3)
        self.assertTrue(report["platform_target_achieved"])
        self.assertEqual(report["platform_target_shortfalls"], {
            "Ashby": 0,
            "Greenhouse": 0,
            "Lever": 0,
            "LinkedIn": 0,
        })
        self.assertEqual(report["actual_submit_count"], 0)
        for count in report["platform_counts"].values():
            self.assertEqual(count, 3)

    def test_synthetic_apply_execution_can_target_each_platform_role_pair(self) -> None:
        report = run_synthetic_apply_execution(per_platform_role_target=2)

        self.assertEqual(report["run_count"], 40)
        self.assertEqual(report["per_platform_role_target"], 2)
        self.assertTrue(report["platform_role_target_achieved"])
        self.assertEqual(set(report["platform_role_target_shortfalls"].values()), {0})
        self.assertEqual(len(report["platform_role_counts"]), 20)
        for count in report["platform_role_counts"].values():
            self.assertEqual(count, 2)
        self.assertEqual(report["actual_submit_count"], 0)

    def test_write_synthetic_apply_execution_outputs_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            json_output = Path(temp_dir) / "execution.json"
            markdown_output = Path(temp_dir) / "execution.md"

            report = write_synthetic_apply_execution(
                json_output,
                markdown_output,
                count=8,
                per_platform_target=2,
            )

            self.assertEqual(report["run_count"], 8)
            self.assertTrue(report["platform_target_achieved"])
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertIn("Synthetic Apply Execution", markdown_output.read_text())

    def test_synthetic_browser_action_execution_targets_each_platform(self) -> None:
        report = run_synthetic_browser_action_execution(per_platform_target=3)

        self.assertEqual(report["run_count"], 12)
        self.assertEqual(report["per_platform_target"], 3)
        self.assertTrue(report["platform_target_achieved"])
        self.assertEqual(report["platform_target_shortfalls"], {
            "Ashby": 0,
            "Greenhouse": 0,
            "Lever": 0,
            "LinkedIn": 0,
        })
        self.assertEqual(report["selector_miss_count"], 0)
        self.assertEqual(report["actual_submit_count"], 0)
        self.assertGreater(report["executed_action_count"], 0)
        markdown = render_synthetic_browser_action_execution_markdown(report)
        self.assertIn("Synthetic Browser Action Execution", markdown)
        self.assertIn("Local synthetic submit count: 0", markdown)

    def test_synthetic_browser_action_execution_targets_each_platform_role_pair(self) -> None:
        report = run_synthetic_browser_action_execution(per_platform_role_target=2)

        self.assertEqual(report["run_count"], 40)
        self.assertEqual(report["per_platform_role_target"], 2)
        self.assertTrue(report["platform_role_target_achieved"])
        self.assertEqual(set(report["platform_role_target_shortfalls"].values()), {0})
        self.assertEqual(len(report["platform_role_counts"]), 20)
        for count in report["platform_role_counts"].values():
            self.assertEqual(count, 2)
        self.assertEqual(report["actual_submit_count"], 0)
        self.assertEqual(report["selector_miss_count"], 0)
        markdown = render_synthetic_browser_action_execution_markdown(report)
        self.assertIn("Platform-role target achieved: true", markdown)

    def test_synthetic_browser_action_execution_can_submit_fake_local_final_gates(self) -> None:
        report = run_synthetic_browser_action_execution(
            per_platform_target=1,
            allow_local_synthetic_submit=True,
        )

        self.assertEqual(report["run_count"], 4)
        self.assertFalse(report["real_platform_submission"])
        self.assertTrue(report["local_synthetic_submit_allowed"])
        self.assertEqual(report["actual_submit_count"], 4)
        self.assertEqual(report["would_submit_count"], 4)
        self.assertEqual(report["eligible_submit_count"], 4)
        self.assertEqual(report["eligible_submit_target_count"], 4)
        self.assertTrue(report["eligible_submit_achieved"])
        self.assertEqual(report["outcome_counts"]["submitted_local_synthetic"], 4)
        self.assertGreater(report["synthetic_gate_answer_count"], 0)

    def test_synthetic_browser_action_execution_keeps_captcha_blocked_in_submit_mode(self) -> None:
        report = run_synthetic_browser_action_execution(
            count=5,
            allow_local_synthetic_submit=True,
        )

        self.assertEqual(report["run_count"], 5)
        self.assertEqual(report["actual_submit_count"], 4)
        self.assertEqual(report["eligible_submit_count"], 4)
        self.assertEqual(report["eligible_submit_target_count"], 4)
        self.assertEqual(report["expected_blocker_count"], 1)
        self.assertTrue(report["eligible_submit_achieved"])
        self.assertEqual(report["policy_stop_counts"]["manual_security_step"], 1)
        self.assertFalse(report["real_platform_submission"])

    def test_write_synthetic_browser_action_execution_outputs_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            json_output = Path(temp_dir) / "browser_execution.json"
            markdown_output = Path(temp_dir) / "browser_execution.md"

            report = write_synthetic_browser_action_execution(
                json_output,
                markdown_output,
                count=8,
                per_platform_target=2,
            )

            self.assertEqual(report["run_count"], 8)
            self.assertTrue(report["platform_target_achieved"])
            self.assertEqual(report["selector_miss_count"], 0)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertIn("Synthetic Browser Action Execution", markdown_output.read_text())

    def test_learning_task_template_applies_approved_answers(self) -> None:
        readiness = {
            "minimal_learning_tasks": [
                {
                    "group_key": "profile:profile_links",
                    "question": "What LinkedIn profile URL should automation use?",
                    "recommended_storage": "profile",
                    "labels": ["LinkedIn Profile"],
                    "platforms": ["Greenhouse"],
                },
                {
                    "group_key": "local_material:resume_file",
                    "question": "Which approved resume file should automation upload?",
                    "recommended_storage": "local_material",
                    "labels": ["Resume"],
                    "platforms": ["Ashby"],
                },
                {
                    "group_key": "answer_memory:standard_question",
                    "question": "Do you consent to SMS messages?",
                    "recommended_storage": "answer_memory",
                    "labels": ["Do you consent to SMS messages?"],
                    "platforms": ["Greenhouse"],
                },
                {
                    "group_key": "do_not_store:gender",
                    "question": "Gender",
                    "recommended_storage": "do_not_store",
                    "labels": ["Gender"],
                    "platforms": ["Greenhouse"],
                },
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            template_path = Path(temp_dir) / "learning.json"
            markdown_path = Path(temp_dir) / "learning.md"
            profile_path = Path(temp_dir) / "profile.json"
            memory_path = Path(temp_dir) / "memory.json"
            template = write_learning_task_template(readiness, template_path, markdown_path)
            for task in template["tasks"]:
                task["approved"] = True
                if task["recommended_storage"] == "profile":
                    task["answer"] = "https://www.linkedin.com/in/example/"
                elif task["recommended_storage"] == "local_material":
                    task["answer"] = "/tmp/example-resume.pdf"
                elif task["recommended_storage"] == "answer_memory":
                    task["answer"] = "No, I do not consent to SMS messages."
                else:
                    task["answer"] = "Prefer not to answer"
            template_path.write_text(json.dumps(template), encoding="utf-8")
            profile_path.write_text(
                json.dumps(
                    {
                        "candidate": {"name": "Test User"},
                        "preferences": {},
                        "resume_facts": {},
                        "question_answers": {},
                    }
                ),
                encoding="utf-8",
            )

            dry_run = apply_learning_task_answers(
                template_path,
                profile_path,
                memory_path,
                dry_run=True,
            )
            self.assertEqual(dry_run["profile_updates"], ["linkedin_profile", "resume_path"])
            self.assertFalse(memory_path.exists())

            result = apply_learning_task_answers(template_path, profile_path, memory_path)

            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertEqual(
                profile["question_answers"]["linkedin_profile"],
                "https://www.linkedin.com/in/example/",
            )
            self.assertEqual(profile["question_answers"]["resume_path"], "/tmp/example-resume.pdf")
            memory = load_answer_memory(memory_path)
            self.assertEqual(len(memory["answers"]), 1)
            self.assertEqual(len(result["skipped"]), 1)
            markdown = render_learning_task_template_markdown(build_learning_task_template(readiness))
            self.assertIn("Learning Task Template", markdown)

    def test_apply_critical_input_answers_persists_user_approved_values(self) -> None:
        learning_tasks = {
            "tasks": [
                {
                    "group_key": "profile:zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "recommended_storage": "profile",
                    "labels": ["Zip Code"],
                    "platforms": ["Ashby"],
                    "related_prompt_count": 1,
                    "observed_count": 4,
                    "required_count": 4,
                    "persist_allowed": True,
                },
                {
                    "group_key": "resume_facts:education_grading",
                    "question": "What GPA or grading answer should automation use?",
                    "recommended_storage": "resume_facts",
                    "labels": ["What is your GPA?"],
                    "platforms": ["Greenhouse"],
                    "related_prompt_count": 1,
                    "observed_count": 7,
                    "required_count": 7,
                    "persist_allowed": True,
                },
                {
                    "group_key": "answer_memory:favorite_restaurant",
                    "question": "What is your favorite restaurant?",
                    "recommended_storage": "answer_memory",
                    "labels": ["What is your favorite restaurant?"],
                    "platforms": ["Greenhouse"],
                    "related_prompt_count": 1,
                    "observed_count": 1,
                    "required_count": 1,
                    "persist_allowed": True,
                },
                {
                    "group_key": "answer_memory:citizenship_status:default_policy",
                    "question": "What citizenship answers should automation use?",
                    "recommended_storage": "answer_memory",
                    "answer_scope": "category_default_policy",
                    "suggested_answer_source": "requires_exact_user_confirmation",
                    "approval_risk": "high",
                    "labels": ["Are you a U.S. citizen?"],
                    "platforms": ["Greenhouse"],
                    "related_prompt_count": 1,
                    "observed_count": 2,
                    "required_count": 2,
                    "persist_allowed": True,
                },
                {
                    "group_key": "supervised_confirmation:policy_acknowledgement",
                    "question": "May automation mark applicant privacy acknowledgement?",
                    "recommended_storage": "supervised_confirmation",
                    "answer_scope": "supervised_only",
                    "labels": ["Privacy policy"],
                    "platforms": ["Lever"],
                    "related_prompt_count": 1,
                    "observed_count": 1,
                    "required_count": 1,
                    "persist_allowed": False,
                },
            ],
        }
        pack = build_learning_approval_pack(learning_tasks, {})
        answers = {
            "profile:zip_or_postal_code": "94105",
            "resume_facts:education_grading": "Not applicable",
            "answer_memory:favorite_restaurant": "Din Tai Fung",
            "answer_memory:citizenship_status:default_policy": "No restricted-country citizenship.",
            "supervised_confirmation:policy_acknowledgement": "Approved after browser review",
        }
        for item in pack["critical_inputs"]:
            item["user_answer"] = answers[item["group_key"]]
            item["approval_decision"] = "approved"
            if item["input_type"] == "high_risk_exact_confirmation":
                item["high_risk_user_confirmed"] = True

        with tempfile.TemporaryDirectory() as temp_dir:
            pack_path = Path(temp_dir) / "approval_pack.json"
            profile_path = Path(temp_dir) / "profile.json"
            memory_path = Path(temp_dir) / "memory.json"
            pack_path.write_text(json.dumps(pack), encoding="utf-8")
            profile_path.write_text(
                json.dumps(
                    {
                        "candidate": {"name": "Test User"},
                        "preferences": {},
                        "resume_facts": {},
                        "question_answers": {},
                    }
                ),
                encoding="utf-8",
            )

            dry_run = apply_critical_input_answers(pack_path, profile_path, memory_path, dry_run=True)
            self.assertEqual(dry_run["approved_input_count"], 4)
            self.assertEqual(dry_run["profile_updates"], ["zip_code"])
            self.assertEqual(dry_run["resume_fact_updates"], ["grading_system"])
            self.assertEqual(dry_run["skipped_input_count"], 1)
            self.assertFalse(memory_path.exists())

            result = apply_critical_input_answers(pack_path, profile_path, memory_path)

            self.assertEqual(result["approved_input_count"], 4)
            self.assertEqual(result["skipped_input_count"], 1)
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertEqual(profile["question_answers"]["zip_code"], "94105")
            self.assertEqual(profile["resume_facts"]["grading_system"], "Not applicable")
            memory = load_answer_memory(memory_path)
            self.assertIsNotNone(find_learned_answer(memory, "What is your favorite restaurant?"))
            self.assertIsNotNone(find_learned_answer(memory, "Are you a U.S. citizen?"))
            self.assertEqual(result["category_policy_updates"], ["citizenship_status"])

    def test_apply_critical_input_answers_skips_unconfirmed_high_risk_values(self) -> None:
        learning_tasks = {
            "tasks": [
                {
                    "group_key": "answer_memory:citizenship_status:default_policy",
                    "question": "What citizenship answers should automation use?",
                    "recommended_storage": "answer_memory",
                    "answer_scope": "category_default_policy",
                    "suggested_answer_source": "requires_exact_user_confirmation",
                    "approval_risk": "high",
                    "labels": ["Are you a U.S. citizen?"],
                    "platforms": ["Greenhouse"],
                    "related_prompt_count": 1,
                    "observed_count": 2,
                    "required_count": 2,
                    "persist_allowed": True,
                },
            ],
        }
        pack = build_learning_approval_pack(learning_tasks, {})
        template = build_critical_input_answer_template(pack)
        template["critical_inputs"][0]["user_answer"] = "Exact high-risk answer."
        template["critical_inputs"][0]["approval_decision"] = "approved"
        template["critical_inputs"][0]["high_risk_user_confirmed"] = False

        with tempfile.TemporaryDirectory() as temp_dir:
            pack_path = Path(temp_dir) / "approval_pack.json"
            answers_path = Path(temp_dir) / "answers.json"
            profile_path = Path(temp_dir) / "profile.json"
            memory_path = Path(temp_dir) / "memory.json"
            pack_path.write_text(json.dumps(pack), encoding="utf-8")
            answers_path.write_text(json.dumps(template), encoding="utf-8")
            profile_path.write_text(
                json.dumps({"candidate": {"name": "Test User"}, "question_answers": {}, "resume_facts": {}}),
                encoding="utf-8",
            )

            result = apply_critical_input_answers(
                pack_path,
                profile_path,
                memory_path,
                answers_path=answers_path,
            )

            self.assertEqual(result["approved_input_count"], 0)
            self.assertEqual(result["skipped_input_count"], 1)
            self.assertEqual(
                result["critical_input_skipped"][0]["reason"],
                "high_risk_user_confirmed_required",
            )
            self.assertFalse(memory_path.exists())

    def test_critical_input_answer_template_can_drive_apply_command(self) -> None:
        learning_tasks = {
            "tasks": [
                {
                    "group_key": "profile:zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "recommended_storage": "profile",
                    "labels": ["Zip Code"],
                    "platforms": ["Ashby"],
                    "related_prompt_count": 1,
                    "observed_count": 4,
                    "required_count": 4,
                    "persist_allowed": True,
                },
                {
                    "group_key": "answer_memory:favorite_junk_food",
                    "question": "What's your favorite junk food?",
                    "recommended_storage": "answer_memory",
                    "labels": ["What's your favorite junk food?"],
                    "platforms": ["Greenhouse"],
                    "related_prompt_count": 1,
                    "observed_count": 2,
                    "required_count": 2,
                    "persist_allowed": True,
                },
            ],
        }
        pack = build_learning_approval_pack(learning_tasks, {})
        template = build_critical_input_answer_template(pack)
        self.assertEqual(template["answer_count"], 2)
        self.assertEqual(template["preserved_answer_count"], 0)
        self.assertEqual(len(template["critical_inputs"]), 2)
        self.assertEqual(template["answers"][0]["approval_decision"], "")
        markdown = render_critical_input_answer_template_markdown(template)
        self.assertIn("Critical Input Answer Template", markdown)

        for answer in template["answers"]:
            if answer["group_key"] == "profile:zip_or_postal_code":
                answer["user_answer"] = "94105"
                answer["approval_decision"] = "approved"
            else:
                answer["user_answer"] = "Potato chips"
                answer["approval_decision"] = "approved"

        with tempfile.TemporaryDirectory() as temp_dir:
            pack_path = Path(temp_dir) / "approval_pack.json"
            answers_path = Path(temp_dir) / "critical_input_answers.json"
            answers_md_path = Path(temp_dir) / "critical_input_answers.md"
            profile_path = Path(temp_dir) / "profile.json"
            memory_path = Path(temp_dir) / "memory.json"
            pack_path.write_text(json.dumps(pack), encoding="utf-8")
            answers_path.write_text(json.dumps(template), encoding="utf-8")
            profile_path.write_text(
                json.dumps(
                    {
                        "candidate": {"name": "Test User"},
                        "preferences": {},
                        "resume_facts": {},
                        "question_answers": {},
                    }
                ),
                encoding="utf-8",
            )

            written = write_critical_input_answer_template(pack, answers_path, answers_md_path)
            self.assertEqual(written["answer_count"], 2)
            self.assertTrue(answers_md_path.exists())
            answers_path.write_text(json.dumps(template), encoding="utf-8")

            result = apply_critical_input_answers(
                pack_path,
                profile_path,
                memory_path,
                answers_path=answers_path,
            )

            self.assertEqual(result["approved_input_count"], 2)
            self.assertEqual(result["skipped_input_count"], 0)
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertEqual(profile["question_answers"]["zip_code"], "94105")
            memory = load_answer_memory(memory_path)
            self.assertIsNotNone(find_learned_answer(memory, "What's your favorite junk food?"))

            critical_inputs_payload = json.loads(json.dumps(build_critical_input_answer_template(pack)))
            for answer in critical_inputs_payload["critical_inputs"]:
                if answer["group_key"] == "profile:zip_or_postal_code":
                    answer["user_answer"] = "94105"
                    answer["approval_decision"] = "approved"
            status = build_critical_input_status_report(pack, critical_inputs_payload)
            self.assertEqual(status["summary"]["ready_to_apply_count"], 1)

    def test_critical_input_answer_template_syncs_new_pack_and_preserves_answers(self) -> None:
        old_tasks = {
            "tasks": [
                {
                    "group_key": "profile:zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "recommended_storage": "profile",
                    "labels": ["Zip Code"],
                    "platforms": ["Ashby"],
                    "required_count": 4,
                    "persist_allowed": True,
                },
                {
                    "group_key": "resume_facts:education_grading",
                    "question": "What GPA should automation use?",
                    "recommended_storage": "resume_facts",
                    "labels": ["What is your GPA?"],
                    "platforms": ["Greenhouse"],
                    "required_count": 8,
                    "persist_allowed": True,
                },
            ],
        }
        new_tasks = {
            "tasks": [
                old_tasks["tasks"][0],
                {
                    "group_key": "resume_facts:education_grading",
                    "question": "What GPA should automation use?",
                    "recommended_storage": "resume_facts",
                    "labels": ["What is your GPA?"],
                    "suggested_answer": "Not provided in my current resume; GPA/test scores are not included.",
                    "suggested_answer_source": "profile.resume_facts.education_without_grade",
                    "platforms": ["Greenhouse"],
                    "required_count": 8,
                    "persist_allowed": True,
                },
            ],
        }
        old_pack = build_learning_approval_pack(old_tasks, {})
        existing = build_critical_input_answer_template(old_pack)
        for row in existing["critical_inputs"]:
            if row["group_key"] == "profile:zip_or_postal_code":
                row["user_answer"] = "98004"
                row["approval_decision"] = "approved"

        new_pack = build_learning_approval_pack(new_tasks, {})
        synced = build_critical_input_answer_template(
            new_pack,
            existing_answers_payload=existing,
        )
        rows_by_id = {row["input_id"]: row for row in synced["critical_inputs"]}

        self.assertEqual(synced["answer_count"], 2)
        self.assertEqual(synced["preserved_answer_count"], 1)
        self.assertEqual(rows_by_id["profile_zip_or_postal_code"]["user_answer"], "98004")
        self.assertEqual(rows_by_id["profile_zip_or_postal_code"]["approval_decision"], "approved")
        self.assertIn("resume_facts_education_grading", rows_by_id)
        self.assertEqual(
            rows_by_id["resume_facts_education_grading"]["user_answer"],
            "Not provided in my current resume; GPA/test scores are not included.",
        )

    def test_critical_input_answer_update_merges_compact_answers_safely(self) -> None:
        learning_tasks = {
            "tasks": [
                {
                    "group_key": "profile:zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "recommended_storage": "profile",
                    "labels": ["Zip Code"],
                    "platforms": ["Ashby"],
                    "required_count": 4,
                    "persist_allowed": True,
                },
                {
                    "group_key": "answer_memory:citizenship_status:default_policy",
                    "question": "What citizenship answers should automation use?",
                    "recommended_storage": "answer_memory",
                    "answer_scope": "category_default_policy",
                    "suggested_answer_source": "requires_exact_user_confirmation",
                    "approval_risk": "high",
                    "labels": ["Are you a U.S. citizen?"],
                    "platforms": ["Greenhouse"],
                    "required_count": 2,
                    "persist_allowed": True,
                },
                {
                    "group_key": "supervised_confirmation:policy_acknowledgement",
                    "question": "May automation mark applicant privacy acknowledgement?",
                    "recommended_storage": "supervised_confirmation",
                    "answer_scope": "supervised_only",
                    "labels": ["Privacy policy"],
                    "platforms": ["Lever"],
                    "required_count": 1,
                    "persist_allowed": False,
                },
            ],
        }
        pack = build_learning_approval_pack(learning_tasks, {})
        template = build_critical_input_answer_template(pack)
        updates = {
            "profile_zip_or_postal_code": "98004",
            "answer_memory_citizenship_status_default_policy": "I am a U.S. citizen.",
            "supervised_confirmation_policy_acknowledgement": {
                "user_answer": "Yes, I acknowledge.",
                "approval_decision": "approved",
            },
            "unknown_input": "ignore me",
        }

        report = build_critical_input_answer_update(template, updates, approve=True)
        updated_rows = {
            row["input_id"]: row for row in report["updated_answers"]["critical_inputs"]
        }

        self.assertEqual(report["summary"]["matched_update_count"], 3)
        self.assertEqual(report["summary"]["unknown_update_count"], 1)
        self.assertEqual(report["summary"]["answer_updated_count"], 2)
        self.assertEqual(report["summary"]["approval_updated_count"], 1)
        self.assertEqual(report["summary"]["high_risk_approval_blocked_count"], 1)
        self.assertEqual(report["summary"]["supervised_skipped_count"], 1)
        self.assertEqual(updated_rows["profile_zip_or_postal_code"]["approval_decision"], "approved")
        self.assertEqual(updated_rows["profile_zip_or_postal_code"]["user_answer"], "98004")
        self.assertEqual(
            updated_rows["answer_memory_citizenship_status_default_policy"]["user_answer"],
            "I am a U.S. citizen.",
        )
        self.assertEqual(
            updated_rows["answer_memory_citizenship_status_default_policy"]["approval_decision"],
            "",
        )
        self.assertEqual(
            updated_rows["supervised_confirmation_policy_acknowledgement"]["user_answer"],
            "",
        )
        markdown = render_critical_input_answer_update_markdown(report)
        self.assertIn("High-risk approvals blocked: 1", markdown)

    def test_critical_input_answer_update_can_approve_explicit_high_risk_confirmation(self) -> None:
        learning_tasks = {
            "tasks": [
                {
                    "group_key": "answer_memory:citizenship_status:default_policy",
                    "question": "What citizenship answers should automation use?",
                    "recommended_storage": "answer_memory",
                    "answer_scope": "category_default_policy",
                    "suggested_answer_source": "requires_exact_user_confirmation",
                    "approval_risk": "high",
                    "labels": ["Are you a U.S. citizen?"],
                    "platforms": ["Greenhouse"],
                    "required_count": 2,
                    "persist_allowed": True,
                }
            ],
        }
        pack = build_learning_approval_pack(learning_tasks, {})
        template = build_critical_input_answer_template(pack)
        updates = {
            "answer_memory_citizenship_status_default_policy": {
                "user_answer": "I am a U.S. citizen.",
                "approval_decision": "approved",
                "high_risk_user_confirmed": True,
            }
        }

        report = build_critical_input_answer_update(template, updates)
        row = report["updated_answers"]["critical_inputs"][0]

        self.assertEqual(row["approval_decision"], "approved")
        self.assertTrue(row["high_risk_user_confirmed"])
        self.assertEqual(report["summary"]["approval_updated_count"], 1)
        self.assertEqual(report["summary"]["high_risk_confirmation_updated_count"], 1)
        self.assertEqual(report["summary"]["high_risk_approval_blocked_count"], 0)
        self.assertEqual(report["summary"]["ready_after_update_count"], 1)

    def test_write_critical_input_answer_update_updates_both_mirrors(self) -> None:
        learning_tasks = {
            "tasks": [
                {
                    "group_key": "profile:zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "recommended_storage": "profile",
                    "labels": ["Zip Code"],
                    "platforms": ["Ashby"],
                    "required_count": 4,
                    "persist_allowed": True,
                }
            ],
        }
        pack = build_learning_approval_pack(learning_tasks, {})
        template = build_critical_input_answer_template(pack)

        with tempfile.TemporaryDirectory() as temp_dir:
            answers_path = Path(temp_dir) / "answers.json"
            answers_md_path = Path(temp_dir) / "answers.md"
            updates_path = Path(temp_dir) / "updates.json"
            report_path = Path(temp_dir) / "report.json"
            report_md_path = Path(temp_dir) / "report.md"
            answers_path.write_text(json.dumps(template), encoding="utf-8")
            updates_path.write_text(
                json.dumps({"profile_zip_or_postal_code": "98004"}),
                encoding="utf-8",
            )

            report = write_critical_input_answer_update(
                answers_path,
                json.loads(updates_path.read_text(encoding="utf-8")),
                report_path,
                report_md_path,
                answers_markdown_output=answers_md_path,
                approve=True,
            )
            saved = json.loads(answers_path.read_text(encoding="utf-8"))

            self.assertEqual(report["summary"]["ready_after_update_count"], 1)
            self.assertEqual(saved["critical_inputs"][0]["user_answer"], "98004")
            self.assertEqual(saved["answers"][0]["user_answer"], "98004")
            self.assertEqual(saved["critical_inputs"][0]["approval_decision"], "approved")
            self.assertTrue(report_path.exists())
            self.assertTrue(report_md_path.exists())
            self.assertTrue(answers_md_path.exists())

    def test_critical_input_workflow_dry_runs_then_applies_confirmed_answers(self) -> None:
        learning_tasks = {
            "tasks": [
                {
                    "group_key": "profile:zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "recommended_storage": "profile",
                    "labels": ["Zip Code"],
                    "platforms": ["Ashby"],
                    "required_count": 4,
                    "persist_allowed": True,
                },
                {
                    "group_key": "answer_memory:favorite_junk_food",
                    "question": "What's your favorite junk food?",
                    "recommended_storage": "answer_memory",
                    "labels": ["What's your favorite junk food?"],
                    "platforms": ["Greenhouse"],
                    "required_count": 2,
                    "persist_allowed": True,
                },
            ],
        }
        pack = build_learning_approval_pack(learning_tasks, {})
        template = build_critical_input_answer_template(pack)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            approval_pack_path = root / "pack.json"
            answers_path = root / "answers.json"
            answers_md_path = root / "answers.md"
            profile_path = root / "profile.json"
            memory_path = root / "memory.json"
            workflow_json = root / "workflow.json"
            workflow_md = root / "workflow.md"
            update_json = root / "update.json"
            update_md = root / "update.md"
            status_json = root / "status.json"
            status_md = root / "status.md"
            approval_pack_path.write_text(json.dumps(pack), encoding="utf-8")
            answers_path.write_text(json.dumps(template), encoding="utf-8")
            profile_path.write_text(
                json.dumps(
                    {
                        "candidate": {"name": "Test User"},
                        "preferences": {},
                        "resume_facts": {},
                        "question_answers": {},
                    }
                ),
                encoding="utf-8",
            )
            updates = {
                "profile_zip_or_postal_code": "98004",
                "answer_memory_favorite_junk_food": "Potato chips",
            }

            dry_run_workflow = write_critical_input_answer_workflow(
                approval_pack_path,
                answers_path,
                updates,
                profile_path,
                memory_path,
                workflow_json,
                workflow_md,
                update_json,
                update_md,
                status_json,
                status_md,
                answers_markdown_output=answers_md_path,
                approve=True,
                apply_confirmed=False,
            )

            self.assertFalse(dry_run_workflow["summary"]["apply_executed"])
            self.assertEqual(dry_run_workflow["summary"]["dry_run_approved_inputs"], 2)
            self.assertFalse(memory_path.exists())
            self.assertEqual(
                json.loads(profile_path.read_text(encoding="utf-8"))["question_answers"],
                {},
            )

            applied_workflow = write_critical_input_answer_workflow(
                approval_pack_path,
                answers_path,
                updates,
                profile_path,
                memory_path,
                workflow_json,
                workflow_md,
                update_json,
                update_md,
                status_json,
                status_md,
                answers_markdown_output=answers_md_path,
                approve=True,
                apply_confirmed=True,
            )

            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            memory = load_answer_memory(memory_path)
            self.assertTrue(applied_workflow["summary"]["apply_executed"])
            self.assertTrue(applied_workflow["summary"]["ready_for_complete_apply"])
            self.assertEqual(applied_workflow["apply_gate"]["blocking_reasons"], [])
            self.assertEqual(profile["question_answers"]["zip_code"], "98004")
            self.assertIsNotNone(find_learned_answer(memory, "What's your favorite junk food?"))
            self.assertTrue(workflow_json.exists())
            self.assertTrue(workflow_md.exists())
            self.assertTrue(status_json.exists())
            self.assertIn("Critical Input Answer Workflow", render_critical_input_answer_workflow_markdown(applied_workflow))

    def test_critical_input_workflow_blocks_partial_apply_by_default(self) -> None:
        learning_tasks = {
            "tasks": [
                {
                    "group_key": "profile:zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "recommended_storage": "profile",
                    "labels": ["Zip Code"],
                    "platforms": ["Ashby"],
                    "required_count": 4,
                    "persist_allowed": True,
                },
                {
                    "group_key": "answer_memory:favorite_junk_food",
                    "question": "What's your favorite junk food?",
                    "recommended_storage": "answer_memory",
                    "labels": ["What's your favorite junk food?"],
                    "platforms": ["Greenhouse"],
                    "required_count": 2,
                    "persist_allowed": True,
                },
            ],
        }
        pack = build_learning_approval_pack(learning_tasks, {})
        template = build_critical_input_answer_template(pack)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            approval_pack_path = root / "pack.json"
            answers_path = root / "answers.json"
            answers_md_path = root / "answers.md"
            profile_path = root / "profile.json"
            memory_path = root / "memory.json"
            workflow_json = root / "workflow.json"
            workflow_md = root / "workflow.md"
            update_json = root / "update.json"
            update_md = root / "update.md"
            status_json = root / "status.json"
            status_md = root / "status.md"
            approval_pack_path.write_text(json.dumps(pack), encoding="utf-8")
            answers_path.write_text(json.dumps(template), encoding="utf-8")
            original_answers = answers_path.read_text(encoding="utf-8")
            profile_path.write_text(
                json.dumps(
                    {
                        "candidate": {"name": "Test User"},
                        "preferences": {},
                        "resume_facts": {},
                        "question_answers": {},
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "critical_inputs_waiting"):
                write_critical_input_answer_workflow(
                    approval_pack_path,
                    answers_path,
                    {"profile_zip_or_postal_code": "98004"},
                    profile_path,
                    memory_path,
                    workflow_json,
                    workflow_md,
                    update_json,
                    update_md,
                    status_json,
                    status_md,
                    answers_markdown_output=answers_md_path,
                    approve=True,
                    apply_confirmed=True,
                )

            self.assertEqual(answers_path.read_text(encoding="utf-8"), original_answers)
            self.assertFalse(memory_path.exists())
            self.assertEqual(
                json.loads(profile_path.read_text(encoding="utf-8"))["question_answers"],
                {},
            )

            partial = write_critical_input_answer_workflow(
                approval_pack_path,
                answers_path,
                {"profile_zip_or_postal_code": "98004"},
                profile_path,
                memory_path,
                workflow_json,
                workflow_md,
                update_json,
                update_md,
                status_json,
                status_md,
                answers_markdown_output=answers_md_path,
                approve=True,
                apply_confirmed=True,
                allow_partial_apply=True,
            )

            self.assertFalse(partial["summary"]["ready_for_complete_apply"])
            self.assertIn("critical_inputs_waiting", partial["apply_gate"]["blocking_reasons"])
            self.assertTrue(partial["summary"]["apply_executed"])
            self.assertEqual(
                json.loads(profile_path.read_text(encoding="utf-8"))["question_answers"]["zip_code"],
                "98004",
            )

    def test_critical_input_workflow_blocks_unconfirmed_high_risk_apply(self) -> None:
        learning_tasks = {
            "tasks": [
                {
                    "group_key": "answer_memory:citizenship_status:default_policy",
                    "question": "What citizenship answer should automation reuse?",
                    "recommended_storage": "answer_memory",
                    "labels": ["Are you a U.S. Citizen?"],
                    "platforms": ["Ashby"],
                    "required_count": 3,
                    "persist_allowed": True,
                    "approval_risk": "high",
                    "suggested_answer_source": "requires_exact_user_confirmation",
                },
            ],
        }
        pack = build_learning_approval_pack(learning_tasks, {})
        template = build_critical_input_answer_template(pack)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            approval_pack_path = root / "pack.json"
            answers_path = root / "answers.json"
            profile_path = root / "profile.json"
            memory_path = root / "memory.json"
            workflow_json = root / "workflow.json"
            workflow_md = root / "workflow.md"
            update_json = root / "update.json"
            update_md = root / "update.md"
            status_json = root / "status.json"
            status_md = root / "status.md"
            approval_pack_path.write_text(json.dumps(pack), encoding="utf-8")
            answers_path.write_text(json.dumps(template), encoding="utf-8")
            original_answers = answers_path.read_text(encoding="utf-8")
            profile_path.write_text(
                json.dumps({"candidate": {"name": "Test User"}, "question_answers": {}, "resume_facts": {}}),
                encoding="utf-8",
            )
            updates = {
                "answer_memory_citizenship_status_default_policy": {
                    "user_answer": "Exact user-confirmed citizenship answer.",
                    "approval_decision": "approved",
                    "high_risk_user_confirmed": False,
                }
            }

            with self.assertRaisesRegex(ValueError, "high_risk_confirmation_missing"):
                write_critical_input_answer_workflow(
                    approval_pack_path,
                    answers_path,
                    updates,
                    profile_path,
                    memory_path,
                    workflow_json,
                    workflow_md,
                    update_json,
                    update_md,
                    status_json,
                    status_md,
                    approve=True,
                    approve_high_risk=True,
                    apply_confirmed=True,
                )

            self.assertEqual(answers_path.read_text(encoding="utf-8"), original_answers)
            self.assertFalse(memory_path.exists())

            updates["answer_memory_citizenship_status_default_policy"]["high_risk_user_confirmed"] = True
            workflow = write_critical_input_answer_workflow(
                approval_pack_path,
                answers_path,
                updates,
                profile_path,
                memory_path,
                workflow_json,
                workflow_md,
                update_json,
                update_md,
                status_json,
                status_md,
                approve=True,
                approve_high_risk=True,
                apply_confirmed=True,
            )

            memory = load_answer_memory(memory_path)
            self.assertTrue(workflow["summary"]["ready_for_complete_apply"])
            self.assertTrue(workflow["summary"]["apply_executed"])
            self.assertIsNotNone(find_learned_answer(memory, "Are you a U.S. Citizen?"))

    def test_critical_input_preflight_reports_temp_only_impact(self) -> None:
        learning_tasks = {
            "tasks": [
                {
                    "group_key": "profile:zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "recommended_storage": "profile",
                    "labels": ["Zip Code"],
                    "platforms": ["Ashby"],
                    "required_count": 4,
                    "persist_allowed": True,
                },
                {
                    "group_key": "answer_memory:favorite_junk_food",
                    "question": "What's your favorite junk food?",
                    "recommended_storage": "answer_memory",
                    "labels": ["What's your favorite junk food?"],
                    "platforms": ["Greenhouse"],
                    "required_count": 2,
                    "persist_allowed": True,
                },
            ],
        }
        pack = build_learning_approval_pack(learning_tasks, {})
        template = build_critical_input_answer_template(pack)
        updates = {
            "profile_zip_or_postal_code": "98004",
            "answer_memory_favorite_junk_food": "Potato chips",
        }
        research = {
            "positions_observed_total": 1,
            "positions": [
                {
                    "position_key": "ashby:example:sre",
                    "platform": "Ashby",
                    "company": "Example",
                    "title": "Site Reliability Engineer",
                    "role_family": "SRE",
                }
            ],
            "items": [
                {
                    "position_key": "ashby:example:sre",
                    "normalized_label": "zip code",
                    "label": "Zip Code",
                    "category": "profile_identity",
                    "automation_action": "auto_fill_from_profile",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "test",
                },
                {
                    "position_key": "ashby:example:sre",
                    "normalized_label": "what s your favorite junk food",
                    "label": "What's your favorite junk food?",
                    "category": "standard_preference",
                    "automation_action": "auto_answer_from_memory",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "test",
                },
            ],
        }
        profile_payload = {
            "candidate": {
                "name": "Test User",
                "email": "test@example.com",
                "phone": "555-0100",
                "location": "Bellevue, WA",
            },
            "preferences": {},
            "resume_facts": {},
            "question_answers": {},
        }

        preflight = build_critical_input_preflight(
            pack,
            template,
            updates,
            research,
            profile_payload,
            answer_memory={"version": 1, "answers": []},
            approve=True,
        )

        summary = preflight["summary"]
        self.assertEqual(summary["matched_updates"], 2)
        self.assertEqual(summary["critical_ready_before"], 0)
        self.assertEqual(summary["critical_ready_after"], 2)
        self.assertEqual(summary["data_blocking_prompts_before"], 2)
        self.assertEqual(summary["data_blocking_prompts_after"], 0)
        self.assertEqual(summary["positions_ready_for_autofill_before"], 0)
        self.assertEqual(summary["positions_ready_for_autofill_after"], 1)
        self.assertEqual(summary["temp_profile_updates"], 1)
        self.assertEqual(summary["temp_answer_memory_updates"], 1)
        self.assertFalse(preflight["policy"]["writes_real_profile_or_memory"])
        self.assertIn("Critical Input Preflight", render_critical_input_preflight_markdown(preflight))
        self.assertIn("Impact Summary", render_critical_input_preflight_html(preflight))

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            approval_pack_path = root / "pack.json"
            answers_path = root / "answers.json"
            updates_path = root / "updates.json"
            research_path = root / "research.json"
            profile_path = root / "profile.json"
            memory_path = root / "memory.json"
            json_output = root / "preflight.json"
            markdown_output = root / "preflight.md"
            html_output = root / "preflight.html"
            approval_pack_path.write_text(json.dumps(pack), encoding="utf-8")
            answers_path.write_text(json.dumps(template), encoding="utf-8")
            updates_path.write_text(json.dumps(updates), encoding="utf-8")
            research_path.write_text(json.dumps(research), encoding="utf-8")
            profile_path.write_text(json.dumps(profile_payload), encoding="utf-8")

            written = write_critical_input_preflight(
                approval_pack_path,
                answers_path,
                json.loads(updates_path.read_text(encoding="utf-8")),
                research_path,
                profile_path,
                memory_path,
                json_output,
                markdown_output,
                html_output,
                approve=True,
            )

            self.assertEqual(written["summary"]["data_blocking_prompts_after"], 0)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertTrue(html_output.exists())
            saved_profile = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertEqual(saved_profile["question_answers"], {})
            self.assertFalse(memory_path.exists())

    def test_critical_input_preflight_keeps_unconfirmed_high_risk_waiting(self) -> None:
        learning_tasks = {
            "tasks": [
                {
                    "group_key": "answer_memory:citizenship_status:default_policy",
                    "question": "What citizenship answers should automation use?",
                    "recommended_storage": "answer_memory",
                    "answer_scope": "category_default_policy",
                    "suggested_answer_source": "requires_exact_user_confirmation",
                    "approval_risk": "high",
                    "labels": ["Are you a U.S. citizen?"],
                    "platforms": ["Greenhouse"],
                    "required_count": 2,
                    "persist_allowed": True,
                }
            ],
        }
        pack = build_learning_approval_pack(learning_tasks, {})
        template = build_critical_input_answer_template(pack)
        updates = {
            "answer_memory_citizenship_status_default_policy": {
                "user_answer": "I am a U.S. citizen.",
                "approval_decision": "approved",
            }
        }
        research = {
            "positions_observed_total": 1,
            "positions": [
                {
                    "position_key": "greenhouse:example:sre",
                    "platform": "Greenhouse",
                    "company": "Example",
                    "title": "Site Reliability Engineer",
                    "role_family": "SRE",
                }
            ],
            "items": [
                {
                    "position_key": "greenhouse:example:sre",
                    "normalized_label": "are you a u s citizen",
                    "label": "Are you a U.S. citizen?",
                    "category": "standard_preference",
                    "automation_action": "auto_answer_from_memory",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "test",
                }
            ],
        }
        profile_payload = {
            "candidate": {
                "name": "Test User",
                "email": "test@example.com",
                "phone": "555-0100",
                "location": "Bellevue, WA",
            },
            "preferences": {},
            "resume_facts": {},
            "question_answers": {},
        }

        preflight = build_critical_input_preflight(
            pack,
            template,
            updates,
            research,
            profile_payload,
            answer_memory={"version": 1, "answers": []},
            approve=True,
        )

        summary = preflight["summary"]
        self.assertEqual(summary["high_risk_approval_blocked"], 1)
        self.assertEqual(summary["critical_ready_after"], 0)
        self.assertEqual(summary["critical_waiting_after"], 1)
        self.assertEqual(summary["temp_approved_inputs"], 0)
        self.assertEqual(summary["data_blocking_prompts_after"], 1)

    def test_critical_input_impact_report_ranks_simulated_blocker_reduction(self) -> None:
        learning_tasks = {
            "tasks": [
                {
                    "group_key": "profile:zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "recommended_storage": "profile",
                    "labels": ["Zip Code"],
                    "platforms": ["Ashby"],
                    "required_count": 4,
                    "persist_allowed": True,
                },
                {
                    "group_key": "answer_memory:favorite_junk_food",
                    "question": "What's your favorite junk food?",
                    "recommended_storage": "answer_memory",
                    "labels": ["What's your favorite junk food?"],
                    "platforms": ["Greenhouse"],
                    "required_count": 2,
                    "persist_allowed": True,
                },
                {
                    "group_key": "supervised_confirmation:policy_acknowledgement",
                    "question": "May automation mark applicant privacy acknowledgement?",
                    "recommended_storage": "supervised_confirmation",
                    "answer_scope": "supervised_only",
                    "labels": ["Privacy policy"],
                    "platforms": ["Lever"],
                    "required_count": 1,
                    "persist_allowed": False,
                },
            ],
        }
        pack = build_learning_approval_pack(learning_tasks, {})
        template = build_critical_input_answer_template(pack)
        research = {
            "positions_observed_total": 1,
            "positions": [
                {
                    "position_key": "ashby:example:sre",
                    "platform": "Ashby",
                    "company": "Example",
                    "title": "Site Reliability Engineer",
                    "role_family": "SRE",
                }
            ],
            "items": [
                {
                    "position_key": "ashby:example:sre",
                    "normalized_label": "zip code",
                    "label": "Zip Code",
                    "category": "profile_identity",
                    "automation_action": "auto_fill_from_profile",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "test",
                },
                {
                    "position_key": "ashby:example:sre",
                    "normalized_label": "what s your favorite junk food",
                    "label": "What's your favorite junk food?",
                    "category": "standard_preference",
                    "automation_action": "auto_answer_from_memory",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "test",
                },
            ],
        }
        profile_payload = {
            "candidate": {
                "name": "Test User",
                "email": "test@example.com",
                "phone": "555-0100",
                "location": "Bellevue, WA",
            },
            "preferences": {},
            "resume_facts": {},
            "question_answers": {},
        }

        report = build_critical_input_impact_report(
            pack,
            template,
            research,
            profile_payload,
            answer_memory={"version": 1, "answers": []},
        )

        self.assertEqual(report["input_count"], 3)
        self.assertEqual(report["combined_answerable_input_count"], 2)
        self.assertEqual(report["summary"]["baseline_data_blocking_prompts"], 2)
        self.assertEqual(report["summary"]["combined_data_blocking_prompts_after"], 0)
        self.assertEqual(report["combined_remaining_data_blocker_counts"]["total"], 0)
        self.assertTrue(report["policy"]["uses_fake_answers_for_impact_only"])
        impacts = {row["input_id"]: row for row in report["input_impacts"]}
        self.assertEqual(impacts["profile_zip_or_postal_code"]["data_blocking_prompts_delta"], -1)
        self.assertEqual(
            impacts["answer_memory_favorite_junk_food"]["data_blocking_prompts_delta"],
            -1,
        )
        self.assertEqual(
            impacts["supervised_confirmation_policy_acknowledgement"]["temp_approved_inputs"],
            0,
        )
        self.assertIn("Remaining data blocker prompts: 0", render_critical_input_impact_markdown(report))
        self.assertIn("Remaining Data Blockers", render_critical_input_impact_html(report))

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            json_output = root / "impact.json"
            markdown_output = root / "impact.md"
            html_output = root / "impact.html"
            written = write_critical_input_impact_report(
                pack,
                template,
                research,
                profile_payload,
                json_output,
                markdown_output,
                html_output,
                answer_memory={"version": 1, "answers": []},
            )
            self.assertEqual(written["summary"]["combined_data_blocking_prompts_after"], 0)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertTrue(html_output.exists())

    def test_critical_input_status_report_groups_waiting_ready_and_supervised(self) -> None:
        learning_tasks = {
            "tasks": [
                {
                    "group_key": "profile:zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "recommended_storage": "profile",
                    "labels": ["Zip Code"],
                    "platforms": ["Ashby"],
                    "required_count": 4,
                    "persist_allowed": True,
                },
                {
                    "group_key": "answer_memory:favorite_junk_food",
                    "question": "What's your favorite junk food?",
                    "recommended_storage": "answer_memory",
                    "labels": ["What's your favorite junk food?"],
                    "platforms": ["Greenhouse"],
                    "required_count": 2,
                    "persist_allowed": True,
                },
                {
                    "group_key": "supervised_confirmation:policy_acknowledgement",
                    "question": "May automation mark applicant privacy acknowledgement?",
                    "recommended_storage": "supervised_confirmation",
                    "answer_scope": "supervised_only",
                    "labels": ["Privacy policy"],
                    "platforms": ["Lever"],
                    "required_count": 1,
                    "persist_allowed": False,
                },
            ],
        }
        pack = build_learning_approval_pack(learning_tasks, {"manual_gates": [{"label": "Submit"}]})
        answers = build_critical_input_answer_template(pack)
        for item in answers["answers"]:
            if item["group_key"] == "profile:zip_or_postal_code":
                item["user_answer"] = "94105"
                item["approval_decision"] = "approved"
            elif item["group_key"] == "answer_memory:favorite_junk_food":
                item["user_answer"] = "Potato chips"

        report = build_critical_input_status_report(pack, answers)
        self.assertEqual(report["summary"]["input_count"], 3)
        self.assertEqual(report["summary"]["ready_to_apply_count"], 1)
        self.assertEqual(report["summary"]["waiting_for_approval_count"], 1)
        self.assertEqual(report["summary"]["supervised_only_count"], 1)
        self.assertFalse(report["summary"]["ready_for_autofill_recheck"])
        statuses = {row["group_key"]: row["status"] for row in report["rows"]}
        self.assertEqual(statuses["profile:zip_or_postal_code"], "ready_to_apply")
        self.assertEqual(statuses["answer_memory:favorite_junk_food"], "waiting_for_approval")
        self.assertEqual(statuses["supervised_confirmation:policy_acknowledgement"], "supervised_only")
        markdown = render_critical_input_status_markdown(report)
        self.assertIn("Critical Input Status", markdown)
        self.assertIn("waiting_for_approval", markdown)

        with tempfile.TemporaryDirectory() as temp_dir:
            json_output = Path(temp_dir) / "status.json"
            markdown_output = Path(temp_dir) / "status.md"
            written = write_critical_input_status_report(
                pack,
                json_output,
                markdown_output,
                answers_payload=answers,
            )
            self.assertEqual(written["summary"]["ready_to_apply_count"], 1)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())

    def test_critical_input_suggestions_make_review_packet_without_writing_profile(self) -> None:
        learning_tasks = {
            "tasks": [
                {
                    "group_key": "profile:zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "recommended_storage": "profile",
                    "labels": ["Zip Code"],
                    "platforms": ["Ashby"],
                    "required_count": 4,
                    "persist_allowed": True,
                },
                {
                    "group_key": "answer_memory:citizenship_status:default_policy",
                    "question": "What citizenship answers should automation use?",
                    "recommended_storage": "answer_memory",
                    "answer_scope": "category_default_policy",
                    "suggested_answer_source": "requires_exact_user_confirmation",
                    "approval_risk": "high",
                    "labels": ["Are you a U.S. citizen?"],
                    "platforms": ["Greenhouse"],
                    "required_count": 2,
                    "persist_allowed": True,
                },
                {
                    "group_key": "supervised_confirmation:policy_acknowledgement",
                    "question": "May automation mark applicant privacy acknowledgement?",
                    "recommended_storage": "supervised_confirmation",
                    "answer_scope": "supervised_only",
                    "labels": ["Privacy policy"],
                    "platforms": ["Lever"],
                    "required_count": 1,
                    "persist_allowed": False,
                },
                {
                    "group_key": "answer_memory:startup_culture",
                    "question": "What aspects of startup culture resonate with you?",
                    "recommended_storage": "answer_memory",
                    "labels": ["What aspects of startup culture resonate with you?"],
                    "suggested_answer": "Ownership, fast feedback loops, and production impact.",
                    "suggested_answer_source": "standard_startup_working_style",
                    "platforms": ["Ashby"],
                    "required_count": 1,
                    "persist_allowed": True,
                },
            ],
        }
        profile = CandidateProfile.from_mapping(
            {
                "candidate": {"name": "Test User", "location": "Bellevue, WA"},
                "question_answers": {
                    "zip_code": "98004",
                    "authorization": "I am authorized to work in the United States.",
                    "sponsorship": "Yes, I require sponsorship.",
                    "policy_acknowledgement": "Yes, I acknowledge.",
                },
                "preferences": {},
                "resume_facts": {},
            }
        )
        pack = build_learning_approval_pack(learning_tasks, {})
        template = build_critical_input_answer_template(pack)
        for row in template["critical_inputs"]:
            if row["group_key"] == "answer_memory:startup_culture":
                row["user_answer"] = ""

        packet = build_critical_input_suggestion_packet(template, profile=profile, answer_memory=None)
        rows = {row["input_id"]: row for row in packet["critical_inputs"]}
        markdown = render_critical_input_suggestions_markdown(packet)

        self.assertEqual(packet["input_count"], 4)
        self.assertEqual(packet["direct_suggestion_count"], 3)
        self.assertFalse(packet["policy"]["writes_profile_or_memory"])
        self.assertEqual(rows["profile_zip_or_postal_code"]["suggested_answer"], "98004")
        self.assertEqual(
            rows["answer_memory_startup_culture"]["suggested_answer"],
            "Ownership, fast feedback loops, and production impact.",
        )
        self.assertEqual(
            rows["answer_memory_startup_culture"]["suggestion_source"],
            "standard_startup_working_style",
        )
        self.assertTrue(rows["profile_zip_or_postal_code"]["can_copy_to_user_answer_after_review"])
        self.assertIn("sponsorship", rows["answer_memory_citizenship_status_default_policy"]["review_context"])
        self.assertEqual(
            rows["supervised_confirmation_policy_acknowledgement"]["recommended_action"],
            "supervised_browser_review_only",
        )
        self.assertIn("Critical Input Suggestions", markdown)

        with tempfile.TemporaryDirectory() as temp_dir:
            json_output = Path(temp_dir) / "suggestions.json"
            markdown_output = Path(temp_dir) / "suggestions.md"
            written = write_critical_input_suggestion_packet(
                template,
                json_output,
                markdown_output,
                profile=profile,
            )

            self.assertEqual(written["input_count"], 4)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertIn("98004", markdown_output.read_text())

    def test_critical_input_unblocker_packet_filters_only_missing_suggestions(self) -> None:
        suggestions_payload = {
            "critical_inputs": [
                {
                    "input_id": "profile_zip_or_postal_code",
                    "input_type": "profile_or_resume_fact",
                    "group_key": "profile:zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "required_user_response": "Provide exact ZIP/postal code.",
                    "suggested_answer": "",
                    "suggestion_source": "profile.location_without_zip",
                    "suggestion_note": "Profile has city but no exact ZIP.",
                    "required_count": 4,
                    "platforms": ["Ashby"],
                    "labels": ["Zip Code"],
                },
                {
                    "input_id": "answer_memory_citizenship_status_default_policy",
                    "input_type": "high_risk_exact_confirmation",
                    "group_key": "answer_memory:citizenship_status:default_policy",
                    "question": "What citizenship answers should automation use?",
                    "required_user_response": "Confirm exact truthful legal answer.",
                    "suggested_answer": "",
                    "suggestion_source": "requires_exact_user_confirmation",
                    "suggestion_note": "Citizenship must not be inferred.",
                    "required_count": 2,
                    "platforms": ["Greenhouse"],
                    "labels": ["Are you a U.S. Citizen?"],
                },
                {
                    "input_id": "answer_memory_startup_culture",
                    "input_type": "exact_prompt_answer",
                    "group_key": "answer_memory:startup_culture",
                    "question": "What aspects of startup culture resonate with you?",
                    "suggested_answer": "Ownership and fast feedback loops.",
                    "required_count": 1,
                    "platforms": ["Ashby"],
                    "labels": ["What aspects of startup culture resonate with you?"],
                },
            ],
        }
        answers_payload = {
            "critical_inputs": [
                {
                    "input_id": "profile_zip_or_postal_code",
                    "input_type": "profile_or_resume_fact",
                    "group_key": "profile:zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "user_answer": "",
                },
                {
                    "input_id": "answer_memory_citizenship_status_default_policy",
                    "input_type": "high_risk_exact_confirmation",
                    "group_key": "answer_memory:citizenship_status:default_policy",
                    "question": "What citizenship answers should automation use?",
                    "approval_risk": "high",
                    "user_answer": "",
                },
                {
                    "input_id": "answer_memory_startup_culture",
                    "input_type": "exact_prompt_answer",
                    "group_key": "answer_memory:startup_culture",
                    "question": "What aspects of startup culture resonate with you?",
                    "user_answer": "Ownership and fast feedback loops.",
                },
            ],
            "answers": [],
        }
        impact_payload = {
            "input_impacts": [
                {
                    "input_id": "profile_zip_or_postal_code",
                    "data_blocking_prompts_delta": -4,
                    "ready_prompts_delta": 4,
                    "positions_ready_for_autofill_delta": 5,
                }
            ]
        }

        packet = build_critical_input_unblocker_packet(
            suggestions_payload,
            impact_payload=impact_payload,
        )
        markdown = render_critical_input_unblocker_markdown(packet)
        html = render_critical_input_unblocker_html(packet)

        self.assertEqual(packet["input_count"], 2)
        self.assertEqual(packet["high_risk_count"], 1)
        self.assertEqual(packet["profile_or_resume_fact_count"], 1)
        self.assertEqual(packet["full_update_count"], 3)
        self.assertEqual(packet["prefilled_update_count"], 1)
        self.assertEqual(packet["missing_exact_update_count"], 2)
        self.assertEqual(packet["unblockers"][0]["input_id"], "profile_zip_or_postal_code")
        self.assertEqual(packet["compact_updates_template"]["profile_zip_or_postal_code"], "")
        self.assertEqual(
            packet["full_updates_template"]["answer_memory_startup_culture"],
            "Ownership and fast feedback loops.",
        )
        self.assertEqual(
            packet["compact_updates_template"]["answer_memory_citizenship_status_default_policy"],
            {
                "user_answer": "",
                "approval_decision": "approved",
                "high_risk_user_confirmed": False,
            },
        )
        self.assertNotIn("answer_memory_startup_culture", packet["compact_updates_template"])
        self.assertIn("answer_memory_startup_culture", packet["full_updates_template"])
        self.assertIn("--approve-high-risk", packet["workflow_command"])
        self.assertIn("Critical Input Final Unblockers", markdown)
        self.assertIn("Load full one-shot template", html)
        self.assertIn("Build full one-shot JSON", html)
        self.assertIn("collectUnblockerValues", html)
        self.assertIn("high-risk confirmations missing", html)
        self.assertIn("full one-shot JSON includes prefilled draft answers", html)

        full_updates = json.loads(json.dumps(packet["full_updates_template"]))
        full_updates["profile_zip_or_postal_code"] = "98004"
        full_updates["answer_memory_citizenship_status_default_policy"]["user_answer"] = "Synthetic truthful answer."
        full_updates["answer_memory_citizenship_status_default_policy"]["high_risk_user_confirmed"] = True
        update_report = build_critical_input_answer_update(
            answers_payload,
            full_updates,
            approve=True,
            approve_high_risk=True,
        )
        self.assertEqual(update_report["summary"]["ready_after_update_count"], 3)
        self.assertEqual(update_report["summary"]["waiting_after_update_count"], 0)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            json_output = root / "unblockers.json"
            markdown_output = root / "unblockers.md"
            html_output = root / "unblockers.html"
            written = write_critical_input_unblocker_packet(
                suggestions_payload,
                json_output,
                markdown_output,
                html_output,
                impact_payload=impact_payload,
            )

            self.assertEqual(written["input_count"], 2)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertTrue(html_output.exists())

    def test_critical_input_unblocker_final_update_merges_compact_answers_with_full_template(self) -> None:
        unblockers = {
            "unblockers": [
                {
                    "input_id": "profile_zip_or_postal_code",
                    "high_risk": False,
                },
                {
                    "input_id": "answer_memory_citizenship_status_default_policy",
                    "high_risk": True,
                },
            ]
        }
        full_template = {
            "answer_memory_employment_history_default_policy": "No prior employment unless specifically confirmed.",
            "profile_zip_or_postal_code": "",
            "answer_memory_citizenship_status_default_policy": {
                "user_answer": "",
                "approval_decision": "approved",
                "high_risk_user_confirmed": False,
            },
        }
        incomplete = {
            "profile_zip_or_postal_code": "98004",
            "answer_memory_citizenship_status_default_policy": {
                "user_answer": "U.S. citizen; no restricted-country citizenship or permanent residency.",
                "approval_decision": "approved",
                "high_risk_user_confirmed": False,
            },
        }

        blocked = build_critical_input_unblocker_final_update(
            incomplete,
            full_template,
            unblocker_packet=unblockers,
        )
        self.assertFalse(blocked["ready_for_workflow"])
        self.assertEqual(blocked["summary"]["merged_update_count"], 3)
        self.assertEqual(blocked["missing_unblocker_ids"], [])
        self.assertEqual(
            blocked["unconfirmed_high_risk_ids"],
            ["answer_memory_citizenship_status_default_policy"],
        )
        self.assertEqual(
            blocked["merged_updates"]["answer_memory_employment_history_default_policy"],
            "No prior employment unless specifically confirmed.",
        )

        complete = json.loads(json.dumps(incomplete))
        complete["answer_memory_citizenship_status_default_policy"]["high_risk_user_confirmed"] = True
        ready = build_critical_input_unblocker_final_update(
            complete,
            full_template,
            unblocker_packet=unblockers,
        )
        markdown = render_critical_input_unblocker_final_update_markdown(ready)

        self.assertTrue(ready["ready_for_workflow"])
        self.assertEqual(ready["summary"]["missing_unblocker_count"], 0)
        self.assertEqual(ready["summary"]["unconfirmed_high_risk_count"], 0)
        self.assertIn("critical_input_confirmed_updates_latest.json", ready["workflow_command"])
        self.assertIn("Ready for workflow: true", markdown)

        synthetic_compact = build_synthetic_unblocker_compact_updates(unblockers)
        self.assertEqual(synthetic_compact["profile_zip_or_postal_code"], "99999")
        self.assertTrue(
            synthetic_compact["answer_memory_citizenship_status_default_policy"][
                "high_risk_user_confirmed"
            ]
        )
        self.assertIn(
            "Synthetic rehearsal answer",
            synthetic_compact["answer_memory_citizenship_status_default_policy"]["user_answer"],
        )
        synthetic_ready = build_critical_input_unblocker_final_update(
            synthetic_compact,
            full_template,
            unblocker_packet=unblockers,
        )
        self.assertTrue(synthetic_ready["ready_for_workflow"])
        self.assertEqual(synthetic_ready["summary"]["missing_unblocker_count"], 0)
        self.assertEqual(synthetic_ready["summary"]["unconfirmed_high_risk_count"], 0)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            compact_path = root / "compact.json"
            full_path = root / "full.json"
            unblockers_path = root / "unblockers.json"
            updates_output = root / "confirmed.json"
            json_output = root / "report.json"
            markdown_output = root / "report.md"
            compact_path.write_text(json.dumps(complete), encoding="utf-8")
            full_path.write_text(json.dumps(full_template), encoding="utf-8")
            unblockers_path.write_text(json.dumps(unblockers), encoding="utf-8")

            written = write_critical_input_unblocker_final_update(
                compact_path,
                full_path,
                unblockers_path,
                updates_output,
                json_output,
                markdown_output,
            )

            self.assertTrue(written["ready_for_workflow"])
            self.assertTrue(updates_output.exists())
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            confirmed_updates = json.loads(updates_output.read_text(encoding="utf-8"))
            self.assertIn("answer_memory_employment_history_default_policy", confirmed_updates)
            self.assertEqual(confirmed_updates["profile_zip_or_postal_code"], "98004")

    def test_final_answer_intake_builds_compact_updates_from_alias_answers(self) -> None:
        unblockers = {
            "unblockers": [
                {
                    "input_id": "profile_zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "required_user_response": "Provide exact ZIP/postal code.",
                    "high_risk": False,
                    "required_count": 4,
                    "platforms": ["Ashby"],
                    "labels": ["Zip Code"],
                },
                {
                    "input_id": "answer_memory_citizenship_status_default_policy",
                    "input_type": "high_risk_exact_confirmation",
                    "question": "What citizenship answers should automation use?",
                    "required_user_response": "Confirm the exact truthful legal answer.",
                    "high_risk": True,
                    "required_count": 7,
                    "platforms": ["Greenhouse"],
                    "labels": ["Are you a U.S. Citizen?"],
                },
            ]
        }
        template = build_final_answer_intake_template(unblockers)
        template_markdown = render_final_answer_intake_template_markdown(template)
        template_html = render_final_answer_intake_template_html(template)
        server_template_html = render_final_answer_intake_template_html(template, save_endpoint="/save")

        self.assertEqual(template["answer_count"], 2)
        self.assertEqual(template["high_risk_count"], 1)
        self.assertEqual(template["aliases"]["zip_or_postal_code"], "profile_zip_or_postal_code")
        self.assertIn("answer_format_hint", template["fields"][0])
        self.assertIn("answer_specificity_hint", template["fields"][0])
        self.assertIn("answer_example_shape", template["fields"][0])
        self.assertIn("citizenship_status", template["answers"])
        self.assertIn("Final Answer Intake Template", template_markdown)
        self.assertIn("zip_or_postal_code", template_markdown)
        self.assertIn("Answer format hint", template_markdown)
        self.assertIn("Specificity check", template_markdown)
        self.assertIn("Answer Shape Examples", template_markdown)
        self.assertIn("[ZIP_CODE]", template_markdown)
        self.assertIn("Final Answer Intake", template_html)
        self.assertIn('data-answer="zip_or_postal_code"', template_html)
        self.assertIn('data-high-risk="false"', template_html)
        self.assertIn('data-confirm="citizenship_status"', template_html)
        self.assertIn('data-specificity-status="citizenship_status"', template_html)
        self.assertIn("clientSpecificityReason", template_html)
        self.assertIn("answer(s) need more specificity", template_html)
        self.assertIn("readiness-summary", template_html)
        self.assertIn("answer(s) missing", template_html)
        self.assertIn("Specificity check", template_html)
        self.assertIn("Example shape", template_html)
        self.assertIn("Generated JSON", template_html)
        self.assertNotIn("Save and validate locally", template_html)
        self.assertIn("Save and validate locally", server_template_html)
        self.assertIn('fetch(SAVE_ENDPOINT', server_template_html)
        preserved_template = build_final_answer_intake_template(
            unblockers,
            existing_intake_payload={
                "answers": {
                    "zip_or_postal_code": "98004",
                    "citizenship_status": {
                        "answer": "U.S. citizen.",
                        "high_risk_user_confirmed": True,
                    },
                }
            },
        )
        self.assertEqual(preserved_template["answers"]["zip_or_postal_code"], "98004")
        self.assertEqual(preserved_template["answers"]["citizenship_status"]["answer"], "U.S. citizen.")
        self.assertTrue(preserved_template["answers"]["citizenship_status"]["high_risk_user_confirmed"])

        unconfirmed = build_final_answer_intake_update(
            unblockers,
            {
                "answers": {
                    "zip_or_postal_code": "98004",
                    "citizenship_status": {
                        "answer": "U.S. citizen; no restricted-country citizenship or permanent residency.",
                        "high_risk_user_confirmed": False,
                    },
                }
            },
        )
        self.assertFalse(unconfirmed["ready_for_finalize"])
        self.assertEqual(
            unconfirmed["unconfirmed_high_risk_ids"],
            ["answer_memory_citizenship_status_default_policy"],
        )
        vague = build_final_answer_intake_update(
            unblockers,
            {
                "answers": {
                    "zip_or_postal_code": "98004",
                    "citizenship_status": {
                        "answer": "yes",
                        "high_risk_user_confirmed": True,
                    },
                }
            },
        )
        self.assertFalse(vague["ready_for_finalize"])
        self.assertEqual(vague["summary"]["needs_more_specific_answer_count"], 1)
        self.assertEqual(
            vague["needs_more_specific_answer_ids"],
            ["answer_memory_citizenship_status_default_policy"],
        )
        self.assertNotIn("answer_memory_citizenship_status_default_policy", vague["compact_updates"])
        self.assertEqual(vague["fields"][1]["status"], "needs_more_specific_answer")

        ready = build_final_answer_intake_update(
            unblockers,
            {
                "answers": {
                    "zip_or_postal_code": "98004",
                    "citizenship_status": {
                        "answer": "U.S. citizen; no restricted-country citizenship or permanent residency.",
                        "high_risk_user_confirmed": True,
                    },
                }
            },
        )
        update_markdown = render_final_answer_intake_update_markdown(ready)

        self.assertTrue(ready["ready_for_finalize"])
        self.assertEqual(ready["summary"]["compact_update_count"], 2)
        self.assertEqual(ready["summary"]["needs_more_specific_answer_count"], 0)
        self.assertEqual(ready["compact_updates"]["profile_zip_or_postal_code"], "98004")
        self.assertTrue(
            ready["compact_updates"]["answer_memory_citizenship_status_default_policy"][
                "high_risk_user_confirmed"
            ]
        )
        self.assertIn("Ready for finalize: true", update_markdown)
        self.assertIn("answers needing more specificity: 0", update_markdown)
        self.assertIn("critical-input-unblockers-finalize", update_markdown)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template_json = root / "template.json"
            template_md = root / "template.md"
            template_html_path = root / "template.html"
            updates_json = root / "compact.json"
            report_json = root / "report.json"
            report_md = root / "report.md"
            saved_template_json = root / "saved_template.json"
            saved_template_md = root / "saved_template.md"
            saved_template_html = root / "saved_template.html"
            saved_updates_json = root / "saved_compact.json"
            saved_report_json = root / "saved_report.json"
            saved_report_md = root / "saved_report.md"

            written_template = write_final_answer_intake_template(
                unblockers,
                template_json,
                template_md,
                template_html_path,
            )
            written_report = write_final_answer_intake_update(
                unblockers,
                {"answers": {"zip_or_postal_code": "98004", "citizenship_status": "U.S. citizen."}},
                updates_json,
                report_json,
                report_md,
                confirm_high_risk=True,
            )

            self.assertEqual(written_template["answer_count"], 2)
            self.assertTrue(written_report["ready_for_finalize"])
            self.assertTrue(template_json.exists())
            self.assertTrue(template_md.exists())
            self.assertTrue(template_html_path.exists())
            self.assertTrue(updates_json.exists())
            self.assertTrue(report_json.exists())
            self.assertTrue(report_md.exists())
            compact_updates = json.loads(updates_json.read_text(encoding="utf-8"))
            self.assertEqual(compact_updates["profile_zip_or_postal_code"], "98004")
            self.assertTrue(
                compact_updates["answer_memory_citizenship_status_default_policy"][
                    "high_risk_user_confirmed"
                ]
            )
            save_result = save_final_answer_intake_payload(
                unblockers,
                {
                    "source": "final_answer_intake_template",
                    "answers": {
                        "zip_or_postal_code": "98004",
                        "citizenship_status": {
                            "answer": "U.S. citizen.",
                            "high_risk_user_confirmed": True,
                        },
                    },
                },
                saved_template_json,
                saved_template_md,
                saved_template_html,
                saved_updates_json,
                saved_report_json,
                saved_report_md,
            )
            self.assertTrue(save_result["ready_for_finalize"])
            self.assertFalse(save_result["policy"]["writes_profile_or_memory"])
            self.assertFalse(save_result["policy"]["submits_real_applications"])
            self.assertTrue(saved_template_json.exists())
            self.assertTrue(saved_template_md.exists())
            self.assertTrue(saved_template_html.exists())
            self.assertTrue(saved_updates_json.exists())
            self.assertTrue(saved_report_json.exists())
            self.assertTrue(saved_report_md.exists())
            saved_compact_updates = json.loads(saved_updates_json.read_text(encoding="utf-8"))
            self.assertEqual(saved_compact_updates["profile_zip_or_postal_code"], "98004")
            self.assertTrue(
                saved_compact_updates["answer_memory_citizenship_status_default_policy"][
                    "high_risk_user_confirmed"
                ]
            )

    def test_final_answer_blocker_report_and_telegram_alert_exclude_answer_text(self) -> None:
        unblockers = {
            "unblockers": [
                {
                    "input_id": "profile_zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "required_user_response": "Provide exact ZIP/postal code.",
                    "high_risk": False,
                    "required_count": 4,
                    "platforms": ["Ashby"],
                    "labels": ["Zip Code", "Postal Code"],
                    "why_not_inferred": "Profile has a city but no exact ZIP/postal code.",
                },
                {
                    "input_id": "answer_memory_citizenship_status_default_policy",
                    "input_type": "high_risk_exact_confirmation",
                    "question": "What citizenship answers should automation use?",
                    "required_user_response": "Confirm the exact truthful legal answer.",
                    "high_risk": True,
                    "required_count": 7,
                    "platforms": ["Greenhouse"],
                    "labels": ["Are you a U.S. Citizen?", "Are you a U.S. Person?"],
                    "why_not_inferred": "Work authorization exists but citizenship needs exact confirmation.",
                },
            ]
        }
        template = build_final_answer_intake_template(
            unblockers,
            existing_intake_payload={
                "answers": {
                    "zip_or_postal_code": "98004",
                    "citizenship_status": {
                        "answer": "Sensitive citizenship answer phrase 12345.",
                        "high_risk_user_confirmed": False,
                    },
                }
            },
        )
        goal_audit = {
            "status": "needs_user_answers",
            "goal_complete": False,
            "blocker_summary": {
                "final_answer_waiting_count_after_drafts": 1,
                "position_execution_remaining_user_answers": 0,
                "position_execution_global_remaining_user_answers": 1,
                "selected_queue_supervised_autofill_ready": True,
                "post_answer_synthetic_queue_rehearsal_ready": True,
                "post_answer_text_reply_rehearsal_ready": True,
                "post_answer_intake_answer_count": 6,
                "post_answer_intake_missing_unblocker_count": 0,
                "post_answer_intake_unconfirmed_high_risk_count": 0,
                "post_answer_intake_needs_more_specific_answer_count": 0,
                "post_answer_intake_unknown_answer_count": 0,
                "post_answer_synthetic_autofill_selected_count": 100,
                "post_answer_synthetic_selector_miss_count": 0,
                "post_answer_synthetic_final_submit_stop_count": 100,
            },
        }
        report = build_final_answer_blocker_report(template, goal_audit=goal_audit)
        markdown = render_final_answer_blocker_report_markdown(report)
        alert = build_telegram_final_answer_blocker_alert(report)

        self.assertFalse(report["ready_for_post_answer_pipeline"])
        self.assertTrue(report["ready_after_truthful_answer_reply"])
        self.assertEqual(report["summary"]["blocker_count"], 1)
        self.assertEqual(report["summary"]["missing_answer_count"], 0)
        self.assertEqual(report["summary"]["unconfirmed_high_risk_count"], 1)
        self.assertTrue(report["summary"]["ready_after_truthful_answer_reply"])
        self.assertTrue(report["automation_after_answers"]["text_reply_rehearsal_ready"])
        self.assertEqual(report["automation_after_answers"]["synthetic_selected_count"], 100)
        self.assertEqual(report["automation_after_answers"]["intake_validation"]["answer_count"], 6)
        self.assertEqual(report["blockers"][0]["alias"], "citizenship_status")
        self.assertIn("answer_example_shape", report["blockers"][0])
        self.assertEqual(report["blockers"][0]["observed_prompt_count"], 2)
        self.assertIn("Are you a U.S. Citizen?", report["blockers"][0]["observed_prompt_examples"])
        self.assertIn("why_not_inferred", report["blockers"][0])
        self.assertEqual(
            report["reply_template_lines"],
            ["citizenship_status\uff1a<fill>", "citizenship_status_confirmed\uff1a\u786e\u8ba4"],
        )
        reply_template_text = render_final_answer_reply_template_text(report)
        self.assertIn("rehearse-after-answers", report["next_commands"][0])
        self.assertIn("resume-after-answers --reply-text", report["next_commands"][1])
        self.assertIn("--validate-only", report["next_commands"][1])
        self.assertIn("--validate-only", report["next_commands"][2])
        self.assertIn("resume-after-answers", report["next_commands"][3])
        self.assertIn("Final Answer Blockers", markdown)
        self.assertIn("citizenship_status", markdown)
        self.assertIn("Example Shape", markdown)
        self.assertIn("Why Not Inferred", markdown)
        self.assertIn("Observed Prompt Examples", markdown)
        self.assertIn("Are you a U.S. Citizen?", markdown)
        self.assertIn("Ready after truthful answer reply: true", markdown)
        self.assertIn("## Automation After Answers", markdown)
        self.assertIn("text reply rehearsal ready: true", markdown)
        self.assertIn("synthetic packet: selected 100, selector misses 0, final-submit stops 100", markdown)
        self.assertIn("## Reply Template", markdown)
        self.assertIn("citizenship_status\uff1a<fill>", markdown)
        self.assertIn("\u786e\u8ba4", markdown)
        self.assertIn("citizenship_status_confirmed\uff1a\u786e\u8ba4", reply_template_text)
        self.assertIn("citizenship_status shape:", reply_template_text)
        self.assertIn("citizenship_status why not inferred:", reply_template_text)
        self.assertIn("citizenship_status seen prompt:", reply_template_text)
        self.assertIn("Final answer reply template", reply_template_text)
        self.assertIn("Job automation needs final answers", alert)
        self.assertIn("After-answer path ready: yes", alert)
        self.assertIn("citizenship_status", alert)
        self.assertIn("Shape:", alert)
        self.assertIn("Reply format:", alert)
        self.assertIn("citizenship_status\uff1a<fill>", alert)
        self.assertIn("citizenship_status_confirmed\uff1a\u786e\u8ba4", alert)
        self.assertIn("\u786e\u8ba4", alert)
        self.assertNotIn("98004", json.dumps(report))
        self.assertNotIn("98004", markdown)
        self.assertNotIn("98004", alert)
        self.assertNotIn("98004", reply_template_text)
        self.assertNotIn("Sensitive citizenship answer phrase 12345", json.dumps(report))
        self.assertNotIn("Sensitive citizenship answer phrase 12345", markdown)
        self.assertNotIn("Sensitive citizenship answer phrase 12345", alert)
        self.assertNotIn("Sensitive citizenship answer phrase 12345", reply_template_text)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            json_output = root / "blockers.json"
            markdown_output = root / "blockers.md"
            reply_template_output = root / "reply_template.txt"
            env_path = root / "telegram.env"
            env_path.write_text(
                'export SIGNAL_DECK_TELEGRAM_BOT_TOKEN="token-123"\n'
                'export SIGNAL_DECK_TELEGRAM_CHAT_ID="111"\n',
                encoding="utf-8",
            )
            written = write_final_answer_blocker_report(
                template,
                goal_audit,
                json_output,
                markdown_output,
                reply_template_output,
            )
            notify_result = notify_telegram_for_final_answer_blockers(
                written,
                env_path=env_path,
                dry_run=True,
            )
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertTrue(reply_template_output.exists())
            self.assertIn(
                "citizenship_status_confirmed\uff1a\u786e\u8ba4",
                reply_template_output.read_text(encoding="utf-8"),
            )
            self.assertTrue(notify_result["ok"])
            self.assertTrue(notify_result["skipped"])
            self.assertNotIn("Sensitive citizenship answer phrase 12345", notify_result["message"])

    def test_final_answer_reply_text_builds_ready_intake_without_markdown_answer_text(self) -> None:
        unblockers = {
            "unblockers": [
                {
                    "input_id": "profile_zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "high_risk": False,
                    "required_count": 56,
                },
                {
                    "input_id": "answer_memory_citizenship_status_default_policy",
                    "input_type": "high_risk_exact_confirmation",
                    "question": "What citizenship answers should automation use?",
                    "high_risk": True,
                    "required_count": 57,
                },
                {
                    "input_id": "answer_memory_background_or_export_control_default_policy",
                    "input_type": "high_risk_exact_confirmation",
                    "question": "What background/export-control answers should automation use?",
                    "high_risk": True,
                    "required_count": 31,
                },
                {
                    "input_id": "answer_memory_country_work_permit_default_policy",
                    "input_type": "high_risk_exact_confirmation",
                    "question": "What country work permit answers should automation use?",
                    "high_risk": True,
                    "required_count": 28,
                },
                {
                    "input_id": "answer_memory_interview_recording_consent_default_policy",
                    "input_type": "high_risk_exact_confirmation",
                    "question": "Should automation consent to interview recording?",
                    "high_risk": True,
                    "required_count": 18,
                },
                {
                    "input_id": "answer_memory_health_requirement_default_policy",
                    "input_type": "high_risk_exact_confirmation",
                    "question": "What health requirement answer should automation use?",
                    "high_risk": True,
                    "required_count": 2,
                },
            ]
        }
        template = build_final_answer_intake_template(unblockers)
        reply_text = "\n".join(
            [
                "zip_or_postal_code: 98004",
                "citizenship_status: U.S. citizen; no restricted-country citizenship or permanent residency.",
                "citizenship_status_confirmed: yes",
                "background_or_export_control: No disqualifying background, export-control, indictment, debarment, substance, firearm, felony, or legal-eligibility issues; no exceptions.",
                "background_or_export_control_confirmed: yes",
                "country_work_permit: Authorized to work in the United States; no non-U.S. country work permits or visa sponsorship exceptions should be assumed.",
                "country_work_permit_confirmed: yes",
                "interview_recording_consent: Yes, I consent to interview recording, transcription, AI notetakers, and interview analysis.",
                "interview_recording_consent_confirmed: yes",
                "health_requirement: I can comply with standard health or vaccination requirements for client-site access; no exceptions.",
                "health_requirement_confirmed: yes",
            ]
        )
        reply_report = build_final_answer_reply_intake(template, reply_text)
        reply_markdown = render_final_answer_reply_intake_markdown(reply_report)
        intake_report = build_final_answer_intake_update(unblockers, reply_report["intake_payload"])

        self.assertEqual(reply_report["answer_count"], 6)
        self.assertEqual(reply_report["unknown_key_count"], 0)
        self.assertEqual(reply_report["duplicate_key_count"], 0)
        self.assertEqual(len(reply_report["confirmed_high_risk_aliases"]), 5)
        self.assertTrue(intake_report["ready_for_finalize"])
        self.assertEqual(intake_report["summary"]["compact_update_count"], 6)
        self.assertIn("Final Answer Reply Intake", reply_markdown)
        self.assertIn("zip_or_postal_code", reply_markdown)
        self.assertNotIn("98004", reply_markdown)
        self.assertNotIn("U.S. citizen", reply_markdown)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reply_json = root / "reply.json"
            reply_md = root / "reply.md"
            compact_json = root / "compact.json"
            report_json = root / "report.json"
            report_md = root / "report.md"
            written_reply = write_final_answer_reply_intake(
                template,
                reply_text,
                reply_json,
                reply_md,
            )
            written_intake = write_final_answer_intake_update(
                unblockers,
                written_reply["intake_payload"],
                compact_json,
                report_json,
                report_md,
            )
            self.assertTrue(written_intake["ready_for_finalize"])
            self.assertTrue(reply_json.exists())
            self.assertTrue(reply_md.exists())
            self.assertNotIn("98004", reply_md.read_text(encoding="utf-8"))

            template_path = root / "template.json"
            unblockers_path = root / "unblockers.json"
            reply_path = root / "reply.txt"
            intake_payload_json = root / "intake_payload.json"
            full_template_json = root / "full_template.json"
            confirmed_updates_json = root / "confirmed_updates.json"
            confirmed_report_json = root / "confirmed_report.json"
            confirmed_report_md = root / "confirmed_report.md"
            post_answer_json = root / "post_answer.json"
            post_answer_md = root / "post_answer.md"
            template_path.write_text(json.dumps(template, ensure_ascii=True, indent=2), encoding="utf-8")
            unblockers_path.write_text(json.dumps(unblockers, ensure_ascii=True, indent=2), encoding="utf-8")
            reply_path.write_text(reply_text, encoding="utf-8")
            full_template_json.write_text(
                json.dumps(
                    {str(row["input_id"]): "" for row in unblockers["unblockers"]},
                    ensure_ascii=True,
                    indent=2,
                ),
                encoding="utf-8",
            )
            cli_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "job_apply_agent",
                    "final-answer-reply",
                    "--template",
                    str(template_path),
                    "--unblockers",
                    str(unblockers_path),
                    "--reply-file",
                    str(reply_path),
                    "--json-output",
                    str(root / "cli_reply.json"),
                    "--markdown-output",
                    str(root / "cli_reply.md"),
                    "--intake-output",
                    str(intake_payload_json),
                    "--compact-updates-output",
                    str(root / "cli_compact.json"),
                    "--final-answer-intake-report-json",
                    str(root / "cli_intake_report.json"),
                    "--final-answer-intake-report-markdown",
                    str(root / "cli_intake_report.md"),
                    "--full-template",
                    str(full_template_json),
                    "--confirmed-updates-output",
                    str(confirmed_updates_json),
                    "--confirmed-report-json-output",
                    str(confirmed_report_json),
                    "--confirmed-report-markdown-output",
                    str(confirmed_report_md),
                    "--run-post-answer-pipeline",
                    "--post-answer-json-output",
                    str(post_answer_json),
                    "--post-answer-markdown-output",
                    str(post_answer_md),
                    "--fail-on-not-ready",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(cli_result.returncode, 0, cli_result.stderr)
            intake_payload = json.loads(intake_payload_json.read_text(encoding="utf-8"))
            post_answer_report = json.loads(post_answer_json.read_text(encoding="utf-8"))
            self.assertIn("answers", intake_payload)
            self.assertEqual(post_answer_report["status"], "ready_for_apply")
            self.assertTrue(post_answer_report["ready_for_workflow"])
            self.assertFalse(post_answer_report["apply_requested"])
            self.assertIn("Wrote final answer intake payload JSON", cli_result.stdout)

            resume_help = subprocess.run(
                [sys.executable, "-m", "job_apply_agent", "resume-after-answers", "--help"],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(resume_help.returncode, 0, resume_help.stderr)
            self.assertIn("--reply-text", resume_help.stdout)
            self.assertIn("--reply-file", resume_help.stdout)
            self.assertIn("--validate-only", resume_help.stdout)

    def test_final_answer_reply_accepts_chinese_colon_and_confirmations(self) -> None:
        unblockers = {
            "unblockers": [
                {
                    "input_id": "profile_zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "high_risk": False,
                    "required_count": 56,
                },
                {
                    "input_id": "answer_memory_health_requirement_default_policy",
                    "question": "What health requirement answer should automation use?",
                    "high_risk": True,
                    "required_count": 2,
                },
            ]
        }
        template = build_final_answer_intake_template(unblockers)
        reply_text = "\n".join(
            [
                "1. zip_or_postal_code\uff1a98004",
                "2. health_requirement\uff1aI can comply with standard health or vaccination requirements; no exceptions.",
                "3. health_requirement_confirmed\uff1a\u786e\u8ba4",
            ]
        )

        reply_report = build_final_answer_reply_intake(template, reply_text)
        intake_report = build_final_answer_intake_update(unblockers, reply_report["intake_payload"])

        self.assertEqual(reply_report["answer_count"], 2)
        self.assertEqual(reply_report["unknown_key_count"], 0)
        self.assertEqual(reply_report["confirmed_high_risk_aliases"], ["health_requirement"])
        self.assertTrue(intake_report["ready_for_finalize"])

    def test_final_answer_reply_accepts_chinese_labels_and_common_short_labels(self) -> None:
        unblockers = {
            "unblockers": [
                {
                    "input_id": "profile_zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "high_risk": False,
                    "required_count": 56,
                },
                {
                    "input_id": "answer_memory_citizenship_status_default_policy",
                    "input_type": "high_risk_exact_confirmation",
                    "question": "What citizenship answers should automation use?",
                    "high_risk": True,
                    "required_count": 57,
                },
                {
                    "input_id": "answer_memory_background_or_export_control_default_policy",
                    "input_type": "high_risk_exact_confirmation",
                    "question": "What background/export-control answers should automation use?",
                    "high_risk": True,
                    "required_count": 31,
                },
                {
                    "input_id": "answer_memory_country_work_permit_default_policy",
                    "input_type": "high_risk_exact_confirmation",
                    "question": "What country work permit answers should automation use?",
                    "high_risk": True,
                    "required_count": 28,
                },
                {
                    "input_id": "answer_memory_interview_recording_consent_default_policy",
                    "input_type": "high_risk_exact_confirmation",
                    "question": "Should automation consent to interview recording?",
                    "high_risk": True,
                    "required_count": 18,
                },
                {
                    "input_id": "answer_memory_health_requirement_default_policy",
                    "input_type": "high_risk_exact_confirmation",
                    "question": "What health requirement answer should automation use?",
                    "high_risk": True,
                    "required_count": 2,
                },
            ]
        }
        template = build_final_answer_intake_template(unblockers)
        blocker_report = build_final_answer_blocker_report(template)
        reply_template_text = render_final_answer_reply_template_text(blocker_report)
        reply_text = "\n".join(
            [
                "postal code\uff1a98004",
                "\u516c\u6c11\u8eab\u4efd\uff1aU.S. citizen; no restricted-country citizenship or permanent residency.",
                "\u516c\u6c11\u8eab\u4efd\u786e\u8ba4\uff1a\u786e\u8ba4",
                "\u80cc\u666f\u6216\u51fa\u53e3\u7ba1\u5236\uff1aNo disqualifying background, export-control, indictment, debarment, substance, firearm, felony, or legal-eligibility issues; no exceptions.",
                "\u80cc\u666f\u6216\u51fa\u53e3\u7ba1\u5236\u786e\u8ba4\uff1a\u786e\u8ba4",
                "work authorization\uff1aAuthorized to work in the United States; no non-U.S. country work permits or visa sponsorship exceptions should be assumed.",
                "\u5de5\u4f5c\u8bb8\u53ef\u786e\u8ba4\uff1a\u786e\u8ba4",
                "\u9762\u8bd5\u5f55\u97f3\u540c\u610f\uff1aYes, I consent to interview recording, transcription, AI notetakers, and interview analysis.",
                "\u9762\u8bd5\u5f55\u97f3\u540c\u610f\u786e\u8ba4\uff1a\u786e\u8ba4",
                "health\uff1aI can comply with standard health or vaccination requirements for client-site access; no exceptions.",
                "\u5065\u5eb7\u8981\u6c42\u786e\u8ba4\uff1a\u786e\u8ba4",
            ]
        )

        reply_report = build_final_answer_reply_intake(template, reply_text)
        intake_report = build_final_answer_intake_update(unblockers, reply_report["intake_payload"])

        self.assertIn("ZIP/\u90ae\u7f16", reply_template_text)
        self.assertEqual(reply_report["answer_count"], 6)
        self.assertEqual(reply_report["unknown_key_count"], 0)
        self.assertEqual(len(reply_report["confirmed_high_risk_aliases"]), 5)
        self.assertEqual(
            reply_report["parsed_aliases"],
            [
                "background_or_export_control",
                "citizenship_status",
                "country_work_permit",
                "health_requirement",
                "interview_recording_consent",
                "zip_or_postal_code",
            ],
        )
        self.assertTrue(intake_report["ready_for_finalize"])

    def test_final_answer_reply_template_placeholders_do_not_finalize(self) -> None:
        unblockers = {
            "unblockers": [
                {
                    "input_id": "profile_zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "high_risk": False,
                    "required_count": 56,
                },
                {
                    "input_id": "answer_memory_health_requirement_default_policy",
                    "question": "What health requirement answer should automation use?",
                    "high_risk": True,
                    "required_count": 2,
                },
            ]
        }
        template = build_final_answer_intake_template(unblockers)
        blocker_report = build_final_answer_blocker_report(template)
        reply_text = render_final_answer_reply_template_text(blocker_report)

        reply_report = build_final_answer_reply_intake(template, reply_text)
        intake_report = build_final_answer_intake_update(unblockers, reply_report["intake_payload"])

        self.assertEqual(reply_report["answer_count"], 2)
        self.assertEqual(reply_report["unknown_key_count"], 0)
        self.assertEqual(reply_report["confirmed_high_risk_aliases"], ["health_requirement"])
        self.assertFalse(intake_report["ready_for_finalize"])
        self.assertEqual(intake_report["summary"]["needs_more_specific_answer_count"], 2)
        self.assertEqual(intake_report["compact_updates"], {})
        self.assertEqual(
            [field["status"] for field in intake_report["fields"]],
            ["needs_more_specific_answer", "needs_more_specific_answer"],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template_path = root / "template.json"
            unblockers_path = root / "unblockers.json"
            reply_path = root / "reply.txt"
            template_path.write_text(json.dumps(template, ensure_ascii=True, indent=2), encoding="utf-8")
            unblockers_path.write_text(json.dumps(unblockers, ensure_ascii=True, indent=2), encoding="utf-8")
            reply_path.write_text(reply_text, encoding="utf-8")

            cli_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "job_apply_agent",
                    "final-answer-reply",
                    "--template",
                    str(template_path),
                    "--unblockers",
                    str(unblockers_path),
                    "--reply-file",
                    str(reply_path),
                    "--json-output",
                    str(root / "reply.json"),
                    "--markdown-output",
                    str(root / "reply.md"),
                    "--intake-output",
                    str(root / "payload.json"),
                    "--compact-updates-output",
                    str(root / "compact.json"),
                    "--final-answer-intake-report-json",
                    str(root / "intake.json"),
                    "--final-answer-intake-report-markdown",
                    str(root / "intake.md"),
                    "--fail-on-not-ready",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(cli_result.returncode, 2)
            self.assertIn("Needs specificity aliases", cli_result.stdout)
            self.assertIn("zip_or_postal_code", cli_result.stdout)
            self.assertIn("health_requirement", cli_result.stdout)
            validate_only_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "job_apply_agent",
                    "final-answer-reply",
                    "--template",
                    str(template_path),
                    "--unblockers",
                    str(unblockers_path),
                    "--reply-file",
                    str(reply_path),
                    "--json-output",
                    str(root / "validate_reply.json"),
                    "--markdown-output",
                    str(root / "validate_reply.md"),
                    "--intake-output",
                    str(root / "validate_payload.json"),
                    "--compact-updates-output",
                    str(root / "validate_compact.json"),
                    "--final-answer-intake-report-json",
                    str(root / "validate_intake.json"),
                    "--final-answer-intake-report-markdown",
                    str(root / "validate_intake.md"),
                    "--validate-only",
                    "--fail-on-not-ready",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(validate_only_result.returncode, 2)
            self.assertIn("Validated final answer reply without writing files.", validate_only_result.stdout)
            self.assertIn("Needs specificity aliases", validate_only_result.stdout)
            self.assertFalse((root / "validate_reply.json").exists())
            self.assertFalse((root / "validate_payload.json").exists())
            self.assertFalse((root / "validate_compact.json").exists())
            self.assertFalse((root / "validate_intake.json").exists())
            resume_validate_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "job_apply_agent",
                    "resume-after-answers",
                    "--reply-file",
                    str(reply_path),
                    "--validate-only",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(resume_validate_result.returncode, 2)
            self.assertIn("Validated final answer reply without writing files.", resume_validate_result.stdout)
            self.assertIn("Needs specificity aliases", resume_validate_result.stdout)

    def test_final_answer_intake_server_post_answer_flags_are_guarded(self) -> None:
        base_args = {
            "run_post_answer_pipeline": False,
            "synthetic_rehearse_queue": False,
            "post_answer_apply": False,
            "post_answer_live_check": False,
            "post_answer_include_values": False,
            "post_answer_open_browser": False,
        }

        _validate_final_answer_intake_server_post_answer_args(argparse.Namespace(**base_args))

        with self.assertRaisesRegex(ValueError, "requires --run-post-answer-pipeline"):
            _validate_final_answer_intake_server_post_answer_args(
                argparse.Namespace(**{**base_args, "post_answer_apply": True})
            )
        with self.assertRaisesRegex(ValueError, "require --post-answer-apply"):
            _validate_final_answer_intake_server_post_answer_args(
                argparse.Namespace(
                    **{
                        **base_args,
                        "run_post_answer_pipeline": True,
                        "post_answer_live_check": True,
                    }
                )
            )
        with self.assertRaisesRegex(ValueError, "requires --post-answer-live-check"):
            _validate_final_answer_intake_server_post_answer_args(
                argparse.Namespace(
                    **{
                        **base_args,
                        "run_post_answer_pipeline": True,
                        "post_answer_apply": True,
                        "post_answer_open_browser": True,
                    }
                )
            )
        with self.assertRaisesRegex(ValueError, "cannot be combined"):
            _validate_final_answer_intake_server_post_answer_args(
                argparse.Namespace(
                    **{
                        **base_args,
                        "run_post_answer_pipeline": True,
                        "synthetic_rehearse_queue": True,
                    }
                )
            )
        _validate_final_answer_intake_server_post_answer_args(
            argparse.Namespace(
                **{
                    **base_args,
                    "run_post_answer_pipeline": True,
                    "post_answer_apply": True,
                    "post_answer_live_check": True,
                    "post_answer_open_browser": True,
                }
            )
        )

        summary = _post_answer_pipeline_summary(
            {
                "status": "ready_for_supervised_autofill",
                "ready_for_workflow": True,
                "apply_requested": True,
                "live_check_requested": True,
                "open_browser_requested": False,
                "handoff_status": "open_ready",
                "handoff_open_ready": 100,
                "autofill_packet_status": "ready_for_supervised_browser_autofill",
                "autofill_packet_selected": 100,
                "opened_count": 0,
                "policy": {"submits_real_applications": False},
            }
        )
        self.assertEqual(summary["status"], "ready_for_supervised_autofill")
        self.assertTrue(summary["ready_for_workflow"])
        self.assertEqual(summary["handoff_open_ready"], 100)
        self.assertFalse(summary["policy"]["submits_real_applications"])

    def test_critical_input_updates_readiness_blocks_blanks_and_unconfirmed_high_risk(self) -> None:
        learning_tasks = {
            "tasks": [
                {
                    "group_key": "profile:zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "recommended_storage": "profile",
                    "labels": ["Zip Code"],
                    "platforms": ["Ashby"],
                    "required_count": 4,
                    "persist_allowed": True,
                },
                {
                    "group_key": "answer_memory:citizenship_status:default_policy",
                    "question": "What citizenship answers should automation use?",
                    "recommended_storage": "answer_memory",
                    "answer_scope": "category_default_policy",
                    "suggested_answer_source": "requires_exact_user_confirmation",
                    "approval_risk": "high",
                    "labels": ["Are you a U.S. citizen?"],
                    "platforms": ["Greenhouse"],
                    "required_count": 2,
                    "persist_allowed": True,
                },
                {
                    "group_key": "answer_memory:favorite_junk_food",
                    "question": "What's your favorite junk food?",
                    "recommended_storage": "answer_memory",
                    "labels": ["What's your favorite junk food?"],
                    "platforms": ["Ashby"],
                    "required_count": 1,
                    "persist_allowed": True,
                },
            ],
        }
        pack = build_learning_approval_pack(learning_tasks, {})
        answers = build_critical_input_answer_template(pack)
        updates = {
            "profile_zip_or_postal_code": "",
            "answer_memory_citizenship_status_default_policy": {
                "user_answer": "Synthetic candidate is a U.S. citizen.",
                "approval_decision": "approved",
                "high_risk_user_confirmed": False,
            },
            "answer_memory_favorite_junk_food": "Potato chips",
        }
        research = {
            "positions_observed_total": 1,
            "positions": [
                {
                    "position_key": "ashby:example:sre",
                    "platform": "Ashby",
                    "company": "Example",
                    "title": "Site Reliability Engineer",
                    "role_family": "SRE",
                }
            ],
            "items": [
                {
                    "position_key": "ashby:example:sre",
                    "normalized_label": "zip code",
                    "label": "Zip Code",
                    "category": "profile_identity",
                    "automation_action": "auto_fill_from_profile",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "test",
                },
                {
                    "position_key": "ashby:example:sre",
                    "normalized_label": "are you a u s citizen",
                    "label": "Are you a U.S. citizen?",
                    "category": "standard_preference",
                    "automation_action": "auto_answer_from_memory",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "test",
                },
                {
                    "position_key": "ashby:example:sre",
                    "normalized_label": "what s your favorite junk food",
                    "label": "What's your favorite junk food?",
                    "category": "standard_preference",
                    "automation_action": "auto_answer_from_memory",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "test",
                },
            ],
        }
        profile_payload = {
            "candidate": {"name": "Test User", "location": "Bellevue, WA"},
            "preferences": {},
            "resume_facts": {},
            "question_answers": {},
        }

        blocked = build_critical_input_updates_readiness(
            pack,
            answers,
            updates,
            research,
            profile_payload,
            answer_memory={"version": 1, "answers": []},
        )
        blocked_markdown = render_critical_input_updates_readiness_markdown(blocked)

        self.assertFalse(blocked["ready_for_apply"])
        self.assertEqual(blocked["summary"]["waiting_after_update_count"], 1)
        self.assertEqual(blocked["summary"]["high_risk_unconfirmed_count"], 1)
        self.assertIn("critical_inputs_waiting", blocked["summary"]["blocking_reasons"])
        self.assertIn("high_risk_confirmation_missing", blocked["summary"]["blocking_reasons"])
        self.assertIn("Critical Input Updates Readiness", blocked_markdown)

        updates["profile_zip_or_postal_code"] = "98004"
        updates["answer_memory_citizenship_status_default_policy"]["high_risk_user_confirmed"] = True
        ready = build_critical_input_updates_readiness(
            pack,
            answers,
            updates,
            research,
            profile_payload,
            answer_memory={"version": 1, "answers": []},
        )

        self.assertTrue(ready["ready_for_apply"])
        self.assertEqual(ready["summary"]["waiting_after_update_count"], 0)
        self.assertEqual(ready["summary"]["high_risk_unconfirmed_count"], 0)
        self.assertEqual(ready["summary"]["data_blocking_prompts_after"], 0)
        self.assertFalse(ready["writes_real_profile_or_memory"])

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            approval_pack_path = root / "pack.json"
            answers_path = root / "answers.json"
            updates_path = root / "updates.json"
            research_path = root / "research.json"
            profile_path = root / "profile.json"
            memory_path = root / "memory.json"
            json_output = root / "readiness.json"
            markdown_output = root / "readiness.md"
            approval_pack_path.write_text(json.dumps(pack), encoding="utf-8")
            answers_path.write_text(json.dumps(answers), encoding="utf-8")
            updates_path.write_text(json.dumps(updates), encoding="utf-8")
            research_path.write_text(json.dumps(research), encoding="utf-8")
            profile_path.write_text(json.dumps(profile_payload), encoding="utf-8")

            written = write_critical_input_updates_readiness(
                approval_pack_path,
                answers_path,
                updates_path,
                research_path,
                profile_path,
                memory_path,
                json_output,
                markdown_output,
            )

            self.assertTrue(written["ready_for_apply"])
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertFalse(memory_path.exists())

    def test_synthetic_unblocker_proof_clears_data_blockers_temp_only(self) -> None:
        learning_tasks = {
            "tasks": [
                {
                    "group_key": "profile:zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "recommended_storage": "profile",
                    "labels": ["Zip Code"],
                    "platforms": ["Ashby"],
                    "required_count": 4,
                    "persist_allowed": True,
                },
                {
                    "group_key": "answer_memory:citizenship_status:default_policy",
                    "question": "What citizenship answers should automation use?",
                    "recommended_storage": "answer_memory",
                    "answer_scope": "category_default_policy",
                    "suggested_answer_source": "requires_exact_user_confirmation",
                    "approval_risk": "high",
                    "labels": ["Are you a U.S. citizen?"],
                    "platforms": ["Greenhouse"],
                    "required_count": 2,
                    "persist_allowed": True,
                },
                {
                    "group_key": "answer_memory:favorite_junk_food",
                    "question": "What's your favorite junk food?",
                    "recommended_storage": "answer_memory",
                    "labels": ["What's your favorite junk food?"],
                    "platforms": ["Ashby"],
                    "required_count": 1,
                    "persist_allowed": True,
                },
            ],
        }
        pack = build_learning_approval_pack(learning_tasks, {})
        answers = build_critical_input_answer_template(pack)
        for row in answers["answers"]:
            if row["group_key"] == "answer_memory:favorite_junk_food":
                row["user_answer"] = "Potato chips"

        unblockers = {
            "unblockers": [
                {
                    "input_id": "profile_zip_or_postal_code",
                    "input_type": "profile_or_resume_fact",
                    "group_key": "profile:zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                },
                {
                    "input_id": "answer_memory_citizenship_status_default_policy",
                    "input_type": "high_risk_exact_confirmation",
                    "group_key": "answer_memory:citizenship_status:default_policy",
                    "question": "What citizenship answers should automation use?",
                    "approval_risk": "high",
                },
            ]
        }
        research = {
            "positions_observed_total": 1,
            "positions": [
                {
                    "position_key": "ashby:example:sre",
                    "platform": "Ashby",
                    "company": "Example",
                    "title": "Site Reliability Engineer",
                    "role_family": "SRE",
                }
            ],
            "items": [
                {
                    "position_key": "ashby:example:sre",
                    "normalized_label": "zip code",
                    "label": "Zip Code",
                    "category": "profile_identity",
                    "automation_action": "auto_fill_from_profile",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "test",
                },
                {
                    "position_key": "ashby:example:sre",
                    "normalized_label": "what s your favorite junk food",
                    "label": "What's your favorite junk food?",
                    "category": "standard_preference",
                    "automation_action": "auto_answer_from_memory",
                    "required": True,
                    "platform": "Ashby",
                    "source_file": "test",
                },
            ],
        }
        profile_payload = {
            "candidate": {"name": "Test User", "location": "Bellevue, WA"},
            "preferences": {},
            "resume_facts": {},
            "question_answers": {},
        }
        autofill_batch = {
            "selected_count": 100,
            "local_synthetic_submit_count": 100,
            "local_synthetic_submit_achieved": True,
            "local_synthetic_submit_selector_miss_count": 0,
        }

        proof = build_synthetic_unblocker_proof(
            pack,
            answers,
            unblockers,
            research,
            profile_payload,
            answer_memory={"version": 1, "answers": []},
            autofill_batch=autofill_batch,
        )
        summary = proof["summary"]

        self.assertFalse(proof["real_platform_submission"])
        self.assertFalse(proof["writes_real_profile_or_memory"])
        self.assertEqual(summary["synthetic_final_unblocker_update_count"], 2)
        self.assertEqual(summary["existing_draft_update_count"], 1)
        self.assertEqual(summary["high_risk_confirmed_count"], 1)
        self.assertEqual(summary["data_blocking_prompts_after"], 0)
        self.assertTrue(summary["local_100_synthetic_apply_path_ready"])
        self.assertTrue(summary["proof_complete"])
        self.assertIn("Synthetic Unblocker Proof", render_synthetic_unblocker_proof_markdown(proof))

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            approval_pack_path = root / "pack.json"
            answers_path = root / "answers.json"
            unblockers_path = root / "unblockers.json"
            research_path = root / "research.json"
            profile_path = root / "profile.json"
            memory_path = root / "memory.json"
            json_output = root / "proof.json"
            markdown_output = root / "proof.md"
            approval_pack_path.write_text(json.dumps(pack), encoding="utf-8")
            answers_path.write_text(json.dumps(answers), encoding="utf-8")
            unblockers_path.write_text(json.dumps(unblockers), encoding="utf-8")
            research_path.write_text(json.dumps(research), encoding="utf-8")
            profile_path.write_text(json.dumps(profile_payload), encoding="utf-8")

            written = write_synthetic_unblocker_proof(
                approval_pack_path,
                answers_path,
                unblockers_path,
                research_path,
                profile_path,
                memory_path,
                json_output,
                markdown_output,
                autofill_batch=autofill_batch,
            )

            self.assertEqual(written["summary"]["data_blocking_prompts_after"], 0)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertFalse(memory_path.exists())

    def test_critical_input_questionnaire_outputs_compact_json_html_form(self) -> None:
        learning_tasks = {
            "tasks": [
                {
                    "group_key": "profile:zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "recommended_storage": "profile",
                    "labels": ["Zip Code"],
                    "platforms": ["Ashby"],
                    "required_count": 4,
                    "persist_allowed": True,
                },
                {
                    "group_key": "answer_memory:citizenship_status:default_policy",
                    "question": "What citizenship answers should automation use?",
                    "recommended_storage": "answer_memory",
                    "answer_scope": "category_default_policy",
                    "suggested_answer_source": "requires_exact_user_confirmation",
                    "approval_risk": "high",
                    "labels": ["Are you a U.S. citizen?"],
                    "platforms": ["Greenhouse"],
                    "required_count": 2,
                    "persist_allowed": True,
                },
                {
                    "group_key": "supervised_confirmation:policy_acknowledgement",
                    "question": "May automation mark applicant privacy acknowledgement?",
                    "recommended_storage": "supervised_confirmation",
                    "answer_scope": "supervised_only",
                    "labels": ["Privacy policy"],
                    "platforms": ["Lever"],
                    "required_count": 1,
                    "persist_allowed": False,
                },
            ],
        }
        profile = CandidateProfile.from_mapping(
            {
                "candidate": {"name": "Test User", "location": "Bellevue, WA"},
                "question_answers": {"zip_code": "98004"},
                "preferences": {},
                "resume_facts": {},
            }
        )
        pack = build_learning_approval_pack(learning_tasks, {})
        template = build_critical_input_answer_template(pack)
        suggestions = build_critical_input_suggestion_packet(template, profile=profile)
        impact = {
            "input_impacts": [
                {
                    "input_id": "answer_memory_citizenship_status_default_policy",
                    "data_blocking_prompts_delta": -5,
                    "ready_prompts_delta": 5,
                    "positions_ready_for_autofill_delta": 12,
                    "simulated_answer": "Synthetic user confirms citizenship policy.",
                },
                {
                    "input_id": "profile_zip_or_postal_code",
                    "data_blocking_prompts_delta": -2,
                    "ready_prompts_delta": 2,
                    "positions_ready_for_autofill_delta": 3,
                    "simulated_answer": "98004",
                },
            ]
        }

        questionnaire = build_critical_input_questionnaire(template, suggestions, impact_payload=impact)
        html = render_critical_input_questionnaire_html(questionnaire)
        markdown = render_critical_input_questionnaire_markdown(questionnaire)

        self.assertEqual(questionnaire["question_count"], 3)
        self.assertEqual(questionnaire["answerable_question_count"], 2)
        self.assertEqual(questionnaire["high_risk_question_count"], 1)
        self.assertEqual(questionnaire["supervised_only_count"], 1)
        self.assertEqual(
            questionnaire["questions"][0]["input_id"],
            "answer_memory_citizenship_status_default_policy",
        )
        self.assertEqual(questionnaire["questions"][0]["impact_rank"], 1)
        self.assertEqual(questionnaire["compact_updates_template"]["profile_zip_or_postal_code"], "")
        self.assertFalse(
            questionnaire["compact_updates_template"][
                "answer_memory_citizenship_status_default_policy"
            ]["high_risk_user_confirmed"]
        )
        self.assertNotIn(
            "supervised_confirmation_policy_acknowledgement",
            questionnaire["compact_updates_template"],
        )
        self.assertIn("Critical Input Questionnaire", html)
        self.assertIn("buildCriticalInputUpdates", html)
        self.assertIn("critical-inputs-workflow", html)
        self.assertIn("High risk", html)
        self.assertIn("Impact -5 blockers", html)
        self.assertIn("Compact Updates Template", markdown)
        self.assertIn("impact: data blockers -5", markdown)

        with tempfile.TemporaryDirectory() as temp_dir:
            json_output = Path(temp_dir) / "questionnaire.json"
            markdown_output = Path(temp_dir) / "questionnaire.md"
            html_output = Path(temp_dir) / "questionnaire.html"
            written = write_critical_input_questionnaire(
                template,
                json_output,
                markdown_output,
                html_output,
                suggestions_payload=suggestions,
                impact_payload=impact,
            )
            self.assertEqual(written["answerable_question_count"], 2)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertTrue(html_output.exists())

    def test_fake_critical_input_probe_is_dry_run_only(self) -> None:
        learning_tasks = {
            "tasks": [
                {
                    "group_key": "profile:zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "recommended_storage": "profile",
                    "labels": ["Zip Code"],
                    "platforms": ["Ashby"],
                    "required_count": 4,
                    "persist_allowed": True,
                },
                {
                    "group_key": "answer_memory:citizenship_status:default_policy",
                    "question": "What citizenship answers should automation use?",
                    "recommended_storage": "answer_memory",
                    "answer_scope": "category_default_policy",
                    "suggested_answer_source": "requires_exact_user_confirmation",
                    "approval_risk": "high",
                    "labels": ["Are you a U.S. citizen?"],
                    "platforms": ["Greenhouse"],
                    "required_count": 2,
                    "persist_allowed": True,
                },
                {
                    "group_key": "supervised_confirmation:policy_acknowledgement",
                    "question": "May automation mark applicant privacy acknowledgement?",
                    "recommended_storage": "supervised_confirmation",
                    "answer_scope": "supervised_only",
                    "labels": ["Privacy policy"],
                    "platforms": ["Lever"],
                    "required_count": 1,
                    "persist_allowed": False,
                },
            ],
        }
        pack = build_learning_approval_pack(learning_tasks, {})
        report = build_fake_critical_input_probe(pack)

        self.assertFalse(report["real_platform_submission"])
        self.assertFalse(report["writes_real_profile_or_memory"])
        self.assertEqual(report["fake_answered_count"], 2)
        self.assertEqual(report["ready_to_apply_count"], 2)
        self.assertEqual(report["supervised_only_count"], 1)
        self.assertTrue(report["fake_answers"]["fake_candidate_only"])
        self.assertIn("Fake Critical Input Probe", render_fake_critical_input_probe_markdown(report))

        with tempfile.TemporaryDirectory() as temp_dir:
            pack_path = Path(temp_dir) / "approval_pack.json"
            fake_answers_path = Path(temp_dir) / "fake_answers.json"
            profile_path = Path(temp_dir) / "profile.json"
            memory_path = Path(temp_dir) / "memory.json"
            report_json = Path(temp_dir) / "fake_probe.json"
            report_md = Path(temp_dir) / "fake_probe.md"
            answers_md = Path(temp_dir) / "fake_answers.md"
            pack_path.write_text(json.dumps(pack), encoding="utf-8")
            profile_path.write_text(
                json.dumps(
                    {
                        "candidate": {"name": "Real User Placeholder"},
                        "preferences": {},
                        "resume_facts": {},
                        "question_answers": {},
                    }
                ),
                encoding="utf-8",
            )
            written = write_fake_critical_input_probe(
                pack,
                report_json,
                report_md,
                fake_answers_path,
                answers_md,
            )
            self.assertEqual(written["ready_to_apply_count"], 2)
            self.assertTrue(report_json.exists())
            self.assertTrue(fake_answers_path.exists())

            dry_run = apply_critical_input_answers(
                pack_path,
                profile_path,
                memory_path,
                answers_path=fake_answers_path,
                dry_run=True,
            )
            self.assertEqual(dry_run["approved_input_count"], 2)
            self.assertFalse(memory_path.exists())

            with self.assertRaises(ValueError):
                apply_critical_input_answers(
                    pack_path,
                    profile_path,
                    memory_path,
                    answers_path=fake_answers_path,
                    dry_run=False,
                )

    def test_fake_learning_probe_clears_learning_blockers_without_real_submission(self) -> None:
        research = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "positions_observed_total": 1,
            "positions": [{"position_key": "greenhouse:1", "platform": "Greenhouse"}],
            "items": [
                {
                    "label": "Have you previously worked at ExampleCo?",
                    "normalized_label": "have previously worked at exampleco",
                    "category": "employment_history",
                    "automation_action": "human_review_required",
                    "sensitivity": "profile",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "example.json",
                },
                {
                    "label": "Resume",
                    "normalized_label": "resume",
                    "category": "resume_upload",
                    "automation_action": "auto_fill_from_profile",
                    "sensitivity": "document",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "example.json",
                },
                {
                    "label": "Submit application",
                    "normalized_label": "submit application",
                    "category": "final_submit",
                    "automation_action": "human_review_required",
                    "sensitivity": "submission_control",
                    "required": False,
                    "platform": "Greenhouse",
                    "source_file": "example.json",
                },
                {
                    "label": "Candidate Personal Data Disclosure",
                    "normalized_label": "candidate personal data disclosure",
                    "category": "policy_acknowledgement",
                    "automation_action": "human_review_required",
                    "sensitivity": "policy",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "example.json",
                },
                {
                    "label": "Do you have reliability engineering experience related to ClickHouse or another SQL database in production?",
                    "normalized_label": (
                        "do you have reliability engineering experience related to clickhouse "
                        "or another sql database in production"
                    ),
                    "category": "domain_experience",
                    "automation_action": "human_review_required",
                    "sensitivity": "resume_fact",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "example.json",
                },
            ],
        }
        learning_tasks = {
            "task_count": 3,
            "tasks": [
                {
                    "group_key": "answer_memory:employment_history:default_policy",
                    "question": "Should automation answer no to prior-employer questions?",
                    "recommended_storage": "answer_memory",
                    "answer_scope": "category_default_policy",
                    "labels": ["Have you previously worked at ExampleCo?"],
                    "suggested_answer": "No",
                },
                {
                    "group_key": "local_material:resume_file",
                    "question": "Which approved resume file should automation upload?",
                    "recommended_storage": "local_material",
                    "answer_scope": "local_file_path",
                    "labels": ["Resume"],
                },
                {
                    "group_key": "supervised_confirmation:policy_acknowledgement",
                    "question": "May automation acknowledge reviewed policies in a fake run?",
                    "recommended_storage": "supervised_confirmation",
                    "answer_scope": "supervised_only",
                    "labels": ["Candidate Personal Data Disclosure"],
                },
            ],
        }
        baseline = {"blocking_prompt_count": 3, "coverage_counts": {"needs_user_confirmation": 2}}

        report = build_fake_learning_probe(research, learning_tasks, baseline_gaps=baseline)

        self.assertFalse(report["real_platform_submission"])
        self.assertEqual(report["fake_answered_task_count"], 2)
        self.assertEqual(report["synthetic_blocker_clearance_added_count"], 1)
        self.assertEqual(report["remaining_learning_blocker_count"], 0)
        self.assertTrue(report["learning_blockers_cleared"])
        self.assertEqual(report["remaining_manual_gate_count"], 1)
        self.assertIn(
            "database performance",
            report["synthetic_blocker_clearance_added_rows"][0]["answer"],
        )
        self.assertEqual(
            report["after_fake_learning"]["coverage_counts"]["final_submit_confirmation"],
            1,
        )
        self.assertIn("Fake Learning Probe", render_fake_learning_probe_markdown(report))

        synthetic_state = build_synthetic_learning_state(learning_tasks)
        self.assertFalse(synthetic_state["policy"]["writes_real_profile_or_memory"])
        self.assertIn("profile", synthetic_state)
        self.assertIn("answer_memory", synthetic_state)
        self.assertGreaterEqual(len(synthetic_state["answer_memory"]["answers"]), 2)
        self.assertIn("resume_path", synthetic_state["profile"]["question_answers"])

        blocker_patch = add_synthetic_answers_for_blockers(
            synthetic_state["answer_memory"],
            [
                {
                    "label": "Do you have reliability engineering experience related to ClickHouse?",
                    "category": "domain_experience",
                }
            ],
            source="unit_test_synthetic_rehearsal",
        )
        self.assertEqual(blocker_patch["added_count"], 1)
        self.assertIn("ClickHouse", blocker_patch["added_rows"][0]["label"])
        self.assertIn("database performance", blocker_patch["added_rows"][0]["answer"])
        self.assertFalse(any("real_platform" in row for row in blocker_patch["added_rows"]))

    def test_write_fake_learning_probe_outputs_reports(self) -> None:
        research = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "positions_observed_total": 1,
            "positions": [{"position_key": "greenhouse:1", "platform": "Greenhouse"}],
            "items": [
                {
                    "label": "Do you know anyone currently at ExampleCo?",
                    "normalized_label": "do you know anyone currently at exampleco",
                    "category": "conflict_of_interest",
                    "automation_action": "human_review_required",
                    "sensitivity": "policy",
                    "required": True,
                    "platform": "Greenhouse",
                    "source_file": "example.json",
                }
            ],
        }
        learning_tasks = {
            "task_count": 1,
            "tasks": [
                {
                    "group_key": "answer_memory:conflict_of_interest:default_policy",
                    "question": "Should automation answer no to conflict questions?",
                    "recommended_storage": "answer_memory",
                    "answer_scope": "category_default_policy",
                    "labels": ["Do you know anyone currently at ExampleCo?"],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            json_output = Path(temp_dir) / "probe.json"
            markdown_output = Path(temp_dir) / "probe.md"

            report = write_fake_learning_probe(
                research,
                learning_tasks,
                baseline_gaps=None,
                json_output=json_output,
                markdown_output=markdown_output,
            )

            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertEqual(report["remaining_learning_blocker_count"], 0)
            self.assertIn("Fake Learning Probe", markdown_output.read_text())

    def test_fake_position_rehearsal_runs_observed_prompts_locally(self) -> None:
        research = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "positions_observed_total": 2,
            "positions": [
                {
                    "position_key": "linkedin:4410000001",
                    "platform": "LinkedIn",
                    "job_id": "4410000001",
                    "company": "OpenCo",
                    "title": "Site Reliability Engineer",
                    "role_family": "Site Reliability",
                    "apply_url": "https://www.linkedin.com/jobs/view/4410000001/",
                },
                {
                    "position_key": "linkedin:4415508499",
                    "platform": "LinkedIn",
                    "job_id": "4415508499",
                    "company": "ClosedCo",
                    "title": "Cloud Engineer",
                    "role_family": "Cloud DevOps",
                    "apply_url": "https://www.linkedin.com/jobs/view/4415508499/",
                },
            ],
            "items": [
                {
                    "position_key": "linkedin:4410000001",
                    "label": "Resume/CV",
                    "category": "resume_upload",
                    "automation_action": "auto_fill_from_profile",
                    "required": True,
                    "platform": "LinkedIn",
                    "source_file": "observed.json",
                },
                {
                    "position_key": "linkedin:4410000001",
                    "label": "What is your expected compensation range?",
                    "item_type": "inferred_question",
                    "category": "compensation",
                    "automation_action": "auto_answer_from_memory",
                    "required": True,
                    "platform": "LinkedIn",
                    "source_file": "observed.json",
                },
                {
                    "position_key": "linkedin:4410000001",
                    "label": "Submit application",
                    "category": "final_submit",
                    "automation_action": "human_review_required",
                    "required": True,
                    "platform": "LinkedIn",
                    "source_file": "observed.json",
                },
                {
                    "position_key": "linkedin:4415508499",
                    "label": "What is your expected compensation range?",
                    "category": "compensation",
                    "automation_action": "auto_answer_from_memory",
                    "required": True,
                    "platform": "LinkedIn",
                    "source_file": "observed.json",
                },
            ],
        }
        closed_jobs = {
            "jobs": [
                {
                    "key": "linkedin:4415508499",
                    "status": "CLOSED",
                    "reason": "No longer accepting applications",
                }
            ]
        }

        report = build_fake_position_rehearsal(
            research,
            {"task_count": 0, "tasks": []},
            limit=2,
            closed_jobs=closed_jobs,
            allow_local_synthetic_submit=True,
        )

        self.assertFalse(report["real_platform_submission"])
        self.assertEqual(report["run_count"], 1)
        self.assertEqual(report["excluded_closed_position_count"], 1)
        self.assertEqual(report["pre_synthetic_missing_input_count"], 0)
        self.assertEqual(report["selector_miss_count"], 0)
        self.assertEqual(report["inferred_prompt_item_count"], 1)
        self.assertEqual(report["inferred_prompt_position_count"], 1)
        self.assertEqual(report["actual_submit_count"], 1)
        self.assertTrue(report["eligible_submit_achieved"])
        self.assertEqual(report["policy_stop_counts"]["local_synthetic_submit_allowed"], 1)
        self.assertIn("Fake Position Rehearsal", render_fake_position_rehearsal_markdown(report))

    def test_fake_position_rehearsal_can_target_platform_role_pairs(self) -> None:
        positions = []
        items = []
        for platform in ["LinkedIn", "Ashby"]:
            for role_family, title in [
                ("Site Reliability", "Site Reliability Engineer"),
                ("Software Backend", "Backend Software Engineer"),
            ]:
                key = f"{platform.lower()}:{role_family.lower().replace(' ', '-')}"
                positions.append(
                    {
                        "position_key": key,
                        "platform": platform,
                        "company": f"{platform} Co",
                        "title": title,
                        "role_family": role_family,
                        "apply_url": f"https://example.com/{key}",
                    }
                )
                items.append(
                    {
                        "position_key": key,
                        "label": "Email",
                        "category": "profile_identity",
                        "automation_action": "auto_fill_from_profile",
                        "required": True,
                        "platform": platform,
                    }
                )
        research = {"positions": positions, "items": items}

        report = build_fake_position_rehearsal(
            research,
            {"task_count": 0, "tasks": []},
            limit=1,
            allow_local_synthetic_submit=True,
            per_platform_role_target=1,
            target_platforms=["LinkedIn", "Ashby"],
            target_role_families=["Site Reliability", "Software Backend"],
        )

        self.assertEqual(report["requested_count"], 4)
        self.assertEqual(report["run_count"], 4)
        self.assertTrue(report["platform_role_target_achieved"])
        self.assertEqual(report["platform_role_target_shortfalls"]["Ashby::Site Reliability"], 0)
        self.assertEqual(report["actual_submit_count"], 4)

    def test_write_fake_position_rehearsal_outputs_reports(self) -> None:
        research = {
            "positions": [
                {
                    "position_key": "greenhouse:1",
                    "platform": "Greenhouse",
                    "company": "ExampleCo",
                    "title": "Platform Engineer",
                    "role_family": "Platform Infrastructure",
                    "apply_url": "https://job-boards.greenhouse.io/example/jobs/1",
                }
            ],
            "items": [
                {
                    "position_key": "greenhouse:1",
                    "label": "First Name",
                    "category": "profile_identity",
                    "automation_action": "auto_fill_from_profile",
                    "required": True,
                    "platform": "Greenhouse",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            json_output = Path(temp_dir) / "rehearsal.json"
            markdown_output = Path(temp_dir) / "rehearsal.md"

            report = write_fake_position_rehearsal(
                research,
                {"task_count": 0, "tasks": []},
                json_output,
                markdown_output,
                limit=1,
                allow_local_synthetic_submit=True,
            )

            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertEqual(report["run_count"], 1)
            self.assertEqual(report["actual_submit_count"], 1)
            self.assertIn("Fake Position Rehearsal", markdown_output.read_text())

    def test_synthetic_application_simulation_never_submits_real_applications(self) -> None:
        report = run_synthetic_application_simulation(count=20)

        self.assertEqual(report["run_count"], 20)
        self.assertFalse(report["real_platform_submission"])
        self.assertEqual(report["status_counts"]["closed_skip"], 1)
        self.assertIn("final_submit_confirmation", report["step_status_counts"])
        self.assertIn("manual_security_step", report["step_status_counts"])
        self.assertTrue(
            all(run["real_platform_submission"] is False for run in report["runs"])
        )

    def test_write_synthetic_application_simulation_outputs_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            json_output = Path(temp_dir) / "synthetic.json"
            markdown_output = Path(temp_dir) / "synthetic.md"

            report = write_synthetic_application_simulation(json_output, markdown_output, count=5)

            self.assertEqual(report["run_count"], 5)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertIn("Synthetic Application Simulation", markdown_output.read_text())

    def test_application_playbook_summarizes_platform_blockers(self) -> None:
        research = {
            "positions_observed_total": 2,
            "platforms": {
                "LinkedIn": {"positions_observed": 1},
                "Greenhouse": {"positions_observed": 1},
            },
            "items": [
                {
                    "platform": "LinkedIn",
                    "label": "Submit application",
                    "normalized_label": "submit application",
                    "category": "final_submit",
                    "automation_action": "human_review_required",
                },
                {
                    "platform": "Greenhouse",
                    "label": "Gender",
                    "normalized_label": "gender",
                    "category": "eeoc_sensitive",
                    "automation_action": "do_not_store_sensitive",
                },
            ],
        }
        gaps = {
            "prompt_statuses": [
                {
                    "normalized_label": "submit application",
                    "coverage_status": "final_submit_confirmation",
                },
                {
                    "normalized_label": "gender",
                    "coverage_status": "sensitive_not_stored",
                },
            ]
        }
        readiness = {
            "positions": [
                {"platform": "LinkedIn", "readiness": "autofill_ready"},
                {"platform": "Greenhouse", "readiness": "supervised_ready"},
            ],
            "minimal_learning_tasks": [
                {
                    "platforms": ["Greenhouse"],
                    "question": "Do you consent to SMS messages?",
                    "recommended_storage": "answer_memory",
                    "group_key": "answer_memory:sms",
                }
            ],
        }
        synthetic = {
            "run_count": 100,
            "platform_counts": {"LinkedIn": 25, "Greenhouse": 25},
            "status_counts": {"autofill_ready_with_supervised_gates": 95, "closed_skip": 5},
            "runs": [
                {
                    "platform": "LinkedIn",
                    "status": "autofill_ready_with_supervised_gates",
                    "blocking_labels": ["Submit application"],
                },
                {
                    "platform": "Greenhouse",
                    "status": "autofill_ready_with_supervised_gates",
                    "blocking_labels": ["Gender", "Submit application"],
                },
            ],
        }

        playbook = build_application_playbook(research, gaps, readiness, synthetic)

        self.assertEqual(playbook["platform_count"], 2)
        self.assertEqual(playbook["platforms"]["LinkedIn"]["synthetic_runs"], 25)
        self.assertEqual(
            playbook["platforms"]["LinkedIn"]["blocker_prompts"][0]["coverage_status"],
            "final_submit_confirmation",
        )
        self.assertEqual(
            playbook["platforms"]["Greenhouse"]["learning_tasks"][0]["recommended_storage"],
            "answer_memory",
        )
        self.assertIn("Gender", playbook["platforms"]["Greenhouse"]["synthetic_gate_labels"])
        markdown = render_application_playbook_markdown(playbook)
        self.assertIn("Application Automation Playbook", markdown)
        self.assertIn("Never click final submit", markdown)
        self.assertIn("Synthetic gates", markdown)

    def test_write_application_playbook_outputs_reports(self) -> None:
        research = {
            "positions_observed_total": 1,
            "platforms": {"Ashby": {"positions_observed": 1}},
            "items": [],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            json_output = Path(temp_dir) / "playbook.json"
            markdown_output = Path(temp_dir) / "playbook.md"

            playbook = write_application_playbook(
                research,
                gaps=None,
                readiness=None,
                synthetic=None,
                json_output=json_output,
                markdown_output=markdown_output,
            )

            self.assertEqual(playbook["platform_count"], 1)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertIn("Application Automation Playbook", markdown_output.read_text())

    def test_research_coverage_gate_reports_real_and_synthetic_shortfalls(self) -> None:
        research = {
            "positions_observed_total": 3,
            "platforms": {
                "LinkedIn": {"positions_observed": 2},
                "Greenhouse": {"positions_observed": 1},
                "MockJobs": {"positions_observed": 1},
            },
            "coverage_groups": {
                "LinkedIn::Site Reliability": {"positions_observed": 2},
                "Greenhouse::Platform Infrastructure": {"positions_observed": 1},
            },
        }
        synthetic = {
            "run_count": 2000,
            "per_platform_role_target": 100,
            "platform_role_target_achieved": True,
            "actual_submit_count": 0,
            "selector_miss_count": 0,
            "platform_role_counts": {"LinkedIn | Site Reliability Engineer": 100},
        }
        gaps = {
            "blocking_prompt_count": 1,
            "coverage_counts": {"needs_answer_memory": 1},
        }

        gate = build_research_coverage_gate(
            research,
            synthetic=synthetic,
            gaps=gaps,
            position_target=2,
            target_platforms=["LinkedIn", "Greenhouse"],
            target_role_families=["Site Reliability", "Platform Infrastructure"],
        )

        self.assertFalse(gate["real_platform_role_target_achieved"])
        self.assertTrue(gate["synthetic"]["platform_role_target_achieved"])
        self.assertFalse(gate["ready_for_full_automation"])
        self.assertEqual(gate["real_platform_shortfalls"]["LinkedIn"], 0)
        self.assertEqual(gate["real_platform_shortfalls"]["Greenhouse"], 1)
        self.assertEqual(gate["real_platform_role_shortfalls"]["LinkedIn::Site Reliability"], 0)
        self.assertEqual(gate["real_platform_role_shortfalls"]["Greenhouse::Site Reliability"], 2)
        self.assertEqual(gate["observed_extra_platforms"], ["MockJobs"])
        self.assertGreater(len(gate["next_collection_targets"]), 0)
        markdown = render_research_coverage_gate_markdown(gate)
        self.assertIn("Research Coverage Gate", markdown)
        self.assertIn("Synthetic platform-role target achieved: true", markdown)

    def test_research_coverage_gate_requires_local_synthetic_submit_evidence(self) -> None:
        research = {
            "positions_observed_total": 4,
            "platforms": {
                "LinkedIn": {"positions_observed": 2},
                "Greenhouse": {"positions_observed": 2},
            },
            "coverage_groups": {
                "LinkedIn::Site Reliability": {"positions_observed": 2},
                "Greenhouse::Site Reliability": {"positions_observed": 2},
            },
        }
        gaps = {"blocking_prompt_count": 0, "coverage_counts": {}}
        without_submit = {
            "run_count": 4,
            "per_platform_role_target": 2,
            "platform_role_target_achieved": True,
            "actual_submit_count": 0,
            "selector_miss_count": 0,
            "real_platform_submission": False,
        }
        with_submit = {
            **without_submit,
            "actual_submit_count": 2,
            "would_submit_count": 2,
            "eligible_submit_count": 2,
            "eligible_submit_target_count": 2,
            "eligible_submit_achieved": True,
            "expected_blocker_count": 2,
            "local_synthetic_submit_allowed": True,
        }

        blocked_gate = build_research_coverage_gate(
            research,
            synthetic=without_submit,
            gaps=gaps,
            position_target=2,
            target_platforms=["LinkedIn", "Greenhouse"],
            target_role_families=["Site Reliability"],
        )
        ready_gate = build_research_coverage_gate(
            research,
            synthetic=with_submit,
            gaps=gaps,
            position_target=2,
            target_platforms=["LinkedIn", "Greenhouse"],
            target_role_families=["Site Reliability"],
        )

        self.assertFalse(blocked_gate["ready_for_full_automation"])
        self.assertTrue(ready_gate["ready_for_full_automation"])
        self.assertEqual(ready_gate["synthetic"]["actual_submit_count"], 2)
        self.assertEqual(ready_gate["synthetic"]["eligible_submit_count"], 2)
        self.assertEqual(ready_gate["synthetic"]["eligible_submit_target_count"], 2)
        self.assertTrue(ready_gate["synthetic"]["eligible_submit_achieved"])
        self.assertFalse(ready_gate["synthetic"]["real_platform_submission"])

    def test_write_research_coverage_gate_outputs_reports(self) -> None:
        research = {
            "positions_observed_total": 1,
            "platforms": {"LinkedIn": {"positions_observed": 1}},
            "coverage_groups": {"LinkedIn::Site Reliability": {"positions_observed": 1}},
        }
        synthetic = {
            "run_count": 1,
            "platform_role_target_achieved": False,
            "actual_submit_count": 0,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            json_output = Path(temp_dir) / "coverage.json"
            markdown_output = Path(temp_dir) / "coverage.md"

            gate = write_research_coverage_gate(
                research,
                synthetic,
                gaps=None,
                json_output=json_output,
                markdown_output=markdown_output,
                position_target=1,
            )

            self.assertIn("real_platform_counts", gate)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertIn("Research Coverage Gate", markdown_output.read_text())

    def test_goal_readiness_audit_separates_user_blockers_from_policy_gates(self) -> None:
        coverage_gate = {
            "positions_observed_total": 400,
            "real_platform_target_achieved": True,
            "real_platform_role_target_achieved": True,
            "next_collection_targets": [],
            "synthetic": {
                "run_count": 400,
                "platform_role_target_achieved": True,
                "actual_submit_count": 350,
                "eligible_submit_count": 350,
                "eligible_submit_target_count": 350,
                "eligible_submit_achieved": True,
                "expected_blocker_count": 50,
                "selector_miss_count": 0,
                "real_platform_submission": False,
            },
        }
        gaps = {
            "unique_prompts_observed": 12,
            "ready_prompt_count": 8,
            "blocking_prompt_count": 4,
            "coverage_counts": {
                "needs_user_confirmation": 2,
                "needs_resume_facts": 1,
                "final_submit_confirmation": 1,
                "sensitive_not_stored": 3,
            },
            "blocking_prompts": [
                {
                    "label": "Have you worked with us before?",
                    "category": "employment_history",
                    "coverage_status": "needs_user_confirmation",
                    "required_count": 5,
                    "platforms": ["Greenhouse"],
                }
            ],
        }
        readiness = {
            "manual_gate_count": 3,
            "readiness_counts": {"autofill_ready": 20, "closed_skip": 1, "needs_learning": 2},
        }
        critical_status = {"summary": {"waiting_count": 2, "supervised_only_count": 1}}
        critical_updates_readiness = {
            "summary": {
                "update_entry_count": 12,
                "waiting_after_update_count": 2,
                "ready_after_update_count": 10,
                "data_blocking_prompts_after": 1,
                "unknown_updates": 0,
                "high_risk_unconfirmed_count": 0,
            },
            "waiting_rows": [
                {
                    "input_id": "profile_zip_or_postal_code",
                    "status": "waiting_for_answer",
                    "question": "What ZIP/postal code should automation use?",
                    "input_type": "profile_or_resume_fact",
                    "approval_risk": "needs_review",
                    "next_action": "fill user_answer and approve only if truthful and reusable",
                },
                {
                    "input_id": "answer_memory_citizenship_status_default_policy",
                    "status": "approved_missing_answer",
                    "question": "What citizenship answers should automation use?",
                    "input_type": "high_risk_exact_confirmation",
                    "approval_risk": "high",
                    "next_action": "fill user_answer before applying",
                },
            ],
        }
        fake_critical = {
            "ready_to_apply_count": 10,
            "waiting_count": 0,
            "real_platform_submission": False,
            "policy": {"submits_real_applications": False},
        }
        fake_rehearsal = {
            "run_count": 100,
            "platform_role_target_achieved": True,
            "eligible_submit_achieved": True,
            "actual_submit_count": 100,
            "selector_miss_count": 0,
            "real_platform_submission": False,
        }
        autofill_batch = {
            "selected_count": 100,
            "selected_autofill_allowed_count": 100,
            "selector_miss_count": 0,
            "would_submit_count": 0,
            "real_platform_submission": False,
            "local_synthetic_submit_count": 100,
            "local_synthetic_submit_achieved": True,
            "local_synthetic_submit_selector_miss_count": 0,
        }
        synthetic_unblocker_proof = {
            "real_platform_submission": False,
            "writes_real_profile_or_memory": False,
            "summary": {
                "proof_complete": True,
                "synthetic_final_unblocker_update_count": 2,
                "existing_draft_update_count": 10,
                "data_blocking_prompts_after": 0,
                "local_100_synthetic_apply_path_ready": True,
            },
        }
        post_answer_pipeline = {
            "status": "synthetic_queue_rehearsal_ready",
            "ready_for_workflow": True,
            "source": "final_answer_reply_synthetic_rehearsal",
            "synthetic_final_answers": True,
            "policy": {"submits_real_applications": False},
            "final_answer_intake_report": {
                "summary": {
                    "answer_input_count": 6,
                    "missing_unblocker_count": 0,
                    "unconfirmed_high_risk_count": 0,
                    "needs_more_specific_answer_count": 0,
                    "unknown_answer_count": 0,
                }
            },
            "synthetic_queue_rehearsal": {
                "ready_for_supervised_browser_autofill": True,
                "submits_real_applications": False,
                "autofill_packet_selected": 100,
                "autofill_packet_selector_misses": 0,
                "autofill_packet_final_submit_stops": 100,
            },
        }
        fake_learning_probe = {
            "fake_answered_task_count": 87,
            "synthetic_blocker_clearance_added_count": 4,
            "remaining_learning_blocker_count": 0,
            "remaining_manual_gate_count": 132,
            "learning_blockers_cleared": True,
            "real_platform_submission": False,
            "policy": {
                "writes_real_profile_or_memory": False,
                "submits_real_applications": False,
            },
        }
        closed_jobs = {"jobs": [{"key": "linkedin:1", "reason": "No longer accepting applications"}]}
        closed_preflight = {
            "candidate_count": 100,
            "live_checked_count": 100,
            "open_eligible_count": 100,
            "closed_count": 0,
            "uncertain_count": 0,
            "error_count": 0,
            "retry_attempts": 1,
            "fetch_attempt_count": 100,
        }
        platform_question_playbook = {
            "summary": {
                "target_platform_count": 2,
                "target_platforms_at_100_count": 2,
                "research_question_item_count": 500,
                "selected_position_count": 100,
                "selected_local_synthetic_submit_count": 100,
                "selected_selector_miss_count": 0,
                "closed_posting_count": 1,
                "final_answer_missing_count": 2,
                "real_platform_submission": False,
            }
        }
        position_execution_audit = {
            "status": "ready_after_confirmed_answers",
            "summary": {
                "target_count": 100,
                "position_count": 100,
                "ready_after_answers_count": 100,
                "synthetic_ready_now_count": 100,
                "local_synthetic_submit_position_count": 100,
                "selector_miss_count": 0,
                "unsafe_real_submit_position_count": 0,
                "final_submit_stop_position_count": 100,
                "remaining_user_answer_count": 2,
            },
        }

        audit = build_goal_readiness_audit(
            coverage_gate,
            gaps,
            readiness,
            critical_input_status=critical_status,
            critical_input_updates_readiness=critical_updates_readiness,
            fake_learning_probe=fake_learning_probe,
            fake_critical_input_probe=fake_critical,
            fake_position_rehearsal=fake_rehearsal,
            autofill_batch_plan=autofill_batch,
            synthetic_unblocker_proof=synthetic_unblocker_proof,
            post_answer_pipeline=post_answer_pipeline,
            closed_preflight=closed_preflight,
            closed_jobs=closed_jobs,
            platform_question_playbook=platform_question_playbook,
            position_execution_audit=position_execution_audit,
        )
        markdown = render_goal_readiness_audit_markdown(audit)

        self.assertEqual(audit["status"], "needs_user_answers")
        self.assertFalse(audit["goal_complete"])
        self.assertFalse(audit["can_unattended_submit_real_employers"])
        self.assertEqual(audit["blocker_summary"]["data_blocking_prompt_count"], 3)
        self.assertEqual(audit["blocker_summary"]["draft_data_blocking_prompt_count_after_updates"], 1)
        self.assertEqual(audit["blocker_summary"]["final_answer_waiting_count_after_drafts"], 2)
        self.assertEqual(audit["blocker_summary"]["final_answer_waiting_high_risk_count_after_drafts"], 1)
        self.assertEqual(audit["final_answer_waiting_rows"][0]["alias"], "zip_or_postal_code")
        self.assertFalse(audit["final_answer_waiting_rows"][0]["high_risk"])
        self.assertEqual(audit["final_answer_waiting_rows"][1]["alias"], "citizenship_status")
        self.assertTrue(audit["final_answer_waiting_rows"][1]["high_risk"])
        self.assertEqual(audit["blocker_summary"]["critical_update_entry_count"], 12)
        self.assertEqual(audit["blocker_summary"]["policy_gate_prompt_count"], 4)
        self.assertTrue(audit["blocker_summary"]["real_platform_target_achieved"])
        self.assertTrue(audit["blocker_summary"]["real_platform_role_target_achieved"])
        self.assertEqual(audit["blocker_summary"]["positions_observed_total"], 400)
        self.assertEqual(audit["blocker_summary"]["synthetic_browser_run_count"], 400)
        self.assertTrue(audit["blocker_summary"]["synthetic_browser_platform_role_target_achieved"])
        self.assertEqual(audit["blocker_summary"]["synthetic_browser_local_submit_count"], 350)
        self.assertEqual(audit["blocker_summary"]["synthetic_browser_eligible_submit_count"], 350)
        self.assertEqual(audit["blocker_summary"]["synthetic_browser_eligible_submit_target_count"], 350)
        self.assertTrue(audit["blocker_summary"]["synthetic_browser_eligible_submit_achieved"])
        self.assertEqual(audit["blocker_summary"]["synthetic_browser_expected_blocker_count"], 50)
        self.assertEqual(audit["blocker_summary"]["synthetic_browser_selector_miss_count"], 0)
        self.assertFalse(audit["blocker_summary"]["synthetic_browser_real_platform_submission"])
        self.assertEqual(audit["blocker_summary"]["autofill_batch_local_synthetic_submit_count"], 100)
        self.assertTrue(audit["blocker_summary"]["autofill_batch_local_synthetic_submit_achieved"])
        self.assertTrue(audit["blocker_summary"]["synthetic_unblocker_proof_complete"])
        self.assertEqual(audit["blocker_summary"]["post_answer_pipeline_status"], "synthetic_queue_rehearsal_ready")
        self.assertTrue(audit["blocker_summary"]["post_answer_synthetic_queue_rehearsal_ready"])
        self.assertEqual(audit["blocker_summary"]["post_answer_synthetic_autofill_selected_count"], 100)
        self.assertEqual(audit["blocker_summary"]["post_answer_synthetic_selector_miss_count"], 0)
        self.assertEqual(audit["blocker_summary"]["post_answer_synthetic_final_submit_stop_count"], 100)
        self.assertFalse(audit["blocker_summary"]["post_answer_synthetic_submits_real_applications"])
        self.assertEqual(
            audit["blocker_summary"]["post_answer_pipeline_source"],
            "final_answer_reply_synthetic_rehearsal",
        )
        self.assertTrue(audit["blocker_summary"]["post_answer_text_reply_rehearsal_ready"])
        self.assertEqual(audit["blocker_summary"]["post_answer_intake_answer_count"], 6)
        self.assertEqual(audit["blocker_summary"]["post_answer_intake_missing_unblocker_count"], 0)
        self.assertEqual(audit["blocker_summary"]["post_answer_intake_unconfirmed_high_risk_count"], 0)
        self.assertTrue(audit["blocker_summary"]["fake_learning_blockers_cleared"])
        self.assertEqual(audit["blocker_summary"]["fake_learning_remaining_blockers"], 0)
        self.assertEqual(
            audit["blocker_summary"]["fake_learning_synthetic_blocker_clearance_added_count"],
            4,
        )
        self.assertTrue(audit["blocker_summary"]["platform_playbook_ready"])
        self.assertEqual(audit["blocker_summary"]["platform_playbook_target_platforms_at_100"], "2/2")
        self.assertEqual(audit["blocker_summary"]["platform_playbook_selected_position_count"], 100)
        self.assertTrue(audit["blocker_summary"]["position_execution_ready"])
        self.assertEqual(audit["blocker_summary"]["position_execution_position_count"], 100)
        self.assertEqual(audit["blocker_summary"]["position_execution_selector_miss_count"], 0)
        self.assertEqual(audit["requirements"][0]["status"], "achieved")
        self.assertEqual(audit["requirements"][0]["evidence"]["latest_preflight_open_eligible"], 100)
        self.assertEqual(audit["requirements"][0]["evidence"]["latest_preflight_uncertain"], 0)
        self.assertEqual(audit["blocker_summary"]["latest_preflight_open_eligible_count"], 100)
        self.assertEqual(audit["blocker_summary"]["latest_preflight_uncertain_count"], 0)
        self.assertGreaterEqual(audit["requirements"][0]["evidence"]["closed_phrase_count"], 20)
        self.assertGreaterEqual(audit["requirements"][0]["evidence"]["closed_regex_count"], 7)
        fake_requirement = next(item for item in audit["requirements"] if item["id"] == "fake_candidate_100_position_rehearsal")
        self.assertTrue(fake_requirement["evidence"]["post_answer_synthetic_queue_rehearsal_ready"])
        fake_learning_requirement = next(item for item in audit["requirements"] if item["id"] == "fake_learning_blocker_clearance")
        self.assertEqual(fake_learning_requirement["status"], "achieved")
        self.assertEqual(fake_learning_requirement["evidence"]["synthetic_blocker_clearance_added_count"], 4)
        text_reply_requirement = next(
            item for item in audit["requirements"] if item["id"] == "final_answer_text_reply_rehearsal"
        )
        self.assertEqual(text_reply_requirement["status"], "achieved")
        self.assertEqual(text_reply_requirement["evidence"]["parsed_answer_count"], 6)
        playbook_requirement = next(item for item in audit["requirements"] if item["id"] == "platform_question_playbook")
        self.assertEqual(playbook_requirement["status"], "achieved")
        self.assertEqual(playbook_requirement["evidence"]["target_platforms_at_100"], "2/2")
        position_requirement = next(
            item for item in audit["requirements"] if item["id"] == "position_execution_100_ledger"
        )
        self.assertEqual(position_requirement["status"], "achieved")
        self.assertEqual(position_requirement["evidence"]["position_count"], 100)
        ready_position_execution_audit = json.loads(json.dumps(position_execution_audit))
        ready_position_execution_audit["status"] = "ready_for_supervised_autofill"
        ready_position_execution_audit["summary"]["remaining_user_answer_count"] = 0
        ready_position_execution_audit["summary"]["global_remaining_user_answer_count"] = 2
        ready_position_execution_audit["summary"]["ready_for_supervised_autofill_now"] = True
        selected_ready_audit = build_goal_readiness_audit(
            coverage_gate,
            gaps,
            readiness,
            critical_input_status=critical_status,
            critical_input_updates_readiness=critical_updates_readiness,
            fake_learning_probe=fake_learning_probe,
            fake_critical_input_probe=fake_critical,
            fake_position_rehearsal=fake_rehearsal,
            autofill_batch_plan=autofill_batch,
            synthetic_unblocker_proof=synthetic_unblocker_proof,
            post_answer_pipeline=post_answer_pipeline,
            closed_preflight=closed_preflight,
            closed_jobs=closed_jobs,
            platform_question_playbook=platform_question_playbook,
            position_execution_audit=ready_position_execution_audit,
        )
        self.assertEqual(selected_ready_audit["status"], "selected_100_supervised_autofill_ready")
        self.assertTrue(selected_ready_audit["selected_queue_supervised_autofill_ready"])
        self.assertFalse(selected_ready_audit["supervised_autofill_ready_after_user_answers"])
        self.assertFalse(selected_ready_audit["goal_complete"])
        self.assertEqual(
            selected_ready_audit["blocker_summary"]["position_execution_remaining_user_answers"],
            0,
        )
        self.assertEqual(
            selected_ready_audit["blocker_summary"]["position_execution_global_remaining_user_answers"],
            2,
        )
        self.assertEqual(audit["requirements"][4]["status"], "achieved")
        self.assertEqual(audit["top_data_blocking_prompts"][0]["coverage_status"], "needs_user_confirmation")
        self.assertIn("Goal Readiness Audit", markdown)
        self.assertIn("needs_user_answers", markdown)
        self.assertIn("real platform coverage achieved: true", markdown)
        self.assertIn("real platform-role coverage achieved: true", markdown)
        self.assertIn("synthetic browser rehearsal: runs 400", markdown)
        self.assertIn("eligible 350 / 350", markdown)
        self.assertIn("real platform submission false", markdown)
        self.assertIn("100-batch local synthetic submits: 100", markdown)
        self.assertIn("final answer blanks after prepared drafts: 2", markdown)
        self.assertIn("final answer high-risk blanks after prepared drafts: 1", markdown)
        self.assertIn("Final Answer Blanks", markdown)
        self.assertIn("zip_or_postal_code", markdown)
        self.assertIn("citizenship_status", markdown)
        self.assertIn("synthetic final unblocker proof complete: true", markdown)
        self.assertIn("post-answer synthetic queue ready: true", markdown)
        self.assertIn("post-answer text reply rehearsal ready: true", markdown)
        self.assertIn("post-answer intake validation: answers 6, missing 0, unconfirmed 0, specificity 0, unknown 0", markdown)
        self.assertIn("post-answer synthetic selected: 100, selector misses 0, final-submit stops 100", markdown)
        self.assertIn("fake learning blockers cleared: true", markdown)
        self.assertIn("fake learning remaining: 0 learnable, 132 manual gates, synthetic additions 4", markdown)
        self.assertIn("platform playbook ready: true", markdown)
        self.assertIn("platform playbook targets at 100: 2/2", markdown)
        self.assertIn("position execution audit ready: true", markdown)
        self.assertIn("position execution audited: 100 / 100", markdown)
        self.assertIn("latest live preflight: 100 open / 100 candidates", markdown)
        self.assertIn("Top Data-Blocking Prompts", markdown)
        self.assertIn("Have you worked with us before?", markdown)
        self.assertIn("resume-after-answers", "\n".join(audit["next_actions"]))

        with tempfile.TemporaryDirectory() as temp_dir:
            json_output = Path(temp_dir) / "goal.json"
            markdown_output = Path(temp_dir) / "goal.md"
            written = write_goal_readiness_audit(
                coverage_gate,
                gaps,
                readiness,
                json_output,
                markdown_output,
                critical_input_status=critical_status,
                critical_input_updates_readiness=critical_updates_readiness,
                fake_learning_probe=fake_learning_probe,
                fake_critical_input_probe=fake_critical,
                fake_position_rehearsal=fake_rehearsal,
                autofill_batch_plan=autofill_batch,
                synthetic_unblocker_proof=synthetic_unblocker_proof,
                post_answer_pipeline=post_answer_pipeline,
                closed_preflight=closed_preflight,
                closed_jobs=closed_jobs,
                platform_question_playbook=platform_question_playbook,
                position_execution_audit=position_execution_audit,
            )

            self.assertEqual(written["missing_requirement_count"], 1)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertIn("Real employer unattended submit: false", markdown_output.read_text())

    def test_automation_handoff_report_prioritizes_answers_and_stop_actions(self) -> None:
        goal_readiness_audit = {
            "status": "needs_user_answers",
            "goal_complete": False,
            "can_unattended_submit_real_employers": False,
            "blocker_summary": {
                "data_blocking_prompt_count": 253,
                "critical_waiting_count": 10,
                "critical_supervised_only_count": 1,
                "synthetic_unblocker_proof_complete": True,
                "synthetic_final_unblocker_update_count": 6,
                "synthetic_unblocker_existing_draft_update_count": 83,
                "synthetic_unblocker_data_blocking_prompts_after": 0,
            },
            "requirements": [
                {
                    "id": "real_user_answer_learning",
                    "requirement": "Learn the remaining truthful user answers.",
                    "status": "needs_user_answers",
                    "evidence": {"data_blocking_prompt_count": 253},
                }
            ],
        }
        critical_input_questionnaire = {
            "question_count": 2,
            "answerable_question_count": 1,
            "high_risk_question_count": 1,
            "questions": [
                {
                    "impact_rank": 1,
                    "input_id": "answer_memory_citizenship_status_default_policy",
                    "input_type": "category_default_policy",
                    "question": "What should automation answer for citizenship status questions?",
                    "required_user_response": "Confirm the truthful reusable policy.",
                    "approval_risk": "high",
                    "high_risk": True,
                    "supervised_only": False,
                    "suggested_answer": "",
                    "impact": {
                        "data_blocking_prompts_delta": -17,
                        "ready_prompts_delta": 17,
                        "positions_ready_for_autofill_delta": 13,
                    },
                    "required_count": 17,
                    "platforms": ["Greenhouse", "Ashby"],
                    "labels": ["Citizenship status"],
                },
                {
                    "impact_rank": 2,
                    "input_id": "supervised_confirmation_policy_acknowledgement",
                    "input_type": "supervised_browser_review_only",
                    "question": "Confirm policy acknowledgement.",
                    "required_user_response": "Review in browser.",
                    "approval_risk": "supervised_only",
                    "high_risk": True,
                    "supervised_only": True,
                    "impact": {
                        "data_blocking_prompts_delta": 0,
                        "ready_prompts_delta": 0,
                        "positions_ready_for_autofill_delta": 0,
                    },
                },
            ],
        }
        critical_input_impact = {
            "summary": {
                "combined_data_blocking_prompts_delta": -66,
                "combined_data_blocking_prompts_after": 12,
                "combined_positions_ready_for_autofill_delta": 171,
                "top_input_id": "answer_memory_citizenship_status_default_policy",
            },
            "individual_impact_count": 50,
            "individual_impact_truncated": True,
            "combined_remaining_data_blocker_counts": {"total": 12},
            "input_impacts": [],
        }
        autofill_batch = {
            "selected_count": 100,
            "selected_autofill_allowed_count": 100,
            "browser_action_count": 502,
            "stop_action_count": 167,
            "selector_miss_count": 0,
            "would_submit_count": 0,
            "local_synthetic_submit_count": 100,
            "local_synthetic_submit_achieved": True,
            "local_synthetic_submit_selector_miss_count": 0,
            "selected_stop_action_counts": {
                "final_submit_confirmation | Submit application": 100,
                "sensitive_not_stored | Disability status": 10,
            },
            "blocked_stop_action_counts": {
                "missing_profile_value | GitHub URL": 3,
                "missing_profile_value | Website": 11,
            },
            "selected_stop_actions": [
                {
                    "scope": "selected",
                    "position_index": 1,
                    "platform": "Greenhouse",
                    "company": "DoorDash",
                    "title": "SRE",
                    "apply_url": "https://job-boards.greenhouse.io/doordash/jobs/1",
                    "status": "final_submit_confirmation",
                    "label": "Submit application",
                    "handling": "stop before final submit and wait for explicit approval",
                }
            ],
            "blocked_candidate_stop_actions": [
                {
                    "scope": "blocked_candidate",
                    "position_index": 1,
                    "platform": "Lever",
                    "company": "Example",
                    "title": "Platform Engineer",
                    "apply_url": "https://jobs.lever.co/example/1",
                    "status": "missing_profile_value",
                    "label": "GitHub URL",
                }
            ],
        }
        apply_queue_handoff = {
            "status": "waiting_for_confirmed_answers",
            "open_ready_count": 0,
            "open_after_answers_count": 100,
            "manual_live_check_count": 0,
            "closed_or_skipped_count": 0,
        }
        apply_queue_autofill_packet = {
            "status": "waiting_for_confirmed_answers",
            "ready_for_supervised_browser_autofill": False,
            "ready_after_confirmed_answers": True,
            "selected_count": 100,
            "summary": {
                "browser_action_count": 101,
                "final_submit_stop_count": 100,
                "selector_miss_count": 0,
                "local_synthetic_submit_count": 100,
            },
        }
        apply_queue_refresh = {
            "status": "queue_refreshed",
            "rounds": [{"round": 1, "live_check_status": "checked", "top_up_required": 0}],
            "final": {
                "live_open_after_answers_count": 100,
                "top_up_required_count": 0,
                "manual_live_check_count": 0,
                "closed_or_skipped_count": 0,
            },
        }
        position_execution_audit = {
            "status": "ready_after_confirmed_answers",
            "summary": {
                "position_count": 100,
                "target_count": 100,
                "ready_after_answers_count": 100,
                "synthetic_ready_now_count": 100,
                "selector_miss_count": 0,
                "final_submit_stop_count": 100,
                "remaining_user_answer_count": 6,
            },
            "positions": [
                {
                    "index": 1,
                    "status": "ready_after_confirmed_answers",
                    "platform": "Lever",
                    "company": "Example",
                    "title": "SRE",
                    "role_family": "SRE",
                    "live_status": "open_live_checked",
                    "local_synthetic_submit_count": 1,
                    "final_submit_stop_count": 1,
                    "selector_miss_count": 0,
                    "blockers_or_gates": [
                        "waiting_for_confirmed_answers",
                        "final_submit_supervised_gate",
                    ],
                    "apply_url": "https://jobs.lever.co/example/1",
                }
            ],
            "platform_summary": [
                {
                    "platform": "Lever",
                    "audited_positions": 100,
                    "observed_positions": 100,
                    "local_synthetic_submit_positions": 100,
                    "selector_miss_positions": 0,
                    "final_submit_stop_positions": 100,
                    "remaining_answer_inputs": 2,
                }
            ],
        }
        final_answer_intake_template = {
            "answer_count": 6,
            "high_risk_count": 5,
            "fields": [
                {
                    "alias": "citizenship_status",
                    "input_id": "answer_memory_citizenship_status_default_policy",
                    "question": "What should automation answer for citizenship status questions?",
                    "required_user_response": "Confirm the truthful reusable policy.",
                    "high_risk": True,
                    "required_count": 17,
                    "platforms": ["Greenhouse", "Ashby"],
                    "labels": ["Citizenship status"],
                }
            ],
        }
        answer_memory = {"answers": [{"sample_question": "Expected compensation?", "answer": "100000+"}]}
        closed_jobs = {"jobs": [{"key": "linkedin:4415090263", "reason": "No longer accepting applications"}]}

        report = build_automation_handoff_report(
            goal_readiness_audit,
            critical_input_questionnaire,
            critical_input_impact,
            autofill_batch,
            final_answer_intake_template=final_answer_intake_template,
            answer_memory=answer_memory,
            closed_jobs=closed_jobs,
            apply_queue_handoff=apply_queue_handoff,
            apply_queue_autofill_packet=apply_queue_autofill_packet,
            apply_queue_refresh=apply_queue_refresh,
            position_execution_audit=position_execution_audit,
        )
        markdown = render_automation_handoff_markdown(report)
        html = render_automation_handoff_html(report)

        self.assertEqual(report["status"], "waiting_for_confirmed_answers")
        self.assertEqual(report["summary"]["autofill_selected_count"], 100)
        self.assertEqual(report["summary"]["autofill_local_synthetic_submit_count"], 100)
        self.assertTrue(report["summary"]["autofill_local_synthetic_submit_achieved"])
        self.assertEqual(report["summary"]["combined_data_blocking_prompts_after"], 12)
        self.assertEqual(report["summary"]["combined_remaining_data_blocker_count"], 12)
        self.assertTrue(report["summary"]["individual_impact_truncated"])
        self.assertEqual(report["summary"]["closed_registry_count"], 1)
        self.assertEqual(report["summary"]["apply_queue_open_after_answers_count"], 100)
        self.assertEqual(report["summary"]["apply_queue_refresh_status"], "queue_refreshed")
        self.assertEqual(report["summary"]["apply_queue_refresh_live_open_after_answers_count"], 100)
        self.assertEqual(report["summary"]["apply_queue_refresh_top_up_required_count"], 0)
        self.assertEqual(report["summary"]["autofill_packet_browser_action_count"], 101)
        self.assertEqual(report["summary"]["autofill_packet_final_submit_stop_count"], 100)
        self.assertEqual(report["summary"]["position_execution_audited_count"], 100)
        self.assertEqual(report["summary"]["position_execution_ready_after_answers_count"], 100)
        self.assertEqual(report["summary"]["position_execution_selector_miss_count"], 0)
        self.assertEqual(report["summary"]["final_answer_intake_count"], 6)
        self.assertEqual(report["summary"]["final_answer_intake_high_risk_count"], 5)
        self.assertFalse(report["summary"]["final_answer_intake_ready_for_finalize"])
        self.assertEqual(report["summary"]["final_answer_intake_missing_count"], 6)
        self.assertEqual(report["summary"]["final_answer_intake_needs_more_specific_count"], 0)
        self.assertTrue(report["summary"]["synthetic_unblocker_proof_complete"])
        self.assertEqual(report["summary"]["synthetic_final_unblocker_update_count"], 6)
        self.assertEqual(report["confirmed_answer_runbook"][0]["status"], "waiting_for_user")
        self.assertIn("--validate-only", report["confirmed_answer_runbook"][2]["action"])
        self.assertIn("refresh-apply-queue", report["confirmed_answer_runbook"][5]["action"])
        self.assertIn("--include-values", report["confirmed_answer_runbook"][5]["action"])
        self.assertIn("resume-after-answers", report["one_command_resume"])
        self.assertIn("--live-check-limit", report["one_command_resume"])
        self.assertIn("--open-browser", report["one_command_resume_and_open"])
        self.assertIn("resume-after-answers", report["next_commands"][0])
        self.assertIn("final-answer-blockers", report["next_commands"][1])
        self.assertIn("rehearse-after-answers", report["next_commands"][2])
        self.assertIn("resume-after-answers --reply-text", report["next_commands"][3])
        self.assertIn("--validate-only", report["next_commands"][3])
        self.assertIn("final-answer-reply --reply-file", report["next_commands"][4])
        self.assertIn("job_apply_agent/outbox/final_answer_reply_template_latest.txt", report["next_commands"][4])
        self.assertIn("--run-post-answer-pipeline", report["next_commands"][4])
        self.assertIn("resume-after-answers", report["next_commands"][5])
        self.assertIn("resume-after-answers", report["next_commands"][6])
        self.assertIn("--open-browser", report["next_commands"][6])
        self.assertIn("post-answer-pipeline --synthetic-final-answers --synthetic-rehearse-queue", report["next_commands"][7])
        self.assertIn("post-answer-pipeline --fail-on-not-ready", report["next_commands"][8])
        self.assertIn("post-answer-pipeline --apply --live-check", report["next_commands"][9])
        self.assertIn("refresh-apply-queue --max-rounds 2", " ".join(report["next_commands"]))
        self.assertIn("closed-preflight --jobs", " ".join(report["next_commands"]))
        self.assertEqual(report["answer_impact_queue"][0]["input_id"], "answer_memory_citizenship_status_default_policy")
        self.assertEqual(report["final_answer_intake"][0]["alias"], "citizenship_status")
        self.assertEqual(report["answer_impact_queue"][0]["handoff_action"], "confirm_truthful_answer_before_persisting")
        self.assertEqual(report["selected_stop_action_summary"][0]["status"], "final_submit_confirmation")
        self.assertEqual(report["missing_profile_inputs"][0]["label"], "Website")
        self.assertIn("Application Automation Handoff", markdown)
        self.assertIn("data blockers after simulated confirmations: 12", markdown)
        self.assertIn("local synthetic submit proof: 100 submits", markdown)
        self.assertIn("synthetic final unblocker proof: true", markdown)
        self.assertIn("apply queue refresh: queue_refreshed", markdown)
        self.assertIn("autofill packet: waiting_for_confirmed_answers", markdown)
        self.assertIn("Confirmed-Answer Runbook", markdown)
        self.assertIn("One-Command Resume", markdown)
        self.assertIn("resume-after-answers", markdown)
        self.assertIn("rehearse-after-answers", markdown)
        self.assertIn("final-answer-reply --reply-file", markdown)
        self.assertIn("Final-Answer Intake", markdown)
        self.assertIn("needs specificity 0", markdown)
        self.assertIn("100-Position Stop Actions", markdown)
        self.assertIn("position execution audit: ready_after_confirmed_answers", markdown)
        self.assertIn("100-Position Execution Audit", markdown)
        self.assertIn("GitHub URL", html)
        self.assertIn("Queue refresh", html)
        self.assertIn("Confirmed-Answer Runbook", html)
        self.assertIn("One-Command Resume", html)
        self.assertIn("Final-Answer Intake", html)
        self.assertIn("Answer Impact Queue", html)
        self.assertIn("100-Position Execution Audit", html)

        with tempfile.TemporaryDirectory() as temp_dir:
            json_output = Path(temp_dir) / "handoff.json"
            markdown_output = Path(temp_dir) / "handoff.md"
            html_output = Path(temp_dir) / "handoff.html"
            written = write_automation_handoff_report(
                goal_readiness_audit,
                critical_input_questionnaire,
                critical_input_impact,
                autofill_batch,
                json_output,
                markdown_output,
                html_output,
                final_answer_intake_template=final_answer_intake_template,
                answer_memory=answer_memory,
                closed_jobs=closed_jobs,
                apply_queue_handoff=apply_queue_handoff,
                apply_queue_autofill_packet=apply_queue_autofill_packet,
                apply_queue_refresh=apply_queue_refresh,
                position_execution_audit=position_execution_audit,
            )
            self.assertEqual(written["status"], "waiting_for_confirmed_answers")
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertTrue(html_output.exists())

    def test_apply_queue_readiness_waits_for_answers_and_filters_closed_registry(self) -> None:
        open_position = {
            "index": 1,
            "position_key": "url:https://job-boards.greenhouse.io/example/jobs/1",
            "platform": "Greenhouse",
            "company": "Example",
            "title": "Site Reliability Engineer",
            "role_family": "Site Reliability",
            "apply_url": "https://job-boards.greenhouse.io/example/jobs/1",
            "readiness": "autofill_ready",
            "manifest_status": "autofill_ready_with_supervised_gates",
            "autofill_allowed": True,
            "browser_action_count": 7,
            "stop_action_count": 1,
            "stop_action_statuses": ["final_submit_confirmation"],
            "local_check_selector_miss_count": 0,
            "local_synthetic_submit_count": 1,
        }
        closed_position = {
            "index": 2,
            "position_key": "url:https://jobs.lever.co/closed/2",
            "platform": "Lever",
            "company": "Closed Co",
            "title": "Platform Engineer",
            "role_family": "Platform",
            "apply_url": "https://jobs.lever.co/closed/2",
            "readiness": "autofill_ready",
            "manifest_status": "autofill_ready_with_supervised_gates",
            "autofill_allowed": True,
            "browser_action_count": 6,
            "stop_action_count": 1,
            "stop_action_statuses": ["final_submit_confirmation"],
            "local_check_selector_miss_count": 0,
            "local_synthetic_submit_count": 1,
        }
        autofill_batch = {
            "selected_count": 2,
            "selected_autofill_allowed_count": 2,
            "selector_miss_count": 0,
            "local_synthetic_submit_count": 2,
            "local_synthetic_submit_achieved": True,
            "positions": [open_position, closed_position],
        }
        updates_readiness = {
            "ready_for_apply": False,
            "summary": {
                "waiting_after_update_count": 6,
                "data_blocking_prompts_after": 51,
                "high_risk_unconfirmed_count": 0,
            },
        }
        goal_audit = {"status": "needs_user_answers", "goal_complete": False}
        closed_jobs = {
            "version": 1,
            "jobs": [
                {
                    "key": job_registry_key(closed_position),
                    "status": "CLOSED",
                    "reason": "No longer accepting applications",
                }
            ],
        }

        report = build_apply_queue_readiness(
            autofill_batch,
            critical_input_updates_readiness=updates_readiness,
            goal_readiness_audit=goal_audit,
            closed_jobs=closed_jobs,
        )
        markdown = render_apply_queue_readiness_markdown(report)
        html = render_apply_queue_readiness_html(report)

        self.assertEqual(report["status"], "waiting_for_confirmed_answers")
        self.assertFalse(report["ready_for_supervised_autofill"])
        self.assertEqual(report["live_check_job_count"], 1)
        self.assertEqual(report["live_check_jobs"][0]["apply_url"], open_position["apply_url"])
        self.assertEqual(report["positions"][0]["queue_status"], "waiting_for_confirmed_answers")
        self.assertEqual(report["positions"][1]["queue_status"], "closed_registry")
        self.assertIn("critical_input_updates_not_ready", report["global_blockers"])
        self.assertIn("data_blockers_remaining_after_updates", report["global_blockers"])
        self.assertTrue(report["policy"]["stop_on_no_longer_accepting"])
        self.assertFalse(report["policy"]["real_platform_submission"])
        self.assertIn("Apply Queue Readiness", markdown)
        self.assertIn("closed_registry", markdown)
        self.assertIn("waiting_for_confirmed_answers", html)

    def test_apply_queue_readiness_ready_for_live_preflight_with_100_clean_positions(self) -> None:
        positions = []
        for index in range(1, 101):
            positions.append(
                {
                    "index": index,
                    "position_key": f"url:https://jobs.ashbyhq.com/example/{index}",
                    "platform": "Ashby",
                    "company": "Example",
                    "title": f"Platform Engineer {index}",
                    "role_family": "Platform",
                    "apply_url": f"https://jobs.ashbyhq.com/example/{index}?src=LinkedIn",
                    "readiness": "autofill_ready",
                    "manifest_status": "autofill_ready_with_supervised_gates",
                    "autofill_allowed": True,
                    "browser_action_count": 5,
                    "stop_action_count": 1,
                    "stop_action_statuses": ["final_submit_confirmation"],
                    "local_check_selector_miss_count": 0,
                    "local_synthetic_submit_count": 1,
                }
            )
        autofill_batch = {
            "selected_count": 100,
            "selected_autofill_allowed_count": 100,
            "selector_miss_count": 0,
            "local_synthetic_submit_count": 100,
            "local_synthetic_submit_achieved": True,
            "positions": positions,
        }
        updates_readiness = {
            "ready_for_apply": True,
            "summary": {
                "waiting_after_update_count": 0,
                "data_blocking_prompts_after": 0,
                "high_risk_unconfirmed_count": 0,
            },
        }

        report = build_apply_queue_readiness(
            autofill_batch,
            critical_input_updates_readiness=updates_readiness,
            goal_readiness_audit={"status": "ready", "goal_complete": False},
            closed_jobs={"version": 1, "jobs": []},
        )

        self.assertEqual(report["status"], "ready_for_live_closed_preflight")
        self.assertTrue(report["ready_for_supervised_autofill"])
        self.assertFalse(report["ready_for_unattended_real_submit"])
        self.assertEqual(report["live_check_job_count"], 100)
        self.assertEqual(
            report["queue_status_counts"],
            {"ready_for_live_closed_preflight": 100},
        )
        self.assertEqual(report["global_blockers"], [])
        self.assertIn("closed-preflight", report["next_commands"][1])
        self.assertNotIn("--apply", report["next_commands"][0])

        with tempfile.TemporaryDirectory() as temp_dir:
            autofill_path = Path(temp_dir) / "autofill.json"
            updates_path = Path(temp_dir) / "updates.json"
            goal_path = Path(temp_dir) / "goal.json"
            closed_path = Path(temp_dir) / "closed.json"
            json_output = Path(temp_dir) / "queue.json"
            markdown_output = Path(temp_dir) / "queue.md"
            html_output = Path(temp_dir) / "queue.html"
            live_jobs_output = Path(temp_dir) / "live_jobs.json"
            autofill_path.write_text(json.dumps(autofill_batch), encoding="utf-8")
            updates_path.write_text(json.dumps(updates_readiness), encoding="utf-8")
            goal_path.write_text(json.dumps({"status": "ready"}), encoding="utf-8")
            closed_path.write_text(json.dumps({"version": 1, "jobs": []}), encoding="utf-8")

            written = write_apply_queue_readiness(
                autofill_path,
                updates_path,
                goal_path,
                closed_path,
                json_output,
                markdown_output,
                html_output,
                live_jobs_output,
            )

            self.assertEqual(written["status"], "ready_for_live_closed_preflight")
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertTrue(html_output.exists())
            self.assertTrue(live_jobs_output.exists())
            live_payload = json.loads(live_jobs_output.read_text(encoding="utf-8"))
            self.assertEqual(len(live_payload["jobs"]), 100)

    def test_apply_queue_allows_filtered_batch_that_avoids_unresolved_answers(self) -> None:
        positions = []
        for index in range(1, 101):
            positions.append(
                {
                    "index": index,
                    "position_key": f"url:https://jobs.lever.co/example/{index}",
                    "platform": "Lever",
                    "company": "Example",
                    "title": f"SRE {index}",
                    "role_family": "SRE",
                    "apply_url": f"https://jobs.lever.co/example/{index}",
                    "readiness": "autofill_ready",
                    "manifest_status": "autofill_ready_with_supervised_gates",
                    "autofill_allowed": True,
                    "browser_action_count": 5,
                    "stop_action_count": 1,
                    "stop_action_statuses": ["final_submit_confirmation"],
                    "local_check_selector_miss_count": 0,
                    "local_synthetic_submit_count": 1,
                }
            )
        autofill_batch = {
            "selected_count": 100,
            "selected_autofill_allowed_count": 100,
            "selector_miss_count": 0,
            "local_synthetic_submit_count": 100,
            "local_synthetic_submit_achieved": True,
            "avoid_unresolved_final_answers": True,
            "avoid_final_answer_aliases": ["citizenship_status", "zip_or_postal_code"],
            "excluded_unresolved_final_answer_position_count": 0,
            "positions": positions,
        }
        updates_readiness = {
            "ready_for_apply": False,
            "summary": {
                "waiting_after_update_count": 6,
                "data_blocking_prompts_after": 49,
                "high_risk_unconfirmed_count": 5,
            },
        }

        report = build_apply_queue_readiness(
            autofill_batch,
            critical_input_updates_readiness=updates_readiness,
            goal_readiness_audit={"status": "needs_user_answers", "goal_complete": False},
            closed_jobs={"version": 1, "jobs": []},
        )

        self.assertEqual(report["status"], "ready_for_live_closed_preflight")
        self.assertTrue(report["ready_for_supervised_autofill"])
        self.assertEqual(report["global_blockers"], [])
        self.assertTrue(report["summary"]["filtered_batch_clears_unresolved_final_answers"])
        self.assertFalse(report["summary"]["updates_ready_for_apply"])
        self.assertTrue(report["summary"]["effective_updates_ready_for_queue"])
        self.assertEqual(report["queue_status_counts"], {"ready_for_live_closed_preflight": 100})

    def test_apply_queue_handoff_waits_for_answers_and_keeps_uncertain_closed(self) -> None:
        apply_queue = {
            "status": "waiting_for_confirmed_answers",
            "ready_for_supervised_autofill": False,
            "position_count": 3,
            "target_count": 3,
            "live_check_job_count": 3,
            "global_blockers": ["critical_input_updates_not_ready"],
            "positions": [
                {
                    "index": 1,
                    "queue_status": "waiting_for_confirmed_answers",
                    "position_key": "url:https://jobs.lever.co/example/open",
                    "platform": "Lever",
                    "company": "OpenCo",
                    "title": "SRE",
                    "role_family": "SRE",
                    "apply_url": "https://jobs.lever.co/example/open",
                    "final_submit_supervised": True,
                    "blockers": ["critical_answers_not_ready"],
                },
                {
                    "index": 2,
                    "queue_status": "waiting_for_confirmed_answers",
                    "position_key": "url:https://jobs.ashbyhq.com/example/uncertain",
                    "platform": "Ashby",
                    "company": "UncertainCo",
                    "title": "Platform Engineer",
                    "role_family": "Platform",
                    "apply_url": "https://jobs.ashbyhq.com/example/uncertain",
                    "final_submit_supervised": True,
                    "blockers": ["critical_answers_not_ready"],
                },
                {
                    "index": 3,
                    "queue_status": "closed_registry",
                    "position_key": "url:https://job-boards.greenhouse.io/example/jobs/closed",
                    "platform": "Greenhouse",
                    "company": "ClosedCo",
                    "title": "DevOps Engineer",
                    "role_family": "DevOps",
                    "apply_url": "https://job-boards.greenhouse.io/example/jobs/closed",
                    "final_submit_supervised": True,
                    "blockers": ["closed_registry_or_text"],
                },
            ],
        }
        closed_preflight = {
            "candidate_count": 3,
            "live_checked_count": 3,
            "open_eligible_count": 1,
            "closed_count": 1,
            "uncertain_count": 1,
            "error_count": 1,
            "status_counts": {
                "open_live_checked": 1,
                "check_error": 1,
                "closed_live_text": 1,
            },
            "checks": [
                {
                    "key": "url:https://jobs.lever.co/example/open",
                    "url": "https://jobs.lever.co/example/open",
                    "status": "open_live_checked",
                    "open_eligible": True,
                    "closed": False,
                },
                {
                    "key": "url:https://jobs.ashbyhq.com/example/uncertain",
                    "url": "https://jobs.ashbyhq.com/example/uncertain",
                    "status": "check_error",
                    "open_eligible": False,
                    "closed": False,
                    "error": "timed out",
                },
                {
                    "key": "url:https://job-boards.greenhouse.io/example/jobs/closed",
                    "url": "https://job-boards.greenhouse.io/example/jobs/closed",
                    "status": "closed_live_text",
                    "open_eligible": False,
                    "closed": True,
                    "reason": "No longer accepting applications",
                },
            ],
        }

        report = build_apply_queue_handoff(apply_queue, closed_preflight)
        markdown = render_apply_queue_handoff_markdown(report)
        html = render_apply_queue_handoff_html(report)

        self.assertEqual(report["status"], "waiting_for_confirmed_answers")
        self.assertFalse(report["ready_for_supervised_open_batch"])
        self.assertEqual(report["open_ready_count"], 0)
        self.assertEqual(report["open_after_answers_count"], 1)
        self.assertEqual(report["manual_live_check_count"], 1)
        self.assertEqual(report["closed_or_skipped_count"], 1)
        self.assertEqual(report["top_up_required_count"], 1)
        self.assertEqual(report["positions"][0]["handoff_status"], "waiting_for_answers_before_open")
        self.assertEqual(report["positions"][1]["handoff_status"], "requires_manual_live_check")
        self.assertEqual(report["positions"][2]["handoff_status"], "skip_closed")
        self.assertEqual(report["open_after_answers_jobs"][0]["company"], "OpenCo")
        self.assertIn("live_preflight_uncertain_or_missing", report["global_blockers"])
        self.assertTrue(report["policy"]["do_not_open_uncertain_candidates"])
        self.assertIn("Apply Queue Handoff", markdown)
        self.assertIn("top-up required: 1", markdown)
        self.assertIn("waiting_for_answers_before_open", html)

    def test_apply_queue_handoff_ready_writes_open_ready_jobs(self) -> None:
        positions = []
        checks = []
        for index in range(1, 101):
            url = f"https://jobs.lever.co/example/{index}"
            positions.append(
                {
                    "index": index,
                    "queue_status": "ready_for_live_closed_preflight",
                    "position_key": f"url:{url}",
                    "platform": "Lever",
                    "company": "Example",
                    "title": f"SRE {index}",
                    "role_family": "SRE",
                    "apply_url": url,
                    "final_submit_supervised": True,
                    "blockers": [],
                }
            )
            checks.append(
                {
                    "key": f"url:{url}",
                    "url": url,
                    "status": "open_live_checked",
                    "open_eligible": True,
                    "closed": False,
                }
            )
        apply_queue = {
            "status": "ready_for_live_closed_preflight",
            "ready_for_supervised_autofill": True,
            "position_count": 100,
            "live_check_job_count": 100,
            "global_blockers": [],
            "positions": positions,
        }
        closed_preflight = {
            "candidate_count": 100,
            "live_checked_count": 100,
            "open_eligible_count": 100,
            "closed_count": 0,
            "uncertain_count": 0,
            "error_count": 0,
            "status_counts": {"open_live_checked": 100},
            "checks": checks,
        }

        report = build_apply_queue_handoff(apply_queue, closed_preflight)
        self.assertEqual(report["status"], "ready_to_open_for_supervised_autofill")
        self.assertTrue(report["ready_for_supervised_open_batch"])
        self.assertEqual(report["open_ready_count"], 100)
        self.assertEqual(report["handoff_status_counts"], {"ready_to_open_for_supervised_autofill": 100})
        self.assertFalse(report["real_platform_submission"])
        self.assertEqual(report["open_ready_jobs"][0]["automation"]["mode"], "supervised_autofill")

        with tempfile.TemporaryDirectory() as temp_dir:
            queue_path = Path(temp_dir) / "queue.json"
            preflight_path = Path(temp_dir) / "preflight.json"
            json_output = Path(temp_dir) / "handoff.json"
            markdown_output = Path(temp_dir) / "handoff.md"
            html_output = Path(temp_dir) / "handoff.html"
            jobs_output = Path(temp_dir) / "open_ready.json"
            queue_path.write_text(json.dumps(apply_queue), encoding="utf-8")
            preflight_path.write_text(json.dumps(closed_preflight), encoding="utf-8")

            written = write_apply_queue_handoff(
                queue_path,
                preflight_path,
                json_output,
                markdown_output,
                html_output,
                jobs_output,
            )

            self.assertEqual(written["status"], "ready_to_open_for_supervised_autofill")
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertTrue(html_output.exists())
            self.assertTrue(jobs_output.exists())
            jobs_payload = json.loads(jobs_output.read_text(encoding="utf-8"))
            self.assertEqual(len(jobs_payload["jobs"]), 100)

    def test_apply_queue_handoff_closed_live_check_requires_topup_before_open_batch(self) -> None:
        positions = []
        checks = []
        for index in range(1, 101):
            url = f"https://jobs.lever.co/example/{index}"
            positions.append(
                {
                    "index": index,
                    "queue_status": "ready_for_live_closed_preflight",
                    "position_key": f"url:{url}",
                    "platform": "Lever",
                    "company": "Example",
                    "title": f"SRE {index}",
                    "role_family": "SRE",
                    "apply_url": url,
                    "final_submit_supervised": True,
                    "blockers": [],
                }
            )
            checks.append(
                {
                    "key": f"url:{url}",
                    "url": url,
                    "status": "open_live_checked",
                    "open_eligible": True,
                    "closed": False,
                }
            )
        checks[-1].update(
            {
                "status": "closed_live_text",
                "open_eligible": False,
                "closed": True,
                "reason": "No longer accepting applications",
            }
        )
        apply_queue = {
            "status": "ready_for_live_closed_preflight",
            "ready_for_supervised_autofill": True,
            "position_count": 100,
            "target_count": 100,
            "live_check_job_count": 100,
            "global_blockers": [],
            "positions": positions,
        }
        closed_preflight = {
            "candidate_count": 100,
            "live_checked_count": 100,
            "open_eligible_count": 99,
            "closed_count": 1,
            "uncertain_count": 0,
            "error_count": 0,
            "status_counts": {"open_live_checked": 99, "closed_live_text": 1},
            "checks": checks,
        }

        report = build_apply_queue_handoff(apply_queue, closed_preflight)
        markdown = render_apply_queue_handoff_markdown(report)

        self.assertEqual(report["status"], "needs_live_preflight_cleanup")
        self.assertFalse(report["ready_for_supervised_open_batch"])
        self.assertEqual(report["open_ready_count"], 99)
        self.assertEqual(report["closed_or_skipped_count"], 1)
        self.assertEqual(report["live_open_after_answers_count"], 99)
        self.assertEqual(report["top_up_required_count"], 1)
        self.assertIn("live_open_after_answers_below_target", report["global_blockers"])
        self.assertTrue(
            any(command.startswith("python3 -m job_apply_agent refresh-apply-queue") for command in report["next_commands"])
        )
        self.assertIn("top-up required: 1", markdown)

    def test_refresh_apply_queue_cli_help_exposes_live_check_controls(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "job_apply_agent", "refresh-apply-queue", "--help"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--live-check-limit", result.stdout)
        self.assertIn("--skip-live-check", result.stdout)
        self.assertIn("--force-rebuild", result.stdout)

    def test_apply_queue_handoff_supplemental_preflight_overrides_timeout(self) -> None:
        url = "https://jobs.lever.co/example/retry"
        apply_queue = {
            "status": "waiting_for_confirmed_answers",
            "ready_for_supervised_autofill": False,
            "position_count": 1,
            "live_check_job_count": 1,
            "positions": [
                {
                    "index": 1,
                    "queue_status": "waiting_for_confirmed_answers",
                    "position_key": f"url:{url}",
                    "platform": "Lever",
                    "company": "RetryCo",
                    "title": "SRE",
                    "role_family": "SRE",
                    "apply_url": url,
                    "final_submit_supervised": True,
                    "blockers": ["critical_answers_not_ready"],
                }
            ],
        }
        primary_preflight = {
            "candidate_count": 1,
            "live_checked_count": 1,
            "open_eligible_count": 0,
            "uncertain_count": 1,
            "status_counts": {"check_error": 1},
            "checks": [
                {
                    "key": f"url:{url}",
                    "url": url,
                    "status": "check_error",
                    "open_eligible": False,
                    "closed": False,
                    "error": "timed out",
                }
            ],
        }
        retry_preflight = {
            "candidate_count": 1,
            "live_checked_count": 1,
            "open_eligible_count": 1,
            "uncertain_count": 0,
            "status_counts": {"open_live_checked": 1},
            "checks": [
                {
                    "key": f"url:{url}",
                    "url": url,
                    "status": "open_live_checked",
                    "open_eligible": True,
                    "closed": False,
                }
            ],
        }

        report = build_apply_queue_handoff(
            apply_queue,
            primary_preflight,
            supplemental_preflights=[retry_preflight],
        )

        self.assertEqual(report["open_after_answers_count"], 1)
        self.assertEqual(report["manual_live_check_count"], 0)
        self.assertEqual(report["preflight"]["source_report_count"], 2)
        self.assertEqual(report["preflight"]["open_eligible_count"], 1)
        self.assertEqual(report["preflight"]["uncertain_count"], 0)
        self.assertEqual(report["positions"][0]["live_status"], "open_live_checked")

        with tempfile.TemporaryDirectory() as temp_dir:
            queue_path = Path(temp_dir) / "queue.json"
            primary_path = Path(temp_dir) / "primary.json"
            retry_path = Path(temp_dir) / "retry.json"
            queue_path.write_text(json.dumps(apply_queue), encoding="utf-8")
            primary_path.write_text(json.dumps(primary_preflight), encoding="utf-8")
            retry_path.write_text(json.dumps(retry_preflight), encoding="utf-8")
            written = write_apply_queue_handoff(
                queue_path,
                primary_path,
                Path(temp_dir) / "handoff.json",
                Path(temp_dir) / "handoff.md",
                Path(temp_dir) / "handoff.html",
                Path(temp_dir) / "open_ready.json",
                supplemental_preflight_paths=[retry_path],
            )
            self.assertEqual(written["preflight"]["open_eligible_count"], 1)
            self.assertEqual(written["source_paths"]["supplemental_preflights"], [str(retry_path)])

    def test_apply_queue_autofill_packet_builds_deferred_browser_actions(self) -> None:
        profile = CandidateProfile(
            name="Alan Jiang",
            email="alan@example.com",
            phone="555-0100",
            location="Bellevue, WA",
            target_titles=["SRE"],
            target_locations=["United States"],
            remote_ok=True,
            keywords=[],
            blocklist=[],
            min_score=1,
            resume_facts={},
            question_answers={},
        )
        research = {
            "positions": [
                {
                    "position_key": "url:https://jobs.lever.co/example/1",
                    "platform": "Lever",
                    "company": "Example",
                    "title": "SRE",
                    "role_family": "SRE",
                    "apply_url": "https://jobs.lever.co/example/1",
                },
                {
                    "position_key": "url:https://jobs.lever.co/example/2",
                    "platform": "Lever",
                    "company": "Example",
                    "title": "Platform Engineer",
                    "role_family": "Platform",
                    "apply_url": "https://jobs.lever.co/example/2",
                },
            ],
            "items": [
                {
                    "position_key": "url:https://jobs.lever.co/example/1",
                    "label": "Email",
                    "category": "profile_identity",
                    "automation_action": "auto_fill_from_profile",
                    "required": True,
                },
                {
                    "position_key": "url:https://jobs.lever.co/example/1",
                    "label": "Submit application",
                    "category": "final_submit",
                    "automation_action": "submit_gate",
                    "required": True,
                },
                {
                    "position_key": "url:https://jobs.lever.co/example/2",
                    "label": "Email",
                    "category": "profile_identity",
                    "automation_action": "auto_fill_from_profile",
                    "required": True,
                },
                {
                    "position_key": "url:https://jobs.lever.co/example/2",
                    "label": "Submit application",
                    "category": "final_submit",
                    "automation_action": "submit_gate",
                    "required": True,
                },
            ],
        }
        handoff = {
            "status": "waiting_for_confirmed_answers",
            "ready_for_supervised_open_batch": False,
            "open_after_answers_count": 2,
            "manual_live_check_count": 0,
            "closed_or_skipped_count": 0,
            "positions": [
                {
                    "index": 1,
                    "handoff_status": "waiting_for_answers_before_open",
                    "queue_status": "waiting_for_confirmed_answers",
                    "live_status": "open_live_checked",
                    "live_open_eligible": True,
                    "live_closed": False,
                    "position_key": "url:https://jobs.lever.co/example/1",
                    "platform": "Lever",
                    "company": "Example",
                    "title": "SRE",
                    "role_family": "SRE",
                    "apply_url": "https://jobs.lever.co/example/1",
                },
                {
                    "index": 2,
                    "handoff_status": "waiting_for_answers_before_open",
                    "queue_status": "waiting_for_confirmed_answers",
                    "live_status": "open_live_checked",
                    "live_open_eligible": True,
                    "live_closed": False,
                    "position_key": "url:https://jobs.lever.co/example/2",
                    "platform": "Lever",
                    "company": "Example",
                    "title": "Platform Engineer",
                    "role_family": "Platform",
                    "apply_url": "https://jobs.lever.co/example/2",
                },
            ],
        }

        report = build_apply_queue_autofill_packet(
            research,
            handoff,
            profile=profile,
            answer_memory={"version": 1, "answers": []},
            target_count=2,
            limit=2,
        )
        markdown = render_apply_queue_autofill_packet_markdown(report)
        html = render_apply_queue_autofill_packet_html(report)

        self.assertEqual(report["status"], "waiting_for_confirmed_answers")
        self.assertTrue(report["ready_after_confirmed_answers"])
        self.assertFalse(report["ready_for_supervised_browser_autofill"])
        self.assertEqual(report["selected_count"], 2)
        self.assertEqual(report["summary"]["browser_action_count"], 2)
        self.assertEqual(report["summary"]["final_submit_stop_count"], 2)
        self.assertEqual(report["summary"]["selector_miss_count"], 0)
        self.assertEqual(report["summary"]["local_synthetic_submit_count"], 2)
        self.assertEqual(report["packet_status_counts"], {"ready_after_confirmed_answers": 2})
        self.assertIn("confirmed_answers_not_ready", report["global_blockers"])
        self.assertIn("ready_after_confirmed_answers", report["global_blockers"])
        action_text = json.dumps(report["positions"][0]["browser_actions"])
        self.assertNotIn("alan@example.com", action_text)
        self.assertNotIn('"value":', action_text)
        self.assertIn("Apply Queue Autofill Packet", markdown)
        self.assertIn("ready_after_confirmed_answers", html)

    def test_position_execution_audit_summarizes_100_queue_evidence(self) -> None:
        packet = {
            "status": "waiting_for_confirmed_answers",
            "selected_count": 2,
            "ready_after_confirmed_answers": True,
            "ready_for_supervised_browser_autofill": False,
            "summary": {"local_synthetic_submit_count": 2, "selector_miss_count": 0},
            "positions": [
                {
                    "index": 1,
                    "packet_status": "ready_after_confirmed_answers",
                    "handoff_status": "waiting_for_answers_before_open",
                    "queue_status": "waiting_for_confirmed_answers",
                    "live_status": "open_live_checked",
                    "live_open_eligible": True,
                    "position_key": "url:https://jobs.lever.co/example/1",
                    "platform": "Lever",
                    "company": "Example",
                    "title": "SRE",
                    "role_family": "SRE",
                    "apply_url": "https://jobs.lever.co/example/1",
                    "manifest_status": "autofill_ready_with_supervised_gates",
                    "autofill_allowed": True,
                    "browser_action_count": 1,
                    "stop_action_count": 1,
                    "final_submit_stop_count": 1,
                    "manual_gate_count": 1,
                    "local_check_selector_miss_count": 0,
                    "local_synthetic_submit_count": 1,
                    "local_synthetic_submit_selector_miss_count": 0,
                    "real_platform_submission": False,
                    "would_submit": False,
                    "final_submit_allowed": False,
                },
                {
                    "index": 2,
                    "packet_status": "ready_after_confirmed_answers",
                    "handoff_status": "waiting_for_answers_before_open",
                    "queue_status": "waiting_for_confirmed_answers",
                    "live_status": "open_live_checked",
                    "live_open_eligible": True,
                    "position_key": "url:https://jobs.greenhouse.io/example/2",
                    "platform": "Greenhouse",
                    "company": "Example",
                    "title": "Platform Engineer",
                    "role_family": "Platform",
                    "apply_url": "https://jobs.greenhouse.io/example/2",
                    "manifest_status": "autofill_ready_with_supervised_gates",
                    "autofill_allowed": True,
                    "browser_action_count": 1,
                    "stop_action_count": 1,
                    "final_submit_stop_count": 1,
                    "manual_gate_count": 1,
                    "local_check_selector_miss_count": 0,
                    "local_synthetic_submit_count": 1,
                    "local_synthetic_submit_selector_miss_count": 0,
                    "real_platform_submission": False,
                    "would_submit": False,
                    "final_submit_allowed": False,
                },
            ],
        }
        synthetic_packet = {
            "status": "ready_for_supervised_browser_autofill",
            "selected_count": 2,
            "ready_for_supervised_browser_autofill": True,
            "positions": [
                {
                    **packet["positions"][0],
                    "packet_status": "ready_now",
                    "local_synthetic_submit_count": 1,
                },
                {
                    **packet["positions"][1],
                    "packet_status": "ready_now",
                    "local_synthetic_submit_count": 1,
                },
            ],
        }
        platform_playbook = {
            "summary": {
                "observed_position_count": 200,
                "target_platforms_at_100_count": 2,
                "closed_posting_count": 7,
                "final_answer_missing_count": 6,
            },
            "platforms": [
                {"platform": "Lever", "positions_observed": 100, "remaining_answer_inputs": 2},
                {"platform": "Greenhouse", "positions_observed": 100, "remaining_answer_inputs": 6},
            ],
        }
        goal_audit = {
            "status": "needs_user_answers",
            "goal_complete": False,
            "blocker_summary": {"final_answer_waiting_count_after_drafts": 6},
        }

        audit = build_position_execution_audit(
            packet,
            synthetic_autofill_packet=synthetic_packet,
            platform_playbook=platform_playbook,
            goal_readiness_audit=goal_audit,
            target_count=2,
        )

        self.assertEqual(audit["status"], "ready_after_confirmed_answers")
        self.assertEqual(audit["summary"]["position_count"], 2)
        self.assertEqual(audit["summary"]["local_synthetic_submit_position_count"], 2)
        self.assertEqual(audit["summary"]["selector_miss_position_count"], 0)
        self.assertEqual(audit["summary"]["final_submit_stop_position_count"], 2)
        self.assertEqual(audit["summary"]["remaining_user_answer_count"], 6)
        self.assertEqual(audit["summary"]["global_remaining_user_answer_count"], 6)
        self.assertTrue(audit["summary"]["ready_for_supervised_autofill_after_answers"])
        self.assertEqual(
            {
                row["id"]: row["status"]
                for row in audit["requirements"]
            }["confirmed_answer_gate"],
            "needs_user_answers",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet_path = root / "packet.json"
            synthetic_path = root / "synthetic.json"
            playbook_path = root / "playbook.json"
            goal_path = root / "goal.json"
            json_output = root / "audit.json"
            markdown_output = root / "audit.md"
            html_output = root / "audit.html"
            packet_path.write_text(json.dumps(packet), encoding="utf-8")
            synthetic_path.write_text(json.dumps(synthetic_packet), encoding="utf-8")
            playbook_path.write_text(json.dumps(platform_playbook), encoding="utf-8")
            goal_path.write_text(json.dumps(goal_audit), encoding="utf-8")

            written = write_position_execution_audit(
                packet_path,
                synthetic_path,
                playbook_path,
                goal_path,
                json_output,
                markdown_output,
                html_output,
                target_count=2,
            )

            self.assertEqual(written["summary"]["position_count"], 2)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertTrue(html_output.exists())
            self.assertIn("100-Position Execution Audit", markdown_output.read_text(encoding="utf-8"))

    def test_position_execution_audit_marks_filtered_ready_queue_as_ready_now(self) -> None:
        packet = {
            "status": "ready_for_supervised_browser_autofill",
            "selected_count": 2,
            "ready_for_supervised_browser_autofill": True,
            "summary": {"local_synthetic_submit_count": 2, "selector_miss_count": 0},
            "positions": [
                {
                    "index": 1,
                    "packet_status": "ready_now",
                    "handoff_status": "ready_to_open_for_supervised_autofill",
                    "queue_status": "ready_for_live_closed_preflight",
                    "live_status": "open_live_checked",
                    "live_open_eligible": True,
                    "position_key": "url:https://jobs.lever.co/example/1",
                    "platform": "Lever",
                    "company": "Example",
                    "title": "SRE",
                    "role_family": "SRE",
                    "apply_url": "https://jobs.lever.co/example/1",
                    "manifest_status": "autofill_ready_with_supervised_gates",
                    "autofill_allowed": True,
                    "browser_action_count": 1,
                    "stop_action_count": 1,
                    "final_submit_stop_count": 1,
                    "manual_gate_count": 1,
                    "local_check_selector_miss_count": 0,
                    "local_synthetic_submit_count": 1,
                    "local_synthetic_submit_selector_miss_count": 0,
                    "real_platform_submission": False,
                    "would_submit": False,
                    "final_submit_allowed": False,
                },
                {
                    "index": 2,
                    "packet_status": "ready_now",
                    "handoff_status": "ready_to_open_for_supervised_autofill",
                    "queue_status": "ready_for_live_closed_preflight",
                    "live_status": "open_live_checked",
                    "live_open_eligible": True,
                    "position_key": "url:https://jobs.greenhouse.io/example/2",
                    "platform": "Greenhouse",
                    "company": "Example",
                    "title": "Platform Engineer",
                    "role_family": "Platform",
                    "apply_url": "https://jobs.greenhouse.io/example/2",
                    "manifest_status": "autofill_ready_with_supervised_gates",
                    "autofill_allowed": True,
                    "browser_action_count": 1,
                    "stop_action_count": 1,
                    "final_submit_stop_count": 1,
                    "manual_gate_count": 1,
                    "local_check_selector_miss_count": 0,
                    "local_synthetic_submit_count": 1,
                    "local_synthetic_submit_selector_miss_count": 0,
                    "real_platform_submission": False,
                    "would_submit": False,
                    "final_submit_allowed": False,
                },
            ],
        }
        goal_audit = {
            "status": "needs_user_answers",
            "goal_complete": False,
            "blocker_summary": {"final_answer_waiting_count_after_drafts": 6},
        }

        audit = build_position_execution_audit(
            packet,
            platform_playbook={"summary": {"final_answer_missing_count": 6}},
            goal_readiness_audit=goal_audit,
            target_count=2,
        )

        self.assertEqual(audit["status"], "ready_for_supervised_autofill")
        self.assertEqual(audit["summary"]["remaining_user_answer_count"], 0)
        self.assertEqual(audit["summary"]["global_remaining_user_answer_count"], 6)
        self.assertTrue(audit["summary"]["ready_for_supervised_autofill_now"])
        self.assertEqual(
            {
                row["id"]: row["status"]
                for row in audit["requirements"]
            }["confirmed_answer_gate"],
            "achieved",
        )

    def test_apply_queue_autofill_packet_ready_writes_outputs(self) -> None:
        profile_payload = {
            "candidate": {
                "name": "Alan Jiang",
                "email": "alan@example.com",
                "phone": "555-0100",
                "location": "Bellevue, WA",
            },
            "targets": {"titles": ["SRE"], "locations": ["United States"], "remote_ok": True, "min_score": 1},
            "resume_facts": {},
            "question_answers": {},
        }
        research = {
            "positions": [
                {
                    "position_key": "url:https://jobs.lever.co/example/1",
                    "platform": "Lever",
                    "company": "Example",
                    "title": "SRE",
                    "role_family": "SRE",
                    "apply_url": "https://jobs.lever.co/example/1",
                },
                {
                    "position_key": "url:https://jobs.lever.co/example/2",
                    "platform": "Lever",
                    "company": "Example",
                    "title": "SRE II",
                    "role_family": "SRE",
                    "apply_url": "https://jobs.lever.co/example/2",
                },
            ],
            "items": [
                {
                    "position_key": "url:https://jobs.lever.co/example/1",
                    "label": "Email",
                    "category": "profile_identity",
                    "automation_action": "auto_fill_from_profile",
                    "required": True,
                },
                {
                    "position_key": "url:https://jobs.lever.co/example/1",
                    "label": "Submit application",
                    "category": "final_submit",
                    "automation_action": "submit_gate",
                    "required": True,
                },
                {
                    "position_key": "url:https://jobs.lever.co/example/2",
                    "label": "Email",
                    "category": "profile_identity",
                    "automation_action": "auto_fill_from_profile",
                    "required": True,
                },
                {
                    "position_key": "url:https://jobs.lever.co/example/2",
                    "label": "Submit application",
                    "category": "final_submit",
                    "automation_action": "submit_gate",
                    "required": True,
                },
            ],
        }
        handoff = {
            "status": "ready_to_open_for_supervised_autofill",
            "ready_for_supervised_open_batch": True,
            "open_after_answers_count": 0,
            "manual_live_check_count": 0,
            "closed_or_skipped_count": 0,
            "positions": [
                {
                    "index": 1,
                    "handoff_status": "ready_to_open_for_supervised_autofill",
                    "queue_status": "ready_for_live_closed_preflight",
                    "live_status": "open_live_checked",
                    "live_open_eligible": True,
                    "live_closed": False,
                    "position_key": "url:https://jobs.lever.co/example/1",
                    "platform": "Lever",
                    "company": "Example",
                    "title": "SRE",
                    "role_family": "SRE",
                    "apply_url": "https://jobs.lever.co/example/1",
                },
                {
                    "index": 2,
                    "handoff_status": "ready_to_open_for_supervised_autofill",
                    "queue_status": "ready_for_live_closed_preflight",
                    "live_status": "open_live_checked",
                    "live_open_eligible": True,
                    "live_closed": False,
                    "position_key": "url:https://jobs.lever.co/example/2",
                    "platform": "Lever",
                    "company": "Example",
                    "title": "SRE II",
                    "role_family": "SRE",
                    "apply_url": "https://jobs.lever.co/example/2",
                },
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            research_path = Path(temp_dir) / "research.json"
            handoff_path = Path(temp_dir) / "handoff.json"
            profile_path = Path(temp_dir) / "profile.json"
            memory_path = Path(temp_dir) / "memory.json"
            closed_path = Path(temp_dir) / "closed.json"
            json_output = Path(temp_dir) / "packet.json"
            markdown_output = Path(temp_dir) / "packet.md"
            html_output = Path(temp_dir) / "packet.html"
            research_path.write_text(json.dumps(research), encoding="utf-8")
            handoff_path.write_text(json.dumps(handoff), encoding="utf-8")
            profile_path.write_text(json.dumps(profile_payload), encoding="utf-8")
            memory_path.write_text(json.dumps({"version": 1, "answers": []}), encoding="utf-8")
            closed_path.write_text(json.dumps({"version": 1, "jobs": []}), encoding="utf-8")

            written = write_apply_queue_autofill_packet(
                research_path,
                handoff_path,
                profile_path,
                memory_path,
                closed_path,
                json_output,
                markdown_output,
                html_output,
                target_count=2,
                limit=2,
            )

            self.assertEqual(written["status"], "ready_for_supervised_browser_autofill")
            self.assertTrue(written["ready_for_supervised_browser_autofill"])
            self.assertEqual(written["summary"]["local_synthetic_submit_count"], 2)
            self.assertEqual(written["global_blockers"], [])
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertTrue(html_output.exists())

    def test_collection_plan_turns_coverage_shortfalls_into_search_tasks(self) -> None:
        gate = {
            "position_target": 100,
            "ready_for_full_automation": False,
            "real_platform_role_target_achieved": False,
            "synthetic": {"platform_role_target_achieved": True},
            "next_collection_targets": [
                {
                    "platform": "Ashby",
                    "role_family": "Cloud DevOps",
                    "positions_observed": 0,
                    "positions_remaining": 100,
                },
                {
                    "platform": "LinkedIn",
                    "role_family": "Site Reliability",
                    "positions_observed": 7,
                    "positions_remaining": 93,
                },
            ],
        }

        plan = build_collection_plan_from_coverage_gate(gate, max_targets=1, batch_size=25)

        self.assertEqual(plan["task_count"], 1)
        task = plan["tasks"][0]
        self.assertEqual(task["platform"], "Ashby")
        self.assertEqual(task["suggested_batch_size"], 25)
        self.assertIn("cloud devops", task["query"])
        self.assertIn("devops engineer", task["query_variants"])
        self.assertIn("cloud platform engineer", task["query_variants"])
        self.assertIn("infrastructure engineer aws kubernetes terraform", task["query_variants"])
        self.assertGreater(len(task["search_urls"]), 2)
        self.assertTrue(any("jobs.ashbyhq.com" in url for url in task["search_urls"]))
        markdown = render_collection_plan_markdown(plan)
        self.assertIn("Collection Plan", markdown)
        self.assertIn("variants:", markdown)
        self.assertIn("import-candidates", markdown)

        sre_plan = build_collection_plan_from_coverage_gate(
            {
                "next_collection_targets": [
                    {
                        "platform": "Lever",
                        "role_family": "Site Reliability",
                        "positions_observed": 0,
                        "positions_remaining": 100,
                    }
                ],
                "synthetic": {"platform_role_target_achieved": True},
            },
            max_targets=1,
            batch_size=25,
        )
        self.assertIn("database reliability engineer", sre_plan["tasks"][0]["query_variants"])
        self.assertIn("devops sre engineer", sre_plan["tasks"][0]["query_variants"])

    def test_write_collection_plan_outputs_reports(self) -> None:
        gate = {
            "next_collection_targets": [
                {
                    "platform": "Lever",
                    "role_family": "Software Backend",
                    "positions_observed": 0,
                    "positions_remaining": 100,
                }
            ],
            "synthetic": {"platform_role_target_achieved": True},
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            json_output = Path(temp_dir) / "collection.json"
            markdown_output = Path(temp_dir) / "collection.md"

            plan = write_collection_plan(gate, json_output, markdown_output)

            self.assertEqual(plan["task_count"], 1)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())

    def test_discover_candidates_from_collection_plan_extracts_ats_urls(self) -> None:
        plan = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "tasks": [
                {
                    "platform": "Ashby",
                    "role_family": "Site Reliability",
                    "query": "site reliability engineer",
                    "search_urls": ["https://search.example/ashby"],
                },
                {
                    "platform": "Lever",
                    "role_family": "Software Backend",
                    "query": "backend software engineer",
                    "search_urls": ["https://search.example/lever"],
                },
            ],
        }

        def fake_fetcher(url: str, timeout: float) -> str:
            if "ashby" in url:
                return """
                <html>
                  <a href="https://jobs.ashbyhq.com/example/abc?src=LinkedIn">
                    Site Reliability Engineer at Example
                  </a>
                  <a href="/url?q=https%3A%2F%2Fjobs.ashbyhq.com%2Fexample%2Fabc%3Futm%3Dx">
                    Duplicate
                  </a>
                  <a href="https://jobs.ashbyhq.com/example/not-sre">
                    Software Engineer, AI Platform at Example
                  </a>
                  <a href="https://example.com/not-a-job">Ignore</a>
                </html>
                """
            return """
            <html>
              <a href="https://jobs.lever.co/acme/123?lever-source=search">
                Backend Software Engineer - Acme
              </a>
            </html>
            """

        report = discover_candidates_from_collection_plan(
            plan,
            max_tasks=2,
            per_task_limit=5,
            search_pages_per_task=1,
            fetcher=fake_fetcher,
        )

        self.assertEqual(report["candidate_count"], 2)
        self.assertEqual(report["per_platform_counts"]["Ashby"], 1)
        self.assertEqual(report["per_platform_counts"]["Lever"], 1)
        self.assertEqual(
            report["candidates"][0]["apply_url"],
            "https://jobs.ashbyhq.com/example/abc",
        )
        self.assertEqual(report["candidates"][0]["role_family"], "Site Reliability")
        self.assertIn("observe-candidates", report["next_command"])
        markdown = render_candidate_discovery_markdown(report)
        self.assertIn("Candidate Discovery Report", markdown)
        self.assertIn("https://jobs.lever.co/acme/123", markdown)

    def test_discover_candidates_uses_linkedin_guest_search_pages(self) -> None:
        plan = {
            "tasks": [
                {
                    "platform": "LinkedIn",
                    "role_family": "Site Reliability",
                    "query": "site reliability engineer",
                    "query_variants": ["site reliability engineer"],
                }
            ]
        }
        fetched_urls: list[str] = []

        def fake_fetcher(url: str, timeout: float) -> str:
            fetched_urls.append(url)
            self.assertIn("jobs-guest/jobs/api/seeMoreJobPostings/search", url)
            return """
            <li>
              <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/site-reliability-engineer-at-example-4410000001?position=1">
                <span class="sr-only">Site Reliability Engineer</span>
              </a>
            </li>
            """

        report = discover_candidates_from_collection_plan(
            plan,
            max_tasks=1,
            per_task_limit=5,
            search_pages_per_task=1,
            fetcher=fake_fetcher,
        )

        self.assertEqual(len(fetched_urls), 1)
        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["candidates"][0]["apply_url"], "https://www.linkedin.com/jobs/view/4410000001/")
        self.assertEqual(report["candidates"][0]["role_family"], "Site Reliability")

    def test_discover_candidates_stops_search_pages_after_rate_limit(self) -> None:
        plan = {
            "tasks": [
                {
                    "platform": "Lever",
                    "role_family": "Site Reliability",
                    "query": "site reliability engineer",
                    "search_urls": [
                        "https://search.example/one",
                        "https://search.example/two",
                        "https://search.example/three",
                    ],
                }
            ]
        }
        fetched_urls: list[str] = []

        def fake_fetcher(url: str, timeout: float) -> str:
            fetched_urls.append(url)
            raise Exception("HTTP Error 429: Too Many Requests")

        report = discover_candidates_from_collection_plan(
            plan,
            max_tasks=1,
            per_task_limit=5,
            search_pages_per_task=3,
            fetcher=fake_fetcher,
            max_rate_limit_errors_per_task=2,
        )

        self.assertEqual(len(fetched_urls), 2)
        self.assertEqual(report["search_page_count"], 2)
        self.assertEqual(report["rate_limited_task_count"], 1)
        self.assertEqual(report["candidate_count"], 0)
        self.assertIn("Rate-limited tasks: 1", render_candidate_discovery_markdown(report))

    def test_discover_candidates_expands_seed_ats_boards(self) -> None:
        plan = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "tasks": [
                {
                    "platform": "Greenhouse",
                    "role_family": "Site Reliability",
                    "query": "site reliability engineer",
                },
                {
                    "platform": "Lever",
                    "role_family": "Software Backend",
                    "query": "backend software engineer",
                },
                {
                    "platform": "Ashby",
                    "role_family": "Platform Infrastructure",
                    "query": "platform engineer infrastructure",
                },
            ],
        }
        seed_candidates = [
            {"platform": "Greenhouse", "apply_url": "https://job-boards.greenhouse.io/example/jobs/1"},
            {"platform": "Lever", "apply_url": "https://jobs.lever.co/acme/2"},
            {"platform": "Ashby", "apply_url": "https://jobs.ashbyhq.com/ashco/3"},
        ]

        def fake_fetcher(url: str, timeout: float) -> str:
            if "boards-api.greenhouse.io" in url:
                return json.dumps(
                    {
                        "jobs": [
                            {
                                "absolute_url": "https://job-boards.greenhouse.io/example/jobs/10",
                                "title": "Site Reliability Engineer",
                                "company_name": "Example",
                                "location": {"name": "Remote"},
                                "content": "<p>Kubernetes production reliability</p>",
                            },
                            {
                                "absolute_url": "https://job-boards.greenhouse.io/example/jobs/11",
                                "title": "Product Manager",
                                "company_name": "Example",
                            },
                        ]
                    }
                )
            if "api.lever.co" in url:
                return json.dumps(
                    [
                        {
                            "hostedUrl": "https://jobs.lever.co/acme/20",
                            "text": "Backend Software Engineer",
                            "categories": {"location": "New York, NY"},
                            "descriptionPlain": "APIs and distributed systems",
                        },
                        {
                            "hostedUrl": "https://jobs.lever.co/acme/21",
                            "text": "Customer Success Manager",
                        },
                    ]
                )
            return """
            <html><script>
              window.__appData = {
                "organization": {"name": "AshCo"},
                "jobBoard": {"jobPostings": [
                  {
                    "id": "30",
                    "title": "Platform Engineer, Kubernetes",
                    "locationName": "Seattle, WA",
                    "departmentName": "Engineering",
                    "isListed": true
                  },
                  {
                    "id": "31",
                    "title": "Sales Lead",
                    "locationName": "Remote",
                    "isListed": true
                  }
                ]}
              };
            </script></html>
            """

        report = discover_candidates_from_collection_plan(
            plan,
            max_tasks=3,
            per_task_limit=10,
            search_pages_per_task=0,
            seed_candidates=seed_candidates,
            board_fetch_limit=3,
            fetcher=fake_fetcher,
        )

        self.assertEqual(report["board_fetch_count"], 3)
        self.assertEqual(report["board_candidate_count"], 3)
        self.assertEqual(report["candidate_count"], 3)
        urls = {candidate["apply_url"] for candidate in report["candidates"]}
        self.assertIn("https://job-boards.greenhouse.io/example/jobs/10", urls)
        self.assertIn("https://jobs.lever.co/acme/20", urls)
        self.assertIn("https://jobs.ashbyhq.com/ashco/30", urls)
        self.assertEqual(report["per_platform_counts"]["Greenhouse"], 1)
        markdown = render_candidate_discovery_markdown(report)
        self.assertIn("ATS boards fetched: 3", markdown)

    def test_discover_candidates_keeps_matching_direct_seed_jobs(self) -> None:
        plan = {
            "tasks": [
                {
                    "platform": "Lever",
                    "role_family": "Site Reliability",
                    "query": "site reliability engineer",
                }
            ]
        }
        seed_candidates = [
            {
                "platform": "Lever",
                "company": "Example",
                "title": "Site Reliability Engineer",
                "apply_url": "https://jobs.lever.co/example/123",
                "role_family": "Site Reliability",
            },
            {
                "platform": "Lever",
                "company": "Example",
                "title": "Product Manager",
                "apply_url": "https://jobs.lever.co/example/456",
                "role_family": "Other",
            },
        ]

        report = discover_candidates_from_collection_plan(
            plan,
            max_tasks=1,
            per_task_limit=5,
            search_pages_per_task=0,
            seed_candidates=seed_candidates,
            board_fetch_limit=0,
        )

        self.assertEqual(report["direct_seed_candidate_count"], 1)
        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["candidates"][0]["apply_url"], "https://jobs.lever.co/example/123")
        self.assertEqual(report["candidates"][0]["source"], "direct_seed_candidate")
        self.assertIn("Direct seed candidates: 1", render_candidate_discovery_markdown(report))

    def test_discover_candidates_rejects_board_titles_without_role_context(self) -> None:
        plan = {
            "tasks": [
                {
                    "platform": "Lever",
                    "role_family": "Cloud DevOps",
                    "query": "cloud devops engineer",
                }
            ]
        }
        seed_candidates = [
            {"platform": "Lever", "apply_url": "https://jobs.lever.co/theodo/seed"}
        ]

        def fake_fetcher(url: str, timeout: float) -> str:
            return json.dumps(
                [
                    {
                        "hostedUrl": "https://jobs.lever.co/theodo/cloud",
                        "text": "Cloud Engineer",
                        "descriptionPlain": "Own cloud infrastructure and Kubernetes automation.",
                    },
                    {
                        "hostedUrl": "https://jobs.lever.co/theodo/manager",
                        "text": "Engineering Manager - Theodo Cloud",
                        "descriptionPlain": "Cloud infrastructure delivery leadership.",
                    },
                    {
                        "hostedUrl": "https://jobs.lever.co/theodo/recruiter",
                        "text": "Business Developer & Tech Recruiter",
                        "descriptionPlain": "DevOps and cloud hiring for consulting teams.",
                    },
                    {
                        "hostedUrl": "https://jobs.lever.co/theodo/fullstack",
                        "text": "Full Stack Engineer",
                        "descriptionPlain": "Cloud platform delivery for customers.",
                    },
                    {
                        "hostedUrl": "https://jobs.lever.co/theodo/product-owner",
                        "text": "Product Owner - Platform",
                        "descriptionPlain": "Own cloud platform roadmap.",
                    },
                    {
                        "hostedUrl": "https://jobs.lever.co/theodo/director",
                        "text": "Director Engineering, Platform Services",
                        "descriptionPlain": "Lead cloud platform engineering teams.",
                    },
                    {
                        "hostedUrl": "https://jobs.lever.co/theodo/sdet",
                        "text": "Senior SDET, Secrets Management Platform",
                        "descriptionPlain": "Test platform infrastructure features.",
                    },
                ]
            )

        report = discover_candidates_from_collection_plan(
            plan,
            max_tasks=1,
            per_task_limit=10,
            search_pages_per_task=0,
            seed_candidates=seed_candidates,
            board_fetch_limit=1,
            fetcher=fake_fetcher,
        )

        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["candidates"][0]["title"], "Cloud Engineer")

    def test_write_candidate_discovery_report_outputs_files(self) -> None:
        plan = {
            "tasks": [
                {
                    "platform": "Greenhouse",
                    "role_family": "Cloud DevOps",
                    "query": "cloud devops engineer",
                    "search_urls": ["https://search.example/greenhouse"],
                }
            ]
        }

        def fake_fetcher(url: str, timeout: float) -> str:
            return """
            <html>
              <a href="https://job-boards.greenhouse.io/example/jobs/123?gh_src=x">
                Cloud DevOps Engineer - Example
              </a>
            </html>
            """

        with tempfile.TemporaryDirectory() as temp_dir:
            json_output = Path(temp_dir) / "discovered.json"
            markdown_output = Path(temp_dir) / "discovered.md"
            report = write_candidate_discovery_report(
                plan,
                json_output,
                markdown_output,
                fetcher=fake_fetcher,
            )
            self.assertEqual(report["candidate_count"], 1)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertEqual(
                report["candidates"][0]["apply_url"],
                "https://job-boards.greenhouse.io/example/jobs/123",
            )

    def test_select_candidate_topup_prioritizes_coverage_shortfalls(self) -> None:
        observed = [
            {
                "platform": "Lever",
                "title": "DevOps Engineer",
                "apply_url": "https://jobs.lever.co/example/observed",
            }
        ]
        closed = {
            "jobs": [
                {
                    "key": "url:https://jobs.ashbyhq.com/example/closed",
                    "status": "CLOSED",
                    "reason": "HTTP 404 Not Found",
                }
            ]
        }
        candidates = [
            {
                "platform": "Lever",
                "title": "DevOps Engineer",
                "role_family": "Cloud DevOps",
                "apply_url": "https://jobs.lever.co/example/observed",
            },
            {
                "platform": "Lever",
                "title": "Senior DevOps Engineer",
                "role_family": "Cloud DevOps",
                "apply_url": "https://jobs.lever.co/example/devops-1",
            },
            {
                "platform": "Lever",
                "title": "Cloud Infrastructure Engineer",
                "role_family": "Cloud DevOps",
                "apply_url": "https://jobs.lever.co/example/devops-2",
            },
            {
                "platform": "Ashby",
                "title": "Site Reliability Engineer",
                "role_family": "Site Reliability",
                "apply_url": "https://jobs.ashbyhq.com/example/sre",
            },
            {
                "platform": "Ashby",
                "title": "Backend Engineer",
                "role_family": "Software Backend",
                "apply_url": "https://jobs.ashbyhq.com/example/backend",
            },
            {
                "platform": "Ashby",
                "title": "Closed SRE",
                "role_family": "Site Reliability",
                "apply_url": "https://jobs.ashbyhq.com/example/closed",
            },
        ]
        gate = {
            "real_platform_role_shortfalls": {
                "Lever::Cloud DevOps": 98,
                "Ashby::Site Reliability": 87,
            }
        }

        report = select_candidate_topup(
            candidates,
            gate,
            observed_candidates=observed,
            closed_jobs=closed,
            limit=3,
            per_pair_limit=2,
        )

        self.assertEqual(report["selected_count"], 3)
        self.assertEqual(report["per_pair_counts"]["Lever::Cloud DevOps"], 2)
        self.assertEqual(report["per_pair_counts"]["Ashby::Site Reliability"], 1)
        urls = {candidate["apply_url"] for candidate in report["candidates"]}
        self.assertNotIn("https://jobs.lever.co/example/observed", urls)
        self.assertNotIn("https://jobs.ashbyhq.com/example/backend", urls)
        self.assertNotIn("https://jobs.ashbyhq.com/example/closed", urls)

        with tempfile.TemporaryDirectory() as temp_dir:
            json_output = Path(temp_dir) / "topup.json"
            markdown_output = Path(temp_dir) / "topup.md"
            written = write_candidate_topup_selection_report(
                candidates,
                gate,
                observed,
                closed,
                json_output,
                markdown_output,
                limit=3,
                per_pair_limit=2,
            )

            self.assertEqual(written["selected_count"], 3)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertIn("Candidate Top-Up Selection", markdown_output.read_text())

    def test_import_candidate_observations_adds_research_positions(self) -> None:
        candidates = [
            {
                "company": "Example",
                "title": "Backend Software Engineer",
                "apply_url": "https://jobs.lever.co/example/abc?utm_source=x",
                "location": "Remote",
            },
            {
                "company": "Example",
                "title": "Backend Software Engineer",
                "apply_url": "https://jobs.lever.co/example/abc?utm_source=x",
                "location": "Remote",
            },
            {
                "company": "NoUrl",
                "title": "Site Reliability Engineer",
            },
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "candidates.json"
            output_path = Path(temp_dir) / "observed_candidates.jsonl"
            input_path.write_text(json.dumps({"candidates": candidates}), encoding="utf-8")

            result = import_candidate_observations(input_path, output_path, source="test")
            research = build_application_research(temp_dir, position_target=100)

            self.assertEqual(result["candidate_count"], 3)
            self.assertEqual(result["imported_count"], 1)
            self.assertEqual(result["skipped_count"], 2)
            self.assertEqual(research["positions_observed_total"], 1)
            self.assertEqual(research["platforms"]["Lever"]["positions_observed"], 1)
            self.assertIn("Lever::Software Backend", research["coverage_groups"])

    def test_application_research_uses_observed_role_family_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stale_json = Path(temp_dir) / "stale_candidate.json"
            observed_jsonl = Path(temp_dir) / "observed_candidates.jsonl"
            stale_json.write_text(
                json.dumps(
                    {
                        "jobs": [
                            {
                                "platform": "Greenhouse",
                                "company": "Example",
                                "title": "Engineer II",
                                "apply_url": "https://job-boards.greenhouse.io/example/jobs/123",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            observed_jsonl.write_text(
                json.dumps(
                    {
                        "status": "OBSERVED_CANDIDATE",
                        "platform": "Greenhouse",
                        "company": "Example",
                        "title": "Engineer II",
                        "role_family": "Platform Infrastructure",
                        "description": "Own Kubernetes platform infrastructure for production services.",
                        "apply_url": "https://job-boards.greenhouse.io/example/jobs/123",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            research = build_application_research(temp_dir, position_target=100)

            self.assertEqual(research["positions_observed_total"], 1)
            self.assertIn("Greenhouse::Platform Infrastructure", research["coverage_groups"])
            self.assertNotIn("Greenhouse::Other", research["coverage_groups"])

    def test_devops_role_family_beats_platform_description_terms(self) -> None:
        candidates = [
            {
                "company": "Example",
                "title": "Senior DevOps Engineer",
                "apply_url": "https://jobs.lever.co/example/devops",
                "description": "Own cloud infrastructure, platform reliability, Kubernetes, and CI/CD.",
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "candidates.json"
            output_path = Path(temp_dir) / "observed_candidates.jsonl"
            input_path.write_text(json.dumps({"candidates": candidates}), encoding="utf-8")

            import_candidate_observations(input_path, output_path, source="test")
            rows = load_candidate_rows(output_path)

            self.assertEqual(rows[0]["role_family"], "Cloud DevOps")

    def test_role_family_infers_common_collection_query_variants(self) -> None:
        candidates = [
            {
                "company": "Example",
                "title": "Observability Engineer",
                "apply_url": "https://jobs.ashbyhq.com/example/observability",
            },
            {
                "company": "Example",
                "title": "Build & Release Engineer",
                "apply_url": "https://jobs.lever.co/example/build-release",
            },
            {
                "company": "Example",
                "title": "Senior Back-End Developer",
                "apply_url": "https://job-boards.greenhouse.io/example/jobs/456",
            },
            {
                "company": "Example",
                "title": "GitOps Engineer",
                "apply_url": "https://jobs.lever.co/example/gitops",
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "candidates.json"
            output_path = Path(temp_dir) / "observed_candidates.jsonl"
            input_path.write_text(json.dumps({"candidates": candidates}), encoding="utf-8")

            import_candidate_observations(input_path, output_path, source="test")
            rows = load_candidate_rows(output_path)

            self.assertEqual(rows[0]["role_family"], "Site Reliability")
            self.assertEqual(rows[1]["role_family"], "Platform Infrastructure")
            self.assertEqual(rows[2]["role_family"], "Software Backend")
            self.assertEqual(rows[3]["role_family"], "Cloud DevOps")

    def test_application_research_ignores_closed_job_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            closed_registry = {
                "version": 1,
                "jobs": [
                    {
                        "key": "linkedin:4415508499",
                        "status": "CLOSED",
                        "reason": "No longer accepting applications",
                        "platform": "LinkedIn",
                        "job_id": "4415508499",
                        "company": "ClosedCo",
                        "title": "Site Reliability Engineer",
                        "short_apply_url": "https://www.linkedin.com/jobs/view/4415508499/",
                    }
                ],
            }
            (Path(temp_dir) / "closed_jobs.json").write_text(
                json.dumps(closed_registry),
                encoding="utf-8",
            )

            research = build_application_research(temp_dir, position_target=100)

            self.assertEqual(research["positions_observed_total"], 0)
            self.assertNotIn("LinkedIn", research["platforms"])

    def test_application_research_revalidates_stale_role_family_labels(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            observed_path = Path(temp_dir) / "observed_candidates.jsonl"
            rows = [
                {
                    "status": "OBSERVED_CANDIDATE",
                    "platform": "Lever",
                    "company": "Example",
                    "title": "Engineering Manager - Theodo Cloud",
                    "description": "Cloud infrastructure delivery leadership.",
                    "role_family": "Cloud DevOps",
                    "apply_url": "https://jobs.lever.co/example/manager",
                },
                {
                    "status": "OBSERVED_CANDIDATE",
                    "platform": "Lever",
                    "company": "Example",
                    "title": "Senior DevOps Engineer",
                    "role_family": "Cloud DevOps",
                    "apply_url": "https://jobs.lever.co/example/devops",
                },
                {
                    "status": "OBSERVED_CANDIDATE",
                    "platform": "Lever",
                    "company": "Example",
                    "title": "Product Owner - Platform",
                    "description": "Own cloud platform roadmap.",
                    "role_family": "Platform Infrastructure",
                    "apply_url": "https://jobs.lever.co/example/product-owner",
                },
            ]
            observed_path.write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )

            research = build_application_research(temp_dir, position_target=100)

            self.assertEqual(research["positions_observed_total"], 3)
            self.assertEqual(research["role_family_counts"].get("Cloud DevOps"), 1)
            self.assertEqual(research["role_family_counts"].get("Other"), 2)

    def test_application_research_infers_standard_linkedin_prompts_when_guest_page_has_none(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            observed_path = Path(temp_dir) / "observed_candidates.jsonl"
            observed_path.write_text(
                json.dumps(
                    {
                        "status": "OBSERVED_CANDIDATE",
                        "platform": "LinkedIn",
                        "company": "Example",
                        "title": "Platform Engineer",
                        "role_family": "Platform Infrastructure",
                        "apply_url": "https://www.linkedin.com/jobs/view/4410000001/",
                        "questions": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            research = build_application_research(temp_dir, position_target=100)

            self.assertEqual(research["positions_observed_total"], 1)
            self.assertEqual(len(research["items"]), len(DEFAULT_QUESTIONS))
            self.assertTrue(
                all(item["item_type"] == "inferred_question" for item in research["items"])
            )
            self.assertEqual(
                {item["source_file"] for item in research["items"]},
                {"linkedin_standard_prompt_inference"},
            )
            self.assertIn("LinkedIn::Platform Infrastructure", research["coverage_groups"])

    def test_extract_live_job_page_metadata_finds_prompts(self) -> None:
        page = """
        <html>
          <head>
            <meta property="og:title" content="Backend Software Engineer">
            <meta property="og:site_name" content="ExampleCo">
            <meta name="description" content="Build reliable APIs.">
          </head>
          <body>
            <label>First Name *</label>
            <input aria-label="Email" />
            <div>Are you legally authorized to work in the United States?</div>
            <button>Submit Application</button>
          </body>
        </html>
        """

        metadata = extract_live_job_page_metadata(page)
        prompts = extract_application_prompts_from_html(page)

        self.assertEqual(metadata["title"], "Backend Software Engineer")
        self.assertEqual(metadata["company"], "ExampleCo")
        self.assertIn("First Name", prompts)
        self.assertIn("Email", prompts)
        self.assertIn("Are you legally authorized to work in the United States?", prompts)

    def test_extract_live_job_page_metadata_can_skip_listing_page_form_noise(self) -> None:
        page = """
        <html>
          <body>
            <label>Email or phone</label>
            <input name="session_password" aria-label="Password">
            <input name="keywords" aria-label="Search job titles or companies">
            <div>Am I a good fit for this job?</div>
            <a>Forgot password?</a>
          </body>
        </html>
        """

        metadata = extract_live_job_page_metadata(page, include_form_fields=False)

        self.assertEqual(metadata["questions"], [])

    def test_extract_live_job_page_metadata_finds_linkedin_company(self) -> None:
        page = """
        <html>
          <head>
            <title>Revel hiring Software Engineer - Infrastructure &amp; Deployment in Los Angeles, CA | LinkedIn</title>
            <meta name="twitter:site" content="@LinkedIn">
            <meta name="description" content="Posted 8:06:10 PM. About Revel...">
          </head>
          <body>Revel hiring Software Engineer - Infrastructure & Deployment in Los Angeles, CA</body>
        </html>
        """

        metadata = extract_live_job_page_metadata(page, include_form_fields=False)

        self.assertEqual(metadata["company"], "Revel")

    def test_extract_live_job_page_metadata_reads_ashby_app_data_fields(self) -> None:
        page = """
        <html>
          <head><title>Platform Engineer @ Omnea</title></head>
          <body>
            You need to enable JavaScript to run this app.
            <div>Who else works at Ashby?</div>
          </body>
          <script>
            window.__appData = {
              "posting": {
                "applicationForm": {
                  "fieldEntries": [
                    {
                      "field": {
                        "title": "How many years of paid experience do you have?",
                        "type": "ValueSelect"
                      },
                      "isRequired": true
                    },
                    {
                      "field": {
                        "title": "Please outline your compensation expectations in GBP",
                        "type": "String"
                      }
                    }
                  ],
                  "sections": [
                    {
                      "fieldEntries": [
                        {
                          "field": {
                            "title": "Do you require a visa or work permit?",
                            "type": "ValueSelect"
                          }
                        }
                      ]
                    }
                  ]
                },
                "surveyForms": [
                  {
                    "fieldEntries": [
                      {
                        "field": {
                          "title": "",
                          "humanReadablePath": "Future Contact Consent",
                          "type": "MultiValueSelect"
                        },
                        "descriptionHtml": "<p>Do you agree to allow Omnea to contact you about job opportunities?</p>"
                      }
                    ]
                  }
                ]
              }
            };
          </script>
        </html>
        """

        metadata = extract_live_job_page_metadata(page, include_form_fields=False)

        self.assertIn("How many years of paid experience do you have?", metadata["questions"])
        self.assertIn("Please outline your compensation expectations in GBP", metadata["questions"])
        self.assertIn("Do you require a visa or work permit?", metadata["questions"])
        self.assertIn(
            "Do you agree to allow Omnea to contact you about job opportunities?",
            metadata["questions"],
        )
        self.assertNotIn("Who else works at Ashby?", metadata["questions"])

    def test_extract_application_prompts_skips_job_board_navigation_noise(self) -> None:
        page = """
        <html>
          <body>
            <button>Toggle flyout</button>
            <button>Go to page 2</button>
            <label>department filter</label>
            <label>question 52718138</label>
            <label>end month 0</label>
            <label>4007244008</label>
            <label>OpenStack</label>
            <label>Ubuntu Server</label>
            <label>K8s</label>
            <label>Ready to apply?</label>
            <label>Most Recent Employer</label>
            <div>Share your hands-on experience with observability tools?</div>
          </body>
        </html>
        """

        prompts = extract_application_prompts_from_html(page)

        self.assertNotIn("Toggle flyout", prompts)
        self.assertNotIn("Go to page 2", prompts)
        self.assertNotIn("department filter", prompts)
        self.assertNotIn("question 52718138", prompts)
        self.assertNotIn("end month 0", prompts)
        self.assertNotIn("4007244008", prompts)
        self.assertNotIn("OpenStack", prompts)
        self.assertNotIn("Ubuntu Server", prompts)
        self.assertNotIn("K8s", prompts)
        self.assertNotIn("Ready to apply?", prompts)
        self.assertIn("Most Recent Employer", prompts)
        self.assertIn("Share your hands-on experience with observability tools?", prompts)

    def test_observe_candidate_pages_records_closed_and_imports_open_questions(self) -> None:
        candidates = [
            {
                "platform": "LinkedIn",
                "job_id": "4415508499",
                "company": "ClosedCo",
                "title": "SRE",
                "apply_url": "https://www.linkedin.com/jobs/view/4415508499/?trk=search",
            },
            {
                "platform": "Greenhouse",
                "company": "OpenCo",
                "title": "Backend Software Engineer",
                "apply_url": "https://job-boards.greenhouse.io/openco/jobs/123?src=LinkedIn",
            },
        ]

        def fake_fetcher(url: str, timeout: float) -> str:
            if "4415508499" in url:
                return "<html>No longer accepting applications</html>"
            return """
            <html>
              <head><meta property="og:site_name" content="OpenCo"></head>
              <body>
                <label>LinkedIn Profile</label>
                <div>Will you now or in the future require visa sponsorship?</div>
                <button>Submit application</button>
              </body>
            </html>
            """

        with tempfile.TemporaryDirectory() as temp_dir:
            observed_output = Path(temp_dir) / "observed_candidates.jsonl"
            closed_path = Path(temp_dir) / "closed_jobs.json"

            report = observe_candidate_pages(
                candidates,
                observed_output,
                closed_path,
                fetcher=fake_fetcher,
                max_checks=5,
                source="test_observation",
            )
            research = build_application_research(temp_dir, position_target=100)

            self.assertEqual(report["live_checked_count"], 2)
            self.assertEqual(report["closed_count"], 1)
            self.assertEqual(report["observed_count"], 1)
            self.assertEqual(report["status_counts"]["closed_live_text"], 1)
            self.assertEqual(report["status_counts"]["observed_open"], 1)
            self.assertTrue(is_job_closed(candidates[0], load_closed_jobs(closed_path)))
            observed_rows = load_candidate_rows(observed_output)
            self.assertEqual(len(observed_rows), 1)
            self.assertEqual(observed_rows[0]["status"], "OBSERVED_CANDIDATE")
            self.assertIn("LinkedIn Profile", observed_rows[0]["questions"])
            self.assertEqual(research["positions_observed_total"], 1)
            self.assertIn("Greenhouse::Software Backend", research["coverage_groups"])
            markdown = render_candidate_observation_markdown(report)
            self.assertIn("Candidate Observation Report", markdown)
            self.assertIn("observed_open", markdown)

    def test_observe_candidate_pages_can_refresh_existing_observations(self) -> None:
        candidates = [
            {
                "company": "Example",
                "title": "Platform Engineer",
                "platform": "Ashby",
                "apply_url": "https://jobs.ashbyhq.com/example/abc",
            }
        ]

        def fake_fetcher(url: str, timeout: float) -> str:
            return "<html><label>LinkedIn Profile URL</label></html>"

        with tempfile.TemporaryDirectory() as temp_dir:
            observed_output = Path(temp_dir) / "observed_candidates.jsonl"
            closed_path = Path(temp_dir) / "closed_jobs.json"

            first = observe_candidate_pages(
                candidates,
                observed_output,
                closed_path,
                fetcher=fake_fetcher,
                max_checks=1,
            )
            duplicate = observe_candidate_pages(
                candidates,
                observed_output,
                closed_path,
                fetcher=fake_fetcher,
                max_checks=1,
            )
            refreshed = observe_candidate_pages(
                candidates,
                observed_output,
                closed_path,
                fetcher=fake_fetcher,
                max_checks=1,
                refresh_existing=True,
            )

            self.assertEqual(first["observed_count"], 1)
            self.assertEqual(duplicate["observed_count"], 0)
            self.assertEqual(duplicate["status_counts"]["duplicate_observation"], 1)
            self.assertEqual(refreshed["observed_count"], 1)
            self.assertEqual(len(load_candidate_rows(observed_output)), 2)

    def test_observe_candidate_pages_follows_lever_apply_form(self) -> None:
        candidates = [
            {
                "company": "LeverCo",
                "title": "Site Reliability Engineer",
                "platform": "Lever",
                "role_family": "Site Reliability",
                "apply_url": "https://jobs.lever.co/leverco/sre-1",
                "questions": ["What's in it for you?"],
            }
        ]
        fetched: list[str] = []

        def fake_fetcher(url: str, timeout: float) -> str:
            fetched.append(url)
            if url.endswith("/apply"):
                return """
                <html>
                  <head><title>LeverCo - Site Reliability Engineer</title></head>
                  <body>
                    <label>Resume/CV</label>
                    <label>Full name ✱</label>
                    <label>Email ✱</label>
                    <label>LinkedIn URL</label>
                    <button>Submit application</button>
                  </body>
                </html>
                """
            return """
            <html>
              <head><title>LeverCo - Site Reliability Engineer</title></head>
              <body>
                <a class="postings-btn template-btn-submit" href="https://jobs.lever.co/leverco/sre-1/apply">
                  apply for this job
                </a>
              </body>
            </html>
            """

        with tempfile.TemporaryDirectory() as temp_dir:
            observed_output = Path(temp_dir) / "observed_candidates.jsonl"
            closed_path = Path(temp_dir) / "closed_jobs.json"

            report = observe_candidate_pages(
                candidates,
                observed_output,
                closed_path,
                fetcher=fake_fetcher,
                max_checks=1,
                source="lever_apply_form_test",
            )
            rows = load_candidate_rows(observed_output)
            research = build_application_research(temp_dir, position_target=100)

            self.assertEqual(report["observed_count"], 1)
            self.assertIn("https://jobs.lever.co/leverco/sre-1/apply", fetched)
            self.assertEqual(rows[0]["apply_url"], "https://jobs.lever.co/leverco/sre-1")
            self.assertIn("Resume/CV", rows[0]["questions"])
            self.assertIn("Full name \u2731", rows[0]["questions"])
            self.assertIn("What's in it for you?", rows[0]["questions"])
            self.assertEqual(research["coverage_groups"]["Lever::Site Reliability"]["positions_observed"], 1)
            labels = {item["label"] for item in research["items"]}
            self.assertIn("Resume/CV", labels)
            self.assertIn("Full name \u2731", labels)

    def test_observe_candidate_pages_records_404_as_closed(self) -> None:
        candidates = [
            {
                "company": "Example",
                "title": "Site Reliability Engineer",
                "platform": "Lever",
                "apply_url": "https://jobs.lever.co/example/closed",
            }
        ]

        def not_found_fetcher(url: str, timeout: float) -> str:
            raise urllib.error.HTTPError(url, 404, "Not Found", hdrs=None, fp=None)

        with tempfile.TemporaryDirectory() as temp_dir:
            observed_output = Path(temp_dir) / "observed_candidates.jsonl"
            closed_path = Path(temp_dir) / "closed_jobs.json"

            report = observe_candidate_pages(
                candidates,
                observed_output,
                closed_path,
                fetcher=not_found_fetcher,
                max_checks=1,
            )

            self.assertEqual(report["observed_count"], 0)
            self.assertEqual(report["closed_count"], 1)
            self.assertEqual(report["status_counts"]["closed_fetch_error"], 1)
            self.assertTrue(is_job_closed(candidates[0], load_closed_jobs(closed_path)))

    def test_write_candidate_observation_report_outputs_files(self) -> None:
        candidates = [
            {
                "company": "Example",
                "title": "Platform Engineer",
                "apply_url": "https://jobs.ashbyhq.com/example/abc",
            }
        ]

        def fake_fetcher(url: str, timeout: float) -> str:
            return "<html><label>Website</label><button>Submit Application</button></html>"

        with tempfile.TemporaryDirectory() as temp_dir:
            observed_output = Path(temp_dir) / "observed.jsonl"
            closed_path = Path(temp_dir) / "closed.json"
            json_output = Path(temp_dir) / "observation.json"
            markdown_output = Path(temp_dir) / "observation.md"

            report = write_candidate_observation_report(
                candidates,
                observed_output,
                closed_path,
                json_output,
                markdown_output,
                fetcher=fake_fetcher,
            )

            self.assertEqual(report["observed_count"], 1)
            self.assertTrue(json_output.exists())
            self.assertTrue(markdown_output.exists())
            self.assertTrue(observed_output.exists())

    def test_write_question_export_outputs_excel_and_html(self) -> None:
        gaps = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "research_generated_at": "2026-05-22T00:00:00+00:00",
            "positions_observed_total": 2,
            "unique_prompts_observed": 3,
            "ready_prompt_count": 1,
            "blocking_prompt_count": 2,
            "coverage_counts": {"covered_auto_answer": 1, "needs_user_confirmation": 1},
            "prompt_statuses": [
                {
                    "label": "Have you worked at DoorDash?*",
                    "coverage_status": "needs_user_confirmation",
                    "category": "employment_history",
                    "automation_action": "human_review_required",
                    "sensitivity": "profile",
                    "observed_count": 3,
                    "required_count": 3,
                    "platforms": ["Greenhouse"],
                    "source_files": ["doordash.json"],
                    "coverage_reason": "employer_specific_policy_or_unclear_prompt",
                    "next_action": "ask user during supervised learning",
                },
                {
                    "label": "What is your expected compensation?",
                    "coverage_status": "covered_auto_answer",
                    "category": "compensation",
                    "automation_action": "auto_answer_from_memory",
                    "sensitivity": "standard_preference",
                    "observed_count": 4,
                    "required_count": 4,
                    "platforms": ["LinkedIn"],
                    "source_files": ["linkedin.jsonl"],
                    "answer_source": "answer_memory",
                    "next_action": "autofill",
                },
            ],
            "blocking_prompts": [
                {
                    "label": "Have you worked at DoorDash?*",
                    "coverage_status": "needs_user_confirmation",
                    "category": "employment_history",
                    "automation_action": "human_review_required",
                    "sensitivity": "profile",
                    "observed_count": 3,
                    "required_count": 3,
                    "platforms": ["Greenhouse"],
                    "source_files": ["doordash.json"],
                    "next_action": "ask user during supervised learning",
                }
            ],
        }
        readiness = {
            "readiness_counts": {"autofill_ready": 1, "needs_learning": 1},
            "manual_gate_count": 1,
            "positions": [
                {
                    "readiness": "needs_learning",
                    "platform": "Greenhouse",
                    "company": "DoorDash",
                    "title": "Software Engineer",
                    "role_family": "Software Backend",
                    "apply_url": "https://job-boards.greenhouse.io/doordash/jobs/1",
                    "prompt_count": 3,
                    "required_prompt_count": 3,
                    "covered_prompt_count": 2,
                    "ready_for_autofill": False,
                    "ready_for_supervised_submit": False,
                    "ready_for_unattended_submit": False,
                    "learning_blockers": [{"label": "Have you worked at DoorDash?*"}],
                    "manual_gates": [{"label": "Submit application"}],
                }
            ],
            "manual_gates": [
                {
                    "label": "Submit application",
                    "coverage_status": "final_submit_confirmation",
                    "category": "final_submit",
                    "platforms": ["Greenhouse"],
                    "observed_count": 1,
                    "required_count": 0,
                    "recommended_storage": "do_not_automate",
                    "next_action": "human must approve final submit",
                }
            ],
        }
        coverage_gate = {
            "ready_for_full_automation": False,
            "real_platform_target_achieved": False,
            "real_platform_role_target_achieved": False,
            "synthetic": {"platform_role_target_achieved": True, "actual_submit_count": 0},
            "real_platform_counts": {"Greenhouse": 2},
            "real_platform_shortfalls": {"Greenhouse": 98},
            "next_collection_targets": [
                {
                    "platform": "Greenhouse",
                    "role_family": "Software Backend",
                    "positions_observed": 2,
                    "positions_remaining": 98,
                }
            ],
        }
        collection_plan = {
            "tasks": [
                {
                    "platform": "Greenhouse",
                    "role_family": "Software Backend",
                    "suggested_batch_size": 25,
                    "positions_remaining": 98,
                    "query": "backend software engineer",
                    "search_urls": ["https://example.com/search"],
                }
            ]
        }
        learning_tasks = {
            "task_count": 1,
            "tasks": [
                {
                    "recommended_storage": "answer_memory",
                    "question": "Have you worked at DoorDash?*",
                    "group_key": "answer_memory:doordash",
                    "platforms": ["Greenhouse"],
                    "labels": ["Have you worked at DoorDash?*"],
                    "related_prompt_count": 1,
                    "observed_count": 3,
                    "required_count": 3,
                    "approved": False,
                    "answer": "",
                    "persist_allowed": True,
                    "notes": "",
                }
            ],
        }
        source_artifacts = [
            {
                "name": "Answer gaps",
                "path": "/tmp/answer_gaps_latest.json",
                "exists": True,
                "size_bytes": 123,
                "updated_at": "2026-05-22T00:00:00+00:00",
            }
        ]
        synthetic_browser_execution = {
            "execution": "local_synthetic_browser_action_executor",
            "run_count": 200,
            "actual_submit_count": 150,
            "eligible_submit_count": 150,
            "eligible_submit_target_count": 150,
            "eligible_submit_achieved": True,
            "real_platform_submission": False,
            "selector_miss_count": 0,
            "policy_stop_counts": {"local_synthetic_submit_allowed": 150},
            "platform_role_counts": {"Greenhouse | Software Backend": 100},
        }
        fake_learning_probe = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "real_platform_submission": False,
            "input_task_count": 10,
            "fake_answered_task_count": 10,
            "fake_answer_memory_entry_count": 20,
            "fake_category_policy_count": 3,
            "baseline": {"blocking_prompt_count": 8},
            "after_fake_learning": {"blocking_prompt_count": 2},
            "remaining_learning_blocker_count": 0,
            "remaining_manual_gate_count": 2,
            "learning_blockers_cleared": True,
        }
        fake_critical_input_probe = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "source": "fake_critical_input_probe",
            "real_platform_submission": False,
            "writes_real_profile_or_memory": False,
            "fake_candidate_only": True,
            "input_count": 11,
            "fake_answered_count": 10,
            "ready_to_apply_count": 10,
            "waiting_count": 0,
            "supervised_only_count": 1,
            "profile_ready_count": 1,
            "resume_fact_ready_count": 1,
            "answer_memory_ready_count": 8,
            "high_risk_ready_count": 5,
            "ready_for_apply_critical_inputs": True,
            "ready_for_autofill_recheck": True,
            "status_counts": {"ready_to_apply": 10, "supervised_only": 1},
            "policy": {"dry_run_only": True, "final_submit_remains_supervised": True},
        }
        fake_position_rehearsal = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "execution": "observed_prompt_local_browser_manifest_executor",
            "requested_count": 100,
            "run_count": 100,
            "real_platform_submission": False,
            "local_synthetic_submit_allowed": True,
            "actual_submit_count": 100,
            "eligible_submit_target_count": 100,
            "eligible_submit_count": 100,
            "eligible_submit_achieved": True,
            "selector_miss_count": 0,
            "pre_synthetic_missing_input_count": 0,
            "policy_stop_counts": {"local_synthetic_submit_allowed": 100},
            "platform_counts": {"Greenhouse": 100},
        }
        goal_readiness_audit = {
            "status": "needs_user_answers",
            "goal_complete": False,
            "missing_requirement_count": 1,
            "can_unattended_submit_real_employers": False,
            "blocker_summary": {"data_blocking_prompt_count": 3, "critical_waiting_count": 1},
            "requirements": [
                {
                    "id": "real_position_research_100_each",
                    "requirement": "Research at least 100 positions per target platform and role family.",
                    "status": "achieved",
                },
                {
                    "id": "real_user_answer_learning",
                    "requirement": "Learn remaining truthful answers.",
                    "status": "needs_user_answers",
                },
            ],
            "top_data_blocking_prompts": [
                {
                    "coverage_status": "needs_user_confirmation",
                    "category": "employment_history",
                    "label": "Have you worked at DoorDash?*",
                    "required_count": 3,
                }
            ],
            "next_actions": ["Fill critical input answers."],
        }
        critical_input_suggestions = {
            "input_count": 1,
            "direct_suggestion_count": 1,
            "exact_user_answer_required_count": 0,
            "critical_inputs": [
                {
                    "input_id": "profile_zip_or_postal_code",
                    "input_type": "profile_or_resume_fact",
                    "question": "What ZIP/postal code should automation use?",
                    "approval_risk": "needs_review",
                    "recommended_action": "review_then_copy_to_user_answer",
                    "suggested_answer": "98004",
                    "suggestion_source": "profile.question_answers",
                    "suggestion_confidence": "high",
                    "suggestion_note": "Existing profile ZIP/postal code can be reused after review.",
                    "can_copy_to_user_answer_after_review": True,
                    "required_count": 4,
                }
            ],
        }
        critical_input_questionnaire = {
            "question_count": 1,
            "answerable_question_count": 1,
            "instructions": "Fill truthful answers.",
            "workflow_command": "python3 -m job_apply_agent critical-inputs-workflow --updates confirmed.json --approve --apply",
            "questions": [
                {
                    "impact_rank": 1,
                    "input_id": "profile_zip_or_postal_code",
                    "input_type": "profile_or_resume_fact",
                    "question": "What ZIP/postal code should automation use?",
                    "required_user_response": "Provide exact ZIP/postal code.",
                    "approval_risk": "needs_review",
                    "high_risk": False,
                    "supervised_only": False,
                    "suggested_answer": "98004",
                    "suggestion_source": "profile.question_answers",
                    "suggestion_confidence": "high",
                    "impact": {
                        "data_blocking_prompts_delta": -2,
                        "ready_prompts_delta": 2,
                        "positions_ready_for_autofill_delta": 3,
                    },
                    "platforms": ["Ashby"],
                    "labels": ["Zip Code"],
                    "required_count": 4,
                    "workflow_update_shape": "string_value",
                }
            ],
        }
        critical_input_impact = {
            "input_count": 1,
            "summary": {
                "combined_data_blocking_prompts_delta": -2,
                "combined_positions_ready_for_autofill_delta": 3,
                "top_input_id": "profile_zip_or_postal_code",
            },
            "input_impacts": [
                {
                    "input_id": "profile_zip_or_postal_code",
                    "input_type": "profile_or_resume_fact",
                    "question": "What ZIP/postal code should automation use?",
                    "approval_risk": "needs_review",
                    "simulated_answer": "98004",
                    "data_blocking_prompts_before": 253,
                    "data_blocking_prompts_after": 251,
                    "data_blocking_prompts_delta": -2,
                    "ready_prompts_delta": 2,
                    "positions_ready_for_autofill_delta": 3,
                    "temp_profile_updates": 1,
                    "temp_answer_memory_updates": 0,
                }
            ],
        }
        critical_input_preflight = {
            "summary": {"data_blocking_prompts_delta": -2, "matched_updates": 1},
            "deltas": {"positions_ready_for_autofill_delta": 3},
            "policy": {"writes_real_profile_or_memory": False},
            "next_commands": ["python3 -m job_apply_agent critical-inputs-workflow --apply"],
        }
        critical_input_unblockers = {
            "input_count": 1,
            "high_risk_count": 0,
            "prefilled_update_count": 2,
            "unblockers": [
                {
                    "input_id": "profile_zip_or_postal_code",
                    "input_type": "profile_or_resume_fact",
                    "high_risk": False,
                    "question": "What ZIP/postal code should automation use?",
                    "required_user_response": "Provide exact ZIP/postal code.",
                    "why_not_inferred": "Profile has city but no exact ZIP.",
                    "impact": {
                        "data_blocking_prompts_delta": -2,
                        "positions_ready_for_autofill_delta": 3,
                    },
                    "required_count": 4,
                    "platforms": ["Ashby"],
                    "labels": ["Zip Code"],
                }
            ],
        }
        final_answer_intake_template = {
            "answer_count": 1,
            "high_risk_count": 0,
            "aliases": {"zip_or_postal_code": "profile_zip_or_postal_code"},
            "fields": [
                {
                    "alias": "zip_or_postal_code",
                    "input_id": "profile_zip_or_postal_code",
                    "question": "What ZIP/postal code should automation use?",
                    "required_user_response": "Provide exact ZIP/postal code.",
                    "high_risk": False,
                    "required_count": 4,
                    "platforms": ["Ashby"],
                    "labels": ["Zip Code"],
                    "why_not_inferred": "Profile has city but no exact ZIP.",
                }
            ],
            "answers": {"zip_or_postal_code": ""},
        }
        post_answer_pipeline = {
            "generated_at": "2026-05-23T00:00:00+00:00",
            "status": "waiting_for_confirmed_answers",
            "ready_for_workflow": False,
            "synthetic_final_answers": False,
            "apply_requested": False,
            "live_check_requested": False,
            "open_browser_requested": False,
            "confirmed_updates_output": "job_apply_agent/outbox/critical_input_confirmed_updates_latest.json",
            "final_update_report": {
                "summary": {
                    "merged_update_count": 89,
                    "missing_unblocker_count": 1,
                    "unconfirmed_high_risk_count": 0,
                    "unknown_compact_update_count": 0,
                }
            },
            "steps": [
                {
                    "name": "finalize_confirmed_updates",
                    "status": "waiting_for_answers",
                    "details": {"missing_unblockers": 1},
                }
            ],
            "policy": {"final_submit_remains_supervised": True},
        }
        autofill_batch = {
            "generated_at": "2026-05-22T00:00:00+00:00",
            "requested_count": 100,
            "selected_count": 1,
            "selected_autofill_allowed_count": 1,
            "browser_action_count": 7,
            "selector_miss_count": 0,
            "would_submit_count": 0,
            "real_platform_submission": False,
            "platform_counts": {"Greenhouse": 1},
            "selected_stop_actions": [
                {
                    "scope": "selected",
                    "position_index": 1,
                    "platform": "Greenhouse",
                    "company": "DoorDash",
                    "title": "Software Engineer",
                    "role_family": "Software Backend",
                    "apply_url": "https://job-boards.greenhouse.io/doordash/jobs/1",
                    "status": "final_submit_confirmation",
                    "label": "Submit application",
                    "category": "final_submit",
                    "required": True,
                    "handling": "stop before final submit and wait for explicit approval",
                }
            ],
            "positions": [
                {
                    "index": 1,
                    "platform": "Greenhouse",
                    "company": "DoorDash",
                    "title": "Software Engineer",
                    "role_family": "Software Backend",
                    "apply_url": "https://job-boards.greenhouse.io/doordash/jobs/1",
                    "readiness": "autofill_ready",
                    "manifest_status": "autofill_ready_with_supervised_gates",
                    "autofill_allowed": True,
                    "browser_action_count": 7,
                    "stop_action_count": 1,
                    "local_check_policy_stop": "final_submit_confirmation",
                    "local_check_selector_miss_count": 0,
                    "would_submit": False,
                    "real_platform_submission": False,
                }
            ],
        }
        answer_memory = {
            "answers": [
                {
                    "normalized_question": "what expected compensation",
                    "sample_question": "What is your expected compensation?",
                    "answer": "$100,000+",
                    "approved_count": 1,
                    "source": "user_confirmed_standard_preferences",
                }
            ]
        }
        closed_jobs = {
            "jobs": [
                {
                    "key": "linkedin:4415508499",
                    "status": "CLOSED",
                    "reason": "No longer accepting applications",
                    "source": "live_page_check",
                    "platform": "LinkedIn",
                    "company": "Tesla",
                    "title": "SRE",
                    "short_apply_url": "https://www.linkedin.com/jobs/view/4415508499/",
                }
            ]
        }
        profile = {
            "candidate": {
                "name": "Example Person",
                "email": "example@example.com",
                "phone": "555-0100",
                "location": "Bellevue, WA",
            },
            "preferences": {
                "minimum_compensation_usd": 100000,
                "relocation_ok": True,
                "start_availability": "about two months",
            },
            "resume_facts": {"current_role": "SRE", "strongest_skills": ["Linux", "Kubernetes"]},
            "question_answers": {"relocation": "Yes", "sponsorship": "No"},
        }
        automation_handoff = {
            "status": "waiting_for_confirmed_answers",
            "summary": {
                "goal_status": "needs_user_answers",
                "data_blocking_prompt_count": 3,
                "critical_waiting_count": 1,
                "autofill_selected_count": 1,
            },
            "requirements": [
                {
                    "id": "real_user_answer_learning",
                    "status": "needs_user_answers",
                    "requirement": "Learn remaining truthful answers.",
                    "evidence": "data_blocking_prompt_count=3",
                }
            ],
            "answer_impact_queue": [
                {
                    "rank": 1,
                    "input_id": "profile_zip_or_postal_code",
                    "approval_risk": "needs_review",
                    "high_risk": False,
                    "supervised_only": False,
                    "question": "What ZIP/postal code should automation use?",
                    "required_user_response": "Provide exact ZIP/postal code.",
                    "suggested_answer": "98004",
                    "data_blocking_prompts_delta": -2,
                    "ready_prompts_delta": 2,
                    "positions_ready_for_autofill_delta": 3,
                    "handoff_action": "review_suggestion_then_approve_or_replace",
                }
            ],
            "selected_stop_action_summary": [
                {
                    "scope": "selected_100_position_batch",
                    "status": "final_submit_confirmation",
                    "label": "Submit application",
                    "count": 1,
                    "handling": "pause before real final submit and wait for explicit approval",
                }
            ],
            "blocked_candidate_stop_action_summary": [
                {
                    "scope": "blocked_candidate_pool",
                    "status": "missing_profile_value",
                    "label": "GitHub URL",
                    "count": 1,
                    "handling": "add this stable profile/link/material value before selecting these candidates",
                }
            ],
            "missing_profile_inputs": [
                {
                    "label": "GitHub URL",
                    "count": 1,
                    "sample_positions": "Lever: Example - SRE",
                    "handling": "add this stable profile/link/material value before selecting these candidates",
                }
            ],
            "policy": {"final_submit": "supervised"},
            "next_commands": ["python3 -m job_apply_agent automation-handoff"],
        }
        apply_queue_handoff = {
            "status": "waiting_for_confirmed_answers",
            "ready_for_supervised_open_batch": False,
            "open_ready_count": 0,
            "open_after_answers_count": 1,
            "manual_live_check_count": 1,
            "closed_or_skipped_count": 0,
            "preflight": {
                "live_checked_count": 2,
                "open_eligible_count": 1,
                "uncertain_count": 1,
                "status_counts": {"open_live_checked": 1, "check_error": 1},
            },
            "handoff_status_counts": {
                "waiting_for_answers_before_open": 1,
                "requires_manual_live_check": 1,
            },
            "global_blockers": ["critical_input_updates_not_ready"],
            "next_commands": ["python3 -m job_apply_agent apply-queue-handoff"],
            "positions": [
                {
                    "index": 1,
                    "handoff_status": "waiting_for_answers_before_open",
                    "queue_status": "waiting_for_confirmed_answers",
                    "live_status": "open_live_checked",
                    "platform": "Greenhouse",
                    "company": "DoorDash",
                    "title": "Software Engineer",
                    "role_family": "Software Backend",
                    "live_open_eligible": True,
                    "live_closed": False,
                    "next_action": "apply confirmed critical inputs, rerun apply-queue, then open",
                    "apply_url": "https://job-boards.greenhouse.io/doordash/jobs/1",
                }
            ],
        }
        apply_queue_refresh = {
            "status": "queue_refreshed",
            "skip_live_check": False,
            "max_rounds": 3,
            "rounds": [
                {
                    "round": 1,
                    "live_check_status": "checked",
                    "live_open_after_answers_count": 1,
                    "top_up_required": 0,
                }
            ],
            "final": {
                "live_open_after_answers_count": 1,
                "top_up_required_count": 0,
                "manual_live_check_count": 0,
                "closed_or_skipped_count": 0,
            },
            "policy": {"skip_closed_jobs": True},
        }

        export = build_question_export(
            gaps,
            readiness,
            coverage_gate,
            collection_plan,
            learning_tasks,
            source_artifacts=source_artifacts,
            synthetic_browser_execution=synthetic_browser_execution,
            fake_learning_probe=fake_learning_probe,
            fake_critical_input_probe=fake_critical_input_probe,
            fake_position_rehearsal=fake_position_rehearsal,
            goal_readiness_audit=goal_readiness_audit,
            critical_input_suggestions=critical_input_suggestions,
            critical_input_questionnaire=critical_input_questionnaire,
            critical_input_preflight=critical_input_preflight,
            critical_input_impact=critical_input_impact,
            critical_input_unblockers=critical_input_unblockers,
            final_answer_intake_template=final_answer_intake_template,
            post_answer_pipeline=post_answer_pipeline,
            autofill_batch=autofill_batch,
            apply_queue_handoff=apply_queue_handoff,
            apply_queue_refresh=apply_queue_refresh,
            automation_handoff=automation_handoff,
            answer_memory=answer_memory,
            closed_jobs=closed_jobs,
            profile=profile,
        )
        html = render_question_export_html(export)

        self.assertIn("Job Application Question Export", html)
        self.assertIn("Have you worked at DoorDash?", html)
        self.assertIn("Source Artifacts", html)
        self.assertIn("Synthetic Browser Execution", html)
        self.assertIn("Goal Readiness Audit", html)
        self.assertIn("needs_user_answers", html)
        self.assertIn("Critical Input Suggestions", html)
        self.assertIn("profile_zip_or_postal_code", html)
        self.assertIn("critical-inputs-update", html)
        self.assertIn("critical-inputs-workflow", html)
        self.assertIn("Critical Input Questionnaire", html)
        self.assertIn("Critical Input Impact", html)
        self.assertIn("Critical Input Preflight", html)
        self.assertIn("Final Answer Unblockers", html)
        self.assertIn("Final-Answer Intake", html)
        self.assertIn("zip_or_postal_code", html)
        self.assertIn("Example shape", html)
        self.assertIn("[ZIP_CODE]", html)
        self.assertIn("Post-Answer Pipeline", html)
        self.assertIn("waiting_for_answers", html)
        self.assertIn("Autofill Batch", html)
        self.assertIn("Apply Queue Handoff", html)
        self.assertIn("Apply queue refresh", html)
        self.assertIn("queue_refreshed", html)
        self.assertIn("waiting_for_answers_before_open", html)
        self.assertIn("Automation Handoff", html)
        self.assertIn("review_suggestion_then_approve_or_replace", html)
        self.assertIn("Submit application", html)
        self.assertIn("Impact blockers", html)
        self.assertIn("Fake Learning Probe", html)
        self.assertIn("Fake Critical Input Probe", html)
        self.assertIn("Fake Position Rehearsal", html)
        self.assertIn("observed_prompt_local_browser_manifest_executor", html)
        self.assertIn("learning_blockers_cleared", html)
        self.assertIn("ready_for_autofill_recheck", html)
        self.assertIn("writes_real_profile_or_memory", html)
        self.assertIn("Closed Posting Registry", html)
        self.assertIn("Answer Memory Index", html)
        self.assertIn("Profile Snapshot", html)
        self.assertIn("minimum_compensation_usd", html)
        self.assertIn("configured; redacted in export", html)
        self.assertNotIn("example@example.com", html)
        self.assertIn("No longer accepting applications", html)
        self.assertIn("Problem Buckets", html)
        self.assertIn("Learning Approval Pack", html)
        self.assertIn("Missing Critical Inputs", html)
        self.assertIn("Approval Tasks", html)
        self.assertIn("Platform Role Summary", html)
        self.assertIn("Platform Role Blockers", html)
        self.assertIn("Real Platform Shortfalls", html)
        self.assertIn("Collection Tasks", html)
        self.assertIn("Manual Gates", html)
        self.assertIn("Provide the exact answer to reuse for this prompt wording.", html)
        self.assertIn("https://job-boards.greenhouse.io/doordash/jobs/1", html)
        self.assertIn("Autofill ready", html)

        with tempfile.TemporaryDirectory() as temp_dir:
            xlsx_output = Path(temp_dir) / "questions.xlsx"
            html_output = Path(temp_dir) / "questions.html"
            result = write_question_export(
                gaps,
                readiness,
                coverage_gate,
                collection_plan,
                learning_tasks,
                xlsx_output,
                html_output,
                source_artifacts=source_artifacts,
                synthetic_browser_execution=synthetic_browser_execution,
                fake_learning_probe=fake_learning_probe,
                fake_critical_input_probe=fake_critical_input_probe,
                fake_position_rehearsal=fake_position_rehearsal,
                goal_readiness_audit=goal_readiness_audit,
                critical_input_suggestions=critical_input_suggestions,
                critical_input_questionnaire=critical_input_questionnaire,
                critical_input_preflight=critical_input_preflight,
                critical_input_impact=critical_input_impact,
                critical_input_unblockers=critical_input_unblockers,
                final_answer_intake_template=final_answer_intake_template,
                post_answer_pipeline=post_answer_pipeline,
                autofill_batch=autofill_batch,
                apply_queue_handoff=apply_queue_handoff,
                apply_queue_refresh=apply_queue_refresh,
                automation_handoff=automation_handoff,
                answer_memory=answer_memory,
                closed_jobs=closed_jobs,
                profile=profile,
            )

            self.assertEqual(len(result["question_rows"]), 2)
            self.assertEqual(result["problem_buckets"][0]["coverage_status"], "needs_user_confirmation")
            self.assertEqual(result["summary"]["approval_pack_task_count"], 1)
            self.assertEqual(result["summary"]["critical_input_count"], 1)
            self.assertEqual(result["learning_approval_critical_inputs"][0]["input_type"], "exact_prompt_answer")
            self.assertEqual(len(result["learning_approval_tasks"]), 1)
            self.assertEqual(result["summary"]["fake_critical_input_ready_count"], 10)
            self.assertEqual(result["summary"]["goal_audit_status"], "needs_user_answers")
            self.assertEqual(result["summary"]["critical_input_direct_suggestion_count"], 1)
            self.assertEqual(result["summary"]["critical_questionnaire_question_count"], 1)
            self.assertEqual(result["summary"]["critical_impact_top_input_id"], "profile_zip_or_postal_code")
            self.assertEqual(result["summary"]["final_unblocker_count"], 1)
            self.assertEqual(result["summary"]["final_answer_intake_count"], 1)
            self.assertEqual(result["summary"]["final_answer_intake_high_risk_count"], 0)
            self.assertEqual(result["summary"]["post_answer_pipeline_status"], "waiting_for_confirmed_answers")
            self.assertEqual(result["summary"]["autofill_batch_selected_count"], 1)
            self.assertEqual(result["summary"]["apply_queue_handoff_status"], "waiting_for_confirmed_answers")
            self.assertEqual(result["summary"]["apply_queue_handoff_open_after_answers_count"], 1)
            self.assertEqual(result["summary"]["apply_queue_refresh_status"], "queue_refreshed")
            self.assertEqual(result["summary"]["apply_queue_refresh_live_open_after_answers_count"], 1)
            self.assertEqual(result["summary"]["apply_queue_refresh_top_up_required_count"], 0)
            self.assertEqual(result["summary"]["automation_handoff_status"], "waiting_for_confirmed_answers")
            self.assertEqual(result["summary"]["automation_handoff_answer_queue_count"], 1)
            self.assertEqual(result["summary"]["answer_memory_count"], 1)
            self.assertEqual(result["summary"]["closed_posting_count"], 1)
            self.assertGreaterEqual(result["summary"]["profile_snapshot_field_count"], 1)
            self.assertTrue(xlsx_output.exists())
            self.assertTrue(html_output.exists())
            with zipfile.ZipFile(xlsx_output) as workbook:
                names = set(workbook.namelist())
                self.assertIn("xl/workbook.xml", names)
                self.assertIn("xl/worksheets/sheet1.xml", names)
                self.assertIn("xl/worksheets/sheet2.xml", names)
                self.assertIn("xl/worksheets/sheet8.xml", names)
                self.assertIn("xl/worksheets/sheet26.xml", names)
                self.assertIn("xl/worksheets/sheet27.xml", names)
                self.assertIn("xl/worksheets/sheet28.xml", names)
                self.assertIn("xl/worksheets/sheet29.xml", names)
                self.assertIn("xl/worksheets/sheet30.xml", names)
                self.assertIn("xl/worksheets/sheet39.xml", names)
                self.assertIn("xl/worksheets/sheet40.xml", names)
                self.assertIn("xl/worksheets/sheet42.xml", names)
                self.assertIn("xl/worksheets/sheet43.xml", names)
                self.assertIn("xl/worksheets/sheet44.xml", names)
                self.assertIn("xl/worksheets/sheet45.xml", names)
                self.assertIn("xl/worksheets/sheet46.xml", names)
                critical_inputs = workbook.read("xl/worksheets/sheet2.xml").decode("utf-8")
                self.assertIn("exact_prompt_answer", critical_inputs)
                self.assertIn("user_answer", critical_inputs)
                source_sheet = workbook.read("xl/worksheets/sheet3.xml").decode("utf-8")
                self.assertIn("Answer gaps", source_sheet)
                synthetic_sheet = workbook.read("xl/worksheets/sheet4.xml").decode("utf-8")
                self.assertIn("local_synthetic_browser_action_executor", synthetic_sheet)
                fake_probe = workbook.read("xl/worksheets/sheet7.xml").decode("utf-8")
                self.assertIn("learning_blockers_cleared", fake_probe)
                fake_critical_inputs = workbook.read("xl/worksheets/sheet8.xml").decode("utf-8")
                self.assertIn("ready_for_autofill_recheck", fake_critical_inputs)
                self.assertIn("writes_real_profile_or_memory", fake_critical_inputs)
                fake_position = workbook.read("xl/worksheets/sheet9.xml").decode("utf-8")
                self.assertIn("observed_prompt_local_browser_manifest_executor", fake_position)
                questionnaire_sheet = workbook.read("xl/worksheets/sheet10.xml").decode("utf-8")
                self.assertIn("profile_zip_or_postal_code", questionnaire_sheet)
                impact_sheet = workbook.read("xl/worksheets/sheet11.xml").decode("utf-8")
                self.assertIn("simulated_answer", impact_sheet)
                preflight_sheet = workbook.read("xl/worksheets/sheet12.xml").decode("utf-8")
                self.assertIn("writes_real_profile_or_memory", preflight_sheet)
                autofill_sheet = workbook.read("xl/worksheets/sheet13.xml").decode("utf-8")
                self.assertIn("selected_count", autofill_sheet)
                autofill_positions = workbook.read("xl/worksheets/sheet14.xml").decode("utf-8")
                self.assertIn("final_submit_confirmation", autofill_positions)
                autofill_stops = workbook.read("xl/worksheets/sheet15.xml").decode("utf-8")
                self.assertIn("Submit application", autofill_stops)
                apply_queue_handoff_sheet = workbook.read("xl/worksheets/sheet16.xml").decode("utf-8")
                self.assertIn("open_after_answers_count", apply_queue_handoff_sheet)
                apply_queue_refresh_sheet = workbook.read("xl/worksheets/sheet17.xml").decode("utf-8")
                self.assertIn("queue_refreshed", apply_queue_refresh_sheet)
                self.assertIn("live_open_after_answers_count", apply_queue_refresh_sheet)
                apply_queue_handoff_positions = workbook.read("xl/worksheets/sheet18.xml").decode("utf-8")
                self.assertIn("waiting_for_answers_before_open", apply_queue_handoff_positions)
                handoff_sheet = workbook.read("xl/worksheets/sheet19.xml").decode("utf-8")
                self.assertIn("waiting_for_confirmed_answers", handoff_sheet)
                handoff_answer_queue = workbook.read("xl/worksheets/sheet21.xml").decode("utf-8")
                self.assertIn("profile_zip_or_postal_code", handoff_answer_queue)
                handoff_stop_summary = workbook.read("xl/worksheets/sheet22.xml").decode("utf-8")
                self.assertIn("final_submit_confirmation", handoff_stop_summary)
                problem_buckets = workbook.read("xl/worksheets/sheet24.xml").decode("utf-8")
                self.assertIn("needs_user_confirmation", problem_buckets)
                user_questions = workbook.read("xl/worksheets/sheet25.xml").decode("utf-8")
                self.assertIn("Have you worked at DoorDash?", user_questions)
                platform_role_summary = workbook.read("xl/worksheets/sheet29.xml").decode("utf-8")
                self.assertIn("Software Backend", platform_role_summary)
                platform_role_blockers = workbook.read("xl/worksheets/sheet30.xml").decode("utf-8")
                self.assertIn("Have you worked at DoorDash?", platform_role_blockers)
                platform_shortfalls = workbook.read("xl/worksheets/sheet32.xml").decode("utf-8")
                self.assertIn("Greenhouse", platform_shortfalls)
                closed_postings = workbook.read("xl/worksheets/sheet37.xml").decode("utf-8")
                self.assertIn("No longer accepting applications", closed_postings)
                approval_buckets = workbook.read("xl/worksheets/sheet38.xml").decode("utf-8")
                self.assertIn("exact_prompt_answer", approval_buckets)
                approval_tasks = workbook.read("xl/worksheets/sheet39.xml").decode("utf-8")
                self.assertIn("Have you worked at DoorDash?", approval_tasks)
                goal_audit = workbook.read("xl/worksheets/sheet41.xml").decode("utf-8")
                self.assertIn("needs_user_answers", goal_audit)
                critical_suggestions = workbook.read("xl/worksheets/sheet42.xml").decode("utf-8")
                self.assertIn("profile_zip_or_postal_code", critical_suggestions)
                profile_snapshot = workbook.read("xl/worksheets/sheet43.xml").decode("utf-8")
                self.assertIn("minimum_compensation_usd", profile_snapshot)
                self.assertIn("configured; redacted in export", profile_snapshot)
                self.assertNotIn("example@example.com", profile_snapshot)
                final_unblockers = workbook.read("xl/worksheets/sheet44.xml").decode("utf-8")
                self.assertIn("profile_zip_or_postal_code", final_unblockers)
                self.assertIn("Provide exact ZIP/postal code.", final_unblockers)
                post_answer = workbook.read("xl/worksheets/sheet45.xml").decode("utf-8")
                self.assertIn("waiting_for_confirmed_answers", post_answer)
                self.assertIn("missing_unblocker_count", post_answer)
                final_answer_intake = workbook.read("xl/worksheets/sheet46.xml").decode("utf-8")
                self.assertIn("zip_or_postal_code", final_answer_intake)
                self.assertIn("waiting_for_answer", final_answer_intake)
                self.assertIn("[ZIP_CODE]", final_answer_intake)

    def test_platform_question_playbook_summarizes_research_and_rehearsal(self) -> None:
        research = {
            "positions_observed_total": 201,
            "platforms": {
                "Greenhouse": {"positions_observed": 101, "prompt_items": 3},
                "Lever": {"positions_observed": 100, "prompt_items": 2},
            },
            "positions": [
                {
                    "position_key": "greenhouse:1",
                    "platform": "Greenhouse",
                    "company": "DoorDash",
                    "title": "SRE",
                    "role_family": "Site Reliability",
                    "apply_url": "https://job-boards.greenhouse.io/doordash/jobs/1",
                },
                {
                    "position_key": "lever:1",
                    "platform": "Lever",
                    "company": "Emburse",
                    "title": "Platform Engineer",
                    "role_family": "Platform Infrastructure",
                    "apply_url": "https://jobs.lever.co/emburse/1",
                },
            ],
            "items": [
                {
                    "position_key": "greenhouse:1",
                    "platform": "Greenhouse",
                    "item_type": "question",
                    "label": "Are you authorized to work in the United States?",
                    "normalized_label": "authorized work united states",
                    "required": True,
                    "category": "authorization",
                    "automation_action": "auto_answer_from_memory",
                },
                {
                    "position_key": "greenhouse:1",
                    "platform": "Greenhouse",
                    "item_type": "question",
                    "label": "Why are you interested in this role?",
                    "normalized_label": "why interested role",
                    "required": True,
                    "category": "role_specific_free_text",
                    "automation_action": "generate_custom_material",
                },
                {
                    "position_key": "lever:1",
                    "platform": "Lever",
                    "item_type": "question",
                    "label": "What is your expected compensation?",
                    "normalized_label": "expected compensation",
                    "required": True,
                    "category": "compensation",
                    "automation_action": "auto_answer_from_memory",
                },
            ],
        }
        autofill_batch = {
            "selected_count": 100,
            "local_synthetic_submit_count": 100,
            "local_synthetic_submit_achieved": True,
            "local_synthetic_submit_selector_miss_count": 0,
            "positions": [
                {
                    "index": 1,
                    "platform": "Greenhouse",
                    "company": "DoorDash",
                    "title": "SRE",
                    "role_family": "Site Reliability",
                    "prompt_count": 2,
                    "manifest_status": "autofill_ready_with_supervised_gates",
                    "local_synthetic_submit_outcome": "submitted_local_synthetic",
                    "local_synthetic_submit_count": 1,
                    "local_synthetic_submit_selector_miss_count": 0,
                    "stop_action_statuses": ["final_submit_confirmation"],
                    "apply_url": "https://job-boards.greenhouse.io/doordash/jobs/1",
                },
                {
                    "index": 2,
                    "platform": "Lever",
                    "company": "Emburse",
                    "title": "Platform Engineer",
                    "role_family": "Platform Infrastructure",
                    "prompt_count": 1,
                    "manifest_status": "autofill_ready_with_supervised_gates",
                    "local_synthetic_submit_outcome": "submitted_local_synthetic",
                    "local_synthetic_submit_count": 1,
                    "local_synthetic_submit_selector_miss_count": 0,
                    "stop_action_statuses": ["final_submit_confirmation"],
                    "apply_url": "https://jobs.lever.co/emburse/1",
                },
            ],
        }
        fake_position_rehearsal = {
            "target_platforms": ["Greenhouse", "Lever"],
            "run_count": 2,
            "actual_submit_count": 2,
            "selector_miss_count": 0,
            "runs": [
                {"platform": "Greenhouse", "actual_submit_count": 1, "selector_miss_count": 0},
                {"platform": "Lever", "actual_submit_count": 1, "selector_miss_count": 0},
            ],
        }
        automation_handoff = {
            "summary": {
                "final_answer_intake_missing_count": 1,
                "autofill_packet_ready_after_answers": True,
            },
            "final_answer_intake": [
                {
                    "alias": "citizenship_status",
                    "input_id": "answer_memory_citizenship_status_default_policy",
                    "status": "waiting_for_answer",
                    "high_risk": True,
                    "required_count": 3,
                    "question": "What citizenship answers should automation use?",
                    "platforms": ["Greenhouse", "Lever"],
                }
            ],
        }
        closed_jobs = {
            "jobs": [
                {
                    "platform": "Greenhouse",
                    "apply_url": "https://job-boards.greenhouse.io/closed/jobs/1",
                    "reason": "No longer accepting applications",
                }
            ]
        }

        report = build_platform_question_playbook(
            research,
            autofill_batch=autofill_batch,
            fake_position_rehearsal=fake_position_rehearsal,
            automation_handoff=automation_handoff,
            closed_jobs=closed_jobs,
        )
        html = render_platform_question_playbook_html(report)
        markdown = render_platform_question_playbook_markdown(report)

        self.assertEqual(report["summary"]["target_platforms_at_100_count"], 2)
        self.assertEqual(report["summary"]["selected_position_count"], 100)
        self.assertEqual(report["summary"]["selected_local_synthetic_submit_count"], 100)
        self.assertEqual(report["summary"]["final_answer_missing_count"], 1)
        self.assertTrue(report["summary"]["ready_after_answers_for_selected_100"])
        requirement_statuses = {row["id"]: row["status"] for row in report["requirements"]}
        self.assertEqual(requirement_statuses["platform_question_research"], "achieved")
        self.assertEqual(requirement_statuses["selected_100_local_rehearsal"], "achieved")
        self.assertEqual(requirement_statuses["remaining_truthful_answers"], "needs_user_answers")
        greenhouse = next(row for row in report["platforms"] if row["platform"] == "Greenhouse")
        self.assertEqual(greenhouse["closed_postings"], 1)
        self.assertEqual(greenhouse["remaining_answer_inputs"], 1)
        self.assertIn("role_specific_free_text", html)
        self.assertIn("No longer accepting applications", json.dumps(report))
        self.assertIn("Platform Question Playbook", markdown)

        with tempfile.TemporaryDirectory() as temp_dir:
            written = write_platform_question_playbook(
                research,
                Path(temp_dir) / "playbook.json",
                Path(temp_dir) / "playbook.md",
                Path(temp_dir) / "playbook.html",
                autofill_batch=autofill_batch,
                fake_position_rehearsal=fake_position_rehearsal,
                automation_handoff=automation_handoff,
                closed_jobs=closed_jobs,
            )
            self.assertEqual(written["outputs"]["json"], str(Path(temp_dir) / "playbook.json"))
            self.assertTrue((Path(temp_dir) / "playbook.html").exists())


if __name__ == "__main__":
    unittest.main()
