"""Model-provider abstraction for the scoring engine.

One small interface, three backends selected by the ``MODEL_PROVIDER`` env var:

  * ``anthropic`` (default) — Claude via the Anthropic SDK, using forced tool use
    for reliable structured output (works across SDK versions and 4.x models).
  * ``ollama`` — a local model via Ollama's HTTP API, fully offline (DECISIONS 007).
  * ``stub`` — a deterministic, no-network heuristic so the app is demoable and
    testable without any API key (DECISIONS 012).

Each provider implements ``propose(system, user, schema) -> schema instance``.
Keeping the schema a parameter avoids any import cycle with ``scoring``.
"""

import hashlib
import os
from typing import Type, TypeVar

import httpx
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ProviderError(RuntimeError):
    """Raised when a provider cannot be constructed or called."""


# --- Anthropic ------------------------------------------------------------


class AnthropicProvider:
    """Claude via the Anthropic SDK, using a forced tool call as the schema."""

    def __init__(self, model: str) -> None:
        self.model = model
        self.label = model  # recorded as the score's `model` provenance

    def propose(self, system: str, user: str, schema: Type[T]) -> T:
        import anthropic  # imported lazily so the stub path needs no config

        client = anthropic.Anthropic()
        tool = {
            "name": "record_scores",
            "description": "Record the five-dimension scores, ROI hypothesis, and AI-fit judgment.",
            "input_schema": schema.model_json_schema(),
        }
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=1500,
                system=system,
                tools=[tool],
                tool_choice={"type": "tool", "name": "record_scores"},
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.AnthropicError as exc:  # auth, rate limit, network, etc.
            raise ProviderError(f"Anthropic request failed: {exc}") from exc

        for block in response.content:
            if block.type == "tool_use":
                return schema.model_validate(block.input)
        raise ProviderError("Anthropic returned no structured tool output.")


# --- Ollama (local) -------------------------------------------------------


class OllamaProvider:
    """A local model served by Ollama, using its JSON-schema structured output."""

    def __init__(self, host: str, model: str) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.label = f"ollama:{model}"

    def propose(self, system: str, user: str, schema: Type[T]) -> T:
        try:
            resp = httpx.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "format": schema.model_json_schema(),
                    "stream": False,
                    "options": {"temperature": 0},  # deterministic local scoring
                },
                timeout=120.0,
            )
            resp.raise_for_status()
            content = resp.json()["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise ProviderError(f"Ollama request failed: {exc}") from exc
        return schema.model_validate_json(content)


# --- Stub (offline, deterministic) ----------------------------------------

# Markers that signal AI is likely the *wrong* tool: deterministic computation,
# trivial lookups/integration, or fully-autonomous high-stakes decisions.
_NOT_FIT_MARKERS = (
    "autonomous",
    "autonomously",
    "without a human",
    "without human",
    "deterministic",
    "reconcile",
    "reconciliation",
    "ledger",
    "arithmetic",
    "exact",
    "rules engine",
    "database lookup",
    "lookup against",
    "api call",
    "via api",
    "via an api",
    "enrollment database",
    "system of record",
)


class StubProvider:
    """Deterministic heuristic scorer — no network, stable across runs.

    Not a real model: scores are derived from a hash of the text so the same
    use case always scores the same (useful for offline demos and the eval
    harness). Rationales are clearly labelled as heuristic.
    """

    label = "stub-v1"
    model = "stub-v1"

    def propose(self, system: str, user: str, schema: Type[T]) -> T:
        text = user.lower()
        is_fit = not any(marker in text for marker in _NOT_FIT_MARKERS)
        lo, hi = (3, 5) if is_fit else (1, 3)

        def dim(salt: str) -> int:
            digest = hashlib.sha256((salt + user).encode("utf-8")).hexdigest()
            return lo + (int(digest[:8], 16) % (hi - lo + 1))

        note = "" if is_fit else " AI is likely not the right tool here."
        data = {
            "impact": dim("impact"),
            "impact_rationale": f"(heuristic) Estimated business impact.{note}",
            "feasibility": dim("feasibility"),
            "feasibility_rationale": f"(heuristic) Estimated technical feasibility.{note}",
            "risk": dim("risk"),
            "risk_rationale": "(heuristic) Estimated risk posture (5 = low risk).",
            "adoption": dim("adoption"),
            "adoption_rationale": "(heuristic) Estimated stakeholder adoption.",
            "strategic_value": dim("strategic"),
            "strategic_value_rationale": "(heuristic) Estimated strategic alignment.",
            "roi_hypothesis": "(heuristic) ROI depends on volume and accuracy; validate with a small pilot.",
            "ai_fit": is_fit,
            "ai_fit_reason": (
                "(heuristic) No strong 'not a fit' signals detected; AI appears applicable with human review."
                if is_fit
                else "(heuristic) Text suggests deterministic computation, a simple lookup, or fully-autonomous high-stakes action — better solved without AI, or with AI only as decision support."
            ),
        }
        return schema.model_validate(data)


# --- Factory --------------------------------------------------------------


def get_provider():
    """Return the provider selected by ``MODEL_PROVIDER`` (default ``anthropic``)."""
    name = os.getenv("MODEL_PROVIDER", "anthropic").strip().lower()

    if name == "anthropic":
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ProviderError(
                "No ANTHROPIC_API_KEY set. Add it to .env, or set "
                "MODEL_PROVIDER=stub for offline scoring."
            )
        return AnthropicProvider(model=os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8"))

    if name == "ollama":
        return OllamaProvider(
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", "llama3.1"),
        )

    if name == "stub":
        return StubProvider()

    raise ProviderError(
        f"Unknown MODEL_PROVIDER: {name!r} (use anthropic | ollama | stub)."
    )
