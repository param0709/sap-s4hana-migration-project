"""ECC Customer Master schema definition (source of truth for Day 1 schema checks).

Column list and requirement flags are taken directly from the project
data dictionary, section "ECC Customer Master Input".
"""

# Columns the migration cannot proceed without.
REQUIRED_COLUMNS: tuple[str, ...] = (
    "KUNNR",   # ECC customer number
    "NAME1",   # Customer name
    "ORT01",   # City
    "LAND1",   # Country code
    "KTOKD",   # Customer account group
    "BUKRS",   # Company code
)

# Columns that are expected but not mandatory.
OPTIONAL_COLUMNS: tuple[str, ...] = (
    "NAME2",       # Additional name
    "STRAS",       # Street address
    "REGIO",       # State or region
    "PSTLZ",       # Postal code
    "STCD3",       # GSTIN or tax number (conditional)
    "SMTP_ADDR",   # Email address
    "TELF1",       # Phone number
    "ERDAT",       # Creation date
    "LOEVM",       # Deletion indicator
)

KNOWN_COLUMNS: tuple[str, ...] = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

COLUMN_DESCRIPTIONS: dict[str, str] = {
    "KUNNR": "ECC customer number",
    "NAME1": "Customer name",
    "NAME2": "Additional name",
    "STRAS": "Street address",
    "ORT01": "City",
    "REGIO": "State or region",
    "LAND1": "Country code",
    "PSTLZ": "Postal code",
    "STCD3": "GSTIN or tax number",
    "SMTP_ADDR": "Email address",
    "TELF1": "Phone number",
    "KTOKD": "Customer account group",
    "BUKRS": "Company code",
    "ERDAT": "Creation date",
    "LOEVM": "Deletion indicator",
}
