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

from app import __version__, db, models, scoring

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


# --- health ----------------------------------------------------------------


@app.get("/health")
def health() -> JSONResponse:
    """Liveness probe — used by demos/tests to confirm the app booted."""
    return JSONResponse({"status": "ok", "version": __version__})


# --- list + search ---------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
def index(request: Request, q: str = "") -> HTMLResponse:
    """List view of submitted use cases. Becomes the portfolio in Phase 4."""
    with db.get_connection() as conn:
        cases = _filter_cases(models.list_use_cases(conn), q)
        scores = models.latest_scores(conn)
    return templates.TemplateResponse(
        request,
        "index.html",
        {"title": "Portfolio", "cases": cases, "scores": scores, "q": q},
    )


@app.get("/use-cases/search", response_class=HTMLResponse)
def search_use_cases(request: Request, q: str = "") -> HTMLResponse:
    """HTMX partial: the filtered table rows for the live-search box."""
    with db.get_connection() as conn:
        cases = _filter_cases(models.list_use_cases(conn), q)
        scores = models.latest_scores(conn)
    return templates.TemplateResponse(
        request,
        "_use_case_rows.html",
        {"cases": cases, "scores": scores},
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
