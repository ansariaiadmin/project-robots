"""Lexical — FTS5 BM25 search with LIKE fallback (stdlib only)."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from robots.rag.store import index_db_path

_STOPWORDS = frozenset({
    "the", "and", "for", "with", "from", "that", "this", "are", "was",
    "have", "has", "will", "would", "should", "could", "about", "into",
})


def tokenize_query(query: str, max_terms: int = 20) -> list[str]:
    terms = re.findall(r"[A-Za-z0-9_]+", query.lower())
    out: list[str] = []
    for term in terms:
        if term.lower() in _STOPWORDS:
            continue
        out.append(term)
        if len(out) >= max_terms:
            break
    return out


def _match_expr(terms: list[str]) -> str:
    # Escape double quotes for FTS5 phrase safety; OR-join terms.
    safe = [t.replace('"', "") for t in terms if t.replace('"', "")]
    if not safe:
        return ""
    return " OR ".join(f'"{t}"' for t in safe)


def fts_search(project: Path, query: str, limit: int = 40) -> list[str]:
    """Return chunk_ids ranked by BM25. Empty list when no terms/index."""
    terms = tokenize_query(query)
    if not terms:
        return []
    db_path = index_db_path(project)
    if not db_path.is_file():
        return []
    match = _match_expr(terms)
    if not match:
        return []
    con = sqlite3.connect(str(db_path))
    try:
        try:
            cur = con.execute(
                "SELECT chunk_id FROM chunks_fts WHERE chunks_fts MATCH ? "
                "ORDER BY bm25(chunks_fts) LIMIT ?",
                (match, limit),
            )
            return [row[0] for row in cur.fetchall()]
        except sqlite3.OperationalError:
            return like_fallback(project, terms, limit)
    finally:
        con.close()


def like_fallback(project: Path, terms: list[str], limit: int = 40) -> list[str]:
    """Fallback lexical ranking via LIKE hit counts (no FTS5)."""
    from robots.rag.store import load_chunks

    try:
        chunks = load_chunks(project)
    except Exception:
        return []
    scored: list[tuple[int, str]] = []
    for chunk in chunks:
        haystack = f"{chunk['path']} {chunk['symbol']} {chunk['text']}".lower()
        hits = sum(1 for t in terms if t.lower() in haystack)
        if hits:
            # Tie-break: smaller chunks first for precision.
            scored.append((hits, chunk["id"]))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [cid for _, cid in scored[:limit]]


def has_fts(project: Path) -> bool:
    db_path = index_db_path(project)
    if not db_path.is_file():
        return False
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("SELECT chunk_id FROM chunks_fts LIMIT 1").fetchall()
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        con.close()
