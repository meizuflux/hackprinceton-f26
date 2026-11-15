import type {
  AuditChain,
  CaseApi,
  EvidenceFile,
  EvidenceView,
  RecordPage,
  CaseData,
  CaseSummary,
  IngestionProgress,
  UploadOptions,
  UploadResult,
} from "./types";

/** An error returned by the backend as `{"error": {"code", "message"}}`. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function isApiError(error: unknown, code?: string): error is ApiError {
  return (
    error instanceof ApiError && (code === undefined || error.code === code)
  );
}

/** Read the backend error body, falling back to FastAPI's `detail`. */
export async function readApiError(response: Response): Promise<ApiError> {
  const body = await response.json().catch(() => null);
  const code =
    typeof body?.error?.code === "string" ? body.error.code : "http_error";
  const message =
    typeof body?.error?.message === "string"
      ? body.error.message
      : typeof body?.detail === "string"
        ? body.detail
        : `The server returned ${response.status}.`;
  return new ApiError(response.status, code, message);
}

/** Adapter for `backend/mapletrace_api`. The backend is authoritative for every case fact. */
export function createHttpApi(baseUrl: string): CaseApi {
  const base = baseUrl.replace(/\/$/, "");

  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    let response: Response;
    try {
      response = await fetch(`${base}${path}`, init);
    } catch {
      throw new ApiError(0, "unreachable", "The case service is unreachable.");
    }
    if (!response.ok) throw await readApiError(response);
    return response.json() as Promise<T>;
  }

  return {
    mode: "live",

    async createUpload(
      file: File,
      options?: UploadOptions,
    ): Promise<UploadResult> {
      if (!file.name.toLowerCase().endsWith(".zip")) {
        throw new Error("Choose a .zip archive.");
      }
      if (file.size === 0) throw new Error("The ZIP archive is empty.");
      const form = new FormData();
      form.append("file", file);
      const caseName = options?.caseName?.trim();
      if (caseName) form.append("case_name", caseName);
      return request<UploadResult>("/upload", { method: "POST", body: form });
    },

    async getStatus(jobId: string): Promise<IngestionProgress> {
      const job = await request<Partial<IngestionProgress>>(
        `/status/${encodeURIComponent(jobId)}`,
      );
      const status =
        job.status === "ready" || job.status === "failed"
          ? job.status
          : "processing";
      return {
        status,
        progress: typeof job.progress === "number" ? job.progress : 0,
        message: job.message ?? "",
        stage: job.stage,
        caseId: job.caseId,
      };
    },

    getCase(caseId?: string): Promise<CaseData> {
      return request<CaseData>(
        caseId ? `/cases/${encodeURIComponent(caseId)}` : "/case",
      );
    },

    async openDemo(): Promise<string> {
      const result = await request<{ caseId: string }>("/demo", {
        method: "POST",
      });
      return result.caseId;
    },

    listCases(): Promise<CaseSummary[]> {
      return request<CaseSummary[]>("/cases");
    },

    listFiles(caseId: string): Promise<EvidenceFile[]> {
      return request<EvidenceFile[]>(
        `/cases/${encodeURIComponent(caseId)}/files`,
      );
    },

    getRecords(caseId, query = {}): Promise<RecordPage> {
      const params = new URLSearchParams();
      if (query.evidenceId) params.set("evidenceId", query.evidenceId);
      if (query.recordType) params.set("recordType", query.recordType);
      if (query.limit !== undefined) params.set("limit", String(query.limit));
      if (query.offset !== undefined)
        params.set("offset", String(query.offset));
      const search = params.size ? `?${params}` : "";
      return request<RecordPage>(
        `/cases/${encodeURIComponent(caseId)}/records${search}`,
      );
    },

    getAuditChain(caseId: string): Promise<AuditChain> {
      return request<AuditChain>(
        `/cases/${encodeURIComponent(caseId)}/audit-chain`,
      );
    },

    viewEvidence(caseId, evidenceId, query = {}): Promise<EvidenceView> {
      const params = new URLSearchParams();
      if (query.locator) params.set("locator", query.locator);
      if (query.offset !== undefined)
        params.set("offset", String(query.offset));
      if (query.limit !== undefined) params.set("limit", String(query.limit));
      const search = params.size ? `?${params}` : "";
      return request<EvidenceView>(
        `/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(evidenceId)}/view${search}`,
      );
    },

    evidenceFileUrl(caseId: string, evidenceId: string, options = {}) {
      return `${base}/cases/${encodeURIComponent(caseId)}/evidence/${encodeURIComponent(evidenceId)}${options.inline ? "?inline=true" : ""}`;
    },
  };
}
