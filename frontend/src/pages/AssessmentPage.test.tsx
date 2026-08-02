import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AssessmentPage } from "./AssessmentPage";
import { api, ApiError } from "../api/client";
import {
  makeBlockedReadiness,
  makeFile,
  makeIssue,
  makeProfile,
  makeProject,
  makeReadyReadiness,
} from "../test/fixtures";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    api: {
      getProject: vi.fn(),
      listFiles: vi.fn(),
      getProfile: vi.fn(),
      getIssues: vi.fn(),
      getReadiness: vi.fn(),
      runAssessment: vi.fn(),
    },
  };
});

function renderPage(projectId = "p1") {
  return render(
    <MemoryRouter initialEntries={[`/projects/${projectId}/assessment`]}>
      <Routes>
        <Route path="/projects/:projectId/assessment" element={<AssessmentPage />} />
        <Route path="/projects/:projectId/upload" element={<div>Upload route</div>} />
        <Route path="/" element={<div>Projects route</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

const assessmentRequiredError = new ApiError(
  "Run assessment on this file before requesting its readiness score.",
  409,
  "ASSESSMENT_REQUIRED",
);

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getProject).mockResolvedValue(makeProject());
  vi.mocked(api.listFiles).mockResolvedValue([makeFile()]);
  vi.mocked(api.getProfile).mockResolvedValue(makeProfile());
  vi.mocked(api.getIssues).mockResolvedValue({
    project_id: "p1",
    uploaded_file_id: "f1",
    total_issues: 0,
    items: [],
  });
  vi.mocked(api.getReadiness).mockResolvedValue(makeReadyReadiness());
});

describe("AssessmentPage", () => {
  // 1. Loads project/file/profile context.
  it("loads project, file and profile context", async () => {
    renderPage();

    expect(
      await screen.findByText(/MIG-2026-0001 · Nova Retail Pvt Ltd/),
    ).toBeInTheDocument();
    // Profiling metric visible.
    expect(await screen.findByText("Records")).toBeInTheDocument();
    expect(api.getProfile).toHaveBeenCalledWith("p1", "f1");
  });

  // 2. Before assessment: profiling visible, Run assessment enabled.
  it("shows profiling and an enabled Run assessment button before assessment", async () => {
    vi.mocked(api.getReadiness).mockRejectedValue(assessmentRequiredError);

    renderPage();

    expect(await screen.findByText("Assessment not run")).toBeInTheDocument();
    // Profiling still rendered despite readiness not being available.
    expect(screen.getByText("Records")).toBeInTheDocument();
    const button = screen.getByRole("button", { name: /run assessment/i });
    expect(button).toBeEnabled();
  });

  // 3. Clicking Run assessment refreshes readiness and issues.
  it("runs assessment and refreshes readiness and issues", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getReadiness)
      .mockRejectedValueOnce(assessmentRequiredError)
      .mockResolvedValue(makeReadyReadiness());
    vi.mocked(api.getIssues)
      .mockResolvedValueOnce({
        project_id: "p1",
        uploaded_file_id: "f1",
        total_issues: 0,
        items: [],
      })
      .mockResolvedValue({
        project_id: "p1",
        uploaded_file_id: "f1",
        total_issues: 1,
        items: [makeIssue()],
      });
    vi.mocked(api.runAssessment).mockResolvedValue({
      project_id: "p1",
      uploaded_file_id: "f1",
      total_records: 3,
      records_ready: 2,
      records_needing_review: 1,
      total_issues: 1,
      issues_by_severity: { critical: 0, high: 0, medium: 1, low: 0 },
      issues_by_rule: { "BR-006": 1 },
    });

    renderPage();
    const button = await screen.findByRole("button", { name: /run assessment/i });
    await user.click(button);

    expect(await screen.findByText("Assessment complete.")).toBeInTheDocument();
    expect(api.runAssessment).toHaveBeenCalledWith("p1", "f1");
    // Readiness meter now present.
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "98.96");
    // Issue row now present.
    expect(screen.getByText("BR-006")).toBeInTheDocument();
  });

  // 4. Readiness score, band and blockers render correctly.
  it("renders readiness score, band and migration-ready flag", async () => {
    renderPage();

    const meter = await screen.findByRole("progressbar");
    expect(meter).toHaveAttribute("aria-valuenow", "98.96");
    expect(meter).toHaveAttribute("aria-valuemax", "100");
    expect(meter.getAttribute("aria-label")).toMatch(/Ready/);
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByText("Yes")).toBeInTheDocument();
  });

  // 4b. Blocked readiness surfaces a prominent critical-blocker alert.
  it("shows a prominent blocker alert when band is blocked", async () => {
    vi.mocked(api.getReadiness).mockResolvedValue(makeBlockedReadiness());
    vi.mocked(api.getIssues).mockResolvedValue({
      project_id: "p1",
      uploaded_file_id: "f1",
      total_issues: 1,
      items: [makeIssue({ rule_id: "BR-004", severity: "critical" })],
    });

    renderPage();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/2 critical blockers must be resolved/i);
    expect(screen.getByText("Blocked")).toBeInTheDocument();
    expect(screen.getByText("No")).toBeInTheDocument();
  });

  // 5. Valid file shows ready state and no issues.
  it("shows the no-issues empty state for a clean assessed file", async () => {
    renderPage();

    expect(await screen.findByText("No issues found")).toBeInTheDocument();
  });

  // 6. Issues table shows full consultant context.
  it("shows full issue context in the issues table", async () => {
    vi.mocked(api.getReadiness).mockResolvedValue(
      makeReadyReadiness({ total_issues: 1, records_needing_review: 1, records_ready: 2 }),
    );
    vi.mocked(api.getIssues).mockResolvedValue({
      project_id: "p1",
      uploaded_file_id: "f1",
      total_issues: 1,
      items: [makeIssue()],
    });

    renderPage();

    const row = (await screen.findByText("BR-006")).closest("tr");
    expect(row).not.toBeNull();
    const cells = within(row as HTMLElement);
    expect(cells.getByText("Email format")).toBeInTheDocument();
    expect(cells.getByText("SMTP_ADDR")).toBeInTheDocument();
    expect(cells.getByText("medium")).toBeInTheDocument();
    expect(cells.getByText("bad-email")).toBeInTheDocument();
    expect(cells.getByText(/invalid format/i)).toBeInTheDocument();
    expect(cells.getByText(/Enter a valid email address/i)).toBeInTheDocument();
  });

  // 7. Severity filtering works.
  it("filters issues by severity", async () => {
    vi.mocked(api.getReadiness).mockResolvedValue(
      makeReadyReadiness({ total_issues: 2, records_needing_review: 2, records_ready: 1 }),
    );
    vi.mocked(api.getIssues).mockResolvedValue({
      project_id: "p1",
      uploaded_file_id: "f1",
      total_issues: 2,
      items: [
        makeIssue({ id: "i1", rule_id: "BR-004", severity: "critical", source_row_number: 1 }),
        makeIssue({ id: "i2", rule_id: "BR-006", severity: "medium", source_row_number: 2 }),
      ],
    });

    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("BR-004")).toBeInTheDocument();
    expect(screen.getByText("BR-006")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^critical$/i }));

    expect(screen.getByText("BR-004")).toBeInTheDocument();
    expect(screen.queryByText("BR-006")).not.toBeInTheDocument();
  });

  // 8. Missing current value displays "Missing".
  it("renders a null current value as Missing", async () => {
    vi.mocked(api.getReadiness).mockResolvedValue(
      makeReadyReadiness({ total_issues: 1, records_needing_review: 1, records_ready: 2 }),
    );
    vi.mocked(api.getIssues).mockResolvedValue({
      project_id: "p1",
      uploaded_file_id: "f1",
      total_issues: 1,
      items: [makeIssue({ rule_id: "BR-004", field_name: "STCD3", current_value: null })],
    });

    renderPage();

    const row = (await screen.findByText("BR-004")).closest("tr") as HTMLElement;
    expect(within(row).getByText("Missing")).toBeInTheDocument();
  });

  // 9. API failure retains already-loaded profile data.
  it("keeps profiling visible when readiness load fails", async () => {
    vi.mocked(api.getReadiness).mockRejectedValue(
      new ApiError("Internal error", 500),
    );

    renderPage();

    expect(await screen.findByText("Readiness unavailable")).toBeInTheDocument();
    // Profile metrics remain visible (labels unique to the metric strip).
    expect(screen.getByText("Records")).toBeInTheDocument();
    expect(screen.getByText("Missing values")).toBeInTheDocument();
  });

  // 10. No-file state links back to upload.
  it("shows an empty state linking back to upload when no file exists", async () => {
    vi.mocked(api.listFiles).mockResolvedValue([]);

    renderPage();

    const link = await screen.findByRole("link", { name: /upload ecc data/i });
    expect(link).toHaveAttribute("href", "/projects/p1/upload");
    await waitFor(() => expect(api.getProfile).not.toHaveBeenCalled());
  });
});
