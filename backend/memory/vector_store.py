# PIP Memory layer - Vector Store (ChromaDB)
#
# Startup Rebuild Trigger:
# ChromaDB is NEVER authoritative. If ChromaDB drifts from SQLite, a startup
# rebuild-on-mismatch trigger re-indexes from SQLite's authoritative state.
#
# That trigger is check_consistency() -> rebuild_if_drifted(), called from
# server.py's _catch_up_blocking(). Named here because this paragraph spent a long
# time describing behavior that did not exist anywhere: the rebuild function was
# written, was correct, and was reachable only from a backup restore. Anyone
# reading this header had every reason to believe an emptied index would repair
# itself, and for two days on a live installation it did not.
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
from backend.memory import profile_store

logger = logging.getLogger(__name__)

_DEFAULT_CHROMA_DB_PATH = str(Path(__file__).parent.parent.parent / "data" / "chroma")


def chroma_path() -> str:
    """
    Where this profile's vector index lives.

    PIP_CHROMA_PATH so each profile gets its own. Two profiles sharing one
    Chroma directory would not leak content - chunk ids and metadata are keyed
    with an HMAC of the live key, so one profile cannot address the other's
    chunks - but they would accumulate in one directory forever, each profile
    carrying dead weight it can neither read nor delete.

    Read at call time rather than at import. An import-time constant cannot be
    isolated by a fixture, because collection has already happened by the time
    one runs - so putting the variable in conftest's table while reading it
    once at import would have declared an isolation that did not exist.
    """
    return os.environ.get("PIP_CHROMA_PATH") or _DEFAULT_CHROMA_DB_PATH


# Retained because the test suite and restore_backup.py monkeypatch and read
# it by name. chroma_path() is what _get_client() actually consults, and it
# prefers this module attribute when something has replaced it - so an
# existing monkeypatch keeps working and an environment override keeps working,
# without two sources of truth disagreeing at runtime.
CHROMA_DB_PATH = _DEFAULT_CHROMA_DB_PATH
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
        # The module attribute wins when a test has replaced it; otherwise the
        # environment, then the default.
        path = CHROMA_DB_PATH if CHROMA_DB_PATH != _DEFAULT_CHROMA_DB_PATH else chroma_path()
        _client = chromadb.PersistentClient(path=path)
    return _client


def _get_collection():
    global _collection
    if _collection is None:
        _collection = _get_client().get_or_create_collection(COLLECTION_NAME)
    return _collection


def reset_client() -> None:
    """
    Forget the cached client and collection, so the next call opens whatever
    PIP_CHROMA_PATH now says.

    Needed because switching profiles no longer means a new process. The client
    is cached for the life of the module and holds an open handle on one
    directory, so a switch that did not clear it would leave the second profile
    reading and writing the first profile's index - not a leak of content
    (chunk ids are keyed with an HMAC of the live key, so one profile cannot
    address the other's chunks) but a silent accumulation of unreadable weight
    in a directory that does not belong to it, and an ingest that appears to
    work while landing nowhere the owner can find.

    Not a close(). Chroma's PersistentClient has no documented shutdown that is
    safe to call while another thread may be mid-query, and dropping the
    reference is what the process already relies on at exit. The SQLite handle
    underneath is released when the last reference goes.
    """
    global _client, _collection
    _client = None
    _collection = None


def _get_model() -> SentenceTransformer:
    """
    The embedding model, loaded once per process, from local disk when possible.

    local_files_only=True is worth a great deal more than it looks. Without it,
    SentenceTransformer contacts the HuggingFace Hub to check for updates on
    every load - even though the model is pinned by name and already cached -
    and that call has to complete before PIP can embed anything.

    Measured on this machine: 87.22s to load with the check, 0.24s without. The
    weights themselves read in under a second; the rest was one network round
    trip. The cause was local (huggingface.co advertises 8 IPv6 addresses, this
    machine has no working IPv6 route, and each attempt burned its timeout
    before falling back to IPv4) but the lesson is not: a pinned, cached model
    should not need the network to load, and any network it does touch can be
    slow or absent on someone else's machine.

    It also removes an outbound call this application should not have been
    making. PIP is local-first by design - its threat model treats other local
    processes as untrusted - and it was quietly reaching a CDN on every start.

    The fallback keeps a fresh machine working: no cached copy means
    local_files_only raises, and that one time we fetch it properly. So the
    first run downloads, and every run after is offline and fast.
    """
    global _model
    if _model is None:
        try:
            _model = SentenceTransformer(EMBEDDING_MODEL_NAME, device="cpu", local_files_only=True)
        except Exception as e:
            logger.info(
                f"Embedding model {EMBEDDING_MODEL_NAME} is not in the local cache "
                f"({type(e).__name__}); downloading it once."
            )
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
        document_id = existing["id"]
    else:
        cursor = conn.execute(
            "INSERT INTO documents (project_id, file_path, content_hash, chunk_count, status, ingested_at) "
            "VALUES (?, ?, ?, ?, 'active', ?)",
            (project_id, file_path, content_hash, len(chunks), timestamp),
        )
        document_id = cursor.lastrowid
    conn.commit()

    # The bytes, not just the record of them. Without this the documents table
    # describes files that only exist on the machine that ingested them, and a
    # restore elsewhere brings back a registry nothing can satisfy.
    #
    # Read from disk again rather than reusing the extracted text: what belongs
    # here is the FILE, byte for byte. _extract_text() returns the readable
    # text of a PDF, which is not a PDF - storing that would restore something
    # that no longer opens in the application it came from, and would re-chunk
    # differently on the next rebuild.
    profile_store.store_document_content(conn, document_id, resolved_path.read_bytes())

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
    """
    The REGISTRY of what should be indexed - metadata only, straight from
    SQLite. chunk_count here is what ingestion recorded, not what ChromaDB
    currently holds, and nothing in this function goes near the vector index.

    Worth saying out loud because the Documents screen renders it as though it
    were the index: "56 chunks" beside a file name reads as a fact about
    retrieval, and stays on screen unchanged when the index behind it is
    empty. check_consistency() below is the thing that can tell the difference.
    """
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

        # A project-scoped query reaches that project's documents AND the
        # unfiled ones - project_id "" as ingest_document writes it when no
        # project was active.
        #
        # It used to be an equality match on the project alone, which quietly
        # made every unfiled document unreachable the moment anyone activated
        # a project. That is not a corner case: the Documents screen has no
        # project picker, so it files an upload under whatever project happens
        # to be active at the time, and "none" is what that is for anyone who
        # uploads before organising their work. On this installation it was
        # all four documents and all 85 chunks - PIP held them, listed them,
        # reported their chunk counts, and could not retrieve one of them
        # while a project was open.
        #
        # An unfiled document is not a document belonging to some other
        # project; it is a general reference nobody has sorted yet, and the
        # useful reading of "no project" is "any project". Documents that WERE
        # filed stay scoped - the point is to stop treating absence of a label
        # as a label.
        where = (
            {"$or": [{"project_id": project_id}, {"project_id": ""}]}
            if project_id
            else None
        )
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
        # Chroma's default space is l2, which returns SQUARED euclidean distance.
        # For unit vectors ||a-b||^2 = 2 - 2cos, so 1 - d/2 recovers cosine exactly -
        # and all-MiniLM-L6-v2 ends in a Normalize module, so its output is unit
        # length. Verified against chromadb 1.5.9: a pair with cosine 0.5403 comes
        # back at distance 0.9194, and 1 - 0.9194/2 = 0.5403.
        #
        # This comment used to describe the space as cosine distance in [0,2], which
        # is a different quantity that happens to produce the same formula, so the
        # number was right for a reason that was not. Worth being exact about,
        # because the fix is not symmetric: creating this collection with
        # metadata={"hnsw:space": "cosine"} would make distance = 1 - cos, and this
        # line would then report (1 + cos)/2 - every score wrong, none of them
        # obviously so, and similarity_threshold silently meaning something else.
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


def _chunk_count_in_chroma(collection, file_path: str, db_key: Optional[str]) -> int:
    """
    How many chunks the index actually holds for one document.

    Counted through the same key the write path writes under - the HMAC
    file_key when encryption is on, the plain path when it is not - so this
    asks the question retrieval asks, rather than a question that merely looks
    like it. A chunk written under a different key is correctly counted as
    absent here, because that is exactly what it is to query().
    """
    where = {"file_key": _file_key(db_key, file_path)} if db_key else {"file_path": file_path}
    return len(collection.get(where=where, include=[]).get("ids") or [])


def check_consistency(conn) -> dict[str, Any]:
    """
    Compares SQLite's documents registry against what ChromaDB actually holds.

    This is the check the module header at the top of this file has always
    said fires at startup. It did not exist. The consequence was not
    theoretical: this installation's Chroma directory was moved aside during
    the encryption migration (chunks written before PIP_DB_KEY existed cannot
    be decrypted under it, so replacing the directory was right), the rebuild
    that should have followed never ran, and PIP answered questions for two
    days with an empty index. Stage 5 returned nothing every time, every
    answer came from the Decision Log and profile alone, and the Documents
    screen went on reporting 85 healthy chunks the whole time - because it
    reads list_documents(), which is metadata (see its docstring).

    Nothing failed loudly because nothing was failing: an empty index is
    indistinguishable, from inside query(), from a question no document
    happens to answer. That is what makes this worth a startup check rather
    than a log line - the failure mode is silence, and silence is also what
    success looks like.

    Reported per document, not as one total. A total hides the case a check
    like this most needs to catch: one document missing while another's count
    absorbs the difference.
    """
    active = list_documents(conn)
    if not active:
        # Nothing registered means nothing to verify, and no reason to open a
        # collection on a fresh install just to confirm it is empty.
        return {"documents": 0, "indexed": 0, "expected": 0, "drifted": [], "ok": True}

    collection = _get_collection()
    db_key = _get_db_key()

    drifted, indexed, expected = [], 0, 0
    for doc in active:
        want = doc["chunk_count"] or 0
        expected += want
        try:
            have = _chunk_count_in_chroma(collection, doc["file_path"], db_key)
        except Exception as e:
            # Treat an unreadable count as drift rather than as agreement.
            # Failing open here would mean failing silent, which is the whole
            # bug this function exists to end.
            logger.warning(f"Consistency check could not count chunks for {doc['file_path']}: {e}")
            drifted.append({"file_path": doc["file_path"], "expected": want, "indexed": None})
            continue
        indexed += have
        if have != want:
            drifted.append({"file_path": doc["file_path"], "expected": want, "indexed": have})

    return {
        "documents": len(active),
        "indexed": indexed,
        "expected": expected,
        "drifted": drifted,
        "ok": not drifted,
    }


def rebuild_if_drifted(conn) -> dict[str, Any]:
    """
    The rebuild-on-mismatch trigger, finally wired to something.

    rebuild_from_sqlite() has been correct and callable since it was written;
    its only caller was scripts/restore_backup.py, so the drift it repairs got
    repaired only when someone happened to restore a backup for an unrelated
    reason. A recovery path nothing invokes is indistinguishable from one that
    does not exist, and this file's own header describing it as automatic made
    it worse than absent - it told every later reader the case was handled.

    Returns the check result either way, with the rebuild's own result folded
    in when one ran, so the caller can log what was found as well as what was
    done.
    """
    report = check_consistency(conn)
    if report["ok"]:
        return report

    logger.warning(
        f"Vector index disagrees with the document registry "
        f"({report['indexed']} chunks indexed, {report['expected']} expected across "
        f"{report['documents']} document(s)); rebuilding."
    )
    report["rebuild"] = rebuild_from_sqlite(conn)
    return report


def rebuild_from_sqlite(conn) -> dict[str, Any]:
    """
    Re-ingests every active document from its recorded file_path. Called at startup
    by rebuild_if_drifted() when the registry and the index disagree (Part 11.1
    rebuild-on-mismatch trigger), and by scripts/restore_backup.py.

    Does NOT remove chunks whose file_path is no longer active - this docstring
    used to claim it did, and nothing did. delete_document() is what clears a
    removed document's chunks, and it does so at the moment of removal, so the
    orphans this would collect can only come from drift severe enough that a
    rebuild is running anyway. Left as a known gap rather than silently
    widened into a delete pass: this function runs unattended at startup now,
    and unattended deletion of data the caller did not ask about is a bigger
    promise than a rebuild should make.
    """
    # Put back anything whose bytes we hold but whose file is not here. This is
    # what makes a rebuild work on a restored machine: every recorded path
    # points somewhere that has never existed on it, and re-embedding cannot
    # start until the files do.
    materialised = profile_store.materialise_documents(conn)

    active_docs = list_documents(conn)
    rebuilt, failed = [], []

    for doc in active_docs:
        try:
            if not Path(doc["file_path"]).exists():
                failed.append({
                    "file_path": doc["file_path"],
                    "reason": "file not found on disk, and no stored copy in the database",
                })
                continue
            ingest_document(conn, doc["file_path"], doc["project_id"], force=True)
            rebuilt.append(doc["file_path"])
        except Exception as e:
            failed.append({"file_path": doc["file_path"], "reason": str(e)})

    return {"rebuilt": rebuilt, "failed": failed, "materialised": materialised["written"]}
