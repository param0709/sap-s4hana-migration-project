import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AssessmentPage } from "./AssessmentPage";
import { api, ApiError } from "../api/client";
import {
  makeCviBlocked,
  makeCviReady,
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
      getCviReadiness: vi.fn(),
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

const cviAssessmentRequiredError = new ApiError(
  "Run assessment on this file before requesting CVI readiness.",
  409,
  "ASSESSMENT_REQUIRED",
);

const readinessUnavailableError = new ApiError(
  "This file has no complete persisted record set to score. Re-upload the file before requesting readiness.",
  409,
  "READINESS_DATA_UNAVAILABLE",
);

const profileUnavailableError = new ApiError(
  "The persisted record count does not match this upload's metadata. Re-upload the file to rebuild a complete profile source.",
  409,
  "PROFILE_DATA_UNAVAILABLE",
);

const emptyIssues = (fileId = "f1") => ({
  project_id: "p1",
  uploaded_file_id: fileId,
  total_issues: 0,
  items: [],
});

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
  vi.mocked(api.getCviReadiness).mockResolvedValue(makeCviReady());
});

describe("AssessmentPage", () => {
  // 1. Loads project/file/profile context.
  it("loads project, file and profile context", async () => {
    renderPage();

    expect(
      await screen.findByText(/MIG-2026-0001 · Nova Retail Pvt Ltd/),
    ).toBeInTheDocument();
    // Profiling metric visible.
    expect((await screen.findAllByText("Records")).length).toBeGreaterThan(0);
    expect(api.getProfile).toHaveBeenCalledWith("p1", "f1");
  });

  // 2. Before assessment: profiling visible, Run assessment enabled.
  it("shows profiling and an enabled Run assessment button before assessment", async () => {
    vi.mocked(api.getReadiness).mockRejectedValue(assessmentRequiredError);
    vi.mocked(api.getCviReadiness).mockRejectedValue(cviAssessmentRequiredError);

    renderPage();

    expect(await screen.findByText("Assessment not run")).toBeInTheDocument();
    // Profiling still rendered despite readiness not being available.
    expect(screen.getAllByText("Records").length).toBeGreaterThan(0);
    const button = screen.getByRole("button", { name: /run assessment/i });
    expect(button).toBeEnabled();
  });

  // 3. Clicking Run assessment refreshes readiness and issues.
  it("runs assessment and refreshes readiness and issues", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getReadiness)
      .mockRejectedValueOnce(assessmentRequiredError)
      .mockResolvedValue(makeReadyReadiness());
    vi.mocked(api.getCviReadiness)
      .mockRejectedValueOnce(cviAssessmentRequiredError)
      .mockResolvedValue(makeCviReady());
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

    expect(
      await screen.findByText("Assessment and CVI readiness refreshed."),
    ).toBeInTheDocument();
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

  it("renders a ready Day 5 CVI result and account-group mapping", async () => {
    renderPage();

    expect(await screen.findByText("CVI ready")).toBeInTheDocument();
    expect(screen.getByText("CVI-001")).toBeInTheDocument();
    expect(screen.getByText("FLCU00")).toBeInTheDocument();
    expect(screen.getAllByText("ZEXP")).toHaveLength(2);
  });

  it("surfaces failed CVI checks and their true source rows", async () => {
    vi.mocked(api.getCviReadiness).mockResolvedValue(makeCviBlocked());

    renderPage();

    expect(await screen.findByText("CVI blocked")).toBeInTheDocument();
    const cviAlert = screen
      .getAllByRole("alert")
      .find((alert) => /1 CVI check requires attention/i.test(alert.textContent ?? ""));
    expect(cviAlert).toBeInTheDocument();
    expect(screen.getByText(/Unmapped/)).toHaveTextContent(/ZUNK.*rows 4/i);
    expect(screen.getByText(/Rows: 4/)).toHaveTextContent(/Approve the missing target mapping/i);
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
    expect(
      screen.getByText(/Every assessed record passed the deterministic business rules/i),
    ).toBeInTheDocument();
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
    expect(screen.getAllByText("Records").length).toBeGreaterThan(0);
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

  // 11. An incomplete persisted record set must never read as a clean pass.
  it("shows the unavailable issue state when the record set is incomplete", async () => {
    vi.mocked(api.getProfile).mockRejectedValue(profileUnavailableError);
    vi.mocked(api.getReadiness).mockRejectedValue(readinessUnavailableError);
    // The issues endpoint still answers 200 with an empty collection.
    vi.mocked(api.getIssues).mockResolvedValue(emptyIssues());

    renderPage();

    expect(await screen.findByText("Issue assessment unavailable")).toBeInTheDocument();
    expect(
      screen.getByText(
        /does not have a complete persisted record set for issue assessment/i,
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("No issues found")).not.toBeInTheDocument();
    expect(screen.queryByText(/Every assessed record passed/i)).not.toBeInTheDocument();
    // The defensive readiness and profile messages are unchanged.
    expect(screen.getByText("Readiness unavailable")).toBeInTheDocument();
    expect(screen.getByText("Profile unavailable")).toBeInTheDocument();
    // Re-upload uses the existing upload route.
    expect(screen.getByRole("link", { name: /re-upload source file/i })).toHaveAttribute(
      "href",
      "/projects/p1/upload",
    );
  });

  // 11b. Readiness alone being unavailable is enough to distrust the collection.
  it("does not claim a clean pass when only readiness data is unavailable", async () => {
    vi.mocked(api.getReadiness).mockRejectedValue(readinessUnavailableError);
    vi.mocked(api.getIssues).mockResolvedValue(emptyIssues());

    renderPage();

    expect(await screen.findByText("Issue assessment unavailable")).toBeInTheDocument();
    expect(screen.queryByText("No issues found")).not.toBeInTheDocument();
  });

  // 12. A failed issue request is not an empty successful result.
  it("shows a load failure when the issues request fails", async () => {
    vi.mocked(api.getIssues).mockRejectedValue(
      new ApiError("Internal error", 500),
    );

    renderPage();

    expect(await screen.findByText("Unable to load issues")).toBeInTheDocument();
    expect(screen.queryByText("No issues found")).not.toBeInTheDocument();
    expect(screen.queryByText(/Every assessed record passed/i)).not.toBeInTheDocument();
  });

  // 12b. A transport failure falls back to the generic guidance.
  it("falls back to generic guidance when the issue error has no message", async () => {
    vi.mocked(api.getIssues).mockRejectedValue(new Error("boom"));

    renderPage();

    expect(await screen.findByText("Unable to load issues")).toBeInTheDocument();
    expect(
      screen.getByText(/The issue assessment could not be loaded/i),
    ).toBeInTheDocument();
  });

  // 13. An unassessed file is never presented as having passed.
  it("keeps the assessment-required state and never claims a pass", async () => {
    vi.mocked(api.getReadiness).mockRejectedValue(assessmentRequiredError);
    vi.mocked(api.getCviReadiness).mockRejectedValue(cviAssessmentRequiredError);

    renderPage();

    expect(await screen.findByText("Assessment not run")).toBeInTheDocument();
    expect(screen.getByText("Not assessed yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run assessment/i })).toBeEnabled();
    expect(screen.queryByText("No issues found")).not.toBeInTheDocument();
    expect(screen.queryByText(/Every assessed record passed/i)).not.toBeInTheDocument();
    expect(screen.getAllByText("Assessment required").length).toBeGreaterThan(0);
  });

  // 14. Switching source files must not leak the previous file's issue state.
  it("resets issue state when the source file changes", async () => {
    const user = userEvent.setup();
    const first = makeFile();
    const second = makeFile({
      id: "f2",
      file_name: "incomplete_ecc_customers.csv",
      uploaded_at: "2026-07-30T07:24:00Z",
    });
    vi.mocked(api.listFiles).mockResolvedValue([first, second]);
    vi.mocked(api.getProfile).mockImplementation(async (_p, fileId) => {
      if (fileId === "f2") throw profileUnavailableError;
      return makeProfile();
    });
    vi.mocked(api.getIssues).mockImplementation(async (_p, fileId) => ({
      project_id: "p1",
      uploaded_file_id: fileId,
      total_issues: fileId === "f1" ? 1 : 0,
      items: fileId === "f1" ? [makeIssue()] : [],
    }));
    vi.mocked(api.getReadiness).mockImplementation(async (_p, fileId) => {
      if (fileId === "f2") throw readinessUnavailableError;
      return makeReadyReadiness({ total_issues: 1, records_needing_review: 1 });
    });

    renderPage();

    expect(await screen.findByText("BR-006")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText(/source file/i), "f2");

    expect(await screen.findByText("Issue assessment unavailable")).toBeInTheDocument();
    expect(screen.queryByText("BR-006")).not.toBeInTheDocument();
    expect(screen.queryByText("No issues found")).not.toBeInTheDocument();
    expect(screen.queryByText(/Every assessed record passed/i)).not.toBeInTheDocument();
  });

  // 15. Switching back to a healthy file restores its issues and filters.
  it("restores issues and severity filtering after switching back", async () => {
    const user = userEvent.setup();
    const first = makeFile();
    const second = makeFile({
      id: "f2",
      file_name: "incomplete_ecc_customers.csv",
      uploaded_at: "2026-07-30T07:24:00Z",
    });
    vi.mocked(api.listFiles).mockResolvedValue([first, second]);
    vi.mocked(api.getProfile).mockImplementation(async (_p, fileId) => {
      if (fileId === "f2") throw profileUnavailableError;
      return makeProfile();
    });
    vi.mocked(api.getIssues).mockImplementation(async (_p, fileId) => ({
      project_id: "p1",
      uploaded_file_id: fileId,
      total_issues: fileId === "f1" ? 2 : 0,
      items:
        fileId === "f1"
          ? [
              makeIssue({ id: "i1", rule_id: "BR-004", severity: "critical" }),
              makeIssue({ id: "i2", rule_id: "BR-006", severity: "medium" }),
            ]
          : [],
    }));
    vi.mocked(api.getReadiness).mockImplementation(async (_p, fileId) => {
      if (fileId === "f2") throw readinessUnavailableError;
      return makeReadyReadiness({ total_issues: 2, records_needing_review: 2 });
    });

    renderPage();

    const select = await screen.findByLabelText(/source file/i);
    expect(await screen.findByText("BR-004")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /^critical$/i }));
    expect(screen.queryByText("BR-006")).not.toBeInTheDocument();

    await user.selectOptions(select, "f2");
    expect(await screen.findByText("Issue assessment unavailable")).toBeInTheDocument();

    await user.selectOptions(select, "f1");
    // Issues return and the stale severity filter is cleared.
    expect(await screen.findByText("BR-004")).toBeInTheDocument();
    expect(screen.getByText("BR-006")).toBeInTheDocument();
  });
});
