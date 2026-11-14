/** Optional backend chat contract. This adapter never supplies mock answers. */
export type ChatCitation = {
  evidence_id: string;
  locator: Record<string, unknown> | string;
  excerpt: string;
  /** Present only when the backend can resolve this citation into CaseData.sources. */
  source_id?: string;
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  citations?: ChatCitation[];
  evidence_status?: "supported" | "partial" | "insufficient";
};

export type ChatStatus = {
  available: boolean;
  case_id?: string;
  authoritative?: boolean;
  reason?: string;
};

export type ChatReply = {
  thread_id: string;
  message: ChatMessage;
};

const configuredBase = import.meta.env.VITE_CHAT_API_BASE_URL?.trim();
const apiBase = (configuredBase || "").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(
      typeof detail?.detail === "string"
        ? detail.detail
        : `Chat service returned ${response.status}.`,
    );
  }
  return response.json() as Promise<T>;
}

export const chatApi = {
  async status(caseId: string, signal?: AbortSignal): Promise<ChatStatus> {
    try {
      const result = await request<ChatStatus>(
        `/api/chat/status?case_id=${encodeURIComponent(caseId)}`,
        { signal },
      );
      if (result.case_id !== caseId) {
        return {
          available: false,
          case_id: result.case_id,
          reason: "Chat is connected to a different case.",
        };
      }
      if (result.available && result.authoritative !== true) {
        return {
          available: false,
          case_id: result.case_id,
          reason: "Chat is not connected to an authoritative ingested case.",
        };
      }
      return { ...result, available: result.available === true };
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError")
        throw error;
      return {
        available: false,
        reason: configuredBase
          ? "The chat service is unavailable."
          : "Chat is unavailable for this fictional preview case.",
      };
    }
  },

  async send(
    caseId: string,
    message: string,
    threadId?: string,
    signal?: AbortSignal,
  ): Promise<ChatReply> {
    const reply = await request<ChatReply>(
      `/api/cases/${encodeURIComponent(caseId)}/chat`,
      {
        method: "POST",
        body: JSON.stringify({ message, thread_id: threadId }),
        signal,
      },
    );
    if (
      !reply ||
      typeof reply.thread_id !== "string" ||
      !reply.thread_id ||
      reply.message?.role !== "assistant" ||
      typeof reply.message.content !== "string" ||
      !reply.message.content.trim() ||
      (reply.message.evidence_status !== undefined &&
        !["supported", "partial", "insufficient"].includes(
          reply.message.evidence_status,
        )) ||
      (reply.message.citations !== undefined &&
        (!Array.isArray(reply.message.citations) ||
          reply.message.citations.some(
            (citation) =>
              !citation ||
              typeof citation.evidence_id !== "string" ||
              !citation.evidence_id ||
              typeof citation.excerpt !== "string" ||
              !citation.locator ||
              (typeof citation.locator !== "string" &&
                (typeof citation.locator !== "object" ||
                  Array.isArray(citation.locator))) ||
              (citation.source_id !== undefined &&
                typeof citation.source_id !== "string"),
          )))
    ) {
      throw new Error(
        "The chat service returned an invalid response. Try again.",
      );
    }
    return reply;
  },
};
