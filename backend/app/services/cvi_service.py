"""Deterministic Day 5 CVI and Business Partner readiness pre-check."""

import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants.cvi import (
    ACCOUNT_GROUP_TO_BP_GROUPING,
    BP_CATEGORY_CODE,
    BP_CATEGORY_LABEL,
    CVI_DISCLAIMER,
    CVI_METHODOLOGY_VERSION,
    REQUIRED_BP_ROLES,
    TARGET_OBJECT,
)
from app.constants.enums import IssueSeverity, RecordStatus
from app.constants.iso_country_codes import ISO_ALPHA2_CODES
from app.models import MigrationRecord, UploadedFile


class CviAssessmentRequiredError(Exception):
    """CVI readiness depends on a completed deterministic assessment."""


class CviDataUnavailableError(Exception):
    """The upload does not have a complete persisted record set."""


@dataclass(frozen=True)
class _CheckDefinition:
    check_id: str
    name: str
    severity: IssueSeverity
    explanation: str
    suggested_action: str


_CHECKS: tuple[_CheckDefinition, ...] = (
    _CheckDefinition(
        "CVI-001",
        "Account group to BP grouping",
        IssueSeverity.CRITICAL,
        "Every ECC customer account group must have a target BP grouping.",
        "Add and approve the missing account-group mapping in target CVI customizing.",
    ),
    _CheckDefinition(
        "CVI-002",
        "Business Partner identity",
        IssueSeverity.CRITICAL,
        "An organization BP requires a source customer number and organization name.",
        "Complete KUNNR and NAME1 before creating the Business Partner.",
    ),
    _CheckDefinition(
        "CVI-003",
        "Business Partner address",
        IssueSeverity.CRITICAL,
        "The target BP address requires city and a valid ISO country code.",
        "Complete ORT01 and correct LAND1 to a valid ISO alpha-2 country code.",
    ),
    _CheckDefinition(
        "CVI-004",
        "Customer company-code extension",
        IssueSeverity.CRITICAL,
        "The FLCU00 customer role requires a source company code.",
        "Complete BUKRS and confirm the company-code extension in the target system.",
    ),
    _CheckDefinition(
        "CVI-005",
        "External Business Partner number uniqueness",
        IssueSeverity.CRITICAL,
        "Each source customer number must identify only one Business Partner.",
        "Resolve duplicate KUNNR values before number assignment.",
    ),
    _CheckDefinition(
        "CVI-006",
        "Source assessment clearance",
        IssueSeverity.HIGH,
        "Records with unresolved data-quality findings are not ready for CVI conversion.",
        "Resolve the open deterministic assessment findings and rerun assessment.",
    ),
)


def _missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _failed_rows(records: list[MigrationRecord]) -> dict[str, set[int]]:
    account_groups = [_text((record.working_data or {}).get("KTOKD")).upper() for record in records]
    customer_numbers = [_text((record.working_data or {}).get("KUNNR")).upper() for record in records]
    customer_counts = Counter(value for value in customer_numbers if value)

    failed: dict[str, set[int]] = {definition.check_id: set() for definition in _CHECKS}
    for record, account_group, customer_number in zip(
        records, account_groups, customer_numbers, strict=True
    ):
        data = record.working_data or {}
        row = record.source_row_number
        country = _text(data.get("LAND1")).upper()

        if not account_group or account_group not in ACCOUNT_GROUP_TO_BP_GROUPING:
            failed["CVI-001"].add(row)
        if _missing(data.get("KUNNR")) or _missing(data.get("NAME1")):
            failed["CVI-002"].add(row)
        if _missing(data.get("ORT01")) or country not in ISO_ALPHA2_CODES:
            failed["CVI-003"].add(row)
        if _missing(data.get("BUKRS")):
            failed["CVI-004"].add(row)
        if customer_number and customer_counts[customer_number] > 1:
            failed["CVI-005"].add(row)
        if record.record_status != RecordStatus.READY:
            failed["CVI-006"].add(row)
    return failed


def calculate_cvi_readiness(
    db: Session,
    project_id: uuid.UUID,
    file_id: uuid.UUID,
) -> dict[str, Any] | None:
    """Return a transparent, read-only CVI readiness result for one file."""
    uploaded_file = db.scalar(
        select(UploadedFile).where(
            UploadedFile.id == file_id,
            UploadedFile.project_id == project_id,
        )
    )
    if uploaded_file is None:
        return None

    records = list(
        db.scalars(
            select(MigrationRecord)
            .where(
                MigrationRecord.project_id == project_id,
                MigrationRecord.uploaded_file_id == file_id,
            )
            .order_by(MigrationRecord.source_row_number)
        ).all()
    )
    if not records or (
        uploaded_file.row_count is not None and len(records) != uploaded_file.row_count
    ):
        raise CviDataUnavailableError(
            "This file has no complete persisted record set for CVI readiness. "
            "Re-upload the file before requesting the pre-check."
        )
    if any(record.record_status == RecordStatus.PENDING for record in records):
        raise CviAssessmentRequiredError(
            "Run assessment on this file before requesting CVI readiness."
        )

    failed_rows = _failed_rows(records)
    checks = []
    for definition in _CHECKS:
        rows = sorted(failed_rows[definition.check_id])
        checks.append(
            {
                "check_id": definition.check_id,
                "name": definition.name,
                "status": "failed" if rows else "passed",
                "severity": definition.severity,
                "affected_records": len(rows),
                "affected_source_rows": rows,
                "explanation": definition.explanation,
                "suggested_action": definition.suggested_action,
            }
        )

    mapped_counts: Counter[tuple[str, str]] = Counter()
    unmapped_rows: dict[str, list[int]] = defaultdict(list)
    for record in records:
        account_group = _text((record.working_data or {}).get("KTOKD")).upper()
        grouping = ACCOUNT_GROUP_TO_BP_GROUPING.get(account_group)
        if grouping is not None:
            mapped_counts[(account_group, grouping)] += 1
        elif account_group:
            unmapped_rows[account_group].append(record.source_row_number)

    blocked_rows = set().union(*failed_rows.values())
    failed_checks = sum(check["status"] == "failed" for check in checks)
    critical_blockers = sum(
        check["status"] == "failed" and check["severity"] == IssueSeverity.CRITICAL
        for check in checks
    )
    cvi_ready = failed_checks == 0

    return {
        "project_id": project_id,
        "uploaded_file_id": file_id,
        "methodology_version": CVI_METHODOLOGY_VERSION,
        "target_object": TARGET_OBJECT,
        "disclaimer": CVI_DISCLAIMER,
        "status": "ready" if cvi_ready else "blocked",
        "cvi_ready": cvi_ready,
        "total_records": len(records),
        "records_ready": len(records) - len(blocked_rows),
        "records_blocked": len(blocked_rows),
        "failed_checks": failed_checks,
        "critical_blockers": critical_blockers,
        "bp_category": {
            "code": BP_CATEGORY_CODE,
            "label": BP_CATEGORY_LABEL,
        },
        "required_bp_roles": list(REQUIRED_BP_ROLES),
        "mapped_account_groups": [
            {
                "ecc_account_group": account_group,
                "bp_grouping": grouping,
                "record_count": count,
            }
            for (account_group, grouping), count in sorted(mapped_counts.items())
        ],
        "unmapped_account_groups": [
            {
                "ecc_account_group": account_group,
                "record_count": len(rows),
                "source_rows": sorted(rows),
            }
            for account_group, rows in sorted(unmapped_rows.items())
        ],
        "checks": checks,
    }
