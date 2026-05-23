from __future__ import annotations

import json
import base64
import html
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
import zipfile
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
    "no longer accepting new applications",
    "no longer accepting applicants",
    "no longer accepting candidates",
    "no longer accepting resumes",
    "not accepting applications",
    "applications for this job are no longer being accepted",
    "applications are closed",
    "application window is closed",
    "application period is closed",
    "this job posting has expired",
    "this job post is no longer active",
    "job is no longer available",
    "this job is no longer available",
    "this position is no longer available",
    "this role is no longer available",
    "position has been filled",
    "this position has been filled",
    "posting has expired",
    "listing has expired",
]
_CLOSED_APPLICATION_PATTERN_SPECS = [
    (
        "no longer accepting applications",
        r"\b(?:we are |we re |we're )?no longer accepting (?:new )?"
        r"(?:applications|applicants|candidates|resumes)\b",
    ),
    (
        "applications are closed",
        r"\bapplications?(?: for (?:this|the) (?:job|role|position))? "
        r"(?:are|is) (?:now )?closed\b",
    ),
    (
        "job is no longer available",
        r"\b(?:job|posting|position|role|listing|opportunity|job post).{0,8}"
        r"no longer (?:available|active|open)\b",
    ),
    (
        "posting has expired",
        r"\b(?:posting|post|listing|job|role|position) (?:has )?expired\b",
    ),
    (
        "position has been filled",
        r"\b(?:this )?(?:position|role|job) (?:has been|was) filled\b",
    ),
]
_CLOSED_APPLICATION_PATTERNS = [
    (phrase, re.compile(pattern)) for phrase, pattern in _CLOSED_APPLICATION_PATTERN_SPECS
]
DEFAULT_LIVE_CHECK_LIMIT = 25
SYNTHETIC_APPLICATION_PLATFORMS = ["LinkedIn", "Ashby", "Greenhouse", "Lever"]
SYNTHETIC_APPLICATION_ROLE_TITLES = [
    "Site Reliability Engineer",
    "Platform Engineer, Kubernetes",
    "Cloud Infrastructure Engineer",
    "DevOps Engineer",
    "Backend Software Engineer",
]
LOCAL_BROWSER_EXECUTION_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


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
class ClosedApplicationMatch:
    phrase: str
    reason: str
    source_field: str
    snippet: str


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


_CATEGORY_DEFAULT_POLICY_CATEGORIES = {
    "background_or_export_control",
    "citizenship_status",
    "conflict_of_interest",
    "country_work_permit",
    "device_policy",
    "employment_history",
    "government_employment",
    "health_requirement",
    "interview_recording_consent",
    "language_ability",
    "location_constraint",
    "professional_license",
    "schedule_constraint",
    "security_clearance",
}


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


def _learn_category_default_policy(
    memory: dict[str, Any],
    category: str,
    answer: str,
    sample_question: str,
    source: str,
) -> None:
    category = str(category or "").strip()
    answer = str(answer or "").strip()
    if category not in _CATEGORY_DEFAULT_POLICY_CATEGORIES or not answer:
        return
    now = datetime.now(timezone.utc).isoformat()
    entries = memory.setdefault("answers", [])
    group_key = f"answer_memory:{category}:default_policy"
    existing = next(
        (
            entry
            for entry in entries
            if entry.get("match_scope") == "category_default_policy"
            and entry.get("category") == category
            and entry.get("answer") == answer
        ),
        None,
    )
    if existing:
        existing["approved_count"] = int(existing.get("approved_count", 0)) + 1
        existing["last_seen_at"] = now
        existing["source"] = source
        return
    entries.append(
        {
            "normalized_question": f"category default policy {category}",
            "sample_question": sample_question,
            "answer": answer,
            "approved_count": 1,
            "source": source,
            "first_seen_at": now,
            "last_seen_at": now,
            "match_scope": "category_default_policy",
            "category": category,
            "group_key": group_key,
        }
    )


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
    match = closed_application_match(job)
    if match:
        return match.reason
    return None


def closed_application_phrase(job: dict[str, Any]) -> str | None:
    match = closed_application_match(job)
    return match.phrase if match else None


def closed_application_match(job: dict[str, Any]) -> ClosedApplicationMatch | None:
    for source_field, text in _closed_application_search_fields(job):
        match = _closed_application_match_text(text, source_field)
        if match:
            return match
    return None


def _closed_fetch_error_phrase(exc: Exception) -> str:
    status_code = getattr(exc, "code", None)
    if status_code in {404, 410}:
        reason = str(getattr(exc, "reason", "") or "").strip()
        return f"HTTP {status_code} {reason}".strip()
    match = re.search(r"\bHTTP Error (404|410)\b(?::\s*([^:]+))?", str(exc), flags=re.IGNORECASE)
    if match:
        reason = (match.group(2) or "").strip()
        return f"HTTP {match.group(1)} {reason}".strip()
    return ""


def _closed_application_match_text(text: str, source_field: str) -> ClosedApplicationMatch | None:
    normalized_text = _normalize(text)
    if not normalized_text:
        return None
    for phrase in CLOSED_APPLICATION_PHRASES:
        normalized_phrase = _normalize(phrase)
        if normalized_phrase and normalized_phrase in normalized_text:
            return ClosedApplicationMatch(
                phrase=phrase,
                reason=f"closed:{normalized_phrase.replace(' ', '_')}",
                source_field=source_field,
                snippet=_closed_application_snippet(text, phrase),
            )
    for phrase, pattern in _CLOSED_APPLICATION_PATTERNS:
        regex_match = pattern.search(normalized_text)
        if regex_match:
            return ClosedApplicationMatch(
                phrase=phrase,
                reason=f"closed:{_normalize(phrase).replace(' ', '_')}",
                source_field=source_field,
                snippet=_closed_application_snippet(text, phrase, normalized_span=regex_match.span()),
            )
    return None


def _closed_application_search_fields(job: dict[str, Any]) -> list[tuple[str, str]]:
    preferred_fields = [
        "page_text",
        "rendered_text",
        "visible_text",
        "page_excerpt",
        "description",
        "status",
        "title",
    ]
    fields: list[tuple[str, str]] = []
    seen: set[str] = set()
    for field in preferred_fields:
        value = job.get(field)
        if value is None:
            continue
        text = _flatten_text(value)
        if text and text not in seen:
            fields.append((field, text))
            seen.add(text)
    fallback = _flatten_text(job)
    if fallback and fallback not in seen:
        fields.append(("payload", fallback))
    return fields


def _closed_application_snippet(
    text: str,
    phrase: str,
    normalized_span: tuple[int, int] | None = None,
) -> str:
    compact = re.sub(r"\s+", " ", str(text)).strip()
    if not compact:
        return ""
    lowered = compact.lower()
    phrase_index = lowered.find(str(phrase).lower())
    if phrase_index >= 0:
        start = max(0, phrase_index - 90)
        end = min(len(compact), phrase_index + len(phrase) + 90)
        return compact[start:end]
    if normalized_span is not None:
        normalized_text = _normalize(compact)
        target = normalized_text[normalized_span[0] : normalized_span[1]]
        target_words = [
            word
            for word in target.split()
            if len(word) > 2 and word not in {"the", "this", "that", "has", "been", "are", "was"}
        ]
        if target_words:
            for first_match in re.finditer(re.escape(target_words[0]), lowered):
                window_start = max(0, first_match.start() - 90)
                window_end = min(len(compact), first_match.start() + 260)
                window = lowered[window_start:window_end]
                if all(word in window for word in target_words):
                    return compact[window_start:window_end]
    return compact[:220]


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
        if entry.get("match_scope") == "category_default_policy":
            continue
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
    category_policy = _find_category_default_policy(answer_memory, question)
    if category_policy:
        return category_policy
    if best_entry and best_overlap >= 0.78:
        return AnswerMemoryMatch(
            answer=str(best_entry.get("answer", "")),
            confidence=best_overlap,
            source=f"learned_similar:{best_entry.get('source', 'manual')}",
        )
    return None


def _find_category_default_policy(
    answer_memory: dict[str, Any],
    question: str,
) -> AnswerMemoryMatch | None:
    classification = classify_application_prompt(question)
    category = classification.category
    if category not in _CATEGORY_DEFAULT_POLICY_CATEGORIES:
        return None
    if classification.automation_action in {
        "manual_security_step",
        "do_not_store_sensitive",
    } or category == "final_submit":
        return None
    return _find_category_default_policy_for_category(answer_memory, category)


def _find_category_default_policy_for_category(
    answer_memory: dict[str, Any] | None,
    category: str,
) -> AnswerMemoryMatch | None:
    if not answer_memory or category not in _CATEGORY_DEFAULT_POLICY_CATEGORIES:
        return None
    best_entry: dict[str, Any] | None = None
    best_count = -1
    for entry in answer_memory.get("answers", []):
        if (
            entry.get("match_scope") != "category_default_policy"
            or entry.get("category") != category
            or not str(entry.get("answer") or "").strip()
        ):
            continue
        approved_count = int(entry.get("approved_count") or 0)
        if approved_count > best_count:
            best_count = approved_count
            best_entry = entry
    if not best_entry:
        return None
    approved_count = max(int(best_entry.get("approved_count", 0)), 1)
    return AnswerMemoryMatch(
        answer=str(best_entry.get("answer", "")),
        confidence=min(0.9, 0.7 + approved_count * 0.02),
        source=f"learned_category_policy:{best_entry.get('source', 'manual')}",
    )


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

    if (
        "skill" in normalized_question
        or "technology" in normalized_question
        or "programming language" in normalized_question
        or "programming languages" in normalized_question
        or "open source technologies" in normalized_question
    ):
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
    if (tag == "BUTTON" or raw_label in {"submit", "submit application", "apply", "apply now"}) and any(
        term in text for term in ["submit", "apply"]
    ):
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
            "nationality",
            "national origin",
            "sexual orientation",
            "transgender",
            "pronoun",
            "preferred pronouns",
            "ey/em",
            "ey em",
            "fae/faer",
            "fae faer",
            "he him",
            "she her",
            "they them",
            "xe xem",
            "ze hir",
            "current age",
            "age range",
            "date of birth",
            "birthdate",
            "communities do you belong",
            "i identify as",
            "identify as indigenous",
            "ethnic group",
            "lgbtq",
            "lgbtqqia",
            "coordination/dexterity impairment",
            "coordination dexterity impairment",
            "hearing impairment",
            "mobility impairment",
            "speech impairment",
            "psychiatric/mental illness",
            "psychiatric mental illness",
            "non-visible physical impairment",
            "non visible physical impairment",
            "ongoing medical condition",
            "developmental impairment",
            "down’s syndrome",
            "down's syndrome",
            "served in the military",
            "g nero",
            "qual g nero",
            "defici",
            "condi o voc se identifica",
            "condi o voce se identifica",
            "auditiva",
            "cognitiva",
            "intelectual",
            "f sica motora",
            "fisica motora",
            "visual",
            "black or african american",
            "female",
            "male",
            "middle eastern or north african",
            "native hawaiian",
            "pacific islander",
            "non binary",
            "asian",
            "indigenous peoples",
            "native american",
            "alaska native",
        ]
    ) or raw_label in {
        "amarela",
        "arab",
        "asian",
        "branca",
        "black",
        "black or african american",
        "indigenous peoples first nations native american or alaska native",
        "filipino",
        "first nations",
        "female",
        "he him",
        "she her",
        "they them",
        "hir hir",
        "hu hu",
        "ind gena",
        "indigena",
        "inuk inuit",
        "latin american",
        "male",
        "middle eastern or north african",
        "native hawaiian or other pacific islander",
        "non binary",
        "parda",
        "preta",
        "prefiro n o revelar",
        "south asian",
        "southeast asian",
        "west asian",
        "white",
    }:
        return ApplicationPromptClassification(
            "eeoc_sensitive",
            "do_not_store_sensitive",
            "protected_class",
            "protected_class_self_identification",
        )
    if (
        (field_type == "file" and any(term in text for term in ["resume", "cv", "autofill"]))
        or ("resume" in text and "cover letter" not in text)
        or ("cv" in text and "cover letter" not in text)
    ) or raw_label in {
        "resume",
        "resume cv",
        "cv resume",
        "curriculum vitae",
    }:
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
    if any(
        term in text
        for term in [
            "legally authorized",
            "authorized to work",
            "work authorization",
            "work eligibility status",
            "eligible to work",
            "legal right to work",
            "authorization to work",
        ]
    ):
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
    if any(
        term in text
        for term in [
            "work permit",
            "working permit",
            "permit to work",
            "right to work in the uk",
            "right to work in uk",
            "legally allowed to work in canada",
            "legally entitled to work in canada",
            "legally entitled to work in australia",
            "right to live and work in singapore",
            "legally work and live in the uae",
            "work and live in the uae",
            "basis of your working rights",
        ]
    ):
        return ApplicationPromptClassification(
            "country_work_permit",
            "human_review_required",
            "work_eligibility",
            "country_specific_work_permit_requires_confirmation",
        )
    if any(
        term in text
        for term in [
            "u s citizen",
            "us citizen",
            "u.s. citizen",
            "u s person",
            "us person",
            "u.s. person",
            "lawful permanent resident",
            "permanent resident",
            "green card",
            "citizenship",
        ]
    ):
        return ApplicationPromptClassification(
            "citizenship_status",
            "human_review_required",
            "work_eligibility",
            "citizenship_or_residency_requires_confirmation",
        )
    if any(
        term in text
        for term in [
            "security clearance",
            "clearance level",
            "dod clearance",
            "active clearance",
            "clearance question",
            "active security question",
            "clearance you hold",
            "scif",
            "secure government facility",
        ]
    ):
        return ApplicationPromptClassification(
            "security_clearance",
            "human_review_required",
            "work_eligibility",
            "security_clearance_requires_confirmation",
        )
    if any(
        term in text
        for term in [
            "deemed export",
            "export control",
            "export controls",
            "export license",
            "ear controlled",
            "alien illegally",
            "alien unlawfully",
            "fugitive from justice",
            "unlawful user",
            "controlled substance",
            "under indictment",
            "court order",
            "background check",
            "military protection order",
            "debarred",
            "suspended",
            "proposed for debarment",
            "layoff status",
            "subject to recall",
            "federal firearms licensee",
            "firearms licensee",
            "mental defective",
            "committed to a mental institution",
            "charged or convicted",
            "misdemeanor",
            "felony",
            "domestic violence",
            "dishonorable conditions",
        ]
    ):
        return ApplicationPromptClassification(
            "background_or_export_control",
            "human_review_required",
            "legal",
            "background_or_export_control_requires_confirmation",
        )
    if any(term in text for term in ["current ctc", "current compensation"]):
        return ApplicationPromptClassification(
            "current_compensation",
            "human_review_required",
            "compensation",
            "current_compensation_requires_confirmation",
        )
    if any(
        term in text
        for term in ["compensation", "salary", "pay range", "base pay", "combien tu vas gagner"]
    ):
        return ApplicationPromptClassification(
            "compensation",
            "auto_answer_from_memory",
            "standard_preference",
            "standard_compensation_answer",
        )
    if "expected ctc" in text:
        return ApplicationPromptClassification(
            "compensation",
            "auto_answer_from_memory",
            "standard_preference",
            "standard_compensation_answer",
        )
    if raw_label == "currency" or "preferred currency" in text:
        return ApplicationPromptClassification(
            "compensation_currency",
            "auto_answer_from_memory",
            "standard_preference",
            "standard_compensation_currency_answer",
        )
    if any(term in text for term in ["18 years of age", "18 or older", "at least 18"]):
        return ApplicationPromptClassification(
            "legal_age",
            "auto_answer_from_memory",
            "standard_preference",
            "minimum_work_age_answer",
        )
    if "did ai complete this application" in text or "ai complete this application" in text:
        return ApplicationPromptClassification(
            "ai_application_disclosure",
            "auto_answer_from_memory",
            "disclosure",
            "ai_assistance_disclosure_answer",
        )
    if any(
        term in text
        for term in [
            "start date",
            "available to start",
            "can you start",
            "how soon are you able to commence",
            "able to commence",
            "commence in this role",
            "notice period",
            "availability",
            "when would you like to hear back",
            "actively looking for a job",
            "future opportunities",
        ]
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
    if any(term in text for term in ["remote friendly", "remote-friendly", "remote work"]):
        return ApplicationPromptClassification(
            "remote_preference",
            "auto_answer_from_memory",
            "standard_preference",
            "standard_remote_preference_answer",
        )
    if any(
        term in text
        for term in [
            "remote state",
            "state will you work",
            "work remotely from",
            "if you are based in the u s please provide your zipcode",
            "if you are based in the us please provide your zipcode",
            "remote friendly",
            "remote-friendly",
            "time zone",
            "timezone",
            "current location",
            "currently located",
            "presently located",
            "where currently based",
            "where are you currently based",
            "where are you based",
            "based in the us",
            "based in the united states",
            "currently based in the united states",
            "currently based in the us",
            "located in the united states",
            "are you based in the us",
            "are you based in the united states",
            "currently reside",
            "region do you reside",
            "state province",
            "contact number",
            "zip code",
            "zipcode",
            "postal code",
            "please select your state",
            "what state do you currently live in",
            "where do you currently live",
            "do you live in",
        ]
    ) or raw_label in {"state", "country", "city", "contact number"}:
        return ApplicationPromptClassification(
            "profile_identity",
            "auto_fill_from_profile",
            "profile",
            "location_or_timezone_profile_field",
        )
    if any(
        term in text
        for term in [
            "most recent employer",
            "current employer",
            "current company",
            "current or last company",
            "last company",
            "company name",
            "company and position",
            "company position",
            "title held",
            "current title",
            "current role",
            "job title",
            "previous employer",
        ]
    ) or raw_label in {"title", "title 0", "current role", "current role 0", "job title"}:
        return ApplicationPromptClassification(
            "employment_history",
            "auto_fill_from_profile",
            "resume_fact",
            "employment_history_profile_field",
        )
    if any(
        term in text
        for term in [
            "start date month",
            "start date year",
            "end date month",
            "end date year",
            "end month",
            "end year",
            "employment dates",
        ]
    ):
        return ApplicationPromptClassification(
            "employment_dates",
            "auto_fill_from_profile",
            "resume_fact",
            "employment_date_profile_field",
        )
    if any(term in text for term in ["when do you graduate", "graduation date", "graduate date"]):
        return ApplicationPromptClassification(
            "education_date",
            "auto_fill_from_profile",
            "resume_fact",
            "education_date_profile_field",
        )
    if (
        "privacy" in text
        or "acknowledgement" in text
        or "acknowledgment" in text
        or "acknowledged" in text
        or "terms conditions" in text
        or "terms and conditions" in text
        or "certify the information provided" in text
        or "accurate and true" in text
        or "candidate privacy policy" in text
        or "california consumer privacy act" in text
        or "processed in accordance" in text
        or "consider me for other job opportunities" in text
        or "contact you about job opportunities" in text
        or "candidate personal data disclosure" in text
        or "personal data disclosure" in text
        or "use the information submitted" in text
        or "12 month contract" in text
        or "confirm your understanding" in text
        or "questions below are intended for u s based applicants only and are voluntary" in text
        or raw_label in {"acknowledge", "acknowledged"}
        or "personal information retained" in text
        or "consenting to the use of ai" in text
        or "ai for evaluating my candidacy" in text
        or "has my consent to contact me about future job opportunities" in text
    ):
        return ApplicationPromptClassification(
            "policy_acknowledgement",
            "human_review_required",
            "policy",
            "policy_acknowledgement_requires_review",
        )
    if re.search(r"\b(?:sms|whatsapp)\b", text) or "text message" in text or "future contact consent" in text:
        return ApplicationPromptClassification(
            "communication_consent",
            "auto_answer_from_memory",
            "consent",
            "optional_communication_consent",
        )
    if ("year" in text or "years" in text) and ("experience" in text or "expertise" in text):
        return ApplicationPromptClassification(
            "experience_years",
            "auto_answer_from_memory",
            "standard_preference",
            "standard_years_experience_answer",
        )
    if "for how many years" in text and any(term in text for term in ["cloud", "infrastructure"]):
        return ApplicationPromptClassification(
            "experience_years",
            "auto_answer_from_memory",
            "standard_preference",
            "standard_years_experience_answer",
        )
    if any(
        term in text
        for term in [
            "current or former direct employee of any government",
            "government civilian or military employee",
            "government employment",
            "federal government",
            "foreign government",
            "united nations employee",
            "armed services",
            "u s armed services",
        ]
    ):
        return ApplicationPromptClassification(
            "government_employment",
            "human_review_required",
            "policy",
            "government_employment_requires_confirmation",
        )
    if any(term in text for term in ["medical license", "professional license"]):
        return ApplicationPromptClassification(
            "professional_license",
            "human_review_required",
            "credential",
            "professional_license_requires_confirmation",
        )
    if any(
        term in text
        for term in [
            "know anyone currently",
            "outside employment",
            "outside activity",
            "related to anyone",
            "related e g family",
            "close friend",
            "close personal relationship",
            "personal relationship",
            "business relationship",
            "familial relationship",
            "familial relationships",
            "relative employed",
            "relative that s currently employed",
            "relatives currently working",
            "relative that works",
            "family member",
            "romantic partner",
            "friends or family",
            "connection to anyone",
            "connection at perk",
            "referred you",
            "someone referred you",
            "were you referred",
            "currently working with any of the following companies",
            "work concurrently",
            "competes with",
            "non compete",
            "non-compete",
            "employment agreement",
            "government official",
            "state-owned enterprise",
            "commercial contracts",
            "bound by",
            "conflict of interest",
        ]
    ):
        return ApplicationPromptClassification(
            "conflict_of_interest",
            "human_review_required",
            "policy",
            "conflict_or_relationship_requires_confirmation",
        )
    if any(term in text for term in ["record and analyze your interview", "may we record", "record your interview"]):
        return ApplicationPromptClassification(
            "interview_recording_consent",
            "human_review_required",
            "consent",
            "interview_recording_requires_confirmation",
        )
    if any(
        term in text
        for term in [
            "gemini notetaker",
            "metaview",
            "transcribe conversations",
            "notetaker during interviews",
            "ai notetaking",
            "records notes during interviews",
        ]
    ):
        return ApplicationPromptClassification(
            "interview_recording_consent",
            "human_review_required",
            "consent",
            "interview_recording_requires_confirmation",
        )
    if any(term in text for term in ["vaccinated against covid", "fully vaccinated"]):
        return ApplicationPromptClassification(
            "health_requirement",
            "human_review_required",
            "health",
            "health_or_vaccination_requirement_requires_confirmation",
        )
    if any(term in text for term in ["full-time internship", "approximately 7:00am", "accommodate this schedule"]):
        return ApplicationPromptClassification(
            "schedule_constraint",
            "human_review_required",
            "candidate_preference",
            "fixed_schedule_requires_confirmation",
        )
    if any(
        term in text
        for term in [
            "experience working in fintech",
            "financial companies",
            "financial services",
            "nation state level adversaries",
            "dedicated sre or infrastructure team",
            "sre or infrastructure team",
            "strong proficiency in python",
            "automation and tooling for ml workflows",
            "ci cd systems",
            "model delivery",
            "systems-level or database performance tuning",
            "systems level or database performance tuning",
            "system-level software",
            "system level software",
            "device connectivity",
            "dhcp",
            "dns",
            "power over ethernet",
            "product security experience",
            "functional and nonfunctional automated test suites",
            "physical debugging tools",
            "serial consoles",
            "debug cables",
            "core data models",
            "dbt",
            "cloud data warehouse",
            "linux command-line tools",
            "linux command line tools",
            "soc or incident response",
            "security events",
            "software vulnerabilities",
            "crowdstrike falcon",
            "experience working on our platform",
            "hands-on experience with clickhouse",
            "hands on experience with clickhouse",
            "olap",
            "dbaas",
            "blockchain",
            "crypto experience",
            "proprietary trading",
            "telecommunications or wireless",
            "ad tech",
            "digital media background",
            "enterprise-level customers",
            "technical support engineer experience",
            "enterprise level customers",
            "reliability engineering experience related to clickhouse",
            "solution architect for databases",
            "fedramp high",
            "dod il5",
            "fedramp",
            "embedded device",
            "hardware software co-design",
            "hardware–software co-design",
            "linux kernel development",
            "kernel debugging",
            "kernel patches",
            "device drivers",
            "yocto",
            "low-level hardware protocols",
            "spi",
            "i2c",
            "uart",
            "usb",
            "windows software in c++",
            "windows apis",
            "windows services",
            "tested database performance",
            "hands on experience with go or c",
            "hands-on experience with go or c",
            "prior experience working in a highly regulated industry",
            "saas software as a service",
            "software as a service company",
            "adtech",
        ]
    ):
        return ApplicationPromptClassification(
            "domain_experience",
            "human_review_required",
            "resume_fact",
            "domain_or_tool_experience_requires_confirmation",
        )
    if any(
        term in text
        for term in [
            "aws",
            "azure",
            "gcp",
            "google cloud",
            "kubernetes",
            "terraform",
            "open source technologies",
            "programming language",
            "programming languages",
            "application programming",
            "python programming",
            "experience proficiency with python",
            "overall experience proficiency with python",
            "strong programmer",
            "familiarity with golang",
            "golang",
            "go or python",
            "c#",
            ".net",
            ".net technology",
            "jira",
            "react ecosystem",
            "vite",
            "tailwind",
            "tanstack",
            "frontend development",
            "high-performance uis",
            "high performance uis",
            "data-intensive",
            "data intensive",
            "genai",
            "ai agentic systems",
            "ai-assisted development",
            "ai assisted development",
            "application security",
            "security practices",
            "authentication and authorization",
            "sso",
            "active directory",
            "web3",
            "ci/cd",
            "cicd",
            "bgp",
            "ospf",
            "dynamic routing",
            "distributed systems",
            "microservices",
            "restful apis",
            "restful api",
            "apis",
            "api, sdk",
            "sdk",
            "vulnerability management",
            "load balancing",
            "cloud platforms",
            "linux administration",
            "linux security",
            "linux system performs slow",
            "linux command-line",
            "system-level software",
            "design patterns",
            "automated test frameworks",
            "test frameworks",
            "test automation",
            "qa methodologies",
            "devops",
            "technical people manager",
            "oncall",
            "on-call",
            "observability",
            "prometheus",
            "production system",
            "production-quality code",
            "production quality code",
            "production software engineering",
            "production environment",
            "real-time data systems",
            "near real-time data systems",
            "required work experience",
            "meet the qualifications",
            "migrations have you completed",
            "integrate a platform",
            "third-party platforms",
            "third party platforms",
            "code you re proud",
            "coding languages",
            "technical coding capabilities",
            "interviews in react",
            "interviews in swift",
            "command skills with linux shell",
            "powershell",
            "knobs/visibility/alerting",
            "visibility alerting",
            "scalably operate complex systems",
            "deploying content to servers",
            "cdn globally",
            "optimization approaches",
            "infrastructure defined in code",
            "ai coding tools",
            "data api",
            "data apis",
            "networking",
            "storage",
            "virtualisation",
            "virtualization",
            "preferred coding language",
            "primary coding language",
            "percentage of your current work involves writing code",
            "percentage of time do you generally enjoy spending coding",
            "writing code",
        ]
    ):
        return ApplicationPromptClassification(
            "skills_experience",
            "auto_answer_from_memory",
            "resume_fact",
            "skill_or_cloud_experience",
        )
    if "influence your decision" in text or "influenced your decision" in text:
        return ApplicationPromptClassification(
            "role_specific_free_text",
            "generate_custom_material",
            "custom_material",
            "role_specific_written_answer",
        )
    if any(
        term in text
        for term in [
            "linkedin",
            "github",
            "portfolio",
            "website",
            "personal site",
            "other url",
            "other website",
            "x profile",
            "twitter",
            "hn url",
            "hacker news",
            "social",
            "profile url",
            "google scholar",
            "scholar",
            "blog",
            "public writing",
            "x twitter account",
            "x (twitter) account",
        ]
    ):
        return ApplicationPromptClassification(
            "profile_link",
            "auto_fill_from_profile",
            "profile",
            "profile_url_field",
        )
    if any(
        term in text
        for term in [
            "most appropriate response",
            "which approach",
            "which of the following practices",
            "data scientist proposes",
            "researcher on the team",
            "data augmentation pipeline",
            "datasets have been collected",
            "preprocessing pipelines",
            "feature engineering pipeline",
            "real-time ml pricing model",
            "please select the tools and technologies",
            "agentic model capability",
            "environment for the agent to perform actions",
        ]
    ):
        return ApplicationPromptClassification(
            "assessment_question",
            "generate_custom_material",
            "custom_material",
            "assessment_draft_generation_requires_review",
        )
    if raw_label in {"name", "preferred name"} or any(
        term in text
        for term in [
            "first name",
            "last name",
            "legal name",
            "full name",
            "middle name",
            "email",
            "phone",
            "mobile number",
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
    if any(
        term in text
        for term in [
            "what is your gpa",
            "current gpa",
            "gpa",
            "act score",
            "grading system",
            "grade point average",
        ]
    ):
        return ApplicationPromptClassification(
            "education_grading",
            "auto_fill_from_profile",
            "resume_fact",
            "education_grading_profile_field",
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
    if any(
        term in text
        for term in [
            "worked at",
            "previously employed",
            "former employee",
            "previously worked for",
            "previously worked at",
            "ever been employed by",
            "employed by",
            "have you worked for",
            "worked for pitchbook",
            "worked for morningstar",
            "worked for two six",
            "consulting or direct hire",
            "affiliate in the past",
            "contract or contingent worker",
            "employee or contractor",
            "ever interviewed at",
            "interviewed at",
            "completed an application",
            "previously applied",
            "previously been employed",
        ]
    ):
        return ApplicationPromptClassification(
            "employment_history",
            "human_review_required",
            "profile",
            "employer_specific_history",
        )
    if "worked with us before" in text or "worked for us before" in text:
        return ApplicationPromptClassification(
            "employment_history",
            "human_review_required",
            "profile",
            "employer_specific_history",
        )
    if any(
        term in text
        for term in [
            "why",
            "interest",
            "relevant experience",
            "project",
            "describe",
            "outline",
            "share your",
            "tell us about",
            "explain",
            "how have you",
            "what is an example",
            "give a brief overview",
            "worked on before",
            "demonstrated leadership",
            "exceptional work",
            "excites you",
            "additional information",
            "additional information or a note",
            "feedback or questions",
            "what will you do",
            "what ai tools",
            "what do you value",
            "what motivates you",
            "what is it about",
            "anything else",
            "share something",
            "developed software applications",
            "decisions drive impact",
            "change is constant",
            "utilize ai tools",
            "high traffic environment",
            "please summarise",
            "this role requires",
            "what makes you the ideal candidate",
            "what makes you a great fit",
            "what are we looking for in you",
            "what are the performance metrics",
            "what can you tell us about our infrastructure",
            "two most important things",
            "most important criteria",
            "what do you see as the two most important criteria",
            "performance metrics we can evaluate",
            "cloud estate more reliable",
            "more secure",
            "cost-efficient",
            "cost efficient",
            "how was frontend work typically handled",
            "customer-facing feature",
            "customer facing feature",
            "what does success look like",
            "what does it mean to be",
            "which companies do you think",
            "ready to shape",
            "ready to build",
            "ready for a new challenge",
            "ready to roll",
            "ready to vibe",
            "audacious enough",
            "make your impact",
            "how will you make an impact",
            "how can you contribute",
            "engineering quality",
            "increasing the impact",
            "what will you be doing",
            "career plans",
            "most significant accomplishments",
            "reviewed code",
            "walk us through",
            "proudest achievement",
            "challenging production incident",
            "tell us what drew you",
            "drew you to apply",
            "feel free to share any context",
            "team culture",
            "what aspect of modern technology",
            "gone deep on",
            "how do you stay current",
            "bug or production issue introduced by ai-generated code",
            "ai-generated code",
            "do you think it's ethical",
            "core values",
            "continuous improvement",
            "are you in",
            "you in",
            "someone who will jump in",
            "thinks big",
            "figure things out",
            "pourquoi rejoindre",
            "pourquoi nous rejoindre",
            "pourquoi on recrute",
            "prêt e",
            "prête",
            "prêt(e)",
            "propuesta de valor",
            "desafios",
            "qué esperamos",
            "where did you gain your most notable software development experience",
            "what is one area of your life",
            "what has been your greatest span of control",
            "what does the wikimedia foundation do",
            "what is canonical",
            "what is kalshi",
            "what is agave",
            "who is",
            "what do we offer",
            "who should apply",
            "who might thrive here",
            "ready to make the move",
            "wanna join the adventure",
            "most appropriate response",
            "which of the following practices",
            "which approach best balances",
            "how should we go about",
            "how do we standardize",
            "how do we design",
            "what scenarios best suit",
            "ethical to automate people",
            "ai generated code",
            "business context and user impact",
            "favorite ai agentic technology",
            "system s perimeter",
            "systems perimeter",
            "internet entities and protocols",
            "hostnames",
            "whois",
            "dns record types",
        ]
    ):
        return ApplicationPromptClassification(
            "role_specific_free_text",
            "generate_custom_material",
            "custom_material",
            "role_specific_written_answer",
        )
    if any(
        term in text
        for term in [
            "hear about",
            "heard about",
            "learn about",
            "where did you find",
            "find this job posting",
            "found this job posting",
            "job board",
            "indeed",
            "stack overflow jobs",
        ]
    ):
        return ApplicationPromptClassification(
            "referral_source",
            "auto_answer_from_memory",
            "standard_preference",
            "standard_referral_source_answer",
        )
    if any(term in text for term in ["referral", "referred by", "referred you", "who should we thank"]):
        return ApplicationPromptClassification(
            "referral_contact",
            "auto_answer_from_memory",
            "standard_preference",
            "standard_referral_contact_answer",
        )
    if any(
        term in text
        for term in [
            "verbal and written english",
            "do you speak english",
            "speak english fluently",
            "professional level",
            "english level",
            "english language skills",
            "fluent english",
            "professional working proficiency in english",
        ]
    ):
        return ApplicationPromptClassification(
            "language_ability",
            "auto_answer_from_memory",
            "standard_preference",
            "standard_english_language_answer",
        )
    if any(
        term in text
        for term in [
            "language(s) can you speak",
            "language s can you speak",
            "languages can you speak",
            "which language",
            "which languages",
            "speak both japanese and english",
            "fluent japanese",
            "languages you speak",
        ]
    ):
        return ApplicationPromptClassification(
            "language_ability",
            "human_review_required",
            "candidate_preference",
            "language_ability_requires_confirmation",
        )
    if any(
        term in text
        for term in [
            "commuting distance",
            "work from canonical facilities",
            "come onsite",
            "in office",
            "in-office",
            "office",
            "onsite",
            "on-site",
            "based in the san francisco",
            "based in the bay area",
            "currently based in the bay area",
            "currently based in the greater san francisco",
            "based in toronto",
            "based in the uk",
            "located in argentina",
            "located in latam",
            "greater boston area",
            "permanently located in europe",
            "work from noida",
            "work from noida bangalore",
            "work from san francisco",
            "travel internationally",
            "open to travel",
            "can you travel",
            "comfortable traveling",
            "significant travel",
            "80 100",
            "toulouse france",
            "interview takes place in person",
            "final interview",
            "50 70 travel",
            "1 week per month",
            "2 weeks per month",
            "25% of your time",
            "vancouver hq",
            "meetings and/or conduct in-person trainings",
            "meetings and/or conduct in person trainings",
            "in-person meetings",
            "in person meetings",
            "clients’ worksites",
            "clients' worksites",
            "clients worksites",
            "omaha riverfront campus",
            "riverfront campus",
            "reside near seattle",
            "commutable distance",
            "living within 40 kilometers",
            "permanently reside in ireland",
            "reside in hyderabad",
            "week long team offsite",
            "mon fri",
            "on site team",
            "hybrid schedule",
            "hybrid policy",
            "hybrid work",
            "four days per week",
            "5 days a week",
            "riyadh",
            "taipei",
            "west coast hours",
            "work west coast hours",
            "work on-site in san francisco",
            "work on site in san francisco",
            "where in canada",
            "which state are you based",
        ]
    ):
        return ApplicationPromptClassification(
            "location_constraint",
            "human_review_required",
            "candidate_preference",
            "location_constraint_requires_confirmation",
        )
    if "own device" in text:
        return ApplicationPromptClassification(
            "device_policy",
            "human_review_required",
            "policy",
            "device_policy_requires_confirmation",
        )
    if "own computer" in text:
        return ApplicationPromptClassification(
            "device_policy",
            "human_review_required",
            "policy",
            "device_policy_requires_confirmation",
        )
    if "grading system" in text:
        return ApplicationPromptClassification(
            "education_grading",
            "human_review_required",
            "resume_fact",
            "education_grading_requires_confirmation",
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
        if _is_closed_jobs_registry_payload(path, payload):
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
            elif row.get("status") in {"OPENED_FOR_REVIEW", "OBSERVED_CANDIDATE"}:
                _register_research_position(path, row, positions, index=index)

    _append_linkedin_standard_prompt_inferences(items, positions)
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
        "platform": (
            snapshot.get("platform")
            or infer_platform_from_url(str(snapshot.get("url") or ""))
            or _infer_platform_from_path(Path("snapshot.json"))
        ),
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


def build_apply_run_audit(
    plan: dict[str, Any],
    page_text: str = "",
    closed_jobs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = str(plan.get("url") or "")
    job_like = {
        "apply_url": url,
        "short_apply_url": url,
        "platform": plan.get("platform"),
        "title": plan.get("title"),
        "page_text": page_text,
    }
    closed_reason = closed_application_reason(job_like, closed_jobs=closed_jobs)
    steps = [step for step in plan.get("steps", []) if isinstance(step, dict)]
    stop_steps = [
        _apply_stop_step(step)
        for step in steps
        if step.get("status") != "ready"
    ]
    missing_statuses = {
        "missing_profile_value",
        "missing_local_material",
        "missing_answer",
        "missing_resume_facts",
    }
    missing_steps = [step for step in stop_steps if step.get("status") in missing_statuses]
    manual_gate_statuses = {
        "needs_human_review",
        "manual_security_step",
        "final_submit_confirmation",
        "sensitive_not_stored",
    }
    manual_gate_steps = [step for step in stop_steps if step.get("status") in manual_gate_statuses]
    if closed_reason:
        status = "closed_skip"
        next_action = "skip this posting and keep it in the closed registry"
        automation_steps: list[dict[str, Any]] = []
        stop_steps = [
            {
                "field_index": None,
                "item_type": "page",
                "action": "skip",
                "label": "No longer accepting applications",
                "category": "closed_posting",
                "status": "closed_skip",
                "reason": closed_reason,
                "next_action": "record closed posting and skip automation",
                "handling": "do not fill any fields on closed postings",
            }
        ]
        missing_steps = []
        manual_gate_steps = []
    elif missing_steps:
        status = "blocked_missing_inputs"
        next_action = "collect missing profile/material/answer inputs before browser automation"
        automation_steps = [_apply_automation_step(step) for step in steps if step.get("status") == "ready"]
    elif manual_gate_steps:
        status = "autofill_ready_with_supervised_gates"
        next_action = "autofill ready fields, then stop for supervised gates"
        automation_steps = [_apply_automation_step(step) for step in steps if step.get("status") == "ready"]
    else:
        status = "autofill_ready"
        next_action = "autofill ready fields and stop before final submit unless explicitly approved"
        automation_steps = [_apply_automation_step(step) for step in steps if step.get("status") == "ready"]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "apply_run_audit",
        "title": plan.get("title"),
        "url": plan.get("url"),
        "platform": plan.get("platform"),
        "status": status,
        "closed_reason": closed_reason,
        "real_platform_submission": False,
        "autofill_allowed": not bool(closed_reason) and not bool(missing_steps),
        "final_submit_allowed": False,
        "would_submit": False,
        "policy": {
            "fake_data_real_submission_allowed": False,
            "submit_requires_explicit_approval": True,
            "stop_on_closed_posting": True,
            "stop_on_captcha_or_security": True,
            "do_not_store_protected_class_answers": True,
        },
        "step_count": len(steps),
        "automation_step_count": len(automation_steps),
        "stop_step_count": len(stop_steps),
        "missing_step_count": len(missing_steps),
        "manual_gate_count": len(manual_gate_steps),
        "status_counts": _count_by(steps, "status"),
        "automation_steps": automation_steps,
        "stop_steps": stop_steps,
        "next_action": next_action,
    }


def write_apply_run_audit(
    plan_path: str | Path,
    json_output: str | Path,
    markdown_output: str | Path,
    page_text: str = "",
    closed_jobs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plan = _read_json_file(Path(plan_path))
    if not isinstance(plan, dict):
        raise ValueError("plan must be a JSON object")
    audit = build_apply_run_audit(plan, page_text=page_text, closed_jobs=closed_jobs)
    audit["plan_file"] = Path(plan_path).name
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(audit, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(render_apply_run_audit_markdown(audit), encoding="utf-8")
    return audit


def build_browser_action_manifest(
    plan: dict[str, Any],
    page_text: str = "",
    closed_jobs: dict[str, Any] | None = None,
    include_values: bool = False,
) -> dict[str, Any]:
    audit = build_apply_run_audit(plan, page_text=page_text, closed_jobs=closed_jobs)
    steps = [step for step in plan.get("steps", []) if isinstance(step, dict)]
    browser_actions = [
        _browser_action_for_step(step, include_values=include_values)
        for step in steps
        if step.get("status") == "ready"
    ]
    if audit.get("status") == "closed_skip":
        browser_actions = []

    stop_actions = [
        {
            **stop,
            "safe_to_execute": False,
            "browser_action": "stop",
        }
        for stop in audit.get("stop_steps", [])
        if isinstance(stop, dict)
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "browser_action_manifest",
        "title": audit.get("title"),
        "url": audit.get("url"),
        "platform": audit.get("platform"),
        "status": audit.get("status"),
        "closed_reason": audit.get("closed_reason"),
        "real_platform_submission": False,
        "autofill_allowed": audit.get("autofill_allowed"),
        "final_submit_allowed": False,
        "would_submit": False,
        "include_values": include_values,
        "action_count": len(browser_actions),
        "stop_action_count": len(stop_actions),
        "browser_actions": browser_actions,
        "stop_actions": stop_actions,
        "policy": audit.get("policy", {}),
        "audit": {
            "status": audit.get("status"),
            "automation_step_count": audit.get("automation_step_count"),
            "stop_step_count": audit.get("stop_step_count"),
            "missing_step_count": audit.get("missing_step_count"),
            "manual_gate_count": audit.get("manual_gate_count"),
            "next_action": audit.get("next_action"),
        },
    }


def write_browser_action_manifest(
    plan_path: str | Path,
    json_output: str | Path,
    markdown_output: str | Path,
    page_text: str = "",
    closed_jobs: dict[str, Any] | None = None,
    include_values: bool = False,
) -> dict[str, Any]:
    plan = _read_json_file(Path(plan_path))
    if not isinstance(plan, dict):
        raise ValueError("plan must be a JSON object")
    manifest = build_browser_action_manifest(
        plan,
        page_text=page_text,
        closed_jobs=closed_jobs,
        include_values=include_values,
    )
    manifest["plan_file"] = Path(plan_path).name
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(render_browser_action_manifest_markdown(manifest), encoding="utf-8")
    return manifest


def build_pre_submit_review(
    manifests: list[dict[str, Any]],
    readiness: dict[str, Any] | None = None,
    gaps: dict[str, Any] | None = None,
    learning_tasks: dict[str, Any] | None = None,
    synthetic: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest_rows = [manifest for manifest in manifests if isinstance(manifest, dict)]
    positions: list[dict[str, Any]] = []
    confirmation_items: list[dict[str, Any]] = []
    for manifest in manifest_rows:
        position_items: list[dict[str, Any]] = []
        for stop in manifest.get("stop_actions", []):
            if not isinstance(stop, dict):
                continue
            item = _confirmation_item_from_stop_action(stop, manifest)
            _append_unique_confirmation_item(confirmation_items, item)
            _append_unique_confirmation_item(position_items, item)
        positions.append(
            {
                "manifest_file": manifest.get("manifest_file") or manifest.get("plan_file"),
                "title": manifest.get("title"),
                "url": manifest.get("url"),
                "platform": manifest.get("platform"),
                "status": manifest.get("status"),
                "closed_reason": manifest.get("closed_reason"),
                "action_count": int(manifest.get("action_count") or 0),
                "stop_action_count": int(manifest.get("stop_action_count") or 0),
                "autofill_allowed": bool(manifest.get("autofill_allowed")),
                "would_submit": bool(manifest.get("would_submit")),
                "confirmation_item_count": len(position_items),
                "confirmation_items": position_items,
            }
        )

    if gaps:
        for prompt in gaps.get("blocking_prompts", []):
            if isinstance(prompt, dict):
                _append_unique_confirmation_item(
                    confirmation_items,
                    _confirmation_item_from_gap(prompt),
                )
    if learning_tasks:
        for task in learning_tasks.get("tasks", []):
            if isinstance(task, dict) and not bool(task.get("approved")):
                _append_unique_confirmation_item(
                    confirmation_items,
                    _confirmation_item_from_learning_task(task),
                )

    submit_allowed_count = sum(1 for manifest in manifest_rows if bool(manifest.get("would_submit")))
    total_action_count = sum(int(manifest.get("action_count") or 0) for manifest in manifest_rows)
    total_stop_count = sum(int(manifest.get("stop_action_count") or 0) for manifest in manifest_rows)
    questions_to_confirm = _question_checklist_from_confirmation_items(confirmation_items)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "pre_submit_review",
        "manifest_count": len(manifest_rows),
        "position_count": len(positions),
        "autofill_ready_position_count": sum(
            1
            for position in positions
            if position.get("autofill_allowed") and not position.get("closed_reason")
        ),
        "closed_position_count": sum(1 for position in positions if position.get("closed_reason")),
        "total_action_count": total_action_count,
        "total_stop_action_count": total_stop_count,
        "confirmation_item_count": len(confirmation_items),
        "question_to_confirm_count": len(questions_to_confirm),
        "confirmation_status_counts": _count_by(confirmation_items, "status"),
        "submit_allowed_count": submit_allowed_count,
        "real_platform_submission": False,
        "final_submit_allowed": False,
        "would_submit": False,
        "actual_submit_count": int((synthetic or {}).get("actual_submit_count") or 0),
        "positions": positions,
        "confirmation_items": confirmation_items,
        "questions_to_confirm": questions_to_confirm,
        "readiness_summary": {
            "positions_observed_total": (readiness or {}).get("positions_observed_total", 0),
            "readiness_counts": (readiness or {}).get("readiness_counts", {}),
            "learning_queue_count": (readiness or {}).get("learning_queue_count", 0),
            "minimal_learning_task_count": (readiness or {}).get("minimal_learning_task_count", 0),
            "manual_gate_count": (readiness or {}).get("manual_gate_count", 0),
        },
        "gap_summary": {
            "unique_prompts_observed": (gaps or {}).get("unique_prompts_observed", 0),
            "blocking_prompt_count": (gaps or {}).get("blocking_prompt_count", 0),
            "coverage_counts": (gaps or {}).get("coverage_counts", {}),
        },
        "synthetic_summary": {
            "run_count": (synthetic or {}).get("run_count", 0),
            "per_platform_target": (synthetic or {}).get("per_platform_target", 0),
            "platform_target_achieved": (synthetic or {}).get("platform_target_achieved"),
            "per_platform_role_target": (synthetic or {}).get("per_platform_role_target", 0),
            "platform_role_target_achieved": (synthetic or {}).get("platform_role_target_achieved"),
            "actual_submit_count": int((synthetic or {}).get("actual_submit_count") or 0),
            "outcome_counts": (synthetic or {}).get("outcome_counts", {}),
            "policy_stop_counts": (synthetic or {}).get("policy_stop_counts", {}),
            "platform_counts": (synthetic or {}).get("platform_counts", {}),
            "role_variant_counts": (synthetic or {}).get("role_variant_counts", {}),
            "platform_role_counts": (synthetic or {}).get("platform_role_counts", {}),
        },
        "policy": {
            "real_platform_submission": False,
            "final_submit_allowed": False,
            "fake_data_real_submission_allowed": False,
            "stop_on_closed_posting": True,
            "stop_on_captcha_or_security": True,
        },
    }


def write_pre_submit_review(
    manifest_paths: list[str | Path],
    json_output: str | Path,
    markdown_output: str | Path,
    readiness: dict[str, Any] | None = None,
    gaps: dict[str, Any] | None = None,
    learning_tasks: dict[str, Any] | None = None,
    synthetic: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifests: list[dict[str, Any]] = []
    for manifest_path in manifest_paths:
        path = Path(manifest_path)
        payload = _read_json_file(path)
        if not isinstance(payload, dict):
            raise ValueError(f"manifest must be a JSON object: {path}")
        payload["manifest_file"] = path.name
        manifests.append(payload)
    review = build_pre_submit_review(
        manifests,
        readiness=readiness,
        gaps=gaps,
        learning_tasks=learning_tasks,
        synthetic=synthetic,
    )
    review["manifest_files"] = [Path(path).name for path in manifest_paths]
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(review, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(render_pre_submit_review_markdown(review), encoding="utf-8")
    return review


def is_safe_browser_execution_target(url: str) -> bool:
    parsed = urllib.parse.urlparse(str(url or ""))
    if parsed.scheme == "file":
        return True
    if parsed.scheme in {"http", "https"}:
        return parsed.hostname in LOCAL_BROWSER_EXECUTION_HOSTS
    return False


def build_browser_dom_execution_plan(
    manifest: dict[str, Any],
    target_url: str,
) -> dict[str, Any]:
    execution_allowed = is_safe_browser_execution_target(target_url)
    source_url = str(manifest.get("url") or "")
    if not execution_allowed:
        safety_status = "blocked_nonlocal_target"
        actions: list[dict[str, Any]] = []
        stop_actions = [
            {
                "status": "safety_block",
                "label": target_url,
                "handling": "only execute browser actions on file, localhost, or loopback targets",
                "safe_to_execute": False,
            }
        ]
    elif manifest.get("status") == "closed_skip":
        safety_status = "closed_skip"
        actions = []
        stop_actions = manifest.get("stop_actions", [])
    else:
        safety_status = "allowed_local_target"
        actions = [
            action
            for action in manifest.get("browser_actions", [])
            if isinstance(action, dict) and action.get("safe_to_execute") is not False
        ]
        stop_actions = manifest.get("stop_actions", [])
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "browser_dom_execution_plan",
        "target_url": target_url,
        "source_url": source_url,
        "title": manifest.get("title"),
        "platform": manifest.get("platform"),
        "execution_allowed": execution_allowed,
        "safety_status": safety_status,
        "real_platform_submission": False,
        "final_submit_allowed": False,
        "would_submit": False,
        "actual_submit_count": 0,
        "browser_action_count": len(actions),
        "stop_action_count": len(stop_actions),
        "browser_actions": actions,
        "stop_actions": stop_actions,
        "policy": {
            "local_targets_only": True,
            "remote_employer_pages_blocked": True,
            "final_submit_allowed": False,
            "fake_data_real_submission_allowed": False,
        },
    }


def render_synthetic_application_html(
    snapshot: dict[str, Any],
    runner_script: str = "",
) -> str:
    title = html.escape(str(snapshot.get("title") or "Synthetic application"))
    page_text = html.escape(str(snapshot.get("page_text") or "Synthetic local application form"))
    field_html = []
    for field in snapshot.get("fields", []):
        if not isinstance(field, dict):
            continue
        field_html.append(_render_synthetic_field_html(field))
    button_html = []
    for button in snapshot.get("buttons", []):
        if not isinstance(button, dict):
            continue
        raw_label = _field_prompt_label(button) or "Submit application"
        label = html.escape(raw_label)
        index = html.escape(str(button.get("i") or ""))
        final_attr = ' data-final-submit="true"' if "submit" in _normalize(raw_label) else ""
        button_html.append(
            f'<button type="button" data-field-index="{index}" data-item-type="button" data-label="{label}" aria-label="{label}"{final_attr}>{label}</button>'
        )
    script_html = f"\n<script>\n{runner_script}\n</script>\n" if runner_script else ""
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{title}</title>",
            "<style>",
            "body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;max-width:760px;margin:32px auto;padding:0 16px;line-height:1.4}",
            "label{display:block;margin:14px 0 4px;font-weight:600}",
            "input,select,textarea{width:100%;box-sizing:border-box;padding:8px;border:1px solid #999;border-radius:4px}",
            "button{margin-top:20px;padding:10px 14px;border:1px solid #333;background:#f7f7f7;border-radius:4px}",
            "pre{white-space:pre-wrap;background:#f5f5f5;padding:12px;border-radius:4px}",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>{title}</h1>",
            f'<p data-page-text="true">{page_text}</p>',
            '<form data-synthetic-application="true">',
            *field_html,
            *button_html,
            "</form>",
            '<h2>Runner Result</h2>',
            '<pre id="runner-result"></pre>',
            script_html,
            "</body>",
            "</html>",
        ]
    )


def build_browser_dom_runner_script(manifest: dict[str, Any]) -> str:
    manifest_json = json.dumps(manifest, ensure_ascii=True)
    return "\n".join(
        [
            "(() => {",
            f"  const manifest = {manifest_json};",
            "  const normalize = (value) => String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();",
            "  const fields = () => Array.from(document.querySelectorAll('[data-field-index], input, select, textarea, button'));",
            "  const filterByItemType = (matches, action) => {",
            "    const itemType = action.item_type || '';",
            "    if (!itemType) return matches;",
            "    const filtered = matches.filter((el) => (el.dataset.itemType || (el.tagName === 'BUTTON' ? 'button' : 'field')) === itemType);",
            "    return filtered.length ? filtered : matches;",
            "  };",
            "  const matchByCandidate = (candidate) => {",
            "    if (!candidate) return [];",
            "    if (candidate.strategy === 'css') return Array.from(document.querySelectorAll(candidate.selector));",
            "    if (candidate.strategy === 'field_index') return fields().filter((el) => String(el.dataset.fieldIndex || '') === String(candidate.selector));",
            "    if (candidate.strategy === 'label_text') return fields().filter((el) => normalize(el.dataset.label || el.getAttribute('aria-label') || '') === normalize(candidate.selector));",
            "    return [];",
            "  };",
            "  const resolve = (action) => {",
            "    for (const candidate of action.selector_candidates || []) {",
            "      const matches = filterByItemType(matchByCandidate(candidate), action);",
            "      if (matches.length === 1) return { element: matches[0], candidate };",
            "    }",
            "    return null;",
            "  };",
            "  const result = {",
            "    source: 'browser_dom_runner_script',",
            "    realPlatformSubmission: false,",
            "    finalSubmitAllowed: false,",
            "    wouldSubmit: false,",
            "    actualSubmitCount: 0,",
            "    executed: [],",
            "    selectorMisses: [],",
            "    stopActions: manifest.stop_actions || []",
            "  };",
            "  if (manifest.status === 'closed_skip') {",
            "    result.outcome = 'closed_skip';",
            "  } else {",
            "    for (const action of manifest.browser_actions || []) {",
            "      const resolved = resolve(action);",
            "      if (!resolved) {",
            "        result.selectorMisses.push({ label: action.label, fieldIndex: action.field_index, browserAction: action.browser_action });",
            "        continue;",
            "      }",
            "      const value = action.value || `[${action.value_source || action.browser_action || 'value'}]`;",
            "      if (action.browser_action === 'upload_file') {",
            "        resolved.element.dataset.uploadedFileSource = action.value_source || '';",
            "      } else if ('value' in resolved.element) {",
            "        resolved.element.value = value;",
            "      }",
            "      resolved.element.dispatchEvent(new Event('input', { bubbles: true }));",
            "      resolved.element.dispatchEvent(new Event('change', { bubbles: true }));",
            "      result.executed.push({ label: action.label, selector: resolved.candidate.selector, strategy: resolved.candidate.strategy, browserAction: action.browser_action });",
            "    }",
            "    result.outcome = result.selectorMisses.length ? 'selector_resolution_failed' : (result.stopActions.length ? 'executed_to_policy_stop' : 'completed_autofill_no_submit');",
            "  }",
            "  window.__JOB_APPLY_RUNNER_RESULT__ = result;",
            "  const target = document.getElementById('runner-result');",
            "  if (target) target.textContent = JSON.stringify(result, null, 2);",
            "})();",
        ]
    )


def write_browser_dom_harness(
    manifest_path: str | Path,
    snapshot_path: str | Path,
    html_output: str | Path,
    script_output: str | Path,
    json_output: str | Path,
    markdown_output: str | Path,
) -> dict[str, Any]:
    manifest = _read_json_file(Path(manifest_path))
    snapshot = _read_json_file(Path(snapshot_path))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be a JSON object")
    script = build_browser_dom_runner_script(manifest)
    html_path = Path(html_output)
    script_path = Path(script_output)
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    for path in [html_path, script_path, json_path, markdown_path]:
        path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_synthetic_application_html(snapshot, runner_script=script), encoding="utf-8")
    script_path.write_text(script, encoding="utf-8")
    plan = build_browser_dom_execution_plan(manifest, html_path.resolve().as_uri())
    plan["manifest_file"] = Path(manifest_path).name
    plan["snapshot_file"] = Path(snapshot_path).name
    plan["html_file"] = str(html_path)
    plan["script_file"] = str(script_path)
    json_path.write_text(json.dumps(plan, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(render_browser_dom_execution_plan_markdown(plan), encoding="utf-8")
    return plan


def execute_browser_action_manifest_locally(
    manifest: dict[str, Any],
    snapshot: dict[str, Any],
    allow_local_synthetic_submit: bool = False,
) -> dict[str, Any]:
    fields = [
        {**field, "_item_type": "field"}
        for field in snapshot.get("fields", [])
        if isinstance(field, dict)
    ]
    fields.extend(
        {**button, "_item_type": "button"}
        for button in snapshot.get("buttons", [])
        if isinstance(button, dict)
    )
    executed_actions: list[dict[str, Any]] = []
    selector_misses: list[dict[str, Any]] = []
    synthetic_gate_answers: list[dict[str, Any]] = []
    remaining_stop_actions = [
        stop
        for stop in manifest.get("stop_actions", [])
        if isinstance(stop, dict)
    ]
    would_submit = False
    actual_submit_count = 0
    if manifest.get("status") == "closed_skip":
        outcome = "closed_skip"
        policy_stop = "closed_posting"
    else:
        for action in manifest.get("browser_actions", []):
            if not isinstance(action, dict):
                continue
            target = _resolve_browser_action_target(action, fields)
            if target is None:
                selector_misses.append(
                    {
                        "field_index": action.get("field_index"),
                        "label": action.get("label"),
                        "browser_action": action.get("browser_action"),
                        "selector_candidates": action.get("selector_candidates", []),
                    }
                )
                continue
            executed_actions.append(
                {
                    "field_index": target.get("i"),
                    "label": _field_prompt_label(target),
                    "browser_action": action.get("browser_action"),
                    "plan_action": action.get("plan_action"),
                    "value_source": action.get("value_source"),
                    "selector_strategy": target.get("_matched_strategy"),
                    "selector": target.get("_matched_selector"),
                    "result": f"locally_executed_{action.get('browser_action') or 'fill'}",
                }
            )
        if allow_local_synthetic_submit and not selector_misses:
            remaining: list[dict[str, Any]] = []
            for stop in remaining_stop_actions:
                if _is_local_synthetic_fillable_stop_action(stop):
                    action = _browser_synthetic_answer_action_for_stop_action(stop)
                    target = _resolve_browser_action_target(action, fields)
                    if target is None:
                        selector_misses.append(
                            {
                                "field_index": action.get("field_index"),
                                "label": action.get("label"),
                                "browser_action": action.get("browser_action"),
                                "selector_candidates": action.get("selector_candidates", []),
                            }
                        )
                        continue
                    value = _local_synthetic_value_for_stop_action(stop)
                    synthetic_gate_answers.append(
                        {
                            "field_index": target.get("i"),
                            "label": _field_prompt_label(target),
                            "status": stop.get("status"),
                            "category": stop.get("category"),
                            "value_source": action.get("value_source"),
                            "selector_strategy": target.get("_matched_strategy"),
                            "selector": target.get("_matched_selector"),
                        }
                    )
                    executed_actions.append(
                        {
                            "field_index": target.get("i"),
                            "label": _field_prompt_label(target),
                            "browser_action": action.get("browser_action"),
                            "plan_action": action.get("plan_action"),
                            "value_source": action.get("value_source"),
                            "selector_strategy": target.get("_matched_strategy"),
                            "selector": target.get("_matched_selector"),
                            "result": "locally_filled_synthetic_gate_answer",
                            "synthetic_value_kind": value.get("kind"),
                        }
                    )
                else:
                    remaining.append(stop)
            remaining_stop_actions = remaining
        if selector_misses:
            outcome = "selector_resolution_failed"
            policy_stop = "selector_resolution"
        elif (
            allow_local_synthetic_submit
            and _only_final_submit_stop_actions(remaining_stop_actions)
        ):
            submit_actions = [
                _browser_submit_action_for_stop_action(stop)
                for stop in remaining_stop_actions
                if isinstance(stop, dict)
            ]
            for action in submit_actions:
                target = _resolve_browser_action_target(action, fields)
                if target is None:
                    selector_misses.append(
                        {
                            "field_index": action.get("field_index"),
                            "label": action.get("label"),
                            "browser_action": action.get("browser_action"),
                            "selector_candidates": action.get("selector_candidates", []),
                        }
                    )
                    continue
                executed_actions.append(
                    {
                        "field_index": target.get("i"),
                        "label": _field_prompt_label(target),
                        "browser_action": "click_submit",
                        "plan_action": "submit_gate",
                        "value_source": "local_synthetic_submit",
                        "selector_strategy": target.get("_matched_strategy"),
                        "selector": target.get("_matched_selector"),
                        "result": "locally_clicked_synthetic_submit",
                    }
                )
                actual_submit_count += 1
            if selector_misses:
                outcome = "selector_resolution_failed"
                policy_stop = "selector_resolution"
                actual_submit_count = 0
            else:
                outcome = "submitted_local_synthetic"
                policy_stop = "local_synthetic_submit_allowed"
                would_submit = True
        elif remaining_stop_actions:
            outcome = "executed_to_policy_stop"
            policy_stop = str(remaining_stop_actions[0].get("status") or "manual_gate")
        else:
            outcome = "completed_autofill_no_submit"
            policy_stop = "final_submit_not_requested"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "local_browser_manifest_executor",
        "title": manifest.get("title"),
        "url": manifest.get("url"),
        "platform": manifest.get("platform"),
        "outcome": outcome,
        "policy_stop": policy_stop,
        "real_platform_submission": False,
        "would_submit": would_submit,
        "actual_submit_count": actual_submit_count,
        "local_synthetic_submit_allowed": bool(allow_local_synthetic_submit),
        "manifest_action_count": manifest.get("action_count", 0),
        "executed_action_count": len(executed_actions),
        "selector_miss_count": len(selector_misses),
        "stop_action_count": manifest.get("stop_action_count", 0),
        "remaining_stop_action_count": len(remaining_stop_actions),
        "synthetic_gate_answer_count": len(synthetic_gate_answers),
        "executed_actions": executed_actions,
        "synthetic_gate_answers": synthetic_gate_answers,
        "selector_misses": selector_misses,
        "stop_actions": remaining_stop_actions,
        "manifest": {
            "status": manifest.get("status"),
            "closed_reason": manifest.get("closed_reason"),
            "autofill_allowed": manifest.get("autofill_allowed"),
            "final_submit_allowed": manifest.get("final_submit_allowed"),
        },
    }


def execute_form_plan_offline(
    plan: dict[str, Any],
    page_text: str = "",
    closed_jobs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    audit = build_apply_run_audit(plan, page_text=page_text, closed_jobs=closed_jobs)
    executed_steps: list[dict[str, Any]] = []
    for step in audit.get("automation_steps", []):
        executed_steps.append(
            {
                "field_index": step.get("field_index"),
                "label": step.get("label"),
                "action": step.get("action"),
                "category": step.get("category"),
                "value_source": step.get("value_source"),
                "result": f"simulated_{step.get('action') or 'fill'}",
            }
        )

    stop_steps = audit.get("stop_steps", [])
    if audit.get("status") == "closed_skip":
        outcome = "closed_skip"
        policy_stop = "closed_posting"
    elif audit.get("missing_step_count", 0):
        outcome = "blocked_missing_inputs"
        policy_stop = "missing_input"
    elif stop_steps:
        outcome = "executed_to_policy_stop"
        policy_stop = str(stop_steps[0].get("status") or "manual_gate")
    else:
        outcome = "completed_autofill_no_submit"
        policy_stop = "final_submit_not_requested"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "offline_apply_executor",
        "title": audit.get("title"),
        "url": audit.get("url"),
        "platform": audit.get("platform"),
        "outcome": outcome,
        "policy_stop": policy_stop,
        "real_platform_submission": False,
        "would_submit": False,
        "actual_submit_count": 0,
        "autofill_allowed": audit.get("autofill_allowed"),
        "executed_step_count": len(executed_steps),
        "stop_step_count": len(stop_steps),
        "executed_steps": executed_steps,
        "stop_steps": stop_steps,
        "audit": {
            "status": audit.get("status"),
            "closed_reason": audit.get("closed_reason"),
            "missing_step_count": audit.get("missing_step_count"),
            "manual_gate_count": audit.get("manual_gate_count"),
            "final_submit_allowed": audit.get("final_submit_allowed"),
        },
    }


def _only_final_submit_stop_actions(stop_actions: Any) -> bool:
    stops = [stop for stop in (stop_actions or []) if isinstance(stop, dict)]
    return bool(stops) and all(
        str(stop.get("status") or "") == "final_submit_confirmation" for stop in stops
    )


def _is_local_synthetic_fillable_stop_action(stop: dict[str, Any]) -> bool:
    return str(stop.get("status") or "") in {
        "missing_answer",
        "needs_human_review",
        "sensitive_not_stored",
    }


def _browser_synthetic_answer_action_for_stop_action(stop: dict[str, Any]) -> dict[str, Any]:
    return {
        "field_index": stop.get("field_index"),
        "item_type": stop.get("item_type"),
        "browser_action": "fill_synthetic_gate_answer",
        "plan_action": "synthetic_gate_answer",
        "label": stop.get("label"),
        "category": stop.get("category"),
        "required": bool(stop.get("required")),
        "selector_candidates": _selector_candidates_for_step(stop),
        "value_source": "local_synthetic_fake_answer",
        "requires_file": False,
        "safe_to_execute": True,
        "guard": "local synthetic forms only; never use for real employer pages",
    }


def _local_synthetic_value_for_stop_action(stop: dict[str, Any]) -> dict[str, str]:
    status = str(stop.get("status") or "")
    label = _normalize(str(stop.get("label") or ""))
    category = str(stop.get("category") or "")
    if status == "sensitive_not_stored":
        return {"kind": "protected_class_fake_decline", "value": "Prefer not to say"}
    if category == "policy_acknowledgement" or "acknowledge" in label or "privacy" in label:
        return {"kind": "policy_acknowledgement", "value": "Yes"}
    if "sms" in label or "whatsapp" in label or "text message" in label:
        return {"kind": "communication_consent", "value": "No"}
    if "hear about" in label or "heard about" in label or "source" in label:
        return {"kind": "referral_source", "value": "LinkedIn"}
    return {"kind": "synthetic_generic", "value": "Synthetic test answer"}


def _browser_submit_action_for_stop_action(stop: dict[str, Any]) -> dict[str, Any]:
    return {
        "field_index": stop.get("field_index"),
        "item_type": stop.get("item_type"),
        "browser_action": "click_submit",
        "plan_action": "submit_gate",
        "label": stop.get("label"),
        "category": stop.get("category"),
        "required": bool(stop.get("required")),
        "selector_candidates": _selector_candidates_for_step(stop),
        "value_source": "local_synthetic_submit",
        "requires_file": False,
        "safe_to_execute": True,
        "guard": "local synthetic forms only; never use for real employer pages",
    }


def run_synthetic_apply_execution(
    count: int = 100,
    include_values: bool = False,
    per_platform_target: int | None = None,
    per_platform_role_target: int | None = None,
) -> dict[str, Any]:
    profile = build_synthetic_candidate_profile()
    executions: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    if per_platform_role_target is not None:
        index = 1
        for platform in SYNTHETIC_APPLICATION_PLATFORMS:
            for role_title in SYNTHETIC_APPLICATION_ROLE_TITLES:
                for _ in range(max(per_platform_role_target, 0)):
                    snapshots.append(
                        _build_synthetic_application_snapshot(
                            index,
                            platform=platform,
                            role_title=role_title,
                        )
                    )
                    index += 1
    elif per_platform_target is not None:
        run_count = max(per_platform_target, 0) * len(SYNTHETIC_APPLICATION_PLATFORMS)
        snapshots = [
            _build_synthetic_application_snapshot(index)
            for index in range(1, run_count + 1)
        ]
    else:
        run_count = max(count, 0)
        snapshots = [
            _build_synthetic_application_snapshot(index)
            for index in range(1, run_count + 1)
        ]
    for index, snapshot in enumerate(snapshots, start=1):
        plan = build_form_fill_plan(
            snapshot,
            profile=profile,
            answer_memory=None,
            include_values=include_values,
        )
        execution = execute_form_plan_offline(plan, page_text=str(snapshot.get("page_text") or ""))
        execution.update(
            {
                "index": index,
                "company": snapshot.get("company"),
                "job_title": snapshot.get("job_title"),
                "role_variant": snapshot.get("role_variant") or snapshot.get("job_title"),
                "role_family": snapshot.get("role_family"),
            }
        )
        executions.append(execution)

    platform_counts = _count_by(executions, "platform")
    role_variant_counts = _count_by(executions, "role_variant")
    platform_role_counts = _platform_role_counts(executions)
    platform_target = int(per_platform_target or 0)
    platform_role_target = int(per_platform_role_target or 0)
    platform_target_shortfalls = {
        platform: max(0, platform_target - int(platform_counts.get(platform, 0)))
        for platform in SYNTHETIC_APPLICATION_PLATFORMS
    }
    platform_role_target_shortfalls = _platform_role_target_shortfalls(
        platform_role_counts,
        platform_role_target,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "execution": "offline_synthetic_apply_executor",
        "requested_count": len(snapshots),
        "per_platform_target": platform_target,
        "platform_target_achieved": (
            all(count == 0 for count in platform_target_shortfalls.values())
            if platform_target
            else None
        ),
        "platform_target_shortfalls": platform_target_shortfalls if platform_target else {},
        "per_platform_role_target": platform_role_target,
        "platform_role_target_achieved": (
            all(count == 0 for count in platform_role_target_shortfalls.values())
            if platform_role_target
            else None
        ),
        "platform_role_target_shortfalls": (
            platform_role_target_shortfalls if platform_role_target else {}
        ),
        "run_count": len(executions),
        "real_platform_submission": False,
        "actual_submit_count": sum(int(item.get("actual_submit_count", 0)) for item in executions),
        "outcome_counts": _count_by(executions, "outcome"),
        "policy_stop_counts": _count_by(executions, "policy_stop"),
        "platform_counts": platform_counts,
        "role_variant_counts": role_variant_counts,
        "platform_role_counts": platform_role_counts,
        "executed_step_count": sum(int(item.get("executed_step_count", 0)) for item in executions),
        "stop_step_count": sum(int(item.get("stop_step_count", 0)) for item in executions),
        "runs": executions,
    }


def write_synthetic_apply_execution(
    json_output: str | Path,
    markdown_output: str | Path,
    count: int = 100,
    include_values: bool = False,
    per_platform_target: int | None = None,
    per_platform_role_target: int | None = None,
) -> dict[str, Any]:
    report = run_synthetic_apply_execution(
        count=count,
        include_values=include_values,
        per_platform_target=per_platform_target,
        per_platform_role_target=per_platform_role_target,
    )
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(render_synthetic_apply_execution_markdown(report), encoding="utf-8")
    return report


def run_synthetic_browser_action_execution(
    count: int = 100,
    include_values: bool = False,
    per_platform_target: int | None = None,
    per_platform_role_target: int | None = None,
    allow_local_synthetic_submit: bool = False,
) -> dict[str, Any]:
    profile = build_synthetic_candidate_profile()
    executions: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    if per_platform_role_target is not None:
        index = 1
        for platform in SYNTHETIC_APPLICATION_PLATFORMS:
            for role_title in SYNTHETIC_APPLICATION_ROLE_TITLES:
                for _ in range(max(per_platform_role_target, 0)):
                    snapshots.append(
                        _build_synthetic_application_snapshot(
                            index,
                            platform=platform,
                            role_title=role_title,
                        )
                    )
                    index += 1
    elif per_platform_target is not None:
        run_count = max(per_platform_target, 0) * len(SYNTHETIC_APPLICATION_PLATFORMS)
        snapshots = [
            _build_synthetic_application_snapshot(index)
            for index in range(1, run_count + 1)
        ]
    else:
        run_count = max(count, 0)
        snapshots = [
            _build_synthetic_application_snapshot(index)
            for index in range(1, run_count + 1)
        ]

    for index, snapshot in enumerate(snapshots, start=1):
        plan = build_form_fill_plan(
            snapshot,
            profile=profile,
            answer_memory=None,
            include_values=include_values,
        )
        manifest = build_browser_action_manifest(
            plan,
            page_text=str(snapshot.get("page_text") or ""),
            include_values=include_values,
        )
        execution = execute_browser_action_manifest_locally(
            manifest,
            snapshot,
            allow_local_synthetic_submit=allow_local_synthetic_submit,
        )
        execution.update(
            {
                "index": index,
                "company": snapshot.get("company"),
                "job_title": snapshot.get("job_title"),
                "role_variant": snapshot.get("role_variant") or snapshot.get("job_title"),
                "role_family": snapshot.get("role_family"),
            }
        )
        executions.append(execution)

    platform_counts = _count_by(executions, "platform")
    role_variant_counts = _count_by(executions, "role_variant")
    platform_role_counts = _platform_role_counts(executions)
    platform_target = int(per_platform_target or 0)
    platform_role_target = int(per_platform_role_target or 0)
    platform_target_shortfalls = {
        platform: max(0, platform_target - int(platform_counts.get(platform, 0)))
        for platform in SYNTHETIC_APPLICATION_PLATFORMS
    }
    platform_role_target_shortfalls = _platform_role_target_shortfalls(
        platform_role_counts,
        platform_role_target,
    )
    expected_blocker_statuses = {"closed_posting", "manual_security_step"}
    expected_blocker_count = sum(
        1
        for item in executions
        if str(item.get("policy_stop") or "") in expected_blocker_statuses
    )
    eligible_submit_target_count = max(0, len(executions) - expected_blocker_count)
    actual_submit_count = sum(int(item.get("actual_submit_count", 0)) for item in executions)
    selector_miss_count = sum(int(item.get("selector_miss_count", 0)) for item in executions)
    eligible_submit_achieved = (
        bool(allow_local_synthetic_submit)
        and selector_miss_count == 0
        and actual_submit_count == eligible_submit_target_count
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "execution": "local_synthetic_browser_action_executor",
        "requested_count": len(snapshots),
        "per_platform_target": platform_target,
        "platform_target_achieved": (
            all(count == 0 for count in platform_target_shortfalls.values())
            if platform_target
            else None
        ),
        "platform_target_shortfalls": platform_target_shortfalls if platform_target else {},
        "per_platform_role_target": platform_role_target,
        "platform_role_target_achieved": (
            all(count == 0 for count in platform_role_target_shortfalls.values())
            if platform_role_target
            else None
        ),
        "platform_role_target_shortfalls": (
            platform_role_target_shortfalls if platform_role_target else {}
        ),
        "run_count": len(executions),
        "real_platform_submission": False,
        "local_synthetic_submit_allowed": bool(allow_local_synthetic_submit),
        "actual_submit_count": actual_submit_count,
        "would_submit_count": sum(1 for item in executions if bool(item.get("would_submit"))),
        "eligible_submit_target_count": eligible_submit_target_count,
        "eligible_submit_count": actual_submit_count,
        "eligible_submit_achieved": eligible_submit_achieved,
        "expected_blocker_count": expected_blocker_count,
        "expected_blocker_policy_stops": sorted(expected_blocker_statuses),
        "outcome_counts": _count_by(executions, "outcome"),
        "policy_stop_counts": _count_by(executions, "policy_stop"),
        "platform_counts": platform_counts,
        "role_variant_counts": role_variant_counts,
        "platform_role_counts": platform_role_counts,
        "executed_action_count": sum(int(item.get("executed_action_count", 0)) for item in executions),
        "selector_miss_count": selector_miss_count,
        "stop_action_count": sum(int(item.get("stop_action_count", 0)) for item in executions),
        "synthetic_gate_answer_count": sum(int(item.get("synthetic_gate_answer_count", 0)) for item in executions),
        "policy": {
            "local_synthetic_submit_only": bool(allow_local_synthetic_submit),
            "real_platform_submission": False,
            "submit_requires_only_final_submit_stop": True,
            "closed_or_captcha_never_submitted": True,
            "synthetic_only_answers_may_fill_review_or_sensitive_gates": bool(allow_local_synthetic_submit),
        },
        "runs": executions,
    }


def write_synthetic_browser_action_execution(
    json_output: str | Path,
    markdown_output: str | Path,
    count: int = 100,
    include_values: bool = False,
    per_platform_target: int | None = None,
    per_platform_role_target: int | None = None,
    allow_local_synthetic_submit: bool = False,
) -> dict[str, Any]:
    report = run_synthetic_browser_action_execution(
        count=count,
        include_values=include_values,
        per_platform_target=per_platform_target,
        per_platform_role_target=per_platform_role_target,
        allow_local_synthetic_submit=allow_local_synthetic_submit,
    )
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(render_synthetic_browser_action_execution_markdown(report), encoding="utf-8")
    return report


def build_learning_task_template(
    readiness_report: dict[str, Any],
    profile: CandidateProfile | None = None,
    answer_memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    for task in readiness_report.get("minimal_learning_tasks", []):
        if not isinstance(task, dict):
            continue
        storage = str(task.get("recommended_storage") or "")
        group_key = str(task.get("group_key") or "")
        suggestion = _learning_task_answer_suggestion(task, profile, answer_memory)
        tasks.append(
            {
                "group_key": group_key,
                "question": task.get("question"),
                "recommended_storage": storage,
                "answer_scope": _learning_task_answer_scope(group_key, storage),
                "automation_behavior": _learning_task_automation_behavior(group_key, storage),
                **suggestion,
                "labels": task.get("labels", []),
                "platforms": task.get("platforms", []),
                "related_prompt_count": task.get("related_prompt_count", 0),
                "observed_count": task.get("observed_count", 0),
                "required_count": task.get("required_count", 0),
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
    profile: CandidateProfile | None = None,
    answer_memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    template = build_learning_task_template(readiness_report, profile=profile, answer_memory=answer_memory)
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(template, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(render_learning_task_template_markdown(template), encoding="utf-8")
    return template


def build_learning_approval_pack(
    learning_tasks: dict[str, Any],
    readiness_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    task_rows: list[dict[str, Any]] = []
    bucket_totals: dict[str, dict[str, Any]] = {}
    for index, task in enumerate(learning_tasks.get("tasks", []), start=1):
        if not isinstance(task, dict):
            continue
        bucket = _learning_approval_bucket(task)
        draft_answer = str(task.get("answer") or task.get("suggested_answer") or "").strip()
        row = {
            "priority": bucket["rank"],
            "bucket": bucket["bucket"],
            "bucket_title": bucket["title"],
            "recommended_action": bucket["recommended_action"],
            "group_key": task.get("group_key"),
            "question": task.get("question"),
            "recommended_storage": task.get("recommended_storage"),
            "answer_scope": task.get("answer_scope")
            or _learning_task_answer_scope(
                str(task.get("group_key") or ""),
                str(task.get("recommended_storage") or ""),
            ),
            "automation_behavior": task.get("automation_behavior")
            or _learning_task_automation_behavior(
                str(task.get("group_key") or ""),
                str(task.get("recommended_storage") or ""),
            ),
            "suggested_answer": task.get("suggested_answer", ""),
            "draft_answer": draft_answer,
            "suggested_answer_source": task.get("suggested_answer_source", ""),
            "suggestion_confidence": task.get("suggestion_confidence", ""),
            "approval_risk": task.get("approval_risk", ""),
            "approval_required": bool(task.get("approval_required", True)),
            "approval_note": task.get("approval_note", ""),
            "persist_allowed": bool(task.get("persist_allowed", True)),
            "related_prompt_count": int(task.get("related_prompt_count") or 0),
            "observed_count": int(task.get("observed_count") or 0),
            "required_count": int(task.get("required_count") or 0),
            "platforms": _string_list(task.get("platforms")),
            "labels": _string_list(task.get("labels")),
            "approved": bool(task.get("approved")),
            "answer": task.get("answer", ""),
            "notes": task.get("notes", ""),
            "source_index": index,
        }
        task_rows.append(row)
        totals = bucket_totals.setdefault(
            bucket["bucket"],
            {
                "bucket": bucket["bucket"],
                "title": bucket["title"],
                "recommended_action": bucket["recommended_action"],
                "priority": bucket["rank"],
                "task_count": 0,
                "related_prompt_count": 0,
                "observed_count": 0,
                "required_count": 0,
                "draft_answer_count": 0,
                "persist_allowed_count": 0,
                "platforms": set(),
            },
        )
        totals["task_count"] += 1
        totals["related_prompt_count"] += row["related_prompt_count"]
        totals["observed_count"] += row["observed_count"]
        totals["required_count"] += row["required_count"]
        if draft_answer:
            totals["draft_answer_count"] += 1
        if row["persist_allowed"]:
            totals["persist_allowed_count"] += 1
        for platform in row["platforms"]:
            totals["platforms"].add(platform)

    task_rows.sort(
        key=lambda row: (
            int(row.get("priority") or 99),
            -int(row.get("required_count") or 0),
            str(row.get("question") or ""),
        )
    )
    bucket_rows: list[dict[str, Any]] = []
    for row in sorted(bucket_totals.values(), key=lambda item: (item["priority"], item["bucket"])):
        bucket_rows.append(
            {
                **{key: value for key, value in row.items() if key != "platforms"},
                "platforms": sorted(row["platforms"]),
            }
        )

    manual_gate_rows = [
        _learning_approval_manual_gate_row(item)
        for item in (readiness_report or {}).get("manual_gates", [])
        if isinstance(item, dict)
    ]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "learning_tasks",
        "task_count": len(task_rows),
        "bucket_count": len(bucket_rows),
        "draft_answer_count": sum(1 for row in task_rows if row.get("draft_answer")),
        "persist_allowed_count": sum(1 for row in task_rows if row.get("persist_allowed")),
        "exact_user_confirmation_count": sum(
            1 for row in task_rows if row.get("bucket") == "exact_user_confirmation"
        ),
        "missing_user_answer_count": sum(1 for row in task_rows if not row.get("draft_answer")),
        "manual_gate_count": len(manual_gate_rows),
        "position_learning_queue_count": int((readiness_report or {}).get("learning_queue_count") or 0),
        "positions_needing_learning": int(
            ((readiness_report or {}).get("readiness_counts") or {}).get("needs_learning") or 0
        ),
        "ready_to_apply_after_approval": not task_rows and not manual_gate_rows,
        "real_submit_policy": "supervised_final_submit_only",
    }
    return {
        "generated_at": summary["generated_at"],
        "summary": summary,
        "buckets": bucket_rows,
        "tasks": task_rows,
        "manual_gates": manual_gate_rows,
        "instructions": (
            "Review draft answers, set approved=true in the learning template only for "
            "truthful non-sensitive answers, then run apply-learning. High-risk and "
            "manual-gate rows stay supervised."
        ),
    }


def write_learning_approval_pack(
    learning_tasks: dict[str, Any],
    readiness_report: dict[str, Any],
    json_output: str | Path,
    markdown_output: str | Path,
) -> dict[str, Any]:
    pack = build_learning_approval_pack(learning_tasks, readiness_report)
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(pack, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(render_learning_approval_pack_markdown(pack), encoding="utf-8")
    return pack


def render_learning_approval_pack_markdown(pack: dict[str, Any]) -> str:
    summary = pack.get("summary") or {}
    lines = [
        "# Learning Approval Pack",
        "",
        f"Generated: {pack.get('generated_at')}",
        f"Learning tasks: {summary.get('task_count', 0)}",
        f"Draft answers ready to review: {summary.get('draft_answer_count', 0)}",
        f"Missing user answers: {summary.get('missing_user_answer_count', 0)}",
        f"Exact user confirmations: {summary.get('exact_user_confirmation_count', 0)}",
        f"Manual gates: {summary.get('manual_gate_count', 0)}",
        "",
        str(pack.get("instructions") or ""),
        "",
        "## Buckets",
        "",
    ]
    for bucket in pack.get("buckets", []):
        lines.append(
            "- {title}: {count} task(s), {drafts} draft answer(s), {observed} observed prompt(s)".format(
                title=bucket.get("title"),
                count=bucket.get("task_count", 0),
                drafts=bucket.get("draft_answer_count", 0),
                observed=bucket.get("observed_count", 0),
            )
        )
        lines.append(f"  action: {bucket.get('recommended_action')}")

    lines.extend(["", "## Tasks", ""])
    tasks = pack.get("tasks", [])
    if not tasks:
        lines.append("- None")
    for task in tasks[:80]:
        lines.append(
            "- {bucket}: {question}".format(
                bucket=task.get("bucket_title"),
                question=task.get("question") or "Unknown question",
            )
        )
        if task.get("draft_answer"):
            lines.append(f"  draft: {task.get('draft_answer')}")
        lines.append(
            "  risk: {risk}; storage: {storage}; prompts: {count}".format(
                risk=task.get("approval_risk"),
                storage=task.get("recommended_storage"),
                count=task.get("related_prompt_count", 0),
            )
        )
        if task.get("approval_note"):
            lines.append(f"  note: {task.get('approval_note')}")
        labels = task.get("labels") or []
        if labels:
            lines.append(f"  labels: {'; '.join(str(label) for label in labels[:3])}")

    lines.extend(["", "## Manual Gates", ""])
    gates = pack.get("manual_gates", [])
    if not gates:
        lines.append("- None")
    for gate in gates[:40]:
        lines.append(
            "- {status}: {label} ({count} observed)".format(
                status=gate.get("coverage_status"),
                label=gate.get("label"),
                count=gate.get("observed_count", 0),
            )
        )
        if gate.get("handling"):
            lines.append(f"  handling: {gate.get('handling')}")
    return "\n".join(lines) + "\n"


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
    category_policy_updates: dict[str, str] = {}
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
            category = _category_default_policy_from_group_key(group_key)
            if category:
                category_policy_updates[category] = answer
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
        if category_policy_updates:
            for category, answer in category_policy_updates.items():
                _learn_category_default_policy(
                    memory,
                    category,
                    answer,
                    sample_question=f"Default policy for {category}",
                    source=source,
                )
            save_answer_memory(memory_path, memory)

    return {
        "dry_run": dry_run,
        "profile_updates": sorted(profile_updates.keys()),
        "answer_memory_updates": sorted(answer_updates.keys()),
        "category_policy_updates": sorted(category_policy_updates.keys()),
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
        if task.get("answer_scope"):
            lines.append(f"  scope: {task.get('answer_scope')}")
        if task.get("automation_behavior"):
            lines.append(f"  automation: {task.get('automation_behavior')}")
        if task.get("suggested_answer"):
            lines.append(f"  suggested: {task.get('suggested_answer')}")
        if task.get("suggested_answer_source"):
            lines.append(
                "  suggestion: {source}; confidence={confidence}; risk={risk}".format(
                    source=task.get("suggested_answer_source"),
                    confidence=task.get("suggestion_confidence"),
                    risk=task.get("approval_risk"),
                )
            )
        if task.get("approval_note"):
            lines.append(f"  note: {task.get('approval_note')}")
        if task.get("platforms"):
            lines.append(f"  platforms: {', '.join(str(item) for item in task.get('platforms', []))}")
        if task.get("labels"):
            label_text = "; ".join(str(item) for item in task.get("labels", [])[:5])
            lines.append(f"  labels: {label_text}")
        lines.append(f"  persist_allowed: {str(bool(task.get('persist_allowed'))).lower()}")
        if task.get("notes"):
            lines.append(f"  notes: {task.get('notes')}")
    return "\n".join(lines) + "\n"


def build_fake_learning_probe(
    research: dict[str, Any],
    learning_tasks: dict[str, Any],
    baseline_gaps: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fake_profile, profile_updates = _fake_profile_for_learning_tasks(learning_tasks)
    fake_memory, answer_summary = _fake_answer_memory_for_learning_tasks(learning_tasks)
    fake_gaps = build_answer_gap_report(
        research,
        profile=fake_profile,
        answer_memory=fake_memory,
    )
    fake_readiness = build_position_readiness_report(research, fake_gaps)
    remaining_learning = [
        _fake_probe_prompt_row(item)
        for item in fake_gaps.get("blocking_prompts", [])
        if item.get("coverage_status") in _LEARNING_BLOCKER_STATUSES
    ]
    remaining_manual = [
        _fake_probe_prompt_row(item)
        for item in fake_gaps.get("blocking_prompts", [])
        if item.get("coverage_status") in _MANUAL_GATE_STATUSES
    ]
    baseline_blocking = int((baseline_gaps or {}).get("blocking_prompt_count") or 0)
    fake_blocking = int(fake_gaps.get("blocking_prompt_count") or 0)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "fake_learning_probe",
        "real_platform_submission": False,
        "fake_candidate": {
            "name": fake_profile.name,
            "email_domain": fake_profile.email.split("@")[-1] if "@" in fake_profile.email else "",
            "profile": "synthetic test profile only",
        },
        "input_task_count": int(learning_tasks.get("task_count") or len(learning_tasks.get("tasks", []))),
        "fake_answered_task_count": answer_summary["answered_task_count"],
        "fake_answer_memory_entry_count": len(fake_memory.get("answers", [])),
        "fake_category_policy_count": answer_summary["category_policy_count"],
        "fake_profile_updates": profile_updates,
        "fake_answer_scope_counts": answer_summary["answer_scope_counts"],
        "baseline": {
            "blocking_prompt_count": baseline_blocking,
            "coverage_counts": (baseline_gaps or {}).get("coverage_counts", {}),
        },
        "after_fake_learning": {
            "blocking_prompt_count": fake_blocking,
            "blocking_prompt_delta": fake_blocking - baseline_blocking,
            "ready_prompt_count": int(fake_gaps.get("ready_prompt_count") or 0),
            "coverage_counts": fake_gaps.get("coverage_counts", {}),
            "learning_queue_count": int(fake_readiness.get("learning_queue_count") or 0),
            "minimal_learning_task_count": int(fake_readiness.get("minimal_learning_task_count") or 0),
            "manual_gate_count": int(fake_readiness.get("manual_gate_count") or 0),
            "readiness_counts": fake_readiness.get("readiness_counts", {}),
        },
        "remaining_learning_blocker_count": len(remaining_learning),
        "remaining_manual_gate_count": len(remaining_manual),
        "learning_blockers_cleared": len(remaining_learning) == 0,
        "remaining_learning_blockers": remaining_learning[:100],
        "remaining_manual_gates": remaining_manual[:100],
        "policy": {
            "uses_fake_candidate_only": True,
            "writes_real_profile_or_memory": False,
            "submits_real_applications": False,
            "sensitive_final_and_security_gates_remain_blocking": True,
        },
    }


def write_fake_learning_probe(
    research: dict[str, Any],
    learning_tasks: dict[str, Any],
    baseline_gaps: dict[str, Any] | None,
    json_output: str | Path,
    markdown_output: str | Path,
) -> dict[str, Any]:
    report = build_fake_learning_probe(
        research,
        learning_tasks,
        baseline_gaps=baseline_gaps,
    )
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(render_fake_learning_probe_markdown(report), encoding="utf-8")
    return report


def render_fake_learning_probe_markdown(report: dict[str, Any]) -> str:
    after = report.get("after_fake_learning") or {}
    lines = [
        "# Fake Learning Probe",
        "",
        f"Generated: {report.get('generated_at')}",
        f"Real platform submission: {str(bool(report.get('real_platform_submission'))).lower()}",
        f"Input learning tasks: {report.get('input_task_count', 0)}",
        f"Fake answered tasks: {report.get('fake_answered_task_count', 0)}",
        f"Fake answer memory entries: {report.get('fake_answer_memory_entry_count', 0)}",
        f"Fake category policies: {report.get('fake_category_policy_count', 0)}",
        f"Baseline blockers: {(report.get('baseline') or {}).get('blocking_prompt_count', 0)}",
        f"After fake learning blockers: {after.get('blocking_prompt_count', 0)}",
        f"Remaining learning blockers: {report.get('remaining_learning_blocker_count', 0)}",
        f"Remaining manual gates: {report.get('remaining_manual_gate_count', 0)}",
        f"Learning blockers cleared: {str(bool(report.get('learning_blockers_cleared'))).lower()}",
        "",
        "## Coverage Counts",
        "",
    ]
    for key, value in sorted((after.get("coverage_counts") or {}).items()):
        lines.append(f"- {key}: {value}")
    if report.get("remaining_learning_blockers"):
        lines.extend(["", "## Remaining Learning Blockers", ""])
        for item in report.get("remaining_learning_blockers", [])[:20]:
            lines.append(
                "- {status}: {label} ({category}; observed {count}x)".format(
                    status=item.get("coverage_status"),
                    label=item.get("label"),
                    category=item.get("category"),
                    count=item.get("observed_count"),
                )
            )
    if report.get("remaining_manual_gates"):
        lines.extend(["", "## Remaining Manual Gates", ""])
        for item in report.get("remaining_manual_gates", [])[:20]:
            lines.append(
                "- {status}: {label} ({category}; observed {count}x)".format(
                    status=item.get("coverage_status"),
                    label=item.get("label"),
                    category=item.get("category"),
                    count=item.get("observed_count"),
                )
            )
    return "\n".join(lines) + "\n"


def build_fake_position_rehearsal(
    research: dict[str, Any],
    learning_tasks: dict[str, Any],
    limit: int = 100,
    closed_jobs: dict[str, Any] | None = None,
    include_values: bool = False,
    allow_local_synthetic_submit: bool = False,
    per_platform_role_target: int | None = None,
    target_platforms: list[str] | None = None,
    target_role_families: list[str] | None = None,
) -> dict[str, Any]:
    fake_profile, profile_updates = _fake_profile_for_learning_tasks(learning_tasks)
    fake_memory, answer_summary = _fake_answer_memory_for_learning_tasks(learning_tasks)
    items_by_position = _research_items_by_position(research)
    selection = _select_fake_rehearsal_positions(
        research,
        items_by_position,
        limit=limit,
        closed_jobs=closed_jobs,
        per_platform_role_target=per_platform_role_target,
        target_platforms=target_platforms,
        target_role_families=target_role_families,
    )

    executions: list[dict[str, Any]] = []
    for index, position in enumerate(selection["selected_positions"], start=1):
        position_key = str(position.get("position_key") or "")
        position_items = items_by_position.get(position_key, [])
        snapshot = _observed_position_snapshot(
            position,
            position_items,
        )
        plan = build_form_fill_plan(
            snapshot,
            profile=fake_profile,
            answer_memory=fake_memory,
            include_values=include_values,
        )
        manifest = build_browser_action_manifest(
            plan,
            page_text=str(snapshot.get("page_text") or ""),
            closed_jobs=closed_jobs,
            include_values=include_values,
        )
        pre_counts = _pre_synthetic_stop_counts(manifest)
        execution = execute_browser_action_manifest_locally(
            manifest,
            snapshot,
            allow_local_synthetic_submit=allow_local_synthetic_submit,
        )
        execution.update(
            {
                "index": index,
                "position_key": position_key,
                "company": position.get("company"),
                "job_title": position.get("title"),
                "role_variant": position.get("title"),
                "role_family": position.get("role_family"),
                "apply_url": position.get("apply_url"),
                "prompt_count": len(position_items),
                "inferred_prompt_count": sum(
                    1 for item in position_items if item.get("item_type") == "inferred_question"
                ),
                "manifest_status": manifest.get("status"),
                "pre_synthetic_missing_input_count": pre_counts["missing_input_count"],
                "pre_synthetic_manual_security_count": pre_counts["manual_security_count"],
                "pre_synthetic_sensitive_gate_count": pre_counts["sensitive_gate_count"],
                "pre_synthetic_final_submit_count": pre_counts["final_submit_count"],
                "pre_synthetic_stop_action_count": pre_counts["stop_action_count"],
            }
        )
        executions.append(execution)

    platform_counts = _count_by(executions, "platform")
    role_variant_counts = _count_by(executions, "role_variant")
    role_family_counts = _count_by(executions, "role_family")
    platform_role_family_counts = _platform_role_family_counts(executions)
    platform_role_target = int(per_platform_role_target or 0)
    target_platforms = selection.get("target_platforms", [])
    target_role_families = selection.get("target_role_families", [])
    actual_submit_count = sum(int(item.get("actual_submit_count", 0)) for item in executions)
    selector_miss_count = sum(int(item.get("selector_miss_count", 0)) for item in executions)
    pre_missing_count = sum(int(item.get("pre_synthetic_missing_input_count", 0)) for item in executions)
    expected_blocker_count = sum(
        1
        for item in executions
        if str(item.get("policy_stop") or "") in {"closed_posting", "manual_security_step"}
    )
    eligible_submit_target_count = sum(
        1
        for item in executions
        if int(item.get("pre_synthetic_missing_input_count", 0)) == 0
        and int(item.get("pre_synthetic_manual_security_count", 0)) == 0
        and str(item.get("policy_stop") or "") != "closed_posting"
    )
    unexpected_runs = _fake_rehearsal_unexpected_runs(executions)
    eligible_submit_achieved = (
        bool(allow_local_synthetic_submit)
        and selector_miss_count == 0
        and pre_missing_count == 0
        and actual_submit_count == eligible_submit_target_count
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "fake_position_rehearsal",
        "execution": "observed_prompt_local_browser_manifest_executor",
        "requested_count": int(selection.get("requested_count") or max(int(limit), 0)),
        "per_platform_role_target": platform_role_target,
        "platform_role_target_achieved": (
            all(count == 0 for count in (selection.get("platform_role_target_shortfalls") or {}).values())
            if platform_role_target
            else None
        ),
        "platform_role_target_shortfalls": selection.get("platform_role_target_shortfalls", {}),
        "target_platforms": target_platforms,
        "target_role_families": target_role_families,
        "run_count": len(executions),
        "real_platform_submission": False,
        "local_synthetic_submit_allowed": bool(allow_local_synthetic_submit),
        "actual_submit_count": actual_submit_count,
        "would_submit_count": sum(1 for item in executions if bool(item.get("would_submit"))),
        "eligible_submit_target_count": eligible_submit_target_count,
        "eligible_submit_count": actual_submit_count,
        "eligible_submit_achieved": eligible_submit_achieved,
        "expected_blocker_count": expected_blocker_count,
        "selector_miss_count": selector_miss_count,
        "pre_synthetic_missing_input_count": pre_missing_count,
        "pre_synthetic_manual_security_count": sum(
            int(item.get("pre_synthetic_manual_security_count", 0)) for item in executions
        ),
        "pre_synthetic_sensitive_gate_count": sum(
            int(item.get("pre_synthetic_sensitive_gate_count", 0)) for item in executions
        ),
        "pre_synthetic_final_submit_count": sum(
            int(item.get("pre_synthetic_final_submit_count", 0)) for item in executions
        ),
        "unexpected_run_count": len(unexpected_runs),
        "excluded_closed_position_count": len(selection["excluded_closed_positions"]),
        "skipped_no_prompt_position_count": len(selection["skipped_no_prompt_positions"]),
        "source_position_count": len(research.get("positions", []) or []),
        "source_prompt_item_count": len(research.get("items", []) or []),
        "inferred_prompt_item_count": sum(
            int(item.get("inferred_prompt_count", 0)) for item in executions
        ),
        "inferred_prompt_position_count": sum(
            1 for item in executions if int(item.get("inferred_prompt_count", 0)) > 0
        ),
        "fake_answer_memory_entry_count": len(fake_memory.get("answers", [])),
        "fake_category_policy_count": answer_summary["category_policy_count"],
        "fake_profile_updates": profile_updates,
        "outcome_counts": _count_by(executions, "outcome"),
        "policy_stop_counts": _count_by(executions, "policy_stop"),
        "platform_counts": platform_counts,
        "role_variant_counts": role_variant_counts,
        "role_family_counts": role_family_counts,
        "platform_role_family_counts": platform_role_family_counts,
        "executed_action_count": sum(int(item.get("executed_action_count", 0)) for item in executions),
        "stop_action_count": sum(int(item.get("stop_action_count", 0)) for item in executions),
        "synthetic_gate_answer_count": sum(
            int(item.get("synthetic_gate_answer_count", 0)) for item in executions
        ),
        "selected_positions": [
            _fake_rehearsal_position_row(item) for item in selection["selected_positions"]
        ],
        "excluded_closed_positions": selection["excluded_closed_positions"][:100],
        "skipped_no_prompt_positions": selection["skipped_no_prompt_positions"][:100],
        "unexpected_runs": unexpected_runs[:100],
        "runs": executions,
        "policy": {
            "uses_fake_candidate_only": True,
            "real_platform_submission": False,
            "local_synthetic_submit_only": bool(allow_local_synthetic_submit),
            "fake_data_real_submission_allowed": False,
            "closed_jobs_excluded_before_rehearsal": True,
            "closed_page_text_still_stops_execution": True,
            "remote_employer_final_submit_blocked": True,
            "captcha_or_security_not_bypassed": True,
        },
    }


def write_fake_position_rehearsal(
    research: dict[str, Any],
    learning_tasks: dict[str, Any],
    json_output: str | Path,
    markdown_output: str | Path,
    limit: int = 100,
    closed_jobs: dict[str, Any] | None = None,
    include_values: bool = False,
    allow_local_synthetic_submit: bool = False,
    per_platform_role_target: int | None = None,
    target_platforms: list[str] | None = None,
    target_role_families: list[str] | None = None,
) -> dict[str, Any]:
    report = build_fake_position_rehearsal(
        research,
        learning_tasks,
        limit=limit,
        closed_jobs=closed_jobs,
        include_values=include_values,
        allow_local_synthetic_submit=allow_local_synthetic_submit,
        per_platform_role_target=per_platform_role_target,
        target_platforms=target_platforms,
        target_role_families=target_role_families,
    )
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(render_fake_position_rehearsal_markdown(report), encoding="utf-8")
    return report


def render_fake_position_rehearsal_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Fake Position Rehearsal",
        "",
        f"Generated: {report.get('generated_at')}",
        f"Runs: {report.get('run_count', 0)} / {report.get('requested_count', 0)}",
        f"Execution: {report.get('execution')}",
        f"Per-platform-role target: {report.get('per_platform_role_target', 0)}",
        f"Platform-role target achieved: {str(report.get('platform_role_target_achieved')).lower()}",
        f"Real platform submission: {str(bool(report.get('real_platform_submission'))).lower()}",
        f"Local synthetic submit allowed: {str(bool(report.get('local_synthetic_submit_allowed'))).lower()}",
        f"Local synthetic submit count: {report.get('actual_submit_count', 0)}",
        f"Eligible synthetic submit count: {report.get('eligible_submit_count', 0)} / {report.get('eligible_submit_target_count', 0)}",
        f"Eligible submit achieved: {str(bool(report.get('eligible_submit_achieved'))).lower()}",
        f"Selector misses: {report.get('selector_miss_count', 0)}",
        f"Pre-synthetic missing inputs: {report.get('pre_synthetic_missing_input_count', 0)}",
        f"Manual security gates: {report.get('pre_synthetic_manual_security_count', 0)}",
        f"Inferred prompt positions: {report.get('inferred_prompt_position_count', 0)}",
        f"Inferred prompt items: {report.get('inferred_prompt_item_count', 0)}",
        f"Excluded closed positions: {report.get('excluded_closed_position_count', 0)}",
        f"Unexpected runs: {report.get('unexpected_run_count', 0)}",
        "",
        "## Outcome Counts",
        "",
    ]
    for outcome, count in sorted((report.get("outcome_counts") or {}).items()):
        lines.append(f"- {outcome}: {count}")
    lines.extend(["", "## Policy Stop Counts", ""])
    for stop, count in sorted((report.get("policy_stop_counts") or {}).items()):
        lines.append(f"- {stop}: {count}")
    lines.extend(["", "## Platform Counts", ""])
    for platform, count in sorted((report.get("platform_counts") or {}).items()):
        lines.append(f"- {platform}: {count}")
    if report.get("role_family_counts"):
        lines.extend(["", "## Role Family Counts", ""])
        for role_family, count in sorted((report.get("role_family_counts") or {}).items()):
            lines.append(f"- {role_family}: {count}")
    if report.get("platform_role_family_counts"):
        lines.extend(["", "## Platform Role Family Counts", ""])
        for key, count in sorted((report.get("platform_role_family_counts") or {}).items()):
            lines.append(f"- {key}: {count}")
    if report.get("platform_role_target_shortfalls"):
        lines.extend(["", "## Platform Role Target Shortfalls", ""])
        for key, count in sorted((report.get("platform_role_target_shortfalls") or {}).items()):
            if int(count or 0):
                lines.append(f"- {key}: {count}")
        if all(int(count or 0) == 0 for count in (report.get("platform_role_target_shortfalls") or {}).values()):
            lines.append("- None")
    if report.get("unexpected_runs"):
        lines.extend(["", "## Unexpected Runs", ""])
        for run in report.get("unexpected_runs", [])[:20]:
            lines.append(
                "- {outcome}: {company} - {title} [{platform}; stop={stop}; missing={missing}; misses={misses}]".format(
                    outcome=run.get("outcome"),
                    company=run.get("company") or "Unknown company",
                    title=run.get("job_title") or run.get("title") or "Unknown title",
                    platform=run.get("platform") or "Unknown",
                    stop=run.get("policy_stop"),
                    missing=run.get("pre_synthetic_missing_input_count", 0),
                    misses=run.get("selector_miss_count", 0),
                )
            )
    lines.extend(["", "## First Runs", ""])
    for run in report.get("runs", [])[:20]:
        lines.append(
            "- {outcome}: {company} - {title} [{platform}; actions={actions}; submit={submit}; stop={stop}]".format(
                outcome=run.get("outcome"),
                company=run.get("company") or "Unknown company",
                title=run.get("job_title") or run.get("title") or "Unknown title",
                platform=run.get("platform") or "Unknown",
                actions=run.get("executed_action_count", 0),
                submit=run.get("actual_submit_count", 0),
                stop=run.get("policy_stop"),
            )
        )
    return "\n".join(lines) + "\n"


def _fake_profile_for_learning_tasks(
    learning_tasks: dict[str, Any],
) -> tuple[CandidateProfile, list[str]]:
    profile = build_synthetic_candidate_profile()
    question_answers = dict(profile.question_answers)
    resume_facts = dict(profile.resume_facts)
    updates: list[str] = []
    for task in learning_tasks.get("tasks", []):
        if not isinstance(task, dict):
            continue
        group_key = str(task.get("group_key") or "")
        storage = str(task.get("recommended_storage") or "")
        if group_key == "profile:zip_or_postal_code":
            question_answers["zip_code"] = "98101"
            updates.append("question_answers.zip_code")
        elif group_key == "profile:profile_links":
            question_answers.setdefault(
                "linkedin_profile",
                "https://www.linkedin.com/in/fake-synthetic-candidate/",
            )
            updates.append("question_answers.linkedin_profile")
        elif group_key == "local_material:resume_file":
            question_answers["resume_path"] = "/tmp/fake-synthetic-resume.pdf"
            updates.append("question_answers.resume_path")
        elif storage == "resume_facts":
            if group_key == "resume_facts:education_grading":
                resume_facts["grading_system"] = "Not applicable for synthetic candidate."
                updates.append("resume_facts.grading_system")
            else:
                normalized = _normalize(group_key)
                key = normalized.replace(" ", "_")[:60] or "synthetic_resume_fact"
                resume_facts[key] = "Synthetic candidate has the requested resume fact."
                updates.append(f"resume_facts.{key}")
    return (
        CandidateProfile(
            name=profile.name,
            email=profile.email,
            phone=profile.phone,
            location=profile.location,
            target_titles=profile.target_titles,
            target_locations=profile.target_locations,
            remote_ok=profile.remote_ok,
            keywords=profile.keywords,
            blocklist=profile.blocklist,
            min_score=profile.min_score,
            resume_facts=resume_facts,
            question_answers=question_answers,
        ),
        sorted(set(updates)),
    )


def _fake_answer_memory_for_learning_tasks(
    learning_tasks: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    memory: dict[str, Any] = {"version": 1, "answers": []}
    answered_task_count = 0
    category_policy_count = 0
    answer_scope_counts: dict[str, int] = {}
    for task in learning_tasks.get("tasks", []):
        if not isinstance(task, dict):
            continue
        storage = str(task.get("recommended_storage") or "")
        if storage not in {"answer_memory", "supervised_confirmation"}:
            continue
        answer = _fake_learning_answer_for_task(task)
        if not answer:
            continue
        answered_task_count += 1
        scope = str(task.get("answer_scope") or _learning_task_answer_scope(str(task.get("group_key") or ""), storage))
        answer_scope_counts[scope] = answer_scope_counts.get(scope, 0) + 1
        group_key = str(task.get("group_key") or "")
        category = _category_default_policy_from_group_key(group_key)
        if category:
            _learn_category_default_policy(
                memory,
                category,
                answer,
                sample_question=f"Synthetic default policy for {category}",
                source="fake_learning_probe",
            )
            category_policy_count += 1
        labels = [str(label) for label in _string_list(task.get("labels")) if str(label).strip()]
        if not labels:
            labels = [str(task.get("question") or "")]
        for label in labels:
            _append_fake_answer_memory_entry(memory, label, answer)
    return (
        memory,
        {
            "answered_task_count": answered_task_count,
            "category_policy_count": category_policy_count,
            "answer_scope_counts": dict(sorted(answer_scope_counts.items())),
        },
    )


def _append_fake_answer_memory_entry(
    memory: dict[str, Any],
    question: str,
    answer: str,
) -> None:
    normalized = _normalize_question(question)
    if not normalized or not str(answer).strip():
        return
    entries = memory.setdefault("answers", [])
    if any(
        entry.get("normalized_question") == normalized
        and entry.get("answer") == str(answer).strip()
        for entry in entries
    ):
        return
    now = datetime.now(timezone.utc).isoformat()
    entries.append(
        {
            "normalized_question": normalized,
            "sample_question": question,
            "answer": str(answer).strip(),
            "approved_count": 1,
            "source": "fake_learning_probe",
            "first_seen_at": now,
            "last_seen_at": now,
            "example_job": {
                "platform": "synthetic",
                "company": "Fake Learning Probe",
                "title": "Synthetic automation verification",
                "job_id": "fake-learning-probe",
            },
        }
    )


def _fake_learning_answer_for_task(task: dict[str, Any]) -> str:
    suggested = str(task.get("suggested_answer") or "").strip()
    if suggested:
        return suggested
    group_key = str(task.get("group_key") or "")
    category = _category_default_policy_from_group_key(group_key)
    if category:
        category_answers = {
            "background_or_export_control": "Synthetic candidate has no disqualifying background or export-control issues.",
            "citizenship_status": "Synthetic candidate is a U.S. citizen and U.S. person where required.",
            "country_work_permit": "Synthetic candidate is authorized to work in the country for this synthetic role.",
            "health_requirement": "Synthetic candidate can meet job-related health or vaccination requirements.",
            "interview_recording_consent": "Yes, synthetic candidate consents to interview recording for recruiting review.",
        }
        if category in category_answers:
            return category_answers[category]
        return _category_default_policy_suggestion(category, {}, None).get(
            "suggested_answer",
            "Synthetic candidate default answer.",
        )
    label = " ".join([str(task.get("question") or ""), *(_string_list(task.get("labels"))[:3])])
    classification = classify_application_prompt(label)
    if classification.category == "policy_acknowledgement":
        return "Yes, synthetic candidate acknowledges this policy or disclosure for test purposes."
    if classification.category in {"skills_experience", "technical_experience"}:
        return "Yes, synthetic candidate has four years of relevant hands-on experience."
    if classification.category == "language_ability":
        return "English."
    if classification.category in {"compensation", "salary"}:
        return "$100,000+ base salary."
    text = _normalize(label)
    if "yes" in text or "do you" in text or "have you" in text or "are you" in text:
        return "Yes, for this synthetic candidate."
    return "Synthetic candidate test answer."


def _fake_probe_prompt_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "coverage_status": item.get("coverage_status"),
        "label": item.get("label"),
        "category": item.get("category"),
        "automation_action": item.get("automation_action"),
        "observed_count": item.get("observed_count", 0),
        "required_count": item.get("required_count", 0),
        "platforms": item.get("platforms", []),
        "next_action": item.get("next_action"),
    }


def _research_items_by_position(research: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in research.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        position_key = str(item.get("position_key") or "")
        if not position_key:
            continue
        grouped.setdefault(position_key, []).append(item)
    return grouped


def _select_fake_rehearsal_positions(
    research: dict[str, Any],
    items_by_position: dict[str, list[dict[str, Any]]],
    limit: int,
    closed_jobs: dict[str, Any] | None,
    per_platform_role_target: int | None = None,
    target_platforms: list[str] | None = None,
    target_role_families: list[str] | None = None,
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    excluded_closed: list[dict[str, Any]] = []
    skipped_no_prompt: list[dict[str, Any]] = []

    for position in research.get("positions", []) or []:
        if not isinstance(position, dict):
            continue
        position_key = str(position.get("position_key") or "")
        prompt_items = items_by_position.get(position_key, [])
        if not prompt_items:
            skipped_no_prompt.append(_fake_rehearsal_position_row(position))
            continue
        closed_reason = closed_application_reason(position, closed_jobs=closed_jobs)
        if closed_reason:
            row = _fake_rehearsal_position_row(position)
            row["closed_reason"] = closed_reason
            excluded_closed.append(row)
            continue
        group_key = "{platform}::{role_family}".format(
            platform=position.get("platform") or "Unknown",
            role_family=position.get("role_family") or "Other",
        )
        grouped.setdefault(group_key, []).append(position)

    selected: list[dict[str, Any]] = []
    platform_role_shortfalls: dict[str, int] = {}
    requested_count = max(int(limit), 0)
    normalized_target_platforms: list[str] = []
    normalized_target_role_families: list[str] = []
    if per_platform_role_target is not None:
        target = max(int(per_platform_role_target), 0)
        normalized_target_platforms = [
            str(platform)
            for platform in (target_platforms or list(SYNTHETIC_APPLICATION_PLATFORMS))
            if str(platform).strip()
        ]
        normalized_target_role_families = [
            str(role_family)
            for role_family in (target_role_families or _default_target_role_families())
            if str(role_family).strip()
        ]
        requested_count = target * len(normalized_target_platforms) * len(normalized_target_role_families)
        for platform in normalized_target_platforms:
            for role_family in normalized_target_role_families:
                group_key = f"{platform}::{role_family}"
                available = grouped.get(group_key, [])
                selected.extend(available[:target])
                platform_role_shortfalls[group_key] = max(0, target - len(available[:target]))
    else:
        group_keys = sorted(grouped)
        target = requested_count
        while len(selected) < target and any(grouped.get(key) for key in group_keys):
            for key in group_keys:
                if len(selected) >= target:
                    break
                if grouped.get(key):
                    selected.append(grouped[key].pop(0))

    return {
        "selected_positions": selected,
        "excluded_closed_positions": excluded_closed,
        "skipped_no_prompt_positions": skipped_no_prompt,
        "requested_count": requested_count,
        "per_platform_role_target": int(per_platform_role_target or 0),
        "target_platforms": normalized_target_platforms,
        "target_role_families": normalized_target_role_families,
        "platform_role_target_shortfalls": dict(sorted(platform_role_shortfalls.items())),
    }


def _observed_position_snapshot(
    position: dict[str, Any],
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []
    buttons: list[dict[str, Any]] = []
    seen: set[str] = set()
    field_index = 1
    for item in items:
        label = str(item.get("label") or "").strip()
        normalized = _normalize_question(label)
        if not label or normalized in seen:
            continue
        seen.add(normalized)
        control = _observed_research_item_control(item, field_index)
        if _observed_item_is_submit_button(item):
            buttons.append(control)
        else:
            fields.append(control)
        field_index += 1
    if not any(_observed_item_is_submit_button(button) for button in buttons):
        buttons.append(
            {
                "i": field_index,
                "text": "Submit application",
                "tag": "BUTTON",
                "required": True,
            }
        )
    title = str(position.get("title") or "Observed role")
    company = str(position.get("company") or "Observed company")
    return {
        "title": f"{company} application",
        "company": company,
        "job_title": title,
        "role_variant": title,
        "role_family": position.get("role_family") or _infer_role_family(title),
        "platform": position.get("platform") or infer_platform_from_url(str(position.get("apply_url") or "")) or "Unknown",
        "url": position.get("apply_url"),
        "page_text": f"Local fake rehearsal for {title}; original page is not submitted.",
        "fields": fields,
        "buttons": buttons,
    }


def _observed_research_item_control(item: dict[str, Any], field_index: int) -> dict[str, Any]:
    label = str(item.get("label") or "").strip()
    category = str(item.get("category") or "")
    tag = _observed_research_item_tag(item)
    control: dict[str, Any] = {
        "i": field_index,
        "label": label,
        "tag": tag,
        "required": _truthy(item.get("required")),
    }
    if _observed_item_is_submit_button(item):
        control.pop("label", None)
        control["text"] = label or "Submit application"
        control["tag"] = "BUTTON"
    elif category in {"resume_upload", "cover_letter_upload", "file_upload"}:
        control["type"] = "file"
    elif category == "policy_acknowledgement":
        control["type"] = "checkbox"
    elif category == "manual_security_step":
        control["name"] = "g-recaptcha-response"
    return control


def _observed_research_item_tag(item: dict[str, Any]) -> str:
    category = str(item.get("category") or "")
    label = _normalize(str(item.get("label") or ""))
    if _observed_item_is_submit_button(item):
        return "BUTTON"
    if category in {"role_specific_free_text", "skills_experience", "technical_experience"}:
        return "TEXTAREA"
    if category == "manual_security_step":
        return "TEXTAREA"
    if category in {"policy_acknowledgement", "resume_upload", "cover_letter_upload", "file_upload"}:
        return "INPUT"
    if any(term in label for term in ["describe", "explain", "why", "details", "tell us"]):
        return "TEXTAREA"
    if category in {
        "authorization",
        "sponsorship",
        "relocation",
        "communication_consent",
        "citizenship_status",
        "country_work_permit",
        "sensitive_demographic",
    }:
        return "SELECT"
    return "INPUT"


def _observed_item_is_submit_button(item: dict[str, Any]) -> bool:
    category = str(item.get("category") or "")
    label = _normalize(str(item.get("label") or item.get("text") or ""))
    return category == "final_submit" or label in {
        "submit",
        "submit application",
        "submit my application",
        "send application",
        "apply",
    }


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    text = _normalize(str(value))
    if text in {"", "0", "false", "no", "none", "null"}:
        return False
    return True


def _pre_synthetic_stop_counts(manifest: dict[str, Any]) -> dict[str, int]:
    missing_statuses = {
        "missing_profile_value",
        "missing_local_material",
        "missing_answer",
        "missing_resume_facts",
    }
    stops = [stop for stop in manifest.get("stop_actions", []) if isinstance(stop, dict)]
    return {
        "stop_action_count": len(stops),
        "missing_input_count": sum(1 for stop in stops if str(stop.get("status") or "") in missing_statuses),
        "manual_security_count": sum(1 for stop in stops if str(stop.get("status") or "") == "manual_security_step"),
        "sensitive_gate_count": sum(1 for stop in stops if str(stop.get("status") or "") == "sensitive_not_stored"),
        "final_submit_count": sum(1 for stop in stops if str(stop.get("status") or "") == "final_submit_confirmation"),
    }


def _fake_rehearsal_unexpected_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expected_policy_stops = {
        "local_synthetic_submit_allowed",
        "manual_security_step",
        "closed_posting",
        "final_submit_confirmation",
        "final_submit_not_requested",
    }
    unexpected: list[dict[str, Any]] = []
    for run in runs:
        if int(run.get("selector_miss_count", 0)):
            unexpected.append(_fake_rehearsal_run_row(run))
            continue
        if int(run.get("pre_synthetic_missing_input_count", 0)):
            unexpected.append(_fake_rehearsal_run_row(run))
            continue
        policy_stop = str(run.get("policy_stop") or "")
        if policy_stop not in expected_policy_stops:
            unexpected.append(_fake_rehearsal_run_row(run))
    return unexpected


def _fake_rehearsal_run_row(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": run.get("index"),
        "position_key": run.get("position_key"),
        "platform": run.get("platform"),
        "company": run.get("company"),
        "job_title": run.get("job_title") or run.get("title"),
        "role_family": run.get("role_family"),
        "apply_url": run.get("apply_url") or run.get("url"),
        "outcome": run.get("outcome"),
        "policy_stop": run.get("policy_stop"),
        "selector_miss_count": run.get("selector_miss_count", 0),
        "pre_synthetic_missing_input_count": run.get("pre_synthetic_missing_input_count", 0),
        "pre_synthetic_manual_security_count": run.get("pre_synthetic_manual_security_count", 0),
    }


def _fake_rehearsal_position_row(position: dict[str, Any]) -> dict[str, Any]:
    return {
        "position_key": position.get("position_key"),
        "platform": position.get("platform"),
        "company": position.get("company"),
        "title": position.get("title"),
        "role_family": position.get("role_family"),
        "apply_url": position.get("apply_url"),
    }


def _platform_role_family_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        platform = str(item.get("platform") or "Unknown")
        role_family = str(item.get("role_family") or "Other")
        key = f"{platform} | {role_family}"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


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
            "graduation_date": "2021-06",
            "grading_system": "Not applicable for synthetic candidate.",
            "current_role": "Site Reliability Engineer at Synthetic Infrastructure Labs",
            "employment_dates": "2021-07 to Present",
            "current_role_start_month": "July",
            "current_role_start_year": "2021",
            "current_role_end_month": "Present",
            "current_role_end_year": "Present",
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
            "compensation_currency": "USD",
            "age_over_18": "Yes",
            "ai_application_disclosure": "Yes",
            "referral_source": "LinkedIn",
            "referral_contact": "N/A - no specific employee referral.",
            "remote_preference": "Very remote-friendly.",
            "onsite_hybrid": "Yes, open to onsite or hybrid work for the right role.",
            "communication_consent": "Yes, recruiting teams may contact me by SMS or WhatsApp.",
            "policy_acknowledgement": "Yes, I acknowledge.",
            "english_level": "Professional working proficiency in English.",
            "middle_name": "Quinn",
            "linkedin_profile": "https://www.linkedin.com/in/fake-synthetic-candidate/",
            "github_profile": "https://github.com/fake-synthetic-candidate",
            "portfolio": "https://fake-synthetic-candidate.example.com",
            "website": "https://fake-synthetic-candidate.example.com",
            "x_profile": "https://x.com/fake_synthetic",
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


def build_application_playbook(
    research: dict[str, Any],
    gaps: dict[str, Any] | None = None,
    readiness: dict[str, Any] | None = None,
    synthetic: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gaps = gaps or {}
    readiness = readiness or {}
    synthetic = synthetic or {}
    platform_names = set(str(name) for name in research.get("platforms", {}).keys())
    platform_names.update(str(name) for name in synthetic.get("platform_counts", {}).keys())
    platform_names.update(
        str(position.get("platform") or "Unknown")
        for position in readiness.get("positions", [])
        if isinstance(position, dict)
    )

    gap_by_prompt = {
        str(item.get("normalized_label") or ""): item
        for item in gaps.get("prompt_statuses", [])
        if isinstance(item, dict)
    }
    learning_tasks = [
        task
        for task in readiness.get("minimal_learning_tasks", [])
        if isinstance(task, dict)
    ]
    platforms: dict[str, Any] = {}
    for platform in sorted(platform_names):
        platform_items = [
            item
            for item in research.get("items", [])
            if isinstance(item, dict) and str(item.get("platform") or "Unknown") == platform
        ]
        platform_synthetic_runs = [
            run
            for run in synthetic.get("runs", [])
            if isinstance(run, dict) and str(run.get("platform") or "Unknown") == platform
        ]
        platform_positions = [
            position
            for position in readiness.get("positions", [])
            if isinstance(position, dict) and str(position.get("platform") or "Unknown") == platform
        ]
        common_prompts = []
        for item in platform_items:
            prompt_status = gap_by_prompt.get(str(item.get("normalized_label") or ""), {})
            common_prompts.append(
                {
                    "label": item.get("label"),
                    "category": item.get("category"),
                    "automation_action": item.get("automation_action"),
                    "coverage_status": prompt_status.get("coverage_status"),
                    "handling": _playbook_handling_for_status(
                        str(prompt_status.get("coverage_status") or "")
                    ),
                }
            )
        common_prompts = _dedupe_prompt_rows(common_prompts)
        blocker_prompts = [
            prompt
            for prompt in common_prompts
            if str(prompt.get("coverage_status") or "")
            in {
                "needs_answer_memory",
                "needs_profile_field",
                "needs_profile_material",
                "needs_resume_facts",
                "needs_user_confirmation",
                "manual_security_step",
                "final_submit_confirmation",
                "sensitive_not_stored",
            }
        ]
        platform_learning = [
            {
                "question": task.get("question"),
                "recommended_storage": task.get("recommended_storage"),
                "group_key": task.get("group_key"),
            }
            for task in learning_tasks
            if platform in [str(item) for item in task.get("platforms", [])]
        ]
        platforms[platform] = {
            "positions_observed": research.get("platforms", {})
            .get(platform, {})
            .get("positions_observed", 0),
            "synthetic_runs": synthetic.get("platform_counts", {}).get(platform, 0),
            "synthetic_status_counts": _count_by(platform_synthetic_runs, "status"),
            "synthetic_gate_labels": _unique_strings(
                label
                for run in platform_synthetic_runs
                for label in run.get("blocking_labels", [])
                if label
            )[:12],
            "prompt_items": len(platform_items),
            "category_counts": _count_by(platform_items, "category"),
            "automation_action_counts": _count_by(platform_items, "automation_action"),
            "coverage_status_counts": _count_by(
                [
                    gap_by_prompt.get(str(item.get("normalized_label") or ""), {})
                    for item in platform_items
                    if gap_by_prompt.get(str(item.get("normalized_label") or ""))
                ],
                "coverage_status",
            ),
            "readiness_counts": _count_by(platform_positions, "readiness"),
            "common_prompts": common_prompts[:30],
            "blocker_prompts": blocker_prompts[:30],
            "learning_tasks": platform_learning,
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "platform_application_automation_playbook",
        "positions_observed_total": research.get("positions_observed_total", 0),
        "synthetic_run_count": synthetic.get("run_count", 0),
        "platform_count": len(platforms),
        "global_rules": _application_playbook_global_rules(synthetic),
        "platforms": platforms,
    }


def build_research_coverage_gate(
    research: dict[str, Any],
    synthetic: dict[str, Any] | None = None,
    gaps: dict[str, Any] | None = None,
    position_target: int = 100,
    target_platforms: list[str] | None = None,
    target_role_families: list[str] | None = None,
) -> dict[str, Any]:
    synthetic = synthetic or {}
    gaps = gaps or {}
    target_platforms = target_platforms or list(SYNTHETIC_APPLICATION_PLATFORMS)
    target_role_families = target_role_families or _default_target_role_families()

    platform_counts = {
        platform: int(
            (research.get("platforms", {}).get(platform, {}) or {}).get(
                "positions_observed", 0
            )
        )
        for platform in target_platforms
    }
    platform_shortfalls = {
        platform: max(0, position_target - count)
        for platform, count in platform_counts.items()
    }

    coverage_groups = research.get("coverage_groups", {}) or {}
    platform_role_counts: dict[str, int] = {}
    for platform in target_platforms:
        for role_family in target_role_families:
            key = f"{platform}::{role_family}"
            platform_role_counts[key] = int(
                (coverage_groups.get(key, {}) or {}).get("positions_observed", 0)
            )
    platform_role_shortfalls = {
        key: max(0, position_target - count)
        for key, count in sorted(platform_role_counts.items())
    }

    real_platform_target_achieved = all(
        shortfall == 0 for shortfall in platform_shortfalls.values()
    )
    real_platform_role_target_achieved = all(
        shortfall == 0 for shortfall in platform_role_shortfalls.values()
    )
    synthetic_role_achieved = bool(synthetic.get("platform_role_target_achieved"))
    question_blocker_count = int((gaps or {}).get("blocking_prompt_count") or 0)
    synthetic_actual_submit_count = int(synthetic.get("actual_submit_count") or 0)
    synthetic_selector_miss_count = int(synthetic.get("selector_miss_count") or 0)
    synthetic_real_platform_submission = bool(synthetic.get("real_platform_submission"))
    synthetic_eligible_target = _synthetic_eligible_submit_target(synthetic)
    synthetic_eligible_count = int(
        synthetic.get("eligible_submit_count")
        if synthetic.get("eligible_submit_count") is not None
        else synthetic_actual_submit_count
    )
    synthetic_eligible_achieved = (
        bool(synthetic.get("eligible_submit_achieved"))
        if synthetic.get("eligible_submit_achieved") is not None
        else (
            synthetic_eligible_target > 0
            and synthetic_eligible_count == synthetic_eligible_target
            and synthetic_selector_miss_count == 0
            and not synthetic_real_platform_submission
        )
    )
    ready_for_full_automation = (
        real_platform_target_achieved
        and real_platform_role_target_achieved
        and synthetic_role_achieved
        and question_blocker_count == 0
        and synthetic_selector_miss_count == 0
        and synthetic_eligible_achieved
        and not synthetic_real_platform_submission
    )

    next_collection_targets = [
        {
            "platform": platform,
            "role_family": role_family,
            "positions_observed": platform_role_counts[f"{platform}::{role_family}"],
            "positions_remaining": platform_role_shortfalls[f"{platform}::{role_family}"],
        }
        for platform in target_platforms
        for role_family in target_role_families
        if platform_role_shortfalls[f"{platform}::{role_family}"] > 0
    ]
    next_collection_targets.sort(
        key=lambda item: (
            -int(item.get("positions_remaining") or 0),
            str(item.get("platform") or ""),
            str(item.get("role_family") or ""),
        )
    )

    observed_platforms = set(str(platform) for platform in research.get("platforms", {}).keys())
    extra_platforms = sorted(observed_platforms - set(target_platforms))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "research_coverage_gate",
        "position_target": position_target,
        "target_platforms": target_platforms,
        "target_role_families": target_role_families,
        "positions_observed_total": int(research.get("positions_observed_total") or 0),
        "real_platform_counts": platform_counts,
        "real_platform_shortfalls": platform_shortfalls,
        "real_platform_target_achieved": real_platform_target_achieved,
        "real_platform_role_counts": dict(sorted(platform_role_counts.items())),
        "real_platform_role_shortfalls": platform_role_shortfalls,
        "real_platform_role_target_achieved": real_platform_role_target_achieved,
        "observed_extra_platforms": extra_platforms,
        "synthetic": {
            "run_count": int(synthetic.get("run_count") or 0),
            "per_platform_role_target": int(synthetic.get("per_platform_role_target") or 0),
            "platform_role_target_achieved": synthetic.get("platform_role_target_achieved"),
            "local_synthetic_submit_allowed": bool(synthetic.get("local_synthetic_submit_allowed")),
            "actual_submit_count": synthetic_actual_submit_count,
            "would_submit_count": int(synthetic.get("would_submit_count") or 0),
            "eligible_submit_target_count": synthetic_eligible_target,
            "eligible_submit_count": synthetic_eligible_count,
            "eligible_submit_achieved": synthetic_eligible_achieved,
            "expected_blocker_count": int(
                synthetic.get("expected_blocker_count")
                if synthetic.get("expected_blocker_count") is not None
                else _synthetic_expected_blocker_count(synthetic)
            ),
            "real_platform_submission": synthetic_real_platform_submission,
            "selector_miss_count": synthetic_selector_miss_count,
            "platform_role_counts": synthetic.get("platform_role_counts", {}),
        },
        "questions": {
            "blocking_prompt_count": question_blocker_count,
            "coverage_counts": (gaps or {}).get("coverage_counts", {}),
        },
        "ready_for_full_automation": ready_for_full_automation,
        "next_collection_targets": next_collection_targets,
    }


def _synthetic_expected_blocker_count(synthetic: dict[str, Any]) -> int:
    policy_stop_counts = synthetic.get("policy_stop_counts") or {}
    return sum(
        int(policy_stop_counts.get(status) or 0)
        for status in ["closed_posting", "manual_security_step"]
    )


def _synthetic_eligible_submit_target(synthetic: dict[str, Any]) -> int:
    if synthetic.get("eligible_submit_target_count") is not None:
        return int(synthetic.get("eligible_submit_target_count") or 0)
    run_count = int(synthetic.get("run_count") or 0)
    return max(0, run_count - _synthetic_expected_blocker_count(synthetic))


def write_research_coverage_gate(
    research: dict[str, Any],
    synthetic: dict[str, Any] | None,
    gaps: dict[str, Any] | None,
    json_output: str | Path,
    markdown_output: str | Path,
    position_target: int = 100,
) -> dict[str, Any]:
    gate = build_research_coverage_gate(
        research,
        synthetic=synthetic,
        gaps=gaps,
        position_target=position_target,
    )
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(gate, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(render_research_coverage_gate_markdown(gate), encoding="utf-8")
    return gate


def render_research_coverage_gate_markdown(gate: dict[str, Any]) -> str:
    lines = [
        "# Research Coverage Gate",
        "",
        f"Generated: {gate.get('generated_at')}",
        f"Target per real group: {gate.get('position_target', 100)}",
        f"Observed real positions: {gate.get('positions_observed_total', 0)}",
        f"Real platform target achieved: {str(bool(gate.get('real_platform_target_achieved'))).lower()}",
        f"Real platform-role target achieved: {str(bool(gate.get('real_platform_role_target_achieved'))).lower()}",
        f"Synthetic platform-role target achieved: {str(bool((gate.get('synthetic') or {}).get('platform_role_target_achieved'))).lower()}",
        f"Ready for full automation: {str(bool(gate.get('ready_for_full_automation'))).lower()}",
        "",
        "## Real Platform Coverage",
        "",
        "| Platform | Observed | Remaining |",
        "| --- | ---: | ---: |",
    ]
    platform_counts = gate.get("real_platform_counts") or {}
    platform_shortfalls = gate.get("real_platform_shortfalls") or {}
    for platform, count in sorted(platform_counts.items()):
        lines.append(f"| {platform} | {count} | {platform_shortfalls.get(platform, 0)} |")

    lines.extend(["", "## Real Platform Role Coverage", ""])
    lines.extend(["| Platform / role family | Observed | Remaining |", "| --- | ---: | ---: |"])
    role_counts = gate.get("real_platform_role_counts") or {}
    role_shortfalls = gate.get("real_platform_role_shortfalls") or {}
    for key, count in sorted(role_counts.items()):
        lines.append(f"| {key} | {count} | {role_shortfalls.get(key, 0)} |")

    synthetic = gate.get("synthetic") or {}
    lines.extend(
        [
            "",
            "## Synthetic Evidence",
            "",
            f"- runs: {synthetic.get('run_count', 0)}",
            f"- per-platform-role target: {synthetic.get('per_platform_role_target', 0)}",
            f"- platform-role target achieved: {str(synthetic.get('platform_role_target_achieved')).lower()}",
            f"- local synthetic submit allowed: {str(bool(synthetic.get('local_synthetic_submit_allowed'))).lower()}",
            f"- local synthetic submit count: {synthetic.get('actual_submit_count', 0)}",
            f"- eligible synthetic submit count: {synthetic.get('eligible_submit_count', 0)} / {synthetic.get('eligible_submit_target_count', 0)}",
            f"- eligible synthetic submit achieved: {str(bool(synthetic.get('eligible_submit_achieved'))).lower()}",
            f"- expected blocker count: {synthetic.get('expected_blocker_count', 0)}",
            f"- real platform submission: {str(bool(synthetic.get('real_platform_submission'))).lower()}",
            f"- selector miss count: {synthetic.get('selector_miss_count', 0)}",
        ]
    )

    questions = gate.get("questions") or {}
    lines.extend(["", "## Question Blockers", ""])
    lines.append(f"- blocking prompts: {questions.get('blocking_prompt_count', 0)}")
    coverage_counts = questions.get("coverage_counts") or {}
    for status, count in sorted(coverage_counts.items()):
        lines.append(f"- {status}: {count}")

    lines.extend(["", "## Next Collection Targets", ""])
    targets = gate.get("next_collection_targets") or []
    if targets:
        for target in targets[:40]:
            lines.append(
                "- {platform} / {role}: collect {remaining} more (observed {observed})".format(
                    platform=target.get("platform"),
                    role=target.get("role_family"),
                    remaining=target.get("positions_remaining", 0),
                    observed=target.get("positions_observed", 0),
                )
            )
    else:
        lines.append("- None")

    extras = gate.get("observed_extra_platforms") or []
    if extras:
        lines.extend(["", "## Observed Non-Target Platforms", ""])
        for platform in extras:
            lines.append(f"- {platform}")
    return "\n".join(lines) + "\n"


def build_collection_plan_from_coverage_gate(
    gate: dict[str, Any],
    max_targets: int = 20,
    batch_size: int = 25,
) -> dict[str, Any]:
    targets = [
        target
        for target in gate.get("next_collection_targets", [])
        if isinstance(target, dict) and int(target.get("positions_remaining") or 0) > 0
    ][: max(max_targets, 0)]
    tasks: list[dict[str, Any]] = []
    for target in targets:
        platform = str(target.get("platform") or "Unknown")
        role_family = str(target.get("role_family") or "Other")
        query = _collection_query_for_role(role_family)
        query_variants = _collection_query_variants_for_role(role_family)
        search_urls: list[str] = []
        for variant in query_variants:
            for url in _collection_search_urls(platform, variant):
                if url not in search_urls:
                    search_urls.append(url)
        tasks.append(
            {
                "platform": platform,
                "role_family": role_family,
                "positions_observed": int(target.get("positions_observed") or 0),
                "positions_remaining": int(target.get("positions_remaining") or 0),
                "suggested_batch_size": min(batch_size, int(target.get("positions_remaining") or 0)),
                "query": query,
                "query_variants": query_variants,
                "search_urls": search_urls,
                "output_expectation": {
                    "format": "jsonl",
                    "required_fields": ["platform", "company", "title", "apply_url"],
                    "optional_fields": ["job_id", "location", "description", "questions", "page_excerpt"],
                },
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "research_coverage_gate",
        "position_target": gate.get("position_target", 100),
        "ready_for_full_automation": bool(gate.get("ready_for_full_automation")),
        "real_platform_role_target_achieved": bool(
            gate.get("real_platform_role_target_achieved")
        ),
        "synthetic_platform_role_target_achieved": bool(
            (gate.get("synthetic") or {}).get("platform_role_target_achieved")
        ),
        "task_count": len(tasks),
        "tasks": tasks,
        "import_command": (
            "python3 -m job_apply_agent import-candidates --input <candidates.jsonl> "
            "--output job_apply_agent/outbox/observed_candidates.jsonl"
        ),
    }


def write_collection_plan(
    gate: dict[str, Any],
    json_output: str | Path,
    markdown_output: str | Path,
    max_targets: int = 20,
    batch_size: int = 25,
) -> dict[str, Any]:
    plan = build_collection_plan_from_coverage_gate(
        gate,
        max_targets=max_targets,
        batch_size=batch_size,
    )
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(plan, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(render_collection_plan_markdown(plan), encoding="utf-8")
    return plan


def render_collection_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Collection Plan",
        "",
        f"Generated: {plan.get('generated_at')}",
        f"Tasks: {plan.get('task_count', 0)}",
        f"Ready for full automation: {str(bool(plan.get('ready_for_full_automation'))).lower()}",
        f"Real platform-role target achieved: {str(bool(plan.get('real_platform_role_target_achieved'))).lower()}",
        f"Synthetic platform-role target achieved: {str(bool(plan.get('synthetic_platform_role_target_achieved'))).lower()}",
        "",
        "## Tasks",
        "",
    ]
    tasks = plan.get("tasks") or []
    if tasks:
        for index, task in enumerate(tasks, start=1):
            lines.append(
                "{index}. {platform} / {role}: collect {batch} now, {remaining} remaining".format(
                    index=index,
                    platform=task.get("platform"),
                    role=task.get("role_family"),
                    batch=task.get("suggested_batch_size", 0),
                    remaining=task.get("positions_remaining", 0),
                )
            )
            lines.append(f"   query: {task.get('query')}")
            variants = [
                variant
                for variant in _string_list(task.get("query_variants"))
                if variant != task.get("query")
            ]
            if variants:
                lines.append(f"   variants: {', '.join(variants[:5])}")
            for url in task.get("search_urls", [])[:4]:
                lines.append(f"   search: {url}")
    else:
        lines.append("- None")
    lines.extend(["", "## Import", "", f"`{plan.get('import_command')}`"])
    return "\n".join(lines) + "\n"


def import_candidate_observations(
    input_path: str | Path,
    output_path: str | Path,
    source: str = "manual_collection",
) -> dict[str, Any]:
    candidates = load_candidate_rows(input_path)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    existing_keys: set[str] = set()
    if output.exists():
        for row in load_submissions_jsonl(output, limit=None):
            existing_keys.add(job_registry_key(row))
    imported: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for candidate in candidates:
        normalized = _normalize_candidate_observation(candidate, source=source)
        key = normalized["registry_key"]
        if not normalized.get("apply_url"):
            skipped.append({"reason": "missing_apply_url", "candidate": candidate})
            continue
        if key in existing_keys:
            skipped.append({"reason": "duplicate", "key": key})
            continue
        imported.append(normalized)
        existing_keys.add(key)
    with output.open("a", encoding="utf-8") as handle:
        for row in imported:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "input": str(input_path),
        "output": str(output_path),
        "candidate_count": len(candidates),
        "imported_count": len(imported),
        "skipped_count": len(skipped),
        "imported": imported,
        "skipped": skipped,
    }


def discover_candidates_from_collection_plan(
    collection_plan: dict[str, Any],
    max_tasks: int = 4,
    per_task_limit: int = 10,
    search_pages_per_task: int = 2,
    timeout: float = 15.0,
    seed_candidates: list[dict[str, Any]] | None = None,
    board_fetch_limit: int = 20,
    max_rate_limit_errors_per_task: int = 2,
    fetcher: Any | None = None,
) -> dict[str, Any]:
    fetch_page = fetcher or fetch_live_page_text
    tasks = [
        task
        for task in collection_plan.get("tasks", [])
        if isinstance(task, dict)
    ][: max(max_tasks, 0)]
    candidates: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    search_page_count = 0
    board_fetch_count = 0
    board_candidate_count = 0
    direct_seed_candidate_count = 0
    rate_limited_task_count = 0

    for task in tasks:
        task_candidates = 0
        task_rate_limit_errors = 0
        search_urls = _candidate_discovery_search_urls(task)[: max(search_pages_per_task, 0)]
        for search_url in search_urls:
            if task_candidates >= max(per_task_limit, 0):
                break
            search_page_count += 1
            try:
                page_html = fetch_page(search_url, timeout)
            except Exception as exc:  # noqa: BLE001 - discovery keeps moving across tasks.
                errors.append(
                    {
                        "platform": task.get("platform"),
                        "role_family": task.get("role_family"),
                        "search_url": search_url,
                        "error": str(exc),
                    }
                )
                if _is_rate_limit_error(exc):
                    task_rate_limit_errors += 1
                    if (
                        max_rate_limit_errors_per_task >= 0
                        and task_rate_limit_errors >= max_rate_limit_errors_per_task
                    ):
                        rate_limited_task_count += 1
                        errors.append(
                            {
                                "platform": task.get("platform"),
                                "role_family": task.get("role_family"),
                                "search_url": search_url,
                                "error": (
                                    "Search rate limit reached; stopped remaining search pages "
                                    "for this task and continued with ATS board expansion"
                                ),
                            }
                        )
                        break
                continue

            for link in _extract_candidate_links_from_search_html(
                page_html,
                platform=str(task.get("platform") or ""),
            ):
                candidate = _candidate_from_discovered_link(link, task, search_url)
                if candidate is None:
                    continue
                key = job_registry_key(candidate)
                if key in seen_keys:
                    continue
                candidates.append(candidate)
                seen_keys.add(key)
                task_candidates += 1
                if task_candidates >= max(per_task_limit, 0):
                    break

    if seed_candidates:
        for seed_candidate in seed_candidates:
            candidate = _candidate_from_seed_candidate(seed_candidate, tasks)
            if candidate is None:
                continue
            key = job_registry_key(candidate)
            if not key or key in seen_keys:
                continue
            candidates.append(candidate)
            seen_keys.add(key)
            direct_seed_candidate_count += 1

        board_report = _discover_candidates_from_seed_boards(
            seed_candidates,
            tasks,
            timeout=timeout,
            fetcher=fetch_page,
            board_fetch_limit=board_fetch_limit,
            per_platform_limit=max(per_task_limit, 0) * max(len(tasks), 1),
        )
        board_fetch_count = int(board_report.get("board_fetch_count") or 0)
        errors.extend(board_report.get("errors") or [])
        for candidate in board_report.get("candidates") or []:
            key = job_registry_key(candidate)
            if not key or key in seen_keys:
                continue
            candidates.append(candidate)
            seen_keys.add(key)
            board_candidate_count += 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "collection_plan_search_discovery",
        "collection_plan_generated_at": collection_plan.get("generated_at"),
        "task_count": len(tasks),
        "search_page_count": search_page_count,
        "rate_limited_task_count": rate_limited_task_count,
        "seed_candidate_count": len(seed_candidates or []),
        "direct_seed_candidate_count": direct_seed_candidate_count,
        "board_fetch_count": board_fetch_count,
        "board_candidate_count": board_candidate_count,
        "candidate_count": len(candidates),
        "error_count": len(errors),
        "per_platform_counts": _count_by(candidates, "platform"),
        "per_platform_role_counts": _platform_role_counts(
            [
                {
                    "platform": candidate.get("platform"),
                    "role_variant": candidate.get("role_family"),
                }
                for candidate in candidates
            ]
        ),
        "candidates": candidates,
        "errors": errors,
        "next_command": (
            "python3 -m job_apply_agent observe-candidates "
            "--input job_apply_agent/outbox/discovered_candidates_latest.json "
            "--live-check-limit 25"
        ),
        "policy": {
            "read_only_discovery": True,
            "requires_live_check_before_import": True,
            "do_not_submit_real_applications": True,
        },
    }


def write_candidate_discovery_report(
    collection_plan: dict[str, Any],
    json_output: str | Path,
    markdown_output: str | Path,
    max_tasks: int = 4,
    per_task_limit: int = 10,
    search_pages_per_task: int = 2,
    timeout: float = 15.0,
    seed_candidates: list[dict[str, Any]] | None = None,
    board_fetch_limit: int = 20,
    max_rate_limit_errors_per_task: int = 2,
    fetcher: Any | None = None,
) -> dict[str, Any]:
    report = discover_candidates_from_collection_plan(
        collection_plan,
        max_tasks=max_tasks,
        per_task_limit=per_task_limit,
        search_pages_per_task=search_pages_per_task,
        timeout=timeout,
        seed_candidates=seed_candidates,
        board_fetch_limit=board_fetch_limit,
        max_rate_limit_errors_per_task=max_rate_limit_errors_per_task,
        fetcher=fetcher,
    )
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(render_candidate_discovery_markdown(report), encoding="utf-8")
    return report


def select_candidate_topup(
    candidates: list[dict[str, Any]],
    coverage_gate: dict[str, Any],
    observed_candidates: list[dict[str, Any]] | None = None,
    closed_jobs: dict[str, Any] | None = None,
    limit: int = 100,
    per_pair_limit: int = 35,
) -> dict[str, Any]:
    shortfalls = {
        str(pair): int(remaining)
        for pair, remaining in (coverage_gate.get("real_platform_role_shortfalls") or {}).items()
        if int(remaining or 0) > 0
    }
    observed_keys = {
        job_registry_key(candidate)
        for candidate in (observed_candidates or [])
        if job_registry_key(candidate)
    }
    indexed_candidates = [
        (index, _candidate_with_role_family(candidate))
        for index, candidate in enumerate(candidates)
        if isinstance(candidate, dict)
    ]
    by_pair: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    skipped: list[dict[str, Any]] = []
    for index, candidate in indexed_candidates:
        key = job_registry_key(candidate)
        pair = _candidate_platform_role_pair(candidate)
        if not key:
            skipped.append({"reason": "missing_key", "index": index})
            continue
        if key in observed_keys:
            skipped.append({"reason": "already_observed", "key": key, "index": index})
            continue
        if is_job_closed(candidate, closed_jobs):
            skipped.append({"reason": "closed_registry", "key": key, "index": index})
            continue
        if not pair or shortfalls.get(pair, 0) <= 0:
            skipped.append({"reason": "no_active_shortfall", "key": key, "pair": pair, "index": index})
            continue
        by_pair.setdefault(pair, []).append((index, candidate))

    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()
    per_pair_counts: dict[str, int] = {}
    pair_order = sorted(shortfalls, key=lambda pair: shortfalls[pair], reverse=True)
    for pair in pair_order:
        pair_budget = min(max(per_pair_limit, 0), shortfalls.get(pair, 0))
        for _index, candidate in by_pair.get(pair, []):
            if len(selected) >= max(limit, 0) or per_pair_counts.get(pair, 0) >= pair_budget:
                break
            key = job_registry_key(candidate)
            if key in selected_keys:
                continue
            selected.append(candidate)
            selected_keys.add(key)
            per_pair_counts[pair] = per_pair_counts.get(pair, 0) + 1
        if len(selected) >= max(limit, 0):
            break

    if len(selected) < max(limit, 0):
        for pair in pair_order:
            for _index, candidate in by_pair.get(pair, []):
                if len(selected) >= max(limit, 0):
                    break
                key = job_registry_key(candidate)
                if key in selected_keys:
                    continue
                selected.append(candidate)
                selected_keys.add(key)
                per_pair_counts[pair] = per_pair_counts.get(pair, 0) + 1
            if len(selected) >= max(limit, 0):
                break

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "coverage_gap_topup_selection",
        "candidate_count": len(candidates),
        "observed_candidate_count": len(observed_candidates or []),
        "active_shortfall_pair_count": len(shortfalls),
        "limit": limit,
        "per_pair_limit": per_pair_limit,
        "selected_count": len(selected),
        "skipped_count": len(skipped),
        "per_pair_counts": dict(sorted(per_pair_counts.items())),
        "remaining_shortfalls": shortfalls,
        "candidates": selected,
        "skipped": skipped[:500],
        "next_command": (
            "python3 -m job_apply_agent observe-candidates "
            "--input job_apply_agent/outbox/topup_candidates_latest.json "
            "--live-check-limit {count}"
        ).format(count=len(selected)),
    }


def write_candidate_topup_selection_report(
    candidates: list[dict[str, Any]],
    coverage_gate: dict[str, Any],
    observed_candidates: list[dict[str, Any]],
    closed_jobs: dict[str, Any] | None,
    json_output: str | Path,
    markdown_output: str | Path,
    limit: int = 100,
    per_pair_limit: int = 35,
) -> dict[str, Any]:
    report = select_candidate_topup(
        candidates,
        coverage_gate,
        observed_candidates=observed_candidates,
        closed_jobs=closed_jobs,
        limit=limit,
        per_pair_limit=per_pair_limit,
    )
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(render_candidate_topup_selection_markdown(report), encoding="utf-8")
    return report


def render_candidate_topup_selection_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Candidate Top-Up Selection",
        "",
        f"Generated: {report.get('generated_at')}",
        f"Candidates considered: {report.get('candidate_count', 0)}",
        f"Observed candidates supplied: {report.get('observed_candidate_count', 0)}",
        f"Selected: {report.get('selected_count', 0)}",
        f"Skipped: {report.get('skipped_count', 0)}",
        "",
        "## Selected By Pair",
        "",
    ]
    counts = report.get("per_pair_counts") or {}
    if counts:
        for pair, count in sorted(counts.items(), key=lambda item: (-int(item[1]), item[0])):
            lines.append(f"- {pair}: {count}")
    else:
        lines.append("- None")
    lines.extend(["", "## Candidates", ""])
    for candidate in (report.get("candidates") or [])[:120]:
        lines.append(
            "- {platform} / {role}: {company} - {title} {url}".format(
                platform=candidate.get("platform") or "Unknown",
                role=candidate.get("role_family") or "Other",
                company=candidate.get("company") or "Unknown company",
                title=candidate.get("title") or "Unknown title",
                url=candidate.get("apply_url") or candidate.get("short_apply_url") or "",
            ).rstrip()
        )
    lines.extend(["", "## Next", "", f"`{report.get('next_command')}`"])
    return "\n".join(lines) + "\n"


def render_candidate_discovery_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Candidate Discovery Report",
        "",
        f"Generated: {report.get('generated_at')}",
        f"Tasks searched: {report.get('task_count', 0)}",
        f"Search pages fetched: {report.get('search_page_count', 0)}",
        f"Rate-limited tasks: {report.get('rate_limited_task_count', 0)}",
        f"Seed candidates: {report.get('seed_candidate_count', 0)}",
        f"Direct seed candidates: {report.get('direct_seed_candidate_count', 0)}",
        f"ATS boards fetched: {report.get('board_fetch_count', 0)}",
        f"Board candidates discovered: {report.get('board_candidate_count', 0)}",
        f"Candidates discovered: {report.get('candidate_count', 0)}",
        f"Errors: {report.get('error_count', 0)}",
        "",
        "## Platform Counts",
        "",
    ]
    counts = report.get("per_platform_counts") or {}
    if counts:
        for platform, count in sorted(counts.items()):
            lines.append(f"- {platform}: {count}")
    else:
        lines.append("- None")

    lines.extend(["", "## Candidates", ""])
    candidates = report.get("candidates") or []
    if candidates:
        lines.extend(["| Platform | Role family | Company | Title | URL |", "| --- | --- | --- | --- | --- |"])
        for candidate in candidates[:80]:
            lines.append(
                "| {platform} | {role} | {company} | {title} | {url} |".format(
                    platform=candidate.get("platform") or "",
                    role=candidate.get("role_family") or "",
                    company=candidate.get("company") or "",
                    title=candidate.get("title") or "",
                    url=candidate.get("apply_url") or "",
                )
            )
        if len(candidates) > 80:
            lines.append(f"\n... {len(candidates) - 80} more in the JSON report.")
    else:
        lines.append("- None")

    errors = report.get("errors") or []
    if errors:
        lines.extend(["", "## Errors", ""])
        for error in errors[:20]:
            lines.append(
                "- {platform} / {role}: {error}".format(
                    platform=error.get("platform"),
                    role=error.get("role_family"),
                    error=error.get("error"),
                )
            )

    lines.extend(["", "## Next", "", f"`{report.get('next_command')}`"])
    return "\n".join(lines) + "\n"


def write_question_export(
    gaps: dict[str, Any],
    readiness: dict[str, Any],
    coverage_gate: dict[str, Any],
    collection_plan: dict[str, Any],
    learning_tasks: dict[str, Any],
    xlsx_output: str | Path,
    html_output: str | Path,
    source_artifacts: list[dict[str, Any]] | None = None,
    synthetic_browser_execution: dict[str, Any] | None = None,
    fake_learning_probe: dict[str, Any] | None = None,
    fake_position_rehearsal: dict[str, Any] | None = None,
    learning_approval_pack: dict[str, Any] | None = None,
    answer_memory: dict[str, Any] | None = None,
    closed_jobs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    export = build_question_export(
        gaps,
        readiness,
        coverage_gate,
        collection_plan,
        learning_tasks,
        source_artifacts=source_artifacts,
        synthetic_browser_execution=synthetic_browser_execution,
        fake_learning_probe=fake_learning_probe,
        fake_position_rehearsal=fake_position_rehearsal,
        learning_approval_pack=learning_approval_pack,
        answer_memory=answer_memory,
        closed_jobs=closed_jobs,
    )
    xlsx_path = Path(xlsx_output)
    html_path = Path(html_output)
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    _write_question_export_xlsx(export, xlsx_path)
    html_path.write_text(render_question_export_html(export), encoding="utf-8")
    export["outputs"] = {"xlsx": str(xlsx_path), "html": str(html_path)}
    return export


def build_question_export(
    gaps: dict[str, Any],
    readiness: dict[str, Any],
    coverage_gate: dict[str, Any],
    collection_plan: dict[str, Any],
    learning_tasks: dict[str, Any],
    source_artifacts: list[dict[str, Any]] | None = None,
    synthetic_browser_execution: dict[str, Any] | None = None,
    fake_learning_probe: dict[str, Any] | None = None,
    fake_position_rehearsal: dict[str, Any] | None = None,
    learning_approval_pack: dict[str, Any] | None = None,
    answer_memory: dict[str, Any] | None = None,
    closed_jobs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    question_rows = [_question_export_row(item) for item in gaps.get("prompt_statuses", [])]
    blocker_rows = [_question_export_row(item) for item in gaps.get("blocking_prompts", [])]
    problem_buckets = _question_problem_bucket_rows(blocker_rows)
    user_questions = [_learning_task_export_row(task) for task in learning_tasks.get("tasks", [])]
    learning_approval_pack = learning_approval_pack or build_learning_approval_pack(
        learning_tasks,
        readiness,
    )
    approval_bucket_rows = _learning_approval_bucket_export_rows(learning_approval_pack)
    approval_task_rows = _learning_approval_task_export_rows(learning_approval_pack)
    approval_manual_gate_rows = _learning_approval_manual_gate_export_rows(learning_approval_pack)
    manual_gates = [_manual_gate_export_row(item) for item in readiness.get("manual_gates", [])]
    positions = [_position_export_row(item) for item in readiness.get("positions", [])]
    source_artifact_rows = _source_artifact_export_rows(source_artifacts or [])
    synthetic_execution_rows = _synthetic_execution_export_rows(
        coverage_gate,
        synthetic_browser_execution,
    )
    synthetic_policy_stop_rows = _mapping_dict_rows(
        (synthetic_browser_execution or {}).get("policy_stop_counts", {}),
        "policy_stop",
        "count",
    )
    synthetic_platform_role_rows = _mapping_dict_rows(
        (synthetic_browser_execution or {}).get("platform_role_counts")
        or ((coverage_gate.get("synthetic") or {}).get("platform_role_counts") or {}),
        "platform_role",
        "count",
    )
    fake_learning_probe_rows = _fake_learning_probe_export_rows(fake_learning_probe)
    fake_position_rehearsal_rows = _fake_position_rehearsal_export_rows(fake_position_rehearsal)
    answer_memory_rows = _answer_memory_export_rows(answer_memory)
    closed_posting_rows = _closed_posting_export_rows(closed_jobs)
    collection_targets = [
        {
            "platform": target.get("platform"),
            "role_family": target.get("role_family"),
            "positions_observed": target.get("positions_observed", 0),
            "positions_remaining": target.get("positions_remaining", 0),
        }
        for target in coverage_gate.get("next_collection_targets", [])
    ]
    collection_tasks = [
        {
            "platform": task.get("platform"),
            "role_family": task.get("role_family"),
            "suggested_batch_size": task.get("suggested_batch_size", 0),
            "positions_remaining": task.get("positions_remaining", 0),
            "query": task.get("query"),
            "search_urls": "\n".join(_string_list(task.get("search_urls"))),
        }
        for task in collection_plan.get("tasks", [])
    ]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_generated_at": gaps.get("research_generated_at"),
        "positions_observed_total": gaps.get("positions_observed_total", 0),
        "unique_prompts_observed": gaps.get("unique_prompts_observed", 0),
        "ready_prompt_count": gaps.get("ready_prompt_count", 0),
        "blocking_prompt_count": gaps.get("blocking_prompt_count", 0),
        "learning_task_count": learning_tasks.get("task_count", len(user_questions)),
        "manual_gate_count": readiness.get("manual_gate_count", 0),
        "approval_pack_task_count": (learning_approval_pack.get("summary") or {}).get("task_count", 0),
        "approval_pack_draft_answer_count": (learning_approval_pack.get("summary") or {}).get(
            "draft_answer_count", 0
        ),
        "approval_pack_missing_user_answer_count": (learning_approval_pack.get("summary") or {}).get(
            "missing_user_answer_count", 0
        ),
        "approval_pack_exact_confirmation_count": (learning_approval_pack.get("summary") or {}).get(
            "exact_user_confirmation_count", 0
        ),
        "ready_for_full_automation": bool(coverage_gate.get("ready_for_full_automation")),
        "real_platform_target_achieved": bool(coverage_gate.get("real_platform_target_achieved")),
        "real_platform_role_target_achieved": bool(
            coverage_gate.get("real_platform_role_target_achieved")
        ),
        "synthetic_platform_role_target_achieved": bool(
            (coverage_gate.get("synthetic") or {}).get("platform_role_target_achieved")
        ),
        "local_synthetic_submit_count": int((coverage_gate.get("synthetic") or {}).get("actual_submit_count") or 0),
        "eligible_synthetic_submit_count": int((coverage_gate.get("synthetic") or {}).get("eligible_submit_count") or 0),
        "eligible_synthetic_submit_target_count": int(
            (coverage_gate.get("synthetic") or {}).get("eligible_submit_target_count") or 0
        ),
        "eligible_synthetic_submit_achieved": bool(
            (coverage_gate.get("synthetic") or {}).get("eligible_submit_achieved")
        ),
        "expected_synthetic_blocker_count": int(
            (coverage_gate.get("synthetic") or {}).get("expected_blocker_count") or 0
        ),
        "fake_learning_remaining_blockers": int(
            (fake_learning_probe or {}).get("remaining_learning_blocker_count") or 0
        ),
        "fake_learning_manual_gates": int(
            (fake_learning_probe or {}).get("remaining_manual_gate_count") or 0
        ),
        "fake_learning_blockers_cleared": bool(
            (fake_learning_probe or {}).get("learning_blockers_cleared")
        ),
        "fake_position_rehearsal_runs": int(
            (fake_position_rehearsal or {}).get("run_count") or 0
        ),
        "fake_position_platform_role_target_achieved": bool(
            (fake_position_rehearsal or {}).get("platform_role_target_achieved")
        ),
        "fake_position_rehearsal_submit_count": int(
            (fake_position_rehearsal or {}).get("actual_submit_count") or 0
        ),
        "fake_position_rehearsal_submit_achieved": bool(
            (fake_position_rehearsal or {}).get("eligible_submit_achieved")
        ),
        "fake_position_rehearsal_missing_inputs": int(
            (fake_position_rehearsal or {}).get("pre_synthetic_missing_input_count") or 0
        ),
        "fake_position_rehearsal_selector_misses": int(
            (fake_position_rehearsal or {}).get("selector_miss_count") or 0
        ),
        "real_submit_count": 0,
        "answer_memory_count": len(answer_memory_rows),
        "closed_posting_count": len(closed_posting_rows),
    }
    return {
        "generated_at": summary["generated_at"],
        "summary": summary,
        "source_artifacts": source_artifact_rows,
        "synthetic_execution": synthetic_execution_rows,
        "synthetic_policy_stops": synthetic_policy_stop_rows,
        "synthetic_platform_roles": synthetic_platform_role_rows,
        "fake_learning_probe": fake_learning_probe_rows,
        "fake_position_rehearsal": fake_position_rehearsal_rows,
        "answer_memory": answer_memory_rows,
        "closed_postings": closed_posting_rows,
        "coverage_counts": gaps.get("coverage_counts", {}),
        "readiness_counts": readiness.get("readiness_counts", {}),
        "real_platform_counts": coverage_gate.get("real_platform_counts", {}),
        "real_platform_shortfalls": coverage_gate.get("real_platform_shortfalls", {}),
        "question_rows": question_rows,
        "blocker_rows": blocker_rows,
        "problem_buckets": problem_buckets,
        "user_questions": user_questions,
        "learning_approval_summary": learning_approval_pack.get("summary", {}),
        "learning_approval_buckets": approval_bucket_rows,
        "learning_approval_tasks": approval_task_rows,
        "learning_approval_manual_gates": approval_manual_gate_rows,
        "manual_gates": manual_gates,
        "positions": positions,
        "collection_targets": collection_targets,
        "collection_tasks": collection_tasks,
        "policy": {
            "closed_postings": "Skip and persist postings when live text says No longer accepting applications.",
            "fake_data": "Use fake candidate data only in local synthetic/sandbox forms, never in real employer submissions.",
            "final_submit": "Final submit remains supervised unless explicitly approved for a real application.",
            "sensitive_answers": "Protected-class answers are not persisted.",
        },
    }


def render_question_export_html(export: dict[str, Any]) -> str:
    summary = export.get("summary") or {}
    parts = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Job Application Question Export</title>",
        "<style>",
        _question_export_css(),
        "</style>",
        "</head>",
        "<body>",
        "<main>",
        "<h1>Job Application Question Export</h1>",
        f"<p class=\"muted\">Generated: {_html_escape(summary.get('generated_at'))}</p>",
        _html_kpis(
            [
                ("Observed positions", summary.get("positions_observed_total", 0)),
                ("Unique prompts", summary.get("unique_prompts_observed", 0)),
                ("Ready prompts", summary.get("ready_prompt_count", 0)),
                ("Blocking prompts", summary.get("blocking_prompt_count", 0)),
                ("Learning tasks", summary.get("learning_task_count", 0)),
                ("Draft answers", summary.get("approval_pack_draft_answer_count", 0)),
                ("Missing answers", summary.get("approval_pack_missing_user_answer_count", 0)),
                ("Manual gates", summary.get("manual_gate_count", 0)),
                ("Closed postings", summary.get("closed_posting_count", 0)),
                ("Stored answers", summary.get("answer_memory_count", 0)),
            ]
        ),
        "<section><h2>Source Artifacts</h2>",
        _html_table(
            ["Name", "Path", "Exists", "Size bytes", "Updated at"],
            [
                [
                    row.get("name"),
                    row.get("path"),
                    _yes_no(row.get("exists")),
                    row.get("size_bytes"),
                    row.get("updated_at"),
                ]
                for row in export.get("source_artifacts", [])
            ],
        ),
        "</section>",
        "<section><h2>Automation Gate</h2>",
        _html_table(
            ["Check", "Status"],
            [
                ["Ready for full automation", _yes_no(summary.get("ready_for_full_automation"))],
                ["Real platform target achieved", _yes_no(summary.get("real_platform_target_achieved"))],
                [
                    "Real platform-role target achieved",
                    _yes_no(summary.get("real_platform_role_target_achieved")),
                ],
                [
                    "Synthetic platform-role target achieved",
                    _yes_no(summary.get("synthetic_platform_role_target_achieved")),
                ],
                ["Fake observed-position rehearsal runs", summary.get("fake_position_rehearsal_runs", 0)],
                [
                    "Fake observed-position submit count",
                    "{count} / {target}".format(
                        count=summary.get("fake_position_rehearsal_submit_count", 0),
                        target=summary.get("fake_position_rehearsal_runs", 0),
                    ),
                ],
                [
                    "Fake observed-position submit achieved",
                    _yes_no(summary.get("fake_position_rehearsal_submit_achieved")),
                ],
                [
                    "Fake observed-position platform-role target achieved",
                    _yes_no(summary.get("fake_position_platform_role_target_achieved")),
                ],
                ["Local synthetic submit count", summary.get("local_synthetic_submit_count", 0)],
                [
                    "Eligible synthetic submit count",
                    "{count} / {target}".format(
                        count=summary.get("eligible_synthetic_submit_count", 0),
                        target=summary.get("eligible_synthetic_submit_target_count", 0),
                    ),
                ],
                ["Eligible synthetic submit achieved", _yes_no(summary.get("eligible_synthetic_submit_achieved"))],
                ["Expected synthetic blocker count", summary.get("expected_synthetic_blocker_count", 0)],
                ["Actual real submit count", summary.get("real_submit_count", 0)],
            ],
        ),
        "</section>",
        "<section><h2>Synthetic Browser Execution</h2>",
        _html_table(
            ["Metric", "Value"],
            [[row.get("metric"), row.get("value")] for row in export.get("synthetic_execution", [])],
        ),
        "</section>",
        "<section><h2>Synthetic Policy Stops</h2>",
        _html_table(
            ["Policy stop", "Count"],
            [[row.get("policy_stop"), row.get("count")] for row in export.get("synthetic_policy_stops", [])],
        ),
        "</section>",
        "<section><h2>Synthetic Platform Role Counts</h2>",
        _html_table(
            ["Platform role", "Count"],
            [[row.get("platform_role"), row.get("count")] for row in export.get("synthetic_platform_roles", [])],
        ),
        "</section>",
        "<section><h2>Fake Learning Probe</h2>",
        _html_table(
            ["Metric", "Value"],
            [[row.get("metric"), row.get("value")] for row in export.get("fake_learning_probe", [])],
        ),
        "</section>",
        "<section><h2>Fake Position Rehearsal</h2>",
        _html_table(
            ["Metric", "Value"],
            [[row.get("metric"), row.get("value")] for row in export.get("fake_position_rehearsal", [])],
        ),
        "</section>",
        "<section><h2>Problem Buckets</h2>",
        _html_table(
            [
                "Coverage status",
                "Category",
                "Unique prompts",
                "Observed",
                "Required",
                "Platforms",
                "Next action",
                "Top labels",
            ],
            [
                [
                    row.get("coverage_status"),
                    row.get("category"),
                    row.get("unique_prompt_count"),
                    row.get("observed_count"),
                    row.get("required_count"),
                    row.get("platforms"),
                    row.get("next_action"),
                    row.get("top_labels"),
                ]
                for row in export.get("problem_buckets", [])
            ],
        ),
        "</section>",
        "<section><h2>Learning Approval Pack</h2>",
        _html_key_value_table(export.get("learning_approval_summary", {})),
        _html_table(
            [
                "Priority",
                "Bucket",
                "Tasks",
                "Draft answers",
                "Missing answers",
                "Observed",
                "Required",
                "Platforms",
                "Recommended action",
            ],
            [
                [
                    row.get("priority"),
                    row.get("title"),
                    row.get("task_count"),
                    row.get("draft_answer_count"),
                    row.get("missing_answer_count"),
                    row.get("observed_count"),
                    row.get("required_count"),
                    row.get("platforms"),
                    row.get("recommended_action"),
                ]
                for row in export.get("learning_approval_buckets", [])
            ],
        ),
        "</section>",
        "<section><h2>Approval Tasks</h2>",
        _html_table(
            [
                "Bucket",
                "Question",
                "Draft answer",
                "Risk",
                "Storage",
                "Scope",
                "Prompts",
                "Platforms",
                "Recommended action",
                "Approval note",
            ],
            [
                [
                    row.get("bucket_title"),
                    row.get("question"),
                    row.get("draft_answer"),
                    row.get("approval_risk"),
                    row.get("recommended_storage"),
                    row.get("answer_scope"),
                    row.get("related_prompt_count"),
                    row.get("platforms"),
                    row.get("recommended_action"),
                    row.get("approval_note"),
                ]
                for row in export.get("learning_approval_tasks", [])
            ],
        ),
        "</section>",
        "<section><h2>Questions For User</h2>",
        _html_table(
            [
                "Storage",
                "Scope",
                "Question",
                "Platforms",
                "Related prompts",
                "Persist allowed",
                "Automation behavior",
                "Suggested answer",
                "Suggestion source",
                "Confidence",
                "Approval risk",
                "Approval note",
                "Answer",
            ],
            [
                [
                    row.get("recommended_storage"),
                    row.get("answer_scope"),
                    row.get("question"),
                    row.get("platforms"),
                    row.get("related_prompt_count"),
                    _yes_no(row.get("persist_allowed")),
                    row.get("automation_behavior"),
                    row.get("suggested_answer"),
                    row.get("suggested_answer_source"),
                    row.get("suggestion_confidence"),
                    row.get("approval_risk"),
                    row.get("approval_note"),
                    row.get("answer"),
                ]
                for row in export.get("user_questions", [])
            ],
        ),
        "</section>",
        "<section><h2>Blocking Prompts</h2>",
        _html_table(
            [
                "Coverage status",
                "Label",
                "Category",
                "Platforms",
                "Observed",
                "Required",
                "Next action",
            ],
            [
                [
                    row.get("coverage_status"),
                    row.get("label"),
                    row.get("category"),
                    row.get("platforms"),
                    row.get("observed_count"),
                    row.get("required_count"),
                    row.get("next_action"),
                ]
                for row in export.get("blocker_rows", [])
            ],
        ),
        "</section>",
        "<section><h2>Coverage Counts</h2>",
        _html_key_value_table(export.get("coverage_counts", {})),
        "</section>",
        "<section><h2>Readiness Counts</h2>",
        _html_key_value_table(export.get("readiness_counts", {})),
        "</section>",
        "<section><h2>Real Platform Counts</h2>",
        _html_key_value_table(export.get("real_platform_counts", {})),
        "</section>",
        "<section><h2>Real Platform Shortfalls</h2>",
        _html_key_value_table(export.get("real_platform_shortfalls", {})),
        "</section>",
        "<section><h2>Collection Targets</h2>",
        _html_table(
            ["Platform", "Role family", "Observed", "Remaining"],
            [
                [
                    row.get("platform"),
                    row.get("role_family"),
                    row.get("positions_observed"),
                    row.get("positions_remaining"),
                ]
                for row in export.get("collection_targets", [])
            ],
        ),
        "</section>",
        "<section><h2>Collection Tasks</h2>",
        _html_table(
            ["Platform", "Role family", "Batch size", "Remaining", "Query", "Search URLs"],
            [
                [
                    row.get("platform"),
                    row.get("role_family"),
                    row.get("suggested_batch_size"),
                    row.get("positions_remaining"),
                    row.get("query"),
                    row.get("search_urls"),
                ]
                for row in export.get("collection_tasks", [])
            ],
        ),
        "</section>",
        "<section><h2>Position Readiness</h2>",
        _html_table(
            [
                "Readiness",
                "Platform",
                "Company",
                "Title",
                "Role family",
                "Apply URL",
                "Prompt count",
                "Required prompts",
                "Covered prompts",
                "Autofill ready",
                "Supervised ready",
                "Unattended ready",
                "Blockers",
                "Manual gates",
                "Closed reason",
            ],
            [
                [
                    row.get("readiness"),
                    row.get("platform"),
                    row.get("company"),
                    row.get("title"),
                    row.get("role_family"),
                    row.get("apply_url"),
                    row.get("prompt_count"),
                    row.get("required_prompt_count"),
                    row.get("covered_prompt_count"),
                    _yes_no(row.get("ready_for_autofill")),
                    _yes_no(row.get("ready_for_supervised_submit")),
                    _yes_no(row.get("ready_for_unattended_submit")),
                    row.get("learning_blockers"),
                    row.get("manual_gates"),
                    row.get("closed_reason"),
                ]
                for row in export.get("positions", [])
            ],
        ),
        "</section>",
        "<section><h2>Manual Gates</h2>",
        _html_table(
            ["Coverage status", "Label", "Category", "Platforms", "Observed", "Required", "Next action"],
            [
                [
                    row.get("coverage_status"),
                    row.get("label"),
                    row.get("category"),
                    row.get("platforms"),
                    row.get("observed_count"),
                    row.get("required_count"),
                    row.get("next_action"),
                ]
                for row in export.get("manual_gates", [])
            ],
        ),
        "</section>",
        "<section><h2>Answer Memory Index</h2>",
        _html_table(
            [
                "Normalized question",
                "Sample question",
                "Source",
                "Approved count",
                "First seen",
                "Last seen",
                "Example job",
                "Answer stored",
            ],
            [
                [
                    row.get("normalized_question"),
                    row.get("sample_question"),
                    row.get("source"),
                    row.get("approved_count"),
                    row.get("first_seen_at"),
                    row.get("last_seen_at"),
                    row.get("example_job"),
                    _yes_no(row.get("answer_stored")),
                ]
                for row in export.get("answer_memory", [])
            ],
        ),
        "</section>",
        "<section><h2>Closed Posting Registry</h2>",
        _html_table(
            [
                "Key",
                "Status",
                "Reason",
                "Source",
                "Platform",
                "Company",
                "Title",
                "URL",
                "Last seen",
                "Seen count",
            ],
            [
                [
                    row.get("key"),
                    row.get("status"),
                    row.get("reason"),
                    row.get("source"),
                    row.get("platform"),
                    row.get("company"),
                    row.get("title"),
                    row.get("short_apply_url"),
                    row.get("last_seen_at"),
                    row.get("seen_count"),
                ]
                for row in export.get("closed_postings", [])
            ],
        ),
        "</section>",
        "<section><h2>All Observed Prompts</h2>",
        _html_table(
            ["Status", "Label", "Category", "Action", "Platforms", "Observed", "Required", "Next action"],
            [
                [
                    row.get("coverage_status"),
                    row.get("label"),
                    row.get("category"),
                    row.get("automation_action"),
                    row.get("platforms"),
                    row.get("observed_count"),
                    row.get("required_count"),
                    row.get("next_action"),
                ]
                for row in export.get("question_rows", [])
            ],
        ),
        "</section>",
        "<section><h2>Policy</h2>",
        _html_key_value_table(export.get("policy", {})),
        "</section>",
        "</main>",
        "</body>",
        "</html>",
    ]
    return "\n".join(parts)


def load_candidate_rows(path: str | Path) -> list[dict[str, Any]]:
    return _load_candidate_rows(Path(path))


def observe_candidate_pages(
    candidates: list[dict[str, Any]],
    observed_output_path: str | Path,
    closed_jobs_path: str | Path,
    max_checks: int | None = DEFAULT_LIVE_CHECK_LIMIT,
    timeout: float = 15.0,
    fetcher: Any | None = None,
    source: str = "live_candidate_observation",
    refresh_existing: bool = False,
) -> dict[str, Any]:
    closed_jobs = load_closed_jobs(closed_jobs_path)
    fetch_page = fetcher or fetch_live_page_text
    output = Path(observed_output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    existing_keys: set[str] = set()
    if output.exists():
        for row in load_submissions_jsonl(output, limit=None):
            existing_keys.add(job_registry_key(row))

    checks: list[dict[str, Any]] = []
    observed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    live_checked_count = 0
    newly_closed_count = 0

    for index, candidate in enumerate(candidates, start=1):
        apply_url = str(
            candidate.get("apply_url")
            or candidate.get("short_apply_url")
            or candidate.get("url")
            or candidate.get("job_url")
            or ""
        ).strip()
        short_url = shorten_apply_url(apply_url, candidate)
        check = {
            "index": index,
            "key": job_registry_key({**candidate, "apply_url": short_url or apply_url}),
            "company": candidate.get("company") or candidate.get("company_name"),
            "title": candidate.get("title") or candidate.get("job_title"),
            "platform": candidate.get("platform") or infer_platform_from_url(short_url),
            "job_id": candidate.get("job_id") or extract_linkedin_job_id(short_url),
            "url": short_url,
            "status": "pending",
            "closed": False,
            "observed": False,
        }

        registry_reason = _closed_registry_reason(candidate, closed_jobs)
        if registry_reason:
            check.update(
                {
                    "status": "closed_registry",
                    "closed": True,
                    "reason": registry_reason.removeprefix("closed:").replace("_", " "),
                }
            )
            checks.append(check)
            continue

        embedded_match = closed_application_match(candidate)
        if embedded_match:
            record_closed_job(
                closed_jobs_path,
                {**candidate, "apply_url": short_url or apply_url},
                reason=embedded_match.phrase,
                source=f"{source}:embedded_text",
            )
            closed_jobs = load_closed_jobs(closed_jobs_path)
            newly_closed_count += 1
            check.update(
                {
                    "status": "closed_embedded_text",
                    "closed": True,
                    "reason": embedded_match.phrase,
                    "closed_phrase": embedded_match.phrase,
                    "closed_source_field": embedded_match.source_field,
                    "closed_snippet": embedded_match.snippet,
                }
            )
            checks.append(check)
            continue

        if not short_url:
            check["status"] = "missing_apply_url"
            checks.append(check)
            continue

        if not should_live_check_url(short_url):
            check["status"] = "not_live_checkable"
            checks.append(check)
            continue

        if max_checks is not None and max_checks >= 0 and live_checked_count >= max_checks:
            check["status"] = "not_checked_limit"
            checks.append(check)
            continue

        live_checked_count += 1
        try:
            page_html = fetch_page(short_url, timeout)
        except Exception as exc:  # noqa: BLE001 - observation reports uncertainty.
            closed_error_phrase = _closed_fetch_error_phrase(exc)
            if closed_error_phrase:
                record_closed_job(
                    closed_jobs_path,
                    {**candidate, "apply_url": short_url},
                    reason=closed_error_phrase,
                    source=f"{source}:fetch_error",
                )
                closed_jobs = load_closed_jobs(closed_jobs_path)
                newly_closed_count += 1
                check.update(
                    {
                        "status": "closed_fetch_error",
                        "closed": True,
                        "reason": closed_error_phrase,
                        "error": str(exc),
                    }
                )
                checks.append(check)
                continue
            check.update({"status": "check_error", "error": str(exc)})
            checks.append(check)
            continue

        page_text = _html_to_text(page_html)
        live_match = closed_application_match({"page_text": page_text})
        if live_match:
            record_closed_job(
                closed_jobs_path,
                {**candidate, "apply_url": short_url},
                reason=live_match.phrase,
                source=f"{source}:live_text",
            )
            closed_jobs = load_closed_jobs(closed_jobs_path)
            newly_closed_count += 1
            check.update(
                {
                    "status": "closed_live_text",
                    "closed": True,
                    "reason": live_match.phrase,
                    "closed_phrase": live_match.phrase,
                    "closed_source_field": live_match.source_field,
                    "closed_snippet": live_match.snippet,
                }
            )
            checks.append(check)
            continue

        platform = candidate.get("platform") or infer_platform_from_url(short_url)
        metadata = extract_live_job_page_metadata(
            page_html,
            include_form_fields=str(platform or "").lower() != "linkedin",
        )
        application_form_url = _application_form_url_from_page_html(
            page_html,
            short_url,
            platform=str(platform or ""),
        )
        if application_form_url and application_form_url != short_url and not metadata.get("questions"):
            try:
                form_page_html = fetch_page(application_form_url, timeout)
            except Exception as exc:  # noqa: BLE001 - keep original posting observation.
                check["application_form_error"] = str(exc)
            else:
                form_page_text = _html_to_text(form_page_html)
                form_live_match = closed_application_match({"page_text": form_page_text})
                if form_live_match:
                    record_closed_job(
                        closed_jobs_path,
                        {**candidate, "apply_url": short_url},
                        reason=form_live_match.phrase,
                        source=f"{source}:form_live_text",
                    )
                    closed_jobs = load_closed_jobs(closed_jobs_path)
                    newly_closed_count += 1
                    check.update(
                        {
                            "status": "closed_form_live_text",
                            "closed": True,
                            "reason": form_live_match.phrase,
                            "closed_phrase": form_live_match.phrase,
                            "closed_source_field": form_live_match.source_field,
                            "closed_snippet": form_live_match.snippet,
                            "application_form_url": application_form_url,
                        }
                    )
                    checks.append(check)
                    continue
                form_metadata = extract_live_job_page_metadata(
                    form_page_html,
                    include_form_fields=True,
                )
                if form_metadata.get("questions"):
                    metadata = {
                        **metadata,
                        "title": metadata.get("title") or form_metadata.get("title"),
                        "company": metadata.get("company") or form_metadata.get("company"),
                        "description": metadata.get("description") or form_metadata.get("description"),
                        "page_excerpt": form_metadata.get("page_excerpt") or metadata.get("page_excerpt"),
                        "questions": form_metadata.get("questions"),
                    }
                    check["application_form_url"] = application_form_url
        questions = _unique_normalized_strings(
            [
                *_string_list(candidate.get("questions")),
                *_string_list(metadata.get("questions")),
            ]
        )
        observation_input = {
            **candidate,
            "apply_url": short_url,
            "platform": platform,
            "company": candidate.get("company") or candidate.get("company_name") or metadata.get("company"),
            "title": candidate.get("title") or candidate.get("job_title") or metadata.get("title"),
            "questions": questions,
            "page_excerpt": candidate.get("page_excerpt") or metadata.get("page_excerpt"),
            "description": candidate.get("description") or metadata.get("description"),
        }
        normalized = _normalize_candidate_observation(observation_input, source=source)
        key = normalized["registry_key"]
        if key in existing_keys and not refresh_existing:
            check.update({"status": "duplicate_observation", "observed": False})
            skipped.append({"reason": "duplicate", "key": key})
            checks.append(check)
            continue
        observed.append(normalized)
        existing_keys.add(key)
        check.update(
            {
                "status": "observed_open",
                "observed": True,
                "question_count": len(_string_list(normalized.get("questions"))),
            }
        )
        checks.append(check)

    with output.open("a", encoding="utf-8") as handle:
        for row in observed:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")

    closed_checks = [check for check in checks if check.get("closed")]
    observed_checks = [check for check in checks if check.get("observed")]
    error_checks = [check for check in checks if check.get("status") == "check_error"]
    uncertain_checks = [
        check
        for check in checks
        if not check.get("closed") and not check.get("observed")
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "candidate_count": len(candidates),
        "checked_count": len(checks),
        "live_checked_count": live_checked_count,
        "observed_count": len(observed_checks),
        "closed_count": len(closed_checks),
        "newly_closed_count": newly_closed_count,
        "uncertain_count": len(uncertain_checks),
        "error_count": len(error_checks),
        "skipped_count": len(skipped),
        "status_counts": _count_by(checks, "status"),
        "observed_output": str(observed_output_path),
        "closed_jobs_path": str(closed_jobs_path),
        "max_checks": max_checks,
        "refresh_existing": refresh_existing,
        "checks": checks,
        "observed": observed,
        "closed_candidates": closed_checks,
        "uncertain_candidates": uncertain_checks,
        "skipped": skipped,
        "policy": {
            "stop_on_closed_posting": True,
            "persist_closed_postings": True,
            "write_only_live_observed_open_positions": True,
            "do_not_submit_real_applications": True,
        },
    }


def write_candidate_observation_report(
    candidates: list[dict[str, Any]],
    observed_output_path: str | Path,
    closed_jobs_path: str | Path,
    json_output: str | Path,
    markdown_output: str | Path,
    max_checks: int | None = DEFAULT_LIVE_CHECK_LIMIT,
    timeout: float = 15.0,
    fetcher: Any | None = None,
    source: str = "live_candidate_observation",
    refresh_existing: bool = False,
) -> dict[str, Any]:
    report = observe_candidate_pages(
        candidates,
        observed_output_path,
        closed_jobs_path,
        max_checks=max_checks,
        timeout=timeout,
        fetcher=fetcher,
        source=source,
        refresh_existing=refresh_existing,
    )
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(render_candidate_observation_markdown(report), encoding="utf-8")
    return report


def extract_live_job_page_metadata(
    page_html: str,
    include_form_fields: bool = True,
) -> dict[str, Any]:
    page_text = _html_to_text(page_html)
    title = _extract_html_title(page_html)
    company = _extract_company_from_html_title(title) or _extract_html_meta(
        page_html,
        ["og:site_name", "twitter:site"],
    )
    if str(company).strip().lower() in {"@linkedin", "linkedin"}:
        company = _extract_company_from_page_text(page_text)
    ashby_questions = _extract_ashby_application_prompts(page_html)
    html_questions = [] if ashby_questions else extract_application_prompts_from_html(
        page_html,
        include_form_fields=include_form_fields,
    )
    questions = _unique_normalized_strings([*html_questions, *ashby_questions])
    return {
        "title": title,
        "company": company,
        "questions": questions,
        "description": _extract_html_meta(page_html, ["description", "og:description"]),
        "page_excerpt": page_text[:1200],
    }


def _application_form_url_from_page_html(
    page_html: str,
    page_url: str,
    platform: str = "",
) -> str:
    platform_text = _normalize(str(platform or infer_platform_from_url(page_url) or ""))
    if platform_text != "lever":
        return ""
    for match in re.finditer(r"(?is)<a\b([^>]*)>(.*?)</a>", str(page_html or "")):
        attrs = _html_attrs(match.group(1))
        href = attrs.get("href")
        if not href:
            continue
        text = _clean_html_text(match.group(2))
        css_class = attrs.get("class", "")
        href_text = urllib.parse.urljoin(str(page_url or ""), html.unescape(href).strip())
        if not href_text:
            continue
        parsed = urllib.parse.urlparse(href_text)
        if "jobs.lever.co" not in parsed.netloc.lower():
            continue
        if parsed.path.rstrip("/").endswith("/apply") and (
            "apply" in _normalize(text) or "postings-btn" in css_class
        ):
            return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))
    parsed = urllib.parse.urlparse(str(page_url or ""))
    if "jobs.lever.co" in parsed.netloc.lower() and not parsed.path.rstrip("/").endswith("/apply"):
        return urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path.rstrip("/") + "/apply", "", "", "")
        )
    return ""


def _extract_company_from_html_title(title: str) -> str:
    value = re.sub(r"\s+", " ", str(title or "")).strip()
    match = re.match(r"(.+?)\s+hiring\s+.+?\s+\|\s+LinkedIn\b", value, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def _extract_company_from_page_text(page_text: str) -> str:
    value = re.sub(r"\s+", " ", str(page_text or "")).strip()
    match = re.search(r"\b([A-Z][A-Za-z0-9&.,' -]{1,80})\s+hiring\s+", value)
    if match:
        return match.group(1).strip()
    return ""


def _extract_ashby_application_prompts(page_html: str) -> list[str]:
    app_data = _parse_ashby_app_data(page_html)
    posting = app_data.get("posting") if isinstance(app_data.get("posting"), dict) else {}
    forms: list[dict[str, Any]] = []
    application_form = posting.get("applicationForm")
    if isinstance(application_form, dict):
        forms.append(application_form)
    for survey_form in posting.get("surveyForms") or []:
        if isinstance(survey_form, dict):
            forms.append(survey_form)

    prompts: list[str] = []
    for form in forms:
        for entry in _ashby_form_field_entries(form):
            prompt = _ashby_form_entry_prompt(entry)
            if not prompt:
                continue
            classification = classify_application_prompt(prompt)
            if _skip_low_signal_prompt(prompt, classification):
                continue
            prompts.append(prompt)
    return _unique_normalized_strings(prompts)


def _ashby_form_field_entries(form: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for key in ["fieldEntries", "entries"]:
        entries.extend(item for item in form.get(key) or [] if isinstance(item, dict))
    for section in form.get("sections") or []:
        if not isinstance(section, dict):
            continue
        entries.extend(item for item in section.get("fieldEntries") or [] if isinstance(item, dict))
        entries.extend(item for item in section.get("fields") or [] if isinstance(item, dict))
    form_definition = form.get("formDefinition") if isinstance(form.get("formDefinition"), dict) else {}
    for section in form_definition.get("sections") or []:
        if not isinstance(section, dict):
            continue
        entries.extend(item for item in section.get("fields") or [] if isinstance(item, dict))
    return entries


def _ashby_form_entry_prompt(entry: dict[str, Any]) -> str:
    field = entry.get("field") if isinstance(entry.get("field"), dict) else {}
    title = _clean_html_text(str(field.get("title") or ""))
    human_path = _clean_html_text(str(field.get("humanReadablePath") or ""))
    description = _clean_html_text(str(entry.get("descriptionHtml") or field.get("descriptionHtml") or ""))
    if not description:
        description = _ashby_rich_text_to_plain(entry.get("description") or field.get("description"))
    if description and "?" in description and not title:
        return description
    return title or human_path or description


def _ashby_rich_text_to_plain(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return _clean_html_text(value)
    if isinstance(value, dict):
        parts: list[str] = []
        text = value.get("text")
        if text:
            parts.append(str(text))
        for item in value.get("content") or []:
            part = _ashby_rich_text_to_plain(item)
            if part:
                parts.append(part)
        return _clean_html_text(" ".join(parts))
    if isinstance(value, list):
        return _clean_html_text(" ".join(_ashby_rich_text_to_plain(item) for item in value))
    return _clean_html_text(str(value))


def _unique_normalized_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = re.sub(r"\s+", " ", str(value or "")).strip(" *:\u00a0")
        key = _normalize(text)
        if not text or not key or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def extract_application_prompts_from_html(
    page_html: str,
    include_form_fields: bool = True,
) -> list[str]:
    prompts: list[str] = []

    def add(value: str, source_kind: str = "text") -> None:
        text = _clean_html_text(value)
        if source_kind == "button" and _normalize(text) not in {
            "submit application",
            "submit",
            "continue",
            "next",
            "save and continue",
        }:
            return
        if not _looks_like_application_prompt(text):
            return
        normalized = _normalize_question(text)
        if len(text) < 2 or not normalized:
            return
        if normalized in {_normalize_question(item) for item in prompts}:
            return
        prompts.append(text)

    if include_form_fields:
        for pattern in [
            r"(?is)<label\b[^>]*>(.*?)</label>",
            r"(?is)<legend\b[^>]*>(.*?)</legend>",
        ]:
            for match in re.finditer(pattern, page_html):
                add(match.group(1))

        for match in re.finditer(r"(?is)<button\b[^>]*>(.*?)</button>", page_html):
            add(match.group(1), source_kind="button")

        for tag_match in re.finditer(
            r"(?is)<(?:input|textarea|select|button)\b([^>]*)>",
            page_html,
        ):
            attrs = _html_attrs(tag_match.group(1))
            for attr in ["aria-label", "placeholder", "name", "id"]:
                value = attrs.get(attr)
                if not value:
                    continue
                if attr in {"name", "id"}:
                    value = _humanize_field_identifier(value)
                add(value, source_kind="field_attr")

    for match in re.finditer(r"(?is)>([^<>]{8,240}\?)<", page_html):
        add(match.group(1), source_kind="question")

    return prompts[:80]


def render_candidate_observation_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Candidate Observation Report",
        "",
        f"Generated: {report.get('generated_at')}",
        f"Candidates: {report.get('candidate_count', 0)}",
        f"Live checked: {report.get('live_checked_count', 0)}",
        f"Observed open: {report.get('observed_count', 0)}",
        f"Closed: {report.get('closed_count', 0)}",
        f"Newly closed: {report.get('newly_closed_count', 0)}",
        f"Uncertain: {report.get('uncertain_count', 0)}",
        f"Errors: {report.get('error_count', 0)}",
        f"Observed output: {report.get('observed_output')}",
        "",
        "## Status Counts",
        "",
    ]
    for status, count in sorted((report.get("status_counts") or {}).items()):
        lines.append(f"- {status}: {count}")

    observed = report.get("observed") or []
    lines.extend(["", "## Observed Open Positions", ""])
    if observed:
        for item in observed[:80]:
            lines.append(
                "- {platform}: {company} - {title} ({questions} question(s))".format(
                    platform=item.get("platform") or "Unknown",
                    company=item.get("company") or "Unknown",
                    title=item.get("title") or "Unknown",
                    questions=len(_string_list(item.get("questions"))),
                )
            )
            if item.get("apply_url"):
                lines.append(f"  url: {item.get('apply_url')}")
    else:
        lines.append("- None")

    closed = report.get("closed_candidates") or []
    lines.extend(["", "## Closed Candidates", ""])
    if closed:
        for item in closed[:80]:
            lines.append(
                "- {status}: {company} - {title} ({reason})".format(
                    status=item.get("status"),
                    company=item.get("company") or "Unknown",
                    title=item.get("title") or "Unknown",
                    reason=item.get("reason") or "closed",
                )
            )
            if item.get("url"):
                lines.append(f"  url: {item.get('url')}")
    else:
        lines.append("- None")

    uncertain = report.get("uncertain_candidates") or []
    lines.extend(["", "## Uncertain Candidates", ""])
    if uncertain:
        for item in uncertain[:80]:
            detail = item.get("error") or item.get("status") or "uncertain"
            lines.append(
                "- {status}: {company} - {title} ({detail})".format(
                    status=item.get("status"),
                    company=item.get("company") or "Unknown",
                    title=item.get("title") or "Unknown",
                    detail=detail,
                )
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Policy", ""])
    for key, value in sorted((report.get("policy") or {}).items()):
        lines.append(f"- {key}: {str(bool(value)).lower()}")
    return "\n".join(lines) + "\n"


def write_application_playbook(
    research: dict[str, Any],
    gaps: dict[str, Any] | None,
    readiness: dict[str, Any] | None,
    synthetic: dict[str, Any] | None,
    json_output: str | Path,
    markdown_output: str | Path,
) -> dict[str, Any]:
    playbook = build_application_playbook(
        research,
        gaps=gaps,
        readiness=readiness,
        synthetic=synthetic,
    )
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(playbook, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(render_application_playbook_markdown(playbook), encoding="utf-8")
    return playbook


def render_application_playbook_markdown(playbook: dict[str, Any]) -> str:
    lines = [
        "# Application Automation Playbook",
        "",
        f"Generated: {playbook.get('generated_at')}",
        f"Observed real/dry-run positions: {playbook.get('positions_observed_total', 0)}",
        f"Synthetic runs: {playbook.get('synthetic_run_count', 0)}",
        f"Platforms: {playbook.get('platform_count', 0)}",
        "",
        "## Global Rules",
        "",
    ]
    for rule in playbook.get("global_rules", []):
        lines.append(f"- {rule}")

    for platform, payload in sorted(playbook.get("platforms", {}).items()):
        lines.extend(["", f"## {platform}", ""])
        lines.append(f"- observed positions: {payload.get('positions_observed', 0)}")
        lines.append(f"- synthetic runs: {payload.get('synthetic_runs', 0)}")
        lines.append(f"- prompt items: {payload.get('prompt_items', 0)}")
        if payload.get("readiness_counts"):
            readiness_text = ", ".join(
                f"{key}={value}" for key, value in payload.get("readiness_counts", {}).items()
            )
            lines.append(f"- readiness: {readiness_text}")
        if payload.get("automation_action_counts"):
            action_text = ", ".join(
                f"{key}={value}"
                for key, value in payload.get("automation_action_counts", {}).items()
            )
            lines.append(f"- actions: {action_text}")
        if payload.get("synthetic_status_counts"):
            synthetic_text = ", ".join(
                f"{key}={value}"
                for key, value in payload.get("synthetic_status_counts", {}).items()
            )
            lines.append(f"- synthetic statuses: {synthetic_text}")

        lines.extend(["", "Common blockers/gates:"])
        blockers = payload.get("blocker_prompts", [])
        if blockers:
            for prompt in blockers[:12]:
                lines.append(
                    "- {status}: {label} ({category}; {handling})".format(
                        status=prompt.get("coverage_status"),
                        label=prompt.get("label"),
                        category=prompt.get("category"),
                        handling=prompt.get("handling"),
                    )
                )
        else:
            lines.append("- None observed")
        synthetic_gates = payload.get("synthetic_gate_labels") or []
        if synthetic_gates:
            lines.append("")
            lines.append("Synthetic gates:")
            for label in synthetic_gates[:12]:
                lines.append(f"- {label}")

        lines.extend(["", "Learning tasks:"])
        tasks = payload.get("learning_tasks", [])
        if tasks:
            for task in tasks[:10]:
                lines.append(
                    "- {storage}: {question}".format(
                        storage=task.get("recommended_storage"),
                        question=task.get("question"),
                    )
                )
        else:
            lines.append("- None")
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


def render_apply_run_audit_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# Apply Run Audit",
        "",
        f"Generated: {audit.get('generated_at')}",
        f"Plan: {audit.get('plan_file', 'unknown')}",
        f"Title: {audit.get('title')}",
        f"URL: {audit.get('url')}",
        f"Platform: {audit.get('platform')}",
        f"Status: {audit.get('status')}",
        f"Autofill allowed: {str(bool(audit.get('autofill_allowed'))).lower()}",
        f"Final submit allowed: {str(bool(audit.get('final_submit_allowed'))).lower()}",
        f"Would submit: {str(bool(audit.get('would_submit'))).lower()}",
        f"Next action: {audit.get('next_action')}",
    ]
    if audit.get("closed_reason"):
        lines.append(f"Closed reason: {audit.get('closed_reason')}")
    lines.extend(
        [
            "",
            "## Counts",
            "",
            f"- total steps: {audit.get('step_count', 0)}",
            f"- automation steps: {audit.get('automation_step_count', 0)}",
            f"- stop steps: {audit.get('stop_step_count', 0)}",
            f"- missing steps: {audit.get('missing_step_count', 0)}",
            f"- manual gates: {audit.get('manual_gate_count', 0)}",
            "",
            "## Automation Steps",
            "",
        ]
    )
    automation_steps = audit.get("automation_steps", [])
    if automation_steps:
        for step in automation_steps[:80]:
            lines.append(
                "- {action}: `{label}` ({source})".format(
                    action=step.get("action"),
                    label=step.get("label"),
                    source=step.get("value_source") or step.get("reason"),
                )
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Stop Steps", ""])
    stop_steps = audit.get("stop_steps", [])
    if stop_steps:
        for step in stop_steps[:80]:
            lines.append(
                "- {status}: `{label}` ({handling})".format(
                    status=step.get("status"),
                    label=step.get("label"),
                    handling=step.get("handling"),
                )
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Policy", ""])
    for key, value in sorted((audit.get("policy") or {}).items()):
        lines.append(f"- {key}: {str(bool(value)).lower()}")
    return "\n".join(lines) + "\n"


def render_browser_action_manifest_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        "# Browser Action Manifest",
        "",
        f"Generated: {manifest.get('generated_at')}",
        f"Plan: {manifest.get('plan_file', 'unknown')}",
        f"Title: {manifest.get('title')}",
        f"URL: {manifest.get('url')}",
        f"Platform: {manifest.get('platform')}",
        f"Status: {manifest.get('status')}",
        f"Autofill allowed: {str(bool(manifest.get('autofill_allowed'))).lower()}",
        f"Final submit allowed: {str(bool(manifest.get('final_submit_allowed'))).lower()}",
        f"Would submit: {str(bool(manifest.get('would_submit'))).lower()}",
        f"Browser actions: {manifest.get('action_count', 0)}",
        f"Stop actions: {manifest.get('stop_action_count', 0)}",
    ]
    if manifest.get("closed_reason"):
        lines.append(f"Closed reason: {manifest.get('closed_reason')}")
    lines.extend(["", "## Browser Actions", ""])
    browser_actions = manifest.get("browser_actions", [])
    if browser_actions:
        for action in browser_actions[:80]:
            selectors = action.get("selector_candidates") or []
            selector = selectors[0].get("selector") if selectors else "no selector"
            lines.append(
                "- {browser_action}: `{label}` via `{selector}` ({source})".format(
                    browser_action=action.get("browser_action"),
                    label=action.get("label"),
                    selector=selector,
                    source=action.get("value_source") or "no value source",
                )
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Stop Actions", ""])
    stop_actions = manifest.get("stop_actions", [])
    if stop_actions:
        for action in stop_actions[:80]:
            lines.append(
                "- {status}: `{label}` ({handling})".format(
                    status=action.get("status"),
                    label=action.get("label"),
                    handling=action.get("handling"),
                )
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Policy", ""])
    for key, value in sorted((manifest.get("policy") or {}).items()):
        lines.append(f"- {key}: {str(bool(value)).lower()}")
    return "\n".join(lines) + "\n"


def render_pre_submit_review_markdown(review: dict[str, Any]) -> str:
    lines = [
        "# Pre-Submit Review",
        "",
        f"Generated: {review.get('generated_at')}",
        f"Manifests: {review.get('manifest_count', 0)}",
        f"Positions: {review.get('position_count', 0)}",
        f"Autofill-ready positions: {review.get('autofill_ready_position_count', 0)}",
        f"Closed positions: {review.get('closed_position_count', 0)}",
        f"Browser actions: {review.get('total_action_count', 0)}",
        f"Stop actions: {review.get('total_stop_action_count', 0)}",
        f"Confirmation items: {review.get('confirmation_item_count', 0)}",
        f"Questions to confirm: {review.get('question_to_confirm_count', 0)}",
        f"Actual submit count: {review.get('actual_submit_count', 0)}",
        f"Would submit: {str(bool(review.get('would_submit'))).lower()}",
        "",
        "## Confirmation Status Counts",
        "",
    ]
    for status, count in sorted((review.get("confirmation_status_counts") or {}).items()):
        lines.append(f"- {status}: {count}")

    lines.extend(["", "## Positions", ""])
    positions = review.get("positions", [])
    if positions:
        for position in positions[:80]:
            lines.append(
                "- {status}: {title} [{platform}; actions={actions}; stops={stops}]".format(
                    status=position.get("status"),
                    title=position.get("title") or "Unknown title",
                    platform=position.get("platform") or "Unknown",
                    actions=position.get("action_count", 0),
                    stops=position.get("stop_action_count", 0),
                )
            )
            items = position.get("confirmation_items") or []
            if items:
                labels = "; ".join(str(item.get("label")) for item in items[:4])
                lines.append(f"  confirm: {labels}")
            if position.get("closed_reason"):
                lines.append(f"  closed: {position.get('closed_reason')}")
    else:
        lines.append("- None")

    lines.extend(["", "## Questions To Confirm", ""])
    questions = review.get("questions_to_confirm", [])
    if questions:
        for question in questions[:120]:
            lines.append(
                "- {status}: {label} [{category}]".format(
                    status=", ".join(question.get("statuses", [])),
                    label=question.get("label") or "Unknown",
                    category=question.get("category") or "uncategorized",
                )
            )
            if question.get("sources"):
                lines.append(f"  sources: {', '.join(question.get('sources', []))}")
            if question.get("next_actions"):
                lines.append(f"  next: {question.get('next_actions')[0]}")
    else:
        lines.append("- None")

    lines.extend(["", "## Items To Confirm", ""])
    confirmation_items = review.get("confirmation_items", [])
    if confirmation_items:
        for item in confirmation_items[:120]:
            lines.append(
                "- {status}: {label} [{source}; {category}]".format(
                    status=item.get("status"),
                    label=item.get("label") or item.get("question") or "Unknown",
                    source=item.get("source"),
                    category=item.get("category") or "uncategorized",
                )
            )
            if item.get("next_action"):
                lines.append(f"  next: {item.get('next_action')}")
    else:
        lines.append("- None")

    synthetic = review.get("synthetic_summary") or {}
    lines.extend(
        [
            "",
            "## Synthetic Evidence",
            "",
            f"- runs: {synthetic.get('run_count', 0)}",
            f"- per-platform target: {synthetic.get('per_platform_target', 0)}",
            f"- platform target achieved: {str(synthetic.get('platform_target_achieved')).lower()}",
            f"- per-platform-role target: {synthetic.get('per_platform_role_target', 0)}",
            f"- platform-role target achieved: {str(synthetic.get('platform_role_target_achieved')).lower()}",
            f"- actual submit count: {synthetic.get('actual_submit_count', 0)}",
        ]
    )
    policy_stops = synthetic.get("policy_stop_counts") or {}
    if policy_stops:
        lines.append("- policy stops: " + ", ".join(f"{key}={value}" for key, value in sorted(policy_stops.items())))

    lines.extend(["", "## Policy", ""])
    for key, value in sorted((review.get("policy") or {}).items()):
        lines.append(f"- {key}: {str(bool(value)).lower()}")
    return "\n".join(lines) + "\n"


def render_browser_dom_execution_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Browser DOM Execution Plan",
        "",
        f"Generated: {plan.get('generated_at')}",
        f"Target URL: {plan.get('target_url')}",
        f"Source URL: {plan.get('source_url')}",
        f"Title: {plan.get('title')}",
        f"Platform: {plan.get('platform')}",
        f"Execution allowed: {str(bool(plan.get('execution_allowed'))).lower()}",
        f"Safety status: {plan.get('safety_status')}",
        f"Browser actions: {plan.get('browser_action_count', 0)}",
        f"Stop actions: {plan.get('stop_action_count', 0)}",
        f"Actual submit count: {plan.get('actual_submit_count', 0)}",
        f"Would submit: {str(bool(plan.get('would_submit'))).lower()}",
        "",
        "## Browser Actions",
        "",
    ]
    actions = plan.get("browser_actions", [])
    if actions:
        for action in actions[:80]:
            lines.append(
                "- {browser_action}: `{label}` ({source})".format(
                    browser_action=action.get("browser_action"),
                    label=action.get("label"),
                    source=action.get("value_source") or "no value source",
                )
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Stop Actions", ""])
    stop_actions = plan.get("stop_actions", [])
    if stop_actions:
        for action in stop_actions[:80]:
            lines.append(
                "- {status}: `{label}` ({handling})".format(
                    status=action.get("status"),
                    label=action.get("label"),
                    handling=action.get("handling"),
                )
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Policy", ""])
    for key, value in sorted((plan.get("policy") or {}).items()):
        lines.append(f"- {key}: {str(bool(value)).lower()}")
    return "\n".join(lines) + "\n"


def render_synthetic_apply_execution_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Synthetic Apply Execution",
        "",
        f"Generated: {report.get('generated_at')}",
        f"Runs: {report.get('run_count', 0)}",
        f"Execution: {report.get('execution')}",
        f"Per-platform target: {report.get('per_platform_target', 0)}",
        f"Platform target achieved: {str(report.get('platform_target_achieved')).lower()}",
        f"Per-platform-role target: {report.get('per_platform_role_target', 0)}",
        f"Platform-role target achieved: {str(report.get('platform_role_target_achieved')).lower()}",
        f"Real platform submission: {str(bool(report.get('real_platform_submission'))).lower()}",
        f"Actual submit count: {report.get('actual_submit_count', 0)}",
        f"Executed steps: {report.get('executed_step_count', 0)}",
        f"Stop steps: {report.get('stop_step_count', 0)}",
        "",
        "## Outcome Counts",
        "",
    ]
    for outcome, count in sorted(report.get("outcome_counts", {}).items()):
        lines.append(f"- {outcome}: {count}")
    lines.extend(["", "## Policy Stop Counts", ""])
    for stop, count in sorted(report.get("policy_stop_counts", {}).items()):
        lines.append(f"- {stop}: {count}")
    lines.extend(["", "## Platform Counts", ""])
    for platform, count in sorted(report.get("platform_counts", {}).items()):
        lines.append(f"- {platform}: {count}")
    lines.extend(["", "## Role Variant Counts", ""])
    for role_variant, count in sorted(report.get("role_variant_counts", {}).items()):
        lines.append(f"- {role_variant}: {count}")
    if report.get("platform_role_counts"):
        lines.extend(["", "## Platform Role Counts", ""])
        for key, count in sorted(report.get("platform_role_counts", {}).items()):
            lines.append(f"- {key}: {count}")
    lines.extend(["", "## First Runs", ""])
    for run in report.get("runs", [])[:20]:
        lines.append(
            "- {outcome}: {company} - {title} [{platform}; executed={executed}; stop={stop}]".format(
                outcome=run.get("outcome"),
                company=run.get("company"),
                title=run.get("job_title") or run.get("title"),
                platform=run.get("platform"),
                executed=run.get("executed_step_count", 0),
                stop=run.get("policy_stop"),
            )
        )
        stop_steps = run.get("stop_steps") or []
        if stop_steps:
            labels = "; ".join(str(step.get("label")) for step in stop_steps[:4])
            lines.append(f"  gates: {labels}")
    return "\n".join(lines) + "\n"


def render_synthetic_browser_action_execution_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Synthetic Browser Action Execution",
        "",
        f"Generated: {report.get('generated_at')}",
        f"Runs: {report.get('run_count', 0)}",
        f"Execution: {report.get('execution')}",
        f"Per-platform target: {report.get('per_platform_target', 0)}",
        f"Platform target achieved: {str(report.get('platform_target_achieved')).lower()}",
        f"Per-platform-role target: {report.get('per_platform_role_target', 0)}",
        f"Platform-role target achieved: {str(report.get('platform_role_target_achieved')).lower()}",
        f"Real platform submission: {str(bool(report.get('real_platform_submission'))).lower()}",
        f"Local synthetic submit allowed: {str(bool(report.get('local_synthetic_submit_allowed'))).lower()}",
        f"Local synthetic submit count: {report.get('actual_submit_count', 0)}",
        f"Eligible synthetic submit count: {report.get('eligible_submit_count', 0)} / {report.get('eligible_submit_target_count', 0)}",
        f"Eligible synthetic submit achieved: {str(bool(report.get('eligible_submit_achieved'))).lower()}",
        f"Expected blocker count: {report.get('expected_blocker_count', 0)}",
        f"Would submit count: {report.get('would_submit_count', 0)}",
        f"Executed browser actions: {report.get('executed_action_count', 0)}",
        f"Synthetic gate answers: {report.get('synthetic_gate_answer_count', 0)}",
        f"Selector misses: {report.get('selector_miss_count', 0)}",
        f"Stop actions: {report.get('stop_action_count', 0)}",
        "",
        "## Outcome Counts",
        "",
    ]
    for outcome, count in sorted(report.get("outcome_counts", {}).items()):
        lines.append(f"- {outcome}: {count}")
    lines.extend(["", "## Policy Stop Counts", ""])
    for stop, count in sorted(report.get("policy_stop_counts", {}).items()):
        lines.append(f"- {stop}: {count}")
    lines.extend(["", "## Platform Counts", ""])
    for platform, count in sorted(report.get("platform_counts", {}).items()):
        lines.append(f"- {platform}: {count}")
    lines.extend(["", "## Role Variant Counts", ""])
    for role_variant, count in sorted(report.get("role_variant_counts", {}).items()):
        lines.append(f"- {role_variant}: {count}")
    if report.get("platform_role_counts"):
        lines.extend(["", "## Platform Role Counts", ""])
        for key, count in sorted(report.get("platform_role_counts", {}).items()):
            lines.append(f"- {key}: {count}")
    lines.extend(["", "## First Runs", ""])
    for run in report.get("runs", [])[:20]:
        lines.append(
            "- {outcome}: {company} - {title} [{platform}; actions={actions}; misses={misses}; stop={stop}]".format(
                outcome=run.get("outcome"),
                company=run.get("company"),
                title=run.get("job_title") or run.get("title"),
                platform=run.get("platform"),
                actions=run.get("executed_action_count", 0),
                misses=run.get("selector_miss_count", 0),
                stop=run.get("policy_stop"),
            )
        )
        misses = run.get("selector_misses") or []
        if misses:
            labels = "; ".join(str(item.get("label")) for item in misses[:4])
            lines.append(f"  selector misses: {labels}")
        stops = run.get("stop_actions") or []
        if stops:
            labels = "; ".join(str(step.get("label")) for step in stops[:4])
            lines.append(f"  gates: {labels}")
    return "\n".join(lines) + "\n"


def render_closed_posting_preflight_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Closed Posting Preflight",
        "",
        f"Generated: {report.get('generated_at')}",
        f"Candidates: {report.get('candidate_count', 0)}",
        f"Live checked: {report.get('live_checked_count', 0)}",
        f"Closed: {report.get('closed_count', 0)}",
        f"Newly closed: {report.get('newly_closed_count', 0)}",
        f"Open eligible: {report.get('open_eligible_count', 0)}",
        f"Uncertain: {report.get('uncertain_count', 0)}",
        f"Errors: {report.get('error_count', 0)}",
        "",
        "## Status Counts",
        "",
    ]
    for status, count in sorted((report.get("status_counts") or {}).items()):
        lines.append(f"- {status}: {count}")

    lines.extend(["", "## Open Eligible", ""])
    open_candidates = report.get("open_candidates") or []
    if open_candidates:
        for item in open_candidates[:50]:
            lines.append(
                "- {company} - {title} [{platform}] {url}".format(
                    company=item.get("company") or "Unknown company",
                    title=item.get("title") or "Unknown title",
                    platform=item.get("platform") or "Unknown",
                    url=item.get("url") or "",
                ).rstrip()
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Closed Or Skipped", ""])
    closed_candidates = report.get("closed_candidates") or []
    if closed_candidates:
        for item in closed_candidates[:80]:
            lines.append(
                "- {status}: {company} - {title} [{platform}] reason={reason}".format(
                    status=item.get("status"),
                    company=item.get("company") or "Unknown company",
                    title=item.get("title") or "Unknown title",
                    platform=item.get("platform") or "Unknown",
                    reason=item.get("reason") or "closed",
                )
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Uncertain", ""])
    uncertain_candidates = report.get("uncertain_candidates") or []
    if uncertain_candidates:
        for item in uncertain_candidates[:80]:
            error = f" error={item.get('error')}" if item.get("error") else ""
            lines.append(
                "- {status}: {company} - {title} [{platform}] {url}{error}".format(
                    status=item.get("status"),
                    company=item.get("company") or "Unknown company",
                    title=item.get("title") or "Unknown title",
                    platform=item.get("platform") or "Unknown",
                    url=item.get("url") or "",
                    error=error,
                ).rstrip()
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Policy", ""])
    for key, value in sorted((report.get("policy") or {}).items()):
        lines.append(f"- {key}: {str(bool(value)).lower()}")
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
            closed_error_phrase = _closed_fetch_error_phrase(exc)
            if closed_error_phrase:
                check["closed"] = True
                check["reason"] = closed_error_phrase
                check["error"] = str(exc)
                record_closed_job(
                    closed_jobs_path,
                    {**submission, "apply_url": url},
                    reason=closed_error_phrase,
                    source=f"{source}:fetch_error",
                )
                closed_jobs = load_closed_jobs(closed_jobs_path)
                checks.append(check)
                continue
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


def build_closed_posting_preflight(
    candidates: list[dict[str, Any]],
    closed_jobs_path: str | Path,
    max_checks: int | None = DEFAULT_LIVE_CHECK_LIMIT,
    timeout: float = 15.0,
    fetcher: Any | None = None,
    source: str = "closed_posting_preflight",
) -> dict[str, Any]:
    closed_jobs = load_closed_jobs(closed_jobs_path)
    fetch_page = fetcher or fetch_live_page_text
    checks: list[dict[str, Any]] = []
    live_checked_count = 0
    newly_closed_count = 0

    for index, candidate in enumerate(candidates, start=1):
        apply_url = str(
            candidate.get("apply_url")
            or candidate.get("short_apply_url")
            or candidate.get("url")
            or ""
        ).strip()
        short_url = shorten_apply_url(apply_url, candidate)
        check = {
            "index": index,
            "key": job_registry_key(candidate),
            "company": candidate.get("company"),
            "title": candidate.get("title"),
            "platform": candidate.get("platform") or infer_platform_from_url(short_url),
            "job_id": candidate.get("job_id") or extract_linkedin_job_id(short_url),
            "url": short_url,
            "status": "pending",
            "closed": False,
            "open_eligible": False,
        }

        registry_reason = _closed_registry_reason(candidate, closed_jobs)
        if registry_reason:
            check.update(
                {
                    "status": "closed_registry",
                    "closed": True,
                    "reason": registry_reason.removeprefix("closed:").replace("_", " "),
                }
            )
            checks.append(check)
            continue

        embedded_match = closed_application_match(candidate)
        if embedded_match:
            check.update(
                {
                    "status": "closed_embedded_text",
                    "closed": True,
                    "reason": embedded_match.phrase,
                    "closed_phrase": embedded_match.phrase,
                    "closed_source_field": embedded_match.source_field,
                    "closed_snippet": embedded_match.snippet,
                }
            )
            record_closed_job(
                closed_jobs_path,
                {**candidate, "apply_url": short_url or apply_url},
                reason=embedded_match.phrase,
                source=f"{source}:embedded_text",
            )
            closed_jobs = load_closed_jobs(closed_jobs_path)
            newly_closed_count += 1
            checks.append(check)
            continue

        if not short_url:
            check["status"] = "missing_apply_url"
            checks.append(check)
            continue

        if not should_live_check_url(short_url):
            check["status"] = "not_live_checkable"
            checks.append(check)
            continue

        if max_checks is not None and max_checks >= 0 and live_checked_count >= max_checks:
            check["status"] = "not_checked_limit"
            checks.append(check)
            continue

        live_checked_count += 1
        try:
            page_text = fetch_page(short_url, timeout)
        except Exception as exc:  # noqa: BLE001 - preflight reports the uncertainty.
            closed_error_phrase = _closed_fetch_error_phrase(exc)
            if closed_error_phrase:
                check.update(
                    {
                        "status": "closed_fetch_error",
                        "closed": True,
                        "reason": closed_error_phrase,
                        "error": str(exc),
                    }
                )
                record_closed_job(
                    closed_jobs_path,
                    {**candidate, "apply_url": short_url},
                    reason=closed_error_phrase,
                    source=f"{source}:fetch_error",
                )
                closed_jobs = load_closed_jobs(closed_jobs_path)
                newly_closed_count += 1
                checks.append(check)
                continue
            check.update({"status": "check_error", "error": str(exc)})
            checks.append(check)
            continue

        live_match = closed_application_match({"page_text": page_text})
        if live_match:
            check.update(
                {
                    "status": "closed_live_text",
                    "closed": True,
                    "reason": live_match.phrase,
                    "closed_phrase": live_match.phrase,
                    "closed_source_field": live_match.source_field,
                    "closed_snippet": live_match.snippet,
                }
            )
            record_closed_job(
                closed_jobs_path,
                {**candidate, "apply_url": short_url},
                reason=live_match.phrase,
                source=f"{source}:live_text",
            )
            closed_jobs = load_closed_jobs(closed_jobs_path)
            newly_closed_count += 1
            checks.append(check)
            continue

        check.update({"status": "open_live_checked", "open_eligible": True})
        checks.append(check)

    closed_checks = [check for check in checks if check.get("closed")]
    open_checks = [check for check in checks if check.get("open_eligible")]
    error_checks = [check for check in checks if check.get("status") == "check_error"]
    uncertain_checks = [
        check
        for check in checks
        if not check.get("closed") and not check.get("open_eligible")
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "candidate_count": len(candidates),
        "checked_count": len(checks),
        "live_checked_count": live_checked_count,
        "closed_count": len(closed_checks),
        "newly_closed_count": newly_closed_count,
        "registry_closed_count": sum(
            1 for check in checks if check.get("status") == "closed_registry"
        ),
        "open_eligible_count": len(open_checks),
        "uncertain_count": len(uncertain_checks),
        "error_count": len(error_checks),
        "status_counts": _count_by(checks, "status"),
        "max_checks": max_checks,
        "checks": checks,
        "closed_candidates": closed_checks,
        "open_candidates": open_checks,
        "uncertain_candidates": uncertain_checks,
        "policy": {
            "stop_on_closed_posting": True,
            "persist_closed_postings": True,
            "open_only_live_verified_candidates": True,
        },
    }


def write_closed_posting_preflight(
    candidates: list[dict[str, Any]],
    closed_jobs_path: str | Path,
    json_output: str | Path,
    markdown_output: str | Path,
    max_checks: int | None = DEFAULT_LIVE_CHECK_LIMIT,
    timeout: float = 15.0,
    fetcher: Any | None = None,
    source: str = "closed_posting_preflight",
) -> dict[str, Any]:
    report = build_closed_posting_preflight(
        candidates,
        closed_jobs_path,
        max_checks=max_checks,
        timeout=timeout,
        fetcher=fetcher,
        source=source,
    )
    json_path = Path(json_output)
    markdown_path = Path(markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    markdown_path.write_text(render_closed_posting_preflight_markdown(report), encoding="utf-8")
    return report


def fetch_live_page_text(url: str, timeout: float = 15.0, max_bytes: int = 128_000_000) -> str:
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
    apply_url = str(
        job.get("apply_url") or job.get("short_apply_url") or job.get("url") or ""
    ).strip()
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
    match = re.search(r"/jobs/view/(?:[^/?#]*-)?(\d+)(?:[/?#]|$)", str(url))
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
        path = "/" + "/".join(part for part in parsed.path.split("/") if part)
        return urllib.parse.urlunparse((parsed.scheme.lower(), host, path, "", "", ""))

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


def _is_closed_jobs_registry_payload(path: Path, payload: dict[str, Any]) -> bool:
    if path.name == "closed_jobs.json":
        return True
    jobs = payload.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        return False
    return all(
        isinstance(job, dict) and str(job.get("status") or "").upper() == "CLOSED"
        for job in jobs
    )


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
        if _skip_low_signal_prompt(question, classification):
            continue
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
                required=_question_list_prompt_required(question, classification),
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
        classification = classify_application_prompt(question)
        if _skip_low_signal_prompt(question, classification):
            continue
        seen.add(normalized)
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
                required=_question_list_prompt_required(question, classification),
            )
        )


def _append_linkedin_standard_prompt_inferences(
    items: list[dict[str, Any]],
    positions: dict[str, dict[str, Any]],
) -> None:
    positions_with_items = {
        str(item.get("position_key") or "")
        for item in items
        if str(item.get("position_key") or "")
    }
    inference_path = Path("linkedin_standard_prompt_inference")
    for position in positions.values():
        position_key = str(position.get("position_key") or "")
        if not position_key or position_key in positions_with_items:
            continue
        if str(position.get("platform") or "") != "LinkedIn":
            continue
        for question in DEFAULT_QUESTIONS:
            classification = classify_application_prompt(question)
            if _skip_low_signal_prompt(question, classification):
                continue
            items.append(
                _research_item(
                    inference_path,
                    "LinkedIn",
                    position.get("company"),
                    position.get("title"),
                    position_key,
                    "inferred_question",
                    question,
                    classification,
                    required=True,
                )
            )


def _question_list_prompt_required(
    label: str,
    classification: ApplicationPromptClassification,
) -> bool:
    text = _normalize(label)
    if any(
        marker in text
        for marker in [
            "optional",
            "if applicable",
            "leave blank if none",
            "if any",
            "if other",
            "if selected other",
            "if you selected other",
            "if yes",
            "if no",
            "feel free",
        ]
    ):
        return False
    if "*" in str(label) or "required" in text:
        return True
    if classification.category in {
        "profile_link",
        "referral_contact",
        "communication_consent",
        "cover_letter",
        "cover_letter_upload",
    }:
        return False
    if classification.category == "profile_identity" and "middle name" in text:
        return False
    if classification.category == "profile_identity" and any(
        term in text for term in ["website", "github", "portfolio", "other url"]
    ):
        return False
    return True


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
    role_family = _research_position_role_family(payload)
    record = positions.setdefault(
        position_key,
        {
            "position_key": position_key,
            "platform": platform or "Unknown",
            "job_id": job_id or None,
            "company": payload.get("company"),
            "title": payload.get("title"),
            "role_family": role_family,
            "apply_url": shorten_apply_url(apply_url, payload) if apply_url else None,
            "source_files": [],
        },
    )
    if record.get("role_family") == "Other" and role_family != "Other":
        record["role_family"] = role_family
    for key in ["company", "title", "apply_url"]:
        if record.get(key):
            continue
        if key == "apply_url":
            record[key] = shorten_apply_url(apply_url, payload) if apply_url else None
        else:
            record[key] = payload.get(key)
    if path.name not in record["source_files"]:
        record["source_files"].append(path.name)
    return record


def _research_position_role_family(payload: dict[str, Any]) -> str:
    role_family = str(payload.get("role_family") or payload.get("role_variant") or "").strip()
    title_evidence = " ".join(
        str(payload.get(key) or "")
        for key in ["title", "title_text", "job_title"]
    )
    title_role_family = _infer_role_family(title_evidence)
    if role_family and role_family != "Other":
        candidate = dict(payload)
        candidate.pop("role_family", None)
        candidate.pop("role_variant", None)
        if _candidate_matches_role_family(candidate, role_family):
            return role_family
        return title_role_family
    evidence = " ".join(
        str(payload.get(key) or "")
        for key in [
            "title",
            "title_text",
            "job_title",
            "description",
            "summary",
            "page_excerpt",
        ]
    )
    if title_role_family != "Other":
        return title_role_family
    return _infer_role_family(evidence)


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
    optional_prompt = int(prompt.get("required_count") or 0) == 0

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
        if category == "skills_experience" and profile:
            resume_fact_answer, missing_facts = answer_question(
                profile,
                {"title": "this role", "company": "the company"},
                label,
            )
            if not missing_facts and not _has_sensitive_or_unclear_question({label: resume_fact_answer}):
                return {
                    "coverage_status": "covered_auto_answer",
                    "coverage_reason": "profile_resume_fact_answer",
                    "answer_source": "profile.resume_facts",
                    "next_action": "autofill from verified resume facts",
                }
        if optional_prompt:
            return {
                "coverage_status": "optional_missing_answer",
                "coverage_reason": "optional_standard_question_without_answer",
                "next_action": "skip optional field unless user provides a value",
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
        if int(prompt.get("required_count") or 0) == 0:
            return {
                "coverage_status": "optional_missing_profile",
                "coverage_reason": profile_status["reason"],
                "next_action": "skip optional field unless user provides a value",
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
        if optional_prompt:
            return {
                "coverage_status": "optional_missing_answer",
                "coverage_reason": "optional_human_review_prompt_without_answer",
                "next_action": "skip optional field unless user provides a value",
            }
        return {
            "coverage_status": "needs_user_confirmation",
            "coverage_reason": "employer_specific_policy_or_unclear_prompt",
            "next_action": "ask user during supervised learning and save only if non-sensitive",
        }

    if optional_prompt:
        return {
            "coverage_status": "optional_missing_answer",
            "coverage_reason": "optional_unclassified_prompt_without_answer",
            "next_action": "skip optional field unless user provides a value",
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
        field_value = _profile_value_for_form_field(category, label, profile)
        if not field_value.get("available"):
            return {
                "covered": False,
                "missing_status": str(field_value.get("missing_status") or "needs_profile_field"),
                "reason": str(field_value.get("reason") or "missing_basic_identity"),
                "next_action": str(field_value.get("next_action") or "add missing profile value"),
            }
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
    if category == "education_date":
        if profile.resume_facts.get("graduation_date"):
            return {"covered": True, "reason": "graduation_date_resume_fact_present", "source": "profile.resume_facts.graduation_date"}
        return {
            "covered": False,
            "missing_status": "needs_resume_facts",
            "reason": "missing_graduation_date",
            "next_action": "add graduation date to profile resume_facts",
        }
    if category == "education_grading":
        if profile.resume_facts.get("gpa") or profile.resume_facts.get("grading_system"):
            return {"covered": True, "reason": "education_grading_fact_present", "source": "profile.resume_facts"}
        return {
            "covered": False,
            "missing_status": "needs_resume_facts",
            "reason": "missing_gpa_or_grading_system",
            "next_action": "add GPA or grading system if you want this autofilled",
        }
    if category == "employment_history":
        if profile.resume_facts.get("current_role"):
            return {"covered": True, "reason": "current_role_resume_fact_present", "source": "profile.resume_facts.current_role"}
        return {
            "covered": False,
            "missing_status": "needs_resume_facts",
            "reason": "missing_current_role_fact",
            "next_action": "add current employer/title facts to profile resume_facts",
        }
    if category == "employment_dates":
        if profile.resume_facts.get("employment_dates") or any(
            profile.resume_facts.get(key)
            for key in [
                "current_role_start_month",
                "current_role_start_year",
                "current_role_end_month",
                "current_role_end_year",
            ]
        ):
            return {"covered": True, "reason": "employment_dates_resume_fact_present", "source": "profile.resume_facts.employment_dates"}
        return {
            "covered": False,
            "missing_status": "needs_resume_facts",
            "reason": "missing_employment_dates",
            "next_action": "add employment date facts from resume before autofill",
        }
    if category == "profile_link":
        link_status = _profile_link_value(label, profile)
        if link_status["available"]:
            return {
                "covered": True,
                "reason": "profile_link_present",
                "source": link_status["source"],
            }
        return {
            "covered": False,
            "missing_status": "needs_profile_field",
            "reason": link_status["reason"],
            "next_action": link_status["next_action"],
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


def _profile_link_value(label: str, profile: CandidateProfile) -> dict[str, Any]:
    text = _normalize(label)
    key_groups: list[tuple[list[str], list[str]]] = [
        (["linkedin"], ["linkedin_profile", "linkedin", "linkedin_url"]),
        (["github"], ["github_profile", "github", "github_url"]),
        (["google scholar", "scholar"], ["google_scholar", "google_scholar_url"]),
        (["x profile", "twitter"], ["x_profile", "twitter_profile", "twitter_url"]),
        (
            ["portfolio", "website", "personal site", "personal blog", "blog", "public writing"],
            ["portfolio", "portfolio_url", "website", "website_url", "personal_site", "blog", "public_writing_url"],
        ),
    ]
    requested_keys: list[str] = []
    for hints, keys in key_groups:
        if any(hint in text for hint in hints):
            requested_keys = keys
            break
    if not requested_keys:
        requested_keys = [
            "linkedin_profile",
            "linkedin",
            "github",
            "portfolio",
            "website",
            "profile_url",
        ]

    for key in requested_keys:
        value = str(profile.question_answers.get(key) or "").strip()
        if value:
            return _source_value(f"profile.question_answers.{key}", value)
    return {
        "available": False,
        "source": f"profile.question_answers.{requested_keys[0]}",
        "reason": "missing_profile_link",
        "next_action": f"add {requested_keys[0]} to the local profile",
    }


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
        "optional_missing_profile": 8,
        "optional_missing_answer": 9,
        "covered_auto_answer": 10,
        "covered_profile": 11,
        "covered_generation": 12,
        "covered_requires_review": 13,
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
        if "middle name" in text:
            return _source_value("profile.question_answers.middle_name", profile.question_answers.get("middle_name", ""))
        if "email" in text:
            return _source_value("profile.email", profile.email)
        if "phone" in text or "mobile" in text or "contact number" in text:
            return _source_value("profile.phone", profile.phone)
        if "zip code" in text or "postal code" in text:
            return _source_value(
                "profile.question_answers.zip_code",
                profile.question_answers.get("zip_code", ""),
                missing_status="needs_profile_field",
                next_action="add ZIP/postal code to profile.question_answers",
            )
        if text == "state" or "state province" in text or "please select your state" in text:
            return _source_value("profile.location.state", _state_from_location(profile.location))
        if text == "city" or "city" in text:
            return _source_value("profile.location.city", _city_from_location(profile.location))
        if (
            text == "country"
            or "country" in text
            or "located in the united states" in text
            or "based in the united states" in text
            or "based in the us" in text
        ):
            return _source_value("profile.location.country", _country_from_location(profile.location))
        if any(term in text for term in ["location", "address", "currently based", "currently located", "currently reside"]):
            return _source_value("profile.location", profile.location)
        return _source_value("profile.name", profile.name)
    if category == "education":
        return _source_value("profile.resume_facts.education", profile.resume_facts.get("education", ""))
    if category == "education_date":
        return _source_value(
            "profile.resume_facts.graduation_date",
            profile.resume_facts.get("graduation_date", ""),
            missing_status="needs_resume_facts",
            next_action="add graduation date to profile resume_facts",
        )
    if category == "education_grading":
        value = profile.resume_facts.get("gpa") or profile.resume_facts.get("grading_system", "")
        return _source_value(
            "profile.resume_facts.education_grading",
            value,
            missing_status="needs_resume_facts",
            next_action="add GPA or grading system if you want this autofilled",
        )
    if category == "employment_history":
        return _source_value(
            "profile.resume_facts.current_role",
            profile.resume_facts.get("current_role", ""),
        )
    if category == "employment_dates":
        value = _employment_date_value(label, profile)
        return _source_value(
            value.get("source", "profile.resume_facts.employment_dates"),
            value.get("value", ""),
            missing_status="needs_resume_facts",
            next_action="add employment date facts from resume before autofill",
        )
    if category == "profile_link":
        return _profile_link_value(label, profile)
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
    classification = classify_application_prompt(label)
    if profile and classification.category in {"skills_experience", "technical_experience"}:
        answer, missing_facts = answer_question(
            profile,
            {"title": "this role", "company": "the company"},
            label,
        )
        if not missing_facts and not _has_sensitive_or_unclear_question({label: answer}):
            return {
                "available": True,
                "source": "profile.resume_facts",
                "value": answer,
                "reason": "profile_resume_fact_answer",
            }
    return {
        "available": False,
        "source": "answer_memory",
        "reason": "missing_approved_answer",
        "next_action": "ask once and save approved answer",
    }


def _source_value(
    source: str,
    value: str,
    missing_status: str = "needs_profile_field",
    next_action: str = "add missing profile value before automation",
) -> dict[str, Any]:
    value = str(value or "").strip()
    return {
        "available": bool(value),
        "source": source,
        "value": value,
        "reason": "source_value_available" if value else "source_value_missing",
        "missing_status": missing_status,
        "next_action": next_action,
    }


def _city_from_location(location: str) -> str:
    parts = [part.strip() for part in str(location or "").split(",") if part.strip()]
    return parts[0] if parts else ""


def _state_from_location(location: str) -> str:
    parts = [part.strip() for part in str(location or "").split(",") if part.strip()]
    if len(parts) >= 2:
        state = parts[1].split()[0].strip()
        return state
    return ""


def _country_from_location(location: str) -> str:
    text = _normalize(location)
    if any(term in text for term in ["wa", "washington", "bellevue", "seattle", "united states", " usa", " us"]):
        return "United States"
    return ""


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
        and int(item.get("required_count") or 0) > 0
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
    label = str(item.get("label") or "")
    normalized_label = str(item.get("normalized_label") or _normalize(label))
    if storage == "local_material" and category in {"resume_upload", "file_upload"}:
        return "local_material:resume_file"
    if storage == "profile" and category == "profile_link":
        return "profile:profile_links"
    if storage == "profile" and category == "profile_identity" and any(
        term in normalized_label for term in ["zip code", "zipcode", "postal code"]
    ):
        return "profile:zip_or_postal_code"
    if storage == "resume_facts" and category == "education_grading":
        return "resume_facts:education_grading"
    if category == "communication_consent":
        return "answer_memory:communication_consent"
    if category == "policy_acknowledgement":
        return "supervised_confirmation:policy_acknowledgement"
    if status == "needs_user_confirmation" and category in {
        "background_or_export_control",
        "citizenship_status",
        "conflict_of_interest",
        "country_work_permit",
        "device_policy",
        "employment_history",
        "government_employment",
        "health_requirement",
        "interview_recording_consent",
        "language_ability",
        "location_constraint",
        "professional_license",
        "schedule_constraint",
        "security_clearance",
    }:
        return f"answer_memory:{category}:default_policy"
    return f"{storage}:{status}:{normalized_label or label}"


def _category_default_policy_from_group_key(group_key: str) -> str:
    match = re.fullmatch(r"answer_memory:([a-z0-9_]+):default_policy", str(group_key or ""))
    if not match:
        return ""
    category = match.group(1)
    return category if category in _CATEGORY_DEFAULT_POLICY_CATEGORIES else ""


def _learning_task_answer_scope(group_key: str, storage: str) -> str:
    if _category_default_policy_from_group_key(group_key):
        return "category_default_policy"
    if storage == "answer_memory":
        return "exact_prompt_labels"
    if storage == "profile":
        return "profile_field"
    if storage == "local_material":
        return "local_file_path"
    if storage == "resume_facts":
        return "resume_fact"
    return "supervised_only"


def _learning_task_automation_behavior(group_key: str, storage: str) -> str:
    if _category_default_policy_from_group_key(group_key):
        return "Prefill future prompts in this category, but keep human review before real submit."
    if storage == "answer_memory":
        return "Autofill matching prompt labels after approval."
    if storage == "profile":
        return "Use as reusable profile data for form fields."
    if storage == "local_material":
        return "Use local file path for upload planning."
    if storage == "resume_facts":
        return "Use as verified resume fact for generated or filled answers."
    return "Do not automate without supervised review."


def _learning_task_answer_suggestion(
    task: dict[str, Any],
    profile: CandidateProfile | None,
    answer_memory: dict[str, Any] | None,
) -> dict[str, Any]:
    storage = str(task.get("recommended_storage") or "")
    group_key = str(task.get("group_key") or "")
    question = str(task.get("question") or "")
    labels = [str(label) for label in _string_list(task.get("labels")) if str(label).strip()]

    base = {
        "suggested_answer": "",
        "suggested_answer_source": "needs_user",
        "suggestion_confidence": "none",
        "approval_risk": "needs_review",
        "approval_required": True,
        "approval_note": "No safe reusable suggestion; user should answer this task.",
    }

    if storage == "profile":
        profile_answer = _suggest_profile_learning_answer(group_key, profile)
        if profile_answer:
            return {
                **base,
                "suggested_answer": profile_answer,
                "suggested_answer_source": "profile",
                "suggestion_confidence": "high",
                "approval_risk": "low",
                "approval_note": "Existing profile value can be reused after review.",
            }
        return {
            **base,
            "approval_note": "Profile field is missing; add the value before approving.",
        }

    if storage == "local_material":
        profile_answer = _suggest_profile_learning_answer(group_key, profile)
        if profile_answer:
            return {
                **base,
                "suggested_answer": profile_answer,
                "suggested_answer_source": "profile.question_answers",
                "suggestion_confidence": "high",
                "approval_risk": "low",
                "approval_note": "Existing local material path can be reused after review.",
            }
        return {
            **base,
            "approval_note": "Local file path is missing; choose the approved resume/material path.",
        }

    if storage == "resume_facts":
        fact_answer = _suggest_resume_fact_learning_answer(group_key, profile)
        if fact_answer:
            return {
                **base,
                "suggested_answer": fact_answer,
                "suggested_answer_source": "profile.resume_facts",
                "suggestion_confidence": "medium",
                "approval_risk": "medium",
                "approval_note": "Resume fact exists, but verify it is appropriate for repeated form answers.",
            }
        return {
            **base,
            "approval_note": "Resume fact is missing or should not be inferred.",
        }

    if storage == "answer_memory":
        category = _category_default_policy_from_group_key(group_key)
        if category:
            category_match = _find_category_default_policy_for_category(answer_memory, category)
            if category_match:
                return {
                    **base,
                    "suggested_answer": category_match.answer,
                    "suggested_answer_source": category_match.source,
                    "suggestion_confidence": (
                        "high" if category_match.confidence >= 0.85 else "medium"
                    ),
                    "approval_risk": "low",
                    "approval_note": "Existing category default policy matches this task.",
                }
            return _category_default_policy_suggestion(category, base, profile)

        for label in [*labels, question]:
            learned = find_learned_answer(answer_memory, label) if answer_memory else None
            if learned:
                return {
                    **base,
                    "suggested_answer": learned.answer,
                    "suggested_answer_source": learned.source,
                    "suggestion_confidence": "high" if learned.confidence >= 0.85 else "medium",
                    "approval_risk": "low",
                    "approval_note": "Existing approved answer memory matches this task.",
                }
            direct = _direct_answer(profile, _normalize(label)) if profile else None
            if direct:
                return {
                    **base,
                    "suggested_answer": direct,
                    "suggested_answer_source": "profile.question_answers",
                    "suggestion_confidence": "medium",
                    "approval_risk": "medium",
                    "approval_note": "Profile preference suggests an answer; verify before approval.",
                }

        resume_suggestion = _resume_based_learning_answer_suggestion(task, profile)
        if resume_suggestion:
            return {**base, **resume_suggestion}
        standard_suggestion = _standard_learning_answer_suggestion(task, profile)
        if standard_suggestion:
            return {**base, **standard_suggestion}

    return base


def _standard_learning_answer_suggestion(
    task: dict[str, Any],
    profile: CandidateProfile | None,
) -> dict[str, Any] | None:
    text = _normalize(" ".join([str(task.get("question") or ""), *_string_list(task.get("labels"))]))
    if not text:
        return None
    if "attended an on campus or virtual event" in text:
        return _suggested_learning_answer(
            "N/A - no specific campus or virtual event attended unless an event is confirmed.",
            "standard_no_event_attendance",
            "No event attendance is stored in the current profile; verify before approving.",
        )
    if "active member or contributor" in text and "communities" in text:
        return _suggested_learning_answer(
            "No confirmed active community membership or contributor status in the current profile.",
            "profile.resume_facts_absence",
            "Negative draft based on missing profile evidence; verify before approving.",
        )
    if any(term in text for term in ["certification", "certifications", "itil", "vibration certification"]):
        return _suggested_learning_answer(
            "No confirmed relevant certification in the current resume facts.",
            "profile.resume_facts_absence",
            "Do not claim certifications unless explicitly confirmed.",
        )
    if any(term in text for term in ["net technology", "net framework", "dotnet"]):
        return _suggested_learning_answer(
            "No confirmed .NET experience in the current resume facts.",
            "profile.resume_facts_absence",
            "Negative draft based on missing resume evidence; verify before approving.",
        )
    if any(term in text for term in ["spi", "i2c", "uart", "usb", "firmware", "multithreaded firmware"]):
        return _suggested_learning_answer(
            "No confirmed low-level hardware protocol or firmware experience in the current resume facts.",
            "profile.resume_facts_absence",
            "Negative draft based on missing resume evidence; verify before approving.",
        )
    if "business or executive stakeholders" in text and "dashboards" in text:
        return _suggested_learning_answer(
            "No confirmed executive-stakeholder dashboard ownership in the current resume facts.",
            "profile.resume_facts_absence",
            "Negative draft based on missing resume evidence; verify before approving.",
        )
    if "content delivery" in text or "waf providers" in text:
        return _suggested_learning_answer(
            "No confirmed CDN/WAF provider ownership in the current resume facts.",
            "profile.resume_facts_absence",
            "Negative draft based on missing resume evidence; verify before approving.",
        )
    if "subdomains are most relevant" in text:
        skills = (profile.resume_facts.get("strongest_skills") if profile else "") or ""
        answer = (
            "Site reliability, cloud infrastructure, Linux operations, API gateway reliability, "
            "automation tooling, data infrastructure, incident response, and observability."
        )
        if skills:
            answer = f"{answer} Current skill evidence: {_clean_sentence(skills)}."
        return _suggested_learning_answer(
            answer,
            "profile.resume_facts",
            "Drafted from resume skill areas; verify the employer's exact option wording.",
        )
    if "infrastructure by examining" in text or "system s perimeter" in text:
        return _suggested_learning_answer(
            (
                "I would review only public, non-invasive signals such as DNS records, TLS/certificate "
                "metadata, public endpoints, headers, and visible cloud/CDN patterns, then describe "
                "reliability and security observations without scanning or making claims beyond public data."
            ),
            "standard_public_infrastructure_review",
            "Methodology draft only; verify employer-specific facts before approving.",
        )
    if "internet entities and protocols" in text or "hostnames" in text or "whois" in text:
        return _suggested_learning_answer(
            (
                "Current resume facts support production infrastructure, TLS/certificate automation, "
                "API gateway operations, Linux reliability work, and incident response; no specific "
                "WHOIS/SAN ownership is confirmed."
            ),
            "profile.resume_facts",
            "Drafted from infrastructure resume facts; verify exact protocol experience before approving.",
        )
    if "security and isolation controls" in text and "ai agents" in text:
        return _suggested_learning_answer(
            (
                "No confirmed production ownership of security/isolation controls for AI agents with "
                "regulated-data access in the current resume facts."
            ),
            "profile.resume_facts_absence",
            "Negative draft based on missing resume evidence; verify before approving.",
        )
    if "thermal management" in text or "power distribution" in text or "structural constraints" in text:
        return _suggested_learning_answer(
            "No confirmed thermal, power-distribution, or structural engineering experience in the current resume facts.",
            "profile.resume_facts_absence",
            "Negative draft based on missing resume evidence; verify before approving.",
        )
    if "actively looking for a job" in text or "just exploring future opportunities" in text:
        start_date = (profile.question_answers.get("start_date") if profile else "") or ""
        answer = "I am actively looking for the right role."
        if start_date:
            answer = f"{answer} {_clean_sentence(start_date)}."
        return _suggested_learning_answer(
            answer,
            "profile.question_answers.start_date",
            "Drafted from current job-search availability; verify before approving.",
        )
    if "when would you like to hear back" in text:
        return _suggested_learning_answer(
            "As soon as convenient for the recruiting team.",
            "standard_recruiter_followup_preference",
            "Low-specificity scheduling preference; verify before approving.",
        )
    if "which environment best matches" in text:
        return _suggested_learning_answer(
            "Production infrastructure and reliability-focused engineering environments.",
            "profile.resume_facts",
            "Drafted from the current SRE/production engineering profile; verify before approving.",
        )
    return None


def _suggested_learning_answer(answer: str, source: str, note: str) -> dict[str, Any]:
    return {
        "suggested_answer": answer,
        "suggested_answer_source": source,
        "suggestion_confidence": "low" if "absence" in source or source.startswith("standard_no") else "medium",
        "approval_risk": "medium",
        "approval_note": note,
    }


def _resume_based_learning_answer_suggestion(
    task: dict[str, Any],
    profile: CandidateProfile | None,
) -> dict[str, Any] | None:
    if not profile:
        return None
    labels = [str(label) for label in _string_list(task.get("labels")) if str(label).strip()]
    prompt_text = " ".join([str(task.get("question") or ""), *labels]).strip()
    normalized = _normalize(prompt_text)
    if not normalized:
        return None
    classification = classify_application_prompt(prompt_text)
    skill_like = classification.category in {
        "domain_experience",
        "skills_experience",
        "technical_experience",
        "experience_years",
    }
    if not skill_like and not _looks_like_resume_skill_learning_prompt(normalized):
        return None

    selected_skills = _resume_skill_selection_answer(profile, normalized)
    if selected_skills:
        return {
            "suggested_answer": selected_skills,
            "suggested_answer_source": "profile.resume_facts_skill_inventory",
            "suggestion_confidence": "medium",
            "approval_risk": "medium",
            "approval_note": (
                "Drafted from current resume facts; verify the employer's exact choices "
                "before approving."
            ),
        }

    strict_missing_subject = _strict_missing_experience_subject(profile, normalized)
    if strict_missing_subject:
        return {
            "suggested_answer": f"No confirmed {strict_missing_subject} in the current resume facts.",
            "suggested_answer_source": "profile.resume_facts_absence",
            "suggestion_confidence": "low",
            "approval_risk": "medium",
            "approval_note": (
                "Strict domain draft based only on missing exact resume evidence; approve only "
                "if it is truthful, or replace with the correct exception."
            ),
        }

    matched_terms = _resume_supported_terms_for_prompt(profile, normalized)
    if matched_terms:
        evidence = _resume_evidence_for_terms(profile, matched_terms)
        if not evidence:
            evidence = profile.resume_facts.get("strongest_skills") or profile.resume_facts.get(
                "professional_summary", ""
            )
        answer = "Yes. Current resume facts support this through: {evidence}.".format(
            evidence=_clean_sentence(evidence)
        )
        return {
            "suggested_answer": answer,
            "suggested_answer_source": "profile.resume_facts",
            "suggestion_confidence": "medium",
            "approval_risk": "medium",
            "approval_note": "Resume-derived draft; verify before approving for real applications.",
        }

    if _looks_like_yes_no_experience_prompt(normalized):
        subject = _experience_subject_summary(normalized)
        return {
            "suggested_answer": f"No confirmed {subject} in the current resume facts.",
            "suggested_answer_source": "profile.resume_facts_absence",
            "suggestion_confidence": "low",
            "approval_risk": "medium",
            "approval_note": (
                "Negative draft based only on missing resume evidence; approve only if it is "
                "truthful, or replace with the correct exception."
            ),
        }
    return None


def _looks_like_resume_skill_learning_prompt(normalized: str) -> bool:
    return any(
        term in normalized
        for term in [
            "experience",
            "on call rotation",
            "on-call rotation",
            "proficiency",
            "familiar",
            "worked with",
            "hands on",
            "hands-on",
            "select the tools",
            "select all that apply",
            "which backend",
            "which frontend",
            "which infrastructure",
            "which cloud technology",
            "monitoring tool",
            "monitoring tool sets",
            "technologies",
        ]
    )


def _looks_like_yes_no_experience_prompt(normalized: str) -> bool:
    return (
        normalized.startswith(("do you ", "have you ", "are you ", "did you "))
        or "do you have" in normalized
        or "have you worked" in normalized
        or "have you used" in normalized
        or "hands on experience" in normalized
        or "hands-on experience" in normalized
    ) and any(term in normalized for term in ["experience", "worked", "used", "familiar", "proficiency"])


def _resume_skill_selection_answer(profile: CandidateProfile, normalized: str) -> str:
    if not any(
        term in normalized
        for term in [
            "select the tools",
            "select all that apply",
            "tools and technologies",
            "which backend",
            "which frontend",
            "which infrastructure",
            "which cloud technology",
            "monitoring tool",
            "monitoring tool sets",
            "technologies are you familiar",
            "tools you are familiar",
        ]
    ):
        return ""
    skill_options = [
        ("Python", ["python"]),
        ("Linux", ["linux"]),
        ("Azure", ["azure"]),
        ("AWS", ["aws"]),
        ("Kubernetes-style orchestration", ["kubernetes", "tupperware"]),
        ("API gateway operations / Apache APISIX", ["api gateway", "apisix"]),
        ("SQL / Hive", ["sql", "hive"]),
        ("Redis", ["redis"]),
        ("MongoDB", ["mongodb"]),
        ("Prometheus / observability", ["prometheus", "observability"]),
        ("Grafana", ["grafana"]),
        ("Automation tooling", ["automation"]),
        ("Incident response / on-call", ["incident", "on call", "on-call"]),
        ("LLM-powered automation", ["llm"]),
    ]
    resume_blob = _resume_fact_blob(profile)
    selected = [
        label
        for label, terms in skill_options
        if any(_normalized_contains_term(resume_blob, term) for term in terms)
    ]
    return ", ".join(selected)


def _resume_supported_terms_for_prompt(profile: CandidateProfile, normalized: str) -> list[str]:
    resume_blob = _resume_fact_blob(profile)
    supported: list[str] = []
    for label, prompt_terms, resume_terms in _resume_skill_term_groups():
        if not any(_normalized_contains_term(normalized, term) for term in prompt_terms):
            continue
        if any(_normalized_contains_term(resume_blob, term) for term in resume_terms):
            supported.append(label)
    return supported


def _strict_missing_experience_subject(profile: CandidateProfile, normalized: str) -> str:
    resume_blob = _resume_fact_blob(profile)
    strict_groups = [
        (
            "FedRAMP or DoD IL5 experience",
            ["fedramp", "dod il5", "il5"],
            ["fedramp", "dod il5", "il5"],
        ),
        ("nation-state adversary experience", ["nation state"], ["nation state"]),
        (
            "fintech or financial companies experience",
            ["fintech", "financial companies", "financial services"],
            ["fintech", "financial companies", "financial services"],
        ),
        (
            "highly regulated industry experience",
            ["highly regulated", "fintech", "healthtech", "government"],
            ["highly regulated", "fintech", "healthtech", "government"],
        ),
        ("proprietary trading experience", ["proprietary trading"], ["proprietary trading"]),
        (
            "telecommunications or wireless industry experience",
            ["telecommunications", "wireless"],
            ["telecommunications", "wireless"],
        ),
        (
            "ad tech or digital media experience",
            ["ad tech", "adtech", "digital media"],
            ["ad tech", "adtech", "digital media"],
        ),
        ("blockchain or crypto experience", ["blockchain", "crypto"], ["blockchain", "crypto", "web3"]),
        (
            "customer-facing technical support experience",
            ["customer facing technical support", "customer-facing technical support"],
            ["customer facing technical support", "customer-facing technical support"],
        ),
        ("Go or C++ experience", ["go or c", "golang", "c++"], ["go", "golang", "c++"]),
        (
            "ClickHouse, OLAP, or DBaaS experience",
            ["clickhouse", "olap", "dbaas"],
            ["clickhouse", "olap", "dbaas"],
        ),
    ]
    for subject, prompt_terms, resume_terms in strict_groups:
        if not any(_normalized_contains_term(normalized, term) for term in prompt_terms):
            continue
        if any(_normalized_contains_term(resume_blob, term) for term in resume_terms):
            return ""
        if subject == "ClickHouse, OLAP, or DBaaS experience" and (
            _normalized_contains_term(normalized, "sql database")
            or _normalized_contains_term(normalized, "another sql")
        ) and _normalized_contains_term(resume_blob, "sql"):
            return ""
        return subject
    return ""


def _resume_skill_term_groups() -> list[tuple[str, list[str], list[str]]]:
    return [
        ("Python", ["python"], ["python"]),
        ("Linux", ["linux", "rocky linux"], ["linux", "rocky linux"]),
        ("Azure", ["azure"], ["azure"]),
        ("AWS", ["aws"], ["aws"]),
        ("Kubernetes-style orchestration", ["kubernetes", "k8s"], ["kubernetes", "tupperware"]),
        ("API gateway operations", ["api gateway", "apisix"], ["api gateway", "apisix"]),
        (
            "SQL/data infrastructure",
            ["sql", "database", "data warehouse", "data infrastructure"],
            ["sql", "hive", "data infrastructure"],
        ),
        ("Redis", ["redis"], ["redis"]),
        ("MongoDB", ["mongodb"], ["mongodb"]),
        (
            "Prometheus/observability",
            ["prometheus", "observability", "alerting"],
            ["prometheus", "observability", "alerts"],
        ),
        (
            "incident response/on-call",
            ["incident", "on call", "on-call", "sre", "reliability"],
            ["incident", "on call", "on-call", "sre", "reliability"],
        ),
        ("automation tooling", ["automation", "tooling"], ["automation", "tooling"]),
        ("ML/LLM operations", ["ml", "llm", "model", "ai"], ["ml", "llm", "regression detection"]),
    ]


def _resume_fact_blob(profile: CandidateProfile) -> str:
    values = [str(value) for value in profile.resume_facts.values() if str(value).strip()]
    return _normalize(" ".join(values))


def _resume_evidence_for_terms(profile: CandidateProfile, terms: list[str]) -> str:
    normalized_terms = [_normalize(term) for term in terms if str(term).strip()]
    snippets: list[str] = []
    for key in [
        "current_role",
        "kubernetes_oncall_experience",
        "cloud_experience",
        "strongest_skills",
        "impact_example",
        "professional_summary",
    ]:
        value = str(profile.resume_facts.get(key) or "").strip()
        if not value:
            continue
        normalized_value = _normalize(value)
        if any(term and _normalized_contains_term(normalized_value, term) for term in normalized_terms):
            snippets.append(_clean_sentence(value))
    if not snippets and profile.resume_facts.get("strongest_skills"):
        snippets.append(_clean_sentence(profile.resume_facts["strongest_skills"]))
    return " ".join(snippets[:2])


def _experience_subject_summary(normalized: str) -> str:
    subject_terms = [
        "fintech",
        "financial companies",
        "clickhouse",
        "olap",
        "dbaas",
        "blockchain",
        "crypto",
        "proprietary trading",
        "telecommunications",
        "wireless",
        "ad tech",
        "digital media",
        "customer facing technical support",
        "go or c",
        "c++",
        "fedramp",
        "dod il5",
    ]
    for term in subject_terms:
        if _normalized_contains_term(normalized, term):
            return f"{term} experience"
    return "experience for this specific prompt"


def _normalized_contains_term(normalized_text: str, term: str) -> bool:
    normalized_term = _normalize(term)
    if not normalized_text or not normalized_term:
        return False
    return re.search(rf"(?:^| ){re.escape(normalized_term)}(?: |$)", normalized_text) is not None


def _suggest_profile_learning_answer(
    group_key: str,
    profile: CandidateProfile | None,
) -> str:
    if not profile:
        return ""
    if group_key == "profile:profile_links":
        return profile.question_answers.get("linkedin_profile", "")
    if group_key == "profile:zip_or_postal_code":
        return profile.question_answers.get("zip_code", "") or profile.question_answers.get("postal_code", "")
    if group_key == "local_material:resume_file":
        for key in ["resume_path", "resume_file", "resume_pdf"]:
            if profile.question_answers.get(key):
                return profile.question_answers[key]
    return ""


def _suggest_resume_fact_learning_answer(
    group_key: str,
    profile: CandidateProfile | None,
) -> str:
    if not profile:
        return ""
    if group_key == "resume_facts:education_grading":
        return profile.resume_facts.get("gpa") or profile.resume_facts.get("grading_system", "")
    return ""


def _category_default_policy_suggestion(
    category: str,
    base: dict[str, Any],
    profile: CandidateProfile | None,
) -> dict[str, Any]:
    suggestions = {
        "employment_history": (
            "No, unless a specific employer, contractor, application, or interview exception has been confirmed.",
            "medium",
            "medium",
            "Use only after confirming prior-employer and prior-application history exceptions.",
        ),
        "conflict_of_interest": (
            "No, unless a specific relationship, referral, non-compete, outside employment, or conflict has been confirmed.",
            "medium",
            "medium",
            "Use only after confirming relationship and conflict exceptions.",
        ),
        "security_clearance": (
            "No active security clearance unless specifically confirmed.",
            "medium",
            "medium",
            "Do not claim a clearance without explicit evidence.",
        ),
        "location_constraint": (
            _location_policy_suggestion(profile),
            "medium",
            "low",
            "Matches current relocation/onsite preference; still review city-specific requirements.",
        ),
        "device_policy": (
            "Yes, if the device or BYOD policy is reasonable and reviewed before submit.",
            "low",
            "medium",
            "Review employer device terms before real submission.",
        ),
        "government_employment": (
            "No current or prior government, military, or UN employment unless specifically confirmed.",
            "medium",
            "medium",
            "Use only after confirming government or military employment history.",
        ),
        "language_ability": (
            "English only unless another language proficiency is explicitly confirmed.",
            "medium",
            "low",
            "English proficiency is present; do not claim other languages without confirmation.",
        ),
        "professional_license": (
            "No professional or medical license unless specifically confirmed.",
            "medium",
            "medium",
            "Do not claim regulated licenses without explicit evidence.",
        ),
        "schedule_constraint": (
            "Available to start in about two months; review fixed schedule, internship schedule, or unusual-hours requirements before submit.",
            "medium",
            "medium",
            "Uses the current start-date preference, but unusual schedules need review.",
        ),
    }
    high_risk_notes = {
        "background_or_export_control": "Legal/background/export-control questions need exact user confirmation; do not infer.",
        "citizenship_status": "Citizenship, U.S.-person, and permanent-resident questions need exact user confirmation; do not infer.",
        "country_work_permit": "Country-specific right-to-work questions need exact user confirmation; do not infer.",
        "health_requirement": "Health or vaccination requirement questions need exact user confirmation; do not infer.",
        "interview_recording_consent": "Interview recording, transcription, and AI notetaker consent should be explicitly approved before reuse.",
    }
    if category in suggestions:
        answer, confidence, risk, note = suggestions[category]
        return {
            **base,
            "suggested_answer": answer,
            "suggested_answer_source": "category_default_policy_template",
            "suggestion_confidence": confidence,
            "approval_risk": risk,
            "approval_note": note,
        }
    if category in high_risk_notes:
        return {
            **base,
            "suggested_answer_source": "requires_exact_user_confirmation",
            "suggestion_confidence": "none",
            "approval_risk": "high",
            "approval_note": high_risk_notes[category],
        }
    return base


def _learning_approval_bucket(task: dict[str, Any]) -> dict[str, Any]:
    storage = str(task.get("recommended_storage") or "")
    scope = str(
        task.get("answer_scope")
        or _learning_task_answer_scope(str(task.get("group_key") or ""), storage)
    )
    source = str(task.get("suggested_answer_source") or "")
    risk = str(task.get("approval_risk") or "")
    suggested = str(task.get("suggested_answer") or task.get("answer") or "").strip()
    if storage == "supervised_confirmation" or scope == "supervised_only":
        return _learning_approval_bucket_definition("supervised_only")
    if source == "requires_exact_user_confirmation" or risk == "high":
        return _learning_approval_bucket_definition("exact_user_confirmation")
    if scope == "category_default_policy":
        return _learning_approval_bucket_definition("default_policy_review")
    if storage in {"profile", "local_material", "resume_facts"}:
        return _learning_approval_bucket_definition("profile_or_resume_fact")
    if suggested:
        return _learning_approval_bucket_definition("approve_existing_suggestion")
    return _learning_approval_bucket_definition("exact_prompt_answer")


def _learning_approval_bucket_definition(bucket: str) -> dict[str, Any]:
    definitions = {
        "default_policy_review": {
            "bucket": "default_policy_review",
            "title": "Review reusable default policies",
            "recommended_action": "Approve or edit the default policy once; it can cover many similar prompts.",
            "rank": 1,
        },
        "approve_existing_suggestion": {
            "bucket": "approve_existing_suggestion",
            "title": "Approve existing suggested answers",
            "recommended_action": "Review the suggested answer and approve it if it is truthful.",
            "rank": 2,
        },
        "profile_or_resume_fact": {
            "bucket": "profile_or_resume_fact",
            "title": "Fill profile or resume facts",
            "recommended_action": "Add the missing stable profile field, material path, or resume fact.",
            "rank": 3,
        },
        "exact_prompt_answer": {
            "bucket": "exact_prompt_answer",
            "title": "Answer exact prompt labels",
            "recommended_action": "Provide the exact answer to reuse for these specific prompts.",
            "rank": 4,
        },
        "exact_user_confirmation": {
            "bucket": "exact_user_confirmation",
            "title": "Confirm high-risk legal or sensitive answers",
            "recommended_action": "Answer explicitly; do not infer or bulk-approve.",
            "rank": 5,
        },
        "supervised_only": {
            "bucket": "supervised_only",
            "title": "Keep supervised only",
            "recommended_action": "Handle in the browser during supervised review; do not store as reusable automation.",
            "rank": 6,
        },
    }
    return definitions.get(bucket, definitions["exact_prompt_answer"])


def _learning_approval_manual_gate_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "coverage_status": item.get("coverage_status"),
        "label": item.get("label"),
        "category": item.get("category"),
        "platforms": _string_list(item.get("platforms")),
        "observed_count": int(item.get("observed_count") or 0),
        "required_count": int(item.get("required_count") or 0),
        "recommended_storage": item.get("recommended_storage"),
        "handling": item.get("next_action"),
    }


def _location_policy_suggestion(profile: CandidateProfile | None) -> str:
    return "Open to remote, hybrid, onsite, travel, and relocation for the right role; review city-specific requirements before submit."


def _minimal_learning_question(item: dict[str, Any]) -> str:
    category = str(item.get("category") or "")
    storage = str(item.get("recommended_storage") or "")
    if storage == "local_material" and category in {"resume_upload", "file_upload"}:
        return "What approved local resume PDF/path should automation upload?"
    if storage == "profile" and category == "profile_link":
        return "What LinkedIn profile URL should automation use?"
    if storage == "profile" and category == "profile_identity":
        label = _normalize(str(item.get("label") or ""))
        if any(term in label for term in ["zip code", "zipcode", "postal code"]):
            return "What ZIP/postal code should automation use for profile and remote-work fields?"
    if storage == "resume_facts" and category == "education_grading":
        return "What GPA, grading system, ACT/SAT score, or 'not applicable' answer should automation use for education grading fields?"
    if category == "communication_consent":
        return "For recruiting updates, should automation answer yes or no to SMS/WhatsApp consent?"
    if category == "policy_acknowledgement":
        return "May automation mark applicant privacy acknowledgement after you review the policy?"
    category_questions = {
        "background_or_export_control": "What default answer and exceptions should automation use for background, export-control, indictment, debarment, substance, firearm, felony, or legal-eligibility questions?",
        "citizenship_status": "What citizenship, U.S. person, permanent-resident, and restricted-country answers should automation use?",
        "conflict_of_interest": "Should automation answer no to employee-relative, referral, outside-employment, non-compete, and conflict-of-interest questions unless an exception is listed?",
        "country_work_permit": "What default answer and country-specific exceptions should automation use for non-U.S. work permit/right-to-work questions?",
        "device_policy": "Should automation accept bring-your-own-device or own-computer requirements?",
        "employment_history": "Should automation answer no to prior-employer, prior-application, contractor, or interview-history questions unless an employer exception is listed?",
        "government_employment": "What default answer should automation use for current or prior government, military, or UN employment questions?",
        "health_requirement": "What answer should automation use for health or vaccination requirement questions?",
        "interview_recording_consent": "Should automation consent to interview recording, transcription, AI notetakers, or interview analysis?",
        "language_ability": "Which non-English languages, if any, should automation claim for spoken and written proficiency?",
        "location_constraint": "What default rule should automation use for onsite, hybrid, travel, timezone, and city/country location constraints?",
        "professional_license": "What professional or medical licenses should automation claim, if any?",
        "schedule_constraint": "What default answer should automation use for fixed schedule, internship schedule, or unusual-hours constraints?",
        "security_clearance": "What security clearance level, eligibility, SCIF availability, and clearance exceptions should automation use?",
    }
    if category in category_questions:
        return category_questions[category]
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


def _build_synthetic_application_snapshot(
    index: int,
    platform: str | None = None,
    role_title: str | None = None,
) -> dict[str, Any]:
    platform = platform or SYNTHETIC_APPLICATION_PLATFORMS[
        (index - 1) % len(SYNTHETIC_APPLICATION_PLATFORMS)
    ]
    title = role_title or SYNTHETIC_APPLICATION_ROLE_TITLES[
        (index - 1) % len(SYNTHETIC_APPLICATION_ROLE_TITLES)
    ]
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
        "role_variant": title,
        "role_family": _infer_role_family(title),
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


def _application_playbook_global_rules(synthetic: dict[str, Any]) -> list[str]:
    rules = [
        "Skip and persist postings when page text says No longer accepting applications.",
        "Use fake candidate data only in local synthetic/sandbox forms, never in real employer submissions.",
        "Autofill profile, resume path, profile links, and approved standard answers from local stores.",
        "Generate role-specific free text from resume facts, then keep it in human review before submit.",
        "Pause for CAPTCHA, bot checks, login blockers, or unclear security prompts.",
        "Do not store protected-class self-identification answers such as gender, veteran status, race, disability, or ethnicity.",
        "Never click final submit without explicit approval for that application.",
    ]
    if synthetic.get("status_counts"):
        counts = ", ".join(
            f"{key}={value}" for key, value in sorted(synthetic.get("status_counts", {}).items())
        )
        rules.append(f"Latest synthetic status counts: {counts}.")
    return rules


def _apply_automation_step(step: dict[str, Any]) -> dict[str, Any]:
    return {
        "field_index": step.get("field_index"),
        "item_type": step.get("item_type"),
        "action": step.get("action"),
        "label": step.get("label"),
        "category": step.get("category"),
        "value_source": step.get("value_source"),
        "reason": step.get("reason"),
    }


def _browser_action_for_step(step: dict[str, Any], include_values: bool = False) -> dict[str, Any]:
    original_action = str(step.get("action") or "fill")
    browser_action = {
        "upload": "upload_file",
        "generate": "fill_generated",
        "answer": "fill",
        "fill": "fill",
    }.get(original_action, "fill")
    action: dict[str, Any] = {
        "field_index": step.get("field_index"),
        "item_type": step.get("item_type"),
        "browser_action": browser_action,
        "plan_action": original_action,
        "label": step.get("label"),
        "category": step.get("category"),
        "required": bool(step.get("required")),
        "selector_candidates": _selector_candidates_for_step(step),
        "value_source": step.get("value_source"),
        "requires_file": original_action == "upload" or str(step.get("type") or "").lower() == "file",
        "safe_to_execute": True,
        "guard": "execute only when the live page is not closed and the selector matches the expected field",
    }
    if include_values and "value" in step:
        action["value"] = step.get("value")
    return action


def _selector_candidates_for_step(step: dict[str, Any]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    tag = _css_tag_name(step.get("tag"))
    step_id = _clean_selector_value(step.get("id"))
    name = _clean_selector_value(step.get("name"))
    field_type = _clean_selector_value(step.get("type"))
    label = _clean_selector_value(step.get("label"))

    if step_id:
        if _is_simple_css_identifier(step_id):
            candidates.append({"strategy": "css", "selector": f"#{step_id}", "confidence": "high"})
        candidates.append(
            {
                "strategy": "css",
                "selector": _css_attribute_selector("id", step_id, tag=tag),
                "confidence": "high",
            }
        )
    if name:
        candidates.append(
            {
                "strategy": "css",
                "selector": _css_attribute_selector("name", name, tag=tag),
                "confidence": "high",
            }
        )
    if field_type:
        candidates.append(
            {
                "strategy": "css",
                "selector": _css_attribute_selector("type", field_type, tag=tag or "input"),
                "confidence": "medium",
            }
        )
    if label:
        candidates.append({"strategy": "label_text", "selector": label, "confidence": "medium"})
    if step.get("field_index") is not None:
        candidates.append(
            {
                "strategy": "field_index",
                "selector": str(step.get("field_index")),
                "confidence": "low",
            }
        )
    return candidates


def _css_attribute_selector(attribute: str, value: str, tag: str = "") -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    prefix = tag if tag else ""
    return f'{prefix}[{attribute}="{escaped}"]'


def _css_tag_name(value: Any) -> str:
    tag = str(value or "").strip().lower()
    return tag if re.fullmatch(r"[a-z][a-z0-9-]*", tag) else ""


def _clean_selector_value(value: Any) -> str:
    return str(value or "").strip()


def _is_simple_css_identifier(value: str) -> bool:
    return bool(re.fullmatch(r"-?[_a-zA-Z][-_a-zA-Z0-9]*", value))


def _resolve_browser_action_target(
    action: dict[str, Any],
    fields: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for candidate in action.get("selector_candidates", []):
        if not isinstance(candidate, dict):
            continue
        matches = [
            field
            for field in fields
            if _field_matches_selector_candidate(field, candidate)
        ]
        matches = _filter_targets_by_item_type(matches, action)
        if len(matches) == 1:
            return {
                **matches[0],
                "_matched_strategy": candidate.get("strategy"),
                "_matched_selector": candidate.get("selector"),
            }
    return None


def _filter_targets_by_item_type(
    targets: list[dict[str, Any]],
    action: dict[str, Any],
) -> list[dict[str, Any]]:
    item_type = str(action.get("item_type") or "")
    if not item_type:
        return targets
    filtered = [
        target
        for target in targets
        if str(target.get("_item_type") or ("button" if str(target.get("tag") or "").upper() == "BUTTON" else "field"))
        == item_type
    ]
    return filtered or targets


def _field_matches_selector_candidate(
    field: dict[str, Any],
    candidate: dict[str, Any],
) -> bool:
    strategy = str(candidate.get("strategy") or "")
    selector = str(candidate.get("selector") or "")
    if strategy == "field_index":
        return str(field.get("i")) == selector
    if strategy == "label_text":
        return _normalize(_field_prompt_label(field)) == _normalize(selector)
    if strategy != "css":
        return False
    if selector.startswith("#"):
        return str(field.get("id") or "").strip() == selector[1:]
    match = re.fullmatch(
        r"(?:(?P<tag>[a-z][a-z0-9-]*)?)\[(?P<attr>[A-Za-z_][A-Za-z0-9_-]*)=\"(?P<value>(?:\\.|[^\"])*)\"\]",
        selector,
    )
    if not match:
        return False
    tag = str(match.group("tag") or "")
    if tag and _css_tag_name(field.get("tag")) != tag:
        return False
    attr = str(match.group("attr"))
    value = match.group("value").replace('\\"', '"').replace("\\\\", "\\")
    return str(field.get(attr) or "").strip() == value


def _render_synthetic_field_html(field: dict[str, Any]) -> str:
    label = _field_prompt_label(field)
    escaped_label = html.escape(label)
    field_index = html.escape(str(field.get("i") or ""))
    tag = str(field.get("tag") or "INPUT").upper()
    field_type = str(field.get("type") or "text").lower()
    element_id = str(field.get("id") or f"field-{field.get('i') or uuid.uuid4().hex}").strip()
    escaped_id = html.escape(element_id, quote=True)
    name = str(field.get("name") or "").strip()
    name_attr = f' name="{html.escape(name, quote=True)}"' if name else ""
    required_attr = " required" if field.get("required") else ""
    data_attrs = (
        f' id="{escaped_id}"'
        f' data-field-index="{field_index}"'
        ' data-item-type="field"'
        f' data-label="{escaped_label}"'
        f' aria-label="{escaped_label}"'
        f"{name_attr}{required_attr}"
    )
    if tag == "TEXTAREA":
        control = f"<textarea{data_attrs}></textarea>"
    elif tag == "SELECT":
        control = (
            f"<select{data_attrs}>"
            '<option value=""></option>'
            '<option value="Yes">Yes</option>'
            '<option value="No">No</option>'
            '<option value="Prefer not to say">Prefer not to say</option>'
            "</select>"
        )
    else:
        input_type = html.escape(field_type or "text", quote=True)
        control = f'<input type="{input_type}"{data_attrs}>'
    return f'<label for="{escaped_id}">{escaped_label}</label>\n{control}'


def _confirmation_item_from_stop_action(
    stop: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    status = str(stop.get("status") or "unknown")
    return {
        "source": "browser_manifest",
        "status": status,
        "label": stop.get("label"),
        "category": stop.get("category"),
        "platform": manifest.get("platform"),
        "title": manifest.get("title"),
        "url": manifest.get("url"),
        "required": bool(stop.get("required")),
        "next_action": stop.get("handling") or stop.get("next_action"),
        "persist_allowed": status not in {"sensitive_not_stored", "manual_security_step", "final_submit_confirmation"},
    }


def _confirmation_item_from_gap(prompt: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "answer_gap",
        "status": prompt.get("coverage_status"),
        "label": prompt.get("label"),
        "category": prompt.get("category"),
        "platforms": prompt.get("platforms", []),
        "required_count": prompt.get("required_count", 0),
        "observed_count": prompt.get("observed_count", 0),
        "next_action": prompt.get("next_action"),
        "persist_allowed": prompt.get("coverage_status") != "sensitive_not_stored",
    }


def _confirmation_item_from_learning_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "learning_task",
        "status": "needs_user_confirmation",
        "label": task.get("question"),
        "category": task.get("recommended_storage"),
        "platforms": task.get("platforms", []),
        "labels": task.get("labels", []),
        "next_action": "approve and fill answer in learning task template",
        "persist_allowed": bool(task.get("persist_allowed", True)),
    }


def _append_unique_confirmation_item(
    items: list[dict[str, Any]],
    item: dict[str, Any],
) -> None:
    key = (
        str(item.get("source") or ""),
        str(item.get("status") or ""),
        _normalize(str(item.get("label") or "")),
        str(item.get("platform") or ",".join(item.get("platforms", [])) or ""),
    )
    for existing in items:
        existing_key = (
            str(existing.get("source") or ""),
            str(existing.get("status") or ""),
            _normalize(str(existing.get("label") or "")),
            str(existing.get("platform") or ",".join(existing.get("platforms", [])) or ""),
        )
        if existing_key == key:
            return
    items.append(item)


def _question_checklist_from_confirmation_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    question_statuses = {
        "needs_answer_memory",
        "needs_human_review",
        "needs_user_confirmation",
        "sensitive_not_stored",
    }
    by_label: dict[str, dict[str, Any]] = {}
    for item in items:
        status = str(item.get("status") or "")
        if status not in question_statuses:
            continue
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        key = _normalize(label)
        row = by_label.setdefault(
            key,
            {
                "label": label,
                "category": item.get("category"),
                "statuses": [],
                "sources": [],
                "platforms": [],
                "next_actions": [],
                "persist_allowed": True,
            },
        )
        _append_unique_scalar(row["statuses"], status)
        _append_unique_scalar(row["sources"], str(item.get("source") or "unknown"))
        for platform in _string_list(item.get("platforms")):
            _append_unique_scalar(row["platforms"], platform)
        if item.get("platform"):
            _append_unique_scalar(row["platforms"], str(item.get("platform")))
        if item.get("next_action"):
            _append_unique_scalar(row["next_actions"], str(item.get("next_action")))
        if item.get("persist_allowed") is False:
            row["persist_allowed"] = False
    rows = list(by_label.values())
    rows.sort(
        key=lambda row: (
            min(_answer_status_sort_rank(status) for status in row.get("statuses", []) or ["unknown"]),
            str(row.get("label") or ""),
        )
    )
    return rows


def _append_unique_scalar(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _apply_stop_step(step: dict[str, Any]) -> dict[str, Any]:
    status = str(step.get("status") or "unknown")
    return {
        "field_index": step.get("field_index"),
        "item_type": step.get("item_type"),
        "tag": step.get("tag"),
        "type": step.get("type"),
        "name": step.get("name"),
        "id": step.get("id"),
        "action": step.get("action"),
        "label": step.get("label"),
        "category": step.get("category"),
        "required": bool(step.get("required")),
        "status": status,
        "reason": step.get("reason"),
        "next_action": step.get("next_action"),
        "handling": _apply_stop_handling(status),
    }


def _apply_stop_handling(status: str) -> str:
    handling = {
        "missing_profile_value": "add profile value before running browser automation",
        "missing_local_material": "record approved local material path before upload",
        "missing_answer": "ask once and store approved non-sensitive answer",
        "missing_resume_facts": "add resume facts before generating custom material",
        "needs_human_review": "stop and ask user in supervised flow",
        "manual_security_step": "stop for CAPTCHA/security step",
        "final_submit_confirmation": "stop before final submit and wait for explicit approval",
        "sensitive_not_stored": "ask on page if needed and do not persist protected-class answer",
    }
    return handling.get(status, "inspect manually before continuing")


def _playbook_handling_for_status(status: str) -> str:
    handling = {
        "covered_auto_answer": "autofill from approved answer memory/profile",
        "covered_generation": "generate from resume facts before human review",
        "covered_profile": "autofill from profile/local material",
        "covered_requires_review": "preselect but keep supervised review",
        "needs_answer_memory": "ask once and save approved non-sensitive answer",
        "needs_profile_field": "add local profile field",
        "needs_profile_material": "record approved local document path",
        "needs_resume_facts": "add resume facts before generation",
        "needs_user_confirmation": "ask during supervised flow",
        "manual_security_step": "pause for human security/CAPTCHA step",
        "final_submit_confirmation": "wait for explicit final submit approval",
        "sensitive_not_stored": "ask each time and do not persist answer",
    }
    return handling.get(status, "inspect in supervised flow")


def _dedupe_prompt_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    for row in rows:
        key = (str(row.get("label") or ""), str(row.get("coverage_status") or ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _unique_strings(values: Any) -> list[str]:
    seen: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.append(text)
    return seen


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "Unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _platform_role_key(platform: str, role_variant: str) -> str:
    return f"{platform} | {role_variant}"


def _platform_role_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        platform = str(item.get("platform") or "Unknown")
        role_variant = str(item.get("role_variant") or item.get("job_title") or "Unknown role")
        key = _platform_role_key(platform, role_variant)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _platform_role_target_shortfalls(
    counts: dict[str, int],
    target: int,
) -> dict[str, int]:
    if target <= 0:
        return {}
    shortfalls: dict[str, int] = {}
    for platform in SYNTHETIC_APPLICATION_PLATFORMS:
        for role_title in SYNTHETIC_APPLICATION_ROLE_TITLES:
            key = _platform_role_key(platform, role_title)
            shortfalls[key] = max(0, target - int(counts.get(key, 0)))
    return dict(sorted(shortfalls.items()))


def _default_target_role_families() -> list[str]:
    role_families: list[str] = []
    for title in SYNTHETIC_APPLICATION_ROLE_TITLES:
        role_family = _infer_role_family(title)
        if role_family not in role_families:
            role_families.append(role_family)
    return role_families


def _collection_query_for_role(role_family: str) -> str:
    queries = {
        "Site Reliability": "site reliability engineer OR sre production reliability",
        "Platform Infrastructure": "platform engineer infrastructure kubernetes cloud",
        "Cloud DevOps": "cloud devops engineer aws azure gcp infrastructure",
        "Software Backend": "backend software engineer infrastructure distributed systems",
    }
    return queries.get(role_family, f"{role_family} software engineer")


def _collection_query_variants_for_role(role_family: str) -> list[str]:
    variants = {
        "Site Reliability": [
            "site reliability engineer OR sre production reliability",
            "site reliability engineer",
            "sre engineer",
            "site reliability engineer sre",
            "infrastructure site reliability engineer",
            "platform site reliability engineer",
            "production engineer reliability",
            "production reliability engineer",
            "database reliability engineer",
            "reliability engineer kubernetes",
            "observability engineer",
            "devops sre engineer",
        ],
        "Platform Infrastructure": [
            "platform engineer infrastructure kubernetes cloud",
            "platform engineer",
            "infrastructure engineer kubernetes",
            "developer experience engineer infrastructure",
            "linux systems engineer platform",
        ],
        "Cloud DevOps": [
            "cloud devops engineer aws azure gcp infrastructure",
            "devops engineer",
            "senior devops engineer",
            "cloud infrastructure engineer",
            "cloud engineer kubernetes terraform",
            "cloud platform engineer",
            "infrastructure engineer aws kubernetes terraform",
            "cloud operations engineer",
            "site reliability devops engineer",
            "gitops engineer kubernetes",
        ],
        "Software Backend": [
            "backend software engineer infrastructure distributed systems",
            "backend software engineer",
            "back-end developer",
            "server-side software engineer",
            "java python go backend engineer",
        ],
    }.get(role_family, [f"{role_family} software engineer"])
    unique: list[str] = []
    for variant in variants:
        if variant not in unique:
            unique.append(variant)
    return unique


def _collection_search_urls(platform: str, query: str) -> list[str]:
    encoded_query = urllib.parse.quote_plus(query)
    platform_text = str(platform or "").lower()
    if platform_text == "linkedin":
        return [
            "https://www.linkedin.com/jobs/search/?keywords="
            f"{encoded_query}&location=United%20States",
            "https://www.google.com/search?q="
            f"site%3Alinkedin.com%2Fjobs%2Fview+{encoded_query}",
        ]
    if platform_text == "ashby":
        return [
            "https://www.google.com/search?q="
            f"site%3Ajobs.ashbyhq.com+{encoded_query}",
            "https://www.google.com/search?q="
            f"site%3Aashbyhq.com+%22{encoded_query}%22",
        ]
    if platform_text == "greenhouse":
        return [
            "https://www.google.com/search?q="
            f"site%3Ajob-boards.greenhouse.io+{encoded_query}",
            "https://www.google.com/search?q="
            f"site%3Agreenhouse.io+%22{encoded_query}%22",
        ]
    if platform_text == "lever":
        return [
            "https://www.google.com/search?q="
            f"site%3Ajobs.lever.co+{encoded_query}",
            "https://www.google.com/search?q="
            f"site%3Alever.co+%22{encoded_query}%22",
        ]
    return [f"https://www.google.com/search?q={urllib.parse.quote_plus(platform + ' ' + query)}"]


def _load_candidate_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return load_submissions_jsonl(path, limit=None)
    payload = _read_json_file(path)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ["candidates", "jobs", "results", "items"]:
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]
    return []


def _discover_candidates_from_seed_boards(
    seed_candidates: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    timeout: float,
    fetcher: Any,
    board_fetch_limit: int,
    per_platform_limit: int,
) -> dict[str, Any]:
    board_seeds: list[dict[str, str]] = []
    seen_boards: set[str] = set()
    task_platforms = {_normalize(str(task.get("platform") or "")) for task in tasks}
    for candidate in seed_candidates:
        seed = _candidate_board_seed(candidate)
        if seed is None:
            continue
        if task_platforms and _normalize(str(seed.get("platform") or "")) not in task_platforms:
            continue
        key = str(seed.get("key") or "")
        if not key or key in seen_boards:
            continue
        seen_boards.add(key)
        board_seeds.append(seed)

    candidates: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    per_platform_counts: dict[str, int] = {}
    seen_candidates: set[str] = set()
    board_fetch_count = 0

    for seed in board_seeds[: max(board_fetch_limit, 0)]:
        platform = str(seed.get("platform") or "")
        try:
            board_candidates = _fetch_seed_board_candidates(seed, timeout, fetcher)
            board_fetch_count += 1
        except Exception as exc:  # noqa: BLE001 - keep expanding other boards.
            errors.append(
                {
                    "platform": platform,
                    "board": seed.get("slug"),
                    "board_url": seed.get("board_url"),
                    "error": str(exc),
                }
            )
            continue

        for candidate in board_candidates:
            match = _matching_collection_task(candidate, tasks)
            if match is None:
                continue
            platform_count = per_platform_counts.get(platform, 0)
            if per_platform_limit > 0 and platform_count >= per_platform_limit:
                continue
            candidate["role_family"] = match.get("role_family") or candidate.get("role_family")
            candidate["discovery_query"] = match.get("query")
            candidate["discovery_board_url"] = seed.get("board_url")
            candidate["source"] = "ats_board_expansion"
            key = job_registry_key(candidate)
            if not key or key in seen_candidates:
                continue
            seen_candidates.add(key)
            candidates.append(candidate)
            per_platform_counts[platform] = platform_count + 1

    return {
        "board_seed_count": len(board_seeds),
        "board_fetch_count": board_fetch_count,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "errors": errors,
    }


def _candidate_board_seed(candidate: dict[str, Any]) -> dict[str, str] | None:
    apply_url = str(
        candidate.get("apply_url")
        or candidate.get("short_apply_url")
        or candidate.get("url")
        or candidate.get("job_url")
        or ""
    ).strip()
    if not apply_url:
        return None
    parsed = urllib.parse.urlparse(apply_url)
    host = parsed.netloc.lower()
    parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    if not parts:
        return None
    if "job-boards.greenhouse.io" in host:
        slug = parts[0]
        return {
            "key": f"greenhouse:{slug.lower()}",
            "platform": "Greenhouse",
            "slug": slug,
            "company": str(candidate.get("company") or ""),
            "board_url": f"https://boards-api.greenhouse.io/v1/boards/{urllib.parse.quote(slug)}/jobs?content=true",
        }
    if "jobs.lever.co" in host:
        slug = parts[0]
        return {
            "key": f"lever:{slug.lower()}",
            "platform": "Lever",
            "slug": slug,
            "company": str(candidate.get("company") or ""),
            "board_url": f"https://api.lever.co/v0/postings/{urllib.parse.quote(slug)}?mode=json",
        }
    if "jobs.ashbyhq.com" in host:
        slug = parts[0]
        return {
            "key": f"ashby:{slug.lower()}",
            "platform": "Ashby",
            "slug": slug,
            "company": str(candidate.get("company") or ""),
            "board_url": f"https://jobs.ashbyhq.com/{urllib.parse.quote(slug)}",
        }
    return None


def _fetch_seed_board_candidates(
    seed: dict[str, str],
    timeout: float,
    fetcher: Any,
) -> list[dict[str, Any]]:
    platform = str(seed.get("platform") or "")
    if platform == "Greenhouse":
        return _fetch_greenhouse_board_candidates(seed, timeout, fetcher)
    if platform == "Lever":
        return _fetch_lever_board_candidates(seed, timeout, fetcher)
    if platform == "Ashby":
        return _fetch_ashby_board_candidates(seed, timeout, fetcher)
    return []


def _candidate_from_seed_candidate(
    seed_candidate: dict[str, Any],
    tasks: list[dict[str, Any]],
) -> dict[str, Any] | None:
    apply_url = _normalize_candidate_apply_url(
        str(
            seed_candidate.get("apply_url")
            or seed_candidate.get("short_apply_url")
            or seed_candidate.get("url")
            or seed_candidate.get("job_url")
            or ""
        )
    )
    if not apply_url:
        return None
    title = str(seed_candidate.get("title") or seed_candidate.get("job_title") or "").strip()
    description = str(seed_candidate.get("description") or seed_candidate.get("summary") or "").strip()
    platform = (
        str(seed_candidate.get("platform") or infer_platform_from_url(apply_url) or "").strip()
        or "Unknown"
    )
    candidate = {
        "status": "DISCOVERED_CANDIDATE",
        "platform": platform,
        "company": seed_candidate.get("company") or seed_candidate.get("company_name") or _company_from_apply_url(apply_url),
        "title": title,
        "job_id": seed_candidate.get("job_id") or extract_linkedin_job_id(apply_url),
        "apply_url": apply_url,
        "location": seed_candidate.get("location"),
        "description": description[:6000],
        "role_family": seed_candidate.get("role_family") or _infer_role_family(" ".join([title, description])),
        "source": "direct_seed_candidate",
    }
    match = _matching_collection_task(candidate, tasks)
    if match is None:
        return None
    candidate["role_family"] = match.get("role_family") or candidate.get("role_family")
    candidate["discovery_query"] = match.get("query")
    return {key: value for key, value in candidate.items() if value not in {None, ""}}


def _is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "429" in text or "too many requests" in text or "rate limit" in text


def _fetch_greenhouse_board_candidates(
    seed: dict[str, str],
    timeout: float,
    fetcher: Any,
) -> list[dict[str, Any]]:
    payload = json.loads(fetcher(str(seed.get("board_url") or ""), timeout))
    jobs = payload.get("jobs") if isinstance(payload, dict) else []
    candidates: list[dict[str, Any]] = []
    for job in jobs or []:
        if not isinstance(job, dict):
            continue
        apply_url = _normalize_candidate_apply_url(str(job.get("absolute_url") or ""))
        title = str(job.get("title") or "").strip()
        if not apply_url or not title:
            continue
        location = ""
        if isinstance(job.get("location"), dict):
            location = str((job.get("location") or {}).get("name") or "").strip()
        description = _clean_html_text(html.unescape(str(job.get("content") or "")))
        candidates.append(
            _board_candidate(
                platform="Greenhouse",
                company=str(job.get("company_name") or seed.get("company") or ""),
                title=title,
                apply_url=apply_url,
                location=location,
                description=description,
                board_slug=str(seed.get("slug") or ""),
            )
        )
    return candidates


def _fetch_lever_board_candidates(
    seed: dict[str, str],
    timeout: float,
    fetcher: Any,
) -> list[dict[str, Any]]:
    payload = json.loads(fetcher(str(seed.get("board_url") or ""), timeout))
    jobs = payload if isinstance(payload, list) else []
    candidates: list[dict[str, Any]] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        apply_url = _normalize_candidate_apply_url(
            str(job.get("hostedUrl") or job.get("applyUrl") or "")
        )
        title = str(job.get("text") or "").strip()
        if not apply_url or not title:
            continue
        categories = job.get("categories") if isinstance(job.get("categories"), dict) else {}
        description = _clean_html_text(
            "\n".join(
                str(job.get(key) or "")
                for key in ["descriptionPlain", "description", "additionalPlain", "additional"]
            )
        )
        candidates.append(
            _board_candidate(
                platform="Lever",
                company=str(seed.get("company") or _company_from_apply_url(apply_url)),
                title=title,
                apply_url=apply_url,
                location=str(categories.get("location") or "").strip(),
                description=description,
                board_slug=str(seed.get("slug") or ""),
            )
        )
    return candidates


def _fetch_ashby_board_candidates(
    seed: dict[str, str],
    timeout: float,
    fetcher: Any,
) -> list[dict[str, Any]]:
    page_html = fetcher(str(seed.get("board_url") or ""), timeout)
    app_data = _parse_ashby_app_data(page_html)
    organization = app_data.get("organization") if isinstance(app_data.get("organization"), dict) else {}
    job_board = app_data.get("jobBoard") if isinstance(app_data.get("jobBoard"), dict) else {}
    jobs = job_board.get("jobPostings") if isinstance(job_board.get("jobPostings"), list) else []
    slug = str(seed.get("slug") or "")
    candidates: list[dict[str, Any]] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        if job.get("isListed") is False:
            continue
        job_id = str(job.get("id") or "").strip()
        title = str(job.get("title") or "").strip()
        if not job_id or not title:
            continue
        apply_url = _normalize_candidate_apply_url(f"https://jobs.ashbyhq.com/{slug}/{job_id}")
        if not apply_url:
            continue
        description = _clean_html_text(
            " ".join(
                str(job.get(key) or "")
                for key in ["departmentName", "teamName", "employmentType", "workplaceType"]
            )
        )
        candidates.append(
            _board_candidate(
                platform="Ashby",
                company=str(organization.get("name") or seed.get("company") or ""),
                title=title,
                apply_url=apply_url,
                location=str(job.get("locationName") or job.get("locationExternalName") or "").strip(),
                description=description,
                board_slug=slug,
            )
        )
    return candidates


def _parse_ashby_app_data(page_html: str) -> dict[str, Any]:
    marker = "window.__appData"
    marker_index = str(page_html).find(marker)
    if marker_index < 0:
        return {}
    equals_index = str(page_html).find("=", marker_index)
    if equals_index < 0:
        return {}
    raw = str(page_html)[equals_index + 1 :].lstrip()
    try:
        payload, _ = json.JSONDecoder().raw_decode(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _board_candidate(
    platform: str,
    company: str,
    title: str,
    apply_url: str,
    location: str,
    description: str,
    board_slug: str,
) -> dict[str, Any]:
    return {
        "status": "DISCOVERED_CANDIDATE",
        "platform": platform,
        "company": company,
        "title": title,
        "apply_url": apply_url,
        "location": location,
        "description": description[:6000],
        "role_family": _infer_role_family(title),
        "board_slug": board_slug,
    }


def _matching_collection_task(
    candidate: dict[str, Any],
    tasks: list[dict[str, Any]],
) -> dict[str, Any] | None:
    candidate_platform = _normalize(str(candidate.get("platform") or ""))
    for task in tasks:
        if _normalize(str(task.get("platform") or "")) != candidate_platform:
            continue
        if _candidate_matches_role_family(candidate, str(task.get("role_family") or "")):
            return task
    return None


def _candidate_matches_role_family(candidate: dict[str, Any], role_family: str) -> bool:
    if not role_family:
        return True
    inferred = str(candidate.get("role_family") or "")
    if inferred == role_family:
        return True
    if inferred and inferred != "Other":
        return False
    title_text = _normalize(str(candidate.get("title") or ""))
    description_text = _normalize(str(candidate.get("description") or ""))
    role_keywords = {
        "Site Reliability": [
            "site reliability",
            "sre",
            "production reliability",
            "reliability engineer",
            "observability engineer",
            "incident management",
        ],
        "Platform Infrastructure": [
            "platform",
            "infrastructure",
            "kubernetes",
            "ci cd",
            "devops platform",
            "developer experience",
            "devex",
            "linux systems",
            "build automation",
            "build release",
            "build & release",
        ],
        "Cloud DevOps": ["devops", "cloud", "aws", "azure", "gcp", "gitops"],
        "Software Backend": [
            "backend",
            "back end",
            "back-end",
            "api",
            "distributed systems",
            "software engineer",
            "software developer",
            "server side",
            "server-side",
            "java developer",
            "python developer",
            "golang engineer",
        ],
    }
    keywords = role_keywords.get(role_family, [_normalize(role_family)])
    if any(keyword in title_text for keyword in keywords):
        if not _title_has_engineering_signal(title_text):
            return False
        return True
    if not _title_has_engineering_signal(title_text):
        return False
    if not _title_has_role_family_context(title_text, role_family):
        return False
    return any(keyword in description_text for keyword in keywords)


def _title_has_role_family_context(normalized_title: str, role_family: str) -> bool:
    title = str(normalized_title or "")
    if role_family in {"Site Reliability", "Platform Infrastructure", "Cloud DevOps"} and _title_is_generic_engineer(title):
        return True
    context_terms = {
        "Site Reliability": [
            "site reliability",
            "sre",
            "reliability",
            "observability",
            "production engineer",
            "database reliability",
            "dbre",
        ],
        "Platform Infrastructure": [
            "platform",
            "infrastructure",
            "kubernetes",
            "devops",
            "developer experience",
            "devex",
            "linux systems",
            "build release",
            "systems engineer",
        ],
        "Cloud DevOps": [
            "cloud",
            "devops",
            "platform",
            "infrastructure",
            "kubernetes",
            "gitops",
            "site reliability",
            "sre",
            "systems engineer",
        ],
        "Software Backend": [
            "backend",
            "back end",
            "back-end",
            "software engineer",
            "software developer",
            "server side",
            "server-side",
            "api",
        ],
    }.get(role_family, [_normalize(role_family)])
    return any(term in title for term in context_terms)


def _title_is_generic_engineer(normalized_title: str) -> bool:
    return bool(
        re.fullmatch(
            r"(?:(?:senior|sr|staff|principal|lead|associate|junior|jr)\s+)?"
            r"(?:software\s+)?engineer(?:\s+(?:i|ii|iii|iv|v|[1-5]))?",
            str(normalized_title or "").strip(),
        )
    )


def _extract_candidate_links_from_search_html(
    page_html: str,
    platform: str = "",
) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in re.finditer(
        r"<a\b[^>]*\bhref=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
        str(page_html),
        flags=re.IGNORECASE | re.DOTALL,
    ):
        href = html.unescape(match.group(1))
        text = _clean_html_text(match.group(2))
        for candidate_url in _candidate_urls_from_href(href):
            normalized_url = _normalize_candidate_apply_url(candidate_url)
            if not normalized_url:
                continue
            inferred_platform = infer_platform_from_url(normalized_url)
            if platform and inferred_platform and inferred_platform.lower() != platform.lower():
                continue
            if platform and not inferred_platform:
                continue
            key = normalized_url.lower()
            if key in seen:
                continue
            seen.add(key)
            links.append({"url": normalized_url, "text": text})
    for match in re.finditer(
        r"<link>(.*?)</link>",
        str(page_html),
        flags=re.IGNORECASE | re.DOTALL,
    ):
        text = _clean_html_text(match.group(1))
        for candidate_url in _candidate_urls_from_href(text):
            normalized_url = _normalize_candidate_apply_url(candidate_url)
            if not normalized_url:
                continue
            inferred_platform = infer_platform_from_url(normalized_url)
            if platform and inferred_platform and inferred_platform.lower() != platform.lower():
                continue
            key = normalized_url.lower()
            if key not in seen:
                seen.add(key)
                links.append({"url": normalized_url, "text": ""})
    for match in re.finditer(r"https?://[^\s\"'<>]+", str(page_html), flags=re.IGNORECASE):
        for candidate_url in _candidate_urls_from_href(match.group(0)):
            normalized_url = _normalize_candidate_apply_url(candidate_url)
            if not normalized_url:
                continue
            inferred_platform = infer_platform_from_url(normalized_url)
            if platform and inferred_platform and inferred_platform.lower() != platform.lower():
                continue
            key = normalized_url.lower()
            if key not in seen:
                seen.add(key)
                links.append({"url": normalized_url, "text": ""})
    return links


def _candidate_discovery_search_urls(task: dict[str, Any]) -> list[str]:
    platform = str(task.get("platform") or "")
    query = str(task.get("query") or "")
    query_variants = _string_list(task.get("query_variants")) or ([query] if query else [])
    urls: list[str] = []
    if _normalize(platform) == "linkedin":
        for variant in query_variants:
            for url in _linkedin_guest_search_urls(variant):
                if url not in urls:
                    urls.append(url)
    site = _platform_primary_search_domain(platform)
    for variant in query_variants:
        if not site or not variant:
            continue
        encoded = urllib.parse.quote_plus(f"site:{site} {variant}")
        for url in [
            f"https://www.bing.com/search?format=rss&q={encoded}&count=50",
            f"https://www.bing.com/search?q={encoded}&count=50",
        ]:
            if url not in urls:
                urls.append(url)
    for url in _string_list(task.get("search_urls")):
        if url not in urls:
            urls.append(url)
    return urls


def _linkedin_guest_search_urls(query: str) -> list[str]:
    if not str(query or "").strip():
        return []
    base = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    urls: list[str] = []
    for start in [0, 10, 20, 30, 40]:
        params = urllib.parse.urlencode(
            {
                "keywords": str(query).strip(),
                "location": "United States",
                "geoId": "103644278",
                "start": str(start),
            }
        )
        urls.append(f"{base}?{params}")
    return urls


def _platform_primary_search_domain(platform: str) -> str:
    normalized = _normalize(platform)
    if normalized == "ashby":
        return "jobs.ashbyhq.com"
    if normalized == "greenhouse":
        return "job-boards.greenhouse.io"
    if normalized == "lever":
        return "jobs.lever.co"
    if normalized == "linkedin":
        return "linkedin.com/jobs/view"
    return ""


def _candidate_urls_from_href(href: str) -> list[str]:
    value = str(href or "").strip()
    if not value:
        return []
    decoded = html.unescape(value)
    urls: list[str] = []

    def add(candidate: str) -> None:
        candidate = urllib.parse.unquote(html.unescape(str(candidate))).strip()
        if candidate.startswith("//"):
            candidate = "https:" + candidate
        if candidate.startswith("http://") or candidate.startswith("https://"):
            urls.append(candidate)

    add(decoded)
    parsed = urllib.parse.urlparse(decoded)
    query = urllib.parse.parse_qs(parsed.query)
    for key in ["q", "url", "u"]:
        for raw in query.get(key, []):
            add(raw)
            bing_url = _decode_bing_redirect_url(raw)
            if bing_url:
                add(bing_url)
    return urls


def _decode_bing_redirect_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw.startswith("a1") or len(raw) <= 2:
        return ""
    payload = raw[2:]
    padding = "=" * (-len(payload) % 4)
    try:
        return base64.urlsafe_b64decode((payload + padding).encode("ascii")).decode(
            "utf-8",
            "ignore",
        )
    except Exception:  # noqa: BLE001 - best-effort redirect decoding.
        return ""


def _normalize_candidate_apply_url(url: str) -> str:
    parsed = urllib.parse.urlparse(str(url).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    host = parsed.netloc.lower()
    path = parsed.path or ""
    if "linkedin.com" in host:
        job_id = extract_linkedin_job_id(str(url))
        if not job_id:
            return ""
        return f"https://www.linkedin.com/jobs/view/{job_id}/"
    if "greenhouse.io" in host:
        if "/jobs/" not in path:
            return ""
        return shorten_apply_url(urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, "", "", "")))
    if "ashbyhq.com" in host:
        if len([part for part in path.split("/") if part]) < 2:
            return ""
        return shorten_apply_url(urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, "", "", "")))
    if "lever.co" in host:
        if len([part for part in path.split("/") if part]) < 2:
            return ""
        return shorten_apply_url(urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, "", "", "")))
    return ""


def _candidate_from_discovered_link(
    link: dict[str, str],
    task: dict[str, Any],
    search_url: str,
) -> dict[str, Any] | None:
    apply_url = _normalize_candidate_apply_url(str(link.get("url") or ""))
    if not apply_url:
        return None
    platform = infer_platform_from_url(apply_url) or str(task.get("platform") or "Unknown")
    company = _company_from_apply_url(apply_url)
    title = _title_from_search_result_text(str(link.get("text") or ""), company)
    inferred_role = _infer_role_family(title) if title else ""
    role_family = str(task.get("role_family") or inferred_role)
    if title and role_family:
        role_check = {"platform": platform, "title": title, "role_family": inferred_role}
        if not _candidate_matches_role_family(role_check, role_family):
            return None
    candidate = {
        "status": "DISCOVERED_CANDIDATE",
        "platform": platform,
        "company": company,
        "title": title,
        "job_id": extract_linkedin_job_id(apply_url),
        "apply_url": apply_url,
        "role_family": role_family,
        "discovery_query": task.get("query"),
        "discovery_search_url": search_url,
        "source": "collection_plan_search_discovery",
    }
    return {key: value for key, value in candidate.items() if value not in {None, ""}}


def _company_from_apply_url(url: str) -> str:
    parsed = urllib.parse.urlparse(str(url))
    parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    host = parsed.netloc.lower()
    company = ""
    if "greenhouse.io" in host and parts:
        company = parts[0]
    elif "ashbyhq.com" in host and parts:
        company = parts[0]
    elif "lever.co" in host and parts:
        company = parts[0]
    if not company:
        return ""
    return re.sub(r"[-_]+", " ", company).strip().title()


def _title_from_search_result_text(text: str, company: str = "") -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if not value:
        return ""
    value = re.sub(r"\s+\|\s+LinkedIn.*$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+-\s+[^-]{1,80}\s+Jobs?\s*$", "", value, flags=re.IGNORECASE)
    if company:
        value = re.sub(rf"\s+at\s+{re.escape(company)}\b.*$", "", value, flags=re.IGNORECASE)
        value = re.sub(rf"\s+-\s+{re.escape(company)}\b.*$", "", value, flags=re.IGNORECASE)
    return value[:180]


def _normalize_candidate_observation(candidate: dict[str, Any], source: str) -> dict[str, Any]:
    apply_url = str(
        candidate.get("apply_url")
        or candidate.get("short_apply_url")
        or candidate.get("url")
        or candidate.get("job_url")
        or ""
    ).strip()
    short_url = shorten_apply_url(apply_url, candidate)
    title = str(candidate.get("title") or candidate.get("job_title") or "").strip()
    platform = (
        str(candidate.get("platform") or infer_platform_from_url(short_url) or "").strip()
        or "Unknown"
    )
    description = str(candidate.get("description") or candidate.get("summary") or "").strip()
    normalized = {
        "status": "OBSERVED_CANDIDATE",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "platform": platform,
        "company": candidate.get("company") or candidate.get("company_name"),
        "title": title or None,
        "location": candidate.get("location"),
        "job_id": candidate.get("job_id") or extract_linkedin_job_id(short_url),
        "apply_url": short_url or apply_url,
        "role_family": _infer_role_family(" ".join([title, description])),
    }
    for key in ["questions", "page_excerpt", "description"]:
        if candidate.get(key) is not None:
            normalized[key] = candidate.get(key)
    normalized["registry_key"] = job_registry_key(normalized)
    return normalized


def _candidate_with_role_family(candidate: dict[str, Any]) -> dict[str, Any]:
    title = str(candidate.get("title") or candidate.get("job_title") or "").strip()
    description = str(candidate.get("description") or candidate.get("summary") or "").strip()
    role_family = str(candidate.get("role_family") or "").strip()
    if role_family:
        return dict(candidate)
    return {**candidate, "role_family": _infer_role_family(" ".join([title, description]))}


def _candidate_platform_role_pair(candidate: dict[str, Any]) -> str:
    platform = str(candidate.get("platform") or infer_platform_from_url(str(candidate.get("apply_url") or "")) or "")
    role_family = str(candidate.get("role_family") or "").strip()
    if not platform or not role_family:
        return ""
    return f"{platform}::{role_family}"


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
    engineering_signal = _title_has_engineering_signal(text)
    if (
        "site reliability" in text
        or re.search(r"\bsre\b", text)
        or "reliability engineer" in text
        or "observability engineer" in text
        or "production reliability" in text
        or "incident management engineer" in text
    ):
        return "Site Reliability"
    if (
        "devops" in text
        or "cloud engineer" in text
        or "cloud infrastructure" in text
        or "cloud operations" in text
        or "cloud ops" in text
        or "gitops" in text
    ):
        return "Cloud DevOps"
    if engineering_signal and any(
        term in text
        for term in [
            "platform",
            "infrastructure",
            "kubernetes",
            "ci cd",
            "developer experience",
            "devex",
            "build automation",
            "build release",
            "build & release",
            "linux systems",
            "systems engineer",
        ]
    ):
        return "Platform Infrastructure"
    if engineering_signal and "cloud" in text:
        return "Cloud DevOps"
    if any(
        term in text
        for term in [
            "backend",
            "back end",
            "back-end",
            "api",
            "server side",
            "server-side",
            "software engineer",
            "software developer",
            "java developer",
            "python developer",
            "golang engineer",
        ]
    ):
        return "Software Backend"
    if engineering_signal and any(term in text for term in ["ai", "ml", "machine learning", "data"]):
        return "Data AI"
    if engineering_signal and any(term in text for term in ["system engineer", "systems engineer", "hardware"]):
        return "Systems Hardware"
    return "Other"


def _title_has_engineering_signal(normalized_title: str) -> bool:
    if any(
        term in normalized_title
        for term in [
            "account ",
            "accountant",
            "account manager",
            "analytics engineer",
            "business developer",
            "business development",
            "business systems",
            "client platforms",
            "content writer",
            "customer success",
            "data architecture consultant",
            "director ",
            "developer relations",
            "design manager",
            "employee engagement",
            "engineering manager",
            "frontend",
            "front-end",
            "full stack",
            "full-stack",
            "finance",
            "legal",
            "marketing",
            "marketplace",
            "mobile engineering",
            "people partner",
            "people operations",
            "product manager",
            "product owner",
            "project manager",
            "qa analyst",
            "recruiter",
            "revenue operations",
            "sales",
            "sdet",
            "talent acquisition",
            "systems accountant",
            "technical content architect",
            "technical writer",
        ]
    ):
        return False
    return any(
        term in normalized_title
        for term in [
            "architect",
            "backend",
            "cloud engineer",
            "cloud support engineer",
            "developer",
            "devops",
            "engineer",
            "engineering",
            "infrastructure",
            "kubernetes",
            "linux",
            "platform",
            "production",
            "reliability",
            "site reliability",
            "software",
            "systems",
        ]
    )


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
    if _is_low_signal_application_prompt(normalized):
        return True
    return (
        normalized in {"", "select", "select...", "start typing", "search", "application"}
        and classification.category in {"unlabeled_control", "unknown"}
    )


def _is_low_signal_application_prompt(normalized: str) -> bool:
    if re.fullmatch(r"\d{3,}", normalized):
        return True
    if re.fullmatch(r"go (to )?page \d+", normalized):
        return True
    if re.fullmatch(r"question \d+", normalized):
        return True
    if re.fullmatch(r"\d+ (what is the purpose of this document|how is your personal data collected|how long will you use my information for)", normalized):
        return True
    if re.fullmatch(r"(start|end) (month|year) \d+", normalized):
        return True
    if re.fullmatch(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)( required)?", normalized):
        return True
    if re.fullmatch(r"(btn2?|custom field) [a-z0-9 ]+", normalized):
        return True
    if normalized.startswith("toggle child menu"):
        return True
    if normalized.startswith(("pr t e ", "pr t ", "tu veux ", "tu aimes ", "et si tu ", "c est quoi ")):
        return True
    return normalized in {
        "a talented senior net software engineer passionate about designing robust scalable backend systems",
        "ai powered advice",
        "advanced",
        "am i a good fit for this job",
        "amarela",
        "account id",
        "are you a fit",
        "area",
        "asian",
        "beginner",
        "black or african american",
        "built in",
        "arm bicep",
        "department",
        "department filter",
        "discipline",
        "discipline 0",
        "do you consider yourself more of a",
        "enter manually",
        "et apr s",
        "et lille dans tout a",
        "et niort dans tout a",
        "ey em",
        "event media interview or other pr",
        "expert",
        "fae faer",
        "female",
        "he him",
        "hir hir",
        "hu hu",
        "ind gena",
        "indigenous peoples first nations native american or alaska native",
        "if you answered yes to the question above please provide more details",
        "intermediate",
        "keyword filter",
        "l objectif",
        "linked in data",
        "next page",
        "number",
        "office",
        "office filter",
        "open roles",
        "org",
        "origin",
        "previous page",
        "profile",
        "pr sentiel ou t l travail",
        "pr t nous rejoindre",
        "qu esperamos de vos",
        "qui sommes nous",
        "ready to accelerate your career",
        "ready to shape future with us",
        "referer",
        "search input",
        "tailor my resume",
        "tired of being treated like a company drone",
        "tired of promised adventures during the hiring phase then being dropped off on a remote contract and never seen or heard from the mothership again",
        "tired of promised adventures during the hiring phase then dropped off on a remote contract and never seen or heard from the mothership again",
        "toggle flyout",
        "type your response",
        "use name only",
        "want more info",
        "web",
        "what is the interview process like",
        "you ve got this",
        "what is delek what do we do",
        "what s in it for you",
        "what s it",
        "what s the role about",
        "who are we",
        "who are we looking for",
        "who else works at ashby",
        "who are you",
        "would you like to know more about this opportunity",
        "ai ml",
        "asa",
        "anytime as needed",
        "1 week per month",
        "2 weeks per month",
        "cat 1",
        "cat 2",
        "cat 3",
        "cat 4",
        "clearance",
        "no clearance",
        "secret",
        "top secret",
        "top secret ts",
        "ts/sci with ci poly",
        "ts/sci with full scope poly",
        "top secret/sci ts/sci",
        "custom",
        "confidential",
        "claude",
        "chinese",
        "inuk inuit",
        "latin american",
        "metis",
        "cloudflare",
        "datadog",
        "elk",
        "elasticsearch",
        "focus",
        "git",
        "go",
        "google",
        "global region",
        "glassdoor",
        "grafana",
        "harness",
        "html/css",
        "html css",
        "angular",
        "akamai",
        "arm bicep",
        "bash",
        "c",
        "c c",
        "ca",
        "caia",
        "ceph",
        "certifications",
        "cfa",
        "cia",
        "cpa",
        "cloud",
        "commercial systems",
        "community",
        "consulting engineering",
        "containers",
        "data infrastructure",
        "data science",
        "databases",
        "debian",
        "devops",
        "dbms",
        "desktop",
        "distributed systems",
        "distro",
        "distro packaging",
        "docker",
        "embedded",
        "embedded linux",
        "enterprise",
        "esq",
        "fsa",
        "flutter",
        "golang",
        "great do my skills fit",
        "graphics",
        "graphics browser and desktop",
        "hardware",
        "html css javascript",
        "human factors safety sociotechnical systems",
        "identity",
        "juju",
        "kernel",
        "landscape",
        "linux kernel",
        "maas",
        "not sure if this is you",
        "experience",
        "i don t have this experience",
        "job board other",
        "job function",
        "indeed",
        "jenkins",
        "kafka",
        "kafka streams",
        "key vault",
        "llm",
        "lxd",
        "linux desktop",
        "linux environment",
        "machine learning",
        "mcse",
        "mongodb",
        "ms",
        "ms build",
        "ms foundry",
        "mysql postgresql",
        "n a",
        "n o",
        "nginx",
        "nist",
        "no",
        "none",
        "octopus deploy",
        "other please specify",
        "outra",
        "outro",
        "remove all filters",
        "search jobs",
        "role",
        "summary",
        "sounds great but do my skills fit",
        "olap",
        "openai",
        "openstack",
        "observability",
        "operations research decision analytics",
        "other",
        "packaging",
        "performance",
        "python",
        "quality reliability continuous improvement",
        "qemu kvm",
        "ready to apply",
        "react",
        "restaurant365 career page",
        "recruiter outreach",
        "red hat linux",
        "redux",
        "robotics",
        "rust",
        "saas",
        "sat score",
        "scala",
        "security",
        "service bus",
        "she her",
        "silicon enablement and drivers",
        "server",
        "shpe conference",
        "sim",
        "sql",
        "south asian ie indian pakistani sri lankan etc",
        "southeast asian ie vietnamese cambodian malaysian laotian etc",
        "storage",
        "supply chain logistics service operations",
        "spark",
        "splunk",
        "what can you do for alarm com",
        "what do you need",
        "tech stack",
        "they them",
        "time series databases",
        "top secret sci ts sci",
        "ts sci with ci poly",
        "ts sci with full scope poly",
        "twitter x",
        "twitter",
        "typescript",
        "social",
        "ubuntu",
        "ubuntu core",
        "ubuntu desktop",
        "ubuntu server",
        "virtualisation",
        "virtualisation vmm qemu rustvmm",
        "vue js",
        "web back end",
        "web front end",
        "web frontend",
        "west asian ie iranian afghan etc",
        "white",
        "write here",
        "xe xem",
        "yes",
        "ze hir",
        "iot",
        "java",
        "javascript",
        "k8s",
        "linux administration ops",
        "linux security",
        "networking ovn ovs sonic dent dpdk",
    }


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
        and ("experience" in normalized_question or "expertise" in normalized_question)
    ):
        answer = profile.question_answers.get("years_experience")
        if answer:
            return answer
    if "for how many years" in normalized_question:
        answer = profile.question_answers.get("years_experience")
        if answer:
            return answer
    if (
        "which languages" in normalized_question
        and "professional" in normalized_question
        and "other than english" not in normalized_question
        and profile.question_answers.get("english_level")
    ):
        return "English"

    answer_map = {
        "authorization": [
            "authorized",
            "authorization",
            "work in the united states",
            "eligible to work",
            "legal right to work",
            "right to work",
            "work eligibility status",
        ],
        "sponsorship": ["sponsor", "sponsorship", "visa", "immigration assistance"],
        "compensation": ["salary", "compensation", "pay", "ctc", "combien tu vas gagner"],
        "compensation_currency": ["currency", "preferred currency"],
        "start_date": ["start", "available", "availability", "notice period", "notice", "commence"],
        "relocation": ["relocat"],
        "remote_preference": ["remote-friendly", "remote friendly", "remote work", "work remotely"],
        "onsite_hybrid": ["onsite", "on-site", "in office", "in-office", "hybrid", "office"],
        "english_level": [
            "english level",
            "english language skills",
            "verbal and written english",
            "professional working proficiency in english",
            "communicate with a professional working proficiency in english",
        ],
        "policy_acknowledgement": [
            "agree",
            "acknowledgement",
            "acknowledgment",
            "acknowledge",
            "acknowledged",
            "privacy",
            "privacy policy",
            "terms conditions",
            "terms and conditions",
            "certify the information provided",
            "accurate and true",
            "processed in accordance",
            "consider me for other job opportunities",
            "contact you about job opportunities",
            "personal information retained",
            "consenting to the use of ai",
        ],
        "age_over_18": ["18 years of age", "18 or older", "at least 18"],
        "ai_application_disclosure": ["did ai complete", "ai complete this application"],
        "referral_source": [
            "hear about",
            "heard about",
            "learn about",
            "where did you find",
            "find this job posting",
            "found this job posting",
            "influenced your decision",
            "source",
            "stack overflow jobs",
            "job board",
            "indeed",
        ],
        "referral_contact": ["referral", "referred by", "who should we thank"],
        "communication_consent": ["sms", "whatsapp", "text message", "future contact"],
        "cloud_provider_general": [
            "gcp",
            "google cloud",
            "aws",
            "azure",
            "cloud provider",
            "cloud providers",
        ],
    }
    for answer_key, hints in answer_map.items():
        answer = profile.question_answers.get(answer_key)
        if answer and any(hint in normalized_question for hint in hints):
            return answer
    return None


def _employment_date_value(label: str, profile: CandidateProfile) -> dict[str, str]:
    text = _normalize(label)
    facts = profile.resume_facts
    field_key = ""
    if "start" in text and "month" in text:
        field_key = "current_role_start_month"
    elif "start" in text and "year" in text:
        field_key = "current_role_start_year"
    elif "end" in text and "month" in text:
        field_key = "current_role_end_month"
    elif "end" in text and "year" in text:
        field_key = "current_role_end_year"

    if field_key and facts.get(field_key):
        return {
            "source": f"profile.resume_facts.{field_key}",
            "value": facts[field_key],
        }
    return {
        "source": "profile.resume_facts.employment_dates",
        "value": facts.get("employment_dates", ""),
    }


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


def _html_to_text(html_text: str) -> str:
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", str(html_text or ""))
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</(p|div|li|label|legend|h[1-6]|tr)>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _clean_html_text(value: str) -> str:
    return re.sub(r"\s+", " ", _html_to_text(value)).strip(" *:\u00a0")


def _extract_html_meta(html_text: str, names: list[str]) -> str | None:
    wanted = {_normalize(name) for name in names}
    for match in re.finditer(r"(?is)<meta\b([^>]*)>", str(html_text or "")):
        attrs = _html_attrs(match.group(1))
        key = attrs.get("property") or attrs.get("name")
        if key and _normalize(key) in wanted:
            content = attrs.get("content")
            if content:
                return html.unescape(content).strip()
    return None


def _extract_html_title(html_text: str) -> str | None:
    meta_title = _extract_html_meta(html_text, ["og:title", "twitter:title"])
    if meta_title:
        return meta_title
    match = re.search(r"(?is)<title\b[^>]*>(.*?)</title>", str(html_text or ""))
    if match:
        title = _clean_html_text(match.group(1))
        return title or None
    return None


def _html_attrs(attr_text: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in re.finditer(r"(?is)([a-z_:][-a-z0-9_:.]*)\s*=\s*(['\"])(.*?)\2", attr_text):
        attrs[match.group(1).lower()] = html.unescape(match.group(3)).strip()
    return attrs


def _question_problem_bucket_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        status = str(row.get("coverage_status") or "unknown")
        category = str(row.get("category") or "unknown")
        next_action = str(row.get("next_action") or "")
        key = (status, category, next_action)
        bucket = buckets.setdefault(
            key,
            {
                "coverage_status": status,
                "category": category,
                "next_action": next_action,
                "unique_prompt_count": 0,
                "observed_count": 0,
                "required_count": 0,
                "platforms": set(),
                "labels": [],
            },
        )
        bucket["unique_prompt_count"] += 1
        bucket["observed_count"] += int(row.get("observed_count") or 0)
        bucket["required_count"] += int(row.get("required_count") or 0)
        for platform in str(row.get("platforms") or "").split(","):
            platform = platform.strip()
            if platform:
                bucket["platforms"].add(platform)
        label = str(row.get("label") or "").strip()
        if label and label not in bucket["labels"]:
            bucket["labels"].append(label)

    result: list[dict[str, Any]] = []
    for bucket in buckets.values():
        labels = bucket.pop("labels")
        platforms = sorted(bucket.pop("platforms"))
        result.append(
            {
                **bucket,
                "platforms": ", ".join(platforms),
                "top_labels": "\n".join(labels[:8]),
            }
        )
    result.sort(
        key=lambda item: (
            -int(item.get("required_count") or 0),
            -int(item.get("observed_count") or 0),
            str(item.get("coverage_status") or ""),
            str(item.get("category") or ""),
        )
    )
    return result


def _source_artifact_export_rows(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for artifact in artifacts:
        rows.append(
            {
                "name": artifact.get("name"),
                "path": artifact.get("path"),
                "exists": bool(artifact.get("exists")),
                "size_bytes": int(artifact.get("size_bytes") or 0),
                "updated_at": artifact.get("updated_at") or "",
            }
        )
    return rows


def _synthetic_execution_export_rows(
    coverage_gate: dict[str, Any],
    synthetic_browser_execution: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    synthetic = (coverage_gate.get("synthetic") or {}).copy()
    if synthetic_browser_execution:
        synthetic.update(
            {
                key: synthetic_browser_execution.get(key)
                for key in [
                    "generated_at",
                    "execution",
                    "requested_count",
                    "run_count",
                    "per_platform_role_target",
                    "platform_role_target_achieved",
                    "local_synthetic_submit_allowed",
                    "actual_submit_count",
                    "would_submit_count",
                    "eligible_submit_target_count",
                    "eligible_submit_count",
                    "eligible_submit_achieved",
                    "expected_blocker_count",
                    "real_platform_submission",
                    "selector_miss_count",
                    "executed_action_count",
                    "stop_action_count",
                    "synthetic_gate_answer_count",
                ]
                if synthetic_browser_execution.get(key) is not None
            }
        )
    keys = [
        "generated_at",
        "execution",
        "requested_count",
        "run_count",
        "per_platform_role_target",
        "platform_role_target_achieved",
        "local_synthetic_submit_allowed",
        "actual_submit_count",
        "would_submit_count",
        "eligible_submit_target_count",
        "eligible_submit_count",
        "eligible_submit_achieved",
        "expected_blocker_count",
        "real_platform_submission",
        "selector_miss_count",
        "executed_action_count",
        "stop_action_count",
        "synthetic_gate_answer_count",
    ]
    return [{"metric": key, "value": synthetic.get(key, "")} for key in keys if key in synthetic]


def _mapping_dict_rows(values: dict[str, Any], key_name: str, value_name: str) -> list[dict[str, Any]]:
    return [
        {key_name: key, value_name: value}
        for key, value in sorted((values or {}).items(), key=lambda item: str(item[0]))
    ]


def _fake_learning_probe_export_rows(fake_learning_probe: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not fake_learning_probe:
        return []
    after = fake_learning_probe.get("after_fake_learning") or {}
    baseline = fake_learning_probe.get("baseline") or {}
    metrics = {
        "generated_at": fake_learning_probe.get("generated_at"),
        "real_platform_submission": fake_learning_probe.get("real_platform_submission"),
        "input_task_count": fake_learning_probe.get("input_task_count"),
        "fake_answered_task_count": fake_learning_probe.get("fake_answered_task_count"),
        "fake_answer_memory_entry_count": fake_learning_probe.get("fake_answer_memory_entry_count"),
        "fake_category_policy_count": fake_learning_probe.get("fake_category_policy_count"),
        "baseline_blocking_prompt_count": baseline.get("blocking_prompt_count"),
        "after_fake_learning_blocking_prompt_count": after.get("blocking_prompt_count"),
        "remaining_learning_blocker_count": fake_learning_probe.get("remaining_learning_blocker_count"),
        "remaining_manual_gate_count": fake_learning_probe.get("remaining_manual_gate_count"),
        "learning_blockers_cleared": fake_learning_probe.get("learning_blockers_cleared"),
    }
    return [{"metric": key, "value": value} for key, value in metrics.items()]


def _fake_position_rehearsal_export_rows(fake_position_rehearsal: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not fake_position_rehearsal:
        return []
    metrics = {
        "generated_at": fake_position_rehearsal.get("generated_at"),
        "execution": fake_position_rehearsal.get("execution"),
        "requested_count": fake_position_rehearsal.get("requested_count"),
        "run_count": fake_position_rehearsal.get("run_count"),
        "per_platform_role_target": fake_position_rehearsal.get("per_platform_role_target"),
        "platform_role_target_achieved": fake_position_rehearsal.get("platform_role_target_achieved"),
        "real_platform_submission": fake_position_rehearsal.get("real_platform_submission"),
        "local_synthetic_submit_allowed": fake_position_rehearsal.get("local_synthetic_submit_allowed"),
        "actual_submit_count": fake_position_rehearsal.get("actual_submit_count"),
        "eligible_submit_target_count": fake_position_rehearsal.get("eligible_submit_target_count"),
        "eligible_submit_count": fake_position_rehearsal.get("eligible_submit_count"),
        "eligible_submit_achieved": fake_position_rehearsal.get("eligible_submit_achieved"),
        "selector_miss_count": fake_position_rehearsal.get("selector_miss_count"),
        "pre_synthetic_missing_input_count": fake_position_rehearsal.get("pre_synthetic_missing_input_count"),
        "pre_synthetic_manual_security_count": fake_position_rehearsal.get("pre_synthetic_manual_security_count"),
        "pre_synthetic_sensitive_gate_count": fake_position_rehearsal.get("pre_synthetic_sensitive_gate_count"),
        "pre_synthetic_final_submit_count": fake_position_rehearsal.get("pre_synthetic_final_submit_count"),
        "excluded_closed_position_count": fake_position_rehearsal.get("excluded_closed_position_count"),
        "skipped_no_prompt_position_count": fake_position_rehearsal.get("skipped_no_prompt_position_count"),
        "unexpected_run_count": fake_position_rehearsal.get("unexpected_run_count"),
        "inferred_prompt_position_count": fake_position_rehearsal.get("inferred_prompt_position_count"),
        "inferred_prompt_item_count": fake_position_rehearsal.get("inferred_prompt_item_count"),
        "fake_answer_memory_entry_count": fake_position_rehearsal.get("fake_answer_memory_entry_count"),
        "fake_category_policy_count": fake_position_rehearsal.get("fake_category_policy_count"),
    }
    rows = [{"metric": key, "value": value} for key, value in metrics.items()]
    for prefix, values in [
        ("outcome", fake_position_rehearsal.get("outcome_counts") or {}),
        ("policy_stop", fake_position_rehearsal.get("policy_stop_counts") or {}),
        ("platform", fake_position_rehearsal.get("platform_counts") or {}),
        ("role_family", fake_position_rehearsal.get("role_family_counts") or {}),
    ]:
        for key, value in sorted(values.items()):
            rows.append({"metric": f"{prefix}:{key}", "value": value})
    for key, value in sorted((fake_position_rehearsal.get("platform_role_target_shortfalls") or {}).items()):
        rows.append({"metric": f"platform_role_shortfall:{key}", "value": value})
    return rows


def _answer_memory_export_rows(answer_memory: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not answer_memory:
        return []
    entries = answer_memory.get("answers") or []
    if isinstance(entries, dict):
        iterable = entries.values()
    elif isinstance(entries, list):
        iterable = entries
    else:
        iterable = []
    rows: list[dict[str, Any]] = []
    for entry in iterable:
        if not isinstance(entry, dict):
            continue
        example = entry.get("example_job") or {}
        if isinstance(example, dict):
            example_job = " | ".join(
                part
                for part in [
                    str(example.get("platform") or "").strip(),
                    str(example.get("company") or "").strip(),
                    str(example.get("title") or "").strip(),
                    str(example.get("job_id") or "").strip(),
                ]
                if part
            )
        else:
            example_job = ""
        rows.append(
            {
                "normalized_question": entry.get("normalized_question"),
                "sample_question": entry.get("sample_question"),
                "source": entry.get("source"),
                "approved_count": entry.get("approved_count", 0),
                "first_seen_at": entry.get("first_seen_at"),
                "last_seen_at": entry.get("last_seen_at"),
                "example_job": example_job,
                "answer_stored": bool(entry.get("answer")),
            }
        )
    return rows


def _closed_posting_export_rows(closed_jobs: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not closed_jobs:
        return []
    entries = closed_jobs.get("jobs") or []
    if isinstance(entries, dict):
        iterable = entries.values()
    elif isinstance(entries, list):
        iterable = entries
    else:
        iterable = []
    rows: list[dict[str, Any]] = []
    for entry in iterable:
        if not isinstance(entry, dict):
            continue
        rows.append(
            {
                "key": entry.get("key"),
                "status": entry.get("status"),
                "reason": entry.get("reason"),
                "source": entry.get("source"),
                "first_seen_at": entry.get("first_seen_at"),
                "last_seen_at": entry.get("last_seen_at"),
                "seen_count": entry.get("seen_count", 0),
                "platform": entry.get("platform"),
                "job_id": entry.get("job_id"),
                "company": entry.get("company"),
                "title": entry.get("title"),
                "short_apply_url": entry.get("short_apply_url"),
            }
        )
    rows.sort(
        key=lambda row: (
            str(row.get("platform") or ""),
            str(row.get("company") or ""),
            str(row.get("title") or ""),
        )
    )
    return rows


def _question_export_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "coverage_status": item.get("coverage_status"),
        "label": item.get("label"),
        "category": item.get("category"),
        "automation_action": item.get("automation_action"),
        "sensitivity": item.get("sensitivity"),
        "required_count": item.get("required_count", 0),
        "observed_count": item.get("observed_count", 0),
        "platforms": ", ".join(_string_list(item.get("platforms"))),
        "source_files": ", ".join(_string_list(item.get("source_files"))),
        "coverage_reason": item.get("coverage_reason"),
        "answer_source": item.get("answer_source"),
        "next_action": item.get("next_action"),
    }


def _learning_task_export_row(task: dict[str, Any]) -> dict[str, Any]:
    labels = _string_list(task.get("labels"))
    return {
        "recommended_storage": task.get("recommended_storage"),
        "question": task.get("question"),
        "group_key": task.get("group_key"),
        "answer_scope": task.get("answer_scope") or _learning_task_answer_scope(
            str(task.get("group_key") or ""),
            str(task.get("recommended_storage") or ""),
        ),
        "automation_behavior": task.get("automation_behavior") or _learning_task_automation_behavior(
            str(task.get("group_key") or ""),
            str(task.get("recommended_storage") or ""),
        ),
        "platforms": ", ".join(_string_list(task.get("platforms"))),
        "labels": "\n".join(labels),
        "related_prompt_count": task.get("related_prompt_count", len(labels)),
        "observed_count": task.get("observed_count", 0),
        "required_count": task.get("required_count", 0),
        "approved": bool(task.get("approved")),
        "answer": task.get("answer", ""),
        "suggested_answer": task.get("suggested_answer", ""),
        "suggested_answer_source": task.get("suggested_answer_source", ""),
        "suggestion_confidence": task.get("suggestion_confidence", ""),
        "approval_risk": task.get("approval_risk", ""),
        "approval_required": bool(task.get("approval_required", True)),
        "approval_note": task.get("approval_note", ""),
        "persist_allowed": task.get("persist_allowed", True),
        "notes": task.get("notes", ""),
    }


def _learning_approval_bucket_export_rows(pack: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket in pack.get("buckets", []):
        if not isinstance(bucket, dict):
            continue
        rows.append(
            {
                "priority": bucket.get("priority"),
                "bucket": bucket.get("bucket"),
                "title": bucket.get("title"),
                "task_count": bucket.get("task_count", 0),
                "draft_answer_count": bucket.get("draft_answer_count", 0),
                "missing_answer_count": int(bucket.get("task_count", 0))
                - int(bucket.get("draft_answer_count", 0)),
                "related_prompt_count": bucket.get("related_prompt_count", 0),
                "observed_count": bucket.get("observed_count", 0),
                "required_count": bucket.get("required_count", 0),
                "persist_allowed_count": bucket.get("persist_allowed_count", 0),
                "platforms": ", ".join(_string_list(bucket.get("platforms"))),
                "recommended_action": bucket.get("recommended_action"),
            }
        )
    return rows


def _learning_approval_task_export_rows(pack: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task in pack.get("tasks", []):
        if not isinstance(task, dict):
            continue
        rows.append(
            {
                "priority": task.get("priority"),
                "bucket": task.get("bucket"),
                "bucket_title": task.get("bucket_title"),
                "recommended_action": task.get("recommended_action"),
                "question": task.get("question"),
                "draft_answer": task.get("draft_answer"),
                "suggested_answer_source": task.get("suggested_answer_source"),
                "suggestion_confidence": task.get("suggestion_confidence"),
                "approval_risk": task.get("approval_risk"),
                "recommended_storage": task.get("recommended_storage"),
                "answer_scope": task.get("answer_scope"),
                "persist_allowed": task.get("persist_allowed"),
                "related_prompt_count": task.get("related_prompt_count", 0),
                "observed_count": task.get("observed_count", 0),
                "required_count": task.get("required_count", 0),
                "platforms": ", ".join(_string_list(task.get("platforms"))),
                "labels": "\n".join(_string_list(task.get("labels"))),
                "approval_note": task.get("approval_note"),
                "group_key": task.get("group_key"),
            }
        )
    return rows


def _learning_approval_manual_gate_export_rows(pack: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for gate in pack.get("manual_gates", []):
        if not isinstance(gate, dict):
            continue
        rows.append(
            {
                "coverage_status": gate.get("coverage_status"),
                "label": gate.get("label"),
                "category": gate.get("category"),
                "platforms": ", ".join(_string_list(gate.get("platforms"))),
                "observed_count": gate.get("observed_count", 0),
                "required_count": gate.get("required_count", 0),
                "recommended_storage": gate.get("recommended_storage"),
                "handling": gate.get("handling"),
            }
        )
    return rows


def _manual_gate_export_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "coverage_status": item.get("coverage_status"),
        "label": item.get("label"),
        "category": item.get("category"),
        "platforms": ", ".join(_string_list(item.get("platforms"))),
        "observed_count": item.get("observed_count", 0),
        "required_count": item.get("required_count", 0),
        "recommended_storage": item.get("recommended_storage"),
        "next_action": item.get("next_action"),
    }


def _position_export_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "readiness": item.get("readiness"),
        "platform": item.get("platform"),
        "company": item.get("company"),
        "title": item.get("title"),
        "role_family": item.get("role_family"),
        "apply_url": item.get("apply_url"),
        "prompt_count": item.get("prompt_count", 0),
        "required_prompt_count": item.get("required_prompt_count", 0),
        "covered_prompt_count": item.get("covered_prompt_count", 0),
        "ready_for_autofill": item.get("ready_for_autofill"),
        "ready_for_supervised_submit": item.get("ready_for_supervised_submit"),
        "ready_for_unattended_submit": item.get("ready_for_unattended_submit"),
        "learning_blockers": "; ".join(
            str(blocker.get("label") or blocker.get("coverage_status") or "")
            for blocker in item.get("learning_blockers", [])
            if isinstance(blocker, dict)
        ),
        "manual_gates": "; ".join(
            str(gate.get("label") or gate.get("coverage_status") or "")
            for gate in item.get("manual_gates", [])
            if isinstance(gate, dict)
        ),
        "closed_reason": item.get("closed_reason"),
    }


def _write_question_export_xlsx(export: dict[str, Any], path: Path) -> None:
    sheets = [
        ("Summary", _question_export_summary_rows(export)),
        ("Source Artifacts", _table_rows(export.get("source_artifacts", []))),
        ("Synthetic Execution", _table_rows(export.get("synthetic_execution", []))),
        ("Synthetic Stops", _table_rows(export.get("synthetic_policy_stops", []))),
        ("Synthetic Roles", _table_rows(export.get("synthetic_platform_roles", []))),
        ("Fake Learning Probe", _table_rows(export.get("fake_learning_probe", []))),
        ("Fake Position Rehearsal", _table_rows(export.get("fake_position_rehearsal", []))),
        ("Problem Buckets", _table_rows(export.get("problem_buckets", []))),
        ("User Questions", _table_rows(export.get("user_questions", []))),
        ("Blocking Prompts", _table_rows(export.get("blocker_rows", []))),
        ("All Prompts", _table_rows(export.get("question_rows", []))),
        ("Positions", _table_rows(export.get("positions", []))),
        ("Platform Counts", _mapping_rows(export.get("real_platform_counts", {}), "Platform", "Observed")),
        ("Platform Shortfalls", _mapping_rows(export.get("real_platform_shortfalls", {}), "Platform", "Remaining")),
        ("Collection Targets", _table_rows(export.get("collection_targets", []))),
        ("Collection Tasks", _table_rows(export.get("collection_tasks", []))),
        ("Manual Gates", _table_rows(export.get("manual_gates", []))),
        ("Answer Memory", _table_rows(export.get("answer_memory", []))),
        ("Closed Postings", _table_rows(export.get("closed_postings", []))),
        ("Approval Buckets", _table_rows(export.get("learning_approval_buckets", []))),
        ("Approval Tasks", _table_rows(export.get("learning_approval_tasks", []))),
        ("Approval Manual Gates", _table_rows(export.get("learning_approval_manual_gates", []))),
    ]
    sheet_names = [_safe_sheet_name(name) for name, _rows in sheets]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _xlsx_content_types(len(sheets)))
        archive.writestr("_rels/.rels", _xlsx_root_rels())
        archive.writestr("docProps/core.xml", _xlsx_core_props(export.get("generated_at")))
        archive.writestr("docProps/app.xml", _xlsx_app_props(sheet_names))
        archive.writestr("xl/workbook.xml", _xlsx_workbook(sheet_names))
        archive.writestr("xl/_rels/workbook.xml.rels", _xlsx_workbook_rels(len(sheets)))
        archive.writestr("xl/styles.xml", _xlsx_styles())
        for index, (_name, rows) in enumerate(sheets, start=1):
            archive.writestr(
                f"xl/worksheets/sheet{index}.xml",
                _xlsx_sheet(rows, freeze_header=index != 1),
            )


def _question_export_summary_rows(export: dict[str, Any]) -> list[list[Any]]:
    summary = export.get("summary", {})
    rows: list[list[Any]] = [["Metric", "Value"]]
    for key, value in summary.items():
        rows.append([key, value])
    rows.extend([[], ["Coverage Status", "Count"]])
    for key, value in sorted((export.get("coverage_counts") or {}).items()):
        rows.append([key, value])
    rows.extend([[], ["Readiness", "Count"]])
    for key, value in sorted((export.get("readiness_counts") or {}).items()):
        rows.append([key, value])
    rows.extend([[], ["Policy", "Rule"]])
    for key, value in sorted((export.get("policy") or {}).items()):
        rows.append([key, value])
    return rows


def _table_rows(items: list[dict[str, Any]]) -> list[list[Any]]:
    if not items:
        return [["No rows"]]
    headers = list(items[0].keys())
    rows = [headers]
    for item in items:
        rows.append([item.get(header) for header in headers])
    return rows


def _mapping_rows(values: dict[str, Any], key_header: str, value_header: str) -> list[list[Any]]:
    rows: list[list[Any]] = [[key_header, value_header]]
    for key, value in sorted((values or {}).items()):
        rows.append([key, value])
    if len(rows) == 1:
        rows.append(["No rows", ""])
    return rows


def _xlsx_sheet(rows: list[list[Any]], freeze_header: bool = True) -> str:
    max_cols = max((len(row) for row in rows), default=1)
    max_rows = max(len(rows), 1)
    refs = f"A1:{_xlsx_col_name(max_cols)}{max_rows}"
    col_xml = "".join(
        f'<col min="{col}" max="{col}" width="{width}" customWidth="1"/>'
        for col, width in enumerate(_xlsx_col_widths(rows, max_cols), start=1)
    )
    sheet_views = (
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
        'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        if freeze_header and max_rows > 1
        else '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
    )
    row_xml = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for col_index in range(1, max_cols + 1):
            value = row[col_index - 1] if col_index <= len(row) else ""
            style = 1 if row_index == 1 else 0
            cells.append(_xlsx_cell(row_index, col_index, value, style=style))
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    auto_filter = f'<autoFilter ref="{refs}"/>' if max_rows > 1 and max_cols > 1 else ""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"{sheet_views}<cols>{col_xml}</cols><sheetData>{''.join(row_xml)}</sheetData>{auto_filter}"
        "</worksheet>"
    )


def _xlsx_cell(row: int, col: int, value: Any, style: int = 0) -> str:
    ref = f"{_xlsx_col_name(col)}{row}"
    style_attr = f' s="{style}"' if style else ""
    if value is None:
        return f'<c r="{ref}"{style_attr}/>'
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"{style_attr}><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}"{style_attr}><v>{value}</v></c>'
    text = str(value)
    preserve = ' xml:space="preserve"' if text.strip() != text or "\n" in text else ""
    return (
        f'<c r="{ref}" t="inlineStr"{style_attr}><is><t{preserve}>'
        f"{_xml_escape(text)}</t></is></c>"
    )


def _xlsx_col_widths(rows: list[list[Any]], max_cols: int) -> list[int]:
    widths: list[int] = []
    for col_index in range(max_cols):
        longest = 10
        for row in rows[:200]:
            if col_index >= len(row):
                continue
            text = str(row[col_index] or "").split("\n", 1)[0]
            longest = max(longest, len(text))
        widths.append(max(10, min(55, longest + 2)))
    return widths


def _xlsx_col_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name or "A"


def _safe_sheet_name(name: str) -> str:
    return re.sub(r"[\[\]:*?/\\]", " ", str(name))[:31] or "Sheet"


def _xlsx_content_types(sheet_count: int) -> str:
    sheets = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        f"{sheets}</Types>"
    )


def _xlsx_root_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    )


def _xlsx_workbook(sheet_names: list[str]) -> str:
    sheets = "".join(
        f'<sheet name="{_xml_escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, name in enumerate(sheet_names, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheets}</sheets></workbook>"
    )


def _xlsx_workbook_rels(sheet_count: int) -> str:
    rels = "".join(
        f'<Relationship Id="rId{index}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, sheet_count + 1)
    )
    rels += (
        f'<Relationship Id="rId{sheet_count + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{rels}</Relationships>"
    )


def _xlsx_styles() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF24435C"/><bgColor indexed="64"/></patternFill></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1">'
        '<alignment vertical="top" wrapText="1"/></xf>'
        '<xf numFmtId="0" fontId="1" fillId="1" borderId="0" xfId="0" applyFill="1" applyFont="1" applyAlignment="1">'
        '<alignment vertical="top" wrapText="1"/></xf></cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>"
    )


def _xlsx_core_props(generated_at: Any) -> str:
    timestamp = str(generated_at or datetime.now(timezone.utc).isoformat())
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<dc:title>Job Application Question Export</dc:title>'
        '<dc:creator>job_apply_agent</dc:creator>'
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{_xml_escape(timestamp)}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{_xml_escape(timestamp)}</dcterms:modified>'
        "</cp:coreProperties>"
    )


def _xlsx_app_props(sheet_names: list[str]) -> str:
    titles = "".join(f"<vt:lpstr>{_xml_escape(name)}</vt:lpstr>" for name in sheet_names)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        '<Application>job_apply_agent</Application>'
        '<TitlesOfParts><vt:vector size="{count}" baseType="lpstr">{titles}</vt:vector></TitlesOfParts>'
        '</Properties>'
    ).format(count=len(sheet_names), titles=titles)


def _question_export_css() -> str:
    return """
body { margin: 0; font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1f2933; background: #f6f8fa; }
main { max-width: 1180px; margin: 0 auto; padding: 32px 24px 56px; }
h1 { margin: 0 0 4px; font-size: 28px; }
h2 { margin: 28px 0 12px; font-size: 18px; }
.muted { color: #5f6c7b; margin-top: 0; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 20px 0; }
.kpi { background: white; border: 1px solid #d9e2ec; padding: 14px; border-radius: 8px; }
.kpi .label { color: #52606d; font-size: 12px; text-transform: uppercase; letter-spacing: .02em; }
.kpi .value { display: block; font-size: 24px; font-weight: 700; margin-top: 4px; }
section { background: white; border: 1px solid #d9e2ec; border-radius: 8px; padding: 16px; margin-top: 18px; overflow-x: auto; }
table { border-collapse: collapse; width: 100%; min-width: 720px; }
th, td { border-bottom: 1px solid #e4e7eb; padding: 8px 10px; text-align: left; vertical-align: top; }
th { background: #24435c; color: white; position: sticky; top: 0; }
tr:nth-child(even) td { background: #f8fafc; }
td { white-space: pre-wrap; }
""".strip()


def _html_kpis(items: list[tuple[str, Any]]) -> str:
    cards = []
    for label, value in items:
        cards.append(
            '<div class="kpi"><span class="label">{label}</span><span class="value">{value}</span></div>'.format(
                label=_html_escape(label),
                value=_html_escape(value),
            )
        )
    return '<div class="kpis">' + "".join(cards) + "</div>"


def _html_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        rows = [["None"] + [""] * (len(headers) - 1)]
    head = "".join(f"<th>{_html_escape(header)}</th>" for header in headers)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{_html_escape(row[index] if index < len(row) else '')}</td>" for index in range(len(headers)))
        body_rows.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def _html_key_value_table(mapping: dict[str, Any]) -> str:
    return _html_table(["Key", "Value"], [[key, value] for key, value in sorted(mapping.items())])


def _yes_no(value: Any) -> str:
    return "yes" if bool(value) else "no"


def _html_escape(value: Any) -> str:
    return html.escape(_clean_xml_text(value))


def _xml_escape(value: Any) -> str:
    return html.escape(_clean_xml_text(value), quote=True)


def _clean_xml_text(value: Any) -> str:
    text = "" if value is None else str(value)
    return "".join(
        char
        for char in text
        if char in {"\t", "\n", "\r"} or ord(char) >= 0x20
    )


def _humanize_field_identifier(value: str) -> str:
    text = str(value or "").strip()
    if len(text) > 80 or re.search(r"[\[\]/{}]|_{2,}", text):
        return ""
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"[-_.:]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _looks_like_application_prompt(text: str) -> bool:
    normalized = _normalize(text)
    if not normalized:
        return False
    low_signal = {
        "apply",
        "clear text",
        "close",
        "continue with google",
        "dismiss",
        "forgot password",
        "jobs",
        "language",
        "learning",
        "more searches",
        "open menu",
        "people",
        "primary",
        "search",
        "set alert",
        "show",
        "show fewer jobs like this",
        "show fewer similar searches",
        "show less",
        "show more",
        "show more jobs like this",
        "show more similar searches",
        "sign in",
        "sign in with email",
    }
    if normalized in low_signal or _is_low_signal_application_prompt(normalized):
        return False
    meta_keys = {
        "bingbot",
        "description",
        "locale",
        "pagekey",
        "robots",
        "theme color",
        "twitter card",
        "twitter description",
        "twitter image",
        "twitter site",
        "twitter title",
        "viewport",
    }
    if normalized.startswith("public jobs ") or normalized in meta_keys:
        return False
    if len(text) > 160 and "?" not in text:
        return False
    language_options = {
        "arabic",
        "bangla",
        "chinese simplified",
        "chinese traditional",
        "czech",
        "danish",
        "dutch",
        "english english",
        "finnish",
        "french",
        "german",
        "greek",
        "hindi",
        "hungarian",
        "indonesian",
        "italian",
        "japanese",
        "korean",
        "malay",
        "marathi",
        "norwegian",
        "persian",
        "polish",
        "portuguese",
        "romanian",
        "russian",
        "spanish",
        "swedish",
        "tagalog",
        "thai",
        "turkish",
        "ukrainian",
        "vietnamese",
    }
    if normalized in language_options or normalized.endswith(" selected"):
        return False
    if len(text) >= 8:
        non_ascii = sum(1 for char in text if ord(char) > 127)
        if non_ascii / max(len(text), 1) > 0.25:
            return False
    return True


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
