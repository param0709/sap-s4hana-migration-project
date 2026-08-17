# Day 5 — CVI and Business Partner Readiness

Day 5 adds a deterministic, read-only pre-check for converting ECC Customer Master
records into SAP S/4HANA Business Partners through Customer-Vendor Integration (CVI).
The result is available after the normal business-rule assessment completes.

> This is a project-defined pre-check, not an official SAP CVI validation. Every real
> engagement must replace the demo mappings with client-approved target customizing.

## Target assumptions

| Setting | Demo value |
|---|---|
| Target object | SAP S/4HANA Business Partner |
| BP category | `2` — Organization |
| Required customer role | `FLCU00` |
| Number assignment | Existing `KUNNR` treated as the external identity pre-check |

The deterministic demo catalog maps ECC account groups to BP groupings:

| ECC account group | Target BP grouping |
|---|---|
| `0001` | `BP01` |
| `ZDOM` | `ZDOM` |
| `ZEXP` | `ZEXP` |

The catalog lives in `backend/app/constants/cvi.py` so it is visible, testable and easy
to replace. It is not presented as target-system truth.

## Pre-checks

| Check | Severity | Pass condition |
|---|---|---|
| `CVI-001` Account group → BP grouping | Critical | Every nonblank `KTOKD` has an approved mapping |
| `CVI-002` BP identity | Critical | `KUNNR` and `NAME1` are present |
| `CVI-003` BP address | Critical | `ORT01` is present and `LAND1` is a valid ISO alpha-2 code |
| `CVI-004` Company-code extension | Critical | `BUKRS` is present for the `FLCU00` role |
| `CVI-005` External number uniqueness | Critical | Every nonblank `KUNNR` is unique in the extract |
| `CVI-006` Source assessment clearance | High | The underlying record passed all deterministic business rules |

The response includes each failed check, its affected record count, and the original
spreadsheet/CSV row numbers. A result is `ready` only when all six checks pass.

## API

```http
GET /api/v1/projects/{project_id}/files/{file_id}/cvi-readiness
GET /api/v1/reference/cvi
```

The readiness endpoint returns `409 ASSESSMENT_REQUIRED` before assessment and
`409 CVI_DATA_UNAVAILABLE` when the persisted record set is incomplete. It never changes
records, issues or project status.

## Production integration boundary

Before using this workflow on a real program, import and approve the target system's CVI
customizing, number ranges, BP groupings, roles, field mappings, tax categories and
country-specific address rules. Add connectivity and reconciliation against the target
S/4HANA system as a separate, authenticated integration; this repository intentionally
does not pretend that a local configuration is an SAP validation result.
