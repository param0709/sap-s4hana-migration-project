import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { Banner } from "../components/Banner";
import { ProjectStatusPill } from "../components/StatusPill";
import type { Project } from "../types";

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function ProjectListPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.listProjects();
      setProjects(result.items);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not load projects.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <div className="page__head">
        <div>
          <p className="eyebrow">SAP ECC &rarr; S/4HANA</p>
          <h1 className="page__title">Migration projects</h1>
          <p className="page__lede">
            Each project holds one client's files, findings and decisions. Open a project to
            continue where you left off.
          </p>
        </div>
        <button
          type="button"
          className="button button--primary"
          style={{ marginLeft: "auto" }}
          onClick={() => navigate("/projects/new")}
        >
          Create project
        </button>
      </div>

      {error ? <Banner tone="error" title="Projects did not load" body={error} /> : null}

      <div className="panel">
        <div className="panel__body">
          {loading ? (
            <div className="placeholder">
              <p>Loading projects&hellip;</p>
            </div>
          ) : projects.length === 0 ? (
            <div className="placeholder">
              <p className="placeholder__title">No projects yet</p>
              <p>Create a project to upload an ECC customer extract and check it.</p>
              <Link className="button button--primary" to="/projects/new">
                Create project
              </Link>
            </div>
          ) : (
            <table className="table table--flush">
              <thead>
                <tr>
                  <th>Project</th>
                  <th>Client</th>
                  <th>Object</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {projects.map((project) => (
                  <tr key={project.id}>
                    <td>
                      <div className="cell-strong">{project.project_name}</div>
                      <div className="code cell-sub">{project.project_code}</div>
                    </td>
                    <td>{project.client_name}</td>
                    <td>
                      <div>{project.migration_object}</div>
                      <div className="cell-sub">
                        {project.source_system} &rarr; {project.target_system}
                      </div>
                    </td>
                    <td>
                      <ProjectStatusPill status={project.status} />
                    </td>
                    <td className="cell-sub">{formatDate(project.created_at)}</td>
                    <td style={{ textAlign: "right" }}>
                      {project.status === "draft" ? (
                        <Link to={`/projects/${project.id}/upload`}>Upload data</Link>
                      ) : (
                        <Link to={`/projects/${project.id}/assessment`}>Open assessment</Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
}
