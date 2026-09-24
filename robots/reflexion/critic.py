"""Reflexion Critic — Senior engineer critique of plans."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from robots.intelligence import RepositoryIntelligence


@dataclass(slots=True)
class CritiqueFinding:
    """A single critique finding."""
    severity: str  # "critical", "major", "minor", "info"
    category: str  # "root_cause", "abstraction", "error_surface", "coupling", "migration", "observability", "performance", "adr", "style", "security"
    message: str
    file: str = ""
    line: int = 0
    suggestion: str = ""


@dataclass(slots=True)
class CritiqueResult:
    """Result of critique analysis."""
    passed: bool
    severity: float  # 0.0 - 1.0 (max severity)
    findings: list[CritiqueFinding]
    required_changes: list[str]
    summary: str


class Critic:
    """Senior engineer critique of proposed changes."""
    
    HEURISTICS = [
        {
            "id": "root_cause",
            "name": "Root Cause Addressed",
            "description": "Does this change address the root cause or mask a symptom?",
            "severity": "critical",
            "check": "_check_root_cause",
        },
        {
            "id": "abstraction_level",
            "name": "Abstraction Level Correct",
            "description": "Is the abstraction level appropriate? No premature abstraction, no leaky details.",
            "severity": "major",
            "check": "_check_abstraction_level",
        },
        {
            "id": "error_surface",
            "name": "Error Surface Narrowed",
            "description": "Are error surfaces narrowed or widened? Prefer explicit errors over silent failures.",
            "severity": "major",
            "check": "_check_error_surface",
        },
        {
            "id": "temporal_coupling",
            "name": "No Temporal Coupling",
            "description": "Does this introduce temporal coupling, hidden state, or implicit contracts?",
            "severity": "major",
            "check": "_check_temporal_coupling",
        },
        {
            "id": "migration_path",
            "name": "Migration Path for Dependents",
            "description": "Is there a migration path for every dependent? Or breaking change notice?",
            "severity": "critical",
            "check": "_check_migration_path",
        },
        {
            "id": "observability",
            "name": "Observability Added",
            "description": "Are metrics, traces, structured logs added for production validation?",
            "severity": "major",
            "check": "_check_observability",
        },
        {
            "id": "performance_budget",
            "name": "Performance Budget Respected",
            "description": "Does this respect performance budgets? No O(n²) in hot paths.",
            "severity": "minor",
            "check": "_check_performance_budget",
        },
        {
            "id": "adr_quality",
            "name": "ADR Quality Sufficient",
            "description": "Is the architectural decision record complete with alternatives and tradeoffs?",
            "severity": "minor",
            "check": "_check_adr_quality",
        },
        {
            "id": "style_consistency",
            "name": "Architectural Style Consistency",
            "description": "Does this follow the project's architectural style? Consistency > cleverness.",
            "severity": "minor",
            "check": "_check_style_consistency",
        },
        {
            "id": "security",
            "name": "Security Implications",
            "description": "Are there security implications? Input validation, authz, secrets, injection?",
            "severity": "critical",
            "check": "_check_security",
        },
    ]
    
    def __init__(self, config: dict):
        self.config = config
        self.persona = config.get("reflexion", {}).get("critic_persona", "senior_staff_engineer")
        self.enabled_heuristics = config.get("reflexion", {}).get("heuristics", "all")
    
    def critique(
        self,
        plan: dict,
        intelligence: RepositoryIntelligence,
        issue: str,
    ) -> CritiqueResult:
        """Critique a proposed plan."""
        findings = []
        
        # Run enabled heuristics
        for heuristic in self.HEURISTICS:
            if self.enabled_heuristics != "all" and heuristic["id"] not in self.enabled_heuristics:
                continue
            
            check_method = getattr(self, heuristic["check"])
            try:
                heuristic_findings = check_method(plan, intelligence, issue)
                findings.extend(heuristic_findings)
            except Exception as e:
                findings.append(CritiqueFinding(
                    severity="info",
                    category=heuristic["id"],
                    message=f"Heuristic check failed: {e}",
                ))
        
        # Determine overall result
        critical_findings = [f for f in findings if f.severity == "critical"]
        major_findings = [f for f in findings if f.severity == "major"]
        
        passed = len(critical_findings) == 0 and len(major_findings) == 0
        
        # Compute severity score
        severity_weights = {"critical": 1.0, "major": 0.6, "minor": 0.3, "info": 0.1}
        severity = sum(severity_weights.get(f.severity, 0) for f in findings)
        severity = min(severity / 10.0, 1.0)  # Normalize
        
        required_changes = [f.suggestion for f in findings if f.suggestion]
        
        # Generate summary
        summary = self._generate_summary(findings, passed)
        
        return CritiqueResult(
            passed=passed,
            severity=severity,
            findings=findings,
            required_changes=required_changes,
            summary=summary,
        )
    
    def _check_root_cause(self, plan: dict, intelligence: RepositoryIntelligence, issue: str) -> list[CritiqueFinding]:
        """Check if plan addresses root cause."""
        findings = []
        
        # Check if plan only treats symptoms (e.g., only adds try/except without fixing cause)
        steps = plan.get("steps", [])
        has_root_cause_fix = False
        has_symptom_mask = False
        
        for step in steps:
            action = step.get("action", "").lower()
            target = step.get("target", "").lower()
            
            # Symptom masking patterns
            if any(pattern in action for pattern in ["catch", "ignore", "suppress", "workaround", "patch"]):
                has_symptom_mask = True
            
            # Root cause patterns
            if any(pattern in action for pattern in ["refactor", "redesign", "fix", "remove", "replace", "extract"]):
                has_root_cause_fix = True
        
        if has_symptom_mask and not has_root_cause_fix:
            findings.append(CritiqueFinding(
                severity="critical",
                category="root_cause",
                message="Plan appears to mask symptoms without addressing root cause",
                suggestion="Identify and fix the underlying cause, not just the symptom",
            ))
        
        # Check against intelligence coupling - if change is in highly coupled file, root cause may be elsewhere
        for step in steps:
            target = step.get("target", "")
            if target in intelligence.coupling.file_frequency:
                freq = intelligence.coupling.file_frequency[target]
                if freq > 20:  # Highly churned file
                    coupled = intelligence.coupling.get_coupled_files(intelligence.coupling, target)
                    if coupled:
                        findings.append(CritiqueFinding(
                            severity="major",
                            category="root_cause",
                            message=f"Target '{target}' is highly coupled ({freq} changes); root cause may be in coupled files",
                            file=target,
                            suggestion=f"Investigate coupled files: {[c[0] for c in coupled[:3]]}",
                        ))
        
        return findings
    
    def _check_abstraction_level(self, plan: dict, intelligence: RepositoryIntelligence, issue: str) -> list[CritiqueFinding]:
        """Check abstraction level appropriateness."""
        findings = []
        
        # Check for leaky abstractions in changed files
        changed_files = plan.get("changed_files", [])
        for file_path in changed_files:
            layer = intelligence.architecture.layer_of_file.get(file_path, "unknown")
            
            # Check if file imports from wrong layers
            if file_path in intelligence.import_graph:
                node = intelligence.import_graph[file_path]
                for edge in node.imports:
                    imported_layer = intelligence.architecture.layer_of_file.get(edge.imported, "unknown")
                    
                    # Check boundary violations
                    for boundary in intelligence.architecture.boundaries:
                        if boundary.from_layer == layer and boundary.to_layer == imported_layer:
                            if not boundary.allowed:
                                findings.append(CritiqueFinding(
                                    severity="major",
                                    category="abstraction_level",
                                    message=f"Leaky abstraction: {layer} imports from {imported_layer} ({boundary.reason})",
                                    file=file_path,
                                    line=edge.line,
                                    suggestion=f"Move dependency to appropriate layer or use dependency inversion",
                                ))
        
        return findings
    
    def _check_error_surface(self, plan: dict, intelligence: RepositoryIntelligence, issue: str) -> list[CritiqueFinding]:
        """Check if error surfaces are narrowed."""
        findings = []
        
        # Look for error handling patterns in plan
        steps = plan.get("steps", [])
        for step in steps:
            action = step.get("action", "").lower()
            
            # Check for error widening patterns
            if "catch" in action and "rethrow" not in action:
                findings.append(CritiqueFinding(
                    severity="major",
                    category="error_surface",
                    message="Plan catches exceptions without rethrowing or handling - may swallow errors",
                    suggestion="Either handle explicitly with recovery, or rethrow with context",
                ))
            
            # Check for silent failures
            if "ignore" in action or "suppress" in action:
                findings.append(CritiqueFinding(
                    severity="critical",
                    category="error_surface",
                    message="Plan explicitly ignores/suppresses errors",
                    suggestion="Remove error suppression; add proper handling or let propagate",
                ))
        
        return findings
    
    def _check_temporal_coupling(self, plan: dict, intelligence: RepositoryIntelligence, issue: str) -> list[CritiqueFinding]:
        """Check for temporal coupling introduction."""
        findings = []
        
        # Look for patterns that introduce temporal coupling
        steps = plan.get("steps", [])
        for step in steps:
            action = step.get("action", "").lower()
            target = step.get("target", "").lower()
            
            # State mutation patterns
            if any(pattern in action for pattern in ["set_state", "mutate", "update_global", "singleton", "cache"]):
                findings.append(CritiqueFinding(
                    severity="major",
                    category="temporal_coupling",
                    message=f"Action '{action}' may introduce hidden state or temporal coupling",
                    file=target,
                    suggestion="Prefer explicit dependency injection over global state; use immutable data",
                ))
            
            # Async without proper synchronization
            if "async" in action and "await" not in str(plan):
                findings.append(CritiqueFinding(
                    severity="minor",
                    category="temporal_coupling",
                    message="Async operation without clear synchronization strategy",
                    suggestion="Document async boundaries; use structured concurrency",
                ))
        
        return findings
    
    def _check_migration_path(self, plan: dict, intelligence: RepositoryIntelligence, issue: str) -> list[CritiqueFinding]:
        """Check for migration path for dependents."""
        findings = []
        
        # Check if any breaking changes lack migration
        contract_changes = plan.get("contract_changes", [])
        for change in contract_changes:
            if change.get("severity") == "breaking":
                if not change.get("migration_path"):
                    findings.append(CritiqueFinding(
                        severity="critical",
                        category="migration_path",
                        message=f"Breaking change in {change.get('location')} has no migration path",
                        file=change.get("location", ""),
                        suggestion="Provide migration guide, deprecation period, or compatibility shim",
                    ))
        
        # Check architecture coupling for dependents
        changed_files = plan.get("changed_files", [])
        for file_path in changed_files:
            if file_path in intelligence.import_graph:
                node = intelligence.import_graph[file_path]
                if node.imported_by:  # Has dependents
                    # Check if plan mentions migration
                    has_migration = any("migrate" in str(s).lower() for s in steps)
                    if not has_migration:
                        findings.append(CritiqueFinding(
                            severity="major",
                            category="migration_path",
                            message=f"File '{file_path}' has {len(node.imported_by)} dependents; no migration mentioned",
                            file=file_path,
                            suggestion="Add migration step or compatibility layer for dependents",
                        ))
        
        return findings
    
    def _check_observability(self, plan: dict, intelligence: RepositoryIntelligence, issue: str) -> list[CritiqueFinding]:
        """Check for observability additions."""
        findings = []
        
        steps = plan.get("steps", [])
        has_observability = any(
            any(kw in str(step).lower() for kw in ["metric", "trace", "log", "span", "observe", "monitor"])
            for step in steps
        )
        
        # If plan modifies hot paths, observability is required
        changed_files = plan.get("changed_files", [])
        for file_path in changed_files:
            churn = intelligence.coupling.file_frequency.get(file_path, 0)
            if churn > 10 and not has_observability:
                findings.append(CritiqueFinding(
                    severity="major",
                    category="observability",
                    message=f"High-churn file '{file_path}' modified without observability additions",
                    file=file_path,
                    suggestion="Add metrics, structured logging, or tracing for production visibility",
                ))
        
        return findings
    
    def _check_performance_budget(self, plan: dict, intelligence: RepositoryIntelligence, issue: str) -> list[CritiqueFinding]:
        """Check performance budget."""
        findings = []
        
        # Look for performance anti-patterns
        steps = plan.get("steps", [])
        for step in steps:
            action = step.get("action", "").lower()
            target = step.get("target", "").lower()
            
            if any(pattern in action for pattern in ["loop", "nested", "recursive", "sync_io", "blocking"]):
                findings.append(CritiqueFinding(
                    severity="minor",
                    category="performance_budget",
                    message=f"Action '{action}' on '{target}' may have performance implications",
                    file=target,
                    suggestion="Consider async, batching, caching, or algorithmic improvement",
                ))
        
        return findings
    
    def _check_adr_quality(self, plan: dict, intelligence: RepositoryIntelligence, issue: str) -> list[CritiqueFinding]:
        """Check ADR quality."""
        findings = []
        
        adr = plan.get("adr", {})
        if not adr:
            findings.append(CritiqueFinding(
                severity="minor",
                category="adr_quality",
                message="No architectural decision record provided",
                suggestion="Add ADR with context, decision, alternatives, and consequences",
            ))
        else:
            required = ["context", "decision", "alternatives", "consequences"]
            for field in required:
                if field not in adr or not adr[field]:
                    findings.append(CritiqueFinding(
                        severity="minor",
                        category="adr_quality",
                        message=f"ADR missing required field: {field}",
                        suggestion=f"Complete ADR {field} section",
                    ))
        
        return findings
    
    def _check_style_consistency(self, plan: dict, intelligence: RepositoryIntelligence, issue: str) -> list[CritiqueFinding]:
        """Check architectural style consistency."""
        findings = []
        
        # Check if new patterns match existing project patterns
        changed_files = plan.get("changed_files", [])
        for file_path in changed_files:
            layer = intelligence.architecture.layer_of_file.get(file_path, "unknown")
            
            # Check layer-specific patterns
            if layer == "domain" and "framework" in str(plan).lower():
                findings.append(CritiqueFinding(
                    severity="minor",
                    category="style_consistency",
                    message="Domain layer should not depend on frameworks",
                    file=file_path,
                    suggestion="Move framework concerns to infrastructure layer",
                ))
        
        return findings
    
    def _check_security(self, plan: dict, intelligence: RepositoryIntelligence, issue: str) -> list[CritiqueFinding]:
        """Check security implications."""
        findings = []
        
        steps = plan.get("steps", [])
        for step in steps:
            action = step.get("action", "").lower()
            target = step.get("target", "").lower()
            
            # Security-sensitive patterns
            if any(pattern in action for pattern in ["eval", "exec", "pickle", "yaml_load", "subprocess", "shell"]):
                findings.append(CritiqueFinding(
                    severity="critical",
                    category="security",
                    message=f"Security-sensitive operation '{action}' in plan",
                    file=target,
                    suggestion="Validate/sanitize inputs; use safe alternatives (json, ast.literal_eval, subprocess without shell)",
                ))
            
            # Auth/sensitive data
            if any(pattern in target for pattern in ["auth", "password", "secret", "token", "key", "credential"]):
                findings.append(CritiqueFinding(
                    severity="critical",
                    category="security",
                    message=f"Plan modifies security-sensitive component: {target}",
                    file=target,
                    suggestion="Ensure proper encryption, rotation, audit logging; no secrets in code",
                ))
        
        return findings
    
    def _generate_summary(self, findings: list[CritiqueFinding], passed: bool) -> str:
        """Generate critique summary."""
        if passed:
            return "Plan passes all critique heuristics."
        
        by_severity = {}
        for f in findings:
            by_severity[f.severity] = by_severity.get(f.severity, 0) + 1
        
        parts = []
        for sev in ["critical", "major", "minor", "info"]:
            if sev in by_severity:
                parts.append(f"{by_severity[sev]} {sev}")
        
        return f"Critique failed: {', '.join(parts)} findings."


def critique_plan(
    plan: dict,
    intelligence: RepositoryIntelligence,
    issue: str,
    config: dict,
) -> CritiqueResult:
    """Convenience function to critique a plan."""
    critic = Critic(config)
    return critic.critique(plan, intelligence, issue)