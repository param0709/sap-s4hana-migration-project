"""Project-defined Customer-Vendor Integration reference configuration.

This synthetic mapping catalog exists to make the Day 5 workflow deterministic
and demonstrable. Real engagements must replace it with client-approved CVI
customizing exported from the target S/4HANA system.
"""

CVI_METHODOLOGY_VERSION = "v1"
TARGET_OBJECT = "SAP S/4HANA Business Partner"
BP_CATEGORY_CODE = "2"
BP_CATEGORY_LABEL = "Organization"
REQUIRED_BP_ROLES: tuple[str, ...] = ("FLCU00",)

# ECC customer account group -> target Business Partner grouping.
ACCOUNT_GROUP_TO_BP_GROUPING: dict[str, str] = {
    "0001": "BP01",
    "ZDOM": "ZDOM",
    "ZEXP": "ZEXP",
}

CVI_DISCLAIMER = (
    "This is a project-defined pre-check, not an official SAP CVI validation. "
    "Confirm account-group mappings, number ranges, BP groupings and roles in "
    "the target S/4HANA system before migration."
)
