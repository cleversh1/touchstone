# Touchstone — engineering to-dos

Kept here (not in the observation store) on purpose: these are engineering tasks.
If they were stored as observations they'd surface in marketing `recall()` results —
someone drafting a newsletter should never get "expose list_observations" back as
brand context.

## For the V1 content-review bot (`../v1-slack-agent/CONTROL-FLOW.md`)

The bot's Phase 2 loads the full brand-voice rubric and depends on Touchstone changes.

- [x] **Expose `list_observations` as an MCP tool.** Done in code (`touchstone/tools.py`,
  wraps the existing `db.list_observations`; cap `MAX_LIST_LIMIT` in `config.py`).
  Returns the complete set for a category with no relevance floor, because the bot
  needs completeness, not semantic top-k — `recall()` can silently omit the one rule
  a draft violates. On branch `feat/list-observations`; **not yet merged or deployed**.

- [x] **`store()` platform-scope guard for `brand_voice` — DEFERRED (decided 2026-08-03).**
  Not shipping a guard. Platform scoping is handled at review time by the bot's Phase 4
  prompt (states the platform explicitly + "ignore rules scoped to another platform"),
  which covers the real LinkedIn-"I"-vs-Substack-"we" harm. Reason a `store()` guard was
  dropped: the convention isn't uniform in `seed/starter_observations.csv` — platform
  rules self-tag ("V1 LinkedIn…", "V1 Substack…", "V1 Slack #announcements…") but global
  rules tag by *omission* ("In V1 content…", "V1 writing is…", "Banned words in V1
  content…"), so no cheap syntactic check both passes existing global rows and catches an
  untagged platform rule (only a semantic check could, and `store()` has no model call).
  **Migration path if this bites** (watch for rules firing on the wrong platform): adopt
  an explicit-tag convention, migrate the ~8 global seed rows to "V1 all: …", then add a
  strict guard rejecting untagged `brand_voice` writes.

- [ ] **Deploy + verify.** Merge `feat/list-observations` to `main` → Railway rebuild;
  confirm a bot API key can call `list_observations` end-to-end against the deployed
  `/mcp` endpoint. Note: local `.env` `DATABASE_URL` points at Supabase **prod**, and no
  Railway CLI is installed here — deploy/verify run from your Railway dashboard + a key
  minted via `manage.py create-key`.
