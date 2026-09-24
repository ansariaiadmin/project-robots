"""Store — SQLite index (FTS5 + metadata + embeddings) under .cache/<slug>/rag/."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from robots.common import cache_dir, load_config, read_text, source_state, tracked_files
from robots.rag.chunker import chunk_file, token_estimate

TOOL_VERSION = "rag-1.0.0"
INDEX_DB = "index.sqlite"
META_FILE = "meta.json"


def rag_dir(project: Path) -> Path:
    path = cache_dir(project, "rag")
    path.mkdir(parents=True, exist_ok=True)
    return path


def index_db_path(project: Path) -> Path:
    return rag_dir(project) / INDEX_DB


def meta_path(project: Path) -> Path:
    return rag_dir(project) / META_FILE


def load_meta(project: Path) -> dict | None:
    meta_file = meta_path(project)
    if not meta_file.is_file():
        return None
    try:
        return json.loads(meta_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def is_fresh(project: Path, config: dict) -> tuple[bool, dict | None, dict]:
    """Check whether stored index matches current sourceState."""
    current = source_state(project, config)
    meta = load_meta(project)
    if meta is None or not index_db_path(project).is_file():
        return False, meta, current
    return meta.get("sourceState") == current, meta, current


def _connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA journal_mode=DELETE")
    con.execute("PRAGMA synchronous=NORMAL")
    return con


def _init_schema(con: sqlite3.Connection) -> str:
    con.execute(
        "CREATE TABLE IF NOT EXISTS chunks("
        "id TEXT PRIMARY KEY, path TEXT, start_line INTEGER, end_line INTEGER,"
        "symbol TEXT, symtype TEXT, layer TEXT, text TEXT, text_hash TEXT,"
        "token_est INTEGER, churn INTEGER, complexity INTEGER, imports_json TEXT)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS embeddings("
        "chunk_id TEXT PRIMARY KEY, dim INTEGER, vec BLOB, model TEXT)"
    )
    # Prefer porter tokenizer, fall back to unicode61.
    try:
        con.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING "
            "fts5(chunk_id UNINDEXED, text, symbol, path, "
            "tokenize='porter unicode61')"
        )
        return "porter"
    except sqlite3.OperationalError:
        con.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING "
            "fts5(chunk_id UNINDEXED, text, symbol, path)"
        )
        return "unicode61"


def _enrichment(project: Path, config: dict) -> tuple[dict, dict, dict]:
    """Best-effort layer/churn/complexity from intelligence builders."""
    layers: dict[str, str] = {}
    churn: dict[str, int] = {}
    complexity: dict[str, int] = {}
    try:
        from robots.intelligence.architecture import detect_architecture
        from robots.intelligence.graph_builder import build_import_graph

        graph = build_import_graph(project, config)
        arch = detect_architecture(project, config, graph)
        layers = dict(arch.layer_of_file)
        for rel, node in graph.items():
            complexity[rel] = len(node.symbols) + len(node.imports)
    except Exception:
        pass
    try:
        from robots.intelligence.coupling import analyze_coupling

        matrix = analyze_coupling(project, config)
        churn = dict(matrix.file_frequency)
    except Exception:
        pass
    return layers, churn, complexity


def build_index(
    project: Path,
    config: dict,
    force: bool = False,
    chunk_max_lines: int = 120,
    no_embed: bool = False,
) -> dict:
    """Build (or reuse) the RAG index. Returns index info dict."""
    from robots.rag import vectors as vec_mod

    fresh, meta, current = is_fresh(project, config)
    db_path = index_db_path(project)
    if fresh and not force and meta is not None:
        return {
            "reused": True,
            "chunks": int(meta.get("chunkCount", 0)),
            "stale": False,
            "embed": str(meta.get("embedModel", "heuristic")),
            "secretsSkipped": int(meta.get("secretsSkipped", 0)),
            "redactedChunks": int(meta.get("redactedChunks", 0)),
            "sourceState": current,
        }
    max_bytes = int(config["limits"]["maxFileBytes"])
    files = tracked_files(project, config)
    layers, churn, complexity = _enrichment(project, config)
    from robots.autonomous.guard import is_in_scope
    from robots.brain.redact import is_secret_path, redact_text

    rows: list[dict] = []
    secrets_skipped = 0
    redacted_chunks = 0
    for abs_path in files:
        if not is_in_scope(project, abs_path):
            continue
        rel = abs_path.relative_to(project).as_posix()
        if is_secret_path(rel):
            secrets_skipped += 1
            continue
        text = read_text(abs_path, max_bytes)
        if text is None:
            continue
        is_python = abs_path.suffix.lower() == ".py"
        for chunk in chunk_file(rel, text, is_python, max_lines=chunk_max_lines):
            chunk["layer"] = layers.get(rel, "unknown")
            chunk["churn"] = int(churn.get(rel, 0))
            chunk["complexity"] = int(complexity.get(rel, 0))
            chunk["text"], redactions = redact_text(chunk["text"])
            if redactions:
                redacted_chunks += 1
                chunk["token_est"] = len(chunk["text"].encode("utf-8")) // 4 + 1
            rows.append(chunk)
    rows.sort(key=lambda c: (c["path"], c["start_line"]))

    if db_path.exists():
        db_path.unlink()
    con = _connect(db_path)
    try:
        _init_schema(con)
        con.execute("DELETE FROM chunks")
        con.execute("DELETE FROM embeddings")
        con.execute("DELETE FROM chunks_fts")
        for chunk in rows:
            con.execute(
                "INSERT INTO chunks(id,path,start_line,end_line,symbol,symtype,"
                "layer,text,text_hash,token_est,churn,complexity,imports_json)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    chunk["id"], chunk["path"], chunk["start_line"], chunk["end_line"],
                    chunk["symbol"], chunk["symtype"], chunk.get("layer", "unknown"),
                    chunk["text"], chunk["text_hash"], chunk["token_est"],
                    int(chunk.get("churn", 0)), int(chunk.get("complexity", 0)), "[]",
                ),
            )
            con.execute(
                "INSERT INTO chunks_fts(chunk_id,text,symbol,path) VALUES(?,?,?,?)",
                (chunk["id"], chunk["text"], chunk["symbol"], chunk["path"]),
            )
        # Embeddings (heuristic baseline unless external endpoint configured).
        embed_model = "heuristic"
        if not no_embed:
            texts = [c["text"] for c in rows]
            idf = vec_mod.build_idf(texts)
            for chunk in rows:
                vector = vec_mod.text_to_vector(chunk["text"], idf)
                con.execute(
                    "INSERT INTO embeddings(chunk_id,dim,vec,model) VALUES(?,?,?,?)",
                    (chunk["id"], vec_mod.DIM, vec_mod.pack_vector(vector), "heuristic"),
                )
        con.commit()
    finally:
        con.close()

    meta_payload = {
        "sourceState": current,
        "chunkCount": len(rows),
        "embedModel": embed_model,
        "toolVersion": TOOL_VERSION,
        "chunkMaxLines": chunk_max_lines,
        "secretsSkipped": secrets_skipped,
        "redactedChunks": redacted_chunks,
    }
    meta_path(project).write_text(json.dumps(meta_payload, indent=2) + "\n", encoding="utf-8")
    _ = token_estimate
    _ = load_config
    return {
        "reused": False,
        "chunks": len(rows),
        "stale": False,
        "embed": embed_model,
        "secretsSkipped": secrets_skipped,
        "redactedChunks": redacted_chunks,
        "sourceState": current,
    }


def load_chunks(project: Path) -> list[dict]:
    """Load all chunk metadata rows (without external deps)."""
    db_path = index_db_path(project)
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.execute(
            "SELECT id,path,start_line,end_line,symbol,symtype,layer,"
            "text,text_hash,token_est,churn,complexity FROM chunks"
            " ORDER BY path,start_line"
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
    finally:
        con.close()
