/** Backend case chat contract (see frontend/CHAT.md). This adapter never supplies mock answers. */
export type ChatCitation = {
  evidence_id: string;
  locator: Record<string, unknown> | string;
  excerpt: string;
  /** Present only when the backend can resolve this citation into CaseData.sources. */
  source_id?: string;
};

export type EvidenceStatus = "supported" | "partial" | "insufficient";

/** A cited observation; `citations` index into the message's `citations`. */
export type ChatObservation = { text: string; citations: number[] };

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  citations?: ChatCitation[];
  evidence_status?: EvidenceStatus;
  summary?: string;
  observations?: ChatObservation[];
  inference?: string;
  unknowns?: string[];
};

export type ChatSuggestion = { question: string; recorded: boolean };

export type ChatStatus = {
  available: boolean;
  case_id?: string;
  authoritative?: boolean;
  /** True when the server holds an API key, so typed questions call the model. */
  live?: boolean;
  mode?: "live" | "replay";
  model?: string;
  suggestions?: ChatSuggestion[];
  reason?: string;
};

export type ChatReply = {
  thread_id: string;
  message: ChatMessage;
  /** The question matched a suggested question and was answered without thread history. */
  suggested?: boolean;
  /** Every model response came from the recorded cache: no model call was billed. */
  replayed?: boolean;
  model_calls?: number;
  /** The answer's tool loop in order (backend/TRACE.md). */
  steps?: ChatStep[];
};

export type ChatStep =
  | {
      type: "model_call";
      inputTokens: number;
      outputTokens: number;
      costUsd: number;
      durationMs: number;
      durationSource: "recorded" | "estimated" | "live";
    }
  | {
      type: "tool_call";
      tool: string;
      args: Record<string, unknown>;
      resultChars: number;
    };

export class ChatRequestError extends Error {
  constructor(
    message: string,
    readonly code?: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ChatRequestError";
  }
}

const configuredBase = import.meta.env.VITE_CHAT_API_BASE_URL?.trim();
const apiBase = (configuredBase || "").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new ChatRequestError(
      typeof detail?.error?.message === "string"
        ? detail.error.message
        : typeof detail?.detail === "string"
          ? detail.detail
          : `Chat service returned ${response.status}.`,
      typeof detail?.error?.code === "string" ? detail.error.code : undefined,
      response.status,
    );
  }
  return response.json() as Promise<T>;
}

function validCitation(citation: ChatCitation | null | undefined) {
  return (
    !!citation &&
    typeof citation.evidence_id === "string" &&
    !!citation.evidence_id &&
    typeof citation.excerpt === "string" &&
    !!citation.locator &&
    (typeof citation.locator === "string" ||
      (typeof citation.locator === "object" &&
        !Array.isArray(citation.locator))) &&
    (citation.source_id === undefined || typeof citation.source_id === "string")
  );
}

/** Keeps only well-formed structured fields; observation citations must point at a returned citation. */
function sanitize(message: ChatMessage): ChatMessage {
  const count = message.citations?.length ?? 0;
  const observations = Array.isArray(message.observations)
    ? message.observations.filter(
        (o) =>
          o &&
          typeof o.text === "string" &&
          Array.isArray(o.citations) &&
          o.citations.length > 0 &&
          o.citations.every((i) => Number.isInteger(i) && i >= 0 && i < count),
      )
    : undefined;
  return {
    role: "assistant",
    content: message.content,
    citations: message.citations,
    evidence_status: message.evidence_status,
    summary: typeof message.summary === "string" ? message.summary : undefined,
    observations,
    inference:
      typeof message.inference === "string" ? message.inference : undefined,
    unknowns: Array.isArray(message.unknowns)
      ? message.unknowns.filter((u) => typeof u === "string")
      : undefined,
  };
}

export function citationLabel(citation: ChatCitation) {
  return `${citation.evidence_id} ${
    typeof citation.locator === "string"
      ? citation.locator
      : JSON.stringify(citation.locator)
  }`;
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
      const suggestions = Array.isArray(result.suggestions)
        ? result.suggestions.filter(
            (s) => s && typeof s.question === "string" && s.question.trim(),
          )
        : undefined;
      return {
        ...result,
        available: result.available === true,
        ...(suggestions ? { suggestions } : {}),
      };
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
          !reply.message.citations.every(validCitation)))
    ) {
      throw new Error(
        "The chat service returned an invalid response. Try again.",
      );
    }
    return { ...reply, message: sanitize(reply.message) };
  },
};
