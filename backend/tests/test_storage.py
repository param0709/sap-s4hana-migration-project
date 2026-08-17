"""Filesystem compensation and containment tests."""

from pathlib import Path

import pytest

from app.config import settings
from app.services.storage import remove_original


def test_remove_original_refuses_a_path_outside_upload_storage(tmp_path, monkeypatch):
    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    outside = tmp_path / "must-stay.csv"
    outside.write_bytes(b"source evidence")
    monkeypatch.setattr(settings, "storage_dir", str(storage_root))

    with pytest.raises(ValueError):
        remove_original(str(outside))

    assert outside.read_bytes() == b"source evidence"
