# DEMO.md — Live Demo Script

A tight, repeatable walkthrough for a live demo. Practice it cold.

## Before the demo
```bash
make reset      # clean db, re-seed 10 synthetic use cases (3 deliberate "not a fit")
make run        # start server
# open http://localhost:8000, confirm the seeded portfolio loads
```
Have a second terminal ready in case you need to re-run `make reset` between takes.

**Provider:** set `ANTHROPIC_API_KEY` in `.env` to score on the live Claude model. For a
fully offline demo (no key/network), set `MODEL_PROVIDER=stub` — scoring then uses a
deterministic heuristic (clearly labelled in the UI). Either way the rest of the demo is
identical.

## The 75-second happy path

1. **Open on the portfolio view.** *"This is the front door for an AI opportunity pipeline.
   Everything here is synthetic healthcare-payer data — no real or internal data."*
   → Proves: framing, governance posture, that it runs.

2. **Add a new use case via intake.** Paste a short, messy problem statement.
   *"A business stakeholder describes a pain point in plain language — that's the input."*
   → Proves: realistic intake, low friction.

3. **Run scoring.** On the use-case page, click **Run AI scoring**. Show the five dimension
   scores (each with a rationale), the ROI hypothesis, and the composite priority + quadrant.
   *"It scores against a consistent set of five criteria, and it explains each
   score — I never want an unexplained number."*
   → Proves: explainability, alignment to a consistent prioritization framework.

4. **Show a "not a fit" case from the seed.** Open one of the three (e.g. *Autonomous
   medical-necessity denials*). *"It also tells you when AI is the wrong tool, with a reason.
   Knowing where not to use AI is part of responsible AI adoption."* Note they're grouped at
   the bottom of the portfolio so they can't out-rank real opportunities.
   → Proves: responsible-AI judgment as a feature.

5. **Override a score.** Click **Override**, change one value, save. *"The model proposes; a
   human decides. Overrides are stored with full provenance — AI is the aid, not the
   authority."* The card shows a "Human override" badge.
   → Proves: human-in-the-loop.

6. **Open the quadrant + the decision brief.** Click **Quadrant** in the nav, then **Decision
   brief** on a case → **Print / Save as PDF**. *"And it produces the executive artifact — a
   prioritized portfolio, an impact/feasibility quadrant, and a one-page brief per idea."*
   → Proves: it closes the loop to a decision.

7. **(Optional) `make eval`.** *"I don't just trust the demo — a small eval re-scores the seed
   and checks scoring stability, that the 'not a fit' guardrail catches those cases, and that
   every score carries a rationale."* Sample output:
   ```
   Guardrail ('not a fit for AI' cases flagged):  recall 3/3 (100%)   missed: none
   Rubric adherence (rationale per dimension + ROI present):  pass 30/30 (100%)
   Overall: PASS
   ```
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
