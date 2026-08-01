"""Liveness and readiness endpoint."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    """Report service status and whether the database answers."""
    try:
        db.execute(text("SELECT 1"))
        database = "up"
    except Exception:
        database = "down"

    return {
        "status": "ok" if database == "up" else "degraded",
        "service": settings.app_name,
        "environment": settings.app_env,
        "database": database,
    }
