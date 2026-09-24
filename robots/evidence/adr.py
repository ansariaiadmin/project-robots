"""Architectural Decision Record (ADR) — First-class evidence artifact."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal


@dataclass(slots=True)
class ADR:
    """Architectural Decision Record."""

    id: str  # ADR-0001
    title: str
    status: Literal["proposed", "accepted", "deprecated", "superseded"]
    context: str
    decision: str
    alternatives: list[str] = field(default_factory=list)
    consequences: dict[str, list[str]] = field(default_factory=lambda: {"positive": [], "negative": [], "neutral": []})
    links: list[str] = field(default_factory=list)
    created: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    supersedes: str | None = None
    superseded_by: str | None = None

    def to_markdown(self) -> str:
        """Render ADR as markdown."""
        lines = [
            f"# {self.id}: {self.title}",
            "",
            f"**Status**: {self.status}",
            f"**Date**: {self.created}",
        ]

        if self.supersedes:
            lines.append(f"**Supersedes**: {self.supersedes}")
        if self.superseded_by:
            lines.append(f"**Superseded by**: {self.superseded_by}")

        lines.extend(["", "## Context", "", self.context, "", "## Decision", "", self.decision, ""])

        if self.alternatives:
            lines.extend(["## Alternatives Considered", ""])
            for alt in self.alternatives:
                lines.append(f"- {alt}")
            lines.append("")

        if any(self.consequences.values()):
            lines.extend(["## Consequences", ""])
            for category, items in self.consequences.items():
                if items:
                    lines.append(f"### {category.title()}")
                    for item in items:
                        lines.append(f"- {item}")
                    lines.append("")

        if self.links:
            lines.extend(["## Links", ""])
            for link in self.links:
                lines.append(f"- {link}")
            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "context": self.context,
            "decision": self.decision,
            "alternatives": self.alternatives,
            "consequences": self.consequences,
            "links": self.links,
            "created": self.created,
            "supersedes": self.supersedes,
            "superseded_by": self.superseded_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ADR:
        return cls(**data)

    @classmethod
    def from_plan(cls, plan: dict, decision_id: str) -> ADR:
        """Create ADR from a plan."""
        return cls(
            id=decision_id,
            title=plan.get("title", "Automated Decision"),
            status="accepted",
            context=plan.get("context", plan.get("issue", "No context provided")),
            decision=plan.get("decision", plan.get("rationale", "No decision recorded")),
            alternatives=plan.get("alternatives", []),
            consequences=plan.get("consequences", {"positive": [], "negative": [], "neutral": []}),
            links=plan.get("links", []),
        )


class ADRRegistry:
    """Registry of ADRs for a project (central cache only)."""

    def __init__(self, project: Path):
        from robots.common import cache_dir

        self.project = project
        self.adr_dir = cache_dir(project, "adrs")
        self.adr_dir.mkdir(parents=True, exist_ok=True)
        # Legacy read-only fallback (pre-RFC-002 target-repo location).
        self._legacy_dir = project / ".project-robots" / "adrs"
        self._cache: dict[str, ADR] = {}

    def add(self, adr: ADR) -> Path:
        """Add an ADR to the registry."""
        file_path = self.adr_dir / f"{adr.id}.md"
        file_path.write_text(adr.to_markdown(), encoding="utf-8")

        # Also save as JSON for programmatic access
        json_path = self.adr_dir / f"{adr.id}.json"
        import json

        json_path.write_text(json.dumps(adr.to_dict(), indent=2), encoding="utf-8")

        self._cache[adr.id] = adr
        return file_path

    def get(self, adr_id: str) -> ADR | None:
        """Get an ADR by ID (central first, legacy target path read-only)."""
        if adr_id in self._cache:
            return self._cache[adr_id]

        for directory in (self.adr_dir, self._legacy_dir):
            json_path = directory / f"{adr_id}.json"
            if json_path.is_file():
                import json

                adr = ADR.from_dict(json.loads(json_path.read_text()))
                self._cache[adr_id] = adr
                return adr

        return None

    def list(self) -> list[ADR]:
        """List all ADRs."""
        adrs = []
        for json_file in self.adr_dir.glob("*.json"):
            try:
                import json

                adr = ADR.from_dict(json.loads(json_file.read_text()))
                adrs.append(adr)
            except Exception:
                pass
        return sorted(adrs, key=lambda a: a.id)

    def get_latest(self) -> ADR | None:
        """Get the most recent ADR."""
        adrs = self.list()
        return adrs[-1] if adrs else None


def create_adr_from_plan(
    plan: dict,
    project: Path,
    decision_id: str | None = None,
) -> ADR:
    """Create an ADR from a plan."""
    if not decision_id:
        import uuid

        decision_id = f"ADR-{uuid.uuid4().hex[:8].upper()}"

    registry = ADRRegistry(project)
    # Find next sequential ID if using numeric
    existing = registry.list()
    if existing and all(a.id.startswith("ADR-") and a.id[4:].isdigit() for a in existing):
        max_num = max(int(a.id.split("-")[1]) for a in existing)
        decision_id = f"ADR-{max_num + 1:04d}"

    adr = ADR.from_plan(plan, decision_id)
    registry.add(adr)
    return adr
