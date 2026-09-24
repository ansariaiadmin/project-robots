"""Structural — ego-graph BFS over import graph + 90d coupling matrix."""

from __future__ import annotations

from collections import deque
from pathlib import Path


def build_adjacency(import_graph: dict) -> dict[str, set[str]]:
    adj: dict[str, set[str]] = {}
    for path, node in import_graph.items():
        neighbours: set[str] = set()
        imports = getattr(node, "imports", [])
        for edge in imports:
            target = getattr(edge, "imported", "")
            if target in import_graph:
                neighbours.add(target)
        imported_by = getattr(node, "imported_by", [])
        for parent in imported_by:
            if parent in import_graph:
                neighbours.add(parent)
        adj[path] = neighbours
    return adj


def bfs_distances(adj: dict[str, set[str]], seeds: list[str], depth: int = 3) -> dict[str, int]:
    dist: dict[str, int] = {}
    queue: deque[tuple[str, int]] = deque()
    for seed in seeds:
        if seed in adj and seed not in dist:
            dist[seed] = 0
            queue.append((seed, 0))
    while queue:
        node, depth_now = queue.popleft()
        if depth_now >= depth:
            continue
        for neighbour in adj.get(node, set()):
            if neighbour not in dist:
                dist[neighbour] = depth_now + 1
                queue.append((neighbour, depth_now + 1))
    return dist


def file_scores(
    import_graph: dict,
    file_frequency: dict[str, int],
    seeds: list[str],
    depth: int = 3,
) -> dict[str, tuple[float, int]]:
    """Return {file: (score, dist)}. Score = 0.7/(1+dist) + 0.3*norm_coupling."""
    adj = build_adjacency(import_graph)
    # Seeds may reference files outside the python graph (docs etc.); keep them at dist 0.
    dist = bfs_distances(adj, [s for s in seeds if s in adj], depth=depth)
    for seed in seeds:
        dist.setdefault(seed, 0)
    out: dict[str, tuple[float, int]] = {}
    for path, distance in dist.items():
        coupling_norm = min(int(file_frequency.get(path, 0)) / 20.0, 1.0)
        score = 0.7 * (1.0 / (1.0 + distance)) + 0.3 * coupling_norm
        out[path] = (score, distance)
    return out


def structural_rank(
    project: Path,
    config: dict,
    seeds: list[str],
    import_graph: dict | None = None,
    file_frequency: dict[str, int] | None = None,
    depth: int = 3,
    limit: int = 40,
) -> list[str]:
    """Rank chunk_ids by structural file score. Loads graph lazily if needed."""
    if not seeds:
        return []
    if import_graph is None:
        try:
            from robots.intelligence.graph_builder import build_import_graph

            import_graph = build_import_graph(project, config)
        except Exception:
            import_graph = {}
    if file_frequency is None:
        try:
            from robots.intelligence.coupling import analyze_coupling

            file_frequency = dict(analyze_coupling(project, config).file_frequency)
        except Exception:
            file_frequency = {}
    scores = file_scores(import_graph or {}, file_frequency or {}, seeds, depth=depth)
    ranked_files = sorted(scores.items(), key=lambda kv: (-kv[1][0], kv[1][1], kv[0]))
    # Expand to chunk level via store lookup (chunk order = path,start_line).
    from robots.rag.store import load_chunks

    try:
        chunks = load_chunks(project)
    except Exception:
        return []
    order = {path: idx for idx, (path, _) in enumerate(ranked_files)}
    ranked = [c for c in chunks if c["path"] in order]
    ranked.sort(key=lambda c: (order[c["path"]], c["start_line"]))
    return [c["id"] for c in ranked[:limit]]


def seeds_for_query(task: str, changed_paths: list[str], config: dict) -> list[str]:
    """Derive seed files from changed paths + task-word path matches."""
    seeds = list(changed_paths)
    words = {w for w in task.lower().replace("/", " ").replace("-", " ").split() if len(w) >= 3}
    if words:
        # Lightweight: match task words against changed paths only (no full scan here).
        seeds.extend(p for p in changed_paths if any(w in p.lower() for w in words))
    return list(dict.fromkeys(seeds))
