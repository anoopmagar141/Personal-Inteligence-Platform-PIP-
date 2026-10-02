"""
TEST-TOOLING WORKAROUND, NOT PART OF PIP.

Windows Smart App Control on this machine blocks torch's unsigned
torch_global_deps.dll (WinError 4551), so `sentence_transformers` cannot be
imported and every test that imports backend.api.server fails at collection.

This pytest plugin installs a stand-in `sentence_transformers` module before
collection. Its encoder is a deterministic hashed bag-of-words (384 dims, L2
normalised), so lexical overlap still ranks documents, but it is NOT the real
all-MiniLM model. Results that depend on semantic embedding quality are
invalid under this shim and are reported as tooling-limited.

Load with:  python -m pytest -p pip_embed_shim ...   (scratch dir on PYTHONPATH)
"""
import hashlib
import math
import re
import sys
import types

DIM = 384


def _vec(text: str) -> list[float]:
    v = [0.0] * DIM
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        h = int.from_bytes(hashlib.sha256(tok.encode()).digest()[:4], "big")
        v[h % DIM] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class _Arr(list):
    def tolist(self):
        return [list(r) for r in self] if self and isinstance(self[0], list) else list(self)


class SentenceTransformer:  # noqa: D101
    def __init__(self, *a, **k):
        pass

    def encode(self, texts, convert_to_numpy=True, **k):
        if isinstance(texts, str):
            return _Arr(_vec(texts))
        return _Arr([_vec(t) for t in texts])

    def get_sentence_embedding_dimension(self):
        return DIM


mod = types.ModuleType("sentence_transformers")
mod.SentenceTransformer = SentenceTransformer
mod.__pip_shim__ = True
sys.modules["sentence_transformers"] = mod
