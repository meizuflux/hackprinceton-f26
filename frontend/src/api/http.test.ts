import { afterEach, describe, expect, it, vi } from "vitest";
import { resolveApiBase } from "./client";
import { ApiError, createHttpApi, isApiError } from "./http";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

describe("adapter selection", () => {
  it("defaults development to the proxied backend and other modes to the mock", () => {
    expect(resolveApiBase(undefined, "development")).toBe("/api");
    expect(resolveApiBase(undefined, "production")).toBeUndefined();
    expect(resolveApiBase(undefined, "test")).toBeUndefined();
  });

  it("honours an explicit base URL or mock", () => {
    expect(resolveApiBase("http://127.0.0.1:8000", "production")).toBe(
      "http://127.0.0.1:8000",
    );
    expect(resolveApiBase("mock", "development")).toBeUndefined();
  });
});

describe("HTTP case adapter", () => {
  afterEach(() => vi.unstubAllGlobals());
  const api = createHttpApi("/api/");

  it("uploads the ZIP with the project name as the case name", async () => {
    const fetchMock = vi.fn(async () =>
      json({ jobId: "a".repeat(32), caseId: "k-1" }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["PK"], "case.zip");
    await expect(
      api.createUpload(file, { caseName: " Kestrel " }),
    ).resolves.toEqual({ jobId: "a".repeat(32), caseId: "k-1" });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe("/api/upload");
    expect(init.method).toBe("POST");
    const form = init.body as FormData;
    expect(form.get("case_name")).toBe("Kestrel");
    expect(form.get("file")).toBeInstanceOf(File);
  });

  it("rejects non-ZIP files before uploading", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await expect(api.createUpload(new File(["x"], "a.tar"))).rejects.toThrow(
      ".zip",
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("maps job status, including failures and the case ID", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json({
          jobId: "j",
          status: "failed",
          progress: 100,
          stage: "failed",
          message: "BadZipFile: bad",
          caseId: "k-1",
        }),
      ),
    );
    await expect(api.getStatus("j")).resolves.toEqual({
      status: "failed",
      progress: 100,
      message: "BadZipFile: bad",
      stage: "failed",
      caseId: "k-1",
    });
  });

  it("loads a case by ID, or the latest ready case without one", async () => {
    const fetchMock = vi.fn(async () => json({ id: "k-1" }));
    vi.stubGlobal("fetch", fetchMock);
    await api.getCase("k-1");
    await api.getCase();
    expect(fetchMock.mock.calls.map((call) => (call as unknown[])[0])).toEqual([
      "/api/cases/k-1",
      "/api/case",
    ]);
  });

  it("surfaces the backend error envelope", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json({ error: { code: "case_not_found", message: "no case x" } }, 404),
      ),
    );
    const error = await api.getCase("x").catch((e: unknown) => e);
    expect(isApiError(error, "case_not_found")).toBe(true);
    expect((error as ApiError).status).toBe(404);
    expect((error as ApiError).message).toBe("no case x");
  });

  it("reports an unreachable service", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );
    await expect(api.listCases()).rejects.toMatchObject({
      code: "unreachable",
    });
  });

  it("opens the prepared demo case", async () => {
    const fetchMock = vi.fn(async () => json({ caseId: "kestrel-demo" }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(api.openDemo()).resolves.toBe("kestrel-demo");
    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe("/api/demo");
    expect(init.method).toBe("POST");
  });

  it("builds original evidence download URLs", () => {
    expect(api.evidenceFileUrl("k-1", "EV-071")).toBe(
      "/api/cases/k-1/evidence/EV-071",
    );
  });
});
