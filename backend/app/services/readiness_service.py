"""Deterministic Migration Readiness Score — methodology v1.

This module is the single source of truth for the readiness calculation. Neither
the API route nor the frontend re-implements any of this arithmetic.

The score is a **project-defined, transparent, deterministic** readiness
indicator inspired by common migration data-quality dimensions. It is NOT an
official SAP metric and must never be presented as one.

Methodology v1 combines four components, each scored 0.00–100.00:

* Schema conformity (20%)  — penalties for stored schema findings.
* Data completeness (25%)  — the existing deterministic profile completeness.
* Record readiness  (35%)  — share of records whose persisted status is ``ready``.
* Issue severity    (20%)  — weighted penalty for persisted issues.

The overall score is a weighted sum of the *unrounded* component scores; only the
public-facing values are rounded to two decimals.

Critical-blocker safety rule
----------------------------
A high numeric score must never hide a migration-blocking finding. Critical
persisted issues and critical schema findings are counted as blockers (a
critical schema finding counts once regardless of how many columns it names).
When any blocker exists the band is forced to ``blocked`` and ``migration_ready``
is ``false`` even if the numeric score is otherwise excellent.
"""
import uuid
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants.enums import (
    IssueSeverity,
    ReadinessBand,
    RecordStatus,
)
from app.models import MigrationIssue, MigrationRecord, UploadedFile
from app.services import profiling_service

METHODOLOGY_VERSION = "v1"

# Component weights. They must total 1.00.
COMPONENT_WEIGHTS: dict[str, float] = {
    "schema_conformity": 0.20,
    "data_completeness": 0.25,
    "record_readiness": 0.35,
    "issue_severity": 0.20,
}

# Schema-finding penalty per affected column, by severity.
_SCHEMA_PENALTY: dict[str, int] = {
    IssueSeverity.CRITICAL: 15,
    IssueSeverity.HIGH: 10,
    IssueSeverity.MEDIUM: 5,
    IssueSeverity.LOW: 2,
}

# Issue-severity weighting for the issue-health component.
_ISSUE_WEIGHT: dict[str, int] = {
    IssueSeverity.CRITICAL: 10,
    IssueSeverity.HIGH: 6,
    IssueSeverity.MEDIUM: 3,
    IssueSeverity.LOW: 1,
}

# Band thresholds on the (rounded) numeric score, evaluated only after the
# critical-blocker rule has been applied.
_READY_THRESHOLD = 90.0
_MINOR_THRESHOLD = 75.0
_AT_RISK_THRESHOLD = 50.0


class AssessmentRequiredError(Exception):
    """The file has not completed business-rule assessment yet."""


class ReadinessDataUnavailableError(Exception):
    """Persisted records are missing or inconsistent with the upload metadata."""


def _schema_conformity(uploaded_file: UploadedFile) -> tuple[float, int]:
    """Return (score, critical_finding_count) from stored schema findings.

    Each finding costs its severity penalty times the number of affected columns
    (at least one). A critical finding is counted once as a blocker regardless of
    how many columns it names; its column count still drives the penalty.
    """
    findings = uploaded_file.schema_errors or []
    total_penalty = 0
    critical_findings = 0
    for finding in findings:
        severity = str(finding.get("severity", ""))
        columns = finding.get("columns") or []
        penalty = _SCHEMA_PENALTY.get(severity, 0)
        total_penalty += penalty * max(1, len(columns))
        if severity == IssueSeverity.CRITICAL:
            critical_findings += 1
    score = max(0.0, 100.0 - total_penalty)
    return score, critical_findings


def _issue_severity(
    severity_counts: Counter[str],
    total_records: int,
) -> float:
    """Return the issue-health score from persisted-issue severity counts."""
    weighted_points = sum(
        _ISSUE_WEIGHT.get(severity, 0) * count
        for severity, count in severity_counts.items()
    )
    # total_records is guaranteed > 0 by the caller's defensive guard.
    return max(0.0, 100.0 - weighted_points / total_records)


def _band(score: float, critical_blockers: int) -> ReadinessBand:
    if critical_blockers > 0:
        return ReadinessBand.BLOCKED
    if score >= _READY_THRESHOLD:
        return ReadinessBand.READY
    if score >= _MINOR_THRESHOLD:
        return ReadinessBand.MINOR_REMEDIATION
    if score >= _AT_RISK_THRESHOLD:
        return ReadinessBand.AT_RISK
    return ReadinessBand.NOT_READY


def _component(raw_score: float, weight: float) -> dict[str, float]:
    return {
        "score": round(raw_score, 2),
        "weight": weight,
        "weighted_score": round(raw_score * weight, 2),
    }


def calculate_readiness(
    db: Session,
    project_id: uuid.UUID,
    file_id: uuid.UUID,
) -> dict[str, Any] | None:
    """Compute the deterministic readiness score for one assessed file.

    Read-only: this never mutates project, record or issue state. Returns None
    when the file does not exist inside the given project (the route maps that to
    404). Raises ReadinessDataUnavailableError (missing/inconsistent records) or
    AssessmentRequiredError (assessment not yet run) for the two 409 conditions.
    """
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

    total_records = len(records)
    # Defensive data-integrity guards run before anything is scored: an empty or
    # inconsistent record set is treated as unavailable data, never divided by.
    if total_records == 0 or (
        uploaded_file.row_count is not None
        and total_records != uploaded_file.row_count
    ):
        raise ReadinessDataUnavailableError(
            "This file has no complete persisted record set to score. "
            "Re-upload the file before requesting readiness."
        )

    # Assessment prerequisite. A file is assessed only when no record is still
    # pending; an empty issue list alone does not prove assessment ran, because a
    # valid assessed file legitimately has zero issues.
    if any(record.record_status == RecordStatus.PENDING for record in records):
        raise AssessmentRequiredError(
            "Run assessment on this file before requesting its readiness score."
        )

    records_ready = sum(
        record.record_status == RecordStatus.READY for record in records
    )
    records_needing_review = sum(
        record.record_status == RecordStatus.NEEDS_REVIEW for record in records
    )

    # Data completeness reuses the existing profiling result rather than
    # recomputing any profiling mathematics here.
    profile = profiling_service.profile_file(db, project_id, file_id)
    completeness_score = float(profile["overall_completeness_percentage"])

    schema_score, critical_schema_findings = _schema_conformity(uploaded_file)
    record_score = records_ready / total_records * 100.0

    severity_counts: Counter[str] = Counter(
        str(severity)
        for severity in db.scalars(
            select(MigrationIssue.severity).where(
                MigrationIssue.project_id == project_id,
                MigrationIssue.uploaded_file_id == file_id,
            )
        ).all()
    )
    total_issues = sum(severity_counts.values())
    severity_score = _issue_severity(severity_counts, total_records)

    critical_blockers = (
        severity_counts.get(IssueSeverity.CRITICAL, 0) + critical_schema_findings
    )

    # Overall uses the unrounded component scores; only public values are rounded.
    overall_raw = (
        schema_score * COMPONENT_WEIGHTS["schema_conformity"]
        + completeness_score * COMPONENT_WEIGHTS["data_completeness"]
        + record_score * COMPONENT_WEIGHTS["record_readiness"]
        + severity_score * COMPONENT_WEIGHTS["issue_severity"]
    )
    overall = round(overall_raw, 2)

    band = _band(overall, critical_blockers)
    migration_ready = overall >= _READY_THRESHOLD and critical_blockers == 0

    return {
        "project_id": project_id,
        "uploaded_file_id": file_id,
        "methodology_version": METHODOLOGY_VERSION,
        "score": overall,
        "band": band,
        "migration_ready": migration_ready,
        "critical_blockers": critical_blockers,
        "total_records": total_records,
        "records_ready": records_ready,
        "records_needing_review": records_needing_review,
        "total_issues": total_issues,
        "components": {
            "schema_conformity": _component(
                schema_score, COMPONENT_WEIGHTS["schema_conformity"]
            ),
            "data_completeness": _component(
                completeness_score, COMPONENT_WEIGHTS["data_completeness"]
            ),
            "record_readiness": _component(
                record_score, COMPONENT_WEIGHTS["record_readiness"]
            ),
            "issue_severity": _component(
                severity_score, COMPONENT_WEIGHTS["issue_severity"]
            ),
        },
    }
