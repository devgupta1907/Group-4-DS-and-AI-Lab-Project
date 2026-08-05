"""
Dump the live database schema.

Reads the actual Postgres catalog rather than the ORM models, so this
shows what is really in Supabase — including tables created outside
Alembic (e.g. `documents`, created by db/setup_supabase.py) and any
drift between the models and the database.

Run from backend/:
    uv run python src/db/dump_schema.py              # print to console
    uv run python src/db/dump_schema.py --json       # machine-readable
    uv run python src/db/dump_schema.py --ddl        # CREATE TABLE statements
"""

from __future__ import annotations

import argparse
import json
import os

import psycopg2
from dotenv import find_dotenv, load_dotenv

SCHEMA = "public"


def _connect():
    load_dotenv(find_dotenv())
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise SystemExit("SUPABASE_DB_URL is missing from .env")
    return psycopg2.connect(url)


def fetch_schema(cur) -> dict:
    cur.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = %s AND table_type = 'BASE TABLE'
        ORDER BY table_name;
        """,
        (SCHEMA,),
    )
    tables = [r[0] for r in cur.fetchall()]

    out: dict[str, dict] = {}
    for table in tables:
        # --- columns ---
        cur.execute(
            """
            SELECT column_name,
                   data_type,
                   character_maximum_length,
                   is_nullable,
                   column_default
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position;
            """,
            (SCHEMA, table),
        )
        columns = [
            {
                "name": name,
                "type": f"{dtype}({maxlen})" if maxlen else dtype,
                "nullable": nullable == "YES",
                "default": default,
            }
            for name, dtype, maxlen, nullable, default in cur.fetchall()
        ]

        # --- primary key ---
        cur.execute(
            """
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = %s::regclass AND i.indisprimary;
            """,
            (f"{SCHEMA}.{table}",),
        )
        primary_key = [r[0] for r in cur.fetchall()]

        # --- foreign keys ---
        cur.execute(
            """
            SELECT kcu.column_name,
                   ccu.table_name  AS references_table,
                   ccu.column_name AS references_column,
                   rc.delete_rule
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu
              ON tc.constraint_name = ccu.constraint_name
            JOIN information_schema.referential_constraints rc
              ON tc.constraint_name = rc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = %s AND tc.table_name = %s;
            """,
            (SCHEMA, table),
        )
        foreign_keys = [
            {"column": col, "references": f"{ref_t}.{ref_c}", "on_delete": rule}
            for col, ref_t, ref_c, rule in cur.fetchall()
        ]

        # --- indexes ---
        cur.execute(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE schemaname = %s AND tablename = %s ORDER BY indexname;",
            (SCHEMA, table),
        )
        indexes = [{"name": n, "definition": d} for n, d in cur.fetchall()]

        # --- row count ---
        cur.execute(f'SELECT count(*) FROM "{SCHEMA}"."{table}";')
        row_count = cur.fetchone()[0]

        out[table] = {
            "columns": columns,
            "primary_key": primary_key,
            "foreign_keys": foreign_keys,
            "indexes": indexes,
            "row_count": row_count,
        }

    return out


def fetch_functions(cur) -> list[dict]:
    """RPC functions — match_documents lives here, not in any ORM model."""
    cur.execute(
        """
        SELECT p.proname,
               pg_get_function_identity_arguments(p.oid) AS args,
               pg_get_function_result(p.oid)             AS returns
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = %s
        ORDER BY p.proname;
        """,
        (SCHEMA,),
    )
    return [{"name": n, "args": a, "returns": r} for n, a, r in cur.fetchall()]


def print_report(schema: dict, functions: list[dict]) -> None:
    print("=" * 70)
    print(f"DATABASE SCHEMA — schema '{SCHEMA}'")
    print("=" * 70)

    for table, meta in schema.items():
        print(f"\n{table}   ({meta['row_count']} rows)")
        print("-" * 70)
        for col in meta["columns"]:
            flags = []
            if col["name"] in meta["primary_key"]:
                flags.append("PK")
            if not col["nullable"]:
                flags.append("NOT NULL")
            fk = next((f for f in meta["foreign_keys"] if f["column"] == col["name"]), None)
            if fk:
                flags.append(f"FK -> {fk['references']} ON DELETE {fk['on_delete']}")
            suffix = f"   [{', '.join(flags)}]" if flags else ""
            print(f"  {col['name']:<24} {col['type']:<28}{suffix}")

        if meta["indexes"]:
            print("  indexes:")
            for idx in meta["indexes"]:
                print(f"    - {idx['name']}")

    if functions:
        print("\n" + "=" * 70)
        print("FUNCTIONS")
        print("=" * 70)
        for fn in functions:
            print(f"  {fn['name']}({fn['args']})")
            print(f"      -> {fn['returns']}")

    print("\n" + "=" * 70)
    print(f"{len(schema)} tables, {len(functions)} functions")
    print("=" * 70)


def print_ddl(cur, schema: dict) -> None:
    """Reconstructs CREATE TABLE-ish output from the catalog."""
    for table, meta in schema.items():
        print(f"\nCREATE TABLE {SCHEMA}.{table} (")
        lines = []
        for col in meta["columns"]:
            line = f"    {col['name']} {col['type']}"
            if not col["nullable"]:
                line += " NOT NULL"
            if col["default"]:
                line += f" DEFAULT {col['default']}"
            lines.append(line)
        if meta["primary_key"]:
            lines.append(f"    PRIMARY KEY ({', '.join(meta['primary_key'])})")
        for fk in meta["foreign_keys"]:
            lines.append(
                f"    FOREIGN KEY ({fk['column']}) REFERENCES {fk['references']} "
                f"ON DELETE {fk['on_delete']}"
            )
        print(",\n".join(lines))
        print(");")
        for idx in meta["indexes"]:
            if not idx["name"].endswith("_pkey"):
                print(f"{idx['definition']};")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of a report.")
    ap.add_argument("--ddl", action="store_true", help="Emit CREATE TABLE statements.")
    args = ap.parse_args()

    conn = _connect()
    cur = conn.cursor()
    try:
        schema = fetch_schema(cur)
        functions = fetch_functions(cur)

        if args.json:
            print(json.dumps({"tables": schema, "functions": functions}, indent=2, default=str))
        elif args.ddl:
            print_ddl(cur, schema)
        else:
            print_report(schema, functions)
    finally:
        cur.close()
        conn.close()
