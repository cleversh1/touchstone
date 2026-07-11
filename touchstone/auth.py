"""API-key hashing and verification.

Keys are UUIDs handed to team members; only their bcrypt hashes are stored.
Verification iterates active keys (only a handful for a 3-4 person team) and
bcrypt-compares. Because bcrypt is deliberately slow, verified raw keys are
cached in-process so repeat requests within a process are O(1).
"""

from __future__ import annotations

import threading
from typing import Optional

import bcrypt

from . import db

# raw_key -> display name, populated after a successful verification.
_cache: dict[str, str] = {}
_cache_lock = threading.Lock()


def hash_key(raw_key: str) -> str:
    return bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()


def verify_key(raw_key: str) -> Optional[str]:
    """Return the contributor's display name for a valid key, else None."""
    if not raw_key:
        return None

    cached = _cache.get(raw_key)
    if cached is not None:
        return cached

    for key in db.get_active_keys():
        try:
            if bcrypt.checkpw(raw_key.encode(), key["key_hash"].encode()):
                with _cache_lock:
                    _cache[raw_key] = key["name"]
                return key["name"]
        except ValueError:
            # Malformed stored hash — skip it rather than failing the request.
            continue
    return None


def invalidate_cache() -> None:
    """Clear the verified-key cache (call after revoking or rotating keys)."""
    with _cache_lock:
        _cache.clear()


def bearer_token(authorization_header: str) -> str:
    """Extract the token from an 'Authorization: Bearer <token>' header value."""
    if not authorization_header:
        return ""
    parts = authorization_header.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return ""
