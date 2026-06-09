# AI Use-Case Intake & Prioritization Console

A web application that operationalizes the AI Innovation Lead's own workflow: capturing
proposed AI use cases through structured intake and scoring them for portfolio
prioritization. It is the tool the role would actually use to run an AI opportunity
pipeline — built as a working prototype on synthetic data.

> Built against the Claritev problem space using **synthetic data only — no PHI, no internal
> systems**. This repo is a personal portfolio prototype, not affiliated with or using any
> employer data, code, or infrastructure.

---

## The problem it solves

Organizations adopting AI quickly accumulate more ideas than they can act on, with no
consistent way to compare them. Decisions get made on enthusiasm rather than evidence, and
nobody captures *why* an idea was greenlit, parked, or rejected. The result is wasted pilots,
poor prioritization, and no audit trail.

This console gives an AI innovation function a single front door: a structured intake for
proposed use cases and a consistent, explainable scoring model that produces a prioritized
portfolio and a one-page decision brief per idea — including an explicit judgment on whether
AI is even the right tool.

## Who it's for

An AI Innovation Lead, a transformation team, or a business unit triaging where to apply AI.

## What it does

- **Structured intake** — captures each proposed use case: problem statement, affected
  workflow, data availability, stakeholders, and current pain.
- **Explainable scoring** — scores every use case across five dimensions (Impact,
  Feasibility, Risk, Adoption, Strategic Value) and drafts an ROI hypothesis.
- **"When not to use AI" check** — flags use cases that are a poor fit for AI, with a written
  rationale, instead of forcing everything into an AI-shaped solution.
- **Portfolio view** — a prioritized list plus an impact/feasibility quadrant.
- **Decision brief export** — a one-page summary per use case suitable for an executive
  audience.

## Why it maps to the role

This *is* the operating model named in the job posting: developing frameworks for AI
use-case intake, prioritization, ROI measurement, and risk assessment; producing crisp
executive decision documents; and exercising responsible-AI judgment about when *not* to use
AI. The five scoring dimensions deliberately mirror the posting's own prioritization
criteria.

## Tech stack

- **Backend:** FastAPI (Python)
- **Storage:** SQLite (zero-config, file-based — trivial to reset and demo)
- **Frontend:** HTMX + server-rendered templates (no build step, fast to stand up)
- **Scoring:** an LLM (Anthropic Claude by default; pluggable to a local model via Ollama)
- **Export:** server-rendered HTML/PDF brief

See `DECISIONS.md` for why each of these was chosen over the alternatives.

## Quickstart

```bash
# 1. Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Seed synthetic use cases (8-10 realistic healthcare-payer examples)
python -m app.seed

# 3. Run
uvicorn app.main:app --reload
# open http://localhost:8000
```

Set `ANTHROPIC_API_KEY` in `.env` to enable LLM scoring, or set `MODEL_PROVIDER=ollama` to
run scoring fully locally with no external calls.

**With `make`** (Linux/macOS/Windows + GNU Make): `make install` then `make run`.
The `Makefile` handles the venv path on every platform.

**Windows / no `make`** — the raw commands:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Evaluation

Scoring quality is checked, not assumed (`make eval` / `python -m app.eval`):

- **Stability** — re-scoring the seed set produces consistent rankings (low variance).
- **Guardrail correctness** — use cases authored as deliberate "not a fit for AI" cases are
  correctly flagged.
- **Rubric adherence** — scores include the required rationale for each dimension.

## Responsible AI & data

- All data is **synthetic and authored for this project**. No real claims, members, or PHI.
- The LLM **proposes** scores and rationale; a human reviews and can override every value.
  The tool is a decision aid, not a decision maker.
- A local-model option (Ollama) demonstrates a privacy-preserving deployment path for
  sensitive environments.

## Path to production

Not in scope for this prototype, but the decisions I would make to take it further:

- **Governance:** role-based access, audit logging of every score and override, and an
  approval workflow before a use case enters an active pilot.
- **Data:** move from SQLite to Postgres; integrate a real intake source (e.g., a form or
  ticketing system) behind SSO.
- **Evaluation:** expand the eval set, add inter-rater calibration against human scorers, and
  track scoring drift over time.
- **Security/compliance:** HIPAA-aligned handling if any real operational context is ever
  attached; secrets management; PII scanning on intake.
- **Scale:** background scoring jobs, caching, and a richer portfolio analytics layer.

## Project structure

```
app/
  main.py          # FastAPI app + routes
  models.py        # SQLite schema / data model
  scoring.py       # LLM scoring + ROI hypothesis + fit check
  seed.py          # synthetic use-case generator
  eval.py          # scoring evaluation harness
  templates/       # HTMX views (intake, portfolio, quadrant, brief)
data/
  use_cases.seed.json
DECISIONS.md       # decision log (ADR-lite)
DEMO.md            # live demo script + reset
TODO.md            # phased build plan with approval gates
CLAUDE.md          # operating contract for Claude Code
```

## Status

Feature-complete prototype (Phases 0–5). Intake, LLM scoring with human override, the
prioritized portfolio, impact/feasibility quadrant, one-page decision brief, and the scoring
eval all run on seeded synthetic data. `make reset` returns a clean demo state; `make eval`
prints the scoring report. See `TODO.md` for the phased plan and `DEMO.md` for the walkthrough.
