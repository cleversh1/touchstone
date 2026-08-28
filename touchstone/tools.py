"""The MCP tools exposed to agents.

Auth: identity is derived from the Bearer token on the incoming HTTP request.
The ASGI middleware (see server.py) already rejects unauthenticated calls to
/mcp with a 401; re-deriving the name here from the cached key lookup is O(1)
and lets store() stamp `stored_by` correctly.
"""

from __future__ import annotations

from typing import Literal, Optional

from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_headers

from . import auth, config, db, embeddings

from .core import mcp


def _principal():
    """Resolve the authenticated principal, or fail closed."""
    # include_all=True is required: FastMCP strips sensitive headers (including
    # Authorization) from the default get_http_headers() result.
    headers = get_http_headers(include_all=True)  # keys are lower-cased by FastMCP
    token = auth.bearer_token(headers.get("authorization", ""))
    principal = auth.verify_key(token)
    if not principal:
        raise ToolError("Unauthorized: missing or invalid API key.")
    return principal


def _require_scope(scope: str):
    principal = _principal()
    if scope not in principal.scopes:
        raise ToolError(f"Forbidden: this API key requires the {scope!r} scope.")
    return principal


@mcp.tool
def recall(query: str, limit: int = config.DEFAULT_RECALL_LIMIT) -> dict:
    """Retrieve the most relevant stored team observations for the current task.

    Call this at the start of a task. If it returns observations, tell the user
    what you're applying before responding. If it returns nothing, proceed normally.

    Args:
        query: A short description of the task or question, used for retrieval.
        limit: Maximum number of observations to return (default 5).
    """
    _require_scope("observations:read")

    query = (query or "").strip()
    if not query:
        return {"observations": []}

    limit = max(1, min(int(limit), config.MAX_RECALL_LIMIT))

    vector = embeddings.embed(query)
    rows = db.search_nearest(vector, limit)

    observations = [
        {
            "id": str(row["id"]),
            "text": row["text"],
            "stored_by": row["stored_by"],
            "stored_at": db.iso(row["created_at"]),
            "relevance": round(float(row["relevance"]), 4),
        }
        for row in rows
        if float(row["relevance"]) >= config.RELEVANCE_FLOOR
    ]
    return {"observations": observations}


@mcp.tool
def list_observations(
    category: Optional[str] = None,
    limit: int = config.MAX_LIST_LIMIT,
) -> dict:
    """List stored observations in full — no semantic ranking, no relevance floor.

    Use this when you need the *complete* set of observations, not the few most
    relevant to a query. The main case is loading an entire rule category at once
    (e.g. category="brand_voice" to load every brand-voice rule), where recall()'s
    top-k relevance ranking would silently omit a rule a draft happens not to be
    semantically near. Newest first.

    Args:
        category: Optional filter. One of brand_voice, process, decision,
            customer_insight, other. Omit to list across all categories.
        limit: Maximum observations to return (default and hard cap = MAX_LIST_LIMIT).
    """
    _require_scope("observations:read")

    if category is not None and category not in config.CATEGORIES:
        raise ToolError(
            f"Invalid category {category!r}. Must be one of: "
            f"{', '.join(config.CATEGORIES)}."
        )

    limit = max(1, min(int(limit), config.MAX_LIST_LIMIT))
    rows = db.list_observations(category=category, limit=limit)

    observations = [
        {
            "id": str(row["id"]),
            "text": row["text"],
            "category": row["category"],
            "stored_by": row["stored_by"],
            "stored_at": db.iso(row["created_at"]),
            "scope": row["scope"],
            "post_type": row["post_type"],
            "kind": row["kind"],
            "status": row["status"],
            "rule_version": row["rule_version"],
        }
        for row in rows
    ]
    return {"observations": observations, "count": len(observations)}


@mcp.tool
def store(
    observation: str,
    category: Literal[
        "brand_voice", "process", "decision", "customer_insight", "other"
    ],
    source_summary: str = "",
    scope: Literal["all", "announcements", "linkedin", "substack"] = "all",
    post_type: Optional[str] = None,
    kind: Literal["required", "guidance", "example"] = "guidance",
    rule_version: int = 1,
) -> dict:
    """Store a durable team observation for future recall by any team member.

    Only store things useful to a *different* team member on a *similar* task —
    conventions, process steps, and decisions — not ephemeral, task-specific content.

    Args:
        observation: The fact, convention, decision, or process note to store.
        category: One of brand_voice, process, decision, customer_insight, other.
        source_summary: Brief note on what prompted this (e.g. "User corrected draft tone").
        scope: Platform the rule applies to. Use "all" for shared rules.
        post_type: Optional narrower content type, e.g. "builder_product".
        kind: required for factual/mechanical checks, guidance for editorial advice,
            or example for non-binding inspiration.
        rule_version: Revision number for this individual rule.

    Returns:
        The stored observation's id and a status of "stored", or — if a
        near-identical observation already exists — the existing id with
        status "duplicate".
    """
    principal = _require_scope("observations:write")

    observation = (observation or "").strip()
    if len(observation) < config.MIN_OBSERVATION_LENGTH:
        raise ToolError(
            f"Observation is too short to be useful "
            f"(minimum {config.MIN_OBSERVATION_LENGTH} characters)."
        )

    if category not in config.CATEGORIES:
        raise ToolError(
            f"Invalid category {category!r}. Must be one of: "
            f"{', '.join(config.CATEGORIES)}."
        )
    if scope not in config.RULE_SCOPES:
        raise ToolError(f"Invalid scope {scope!r}.")
    if kind not in config.RULE_KINDS:
        raise ToolError(f"Invalid rule kind {kind!r}.")
    if rule_version < 1:
        raise ToolError("rule_version must be at least 1.")

    # Brand rules govern every reviewer. Only a rule administrator may alter
    # them; ordinary agent learnings remain in the other shared-memory categories.
    if category == "brand_voice" and "rules:admin" not in principal.scopes:
        raise ToolError("Forbidden: storing brand_voice rules requires 'rules:admin'.")

    vector = embeddings.embed(observation)

    # Near-duplicate check: if the closest existing observation is above the
    # dedup threshold, don't insert a second copy.
    nearest = db.search_nearest(vector, 1)
    if nearest and float(nearest[0]["relevance"]) >= config.DEDUP_THRESHOLD:
        return {"id": str(nearest[0]["id"]), "status": "duplicate"}

    obs_id = db.insert_observation(
        text=observation,
        embedding=vector,
        category=category,
        stored_by=principal.name,
        source_summary=source_summary.strip(),
        scope=scope,
        post_type=post_type.strip() if post_type else None,
        kind=kind,
        rule_version=rule_version,
    )
    return {"id": obs_id, "status": "stored"}


@mcp.tool
def list_active_rules(
    platform: Literal["announcements", "linkedin", "substack"],
    post_type: Optional[str] = None,
) -> dict:
    """Load the complete active rule set for one platform.

    This is the Vercel content-review bot's required read path. It filters by
    platform and optional post type, returns no semantic ranking, and includes
    a stable rule_set_version that must be stored with every review.
    """
    _require_scope("rules:read")
    rows = db.list_active_rules(platform=platform, post_type=post_type)
    rules = [
        {
            "id": str(row["id"]),
            "text": row["text"],
            "scope": row["scope"],
            "post_type": row["post_type"],
            "kind": row["kind"],
            "rule_version": row["rule_version"],
            "source_summary": row["source_summary"],
        }
        for row in rows
    ]
    return {
        "platform": platform,
        "post_type": post_type,
        "rule_set_version": db.active_rule_set_version(rows),
        "rules": rules,
        "count": len(rules),
    }


@mcp.tool
def deprecate_rule(id: str, replacement_id: Optional[str] = None) -> dict:
    """Mark a brand rule deprecated while preserving its history.

    Args:
        id: The active rule id to deprecate.
        replacement_id: Optional replacement rule id, after it has been stored.
    """
    _require_scope("rules:admin")

    deprecated = db.deprecate_observation(id, replacement_id)
    if not deprecated:
        raise ToolError(f"No active observation found with id {id!r}.")
    return {"status": "deprecated", "id": id, "replacement_id": replacement_id}
