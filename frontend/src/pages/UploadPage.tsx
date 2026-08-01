import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { Banner } from "../components/Banner";
import { SchemaLedger } from "../components/SchemaLedger";
import { FileStatusPill, SeverityPill } from "../components/StatusPill";
import type { EccSchemaReference, Project, UploadedFile } from "../types";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function UploadPage() {
  const { projectId = "" } = useParams<{ projectId: string }>();
  const inputRef = useRef<HTMLInputElement>(null);

  const [project, setProject] = useState<Project | null>(null);
  const [reference, setReference] = useState<EccSchemaReference | null>(null);
  const [result, setResult] = useState<UploadedFile | null>(null);
  const [selected, setSelected] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [rejection, setRejection] = useState<{ code?: string; message: string } | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadContext = useCallback(async () => {
    try {
      const [loadedProject, loadedReference, files] = await Promise.all([
        api.getProject(projectId),
        api.getEccSchema(),
        api.listFiles(projectId),
      ]);
      setProject(loadedProject);
      setReference(loadedReference);
      setResult(files[0] ?? null);
    } catch (caught) {
      setLoadError(
        caught instanceof ApiError ? caught.message : "This project could not be loaded.",
      );
    }
  }, [projectId]);

  useEffect(() => {
    void loadContext();
  }, [loadContext]);

  const upload = async (file: File) => {
    setUploading(true);
    setRejection(null);
    try {
      setResult(await api.uploadEccFile(projectId, file));
    } catch (caught) {
      setResult(null);
      setRejection(
        caught instanceof ApiError
          ? { code: caught.code, message: caught.message }
          : { message: "The file could not be uploaded." },
      );
    } finally {
      setUploading(false);
    }
  };

  const choose = (file: File | null) => {
    setSelected(file);
    setRejection(null);
    if (file) void upload(file);
  };

  if (loadError) {
    return (
      <>
        <Banner tone="error" title="Project unavailable" body={loadError} />
        <Link to="/">Back to projects</Link>
      </>
    );
  }

  const accepted = reference?.allowed_extensions.join(", ") ?? ".csv, .xlsx";
  const errors = result?.schema_errors ?? [];

  return (
    <>
      <p className="eyebrow">
        {project ? `${project.project_code} \u00B7 ${project.client_name}` : "Loading\u2026"}
      </p>
      <h1 className="page__title">Upload ECC customer data</h1>
      <p className="page__lede">
        Upload the customer master extract from ECC. The file is stored exactly as received and
        checked against the expected layout. Nothing in your file is changed.
      </p>

      {rejection ? (
        <Banner
          tone="error"
          title={
            rejection.code === "UNSUPPORTED_FILE_TYPE"
              ? "That file type cannot be read"
              : "File not accepted"
          }
          body={rejection.message}
        />
      ) : null}

      <div className="panel">
        <div className="panel__body">
          <div
            className={`dropzone${dragging ? " dropzone--active" : ""}`}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              choose(event.dataTransfer.files?.[0] ?? null);
            }}
          >
            <p className="dropzone__headline">Drop the ECC extract here</p>
            <p className="dropzone__hint">Excel or CSV, up to 25 MB. Accepted: {accepted}</p>
            <button
              type="button"
              className="button button--primary"
              onClick={() => inputRef.current?.click()}
              disabled={uploading}
            >
              {uploading ? "Checking\u2026" : "Choose file"}
            </button>
            <input
              ref={inputRef}
              type="file"
              className="visually-hidden"
              accept=".xlsx,.csv"
              onChange={(event) => choose(event.target.files?.[0] ?? null)}
            />
            {selected ? <p className="dropzone__file">{selected.name}</p> : null}
          </div>
        </div>

        {result ? (
          <>
            <div className="metrics">
              <div className="metric">
                <p className="metric__label">File</p>
                <p className="metric__value" style={{ fontSize: 14 }}>
                  {result.file_name}
                </p>
              </div>
              <div className="metric">
                <p className="metric__label">Size</p>
                <p className="metric__value">{formatBytes(result.file_size_bytes)}</p>
              </div>
              <div className="metric">
                <p className="metric__label">Rows</p>
                <p className="metric__value">{result.row_count ?? "\u2014"}</p>
              </div>
              <div className="metric">
                <p className="metric__label">Columns</p>
                <p className="metric__value">{result.column_count ?? "\u2014"}</p>
              </div>
            </div>

            <div style={{ padding: "16px 22px", borderTop: "1px solid var(--rule)" }}>
              <FileStatusPill status={result.processing_status} />
            </div>
          </>
        ) : null}
      </div>

      {result && errors.length > 0 ? (
        <div className="panel">
          <div className="panel__body" style={{ paddingBottom: 0 }}>
            <h2 className="section-title">Schema findings</h2>
            <p className="page__lede" style={{ marginBottom: 16 }}>
              Resolve these before the assessment runs. The file stays in the project either way.
            </p>
          </div>
          {errors.map((error) => (
            <div className="finding" key={error.code}>
              <div className="finding__head">
                <SeverityPill severity={error.severity} />
                <span className="finding__code">{error.code}</span>
              </div>
              <p className="finding__message">{error.message}</p>
              {error.columns.length > 0 ? (
                <div className="chip-list">
                  {error.columns.map((column) => (
                    <span key={column} className="code-chip">
                      {column}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      {result && errors.length === 0 ? (
        <Banner
          tone="success"
          title="Schema matched"
          body="Every required ECC Customer Master field is present. This file is ready for the assessment step."
        />
      ) : null}

      {reference ? (
        <div className="panel">
          <div className="panel__body" style={{ paddingBottom: 12 }}>
            <h2 className="section-title">Expected ECC Customer Master layout</h2>
            <p className="page__lede" style={{ marginBottom: 0 }}>
              {result
                ? "Checked field by field against your upload."
                : "These are the fields the upload is checked against."}
            </p>
          </div>
          <SchemaLedger
            reference={reference}
            detectedColumns={result?.detected_columns ?? []}
          />
        </div>
      ) : null}

      <div className="button-row" style={{ marginTop: 22 }}>
        <Link className="button button--quiet" to="/">
          Back to projects
        </Link>
      </div>
    </>
  );
}
