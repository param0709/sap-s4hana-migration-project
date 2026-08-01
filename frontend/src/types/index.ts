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
