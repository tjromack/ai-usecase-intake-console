"""Phase 3 tests: the scoring engine and the human-override flow.

Uses MODEL_PROVIDER=stub so scoring runs deterministically with no network or
API key. Each test gets a fresh seeded database via DATABASE_PATH.
"""

import pytest
from fastapi.testclient import TestClient

from app import db, models, scoring, seed


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("MODEL_PROVIDER", "stub")
    with db.get_connection() as conn:
        models.create_schema(conn)
        seed.seed_database(conn)
    from app.main import app

    return TestClient(app, follow_redirects=True)


def _latest(use_case_id: int):
    with db.get_connection() as conn:
        return models.latest_score_for(conn, use_case_id)


# --- engine unit ----------------------------------------------------------


def test_score_use_case_returns_valid_rubric(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", "stub")
    case = {
        "title": "Test",
        "problem": "Summarize member calls to save agent time.",
        "workflow": "",
        "data_availability": "",
        "stakeholders": "",
        "current_pain": "",
    }
    result = scoring.score_use_case(case)
    for dimension, _label in models.DIMENSIONS:
        assert 1 <= result[dimension] <= 5
        assert result[f"{dimension}_rationale"]
    assert isinstance(result["ai_fit"], bool)
    assert result["prompt_version"] == scoring.PROMPT_VERSION
    assert result["model"] == "stub-v1"


def test_stub_flags_not_a_fit_case(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", "stub")
    case = {
        "title": "Ledger reconciliation",
        "problem": "Use an LLM to reconcile the deterministic ledger arithmetic each month.",
        "workflow": "",
        "data_availability": "",
        "stakeholders": "",
        "current_pain": "",
    }
    result = scoring.score_use_case(case)
    assert result["ai_fit"] is False


def test_missing_api_key_raises_actionable_error(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(scoring.ScoringError) as exc:
        scoring.score_use_case({"title": "x", "problem": "y"})
    assert "MODEL_PROVIDER=stub" in str(exc.value)


# --- routes ---------------------------------------------------------------


def test_run_scoring_stores_llm_row(client) -> None:
    resp = client.post("/use-cases/3/score/run", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert "Strategic Value" in resp.text

    score = _latest(3)
    assert score["source"] == "llm"
    assert score["model"] == "stub-v1"
    assert score["prompt_version"] == scoring.PROMPT_VERSION


def test_override_stores_human_row_and_wins(client) -> None:
    # Seed case 1 starts with a seed score; override it.
    resp = client.post(
        "/use-cases/1/score/override",
        headers={"HX-Request": "true"},
        data={
            "impact": "2",
            "impact_rationale": "Reviewed down.",
            "feasibility": "3",
            "feasibility_rationale": "ok",
            "risk": "3",
            "risk_rationale": "ok",
            "adoption": "3",
            "adoption_rationale": "ok",
            "strategic_value": "3",
            "strategic_value_rationale": "ok",
            "roi_hypothesis": "Modest.",
            "ai_fit": "on",
            "ai_fit_reason": "Still a fit.",
        },
    )
    assert resp.status_code == 200
    assert "Human override" in resp.text

    score = _latest(1)
    assert score["source"] == "human"
    assert score["impact"] == 2
    assert score["model"] == "human"


def test_override_rejects_out_of_range(client) -> None:
    resp = client.post(
        "/use-cases/1/score/override",
        headers={"HX-Request": "true"},
        data={
            "impact": "9",  # out of 1–5
            "feasibility": "3",
            "risk": "3",
            "adoption": "3",
            "strategic_value": "3",
            "roi_hypothesis": "",
            "ai_fit": "on",
        },
    )
    assert resp.status_code == 422
    assert "Enter 1–5." in resp.text


def test_run_scoring_surfaces_provider_error(client, monkeypatch) -> None:
    # Switch to anthropic with no key: the card should render with guidance.
    monkeypatch.setenv("MODEL_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    resp = client.post("/use-cases/3/score/run", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert "MODEL_PROVIDER=stub" in resp.text
