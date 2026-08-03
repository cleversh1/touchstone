#!/usr/bin/env python3
"""Post-deploy smoke test: can an API key call Touchstone over MCP?

Confirms, against a *deployed* Touchstone, that:
  1. the /mcp endpoint is reachable and accepts the Bearer key (auth works), and
  2. the `list_observations` tool is present and returns the brand-voice rubric.

This is the check the V1 content-review bot depends on — its Phase 2 loads the
full rubric via `list_observations`. Run it after every deploy.

Usage:
    export TOUCHSTONE_URL="https://<your-app>.up.railway.app"   # or the full .../mcp URL
    export TOUCHSTONE_API_KEY="<a-minted-key>"
    python verify_mcp.py

    # URL may also be passed as an argument instead of TOUCHSTONE_URL:
    python verify_mcp.py https://<your-app>.up.railway.app

The API key is read ONLY from the environment, never a CLI flag, so it does not
land in shell history. The script prints counts and tool names for the check —
never the key and never rule text.

Exit codes: 0 = pass, 1 = verification failed, 2 = missing/invalid configuration.
"""

from __future__ import annotations

import asyncio
import os
import sys

CATEGORY = "brand_voice"


def _config() -> tuple[str, str]:
    """Resolve the MCP URL and the API key, or exit 2 with a clear message."""
    url = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TOUCHSTONE_URL", "")).strip()
    key = os.environ.get("TOUCHSTONE_API_KEY", "").strip()

    problems = []
    if not url:
        problems.append("Set TOUCHSTONE_URL (or pass the URL as an argument).")
    if not key:
        problems.append("Set TOUCHSTONE_API_KEY in the environment (not a flag).")
    if problems:
        print("Configuration error:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        raise SystemExit(2)

    # Normalise to the streamable-HTTP endpoint, which Touchstone mounts at /mcp.
    url = url.rstrip("/")
    if not url.endswith("/mcp"):
        url = url + "/mcp"
    return url, key


async def _run(url: str, key: str) -> int:
    try:
        from fastmcp import Client
        from fastmcp.client.transports import StreamableHttpTransport
    except ImportError:
        print("fastmcp is not installed. Run: pip install -r requirements.txt", file=sys.stderr)
        return 2

    # The server reads `Authorization: Bearer <key>` off the request; send exactly that.
    transport = StreamableHttpTransport(url=url, headers={"Authorization": f"Bearer {key}"})
    client = Client(transport, timeout=30)

    try:
        async with client:
            tool_names = {t.name for t in await client.list_tools()}
            if "list_observations" not in tool_names:
                print(
                    f"FAIL: server reachable and authorized, but `list_observations` is not "
                    f"exposed. Is this deploy on the merged branch? Tools present: "
                    f"{sorted(tool_names)}",
                    file=sys.stderr,
                )
                return 1

            result = await client.call_tool("list_observations", {"category": CATEGORY})
    except Exception as exc:  # noqa: BLE001 — surface any transport/auth failure cleanly
        # A 401 here means the key was rejected; anything else is connectivity/TLS/URL.
        print(f"FAIL: could not call the deployed MCP endpoint at {url}", file=sys.stderr)
        print(f"      {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    data = getattr(result, "data", None)
    if not isinstance(data, dict):
        data = getattr(result, "structured_content", None) or {}
    observations = data.get("observations", []) if isinstance(data, dict) else []
    count = data.get("count", len(observations)) if isinstance(data, dict) else 0

    if count <= 0:
        print(
            f"FAIL: auth OK and `list_observations` present, but it returned 0 "
            f"'{CATEGORY}' observations. Was the seed imported into this database?",
            file=sys.stderr,
        )
        return 1

    print(f"PASS: {url}")
    print(f"  - auth accepted, {len(tool_names)} tools exposed ({', '.join(sorted(tool_names))})")
    print(f"  - list_observations(category='{CATEGORY}') returned {count} rules")
    return 0


def main() -> int:
    url, key = _config()
    return asyncio.run(_run(url, key))


if __name__ == "__main__":
    raise SystemExit(main())
