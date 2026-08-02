import type {
  FileProfile,
  MigrationIssue,
  Project,
  Readiness,
  UploadedFile,
} from "../types";

export function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: "p1",
    project_code: "MIG-2026-0001",
    project_name: "Customer Master Migration",
    client_name: "Nova Retail Pvt Ltd",
    source_system: "SAP ECC",
    target_system: "SAP S/4HANA",
    migration_object: "Customer Master",
    country: "IN",
    status: "uploaded",
    description: null,
    created_at: "2026-08-01T07:22:59Z",
    updated_at: "2026-08-01T07:26:29Z",
    ...overrides,
  };
}

export function makeFile(overrides: Partial<UploadedFile> = {}): UploadedFile {
  return {
    id: "f1",
    project_id: "p1",
    file_name: "valid_ecc_customers.csv",
    file_category: "source_data",
    file_extension: ".csv",
    file_size_bytes: 273,
    row_count: 3,
    column_count: 8,
    detected_columns: [
      "KUNNR",
      "NAME1",
      "ORT01",
      "LAND1",
      "KTOKD",
      "BUKRS",
      "STCD3",
      "SMTP_ADDR",
    ],
    schema_errors: null,
    processing_status: "accepted",
    uploaded_at: "2026-08-01T07:24:00Z",
    ...overrides,
  };
}

export function makeProfile(overrides: Partial<FileProfile> = {}): FileProfile {
  return {
    project_id: "p1",
    uploaded_file_id: "f1",
    file_name: "valid_ecc_customers.csv",
    total_records: 3,
    total_fields: 8,
    total_missing_values: 1,
    overall_completeness_percentage: 95.83,
    exact_duplicate_records: 0,
    exact_duplicate_groups: 0,
    fields: [
      {
        field_name: "KUNNR",
        total_records: 3,
        missing_values: 0,
        non_missing_values: 3,
        unique_values: 3,
        completeness_percentage: 100,
      },
      {
        field_name: "STCD3",
        total_records: 3,
        missing_values: 1,
        non_missing_values: 2,
        unique_values: 2,
        completeness_percentage: 66.67,
      },
    ],
    duplicate_groups: [],
    ...overrides,
  };
}

export function makeReadyReadiness(overrides: Partial<Readiness> = {}): Readiness {
  return {
    project_id: "p1",
    uploaded_file_id: "f1",
    methodology_version: "v1",
    score: 98.96,
    band: "ready",
    migration_ready: true,
    critical_blockers: 0,
    total_records: 3,
    records_ready: 3,
    records_needing_review: 0,
    total_issues: 0,
    components: {
      schema_conformity: { score: 100, weight: 0.2, weighted_score: 20 },
      data_completeness: { score: 95.83, weight: 0.25, weighted_score: 23.96 },
      record_readiness: { score: 100, weight: 0.35, weighted_score: 35 },
      issue_severity: { score: 100, weight: 0.2, weighted_score: 20 },
    },
    ...overrides,
  };
}

export function makeBlockedReadiness(overrides: Partial<Readiness> = {}): Readiness {
  return {
    project_id: "p1",
    uploaded_file_id: "f1",
    methodology_version: "v1",
    score: 54.0,
    band: "blocked",
    migration_ready: false,
    critical_blockers: 2,
    total_records: 1,
    records_ready: 0,
    records_needing_review: 1,
    total_issues: 1,
    components: {
      schema_conformity: { score: 55, weight: 0.2, weighted_score: 11 },
      data_completeness: { score: 100, weight: 0.25, weighted_score: 25 },
      record_readiness: { score: 0, weight: 0.35, weighted_score: 0 },
      issue_severity: { score: 90, weight: 0.2, weighted_score: 18 },
    },
    ...overrides,
  };
}

export function makeIssue(overrides: Partial<MigrationIssue> = {}): MigrationIssue {
  return {
    id: "i1",
    project_id: "p1",
    uploaded_file_id: "f1",
    migration_record_id: "r1",
    source_row_number: 2,
    issue_type: "business_rule",
    rule_id: "BR-006",
    rule_name: "Email format",
    field_name: "SMTP_ADDR",
    severity: "medium",
    current_value: "bad-email",
    reason: "Email address has an invalid format.",
    suggested_action: "Enter a valid email address or leave the optional field blank.",
    issue_status: "open",
    created_at: "2026-08-02T20:14:00Z",
    ...overrides,
  };
}
