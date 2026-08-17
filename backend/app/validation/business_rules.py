"""Pure deterministic ECC Customer Master business-rule validation."""
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.constants.enums import IssueSeverity
from app.constants.iso_country_codes import ISO_ALPHA2_CODES

_GSTIN_PATTERN = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"
)
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_INDIAN_POSTAL_PATTERN = re.compile(r"^[0-9]{6}$")


@dataclass(frozen=True)
class RuleDefinition:
    rule_id: str
    rule_name: str
    field_name: str
    severity: IssueSeverity
    reason: str
    suggested_action: str


@dataclass(frozen=True)
class RuleFinding:
    rule_id: str
    rule_name: str
    field_name: str
    severity: IssueSeverity
    current_value: Any
    reason: str
    suggested_action: str


RULES: tuple[RuleDefinition, ...] = (
    RuleDefinition(
        "BR-001",
        "Customer number required",
        "KUNNR",
        IssueSeverity.CRITICAL,
        "ECC customer number is missing.",
        "Enter the source customer number before migration.",
    ),
    RuleDefinition(
        "BR-002",
        "Customer name required",
        "NAME1",
        IssueSeverity.CRITICAL,
        "Customer name is missing.",
        "Enter the customer or organisation name before migration.",
    ),
    RuleDefinition(
        "BR-003",
        "ISO country code",
        "LAND1",
        IssueSeverity.HIGH,
        "Country is not a valid ISO 3166-1 alpha-2 code.",
        "Replace the value with a valid two-letter country code.",
    ),
    RuleDefinition(
        "BR-004",
        "GSTIN required for India",
        "STCD3",
        IssueSeverity.CRITICAL,
        "GSTIN is missing for an Indian customer.",
        "Enter the customer's GSTIN before migration.",
    ),
    RuleDefinition(
        "BR-005",
        "GSTIN format",
        "STCD3",
        IssueSeverity.HIGH,
        "GSTIN does not match the required 15-character format.",
        "Correct the GSTIN using the official registration value.",
    ),
    RuleDefinition(
        "BR-006",
        "Email format",
        "SMTP_ADDR",
        IssueSeverity.MEDIUM,
        "Email address has an invalid format.",
        "Enter a valid email address or leave the optional field blank.",
    ),
    RuleDefinition(
        "BR-007",
        "Indian postal-code format",
        "PSTLZ",
        IssueSeverity.MEDIUM,
        "Indian postal code must contain exactly six digits.",
        "Enter a valid six-digit Indian postal code.",
    ),
    RuleDefinition(
        "BR-008",
        "Unique customer number",
        "KUNNR",
        IssueSeverity.CRITICAL,
        "ECC customer number occurs more than once in this file.",
        "Review every occurrence and retain one unique customer number.",
    ),
    RuleDefinition(
        "BR-009",
        "Creation-date format",
        "ERDAT",
        IssueSeverity.LOW,
        "Creation date is not a valid ISO date or datetime.",
        "Correct the date using ISO format, for example 2024-04-10.",
    ),
    RuleDefinition(
        "BR-010",
        "Deleted customer review",
        "LOEVM",
        IssueSeverity.HIGH,
        "Customer is marked for deletion in SAP ECC.",
        "Review the deletion flag before including this customer.",
    ),
    RuleDefinition(
        "BR-011",
        "City required",
        "ORT01",
        IssueSeverity.CRITICAL,
        "Customer city is missing.",
        "Enter the customer city before migration.",
    ),
    RuleDefinition(
        "BR-012",
        "Country required",
        "LAND1",
        IssueSeverity.CRITICAL,
        "Customer country is missing.",
        "Enter a valid two-letter country code before migration.",
    ),
    RuleDefinition(
        "BR-013",
        "Customer account group required",
        "KTOKD",
        IssueSeverity.CRITICAL,
        "ECC customer account group is missing.",
        "Enter the source account group before CVI mapping.",
    ),
    RuleDefinition(
        "BR-014",
        "Company code required",
        "BUKRS",
        IssueSeverity.CRITICAL,
        "Customer company code is missing.",
        "Enter the company code before migration.",
    ),
)

_RULE_BY_ID = {rule.rule_id: rule for rule in RULES}


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, float):
        return math.isnan(value) or math.isinf(value)
    return False


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _country(value: Any) -> str:
    return _text(value).upper()


def _valid_date(value: Any) -> bool:
    if isinstance(value, (date, datetime)):
        return True
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _duplicate_key(value: Any) -> str | None:
    if _is_missing(value):
        return None
    return _text(value).upper()


def _finding(rule_id: str, current_value: Any) -> RuleFinding:
    rule = _RULE_BY_ID[rule_id]
    return RuleFinding(
        rule_id=rule.rule_id,
        rule_name=rule.rule_name,
        field_name=rule.field_name,
        severity=rule.severity,
        current_value=current_value,
        reason=rule.reason,
        suggested_action=rule.suggested_action,
    )


def evaluate_business_rules(
    records: Sequence[Mapping[str, Any]],
) -> list[list[RuleFinding]]:
    """Return findings aligned to input order without modifying source records."""
    customer_keys = [_duplicate_key(record.get("KUNNR")) for record in records]
    counts = Counter(key for key in customer_keys if key is not None)
    results: list[list[RuleFinding]] = []

    for record, customer_key in zip(records, customer_keys, strict=True):
        findings: list[RuleFinding] = []
        country = _country(record.get("LAND1"))
        gstin = record.get("STCD3")
        email = record.get("SMTP_ADDR")
        postal_code = record.get("PSTLZ")
        creation_date = record.get("ERDAT")

        if _is_missing(record.get("KUNNR")):
            findings.append(_finding("BR-001", record.get("KUNNR")))
        if _is_missing(record.get("NAME1")):
            findings.append(_finding("BR-002", record.get("NAME1")))
        if country and country not in ISO_ALPHA2_CODES:
            findings.append(_finding("BR-003", record.get("LAND1")))
        if country == "IN" and _is_missing(gstin):
            findings.append(_finding("BR-004", gstin))
        if country == "IN" and not _is_missing(gstin):
            if _GSTIN_PATTERN.fullmatch(_text(gstin)) is None:
                findings.append(_finding("BR-005", gstin))
        if not _is_missing(email) and _EMAIL_PATTERN.fullmatch(_text(email)) is None:
            findings.append(_finding("BR-006", email))
        if country == "IN" and not _is_missing(postal_code):
            if _INDIAN_POSTAL_PATTERN.fullmatch(_text(postal_code)) is None:
                findings.append(_finding("BR-007", postal_code))
        if customer_key is not None and counts[customer_key] > 1:
            findings.append(_finding("BR-008", record.get("KUNNR")))
        if not _is_missing(creation_date) and not _valid_date(creation_date):
            findings.append(_finding("BR-009", creation_date))
        if _text(record.get("LOEVM")).upper() == "X":
            findings.append(_finding("BR-010", record.get("LOEVM")))
        if _is_missing(record.get("ORT01")):
            findings.append(_finding("BR-011", record.get("ORT01")))
        if _is_missing(record.get("LAND1")):
            findings.append(_finding("BR-012", record.get("LAND1")))
        if _is_missing(record.get("KTOKD")):
            findings.append(_finding("BR-013", record.get("KTOKD")))
        if _is_missing(record.get("BUKRS")):
            findings.append(_finding("BR-014", record.get("BUKRS")))

        results.append(findings)

    return results
