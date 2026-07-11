"""Central configuration, loaded from environment variables.

All tunable knobs live here so they can be adjusted in production via env vars
without a code change — in particular the two thresholds called out as
"needs tuning" in the spec (dedup cutoff and relevance floor).
"""

import os

from dotenv import load_dotenv

load_dotenv()

# --- Core ---
DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
EMBEDDING_MODEL: str = os.environ.get(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
PORT: int = int(os.environ.get("PORT", "8080"))

# --- Admin dashboard auth ---
# Single shared password -> signed session cookie. Real auth, no per-user accounts.
ADMIN_PASSWORD: str = os.environ.get("ADMIN_PASSWORD", "")
# Used to sign the session cookie. MUST be set to a long random value in prod.
SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-insecure-change-me")

# Read-only share link for the exportable "current rules" page. When set, the
# rules are viewable (no login) at /rules/<SHARE_TOKEN> — useful for teammates on
# tools/plans that can't connect over MCP. Left empty, the share route is disabled
# (returns 404), so the feature is off until you opt in with a long random token.
SHARE_TOKEN: str = os.environ.get("SHARE_TOKEN", "")

# --- Retrieval / storage tuning ---
# Observations shorter than this (after trimming) are rejected by store().
MIN_OBSERVATION_LENGTH: int = int(os.environ.get("MIN_OBSERVATION_LENGTH", "15"))
# On store(), if the nearest existing observation has cosine similarity >= this,
# treat the new one as a duplicate and return the existing id instead of inserting.
DEDUP_THRESHOLD: float = float(os.environ.get("DEDUP_THRESHOLD", "0.9"))
# On recall(), drop any result whose cosine similarity is below this floor so that
# unrelated tasks surface nothing rather than weakly-related noise. Calibrated for
# all-MiniLM-L6-v2, where genuine matches score ~0.33+ and unrelated queries stay
# below ~0.15; 0.25 sits in that valley with margin on both sides.
RELEVANCE_FLOOR: float = float(os.environ.get("RELEVANCE_FLOOR", "0.25"))
# Default number of observations recall() returns.
DEFAULT_RECALL_LIMIT: int = int(os.environ.get("DEFAULT_RECALL_LIMIT", "5"))
# Hard cap so a caller can't request an unbounded number.
MAX_RECALL_LIMIT: int = int(os.environ.get("MAX_RECALL_LIMIT", "25"))

# Embedding dimensionality for all-MiniLM-L6-v2. Must match the DB vector() column.
EMBEDDING_DIM: int = 384

# The fixed set of observation categories (matches the MCP tool contract).
CATEGORIES: tuple[str, ...] = (
    "brand_voice",
    "process",
    "decision",
    "customer_insight",
    "other",
)


def require(name: str) -> str:
    """Fetch a required env var or raise a clear error."""
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"Required environment variable {name!r} is not set.")
    return value
