"""PULSE — FastAPI Streaming Service & Tactical Cockpit Entrypoint.

Provides the FastAPI application instance, lifespan initialization for ML artifacts
and SQLite persistence, static asset delivery, and health check monitoring endpoint.

Authority: Phase 6 Decisions D-9, D-11, D-12, Phase 6.5 Decisions D-1, D-3, D-8, ADR-013.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from langgraph.graph.state import CompiledStateGraph

from src.api.schemas import HealthCheckResponse
from src.api.streaming import streaming_router
from src.config.loader import load_params
from src.graph.pulse_graph import build_pulse_graph
from src.utils.logger import get_logger
from src.utils.persistence import init_db

logger = get_logger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager loading graph artifacts and initializing SQLite once at startup.

    Authority: Phase 6 Decision D-12 (Artifacts and graph loaded once at process startup).
    """
    logger.info("Initializing PULSE FastAPI application lifespan...")
    params = load_params()

    # 1. Initialize SQLite persistence layer (D-4)
    await init_db(params.api.db_path)

    # 2. Build and compile LangGraph orchestration graph once (D-12)
    compiled_graph: CompiledStateGraph = build_pulse_graph(params=params)
    app.state.graph = compiled_graph
    app.state.graph_ready = True
    app.state.version = "0.1.0"
    logger.info("PULSE application lifespan initialization complete: graph compiled & ready.")

    yield

    logger.info("PULSE FastAPI application shutting down...")
    app.state.graph = None
    app.state.graph_ready = False


app = FastAPI(
    title="PULSE — Streaming & Tactical Cockpit API",
    description=(
        "Point-Level Understanding & Strategic Leverage Engine Real-Time Streaming "
        "& Presentation Layer"
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Mount static directory for CSS, JS, and UI assets (D-1, D-3)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 2. Include REST & SSE streaming routers
app.include_router(streaming_router)


# 3. Explicit Single-Page Application HTML delivery endpoints (D-8)
@app.get(
    "/",
    response_class=HTMLResponse,
    tags=["UI"],
    summary="Tactical Cockpit Dashboard",
)
async def serve_root_ui() -> FileResponse:
    """Serve the single-page interactive Tactical Cockpit interface."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get(
    "/ui",
    response_class=HTMLResponse,
    tags=["UI"],
    summary="Tactical Cockpit Dashboard (Alias)",
)
async def serve_ui_alias() -> FileResponse:
    """Alias route serving the single-page interactive Tactical Cockpit interface."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get(
    "/health",
    response_model=HealthCheckResponse,
    tags=["Health"],
    summary="Service Health and Readiness Check",
)
async def health_check() -> HealthCheckResponse:
    """Return service health status, graph readiness, and loaded artifact keys (D-11)."""
    has_ready_flag = bool(getattr(app.state, "graph_ready", False))
    has_graph_instance = getattr(app.state, "graph", None) is not None
    graph_ready = has_ready_flag and has_graph_instance
    status = "healthy" if graph_ready else "degraded"

    return HealthCheckResponse(
        status=status,
        graph_ready=graph_ready,
        version=getattr(app.state, "version", "0.1.0"),
        artifacts_loaded=[
            "stratum_table",
            "pressure_model_artifact",
            "payoff_matrices",
        ],
    )


def run_server() -> None:
    """Launch the FastAPI server using uvicorn with configured host and port."""
    import uvicorn

    params = load_params()
    uvicorn.run(
        "src.api.main:app",
        host=params.api.host,
        port=params.api.port,
        log_level="info",
    )


if __name__ == "__main__":
    run_server()
