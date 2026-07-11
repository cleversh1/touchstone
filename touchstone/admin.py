"""Admin dashboard: a single-page UI plus a small JSON API, served by the server.

Auth model (per resolved decision #1): a single ADMIN_PASSWORD -> a signed
session cookie (via Starlette SessionMiddleware). No per-user accounts.
"""

from __future__ import annotations

import hmac
import json

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)

from . import config, db, export
from .core import mcp
from .templates import DASHBOARD_HTML, LOGIN_HTML


def _is_authed(request: Request) -> bool:
    return bool(request.session.get("admin"))


def _login_redirect() -> RedirectResponse:
    return RedirectResponse(url="/admin/login", status_code=303)


@mcp.custom_route("/admin", methods=["GET"])
async def admin_dashboard(request: Request) -> Response:
    if not _is_authed(request):
        return _login_redirect()
    return HTMLResponse(DASHBOARD_HTML)


@mcp.custom_route("/admin/login", methods=["GET"])
async def admin_login_page(request: Request) -> Response:
    if _is_authed(request):
        return RedirectResponse(url="/admin", status_code=303)
    error = request.query_params.get("error")
    html = LOGIN_HTML.replace(
        "<!--ERROR-->",
        '<p class="error">Incorrect password.</p>' if error else "",
    )
    return HTMLResponse(html)


@mcp.custom_route("/admin/login", methods=["POST"])
async def admin_login_submit(request: Request) -> Response:
    form = await request.form()
    password = str(form.get("password", ""))

    if not config.ADMIN_PASSWORD:
        return HTMLResponse(
            "ADMIN_PASSWORD is not configured on the server.", status_code=500
        )

    # Constant-time comparison to avoid leaking length/prefix via timing.
    if hmac.compare_digest(password, config.ADMIN_PASSWORD):
        request.session["admin"] = True
        return RedirectResponse(url="/admin", status_code=303)
    return RedirectResponse(url="/admin/login?error=1", status_code=303)


@mcp.custom_route("/admin/logout", methods=["GET", "POST"])
async def admin_logout(request: Request) -> Response:
    request.session.clear()
    return _login_redirect()


@mcp.custom_route("/admin/api/meta", methods=["GET"])
async def admin_meta(request: Request) -> Response:
    if not _is_authed(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    contributors = await run_in_threadpool(db.distinct_contributors)
    return JSONResponse(
        {"categories": list(config.CATEGORIES), "contributors": contributors}
    )


@mcp.custom_route("/admin/api/observations", methods=["GET"])
async def admin_list(request: Request) -> Response:
    if not _is_authed(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    category = request.query_params.get("category") or None
    stored_by = request.query_params.get("stored_by") or None
    keyword = request.query_params.get("q") or None

    rows = await run_in_threadpool(
        db.list_observations, category, stored_by, keyword
    )
    observations = [
        {
            "id": str(r["id"]),
            "text": r["text"],
            "category": r["category"],
            "stored_by": r["stored_by"],
            "source_summary": r["source_summary"],
            "created_at": db.iso(r["created_at"]),
        }
        for r in rows
    ]
    return JSONResponse({"observations": observations, "count": len(observations)})


@mcp.custom_route("/admin/api/export", methods=["GET"])
async def admin_export(request: Request) -> Response:
    if not _is_authed(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    fmt = request.query_params.get("format", "md")
    if fmt not in export.FORMATS:
        return JSONResponse({"error": f"unknown format {fmt!r}"}, status_code=400)

    rows = await run_in_threadpool(export.all_rows)
    body, content_type, filename = export.render(fmt, rows)
    return Response(
        body,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@mcp.custom_route("/admin/api/observations/delete", methods=["POST"])
async def admin_delete(request: Request) -> Response:
    if not _is_authed(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        body = json.loads(await request.body() or b"{}")
    except json.JSONDecodeError:
        return JSONResponse({"error": "invalid json"}, status_code=400)

    obs_id = str(body.get("id", ""))
    deleted = await run_in_threadpool(db.delete_observation, obs_id)
    if not deleted:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse({"status": "deleted"})
