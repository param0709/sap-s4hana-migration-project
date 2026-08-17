# User Stories

## US-001 — Create Project

As a migration consultant, I want to create a project so that client files and results remain organized.

### Acceptance Criteria

- Client and project details can be entered.
- A unique project ID is generated.
- The initial project status is Draft.

## US-002 — Upload ECC Data

As a consultant, I want to upload ECC customer data so that it can be assessed.

### Acceptance Criteria

- Excel and CSV files are accepted.
- Invalid files are rejected.
- Row and column counts are displayed.
- Required columns are checked.

## US-003 — Run Assessment

As a consultant, I want to run a migration assessment so that data-quality issues are identified.

### Acceptance Criteria

- Data profiling is completed.
- Validation rules are applied.
- Issues include severity, reason and affected record.

## US-004 — Detect Duplicates

As a consultant, I want AI to identify possible duplicate customers.

### Acceptance Criteria

- Duplicate groups include confidence scores.
- Matching attributes are displayed.
- Records are never merged automatically.

## US-005 — Review Issues

As a consultant, I want to approve, edit, reject or defer suggested corrections.

### Acceptance Criteria

- Original and suggested values are visible.
- Every decision records the user and timestamp.
- Rejected changes are not applied.

## US-006 — Review Field Mappings

As a consultant, I want AI-assisted ECC-to-S/4HANA mappings.

### Acceptance Criteria

- Suggestions include confidence and explanation.
- Users can approve, edit or reject mappings.
- Low-confidence mappings are marked for review.

## US-007 — Generate Output

As a consultant, I want to generate migration-ready files.

### Acceptance Criteria

- Only approved changes are included.
- Output follows the target template.
- Rejected records are exported separately.
- A transformation log is generated.

## US-008 — View Dashboard

As a project manager, I want a dashboard showing migration readiness.

### Acceptance Criteria

- Total, ready and invalid records are shown.
- Issues are grouped by severity and category.
- Metrics update after review decisions.

## US-009 — Ask Consultant Assistant

As a consultant, I want to ask questions about the migration.

### Acceptance Criteria

- Documentation questions use RAG.
- Data questions use read-only SQL.
- Sources and query evidence are displayed.
- Unsupported questions return a clear limitation.

## US-010 — Review CVI Readiness

As a migration consultant, I want to review CVI and Business Partner prerequisites so
that I can resolve conversion blockers before preparing a target load.

### Acceptance Criteria

- The result shows the BP category and required customer role.
- ECC account groups show their configured BP grouping or an unmapped blocker.
- Identity, address, company-code, uniqueness and source-assessment checks are explicit.
- Every failed check includes the original spreadsheet/CSV rows.
- The screen clearly states that the result is not an official SAP validation.
