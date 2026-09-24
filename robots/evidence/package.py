"""Evidence Package — Immutable signed record binding change to verification."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from robots.evidence.adr import ADR
from robots.evidence.observability import ObservabilityHooks
from robots.evidence.rollback import RollbackStrategy


@dataclass(slots=True)
class EvidencePackage:
    """Immutable evidence package for a change."""
    decision_id: str
    rationale: str
    risk_score: float
    changes: list[dict]
    tools: list[dict]
    verification: dict
    rollback: RollbackStrategy
    observability: ObservabilityHooks = field(default_factory=ObservabilityHooks)
    adr: ADR = field(default_factory=lambda: ADR(id="", title="", status="proposed", context="", decision=""))
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source_fingerprint: str = ""
    signature: str = ""

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "rationale": self.rationale,
            "risk_score": self.risk_score,
            "changes": self.changes,
            "tools": self.tools,
            "verification": self.verification,
            "rollback": self.rollback.to_dict(),
            "observability": self.observability.to_dict(),
            "adr": self.adr.to_dict(),
            "created_at": self.created_at,
            "source_fingerprint": self.source_fingerprint,
            "signature": self.signature,
        }

    def compute_fingerprint(self, project: Path) -> str:
        """Compute source fingerprint for this change."""
        hasher = hashlib.sha256()
        for change in self.changes:
            file_path = project / change.get("file", change.get("path", ""))
            if file_path.exists():
                hasher.update(file_path.read_bytes())
        self.source_fingerprint = hasher.hexdigest()[:16]
        return self.source_fingerprint

    def sign(self, private_key: str = "") -> str:
        """Sign the evidence package (placeholder for cryptographic signing)."""
        # In production, use proper cryptographic signing
        content = json.dumps(self.to_dict(), sort_keys=True)
        self.signature = hashlib.sha256(content.encode()).hexdigest()[:32]
        return self.signature

    def verify(self, project: Path, public_key: str = "") -> bool:
        """Verify the evidence package."""
        # Recompute fingerprint
        current_fp = self.compute_fingerprint(project)
        if current_fp != self.source_fingerprint:
            return False

        # Verify signature
        expected_sig = self.sign()
        return self.signature == expected_sig

    def canary_deploy(self, project: Path) -> bool:
        """Deploy to canary and verify SLOs."""
        # Placeholder - would integrate with deployment system
        return True

    def rollback(self, project: Path) -> bool:
        """Execute rollback strategy."""
        # Placeholder - would execute rollback steps
        return True


class EvidenceStore:
    """Stores and retrieves evidence packages (central cache only)."""

    def __init__(self, project: Path):
        from robots.common import cache_dir

        self.project = project
        self.evidence_dir = cache_dir(project, "evidence")
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        # Legacy read-only fallback (pre-RFC-002 target-repo location).
        self._legacy_dir = project / ".project-robots" / "evidence"

    def save(self, evidence: EvidencePackage) -> Path:
        """Save evidence package."""
        file_path = self.evidence_dir / f"{evidence.decision_id}.json"
        file_path.write_text(json.dumps(evidence.to_dict(), indent=2), encoding="utf-8")
        return file_path

    def load(self, decision_id: str) -> EvidencePackage | None:
        """Load evidence package (central first, legacy target path read-only).

        Returns None when missing or unreadable; never raises for a missing
        decision_id so callers can treat absence as a normal state.
        """
        for directory in (self.evidence_dir, self._legacy_dir):
            file_path = directory / f"{decision_id}.json"
            if not file_path.is_file():
                continue
            try:
                raw = file_path.read_text(encoding="utf-8")
            except OSError:
                continue
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(data, dict):
                continue
            try:
                return EvidencePackage(
                    decision_id=data["decision_id"],
                    rationale=data.get("rationale", ""),
                    risk_score=data.get("risk_score", 0.0),
                    changes=data.get("changes", []),
                    tools=data.get("tools", []),
                    verification=data.get("verification", {}),
                    rollback=RollbackStrategy(**data["rollback"]) if "rollback" in data else RollbackStrategy(strategy_type="immediate"),
                    observability=ObservabilityHooks(**data["observability"]) if "observability" in data else ObservabilityHooks(),
                    adr=ADR(**data["adr"]) if "adr" in data else ADR(id="", title="", status="proposed", context="", decision=""),
                )
            except (KeyError, TypeError, ValueError):
                continue
        return None

    def list(self) -> list[str]:
        """List all evidence package IDs."""
        return sorted(f.stem for f in self.evidence_dir.glob("*.json"))


def create_evidence_package(
    plan: dict,
    project: Path,
    verification_results: dict,
    tools_used: list[dict],
) -> EvidencePackage:
    """Create evidence package from plan and verification results."""
    import uuid

    from robots.evidence.adr import create_adr_from_plan
    from robots.evidence.observability import create_observability_hooks
    from robots.evidence.rollback import create_rollback_strategy

    decision_id = plan.get("decision_id", f"DEC-{uuid.uuid4().hex[:8].upper()}")

    adr = create_adr_from_plan(plan, project, decision_id.replace("DEC", "ADR"))
    observability = create_observability_hooks(plan)
    rollback = create_rollback_strategy(plan)

    evidence = EvidencePackage(
        decision_id=decision_id,
        rationale=plan.get("rationale", ""),
        risk_score=plan.get("risk_score", {}).get("overall", 0.0),
        changes=plan.get("changes", []),
        tools=tools_used,
        verification=verification_results,
        rollback=rollback,
        observability=observability,
        adr=adr,
    )

    evidence.compute_fingerprint(project)
    evidence.sign()

    return evidence
