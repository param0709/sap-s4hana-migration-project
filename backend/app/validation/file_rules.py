"""Hard gate applied to every upload before anything is parsed or stored.

Checks: extension, declared size, emptiness. A failure here means the file is
rejected outright (FR-005) and never reaches the schema validator.
"""
from app.validation.errors import FileRejectedError

ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".xlsx", ".csv"})


def normalise_extension(file_name: str) -> str:
    """Return the lower-cased extension of a filename, including the dot."""
    if "." not in file_name:
        return ""
    return "." + file_name.rsplit(".", 1)[1].lower()


def check_file_name(file_name: str | None) -> str:
    if not file_name or not file_name.strip():
        raise FileRejectedError("MISSING_FILENAME", "The upload has no file name.")
    return file_name.strip()


def check_extension(file_name: str) -> str:
    """Reject anything that is not an Excel or CSV file."""
    extension = normalise_extension(file_name)
    if extension not in ALLOWED_EXTENSIONS:
        raise FileRejectedError(
            "UNSUPPORTED_FILE_TYPE",
            "Upload an Excel (.xlsx) or CSV (.csv) file. "
            f"'{extension or 'no extension'}' is not supported.",
            {"allowed": sorted(ALLOWED_EXTENSIONS), "received": extension},
        )
    return extension


def check_not_empty(content: bytes, file_name: str) -> None:
    if len(content) == 0:
        raise FileRejectedError(
            "EMPTY_FILE", f"'{file_name}' contains no data.", {"size_bytes": 0}
        )


def check_size(content: bytes, file_name: str, max_bytes: int) -> None:
    if len(content) > max_bytes:
        raise FileRejectedError(
            "FILE_TOO_LARGE",
            f"'{file_name}' is larger than the {max_bytes // (1024 * 1024)} MB limit.",
            {"size_bytes": len(content), "max_bytes": max_bytes},
        )


def validate_upload(content: bytes, file_name: str | None, max_bytes: int) -> tuple[str, str]:
    """Run the full hard gate. Returns (clean_file_name, extension)."""
    clean_name = check_file_name(file_name)
    extension = check_extension(clean_name)
    check_not_empty(content, clean_name)
    check_size(content, clean_name, max_bytes)
    return clean_name, extension
