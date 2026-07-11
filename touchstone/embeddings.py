"""Local embedding via fastembed (ONNX all-MiniLM-L6-v2, 384-dim).

fastembed runs the same MiniLM model as sentence-transformers but through ONNX
Runtime instead of torch — a ~10x smaller footprint, no torch dependency, and
faster cold starts, which matters for container deploys.

The model is loaded lazily on first use and cached as a module-level singleton,
so the model download/load happens once per process rather than per call.
Vectors are L2-normalized for consistency; note that pgvector's cosine operator
(<=>) normalizes internally regardless, so relevance scores are unaffected.
"""

from __future__ import annotations

import threading

import numpy as np

from . import config

_model = None
_lock = threading.Lock()


def _resolve_model_name(name: str) -> str:
    """fastembed identifies MiniLM by its full Hub name; accept the short form too."""
    return name if "/" in name else f"sentence-transformers/{name}"


def get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                # Imported lazily so CLI paths that never embed don't pay the cost.
                from fastembed import TextEmbedding

                _model = TextEmbedding(
                    model_name=_resolve_model_name(config.EMBEDDING_MODEL)
                )
    return _model


def embed(text: str) -> np.ndarray:
    """Return a normalized float32 embedding vector for a single string."""
    vec = np.asarray(next(iter(get_model().embed([text]))), dtype=np.float32)
    norm = float(np.linalg.norm(vec))
    if norm > 0.0:
        vec = vec / norm
    return vec


def warm_up() -> None:
    """Force the model to load now (e.g. at server startup) so the first real
    request doesn't pay the load cost."""
    get_model()
