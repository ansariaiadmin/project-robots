"""Tool Selector — Adaptive tool selection for code changes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from robots.intelligence import RepositoryIntelligence


@dataclass(slots=True)
class ToolRecommendation:
    """Recommended tool for a change."""
    tool: str  # "ast_rewrite", "semantic_patch", "model_checker", "contract_tester", "property_tester"
    reason: str
    confidence: float  # 0.0 - 1.0
    config: dict = None
    
    def __post_init__(self):
        if self.config is None:
            self.config = {}


class ToolSelector:
    """Selects optimal tool for a given code change."""
    
    def __init__(self, config: dict):
        self.config = config
        self.enabled_tools = config.get("tooling", {})
    
    def select(self, changes: list[dict], intelligence: RepositoryIntelligence) -> list[ToolRecommendation]:
        """Select tools for a list of changes (skips malformed entries)."""
        recommendations = []

        for change in changes:
            if not isinstance(change, dict):
                continue
            file_path = change.get("file", change.get("path", ""))
            change_type = change.get("type", "unknown")
            description = change.get("description", "")
            
            tool = self._select_for_change(file_path, change_type, description, intelligence)
            if tool:
                recommendations.append(tool)
        
        return recommendations
    
    def _select_for_change(
        self,
        file_path: str,
        change_type: str,
        description: str,
        intelligence: RepositoryIntelligence,
    ) -> ToolRecommendation | None:
        """Select best tool for a single change."""
        desc_lower = description.lower()
        
        # Get file context
        layer = intelligence.architecture.layer_of_file.get(file_path, "unknown")
        churn = intelligence.coupling.file_frequency.get(file_path, 0)
        debt = intelligence.debt_index.file_metrics.get(file_path)
        complexity = debt.complexity if debt else 0
        
        # Decision tree for tool selection
        
        # 1. Cross-cutting pattern changes (logging, retry, auth, etc.)
        if any(pattern in desc_lower for pattern in [
            "logging", "log", "retry", "circuit", "breaker", "timeout",
            "auth", "permission", "validation", "sanitiz", "decorator",
            "middleware", "interceptor", "aspect", "cross-cutting",
        ]):
            if self.enabled_tools.get("semantic_patch", True):
                return ToolRecommendation(
                    tool="semantic_patch",
                    reason="Cross-cutting concern modification - semantic patch (comby/coccinelle) ideal for pattern-based changes across many files",
                    confidence=0.9,
                    config={"pattern_type": "decorator" if "decorator" in desc_lower else "function_call"},
                )
        
        # 2. Structural refactoring (class extraction, method extraction, etc.)
        if any(pattern in desc_lower for pattern in [
            "extract", "refactor", "restructure", "rename", "move",
            "inline", "encapsulate", "delegate", "composition",
        ]):
            if self.enabled_tools.get("ast_rewrite", True):
                return ToolRecommendation(
                    tool="ast_rewrite",
                    reason="Structural refactoring - AST rewrite (libcst/ruff) preserves semantics while transforming structure",
                    confidence=0.85,
                    config={"refactoring_type": self._infer_refactoring_type(description)},
                )
        
        # 3. Concurrency/state machine changes
        if any(pattern in desc_lower for pattern in [
            "concurrent", "thread", "async", "race", "deadlock",
            "state machine", "workflow", "orchestrat", "saga",
            "consistency", "transaction", "lock",
        ]):
            if self.enabled_tools.get("model_checking", False):
                return ToolRecommendation(
                    tool="model_checker",
                    reason="Concurrency/state logic - model checking (TLA+/Alloy) verifies correctness of concurrent systems",
                    confidence=0.8,
                    config={"spec_type": "tla" if "temporal" in desc_lower else "alloy"},
                )
        
        # 4. API/Contract changes
        if any(pattern in desc_lower for pattern in [
            "api", "interface", "contract", "schema", "protocol",
            "serializ", "deserializ", "grpc", "rest", "graphql",
            "version", "migration", "compatib",
        ]):
            if self.enabled_tools.get("contract_testing", True):
                return ToolRecommendation(
                    tool="contract_tester",
                    reason="API/Contract change - contract testing verifies compatibility and generates migration shims",
                    confidence=0.9,
                    config={"contract_type": "openapi" if "rest" in desc_lower else "protobuf" if "grpc" in desc_lower else "pydantic"},
                )
        
        # 5. Algorithm/Logic correctness
        if any(pattern in desc_lower for pattern in [
            "algorithm", "logic", "calculate", "compute", "transform",
            "sort", "search", "optimize", "invariant", "property",
        ]):
            if self.enabled_tools.get("property_testing", True):
                return ToolRecommendation(
                    tool="property_tester",
                    reason="Algorithm/logic change - property-based testing (Hypothesis) verifies invariants across input space",
                    confidence=0.75,
                    config={"property_type": "invariant" if "invariant" in desc_lower else "roundtrip" if "serializ" in desc_lower else "idempotent"},
                )
        
        # 6. Performance optimization
        if any(pattern in desc_lower for pattern in [
            "performance", "optimize", "speed", "latency", "throughput",
            "memory", "allocat", "cache", "batch", "parallel",
        ]):
            return ToolRecommendation(
                tool="benchmark",
                reason="Performance change - microbenchmarking with statistical analysis required",
                confidence=0.8,
                config={"benchmark_type": "micro" if "function" in desc_lower else "macro"},
            )
        
        # 7. High complexity file - prefer AST for safety
        if complexity > 30 and self.enabled_tools.get("ast_rewrite", True):
            return ToolRecommendation(
                tool="ast_rewrite",
                reason=f"High complexity file (complexity={complexity}) - AST rewrite safer than text-based changes",
                confidence=0.7,
                config={"safety_mode": True},
            )
        
        # 8. High churn file - prefer semantic patch for consistency
        if churn > 20 and self.enabled_tools.get("semantic_patch", True):
            return ToolRecommendation(
                tool="semantic_patch",
                reason=f"High churn file (churn={churn}) - semantic patch ensures consistent pattern application",
                confidence=0.7,
                config={"consistency_mode": True},
            )
        
        # Default: AST rewrite for Python, semantic patch for other patterns
        if self.enabled_tools.get("ast_rewrite", True):
            return ToolRecommendation(
                tool="ast_rewrite",
                reason="Default to AST rewrite for safe, semantics-preserving changes",
                confidence=0.5,
                config={},
            )
        
        return None
    
    def _infer_refactoring_type(self, description: str) -> str:
        """Infer refactoring type from description."""
        desc = description.lower()
        if "extract" in desc:
            return "extract_method" if "method" in desc else "extract_class"
        elif "rename" in desc:
            return "rename"
        elif "move" in desc:
            return "move"
        elif "inline" in desc:
            return "inline"
        elif "encapsulate" in desc:
            return "encapsulate_field"
        return "general"


def select_tools(
    changes: list[dict],
    intelligence: RepositoryIntelligence,
    config: dict,
) -> list[ToolRecommendation]:
    """Convenience function to select tools."""
    selector = ToolSelector(config)
    return selector.select(changes, intelligence)