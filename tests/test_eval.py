"""Phase 5 tests: the scoring evaluation harness (run against the stub)."""

import pytest

from app import eval as evaluation


@pytest.fixture(autouse=True)
def stub_provider(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "stub")


def test_evaluate_passes_on_stub() -> None:
    summary = evaluation.evaluate(runs=2)
    # The stub is deterministic, so re-scoring is perfectly stable.
    assert summary["stability"]["max_spread"] == 0.0
    # All three deliberate not-a-fit seed cases are caught.
    assert summary["guardrail"]["recall"] == 1.0
    assert summary["guardrail"]["missed"] == []
    # Every result carries rationales + ROI.
    assert summary["rubric"]["rate"] == 1.0
    assert summary["passed"] is True


def test_guardrail_covers_three_seed_cases() -> None:
    summary = evaluation.evaluate(runs=1)
    assert summary["guardrail"]["total"] == 3


def test_report_is_human_readable() -> None:
    report = evaluation.format_report(evaluation.evaluate(runs=1))
    assert "Stability" in report
    assert "Guardrail" in report
    assert "Rubric adherence" in report
    assert "Overall:" in report
