import type { IssueSeverity, ProcessingStatus, ProjectStatus } from "../types";

const PROJECT_LABELS: Record<ProjectStatus, string> = {
  draft: "Draft",
  uploaded: "Uploaded",
  assessed: "Assessed",
  under_review: "Under review",
  export_ready: "Ready to export",
  completed: "Completed",
  failed: "Failed",
};

export function ProjectStatusPill({ status }: { status: ProjectStatus }) {
  return (
    <span className={`pill pill--status-${status}`}>{PROJECT_LABELS[status] ?? status}</span>
  );
}

export function SeverityPill({ severity }: { severity: IssueSeverity }) {
  return <span className={`pill pill--${severity}`}>{severity}</span>;
}

export function FileStatusPill({ status }: { status: ProcessingStatus }) {
  if (status === "accepted") {
    return <span className="pill pill--ok">Schema matched</span>;
  }
  if (status === "schema_errors") {
    return <span className="pill pill--high">Schema issues</span>;
  }
  return <span className="pill pill--critical">Rejected</span>;
}
