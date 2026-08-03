import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { Banner } from "../components/Banner";
import { SeverityPill } from "../components/StatusPill";
import type {
  FileProfile,
  IssueSeverity,
  IssueValue,
  MigrationIssue,
  Project,
  Readiness,
  ReadinessBand,
  ReadinessComponents,
  UploadedFile,
} from "../types";

const BAND_LABELS: Record<ReadinessBand, string> = {
  ready: "Ready",
  minor_remediation: "Minor remediation",
  at_risk: "At risk",
  not_ready: "Not ready",
  blocked: "Blocked",
};

const COMPONENT_META: {
  key: keyof ReadinessComponents;
  label: string;
  note: string;
}[] = [
  {
    key: "schema_conformity",
    label: "Schema conformity",
    note: "Penalised for stored schema findings.",
  },
  {
    key: "data_completeness",
    label: "Data completeness",
    note: "Overall completeness from profiling.",
  },
  {
    key: "record_readiness",
    label: "Record readiness",
    note: "Share of records marked ready.",
  },
  {
    key: "issue_severity",
    label: "Issue severity health",
    note: "Weighted penalty for open issues.",
  },
];

const SEVERITY_FILTERS: (IssueSeverity | "all")[] = [
  "all",
  "critical",
  "high",
  "medium",
  "low",
];

/**
 * Backend rejection codes that mean the persisted record set behind this file is
 * missing or inconsistent. An issue collection read while any of these hold is
 * not evidence that every record passed — it is evidence of nothing at all.
 */
const DATA_UNAVAILABLE_CODES = new Set([
  "PROFILE_DATA_UNAVAILABLE",
  "ASSESSMENT_DATA_UNAVAILABLE",
  "READINESS_DATA_UNAVAILABLE",
]);

const ISSUES_UNAVAILABLE_BODY =
  "This file does not have a complete persisted record set for issue assessment. " +
  "Re-upload the file to rebuild the assessment source.";

const ISSUES_FAILED_BODY =
  "The issue assessment could not be loaded. Try again or re-upload the source file.";

/**
 * What the Issues panel is allowed to claim. The distinction matters: only
 * `loaded` with an empty collection may be reported as a clean pass.
 */
type IssuesState =
  | { status: "loading" }
  | { status: "not_assessed" }
  | { status: "unavailable" }
  | { status: "failed"; message: string }
  | { status: "loaded"; items: MigrationIssue[] };

/** Stable identity so the severity filter memo does not rerun needlessly. */
const NO_ISSUES: MigrationIssue[] = [];

function isDataUnavailable(caught: unknown): boolean {
  return (
    caught instanceof ApiError &&
    caught.code !== undefined &&
    DATA_UNAVAILABLE_CODES.has(caught.code)
  );
}

function errorMessage(caught: unknown, fallback: string): string {
  return caught instanceof ApiError && caught.message.trim() !== ""
    ? caught.message
    : fallback;
}

/** A missing current value must read as "Missing", never as null or blank. */
function displayValue(value: IssueValue): string {
  if (value === null) return "Missing";
  if (typeof value === "string" && value.trim() === "") return "Missing";
  return String(value);
}

function newestFirst(files: UploadedFile[]): UploadedFile[] {
  return [...files].sort(
    (a, b) => new Date(b.uploaded_at).getTime() - new Date(a.uploaded_at).getTime(),
  );
}

export function AssessmentPage() {
  const { projectId = "" } = useParams<{ projectId: string }>();

  const [project, setProject] = useState<Project | null>(null);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);

  const [profile, setProfile] = useState<FileProfile | null>(null);
  const [issuesState, setIssuesState] = useState<IssuesState>({ status: "loading" });
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [assessmentRequired, setAssessmentRequired] = useState(false);

  const [contextError, setContextError] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [readinessError, setReadinessError] = useState<string | null>(null);
  const [assessmentError, setAssessmentError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const [loadingContext, setLoadingContext] = useState(true);
  const [loadingFile, setLoadingFile] = useState(false);
  const [running, setRunning] = useState(false);

  const [severityFilter, setSeverityFilter] = useState<IssueSeverity | "all">("all");

  // Only the newest file request may write state, so a slow response for a
  // previously selected file can never land under the file now on screen.
  const requestToken = useRef(0);

  const loadFileData = useCallback(
    async (fileId: string) => {
      const token = (requestToken.current += 1);
      const isCurrent = () => requestToken.current === token;

      setLoadingFile(true);
      setProfile(null);
      setReadiness(null);
      setProfileError(null);
      setReadinessError(null);
      setAssessmentError(null);
      setFeedback(null);
      setAssessmentRequired(false);
      setIssuesState({ status: "loading" });
      setSeverityFilter("all");

      // The issues endpoint answers from persisted rows without checking that
      // the record set is complete, so an unavailable profile or readiness
      // source invalidates whatever that collection happens to contain.
      let dataUnavailable = false;
      let notAssessed = false;
      let issueOutcome: IssuesState | null = null;

      try {
        const loaded = await api.getProfile(projectId, fileId);
        if (!isCurrent()) return;
        setProfile(loaded);
      } catch (caught) {
        if (!isCurrent()) return;
        setProfile(null);
        if (isDataUnavailable(caught)) dataUnavailable = true;
        setProfileError(errorMessage(caught, "The profile could not be loaded."));
      }

      try {
        const result = await api.getIssues(projectId, fileId);
        if (!isCurrent()) return;
        issueOutcome = { status: "loaded", items: result.items };
      } catch (caught) {
        if (!isCurrent()) return;
        if (isDataUnavailable(caught)) {
          dataUnavailable = true;
        } else {
          issueOutcome = {
            status: "failed",
            message: errorMessage(caught, ISSUES_FAILED_BODY),
          };
        }
      }

      try {
        const loaded = await api.getReadiness(projectId, fileId);
        if (!isCurrent()) return;
        setReadiness(loaded);
      } catch (caught) {
        if (!isCurrent()) return;
        setReadiness(null);
        if (caught instanceof ApiError && caught.code === "ASSESSMENT_REQUIRED") {
          setAssessmentRequired(true);
          notAssessed = true;
        } else {
          if (isDataUnavailable(caught)) dataUnavailable = true;
          setReadinessError(
            errorMessage(caught, "The readiness score could not be loaded."),
          );
        }
      }

      if (!isCurrent()) return;
      if (dataUnavailable) {
        setIssuesState({ status: "unavailable" });
      } else if (issueOutcome?.status === "failed") {
        setIssuesState(issueOutcome);
      } else if (notAssessed) {
        setIssuesState({ status: "not_assessed" });
      } else {
        setIssuesState(issueOutcome ?? { status: "unavailable" });
      }
      setLoadingFile(false);
    },
    [projectId],
  );

  const loadContext = useCallback(async () => {
    setLoadingContext(true);
    setContextError(null);
    try {
      const [loadedProject, loadedFiles] = await Promise.all([
        api.getProject(projectId),
        api.listFiles(projectId),
      ]);
      setProject(loadedProject);
      const ordered = newestFirst(loadedFiles);
      setFiles(ordered);
      const firstId = ordered[0]?.id ?? null;
      setSelectedFileId(firstId);
      if (firstId) await loadFileData(firstId);
    } catch (caught) {
      setContextError(
        caught instanceof ApiError ? caught.message : "This project could not be loaded.",
      );
    } finally {
      setLoadingContext(false);
    }
  }, [projectId, loadFileData]);

  useEffect(() => {
    void loadContext();
  }, [loadContext]);

  const onSelectFile = (fileId: string) => {
    setSelectedFileId(fileId);
    void loadFileData(fileId);
  };

  const runAssessment = async () => {
    if (!selectedFileId) return;
    setRunning(true);
    setAssessmentError(null);
    setFeedback(null);
    try {
      await api.runAssessment(projectId, selectedFileId);
      // Refresh project status, issues and readiness without a page reload.
      try {
        setProject(await api.getProject(projectId));
      } catch {
        // Non-fatal: the status pill may lag, the assessment still ran.
      }
      const [issueResult, readinessResult] = await Promise.allSettled([
        api.getIssues(projectId, selectedFileId),
        api.getReadiness(projectId, selectedFileId),
      ]);
      if (issueResult.status === "fulfilled") {
        setIssuesState({ status: "loaded", items: issueResult.value.items });
      } else if (isDataUnavailable(issueResult.reason)) {
        setIssuesState({ status: "unavailable" });
      } else {
        setIssuesState({
          status: "failed",
          message: errorMessage(issueResult.reason, ISSUES_FAILED_BODY),
        });
      }
      if (readinessResult.status === "fulfilled") {
        setReadiness(readinessResult.value);
        setAssessmentRequired(false);
        setReadinessError(null);
      }
      setFeedback("Assessment complete.");
    } catch (caught) {
      if (isDataUnavailable(caught)) setIssuesState({ status: "unavailable" });
      setAssessmentError(
        caught instanceof ApiError
          ? caught.message
          : "The assessment could not be completed. Your profiling results are unchanged.",
      );
    } finally {
      setRunning(false);
    }
  };

  const issues = issuesState.status === "loaded" ? issuesState.items : NO_ISSUES;

  const filteredIssues = useMemo(
    () =>
      severityFilter === "all"
        ? issues
        : issues.filter((issue) => issue.severity === severityFilter),
    [issues, severityFilter],
  );

  const selectedFile = files.find((file) => file.id === selectedFileId) ?? null;

  if (loadingContext) {
    return (
      <div className="placeholder">
        <p>Loading assessment workspace&hellip;</p>
      </div>
    );
  }

  if (contextError) {
    return (
      <>
        <Banner tone="error" title="Project unavailable" body={contextError} />
        <Link to="/">Back to projects</Link>
      </>
    );
  }

  return (
    <>
      <p className="eyebrow">
        {project ? `${project.project_code} · ${project.client_name}` : "…"}
      </p>
      <h1 className="page__title">Assessment &amp; readiness</h1>
      <p className="page__lede">
        Review the profiling profile, run deterministic business-rule assessment and read the
        project&apos;s Migration Readiness Score for the selected ECC extract.
      </p>

      {files.length === 0 ? (
        <div className="panel">
          <div className="placeholder">
            <p className="placeholder__title">No ECC extract uploaded yet</p>
            <p>
              This project has no source file to assess. Upload an ECC Customer Master extract to
              begin.
            </p>
            <Link className="button button--primary" to={`/projects/${projectId}/upload`}>
              Upload ECC data
            </Link>
          </div>
        </div>
      ) : (
        <>
          {files.length > 1 ? (
            <div className="panel">
              <div className="panel__body toolbar">
                <label className="field__label" htmlFor="file-select">
                  Source file
                </label>
                <select
                  id="file-select"
                  className="field__input select"
                  value={selectedFileId ?? ""}
                  onChange={(event) => onSelectFile(event.target.value)}
                >
                  {files.map((file) => (
                    <option key={file.id} value={file.id}>
                      {file.file_name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          ) : null}

          {feedback ? <Banner tone="success" title={feedback} /> : null}
          {assessmentError ? (
            <Banner
              tone="error"
              title="Assessment could not be completed"
              body={assessmentError}
            />
          ) : null}

          <ReadinessSection
            readiness={readiness}
            assessmentRequired={assessmentRequired}
            readinessError={readinessError}
            loading={loadingFile}
            running={running}
            processingStatus={selectedFile?.processing_status ?? null}
            onRunAssessment={runAssessment}
          />

          <ProfileSection profile={profile} error={profileError} loading={loadingFile} />

          <IssuesSection
            state={issuesState}
            visibleIssues={filteredIssues}
            severityFilter={severityFilter}
            onFilter={setSeverityFilter}
            projectId={projectId}
          />
        </>
      )}
    </>
  );
}

function ScoreMeter({ score, band }: { score: number; band: ReadinessBand }) {
  return (
    <div className="readiness__meter">
      <div
        className={`readiness__score readiness__score--${band}`}
        aria-hidden="true"
      >
        {score.toFixed(2)}
        <span className="readiness__score-max">/100</span>
      </div>
      <div
        className={`meter meter--${band}`}
        role="progressbar"
        aria-valuenow={score}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Migration readiness score ${score.toFixed(2)} out of 100, band ${BAND_LABELS[band]}`}
      >
        <div className="meter__fill" style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}

function ComponentBar({
  label,
  note,
  score,
  weight,
}: {
  label: string;
  note: string;
  score: number;
  weight: number;
}) {
  return (
    <div className="component">
      <div className="component__head">
        <span className="component__label">{label}</span>
        <span className="component__weight">{Math.round(weight * 100)}% weight</span>
        <span className="component__score">{score.toFixed(2)}</span>
      </div>
      <div className="component__track" aria-hidden="true">
        <div className="component__fill" style={{ width: `${score}%` }} />
      </div>
      <p className="component__note">{note}</p>
    </div>
  );
}

function ReadinessSection({
  readiness,
  assessmentRequired,
  readinessError,
  loading,
  running,
  processingStatus,
  onRunAssessment,
}: {
  readiness: Readiness | null;
  assessmentRequired: boolean;
  readinessError: string | null;
  loading: boolean;
  running: boolean;
  processingStatus: string | null;
  onRunAssessment: () => void;
}) {
  return (
    <div className="panel">
      <div className="panel__body">
        <h2 className="section-title">Migration readiness</h2>

        {loading && !readiness ? (
          <p className="cell-sub">Loading readiness&hellip;</p>
        ) : assessmentRequired ? (
          <div className="assessment-cta">
            <p className="assessment-cta__title">Assessment not run</p>
            <p className="assessment-cta__body">
              Profiling is available below. Run the deterministic business-rule assessment to
              generate the Migration Readiness Score for this file.
              {processingStatus === "schema_errors"
                ? " Schema findings do not block assessment; they must be resolved before export."
                : ""}
            </p>
            <button
              type="button"
              className="button button--primary"
              onClick={onRunAssessment}
              disabled={running}
            >
              {running ? "Assessing…" : "Run assessment"}
            </button>
          </div>
        ) : readinessError ? (
          <Banner tone="error" title="Readiness unavailable" body={readinessError} />
        ) : readiness ? (
          <>
            {readiness.band === "blocked" ? (
              <div className="blocker-callout" role="alert">
                <p className="blocker-callout__title">
                  {readiness.critical_blockers} critical blocker
                  {readiness.critical_blockers === 1 ? "" : "s"} must be resolved
                </p>
                <p className="blocker-callout__body">
                  A migration-blocking finding is present, so this file is not ready regardless of
                  the numeric score.
                </p>
              </div>
            ) : null}

            <div className="readiness__grid">
              <ScoreMeter score={readiness.score} band={readiness.band} />
              <div className="readiness__facts">
                <div className="fact">
                  <span className="fact__label">Band</span>
                  <span className={`pill pill--band-${readiness.band}`}>
                    {BAND_LABELS[readiness.band]}
                  </span>
                </div>
                <div className="fact">
                  <span className="fact__label">Migration ready</span>
                  <span className="fact__value">
                    {readiness.migration_ready ? "Yes" : "No"}
                  </span>
                </div>
                <div className="fact">
                  <span className="fact__label">Critical blockers</span>
                  <span className="fact__value">{readiness.critical_blockers}</span>
                </div>
                <div className="fact">
                  <span className="fact__label">Ready records</span>
                  <span className="fact__value">
                    {readiness.records_ready}/{readiness.total_records}
                  </span>
                </div>
                <div className="fact">
                  <span className="fact__label">Needs review</span>
                  <span className="fact__value">{readiness.records_needing_review}</span>
                </div>
                <div className="fact">
                  <span className="fact__label">Total issues</span>
                  <span className="fact__value">{readiness.total_issues}</span>
                </div>
              </div>
            </div>

            <div className="readiness__components">
              {COMPONENT_META.map((meta) => {
                const component = readiness.components[meta.key];
                return (
                  <ComponentBar
                    key={meta.key}
                    label={meta.label}
                    note={meta.note}
                    score={component.score}
                    weight={component.weight}
                  />
                );
              })}
            </div>

            <p className="methodology-note">
              Readiness methodology {readiness.methodology_version}: a weighted blend of schema
              conformity (20%), data completeness (25%), record readiness (35%) and issue-severity
              health (20%). Any critical blocker forces a <strong>blocked</strong> band. This is a
              project-defined deterministic readiness indicator, not an official SAP score.
            </p>
          </>
        ) : null}
      </div>
    </div>
  );
}

function ProfileSection({
  profile,
  error,
  loading,
}: {
  profile: FileProfile | null;
  error: string | null;
  loading: boolean;
}) {
  if (error) {
    return (
      <div className="panel">
        <div className="panel__body">
          <h2 className="section-title">Profiling</h2>
          <Banner tone="error" title="Profile unavailable" body={error} />
        </div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="panel">
        <div className="panel__body">
          <h2 className="section-title">Profiling</h2>
          <p className="cell-sub">{loading ? "Loading profile…" : "No profile available."}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel__body">
        <h2 className="section-title">Profiling</h2>
      </div>
      <div className="metrics metrics--six">
        <Metric label="Records" value={profile.total_records} />
        <Metric label="Fields" value={profile.total_fields} />
        <Metric label="Missing values" value={profile.total_missing_values} />
        <Metric
          label="Completeness"
          value={`${profile.overall_completeness_percentage.toFixed(2)}%`}
        />
        <Metric label="Duplicate records" value={profile.exact_duplicate_records} />
        <Metric label="Duplicate groups" value={profile.exact_duplicate_groups} />
      </div>

      <div className="table-scroll">
        <table className="table">
          <thead>
            <tr>
              <th>Field</th>
              <th className="numeric">Missing</th>
              <th className="numeric">Non-missing</th>
              <th className="numeric">Unique</th>
              <th className="numeric">Completeness</th>
            </tr>
          </thead>
          <tbody>
            {profile.fields.map((field) => (
              <tr key={field.field_name}>
                <td className="code">{field.field_name}</td>
                <td className="numeric">{field.missing_values}</td>
                <td className="numeric">{field.non_missing_values}</td>
                <td className="numeric">{field.unique_values}</td>
                <td className="numeric">{field.completeness_percentage.toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {profile.duplicate_groups.length > 0 ? (
        <div className="panel__body">
          <h3 className="section-title">Exact-duplicate groups</h3>
          <ul className="plain-list">
            {profile.duplicate_groups.map((group) => (
              <li key={group.representative_row_number} className="cell-sub">
                Row {group.representative_row_number} is repeated by row(s){" "}
                {group.duplicate_row_numbers.join(", ")} — {group.duplicate_count} duplicate
                {group.duplicate_count === 1 ? "" : "s"}.
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function IssuesSection({
  state,
  visibleIssues,
  severityFilter,
  onFilter,
  projectId,
}: {
  state: IssuesState;
  visibleIssues: MigrationIssue[];
  severityFilter: IssueSeverity | "all";
  onFilter: (value: IssueSeverity | "all") => void;
  projectId: string;
}) {
  const totalIssues = state.status === "loaded" ? state.items.length : 0;

  return (
    <div className="panel">
      <div className="panel__body">
        <div className="issues__head">
          <h2 className="section-title" style={{ marginBottom: 0 }}>
            Issues
          </h2>
          {totalIssues > 0 ? (
            <div className="filter-group" role="group" aria-label="Filter issues by severity">
              {SEVERITY_FILTERS.map((value) => (
                <button
                  key={value}
                  type="button"
                  className={`chip-toggle${severityFilter === value ? " chip-toggle--on" : ""}`}
                  aria-pressed={severityFilter === value}
                  onClick={() => onFilter(value)}
                >
                  {value === "all" ? "All" : value}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      {state.status === "loading" ? (
        <div className="placeholder">
          <p>Loading issues&hellip;</p>
        </div>
      ) : state.status === "unavailable" ? (
        <div className="panel__body">
          <Banner
            tone="error"
            title="Issue assessment unavailable"
            body={ISSUES_UNAVAILABLE_BODY}
          />
          <Link className="button button--primary" to={`/projects/${projectId}/upload`}>
            Re-upload source file
          </Link>
        </div>
      ) : state.status === "failed" ? (
        <div className="panel__body">
          <Banner tone="error" title="Unable to load issues" body={state.message} />
        </div>
      ) : state.status === "not_assessed" ? (
        <div className="placeholder">
          <p className="placeholder__title">Not assessed yet</p>
          <p>Run assessment to check this file against the business rules.</p>
        </div>
      ) : totalIssues === 0 ? (
        <div className="placeholder">
          <p className="placeholder__title">No issues found</p>
          <p>Every assessed record passed the deterministic business rules.</p>
        </div>
      ) : visibleIssues.length === 0 ? (
        <div className="placeholder">
          <p>No issues match this severity filter.</p>
        </div>
      ) : (
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th className="numeric">Row</th>
                <th>Rule</th>
                <th>Field</th>
                <th>Severity</th>
                <th>Current value</th>
                <th>Reason</th>
                <th>Suggested action</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {visibleIssues.map((issue) => (
                <tr key={issue.id}>
                  <td className="numeric">{issue.source_row_number}</td>
                  <td>
                    <div className="code cell-strong">{issue.rule_id}</div>
                    <div className="cell-sub">{issue.rule_name}</div>
                  </td>
                  <td className="code">{issue.field_name}</td>
                  <td>
                    <SeverityPill severity={issue.severity} />
                  </td>
                  <td className={issue.current_value === null ? "value-missing" : "code"}>
                    {displayValue(issue.current_value)}
                  </td>
                  <td>{issue.reason}</td>
                  <td className="cell-sub">{issue.suggested_action}</td>
                  <td className="cell-sub">{issue.issue_status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="metric">
      <p className="metric__label">{label}</p>
      <p className="metric__value">{value}</p>
    </div>
  );
}
