from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from job_apply_agent.core import (
    CandidateProfile,
    apply_learning_task_answers,
    build_answer_gap_report,
    build_application_draft,
    build_application_playbook,
    build_application_research,
    build_browser_review_record,
    build_form_fill_plan,
    build_learning_task_template,
    build_position_readiness_report,
    build_telegram_job_alert,
    classify_application_prompt,
    closed_application_reason,
    closed_application_phrase,
    extract_linkedin_job_id,
    find_learned_answer,
    job_registry_key,
    is_job_closed,
    learn_answers,
    load_answer_memory,
    load_closed_jobs,
    load_jobs,
    load_profile,
    load_submissions_jsonl,
    load_telegram_config,
    notify_telegram_for_submissions,
    open_apply_urls_in_browser,
    record_closed_job,
    refresh_closed_jobs_from_live_pages,
    render_answer_gap_markdown,
    render_application_playbook_markdown,
    render_application_research_markdown,
    render_form_fill_plan_markdown,
    render_learning_task_template_markdown,
    render_position_readiness_markdown,
    run_synthetic_application_simulation,
    run_pipeline,
    score_job,
    shorten_apply_url,
    write_answer_gap_report,
    write_application_playbook,
    write_application_research_report,
    write_form_fill_plan,
    write_learning_task_template,
    write_position_readiness_report,
    write_synthetic_application_simulation,
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


if __name__ == "__main__":
    unittest.main()
