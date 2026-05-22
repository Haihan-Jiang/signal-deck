# Job Apply Agent Prototype

This is a personal dry-run prototype for automated job discovery and application drafting.

It does not log in to real platforms, bypass anti-bot checks, solve CAPTCHAs, or submit real applications. Real platform support should be added only through allowed APIs or browser adapters with a human review gate before submission.

## What It Does

- Loads a placeholder candidate profile.
- Loads mock jobs from a local fixture.
- Scores jobs against target titles, locations, keywords, and blocklisted terms.
- Skips closed postings when page text says things like `No longer accepting applications`.
- Keeps a local closed-job registry so manually confirmed closed pages are skipped in future runs.
- Generates natural application answers from verified profile facts.
- Writes simulated submissions to a JSONL outbox with `dry_run: true`.

## Run

From the repository root:

```bash
python3 -m job_apply_agent score
python3 -m job_apply_agent run --limit 2
```

The default dry-run outbox is:

```text
job_apply_agent/outbox/dry_run_submissions.jsonl
```

To inspect full simulated payloads:

```bash
python3 -m job_apply_agent run --limit 2 --json
```

## Telegram Notification

The agent can notify the existing Telegram bot when application drafts are ready.
It reads credentials from environment variables or from the same local env file
used by the Signal Deck bot:

```text
~/.signal-deck/runtime/telegram.env
```

Supported variable names:

```bash
export SIGNAL_DECK_TELEGRAM_BOT_TOKEN="<YOUR_TOKEN>"
export SIGNAL_DECK_TELEGRAM_CHAT_ID="<YOUR_CHAT_ID>"
export SIGNAL_DECK_TELEGRAM_CHAT_IDS="<PERSONAL_OR_GROUP_IDS_COMMA_SEPARATED>"
```

Job-specific names are also supported:

```bash
export JOB_APPLY_TELEGRAM_BOT_TOKEN="<YOUR_TOKEN>"
export JOB_APPLY_TELEGRAM_CHAT_ID="<YOUR_CHAT_ID>"
export JOB_APPLY_TELEGRAM_CHAT_IDS="<PERSONAL_OR_GROUP_IDS_COMMA_SEPARATED>"
```

Send a notification for the current run:

```bash
python3 -m job_apply_agent run \
  --profile job_apply_agent/outbox/alan_jiang_profile.json \
  --jobs job_apply_agent/outbox/linkedin_visible_jobs.json \
  --memory job_apply_agent/outbox/answer_memory.json \
  --limit 5 \
  --notify-telegram \
  --open-browser
```

Preview the Telegram message without sending:

```bash
python3 -m job_apply_agent run --limit 2 --notify-telegram --telegram-dry-run
```

Telegram notifications shorten known apply URLs before sending. LinkedIn job
URLs are reduced to `https://www.linkedin.com/jobs/view/<job_id>/`, and common
ATS links have tracking parameters removed.

Record a closed page after manual/live verification:

```bash
python3 -m job_apply_agent close \
  --url https://www.linkedin.com/jobs/view/4415508499/ \
  --company Tesla \
  --title "Sr. Site Reliability Engineer, Vehicle Software, Build Infrastructure" \
  --source live_page_check
```

The default closed-job registry is:

```text
job_apply_agent/outbox/closed_jobs.json
```

Open the top five links from an existing outbox file:

```bash
python3 -m job_apply_agent notify \
  --submissions job_apply_agent/outbox/linkedin_next_candidates_dry_run.jsonl \
  --limit 5 \
  --live-check \
  --open-browser
```

When `--open-browser` is used, the agent also appends a non-sensitive review
record to:

```text
job_apply_agent/outbox/browser_review_queue.jsonl
```

Each row records the job, score, short apply URL, open timestamp, current status,
and next action for human review. It intentionally omits applicant contact
details, full answer text, and long tracking URLs.

Use `--live-check` before Telegram/open-browser runs to fetch the current apply
pages and automatically record closed postings when the live page says
`No longer accepting applications`. Closed jobs are saved to
`job_apply_agent/outbox/closed_jobs.json` and skipped in future runs.

## Application Question Research

Summarize the fields and questions already observed across LinkedIn, Ashby,
Greenhouse, and other outbox artifacts:

```bash
python3 -m job_apply_agent research \
  --outbox-dir job_apply_agent/outbox \
  --position-target 100
```

This writes:

```text
job_apply_agent/outbox/application_research_latest.json
job_apply_agent/outbox/application_research_latest.md
```

The report groups prompts into automation actions:

- `auto_fill_from_profile` for identity, resume, profile links, and similar fields.
- `auto_answer_from_memory` for approved standard answers such as authorization, sponsorship, relocation, start date, compensation, and years of experience.
- `generate_custom_material` for role-specific free text, cover letters, and resume customization.
- `human_review_required` for employer-specific, policy, consent, and unclear prompts.
- `do_not_store_sensitive` for protected-class self-identification.
- `manual_security_step` for CAPTCHA or bot checks.

It also tracks coverage by both website and role type so the collection target
can move toward 100 observed positions for each platform/role-family pair.

After generating the research baseline, check which prompts are already covered
by the profile or approved answer memory:

```bash
python3 -m job_apply_agent gaps \
  --research-json job_apply_agent/outbox/application_research_latest.json \
  --profile job_apply_agent/outbox/alan_jiang_profile.json \
  --memory job_apply_agent/outbox/answer_memory.json
```

This writes:

```text
job_apply_agent/outbox/answer_gaps_latest.json
job_apply_agent/outbox/answer_gaps_latest.md
```

The gap report does not print stored answer values. It reports whether each
observed prompt is covered by the profile, approved answer memory, generated
material, or whether it still requires a user confirmation, protected-class
self-ID handling, CAPTCHA/security step, resume path, or final submit approval.

Finally, generate a per-position automation readiness report:

```bash
python3 -m job_apply_agent readiness \
  --research-json job_apply_agent/outbox/application_research_latest.json \
  --gaps-json job_apply_agent/outbox/answer_gaps_latest.json
```

This writes:

```text
job_apply_agent/outbox/automation_readiness_latest.json
job_apply_agent/outbox/automation_readiness_latest.md
```

The readiness report marks each observed position as `autofill_ready`,
`needs_learning`, or `needs_research`, and condenses repeated blockers into a
minimal learning task list for answers/materials that should be confirmed once.

For a captured Ashby or Greenhouse form snapshot, generate an offline fill plan:

```bash
python3 -m job_apply_agent fill-plan \
  --snapshot job_apply_agent/outbox/ramp_application_form_snapshot.json \
  --profile job_apply_agent/outbox/alan_jiang_profile.json \
  --memory job_apply_agent/outbox/answer_memory.json
```

By default, the plan records value sources and blocking gates, not the actual
profile values. Use this before browser execution to verify each field will be
filled from profile data, answer memory, generated material, or stopped for
human review/security/final-submit confirmation.

## Learning From Approved Applications

When you manually submit an application, save the exact questions and answers as JSON:

```json
{
  "Are you authorized to work in the United States?": "I am authorized to work in the United States.",
  "How many years of Kubernetes operations experience do you have?": "3 years"
}
```

Record those approved answers:

```bash
python3 -m job_apply_agent learn \
  --job job_apply_agent/outbox/densityai_job.json \
  --answers job_apply_agent/outbox/densityai_answers.json \
  --memory job_apply_agent/outbox/answer_memory.json
```

Use the answer memory in future runs:

```bash
python3 -m job_apply_agent run \
  --profile job_apply_agent/outbox/alan_jiang_profile.json \
  --jobs job_apply_agent/outbox/linkedin_visible_jobs.json \
  --memory job_apply_agent/outbox/answer_memory.json \
  --limit 3
```

The automation policy marks a draft as:

- `human_review_required` when facts are missing or the job is below threshold.
- `supervised_review` when it is safe to autofill but still requires final human confirmation.
- `unattended_submit` only when explicitly enabled and no missing or sensitive facts are present.

## Replace Placeholders

Edit `sample_profile.json` or provide your own file:

```bash
python3 -m job_apply_agent run --profile /path/to/profile.json --jobs /path/to/jobs.json
```

Keep the profile factual. The answer generator is designed to reuse known facts and surface missing facts instead of inventing credentials.

## Next Production Steps

1. Add a real job-source adapter for a platform that permits automated access.
2. Store credentials outside the repo, for example in a local env file or macOS Keychain.
3. Add a review queue where you approve each drafted application.
4. Add browser automation only for permitted flows and stop when login, CAPTCHA, identity checks, or unclear consent is encountered.
