import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, ApiError } from "./client";
import {
  makeCviReady,
  makeIssue,
  makeProfile,
  makeReadyReadiness,
} from "../test/fixtures";

const BASE = "http://localhost:8000/api/v1";

function fakeResponse(body: unknown, ok: boolean, status: number): Response {
  return {
    ok,
    status,
    json: async () => body,
  } as unknown as Response;
}

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  // 13. Correct requests for profile / assessment / issues / readiness.
  it("requests the profile endpoint with a GET", async () => {
    const profile = makeProfile();
    fetchMock.mockResolvedValue(fakeResponse(profile, true, 200));

    const result = await api.getProfile("p1", "f1");

    expect(fetchMock).toHaveBeenCalledWith(`${BASE}/projects/p1/files/f1/profile`, undefined);
    expect(result).toEqual(profile);
  });

  it("posts to the assessment endpoint", async () => {
    fetchMock.mockResolvedValue(
      fakeResponse(
        {
          project_id: "p1",
          uploaded_file_id: "f1",
          total_records: 3,
          records_ready: 3,
          records_needing_review: 0,
          total_issues: 0,
          issues_by_severity: { critical: 0, high: 0, medium: 0, low: 0 },
          issues_by_rule: {},
        },
        true,
        200,
      ),
    );

    await api.runAssessment("p1", "f1");

    expect(fetchMock).toHaveBeenCalledWith(`${BASE}/projects/p1/files/f1/assessment`, {
      method: "POST",
    });
  });

  it("requests the issues endpoint with a GET", async () => {
    fetchMock.mockResolvedValue(
      fakeResponse(
        { project_id: "p1", uploaded_file_id: "f1", total_issues: 1, items: [makeIssue()] },
        true,
        200,
      ),
    );

    const result = await api.getIssues("p1", "f1");

    expect(fetchMock).toHaveBeenCalledWith(`${BASE}/projects/p1/files/f1/issues`, undefined);
    expect(result.items[0].rule_id).toBe("BR-006");
  });

  // 14. Readiness response is typed through and returned intact.
  it("requests readiness and returns the typed response", async () => {
    const readiness = makeReadyReadiness();
    fetchMock.mockResolvedValue(fakeResponse(readiness, true, 200));

    const result = await api.getReadiness("p1", "f1");

    expect(fetchMock).toHaveBeenCalledWith(`${BASE}/projects/p1/files/f1/readiness`, undefined);
    expect(result.score).toBe(98.96);
    expect(result.band).toBe("ready");
    expect(result.components.record_readiness.weight).toBe(0.35);
  });

  it("requests the Day 5 CVI readiness endpoint", async () => {
    const readiness = makeCviReady();
    fetchMock.mockResolvedValue(fakeResponse(readiness, true, 200));

    const result = await api.getCviReadiness("p1", "f1");

    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/projects/p1/files/f1/cvi-readiness`,
      undefined,
    );
    expect(result.cvi_ready).toBe(true);
    expect(result.bp_category.code).toBe("2");
  });

  // ASSESSMENT_REQUIRED must be distinguishable from a generic failure.
  it("surfaces the ASSESSMENT_REQUIRED code on the ApiError", async () => {
    fetchMock.mockResolvedValue(
      fakeResponse(
        { detail: { code: "ASSESSMENT_REQUIRED", message: "Run assessment first." } },
        false,
        409,
      ),
    );

    await expect(api.getReadiness("p1", "f1")).rejects.toMatchObject({
      code: "ASSESSMENT_REQUIRED",
      status: 409,
    });
    await expect(api.getReadiness("p1", "f1")).rejects.toBeInstanceOf(ApiError);
  });
});
