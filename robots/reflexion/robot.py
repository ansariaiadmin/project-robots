"""Critique Robot — Plan critique and reflexion loop."""

from __future__ import annotations

from pathlib import Path

from robots.common import load_config, write_json
from robots.protocol import BaseRobot, RobotResult, Plan, register_robot
from robots.intelligence import build_repository_intelligence
from robots.reflexion.critic import critique_plan, Critic
from robots.reflexion.refiner import refine_plan


class CritiqueRobot(BaseRobot):
    """Robot for plan critique and reflexion loop."""
    name = "critique"
    version = 1
    
    def critique_plan_direct(
        self,
        plan: dict,
        intelligence,
        issue: str,
        project: Path,
        config: dict,
    ) -> tuple:
        """Critique the given in-memory plan directly (no stale file read).

        Explicit contract for autonomous cycles: the current plan object is
        critiqued, refined in memory, and artifacts are written for
        inspectability only (never read back as the handoff).
        Returns (critique_result, refined_plan, robot_result).
        """
        from robots.common import write_json as _write_json

        working = dict(plan) if isinstance(plan, dict) else {}
        working.setdefault("issue", issue)
        critique = critique_plan(working, intelligence, issue, config)
        refined_plan = working
        if not critique.passed:
            refined_plan = refine_plan(working, critique, intelligence, config)
            _write_json(project, "checks", "latest_refined.json", refined_plan)
        result_data = {
            "original_plan": working,
            "critique": {
                "passed": critique.passed,
                "severity": critique.severity,
                "findings": [
                    {
                        "severity": f.severity,
                        "category": f.category,
                        "message": f.message,
                        "file": f.file,
                        "line": f.line,
                        "suggestion": f.suggestion,
                    }
                    for f in critique.findings
                ],
                "required_changes": critique.required_changes,
                "summary": critique.summary,
            },
            "refined_plan": refined_plan if not critique.passed else None,
        }
        output = _write_json(project, "critique", "latest.json", result_data)
        result = RobotResult(
            ok=critique.passed,
            summary={
                "passed": critique.passed,
                "severity": critique.severity,
                "findings": len(critique.findings),
                "refined": not critique.passed,
            },
            output=output,
            metadata=result_data,
        )
        return critique, refined_plan, result

    def inspect(self, project: Path, config: dict) -> RobotResult:
        """Critique the latest plan (standalone CLI behavior; file-backed)."""
        # Load latest plan
        from robots.common import cache_dir
        plan_path = cache_dir(project, "checks") / "latest.json"
        
        if not plan_path.exists():
            return RobotResult(
                ok=False,
                summary={"error": "No plan found to critique"},
                output=plan_path,
            )
        
        import json
        with plan_path.open() as f:
            plan = json.load(f)
        
        # Build intelligence
        intelligence = build_repository_intelligence(project, config)
        
        # Get issue from plan or use default
        issue = plan.get("issue", "autonomous maintenance")
        
        # Run critique
        critique = critique_plan(plan, intelligence, issue, config)
        
        # If critique fails, refine plan
        refined_plan = plan
        if not critique.passed:
            refined_plan = refine_plan(plan, critique, intelligence, config)
            # Save refined plan
            write_json(project, "checks", "latest_refined.json", refined_plan)
        
        result_data = {
            "original_plan": plan,
            "critique": {
                "passed": critique.passed,
                "severity": critique.severity,
                "findings": [
                    {
                        "severity": f.severity,
                        "category": f.category,
                        "message": f.message,
                        "file": f.file,
                        "line": f.line,
                        "suggestion": f.suggestion,
                    }
                    for f in critique.findings
                ],
                "required_changes": critique.required_changes,
                "summary": critique.summary,
            },
            "refined_plan": refined_plan if not critique.passed else None,
        }
        
        output = write_json(project, "critique", "latest.json", result_data)
        
        return RobotResult(
            ok=critique.passed,
            summary={
                "passed": critique.passed,
                "severity": critique.severity,
                "findings": len(critique.findings),
                "refined": not critique.passed,
            },
            output=output,
            metadata=result_data,
        )
    
    def plan(self, project: Path, config: dict) -> Plan:
        return Plan(
            name="critique",
            steps=[
                {"action": "load_plan", "target": "latest"},
                {"action": "critique", "target": "plan"},
                {"action": "refine", "target": "plan", "condition": "failed"},
            ],
            risk_score=0.0,
        )
    
    def execute(self, project: Path, plan: Plan) -> RobotResult:
        return self.inspect(project, {})


# Register on import
register_robot(CritiqueRobot())


if __name__ == "__main__":
    import sys
    from robots.common import resolve_project
    
    project = resolve_project(sys.argv[1] if len(sys.argv) > 1 else ".")
    config, _ = load_config(project)
    
    robot = CritiqueRobot()
    result = robot.inspect(project, config)
    print(f"{'OK' if result.ok else 'REFACTOR'}: {result.summary}")