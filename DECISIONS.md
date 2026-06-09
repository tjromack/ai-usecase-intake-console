# DECISIONS.md — Decision Log

Lightweight ADRs. One entry per non-trivial choice: the decision, the alternative considered,
and why. Keep these short — they are the script for "why did you build it this way?" Add a new
entry whenever a real tradeoff is made.

**Template**
```
## NNN. <Decision title>
- Date / phase:
- Decision:
- Alternatives considered:
- Why:
- Tradeoff accepted:
- Revisit if:
```

---

## 001. Stack: FastAPI + SQLite + HTMX
- Phase: 0
- Decision: Server-rendered HTMX on FastAPI with file-based SQLite.
- Alternatives considered: React SPA + separate API; Streamlit; Django.
- Why: One developer, short timeline, must demo reliably on a laptop with no build step.
  SQLite is zero-config and resets in one command — ideal for repeatable live demos. HTMX
  keeps interactivity without a frontend toolchain.
- Tradeoff accepted: Less rich client interactivity than a SPA; SQLite won't scale to
  production concurrency (acceptable — this is a prototype).
- Revisit if: Multi-user concurrency or a richer UI is required → Postgres + a JS framework.

## 002. LLM scores the dimensions, rather than a fixed rule-based rubric
- Phase: 3
- Decision: Use an LLM to score the five dimensions and draft the ROI hypothesis.
- Alternatives considered: A deterministic weighted-form rubric the user fills in manually.
- Why: The valuable, hard-to-fake part is reasoning about an ambiguous use case from a short
  description — exactly what an LLM is good at, and exactly what the role does. A pure form
  would shift all the thinking back to the user.
- Tradeoff accepted: Non-determinism and the need to evaluate output quality (handled in
  `app/eval.py`). Mitigated by recording the model + prompt version with each score.
- Revisit if: Scores prove unstable → constrain with a stricter rubric or few-shot anchors.

## 003. Human-in-the-loop is mandatory
- Phase: 3
- Decision: Every LLM score, rationale, and fit flag is editable; overrides are stored.
- Alternatives considered: Auto-accept LLM scores.
- Why: Responsible-AI posture and the actual use case — this is a decision *aid*. It also
  demonstrates the "AI proposes, human decides" pattern that matters in a regulated context.
- Tradeoff accepted: A few extra clicks; worth it for trust and auditability.

## 004. An explicit "when not to use AI" flag
- Phase: 3
- Decision: The scorer must judge whether AI is even appropriate, with a written reason, and
  surface "not a fit" cases distinctly.
- Alternatives considered: Score everything on the assumption AI applies.
- Why: The job posting explicitly values judgment about *when not to use AI*. Building this in
  turns a stated value into a demonstrable feature.

## 005. Synthetic data only, authored in-repo
- Phase: 1
- Decision: Ship a seed of 8–10 synthetic healthcare-payer use cases, including deliberate
  "not a fit" cases.
- Alternatives considered: Scraping public examples; using anonymized real data.
- Why: Governance and honesty — no real or internal data in a personal portfolio. Authored
  cases also let me control the demo and guarantee the guardrail has something to catch.

## 006. Five scoring dimensions mirror the role's prioritization criteria
- Phase: 1/3
- Decision: Impact, Feasibility, Risk, Adoption, Strategic Value.
- Why: These are the criteria named in the job posting itself. Aligning the tool to the
  organization's stated framework makes the prototype immediately legible to the audience.

## 007. Pluggable model provider (Anthropic default, Ollama local)
- Phase: 3
- Decision: Abstract the scoring call behind a provider interface.
- Why: Demonstrates a privacy-preserving local-inference path for sensitive environments
  without rebuilding the app — a relevant point for healthcare data.
- Tradeoff accepted: A thin abstraction layer; minor added complexity.

## 008. Cross-platform Makefile with raw-command fallback; pinned dependencies
- Date / phase: Phase 0
- Decision: Ship a single `Makefile` that detects the OS for the venv bin path
  (`Scripts` on Windows, `bin` elsewhere) and invokes pip as `python -m pip`. Document the
  equivalent raw `python`/`uvicorn` commands in the README. Pin every dependency in
  `requirements.txt`.
- Alternatives considered: A separate `make.bat`/PowerShell script for Windows; unpinned
  (`>=`) dependencies; a task runner (invoke, just).
- Why: The primary dev/demo machine is Windows but the artifact should read naturally on
  any platform. One Makefile that works on both avoids a second script to keep in sync, and
  GNU Make is available here. `python -m pip` avoids the Windows "pip can't upgrade itself"
  error. Pinning keeps the demo reproducible (CLAUDE.md: "demoable at all times").
- Tradeoff accepted: Requires `make` (or running the documented raw commands); pinned
  versions need periodic manual bumps.
- Revisit if: We need richer task orchestration, or pins go stale → adopt `just` or a
  constraints file.
