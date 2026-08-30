# PIP Memory layer - Vector Store (ChromaDB)
#
# Startup Rebuild Trigger:
# ChromaDB is NEVER authoritative. If ChromaDB drifts from SQLite (schema version mismatch
# or document list discrepancy), a startup rebuild-on-mismatch trigger is fired to
# clear ChromaDB and re-index from SQLite authoritative state.
#
# SQLite's `documents` table (schema.sql table 19) is the source-of-truth registry of what
# should be ingested. It stores metadata only (file_path, content_hash, chunk_count) - not
# chunk text. "Rebuild from SQLite" means: re-read the original files at their recorded
# file_path and re-run ingestion, using the documents table only to know WHICH files should
# exist in ChromaDB and whether their on-disk content has changed since last ingest.
#
# Embedding model: all-MiniLM-L6-v2, CPU-only (Part 6.3: preserve GPU headroom for the LLM).
# KNOWN TRADEOFF: this model's max_seq_length is 256 tokens, but chunk_size_tokens in
# settings.json is 500. Chunks longer than ~256 tokens get truncated *for embedding purposes
# only* - the full chunk text is still stored and still returned to Stage 7 context assembly,
# so nothing is lost for the LLM. Only the semantic-search relevance of content past token
# ~256 within a chunk degrades. This is the same class of imprecision the project already
# accepts for similarity_threshold ("start 0.6, calibrate from 100 real interactions") -
# revisit chunk_size_tokens or the embedding model choice once there's real usage data.

import base64
import hashlib
import hmac
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

import chromadb
from cryptography.fernet import Fernet, InvalidToken
from sentence_transformers import SentenceTransformer

from backend.config.settings import get_settings
from backend.core.types import now_utc

logger = logging.getLogger(__name__)

CHROMA_DB_PATH = str(Path(__file__).parent.parent.parent / "data" / "chroma")
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
COLLECTION_NAME = "documents"

# Every RAG tunable is read from config/settings.json rather than restated here.
# The values were previously duplicated - as this module constant and as default
# arguments on ingest_document()/query() - which meant editing settings.json
# changed nothing at all, silently. That is the worse half of the failure: a
# configuration file that is read by no one still LOOKS authoritative, so the
# next person to tune similarity_threshold has no reason to suspect their edit
# did not take.
_RAG = get_settings()["rag"]

SUPPORTED_EXTENSIONS = set(_RAG["supported_extensions"])
DEFAULT_CHUNK_SIZE_TOKENS = _RAG["chunk_size_tokens"]
DEFAULT_CHUNK_OVERLAP_TOKENS = _RAG["chunk_overlap_tokens"]
DEFAULT_SIMILARITY_THRESHOLD = _RAG["similarity_threshold"]
DEFAULT_TOP_K = _RAG["top_k_results"]
DEFAULT_MAX_DOCUMENT_SIZE_MB = _RAG["max_document_size_mb"]


# Security review finding: ChromaDB's on-disk store (chroma.sqlite3 under
# CHROMA_DB_PATH) was completely unencrypted, unlike the SQLCipher-protected
# main database - anyone with filesystem access could read every ingested
# document's full text straight off disk. This reuses PIP_DB_KEY (the same
# hex key SQLCipher is keyed with, read the same way _conn() reads it in
# server.py) to derive a Fernet key and encrypts chunk text and the
# human-readable file path before either ever reaches Chroma.
#
# Embeddings themselves stay plaintext - Chroma's ANN index has to do real
# vector math over them, and there's no practical way to run a similarity
# search over ciphertext with this library. That's a documented, accepted
# residual risk (recovering exact source text from an embedding vector alone
# is hard but not provably impossible given model access), not a gap in this
# fix - the actual human-readable content (chunk text, file path) is what's
# protected.
#
# file_path can't be encrypted with plain Fernet on the value Chroma
# filters/deletes by - Fernet is non-deterministic (a random IV per call), so
# encrypting the same path twice gives two different ciphertexts and a
# `where=` equality match would silently stop finding a file's own chunks.
# Instead HMAC-SHA256(db_key, file_path) is used as the stable, deterministic
# lookup key (same path -> same digest, but the digest doesn't reveal the
# path), while the actual path is stored separately, Fernet-encrypted, purely
# for display once a query has already found the right chunks.
#
# When PIP_DB_KEY isn't set at all (dev/test default, same as
# profile_store.get_connection()'s unencrypted sqlite3 fallback), everything
# below is a no-op passthrough - chunks and file_path are stored and read
# back as plain text, exactly as before this fix.
def _get_db_key() -> Optional[str]:
    return os.environ.get("PIP_DB_KEY") or None


def _fernet(db_key: str) -> Fernet:
    if not re.fullmatch(r"[0-9a-fA-F]+", db_key):
        raise ValueError("PIP_DB_KEY must be hex-encoded")
    digest = hashlib.sha256(bytes.fromhex(db_key)).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _file_key(db_key: str, file_path: str) -> str:
    return hmac.new(bytes.fromhex(db_key), file_path.encode("utf-8"), hashlib.sha256).hexdigest()


# Security fix: ingest_document() used to pass file_path straight into
# Path(file_path).stat()/.read_text()/PdfReader(file_path) with no validation
# at all - any caller (this endpoint is behind the global token auth now, see
# auth.py/server.py, but wasn't when this fix was written) could make PIP
# read and embed an arbitrary file from anywhere the process can
# access (SSH keys, credential files, source with secrets in it - the
# SUPPORTED_EXTENSIONS allowlist doesn't meaningfully block this, since .txt/
# .json/.py cover most of what an attacker would actually want). The embedded
# content then sits in ChromaDB, retrievable via the equally unauthenticated
# rag/query endpoint or surfacing on its own in later chat answers. Every
# ingest now must resolve inside this directory - files the user wants
# indexed have to actually be placed here first.
DOCUMENTS_ROOT = Path(__file__).parent.parent.parent / "data" / "documents"

_client = None
_collection = None
_model = None


def _get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    return _client


def _get_collection():
    global _collection
    if _collection is None:
        _collection = _get_client().get_or_create_collection(COLLECTION_NAME)
    return _collection


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME, device="cpu")
    return _model


def _extract_text(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported document extension: {ext}")

    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    if ext == ".html":
        raw = Path(file_path).read_text(encoding="utf-8", errors="replace")
        return re.sub(r"<[^>]+>", " ", raw)

    return Path(file_path).read_text(encoding="utf-8", errors="replace")


def _chunk_text(text: str, chunk_size_tokens: int = 500, overlap_tokens: int = 50) -> list[str]:
    """
    Word-count-based chunking approximation, not a real BPE tokenizer. This under-counts
    true token count (subword tokenizers typically split words into 1+ tokens each), so
    a "500 token" chunk by this measure will usually be somewhat larger in a real
    tokenizer's count - already priced into the embedding-truncation tradeoff documented
    at the top of this file.
    """
    words = text.split()
    if not words:
        return []

    step = max(chunk_size_tokens - overlap_tokens, 1)
    chunks = []
    for start in range(0, len(words), step):
        chunk_words = words[start:start + chunk_size_tokens]
        if chunk_words:
            chunks.append(" ".join(chunk_words))
        if start + chunk_size_tokens >= len(words):
            break
    return chunks


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _validate_file_path(file_path: str) -> Path:
    """
    Resolves file_path and rejects anything outside DOCUMENTS_ROOT - the only
    thing standing between an ingest call and reading an arbitrary file on
    disk. Path.resolve() collapses '..' segments and symlinks before the
    is_relative_to() check, so "data/documents/../../.ssh/id_rsa" is caught
    the same as an absolute path pointed straight at it.
    """
    root = DOCUMENTS_ROOT.resolve()
    resolved = Path(file_path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(
            f"file_path must resolve inside {root} (got: {resolved}). "
            f"Move the file into {root} (subdirectories are fine) and retry."
        )
    return resolved


def ingest_document(
    conn,
    file_path: str,
    project_id: Optional[str] = None,
    *,
    chunk_size_tokens: int | None = None,
    overlap_tokens: int | None = None,
    force: bool = False,
    max_document_size_mb: int | None = None,
) -> dict[str, Any]:
    """
    Extracts text, chunks it, embeds each chunk, writes chunks+embeddings to ChromaDB,
    and records the ingestion in the SQLite `documents` table (source of truth).
    Re-ingesting the same file_path replaces its previous chunks.

    force=True bypasses the unchanged-hash shortcut. This matters for
    rebuild_from_sqlite(): the whole point of a rebuild is to restore ChromaDB after
    it has drifted out of sync with SQLite (e.g. its chunks were lost or corrupted)
    while the on-disk file itself never changed - trusting the hash in that case
    would silently skip the very re-ingestion the rebuild exists to perform.
    """
    chunk_size_tokens = DEFAULT_CHUNK_SIZE_TOKENS if chunk_size_tokens is None else chunk_size_tokens
    overlap_tokens = DEFAULT_CHUNK_OVERLAP_TOKENS if overlap_tokens is None else overlap_tokens
    max_document_size_mb = (
        DEFAULT_MAX_DOCUMENT_SIZE_MB if max_document_size_mb is None else max_document_size_mb
    )

    resolved_path = _validate_file_path(file_path)
    file_path = str(resolved_path)  # store/key everything by the canonical path from here on

    size_mb = resolved_path.stat().st_size / (1024 * 1024)
    if size_mb > max_document_size_mb:
        raise ValueError(
            f"{file_path} is {size_mb:.1f}MB, exceeds max_document_size_mb ({max_document_size_mb})"
        )

    text = _extract_text(file_path)
    content_hash = _content_hash(text)
    chunks = _chunk_text(text, chunk_size_tokens, overlap_tokens)

    existing = conn.execute(
        "SELECT id, content_hash FROM documents WHERE file_path = ? AND status = 'active'",
        (file_path,),
    ).fetchone()

    if not force and existing and existing["content_hash"] == content_hash:
        return {"status": "unchanged", "file_path": file_path, "chunk_count": len(chunks)}

    collection = _get_collection()
    db_key = _get_db_key()

    if existing:
        _delete_chunks_for_path(collection, file_path, db_key)

    if chunks:
        embeddings = _get_model().encode(chunks, convert_to_numpy=True).tolist()
        if db_key:
            fernet = _fernet(db_key)
            file_key = _file_key(db_key, file_path)
            ids = [f"{file_key}::{i}" for i in range(len(chunks))]
            documents = [fernet.encrypt(c.encode("utf-8")).decode("ascii") for c in chunks]
            file_path_enc = fernet.encrypt(file_path.encode("utf-8")).decode("ascii")
            metadatas = [
                {"file_key": file_key, "file_path_enc": file_path_enc, "project_id": project_id or "", "chunk_index": i}
                for i in range(len(chunks))
            ]
        else:
            ids = [f"{file_path}::{i}" for i in range(len(chunks))]
            documents = chunks
            metadatas = [{"file_path": file_path, "project_id": project_id or "", "chunk_index": i} for i in range(len(chunks))]
        collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

    timestamp = now_utc()
    if existing:
        conn.execute(
            "UPDATE documents SET content_hash = ?, chunk_count = ?, ingested_at = ?, project_id = ? WHERE id = ?",
            (content_hash, len(chunks), timestamp, project_id, existing["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO documents (project_id, file_path, content_hash, chunk_count, status, ingested_at) "
            "VALUES (?, ?, ?, ?, 'active', ?)",
            (project_id, file_path, content_hash, len(chunks), timestamp),
        )
    conn.commit()

    return {"status": "ingested", "file_path": file_path, "chunk_count": len(chunks)}


def _delete_chunks_for_path(collection, file_path: str, db_key: Optional[str]) -> None:
    if db_key:
        collection.delete(where={"file_key": _file_key(db_key, file_path)})
    else:
        collection.delete(where={"file_path": file_path})


def delete_document(conn, file_path: str) -> bool:
    row = conn.execute(
        "SELECT id FROM documents WHERE file_path = ? AND status = 'active'", (file_path,)
    ).fetchone()
    if not row:
        return False

    _delete_chunks_for_path(_get_collection(), file_path, _get_db_key())
    conn.execute(
        "UPDATE documents SET status = 'removed' WHERE id = ?", (row["id"],)
    )
    conn.commit()
    return True


def list_documents(conn) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM documents WHERE status = 'active'")]


def query(
    conn,
    query_text: str,
    project_id: Optional[str] = None,
    threshold: float | None = None,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """
    Returns chunks above the similarity threshold, highest similarity first.
    Failure mode: any ChromaDB error returns an empty list (Stage 5 spec: fail open).

    threshold/top_k default from config/settings.json (rag.similarity_threshold,
    rag.top_k_results). None rather than the literal values as defaults, so the
    setting is resolved per call - a default argument would bind at import and
    quietly ignore any later change.
    """
    threshold = DEFAULT_SIMILARITY_THRESHOLD if threshold is None else threshold
    top_k = DEFAULT_TOP_K if top_k is None else top_k
    try:
        collection = _get_collection()
        query_embedding = _get_model().encode([query_text], convert_to_numpy=True).tolist()

        where = {"project_id": project_id} if project_id else None
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=top_k,
            where=where,
        )
    except Exception as e:
        logger.error(f"RAG query failed, returning empty: {e}")
        return []

    matches = []
    docs = results.get("documents") or [[]]
    metadatas = results.get("metadatas") or [[]]
    distances = results.get("distances") or [[]]

    db_key = _get_db_key()
    fernet = _fernet(db_key) if db_key else None

    for doc, meta, distance in zip(docs[0], metadatas[0], distances[0]):
        # Chroma's default space is L2 distance; convert to a 0-1 similarity-like score.
        # cosine distance in [0,2] -> similarity = 1 - distance/2 stays in [0,1] for
        # normalized embeddings (sentence-transformers embeddings are normalized).
        similarity = 1 - (distance / 2)
        if similarity < threshold:
            continue

        if fernet:
            # (InvalidToken, KeyError) both mean "this chunk wasn't written
            # under the current key/schema" - e.g. it predates PIP_DB_KEY
            # being set, or the key changed. Skip it rather than crash the
            # whole query; rebuild_from_sqlite() is the real fix for stale
            # entries like that, not something this read path should paper
            # over silently returning garbage for.
            try:
                chunk_text = fernet.decrypt(doc.encode("ascii")).decode("utf-8")
                file_path = fernet.decrypt(meta["file_path_enc"].encode("ascii")).decode("utf-8")
            except (InvalidToken, KeyError):
                logger.error("RAG query: could not decrypt a chunk (key mismatch or pre-encryption data), skipping")
                continue
        else:
            chunk_text = doc
            file_path = meta.get("file_path")

        matches.append({
            "chunk_text": chunk_text,
            "file_path": file_path,
            "chunk_index": meta.get("chunk_index"),
            "similarity": similarity,
        })

    return matches


def rebuild_from_sqlite(conn) -> dict[str, Any]:
    """
    Re-ingests every active document from its recorded file_path, and removes any
    ChromaDB chunks for file_paths no longer marked active in SQLite. Called at startup
    when a schema-version or document-count mismatch is detected between SQLite and
    ChromaDB (Part 11.1 rebuild-on-mismatch trigger).
    """
    active_docs = list_documents(conn)
    rebuilt, failed = [], []

    for doc in active_docs:
        try:
            if not Path(doc["file_path"]).exists():
                failed.append({"file_path": doc["file_path"], "reason": "file not found on disk"})
                continue
            ingest_document(conn, doc["file_path"], doc["project_id"], force=True)
            rebuilt.append(doc["file_path"])
        except Exception as e:
            failed.append({"file_path": doc["file_path"], "reason": str(e)})

    return {"rebuilt": rebuilt, "failed": failed}
