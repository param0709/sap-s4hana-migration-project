"""Unit tests for deterministic BR-001 through BR-010 evaluation."""
import copy
from datetime import datetime

import pytest

from app.constants.enums import IssueSeverity
from app.validation.business_rules import RULES, evaluate_business_rules


@pytest.fixture()
def valid_record() -> dict:
    return {
        "KUNNR": "00001001",
        "NAME1": "Alpha Traders Pvt Ltd",
        "ORT01": "Mumbai",
        "LAND1": "IN",
        "KTOKD": "ZDOM",
        "BUKRS": "1000",
        "STCD3": "27ABCDE1234F1Z5",
        "SMTP_ADDR": "sales@alpha.in",
        "PSTLZ": "400050",
        "ERDAT": "2024-04-10",
        "LOEVM": None,
    }


def rule_ids(findings) -> list[str]:
    return [finding.rule_id for finding in findings]


def test_catalog_contains_the_documented_rules_in_order():
    assert [rule.rule_id for rule in RULES] == [
        f"BR-{number:03d}" for number in range(1, 11)
    ]
    assert len({rule.rule_id for rule in RULES}) == 10


def test_valid_indian_record_has_no_findings(valid_record):
    assert evaluate_business_rules([valid_record]) == [[]]


@pytest.mark.parametrize(
    ("field_name", "value", "expected_rule"),
    [
        ("KUNNR", None, "BR-001"),
        ("NAME1", "   ", "BR-002"),
        ("LAND1", "ZZ", "BR-003"),
        ("STCD3", None, "BR-004"),
        ("STCD3", "27ABC123", "BR-005"),
        ("SMTP_ADDR", "not-an-email", "BR-006"),
        ("PSTLZ", "40005", "BR-007"),
        ("ERDAT", "2024-02-30", "BR-009"),
        ("LOEVM", "X", "BR-010"),
    ],
)
def test_each_record_level_rule_is_isolated(
    valid_record, field_name, value, expected_rule
):
    valid_record[field_name] = value

    assert rule_ids(evaluate_business_rules([valid_record])[0]) == [expected_rule]


def test_duplicate_customer_number_flags_every_occurrence(valid_record):
    second = copy.deepcopy(valid_record)
    second["NAME1"] = "Second Customer"

    results = evaluate_business_rules([valid_record, second])

    assert rule_ids(results[0]) == ["BR-008"]
    assert rule_ids(results[1]) == ["BR-008"]


def test_duplicate_matching_trims_and_ignores_case(valid_record):
    valid_record["KUNNR"] = " ab12 "
    second = copy.deepcopy(valid_record)
    second["KUNNR"] = "AB12"

    results = evaluate_business_rules([valid_record, second])

    assert all(rule_ids(findings) == ["BR-008"] for findings in results)


def test_distinct_zero_padded_customer_numbers_remain_distinct(valid_record):
    second = copy.deepcopy(valid_record)
    second["KUNNR"] = "1001"

    assert evaluate_business_rules([valid_record, second]) == [[], []]


def test_optional_blank_values_do_not_fail(valid_record):
    for field_name in ("SMTP_ADDR", "PSTLZ", "ERDAT", "LOEVM"):
        valid_record[field_name] = None

    assert evaluate_business_rules([valid_record]) == [[]]


def test_non_indian_customer_does_not_require_gstin_or_indian_postal_code(
    valid_record,
):
    valid_record.update({"LAND1": "AE", "STCD3": None, "PSTLZ": "Dubai"})

    assert evaluate_business_rules([valid_record]) == [[]]


def test_country_lookup_accepts_trimmed_lowercase_iso_code(valid_record):
    valid_record["LAND1"] = " in "

    assert evaluate_business_rules([valid_record]) == [[]]


def test_gstin_format_remains_case_sensitive(valid_record):
    valid_record["STCD3"] = "27abcde1234f1z5"

    assert rule_ids(evaluate_business_rules([valid_record])[0]) == ["BR-005"]


@pytest.mark.parametrize(
    "value",
    ["2024-04-10", "2024-04-10T00:00:00", "2024-04-10T00:00:00Z"],
)
def test_iso_date_and_datetime_strings_are_accepted(valid_record, value):
    valid_record["ERDAT"] = value

    assert evaluate_business_rules([valid_record]) == [[]]


def test_datetime_object_is_accepted(valid_record):
    valid_record["ERDAT"] = datetime(2024, 4, 10, 12, 30)

    assert evaluate_business_rules([valid_record]) == [[]]


def test_numeric_six_digit_indian_postal_code_is_accepted(valid_record):
    valid_record["PSTLZ"] = 400050

    assert evaluate_business_rules([valid_record]) == [[]]


def test_multiple_findings_follow_rule_id_order(valid_record):
    valid_record.update(
        {
            "KUNNR": None,
            "NAME1": "",
            "LAND1": "ZZ",
            "SMTP_ADDR": "invalid",
            "ERDAT": "not-a-date",
            "LOEVM": "x",
        }
    )

    assert rule_ids(evaluate_business_rules([valid_record])[0]) == [
        "BR-001",
        "BR-002",
        "BR-003",
        "BR-006",
        "BR-009",
        "BR-010",
    ]


def test_finding_contains_complete_issue_metadata(valid_record):
    valid_record["SMTP_ADDR"] = "bad-email"

    finding = evaluate_business_rules([valid_record])[0][0]

    assert finding.rule_id == "BR-006"
    assert finding.rule_name == "Email format"
    assert finding.field_name == "SMTP_ADDR"
    assert finding.severity == IssueSeverity.MEDIUM
    assert finding.current_value == "bad-email"
    assert finding.reason
    assert finding.suggested_action


def test_evaluation_does_not_modify_input_records(valid_record):
    before = copy.deepcopy(valid_record)

    evaluate_business_rules([valid_record])

    assert valid_record == before


def test_empty_input_returns_empty_output():
    assert evaluate_business_rules([]) == []
