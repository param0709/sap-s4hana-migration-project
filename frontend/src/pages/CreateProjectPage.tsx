import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { Banner } from "../components/Banner";
import type { ProjectCreate } from "../types";

const INITIAL: ProjectCreate = {
  project_name: "",
  client_name: "",
  source_system: "SAP ECC",
  target_system: "SAP S/4HANA",
  migration_object: "Customer Master",
  country: "IN",
  description: "",
};

type FieldErrors = Partial<Record<keyof ProjectCreate, string>>;

function validate(form: ProjectCreate): FieldErrors {
  const errors: FieldErrors = {};
  if (form.project_name.trim().length < 2) {
    errors.project_name = "Give the project a name of at least 2 characters.";
  }
  if (form.client_name.trim().length < 2) {
    errors.client_name = "Enter the client this migration belongs to.";
  }
  if (!/^[A-Za-z]{2}$/.test(form.country.trim())) {
    errors.country = "Use a two-letter ISO country code, for example IN.";
  }
  return errors;
}

export function CreateProjectPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState<ProjectCreate>(INITIAL);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const update = (key: keyof ProjectCreate) => (value: string) => {
    setForm((current) => ({ ...current, [key]: value }));
    setFieldErrors((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
  };

  const submit = async () => {
    const errors = validate(form);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setSaving(true);
    setSubmitError(null);
    try {
      const project = await api.createProject({
        ...form,
        country: form.country.trim().toUpperCase(),
        description: form.description?.trim() || undefined,
      });
      navigate(`/projects/${project.id}/upload`);
    } catch (caught) {
      setSubmitError(
        caught instanceof ApiError ? caught.message : "The project could not be created.",
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <p className="eyebrow">New engagement</p>
      <h1 className="page__title">Create a migration project</h1>
      <p className="page__lede">
        The project starts in Draft. You can upload the ECC customer extract as soon as it
        is created.
      </p>

      {submitError ? (
        <Banner tone="error" title="Project not created" body={submitError} />
      ) : null}

      <div className="panel">
        <div className="panel__body">
          <div className="field-grid">
            <div>
              <label className="field__label" htmlFor="project_name">
                Project name
              </label>
              <input
                id="project_name"
                className={`field__input${fieldErrors.project_name ? " field__input--invalid" : ""}`}
                value={form.project_name}
                placeholder="Customer Master Wave 1"
                onChange={(event) => update("project_name")(event.target.value)}
              />
              {fieldErrors.project_name ? (
                <p className="field__error">{fieldErrors.project_name}</p>
              ) : null}
            </div>

            <div>
              <label className="field__label" htmlFor="client_name">
                Client
              </label>
              <input
                id="client_name"
                className={`field__input${fieldErrors.client_name ? " field__input--invalid" : ""}`}
                value={form.client_name}
                placeholder="Northwind India"
                onChange={(event) => update("client_name")(event.target.value)}
              />
              {fieldErrors.client_name ? (
                <p className="field__error">{fieldErrors.client_name}</p>
              ) : null}
            </div>

            <div>
              <label className="field__label" htmlFor="source_system">
                Source system
              </label>
              <input
                id="source_system"
                className="field__input"
                value={form.source_system}
                onChange={(event) => update("source_system")(event.target.value)}
              />
            </div>

            <div>
              <label className="field__label" htmlFor="target_system">
                Target system
              </label>
              <input
                id="target_system"
                className="field__input"
                value={form.target_system}
                onChange={(event) => update("target_system")(event.target.value)}
              />
            </div>

            <div>
              <label className="field__label" htmlFor="migration_object">
                Migration object
                <span className="field__hint">Version 1 covers Customer Master</span>
              </label>
              <input
                id="migration_object"
                className="field__input"
                value={form.migration_object}
                readOnly
              />
            </div>

            <div>
              <label className="field__label" htmlFor="country">
                Country
                <span className="field__hint">ISO two-letter code</span>
              </label>
              <input
                id="country"
                className={`field__input${fieldErrors.country ? " field__input--invalid" : ""}`}
                value={form.country}
                maxLength={2}
                onChange={(event) => update("country")(event.target.value.toUpperCase())}
              />
              {fieldErrors.country ? <p className="field__error">{fieldErrors.country}</p> : null}
            </div>

            <div className="field--wide">
              <label className="field__label" htmlFor="description">
                Notes
                <span className="field__hint">Optional</span>
              </label>
              <textarea
                id="description"
                className="field__textarea"
                value={form.description ?? ""}
                placeholder="Scope, wave, cutover date, anything the team should know."
                onChange={(event) => update("description")(event.target.value)}
              />
            </div>
          </div>

          <div className="button-row">
            <button
              type="button"
              className="button button--primary"
              onClick={() => void submit()}
              disabled={saving}
            >
              {saving ? "Creating\u2026" : "Create project"}
            </button>
            <button
              type="button"
              className="button button--quiet"
              onClick={() => navigate("/")}
              disabled={saving}
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
