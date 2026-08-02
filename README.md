# SAP S/4HANA Migration Co-Pilot

Through Day 4 of the 20-day plan: create a migration project, upload an ECC Customer
Master extract, preserve every source row, validate its columns, calculate deterministic
data-quality profile metrics, run deterministic business-rule assessment (`BR-001`–`BR-010`)
and read a transparent, project-defined Migration Readiness Score.

AI, RAG, CVI checks, field mapping, human review, transformations and exports remain
scheduled for later days.

## What works today

| Capability | Where |
|---|---|
| Health check | `GET /api/v1/health` |
| Create project | `POST /api/v1/projects` |
| List projects | `GET /api/v1/projects` |
| Get project | `GET /api/v1/projects/{project_id}` |
| Upload ECC file | `POST /api/v1/projects/{project_id}/files/ecc` |
| List project files | `GET /api/v1/projects/{project_id}/files` |
| Profile uploaded ECC file | `GET /api/v1/projects/{project_id}/files/{file_id}/profile` |
| Run business-rule assessment | `POST /api/v1/projects/{project_id}/files/{file_id}/assessment` |
| List persisted issues | `GET /api/v1/projects/{project_id}/files/{file_id}/issues` |
| Migration readiness score | `GET /api/v1/projects/{project_id}/files/{file_id}/readiness` |
| Expected ECC layout | `GET /api/v1/reference/ecc-schema` |

Interactive API docs run at `http://localhost:8000/docs`.

The frontend adds an **Assessment & readiness** workspace at
`/projects/:projectId/assessment`: it shows profiling, lets the consultant run assessment,
lists persisted issues (filterable by severity) and renders the readiness score.

## Running it

```bash
cp .env.example .env
docker compose up --build
```

Then open `http://localhost:5173`.

Migrations run automatically when the backend container starts.

## Running the tests

Backend (in-memory SQLite, no running PostgreSQL needed):

```bash
docker compose run --rm backend pytest
```

Frontend (Vitest + React Testing Library, jsdom):

```bash
docker compose run --rm frontend npm test
```

PostgreSQL remains the runtime database for Compose and production. The frontend also
exposes `npm run typecheck` and `npm run build`.

## Upload rules

A file is **rejected outright** when it is not `.xlsx` or `.csv`, is empty,
exceeds 25 MB, has only headers and no data rows, or cannot be parsed.

A file is **stored with findings** when it reads correctly but its columns do not match
the ECC Customer Master layout:

| Finding | Severity |
|---|---|
| `MISSING_REQUIRED_COLUMNS` | critical |
| `DUPLICATE_COLUMNS` | high |
| `BLANK_COLUMN_HEADER` | high |
| `UNEXPECTED_COLUMNS` | medium |

Required columns are `KUNNR`, `NAME1`, `ORT01`, `LAND1`, `KTOKD` and `BUKRS`. Header
matching ignores case and surrounding spaces.

Uploaded originals are written to disk byte for byte and never rewritten.

Every accepted source row is also persisted with separate `original_data` and
`working_data` values. Profiling reads the immutable original values from the database.

Legacy `.xls` workbooks are not supported. Re-save them as `.xlsx` before uploading.

## Profiling definitions

- Missing values are null, empty or whitespace-only values.
- Unique-value counts exclude missing values.
- Field completeness is `non-missing values / total records × 100`.
- Overall completeness uses every record-field cell in the uploaded file.
- Exact duplicate records match on every original field and value. The first occurrence
  is the representative; later identical occurrences are counted as duplicates.
- Files uploaded before durable row persistence must be re-uploaded before profiling.

## Migration readiness (methodology v1)

The readiness score is a **project-defined, transparent, deterministic** indicator
inspired by common migration data-quality dimensions. **It is not an official SAP metric
and must not be presented as one.** It is available only after a file has completed
assessment (otherwise the endpoint returns `409 ASSESSMENT_REQUIRED`).

Four components are each scored `0.00`–`100.00` and combined by weight:

| Component | Weight | Basis |
|---|---|---|
| Schema conformity | 20% | `100` minus severity penalties per affected column for stored schema findings |
| Data completeness | 25% | The deterministic profile's overall completeness percentage |
| Record readiness | 35% | `records_ready / total_records × 100` |
| Issue severity health | 20% | `100 − (weighted issue points / total_records)` |

The overall score is the weighted sum of the unrounded components, rounded to two
decimals. A **critical-blocker safety rule** overrides the number: `critical_blockers`
counts critical persisted issues plus critical schema findings (a critical schema finding
counts once regardless of column count). Any blocker forces the `blocked` band and
`migration_ready = false`, so a high number can never hide a migration-blocking finding.
Otherwise the band is `ready` (≥90), `minor_remediation` (≥75), `at_risk` (≥50) or
`not_ready`. `migration_ready` is `true` only when the score is at least 90 **and** there
are zero critical blockers.

Readiness is read-only: it never runs assessment, never mutates data and adds no database
table or migration.

## Project status

A project is created as `draft` and moves to `uploaded` once a readable ECC file is
stored, including one that carries schema findings. A rejected file leaves the project
in `draft`. Running assessment moves the project to `assessed`. The remaining values
(`under_review`, `export_ready`, `completed`, `failed`) are reserved for later days and
are not set yet.
