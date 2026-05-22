from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


CAPABILITY_LABELS: Dict[str, str] = {
    "planning": "goal framing and work breakdown",
    "research": "evidence gathering and source review",
    "implementation": "building scripts, configs, and artifacts",
    "verification": "tests, evals, and regression checks",
    "risk_control": "safety, cost, secrets, and approval gates",
    "operations": "scheduling, monitoring, and runbooks",
    "reporting": "concise decision-ready handoff",
}


PHASE_ORDER = ["plan", "discover", "build", "verify", "deliver"]


@dataclass(frozen=True)
class AgentRole:
    id: str
    title: str
    charter: str
    capabilities: Tuple[str, ...]
    default_minutes: int
    phase_bias: str


@dataclass(frozen=True)
class WorkUnit:
    id: str
    label: str
    capability: str
    minutes: int
    phase: str
    risk_tags: Tuple[str, ...] = ()
    depends_on: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Assignment:
    work_id: str
    role_id: str
    role_title: str
    capability: str
    phase: str
    minutes: int
    notes: str


@dataclass(frozen=True)
class CompanyPlan:
    mode: str
    task: str
    roles: Tuple[AgentRole, ...]
    work_units: Tuple[WorkUnit, ...]
    assignments: Tuple[Assignment, ...]
    covered_capabilities: Tuple[str, ...]
    gaps: Tuple[str, ...]
    independent_risk_checks: int
    critical_path_minutes: int
    total_person_minutes: int
    handoff_count: int

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=True)


@dataclass(frozen=True)
class ScoreCard:
    mode: str
    coverage_score: float
    latency_score: float
    risk_score: float
    repeatability_score: float
    handoff_penalty: float
    overall: float

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class BenchmarkCase:
    id: str
    task: str
    required_capabilities: Tuple[str, ...]
    expected_risk_tags: Tuple[str, ...] = ()


def default_company_roles() -> Tuple[AgentRole, ...]:
    return (
        AgentRole(
            id="ceo",
            title="CEO / Chief of Staff",
            charter="Clarify the objective, define success evidence, sequence the work, and decide when to stop.",
            capabilities=("planning", "reporting"),
            default_minutes=8,
            phase_bias="plan",
        ),
        AgentRole(
            id="research",
            title="Research Analyst",
            charter="Collect current evidence, inspect local state, and separate facts from assumptions.",
            capabilities=("research", "planning"),
            default_minutes=22,
            phase_bias="discover",
        ),
        AgentRole(
            id="builder",
            title="Builder / Automation Engineer",
            charter="Turn the plan into scripts, configs, prototypes, or repo changes.",
            capabilities=("implementation", "operations"),
            default_minutes=30,
            phase_bias="build",
        ),
        AgentRole(
            id="qa",
            title="QA / Risk Controller",
            charter="Run tests, find failure modes, protect credentials, and enforce approval gates.",
            capabilities=("verification", "risk_control"),
            default_minutes=18,
            phase_bias="verify",
        ),
        AgentRole(
            id="ops",
            title="Operator / Reporter",
            charter="Package the result into a runbook, status report, or next scheduled action.",
            capabilities=("operations", "reporting"),
            default_minutes=14,
            phase_bias="deliver",
        ),
    )


def benchmark_cases() -> Tuple[BenchmarkCase, ...]:
    return (
        BenchmarkCase(
            id="job_draft_pipeline",
            task=(
                "Refresh job candidates, live-check closed postings, draft application material, "
                "write the outbox, and prepare a human-review report."
            ),
            required_capabilities=(
                "planning",
                "research",
                "implementation",
                "verification",
                "risk_control",
                "operations",
                "reporting",
            ),
            expected_risk_tags=("external_submit", "personal_data"),
        ),
        BenchmarkCase(
            id="paper_trading_readiness",
            task=(
                "Audit the Alpaca paper runner before market open, verify latest local data, "
                "classify risk, and report whether production behavior should change."
            ),
            required_capabilities=(
                "planning",
                "research",
                "verification",
                "risk_control",
                "reporting",
            ),
            expected_risk_tags=("money", "production_change", "secret"),
        ),
        BenchmarkCase(
            id="prototype_with_tests",
            task=(
                "Build a no-cost local prototype, add a CLI, run tests, and document how to use it."
            ),
            required_capabilities=(
                "planning",
                "implementation",
                "verification",
                "risk_control",
                "reporting",
            ),
            expected_risk_tags=("cost",),
        ),
        BenchmarkCase(
            id="strategy_research_gate",
            task=(
                "Compare strategy ideas, collect evidence, reject weak data, run a validation gate, "
                "and summarize the deploy/no-deploy decision."
            ),
            required_capabilities=(
                "planning",
                "research",
                "verification",
                "risk_control",
                "reporting",
            ),
            expected_risk_tags=("overfit", "production_change"),
        ),
    )


def plan_one_person_company(task: str) -> CompanyPlan:
    roles = default_company_roles()
    work_units = _derive_work_units(task)
    assignments = tuple(_assign_work(unit, roles) for unit in work_units)
    covered = _covered_capabilities(work_units, assignments)
    gaps = tuple(unit.capability for unit in work_units if unit.capability not in covered)
    return CompanyPlan(
        mode="one_person_company",
        task=task,
        roles=roles,
        work_units=tuple(work_units),
        assignments=assignments,
        covered_capabilities=tuple(sorted(covered)),
        gaps=tuple(sorted(set(gaps))),
        independent_risk_checks=_risk_check_count(work_units, assignments, independent=True),
        critical_path_minutes=_parallel_critical_path(assignments),
        total_person_minutes=sum(assignment.minutes for assignment in assignments),
        handoff_count=max(0, len({assignment.role_id for assignment in assignments}) - 1),
    )


def plan_single_generalist(task: str) -> CompanyPlan:
    role = AgentRole(
        id="solo",
        title="Single Generalist Agent",
        charter="Handle the full task sequentially without independent specialist review.",
        capabilities=tuple(CAPABILITY_LABELS.keys()),
        default_minutes=28,
        phase_bias="plan",
    )
    work_units = _derive_work_units(task)
    overload = max(0, len(work_units) - 4)
    assignments = []
    for unit in work_units:
        minutes = int(math.ceil(unit.minutes * 1.15))
        if overload:
            minutes += 2
        assignments.append(
            Assignment(
                work_id=unit.id,
                role_id=role.id,
                role_title=role.title,
                capability=unit.capability,
                phase=unit.phase,
                minutes=minutes,
                notes="Sequential generalist pass; no independent handoff.",
            )
        )
    covered = _covered_capabilities(work_units, assignments)
    return CompanyPlan(
        mode="single_generalist",
        task=task,
        roles=(role,),
        work_units=tuple(work_units),
        assignments=tuple(assignments),
        covered_capabilities=tuple(sorted(covered)),
        gaps=(),
        independent_risk_checks=_risk_check_count(work_units, tuple(assignments), independent=False),
        critical_path_minutes=sum(assignment.minutes for assignment in assignments),
        total_person_minutes=sum(assignment.minutes for assignment in assignments),
        handoff_count=0,
    )


def score_plan(plan: CompanyPlan) -> ScoreCard:
    required = {unit.capability for unit in plan.work_units}
    coverage_score = len(set(plan.covered_capabilities) & required) / max(1, len(required))
    latency_score = max(0.0, 1.0 - (plan.critical_path_minutes / 170.0))
    risk_tags = {tag for unit in plan.work_units for tag in unit.risk_tags}
    if risk_tags:
        risk_score = min(1.0, plan.independent_risk_checks / max(1.0, len(risk_tags) + 2.0))
    else:
        risk_score = 1.0
    repeatability_score = 1.0
    handoff_penalty = plan.handoff_count * 0.01
    overall = round(
        (0.40 * coverage_score)
        + (0.20 * latency_score)
        + (0.25 * risk_score)
        + (0.15 * repeatability_score)
        - handoff_penalty,
        4,
    )
    return ScoreCard(
        mode=plan.mode,
        coverage_score=round(coverage_score, 4),
        latency_score=round(latency_score, 4),
        risk_score=round(risk_score, 4),
        repeatability_score=repeatability_score,
        handoff_penalty=round(handoff_penalty, 4),
        overall=overall,
    )


def compare_against_single_agent(task: str) -> Dict[str, object]:
    solo = plan_single_generalist(task)
    company = plan_one_person_company(task)
    solo_score = score_plan(solo)
    company_score = score_plan(company)
    return {
        "task": task,
        "single_generalist": solo.to_dict(),
        "one_person_company": company.to_dict(),
        "scores": {
            "single_generalist": solo_score.to_dict(),
            "one_person_company": company_score.to_dict(),
            "delta": round(company_score.overall - solo_score.overall, 2),
        },
        "faster_by_minutes": solo.critical_path_minutes - company.critical_path_minutes,
        "more_risk_checks": company.independent_risk_checks - solo.independent_risk_checks,
    }


def run_benchmark(cases: Optional[Sequence[BenchmarkCase]] = None) -> Dict[str, object]:
    selected_cases = tuple(cases or benchmark_cases())
    case_results = []
    for case in selected_cases:
        result = compare_against_single_agent(case.task)
        result["case_id"] = case.id
        result["required_capabilities"] = case.required_capabilities
        result["expected_risk_tags"] = case.expected_risk_tags
        case_results.append(result)
    deltas = [float(result["scores"]["delta"]) for result in case_results]
    faster = [int(result["faster_by_minutes"]) for result in case_results]
    risk_deltas = [int(result["more_risk_checks"]) for result in case_results]
    return {
        "case_count": len(case_results),
        "metric_weights": {
            "coverage_score": 0.40,
            "latency_score": 0.20,
            "risk_score": 0.25,
            "repeatability_score": 0.15,
        },
        "all_cases_multi_agent_more_effective": all(delta > 0 for delta in deltas),
        "all_cases_multi_agent_faster": all(minutes > 0 for minutes in faster),
        "all_cases_more_independent_risk_checks": all(delta >= 0 for delta in risk_deltas),
        "average_effectiveness_delta": round(sum(deltas) / max(1, len(deltas)), 2),
        "total_minutes_saved": sum(faster),
        "cases": case_results,
        "proof_scope": (
            "This is deterministic benchmark evidence for these task shapes and scoring rules; "
            "it is not a universal proof that every possible task benefits from multiple agents."
        ),
    }


def render_plan(plan: CompanyPlan) -> str:
    lines = [
        f"Mode: {plan.mode}",
        f"Critical path: {plan.critical_path_minutes} min",
        f"Total person-minutes: {plan.total_person_minutes} min",
        f"Independent risk checks: {plan.independent_risk_checks}",
        "",
        "Assignments:",
    ]
    for assignment in plan.assignments:
        label = next(unit.label for unit in plan.work_units if unit.id == assignment.work_id)
        lines.append(
            f"- {assignment.role_title}: {label} "
            f"({assignment.capability}, {assignment.phase}, {assignment.minutes} min)"
        )
    if plan.gaps:
        lines.extend(["", "Gaps: " + ", ".join(plan.gaps)])
    return "\n".join(lines)


def render_benchmark(summary: Dict[str, object]) -> str:
    lines = [
        "One-person company benchmark",
        f"Cases: {summary['case_count']}",
        f"All cases better than single-agent baseline: {summary['all_cases_multi_agent_more_effective']}",
        f"Average effectiveness delta: {summary['average_effectiveness_delta']}",
        f"Total critical-path minutes saved: {summary['total_minutes_saved']}",
        "",
        "Case results:",
    ]
    for result in summary["cases"]:
        scores = result["scores"]
        lines.append(
            f"- {result['case_id']}: delta={scores['delta']}, "
            f"minutes_saved={result['faster_by_minutes']}, "
            f"risk_check_delta={result['more_risk_checks']}"
        )
    lines.extend(["", str(summary["proof_scope"])])
    return "\n".join(lines)


def _derive_work_units(task: str) -> List[WorkUnit]:
    capabilities = _detect_capabilities(task)
    units = [
        WorkUnit(
            id="intake",
            label="Frame the objective, constraints, success evidence, and stop rule",
            capability="planning",
            minutes=8,
            phase="plan",
        )
    ]
    if "research" in capabilities:
        units.append(
            WorkUnit(
                id="research",
                label="Gather evidence and inspect current state before deciding",
                capability="research",
                minutes=24,
                phase="discover",
            )
        )
    if "risk_control" in capabilities:
        units.append(
            WorkUnit(
                id="risk",
                label="Identify safety, cost, secret, approval, or production risks",
                capability="risk_control",
                minutes=16,
                phase="discover",
                risk_tags=_detect_risk_tags(task),
            )
        )
    if "implementation" in capabilities:
        units.append(
            WorkUnit(
                id="build",
                label="Build the artifact, script, configuration, or local automation",
                capability="implementation",
                minutes=32,
                phase="build",
                depends_on=("intake",),
            )
        )
    if "operations" in capabilities:
        units.append(
            WorkUnit(
                id="operate",
                label="Prepare the runbook, schedule, monitor, or repeatable command",
                capability="operations",
                minutes=18,
                phase="build",
                depends_on=("intake",),
            )
        )
    if "verification" in capabilities:
        units.append(
            WorkUnit(
                id="verify",
                label="Run tests, evals, or audits against the real execution path",
                capability="verification",
                minutes=20,
                phase="verify",
                depends_on=("build",),
            )
        )
    units.append(
        WorkUnit(
            id="report",
            label="Deliver concise status, evidence, and next actions",
            capability="reporting",
            minutes=10,
            phase="deliver",
            depends_on=("verify",) if "verification" in capabilities else ("intake",),
        )
    )
    return units


def _detect_capabilities(task: str) -> Tuple[str, ...]:
    text = task.lower()
    capabilities = {"planning", "reporting"}
    keyword_map = {
        "research": (
            "research",
            "source",
            "evidence",
            "compare",
            "latest",
            "audit",
            "inspect",
            "study",
            "data",
            "研究",
            "比较",
            "证据",
            "最新",
        ),
        "implementation": (
            "build",
            "create",
            "write",
            "setup",
            "set up",
            "script",
            "code",
            "prototype",
            "automation",
            "cli",
            "agent",
            "implement",
            "设置",
            "搭建",
            "写",
            "代码",
            "自动化",
        ),
        "verification": (
            "test",
            "verify",
            "validate",
            "prove",
            "check",
            "eval",
            "benchmark",
            "测试",
            "验证",
            "证明",
            "跑",
        ),
        "risk_control": (
            "submit",
            "production",
            "deploy",
            "trade",
            "money",
            "cost",
            "no-cost",
            "paid",
            "secret",
            "credential",
            "approval",
            "risk",
            "safe",
            "safely",
            "safety",
            "live",
            "上线",
            "交易",
            "提交",
            "付费",
            "密钥",
            "风险",
            "安全",
        ),
        "operations": (
            "schedule",
            "monitor",
            "runbook",
            "recurring",
            "daily",
            "daemon",
            "launchd",
            "cron",
            "telegram",
            "通知",
            "定时",
            "监控",
            "每天",
        ),
    }
    for capability, keywords in keyword_map.items():
        if any(keyword in text for keyword in keywords):
            capabilities.add(capability)
    return tuple(sorted(capabilities))


def _detect_risk_tags(task: str) -> Tuple[str, ...]:
    text = task.lower()
    tags = []
    risk_keywords = (
        ("external_submit", ("submit", "application", "apply", "提交", "投递")),
        ("production_change", ("production", "deploy", "上线", "service", "systemd")),
        ("money", ("trade", "money", "portfolio", "alpaca", "交易", "资金")),
        ("secret", ("secret", "credential", "token", "key", "密钥", "凭证")),
        ("cost", ("paid", "api", "llm", "cost", "openai", "付费", "费用")),
        ("personal_data", ("profile", "resume", "personal", "job", "简历", "个人")),
        ("overfit", ("strategy", "model", "backtest", "optimizer", "策略", "回测")),
    )
    for tag, keywords in risk_keywords:
        if any(keyword in text for keyword in keywords):
            tags.append(tag)
    return tuple(tags or ("general_quality",))


def _assign_work(unit: WorkUnit, roles: Sequence[AgentRole]) -> Assignment:
    candidates = [
        role
        for role in roles
        if unit.capability in role.capabilities or role.phase_bias == unit.phase
    ]
    if not candidates:
        raise ValueError(f"No agent can handle capability: {unit.capability}")
    role = sorted(
        candidates,
        key=lambda candidate: (
            unit.capability not in candidate.capabilities,
            candidate.phase_bias != unit.phase,
            candidate.default_minutes,
        ),
    )[0]
    minutes = max(4, int(round((unit.minutes + role.default_minutes) / 2)))
    return Assignment(
        work_id=unit.id,
        role_id=role.id,
        role_title=role.title,
        capability=unit.capability,
        phase=unit.phase,
        minutes=minutes,
        notes=f"Owner chosen for {CAPABILITY_LABELS[unit.capability]}.",
    )


def _covered_capabilities(work_units: Iterable[WorkUnit], assignments: Iterable[Assignment]) -> set:
    work_by_id = {unit.id: unit for unit in work_units}
    covered = set()
    for assignment in assignments:
        unit = work_by_id[assignment.work_id]
        if assignment.capability == unit.capability:
            covered.add(unit.capability)
    return covered


def _risk_check_count(
    work_units: Sequence[WorkUnit], assignments: Sequence[Assignment], independent: bool
) -> int:
    tags = {tag for unit in work_units for tag in unit.risk_tags}
    if not tags:
        return 0
    if not independent:
        return 1
    risk_roles = {assignment.role_id for assignment in assignments if assignment.capability in {"risk_control", "verification"}}
    return len(tags) + len(risk_roles)


def _parallel_critical_path(assignments: Sequence[Assignment]) -> int:
    minutes_by_phase: Dict[str, int] = {phase: 0 for phase in PHASE_ORDER}
    for assignment in assignments:
        minutes_by_phase[assignment.phase] = max(
            minutes_by_phase.get(assignment.phase, 0), assignment.minutes
        )
    return sum(minutes_by_phase[phase] for phase in PHASE_ORDER)
