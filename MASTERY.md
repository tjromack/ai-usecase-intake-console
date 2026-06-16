# MASTERY.md — Owning This Project

Five things to do cold, without notes: **explain** it in 60 seconds, **draw** the
architecture, **rebuild** the core engine, **extend** it to a new domain, and **defend** every
decision to a skeptic.

> **Quick map of the codebase**
> - `app/main.py` — FastAPI routes + HTMX views (portfolio, intake, scoring, quadrant, brief)
> - `app/db.py` — SQLite connection scope (row factory, FK on, commit/rollback)
> - `app/models.py` — schema + data access; the `score` table is **append-only**
> - `app/seed.py` — idempotent loader for the synthetic seed
> - `app/scoring.py` — the rubric/system prompt + `score_use_case()` engine
> - `app/providers.py` — model abstraction: `anthropic` | `ollama` | `stub`
> - `app/prioritization.py` — pure math: composite, quadrant, ordering
> - `app/eval.py` — re-scores the seed; stability / guardrail / rubric report
> - `data/use_cases.seed.json` — the domain content (10 synthetic payer cases)
> - `DECISIONS.md` — 14 ADR-lite entries; the "why" behind every choice

---

## 1. Explain what it does and why, in plain English, in 60 seconds

> It's a single front door for an AI opportunity pipeline. A stakeholder describes a pain
> point in plain language; the tool captures it as a structured use case, then an LLM
> **proposes** scores across five dimensions — Impact, Feasibility, Risk, Adoption, Strategic
> Value — each with a one-line rationale, an ROI hypothesis, and an explicit *fit / not a fit
> for AI* judgment. Those roll up into a 0–100 priority score, a ranked portfolio, an
> impact/feasibility quadrant, and a printable one-page decision brief. The single most
> important property: **the AI proposes, a human decides.** Every value is editable, overrides
> are stored with full provenance, and the tool will tell you when AI is the *wrong* tool — a
> ledger reconciliation or an eligibility lookup gets flagged "not a fit" instead of being
> forced into an AI-shaped solution. It runs on synthetic data only.

**The one-sentence version.** It turns a messy stream of AI ideas into a ranked, explainable
portfolio — and flags the ideas where AI is the wrong tool.

**The three words to never lose:** **propose-not-decide** (human-in-the-loop),
**explainable** (every number carries a rationale + provenance), **not-a-fit** (the
when-not-to-use-AI guardrail).

**Self-check:** you've got it when you can say the domain, the five dimensions, and the anchor
property (AI proposes / human decides / it can say "not a fit") in one breath.

---

## 2. Draw the architecture from memory

```
            ┌─────────────── Browser (HTMX, no build step) ───────────────┐
            │  portfolio · intake form · use-case page · quadrant · brief  │
            └───────────────────────────┬──────────────────────────────────┘
                                         │ HTTP / HTMX partial swaps
                                         ▼
                                  app/main.py  (routes/views)
            ┌───────────────┬────────────┼─────────────────┬───────────────┐
            ▼               ▼            ▼                  ▼               ▼
        intake          scoring     prioritization      eval          db.py
       (form →       score_use_case  composite/         evaluate()   connection
        insert)           │          quadrant/order        │         scope
            │             │             (pure)             │            │
            │             ▼                                │            ▼
            │      app/providers.py  ── propose() ──┐      │      SQLite file
            │      get_provider()                   │      │   data/console.db
            │         │     │      │                │      │  (use_case + score,
            │   ┌─────┘     │      └─────┐          │      │   score is append-only)
            │   ▼           ▼            ▼          │      │
            │ Anthropic   Ollama       stub  ◀──────┴──────┘
            │ (forced     (local)    (offline,    re-scores the seed set
            │  tool use)            deterministic)
            ▼
       models.insert_score(... source = seed | llm | human)   ← latest row wins
```

**Memory aids.**
- **Stages (mnemonic "I-S-P-B"): Intake → Score → Prioritize → Brief.** Eval sits to the side,
  re-running Score over the seed.
- **The external model call happens in exactly one place:** `providers.py::propose()`. Nothing
  else in the codebase talks to a model. Swap the provider, the rest is unchanged.
- **Offline vs online split:** everything is local except the `anthropic` provider, which
  sends the use-case text to the Claude API. `ollama` (local) and `stub` (in-process,
  deterministic) keep it fully offline.
- **Determinism boundary:** storage, ranking, and quadrant math are deterministic; only the
  scoring step is non-deterministic, and it's stamped with `model` + `prompt_version` +
  `source` so any number is traceable.

**Self-check:** you can draw it when you can place the single model call, name the three
providers, and show the append-only `score` table with the three sources.

---

## 3. Rebuild this core engine from scratch

**Build order & contracts** (this is also the dependency order):

1. **`db.py`** — `get_connection() → sqlite3.Connection` (context manager: row factory, FK
   enforcement, commit on success / rollback on error). First because everything persists.
2. **`models.py`** — schema DDL + typed access. Key contract: `score` is **append-only** —
   `insert_score(conn, use_case_id, score_dict, source) → id` always inserts; `latest_scores(conn) → {use_case_id: row}`
   selects `MAX(id)` per case. Dimensions are 1–5, **5 = most favorable** (Risk inverted:
   5 = low risk).
3. **`seed.py`** — `seed_database(conn) → count`; idempotent (upserts cases by `slug`,
   replaces only `source='seed'` scores). Gives every later stage real data to run on.
4. **`providers.py`** — `get_provider() → provider`, and `provider.propose(system, user, schema) → schema instance`.
   The schema is passed in (no import cycle with scoring). Anthropic uses a **forced tool call**
   for structured output; missing key → `ProviderError`, never a silent fake.
5. **`scoring.py`** — `score_use_case(case) → dict`. Builds the user prompt, calls a provider
   with `SYSTEM_PROMPT` + the `ScoreProposal` schema, clamps each dimension to 1–5, stamps
   `model` + `prompt_version` (`score-v2`). Raises `ScoringError` on any provider failure.
6. **`prioritization.py`** — pure functions: `composite(score) → 0–100` (weighted mean),
   `quadrant(score) → label`, `order(rows, sort, dir) → list` (AI-fit grouped first), `row_for(case, score) → dict`.
7. **`eval.py`** — `evaluate(runs) → summary` + `format_report(summary) → str`: re-scores the
   seed and computes stability / guardrail / rubric.

**The minimal happy path in pseudocode** (the thing to write cold):

```
case = intake_form()                       # title, problem, workflow, ...
with get_connection() as conn:
    uc_id = insert_use_case(conn, case)

# scoring — the one non-deterministic step
provider = get_provider()                  # anthropic | ollama | stub
proposal = provider.propose(SYSTEM_PROMPT, format_use_case(case), ScoreProposal)
score = clamp_to_1_5(proposal)
score["model"] = provider.label            # provenance
score["prompt_version"] = PROMPT_VERSION

with get_connection() as conn:
    insert_score(conn, uc_id, score, source="llm")   # append-only
    current = latest_score_for(conn, uc_id)

# human overrides everything, stored as a NEW row
insert_score(conn, uc_id, edited, source="human")

# deterministic rollups
priority = composite(current)              # 0..100
cell     = quadrant(current)               # Quick wins | Big bets | ...
rows     = order([row_for(c, latest[c.id]) for c in cases])  # fit-first
```

**Non-core add-ons:** `main.py` is just the web layer (FastAPI routes + HTMX partial swaps);
templates/CSS are hand-rolled with no framework; `eval.py` is a self-check harness, not part
of the request path.

**Self-check:** you can rebuild it when you can write the happy path above from memory and say
why `propose()` takes the schema as an argument (no import cycle; provider stays generic).

---

## 4. Extend it to a new domain by swapping the "swap layer"

This project is a **reusable scoring/prioritization engine + a thin domain swap layer.** To
port it (e.g. from healthcare AI use cases to grant proposals, vendor selection, or research
ideas), you touch only these:

| Swap this | File | What changes |
| --- | --- | --- |
| Seed content | `data/use_cases.seed.json` | The domain examples + their authored scores; keep ≥2 deliberate "not a fit" cases |
| Rubric & domain framing | `app/scoring.py` → `SYSTEM_PROMPT` | What "good" means per dimension, the domain context, the not-a-fit criteria — then **bump `PROMPT_VERSION`** |
| Priority weights | `app/prioritization.py` → `WEIGHTS` | How the five dimensions combine into the composite |
| Quadrant axes | `app/prioritization.py` → `quadrant()` / `main.py` → `_quadrant_chart` | Which two dimensions form the 2×2 (currently Impact × Feasibility) |
| Offline heuristic vocab | `app/providers.py` → `_NOT_FIT_MARKERS` | The stub's domain words that signal "AI is the wrong tool" |
| Intake fields | `app/models.py` → `USE_CASE_COLUMNS`, `main.py` → `INTAKE_FIELDS`, `templates/_intake_form.html` | What you capture per record |
| Dimension labels* | `app/models.py` → `DIMENSIONS` + `score` columns | The five axes themselves (*this one crosses the engine seam — see below) |

**The engine you DON'T touch:** `db.py` (connection mechanics), the append-only `score`
history and `latest_scores` logic in `models.py`, the `propose()` provider contract in
`providers.py`, the `composite` / `order` math shape in `prioritization.py`, the `eval.py`
harness structure, and the HTMX web layer. None of these reference "healthcare" — they only
know "a record with five 1–5 numbers, rationales, a fit boolean, and provenance."

**The recipe:**
1. Replace `data/use_cases.seed.json` with your domain's cases (+ authored seed scores,
   including at least two "not a fit" examples so the guardrail is demonstrable).
2. Rewrite `SYSTEM_PROMPT` for the new domain and rubric semantics; **bump `PROMPT_VERSION`**
   so old and new scores stay traceable.
3. Adjust `WEIGHTS` to your prioritization philosophy (they sum to 1.0).
4. Update `_NOT_FIT_MARKERS` so the offline stub catches your domain's obvious non-fits.
5. (Optional) adjust intake fields if you capture different inputs.
6. `make reset && make test && MODEL_PROVIDER=stub make eval`.

**Why it's this clean:** the domain lives in *data + one prompt + a few constants*. The math,
storage, provider abstraction, and eval are domain-blind — they operate on a generic
five-number record. The one caveat: changing the *number or names* of the dimensions touches
the schema columns in `models.py` (the engine seam), so the cleanest swaps keep the same five
axes and change only their **meaning** via the prompt.

**Self-check:** you can extend it when you can name the swap files without looking and explain
why renaming a dimension is the one edit that reaches into the engine.

---

## 5. Defend every design decision to a skeptic

**Why an LLM to score, instead of a deterministic weighted form? (002)**
The hard, valuable part is reasoning about an ambiguous use case from a short description —
exactly what an LLM is good at, and exactly what this triage requires. A pure form just shifts
all the thinking back to the user. I accept the non-determinism and *measure* it (`make eval`
stability check), and I record the model + prompt version with every score.

**Then how do you stop the model from being arbitrary or hallucinating? (003, 004, 012)**
Three layers. (1) **Human-in-the-loop is mandatory** — every score, rationale, and fit flag is
editable, and overrides are stored. (2) **Structured output** via a forced tool call, so the
result always validates against the `ScoreProposal` schema — no free-text parsing. (3) The
prompt forces an explicit **not-a-fit** judgment with a written reason. And when scoring can't
run (e.g. no API key), it raises a visible error — it never invents numbers.

**Why forced tool use instead of the newer `messages.parse()` structured-output API? (012)**
Version-robustness. The pinned SDK is `anthropic==0.42.0`, and forced tool use works across
SDK versions and all Claude 4.x models while sidestepping the Opus 4.8 request-surface changes
(no `temperature`/`budget_tokens`). It's a deliberate "works everywhere" choice; the doc notes
I'd switch to `messages.parse()` if we standardize on a newer SDK.

**Why a pluggable provider, and what's the `stub`? (007, 012)**
One `propose()` interface, three backends: `anthropic` (default), `ollama` (local,
privacy-preserving), and `stub` (deterministic heuristic, no key/network). The stub keeps the
app demoable offline and makes tests/eval deterministic. It's clearly labelled as heuristic in
the UI — it's a stand-in, not a pretend model.

**Why SQLite + HTMX + FastAPI instead of Postgres and a React SPA? (001)**
One developer, short timeline, must demo reliably on a laptop with no build step. SQLite is
zero-config and resets in one command; HTMX gives interactivity without a frontend toolchain.
The tradeoff — SQLite won't take production concurrency — is acceptable for a prototype and
documented in the Path to Production.

**Why is the score table append-only? (009)**
The product thesis is capturing *why* a decision was made. Append-only gives a free audit
trail: every re-score or override is a new row tagged `seed` / `llm` / `human`, and reads take
the latest. It costs a "latest per case" join and table growth — worth it for the provenance
story.

**Why is Risk scored 5 = low risk? That reads backwards. (010)**
So that "higher is always better," which lets the composite be a plain weighted mean with no
per-dimension sign-flipping. It's the one counter-intuitive convention, so every scoring view
shows a legend and each Risk rationale states the posture in words. The fallback (relabel to
"Risk posture") is recorded if reviewers find it confusing.

**How is the composite computed, and aren't the weights arbitrary? (013)**
Weighted mean of the five 1–5 dimensions mapped to 0–100: Impact 0.30, Strategic Value 0.25,
Feasibility 0.20, Adoption 0.15, Risk 0.10. The weights are a judgment call — so they're
*explicit*, sum to 1.0, and live in one constant (`prioritization.WEIGHTS`). And not-a-fit
cases are grouped separately in the ranking so a high-scoring non-fit can never out-rank a real
opportunity.

**What does the eval actually prove, and what are the honest caveats? (014)**
`make eval` re-scores the seed and reports three things: **stability** (composite spread across
runs), **guardrail recall** (the deliberate not-a-fit cases flagged), and **rubric adherence**
(rationale per dimension + ROI present). Offline with the stub I get **stability max 0.0
[deterministic], guardrail 3/3 (100%), rubric 30/30 (100%), PASS**. Caveats, stated plainly:
with the stub, stability is *trivially* perfect because it's deterministic, and guardrail
recall reflects keyword heuristics, not model judgment — meaningful stability numbers need the
live provider (run `MODEL_PROVIDER=anthropic make eval` with a key and network). The stub's
not-a-fit markers are also mildly fitted to the seed vocabulary.

**Gotcha I'd own up front:** `make eval` reads `.env`. If `.env` selects the `anthropic`
provider and there's no network, the eval **errors** rather than scoring — that's by design (no
silent fake), but it means "the offline number" is `MODEL_PROVIDER=stub make eval`, not a bare
`make eval` on a configured machine.

**Data and compliance posture. (005)**
All data is synthetic and authored in-repo — no real claims, members, or PHI, and not wired to
any production system. `.env` (which may hold an API key) is git-ignored and was verified absent
from the published repo. The `anthropic` provider is the only path that sends text off the
machine; `ollama`/`stub` keep everything local.

**Self-check:** you can defend it when, for any decision a skeptic names, you can state the
rejected alternative, the tradeoff you accepted, and — for the eval — the real number *and* its
caveat without getting defensive.

---

### How to use this doc

Read it once end to end, then drill the five **self-checks** — they map 1:1 to the five things
you must do cold. You own the project when you can do all five from a blank board: explain it,
draw it, rebuild the happy path, list the swap-layer files, and defend any decision with its
rejected alternative and real numbers.

## Mastery checklist

```
- [ ] 1. Explain it in 60 seconds (domain + the anchor property), no notes
- [ ] 2. Draw the architecture from a blank board (stages, splits, external calls, guardrails)
- [ ] 3. Name the modules in build order, state each contract, write the happy path cold
- [ ] 4. List the swap-layer files, say what stays untouched and why
- [ ] 5. Defend any decision a skeptic names — alternative rejected + real numbers + caveats
```
