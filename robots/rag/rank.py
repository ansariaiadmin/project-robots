"""Rank — Reciprocal Rank Fusion (RRF, k=60)."""

from __future__ import annotations

RRF_K = 60


def rrf_fuse(rank_lists: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    """Fuse ordered id lists. Missing doc in a list contributes 0."""
    scores: dict[str, float] = {}
    for ranked in rank_lists:
        for rank, doc_id in enumerate(ranked, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return scores


def fuse_with_details(
    lexical: list[str],
    structural: list[str],
    vector: list[str],
    k: int = RRF_K,
) -> list[dict]:
    """Return sorted [{id, rrf, rank_L, rank_S, rank_V}] descending by RRF."""
    rank_l = {doc: i + 1 for i, doc in enumerate(lexical)}
    rank_s = {doc: i + 1 for i, doc in enumerate(structural)}
    rank_v = {doc: i + 1 for i, doc in enumerate(vector)}
    scores = rrf_fuse([lexical, structural, vector], k=k)
    details = [
        {
            "id": doc,
            "rrf": score,
            "rank_L": rank_l.get(doc),
            "rank_S": rank_s.get(doc),
            "rank_V": rank_v.get(doc),
        }
        for doc, score in scores.items()
    ]
    details.sort(key=lambda d: (-d["rrf"], d["id"]))
    return details
