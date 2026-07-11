"""Read-only public share page: /rules/<token>.

Gated by an unguessable SHARE_TOKEN (compared in constant time). When SHARE_TOKEN
is unset the route 404s, so the feature is off until explicitly enabled. This lets
teammates on tools/plans that can't speak MCP still view and copy the current rules.
"""

from __future__ import annotations

import hmac

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import HTMLResponse, PlainTextResponse, Response

from . import config, export
from .core import mcp


def _token_ok(token: str) -> bool:
    # Disabled unless a token is configured; constant-time compare otherwise.
    if not config.SHARE_TOKEN:
        return False
    return hmac.compare_digest(token, config.SHARE_TOKEN)


@mcp.custom_route("/rules/{token}", methods=["GET"])
async def rules_page(request: Request) -> Response:
    token = request.path_params.get("token", "")
    if not _token_ok(token):
        # Don't distinguish "disabled" from "wrong token".
        return PlainTextResponse("Not found", status_code=404)

    rows = await run_in_threadpool(export.all_rows)

    fmt = request.query_params.get("format")
    if fmt:
        if fmt not in export.FORMATS:
            return PlainTextResponse(
                f"Unknown format {fmt!r}. Use md, json, or csv.", status_code=400
            )
        body, content_type, _ = export.render(fmt, rows)
        # Inline (not an attachment) so it renders in the browser for easy copy.
        return Response(body, media_type=content_type)

    return HTMLResponse(export.render_share_page(rows, token))
