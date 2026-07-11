# Deploying Touchstone (Railway + Supabase)

Runtime host: **Railway** (persistent container). Database: **Supabase** (Postgres + pgvector).
Total time: ~15 minutes.

---

## 1. Create the database (Supabase)

1. Create a new project at <https://supabase.com/dashboard>. Note the database password you set.
2. Enable pgvector: **Database → Extensions →** search `vector` **→ enable**.
   (The schema also runs `CREATE EXTENSION IF NOT EXISTS vector`, but enabling it here is the reliable path.)
3. Get the connection string: click **Connect** (top bar) → **Connection string → Session pooler**.
   It looks like:
   ```
   postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
   ```

   ⚠️ **Use the *Session* pooler (port 5432), not the *Transaction* pooler (port 6543).**
   Touchstone runs psycopg with prepared statements and its own connection pool; the
   transaction pooler breaks prepared statements, and the session pooler is IPv4-friendly
   (Railway egress is IPv4). Direct connection also works but is IPv6-only on the free tier.

## 2. Apply the schema

From your machine, pointed at the Supabase DB:

```bash
DATABASE_URL="<session-pooler-url>" python manage.py init-db
DATABASE_URL="<session-pooler-url>" python manage.py import-csv --file seed/starter_observations.csv
```

(Or paste `schema.sql` into the Supabase **SQL Editor** and run it.)

## 3. Deploy the server (Railway)

**Option A — from GitHub (recommended):**
1. Push this repo to GitHub (see below).
2. <https://railway.app> → **New Project → Deploy from GitHub repo** → pick the repo.
3. Railway detects `railway.json` and builds with Nixpacks.

**Option B — Railway CLI:**
```bash
npm i -g @railway/cli      # or: brew install railway
railway login
railway init
railway up
```

## 4. Set environment variables (Railway → service → Variables)

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | the Supabase **session pooler** URL from step 1 |
| `ADMIN_PASSWORD` | a strong password for the `/admin` dashboard |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` (optional; default) |

Railway injects `PORT` automatically. Tuning vars (`RELEVANCE_FLOOR`, `DEDUP_THRESHOLD`, …)
are optional overrides.

## 5. Verify

- `https://<your-app>.up.railway.app/healthz` → `{"status":"ok"}`
- `https://<your-app>.up.railway.app/admin` → sign in with `ADMIN_PASSWORD`, see the seeded rules.

> First `recall`/`store` after a deploy or restart loads the MiniLM model into memory
> (a few seconds, one time per container). `/healthz` does not trigger this, so the
> Railway health check passes immediately.

## 6. Mint keys for the team

```bash
railway run python manage.py create-key --name "Sarah"
# or locally:
DATABASE_URL="<session-pooler-url>" python manage.py create-key --name "Sarah"
```

Send each person their key + the config in the main README's "Connecting a team member's Claude".

---

## Push this repo to GitHub

`gh` isn't installed here, so create the repo in the browser (<https://github.com/new>, e.g.
name it `touchstone`, no README/gitignore), then:

```bash
cd touchstone
git branch -M main
git remote add origin git@github.com:<you>/touchstone.git
git push -u origin main
```

---

## Note on the embedding backend

Embeddings use [`fastembed`](https://github.com/qdrant/fastembed) — ONNX Runtime, no
torch — so the image is small (~a few hundred MB) and cold starts are fast. The MiniLM
model (~90 MB) downloads on first use and is cached for the container's lifetime.
