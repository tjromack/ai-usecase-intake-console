"""Scoring evaluation harness — `make eval` / `python -m app.eval`.

Re-scores the synthetic seed set with the configured provider and checks three
things the demo claims (CLAUDE.md: "explainability is a feature"):

  * Stability      — re-scoring produces consistent composite scores (low spread).
  * Guardrail      — the deliberate "not a fit for AI" cases are flagged correctly.
  * Rubric         — every score carries a rationale per dimension and an ROI line.

Runs offline by default: if no MODEL_PROVIDER and no ANTHROPIC_API_KEY are set,
it falls back to the deterministic `stub` provider so `make eval` always works.
The report names the provider that produced the numbers.
"""

import json
import os
import statistics

from dotenv import load_dotenv

from app import models, prioritization, providers, scoring


def _seed_cases() -> list[dict]:
    """Load the canonical seed cases (independent of current DB state)."""
    from app.seed import SEED_FILE

    return json.loads(SEED_FILE.read_text(encoding="utf-8"))


def _known_not_fit(cases: list[dict]) -> set[str]:
    """Slugs the seed deliberately authored as 'not a fit for AI'."""
    return {c["slug"] for c in cases if not c["score"]["ai_fit"]}


def _rationales_complete(result: dict) -> bool:
    for dimension, _label in models.DIMENSIONS:
        if not (result.get(f"{dimension}_rationale") or "").strip():
            return False
    return bool((result.get("roi_hypothesis") or "").strip())


def evaluate(runs: int = 3) -> dict:
    """Re-score the seed set ``runs`` times and compute the three metrics."""
    cases = _seed_cases()
    known_not_fit = _known_not_fit(cases)
    provider_label = providers.get_provider().label

    # slug -> list of (composite, ai_fit, rationales_ok) across runs
    per_case: dict[str, list[tuple]] = {c["slug"]: [] for c in cases}
    errors: list[str] = []

    for case in cases:
        for _ in range(runs):
            try:
                result = scoring.score_use_case(case)
            except scoring.ScoringError as exc:
                errors.append(f"{case['slug']}: {exc}")
                continue
            per_case[case["slug"]].append(
                (
                    prioritization.composite(result),
                    bool(result["ai_fit"]),
                    _rationales_complete(result),
                )
            )

    # Stability: spread (max-min) of composite per case.
    spreads = []
    for results in per_case.values():
        composites = [c for c, _, _ in results if c is not None]
        if len(composites) >= 2:
            spreads.append(max(composites) - min(composites))
    stability = {
        "mean_spread": round(statistics.mean(spreads), 2) if spreads else 0.0,
        "max_spread": round(max(spreads), 2) if spreads else 0.0,
        "deterministic": bool(spreads) and max(spreads) == 0,
    }

    # Guardrail: a known not-a-fit case is "caught" if a majority of runs flag it.
    threshold = runs // 2 + 1
    missed = []
    for slug in sorted(known_not_fit):
        flagged = sum(1 for _, ai_fit, _ in per_case[slug] if not ai_fit)
        if flagged < threshold:
            missed.append(slug)
    guardrail = {
        "total": len(known_not_fit),
        "caught": len(known_not_fit) - len(missed),
        "missed": missed,
        "recall": round((len(known_not_fit) - len(missed)) / len(known_not_fit), 3)
        if known_not_fit
        else 1.0,
    }

    # Rubric adherence: every individual result carries all rationales + ROI.
    all_results = [r for results in per_case.values() for r in results]
    rubric_ok = sum(1 for _, _, ok in all_results if ok)
    rubric = {
        "total": len(all_results),
        "pass": rubric_ok,
        "rate": round(rubric_ok / len(all_results), 3) if all_results else 0.0,
    }

    overall_pass = not errors and guardrail["recall"] == 1.0 and rubric["rate"] == 1.0
    return {
        "provider": provider_label,
        "runs": runs,
        "stability": stability,
        "guardrail": guardrail,
        "rubric": rubric,
        "errors": errors,
        "passed": overall_pass,
    }


def format_report(summary: dict) -> str:
    """Render the summary as a short plain-text report."""
    s, g, r = summary["stability"], summary["guardrail"], summary["rubric"]
    lines = [
        "AI Use-Case Scoring — Evaluation",
        "=" * 40,
        f"Provider: {summary['provider']}   Runs per case: {summary['runs']}",
        "",
        "Stability (composite spread across runs):",
        f"  mean {s['mean_spread']}   max {s['max_spread']}"
        + ("   [deterministic]" if s["deterministic"] else ""),
        "",
        "Guardrail ('not a fit for AI' cases flagged):",
        f"  recall {g['caught']}/{g['total']} ({g['recall'] * 100:.0f}%)"
        + (
            f"   missed: {', '.join(g['missed'])}" if g["missed"] else "   missed: none"
        ),
        "",
        "Rubric adherence (rationale per dimension + ROI present):",
        f"  pass {r['pass']}/{r['total']} ({r['rate'] * 100:.0f}%)",
    ]
    if summary["errors"]:
        lines += ["", "Errors:"] + [f"  - {e}" for e in summary["errors"]]
    lines += ["", f"Overall: {'PASS' if summary['passed'] else 'FAIL'}"]
    return "\n".join(lines)


def main() -> None:
    load_dotenv()
    # Offline default: stub when no provider/key is configured.
    if not os.getenv("MODEL_PROVIDER") and not os.getenv("ANTHROPIC_API_KEY"):
        os.environ["MODEL_PROVIDER"] = "stub"

    summary = evaluate(runs=int(os.getenv("EVAL_RUNS", "3")))
    print(format_report(summary))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
