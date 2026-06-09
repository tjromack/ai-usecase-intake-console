"""Phase 1 tests: the synthetic seed loads correctly and the guardrail cases
are present and well-formed.

Each test uses a throwaway database via the DATABASE_PATH env var so it never
touches the developer's real db.
"""

import sqlite3

import pytest

from app import db, models, seed


@pytest.fixture
def conn(tmp_path, monkeypatch) -> sqlite3.Connection:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    connection = db.connect()
    models.create_schema(connection)
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def test_seed_loads_all_cases_with_scores(conn) -> None:
    count = seed.seed_database(conn)
    cases = models.list_use_cases(conn)
    scores = models.latest_scores(conn)

    assert count >= 8, "TODO requires 8-10 seed cases"
    assert len(cases) == count
    # Every use case has a current score.
    assert all(case["id"] in scores for case in cases)


def test_at_least_two_not_a_fit_cases(conn) -> None:
    seed.seed_database(conn)
    scores = models.latest_scores(conn)

    not_a_fit = [s for s in scores.values() if s["ai_fit"] == 0]
    assert len(not_a_fit) >= 2, "Seed must include >=2 deliberate 'not a fit' cases"
    # Each carries a written reason (the guardrail is explainable).
    assert all((s["ai_fit_reason"] or "").strip() for s in not_a_fit)


def test_every_dimension_has_a_rationale(conn) -> None:
    seed.seed_database(conn)
    scores = models.latest_scores(conn)

    for score in scores.values():
        for dimension, _label in models.DIMENSIONS:
            assert score[dimension] is not None, f"missing {dimension} score"
            assert (
                score[f"{dimension}_rationale"] or ""
            ).strip(), f"missing {dimension} rationale"


def test_scores_are_within_rubric_range(conn) -> None:
    seed.seed_database(conn)
    scores = models.latest_scores(conn)

    for score in scores.values():
        for dimension, _label in models.DIMENSIONS:
            assert 1 <= score[dimension] <= 5


def test_provenance_recorded(conn) -> None:
    seed.seed_database(conn)
    scores = models.latest_scores(conn)

    for score in scores.values():
        assert score["source"] == "seed"
        assert score["model"] == "seed-author"
        assert score["prompt_version"] == "seed-v1"


def test_reseed_is_idempotent(conn) -> None:
    seed.seed_database(conn)
    seed.seed_database(conn)  # second run must not duplicate or stack rows

    cases = models.list_use_cases(conn)
    per_case = conn.execute(
        "SELECT use_case_id, COUNT(*) AS n FROM score GROUP BY use_case_id"
    ).fetchall()

    assert len(cases) >= 8
    assert all(row["n"] == 1 for row in per_case), "seed scores must replace, not stack"
