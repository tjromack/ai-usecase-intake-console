"""FastAPI application entry point.

Phase 0 scope: boot the app, expose a health check, and render the base
template so the scaffold is demoable. Routes for intake, scoring, portfolio,
and brief arrive in later phases.
"""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import __version__

# Load .env early so config is available to every module. Absent .env is fine
# for Phase 0 (no LLM calls yet); scoring will validate its own keys later.
load_dotenv()

# Resolve paths relative to this file so the app runs from any working dir.
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="AI Use-Case Intake & Prioritization Console", version=__version__)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/health")
def health() -> JSONResponse:
    """Liveness probe — used by demos/tests to confirm the app booted."""
    return JSONResponse({"status": "ok", "version": __version__})


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """Landing page. Becomes the prioritized portfolio view in Phase 4."""
    return templates.TemplateResponse(
        request,
        "index.html",
        {"title": "Portfolio"},
    )
