"""Robot — RAGRobot + index/query commands (stdlib baseline)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from robots.common import (
    cache_dir,
    changed_files,
    load_config,
    source_state,
    write_json,
    write_markdown,
)
from robots.protocol import BaseRobot, Plan, RobotResult, register_robot


def build_index_command(
    project: Path,
    config: dict,
    force: bool = False,
    chunk_max_lines: int = 120,
    no_embed: bool = False,
) -> tuple[dict, Path]:
    from robots.rag.store import build_index

    info = build_index(
        project, config, force=force, chunk_max_lines=chunk_max_lines, no_embed=no_embed
    )
    payload = {
        "ok": True,
        "project": str(project),
        "sourceState": source_state(project, config),
        "summary": {
            "chunks": info["chunks"],
            "stale": info["stale"],
            "reused": info["reused"],
            "embed": info["embed"],
        },
    }
    output = write_json(project, "rag", "latest.json", payload)
    return payload, output


def query_command(
    project: Path,
    config: dict,
    task: str,
    k: int = 20,
    budget: int | None = None,
) -> tuple[dict, Path, Path]:
    from robots.brain.redact import is_secret_path, secret_marker
    from robots.rag.budget import allocate
    from robots.rag.lexical import fts_search
    from robots.rag.rank import fuse_with_details
    from robots.rag.store import is_fresh, load_chunks
    from robots.rag.structural import seeds_for_query, structural_rank
    from robots.rag.vectors import vector_rank

    limits = config["limits"]
    token_budget = int(budget or limits["contextTokenBudget"])
    fresh, meta, current = is_fresh(project, config)
    if not fresh:
        payload = {
            "ok": False,
            "project": str(project),
            "summary": {"hits": 0, "firstTokens": 0, "budget": token_budget},
            "reason": "RAG index missing or stale; run `rag-index` first.",
            "sourceState": current,
        }
        output = write_json(project, "rag", "query-latest.json", payload)
        md_path = write_markdown(project, "rag", "query-latest.md", "# RAG Query\n\nStale index.\n")
        return payload, output, md_path

    changes = changed_files(project, config)
    changed_paths = [c["path"] for c in changes]
    seeds = seeds_for_query(task, changed_paths, config)
    lexical_ids = fts_search(project, task or " ".join(changed_paths[:5]), limit=max(k * 2, 20))
    structural_ids = structural_rank(project, config, seeds, limit=max(k * 2, 20))
    # Lazy graph/coupling injection when seeds empty but task names a file.
    if not structural_ids:
        structural_ids = []
    vector_ids = vector_rank(project, task or " ".join(changed_paths[:5]), limit=max(k * 2, 20))

    fused = fuse_with_details(lexical_ids, structural_ids, vector_ids)[:k]
    by_id = {c["id"]: c for c in load_chunks(project)}
    ranked = []
    for entry in fused:
        chunk = by_id.get(entry["id"])
        if chunk is None:
            continue
        ranked.append({**chunk, **entry})

    # Budget allocation over full text (text kept in payload? No — keep refs only).
    alloc_input = [
        {"id": r["id"], "token_est": int(r["token_est"]), "ref": r} for r in ranked
    ]
    first, on_demand, estimated = allocate(alloc_input, token_budget)
    hits = [
        {
            "id": item["ref"]["id"],
            "path": item["ref"]["path"],
            "start": item["ref"]["start_line"],
            "end": item["ref"]["end_line"],
            "symbol": item["ref"]["symbol"],
            "symtype": item["ref"]["symtype"],
            "layer": item["ref"].get("layer", "unknown"),
            "token_est": item["token_est"],
            "open": item["open"],
            "rrf": round(float(item["ref"]["rrf"]), 6),
            "rank_L": item["ref"]["rank_L"],
            "rank_S": item["ref"]["rank_S"],
            "rank_V": item["ref"]["rank_V"],
        }
        for item in (*first, *on_demand)
    ]
    payload = {
        "ok": True,
        "project": str(project),
        "task": task,
        "sourceState": current,
        "summary": {
            "hits": len(hits),
            "firstTokens": estimated,
            "budget": token_budget,
            "embed": str((meta or {}).get("embedModel", "heuristic")),
        },
        "seeds": [s if not is_secret_path(s) else secret_marker(s) for s in seeds[:10]],
        "secretsSeeds": sum(1 for s in seeds[:10] if is_secret_path(s)),
        "hits": hits,
    }
    output = write_json(project, "rag", "query-latest.json", payload)
    lines = ["# RAG Query", "", f"Task: {task or 'Not supplied'}",
             f"Hits: {len(hits)} First-read: {estimated}/{token_budget}", "", "## Hits", ""]
    for hit in hits:
        lines.append(f"- `{hit['path']}:{hit['start']}-{hit['end']}` "
                     f"{hit['symbol']} (rrf={hit['rrf']}, {hit['open']})")
    md_path = write_markdown(project, "rag", "query-latest.md", "\n".join(lines))
    _ = sqlite3  # keep import used for future extensions
    _ = cache_dir
    return payload, output, md_path


def query_for_context(
    project: Path,
    config: dict,
    task: str,
    budget_remaining: int,
    k: int = 15,
) -> dict:
    """Fail-open helper for context_robot / autonomous loop. Never raises."""
    try:
        from robots.rag.store import is_fresh

        fresh, _, _ = is_fresh(project, config)
        if not fresh or budget_remaining <= 0:
            return {"hits": [], "firstTokens": 0, "stale": not fresh}
        payload, _, _ = query_command(project, config, task=task, k=k, budget=budget_remaining)
        if not payload.get("ok"):
            return {"hits": [], "firstTokens": 0, "stale": True}
        first_tokens = int(payload["summary"]["firstTokens"])
        # Strict guarantee: RAG first-tokens must fit the remaining budget.
        # allocate() always keeps the top chunk, so drop all hits on overflow.
        if first_tokens > budget_remaining:
            return {"hits": [], "firstTokens": 0, "stale": False,
                    "embed": payload["summary"].get("embed"), "dropped": "budget-overflow"}
        return {
            "hits": payload["hits"],
            "firstTokens": payload["summary"]["firstTokens"],
            "stale": False,
            "embed": payload["summary"].get("embed"),
        }
    except Exception:
        return {"hits": [], "firstTokens": 0, "stale": True}


class RAGRobot(BaseRobot):
    """Code-Graph RAG robot."""

    name = "rag"
    version = 1

    def inspect(self, project: Path, config: dict) -> RobotResult:
        from robots.rag.store import is_fresh

        fresh, meta, current = is_fresh(project, config)
        _ = current
        chunks = int((meta or {}).get("chunkCount", 0))
        output = cache_dir(project, "rag") / "latest.json"
        return RobotResult(
            ok=fresh,
            summary={"chunks": chunks, "stale": not fresh,
                     "embed": str((meta or {}).get("embedModel", "none"))},
            output=output,
            metadata={"meta": meta or {}},
        )

    def plan(self, project: Path, config: dict) -> Plan:
        return Plan(
            name="rag",
            steps=[
                {"action": "chunk", "target": "tracked-files"},
                {"action": "index", "target": "sqlite-fts5"},
                {"action": "fuse", "target": "rrf-tri-hybrid"},
                {"action": "allocate", "target": "token-budget"},
            ],
        )

    def execute(self, project: Path, plan: Plan) -> RobotResult:  # noqa: ARG002
        config, _ = load_config(project)
        payload, output = build_index_command(project, config)
        return RobotResult(ok=True, summary=payload["summary"], output=output, metadata=payload)


try:
    import contextlib

    with contextlib.suppress(Exception):
        register_robot(RAGRobot())
except ImportError:
    pass
