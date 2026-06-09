# TODO — Phased Build Plan

Build in phases. **Stop at each approval gate** and wait for review before continuing. Commit
at every phase boundary.

---

## Phase 0 — Scaffold
- [x] Repo structure per README; `requirements.txt`, `Makefile`, `.env.example`, `.gitignore`.
- [x] FastAPI app boots with a health route; base template renders.
- [x] `README`, `CLAUDE.md`, `TODO.md`, `DECISIONS.md`, `DEMO.md` present.
- **Gate:** app boots locally; structure agreed. ✅ `make install` → `make test` (2 passed) →
  server returns 200 on `/health`, `/`, `/static/style.css`.

## Phase 1 — Data model & synthetic seed
- [x] SQLite schema: `use_case` (problem, workflow, data_availability, stakeholders, pain,
      submitter, created_at) and `score` (dimension scores, rationales, roi_hypothesis,
      ai_fit flag + reason, model/prompt version, created_at). Append-only history
      (DECISIONS 009); 1–5 dimensions, 5 = most favorable (DECISIONS 010).
- [x] `app/seed.py` generates 10 realistic healthcare-payer use cases, including three
      deliberate "not a fit for AI" cases (autonomous denials, billing reconciliation,
      eligibility lookup).
- [x] `make seed` loads them; `make reset` returns to clean seeded state.
- **Gate:** seed data inspectable; schema reviewed. ✅ `make reset` → 10 cases / 3 not-a-fit;
  8 tests pass (counts, guardrail, rationales present, rubric range, provenance, idempotency).

## Phase 2 — Intake
- [x] Intake form (HTMX) to create/edit a use case. Progressive enhancement: works without
      JS via 303 fallback; required-field validation re-renders inline (DECISIONS 011).
- [x] List view of submitted use cases, with HTMX live-search and AI-fit badges; read-only
      detail view that surfaces the seeded scores + provenance + the 1–5 scale legend.
- **Gate:** can add and view use cases on seeded data. ✅ 16 tests pass; live check confirms
  list/search/create/edit/detail/validation/404 all work on seeded data.

## Phase 3 — Scoring engine
- [x] `app/scoring.py`: LLM scores the five dimensions (Impact, Feasibility, Risk, Adoption,
      Strategic Value), each with a 1–5 score **and** a one-line rationale.
- [x] Drafts an ROI hypothesis.
- [x] Produces an `ai_fit` judgment (fit / not a fit) with a written reason.
- [x] Provider abstraction (`app/providers.py`): Anthropic default (forced tool use),
      `MODEL_PROVIDER=ollama` for local, plus `stub` for offline/no-key demos & tests
      (DECISIONS 012). Model + prompt version recorded with every score.
- [x] Human override: every score/flag editable in the UI; overrides stored as a new
      `source='human'` row (append-only history).
- **Gate:** scoring runs end-to-end on a seeded use case; output is explainable and editable.
  ✅ 23 tests pass; live run (stub) → llm row → human override → append-only history verified.
  Anthropic path implemented (forced tool use) but unexercised here — no API key in this env.

## Phase 4 — Prioritization & export
- [x] Portfolio view: composite priority score (0–100, weighted mean), sortable columns,
      AI-fit cases ranked first with not-a-fit grouped separately (DECISIONS 013).
- [x] Impact/feasibility quadrant: server-rendered SVG scatter, fit vs not-a-fit markers.
- [x] One-page decision brief per use case (HTML, printable to PDF via `window.print()`).
- **Gate:** portfolio + quadrant + brief all demoable. ✅ 32 tests pass; live check confirms
  ranking/grouping, quadrant SVG (4 labels, 10 points), and a printable brief.

## Phase 5 — Evaluation, polish, demo
- [x] `app/eval.py`: stability (re-score composite spread), guardrail (3/3 not-a-fit cases
      flagged), rubric adherence (rationale per dimension + ROI present); offline by default
      (DECISIONS 014).
- [x] `make eval` prints a short report and exits non-zero on failure.
- [x] Empty states (portfolio, quadrant, unscored brief), styling, and LLM-call error
      handling (in-card message with guidance) — landed across Phases 2–4.
- [x] Finalized `DEMO.md` (real button labels, provider note, eval output) and verified
      `make reset` → cold demo path (every screen 200, live scoring/override, eval PASS).
- **Gate:** full demo runs start to finish from a clean state. ✅ 35 tests pass; cold start
  verified end to end; `make eval` → guardrail 3/3, rubric 30/30, Overall PASS.

---

## Out of scope (note in README "Path to Production")
Auth/RBAC, audit logging, real intake integration, Postgres, drift tracking, HIPAA controls.
