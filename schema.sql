-- Touchstone schema. Idempotent: safe to run repeatedly.

CREATE EXTENSION IF NOT EXISTS vector;

-- One row per team member's API key. Only the bcrypt hash is stored.
CREATE TABLE IF NOT EXISTS api_keys (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name       text        NOT NULL,
    key_hash   text        NOT NULL,
    active     boolean     NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- The shared memory store.
CREATE TABLE IF NOT EXISTS observations (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    text           text         NOT NULL,
    embedding      vector(384),
    category       text         NOT NULL,
    stored_by      text         NOT NULL,
    source_summary text         NOT NULL DEFAULT '',
    created_at     timestamptz  NOT NULL DEFAULT now()
);

-- Nearest-neighbour index for cosine similarity search.
-- HNSW (not IVFFlat): IVFFlat partitions vectors into `lists` and probes only a
-- few per query, so on a small store most queries hit empty partitions and
-- return nothing. HNSW gives near-exact recall at any table size with no
-- data-dependent tuning, which is what this team-scale store needs.
CREATE INDEX IF NOT EXISTS observations_embedding_idx
    ON observations USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS observations_category_idx   ON observations (category);
CREATE INDEX IF NOT EXISTS observations_created_at_idx ON observations (created_at DESC);
