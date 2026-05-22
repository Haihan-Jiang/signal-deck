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

For a standalone preflight report before sending alerts or opening tabs:

```bash
python3 -m job_apply_agent closed-preflight \
  --submissions job_apply_agent/outbox/daily_agent_submissions.jsonl \
  --live-check-limit 25
```

This writes:

```text
job_apply_agent/outbox/closed_posting_preflight_latest.json
job_apply_agent/outbox/closed_posting_preflight_latest.md
```

The preflight splits candidates into `open_live_checked`,
`closed_registry` / `closed_live_text`, and uncertain states such as
`check_error` or `not_checked_limit`. Only `open_live_checked` rows are treated
as eligible for browser opening in a stricter supervised run.

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

Turn that learning queue into a fill-in template:

```bash
python3 -m job_apply_agent learning-template \
  --readiness-json job_apply_agent/outbox/automation_readiness_latest.json
```

After editing the JSON so only approved non-sensitive tasks have
`approved: true` and an `answer`, apply those approved answers locally:

```bash
python3 -m job_apply_agent apply-learning \
  --tasks job_apply_agent/outbox/learning_tasks_latest.json \
  --profile job_apply_agent/outbox/alan_jiang_profile.json \
  --memory job_apply_agent/outbox/answer_memory.json
```

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

Before wiring any browser executor, turn a fill plan into an apply-run audit:

```bash
python3 -m job_apply_agent apply-audit \
  --plan job_apply_agent/outbox/ramp_fill_plan_latest.json
```

This writes:

```text
job_apply_agent/outbox/apply_run_audit_latest.json
job_apply_agent/outbox/apply_run_audit_latest.md
```

The audit says exactly which fields may be automated, which steps stop the run,
whether the page should be skipped as closed, and confirms that final submit is
not allowed without explicit approval.

To hand a reviewed plan to a browser executor, generate a guarded browser action
manifest:

```bash
python3 -m job_apply_agent browser-actions \
  --plan job_apply_agent/outbox/ramp_fill_plan_latest.json
```

This writes:

```text
job_apply_agent/outbox/browser_action_manifest_latest.json
job_apply_agent/outbox/browser_action_manifest_latest.md
```

The manifest contains selector candidates and value sources for ready
fill/upload/generated-text actions only. Closed postings produce zero browser
actions, and CAPTCHA, sensitive questions, manual review, and final submit stay
as stop actions.

To turn a manifest plus a captured/synthetic form snapshot into a local DOM
harness:

```bash
python3 -m job_apply_agent dom-harness \
  --manifest job_apply_agent/outbox/ramp_browser_actions_latest.json \
  --snapshot job_apply_agent/outbox/ramp_application_form_snapshot.json
```

This writes:

```text
job_apply_agent/outbox/browser_dom_harness_latest.html
job_apply_agent/outbox/browser_dom_runner_latest.js
job_apply_agent/outbox/browser_dom_execution_plan_latest.json
job_apply_agent/outbox/browser_dom_execution_plan_latest.md
```

The DOM harness is safety-gated for local targets only (`file://`,
`localhost`, or loopback). The runner script fills local HTML controls and
records selector misses, but it does not click submit and records
`actualSubmitCount: 0`.

To collect the remaining user-confirmation questions and browser stop points
into one pre-submit checklist:

```bash
python3 -m job_apply_agent pre-submit-review \
  --manifest job_apply_agent/outbox/ramp_browser_actions_latest.json \
  --manifest job_apply_agent/outbox/doordash_browser_actions_latest.json
```

This writes:

```text
job_apply_agent/outbox/pre_submit_review_latest.json
job_apply_agent/outbox/pre_submit_review_latest.md
```

The review combines browser manifests, answer gaps, readiness, learning tasks,
and synthetic execution evidence. It is the handoff document for deciding which
answers can be learned once, which protected-class/security/final-submit gates
must remain supervised, and how much of the current queue can be autofilled.

For end-to-end safety testing with fake candidate data, use the synthetic
offline harness. It creates fake LinkedIn/Ashby/Greenhouse/Lever-style forms,
checks closed-posting text, builds fill plans, and summarizes blockers without
touching real employer systems:

```bash
python3 -m job_apply_agent synthetic-run --count 100
```

This writes:

```text
job_apply_agent/outbox/synthetic_100_run_latest.json
job_apply_agent/outbox/synthetic_100_run_latest.md
```

The synthetic harness is intentionally not a real submission tool. It exists to
prove field mapping and summarize the gates that still require supervised
handling before any permitted real application flow.

To go one step closer to execution, run the synthetic forms through the offline
apply state machine:

```bash
python3 -m job_apply_agent synthetic-exec --count 100
```

To satisfy a 100-position target for each synthetic platform:

```bash
python3 -m job_apply_agent synthetic-exec --per-platform-target 100
```

This writes:

```text
job_apply_agent/outbox/synthetic_apply_execution_latest.json
job_apply_agent/outbox/synthetic_apply_execution_latest.md
```

It simulates each ready fill/upload/answer step, records the first policy stop,
skips closed postings, and still records `actual_submit_count: 0`.

To verify the browser-action layer itself, execute generated manifests against
local fake forms:

```bash
python3 -m job_apply_agent synthetic-browser-exec --per-platform-target 100
```

This writes:

```text
job_apply_agent/outbox/synthetic_browser_action_execution_latest.json
job_apply_agent/outbox/synthetic_browser_action_execution_latest.md
```

This checks that selector candidates in the manifest resolve to the intended
local form fields across LinkedIn/Ashby/Greenhouse/Lever-style synthetic forms.
It still never opens real employer pages and still records `actual_submit_count:
0`.

Generate a platform playbook from the real observed artifacts plus the synthetic
run:

```bash
python3 -m job_apply_agent playbook
```

This writes:

```text
job_apply_agent/outbox/application_playbook_latest.json
job_apply_agent/outbox/application_playbook_latest.md
```

The playbook is the operational checklist for each platform: common prompts,
field categories, answer sources, learning tasks, closed-posting handling,
CAPTCHA/security stops, protected-class handling, and final-submit boundaries.

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
