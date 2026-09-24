"""Prompt — tier-aware dialect formatter plus plan schema repair (stdlib only)."""

from __future__ import annotations

import json

from robots.brain.capabilities import TIER_1_LOCAL

PLAN_CONTRACT = (
    '{"type": "object", "required": ["rationale", "steps"], '
    '"properties": {"rationale": {"type": "string"}, '
    '"steps": {"type": "array", "items": {"type": "object", '
    '"required": ["action", "target"]}}, '
    '"changes": {"type": "array", "items": {"type": "object", '
    '"required": ["file"], "properties": {'
    '"file": {"type": "string"}, '
    '"pattern": {"type": "string"}, '
    '"replacement": {"type": "string"}, '
    '"description": {"type": "string"}}}}, '
    '"risk_note": {"type": "string"}}}'
)

_EDIT_GUIDE = (
    "Express every code edit as a changes entry with file (project-relative path), "
    "pattern (exact source substring to replace), replacement (new text), and "
    "description. Only touch files shown in context. Omit pattern/replacement "
    "when no file edit is needed."
)

_DEFAULT_STEPS = [
    {"action": "analyze", "target": "impact"},
    {"action": "fix", "target": "root_cause"},
    {"action": "test", "target": "verification"},
]

_CHUNK_CHARS_TIER_1 = 600
_CHUNK_CHARS_RICH = 1500


def _render_chunks(chunks: list[dict], max_chars: int, include_text: bool) -> str:
    lines: list[str] = []
    for chunk in chunks:
        header = (
            f"{chunk.get('path', '?')}:{chunk.get('start', chunk.get('start_line', '?'))}"
            f"-{chunk.get('end', chunk.get('end_line', '?'))} "
            f"[{chunk.get('symbol', '?')}]"
        )
        lines.append(header)
        if include_text:
            text = str(chunk.get("text", ""))
            if len(text) > max_chars:
                text = text[:max_chars] + "\n…(truncated)"
            lines.append(text)
    return "\n".join(lines)


def build_prompt(
    *,
    task: str,
    rag_chunks: list[dict] | None = None,
    intelligence_summary: dict | None = None,
    tier: str = TIER_1_LOCAL,
    budget: int = 4000,
) -> str:
    """Format a tier-appropriate planning prompt.

    Tier 1: compressed XML (<context>/<task>/<contract>), chunk references
    with truncated text, strict JSON-only contract.
    Tier 2/3: rich Markdown with graph-trace reasoning section.
    """
    chunks = rag_chunks or []
    summary = intelligence_summary or {}
    if tier == TIER_1_LOCAL:
        body = "\n".join(
            [
                f"<context budget={int(budget)}>",
                _render_chunks(chunks, _CHUNK_CHARS_TIER_1, include_text=True),
                "</context>",
                f"<task>{task}</task>",
                f"<summary>{json.dumps(summary, ensure_ascii=False)[:800]}</summary>",
                "<contract>",
                f"Respond with JSON ONLY matching this schema: {PLAN_CONTRACT}",
                _EDIT_GUIDE,
                "</contract>",
            ]
        )
        return body
    graph_lines = []
    for chunk in chunks:
        graph_lines.append(f"- `{chunk.get('path', '?')}` {chunk.get('symbol', '?')} (rrf={chunk.get('rrf', '?')})")
    return "\n".join(
        [
            "# Autonomous Repair Plan",
            "",
            "## Task",
            task,
            "",
            "## Repository Summary",
            json.dumps(summary, ensure_ascii=False, indent=2)[:2000],
            "",
            "## Relevant Code (retrieval trace)",
            *(graph_lines or ["- (no retrieval hits)"]),
            "",
            "## Retrieved Context",
            _render_chunks(chunks, _CHUNK_CHARS_RICH, include_text=True) or "(none)",
            "",
            "## Contract",
            "Reason step by step about root cause, blast radius, and verification. "
            f"Then emit a final JSON object matching: {PLAN_CONTRACT}",
            _EDIT_GUIDE,
        ]
    )


def extract_json(raw: str) -> dict | None:
    """Extract the first plausible JSON object from model text."""
    text = (raw or "").strip()
    if not text:
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    fenced = text.find("```")
    while fenced != -1:
        start = text.find("{", fenced)
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(text[start : end + 1])
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                pass
        fenced = text.find("```", fenced + 3)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def repair_plan(raw_text: str, task: str) -> tuple[dict, bool, str]:
    """Validate model output against the plan contract; fill defaults.

    Returns (plan, repaired, error). Never raises: unparseable output
    degrades to the deterministic default plan with repaired=True.
    """
    data = extract_json(raw_text)
    if data is None:
        return _default_plan(task), True, "unparseable model output"
    repaired = False
    if not isinstance(data.get("rationale"), str) or not data["rationale"].strip():
        data["rationale"] = f"Plan for: {task}"
        repaired = True
    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        data["steps"] = [dict(step) for step in _DEFAULT_STEPS]
        repaired = True
    else:
        clean: list[dict] = []
        for step in steps:
            if isinstance(step, dict) and step.get("action") and step.get("target"):
                clean.append({"action": str(step["action"]), "target": str(step["target"])})
            else:
                repaired = True
        if not clean:
            clean = [dict(step) for step in _DEFAULT_STEPS]
        data["steps"] = clean
    if not isinstance(data.get("changes"), list):
        data["changes"] = []
    if "risk_note" in data and not isinstance(data["risk_note"], str):
        data["risk_note"] = str(data["risk_note"])
        repaired = True
    return data, repaired, ""


def _default_plan(task: str) -> dict:
    return {
        "rationale": f"Plan for: {task}",
        "steps": [dict(step) for step in _DEFAULT_STEPS],
        "changes": [],
        "risk_note": "default plan (model output unusable)",
    }
