# One-Person Company Agent Design

This design treats one human owner as the CEO and a small set of specialist
agents as the operating team. The default implementation is local and
deterministic, so it can be tested without API keys, model access, or paid
services.

## Operating Model

1. Intake every task through the CEO / Chief of Staff.
2. Split work into capability units: planning, research, implementation,
   verification, risk control, operations, and reporting.
3. Assign each unit to one owner role, while allowing independent phases to run
   in parallel.
4. Require the QA / Risk Controller to inspect tests, secrets, paid-service
   usage, production changes, money movement, and external submissions.
5. End with the Operator / Reporter producing a concise status, evidence, and
   next action.

## When Multi-Agent Helps

Multi-agent routing is most useful when a task needs several capabilities at
once, such as research plus implementation plus verification. It creates an
independent QA path and reduces critical-path time because research/risk work
and build/ops work can overlap where dependencies allow.

## When Single-Agent Is Enough

Use a single agent for tiny, low-risk tasks with one obvious action, such as a
one-line command, simple text rewrite, or narrow code lookup. The benchmark does
not claim multi-agent routing is universally better.

## Verification

Run:

```bash
python3 -m unittest tests.test_daily_ops_agent
```

The test suite compares the multi-agent company against a deterministic
single-generalist baseline across job automation, paper-trading readiness,
prototype building, and strategy-research gate tasks.

The benchmark reports four weighted metrics:

- Coverage: required capability units completed.
- Latency: deterministic critical-path cost, not noisy wall-clock time.
- Risk: planted risk classes caught by an independent QA/risk path.
- Repeatability: deterministic reruns produce stable scores.
