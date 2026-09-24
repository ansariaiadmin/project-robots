"""Intelligence Robot — Repository intelligence analysis."""

from __future__ import annotations

from pathlib import Path

from robots.common import load_config, write_json
from robots.intelligence import build_repository_intelligence, get_intelligence_summary
from robots.protocol import BaseRobot, Plan, RobotResult, register_robot


class IntelligenceRobot(BaseRobot):
    """Robot for repository intelligence analysis."""

    name = "intelligence"
    version = 1

    def inspect(self, project: Path, config: dict) -> RobotResult:
        """Run intelligence analysis."""
        intelligence = build_repository_intelligence(project, config)
        summary = get_intelligence_summary(intelligence)

        output = write_json(project, "intelligence", "latest.json", intelligence.to_dict())

        return RobotResult(
            ok=True,
            summary=summary,
            output=output,
            metadata={"intelligence": intelligence.to_dict()},
        )

    def plan(self, project: Path, config: dict) -> "Plan":
        from robots.protocol import Plan

        return Plan(
            name="intelligence",
            steps=[{"action": "analyze", "target": "repository"}],
            risk_score=0.0,
        )

    def execute(self, project: Path, plan: "Plan") -> RobotResult:
        return self.inspect(project, {})


# Register on import
register_robot(IntelligenceRobot())


if __name__ == "__main__":
    import sys
    from robots.common import resolve_project

    project = resolve_project(sys.argv[1] if len(sys.argv) > 1 else ".")
    config, _ = load_config(project)

    robot = IntelligenceRobot()
    result = robot.inspect(project, config)
    print(f"OK: {result.summary}")
