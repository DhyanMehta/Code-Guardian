"""Snapshot the real database so the migration can be proven non-destructive.

Run before and after `alembic upgrade head` and diff the output:

    python scripts\\e2e\\_db_snapshot.py > before.txt
    python -m alembic upgrade head
    python scripts\\e2e\\_db_snapshot.py > after.txt
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, inspect, text  # noqa: E402

from backend.config import get_settings  # noqa: E402

engine = create_engine(get_settings().database_url)

with engine.connect() as conn:
    insp = inspect(conn)

    print("=== tables ===")
    for table in sorted(insp.get_table_names()):
        print(f"  {table}")

    print("\n=== columns ===")
    for table in sorted(insp.get_table_names()):
        print(f"  {table}:")
        for col in insp.get_columns(table):
            print(f"    {col['name']:26} {col['type']!s:30} nullable={col['nullable']}")

    print("\n=== indexes ===")
    for table in sorted(insp.get_table_names()):
        for idx in insp.get_indexes(table):
            print(f"  {table}.{idx['name']}: cols={idx['column_names']} "
                  f"unique={idx['unique']}")

    print("\n=== alembic_version ===")
    for row in conn.execute(text("select version_num from alembic_version")):
        print(f"  {row[0]}")

    print("\n=== reviews (all rows, ordered by id) ===")
    reviews = conn.execute(text(
        "select id, repo_full_name, pr_number, commit_sha, status, is_fork, "
        "autofix_status, autofix_branch, autofix_approved_by, autofix_approved_at, "
        "created_at, summary from reviews order by id"
    )).mappings().all()
    for r in reviews:
        print(f"  id={r['id']} pr#{r['pr_number']} status={r['status']:10} "
              f"fork={r['is_fork']} sha={(r['commit_sha'] or '')[:8]}")
        print(f"      autofix={r['autofix_status']} branch={r['autofix_branch']} "
              f"by={r['autofix_approved_by']} at={r['autofix_approved_at']}")
        print(f"      created={r['created_at']}")
        print(f"      summary={r['summary']}")
    print(f"  TOTAL reviews: {len(reviews)}")

    print("\n=== findings per review ===")
    rows = conn.execute(text(
        "select review_id, agent, severity, count(*) as n from findings "
        "group by review_id, agent, severity order by review_id, agent, severity"
    )).mappings().all()
    for row in rows:
        print(f"  review={row['review_id']} {row['agent']:14} "
              f"{row['severity']:8} {row['n']}")
    total = conn.execute(text("select count(*) from findings")).scalar_one()
    print(f"  TOTAL findings: {total}")

    print("\n=== findings checksum (id, agent, severity, title, file, line) ===")
    checksum = conn.execute(text(
        "select md5(string_agg(concat_ws('|', id, agent, severity, title, "
        "coalesce(file_path,''), coalesce(line::text,'')), E'\\n' order by id)) "
        "from findings"
    )).scalar_one()
    print(f"  md5={checksum}")
