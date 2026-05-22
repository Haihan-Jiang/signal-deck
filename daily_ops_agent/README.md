# Daily Ops Agent

`daily_ops_agent` is a zero-cost, deterministic scaffold for a general
"one-person company" made of specialist agents. It does not call an LLM API.
Use it to route a task into roles, produce a repeatable work plan, and benchmark
the multi-agent design against a single-generalist baseline.

## Roles

- `CEO / Chief of Staff`: frames the goal, success evidence, and stop rule.
- `Research Analyst`: gathers current evidence and separates facts from assumptions.
- `Builder / Automation Engineer`: creates scripts, configs, prototypes, and local automations.
- `QA / Risk Controller`: runs tests, catches failure modes, and protects approval gates.
- `Operator / Reporter`: packages the runbook, monitoring surface, and final handoff.

## Run

```bash
python3 -m daily_ops_agent plan \
  --task "Build a no-cost local prototype, run tests, and document usage." \
  --compare-single
```

```bash
python3 -m daily_ops_agent benchmark
```

The benchmark scores coverage, deterministic critical-path latency, planted
risk catches, and repeatability. It proves this design is more effective than
the single-agent baseline for the included task shapes and scoring rules. It
does not prove that every possible task benefits from multiple agents.
