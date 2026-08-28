# Touchstone

A shared memory layer for AI agents, delivered as a self-hosted MCP server.

Every time a team member uses Claude for marketing work, the agent captures what it
learns — brand conventions, process decisions, playbook details — into a shared
store. The next time anyone's agent needs that knowledge, it surfaces it before
responding. Claude knows your brand voice on day one for every new hire, never
forgets a process decision, and gives the same answer to the same question no matter
who asks.

## How it works

```
Team member's Claude
      │  MCP (HTTP)  Authorization: Bearer <key>
      ▼
Touchstone (FastMCP + Starlette, one port)
  ├── recall(query)  → embed → pgvector search → top-k above relevance floor
  ├── store(obs)     → embed → dedup check → insert
  ├── list_active_rules(platform) → complete, scoped rule set + version
  └── deprecate_rule(id) → preserve history while retiring a rule
  └── /admin         → dashboard (password-protected)
      ▼
Supabase (Postgres + pgvector)  →  observations, api_keys
```

Embeddings run locally in-process via `fastembed` (ONNX `all-MiniLM-L6-v2`,
384-dim, free, no torch, no OpenAI dependency).

## MCP tools

| Tool | When | Input | Output |
|------|------|-------|--------|
| `recall` | Shared-memory lookup | `query: str`, `limit: int = 5` | semantically relevant observations |
| `list_observations` | Admin/complete category read | `category?`, `limit?` | complete observations, newest first |
| `list_active_rules` | Vercel content review | `platform`, `post_type?` | active scoped rules + `rule_set_version` |
| `store` | Add a durable observation | observation, category, optional rule metadata | `id`, `status` |
| `deprecate_rule` | Retire a rule without erasing history | `id`, `replacement_id?` | `status: deprecated` |

`category` ∈ `brand_voice · process · decision · customer_insight · other`.

### Design decisions baked in (v0.2)

- **Store filtering** — rejects observations under `MIN_OBSERVATION_LENGTH` chars and
  skips near-duplicates (cosine ≥ `DEDUP_THRESHOLD`), returning the existing id with
  `status: "duplicate"`.
- **Relevance floor** — `recall` drops anything below `RELEVANCE_FLOOR` so unrelated
  tasks surface nothing rather than weak noise.
- **Scoped keys** — issue a narrow `rules:read` key to the Vercel Slack reviewer;
  only `rules:admin` keys can change brand rules.
- **Rule lifecycle** — brand rules carry a scope, optional post type, kind,
  status, and individual revision. Deprecated rules stay in the audit trail.

All thresholds are env vars, tunable in production without a redeploy.

## Local setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then fill in DATABASE_URL, ADMIN_PASSWORD, SECRET_KEY

python manage.py init-db                       # create tables + pgvector
python manage.py import-csv --file seed/starter_observations.csv   # optional seed
python manage.py create-key --name "Sarah"     # mint a team member's key

uvicorn touchstone.server:app --host 0.0.0.0 --port 8080
```

Open <http://localhost:8080/admin> and sign in with `ADMIN_PASSWORD`.

## Deploy to Railway

1. Push this repo to GitHub and create a Railway project from it (or `railway up`).
2. Add a Postgres/pgvector database (Railway's Postgres, or point `DATABASE_URL` at Supabase).
3. Set env vars: `DATABASE_URL`, `ADMIN_PASSWORD`, `SECRET_KEY` (and any tuning overrides).
4. Run `python manage.py init-db` once (Railway shell or locally against the same DB).
5. The server starts via `railway.json` / `Procfile`; health check is `/healthz`.

## Connecting a team member's Claude

Add to their Claude MCP config:

```json
{
  "mcpServers": {
    "team-memory": {
      "url": "https://your-server.railway.app/mcp",
      "headers": { "Authorization": "Bearer <their-key>" }
    }
  }
}
```

Then paste the system-prompt instructions from
[`docs/system_prompt.md`](docs/system_prompt.md) into their Claude project.

## Connecting the Vercel Slack reviewer

Use the dedicated, read-only `list_active_rules` tool and a service key scoped to
`rules:read`. The full integration snippet and required Vercel environment
variables are in [`docs/vercel-agent.md`](docs/vercel-agent.md).

## Admin CLI

```bash
python manage.py init-db                     # apply schema
python manage.py create-key --name "Sarah"   # mint a key (shown once)
python manage.py list-keys                   # names + status, never secrets
python manage.py revoke-key --id <uuid>      # deactivate a key
python manage.py import-csv --file seed.csv  # bulk load (dedup-aware)
```

## Out of scope for v1

Private observations, Slack/email integrations, auto-summarisation, usage
analytics, and rate limiting.
