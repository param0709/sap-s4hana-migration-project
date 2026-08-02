# SAP S/4HANA Migration Co-Pilot

Day 2 of the 20-day plan: create a migration project, upload an ECC Customer Master
extract, preserve every source row, validate its columns and calculate deterministic
data-quality profile metrics.

AI, RAG, authentication, dashboards, business rules, transformations and exports remain
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
| Expected ECC layout | `GET /api/v1/reference/ecc-schema` |

Interactive API docs run at `http://localhost:8000/docs`.

## Running it

```bash
cp .env.example .env
docker compose up --build
```

Then open `http://localhost:5173`.

Migrations run automatically when the backend container starts.

## Running the tests

```bash
docker compose run --rm backend pytest
```

Tests use an in-memory SQLite database, so they need no running PostgreSQL instance.
PostgreSQL remains the runtime database for Compose and production.

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

## Project status

A project is created as `draft` and moves to `uploaded` once a readable ECC file is
stored, including one that carries schema findings. A rejected file leaves the project
in `draft`. The remaining values (`assessed`, `under_review`, `export_ready`,
`completed`, `failed`) are reserved for later days and are not set yet.
