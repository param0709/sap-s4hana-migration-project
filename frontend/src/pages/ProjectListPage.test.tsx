import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProjectListPage } from "./ProjectListPage";
import { api } from "../api/client";
import { makeProject } from "../test/fixtures";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    api: { listProjects: vi.fn() },
  };
});

function renderList() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<ProjectListPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProjectListPage", () => {
  beforeEach(() => vi.clearAllMocks());

  // 11. Draft projects link to upload; uploaded/assessed link to assessment.
  it("shows different row actions for draft versus uploaded/assessed projects", async () => {
    vi.mocked(api.listProjects).mockResolvedValue({
      total: 3,
      items: [
        makeProject({
          id: "draft1",
          project_code: "MIG-2026-0001",
          project_name: "Draft Project",
          status: "draft",
        }),
        makeProject({
          id: "up1",
          project_code: "MIG-2026-0002",
          project_name: "Uploaded Project",
          status: "uploaded",
        }),
        makeProject({
          id: "as1",
          project_code: "MIG-2026-0003",
          project_name: "Assessed Project",
          status: "assessed",
        }),
      ],
    });

    renderList();

    const draftRow = (await screen.findByText("Draft Project")).closest("tr") as HTMLElement;
    const draftLink = draftRow.querySelector("a") as HTMLAnchorElement;
    expect(draftLink).toHaveTextContent("Upload data");
    expect(draftLink).toHaveAttribute("href", "/projects/draft1/upload");

    const uploadedRow = (await screen.findByText("Uploaded Project")).closest(
      "tr",
    ) as HTMLElement;
    const uploadedLink = uploadedRow.querySelector("a") as HTMLAnchorElement;
    expect(uploadedLink).toHaveTextContent("Open assessment");
    expect(uploadedLink).toHaveAttribute("href", "/projects/up1/assessment");

    const assessedRow = (await screen.findByText("Assessed Project")).closest(
      "tr",
    ) as HTMLElement;
    const assessedLink = assessedRow.querySelector("a") as HTMLAnchorElement;
    expect(assessedLink).toHaveTextContent("Open assessment");
    expect(assessedLink).toHaveAttribute("href", "/projects/as1/assessment");
  });
});
