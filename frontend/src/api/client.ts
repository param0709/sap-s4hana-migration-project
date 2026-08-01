import type {
  EccSchemaReference,
  Project,
  ProjectCreate,
  ProjectList,
  UploadedFile,
} from "../types";

const BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

/** An error carrying the backend's structured rejection detail, when present. */
export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

interface RejectionDetail {
  code?: string;
  message?: string;
}

function readDetail(payload: unknown): RejectionDetail | null {
  if (typeof payload !== "object" || payload === null) return null;
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string") return { message: detail };
  if (typeof detail === "object" && detail !== null) return detail as RejectionDetail;
  return null;
}

async function toApiError(response: Response): Promise<ApiError> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // Response had no JSON body.
  }
  const detail = readDetail(body);
  return new ApiError(
    detail?.message ?? `Request failed with status ${response.status}.`,
    response.status,
    detail?.code,
  );
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, init);
  } catch {
    throw new ApiError(
      "Cannot reach the API. Check that the backend is running.",
      0,
      "NETWORK_ERROR",
    );
  }
  if (!response.ok) throw await toApiError(response);
  return (await response.json()) as T;
}

export const api = {
  listProjects: () => request<ProjectList>("/projects"),

  createProject: (payload: ProjectCreate) =>
    request<Project>("/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  getProject: (projectId: string) => request<Project>(`/projects/${projectId}`),

  listFiles: (projectId: string) =>
    request<UploadedFile[]>(`/projects/${projectId}/files`),

  uploadEccFile: (projectId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<UploadedFile>(`/projects/${projectId}/files/ecc`, {
      method: "POST",
      body: form,
    });
  },

  getEccSchema: () => request<EccSchemaReference>("/reference/ecc-schema"),
};
