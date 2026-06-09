"""Load synthetic use cases (and their authored scores) into SQLite.

Usage:
    python -m app.seed            # create schema if needed, then seed (idempotent)
    python -m app.seed --reset    # delete the database first for a clean state

Re-seeding is idempotent: use cases are upserted by ``slug`` and each case's
seed score is replaced (not stacked), while any human/LLM scores recorded later
are left untouched (DECISIONS 009).
"""

import argparse
import json
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

from app import db, models

SEED_FILE = Path(__file__).resolve().parent.parent / "data" / "use_cases.seed.json"


def seed_database(conn: sqlite3.Connection) -> int:
    """Load the seed file into the given connection. Returns the case count."""
    cases = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    for case in cases:
        score = case.get("score")
        use_case_id = models.upsert_use_case(conn, case)
        if score is not None:
            models.clear_seed_scores(conn, use_case_id)
            models.insert_score(
                conn,
                use_case_id,
                {**score, "model": "seed-author", "prompt_version": "seed-v1"},
                source="seed",
            )
    return len(cases)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the database file before seeding for a clean demo state.",
    )
    args = parser.parse_args()

    if args.reset:
        path = db.database_path()
        if path.exists():
            path.unlink()
            print(f"Deleted {path}")

    with db.get_connection() as conn:
        models.create_schema(conn)
        count = seed_database(conn)

    print(f"Seeded {count} use cases into {db.database_path()}")


if __name__ == "__main__":
    main()
