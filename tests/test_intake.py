"""Phase 2 tests: intake create/edit and the list/search views.

Each test gets a fresh seeded database via DATABASE_PATH so routes run against
realistic data without touching the developer's db.
"""

import pytest
from fastapi.testclient import TestClient

from app import db, models, seed


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    with db.get_connection() as conn:
        models.create_schema(conn)
        seed.seed_database(conn)
    # follow_redirects on so the 303 fallback lands on the detail page.
    return TestClient(app_with_clean_state(), follow_redirects=True)


def app_with_clean_state():
    # Import after DATABASE_PATH is set so lifespan/routes use the test db.
    from app.main import app

    return app


def test_list_shows_seeded_cases(client) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Use-case portfolio" in resp.text
    assert "Prior-authorization request triage" in resp.text
    # The guardrail badge renders for a not-a-fit seed case.
    assert "Not a fit" in resp.text


def test_search_partial_filters(client) -> None:
    resp = client.get("/use-cases/search", params={"q": "eligibility"})
    assert resp.status_code == 200
    assert "eligibility" in resp.text.lower()
    assert "Prior-authorization request triage" not in resp.text


def test_create_use_case_persists(client) -> None:
    resp = client.post(
        "/use-cases",
        data={"title": "Test intake case", "problem": "Something hurts."},
    )
    assert resp.status_code == 200
    assert "Test intake case" in resp.text  # landed on the detail page
    assert "Not scored yet" in resp.text  # user-created case is unscored


def test_create_validation_rejects_empty(client) -> None:
    resp = client.post("/use-cases", data={"title": "", "problem": ""})
    assert resp.status_code == 422
    assert "A short title is required." in resp.text


def test_edit_updates_use_case(client) -> None:
    # Edit the first seeded case's submitter.
    resp = client.post(
        "/use-cases/1",
        data={
            "title": "Prior-authorization request triage",
            "problem": "Updated problem text.",
            "submitter": "Edited Submitter",
        },
    )
    assert resp.status_code == 200
    assert "Edited Submitter" in resp.text
    assert "Updated problem text." in resp.text


def test_detail_shows_scores_and_provenance(client) -> None:
    resp = client.get("/use-cases/1")
    assert resp.status_code == 200
    assert "ROI hypothesis" in resp.text
    assert "Strategic Value" in resp.text
    assert "seed-author" in resp.text  # provenance surfaced


def test_unknown_use_case_404(client) -> None:
    resp = client.get("/use-cases/9999")
    assert resp.status_code == 404


def test_htmx_create_returns_hx_redirect(client) -> None:
    resp = client.post(
        "/use-cases",
        data={"title": "HTMX case", "problem": "Via htmx."},
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )
    assert resp.status_code == 204
    assert resp.headers["HX-Redirect"].startswith("/use-cases/")
