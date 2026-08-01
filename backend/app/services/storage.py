"""Filesystem storage for uploaded originals.

Isolated from the database layer so it can be swapped for object storage later
without touching the ingestion logic.
"""
import uuid
from pathlib import Path

from app.config import settings


def project_storage_dir(project_id: uuid.UUID) -> Path:
    directory = Path(settings.storage_dir) / str(project_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def store_original(project_id: uuid.UUID, file_id: uuid.UUID, file_name: str, content: bytes) -> str:
    """Write the received bytes verbatim and return the storage path.

    ``Path(file_name).name`` strips any directory component, so a crafted
    filename cannot write outside the project's own storage directory.
    """
    path = project_storage_dir(project_id) / f"{file_id}_{Path(file_name).name}"
    path.write_bytes(content)
    return str(path)
