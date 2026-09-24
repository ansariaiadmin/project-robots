"""Vectors — stdlib hashed TF-IDF (dim=256) + Ollama/ONNX hook."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import urllib.request
from pathlib import Path

DIM = 256


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_]+", text.lower())


def _hash_index(term: str) -> int:
    digest = hashlib.md5(term.encode("utf-8")).digest()
    return int.from_bytes(digest[:2], "little") % DIM


def build_idf(texts: list[str]) -> dict[str, float]:
    """Compute IDF over a corpus. idf(t) = log((N+1)/(df+1)) + 1."""
    doc_freq: dict[str, int] = {}
    count = 0
    for text in texts:
        count += 1
        for term in set(tokenize(text)):
            doc_freq[term] = doc_freq.get(term, 0) + 1
    total = max(count, 1)
    return {t: math.log((total + 1) / (df + 1)) + 1.0 for t, df in doc_freq.items()}


def text_to_vector(text: str, idf: dict[str, float]) -> list[float]:
    vector = [0.0] * DIM
    terms = tokenize(text)
    if not terms:
        return vector
    counts: dict[str, int] = {}
    for term in terms:
        counts[term] = counts.get(term, 0) + 1
    length = len(terms)
    for term, freq in counts.items():
        idx = _hash_index(term)
        vector[idx] += (freq / length) * idf.get(term, 1.0)
    norm = math.sqrt(sum(v * v for v in vector))
    if norm > 0:
        vector = [v / norm for v in vector]
    return vector


def pack_vector(vector: list[float]) -> bytes:
    import struct

    return struct.pack(f"<{len(vector)}f", *vector)


def unpack_vector(blob: bytes, dim: int = DIM) -> list[float]:
    import struct

    if len(blob) != dim * 4:
        return [0.0] * dim
    return list(struct.unpack(f"<{dim}f", blob))


def cosine(first: list[float], second: list[float]) -> float:
    total = sum(first[i] * second[i] for i in range(min(len(first), len(second))))
    return max(-1.0, min(1.0, total))


def try_external_embedding(
    texts: list[str],
    config: dict,
    timeout: int = 5,
) -> list[list[float]] | None:
    """Hook for Ollama/ONNX endpoints. Returns None on any failure."""
    rag_cfg = config.get("rag", {})
    endpoint = rag_cfg.get("embed_endpoint", "")
    model = rag_cfg.get("embed_model", "")
    if not endpoint or not model:
        return None
    try:
        payload = json.dumps({"model": model, "input": texts[:8]}).encode("utf-8")
        request = urllib.request.Request(
            endpoint, data=payload, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        vectors = data.get("embeddings") or data.get("vectors") or []
        if not vectors:
            return None
        return [[float(v) for v in row] for row in vectors]
    except Exception:
        return None


def vector_rank(project: Path, query: str, limit: int = 40) -> list[str]:
    """Rank chunk_ids by cosine similarity (heuristic vectors from index)."""
    from robots.rag.store import index_db_path

    db_path = index_db_path(project)
    if not db_path.is_file():
        return []
    con = sqlite3.connect(str(db_path))
    try:
        rows = con.execute("SELECT id, text FROM chunks").fetchall()
        embeds = {
            row[0]: row[1]
            for row in con.execute("SELECT chunk_id, vec FROM embeddings").fetchall()
        }
    except sqlite3.OperationalError:
        con.close()
        return []
    con.close()
    if not rows:
        return []
    idf = build_idf([text for _, text in rows])
    query_vec = text_to_vector(query, idf)
    scored: list[tuple[float, str]] = []
    for chunk_id, text in rows:
        blob = embeds.get(chunk_id)
        if blob is None:
            chunk_vec = text_to_vector(text, idf)
        else:
            chunk_vec = unpack_vector(blob)
            if len(chunk_vec) != DIM:
                chunk_vec = text_to_vector(text, idf)
        scored.append((cosine(query_vec, chunk_vec), chunk_id))
    scored.sort(key=lambda item: (-item[0], item[1]))
    # Drop zero-similarity tail to keep precision.
    ranked = [cid for score, cid in scored if score > 0.0]
    return ranked[:limit]
