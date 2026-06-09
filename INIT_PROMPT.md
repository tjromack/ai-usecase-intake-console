# INIT_PROMPT.md — Claude Code Kickoff

Paste this into Claude Code in an empty repo that already contains `README.md`, `CLAUDE.md`,
`TODO.md`, `DECISIONS.md`, and `DEMO.md`.

---

You are helping me build the **AI Use-Case Intake & Prioritization Console**. Before writing
any code, read `README.md`, `CLAUDE.md`, `TODO.md`, and `DECISIONS.md` in this repo. `CLAUDE.md`
is your operating contract — follow its guardrails exactly, especially: synthetic data only
(no PHI, no real or internal systems), human-in-the-loop scoring, minimal dependencies, and
the stack defined there (FastAPI + SQLite + HTMX, LLM scoring with a pluggable provider).

Work through `TODO.md` **one phase at a time**. For each phase:

1. Briefly tell me your plan for the phase and any decision points before you start.
2. Implement only that phase. Keep modules small and single-purpose.
3. Ensure `make run` works and the relevant screen is demoable on seeded data.
4. Record any non-trivial choice (with the rejected alternative and the why) in `DECISIONS.md`,
   using the template there.
5. Make a single, readable commit summarizing what shipped and why.
6. **Stop and wait for my approval before starting the next phase.**

Constraints and reminders:
- The LLM proposes scores, rationales, an ROI hypothesis, and a "fit / not a fit for AI"
  judgment; the UI must let me review and override everything, and overrides must persist.
- Record the model and prompt version alongside each score.
- The five scoring dimensions are Impact, Feasibility, Risk, Adoption, and Strategic Value;
  each score needs a one-line rationale.
- The seed must include at least two deliberate "not a fit for AI" cases so the guardrail is
  demonstrable.
- `make reset` must return the app to a clean, seeded state for repeatable demos.

Start with **Phase 0 (Scaffold)**. Propose the file layout and the `Makefile` targets, then
implement Phase 0 and stop at the gate.
