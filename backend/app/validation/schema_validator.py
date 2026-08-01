"""Compares an uploaded ECC extract against the expected Customer Master schema.

Implements FR-008 (missing required columns) and FR-009 (unexpected and
duplicate columns). Findings are returned rather than raised: a schema mismatch
is something the consultant reviews, not a hard rejection.
"""
from app.constants.ecc_schema import KNOWN_COLUMNS, REQUIRED_COLUMNS
from app.constants.enums import IssueSeverity
from app.validation.errors import SchemaError


def normalise_headers(headers: list[str]) -> list[str]:
    """Trim and upper-case headers so comparison ignores case and stray spaces."""
    return [str(header).strip().upper() for header in headers]


def find_duplicate_columns(columns: list[str]) -> list[str]:
    """Repeated headers. Blank headers are reported separately, not as duplicates."""
    seen: set[str] = set()
    duplicates: list[str] = []
    for column in columns:
        if not column:
            continue
        if column in seen and column not in duplicates:
            duplicates.append(column)
        seen.add(column)
    return duplicates


def validate_ecc_schema(headers: list[str]) -> tuple[list[str], list[SchemaError]]:
    """Validate a file's header row. Returns (normalised_columns, errors)."""
    columns = normalise_headers(headers)
    errors: list[SchemaError] = []

    missing = [column for column in REQUIRED_COLUMNS if column not in columns]
    if missing:
        errors.append(
            SchemaError(
                code="MISSING_REQUIRED_COLUMNS",
                severity=IssueSeverity.CRITICAL,
                message=f"{len(missing)} required column(s) are not present in the file.",
                columns=missing,
            )
        )

    blank_positions = [index + 1 for index, column in enumerate(columns) if not column]
    if blank_positions:
        errors.append(
            SchemaError(
                code="BLANK_COLUMN_HEADER",
                severity=IssueSeverity.HIGH,
                message=(
                    "Some columns have no header. Name them or remove them before migrating."
                ),
                columns=[f"column {position}" for position in blank_positions],
            )
        )

    duplicates = find_duplicate_columns(columns)
    if duplicates:
        errors.append(
            SchemaError(
                code="DUPLICATE_COLUMNS",
                severity=IssueSeverity.HIGH,
                message="The file repeats the same column header more than once.",
                columns=duplicates,
            )
        )

    unexpected = sorted(
        {column for column in columns if column and column not in KNOWN_COLUMNS}
    )
    if unexpected:
        errors.append(
            SchemaError(
                code="UNEXPECTED_COLUMNS",
                severity=IssueSeverity.MEDIUM,
                message=(
                    "These columns are not part of the ECC Customer Master schema. "
                    "They will need a field mapping before migration."
                ),
                columns=unexpected,
            )
        )

    return columns, errors
