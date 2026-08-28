"""ASGI application entrypoint.

Composition:
  - FastMCP streamable-HTTP app mounted at /mcp
  - SessionMiddleware (signed cookies) so the /admin dashboard can log in
  - A pure-ASGI Bearer auth guard that 401s unauthenticated calls to /mcp
    (kept pure-ASGI, not BaseHTTPMiddleware, so it doesn't buffer SSE streams)

Run with:  uvicorn touchstone.server:app --host 0.0.0.0 --port $PORT
"""

from __future__ import annotations

import anyio
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from . import auth, config
from .core import mcp

# Registering the tool and admin-route modules attaches them to `mcp`.
from . import tools  # noqa: F401  (side effect: registers recall/store/delete)
from . import admin  # noqa: F401  (side effect: registers /admin routes)
from . import share  # noqa: F401  (side effect: registers /rules/<token> route)

MCP_PATH = "/mcp"


@mcp.custom_route("/", methods=["GET"])
async def root(request: Request):
    return RedirectResponse(url="/admin", status_code=307)


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(request: Request):
    return JSONResponse({"status": "ok", "service": "touchstone"})


class BearerAuthMiddleware:
    """Pure-ASGI guard: require a valid Bearer key for the MCP endpoint.

    Only HTTP requests under `protected_prefix` are checked; lifespan and
    websocket scopes, and all other paths (root, /admin, /healthz), pass through.
    """

    def __init__(self, app, protected_prefix: str = MCP_PATH):
        self.app = app
        self.prefix = protected_prefix

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith(self.prefix):
            header_map = {k.lower(): v for k, v in scope.get("headers", [])}
            authorization = header_map.get(b"authorization", b"").decode()
            token = auth.bearer_token(authorization)

            # verify_key touches the DB + bcrypt; run it off the event loop.
            name = await anyio.to_thread.run_sync(auth.verify_key, token)
            if not name:
                await self._reject(send)
                return

        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(send):
        body = b'{"error":"unauthorized","detail":"Missing or invalid Bearer API key."}'
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"www-authenticate", b'Bearer realm="touchstone"'),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def build_app():
    inner = mcp.http_app(
        path=MCP_PATH,
        middleware=[
            Middleware(
                SessionMiddleware,
                secret_key=config.SECRET_KEY,
                same_site="lax",
                # Railway terminates TLS before this app. The browser still reaches
                # the public service over HTTPS, so never allow the admin cookie on
                # a plaintext request in production.
                https_only=True,
            )
        ],
    )
    return BearerAuthMiddleware(inner)


app = build_app()
