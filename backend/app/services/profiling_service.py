"""Deterministic profiling over migration records stored in the database."""
import json
import math
import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MigrationRecord, UploadedFile
from app.validation.parser import build_record_keys


class ProfileDataUnavailableError(Exception):
    """An uploaded file exists but predates durable migration-record storage."""


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, float):
        return math.isnan(value) or math.isinf(value)
    return False


def _canonical(value: Any) -> str:
    """Stable representation used only for deterministic equality/counting."""
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def _field_order(uploaded_file: UploadedFile, records: list[dict[str, Any]]) -> list[str]:
    """Prefer source-column order, then append any defensive record-only keys."""
    headers = uploaded_file.detected_columns or []
    ordered = build_record_keys(headers)
    seen = set(ordered)

    for record in records:
        for field_name in record:
            if field_name not in seen:
                seen.add(field_name)
                ordered.append(field_name)
    return ordered


def profile_file(
    db: Session,
    project_id: uuid.UUID,
    file_id: uuid.UUID,
) -> dict[str, Any] | None:
    """Calculate FR-011–FR-014 metrics from immutable database records.

    Unique counts exclude missing values. An exact duplicate is every occurrence
    after the first record with identical original_data; groups expose the first
    row as the representative and identify every later duplicate row.
    """
    uploaded_file = db.scalar(
        select(UploadedFile).where(
            UploadedFile.id == file_id,
            UploadedFile.project_id == project_id,
        )
    )
    if uploaded_file is None:
        return None

    rows = db.execute(
        select(MigrationRecord.source_row_number, MigrationRecord.original_data)
        .where(
            MigrationRecord.project_id == project_id,
            MigrationRecord.uploaded_file_id == file_id,
        )
        .order_by(MigrationRecord.source_row_number)
    ).all()

    if uploaded_file.row_count is not None and len(rows) != uploaded_file.row_count:
        raise ProfileDataUnavailableError(
            "The persisted record count does not match this upload's metadata. Re-upload the file to rebuild a complete profile source."
        )

    row_numbers = [row.source_row_number for row in rows]
    records = [row.original_data or {} for row in rows]
    total_records = len(records)
    field_names = _field_order(uploaded_file, records)
    total_fields = len(field_names)

    fields: list[dict[str, Any]] = []
    total_missing_values = 0
    for field_name in field_names:
        values = [record.get(field_name) for record in records]
        missing_values = sum(_is_missing(value) for value in values)
        non_missing_values = total_records - missing_values
        unique_values = len(
            {_canonical(value) for value in values if not _is_missing(value)}
        )
        completeness = (
            round(non_missing_values * 100 / total_records, 2)
            if total_records
            else 0.0
        )
        total_missing_values += missing_values
        fields.append(
            {
                "field_name": field_name,
                "total_records": total_records,
                "missing_values": missing_values,
                "non_missing_values": non_missing_values,
                "unique_values": unique_values,
                "completeness_percentage": completeness,
            }
        )

    duplicate_members: dict[str, list[int]] = defaultdict(list)
    for row_number, record in zip(row_numbers, records, strict=True):
        duplicate_members[_canonical(record)].append(row_number)

    duplicate_groups = [
        {
            "representative_row_number": members[0],
            "duplicate_row_numbers": members[1:],
            "record_count": len(members),
            "duplicate_count": len(members) - 1,
        }
        for members in duplicate_members.values()
        if len(members) > 1
    ]
    exact_duplicate_records = sum(
        group["duplicate_count"] for group in duplicate_groups
    )

    possible_values = total_records * total_fields
    overall_completeness = (
        round((possible_values - total_missing_values) * 100 / possible_values, 2)
        if possible_values
        else 0.0
    )

    return {
        "project_id": project_id,
        "uploaded_file_id": file_id,
        "file_name": uploaded_file.file_name,
        "total_records": total_records,
        "total_fields": total_fields,
        "total_missing_values": total_missing_values,
        "overall_completeness_percentage": overall_completeness,
        "exact_duplicate_records": exact_duplicate_records,
        "exact_duplicate_groups": len(duplicate_groups),
        "fields": fields,
        "duplicate_groups": duplicate_groups,
    }
