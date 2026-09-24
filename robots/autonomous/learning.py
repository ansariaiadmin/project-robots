"""Learning Engine — Continuous improvement from execution outcomes."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from robots.evidence.package import EvidencePackage
from robots.intelligence import RepositoryIntelligence


@dataclass(slots=True)
class LearningState:
    """Persisted learning state."""
    coupling_adjustments: dict[str, float] = field(default_factory=dict)
    risk_weight_adjustments: dict[str, float] = field(default_factory=dict)
    critique_patterns: dict[str, int] = field(default_factory=dict)
    tool_effectiveness: dict[str, dict[str, float]] = field(default_factory=dict)
    false_positive_patterns: list[dict] = field(default_factory=list)
    false_negative_patterns: list[dict] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class LearningEngine:
    """Updates models from actual execution outcomes."""

    def __init__(self, project: Path):
        from robots.common import cache_dir

        self.project = project
        self.learning_dir = cache_dir(project, "learning")
        self.learning_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.learning_dir / "state.json"
        self.state = self._load_state()

    def _load_state(self) -> LearningState:
        """Load learning state from disk."""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text())
                return LearningState(**data)
            except Exception:
                pass
        return LearningState()

    def _save_state(self) -> None:
        """Save learning state to disk (central cache only)."""
        from dataclasses import asdict

        self.state.updated_at = datetime.utcnow().isoformat()
        self.state_file.write_text(
            json.dumps(asdict(self.state), indent=2, default=str),
            encoding="utf-8",
        )

    def update_coupling(self, evidence: EvidencePackage, intelligence: RepositoryIntelligence) -> None:
        """Update coupling matrix with actual vs predicted impact."""
        predicted_coupling = evidence.verification.get("impact", {}).get("coupling_impact", {})
        actual_coupling = self._measure_actual_coupling(evidence, intelligence)

        for file_path, predicted in predicted_coupling.items():
            actual = actual_coupling.get(file_path, 0)
            error = abs(predicted - actual)

            if error > 0.2:  # Significant prediction error
                key = f"coupling:{file_path}"
                self.state.coupling_adjustments[key] = self.state.coupling_adjustments.get(key, 0) + error * 0.1

        self._save_state()

    def adjust_risk_weights(self, evidence: EvidencePackage) -> None:
        """Adjust risk model weights based on prediction accuracy."""
        predicted_risk = evidence.risk_score
        actual_risk = evidence.verification.get("actual_risk", predicted_risk)
        error = predicted_risk - actual_risk  # Positive = overestimated risk

        # Adjust weights based on which factors contributed to error
        risk_breakdown = evidence.verification.get("risk_score", {}).get("breakdown", {})

        for factor, predicted_value in risk_breakdown.items():
            if factor in self.state.risk_weight_adjustments:
                self.state.risk_weight_adjustments[factor] += error * 0.05
            else:
                self.state.risk_weight_adjustments[factor] = error * 0.05

        self._save_state()

    def refine_critic(self, evidence: EvidencePackage, critique_result) -> None:
        """Refine critic heuristics based on outcomes."""
        critique_data = evidence.verification.get("critique", {})
        findings = critique_data.get("findings", [])

        for finding in findings:
            category = finding.get("category", "unknown")
            severity = finding.get("severity", "info")

            # Track which critique patterns correlate with actual issues
            pattern_key = f"{category}:{severity}"
            self.state.critique_patterns[pattern_key] = self.state.critique_patterns.get(pattern_key, 0) + 1

        # Track false positives/negatives
        if evidence.verification.get("checks", {}).get("passed", False):
            # If checks passed but critique found issues, those might be false positives
            for finding in findings:
                if finding.get("severity") in ("critical", "major"):
                    self.state.false_positive_patterns.append({
                        "pattern": finding.get("category"),
                        "decision_id": evidence.decision_id,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
        else:
            # If checks failed but critique passed, false negative
            if critique_data.get("passed", True):
                self.state.false_negative_patterns.append({
                    "decision_id": evidence.decision_id,
                    "timestamp": datetime.utcnow().isoformat(),
                })

        # Keep only recent patterns
        self.state.false_positive_patterns = self.state.false_positive_patterns[-100:]
        self.state.false_negative_patterns = self.state.false_negative_patterns[-100:]

        self._save_state()

    def record_tool_effectiveness(self, tool: str, success: bool, duration: float) -> None:
        """Record tool effectiveness metrics."""
        if tool not in self.state.tool_effectiveness:
            self.state.tool_effectiveness[tool] = {
                "total": 0, "success": 0, "avg_duration": 0.0,
            }

        stats = self.state.tool_effectiveness[tool]
        stats["total"] += 1
        if success:
            stats["success"] += 1
        stats["avg_duration"] = (stats["avg_duration"] * (stats["total"] - 1) + duration) / stats["total"]

        self._save_state()

    def get_adjusted_weights(self, base_weights: dict[str, float]) -> dict[str, float]:
        """Get risk weights adjusted by learning."""
        adjusted = base_weights.copy()
        for factor, adjustment in self.state.risk_weight_adjustments.items():
            if factor in adjusted:
                adjusted[factor] = max(0.01, min(0.99, adjusted[factor] + adjustment))

        # Renormalize
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        return adjusted

    def get_coupling_adjustment(self, file_path: str) -> float:
        """Get coupling adjustment for a file."""
        return self.state.coupling_adjustments.get(f"coupling:{file_path}", 0.0)

    def get_critique_confidence(self, category: str, severity: str) -> float:
        """Get confidence in a critique pattern based on historical accuracy."""
        pattern_key = f"{category}:{severity}"
        total = self.state.critique_patterns.get(pattern_key, 0)
        false_positives = sum(1 for fp in self.state.false_positive_patterns if fp.get("pattern") == category)

        if total == 0:
            return 0.5

        # Confidence decreases with false positive rate
        fp_rate = false_positives / max(total, 1)
        return max(0.1, 1.0 - fp_rate)

    def get_best_tool(self, tool_candidates: list[str]) -> str:
        """Select best tool based on historical effectiveness."""
        if not tool_candidates:
            return ""

        best_tool = tool_candidates[0]
        best_score = -1

        for tool in tool_candidates:
            stats = self.state.tool_effectiveness.get(tool, {})
            if stats.get("total", 0) >= 3:  # Enough data
                success_rate = stats.get("success", 0) / stats["total"]
                speed_score = 1.0 / max(stats.get("avg_duration", 1.0), 0.1)
                score = success_rate * 0.7 + min(speed_score, 1.0) * 0.3

                if score > best_score:
                    best_score = score
                    best_tool = tool

        return best_tool

    def _measure_actual_coupling(self, evidence: EvidencePackage, intelligence: RepositoryIntelligence) -> dict[str, float]:
        """Measure actual coupling impact after deployment."""
        # This would measure real production impact
        # For now, return empty dict
        return {}


def create_learning_engine(project: Path) -> LearningEngine:
    """Convenience function to create learning engine."""
    return LearningEngine(project)
