"""LLM scoring engine.

The LLM *proposes* five-dimension scores, one-line rationales, an ROI hypothesis,
and an explicit "fit / not a fit for AI" judgment. A human reviews and can
override every value (DECISIONS 002, 003, 004). The model id and prompt version
are recorded with each score for provenance (CLAUDE.md).
"""

from pydantic import BaseModel

from app import models, providers

# Bump when the prompt/rubric changes so scores remain traceable to their prompt.
PROMPT_VERSION = "score-v1"


class ScoreProposal(BaseModel):
    """Structured output the provider must return. All fields required."""

    impact: int
    impact_rationale: str
    feasibility: int
    feasibility_rationale: str
    risk: int
    risk_rationale: str
    adoption: int
    adoption_rationale: str
    strategic_value: int
    strategic_value_rationale: str
    roi_hypothesis: str
    ai_fit: bool
    ai_fit_reason: str


class ScoringError(RuntimeError):
    """Surfaced to the UI when scoring cannot complete (config or provider error)."""


SYSTEM_PROMPT = """You are an AI Innovation Lead triaging proposed AI use cases for a \
healthcare-payer organization. All data is synthetic. You PROPOSE scores; a human \
reviews and can override every value, so be candid and explain your reasoning.

Score the use case on five dimensions, each an integer 1-5 where 5 is the MOST \
FAVORABLE for prioritization:
- Impact: business/member value if it works well.
- Feasibility: how achievable with current AI and the stated data.
- Risk: 5 = low / well-managed risk; 1 = severe risk (regulatory, clinical, fairness).
- Adoption: how readily the stakeholders would actually use it.
- Strategic Value: alignment with an AI-transformation agenda.

Give each dimension a ONE-LINE rationale. Then draft a one-sentence ROI hypothesis.

Finally, judge whether AI is even the right tool (ai_fit). Set ai_fit=false when the \
problem is better solved WITHOUT AI — e.g. deterministic arithmetic/reconciliation, a \
simple database lookup or system integration, or a fully-autonomous high-stakes \
decision that legally/ethically requires a human (such as issuing coverage denials). \
When ai_fit=false, the reason must say plainly why AI is the wrong tool or must be \
limited to decision support. Be willing to flag a poor fit; knowing when NOT to use \
AI is part of the job."""


def _format_use_case(case) -> str:
    """Render the intake record as the user prompt."""

    def field(key: str) -> str:
        value = case[key] if key in case.keys() else None
        return (value or "—").strip()

    return (
        f"Title: {field('title')}\n"
        f"Problem: {field('problem')}\n"
        f"Affected workflow: {field('workflow')}\n"
        f"Data availability: {field('data_availability')}\n"
        f"Stakeholders: {field('stakeholders')}\n"
        f"Current pain: {field('current_pain')}\n"
    )


def _clamp(value: int) -> int:
    """Keep a dimension score inside the 1-5 rubric (the schema can't enforce it)."""
    try:
        return max(1, min(5, int(value)))
    except (TypeError, ValueError):
        return 3


def score_use_case(case) -> dict:
    """Propose a score for one use case. Returns a dict ready for ``insert_score``.

    Raises ScoringError on any provider/config failure so the route can show it.
    """
    user = _format_use_case(case)
    try:
        provider = providers.get_provider()
        proposal = provider.propose(SYSTEM_PROMPT, user, ScoreProposal)
    except providers.ProviderError as exc:
        raise ScoringError(str(exc)) from exc
    except Exception as exc:  # defensive: never leak a raw stack trace to the UI
        raise ScoringError(f"Scoring failed: {exc}") from exc

    data = proposal.model_dump()
    for dimension, _label in models.DIMENSIONS:
        data[dimension] = _clamp(data[dimension])
    data["ai_fit"] = bool(data["ai_fit"])
    data["model"] = provider.label
    data["prompt_version"] = PROMPT_VERSION
    return data
