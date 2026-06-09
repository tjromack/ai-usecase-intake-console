"""Deterministic prioritization math: composite score, quadrant, ordering.

Kept pure and side-effect-free (CLAUDE.md: "deterministic where possible").
The five dimensions are all "higher is better" (5 = most favorable, including
Risk where 5 = low risk — DECISIONS 010), so the composite is a plain weighted
mean with no per-dimension sign handling.
"""

# Weights sum to 1.0. Impact and Strategic Value lead; Risk/Adoption modulate.
# One place to change if the prioritization philosophy changes (DECISIONS 013).
WEIGHTS: dict[str, float] = {
    "impact": 0.30,
    "strategic_value": 0.25,
    "feasibility": 0.20,
    "adoption": 0.15,
    "risk": 0.10,
}

# Group rank for ordering: AI-fit cases first, then not-a-fit, then unscored.
_FIT_FIRST = {1: 0, 0: 1, None: 2}

_SORT_KEYS = ("composite", "impact", "feasibility", "title")


def composite(score) -> float | None:
    """Weighted mean of the five dimensions, mapped from 1-5 onto 0-100.

    Returns None for an unscored use case.
    """
    if score is None:
        return None
    try:
        raw = sum(WEIGHTS[key] * float(score[key]) for key in WEIGHTS)
    except (TypeError, KeyError, ValueError):
        return None
    return round((raw - 1) / 4 * 100, 1)  # 1-5 -> 0-100


def quadrant(score) -> str:
    """Impact x Feasibility placement, split at the scale midpoint (3)."""
    if score is None:
        return "Unscored"
    high_impact = score["impact"] > 3
    high_feasibility = score["feasibility"] > 3
    if high_impact and high_feasibility:
        return "Quick wins"
    if high_impact and not high_feasibility:
        return "Big bets"
    if not high_impact and high_feasibility:
        return "Incremental"
    return "Deprioritize"


def order(
    rows: list[dict], sort: str = "composite", direction: str = "desc"
) -> list[dict]:
    """Order portfolio rows: AI-fit grouped first, then by the chosen key.

    Grouping is always primary so a not-a-fit case can never outrank a fit one
    in the list (the guardrail stays visible). ``rows`` are dicts with keys
    ``ai_fit``, ``composite``, ``impact``, ``feasibility``, ``title``.
    """
    if sort not in _SORT_KEYS:
        sort = "composite"
    reverse = direction != "asc"

    def secondary(row: dict):
        value = row.get(sort)
        if sort == "title":
            return (value or "").lower()
        return value if value is not None else -1

    # Stable two-pass sort: secondary key first, then the fit grouping.
    ordered = sorted(rows, key=secondary, reverse=reverse)
    ordered.sort(key=lambda r: _FIT_FIRST.get(r.get("ai_fit"), 2))
    return ordered


def row_for(case, score) -> dict:
    """Build a portfolio row (case fields + derived priority metrics)."""
    return {
        "id": case["id"],
        "title": case["title"],
        "submitter": case["submitter"],
        "workflow": case["workflow"],
        "ai_fit": score["ai_fit"] if score else None,
        "impact": score["impact"] if score else None,
        "feasibility": score["feasibility"] if score else None,
        "composite": composite(score),
        "quadrant": quadrant(score),
        "scored": score is not None,
    }


def tier(value: float | None) -> str:
    """Coarse band for styling a composite score."""
    if value is None:
        return "none"
    if value >= 66:
        return "high"
    if value >= 33:
        return "mid"
    return "low"
