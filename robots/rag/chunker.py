"""Chunker — AST symbol-boundary + sliding-window fallback (stdlib only)."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

CHUNK_MAX_LINES = 120
SLIDING_LINES = 80
SLIDING_STRIDE = 60
SLIDING_OVERLAP = 10


def token_estimate(text: str) -> int:
    """Estimate tokens as bytes//4, matching context_robot."""
    return max(1, len(text.encode("utf-8")) // 4)


def chunk_id(path: str, start: int, end: int, text_hash: str) -> str:
    digest = hashlib.sha256(f"{path}:{start}:{end}:{text_hash}".encode()).hexdigest()
    return digest[:16]


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def chunk_python_symbols(
    path: str,
    text: str,
    max_lines: int = CHUNK_MAX_LINES,
) -> list[dict] | None:
    """Split Python source on symbol boundaries. Returns None on parse failure."""
    try:
        tree = ast.parse(text, filename=path)
    except (SyntaxError, ValueError):
        return None
    lines = text.splitlines()
    total = len(lines)

    def slice_lines(start: int, end: int) -> str:
        return "\n".join(lines[start - 1 : end])

    # Module header: imports + docstring (first 40 lines max, only leading imports).
    header_end = 0
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)) or (
            isinstance(node, ast.Expr) and header_end == 0
        ):
            header_end = max(header_end, node.end_lineno or 0)
        else:
            break
    header_end = min(header_end, 40)
    chunks: list[dict] = []
    if header_end > 0:
        header_text = slice_lines(1, header_end)
        chunks.append({
            "path": path,
            "start_line": 1,
            "end_line": header_end,
            "symbol": "<module-header>",
            "symtype": "module",
            "text": header_text,
        })

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        start = node.lineno
        end = node.end_lineno or start
        if isinstance(node, ast.ClassDef):
            # Emit methods individually when class is oversized.
            methods = [
                n for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            span = end - start + 1
            if methods and span > max_lines:
                # Class signature chunk.
                sig_end = methods[0].lineno - 1
                if sig_end >= start:
                    chunks.append({
                        "path": path,
                        "start_line": start,
                        "end_line": sig_end,
                        "symbol": node.name,
                        "symtype": "class",
                        "text": slice_lines(start, sig_end),
                    })
                for method in methods:
                    m_start = method.lineno
                    m_end = method.end_lineno or m_start
                    m_text = slice_lines(m_start, m_end)
                    if m_end - m_start + 1 > max_lines:
                        chunks.extend(
                            _split_oversized(path, f"{node.name}.{method.name}", m_start, lines)
                        )
                    else:
                        chunks.append({
                            "path": path,
                            "start_line": m_start,
                            "end_line": m_end,
                            "symbol": f"{node.name}.{method.name}",
                            "symtype": "func",
                            "text": m_text,
                        })
                continue
        symtype = "class" if isinstance(node, ast.ClassDef) else "func"
        if end - start + 1 > max_lines:
            chunks.extend(_split_oversized(path, node.name, start, lines, end_hint=end))
        else:
            chunks.append({
                "path": path,
                "start_line": start,
                "end_line": end,
                "symbol": node.name,
                "symtype": symtype,
                "text": slice_lines(start, end),
            })
    if not chunks and total > 0:
        # No symbols found (e.g. script-only file) -> caller falls back to sliding.
        return []
    # Fill ids/hashes/tokens.
    for chunk in chunks:
        chunk["text_hash"] = _text_hash(chunk["text"])
        chunk["token_est"] = token_estimate(chunk["text"])
        chunk["id"] = chunk_id(path, chunk["start_line"], chunk["end_line"], chunk["text_hash"])
    _ = total
    return chunks


def _split_oversized(
    path: str,
    symbol: str,
    start: int,
    lines: list[str],
    end_hint: int | None = None,
    max_lines: int = CHUNK_MAX_LINES,
) -> list[dict]:
    """Split an oversized symbol region into overlapping windows."""
    total = len(lines)
    end = end_hint or total
    out: list[dict] = []
    cursor = start
    while cursor <= end:
        window_end = min(cursor + max_lines - 1, end)
        text = "\n".join(lines[cursor - 1 : window_end])
        text_hash = _text_hash(text)
        out.append({
            "path": path,
            "start_line": cursor,
            "end_line": window_end,
            "symbol": symbol,
            "symtype": "block",
            "text": text,
            "text_hash": text_hash,
            "token_est": token_estimate(text),
            "id": chunk_id(path, cursor, window_end, text_hash),
        })
        if window_end >= end:
            break
        cursor = window_end - SLIDING_OVERLAP + 1
    return out


def chunk_sliding(
    path: str,
    text: str,
    window: int = SLIDING_LINES,
    stride: int = SLIDING_STRIDE,
) -> list[dict]:
    """Sliding-window chunker for non-Python or unparseable files."""
    lines = text.splitlines()
    total = len(lines)
    if total == 0:
        return []
    out: list[dict] = []
    cursor = 1
    while cursor <= total:
        window_end = min(cursor + window - 1, total)
        chunk_text = "\n".join(lines[cursor - 1 : window_end])
        text_hash = _text_hash(chunk_text)
        out.append({
            "path": path,
            "start_line": cursor,
            "end_line": window_end,
            "symbol": Path(path).name,
            "symtype": "block",
            "text": chunk_text,
            "text_hash": text_hash,
            "token_est": token_estimate(chunk_text),
            "id": chunk_id(path, cursor, window_end, text_hash),
        })
        if window_end >= total:
            break
        cursor += stride
    return out


def chunk_file(
    path: str,
    text: str,
    is_python: bool,
    max_lines: int = CHUNK_MAX_LINES,
) -> list[dict]:
    """Chunk a single file. Python -> symbols, else sliding window."""
    if is_python:
        symbols = chunk_python_symbols(path, text, max_lines=max_lines)
        if symbols:
            return symbols
    return chunk_sliding(path, text)
