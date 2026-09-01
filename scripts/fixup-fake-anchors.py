"""One-shot dev-data fixup: anchor admin-created fake assets and requests.

Assets and item requests anchor to their creator's workplace; the seeded admin
has no employee record, so rows created through the admin session carry NULL
org anchors and stay invisible to workplace/complex-scoped users. This script
distributes those anchorless rows round-robin across the seeded workplaces.

Run once with the backend venv:  python scripts/fixup-fake-anchors.py
"""

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

BACKEND_ENV = Path(__file__).resolve().parents[1] / "backend" / ".env"

ANCHOR_SQL = """
WITH w AS (
    SELECT wp.id AS id, cx.company_id AS company_id, wp.complex_id AS complex_id,
           row_number() OVER (ORDER BY wp.code) - 1 AS rn
    FROM workplaces wp
    JOIN complexes cx ON cx.id = wp.complex_id
), target AS (
    SELECT id, row_number() OVER (ORDER BY created_at) - 1 AS rn
    FROM {table} WHERE workplace_id IS NULL
)
UPDATE {table} t
SET company_id = w.company_id, complex_id = w.complex_id, workplace_id = w.id
FROM w, target r
WHERE t.id = r.id AND w.rn = mod(r.rn, (SELECT count(*) FROM w))
"""


def main() -> int:
    url = next(
        line.split("=", 1)[1].strip().strip('"')
        for line in BACKEND_ENV.read_text(encoding="utf-8").splitlines()
        if line.startswith("DATABASE_URL")
    )
    engine = create_engine(url)
    with engine.begin() as conn:
        for table in ("asset_instances", "item_requests"):
            result = conn.execute(text(ANCHOR_SQL.format(table=table)))
            print(f"{table}: anchored {result.rowcount} row(s)")
    engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
