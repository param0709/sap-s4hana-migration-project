import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { UploadPage } from "./UploadPage";
import { api } from "../api/client";
import { makeFile, makeProject } from "../test/fixtures";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    api: {
      getProject: vi.fn(),
      getEccSchema: vi.fn(),
      listFiles: vi.fn(),
      uploadEccFile: vi.fn(),
    },
  };
});

function renderUpload() {
  return render(
    <MemoryRouter initialEntries={["/projects/p1/upload"]}>
      <Routes>
        <Route path="/projects/:projectId/upload" element={<UploadPage />} />
        <Route path="/projects/:projectId/assessment" element={<div>Assessment route</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("UploadPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getProject).mockResolvedValue(makeProject());
    vi.mocked(api.getEccSchema).mockResolvedValue({
      allowed_extensions: [".csv", ".xlsx"],
      required_columns: [{ name: "KUNNR", description: "ECC customer number" }],
      optional_columns: [{ name: "STCD3", description: "GSTIN or tax number" }],
    });
  });

  // 12. Continue to assessment appears once a file has been uploaded/stored.
  it("exposes Continue to assessment when the project already has a file", async () => {
    vi.mocked(api.listFiles).mockResolvedValue([makeFile()]);

    renderUpload();

    const link = await screen.findByRole("link", { name: /continue to assessment/i });
    expect(link).toHaveAttribute("href", "/projects/p1/assessment");
  });

  it("does not show Continue to assessment before any file exists", async () => {
    vi.mocked(api.listFiles).mockResolvedValue([]);

    renderUpload();

    // The schema layout renders once context loads; the continue link must not.
    expect(await screen.findByText(/Expected ECC Customer Master layout/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /continue to assessment/i }),
    ).not.toBeInTheDocument();
  });
});
