"""Give every test an isolated, seeded database.

Without this, a fresh clone fails `pytest` until `make seed` has run (the index smoke test hits a DB with no
schema). This autouse fixture points `DATABASE_PATH` at a per-test temp file, creates the schema, and loads the
sample use cases (an offline, idempotent seed), so the suite passes cold and no test depends on — or pollutes — a
shared database. Tests that set their own `DATABASE_PATH` simply override it within the test.
"""
import pytest

from app import db, models, seed


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    with db.get_connection() as conn:
        models.create_schema(conn)
        seed.seed_database(conn)
    yield
