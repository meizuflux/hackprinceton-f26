import { demoCase } from "./fixtures";
import { createHttpApi } from "./http";
import type { CaseApi, IngestionProgress, UploadResult } from "./types";

const MOCK_PROCESSING_MS = 5_000;
const jobs = new Map<string, number>();
let nextJob = 1;

/** Mock adapter: validates upload metadata only; never reads or parses the ZIP. */
export const mockApi: CaseApi = {
  mode: "mock",

  async createUpload(file: File): Promise<UploadResult> {
    if (!file.name.toLowerCase().endsWith(".zip")) {
      throw new Error("Choose a .zip archive.");
    }
    if (file.size === 0) {
      throw new Error("The ZIP archive is empty.");
    }
    const jobId = `demo-job-${nextJob++}`;
    jobs.set(jobId, Date.now());
    return { jobId, caseId: demoCase.id };
  },

  async getStatus(jobId: string): Promise<IngestionProgress> {
    const startedAt = jobs.get(jobId);
    if (startedAt === undefined) throw new Error("Unknown ingestion job.");
    const elapsed = Date.now() - startedAt;
    if (elapsed >= MOCK_PROCESSING_MS) {
      return {
        status: "ready",
        progress: 100,
        message: "Workspace preview ready.",
        caseId: demoCase.id,
      };
    }
    const progress = Math.min(
      95,
      Math.floor((elapsed / MOCK_PROCESSING_MS) * 100),
    );
    const message =
      elapsed < 1_700
        ? "Preparing workspace…"
        : elapsed < 3_400
          ? "Organizing evidence…"
          : "Preparing review…";
    return { status: "processing", progress, message };
  },

  async getCase() {
    return demoCase;
  },

  async listCases() {
    return [];
  },

  evidenceFileUrl() {
    return undefined;
  },
};

/**
 * `VITE_API_BASE_URL` selects the backend; `mock` (or an empty value outside
 * development) selects the fixture adapter. Development defaults to `/api`,
 * which Vite proxies to the backend.
 */
export function resolveApiBase(
  configured: string | undefined,
  mode: string,
): string | undefined {
  const value = configured?.trim();
  if (value === "mock") return undefined;
  if (value) return value;
  return mode === "development" ? "/api" : undefined;
}

const apiBase = resolveApiBase(
  import.meta.env.VITE_API_BASE_URL,
  import.meta.env.MODE,
);

export const api: CaseApi = apiBase ? createHttpApi(apiBase) : mockApi;

export const isMock = api.mode === "mock";
