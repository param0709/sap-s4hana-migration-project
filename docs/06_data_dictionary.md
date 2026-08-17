# Data Dictionary

## ECC Customer Master Input

| Field | Description | Required | Example |
|---|---|---:|---|
| KUNNR | ECC customer number | Yes | 00001001 |
| NAME1 | Customer name | Yes | Alpha Traders Pvt Ltd |
| NAME2 | Additional name | No | Western Division |
| STRAS | Street address | No | 12 Linking Road |
| ORT01 | City | Yes | Mumbai |
| REGIO | State or region | No | MH |
| LAND1 | Country code | Yes | IN |
| PSTLZ | Postal code | No | 400050 |
| STCD3 | GSTIN or tax number | Conditional | 27ABCDE1234F1Z5 |
| SMTP_ADDR | Email address | No | sales@alpha.in |
| TELF1 | Phone number | No | 912234567890 |
| KTOKD | Customer account group | Yes | ZDOM |
| BUKRS | Company code | Yes | 1000 |
| ERDAT | Creation date | No | 2024-04-10 |
| LOEVM | Deletion indicator | No | X |

## S/4HANA Target Fields

| Field | Description | Required |
|---|---|---:|
| BP_EXTERNAL_ID | Source customer identifier | Yes |
| BP_CATEGORY | Business Partner category | Yes |
| BP_GROUPING | Business Partner grouping | Yes |
| ORGANIZATION_NAME_1 | Organization name | Yes |
| STREET | Street address | No |
| CITY | City | Yes |
| REGION | State or region | No |
| COUNTRY | ISO country code | Yes |
| POSTAL_CODE | Postal code | No |
| TAX_NUMBER | GSTIN or tax number | Conditional |
| EMAIL | Email address | No |
| PHONE | Phone number | No |
| COMPANY_CODE | Company code | Yes |
| SOURCE_SYSTEM | Legacy system name | Yes |
| MIGRATION_STATUS | Record status | Yes |

## Business Rule Fields

| Field | Description |
|---|---|
| RULE_ID | Unique rule identifier |
| RULE_NAME | Rule name |
| FIELD_NAME | Field being validated |
| CONDITION_EXPRESSION | Condition under which rule applies |
| VALIDATION_TYPE | Required, Regex, Length, Lookup or Custom |
| VALIDATION_EXPRESSION | Validation definition |
| ERROR_MESSAGE | Displayed failure message |
| SEVERITY | Critical, High, Medium or Low |
| SUGGESTED_ACTION | Recommended correction |
| ACTIVE | Whether the rule is enabled |

## Main Database Entities

### migration_projects

Stores project name, client, systems, object, country, status and timestamps.

### uploaded_files

Stores file metadata, category, object-storage location, row count and processing status.

### migration_records

Stores original source data, working data and readiness status.

### migration_issues

Stores validation failures, duplicate suggestions, mapping issues and severity.

### review_decisions

Stores approve, edit, reject, defer and ignore decisions.

### field_mappings

Stores source-to-target mappings, confidence scores and approval status.

### transformation_logs

Stores original value, transformed value, reason, user and timestamp.

### assistant_queries

Stores consultant questions, route type, generated SQL, response and sources.

### audit_logs

Stores important user and system actions.

## Initial Validation Rules

| Rule ID | Field | Validation | Severity |
|---|---|---|---|
| BR-001 | KUNNR | Must not be empty | Critical |
| BR-002 | NAME1 | Must not be empty | Critical |
| BR-003 | LAND1 | Must use ISO-2 code | High |
| BR-004 | STCD3 | Required for Indian business customers | Critical |
| BR-005 | STCD3 | Must match GSTIN format | High |
| BR-006 | SMTP_ADDR | Must match email format | Medium |
| BR-007 | PSTLZ | Indian postal code must contain six digits | Medium |
| BR-008 | KUNNR | Must be unique | Critical |
| BR-009 | ERDAT | Must contain a valid date | Low |
| BR-010 | LOEVM | Deleted records require review | High |
| BR-011 | ORT01 | Must not be empty | Critical |
| BR-012 | LAND1 | Must not be empty | Critical |
| BR-013 | KTOKD | Must not be empty | Critical |
| BR-014 | BUKRS | Must not be empty | Critical |
