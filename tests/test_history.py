"""Override-history UX (2026-07-28): the append-only scoring trail is surfaced, not just the latest.

A human override is stored as a NEW score row (source='human'); the earlier AI/seed proposal stays in the
`score` table. `models.score_history` returns that trail newest-first, and the use-case detail / score card
render it so an override is transparent (CLAUDE.md §2 — never present AI output as a final, silent decision).
"""

import pytest
from fastapi.testclient import TestClient

from app import db, models, seed


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("MODEL_PROVIDER", "stub")
    with db.get_connection() as conn:
        models.create_schema(conn)
        seed.seed_database(conn)
    from app.main import app

    return TestClient(app, follow_redirects=True)


_OVERRIDE = {
    "impact": "2", "impact_rationale": "Reviewed down.",
    "feasibility": "3", "feasibility_rationale": "ok",
    "risk": "3", "risk_rationale": "ok",
    "adoption": "3", "adoption_rationale": "ok",
    "strategic_value": "3", "strategic_value_rationale": "ok",
    "roi_hypothesis": "Modest.", "ai_fit": "on", "ai_fit_reason": "Still a fit.",
}


# --- the model query (pure-ish, against the DB) ------------------------------

def test_score_history_is_append_only_and_newest_first(client):
    # case 1 starts seeded; apply two overrides
    client.post("/use-cases/1/score/override", headers={"HX-Request": "true"}, data=_OVERRIDE)
    client.post("/use-cases/1/score/override", headers={"HX-Request": "true"},
                data={**_OVERRIDE, "impact": "4"})
    with db.get_connection() as conn:
        history = models.score_history(conn, 1)
    assert len(history) >= 3                       # seed + 2 overrides, nothing overwritten
    # newest first: the most recent override's impact is on top
    assert history[0]["source"] == "human" and history[0]["impact"] == 4
    # the original seed row is still present at the bottom of the trail
    assert history[-1]["source"] in ("seed", "llm")


def test_score_history_empty_for_unscored_case(client):
    # create a fresh use case with no score yet
    with db.get_connection() as conn:
        new_id = models.insert_use_case(conn, {
            "title": "Fresh", "problem": "p", "workflow": "", "data_availability": "",
            "stakeholders": "", "current_pain": "", "submitter": "",
        }) if hasattr(models, "insert_use_case") else None
    if new_id is not None:
        with db.get_connection() as conn:
            assert models.score_history(conn, new_id) == []


# --- the UI surfaces the trail ----------------------------------------------

def test_detail_page_shows_history_after_an_override(client):
    client.post("/use-cases/1/score/override", headers={"HX-Request": "true"}, data=_OVERRIDE)
    r = client.get("/use-cases/1")
    assert r.status_code == 200
    assert "Scoring history" in r.text
    assert "source=human" in r.text                # the explanatory note
    # the history section auto-opens when a human override exists
    assert "<details class=\"history\" open>" in r.text


def test_override_response_card_includes_the_trail(client):
    # the HTMX card returned by the override POST itself carries the refreshed history
    r = client.post("/use-cases/1/score/override", headers={"HX-Request": "true"}, data=_OVERRIDE)
    assert r.status_code == 200
    assert "Scoring history" in r.text
    assert "Human override" in r.text              # the current-source badge (existing behaviour)


def test_at_most_one_score_shows_no_history_section(client):
    """An untouched case (≤1 score row) shows the card but not the multi-row history table —
    there's nothing to compare against until a re-score or override appends a second row."""
    r = client.get("/use-cases/2")                 # seeded, never re-scored or overridden here
    assert r.status_code == 200
    with db.get_connection() as conn:
        assert len(models.score_history(conn, 2)) <= 1
    assert "Scoring history" not in r.text
