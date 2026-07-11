"""Export the store to Markdown / JSON / CSV.

Shared by the admin dashboard's Export buttons and the read-only /rules/<token>
share page, so both produce identical output. Markdown is the primary format —
it pastes cleanly into any chat or project instructions, which is the point of
the export (teammates on tools/plans that can't connect over MCP).
"""

from __future__ import annotations

import csv as csvmod
import html
import io
import json
from datetime import datetime, timezone
from typing import Any

from . import config, db

CATEGORY_TITLES = {
    "brand_voice": "Brand voice",
    "process": "Process",
    "decision": "Decisions",
    "customer_insight": "Customer insight",
    "other": "Other",
}


def all_rows() -> list[dict[str, Any]]:
    # Newest-first overall; grouping happens per format.
    return db.list_observations(limit=100_000)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _grouped(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by: dict[str, list[dict[str, Any]]] = {c: [] for c in config.CATEGORIES}
    for r in rows:
        by.setdefault(r["category"], []).append(r)
    return by


def build_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Team Memory — Touchstone",
        "",
        f"_Exported {_now()} · {len(rows)} observation(s)_",
        "",
    ]
    by = _grouped(rows)
    for cat in config.CATEGORIES:
        items = by.get(cat) or []
        if not items:
            continue
        lines.append(f"## {CATEGORY_TITLES.get(cat, cat)}")
        lines.append("")
        for r in items:
            lines.append(f"- {r['text']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_json(rows: list[dict[str, Any]]) -> str:
    data = [
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
    return json.dumps(
        {"exported_at": _now(), "count": len(data), "observations": data}, indent=2
    )


def build_csv(rows: list[dict[str, Any]]) -> str:
    # Columns match seed/import format, so an export round-trips via import-csv.
    buf = io.StringIO()
    w = csvmod.writer(buf)
    w.writerow(["text", "category", "stored_by", "source_summary"])
    for r in rows:
        w.writerow([r["text"], r["category"], r["stored_by"], r["source_summary"]])
    return buf.getvalue()


FORMATS = {
    "md": ("text/markdown; charset=utf-8", "touchstone-export.md", build_markdown),
    "json": ("application/json; charset=utf-8", "touchstone-export.json", build_json),
    "csv": ("text/csv; charset=utf-8", "touchstone-export.csv", build_csv),
}


def render(fmt: str, rows: list[dict[str, Any]]) -> tuple[str, str, str]:
    """Return (body, content_type, filename) for a format key, or raise KeyError."""
    content_type, filename, builder = FORMATS[fmt]
    return builder(rows), content_type, filename


def render_share_page(rows: list[dict[str, Any]], token: str) -> str:
    """A clean, read-only HTML page of the current rules, with a one-click copy."""
    markdown = build_markdown(rows)
    by = _grouped(rows)

    sections = []
    for cat in config.CATEGORIES:
        items = by.get(cat) or []
        if not items:
            continue
        lis = "\n".join(f"<li>{html.escape(r['text'])}</li>" for r in items)
        sections.append(
            f'<h2 class="{html.escape(cat)}">{html.escape(CATEGORY_TITLES.get(cat, cat))}</h2>'
            f"<ul>{lis}</ul>"
        )
    body = "\n".join(sections) or '<p class="empty">No rules yet.</p>'
    md_attr = html.escape(markdown)

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Team Memory — Touchstone</title>
<style>
:root {{ --bg:#0f1115; --panel:#181b22; --border:#262b36; --text:#e6e9ef; --muted:#8b93a3; --accent:#6ea8fe; }}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
.wrap{{max-width:760px;margin:0 auto;padding:32px 20px 80px}}
header{{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:6px}}
h1{{font-size:22px;margin:0}} h1 .dot{{color:var(--accent)}}
.sub{{color:var(--muted);font-size:13px;margin-bottom:20px}}
h2{{font-size:14px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin:26px 0 8px;border-bottom:1px solid var(--border);padding-bottom:6px}}
h2.brand_voice{{color:#b98bff}} h2.process{{color:#5fd0a0}} h2.decision{{color:#6ea8fe}} h2.customer_insight{{color:#f0b45f}}
ul{{margin:0;padding-left:20px}} li{{margin:6px 0}}
.copy{{background:var(--accent);border:none;color:#0b0e14;font-weight:600;border-radius:8px;padding:8px 14px;font-size:14px;cursor:pointer}}
.empty{{color:var(--muted)}}
.note{{color:var(--muted);font-size:12.5px;margin-top:28px;border-top:1px solid var(--border);padding-top:14px}}
</style></head>
<body><div class="wrap">
  <header>
    <h1>Team Memory<span class="dot">.</span></h1>
    <button class="copy" onclick="copyAll()">Copy all (Markdown)</button>
  </header>
  <div class="sub">Read-only · reflects the live store · paste into any chat or project instructions.</div>
  {body}
  <div class="note">Read-only view. To have your AI agent recall and add to this automatically, connect Touchstone over MCP with your personal key.</div>
</div>
<textarea id="md" style="position:absolute;left:-9999px" aria-hidden="true">{md_attr}</textarea>
<script>
function copyAll() {{
  const t = document.getElementById('md');
  navigator.clipboard.writeText(t.value).then(() => {{
    const b = document.querySelector('.copy'); const o = b.textContent;
    b.textContent = 'Copied ✓'; setTimeout(() => b.textContent = o, 1500);
  }});
}}
</script>
</body></html>"""
