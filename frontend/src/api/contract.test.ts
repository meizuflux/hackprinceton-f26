import { afterEach, describe, expect, it, vi } from "vitest";
import { api, isMock } from "./client";
import { demoCase } from "./fixtures";

describe("demo case contract", () => {
  const sourceIds = new Set(demoCase.sources.map((source) => source.id));
  const nodeIds = new Set(demoCase.nodes.map((node) => node.id));
  const gapIds = new Set(demoCase.gaps.map((gap) => gap.id));
  const suggestionIds = new Set(
    demoCase.suggestions.map((suggestion) => suggestion.id),
  );

  const expectCitationsResolve = (citations: string[]) => {
    expect(citations.length).toBeGreaterThan(0);
    for (const citation of citations)
      expect(sourceIds.has(citation)).toBe(true);
  };

  it("uses resolvable citations and graph references throughout the fixture", () => {
    for (const node of demoCase.nodes) {
      expectCitationsResolve(node.citations);
      if (node.gapId) expect(gapIds.has(node.gapId)).toBe(true);
    }
    for (const edge of demoCase.edges) {
      expect(nodeIds.has(edge.source)).toBe(true);
      expect(nodeIds.has(edge.target)).toBe(true);
      expectCitationsResolve(edge.citations);
    }
    for (const gap of demoCase.gaps) {
      expectCitationsResolve(gap.citations);
      expect(gap.suggestedEvidence.length).toBeGreaterThan(0);
      for (const suggestionId of gap.suggestedEvidence)
        expect(suggestionIds.has(suggestionId)).toBe(true);
    }
    for (const insight of demoCase.insights)
      expectCitationsResolve(insight.citations);
    for (const suggestion of demoCase.suggestions) {
      expectCitationsResolve(suggestion.citations);
      expect(gapIds.has(suggestion.gapId)).toBe(true);
    }
  });

  it("is explicitly marked as a mock and returns the demo fixture", async () => {
    expect(isMock).toBe(true);
    await expect(api.getCase()).resolves.toBe(demoCase);
  });
});

describe("mock upload adapter", () => {
  afterEach(() => vi.useRealTimers());

  const fileWithSize = (name: string, size: number) => {
    const file = new File([], name);
    Object.defineProperty(file, "size", { value: size });
    return file;
  };

  it("rejects files without a ZIP extension", async () => {
    await expect(
      api.createUpload(fileWithSize("evidence.tar", 42)),
    ).rejects.toThrow(".zip");
  });

  it("rejects empty ZIP archives", async () => {
    await expect(
      api.createUpload(fileWithSize("empty.zip", 0)),
    ).rejects.toThrow("empty");
  });

  it("rejects archives larger than 100 MB", async () => {
    await expect(
      api.createUpload(fileWithSize("large.zip", 100 * 1024 * 1024 + 1)),
    ).rejects.toThrow("100 MB");
  });

  it("simulates progressive work and completes after five seconds without reading the archive", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-11-14T14:00:00Z"));
    const { jobId } = await api.createUpload(fileWithSize("case.zip", 1024));

    await expect(api.getStatus(jobId)).resolves.toMatchObject({
      status: "processing",
      progress: 0,
      message: expect.stringContaining("Preparing workspace"),
    });
    vi.advanceTimersByTime(1_700);
    await expect(api.getStatus(jobId)).resolves.toMatchObject({
      status: "processing",
      message: expect.stringContaining("Organizing evidence"),
    });
    vi.advanceTimersByTime(1_700);
    await expect(api.getStatus(jobId)).resolves.toMatchObject({
      status: "processing",
      message: expect.stringContaining("Preparing review"),
    });
    vi.advanceTimersByTime(1_600);
    await expect(api.getStatus(jobId)).resolves.toMatchObject({
      status: "ready",
      progress: 100,
    });
  });

  it("rejects unknown job IDs", async () => {
    await expect(api.getStatus("not-a-job")).rejects.toThrow(
      "Unknown ingestion job",
    );
  });
});
