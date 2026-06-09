# DEMO.md — Live Demo Script

A tight, repeatable walkthrough for a live interview demo. Practice it cold.

## Before the demo
```bash
make reset      # clean db, re-seed synthetic use cases
make run        # start server
# open http://localhost:8000, confirm the seeded portfolio loads
```
Have a second terminal ready in case you need to re-run `make reset` between takes.

## The 75-second happy path

1. **Open on the portfolio view.** *"This is the front door for an AI opportunity pipeline.
   Everything here is synthetic healthcare-payer data — no real or internal data."*
   → Proves: framing, governance posture, that it runs.

2. **Add a new use case via intake.** Paste a short, messy problem statement.
   *"A business stakeholder describes a pain point in plain language — that's the input."*
   → Proves: realistic intake, low friction.

3. **Run scoring.** Show the five dimension scores, each with a rationale, plus the ROI
   hypothesis. *"It scores against the same five criteria the org prioritizes on, and it
   explains each score — I never want an unexplained number."*
   → Proves: explainability, alignment to the role's framework.

4. **Show a "not a fit" case from the seed.** *"It also tells you when AI is the wrong tool,
   with a reason. Knowing where not to use AI is part of the job."*
   → Proves: responsible-AI judgment as a feature.

5. **Override a score.** Change one value. *"The model proposes; a human decides. Overrides
   are stored — AI is the aid, not the authority."*
   → Proves: human-in-the-loop.

6. **Open the quadrant + export a one-page brief.** *"And it produces the executive artifact —
   a prioritized portfolio and a decision brief per idea."*
   → Proves: it closes the loop to a decision.

7. **(Optional) `make eval`.** *"I don't just trust the demo — there's a small eval that checks
   scoring stability and that the 'not a fit' guardrail actually catches those cases."*
   → Proves: measurement beyond demos.

## Anticipated questions (have answers ready — see DECISIONS.md)
- *Why an LLM instead of a fixed rubric?* → Decision 002.
- *How do you keep scores from drifting / being arbitrary?* → eval + recorded model/prompt
  version (002), human override (003).
- *Could this run without sending data to an external model?* → local Ollama provider (007).
- *How would this work with real data?* → README "Path to Production": auth, audit, Postgres,
  HIPAA handling.
- *Why these five dimensions?* → Decision 006 (they mirror the org's stated criteria).

## If something breaks
- Don't debug live. Say *"let me reset to a clean state"* → `make reset` → reload.
- Fall back to a screenshot/recording of the happy path kept in `docs/`.
