"""Embedding providers for semantic search.

The default :class:`LocalHashingEmbedder` is dependency-free and deterministic:
it builds an L2-normalized hashed bag-of-words vector. It is not a transformer,
but it captures lexical overlap well enough for dev, tests, and small datasets,
and keeps the pipeline (index-time + query-time embedding, cosine ranking)
identical to what a production model would use.

To plug a real model in production, implement :class:`EmbeddingProvider`
(e.g. wrapping ``sentence-transformers`` or a hosted embeddings API) and select
it in :func:`get_embedder`.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from app.core.config import settings

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class EmbeddingProvider(Protocol):
    dim: int

    def embed(self, text: str) -> list[float]: ...


class LocalHashingEmbedder:
    """Deterministic hashed bag-of-words embedder with the hashing trick."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def _token_slot(self, token: str) -> tuple[int, float]:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        h = int.from_bytes(digest, "big")
        index = h % self.dim
        sign = 1.0 if (h >> 1) & 1 else -1.0  # signed hashing reduces collisions
        return index, sign

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _tokenize(text):
            index, sign = self._token_slot(token)
            vec[index] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            return vec
        return [v / norm for v in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity. Inputs from this module are pre-normalized, so this is
    effectively a dot product, but we normalize defensively."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


_embedder: EmbeddingProvider | None = None


def get_embedder() -> EmbeddingProvider:
    """Return the process-wide embedder selected by configuration."""
    global _embedder
    if _embedder is None:
        if settings.EMBEDDING_PROVIDER == "local":
            _embedder = LocalHashingEmbedder(dim=settings.EMBEDDING_DIM)
        else:  # pragma: no cover - future hosted/transformer providers
            raise ValueError(
                f"Unknown EMBEDDING_PROVIDER: {settings.EMBEDDING_PROVIDER!r}"
            )
    return _embedder
