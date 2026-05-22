from __future__ import annotations

import json
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path

from job_apply_agent.core import (
    CandidateProfile,
    apply_learning_task_answers,
    build_answer_gap_report,
    build_apply_run_audit,
    build_application_draft,
    build_application_playbook,
    build_application_research,
    build_collection_plan_from_coverage_gate,
    build_question_export,
    build_browser_action_manifest,
    build_closed_posting_preflight,
    build_browser_dom_execution_plan,
    build_browser_dom_runner_script,
    build_browser_review_record,
    build_form_fill_plan,
    build_learning_task_template,
    build_pre_submit_review,
    build_position_readiness_report,
    build_research_coverage_gate,
    build_telegram_job_alert,
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
    notify_telegram_for_submissions,
    observe_candidate_pages,
    open_apply_urls_in_browser,
    record_closed_job,
    refresh_closed_jobs_from_live_pages,
    render_answer_gap_markdown,
    render_apply_run_audit_markdown,
    render_application_playbook_markdown,
    render_candidate_observation_markdown,
    render_candidate_discovery_markdown,
    render_question_export_html,
    render_application_research_markdown,
    render_collection_plan_markdown,
    render_browser_action_manifest_markdown,
    render_closed_posting_preflight_markdown,
    render_browser_dom_execution_plan_markdown,
    render_form_fill_plan_markdown,
    render_learning_task_template_markdown,
    render_pre_submit_review_markdown,
    render_position_readiness_markdown,
    render_research_coverage_gate_markdown,
    render_synthetic_apply_execution_markdown,
    render_synthetic_browser_action_execution_markdown,
    render_synthetic_application_html,
    run_synthetic_application_simulation,
    run_synthetic_apply_execution,
    run_synthetic_browser_action_execution,
    run_pipeline,
    score_job,
    select_candidate_topup,
    shorten_apply_url,
    write_answer_gap_report,
    write_apply_run_audit,
    write_application_playbook,
    write_application_research_report,
    write_browser_action_manifest,
    write_candidate_observation_report,
    write_candidate_discovery_report,
    write_candidate_topup_selection_report,
    write_closed_posting_preflight,
    write_collection_plan,
    write_question_export,
    write_browser_dom_harness,
    write_form_fill_plan,
    write_learning_task_template,
    write_pre_submit_review,
    write_position_readiness_report,
    write_research_coverage_gate,
    write_synthetic_apply_execution,
    write_synthetic_application_simulation,
    write_synthetic_browser_action_execution,
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
            self.assertFalse(is_job_closed(submissions[0], result["closed_jobs"]))

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
            "job is no longer available",
        )
        self.assertEqual(
            closed_application_phrase(
                {"visible_text": "We are no longer accepting candidates for this job."}
            ),
            "no longer accepting candidates",
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
            self.assertTrue(is_job_closed(candidates[1], load_closed_jobs(closed_path)))
            self.assertEqual(report["open_candidates"][0]["company"], "OpenCo")
            self.assertTrue(json_output.exists())
            markdown = markdown_output.read_text(encoding="utf-8")
            self.assertIn("Closed Posting Preflight", markdown)
            self.assertIn("OpenCo", markdown)
            self.assertIn("LiveClosed", markdown)
            self.assertIn("timed out", markdown)
            self.assertIn("closed_live_text", render_closed_posting_preflight_markdown(report))

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
            self.assertIn("Why Cisco?", labels)

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
        self.assertIn("Actual submit count: 0", markdown)

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
        self.assertTrue(any("jobs.ashbyhq.com" in url for url in task["search_urls"]))
        markdown = render_collection_plan_markdown(plan)
        self.assertIn("Collection Plan", markdown)
        self.assertIn("import-candidates", markdown)

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

        export = build_question_export(
            gaps,
            readiness,
            coverage_gate,
            collection_plan,
            learning_tasks,
        )
        html = render_question_export_html(export)

        self.assertIn("Job Application Question Export", html)
        self.assertIn("Have you worked at DoorDash?", html)
        self.assertIn("Real Platform Shortfalls", html)
        self.assertIn("Collection Tasks", html)
        self.assertIn("Manual Gates", html)

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
            )

            self.assertEqual(len(result["question_rows"]), 2)
            self.assertTrue(xlsx_output.exists())
            self.assertTrue(html_output.exists())
            with zipfile.ZipFile(xlsx_output) as workbook:
                names = set(workbook.namelist())
                self.assertIn("xl/workbook.xml", names)
                self.assertIn("xl/worksheets/sheet1.xml", names)
                self.assertIn("xl/worksheets/sheet2.xml", names)
                self.assertIn("xl/worksheets/sheet6.xml", names)
                self.assertIn("xl/worksheets/sheet10.xml", names)
                user_questions = workbook.read("xl/worksheets/sheet2.xml").decode("utf-8")
                self.assertIn("Have you worked at DoorDash?", user_questions)
                platform_shortfalls = workbook.read("xl/worksheets/sheet7.xml").decode("utf-8")
                self.assertIn("Greenhouse", platform_shortfalls)


if __name__ == "__main__":
    unittest.main()
