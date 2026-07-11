"""Inlined HTML for the admin dashboard.

Kept as Python string constants (rather than separate files) so the pages are
served reliably regardless of the working directory or deploy packaging.
"""

_STYLE = """
:root {
  --bg: #0f1115; --panel: #181b22; --border: #262b36; --text: #e6e9ef;
  --muted: #8b93a3; --accent: #6ea8fe; --danger: #f2555a; --chip: #222834;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
a { color: var(--accent); text-decoration: none; }
.wrap { max-width: 1000px; margin: 0 auto; padding: 28px 20px 80px; }
header { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
h1 { font-size: 22px; margin: 0; letter-spacing: -0.01em; }
h1 .dot { color: var(--accent); }
.sub { color: var(--muted); font-size: 13px; }
.headright { display: flex; align-items: center; gap: 16px; }
.exp { color: var(--muted); font-size: 12.5px; }
.exp a { color: var(--accent); }
.controls {
  display: flex; flex-wrap: wrap; gap: 10px; margin: 22px 0 16px;
}
.controls input, .controls select {
  background: var(--panel); border: 1px solid var(--border); color: var(--text);
  border-radius: 8px; padding: 8px 10px; font-size: 14px; outline: none;
}
.controls input[type=search] { flex: 1; min-width: 200px; }
.controls input:focus, .controls select:focus { border-color: var(--accent); }
.count { color: var(--muted); font-size: 13px; margin-bottom: 12px; }
.card {
  background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
  padding: 14px 16px; margin-bottom: 12px;
}
.card .text { font-size: 15px; white-space: pre-wrap; }
.meta {
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px;
  margin-top: 10px; color: var(--muted); font-size: 12.5px;
}
.chip {
  background: var(--chip); border: 1px solid var(--border); border-radius: 999px;
  padding: 2px 9px; font-size: 12px; color: var(--text);
}
.chip.brand_voice { color: #b98bff; }
.chip.process { color: #5fd0a0; }
.chip.decision { color: #6ea8fe; }
.chip.customer_insight { color: #f0b45f; }
.chip.other { color: var(--muted); }
.src { font-style: italic; }
.del {
  margin-left: auto; background: transparent; border: 1px solid var(--border);
  color: var(--danger); border-radius: 7px; padding: 4px 10px; font-size: 12.5px;
  cursor: pointer;
}
.del:hover { border-color: var(--danger); }
.empty { color: var(--muted); text-align: center; padding: 60px 0; }
.login {
  max-width: 340px; margin: 14vh auto 0; background: var(--panel);
  border: 1px solid var(--border); border-radius: 12px; padding: 28px;
}
.login h1 { margin-bottom: 6px; }
.login p.sub { margin: 0 0 20px; }
.login input {
  width: 100%; background: var(--bg); border: 1px solid var(--border);
  color: var(--text); border-radius: 8px; padding: 10px 12px; font-size: 15px;
  margin-bottom: 12px; outline: none;
}
.login input:focus { border-color: var(--accent); }
.login button {
  width: 100%; background: var(--accent); border: none; color: #0b0e14;
  font-weight: 600; border-radius: 8px; padding: 10px; font-size: 15px; cursor: pointer;
}
.error { color: var(--danger); font-size: 13px; margin: 0 0 12px; }
"""

LOGIN_HTML = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Touchstone — Sign in</title>
<style>{_STYLE}</style>
</head>
<body>
  <form class="login" method="post" action="/admin/login">
    <h1>Touchstone<span class="dot">.</span></h1>
    <p class="sub">Team memory admin</p>
    <!--ERROR-->
    <input type="password" name="password" placeholder="Admin password" autofocus>
    <button type="submit">Sign in</button>
  </form>
</body>
</html>"""

DASHBOARD_HTML = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Touchstone — Team Memory</title>
<style>{_STYLE}</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <h1>Touchstone<span class="dot">.</span></h1>
      <div class="sub">Shared team memory — browse, search, and prune observations.</div>
    </div>
    <div class="headright">
      <span class="exp">Export:
        <a href="/admin/api/export?format=md" download>Markdown</a> ·
        <a href="/admin/api/export?format=json" download>JSON</a> ·
        <a href="/admin/api/export?format=csv" download>CSV</a>
      </span>
      <a href="/admin/logout">Sign out</a>
    </div>
  </header>

  <div class="controls">
    <input type="search" id="q" placeholder="Search text or source…">
    <select id="category"><option value="">All categories</option></select>
    <select id="stored_by"><option value="">Anyone</option></select>
  </div>
  <div class="count" id="count"></div>
  <div id="list"></div>
</div>

<script>
const $ = (id) => document.getElementById(id);
let debounce;

function esc(s) {{
  return (s ?? "").replace(/[&<>"']/g, c => (
    {{ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }}[c]
  ));
}}

function fmtDate(iso) {{
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleString(undefined,
    {{ year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }});
}}

async function loadMeta() {{
  const r = await fetch("/admin/api/meta");
  if (!r.ok) return;
  const m = await r.json();
  for (const c of m.categories) {{
    const o = document.createElement("option");
    o.value = c; o.textContent = c.replace(/_/g, " ");
    $("category").appendChild(o);
  }}
  for (const p of m.contributors) {{
    const o = document.createElement("option");
    o.value = p; o.textContent = p;
    $("stored_by").appendChild(o);
  }}
}}

async function load() {{
  const params = new URLSearchParams();
  if ($("q").value.trim()) params.set("q", $("q").value.trim());
  if ($("category").value) params.set("category", $("category").value);
  if ($("stored_by").value) params.set("stored_by", $("stored_by").value);

  const r = await fetch("/admin/api/observations?" + params.toString());
  if (r.status === 401) {{ location.href = "/admin/login"; return; }}
  const data = await r.json();
  render(data.observations);
  $("count").textContent = data.count + (data.count === 1 ? " observation" : " observations");
}}

function render(items) {{
  const list = $("list");
  if (!items.length) {{
    list.innerHTML = '<div class="empty">No observations match.</div>';
    return;
  }}
  list.innerHTML = items.map(o => `
    <div class="card" data-id="${{o.id}}">
      <div class="text">${{esc(o.text)}}</div>
      <div class="meta">
        <span class="chip ${{esc(o.category)}}">${{esc(o.category.replace(/_/g, " "))}}</span>
        <span>by <b>${{esc(o.stored_by)}}</b></span>
        <span>${{esc(fmtDate(o.created_at))}}</span>
        ${{o.source_summary ? `<span class="src">“${{esc(o.source_summary)}}”</span>` : ""}}
        <button class="del" onclick="del('${{o.id}}')">Delete</button>
      </div>
    </div>`).join("");
}}

async function del(id) {{
  if (!confirm("Delete this observation? This cannot be undone.")) return;
  const r = await fetch("/admin/api/observations/delete", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify({{ id }})
  }});
  if (r.ok) {{
    const el = document.querySelector(`.card[data-id="${{id}}"]`);
    if (el) el.remove();
  }} else {{
    alert("Delete failed.");
  }}
}}

$("q").addEventListener("input", () => {{ clearTimeout(debounce); debounce = setTimeout(load, 250); }});
$("category").addEventListener("change", load);
$("stored_by").addEventListener("change", load);

loadMeta().then(load);
</script>
</body>
</html>"""
