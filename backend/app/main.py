"""FastAPI application entry point."""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, projects, uploads
from app.config import settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    Path(settings.storage_dir).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.5.0",
    description=(
        "Projects, lossless ECC ingestion, schema validation, deterministic profiling, "
        "deterministic record-level business-rule assessment and a project-defined "
        "deterministic migration readiness score and a Day 5 CVI/Business Partner "
        "readiness pre-check."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(projects.router, prefix=settings.api_prefix)
app.include_router(uploads.router, prefix=settings.api_prefix)
app.include_router(uploads.reference_router, prefix=settings.api_prefix)


@app.get("/")
def root() -> dict:
    return {"service": settings.app_name, "docs": "/docs", "api": settings.api_prefix}
