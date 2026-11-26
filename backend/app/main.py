from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import init_db
from .routers import (
    agents,
    analysis,
    analytics,
    appointments,
    auth,
    calls,
    hubspot,
    integrations,
    kb,
    leads,
    organizations,
    tasks,
    voice,
)

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    app = FastAPI(title="SalesPilot AI", version="1.0.0")

    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()] or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup():
        init_db()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    for module in (
        auth,
        organizations,
        leads,
        agents,
        calls,
        voice,
        analytics,
        integrations,
        analysis,
        kb,
        appointments,
        tasks,
        hubspot,
    ):
        app.include_router(module.router, prefix=API_PREFIX)
    app.include_router(analysis.leads_router, prefix=API_PREFIX)
    app.include_router(hubspot.logs_router, prefix=API_PREFIX)

    frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app


app = create_app()
