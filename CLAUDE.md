# CLAUDE.md — Operating Contract

This file is the working agreement for building this project with Claude Code. Read it before
each session and keep to it.

## Purpose

Build the **AI Use-Case Intake & Prioritization Console**: a FastAPI + SQLite + HTMX web app
that captures proposed AI use cases and scores them across five dimensions for portfolio
prioritization. This is a demonstration prototype that must run reliably and be explainable.

## Operating principles (guardrails)

1. **Synthetic data only.** Never use, fabricate references to, or import real claims, member,
   or PHI data, and never reference any specific employer's internal systems or code.
2. **Human-in-the-loop.** The LLM *proposes* scores and rationale; the UI must let a human
   review and override every value. Never present AI output as a final decision.
3. **Minimal dependencies.** Prefer the standard library and the stack below. Do not add a
   frontend framework, ORM, or build step without flagging it as a decision first.
4. **Deterministic where possible.** Keep ranking/quadrant math and storage deterministic;
   confine non-determinism to the LLM scoring step, and record the model + prompt version.
5. **Explainability is a feature, not a nice-to-have.** Every score carries a short rationale;
   every "not a fit" flag carries a reason.
6. **Demoable at all times.** After each phase, the app must run and the seed data must load.

## Stack

- Python 3.11+, FastAPI, Uvicorn
- SQLite via `sqlite3` (no ORM unless justified in DECISIONS.md)
- HTMX + Jinja2 server-rendered templates
- LLM via Anthropic SDK; provider abstraction so `MODEL_PROVIDER=ollama` runs locally
- `pytest` for tests

## Commands

```bash
make install     # create venv + install
make seed        # load synthetic use cases into SQLite
make run         # uvicorn app.main:app --reload
make test        # pytest
make eval        # run scoring evaluation harness
make reset       # delete the db and re-seed (clean state for a demo)
make fmt         # format (ruff/black)
```

(If `make` is unavailable, the README documents the raw commands.)

## Conventions

- Keep modules small and single-purpose (see structure in README).
- Type hints on public functions; docstrings explaining *why*, not *what*.
- No secrets in code; read from `.env`.
- **Commit at each phase boundary** with a message summarizing what shipped and why. The git
  history is a project artifact — make it readable.
- Update `DECISIONS.md` whenever a non-trivial choice is made (stack, model, schema, scoring
  logic, anything with a rejected alternative).

## Definition of done (per phase)

- The phase's checklist in `TODO.md` is complete.
- `make run` works and the relevant screen is demoable on seeded data.
- New decisions are recorded in `DECISIONS.md`.
- A commit marks the phase boundary.
- **Stop and wait for my approval before starting the next phase.**

## Do not

- Do not proceed past an approval gate without explicit approval.
- Do not introduce real or scraped personal/health data.
- Do not silently swap the stack or add heavy dependencies.
- Do not let the LLM step make irreversible or unreviewable changes.
