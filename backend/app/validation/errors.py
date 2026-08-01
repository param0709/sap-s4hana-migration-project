"""Structured validation findings.

Two distinct outcomes are modelled:

* FileRejected  - the file cannot be read at all; nothing is stored.
* SchemaError   - the file is readable, but its columns do not match the
                  expected ECC Customer Master layout. The file is still
                  stored so the consultant can inspect and re-upload.
"""
from dataclasses import asdict, dataclass, field
from typing import Any

from app.constants.enums import IssueSeverity


class FileRejectedError(Exception):
    """Raised when a file fails the hard gate (type, size, emptiness, parseability)."""

    def __init__(self, code: str, message: str, detail: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail or {}

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "detail": self.detail}


@dataclass(frozen=True)
class SchemaError:
    """One column-level mismatch between the upload and the expected schema."""

    code: str
    severity: IssueSeverity
    message: str
    columns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["severity"] = str(self.severity)
        return data
