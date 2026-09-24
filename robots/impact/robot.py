"""Impact Robot — Impact analysis and risk scoring."""

from __future__ import annotations

from pathlib import Path

from robots.common import load_config, write_json
from robots.impact.contract_diff import analyze_contract_diff
from robots.impact.mutation_engine import run_mutation_testing
from robots.impact.property_fuzzer import run_property_fuzzing
from robots.impact.risk_scorer import RiskScorer, compute_risk_score
from robots.impact.static_reachability import ReachabilityAnalyzer, analyze_reachability
from robots.intelligence import build_repository_intelligence
from robots.protocol import BaseRobot, Plan, RobotResult, register_robot


class ImpactRobot(BaseRobot):
    """Robot for impact analysis and risk scoring."""

    name = "impact"
    version = 1

    def inspect(self, project: Path, config: dict) -> RobotResult:
        """Run impact analysis on current changes."""
        # Get changed files
        from robots.common import changed_files

        changes = changed_files(project, config)
        changed_files_list = [c["path"] for c in changes]

        if not changed_files_list:
            return RobotResult(
                ok=True,
                summary={"message": "No changes to analyze"},
                output=write_json(project, "impact", "latest.json", {}),
            )

        # Build intelligence
        intelligence = build_repository_intelligence(project, config)

        # Run all analyses
        reachability = analyze_reachability(project, config, changed_files_list)
        coupling_impact = ReachabilityAnalyzer(intelligence).compute_coupling_impact(changed_files_list)
        mutation = run_mutation_testing(project, config, changed_files_list)
        contract_diff = analyze_contract_diff(project, config)
        property_result = run_property_fuzzing(project, config, changed_files_list)

        # Compute risk score
        risk_score = compute_risk_score(
            project, config, reachability, coupling_impact, mutation, contract_diff, property_result
        )

        # Decision
        scorer = RiskScorer(config)
        decision = scorer.get_decision(risk_score)

        result_data = {
            "changed_files": changed_files_list,
            "reachability": {
                "affected_files": list(reachability.affected_files),
                "blast_radius": reachability.blast_radius,
                "entry_points": reachability.entry_points,
            },
            "coupling_impact": coupling_impact,
            "mutation": {
                "score": mutation.mutation_score,
                "total": mutation.total_mutants,
                "killed": mutation.killed,
                "survived": mutation.survived,
            },
            "contract_diff": {
                "breaking": contract_diff.breaking_changes,
                "non_breaking": contract_diff.non_breaking_changes,
                "risk": contract_diff.risk_score,
            },
            "property_tests": {
                "tested": property_result.properties_tested,
                "passed": property_result.passed,
                "failed": property_result.failed,
            },
            "risk_score": risk_score.to_dict(),
            "decision": decision,
        }

        output = write_json(project, "impact", "latest.json", result_data)

        return RobotResult(
            ok=decision != "reject",
            summary={
                "decision": decision,
                "risk_score": risk_score.overall,
                "blast_radius": reachability.blast_radius,
                "mutation_score": mutation.mutation_score,
            },
            output=output,
            metadata=result_data,
        )

    def plan(self, project: Path, config: dict) -> Plan:
        return Plan(
            name="impact",
            steps=[
                {"action": "reachability", "target": "changed_files"},
                {"action": "coupling", "target": "history"},
                {"action": "mutation", "target": "tests"},
                {"action": "contract", "target": "api"},
                {"action": "property", "target": "invariants"},
                {"action": "risk_score", "target": "aggregate"},
            ],
            risk_score=0.0,
        )

    def execute(self, project: Path, plan: Plan) -> RobotResult:
        return self.inspect(project, {})


# Register on import
register_robot(ImpactRobot())


if __name__ == "__main__":
    import sys

    from robots.common import resolve_project

    project = resolve_project(sys.argv[1] if len(sys.argv) > 1 else ".")
    config, _ = load_config(project)

    robot = ImpactRobot()
    result = robot.inspect(project, config)
    print(f"{'OK' if result.ok else 'REVIEW'}: {result.summary}")
