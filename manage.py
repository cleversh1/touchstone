#!/usr/bin/env python3
"""Touchstone admin CLI.

Commands:
    init-db                        Apply schema.sql to DATABASE_URL.
    create-key --name "Sarah"      Generate an API key for a team member.
    list-keys                      List issued keys (names + status, never secrets).
    revoke-key --id <uuid>         Deactivate a key.
    import-csv --file seed.csv     Bulk-load seed observations (with dedup).

CSV columns (header row required): text, category[, stored_by][, source_summary]
    - category must be one of: brand_voice, process, decision, customer_insight, other
    - stored_by defaults to "Seed"; source_summary defaults to "Seed import".
"""

from __future__ import annotations

import argparse
import csv
import sys
import uuid

from touchstone import auth, config, db, embeddings


def cmd_init_db(_args) -> int:
    db.init_schema()
    print("Schema applied to DATABASE_URL.")
    return 0


def cmd_create_key(args) -> int:
    raw_key = str(uuid.uuid4())
    scopes = [s.strip() for s in args.scopes.split(",") if s.strip()]
    invalid = sorted(set(scopes) - set(config.KEY_SCOPES))
    if invalid:
        print(f"Unknown scope(s): {', '.join(invalid)}", file=sys.stderr)
        return 2
    if not scopes:
        print("At least one scope is required.", file=sys.stderr)
        return 2
    key_id = db.insert_api_key(args.name, auth.hash_key(raw_key), scopes)
    print(f"Created key for {args.name!r} (id: {key_id}).")
    print("\nSend this key to the team member — it is shown ONCE and not recoverable:\n")
    print(f"    {raw_key}\n")
    print("They add it to their Claude MCP config as:")
    print(f"Scopes: {', '.join(scopes)}")
    print(f'    "Authorization": "Bearer {raw_key}"')
    return 0


def cmd_list_keys(_args) -> int:
    keys = db.list_api_keys()
    if not keys:
        print("No keys issued yet.")
        return 0
    for k in keys:
        status = "active" if k["active"] else "revoked"
        print(f"{k['id']}  {status:8}  {db.iso(k['created_at'])}  {k['name']}")
    return 0


def cmd_revoke_key(args) -> int:
    ok = db.deactivate_api_key(args.id)
    auth.invalidate_cache()
    print("Revoked." if ok else "No matching key found.")
    return 0 if ok else 1


def cmd_import_csv(args) -> int:
    with open(args.file, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or "text" not in reader.fieldnames:
            print("CSV must have a header row with at least a 'text' column.", file=sys.stderr)
            return 1

        stored, skipped, errors = 0, 0, 0
        for i, row in enumerate(reader, start=2):  # row 1 is the header
            text = (row.get("text") or "").strip()
            category = (row.get("category") or "other").strip()
            stored_by = (row.get("stored_by") or "Seed").strip()
            source_summary = (row.get("source_summary") or "Seed import").strip()

            if len(text) < config.MIN_OBSERVATION_LENGTH:
                print(f"  row {i}: skipped (too short)")
                skipped += 1
                continue
            if category not in config.CATEGORIES:
                print(f"  row {i}: error (bad category {category!r})")
                errors += 1
                continue

            vector = embeddings.embed(text)
            nearest = db.search_nearest(vector, 1)
            if nearest and float(nearest[0]["relevance"]) >= config.DEDUP_THRESHOLD:
                print(f"  row {i}: skipped (near-duplicate)")
                skipped += 1
                continue

            db.insert_observation(text, vector, category, stored_by, source_summary)
            stored += 1

        print(f"\nImport complete: {stored} stored, {skipped} skipped, {errors} errors.")
    return 0 if errors == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="manage.py", description="Touchstone admin CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Apply schema.sql").set_defaults(func=cmd_init_db)

    p_create = sub.add_parser("create-key", help="Generate an API key for a team member")
    p_create.add_argument("--name", required=True, help="Team member's display name")
    p_create.add_argument(
        "--scopes",
        default="rules:read,observations:read,observations:write,rules:admin",
        help="Comma-separated scopes; use rules:read for the Vercel review bot",
    )
    p_create.set_defaults(func=cmd_create_key)

    sub.add_parser("list-keys", help="List issued keys").set_defaults(func=cmd_list_keys)

    p_revoke = sub.add_parser("revoke-key", help="Deactivate a key")
    p_revoke.add_argument("--id", required=True, help="Key id (uuid)")
    p_revoke.set_defaults(func=cmd_revoke_key)

    p_import = sub.add_parser("import-csv", help="Bulk-load seed observations")
    p_import.add_argument("--file", required=True, help="Path to a CSV file")
    p_import.set_defaults(func=cmd_import_csv)

    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as exc:  # surface a clean message rather than a traceback
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        # Close the pooled connections so the CLI exits promptly and cleanly.
        db.close_pool()


if __name__ == "__main__":
    raise SystemExit(main())
