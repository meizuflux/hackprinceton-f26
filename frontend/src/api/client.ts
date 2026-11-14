import { demoCase } from "./fixtures";
import type { CaseApi, IngestionProgress, UploadResult } from "./types";

const MOCK_PROCESSING_MS = 5_000;
const jobs = new Map<string, number>();
let nextJob = 1;

/** Mock adapter: validates upload metadata only; never reads or parses the ZIP. */
export const api: CaseApi = {
  async createUpload(file: File): Promise<UploadResult> {
    if (!file.name.toLowerCase().endsWith(".zip")) {
      throw new Error("Choose a .zip archive.");
    }
    if (file.size === 0) {
      throw new Error("The ZIP archive is empty.");
    }
    const jobId = `demo-job-${nextJob++}`;
    jobs.set(jobId, Date.now());
    return { jobId };
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
};

export const isMock = true;
