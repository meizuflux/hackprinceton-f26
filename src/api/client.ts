import { demoCase } from "./fixtures";
import type { CaseApi, IngestionProgress, UploadResult } from "./types";

const MAX_UPLOAD_BYTES = 100 * 1024 * 1024;
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
    if (file.size > MAX_UPLOAD_BYTES) {
      throw new Error("ZIP archives must be 100 MB or smaller.");
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
        message: "Demo case ready. The uploaded archive was not parsed.",
      };
    }
    const progress = Math.min(
      95,
      Math.floor((elapsed / MOCK_PROCESSING_MS) * 100),
    );
    const message =
      elapsed < 1_700
        ? "Mock: Parsing artifacts… (simulated; ZIP contents are not read)"
        : elapsed < 3_400
          ? "Mock: Building graph… (simulated; ZIP contents are not read)"
          : "Mock: Scoring gaps… (simulated; ZIP contents are not read)";
    return { status: "processing", progress, message };
  },

  async getCase() {
    return demoCase;
  },
};

export const isMock = true;
