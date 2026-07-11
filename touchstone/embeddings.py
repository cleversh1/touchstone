"""Local embedding via sentence-transformers (all-MiniLM-L6-v2, 384-dim).

The model is loaded lazily on first use and cached as a module-level singleton,
so the (heavy) import and model load happen once per process rather than per call.
Embeddings are L2-normalized so that cosine similarity behaves consistently with
the pgvector cosine-distance operator (<=>).
"""

from __future__ import annotations

import threading

import numpy as np

from . import config

_model = None
_lock = threading.Lock()


def get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                # Imported lazily: sentence-transformers pulls in torch, which is
                # slow to import and unnecessary for CLI paths that don't embed.
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(config.EMBEDDING_MODEL)
    return _model


def embed(text: str) -> np.ndarray:
    """Return a normalized float32 embedding vector for a single string."""
    vec = get_model().encode(text, normalize_embeddings=True)
    return np.asarray(vec, dtype=np.float32)


def warm_up() -> None:
    """Force the model to load now (e.g. at server startup) so the first real
    request doesn't pay the load cost."""
    get_model()
