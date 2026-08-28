"""API-key hashing and verification.

Keys are UUIDs handed to team members; only their bcrypt hashes are stored.
Verification iterates active keys (only a handful for a 3-4 person team) and
bcrypt-compares. Because bcrypt is deliberately slow, verified raw keys are
cached in-process so repeat requests within a process are O(1).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Optional

import bcrypt

from . import config, db

@dataclass(frozen=True)
class Principal:
    """The identity and permissions attached to one verified API key."""

    name: str
    scopes: frozenset[str]


# raw_key -> (principal, expiry), populated after a successful verification.
_cache: dict[str, tuple[Principal, float]] = {}
_cache_lock = threading.Lock()


def hash_key(raw_key: str) -> str:
    return bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()


def verify_key(raw_key: str) -> Optional[Principal]:
    """Return a valid key's principal, else None.

    The cache has a short TTL so revoking a key takes effect without requiring a
    service restart. A cache must never be the durable authority for access.
    """
    if not raw_key:
        return None

    cached = _cache.get(raw_key)
    if cached is not None:
        principal, expires_at = cached
        if time.monotonic() < expires_at:
            return principal
        with _cache_lock:
            _cache.pop(raw_key, None)

    for key in db.get_active_keys():
        try:
            if bcrypt.checkpw(raw_key.encode(), key["key_hash"].encode()):
                with _cache_lock:
                    principal = Principal(
                        name=key["name"], scopes=frozenset(key["scopes"] or [])
                    )
                    _cache[raw_key] = (
                        principal,
                        time.monotonic() + config.API_KEY_CACHE_SECONDS,
                    )
                return principal
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
