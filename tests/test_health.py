"""Phase 0 smoke tests: the app boots and serves its base routes.

These guard the CLAUDE.md "demoable at all times" invariant — if the scaffold
stops rendering, CI/the test run catches it before a demo does.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_index_renders() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    # Base template rendered: the synthetic-data guardrail banner is present.
    assert "Synthetic data only" in resp.text
