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

-- Existing installations predate scoped keys. Preserve their current full access
-- during migration; new service keys should be created with the narrowest scope.
ALTER TABLE api_keys
    ADD COLUMN IF NOT EXISTS scopes text[] NOT NULL DEFAULT ARRAY[
        'rules:read', 'observations:read', 'observations:write', 'rules:admin'
    ]::text[];

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

-- Brand rules need structured scope and a lifecycle. These fields are deliberately
-- optional/defaulted so existing shared-memory observations remain valid.
ALTER TABLE observations ADD COLUMN IF NOT EXISTS scope text NOT NULL DEFAULT 'all';
ALTER TABLE observations ADD COLUMN IF NOT EXISTS post_type text;
ALTER TABLE observations ADD COLUMN IF NOT EXISTS kind text NOT NULL DEFAULT 'guidance';
ALTER TABLE observations ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'active';
ALTER TABLE observations ADD COLUMN IF NOT EXISTS rule_version integer NOT NULL DEFAULT 1;
ALTER TABLE observations ADD COLUMN IF NOT EXISTS replaced_by uuid;

ALTER TABLE observations DROP CONSTRAINT IF EXISTS observations_scope_check;
ALTER TABLE observations ADD CONSTRAINT observations_scope_check
    CHECK (scope IN ('all', 'announcements', 'linkedin', 'substack'));
ALTER TABLE observations DROP CONSTRAINT IF EXISTS observations_kind_check;
ALTER TABLE observations ADD CONSTRAINT observations_kind_check
    CHECK (kind IN ('required', 'guidance', 'example'));
ALTER TABLE observations DROP CONSTRAINT IF EXISTS observations_status_check;
ALTER TABLE observations ADD CONSTRAINT observations_status_check
    CHECK (status IN ('active', 'deprecated'));
-- `replaced_by` intentionally has no foreign key: imports may deprecate a rule
-- before its replacement is loaded, and historical references must remain intact.

-- Nearest-neighbour index for cosine similarity search.
-- HNSW (not IVFFlat): IVFFlat partitions vectors into `lists` and probes only a
-- few per query, so on a small store most queries hit empty partitions and
-- return nothing. HNSW gives near-exact recall at any table size with no
-- data-dependent tuning, which is what this team-scale store needs.
CREATE INDEX IF NOT EXISTS observations_embedding_idx
    ON observations USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS observations_category_idx   ON observations (category);
CREATE INDEX IF NOT EXISTS observations_created_at_idx ON observations (created_at DESC);
CREATE INDEX IF NOT EXISTS observations_active_rules_idx
    ON observations (category, scope, post_type)
    WHERE status = 'active';
