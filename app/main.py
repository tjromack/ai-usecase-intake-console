"""FastAPI application: routes and view wiring.

Phase 2 scope: structured intake (create/edit a use case) and a searchable list
view, rendered server-side with HTMX. Scoring/override (Phase 3) and the
portfolio/quadrant/brief (Phase 4) build on these routes.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import __version__, db, models, prioritization, scoring

# Load .env early so config is available to every module. Absent .env is fine
# until scoring needs a key (Phase 3); scoring validates its own config.
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Intake fields accepted from the form, in display order.
INTAKE_FIELDS = [
    "title",
    "problem",
    "workflow",
    "data_availability",
    "stakeholders",
    "current_pain",
    "submitter",
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Ensure the schema exists so a fresh clone never 500s before `make seed`."""
    with db.get_connection() as conn:
        models.create_schema(conn)
    yield


app = FastAPI(
    title="AI Use-Case Intake & Prioritization Console",
    version=__version__,
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["tier"] = prioritization.tier  # composite -> styling band


# --- helpers ---------------------------------------------------------------


def _intake_data(**fields: str) -> dict:
    """Normalize submitted form values: strip whitespace, keep known fields."""
    return {key: (value or "").strip() for key, value in fields.items()}


def _validate_intake(data: dict) -> dict[str, str]:
    """Return {field: message} for any required field that is empty."""
    errors: dict[str, str] = {}
    if not data.get("title"):
        errors["title"] = "A short title is required."
    if not data.get("problem"):
        errors["problem"] = "Describe the problem this use case addresses."
    return errors


def _filter_cases(cases, query: str):
    """Case-insensitive substring match across the most useful text fields."""
    q = query.strip().lower()
    if not q:
        return cases
    fields = ("title", "problem", "workflow", "submitter")
    return [c for c in cases if any(q in (c[f] or "").lower() for f in fields)]


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _portfolio_rows(conn, q: str, sort: str, direction: str) -> list[dict]:
    """Filtered, prioritized portfolio rows (case fields + composite/quadrant)."""
    cases = _filter_cases(models.list_use_cases(conn), q)
    scores = models.latest_scores(conn)
    rows = [prioritization.row_for(c, scores.get(c["id"])) for c in cases]
    return prioritization.order(rows, sort, direction)


# --- health ----------------------------------------------------------------


@app.get("/health")
def health() -> JSONResponse:
    """Liveness probe — used by demos/tests to confirm the app booted."""
    return JSONResponse({"status": "ok", "version": __version__})


# --- list + search ---------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request, q: str = "", sort: str = "composite", dir: str = "desc"
) -> HTMLResponse:
    """Prioritized portfolio: composite-ranked, AI-fit cases first."""
    with db.get_connection() as conn:
        rows = _portfolio_rows(conn, q, sort, dir)
    return templates.TemplateResponse(
        request,
        "index.html",
        {"title": "Portfolio", "rows": rows, "q": q, "sort": sort, "dir": dir},
    )


@app.get("/use-cases/search", response_class=HTMLResponse)
def search_use_cases(
    request: Request, q: str = "", sort: str = "composite", dir: str = "desc"
) -> HTMLResponse:
    """HTMX partial: the filtered/sorted table rows for the live-search box."""
    with db.get_connection() as conn:
        rows = _portfolio_rows(conn, q, sort, dir)
    return templates.TemplateResponse(request, "_use_case_rows.html", {"rows": rows})


# --- quadrant + brief (Phase 4) --------------------------------------------

# Impact (y) x Feasibility (x) scatter. Server-rendered SVG, no JS chart lib.
_CHART_W, _CHART_H, _CHART_PAD = 560, 400, 56


def _quadrant_chart(conn) -> dict:
    """Compute SVG geometry for the impact/feasibility quadrant."""
    plot_w = _CHART_W - 2 * _CHART_PAD
    plot_h = _CHART_H - 2 * _CHART_PAD

    def px(value: int) -> float:  # feasibility -> x
        return _CHART_PAD + (value - 1) / 4 * plot_w

    def py(value: int) -> float:  # impact -> y (inverted)
        return (_CHART_H - _CHART_PAD) - (value - 1) / 4 * plot_h

    scores = models.latest_scores(conn)
    points = []
    for case in models.list_use_cases(conn):
        score = scores.get(case["id"])
        if score is None:
            continue
        # Small deterministic jitter so co-located points don't fully overlap.
        jx = ((case["id"] % 3) - 1) * 7
        jy = (((case["id"] // 3) % 3) - 1) * 7
        points.append(
            {
                "id": case["id"],
                "title": case["title"],
                "cx": round(px(score["feasibility"]) + jx, 1),
                "cy": round(py(score["impact"]) + jy, 1),
                "fit": score["ai_fit"] == 1,
                "impact": score["impact"],
                "feasibility": score["feasibility"],
                "composite": prioritization.composite(score),
            }
        )

    return {
        "w": _CHART_W,
        "h": _CHART_H,
        "pad": _CHART_PAD,
        "midx": round(px(3), 1),
        "midy": round(py(3), 1),
        "xticks": [{"x": round(px(v), 1), "label": v} for v in range(1, 6)],
        "yticks": [{"y": round(py(v), 1), "label": v} for v in range(1, 6)],
        "points": points,
    }


@app.get("/quadrant", response_class=HTMLResponse)
def quadrant(request: Request) -> HTMLResponse:
    """Impact/feasibility quadrant view over all scored use cases."""
    with db.get_connection() as conn:
        chart = _quadrant_chart(conn)
    return templates.TemplateResponse(
        request, "quadrant.html", {"title": "Quadrant", "chart": chart}
    )


@app.get("/use-cases/{use_case_id}/brief", response_class=HTMLResponse)
def decision_brief(request: Request, use_case_id: int) -> HTMLResponse:
    """One-page decision brief for a use case (printable to PDF)."""
    with db.get_connection() as conn:
        case = models.get_use_case(conn, use_case_id)
        score = models.latest_score_for(conn, use_case_id) if case else None
    if case is None:
        return _not_found(request)
    return templates.TemplateResponse(
        request,
        "brief.html",
        {
            "title": f"Brief · {case['title']}",
            "case": case,
            "score": score,
            "dimensions": models.DIMENSIONS,
            "composite": prioritization.composite(score),
            "quadrant": prioritization.quadrant(score),
        },
    )


# --- intake: create --------------------------------------------------------


@app.get("/use-cases/new", response_class=HTMLResponse)
def new_use_case(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "intake_page.html",
        {
            "title": "New use case",
            "data": {},
            "errors": {},
            "action": "/use-cases",
            "heading": "Submit a use case",
        },
    )


@app.post("/use-cases")
def create_use_case(
    request: Request,
    title: str = Form(""),
    problem: str = Form(""),
    workflow: str = Form(""),
    data_availability: str = Form(""),
    stakeholders: str = Form(""),
    current_pain: str = Form(""),
    submitter: str = Form(""),
) -> Response:
    data = _intake_data(
        title=title,
        problem=problem,
        workflow=workflow,
        data_availability=data_availability,
        stakeholders=stakeholders,
        current_pain=current_pain,
        submitter=submitter,
    )
    errors = _validate_intake(data)
    if errors:
        return templates.TemplateResponse(
            request,
            "_intake_form.html",
            {"data": data, "errors": errors, "action": "/use-cases"},
            status_code=422,
        )
    with db.get_connection() as conn:
        new_id = models.insert_use_case(conn, data)
    return _redirect(request, f"/use-cases/{new_id}")


# --- intake: edit ----------------------------------------------------------


@app.get("/use-cases/{use_case_id}/edit", response_class=HTMLResponse)
def edit_use_case(request: Request, use_case_id: int) -> HTMLResponse:
    with db.get_connection() as conn:
        case = models.get_use_case(conn, use_case_id)
    if case is None:
        return _not_found(request)
    return templates.TemplateResponse(
        request,
        "intake_page.html",
        {
            "title": f"Edit · {case['title']}",
            "data": dict(case),
            "errors": {},
            "action": f"/use-cases/{use_case_id}",
            "heading": "Edit use case",
        },
    )


@app.post("/use-cases/{use_case_id}")
def update_use_case(
    request: Request,
    use_case_id: int,
    title: str = Form(""),
    problem: str = Form(""),
    workflow: str = Form(""),
    data_availability: str = Form(""),
    stakeholders: str = Form(""),
    current_pain: str = Form(""),
    submitter: str = Form(""),
) -> Response:
    data = _intake_data(
        title=title,
        problem=problem,
        workflow=workflow,
        data_availability=data_availability,
        stakeholders=stakeholders,
        current_pain=current_pain,
        submitter=submitter,
    )
    errors = _validate_intake(data)
    if errors:
        return templates.TemplateResponse(
            request,
            "_intake_form.html",
            {
                "data": {**data, "id": use_case_id},
                "errors": errors,
                "action": f"/use-cases/{use_case_id}",
            },
            status_code=422,
        )
    with db.get_connection() as conn:
        if models.get_use_case(conn, use_case_id) is None:
            return _not_found(request)
        models.update_use_case(conn, use_case_id, data)
    return _redirect(request, f"/use-cases/{use_case_id}")


# --- detail ----------------------------------------------------------------


@app.get("/use-cases/{use_case_id}", response_class=HTMLResponse)
def use_case_detail(request: Request, use_case_id: int) -> HTMLResponse:
    with db.get_connection() as conn:
        case = models.get_use_case(conn, use_case_id)
        score = models.latest_score_for(conn, use_case_id) if case else None
    if case is None:
        return _not_found(request)
    return templates.TemplateResponse(
        request,
        "use_case_detail.html",
        {
            "title": case["title"],
            "case": case,
            "score": score,
            "dimensions": models.DIMENSIONS,
            "composite": prioritization.composite(score),
            "quadrant": prioritization.quadrant(score),
        },
    )


# --- scoring (Phase 3) -----------------------------------------------------


def _score_card(
    request: Request, case, score, error: str | None = None
) -> HTMLResponse:
    """Render the scoring card partial (the HTMX swap target)."""
    return templates.TemplateResponse(
        request,
        "_score_card.html",
        {
            "case": case,
            "score": score,
            "dimensions": models.DIMENSIONS,
            "composite": prioritization.composite(score),
            "quadrant": prioritization.quadrant(score),
            "error": error,
        },
    )


@app.post("/use-cases/{use_case_id}/score/run")
def run_scoring(request: Request, use_case_id: int):
    """Propose scores via the LLM and store them (source='llm')."""
    with db.get_connection() as conn:
        case = models.get_use_case(conn, use_case_id)
    if case is None:
        return _not_found(request)

    # Call the provider outside any open DB connection (it may be slow/networked).
    try:
        proposal = scoring.score_use_case(case)
    except scoring.ScoringError as exc:
        with db.get_connection() as conn:
            score = models.latest_score_for(conn, use_case_id)
        return _score_card(request, case, score, error=str(exc))

    with db.get_connection() as conn:
        models.insert_score(conn, use_case_id, proposal, source="llm")
        score = models.latest_score_for(conn, use_case_id)

    if _is_htmx(request):
        return _score_card(request, case, score)
    return RedirectResponse(f"/use-cases/{use_case_id}", status_code=303)


@app.get("/use-cases/{use_case_id}/score/card", response_class=HTMLResponse)
def score_card(request: Request, use_case_id: int):
    """Return the current scoring card (used by the override form's Cancel)."""
    with db.get_connection() as conn:
        case = models.get_use_case(conn, use_case_id)
        score = models.latest_score_for(conn, use_case_id) if case else None
    if case is None:
        return _not_found(request)
    return _score_card(request, case, score)


@app.get("/use-cases/{use_case_id}/score/override", response_class=HTMLResponse)
def override_form(request: Request, use_case_id: int):
    """Return the editable override form, pre-filled with the current score."""
    with db.get_connection() as conn:
        case = models.get_use_case(conn, use_case_id)
        score = models.latest_score_for(conn, use_case_id) if case else None
    if case is None:
        return _not_found(request)
    return templates.TemplateResponse(
        request,
        "_score_form.html",
        {"case": case, "score": score, "dimensions": models.DIMENSIONS, "errors": {}},
    )


@app.post("/use-cases/{use_case_id}/score/override")
async def save_override(request: Request, use_case_id: int):
    """Persist a human override as a new score row (source='human')."""
    with db.get_connection() as conn:
        case = models.get_use_case(conn, use_case_id)
    if case is None:
        return _not_found(request)

    form = await request.form()
    data: dict = {}
    errors: dict[str, str] = {}
    for dimension, _label in models.DIMENSIONS:
        try:
            value = int(form.get(dimension, ""))
            if not 1 <= value <= 5:
                raise ValueError
            data[dimension] = value
        except (TypeError, ValueError):
            errors[dimension] = "Enter 1–5."
        data[f"{dimension}_rationale"] = (
            form.get(f"{dimension}_rationale") or ""
        ).strip()

    data["roi_hypothesis"] = (form.get("roi_hypothesis") or "").strip()
    data["ai_fit"] = form.get("ai_fit") == "on"
    data["ai_fit_reason"] = (form.get("ai_fit_reason") or "").strip()

    if errors:
        return templates.TemplateResponse(
            request,
            "_score_form.html",
            {
                "case": case,
                "score": data,
                "dimensions": models.DIMENSIONS,
                "errors": errors,
            },
            status_code=422,
        )

    data["model"] = "human"
    data["prompt_version"] = "human-override"
    with db.get_connection() as conn:
        models.insert_score(conn, use_case_id, data, source="human")
        score = models.latest_score_for(conn, use_case_id)

    if _is_htmx(request):
        return _score_card(request, case, score)
    return RedirectResponse(f"/use-cases/{use_case_id}", status_code=303)


# --- shared responses ------------------------------------------------------


def _redirect(request: Request, url: str) -> Response:
    """HTMX-aware redirect: HX-Redirect header for HTMX, 303 otherwise."""
    if _is_htmx(request):
        resp = Response(status_code=204)
        resp.headers["HX-Redirect"] = url
        return resp
    return RedirectResponse(url, status_code=303)


def _not_found(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "not_found.html", {"title": "Not found"}, status_code=404
    )
