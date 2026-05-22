from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_QUESTIONS = [
    "Why are you interested in this role?",
    "Describe relevant experience for this role.",
    "Are you authorized to work in the United States?",
    "What is your expected compensation range?",
]
DEFAULT_TELEGRAM_ENV = Path.home() / ".signal-deck" / "runtime" / "telegram.env"
CLOSED_APPLICATION_PHRASES = [
    "no longer accepting applications",
    "no longer accepting applicants",
    "not accepting applications",
    "applications are closed",
    "application window is closed",
    "job is no longer available",
    "position has been filled",
    "posting has expired",
]
DEFAULT_LIVE_CHECK_LIMIT = 25


@dataclass(frozen=True)
class CandidateProfile:
    name: str
    email: str
    phone: str
    location: str
    target_titles: list[str]
    target_locations: list[str]
    remote_ok: bool
    keywords: list[str]
    blocklist: list[str]
    min_score: int
    resume_facts: dict[str, str]
    question_answers: dict[str, str]

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "CandidateProfile":
        candidate = payload.get("candidate", {})
        preferences = payload.get("preferences", {})
        question_answers = {
            str(k): str(v) for k, v in payload.get("question_answers", {}).items()
        }
        if candidate.get("linkedin_url") and "linkedin_profile" not in question_answers:
            question_answers["linkedin_profile"] = str(candidate.get("linkedin_url"))
        for resume_key in ["resume_path", "resume_file", "resume_pdf"]:
            if candidate.get(resume_key) and resume_key not in question_answers:
                question_answers[resume_key] = str(candidate.get(resume_key))
        return cls(
            name=str(candidate.get("name", "PLACEHOLDER_NAME")),
            email=str(candidate.get("email", "placeholder@example.com")),
            phone=str(candidate.get("phone", "PLACEHOLDER_PHONE")),
            location=str(candidate.get("location", "PLACEHOLDER_LOCATION")),
            target_titles=_string_list(preferences.get("target_titles")),
            target_locations=_string_list(preferences.get("target_locations")),
            remote_ok=bool(preferences.get("remote_ok", True)),
            keywords=_string_list(preferences.get("keywords")),
            blocklist=_string_list(preferences.get("blocklist")),
            min_score=int(preferences.get("min_score", 55)),
            resume_facts={str(k): str(v) for k, v in payload.get("resume_facts", {}).items()},
            question_answers=question_answers,
        )


@dataclass(frozen=True)
class JobScore:
    score: int
    matched: bool
    reasons: list[str]


@dataclass(frozen=True)
class ApplicationDraft:
    job: dict[str, Any]
    score: JobScore
    cover_note: str
    answers: dict[str, str]
    missing_facts: list[str]
    answer_sources: dict[str, str]
    automation: dict[str, Any]


@dataclass(frozen=True)
class AnswerMemoryMatch:
    answer: str
    confidence: float
    source: str


@dataclass(frozen=True)
class ApplicationPromptClassification:
    category: str
    automation_action: str
    sensitivity: str
    reason: str


def load_profile(path: str | Path) -> CandidateProfile:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return CandidateProfile.from_mapping(payload)


def load_jobs(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("jobs", [])
    if not isinstance(payload, list):
        raise ValueError("jobs file must be a list or an object with a jobs list")
    return [job for job in payload if isinstance(job, dict)]


def load_answer_memory(path: str | Path) -> dict[str, Any]:
    memory_path = Path(path)
    if not memory_path.exists():
        return {"version": 1, "answers": []}
    payload = json.loads(memory_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("answer memory must be a JSON object")
    payload.setdefault("version", 1)
    payload.setdefault("answers", [])
    return payload


def save_answer_memory(path: str | Path, memory: dict[str, Any]) -> None:
    memory_path = Path(path)
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    memory_path.write_text(json.dumps(memory, ensure_ascii=True, indent=2), encoding="utf-8")


def load_closed_jobs(path: str | Path) -> dict[str, Any]:
    closed_path = Path(path)
    if not closed_path.exists():
        return {"version": 1, "jobs": []}
    payload = json.loads(closed_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("closed jobs registry must be a JSON object")
    payload.setdefault("version", 1)
    payload.setdefault("jobs", [])
    return payload


def save_closed_jobs(path: str | Path, closed_jobs: dict[str, Any]) -> None:
    closed_path = Path(path)
    closed_path.parent.mkdir(parents=True, exist_ok=True)
    closed_path.write_text(
        json.dumps(closed_jobs, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )


def record_closed_job(
    path: str | Path,
    job: dict[str, Any],
    reason: str = "No longer accepting applications",
    source: str = "manual",
) -> dict[str, Any]:
    closed_jobs = load_closed_jobs(path)
    jobs = closed_jobs.setdefault("jobs", [])
    key = job_registry_key(job)
    now = datetime.now(timezone.utc).isoformat()
    existing = next((entry for entry in jobs if entry.get("key") == key), None)
    if existing:
        existing["last_seen_at"] = now
        existing["seen_count"] = int(existing.get("seen_count", 1)) + 1
        existing["reason"] = reason
        existing["source"] = source
        save_closed_jobs(path, closed_jobs)
        return existing

    record = {
        "key": key,
        "status": "CLOSED",
        "reason": reason,
        "source": source,
        "first_seen_at": now,
        "last_seen_at": now,
        "seen_count": 1,
        "platform": job.get("platform") or infer_platform_from_url(str(job.get("apply_url", ""))),
        "job_id": job.get("job_id") or extract_linkedin_job_id(str(job.get("apply_url", ""))),
        "company": job.get("company"),
        "title": job.get("title"),
        "short_apply_url": shorten_apply_url(str(job.get("apply_url", "")), job),
    }
    jobs.append(record)
    save_closed_jobs(path, closed_jobs)
    return record


def learn_answers(
    memory_path: str | Path,
    job: dict[str, Any],
    answers: dict[str, str],
    source: str = "manual_submission",
) -> dict[str, Any]:
    memory = load_answer_memory(memory_path)
    now = datetime.now(timezone.utc).isoformat()
    entries = memory.setdefault("answers", [])
    for question, answer in answers.items():
        normalized_question = _normalize_question(question)
        if not normalized_question or not str(answer).strip():
            continue
        existing = next(
            (
                entry
                for entry in entries
                if entry.get("normalized_question") == normalized_question
                and entry.get("answer") == str(answer).strip()
            ),
            None,
        )
        if existing:
            existing["approved_count"] = int(existing.get("approved_count", 0)) + 1
            existing["last_seen_at"] = now
            existing["source"] = source
            continue
        entries.append(
            {
                "normalized_question": normalized_question,
                "sample_question": question,
                "answer": str(answer).strip(),
                "approved_count": 1,
                "source": source,
                "first_seen_at": now,
                "last_seen_at": now,
                "example_job": {
                    "platform": job.get("platform"),
                    "company": job.get("company"),
                    "title": job.get("title"),
                    "job_id": job.get("job_id"),
                },
            }
        )
    save_answer_memory(memory_path, memory)
    return memory


def score_job(
    profile: CandidateProfile,
    job: dict[str, Any],
    closed_jobs: dict[str, Any] | None = None,
) -> JobScore:
    closed_reason = closed_application_reason(job, closed_jobs=closed_jobs)
    if closed_reason:
        return JobScore(score=0, matched=False, reasons=[closed_reason])

    title = str(job.get("title", ""))
    location = str(job.get("location", ""))
    description = str(job.get("description", ""))
    text = _normalize(" ".join([title, location, description, " ".join(_string_list(job.get("skills")))]))
    score = 0
    reasons: list[str] = []

    for target in profile.target_titles:
        target_text = _normalize(target)
        if target_text and target_text in _normalize(title):
            score += 30
            reasons.append(f"title:{target}")
        elif _token_overlap(target_text, _normalize(title)) >= 0.5:
            score += 15
            reasons.append(f"title_overlap:{target}")

    for target_location in profile.target_locations:
        target_location_text = _normalize(target_location)
        if target_location_text and target_location_text in _normalize(location):
            score += 15
            reasons.append(f"location:{target_location}")

    if profile.remote_ok and _is_remote(job):
        score += 10
        reasons.append("remote_ok")

    for keyword in profile.keywords:
        keyword_text = _normalize(keyword)
        if keyword_text and keyword_text in text:
            score += 5
            reasons.append(f"keyword:{keyword}")

    for blocked in profile.blocklist:
        blocked_text = _normalize(blocked)
        if blocked_text and blocked_text in text:
            score -= 35
            reasons.append(f"blocked:{blocked}")

    score = max(0, min(score, 100))
    return JobScore(score=score, matched=score >= profile.min_score, reasons=reasons)


def is_job_closed(job: dict[str, Any], closed_jobs: dict[str, Any] | None = None) -> bool:
    return closed_application_reason(job, closed_jobs=closed_jobs) is not None


def closed_application_reason(
    job: dict[str, Any],
    closed_jobs: dict[str, Any] | None = None,
) -> str | None:
    registry_reason = _closed_registry_reason(job, closed_jobs)
    if registry_reason:
        return registry_reason
    phrase = closed_application_phrase(job)
    if phrase:
        return f"closed:{_normalize(phrase).replace(' ', '_')}"
    return None


def closed_application_phrase(job: dict[str, Any]) -> str | None:
    text = _normalize(_flatten_text(job))
    for phrase in CLOSED_APPLICATION_PHRASES:
        normalized_phrase = _normalize(phrase)
        if normalized_phrase and normalized_phrase in text:
            return phrase
    return None


def build_application_draft(
    profile: CandidateProfile,
    job: dict[str, Any],
    answer_memory: dict[str, Any] | None = None,
    allow_unattended_submit: bool = False,
    closed_jobs: dict[str, Any] | None = None,
) -> ApplicationDraft:
    score = score_job(profile, job, closed_jobs=closed_jobs)
    questions = _string_list(job.get("questions")) or DEFAULT_QUESTIONS
    answers: dict[str, str] = {}
    answer_sources: dict[str, str] = {}
    missing_facts: list[str] = []
    for question in questions:
        learned_answer = find_learned_answer(answer_memory, question) if answer_memory else None
        if learned_answer:
            answer, missing = learned_answer.answer, []
            answer_sources[question] = learned_answer.source
        else:
            answer, missing = answer_question(profile, job, question)
            answer_sources[question] = "profile_rules"
        answers[question] = answer
        missing_facts.extend(missing)

    missing_facts = sorted(set(missing_facts))
    draft_without_policy = ApplicationDraft(
        job=job,
        score=score,
        cover_note=build_cover_note(profile, job),
        answers=answers,
        missing_facts=missing_facts,
        answer_sources=answer_sources,
        automation={},
    )
    return ApplicationDraft(
        job=job,
        score=score,
        cover_note=draft_without_policy.cover_note,
        answers=answers,
        missing_facts=missing_facts,
        answer_sources=answer_sources,
        automation=assess_automation_readiness(
            draft_without_policy,
            allow_unattended_submit=allow_unattended_submit,
        ),
    )


def find_learned_answer(
    answer_memory: dict[str, Any] | None, question: str
) -> AnswerMemoryMatch | None:
    if not answer_memory:
        return None
    normalized_question = _normalize_question(question)
    best_entry: dict[str, Any] | None = None
    best_overlap = 0.0
    for entry in answer_memory.get("answers", []):
        entry_question = str(entry.get("normalized_question", ""))
        if not entry_question:
            continue
        if entry_question == normalized_question:
            approved_count = max(int(entry.get("approved_count", 0)), 1)
            return AnswerMemoryMatch(
                answer=str(entry.get("answer", "")),
                confidence=min(0.99, 0.85 + approved_count * 0.03),
                source=f"learned:{entry.get('source', 'manual')}",
            )
        overlap = _token_overlap(entry_question, normalized_question)
        if overlap > best_overlap:
            best_overlap = overlap
            best_entry = entry
    if best_entry and best_overlap >= 0.78:
        return AnswerMemoryMatch(
            answer=str(best_entry.get("answer", "")),
            confidence=best_overlap,
            source=f"learned_similar:{best_entry.get('source', 'manual')}",
        )
    return None


def assess_automation_readiness(
    draft: ApplicationDraft,
    allow_unattended_submit: bool = False,
) -> dict[str, Any]:
    reasons: list[str] = []
    if not draft.score.matched:
        reasons.append("job_score_below_threshold")
    if draft.missing_facts:
        reasons.append("missing_verified_facts")
    if _has_sensitive_or_unclear_question(draft.answers):
        reasons.append("sensitive_or_unclear_question")
    if not allow_unattended_submit:
        reasons.append("final_submit_requires_human_confirmation")

    ready_for_autofill = draft.score.matched and not draft.missing_facts
    ready_for_unattended_submit = (
        allow_unattended_submit
        and ready_for_autofill
        and not _has_sensitive_or_unclear_question(draft.answers)
    )
    mode = "unattended_submit" if ready_for_unattended_submit else "supervised_review"
    if not ready_for_autofill:
        mode = "human_review_required"

    return {
        "ready_for_autofill": ready_for_autofill,
        "ready_for_unattended_submit": ready_for_unattended_submit,
        "mode": mode,
        "reasons": reasons,
    }


def answer_question(
    profile: CandidateProfile, job: dict[str, Any], question: str
) -> tuple[str, list[str]]:
    normalized_question = _normalize(question)
    direct_answer = _direct_answer(profile, normalized_question)
    if direct_answer:
        return direct_answer, []

    title = str(job.get("title", "this role"))
    company = str(job.get("company", "your team"))
    summary = profile.resume_facts.get("professional_summary")
    strongest_skills = profile.resume_facts.get("strongest_skills")
    evidence = profile.resume_facts.get("impact_example")
    missing: list[str] = []

    if "why" in normalized_question or "interest" in normalized_question:
        if not summary:
            missing.append("professional_summary")
            summary = "PLACEHOLDER_PROFESSIONAL_SUMMARY"
        if not strongest_skills:
            missing.append("strongest_skills")
            strongest_skills = "PLACEHOLDER_RELEVANT_SKILLS"
        summary = _clean_sentence(summary)
        strongest_skills = _clean_sentence(strongest_skills)
        return (
            f"I am interested in the {title} role at {company} because it aligns with "
            f"my background: {summary}. The strongest fit is {strongest_skills}.",
            missing,
        )

    if "experience" in normalized_question or "project" in normalized_question:
        cloud_answer = _answer_cloud_question(profile, normalized_question)
        if cloud_answer:
            return cloud_answer
        platform_answer = _answer_platform_reliability_question(profile, normalized_question)
        if platform_answer:
            return platform_answer

        if not evidence:
            missing.append("impact_example")
            evidence = "PLACEHOLDER_PROJECT_OR_IMPACT_EXAMPLE"
        evidence = _clean_sentence(evidence)
        return (
            f"A relevant example from my background is: {evidence}. I would connect "
            f"that experience directly to the requirements of the {title} role.",
            missing,
        )

    if "skill" in normalized_question or "technology" in normalized_question:
        if not strongest_skills:
            missing.append("strongest_skills")
            strongest_skills = "PLACEHOLDER_RELEVANT_SKILLS"
        strongest_skills = _clean_sentence(strongest_skills)
        return f"My most relevant skills for this role are {strongest_skills}.", missing

    if not summary:
        missing.append("professional_summary")
        summary = "PLACEHOLDER_PROFESSIONAL_SUMMARY"
    summary = _clean_sentence(summary)
    return (
        f"My answer would be based only on verified resume facts. Current summary: {summary}.",
        missing,
    )


def _answer_cloud_question(
    profile: CandidateProfile, normalized_question: str
) -> tuple[str, list[str]] | None:
    if not any(term in normalized_question for term in ["gcp", "google cloud", "aws", "azure"]):
        return None

    if "gcp" in normalized_question or "google cloud" in normalized_question:
        gcp_experience = profile.resume_facts.get("gcp_experience")
        if not gcp_experience:
            cloud_experience = profile.resume_facts.get(
                "cloud_experience", "PLACEHOLDER_CLOUD_EXPERIENCE"
            )
            return (
                "I have cloud infrastructure experience, but I should not claim a "
                f"specific duration of GCP experience until this is verified. Known facts: "
                f"{_clean_sentence(cloud_experience)}.",
                ["gcp_experience"],
            )
        return _clean_sentence(gcp_experience) + ".", []

    cloud_experience = profile.resume_facts.get("cloud_experience")
    if not cloud_experience:
        return (
            "I have production infrastructure experience, but the exact cloud-provider "
            "details should be verified before submission.",
            ["cloud_experience"],
        )
    return _clean_sentence(cloud_experience) + ".", []


def _answer_platform_reliability_question(
    profile: CandidateProfile, normalized_question: str
) -> tuple[str, list[str]] | None:
    platform_terms = [
        "kubernetes",
        "on call",
        "oncall",
        "observability",
        "prometheus",
        "grafana",
        "incident",
        "reliability",
    ]
    if not any(term in normalized_question for term in platform_terms):
        return None

    answer = profile.resume_facts.get("kubernetes_oncall_experience")
    if not answer:
        answer = profile.resume_facts.get("current_role") or profile.resume_facts.get("impact_example")
    if not answer:
        return (
            "I have reliability experience, but the exact platform/on-call details should "
            "be verified before submission.",
            ["kubernetes_oncall_experience"],
        )
    return _clean_sentence(answer) + ".", []


def build_cover_note(profile: CandidateProfile, job: dict[str, Any]) -> str:
    title = str(job.get("title", "this role"))
    company = str(job.get("company", "your team"))
    summary = _clean_sentence(
        profile.resume_facts.get("professional_summary", "PLACEHOLDER_PROFESSIONAL_SUMMARY")
    )
    skills = _clean_sentence(
        profile.resume_facts.get("strongest_skills", "PLACEHOLDER_RELEVANT_SKILLS")
    )
    return (
        f"Hi {company} team, I am applying for the {title} role. {summary}. "
        f"My most relevant strengths are {skills}. I would be glad to discuss how "
        f"my background maps to the role."
    )


def run_pipeline(
    profile: CandidateProfile,
    jobs: list[dict[str, Any]],
    outbox_path: str | Path,
    limit: int = 3,
    answer_memory: dict[str, Any] | None = None,
    allow_unattended_submit: bool = False,
    closed_jobs: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    drafts = [
        build_application_draft(
            profile,
            job,
            answer_memory=answer_memory,
            allow_unattended_submit=allow_unattended_submit,
            closed_jobs=closed_jobs,
        )
        for job in jobs
        if score_job(profile, job, closed_jobs=closed_jobs).matched
    ]
    drafts.sort(key=lambda draft: draft.score.score, reverse=True)
    submissions = [
        simulate_submission(profile, draft, outbox_path) for draft in drafts[: max(limit, 0)]
    ]
    return submissions


def load_submissions_jsonl(path: str | Path, limit: int | None = None) -> list[dict[str, Any]]:
    submissions_path = Path(path)
    if not submissions_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in submissions_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    if limit is None or limit < 0:
        return rows
    return rows[-limit:]


def classify_application_prompt(
    label: str,
    field: dict[str, Any] | None = None,
) -> ApplicationPromptClassification:
    field = field or {}
    raw_label = _normalize(
        str(
            label
            or field.get("label")
            or field.get("placeholder")
            or field.get("text")
            or ""
        )
    )
    text = _normalize(
        " ".join(
            str(value)
            for value in [
                label,
                field.get("label"),
                field.get("name"),
                field.get("id"),
                field.get("placeholder"),
                field.get("type"),
                field.get("tag"),
            ]
            if value is not None
        )
    )
    tag = str(field.get("tag") or "").upper()
    field_type = _normalize(str(field.get("type") or ""))

    if any(term in text for term in ["captcha", "g recaptcha", "g-recaptcha"]):
        return ApplicationPromptClassification(
            "security_verification",
            "manual_security_step",
            "security",
            "captcha_or_bot_check",
        )
    if raw_label in {"", "select", "start typing"} or (
        raw_label == "search" and _normalize(str(field.get("type") or "")) == "search"
    ):
        return ApplicationPromptClassification(
            "unlabeled_control",
            "human_review_required",
            "unknown",
            "unlabeled_or_placeholder_control",
        )
    if tag == "BUTTON" and any(term in text for term in ["submit", "apply"]):
        return ApplicationPromptClassification(
            "final_submit",
            "human_review_required",
            "submission_control",
            "final_submit_requires_confirmation",
        )
    if any(
        term in text
        for term in [
            "gender",
            "hispanic",
            "latino",
            "race",
            "ethnicity",
            "veteran",
            "disability",
            "sexual orientation",
            "transgender",
            "pronoun",
        ]
    ):
        return ApplicationPromptClassification(
            "eeoc_sensitive",
            "do_not_store_sensitive",
            "protected_class",
            "protected_class_self_identification",
        )
    if field_type == "file" and any(term in text for term in ["resume", "cv", "autofill"]):
        return ApplicationPromptClassification(
            "resume_upload",
            "auto_fill_from_profile",
            "document",
            "resume_file_upload",
        )
    if field_type == "file" and "cover" in text and "letter" in text:
        return ApplicationPromptClassification(
            "cover_letter_upload",
            "generate_custom_material",
            "document",
            "cover_letter_file_upload",
        )
    if any(term in text for term in ["upload file", "attach"]):
        return ApplicationPromptClassification(
            "file_upload",
            "auto_fill_from_profile",
            "document",
            "generic_file_upload",
        )
    if any(term in text for term in ["legally authorized", "authorized to work", "work authorization"]):
        return ApplicationPromptClassification(
            "work_authorization",
            "auto_answer_from_memory",
            "standard_preference",
            "standard_work_authorization_answer",
        )
    if any(
        term in text
        for term in [
            "sponsor",
            "sponsorship",
            "immigration",
            "h-1b",
            "h 1b",
            "h1b",
            "stem opt",
            "employment eligibility",
        ]
    ):
        return ApplicationPromptClassification(
            "sponsorship",
            "auto_answer_from_memory",
            "standard_preference",
            "standard_sponsorship_answer",
        )
    if any(term in text for term in ["compensation", "salary", "pay range", "base pay"]):
        return ApplicationPromptClassification(
            "compensation",
            "auto_answer_from_memory",
            "standard_preference",
            "standard_compensation_answer",
        )
    if any(
        term in text
        for term in ["start date", "available to start", "can you start", "notice period", "availability"]
    ):
        return ApplicationPromptClassification(
            "availability",
            "auto_answer_from_memory",
            "standard_preference",
            "standard_start_date_answer",
        )
    if "relocat" in text:
        return ApplicationPromptClassification(
            "relocation",
            "auto_answer_from_memory",
            "standard_preference",
            "standard_relocation_answer",
        )
    if "privacy" in text or "acknowledgement" in text or "acknowledgment" in text:
        return ApplicationPromptClassification(
            "policy_acknowledgement",
            "human_review_required",
            "policy",
            "policy_acknowledgement_requires_review",
        )
    if any(term in text for term in ["sms", "whatsapp", "text message"]):
        return ApplicationPromptClassification(
            "communication_consent",
            "human_review_required",
            "consent",
            "optional_communication_consent",
        )
    if ("year" in text or "years" in text) and "experience" in text:
        return ApplicationPromptClassification(
            "experience_years",
            "auto_answer_from_memory",
            "standard_preference",
            "standard_years_experience_answer",
        )
    if any(term in text for term in ["aws", "azure", "gcp", "google cloud", "kubernetes", "terraform"]):
        return ApplicationPromptClassification(
            "skills_experience",
            "auto_answer_from_memory",
            "resume_fact",
            "skill_or_cloud_experience",
        )
    if any(term in text for term in ["linkedin", "github", "portfolio", "website", "personal site"]):
        return ApplicationPromptClassification(
            "profile_link",
            "auto_fill_from_profile",
            "profile",
            "profile_url_field",
        )
    if any(
        term in text
        for term in [
            "first name",
            "last name",
            "legal name",
            "full name",
            "email",
            "phone",
            "location",
            "city",
            "country",
            "address",
        ]
    ):
        return ApplicationPromptClassification(
            "profile_identity",
            "auto_fill_from_profile",
            "profile",
            "basic_profile_field",
        )
    if any(term in text for term in ["school", "degree", "education", "university", "college"]):
        return ApplicationPromptClassification(
            "education",
            "auto_fill_from_profile",
            "resume_fact",
            "education_profile_field",
        )
    if "cover" in text and "letter" in text:
        return ApplicationPromptClassification(
            "cover_letter",
            "generate_custom_material",
            "custom_material",
            "cover_letter_generation",
        )
    if any(term in text for term in ["worked at", "previously employed", "former employee"]):
        return ApplicationPromptClassification(
            "employment_history",
            "human_review_required",
            "profile",
            "employer_specific_history",
        )
    if any(term in text for term in ["why", "interest", "relevant experience", "project", "describe"]):
        return ApplicationPromptClassification(
            "role_specific_free_text",
            "generate_custom_material",
            "custom_material",
            "role_specific_written_answer",
        )
    if any(term in text for term in ["blog", "source", "referral", "hear about"]):
        return ApplicationPromptClassification(
            "employer_specific_question",
            "human_review_required",
            "employer_specific",
            "requires_employer_specific_context",
        )
    return ApplicationPromptClassification(
        "unknown",
        "human_review_required",
        "unknown",
        "unclassified_application_prompt",
    )


def build_application_research(
    outbox_dir: str | Path,
    position_target: int = 100,
    max_items: int | None = None,
) -> dict[str, Any]:
    outbox = Path(outbox_dir)
    items: list[dict[str, Any]] = []
    positions: dict[str, dict[str, Any]] = {}
    if not outbox.exists():
        return _summarize_application_research(items, positions, position_target)

    for path in sorted(outbox.glob("*.json")):
        payload = _read_json_file(path)
        if not isinstance(payload, dict):
            continue
        if isinstance(payload.get("fields"), list) or isinstance(payload.get("buttons"), list):
            _collect_form_snapshot_research(path, payload, items, positions)
        if isinstance(payload.get("questions"), list):
            _collect_job_question_research(path, payload, items, positions)
        if isinstance(payload.get("jobs"), list):
            for index, job in enumerate(payload.get("jobs", [])):
                if isinstance(job, dict):
                    _collect_job_question_research(path, job, items, positions, index=index)

    for path in sorted(outbox.glob("*.jsonl")):
        for index, row in enumerate(load_submissions_jsonl(path, limit=None)):
            if "answers" in row or "questions" in row:
                _collect_submission_question_research(path, row, items, positions, index=index)
            elif row.get("status") == "OPENED_FOR_REVIEW":
                _register_research_position(path, row, positions, index=index)

    summary = _summarize_application_research(items, positions, position_target)
    if max_items is not None and max_items >= 0:
        summary["items"] = summary["items"][:max_items]
    return summary


def write_application_research_report(
    outbox_dir: str | Path,
    json_output: str | Path,
    markdown_output: str | Path,
    position_target: int = 100,
    max_items: int | None = None,
) -> dict[str, Any]:
    research = build_application_research(
        outbox_dir,
        position_target=position_target,
        max_items=max_items,
    )
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(research, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(
        render_application_research_markdown(research),
        encoding="utf-8",
    )
    return research


def build_answer_gap_report(
    research: dict[str, Any],
    profile: CandidateProfile | None = None,
    answer_memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prompts: dict[str, dict[str, Any]] = {}
    for item in research.get("items", []):
        if not isinstance(item, dict):
            continue
        key = str(item.get("normalized_label") or "").strip()
        if not key:
            continue
        prompt = prompts.setdefault(
            key,
            {
                "normalized_label": key,
                "label": item.get("label"),
                "category": item.get("category"),
                "automation_action": item.get("automation_action"),
                "sensitivity": item.get("sensitivity"),
                "required_count": 0,
                "observed_count": 0,
                "platforms": set(),
                "source_files": set(),
            },
        )
        prompt["observed_count"] += 1
        if item.get("required"):
            prompt["required_count"] += 1
        prompt["platforms"].add(str(item.get("platform") or "Unknown"))
        prompt["source_files"].add(str(item.get("source_file") or "unknown"))

    prompt_statuses: list[dict[str, Any]] = []
    for prompt in prompts.values():
        status = _answer_gap_status(prompt, profile, answer_memory)
        prompt_statuses.append(
            {
                **{
                    key: value
                    for key, value in prompt.items()
                    if key not in {"platforms", "source_files"}
                },
                "platforms": sorted(prompt["platforms"]),
                "source_files": sorted(prompt["source_files"]),
                **status,
            }
        )

    prompt_statuses.sort(
        key=lambda item: (
            _answer_status_sort_rank(str(item.get("coverage_status"))),
            -int(item.get("required_count") or 0),
            -int(item.get("observed_count") or 0),
            str(item.get("label") or ""),
        )
    )
    coverage_counts = _count_by(prompt_statuses, "coverage_status")
    blocking_statuses = {
        "needs_answer_memory",
        "needs_profile_field",
        "needs_profile_material",
        "needs_resume_facts",
        "needs_user_confirmation",
        "manual_security_step",
        "final_submit_confirmation",
        "sensitive_not_stored",
    }
    blocking_prompts = [
        item for item in prompt_statuses if item.get("coverage_status") in blocking_statuses
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_generated_at": research.get("generated_at"),
        "positions_observed_total": research.get("positions_observed_total", 0),
        "unique_prompts_observed": len(prompt_statuses),
        "coverage_counts": coverage_counts,
        "ready_prompt_count": sum(
            count
            for status, count in coverage_counts.items()
            if status
            in {
                "covered_auto_answer",
                "covered_profile",
                "covered_generation",
                "covered_requires_review",
            }
        ),
        "blocking_prompt_count": len(blocking_prompts),
        "prompt_statuses": prompt_statuses,
        "blocking_prompts": blocking_prompts,
    }


def write_answer_gap_report(
    research: dict[str, Any],
    json_output: str | Path,
    markdown_output: str | Path,
    profile: CandidateProfile | None = None,
    answer_memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = build_answer_gap_report(
        research,
        profile=profile,
        answer_memory=answer_memory,
    )
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(render_answer_gap_markdown(report), encoding="utf-8")
    return report


def build_position_readiness_report(
    research: dict[str, Any],
    answer_gap_report: dict[str, Any],
    closed_jobs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status_by_prompt = {
        str(item.get("normalized_label") or ""): item
        for item in answer_gap_report.get("prompt_statuses", [])
        if item.get("normalized_label")
    }
    positions_by_key = {
        str(position.get("position_key")): position
        for position in research.get("positions", [])
        if position.get("position_key")
    }
    items_by_position: dict[str, list[dict[str, Any]]] = {}
    for item in research.get("items", []):
        if not isinstance(item, dict):
            continue
        position_key = str(item.get("position_key") or "")
        if not position_key:
            continue
        items_by_position.setdefault(position_key, []).append(item)

    position_rows: list[dict[str, Any]] = []
    for position_key, position in sorted(positions_by_key.items()):
        closed_reason = _closed_registry_reason(position, closed_jobs)
        if closed_reason:
            position_rows.append(
                {
                    **position,
                    "readiness": "closed_skip",
                    "closed_reason": closed_reason,
                    "ready_for_autofill": False,
                    "ready_for_supervised_submit": False,
                    "ready_for_unattended_submit": False,
                    "learning_blockers": [],
                    "manual_gates": [],
                    "prompt_count": len(items_by_position.get(position_key, [])),
                    "required_prompt_count": sum(
                        1 for item in items_by_position.get(position_key, []) if item.get("required")
                    ),
                }
            )
            continue
        items = items_by_position.get(position_key, [])
        if not items:
            position_rows.append(
                {
                    **position,
                    "readiness": "needs_research",
                    "ready_for_autofill": False,
                    "ready_for_supervised_submit": False,
                    "learning_blockers": [],
                    "manual_gates": [],
                    "prompt_count": 0,
                    "required_prompt_count": 0,
                }
            )
            continue
        learning_blockers: list[dict[str, Any]] = []
        manual_gates: list[dict[str, Any]] = []
        covered_prompt_count = 0
        for item in items:
            normalized = str(item.get("normalized_label") or "")
            prompt_status = status_by_prompt.get(normalized)
            coverage_status = str((prompt_status or {}).get("coverage_status") or "needs_user_confirmation")
            prompt_summary = {
                "label": item.get("label"),
                "category": item.get("category"),
                "coverage_status": coverage_status,
                "next_action": (prompt_status or {}).get("next_action", "inspect prompt"),
                "required": bool(item.get("required")),
            }
            if coverage_status in _LEARNING_BLOCKER_STATUSES:
                _append_unique_prompt(learning_blockers, prompt_summary)
            elif coverage_status in _MANUAL_GATE_STATUSES:
                _append_unique_prompt(manual_gates, prompt_summary)
            elif coverage_status in _READY_COVERAGE_STATUSES:
                covered_prompt_count += 1

        if learning_blockers:
            readiness = "needs_learning"
        elif manual_gates:
            readiness = "supervised_ready"
        else:
            readiness = "autofill_ready"
        position_rows.append(
            {
                **position,
                "readiness": readiness,
                "ready_for_autofill": not learning_blockers,
                "ready_for_supervised_submit": not learning_blockers,
                "ready_for_unattended_submit": False,
                "unattended_submit_reason": "final submission remains a supervised action",
                "prompt_count": len(items),
                "required_prompt_count": sum(1 for item in items if item.get("required")),
                "covered_prompt_count": covered_prompt_count,
                "learning_blockers": learning_blockers,
                "manual_gates": manual_gates,
            }
        )

    readiness_counts = _count_by(position_rows, "readiness")
    learning_queue = _build_learning_queue(answer_gap_report)
    manual_gate_queue = _build_manual_gate_queue(answer_gap_report)
    minimal_learning_tasks = _minimal_learning_tasks(learning_queue)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_generated_at": research.get("generated_at"),
        "answer_gap_generated_at": answer_gap_report.get("generated_at"),
        "positions_observed_total": len(position_rows),
        "readiness_counts": readiness_counts,
        "learning_queue_count": len(learning_queue),
        "minimal_learning_task_count": len(minimal_learning_tasks),
        "manual_gate_count": len(manual_gate_queue),
        "minimal_learning_tasks": minimal_learning_tasks,
        "learning_queue": learning_queue,
        "manual_gates": manual_gate_queue,
        "positions": position_rows,
    }


def write_position_readiness_report(
    research: dict[str, Any],
    answer_gap_report: dict[str, Any],
    json_output: str | Path,
    markdown_output: str | Path,
    closed_jobs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = build_position_readiness_report(
        research,
        answer_gap_report,
        closed_jobs=closed_jobs,
    )
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(render_position_readiness_markdown(report), encoding="utf-8")
    return report


def build_form_fill_plan(
    snapshot: dict[str, Any],
    profile: CandidateProfile | None = None,
    answer_memory: dict[str, Any] | None = None,
    include_values: bool = False,
) -> dict[str, Any]:
    fields = [field for field in snapshot.get("fields", []) if isinstance(field, dict)]
    buttons = [button for button in snapshot.get("buttons", []) if isinstance(button, dict)]
    steps: list[dict[str, Any]] = []
    for field in fields:
        label = _field_prompt_label(field)
        classification = classify_application_prompt(label, field)
        if _skip_low_signal_prompt(label, classification):
            continue
        steps.append(
            _form_plan_step(
                field,
                label,
                classification,
                profile=profile,
                answer_memory=answer_memory,
                include_values=include_values,
                item_type="field",
            )
        )
    for button in buttons:
        label = _field_prompt_label(button)
        classification = classify_application_prompt(label, {**button, "tag": "BUTTON"})
        if _skip_low_signal_prompt(label, classification):
            continue
        steps.append(
            _form_plan_step(
                button,
                label,
                classification,
                profile=profile,
                answer_memory=answer_memory,
                include_values=include_values,
                item_type="button",
            )
        )
    blocking_steps = [
        step
        for step in steps
        if step.get("status")
        in {
            "missing_profile_value",
            "missing_local_material",
            "missing_answer",
            "needs_human_review",
            "manual_security_step",
            "final_submit_confirmation",
            "sensitive_not_stored",
        }
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "title": snapshot.get("title"),
        "url": snapshot.get("url"),
        "platform": infer_platform_from_url(str(snapshot.get("url") or "")) or _infer_platform_from_path(Path("snapshot.json")),
        "include_values": include_values,
        "step_count": len(steps),
        "blocking_step_count": len(blocking_steps),
        "status_counts": _count_by(steps, "status"),
        "action_counts": _count_by(steps, "action"),
        "steps": steps,
        "blocking_steps": blocking_steps,
    }


def write_form_fill_plan(
    snapshot_path: str | Path,
    json_output: str | Path,
    markdown_output: str | Path,
    profile: CandidateProfile | None = None,
    answer_memory: dict[str, Any] | None = None,
    include_values: bool = False,
) -> dict[str, Any]:
    snapshot = _read_json_file(Path(snapshot_path))
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be a JSON object")
    plan = build_form_fill_plan(
        snapshot,
        profile=profile,
        answer_memory=answer_memory,
        include_values=include_values,
    )
    plan["snapshot_file"] = Path(snapshot_path).name
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(plan, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(render_form_fill_plan_markdown(plan), encoding="utf-8")
    return plan


def build_learning_task_template(readiness_report: dict[str, Any]) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    for task in readiness_report.get("minimal_learning_tasks", []):
        if not isinstance(task, dict):
            continue
        storage = str(task.get("recommended_storage") or "")
        tasks.append(
            {
                "group_key": task.get("group_key"),
                "question": task.get("question"),
                "recommended_storage": storage,
                "labels": task.get("labels", []),
                "platforms": task.get("platforms", []),
                "approved": False,
                "answer": "",
                "notes": "",
                "persist_allowed": storage in {"profile", "local_material", "answer_memory"},
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "automation_readiness",
        "task_count": len(tasks),
        "instructions": (
            "Set approved=true and fill answer for non-sensitive tasks only. "
            "Protected-class answers and CAPTCHA/final submit gates are intentionally excluded."
        ),
        "tasks": tasks,
    }


def write_learning_task_template(
    readiness_report: dict[str, Any],
    json_output: str | Path,
    markdown_output: str | Path,
) -> dict[str, Any]:
    template = build_learning_task_template(readiness_report)
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(template, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(render_learning_task_template_markdown(template), encoding="utf-8")
    return template


def apply_learning_task_answers(
    tasks_path: str | Path,
    profile_path: str | Path,
    memory_path: str | Path,
    source: str = "learning_task_template",
    dry_run: bool = False,
) -> dict[str, Any]:
    payload = _read_json_file(Path(tasks_path))
    if not isinstance(payload, dict):
        raise ValueError("learning tasks file must be a JSON object")
    profile_payload = _read_json_file(Path(profile_path)) or {}
    if not isinstance(profile_payload, dict):
        raise ValueError("profile must be a JSON object")
    memory = load_answer_memory(memory_path)
    profile_answers = profile_payload.setdefault("question_answers", {})
    profile_updates: dict[str, str] = {}
    answer_updates: dict[str, str] = {}
    skipped: list[dict[str, Any]] = []

    for task in payload.get("tasks", []):
        if not isinstance(task, dict) or not task.get("approved"):
            continue
        answer = str(task.get("answer") or "").strip()
        if not answer:
            skipped.append({"group_key": task.get("group_key"), "reason": "empty_answer"})
            continue
        storage = str(task.get("recommended_storage") or "")
        group_key = str(task.get("group_key") or "")
        if storage == "profile" and group_key == "profile:profile_links":
            profile_updates["linkedin_profile"] = answer
        elif storage == "local_material" and group_key == "local_material:resume_file":
            profile_updates["resume_path"] = answer
        elif storage == "answer_memory":
            labels = [str(label) for label in task.get("labels", []) if str(label).strip()]
            if not labels:
                labels = [str(task.get("question") or "")]
            for label in labels:
                if label.strip():
                    answer_updates[label] = answer
        else:
            skipped.append(
                {
                    "group_key": task.get("group_key"),
                    "reason": f"unsupported_or_supervised_storage:{storage}",
                }
            )

    if not dry_run:
        if profile_updates:
            profile_answers.update(profile_updates)
            Path(profile_path).write_text(
                json.dumps(profile_payload, ensure_ascii=True, indent=2) + "\n",
                encoding="utf-8",
            )
        if answer_updates:
            learn_answers(
                memory_path,
                {
                    "platform": "learning_template",
                    "company": "Reusable application answers",
                    "title": "Learning task import",
                    "job_id": "learning-task-import",
                },
                answer_updates,
                source=source,
            )
            memory = load_answer_memory(memory_path)

    return {
        "dry_run": dry_run,
        "profile_updates": sorted(profile_updates.keys()),
        "answer_memory_updates": sorted(answer_updates.keys()),
        "skipped": skipped,
        "answer_memory_count": len(memory.get("answers", [])),
    }


def render_learning_task_template_markdown(template: dict[str, Any]) -> str:
    lines = [
        "# Learning Task Template",
        "",
        f"Generated: {template.get('generated_at')}",
        f"Tasks: {template.get('task_count', 0)}",
        "",
        str(template.get("instructions") or ""),
        "",
        "## Tasks",
        "",
    ]
    tasks = template.get("tasks", [])
    if not tasks:
        lines.append("- None")
        return "\n".join(lines) + "\n"

    for task in tasks:
        approved = "x" if task.get("approved") else " "
        lines.append(
            "- [{approved}] {storage}: {question}".format(
                approved=approved,
                storage=task.get("recommended_storage") or "unknown",
                question=task.get("question") or "Unknown question",
            )
        )
        lines.append(f"  group: {task.get('group_key')}")
        if task.get("platforms"):
            lines.append(f"  platforms: {', '.join(str(item) for item in task.get('platforms', []))}")
        if task.get("labels"):
            label_text = "; ".join(str(item) for item in task.get("labels", [])[:5])
            lines.append(f"  labels: {label_text}")
        lines.append(f"  persist_allowed: {str(bool(task.get('persist_allowed'))).lower()}")
        if task.get("notes"):
            lines.append(f"  notes: {task.get('notes')}")
    return "\n".join(lines) + "\n"


def build_synthetic_candidate_profile() -> CandidateProfile:
    return CandidateProfile(
        name="Morgan Test",
        email="morgan.test@example.com",
        phone="555-0100",
        location="Seattle, WA",
        target_titles=[
            "Site Reliability Engineer",
            "Platform Engineer",
            "Infrastructure Engineer",
            "DevOps Engineer",
            "Backend Engineer",
        ],
        target_locations=["United States", "Remote", "Seattle", "Bellevue"],
        remote_ok=True,
        keywords=[
            "python",
            "kubernetes",
            "terraform",
            "aws",
            "azure",
            "gcp",
            "reliability",
            "incident",
            "automation",
            "observability",
            "linux",
            "ci/cd",
        ],
        blocklist=["principal", "staff", "manager"],
        min_score=45,
        resume_facts={
            "professional_summary": (
                "Infrastructure engineer with production reliability, automation, "
                "cloud operations, and incident response experience"
            ),
            "strongest_skills": (
                "Python, Kubernetes, Terraform, AWS, Azure, GCP, Linux, CI/CD, "
                "observability, incident management, and backend infrastructure"
            ),
            "impact_example": (
                "Built automation that reduced manual operations work and improved "
                "incident response for production services"
            ),
            "education": "B.S. Computer Science",
            "cloud_experience": (
                "Hands-on experience operating services on AWS, Azure, and GCP, "
                "with Kubernetes-based infrastructure"
            ),
            "kubernetes_oncall_experience": (
                "Four years of Kubernetes, on-call, incident response, and "
                "production observability experience"
            ),
        },
        question_answers={
            "authorization": "Yes, I am authorized to work in the United States.",
            "sponsorship": "No, I do not require visa sponsorship.",
            "compensation": "$100,000+ base salary, depending on level, location, and total package.",
            "start_date": "Two months after offer acceptance.",
            "relocation": "Yes, I am open to relocation for the right role.",
            "years_experience": "4 years",
            "cloud_provider_general": "I have experience across AWS, Azure, and GCP.",
            "linkedin_profile": "https://www.linkedin.com/in/fake-synthetic-candidate/",
            "resume_path": "/tmp/fake-synthetic-resume.pdf",
        },
    )


def run_synthetic_application_simulation(
    count: int = 100,
    include_values: bool = False,
) -> dict[str, Any]:
    profile = build_synthetic_candidate_profile()
    runs: list[dict[str, Any]] = []
    aggregate_steps: list[dict[str, Any]] = []

    for index in range(1, max(count, 0) + 1):
        snapshot = _build_synthetic_application_snapshot(index)
        closed_phrase = closed_application_phrase({"page_text": snapshot.get("page_text", "")})
        if closed_phrase:
            runs.append(
                {
                    "index": index,
                    "platform": snapshot.get("platform"),
                    "company": snapshot.get("company"),
                    "title": snapshot.get("job_title"),
                    "url": snapshot.get("url"),
                    "status": "closed_skip",
                    "closed_reason": closed_phrase,
                    "real_platform_submission": False,
                }
            )
            continue

        plan = build_form_fill_plan(
            snapshot,
            profile=profile,
            answer_memory=None,
            include_values=include_values,
        )
        missing_statuses = {
            "missing_profile_value",
            "missing_local_material",
            "missing_answer",
            "missing_resume_facts",
        }
        review_statuses = {"needs_human_review", "sensitive_not_stored"}
        security_statuses = {"manual_security_step", "final_submit_confirmation"}
        missing_steps = [
            step for step in plan.get("steps", []) if step.get("status") in missing_statuses
        ]
        review_steps = [
            step for step in plan.get("steps", []) if step.get("status") in review_statuses
        ]
        security_steps = [
            step for step in plan.get("steps", []) if step.get("status") in security_statuses
        ]
        if missing_steps:
            status = "needs_learning"
        elif review_steps or security_steps:
            status = "autofill_ready_with_supervised_gates"
        else:
            status = "autofill_ready"
        aggregate_steps.extend(plan.get("steps", []))
        runs.append(
            {
                "index": index,
                "platform": snapshot.get("platform"),
                "company": snapshot.get("company"),
                "title": snapshot.get("job_title"),
                "url": snapshot.get("url"),
                "status": status,
                "real_platform_submission": False,
                "step_count": plan.get("step_count", 0),
                "ready_step_count": plan.get("status_counts", {}).get("ready", 0),
                "missing_step_count": len(missing_steps),
                "review_gate_count": len(review_steps),
                "security_gate_count": len(security_steps),
                "status_counts": plan.get("status_counts", {}),
                "blocking_labels": [
                    step.get("label")
                    for step in [*missing_steps, *review_steps, *security_steps][:8]
                ],
            }
        )

    status_counts = _count_by(runs, "status")
    platform_counts = _count_by(runs, "platform")
    step_status_counts = _count_by(aggregate_steps, "status")
    step_category_counts = _count_by(aggregate_steps, "category")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "simulation": "offline_synthetic_only",
        "real_platform_submission": False,
        "safety_boundary": (
            "Fake candidate data is used only against local synthetic forms. "
            "The harness never submits fake applications to real employers."
        ),
        "requested_count": count,
        "run_count": len(runs),
        "status_counts": status_counts,
        "platform_counts": platform_counts,
        "step_status_counts": step_status_counts,
        "step_category_counts": step_category_counts,
        "issue_summary": _synthetic_issue_summary(runs, aggregate_steps),
        "runs": runs,
    }


def write_synthetic_application_simulation(
    json_output: str | Path,
    markdown_output: str | Path,
    count: int = 100,
    include_values: bool = False,
) -> dict[str, Any]:
    report = run_synthetic_application_simulation(count=count, include_values=include_values)
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(render_synthetic_application_markdown(report), encoding="utf-8")
    return report


def render_synthetic_application_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Synthetic Application Simulation",
        "",
        f"Generated: {report.get('generated_at')}",
        f"Runs: {report.get('run_count', 0)}",
        f"Mode: {report.get('simulation')}",
        f"Real platform submission: {str(bool(report.get('real_platform_submission'))).lower()}",
        "",
        str(report.get("safety_boundary") or ""),
        "",
        "## Status Counts",
        "",
    ]
    for status, count in sorted(report.get("status_counts", {}).items()):
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## Platform Counts", ""])
    for platform, count in sorted(report.get("platform_counts", {}).items()):
        lines.append(f"- {platform}: {count}")
    lines.extend(["", "## Step Status Counts", ""])
    for status, count in sorted(report.get("step_status_counts", {}).items()):
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## Issues To Handle", ""])
    for issue in report.get("issue_summary", []):
        lines.append(
            "- {status}: {count} occurrence(s); handling: {handling}".format(
                status=issue.get("status"),
                count=issue.get("count", 0),
                handling=issue.get("handling"),
            )
        )
        examples = issue.get("example_labels") or []
        if examples:
            lines.append(f"  examples: {'; '.join(str(item) for item in examples[:5])}")
    lines.extend(["", "## First Runs", ""])
    for run in report.get("runs", [])[:20]:
        lines.append(
            "- {status}: {company} - {title} [{platform}]".format(
                status=run.get("status"),
                company=run.get("company"),
                title=run.get("title"),
                platform=run.get("platform"),
            )
        )
        if run.get("closed_reason"):
            lines.append(f"  closed: {run.get('closed_reason')}")
        blockers = run.get("blocking_labels") or []
        if blockers:
            lines.append(f"  gates: {'; '.join(str(item) for item in blockers[:5])}")
    return "\n".join(lines) + "\n"


def render_application_research_markdown(research: dict[str, Any]) -> str:
    lines = [
        "# Application Research Baseline",
        "",
        f"Generated: {research.get('generated_at')}",
        f"Observed unique positions: {research.get('positions_observed_total', 0)}",
        f"Target per platform: {research.get('position_target_per_platform', 100)}",
        "",
        "## Platform Coverage",
        "",
        "| Platform | Positions | Remaining to target | Prompt items |",
        "| --- | ---: | ---: | ---: |",
    ]
    for platform, payload in sorted(research.get("platforms", {}).items()):
        lines.append(
            "| {platform} | {positions} | {remaining} | {items} |".format(
                platform=platform,
                positions=payload.get("positions_observed", 0),
                remaining=payload.get("positions_remaining_to_target", 0),
                items=payload.get("prompt_items", 0),
            )
        )

    lines.extend(["", "## Website And Role-Type Coverage", ""])
    lines.extend(
        [
            "| Platform | Role type | Positions | Remaining to target |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for payload in sorted(
        research.get("coverage_groups", {}).values(),
        key=lambda item: (str(item.get("platform")), str(item.get("role_family"))),
    ):
        lines.append(
            "| {platform} | {role_family} | {positions} | {remaining} |".format(
                platform=payload.get("platform"),
                role_family=payload.get("role_family"),
                positions=payload.get("positions_observed", 0),
                remaining=payload.get("positions_remaining_to_target", 0),
            )
        )

    lines.extend(["", "## Category Counts", ""])
    for category, count in sorted(research.get("category_counts", {}).items()):
        lines.append(f"- {category}: {count}")

    lines.extend(["", "## Automation Actions", ""])
    for action, count in sorted(research.get("automation_action_counts", {}).items()):
        lines.append(f"- {action}: {count}")

    lines.extend(["", "## Repeated Prompts", ""])
    repeated = research.get("repeated_prompts", [])
    if repeated:
        for prompt in repeated[:20]:
            lines.append(
                f"- {prompt.get('label')} ({prompt.get('count')}x, "
                f"{prompt.get('category')}, {prompt.get('automation_action')})"
            )
    else:
        lines.append("- None yet")

    lines.extend(["", "## Human Review Or Sensitive Items", ""])
    review_items = [
        item
        for item in research.get("items", [])
        if item.get("automation_action") in {"human_review_required", "do_not_store_sensitive"}
    ]
    if review_items:
        for item in review_items[:30]:
            lines.append(
                f"- {item.get('category')}: {item.get('label')} "
                f"[{item.get('platform')}, {item.get('source_file')}]"
            )
    else:
        lines.append("- None detected")

    lines.extend(["", "## Next Collection Gaps", ""])
    for gap in research.get("collection_gaps", []):
        lines.append(f"- {gap}")
    return "\n".join(lines) + "\n"


def render_answer_gap_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Application Answer Gap Report",
        "",
        f"Generated: {report.get('generated_at')}",
        f"Observed positions: {report.get('positions_observed_total', 0)}",
        f"Unique prompts: {report.get('unique_prompts_observed', 0)}",
        f"Ready prompts: {report.get('ready_prompt_count', 0)}",
        f"Blocking prompts: {report.get('blocking_prompt_count', 0)}",
        "",
        "## Coverage Status",
        "",
    ]
    for status, count in sorted(report.get("coverage_counts", {}).items()):
        lines.append(f"- {status}: {count}")

    lines.extend(["", "## Blocking Prompts", ""])
    blocking = report.get("blocking_prompts", [])
    if blocking:
        for item in blocking[:40]:
            lines.append(
                "- {status}: {label} ({category}; {action}; observed {count}x; {platforms})".format(
                    status=item.get("coverage_status"),
                    label=item.get("label"),
                    category=item.get("category"),
                    action=item.get("automation_action"),
                    count=item.get("observed_count", 0),
                    platforms=", ".join(item.get("platforms", [])),
                )
            )
            lines.append(f"  next: {item.get('next_action')}")
    else:
        lines.append("- None")

    lines.extend(["", "## Ready Reusable Prompts", ""])
    ready = [
        item
        for item in report.get("prompt_statuses", [])
        if item.get("coverage_status")
        in {
            "covered_auto_answer",
            "covered_profile",
            "covered_generation",
            "covered_requires_review",
        }
    ]
    if ready:
        for item in ready[:40]:
            lines.append(
                "- {status}: {label} ({source}; observed {count}x)".format(
                    status=item.get("coverage_status"),
                    label=item.get("label"),
                    source=item.get("answer_source") or item.get("coverage_reason"),
                    count=item.get("observed_count", 0),
                )
            )
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def render_position_readiness_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Application Automation Readiness",
        "",
        f"Generated: {report.get('generated_at')}",
        f"Observed positions: {report.get('positions_observed_total', 0)}",
        f"Learning queue items: {report.get('learning_queue_count', 0)}",
        f"Minimal learning tasks: {report.get('minimal_learning_task_count', 0)}",
        f"Manual gate types: {report.get('manual_gate_count', 0)}",
        "",
        "## Position Readiness",
        "",
    ]
    for readiness, count in sorted(report.get("readiness_counts", {}).items()):
        lines.append(f"- {readiness}: {count}")

    lines.extend(["", "## Learning Queue", ""])
    minimal_tasks = report.get("minimal_learning_tasks", [])
    if minimal_tasks:
        lines.append("Minimal tasks to ask/record once:")
        for task in minimal_tasks:
            lines.append(
                "- {storage}: {question} ({count} related prompt(s))".format(
                    storage=task.get("recommended_storage"),
                    question=task.get("question"),
                    count=task.get("related_prompt_count", 0),
                )
            )
        lines.append("")
    learning_queue = report.get("learning_queue", [])
    if learning_queue:
        for item in learning_queue:
            lines.append(
                "- {storage}: {label} ({status}; observed {count}x; {platforms})".format(
                    storage=item.get("recommended_storage"),
                    label=item.get("label"),
                    status=item.get("coverage_status"),
                    count=item.get("observed_count", 0),
                    platforms=", ".join(item.get("platforms", [])),
                )
            )
            lines.append(f"  next: {item.get('next_action')}")
    else:
        lines.append("- None")

    lines.extend(["", "## Manual Gates", ""])
    manual_gates = report.get("manual_gates", [])
    if manual_gates:
        for item in manual_gates:
            lines.append(
                "- {status}: {label} (observed {count}x; {platforms})".format(
                    status=item.get("coverage_status"),
                    label=item.get("label"),
                    count=item.get("observed_count", 0),
                    platforms=", ".join(item.get("platforms", [])),
                )
            )
            lines.append(f"  handling: {item.get('next_action')}")
    else:
        lines.append("- None")

    lines.extend(["", "## Positions", ""])
    for position in report.get("positions", [])[:60]:
        lines.append(
            "- {readiness}: {company} - {title} [{platform}; {role}]".format(
                readiness=position.get("readiness"),
                company=position.get("company") or "Unknown company",
                title=position.get("title") or "Unknown title",
                platform=position.get("platform") or "Unknown",
                role=position.get("role_family") or "Other",
            )
        )
        blockers = position.get("learning_blockers") or []
        if blockers:
            label_text = "; ".join(str(item.get("label")) for item in blockers[:3])
            lines.append(f"  needs: {label_text}")
        gates = position.get("manual_gates") or []
        if gates:
            gate_text = "; ".join(str(item.get("coverage_status")) for item in gates[:3])
            lines.append(f"  manual gates: {gate_text}")
        if position.get("closed_reason"):
            lines.append(f"  closed: {position.get('closed_reason')}")
    return "\n".join(lines) + "\n"


def render_form_fill_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Form Fill Plan",
        "",
        f"Generated: {plan.get('generated_at')}",
        f"Snapshot: {plan.get('snapshot_file', 'unknown')}",
        f"Title: {plan.get('title')}",
        f"URL: {plan.get('url')}",
        f"Steps: {plan.get('step_count', 0)}",
        f"Blocking steps: {plan.get('blocking_step_count', 0)}",
        "",
        "## Status Counts",
        "",
    ]
    for status, count in sorted(plan.get("status_counts", {}).items()):
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## Steps", ""])
    for step in plan.get("steps", []):
        lines.append(
            "- {status}: {action} `{label}` ({source})".format(
                status=step.get("status"),
                action=step.get("action"),
                label=step.get("label"),
                source=step.get("value_source") or step.get("reason"),
            )
        )
        if step.get("next_action"):
            lines.append(f"  next: {step.get('next_action')}")
    return "\n".join(lines) + "\n"


def refresh_closed_jobs_from_live_pages(
    submissions: list[dict[str, Any]],
    closed_jobs_path: str | Path,
    max_checks: int | None = DEFAULT_LIVE_CHECK_LIMIT,
    timeout: float = 15.0,
    fetcher: Any | None = None,
    source: str = "live_http_check",
) -> dict[str, Any]:
    closed_jobs = load_closed_jobs(closed_jobs_path)
    fetch_page = fetcher or fetch_live_page_text
    checks: list[dict[str, Any]] = []
    checked_count = 0
    for submission in submissions:
        if max_checks is not None and max_checks >= 0 and checked_count >= max_checks:
            break
        if is_job_closed(submission, closed_jobs):
            continue
        apply_url = str(submission.get("apply_url") or submission.get("short_apply_url") or "").strip()
        if not apply_url:
            continue
        url = shorten_apply_url(apply_url, submission)
        if not should_live_check_url(url):
            continue
        checked_count += 1
        check = {
            "url": url,
            "company": submission.get("company"),
            "title": submission.get("title"),
            "job_id": submission.get("job_id"),
            "closed": False,
        }
        try:
            page_text = fetch_page(url, timeout)
        except Exception as exc:  # noqa: BLE001 - live checks should not block notification.
            check["error"] = str(exc)
            checks.append(check)
            continue
        phrase = closed_application_phrase({"page_text": page_text})
        if phrase:
            check["closed"] = True
            check["reason"] = phrase
            record_closed_job(
                closed_jobs_path,
                {**submission, "apply_url": url},
                reason=phrase,
                source=source,
            )
            closed_jobs = load_closed_jobs(closed_jobs_path)
        checks.append(check)
    return {"closed_jobs": closed_jobs, "checks": checks}


def fetch_live_page_text(url: str, timeout: float = 15.0, max_bytes: int = 300_000) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(max_bytes).decode("utf-8", "ignore")


def should_live_check_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(str(url))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def load_telegram_config(
    env_path: str | Path | None = None,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    environ = environ or dict(os.environ)
    resolved_env_path = Path(env_path) if env_path else DEFAULT_TELEGRAM_ENV
    file_values: dict[str, str] = {}
    if resolved_env_path.exists():
        file_values = _parse_shell_exports(resolved_env_path.read_text(encoding="utf-8"))

    def value(*keys: str) -> str:
        for key in keys:
            candidate = str(environ.get(key) or file_values.get(key) or "").strip()
            if candidate:
                return candidate
        return ""

    token = value("JOB_APPLY_TELEGRAM_BOT_TOKEN", "SIGNAL_DECK_TELEGRAM_BOT_TOKEN")
    chat_targets: list[str] = []
    for raw in [
        value("JOB_APPLY_TELEGRAM_CHAT_IDS", "SIGNAL_DECK_TELEGRAM_CHAT_IDS"),
        value("JOB_APPLY_TELEGRAM_CHAT_ID", "SIGNAL_DECK_TELEGRAM_CHAT_ID"),
    ]:
        for item in str(raw).replace("\n", ",").split(","):
            item = item.strip()
            if item and item not in chat_targets:
                chat_targets.append(item)

    return {
        "bot_token": token,
        "chat_ids": chat_targets,
        "env_path": str(resolved_env_path),
        "configured": bool(token and chat_targets),
    }


def build_telegram_job_alert(
    submissions: list[dict[str, Any]],
    generated_at: datetime | None = None,
    max_items: int = 5,
    closed_jobs: dict[str, Any] | None = None,
) -> str:
    available_submissions = [
        submission for submission in submissions if not is_job_closed(submission, closed_jobs)
    ]
    now = generated_at or datetime.now(timezone.utc)
    review_count = sum(
        1
        for submission in available_submissions
        if submission.get("safety", {}).get("human_review_required_before_real_submit", True)
    )
    lines = [
        "🚀 Job application drafts are ready",
        f"🕔 Generated: {now.astimezone().strftime('%Y-%m-%d %H:%M %Z')}",
        f"📌 Candidates: {len(available_submissions)}; need review before submit: {review_count}",
    ]
    skipped_closed = len(submissions) - len(available_submissions)
    if skipped_closed:
        lines.append(f"🚫 Skipped closed postings: {skipped_closed}")
    if not available_submissions:
        lines.append("No matched candidates were generated in this run.")
        return "\n".join(lines)

    lines.append("")
    for index, submission in enumerate(available_submissions[: max(max_items, 0)], start=1):
        company = submission.get("company") or "Unknown company"
        title = submission.get("title") or "Unknown role"
        score = submission.get("score")
        mode = submission.get("automation", {}).get("mode", "review")
        lines.append(f"{index}. 🏢 {company} - {title}")
        lines.append(f"   🎯 score={score} | mode={mode}")
        apply_url = str(submission.get("apply_url") or "").strip()
        if apply_url:
            lines.append(f"   🔗 {shorten_apply_url(apply_url, submission)}")
        missing = submission.get("missing_facts") or []
        if missing:
            lines.append(f"   ⚠️ needs fact check: {', '.join(str(item) for item in missing)}")

    if len(available_submissions) > max_items:
        lines.append(f"... {len(available_submissions) - max_items} more in job_apply_agent/outbox")
    lines.append("")
    lines.append("✅ Open Codex to review. Final submit is still manual.")
    return _truncate_telegram_text("\n".join(lines))


def notify_telegram_for_submissions(
    submissions: list[dict[str, Any]],
    env_path: str | Path | None = None,
    dry_run: bool = False,
    closed_jobs: dict[str, Any] | None = None,
    max_items: int = 5,
) -> dict[str, Any]:
    config = load_telegram_config(env_path)
    text = build_telegram_job_alert(submissions, max_items=max_items, closed_jobs=closed_jobs)
    if not config["configured"]:
        return {
            "ok": False,
            "skipped": True,
            "reason": "telegram bot token or chat id is not configured",
            "env_path": config["env_path"],
            "message": text,
        }
    if dry_run:
        return {
            "ok": True,
            "skipped": True,
            "reason": "dry run",
            "chat_count": len(config["chat_ids"]),
            "message": text,
        }
    send_telegram_message(config["bot_token"], config["chat_ids"], text)
    return {
        "ok": True,
        "skipped": False,
        "chat_count": len(config["chat_ids"]),
        "message": text,
    }


def open_apply_urls_in_browser(
    submissions: list[dict[str, Any]],
    max_items: int = 5,
    opener: Any | None = None,
    record_path: str | Path | None = None,
    source: str = "open_browser",
    closed_jobs: dict[str, Any] | None = None,
) -> list[str]:
    open_tab = opener or open_url_in_default_browser
    opened_urls: list[str] = []
    records: list[dict[str, Any]] = []
    opened_at = datetime.now(timezone.utc)
    available_submissions = [
        submission for submission in submissions if not is_job_closed(submission, closed_jobs)
    ]
    for submission in available_submissions[: max(max_items, 0)]:
        apply_url = str(submission.get("apply_url") or "").strip()
        if not apply_url:
            continue
        url = shorten_apply_url(apply_url, submission)
        open_tab(url)
        opened_urls.append(url)
        records.append(build_browser_review_record(submission, url, opened_at, source=source))
    if record_path and records:
        append_browser_review_records(record_path, records)
    return opened_urls


def open_url_in_default_browser(url: str) -> bool:
    if sys.platform == "darwin":
        result = subprocess.run(
            ["open", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    return bool(webbrowser.open_new_tab(url))


def build_browser_review_record(
    submission: dict[str, Any],
    short_apply_url: str,
    opened_at: datetime | None = None,
    source: str = "open_browser",
) -> dict[str, Any]:
    now = opened_at or datetime.now(timezone.utc)
    automation = submission.get("automation") if isinstance(submission.get("automation"), dict) else {}
    return {
        "review_id": str(uuid.uuid4()),
        "opened_at": now.isoformat(),
        "status": "OPENED_FOR_REVIEW",
        "next_action": "human_review_then_apply_or_skip",
        "source": source,
        "real_platform_submission": False,
        "submission_id": submission.get("submission_id"),
        "platform": submission.get("platform"),
        "job_id": submission.get("job_id"),
        "company": submission.get("company"),
        "title": submission.get("title"),
        "score": submission.get("score"),
        "automation_mode": automation.get("mode"),
        "missing_facts": submission.get("missing_facts") or [],
        "short_apply_url": short_apply_url,
    }


def append_browser_review_records(
    path: str | Path,
    records: list[dict[str, Any]],
) -> None:
    review_path = Path(path)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    with review_path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")


def job_registry_key(job: dict[str, Any]) -> str:
    apply_url = str(job.get("apply_url") or job.get("short_apply_url") or "").strip()
    platform = str(job.get("platform") or infer_platform_from_url(apply_url) or "").strip().lower()
    job_id = str(job.get("job_id") or "").strip()
    if not job_id:
        job_id = extract_linkedin_job_id(apply_url)
    if platform == "linkedin" and job_id:
        return f"linkedin:{job_id}"
    if apply_url:
        return f"url:{shorten_apply_url(apply_url, job)}"
    company = _normalize(str(job.get("company", "")))
    title = _normalize(str(job.get("title", "")))
    return f"job:{company}:{title}"


def infer_platform_from_url(url: str) -> str | None:
    host = urllib.parse.urlparse(str(url)).netloc.lower()
    if "linkedin.com" in host:
        return "LinkedIn"
    if "greenhouse.io" in host:
        return "Greenhouse"
    if "ashbyhq.com" in host:
        return "Ashby"
    if "lever.co" in host:
        return "Lever"
    return None


def extract_linkedin_job_id(url: str) -> str:
    match = re.search(r"/jobs/view/(\d+)", str(url))
    return match.group(1) if match else ""


def shorten_apply_url(url: str, submission: dict[str, Any] | None = None) -> str:
    value = str(url).strip()
    if not value:
        return ""
    parsed = urllib.parse.urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return value

    host = parsed.netloc.lower()
    if "linkedin.com" in host:
        job_id = extract_linkedin_job_id(value) or str((submission or {}).get("job_id", "")).strip()
        if job_id and job_id.isdigit():
            return f"https://www.linkedin.com/jobs/view/{job_id}/"

    if any(domain in host for domain in ["greenhouse.io", "ashbyhq.com", "lever.co"]):
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

    tracking_keys = {
        "ebp",
        "gh_src",
        "ref",
        "refid",
        "source",
        "src",
        "trackingid",
        "trk",
    }
    kept_query = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in tracking_keys and not key.lower().startswith("utm_")
    ]
    return urllib.parse.urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            "",
            urllib.parse.urlencode(kept_query),
            "",
        )
    )


def send_telegram_message(
    bot_token: str,
    chat_ids: list[str],
    text: str,
    timeout: float = 10.0,
) -> None:
    errors: list[str] = []
    for chat_id in chat_ids:
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data=data,
            headers={"User-Agent": "job-apply-agent/1.0"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            errors.append(f"{chat_id}: {exc}")
            continue
        if not payload.get("ok"):
            errors.append(f"{chat_id}: {payload}")
    if errors:
        raise RuntimeError("Telegram sendMessage failed: " + " | ".join(errors))


def simulate_submission(
    profile: CandidateProfile,
    draft: ApplicationDraft,
    outbox_path: str | Path,
) -> dict[str, Any]:
    job = draft.job
    submission = {
        "submission_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": True,
        "status": "SIMULATED_SUBMITTED",
        "platform": job.get("platform", "mock"),
        "job_id": job.get("job_id"),
        "title": job.get("title"),
        "company": job.get("company"),
        "apply_url": job.get("apply_url"),
        "score": draft.score.score,
        "score_reasons": draft.score.reasons,
        "applicant": {
            "name": profile.name,
            "email": profile.email,
            "phone": profile.phone,
            "location": profile.location,
        },
        "cover_note": draft.cover_note,
        "answers": draft.answers,
        "missing_facts": draft.missing_facts,
        "answer_sources": draft.answer_sources,
        "automation": draft.automation,
        "safety": {
            "real_platform_submission": False,
            "human_review_required_before_real_submit": not draft.automation.get(
                "ready_for_unattended_submit", False
            ),
        },
    }

    path = Path(outbox_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(submission, ensure_ascii=True, sort_keys=True) + "\n")
    return submission


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _collect_form_snapshot_research(
    path: Path,
    payload: dict[str, Any],
    items: list[dict[str, Any]],
    positions: dict[str, dict[str, Any]],
) -> None:
    position = _register_research_position(path, payload, positions)
    platform = position["platform"]
    company = position.get("company")
    title = position.get("title") or payload.get("title")
    for field in payload.get("fields", []):
        if not isinstance(field, dict):
            continue
        label = _field_prompt_label(field)
        classification = classify_application_prompt(label, field)
        if _skip_low_signal_prompt(label, classification):
            continue
        items.append(
            _research_item(
                path,
                platform,
                company,
                title,
                position["position_key"],
                "field",
                label,
                classification,
                required=bool(field.get("required")),
            )
        )
    for button in payload.get("buttons", []):
        if not isinstance(button, dict):
            continue
        label = _field_prompt_label(button)
        classification = classify_application_prompt(label, {**button, "tag": "BUTTON"})
        if _skip_low_signal_prompt(label, classification):
            continue
        items.append(
            _research_item(
                path,
                platform,
                company,
                title,
                position["position_key"],
                "button",
                label,
                classification,
                required=False,
            )
        )


def _collect_job_question_research(
    path: Path,
    job: dict[str, Any],
    items: list[dict[str, Any]],
    positions: dict[str, dict[str, Any]],
    index: int | None = None,
) -> None:
    position = _register_research_position(path, job, positions, index=index)
    for question in _string_list(job.get("questions")):
        classification = classify_application_prompt(question)
        items.append(
            _research_item(
                path,
                position["platform"],
                position.get("company"),
                position.get("title"),
                position["position_key"],
                "question",
                question,
                classification,
                required=True,
            )
        )


def _collect_submission_question_research(
    path: Path,
    submission: dict[str, Any],
    items: list[dict[str, Any]],
    positions: dict[str, dict[str, Any]],
    index: int | None = None,
) -> None:
    position = _register_research_position(path, submission, positions, index=index)
    questions = list((submission.get("answers") or {}).keys())
    questions.extend(_string_list(submission.get("questions")))
    seen: set[str] = set()
    for question in questions:
        normalized = _normalize_question(question)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        classification = classify_application_prompt(question)
        items.append(
            _research_item(
                path,
                position["platform"],
                position.get("company"),
                position.get("title"),
                position["position_key"],
                "question",
                question,
                classification,
                required=True,
            )
        )


def _register_research_position(
    path: Path,
    payload: dict[str, Any],
    positions: dict[str, dict[str, Any]],
    index: int | None = None,
) -> dict[str, Any]:
    apply_url = str(
        payload.get("apply_url")
        or payload.get("short_apply_url")
        or payload.get("url")
        or ""
    ).strip()
    platform = (
        str(payload.get("platform") or infer_platform_from_url(apply_url) or "").strip()
        or _infer_platform_from_path(path)
    )
    job_id = str(payload.get("job_id") or extract_linkedin_job_id(apply_url)).strip()
    if apply_url:
        position_key = job_registry_key(
            {
                "platform": platform,
                "job_id": job_id,
                "apply_url": apply_url,
                "short_apply_url": payload.get("short_apply_url"),
                "company": payload.get("company"),
                "title": payload.get("title"),
            }
        )
    elif index is not None:
        position_key = f"{path.name}:{index}"
    else:
        position_key = path.name
    record = positions.setdefault(
        position_key,
        {
            "position_key": position_key,
            "platform": platform or "Unknown",
            "job_id": job_id or None,
            "company": payload.get("company"),
            "title": payload.get("title"),
            "role_family": _infer_role_family(str(payload.get("title") or payload.get("title_text") or "")),
            "apply_url": shorten_apply_url(apply_url, payload) if apply_url else None,
            "source_files": [],
        },
    )
    if path.name not in record["source_files"]:
        record["source_files"].append(path.name)
    return record


def _research_item(
    path: Path,
    platform: str,
    company: Any,
    title: Any,
    position_key: str,
    item_type: str,
    label: str,
    classification: ApplicationPromptClassification,
    required: bool,
) -> dict[str, Any]:
    return {
        "source_file": path.name,
        "position_key": position_key,
        "platform": platform or "Unknown",
        "company": company,
        "title": title,
        "item_type": item_type,
        "label": label,
        "normalized_label": _normalize_question(label),
        "required": required,
        "category": classification.category,
        "automation_action": classification.automation_action,
        "sensitivity": classification.sensitivity,
        "classification_reason": classification.reason,
    }


def _summarize_application_research(
    items: list[dict[str, Any]],
    positions: dict[str, dict[str, Any]],
    position_target: int,
) -> dict[str, Any]:
    category_counts = _count_by(items, "category")
    action_counts = _count_by(items, "automation_action")
    platforms: dict[str, dict[str, Any]] = {}
    coverage_groups: dict[str, dict[str, Any]] = {}
    role_families: dict[str, int] = {}
    for position in positions.values():
        platform = str(position.get("platform") or "Unknown")
        role_family = str(position.get("role_family") or "Other")
        role_families[role_family] = role_families.get(role_family, 0) + 1
        payload = platforms.setdefault(
            platform,
            {
                "positions_observed": 0,
                "positions_remaining_to_target": position_target,
                "prompt_items": 0,
            },
        )
        payload["positions_observed"] += 1
        group_key = f"{platform}::{role_family}"
        group = coverage_groups.setdefault(
            group_key,
            {
                "platform": platform,
                "role_family": role_family,
                "positions_observed": 0,
                "positions_remaining_to_target": position_target,
            },
        )
        group["positions_observed"] += 1
    for item in items:
        platform = str(item.get("platform") or "Unknown")
        payload = platforms.setdefault(
            platform,
            {
                "positions_observed": 0,
                "positions_remaining_to_target": position_target,
                "prompt_items": 0,
            },
        )
        payload["prompt_items"] += 1
    for payload in platforms.values():
        payload["positions_remaining_to_target"] = max(
            0,
            position_target - int(payload.get("positions_observed", 0)),
        )
    for payload in coverage_groups.values():
        payload["positions_remaining_to_target"] = max(
            0,
            position_target - int(payload.get("positions_observed", 0)),
        )

    prompt_counts: dict[str, dict[str, Any]] = {}
    for item in items:
        key = str(item.get("normalized_label") or "")
        if not key:
            continue
        entry = prompt_counts.setdefault(
            key,
            {
                "label": item.get("label"),
                "count": 0,
                "category": item.get("category"),
                "automation_action": item.get("automation_action"),
            },
        )
        entry["count"] += 1
    repeated_prompts = sorted(
        prompt_counts.values(),
        key=lambda entry: (-int(entry["count"]), str(entry["label"])),
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "position_target_per_platform": position_target,
        "positions_observed_total": len(positions),
        "platforms": dict(sorted(platforms.items())),
        "coverage_groups": dict(sorted(coverage_groups.items())),
        "role_family_counts": dict(sorted(role_families.items())),
        "category_counts": category_counts,
        "automation_action_counts": action_counts,
        "positions": list(positions.values()),
        "items": items,
        "repeated_prompts": repeated_prompts,
        "collection_gaps": _application_collection_gaps(platforms, position_target),
    }


_LEARNING_BLOCKER_STATUSES = {
    "needs_answer_memory",
    "needs_profile_field",
    "needs_profile_material",
    "needs_resume_facts",
    "needs_user_confirmation",
}
_MANUAL_GATE_STATUSES = {
    "manual_security_step",
    "final_submit_confirmation",
    "sensitive_not_stored",
}
_READY_COVERAGE_STATUSES = {
    "covered_auto_answer",
    "covered_profile",
    "covered_generation",
    "covered_requires_review",
}


def _answer_gap_status(
    prompt: dict[str, Any],
    profile: CandidateProfile | None,
    answer_memory: dict[str, Any] | None,
) -> dict[str, Any]:
    label = str(prompt.get("label") or "")
    category = str(prompt.get("category") or "")
    action = str(prompt.get("automation_action") or "")

    if category == "final_submit":
        return {
            "coverage_status": "final_submit_confirmation",
            "coverage_reason": "final_submit_is_never_unattended_by_default",
            "next_action": "human must approve final submit",
        }
    if action == "do_not_store_sensitive":
        return {
            "coverage_status": "sensitive_not_stored",
            "coverage_reason": "protected_class_or_sensitive_self_identification",
            "next_action": "ask during supervised flow; do not persist answer",
        }
    if action == "manual_security_step":
        return {
            "coverage_status": "manual_security_step",
            "coverage_reason": "captcha_or_security_check",
            "next_action": "stop automation and wait for human security step",
        }

    learned = find_learned_answer(answer_memory, label) if answer_memory else None
    direct = _direct_answer(profile, _normalize(label)) if profile else None
    if action == "auto_answer_from_memory":
        if learned:
            return {
                "coverage_status": "covered_auto_answer",
                "coverage_reason": "answer_memory_match",
                "answer_source": learned.source,
                "next_action": "autofill from approved answer memory",
            }
        if direct:
            return {
                "coverage_status": "covered_auto_answer",
                "coverage_reason": "profile_question_answer",
                "answer_source": "profile.question_answers",
                "next_action": "autofill from profile answer",
            }
        return {
            "coverage_status": "needs_answer_memory",
            "coverage_reason": "standard_question_without_approved_answer",
            "next_action": "ask once, then save approved answer memory",
        }

    if action == "auto_fill_from_profile":
        profile_status = _profile_field_status(category, label, profile)
        if profile_status["covered"]:
            return {
                "coverage_status": "covered_profile",
                "coverage_reason": profile_status["reason"],
                "answer_source": profile_status["source"],
                "next_action": "autofill from profile or local document path",
            }
        return {
            "coverage_status": profile_status["missing_status"],
            "coverage_reason": profile_status["reason"],
            "next_action": profile_status["next_action"],
        }

    if action == "generate_custom_material":
        if _profile_has_generation_facts(profile):
            return {
                "coverage_status": "covered_generation",
                "coverage_reason": "resume_facts_available_for_custom_generation",
                "answer_source": "profile.resume_facts",
                "next_action": "generate customized answer/material before review",
            }
        return {
            "coverage_status": "needs_resume_facts",
            "coverage_reason": "missing_resume_facts_for_custom_generation",
            "next_action": "add resume facts before generating role-specific material",
        }

    if action == "human_review_required":
        if learned:
            return {
                "coverage_status": "covered_requires_review",
                "coverage_reason": "learned_answer_still_requires_review",
                "answer_source": learned.source,
                "next_action": "preselect learned answer and keep human review gate",
            }
        if direct:
            return {
                "coverage_status": "covered_requires_review",
                "coverage_reason": "profile_answer_still_requires_review",
                "answer_source": "profile.question_answers",
                "next_action": "preselect profile answer and keep human review gate",
            }
        return {
            "coverage_status": "needs_user_confirmation",
            "coverage_reason": "employer_specific_policy_or_unclear_prompt",
            "next_action": "ask user during supervised learning and save only if non-sensitive",
        }

    return {
        "coverage_status": "needs_user_confirmation",
        "coverage_reason": "unknown_automation_action",
        "next_action": "inspect prompt in supervised flow",
    }


def _profile_field_status(
    category: str,
    label: str,
    profile: CandidateProfile | None,
) -> dict[str, Any]:
    if not profile:
        return {
            "covered": False,
            "missing_status": "needs_profile_field",
            "reason": "profile_not_loaded",
            "next_action": "load a candidate profile",
        }
    if category == "profile_identity":
        if all([profile.name, profile.email, profile.phone, profile.location]):
            return {"covered": True, "reason": "basic_identity_present", "source": "profile"}
        return {
            "covered": False,
            "missing_status": "needs_profile_field",
            "reason": "missing_basic_identity",
            "next_action": "add name, email, phone, and location to profile",
        }
    if category == "education":
        if profile.resume_facts.get("education"):
            return {"covered": True, "reason": "education_resume_fact_present", "source": "profile.resume_facts.education"}
        return {
            "covered": False,
            "missing_status": "needs_profile_field",
            "reason": "missing_education_fact",
            "next_action": "add education to profile resume_facts",
        }
    if category == "profile_link":
        if _profile_answer_contains_any(profile, ["linkedin", "github", "portfolio", "website"]):
            return {"covered": True, "reason": "profile_link_present", "source": "profile.question_answers"}
        return {
            "covered": False,
            "missing_status": "needs_profile_field",
            "reason": "missing_profile_link",
            "next_action": "add LinkedIn/GitHub/profile URLs to the local profile",
        }
    if category in {"resume_upload", "cover_letter_upload", "file_upload"}:
        if _profile_answer_contains_any(profile, ["resume_path", "resume_file", "resume_pdf"]):
            return {"covered": True, "reason": "resume_file_path_present", "source": "profile.question_answers"}
        return {
            "covered": False,
            "missing_status": "needs_profile_material",
            "reason": "missing_local_resume_or_document_path",
            "next_action": "record the approved resume file path for upload automation",
        }
    return {"covered": True, "reason": "profile_category_assumed_available", "source": "profile"}


def _profile_answer_contains_any(profile: CandidateProfile, keys: list[str]) -> bool:
    searchable = _normalize(
        " ".join(
            [
                *profile.question_answers.keys(),
                *profile.question_answers.values(),
                *profile.resume_facts.keys(),
                *profile.resume_facts.values(),
            ]
        )
    )
    return any(_normalize(key) in searchable for key in keys)


def _profile_has_generation_facts(profile: CandidateProfile | None) -> bool:
    if not profile:
        return False
    required = ["professional_summary", "strongest_skills", "impact_example"]
    return all(str(profile.resume_facts.get(key) or "").strip() for key in required)


def _answer_status_sort_rank(status: str) -> int:
    order = {
        "needs_answer_memory": 0,
        "needs_profile_field": 1,
        "needs_profile_material": 2,
        "needs_resume_facts": 3,
        "needs_user_confirmation": 4,
        "manual_security_step": 5,
        "final_submit_confirmation": 6,
        "sensitive_not_stored": 7,
        "covered_auto_answer": 8,
        "covered_profile": 9,
        "covered_generation": 10,
        "covered_requires_review": 11,
    }
    return order.get(status, 99)


def _form_plan_step(
    field: dict[str, Any],
    label: str,
    classification: ApplicationPromptClassification,
    profile: CandidateProfile | None,
    answer_memory: dict[str, Any] | None,
    include_values: bool,
    item_type: str,
) -> dict[str, Any]:
    base = {
        "item_type": item_type,
        "field_index": field.get("i"),
        "tag": field.get("tag"),
        "type": field.get("type"),
        "name": field.get("name"),
        "id": field.get("id"),
        "label": label,
        "required": bool(field.get("required")),
        "category": classification.category,
        "automation_action": classification.automation_action,
        "sensitivity": classification.sensitivity,
        "classification_reason": classification.reason,
    }
    action = classification.automation_action
    if action == "auto_fill_from_profile":
        source = _profile_value_for_form_field(classification.category, label, profile)
        return _form_value_step(
            base,
            action="upload" if classification.category in {"resume_upload", "file_upload"} else "fill",
            source=source,
            include_values=include_values,
            missing_status=(
                "missing_local_material"
                if classification.category in {"resume_upload", "file_upload"}
                else "missing_profile_value"
            ),
        )
    if action == "auto_answer_from_memory":
        source = _answer_value_for_form_field(label, profile, answer_memory)
        return _form_value_step(
            base,
            action="answer",
            source=source,
            include_values=include_values,
            missing_status="missing_answer",
        )
    if action == "generate_custom_material":
        source = {
            "available": _profile_has_generation_facts(profile),
            "source": "profile.resume_facts",
            "value": "GENERATED_FROM_RESUME_FACTS" if profile else "",
            "reason": "resume_facts_available_for_generation",
        }
        return _form_value_step(
            base,
            action="generate",
            source=source,
            include_values=False,
            missing_status="missing_resume_facts",
        )
    if action == "do_not_store_sensitive":
        return {
            **base,
            "action": "manual_sensitive",
            "status": "sensitive_not_stored",
            "reason": "protected_or_sensitive_self_identification",
            "next_action": "ask during supervised flow and do not persist answer",
        }
    if action == "manual_security_step":
        return {
            **base,
            "action": "manual_security",
            "status": "manual_security_step",
            "reason": "captcha_or_security_check",
            "next_action": "pause automation for user security step",
        }
    if classification.category == "final_submit":
        return {
            **base,
            "action": "submit_gate",
            "status": "final_submit_confirmation",
            "reason": "final_submit_requires_human_confirmation",
            "next_action": "only click after explicit user approval",
        }
    return {
        **base,
        "action": "manual_review",
        "status": "needs_human_review",
        "reason": classification.reason,
        "next_action": "ask once in supervised flow and save only if non-sensitive",
    }


def _form_value_step(
    base: dict[str, Any],
    action: str,
    source: dict[str, Any],
    include_values: bool,
    missing_status: str,
) -> dict[str, Any]:
    if source.get("available"):
        step = {
            **base,
            "action": action,
            "status": "ready",
            "value_source": source.get("source"),
            "reason": source.get("reason"),
        }
        if include_values:
            step["value"] = source.get("value")
        return step
    return {
        **base,
        "action": action,
        "status": missing_status,
        "value_source": source.get("source"),
        "reason": source.get("reason"),
        "next_action": source.get("next_action", "add missing value before automation"),
    }


def _profile_value_for_form_field(
    category: str,
    label: str,
    profile: CandidateProfile | None,
) -> dict[str, Any]:
    if not profile:
        return {
            "available": False,
            "source": "profile",
            "reason": "profile_not_loaded",
            "next_action": "load candidate profile",
        }
    text = _normalize(label)
    if category == "profile_identity":
        if "first name" in text:
            value = profile.name.split()[0] if profile.name else ""
            return _source_value("profile.name.first", value)
        if "last name" in text:
            parts = profile.name.split()
            value = parts[-1] if len(parts) > 1 else ""
            return _source_value("profile.name.last", value)
        if "email" in text:
            return _source_value("profile.email", profile.email)
        if "phone" in text:
            return _source_value("profile.phone", profile.phone)
        if any(term in text for term in ["location", "city", "country", "address"]):
            return _source_value("profile.location", profile.location)
        return _source_value("profile.name", profile.name)
    if category == "education":
        return _source_value("profile.resume_facts.education", profile.resume_facts.get("education", ""))
    if category == "profile_link":
        for key in ["linkedin_profile", "linkedin", "profile_url"]:
            if profile.question_answers.get(key):
                return _source_value(f"profile.question_answers.{key}", profile.question_answers[key])
        return {
            "available": False,
            "source": "profile.question_answers.linkedin_profile",
            "reason": "missing_profile_link",
            "next_action": "add LinkedIn profile URL to profile",
        }
    if category in {"resume_upload", "file_upload", "cover_letter_upload"}:
        for key in ["resume_path", "resume_file", "resume_pdf"]:
            if profile.question_answers.get(key):
                return _source_value(f"profile.question_answers.{key}", profile.question_answers[key])
        return {
            "available": False,
            "source": "profile.question_answers.resume_path",
            "reason": "missing_local_resume_or_document_path",
            "next_action": "record approved local resume path",
        }
    return {"available": False, "source": "profile", "reason": "unsupported_profile_field"}


def _answer_value_for_form_field(
    label: str,
    profile: CandidateProfile | None,
    answer_memory: dict[str, Any] | None,
) -> dict[str, Any]:
    learned = find_learned_answer(answer_memory, label) if answer_memory else None
    if learned:
        return {
            "available": True,
            "source": learned.source,
            "value": learned.answer,
            "reason": "answer_memory_match",
        }
    direct = _direct_answer(profile, _normalize(label)) if profile else None
    if direct:
        return {
            "available": True,
            "source": "profile.question_answers",
            "value": direct,
            "reason": "profile_question_answer",
        }
    return {
        "available": False,
        "source": "answer_memory",
        "reason": "missing_approved_answer",
        "next_action": "ask once and save approved answer",
    }


def _source_value(source: str, value: str) -> dict[str, Any]:
    value = str(value or "").strip()
    return {
        "available": bool(value),
        "source": source,
        "value": value,
        "reason": "source_value_available" if value else "source_value_missing",
    }


def _append_unique_prompt(items: list[dict[str, Any]], prompt: dict[str, Any]) -> None:
    label = str(prompt.get("label") or "")
    status = str(prompt.get("coverage_status") or "")
    if any(
        str(item.get("label") or "") == label
        and str(item.get("coverage_status") or "") == status
        for item in items
    ):
        return
    items.append(prompt)


def _build_learning_queue(answer_gap_report: dict[str, Any]) -> list[dict[str, Any]]:
    queue = [
        _queue_prompt(item)
        for item in answer_gap_report.get("prompt_statuses", [])
        if item.get("coverage_status") in _LEARNING_BLOCKER_STATUSES
    ]
    queue.sort(
        key=lambda item: (
            _learning_storage_rank(str(item.get("recommended_storage"))),
            -int(item.get("required_count") or 0),
            -int(item.get("observed_count") or 0),
            str(item.get("label") or ""),
        )
    )
    return queue


def _build_manual_gate_queue(answer_gap_report: dict[str, Any]) -> list[dict[str, Any]]:
    queue = [
        _queue_prompt(item)
        for item in answer_gap_report.get("prompt_statuses", [])
        if item.get("coverage_status") in _MANUAL_GATE_STATUSES
    ]
    queue.sort(
        key=lambda item: (
            _answer_status_sort_rank(str(item.get("coverage_status"))),
            -int(item.get("observed_count") or 0),
            str(item.get("label") or ""),
        )
    )
    return queue


def _minimal_learning_tasks(learning_queue: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in learning_queue:
        group_key = _minimal_learning_group_key(item)
        task = grouped.setdefault(
            group_key,
            {
                "group_key": group_key,
                "question": _minimal_learning_question(item),
                "recommended_storage": item.get("recommended_storage"),
                "related_prompt_count": 0,
                "observed_count": 0,
                "required_count": 0,
                "platforms": set(),
                "labels": [],
            },
        )
        task["related_prompt_count"] += 1
        task["observed_count"] += int(item.get("observed_count") or 0)
        task["required_count"] += int(item.get("required_count") or 0)
        for platform in item.get("platforms", []):
            task["platforms"].add(str(platform))
        label = str(item.get("label") or "")
        if label and label not in task["labels"]:
            task["labels"].append(label)
    tasks: list[dict[str, Any]] = []
    for task in grouped.values():
        tasks.append(
            {
                **{key: value for key, value in task.items() if key != "platforms"},
                "platforms": sorted(task["platforms"]),
            }
        )
    tasks.sort(
        key=lambda item: (
            _learning_storage_rank(str(item.get("recommended_storage"))),
            -int(item.get("required_count") or 0),
            str(item.get("question") or ""),
        )
    )
    return tasks


def _minimal_learning_group_key(item: dict[str, Any]) -> str:
    status = str(item.get("coverage_status") or "")
    category = str(item.get("category") or "")
    storage = str(item.get("recommended_storage") or "")
    if storage == "local_material" and category in {"resume_upload", "file_upload"}:
        return "local_material:resume_file"
    if storage == "profile" and category == "profile_link":
        return "profile:profile_links"
    if category == "communication_consent":
        return "answer_memory:communication_consent"
    if category == "policy_acknowledgement":
        return "supervised_confirmation:policy_acknowledgement"
    return f"{storage}:{status}:{item.get('normalized_label') or item.get('label')}"


def _minimal_learning_question(item: dict[str, Any]) -> str:
    category = str(item.get("category") or "")
    storage = str(item.get("recommended_storage") or "")
    if storage == "local_material" and category in {"resume_upload", "file_upload"}:
        return "What approved local resume PDF/path should automation upload?"
    if storage == "profile" and category == "profile_link":
        return "What LinkedIn profile URL should automation use?"
    if category == "communication_consent":
        return "For recruiting updates, should automation answer yes or no to SMS/WhatsApp consent?"
    if category == "policy_acknowledgement":
        return "May automation mark applicant privacy acknowledgement after you review the policy?"
    return str(item.get("label") or "")


def _queue_prompt(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": item.get("label"),
        "normalized_label": item.get("normalized_label"),
        "category": item.get("category"),
        "coverage_status": item.get("coverage_status"),
        "observed_count": item.get("observed_count", 0),
        "required_count": item.get("required_count", 0),
        "platforms": item.get("platforms", []),
        "source_files": item.get("source_files", []),
        "recommended_storage": _recommended_storage_for_status(
            str(item.get("coverage_status") or ""),
            str(item.get("category") or ""),
        ),
        "next_action": item.get("next_action"),
    }


def _recommended_storage_for_status(status: str, category: str) -> str:
    if status == "needs_answer_memory":
        return "answer_memory"
    if status == "needs_profile_field":
        return "profile"
    if status == "needs_profile_material":
        return "local_material"
    if status == "needs_resume_facts":
        return "resume_facts"
    if status == "needs_user_confirmation":
        return "answer_memory" if category not in {"policy_acknowledgement"} else "supervised_confirmation"
    if status == "manual_security_step":
        return "do_not_automate"
    if status == "final_submit_confirmation":
        return "supervised_submit_gate"
    if status == "sensitive_not_stored":
        return "do_not_store"
    return "none"


def _learning_storage_rank(storage: str) -> int:
    order = {
        "profile": 0,
        "local_material": 1,
        "resume_facts": 2,
        "answer_memory": 3,
        "supervised_confirmation": 4,
    }
    return order.get(storage, 99)


def _build_synthetic_application_snapshot(index: int) -> dict[str, Any]:
    platforms = ["LinkedIn", "Ashby", "Greenhouse", "Lever"]
    role_titles = [
        "Site Reliability Engineer",
        "Platform Engineer, Kubernetes",
        "Cloud Infrastructure Engineer",
        "DevOps Engineer",
        "Backend Infrastructure Engineer",
    ]
    platform = platforms[(index - 1) % len(platforms)]
    title = role_titles[(index - 1) % len(role_titles)]
    company = f"SyntheticCo {index:03d}"
    base_url = {
        "LinkedIn": "https://www.linkedin.com/jobs/view/",
        "Ashby": "https://jobs.ashbyhq.com/synthetic/",
        "Greenhouse": "https://job-boards.greenhouse.io/synthetic/jobs/",
        "Lever": "https://jobs.lever.co/synthetic/",
    }[platform]
    closed = index % 17 == 0
    fields = [
        {"i": 1, "label": "First Name", "tag": "INPUT", "required": True},
        {"i": 2, "label": "Last Name", "tag": "INPUT", "required": True},
        {"i": 3, "label": "Email", "tag": "INPUT", "required": True},
        {"i": 4, "label": "Phone", "tag": "INPUT", "required": True},
        {"i": 5, "label": "Current Location", "tag": "INPUT", "required": True},
        {"i": 6, "label": "Resume/CV", "tag": "INPUT", "type": "file", "required": True},
        {"i": 7, "label": "LinkedIn Profile", "tag": "INPUT", "required": False},
        {
            "i": 8,
            "label": "Are you legally authorized to work in the United States?",
            "tag": "SELECT",
            "required": True,
        },
        {
            "i": 9,
            "label": "Will you now or in the future require visa sponsorship?",
            "tag": "SELECT",
            "required": True,
        },
        {"i": 10, "label": "Expected compensation", "tag": "INPUT", "required": False},
        {"i": 11, "label": "Available start date", "tag": "INPUT", "required": False},
        {"i": 12, "label": "Are you open to relocation?", "tag": "SELECT", "required": False},
        {
            "i": 13,
            "label": "How many years of Kubernetes production experience do you have?",
            "tag": "INPUT",
            "required": True,
        },
        {
            "i": 14,
            "label": "Describe relevant experience for this role.",
            "tag": "TEXTAREA",
            "required": True,
        },
        {
            "i": 15,
            "label": "Which cloud providers have you used: AWS, Azure, or GCP?",
            "tag": "TEXTAREA",
            "required": False,
        },
    ]
    if platform in {"Greenhouse", "Lever"}:
        fields.extend(
            [
                {
                    "i": 16,
                    "label": "I acknowledge the privacy policy.",
                    "tag": "INPUT",
                    "type": "checkbox",
                    "required": True,
                },
                {
                    "i": 17,
                    "label": "Do you consent to SMS or WhatsApp messages?",
                    "tag": "SELECT",
                    "required": False,
                },
                {"i": 18, "label": "Gender", "tag": "SELECT", "required": False},
                {"i": 19, "label": "Veteran status", "tag": "SELECT", "required": False},
            ]
        )
    if platform == "Ashby":
        fields.append(
            {
                "i": 20,
                "label": "How did you hear about this role?",
                "tag": "INPUT",
                "required": False,
            }
        )
    if index % 5 == 0:
        fields.append({"i": 21, "name": "g-recaptcha-response", "tag": "TEXTAREA"})
    return {
        "title": f"{company} application",
        "company": company,
        "job_title": title,
        "platform": platform,
        "url": f"{base_url}{900000 + index}/",
        "page_text": "No longer accepting applications" if closed else f"Apply for {title}",
        "fields": fields,
        "buttons": [{"i": 99, "text": "Submit application", "tag": "BUTTON"}],
    }


def _synthetic_issue_summary(
    runs: list[dict[str, Any]],
    steps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    step_counts = _count_by(steps, "status")
    handling = {
        "missing_profile_value": "add candidate profile field before browser automation",
        "missing_local_material": "record approved local file path before upload automation",
        "missing_answer": "ask once, save approved non-sensitive answer memory",
        "missing_resume_facts": "add resume facts before custom generation",
        "needs_human_review": "preselect only after supervised learning; keep review gate",
        "sensitive_not_stored": "ask on page each time; do not persist protected-class answer",
        "manual_security_step": "pause for human CAPTCHA/security check",
        "final_submit_confirmation": "never click final submit without explicit approval",
    }
    for status, count in sorted(step_counts.items()):
        if status == "ready":
            continue
        labels = [
            str(step.get("label"))
            for step in steps
            if step.get("status") == status and step.get("label")
        ]
        seen: list[str] = []
        for label in labels:
            if label not in seen:
                seen.append(label)
        issues.append(
            {
                "status": status,
                "count": count,
                "handling": handling.get(status, "inspect in supervised flow"),
                "example_labels": seen[:8],
            }
        )
    closed_count = sum(1 for run in runs if run.get("status") == "closed_skip")
    if closed_count:
        issues.insert(
            0,
            {
                "status": "closed_skip",
                "count": closed_count,
                "handling": "skip and persist in closed registry before notify/open/apply",
                "example_labels": ["No longer accepting applications"],
            },
        )
    return issues


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "Unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _application_collection_gaps(
    platforms: dict[str, dict[str, Any]],
    position_target: int,
) -> list[str]:
    gaps: list[str] = []
    for platform, payload in sorted(platforms.items()):
        remaining = max(0, position_target - int(payload.get("positions_observed", 0)))
        if remaining:
            gaps.append(f"{platform}: collect {remaining} more positions to reach {position_target}")
    if not platforms:
        gaps.append(f"collect {position_target} positions for each target platform")
    return gaps


def _infer_role_family(title: str) -> str:
    text = _normalize(title)
    if "site reliability" in text or re.search(r"\bsre\b", text) or "reliability engineer" in text:
        return "Site Reliability"
    if any(term in text for term in ["platform", "infrastructure", "kubernetes", "ci cd"]):
        return "Platform Infrastructure"
    if any(term in text for term in ["devops", "cloud"]):
        return "Cloud DevOps"
    if any(term in text for term in ["backend", "api", "software engineer"]):
        return "Software Backend"
    if any(term in text for term in ["ai", "ml", "machine learning", "data"]):
        return "Data AI"
    if any(term in text for term in ["system engineer", "systems engineer", "hardware"]):
        return "Systems Hardware"
    return "Other"


def _field_prompt_label(field: dict[str, Any]) -> str:
    for key in ["label", "text", "aria", "placeholder", "name", "id", "type"]:
        value = str(field.get(key) or "").strip()
        if value:
            return re.sub(r"\s+", " ", value)
    return ""


def _skip_low_signal_prompt(
    label: str,
    classification: ApplicationPromptClassification,
) -> bool:
    normalized = _normalize(label)
    return (
        normalized in {"", "select", "select...", "start typing", "search", "application"}
        and classification.category in {"unlabeled_control", "unknown"}
    )


def _infer_platform_from_path(path: Path) -> str:
    name = path.name.lower()
    if "greenhouse" in name or "doordash" in name:
        return "Greenhouse"
    if "ashby" in name or "ramp" in name:
        return "Ashby"
    if "linkedin" in name or "daily_candidates" in name or "browser_review_queue" in name:
        return "LinkedIn"
    return "Unknown"


def _parse_shell_exports(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        try:
            parts = shlex.split(raw_value, comments=False, posix=True)
            value = parts[0] if parts else ""
        except ValueError:
            value = raw_value.strip().strip("'\"")
        values[key] = value
    return values


def _closed_registry_reason(
    job: dict[str, Any],
    closed_jobs: dict[str, Any] | None,
) -> str | None:
    if not closed_jobs:
        return None
    key = job_registry_key(job)
    for entry in closed_jobs.get("jobs", []):
        if not isinstance(entry, dict) or entry.get("key") != key:
            continue
        if str(entry.get("status", "")).upper() != "CLOSED":
            continue
        reason = _normalize(str(entry.get("reason", "closed"))) or "closed"
        return f"closed:{reason.replace(' ', '_')}"
    return None


def _truncate_telegram_text(text: str, limit: int = 3900) -> str:
    if len(text) <= limit:
        return text
    suffix = "\n\n[truncated; see job_apply_agent/outbox]"
    return text[: max(0, limit - len(suffix))].rstrip() + suffix


def _direct_answer(profile: CandidateProfile, normalized_question: str) -> str | None:
    for key, answer in profile.question_answers.items():
        key_text = _normalize(key)
        if key_text and key_text in normalized_question:
            return answer

    if (
        ("year" in normalized_question or "years" in normalized_question)
        and "experience" in normalized_question
    ):
        answer = profile.question_answers.get("years_experience")
        if answer:
            return answer

    answer_map = {
        "authorization": ["authorized", "authorization", "work in the united states"],
        "sponsorship": ["sponsor", "sponsorship", "visa"],
        "compensation": ["salary", "compensation", "pay"],
        "start_date": ["start", "available", "availability"],
        "relocation": ["relocat"],
        "cloud_provider_general": ["gcp aws azure", "cloud provider", "cloud providers"],
    }
    for answer_key, hints in answer_map.items():
        answer = profile.question_answers.get(answer_key)
        if answer and any(hint in normalized_question for hint in hints):
            return answer
    return None


def _is_remote(job: dict[str, Any]) -> bool:
    location = _normalize(str(job.get("location", "")))
    workplace_type = _normalize(str(job.get("workplace_type", "")))
    return "remote" in location or "remote" in workplace_type


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def _flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value)
    return str(value)


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _clean_sentence(value: str) -> str:
    return str(value).strip().rstrip(".")


def _normalize_question(value: str) -> str:
    normalized = _normalize(value)
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "do",
        "does",
        "for",
        "have",
        "in",
        "is",
        "of",
        "or",
        "please",
        "the",
        "this",
        "to",
        "with",
        "you",
        "your",
    }
    return " ".join(token for token in normalized.split() if token not in stopwords)


def _has_sensitive_or_unclear_question(answers: dict[str, str]) -> bool:
    sensitive_terms = [
        "PLACEHOLDER",
        "should not claim",
        "should be verified",
        "until this is verified",
        "exact",
    ]
    return any(
        any(term.lower() in answer.lower() for term in sensitive_terms)
        for answer in answers.values()
    )


def _token_overlap(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens)
