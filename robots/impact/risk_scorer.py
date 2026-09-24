"""Risk scoring for impact analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .static_reachability import ReachabilityResult
from .mutation_engine import MutationResult
from .property_fuzzer import PropertyResult
from .contract_diff import ContractDiffResult


@dataclass(slots=True)
class RiskScore:
    """Complete risk score with breakdown."""

    overall: float  # 0.0 - 1.0
    reachability: float
    coupling: float
    mutation_survival: float
    contract_breakage: float
    performance_regression: float
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "overall": self.overall,
            "breakdown": {
                "reachability": self.reachability,
                "coupling": self.coupling,
                "mutation_survival": self.mutation_survival,
                "contract_breakage": self.contract_breakage,
                "performance_regression": self.performance_regression,
            },
            "details": self.details,
        }


class RiskScorer:
    """Computes multi-factor risk score for changes."""

    # Weights for each factor (must sum to 1.0)
    WEIGHTS = {
        "reachability": 0.35,
        "coupling": 0.25,
        "mutation_survival": 0.20,
        "contract_breakage": 0.15,
        "performance_regression": 0.05,
    }

    # Thresholds for auto-apply / review / reject
    THRESHOLDS = {
        "auto_apply": 0.15,
        "fast_track": 0.30,
        "full_review": 0.50,
    }

    def __init__(self, config: dict):
        self.config = config
        impact_config = config.get("impact", {})
        self.weights = impact_config.get("risk_weights", self.WEIGHTS)
        self.thresholds = impact_config.get("risk_thresholds", self.THRESHOLDS)

    def score(
        self,
        reachability: ReachabilityResult,
        coupling_impact: dict[str, float],
        mutation: MutationResult,
        contract_diff: ContractDiffResult,
        property_result: PropertyResult | None = None,
        performance_delta: float | None = None,
    ) -> RiskScore:
        """Compute overall risk score."""

        # 1. Reachability score (0-1): fraction of codebase affected
        total_files = len(reachability.affected_files) + len(coupling_impact)
        reachability_score = min(total_files / 100.0, 1.0)  # Normalize to 100 files

        # 2. Coupling score (0-1): max coupling impact
        coupling_score = max(coupling_impact.values()) if coupling_impact else 0.0

        # 3. Mutation survival score (0-1): 1 - mutation_score
        mutation_survival = 1.0 - mutation.mutation_score if mutation.total_mutants > 0 else 0.5

        # 4. Contract breakage score (0-1): from contract diff
        contract_breakage = contract_diff.risk_score

        # 5. Performance regression (0-1): from benchmarks
        performance_regression = 0.0
        if performance_delta is not None:
            # Positive delta = slower = bad
            performance_regression = min(max(performance_delta, 0.0), 1.0)

        # Weighted overall score
        overall = (
            self.weights["reachability"] * reachability_score
            + self.weights["coupling"] * coupling_score
            + self.weights["mutation_survival"] * mutation_survival
            + self.weights["contract_breakage"] * contract_breakage
            + self.weights["performance_regression"] * performance_regression
        )

        details = {
            "total_affected_files": total_files,
            "blast_radius": reachability.blast_radius,
            "entry_points": reachability.entry_points,
            "coupling_hotspots": sorted(coupling_impact.items(), key=lambda x: -x[1])[:5],
            "mutation_score": mutation.mutation_score,
            "mutation_total": mutation.total_mutants,
            "contract_breaking": contract_diff.breaking_changes,
            "contract_non_breaking": contract_diff.non_breaking_changes,
            "property_tests_passed": property_result.passed if property_result else 0,
            "property_tests_failed": property_result.failed if property_result else 0,
            "performance_delta": performance_delta,
        }

        return RiskScore(
            overall=overall,
            reachability=reachability_score,
            coupling=coupling_score,
            mutation_survival=mutation_survival,
            contract_breakage=contract_breakage,
            performance_regression=performance_regression,
            details=details,
        )

    def get_decision(self, risk_score: RiskScore) -> str:
        """Get deployment decision based on risk score."""
        overall = risk_score.overall

        if overall < self.thresholds["auto_apply"]:
            return "auto_apply"
        elif overall < self.thresholds["fast_track"]:
            return "fast_track"
        elif overall < self.thresholds["full_review"]:
            return "full_review"
        else:
            return "reject"

    def get_thresholds(self) -> dict:
        return self.thresholds.copy()


def compute_risk_score(
    project: Path,
    config: dict,
    reachability: ReachabilityResult,
    coupling_impact: dict[str, float],
    mutation: MutationResult,
    contract_diff: ContractDiffResult,
    property_result: PropertyResult | None = None,
    performance_delta: float | None = None,
) -> RiskScore:
    """Convenience function to compute risk score."""
    scorer = RiskScorer(config)
    return scorer.score(reachability, coupling_impact, mutation, contract_diff, property_result, performance_delta)
