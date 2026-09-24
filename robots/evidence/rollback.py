"""Rollback Strategy — Feature flags, canary, and auto-rollback."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal


@dataclass(slots=True)
class RollbackStrategy:
    """Defines rollback strategy for a change."""
    strategy_type: Literal["feature_flag", "canary", "blue_green", "immediate"]
    trigger_conditions: list[dict] = field(default_factory=list)
    rollback_steps: list[str] = field(default_factory=list)
    verification: list[str] = field(default_factory=list)
    timeout_seconds: int = 300
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "strategy_type": self.strategy_type,
            "trigger_conditions": self.trigger_conditions,
            "rollback_steps": self.rollback_steps,
            "verification": self.verification,
            "timeout_seconds": self.timeout_seconds,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_plan(cls, plan: dict) -> "RollbackStrategy":
        """Generate rollback strategy from a plan."""
        risk_score = plan.get("risk_score", {}).get("overall", 0.0)
        changed_files = plan.get("changed_files", [])
        
        # Select strategy based on risk
        if risk_score < 0.15:
            strategy_type = "feature_flag"
        elif risk_score < 0.30:
            strategy_type = "canary"
        elif risk_score < 0.50:
            strategy_type = "blue_green"
        else:
            strategy_type = "immediate"
        
        # Build trigger conditions
        triggers = [
            {"metric": "error_rate", "threshold": 0.05, "window": "5m"},
            {"metric": "latency_p99", "threshold": 2.0, "window": "5m"},
            {"metric": "availability", "threshold": 0.99, "window": "5m"},
        ]
        
        # Add custom triggers from plan
        for step in plan.get("steps", []):
            if "alert" in str(step).lower():
                triggers.append({"custom": str(step)})
        
        # Build rollback steps
        steps = [
            "Disable feature flag / route traffic away",
            "Verify traffic routed to stable version",
            "Run smoke tests on stable version",
            "Notify on-call team",
        ]
        
        if strategy_type == "canary":
            steps.insert(0, "Reduce canary traffic to 0%")
        elif strategy_type == "blue_green":
            steps.insert(0, "Switch load balancer to blue environment")
        
        # Add verification steps
        verification = [
            "Error rate < 1% for 5 minutes",
            "Latency p99 < baseline",
            "Key business metrics stable",
        ]
        
        return cls(
            strategy_type=strategy_type,
            trigger_conditions=triggers,
            rollback_steps=steps,
            verification=verification,
            timeout_seconds=300 if strategy_type != "immediate" else 60,
            metadata={
                "risk_score": risk_score,
                "changed_files": changed_files,
                "decision_id": plan.get("decision_id", ""),
            },
        )
    
    def to_runbook(self) -> str:
        """Generate runbook markdown."""
        lines = [
            f"# Rollback Runbook: {self.strategy_type.title()}",
            "",
            f"**Timeout**: {self.timeout_seconds}s",
            f"**Risk Score**: {self.metadata.get('risk_score', 'unknown')}",
            "",
            "## Trigger Conditions",
            "",
        ]
        
        for trigger in self.trigger_conditions:
            if "metric" in trigger:
                lines.append(f"- {trigger['metric']} > {trigger['threshold']} over {trigger['window']}")
            else:
                lines.append(f"- Custom: {trigger}")
        
        lines.extend(["", "## Rollback Steps", ""])
        for i, step in enumerate(self.rollback_steps, 1):
            lines.append(f"{i}. {step}")
        
        lines.extend(["", "## Verification", ""])
        for i, check in enumerate(self.verification, 1):
            lines.append(f"{i}. {check}")
        
        lines.extend(["", "## Post-Rollback", ""])
        lines.extend([
            "1. Create incident record",
            "2. Analyze root cause",
            "3. Plan fix with proper testing",
            "4. Re-deploy with improved safeguards",
        ])
        
        return "\n".join(lines)


def create_rollback_strategy(plan: dict) -> RollbackStrategy:
    """Convenience function to create rollback strategy from a plan."""
    return RollbackStrategy.from_plan(plan)