# Functional Requirements

## Project Management

- FR-001: Users shall be able to create migration projects.
- FR-002: Each project shall have a unique project ID.
- FR-003: Users shall be able to view and resume previous projects.

## File Upload

- FR-004: Users shall upload Excel, CSV and PDF files.
- FR-005: The system shall reject empty, corrupted or unsupported files.
- FR-006: The system shall display file name, size, row count and column count.
- FR-007: Original uploaded files shall remain unchanged.

## Schema Validation

- FR-008: The system shall detect missing required columns.
- FR-009: The system shall identify unexpected or duplicate columns.
- FR-010: Source fields shall be compared with the target template.

## Data Profiling

- FR-011: The system shall calculate total records and fields.
- FR-012: The system shall calculate missing and unique values.
- FR-013: The system shall identify exact duplicate records.
- FR-014: The system shall calculate field-level completeness.

## Validation Engine

- FR-015: The system shall validate mandatory fields.
- FR-016: The system shall validate GSTIN, email and country-code formats.
- FR-017: Each failed validation shall generate an issue.
- FR-018: Every issue shall include severity, reason and affected record.

## AI Features

- FR-019: AI shall identify possible semantic duplicates.
- FR-020: Duplicate suggestions shall contain confidence scores.
- FR-021: AI shall suggest mappings for unmapped ECC fields.
- FR-022: AI shall explain issues in natural language.
- FR-023: AI suggestions shall not be applied automatically.

## Review Workflow

- FR-024: Users shall approve, edit, reject or defer suggestions.
- FR-025: Users shall add comments to review decisions.
- FR-026: Every decision shall be recorded.
- FR-027: Low-risk issues may support bulk approval.

## Transformation and Export

- FR-028: Only approved transformations shall be applied.
- FR-029: Users shall view before-and-after values.
- FR-030: The system shall generate an S/4HANA-ready file.
- FR-031: The system shall generate issue and transformation logs.
- FR-032: Users shall download generated reports and files.

## Dashboard

- FR-033: The dashboard shall show migration readiness.
- FR-034: It shall show total, ready and invalid records.
- FR-035: It shall show issues by severity, category and status.
- FR-036: Dashboard data shall support filtering.

## Consultant Assistant

- FR-037: Users shall ask questions about uploaded documents.
- FR-038: RAG answers shall include source references.
- FR-039: Users shall ask quantitative questions about migration data.
- FR-040: Generated database queries shall be read-only.
- FR-041: Destructive SQL commands shall be blocked.