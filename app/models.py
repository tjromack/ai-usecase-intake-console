"""Data model: schema DDL and typed access helpers.

Two tables:
  * ``use_case`` — the intake record (one row per proposed use case).
  * ``score``    — append-only scoring records. A re-score or human override
    inserts a NEW row; the latest row per use case is the current value
    (DECISIONS 009). This preserves a full audit trail of why a score changed.

Scoring convention (DECISIONS 010): every dimension is 1–5 where 5 is the most
favorable for prioritization. For ``risk`` that means 5 = low / well-managed
risk, so the composite math in Phase 4 can treat all dimensions uniformly.
"""

import sqlite3
from typing import Optional

# (column, human label) for the five scoring dimensions, in display order.
DIMENSIONS: list[tuple[str, str]] = [
    ("impact", "Impact"),
    ("feasibility", "Feasibility"),
    ("risk", "Risk"),
    ("adoption", "Adoption"),
    ("strategic_value", "Strategic Value"),
]

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS use_case (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    slug              TEXT UNIQUE,          -- stable id for idempotent seeding
    title             TEXT NOT NULL,
    problem           TEXT NOT NULL,        -- the problem statement
    workflow          TEXT,                 -- affected workflow
    data_availability TEXT,
    stakeholders      TEXT,
    current_pain      TEXT,
    submitter         TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS score (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    use_case_id              INTEGER NOT NULL
                                 REFERENCES use_case(id) ON DELETE CASCADE,

    -- Five dimensions: 1-5 (5 = most favorable), each with a one-line rationale.
    impact                   INTEGER CHECK (impact IS NULL OR impact BETWEEN 1 AND 5),
    impact_rationale         TEXT,
    feasibility              INTEGER CHECK (feasibility IS NULL OR feasibility BETWEEN 1 AND 5),
    feasibility_rationale    TEXT,
    risk                     INTEGER CHECK (risk IS NULL OR risk BETWEEN 1 AND 5),
    risk_rationale           TEXT,
    adoption                 INTEGER CHECK (adoption IS NULL OR adoption BETWEEN 1 AND 5),
    adoption_rationale       TEXT,
    strategic_value          INTEGER CHECK (strategic_value IS NULL OR strategic_value BETWEEN 1 AND 5),
    strategic_value_rationale TEXT,

    roi_hypothesis           TEXT,
    ai_fit                   INTEGER NOT NULL DEFAULT 1,  -- 1 = fit, 0 = not a fit
    ai_fit_reason            TEXT,

    -- Provenance (CLAUDE.md: record model + prompt version with each score).
    model                    TEXT,
    prompt_version           TEXT,
    source                   TEXT NOT NULL DEFAULT 'llm',  -- 'seed' | 'llm' | 'human'
    created_at               TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Latest-score lookups select MAX(id) per use case; this supports that.
CREATE INDEX IF NOT EXISTS idx_score_use_case ON score (use_case_id, id DESC);
"""

USE_CASE_COLUMNS = [
    "slug",
    "title",
    "problem",
    "workflow",
    "data_availability",
    "stakeholders",
    "current_pain",
    "submitter",
]

SCORE_COLUMNS = [
    "impact",
    "impact_rationale",
    "feasibility",
    "feasibility_rationale",
    "risk",
    "risk_rationale",
    "adoption",
    "adoption_rationale",
    "strategic_value",
    "strategic_value_rationale",
    "roi_hypothesis",
    "ai_fit",
    "ai_fit_reason",
    "model",
    "prompt_version",
    "source",
]


def create_schema(conn: sqlite3.Connection) -> None:
    """Create tables and indexes if they do not already exist."""
    conn.executescript(SCHEMA_SQL)


def upsert_use_case(conn: sqlite3.Connection, data: dict) -> int:
    """Insert a use case, or update it in place if its ``slug`` already exists.

    Keyed on ``slug`` so re-seeding is idempotent. Returns the row id.
    """
    cols = [c for c in USE_CASE_COLUMNS if c in data]
    vals = [data[c] for c in cols]
    existing = conn.execute(
        "SELECT id FROM use_case WHERE slug = ?", (data.get("slug"),)
    ).fetchone()
    if existing:
        assignments = ", ".join(f"{c} = ?" for c in cols)
        conn.execute(
            f"UPDATE use_case SET {assignments} WHERE id = ?", [*vals, existing["id"]]
        )
        return existing["id"]
    placeholders = ", ".join("?" * len(cols))
    cur = conn.execute(
        f"INSERT INTO use_case ({', '.join(cols)}) VALUES ({placeholders})", vals
    )
    return int(cur.lastrowid)


def insert_score(
    conn: sqlite3.Connection,
    use_case_id: int,
    score: dict,
    source: Optional[str] = None,
) -> int:
    """Insert a new score row (append-only). ``source`` overrides any in ``score``.

    Accepts ``ai_fit`` as a bool or int. Returns the new row id.
    """
    data = dict(score)
    if source is not None:
        data["source"] = source
    if isinstance(data.get("ai_fit"), bool):
        data["ai_fit"] = int(data["ai_fit"])

    cols = ["use_case_id"] + [c for c in SCORE_COLUMNS if c in data]
    vals = [use_case_id] + [data[c] for c in SCORE_COLUMNS if c in data]
    placeholders = ", ".join("?" * len(cols))
    cur = conn.execute(
        f"INSERT INTO score ({', '.join(cols)}) VALUES ({placeholders})", vals
    )
    return int(cur.lastrowid)


def clear_seed_scores(conn: sqlite3.Connection, use_case_id: int) -> None:
    """Remove prior seed-authored scores for a use case.

    Keeps re-seeding idempotent (one seed score per case) without touching any
    human overrides or LLM scores recorded later.
    """
    conn.execute(
        "DELETE FROM score WHERE use_case_id = ? AND source = 'seed'", (use_case_id,)
    )


def list_use_cases(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """All use cases, oldest first."""
    return conn.execute("SELECT * FROM use_case ORDER BY id").fetchall()


def get_use_case(conn: sqlite3.Connection, use_case_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM use_case WHERE id = ?", (use_case_id,)
    ).fetchone()


def latest_scores(conn: sqlite3.Connection) -> dict[int, sqlite3.Row]:
    """Map of use_case_id -> its most recent score row (latest wins)."""
    rows = conn.execute(
        """
        SELECT s.*
        FROM score s
        JOIN (
            SELECT use_case_id, MAX(id) AS max_id
            FROM score
            GROUP BY use_case_id
        ) latest ON s.id = latest.max_id
        """
    ).fetchall()
    return {row["use_case_id"]: row for row in rows}


def latest_score_for(
    conn: sqlite3.Connection, use_case_id: int
) -> Optional[sqlite3.Row]:
    """The most recent score row for one use case, or None if unscored."""
    return conn.execute(
        "SELECT * FROM score WHERE use_case_id = ? ORDER BY id DESC LIMIT 1",
        (use_case_id,),
    ).fetchone()
