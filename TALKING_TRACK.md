# Talking Track — AI Use-Case Intake & Prioritization Console

> Your study reference for speaking on this project. Read it, then close it and say it in your
> own words. Stage in the portfolio arc: **DECIDE** (which AI use cases to fund at all).

## ⚡ At a glance

- **Pitch:** Scores proposed AI use cases across five dimensions and ranks the portfolio — and flags
  when AI is the *wrong* tool so bad ideas can't out-rank good ones.
- **Architecture:** FastAPI + SQLite + HTMX; an LLM proposes 1–5 scores via forced tool-use,
  deterministic math ranks, and every score is stored append-only with full provenance.
- **Signature decision:** Scores are *proposals, not decisions* — humans override (append-only) and
  "when not to use AI" is built into the rubric.
- **Eval story:** `make eval` checks stability (score drift across re-runs), guardrail recall (3/3
  not-a-fit cases flagged), and rubric adherence (every score has a rationale + ROI line).

---

## The 60-second pitch

**Business framing (lead with this for leaders):**
"This is the front door for AI investment. It turns AI enthusiasm into evidence. Someone proposes
a use case; the tool scores it across five dimensions — Impact, Feasibility, Risk, Adoption, and
Strategic Value — and ranks the whole portfolio so you fund the *right* idea, not the loudest one.
The part that earns trust: it flags when AI is the *wrong* tool. Those not-a-fit cases get grouped
separately so they can never out-rank a real opportunity. Knowing when to say no to AI is the whole
point."

**Technical framing (for engineers):**
"FastAPI + SQLite + HTMX, server-rendered, no build step. An LLM proposes the 1–5 scores via
*forced tool-use* for reliable structured output. The ranking math is pure and deterministic in
`prioritization.py`. Every score — whether seeded, model-generated, or human-overridden — is stored
**append-only** with full provenance: source, model id, prompt version, timestamp. Scores are
*proposals*; a human can override any of them and the original is never destroyed."

---

## Architecture (the flow + the modules that matter)

```
intake form ──▶ LLM scoring (5 dims + rationale + ROI + AI-fit) ──▶ human override (append-only)
                                                                          │
                          portfolio ranking ◀── prioritization.py ◀───────┘
                          + Impact×Feasibility quadrant (server-rendered SVG)
                          + one-page printable decision brief
```

- `app/scoring.py` — the system prompt + rubric; forces a single tool call so the five scores,
  rationales, ROI hypothesis, and AI-fit judgment come back as structured fields, not prose.
- `app/providers.py` — provider abstraction: **Anthropic / Ollama / stub**. The stub is deterministic
  (offline demos, CI).
- `app/prioritization.py` — pure functions: composite score, quadrant placement, ordering. No LLM here.
- `app/models.py` — append-only score history (a new row per re-score or override; nothing overwritten).
- `app/eval.py` — the validation harness (see below).

**The five dimensions** (1–5, where 5 = most favorable, so Risk 5 = *low* risk):
**I**mpact · **F**easibility · **R**isk · **A**doption · **S**trategic value → mnemonic *I-FRAS*.

**Composite** = weighted mean: Impact 0.30, Strategic Value 0.25, Feasibility 0.20, Adoption 0.15,
Risk 0.10. (The weights are one editable constant — that's a feature, not magic.)

---

## The eval story (how you prove it works)

`make eval` re-scores the seed set and reports three things — *always reach for these by reflex*:

1. **Stability** — how much the composite score moves across re-runs (lower = more reliable).
2. **Guardrail recall** — the **3 deliberate not-a-fit cases must be flagged** (target 3/3 = 100%).
   This proves the "when not to use AI" guardrail actually fires.
3. **Rubric adherence** — every score carries a per-dimension rationale *and* an ROI line (no naked numbers).

35 tests cover intake, schema, seed idempotency, guardrail correctness, and rubric adherence.

---

## The signature decision

**Scores are proposals, not decisions — and "when NOT to use AI" is part of the rubric, not an
afterthought.** (DECISIONS 002 and 004.) Humans override; overrides are append-only with provenance;
not-a-fit cases are structurally prevented from out-ranking real ones. This is responsible-AI
governance built into the data model, not bolted on as a disclaimer.

---

## Honest weakness (say it before they do)

- The five dimensions and their weights are **opinionated constants** — a real org would calibrate
  them to its own strategy. (Easy to change: one constant + one prompt.)
- The **stub provider is deterministic**, so "stability" looks perfect offline. The real stability
  story needs a live model.

---

## Other things worth mentioning

- **The quadrant** (Impact × Feasibility, server-rendered SVG) gives leaders an instant "quick wins
  vs big bets vs deprioritize" read with no JS framework.
- **The decision brief** is a one-page, printable executive artifact per use case — verdict, scores,
  rationales, ROI, provenance — built to hand to a board.
- **Privacy path:** the Ollama provider means scoring can run fully on-prem; sensitive proposals
  never leave the org.

---

## The one-liner to remember

> **"Scores are proposals, not decisions — and the tool's most credible feature is knowing when to
> say no to AI."**
