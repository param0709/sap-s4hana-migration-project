export type ProjectStatus =
  | "draft"
  | "uploaded"
  | "assessed"
  | "under_review"
  | "export_ready"
  | "completed"
  | "failed";

export type IssueSeverity = "critical" | "high" | "medium" | "low";

export type ProcessingStatus = "accepted" | "schema_errors" | "rejected";

export interface Project {
  id: string;
  project_code: string;
  project_name: string;
  client_name: string;
  source_system: string;
  target_system: string;
  migration_object: string;
  country: string;
  status: ProjectStatus;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectList {
  total: number;
  items: Project[];
}

export interface ProjectCreate {
  project_name: string;
  client_name: string;
  source_system: string;
  target_system: string;
  migration_object: string;
  country: string;
  description?: string;
}

export interface SchemaError {
  code: string;
  severity: IssueSeverity;
  message: string;
  columns: string[];
}

export interface UploadedFile {
  id: string;
  project_id: string;
  file_name: string;
  file_category: string;
  file_extension: string;
  file_size_bytes: number;
  row_count: number | null;
  column_count: number | null;
  detected_columns: string[] | null;
  schema_errors: SchemaError[] | null;
  processing_status: ProcessingStatus;
  uploaded_at: string;
}

export interface SchemaColumn {
  name: string;
  description: string;
}

export interface EccSchemaReference {
  allowed_extensions: string[];
  required_columns: SchemaColumn[];
  optional_columns: SchemaColumn[];
}

// ---------- Profiling (FR-011–FR-014) ----------

export interface FieldProfile {
  field_name: string;
  total_records: number;
  missing_values: number;
  non_missing_values: number;
  unique_values: number;
  completeness_percentage: number;
}

export interface DuplicateGroup {
  representative_row_number: number;
  duplicate_row_numbers: number[];
  record_count: number;
  duplicate_count: number;
}

export interface FileProfile {
  project_id: string;
  uploaded_file_id: string;
  file_name: string;
  total_records: number;
  total_fields: number;
  total_missing_values: number;
  overall_completeness_percentage: number;
  exact_duplicate_records: number;
  exact_duplicate_groups: number;
  fields: FieldProfile[];
  duplicate_groups: DuplicateGroup[];
}

// ---------- Assessment (FR-015–FR-018) ----------

export type IssueType = "business_rule";
export type IssueStatus = "open";

/** JSON scalar as returned for a persisted issue's current value. */
export type IssueValue = string | number | boolean | null;

export interface SeverityCounts {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface AssessmentSummary {
  project_id: string;
  uploaded_file_id: string;
  total_records: number;
  records_ready: number;
  records_needing_review: number;
  total_issues: number;
  issues_by_severity: SeverityCounts;
  issues_by_rule: Record<string, number>;
}

export interface MigrationIssue {
  id: string;
  project_id: string;
  uploaded_file_id: string;
  migration_record_id: string;
  source_row_number: number;
  issue_type: IssueType;
  rule_id: string;
  rule_name: string;
  field_name: string;
  severity: IssueSeverity;
  current_value: IssueValue;
  reason: string;
  suggested_action: string;
  issue_status: IssueStatus;
  created_at: string;
}

export interface FileIssues {
  project_id: string;
  uploaded_file_id: string;
  total_issues: number;
  items: MigrationIssue[];
}

// ---------- Readiness (project-defined methodology v1) ----------

export type ReadinessBand =
  | "blocked"
  | "ready"
  | "minor_remediation"
  | "at_risk"
  | "not_ready";

export interface ReadinessComponent {
  score: number;
  weight: number;
  weighted_score: number;
}

export interface ReadinessComponents {
  schema_conformity: ReadinessComponent;
  data_completeness: ReadinessComponent;
  record_readiness: ReadinessComponent;
  issue_severity: ReadinessComponent;
}

export interface Readiness {
  project_id: string;
  uploaded_file_id: string;
  methodology_version: "v1";
  score: number;
  band: ReadinessBand;
  migration_ready: boolean;
  critical_blockers: number;
  total_records: number;
  records_ready: number;
  records_needing_review: number;
  total_issues: number;
  components: ReadinessComponents;
}

// ---------- Day 5 CVI / Business Partner readiness ----------

export interface CviCheck {
  check_id: string;
  name: string;
  status: "passed" | "failed";
  severity: IssueSeverity;
  affected_records: number;
  affected_source_rows: number[];
  explanation: string;
  suggested_action: string;
}

export interface AccountGroupMapping {
  ecc_account_group: string;
  bp_grouping: string;
  record_count: number;
}

export interface UnmappedAccountGroup {
  ecc_account_group: string;
  record_count: number;
  source_rows: number[];
}

export interface CviReadiness {
  project_id: string;
  uploaded_file_id: string;
  methodology_version: "v1";
  target_object: string;
  disclaimer: string;
  status: "ready" | "blocked";
  cvi_ready: boolean;
  total_records: number;
  records_ready: number;
  records_blocked: number;
  failed_checks: number;
  critical_blockers: number;
  bp_category: { code: string; label: string };
  required_bp_roles: string[];
  mapped_account_groups: AccountGroupMapping[];
  unmapped_account_groups: UnmappedAccountGroup[];
  checks: CviCheck[];
}
