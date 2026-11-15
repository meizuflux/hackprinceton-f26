import { useCallback, useEffect, useRef, useState } from "react";
import {
  chatApi,
  ChatRequestError,
  type ChatMessage,
  type ChatStatus,
} from "../api/chat";

/** How an answer was produced: replayed from the recorded cache, or a live (billed) model call. */
export type ChatEntry = ChatMessage & {
  origin?: "suggested" | "typed";
  replayed?: boolean;
};

export type ChatFailure = {
  message: string;
  /** `needs_api_key`: not recorded, and the server has no key for a live call. */
  code?: string;
};

/** Shared state for the /chat page and the board's floating "Ask a question" widget. */
export function useCaseChat(caseId: string) {
  const [status, setStatus] = useState<ChatStatus | null>(null);
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [threadId, setThreadId] = useState<string>();
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<ChatFailure>();
  const [statusCheck, setStatusCheck] = useState(0);
  const activeRequest = useRef<AbortController | null>(null);
  const threadRef = useRef<string | undefined>(undefined);
  threadRef.current = threadId;

  useEffect(() => {
    const controller = new AbortController();
    setStatus(null);
    void chatApi
      .status(caseId, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setStatus(result);
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, [caseId, statusCheck]);

  useEffect(() => {
    setMessages([]);
    setThreadId(undefined);
    setFailure(undefined);
    setPending(false);
    return () => {
      activeRequest.current?.abort();
      activeRequest.current = null;
    };
  }, [caseId]);

  const send = useCallback(
    async (text: string, origin: "suggested" | "typed") => {
      activeRequest.current?.abort();
      const controller = new AbortController();
      activeRequest.current = controller;
      setPending(true);
      setFailure(undefined);
      try {
        const reply = await chatApi.send(
          caseId,
          text,
          threadRef.current,
          controller.signal,
        );
        if (activeRequest.current !== controller) return;
        setThreadId(reply.thread_id);
        setMessages((current) => [
          ...current,
          {
            ...reply.message,
            origin: reply.suggested ? "suggested" : origin,
            replayed: reply.replayed,
          },
        ]);
      } catch (cause) {
        if (
          activeRequest.current === controller &&
          !(cause instanceof DOMException && cause.name === "AbortError")
        ) {
          setFailure({
            message:
              cause instanceof Error ? cause.message : "Chat request failed.",
            code: cause instanceof ChatRequestError ? cause.code : undefined,
          });
        }
      } finally {
        if (activeRequest.current === controller) {
          activeRequest.current = null;
          setPending(false);
        }
      }
    },
    [caseId],
  );

  const ask = useCallback(
    (text: string) => {
      const question = text.trim();
      if (!question || pending || !status?.available) return false;
      const origin = status.suggestions?.some((s) => s.question === question)
        ? "suggested"
        : "typed";
      setMessages((current) => [
        ...current,
        { role: "user", content: question, origin },
      ]);
      void send(question, origin);
      return true;
    },
    [pending, status, send],
  );

  const retry = useCallback(() => {
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser || pending || !status?.available) return;
    void send(lastUser.content, lastUser.origin ?? "typed");
  }, [messages, pending, status, send]);

  const cancel = useCallback(() => {
    activeRequest.current?.abort();
    activeRequest.current = null;
    setPending(false);
  }, []);

  return {
    status,
    messages,
    pending,
    failure,
    ask,
    retry,
    cancel,
    recheck: () => setStatusCheck((value) => value + 1),
    /** Typed questions need a server key; without one only recorded answers replay. */
    live: status?.available === true && status.live !== false,
  };
}
