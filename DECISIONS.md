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
  description — exactly what an LLM is good at, and exactly what this kind of triage requires.
  A pure form would shift all the thinking back to the user.
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
- Why: Responsible AI adoption explicitly values judgment about *when not to use AI*. Building
  this in turns a stated principle into a demonstrable feature.

## 005. Synthetic data only, authored in-repo
- Phase: 1
- Decision: Ship a seed of 8–10 synthetic healthcare-payer use cases, including deliberate
  "not a fit" cases.
- Alternatives considered: Scraping public examples; using anonymized real data.
- Why: Governance and honesty — no real or internal data in a portfolio prototype. Authored
  cases also let me control the demo and guarantee the guardrail has something to catch.

## 006. Five scoring dimensions reflect common prioritization criteria
- Phase: 1/3
- Decision: Impact, Feasibility, Risk, Adoption, Strategic Value.
- Why: These are the criteria organizations commonly weigh when deciding where to invest in
  AI. Aligning the tool to a recognizable framework makes the prototype immediately legible.

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

## 009. Scores are append-only history; latest row wins
- Date / phase: Phase 1
- Decision: The `score` table is append-only — a re-score or human override inserts a NEW
  row, and reads select MAX(id) per use case as the current value. A `source` column
  (`seed` | `llm` | `human`) distinguishes who produced each row. Re-seeding replaces only
  prior `source='seed'` rows, never human/LLM scores.
- Alternatives considered: One mutable score row per use case, updated in place.
- Why: The product thesis is capturing *why* a decision was made; keeping every prior score
  gives a free audit trail of how a value changed and who changed it (LLM vs human), which
  matters in a regulated setting. Idempotent seeding falls out naturally by clearing only
  seed-sourced rows.
- Tradeoff accepted: Reads need a "latest per use case" join instead of a plain select;
  the table grows with each re-score.
- Revisit if: History is never used in the UI and the join cost matters → collapse to a
  single current row plus a separate audit log.

## 010. All five dimensions scored 1-5 with 5 = most favorable
- Date / phase: Phase 1
- Decision: Every dimension uses an integer 1-5 where 5 is the most favorable for
  prioritization. For Risk this means 5 = low / well-managed risk (not high risk). Enforced
  with CHECK constraints on the score columns.
- Alternatives considered: Scoring Risk in its natural direction (5 = high risk) and
  inverting it in the composite formula.
- Why: A uniform "higher is better" convention lets the Phase 4 composite priority score
  combine dimensions without per-dimension sign handling, and keeps the quadrant math
  obvious. The direction is documented in `models.py` and encoded in the scoring prompt.
- Tradeoff accepted: "Risk = 5" reads as counter-intuitive until you know the convention;
  mitigated by labeling and rationales that state the risk posture in words.
- Revisit if: Reviewers find the inverted Risk scale confusing → relabel as "Risk posture"
  or "Manageability" in the UI.

## 011. Progressive-enhancement intake; routes kept in main.py for now
- Date / phase: Phase 2
- Decision: The intake form posts via HTMX (`hx-post`, swap the form fragment in on
  validation error, `HX-Redirect` on success) but also carries plain `method/action` so it
  works without JavaScript (server returns a 303 redirect when the `HX-Request` header is
  absent). All Phase 2 routes live in `app/main.py` rather than a separate router module.
- Alternatives considered: HTMX-only (no-JS users get a broken form); full-page POST with no
  HTMX (loses the live-search and inline-error feel); splitting routes into an `APIRouter`
  per area now.
- Why: Progressive enhancement is cheap here and makes the demo robust if a CDN/JS hiccup
  occurs live. Keeping ~8 routes in one file avoids premature structure (CLAUDE.md: minimal
  dependencies / flag structure changes); a router split is a clean refactor once scoring and
  portfolio routes land.
- Tradeoff accepted: A little duplication between `hx-post` and `action`; `main.py` will grow
  until the Phase 3/4 refactor.
- Revisit if: `main.py` exceeds a comfortable size → split into `routers/` by area.

## 012. Structured scoring via forced tool use; a `stub` provider for offline/test
- Date / phase: Phase 3
- Decision: The Anthropic provider gets structured output by forcing a single tool call
  (`tool_choice` → a `record_scores` tool whose `input_schema` is the Pydantic score
  schema) and reading the `tool_use` block, rather than `messages.parse()` /
  `output_config.format`. Add a third `MODEL_PROVIDER=stub` backend: a deterministic,
  no-network heuristic scorer. If `MODEL_PROVIDER=anthropic` but no `ANTHROPIC_API_KEY`,
  scoring raises an actionable error pointing at `stub` rather than silently faking output.
  Default model is `claude-opus-4-8` (configurable via `ANTHROPIC_MODEL`).
- Alternatives considered: The newer `messages.parse()` structured-output API; free-text
  JSON with manual parsing; silently auto-falling back to the stub when the key is missing.
- Why: The pinned SDK is `anthropic==0.42.0` and the live Anthropic path can't be exercised
  in this dev environment — forced tool use is the version-robust structured-output method
  that works across SDK versions and all Claude 4.x models, and avoids the 4.8 request-surface
  pitfalls (no `temperature`/`budget_tokens`). The stub keeps the app demoable and the tests
  deterministic with no key or network (CLAUDE.md: "demoable at all times", "deterministic
  where possible"). A loud error beats a silent fake — a demo that quietly shows heuristic
  numbers as if they were model output would undercut the trust the tool is meant to build.
- Tradeoff accepted: Forced tool use is slightly more verbose than `messages.parse()`; the
  stub's scores are heuristic, not meaningful (clearly labelled as such). The Ollama path is
  implemented but unverified here (no local Ollama).
- Revisit if: We standardize on a newer SDK → switch the Anthropic provider to
  `messages.parse()`; or scores prove unstable → add few-shot anchors / a stricter rubric.

## 013. Composite = transparent weighted mean; not-a-fit grouped separately
- Date / phase: Phase 4
- Decision: Composite priority = weighted mean of the five 1-5 dimensions, mapped to 0-100.
  Weights: Impact 0.30, Strategic Value 0.25, Feasibility 0.20, Adoption 0.15, Risk 0.10
  (sum 1.0, one constant in `prioritization.WEIGHTS`). The portfolio always groups AI-fit
  cases first, then not-a-fit, then unscored — so a high-scoring not-a-fit case can never
  outrank a real opportunity. The quadrant is Impact (y) × Feasibility (x), split at the
  scale midpoint (3). Charts are server-rendered SVG; the brief prints via `window.print()`.
- Alternatives considered: An equal-weighted mean (no opinion on what matters); a JS chart
  library (Chart.js/D3) for the quadrant; a separate PDF library for the brief; letting
  composite alone sort everything (not-a-fit cases could float to the top).
- Why: Explainability is the product (CLAUDE.md). A weighted mean is trivial to explain and
  defend, and exposing the weights as one constant makes the philosophy editable without
  touching logic. Grouping keeps the responsible-AI guardrail visible in the ranking itself.
  Server-rendered SVG + `window.print()` honor the "no build step / minimal dependencies"
  guardrail — the browser's print-to-PDF is enough for a one-page brief.
- Tradeoff accepted: The weights are a judgement call (mitigated: explicit + documented); a
  pure-CSS/SVG quadrant is less interactive than a charting lib; print-to-PDF styling is
  browser-dependent.
- Revisit if: Stakeholders want configurable weights per portfolio → move weights to config/
  the DB; or richer interactivity is needed → reconsider a charting library.

## 014. Eval re-scores the canonical seed and runs offline by default
- Date / phase: Phase 5
- Decision: `app/eval.py` re-scores the seed file (not the live DB) K times with the
  configured provider and reports three metrics — stability (composite spread), guardrail
  recall (the deliberate not-a-fit cases flagged), and rubric adherence (rationale per
  dimension + ROI present). It falls back to the `stub` provider when no `MODEL_PROVIDER`
  and no `ANTHROPIC_API_KEY` are set, so `make eval` always runs; the report names the
  provider. The stub's not-a-fit keyword markers were extended so it catches all three seed
  guardrail cases (incl. the eligibility-lookup case, which describes a DB/API lookup).
- Alternatives considered: Evaluating the stored DB scores (tests authoring, not the scorer);
  requiring a live API key for `make eval` (breaks offline/CI); a separate labelled eval set.
- Why: Re-scoring the canonical seed exercises the actual scorer and is reproducible. Offline
  default keeps the harness runnable in CI and on a demo laptop with no network. The seed's
  authored ai_fit flags are a free ground-truth label set for the guardrail check.
- Tradeoff accepted: With the stub, stability is trivially perfect and guardrail recall
  reflects keyword heuristics, not model judgment — meaningful numbers need a real provider
  (the report says which ran). The stub markers are mildly fitted to the seed vocabulary.
- Revisit if: We add many more seed cases or want true precision/recall → build a dedicated
  labelled eval set and report both precision and recall.

## 015. Surface the append-only override history on the score card (2026-07-28)
- Decision: The scoring card now renders a **"Scoring history"** section — the full append-only trail of score
  rows for a use case (seed → LLM re-scores → human overrides), newest-first, via `models.score_history`. Each
  row shows when, the source (a `human` badge for overrides), AI-fit, the five dimension values, and the
  composite priority, so a viewer can see exactly what changed and who changed it. It renders only when there
  is more than one row (nothing to compare against otherwise) and **auto-opens when a human override exists**.
  The trail is precomputed in the route (`_history_view`, composite per row) and rides in the same `_score_card`
  partial, so it stays fresh after every re-score/override HTMX swap.
- Why: The data was already append-only (DECISIONS 009) — a re-score or override inserts a new row and never
  overwrites — but the UI only showed the *latest* value, so an override read as a silent overwrite. Surfacing
  the trail makes human-in-the-loop **auditable** rather than merely possible (CLAUDE.md §2 / §5: never present
  AI output as a final decision; explainability is a feature). It reuses the existing data model and priorit-
  isation math — no schema change, no new dependency.
- Rejected: A separate history page/route (an extra click for what belongs next to the score); showing only a
  count ("overridden 2×") without the values (hides *what* changed); recomputing composites in the template
  (kept scoring math in Python — the template stays declarative); truncating to the last N rows (the trail is
  short and the whole point is completeness).
