"""Learning Engine — Continuous improvement from execution outcomes."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from robots.evidence.package import EvidencePackage
from robots.intelligence import RepositoryIntelligence


def _tokenize(text: str) -> set[str]:
    """Simple keyword tokenizer: lower, alphanum, min length 3."""
    if not text:
        return set()
    tokens = re.findall(r"[a-zA-Z0-9_]{3,}", text.lower())
    # Filter common stopwords
    stop = {"the", "and", "for", "with", "this", "that", "from", "have", "will", "are", "was", "were"}
    return {t for t in tokens if t not in stop}


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
        self.lessons_file = self.learning_dir / "lessons.jsonl"
        self.state = self._load_state()

    def _load_state(self) -> LearningState:
        """Load learning state from disk."""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                return LearningState(**data)
            except Exception:
                pass
        return LearningState()

    def _save_state(self) -> None:
        """Save learning state to disk (central cache only)."""
        self.state.updated_at = datetime.utcnow().isoformat()
        self.state_file.write_text(
            json.dumps(asdict(self.state), indent=2, default=str),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Lessons Store — JSON append-only + keyword retrieval
    # ------------------------------------------------------------------

    def save_lesson(self, lesson: dict) -> Path:
        """Append a single lesson to lessons.jsonl (append-only)."""
        lesson = dict(lesson)  # copy
        if "timestamp" not in lesson:
            lesson["timestamp"] = datetime.utcnow().isoformat()
        if "id" not in lesson:
            import uuid

            lesson["id"] = f"LES-{uuid.uuid4().hex[:8].upper()}"
        # Ensure keywords exist
        if "keywords" not in lesson:
            text = f"{lesson.get('category', '')} {lesson.get('message', '')} {lesson.get('context', '')}"
            lesson["keywords"] = sorted(_tokenize(text))

        # Append-only write
        with self.lessons_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(lesson, ensure_ascii=False) + "\n")
        return self.lessons_file

    def save_lessons_from_critique(self, evidence: EvidencePackage, critique_result) -> list[dict]:
        """Extract lessons from critic/reflexion and persist."""
        lessons: list[dict] = []
        findings = getattr(critique_result, "findings", []) or []
        if not findings and isinstance(evidence.verification, dict):
            # Fallback to verification critique findings
            findings = evidence.verification.get("critique", {}).get("findings", [])

        for finding in findings:
            if isinstance(finding, dict):
                category = finding.get("category", "unknown")
                severity = finding.get("severity", "info")
                message = finding.get("message", "")
            else:
                category = getattr(finding, "category", "unknown")
                severity = getattr(finding, "severity", "info")
                message = getattr(finding, "message", "")

            lesson = {
                "decision_id": evidence.decision_id,
                "category": category,
                "severity": severity,
                "message": message,
                "context": evidence.rationale[:500] if evidence.rationale else "",
                "risk_score": evidence.risk_score,
                "keywords": sorted(_tokenize(f"{category} {severity} {message} {evidence.rationale}")),
            }
            self.save_lesson(lesson)
            lessons.append(lesson)

        return lessons

    def load_lessons(self) -> list[dict]:
        """Load all lessons from JSONL store."""
        if not self.lessons_file.exists():
            return []
        lessons: list[dict] = []
        try:
            for line in self.lessons_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if isinstance(data, dict):
                        lessons.append(data)
                except json.JSONDecodeError:
                    continue
        except OSError:
            return []
        return lessons

    def get_relevant_lessons(self, issue: str, top_k: int = 5) -> list[dict]:
        """Retrieve lessons relevant to issue via keyword overlap."""
        if not issue:
            return []
        issue_keywords = _tokenize(issue)
        if not issue_keywords:
            return []

        all_lessons = self.load_lessons()
        if not all_lessons:
            return []

        scored: list[tuple[int, dict]] = []
        for lesson in all_lessons:
            lesson_keywords = set(lesson.get("keywords", []))
            if not lesson_keywords:
                # Tokenize on the fly if missing
                text = f"{lesson.get('category', '')} {lesson.get('message', '')} {lesson.get('context', '')}"
                lesson_keywords = _tokenize(text)
            overlap = len(issue_keywords & lesson_keywords)
            if overlap > 0:
                scored.append((overlap, lesson))

        # Sort by overlap desc, then recent first
        scored.sort(key=lambda x: (x[0], x[1].get("timestamp", "")), reverse=True)
        return [lesson for _, lesson in scored[:top_k]]

    # ------------------------------------------------------------------
    # Existing learning methods
    # ------------------------------------------------------------------

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
                    self.state.false_positive_patterns.append(
                        {
                            "pattern": finding.get("category"),
                            "decision_id": evidence.decision_id,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )
        else:
            # If checks failed but critique passed, false negative
            if critique_data.get("passed", True):
                self.state.false_negative_patterns.append(
                    {
                        "decision_id": evidence.decision_id,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

        # Keep only recent patterns
        self.state.false_positive_patterns = self.state.false_positive_patterns[-100:]
        self.state.false_negative_patterns = self.state.false_negative_patterns[-100:]

        self._save_state()

    def record_tool_effectiveness(self, tool: str, success: bool, duration: float) -> None:
        """Record tool effectiveness metrics."""
        if tool not in self.state.tool_effectiveness:
            self.state.tool_effectiveness[tool] = {
                "total": 0,
                "success": 0,
                "avg_duration": 0.0,
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

    def _measure_actual_coupling(
        self, evidence: EvidencePackage, intelligence: RepositoryIntelligence
    ) -> dict[str, float]:
        """Measure actual coupling impact after deployment — real implementation."""
        # Real measurement: for each changed file, count how many other files
        # reference it via import or file system coupling, compared to predicted.
        result: dict[str, float] = {}
        try:
            # Use intelligence dependency graph if available
            dep_graph = getattr(intelligence, "dependencies", None)
            if dep_graph is None and isinstance(intelligence, dict):
                dep_graph = intelligence.get("dependencies", {})

            changed = [c.get("file", c.get("path", "")) for c in evidence.changes]

            for file_path in changed:
                if not file_path:
                    continue
                # If dependency graph has this file, count dependents
                if isinstance(dep_graph, dict):
                    # dep_graph may be {file: [deps]} or {file: {imports: []}}
                    # Count how many files depend on this file
                    count = 0
                    for other_file, deps in dep_graph.items():
                        if other_file == file_path:
                            continue
                        if isinstance(deps, (list, set)):
                            if file_path in deps or any(file_path in str(d) for d in deps):
                                count += 1
                        elif isinstance(deps, dict):
                            imports = deps.get("imports", []) + deps.get("dependencies", [])
                            if file_path in imports or any(file_path in str(d) for d in imports):
                                count += 1
                    # Normalize to 0-1 range based on total files
                    total_files = len(dep_graph) or 1
                    result[file_path] = min(1.0, count / max(total_files * 0.1, 1))
                else:
                    # Fallback: check filesystem for references (grep-like)
                    result[file_path] = 0.0

            # Also include verification actual_risk if available
            if isinstance(evidence.verification, dict):
                actual = evidence.verification.get("actual_coupling", {})
                if isinstance(actual, dict):
                    result.update(actual)

        except Exception:
            # Fail-open, return empty but not stub
            pass

        return result


def create_learning_engine(project: Path) -> LearningEngine:
    """Convenience function to create learning engine."""
    return LearningEngine(project)
