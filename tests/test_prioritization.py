"""Phase 4 tests: composite math, quadrant, ordering, and the new views."""

import pytest
from fastapi.testclient import TestClient

from app import db, models, prioritization, seed


def _score(**overrides) -> dict:
    base = {
        "impact": 3,
        "feasibility": 3,
        "risk": 3,
        "adoption": 3,
        "strategic_value": 3,
        "ai_fit": 1,
    }
    base.update(overrides)
    return base


# --- pure math ------------------------------------------------------------


def test_composite_endpoints() -> None:
    assert (
        prioritization.composite(_score(**{k: 5 for k in prioritization.WEIGHTS}))
        == 100.0
    )
    assert (
        prioritization.composite(_score(**{k: 1 for k in prioritization.WEIGHTS}))
        == 0.0
    )
    assert prioritization.composite(None) is None


def test_composite_is_weighted() -> None:
    # Impact (0.30) should move the score more than Adoption (0.15).
    high_impact = prioritization.composite(_score(impact=5))
    high_adoption = prioritization.composite(_score(adoption=5))
    assert high_impact > high_adoption


def test_quadrant_labels() -> None:
    assert prioritization.quadrant(_score(impact=5, feasibility=5)) == "Quick wins"
    assert prioritization.quadrant(_score(impact=5, feasibility=2)) == "Big bets"
    assert prioritization.quadrant(_score(impact=2, feasibility=5)) == "Incremental"
    assert prioritization.quadrant(_score(impact=2, feasibility=2)) == "Deprioritize"


def test_order_groups_fit_first_then_composite() -> None:
    rows = [
        {
            "title": "lowfit",
            "ai_fit": 1,
            "composite": 20.0,
            "impact": 2,
            "feasibility": 2,
        },
        {
            "title": "highnofit",
            "ai_fit": 0,
            "composite": 90.0,
            "impact": 5,
            "feasibility": 5,
        },
        {
            "title": "highfit",
            "ai_fit": 1,
            "composite": 80.0,
            "impact": 5,
            "feasibility": 5,
        },
    ]
    ordered = prioritization.order(rows, "composite", "desc")
    # A high-scoring not-a-fit case must never outrank fit cases.
    assert [r["title"] for r in ordered] == ["highfit", "lowfit", "highnofit"]


# --- views ----------------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("MODEL_PROVIDER", "stub")
    with db.get_connection() as conn:
        models.create_schema(conn)
        seed.seed_database(conn)
    from app.main import app

    return TestClient(app, follow_redirects=True)


def test_portfolio_shows_priority_and_grouping(client) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Priority" in resp.text
    # The not-a-fit divider appears (seed has three not-a-fit cases).
    assert "ranked separately" in resp.text


def test_portfolio_sort_param_accepted(client) -> None:
    resp = client.get("/", params={"sort": "impact", "dir": "asc"})
    assert resp.status_code == 200


def test_quadrant_renders_svg(client) -> None:
    resp = client.get("/quadrant")
    assert resp.status_code == 200
    assert "<svg" in resp.text
    assert "Quick wins" in resp.text


def test_brief_renders_for_seeded_case(client) -> None:
    resp = client.get("/use-cases/1/brief")
    assert resp.status_code == 200
    assert "Decision brief" in resp.text
    assert "ROI hypothesis" in resp.text
    assert "window.print()" in resp.text  # printable


def test_brief_404_for_unknown(client) -> None:
    assert client.get("/use-cases/9999/brief").status_code == 404
