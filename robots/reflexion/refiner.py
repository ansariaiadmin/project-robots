"""Refiner — Plan refinement based on critique feedback."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from robots.reflexion.critic import CritiqueResult, CritiqueFinding
from robots.intelligence import RepositoryIntelligence


@dataclass(slots=True)
class Refinement:
    """A single plan refinement."""
    finding_id: str
    action: str  # "add_step", "modify_step", "remove_step", "add_adr", "add_migration"
    description: str
    step_index: int | None = None
    new_step: dict | None = None


class Refiner:
    """Refines plans based on critique findings."""
    
    def __init__(self, config: dict):
        self.config = config
        self.max_iterations = config.get("reflexion", {}).get("max_iterations", 3)
    
    def refine(
        self,
        plan: dict,
        critique: CritiqueResult,
        intelligence: RepositoryIntelligence,
    ) -> dict:
        """Refine plan based on critique findings."""
        refined_plan = plan.copy()
        steps = refined_plan.get("steps", []).copy()
        
        # Group findings by category
        by_category = {}
        for finding in critique.findings:
            if finding.category not in by_category:
                by_category[finding.category] = []
            by_category[finding.category].append(finding)
        
        # Apply refinements for each category
        if "root_cause" in by_category:
            steps = self._refine_root_cause(steps, by_category["root_cause"], intelligence)
        
        if "abstraction_level" in by_category:
            steps = self._refine_abstraction_level(steps, by_category["abstraction_level"], intelligence)
        
        if "error_surface" in by_category:
            steps = self._refine_error_surface(steps, by_category["error_surface"])
        
        if "temporal_coupling" in by_category:
            steps = self._refine_temporal_coupling(steps, by_category["temporal_coupling"])
        
        if "migration_path" in by_category:
            steps = self._refine_migration_path(steps, by_category["migration_path"], intelligence)
        
        if "observability" in by_category:
            steps = self._refine_observability(steps, by_category["observability"])
        
        if "performance_budget" in by_category:
            steps = self._refine_performance_budget(steps, by_category["performance_budget"])
        
        if "adr_quality" in by_category:
            refined_plan = self._refine_adr_quality(refined_plan, by_category["adr_quality"])
        
        if "security" in by_category:
            steps = self._refine_security(steps, by_category["security"])
        
        refined_plan["steps"] = steps
        refined_plan["refinements_applied"] = refined_plan.get("refinements_applied", 0) + 1
        
        return refined_plan
    
    def _refine_root_cause(self, steps: list[dict], findings: list, intelligence: RepositoryIntelligence) -> list[dict]:
        """Add root cause analysis step."""
        # Insert root cause investigation at the beginning
        new_step = {
            "action": "root_cause_analysis",
            "target": "issue",
            "description": "Perform root cause analysis before implementing fix",
        }
        return [new_step] + steps
    
    def _refine_abstraction_level(self, steps: list[dict], findings: list, intelligence: RepositoryIntelligence) -> list[dict]:
        """Fix abstraction level violations."""
        new_steps = steps.copy()
        
        for finding in findings:
            if finding.suggestion:
                # Add refactoring step to fix boundary violation
                new_steps.append({
                    "action": "refactor",
                    "target": finding.file,
                    "description": f"Fix abstraction violation: {finding.message}",
                    "suggestion": finding.suggestion,
                })
        
        return new_steps
    
    def _refine_error_surface(self, steps: list[dict], findings: list) -> list[dict]:
        """Fix error handling issues."""
        new_steps = steps.copy()
        
        for finding in findings:
            if "swallow" in finding.message.lower() or "suppress" in finding.message.lower():
                # Replace error suppression with proper handling
                for i, step in enumerate(new_steps):
                    if "ignore" in str(step).lower() or "suppress" in str(step).lower():
                        new_steps[i] = {
                            "action": "handle_error",
                            "target": step.get("target", ""),
                            "description": "Replace error suppression with explicit handling",
                        }
        
        return new_steps
    
    def _refine_temporal_coupling(self, steps: list[dict], findings: list) -> list[dict]:
        """Remove temporal coupling."""
        new_steps = steps.copy()
        
        for finding in findings:
            if finding.suggestion:
                new_steps.append({
                    "action": "remove_temporal_coupling",
                    "target": finding.file,
                    "description": finding.suggestion,
                })
        
        return new_steps
    
    def _refine_migration_path(self, steps: list[dict], findings: list, intelligence: RepositoryIntelligence) -> list[dict]:
        """Add migration steps for dependents."""
        new_steps = steps.copy()
        
        # Add migration step for each breaking change
        for finding in findings:
            if finding.suggestion:
                new_steps.append({
                    "action": "add_migration",
                    "target": finding.file,
                    "description": finding.suggestion,
                })
        
        return new_steps
    
    def _refine_observability(self, steps: list[dict], findings: list) -> list[dict]:
        """Add observability steps."""
        new_steps = steps.copy()
        
        # Add observability as a final step
        new_steps.append({
            "action": "add_observability",
            "target": "changed_files",
            "description": "Add metrics, logging, and tracing for changed components",
        })
        
        return new_steps
    
    def _refine_performance_budget(self, steps: list[dict], findings: list) -> list[dict]:
        """Add performance considerations."""
        new_steps = steps.copy()
        
        for finding in findings:
            if finding.suggestion:
                new_steps.append({
                    "action": "performance_review",
                    "target": finding.file,
                    "description": finding.suggestion,
                })
        
        return new_steps
    
    def _refine_adr_quality(self, plan: dict, findings: list) -> dict:
        """Improve ADR quality."""
        refined = plan.copy()
        
        if "adr" not in refined:
            refined["adr"] = {}
        
        for finding in findings:
            if "missing" in finding.message.lower():
                field = finding.message.split(":")[-1].strip()
                refined["adr"][field] = f"TODO: {finding.suggestion}"
        
        return refined
    
    def _refine_security(self, steps: list[dict], findings: list) -> list[dict]:
        """Fix security issues."""
        new_steps = steps.copy()
        
        for finding in findings:
            # Replace unsafe operations with safe alternatives
            for i, step in enumerate(new_steps):
                action = step.get("action", "").lower()
                if any(unsafe in action for unsafe in ["eval", "exec", "pickle", "shell"]):
                    new_steps[i] = {
                        "action": "secure_implementation",
                        "target": step.get("target", ""),
                        "description": f"Replace unsafe {action} with safe alternative",
                    }
        
        return new_steps


def refine_plan(
    plan: dict,
    critique: CritiqueResult,
    intelligence: RepositoryIntelligence,
    config: dict,
) -> dict:
    """Convenience function to refine a plan."""
    refiner = Refiner(config)
    return refiner.refine(plan, critique, intelligence)