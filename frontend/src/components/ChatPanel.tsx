import { ArrowUp, LoaderCircle, RotateCw } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { chatApi, type ChatMessage, type ChatStatus } from "../api/chat";
import "./chat-panel.css";

type ChatPanelProps = {
  caseId: string;
  onOpenSource: (sourceId: string) => void;
  sourceIds?: readonly string[];
};

export function ChatPanel({
  caseId,
  onOpenSource,
  sourceIds = [],
}: ChatPanelProps) {
  const [status, setStatus] = useState<ChatStatus | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [threadId, setThreadId] = useState<string>();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string>();
  const activeRequest = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [statusCheck, setStatusCheck] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setStatus(null);
    setMessages([]);
    setThreadId(undefined);
    setDraft("");
    setError(undefined);
    setPending(false);
    void chatApi
      .status(caseId, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setStatus(result);
      })
      .catch(() => undefined);
    return () => {
      controller.abort();
      activeRequest.current?.abort();
      activeRequest.current = null;
    };
  }, [caseId, statusCheck]);

  useEffect(() => {
    if (scrollRef.current)
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, pending]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || pending || !status?.available) return;
    setDraft("");
    setError(undefined);
    setMessages((current) => [...current, { role: "user", content: text }]);
    await send(text);
  }

  async function send(text: string) {
    const controller = new AbortController();
    activeRequest.current = controller;
    setPending(true);
    try {
      const response = await chatApi.send(
        caseId,
        text,
        threadId,
        controller.signal,
      );
      if (activeRequest.current !== controller) return;
      setThreadId(response.thread_id);
      setMessages((current) => [...current, response.message]);
    } catch (cause) {
      if (
        activeRequest.current === controller &&
        !(cause instanceof DOMException && cause.name === "AbortError")
      ) {
        setError(
          cause instanceof Error ? cause.message : "Chat request failed.",
        );
      }
    } finally {
      if (activeRequest.current === controller) {
        activeRequest.current = null;
        setPending(false);
      }
    }
  }

  function cancel() {
    activeRequest.current?.abort();
    activeRequest.current = null;
    setPending(false);
  }

  function retry() {
    const lastUser = [...messages]
      .reverse()
      .find((message) => message.role === "user");
    if (!lastUser || pending || !status?.available) return;
    setError(undefined);
    void send(lastUser.content);
  }

  return (
    <section className="chat-panel" aria-label="Ask about this case">
      <header className="chat-panel-heading">
        <div>
          <h1>Ask about this case</h1>
        </div>
        {status?.available && (
          <span className="chat-connection">Connected</span>
        )}
      </header>

      {status && !status.available && (
        <div className="chat-unavailable" role="status">
          <div className="chat-unavailable-heading">
            <strong>Case chat is unavailable</strong>
            <button
              type="button"
              onClick={() => setStatusCheck((value) => value + 1)}
              aria-label="Check chat availability again"
            >
              <RotateCw size={14} /> Check again
            </button>
          </div>
          <p>
            {status.reason ?? "The backend has not enabled chat for this case."}
          </p>
          <p>
            Answers require a connected backend with source citations. No
            preview answers are generated here.
          </p>
        </div>
      )}
      <div className="chat-transcript" ref={scrollRef} aria-live="polite">
        {!status && (
          <div className="chat-pending">
            <LoaderCircle size={15} className="chat-spinner" /> Checking chat
            availability…
          </div>
        )}
        {messages.length === 0 && status?.available && (
          <div className="chat-welcome">
            <p className="chat-empty">
              Ask a question grounded in the ingested evidence.
            </p>
            <div className="chat-prompts" aria-label="Suggested questions">
              {[
                "What evidence is available for this case?",
                "Which sources support the current timeline?",
                "What remains uncertain in the evidence?",
              ].map((prompt) => (
                <button
                  type="button"
                  key={prompt}
                  onClick={() => setDraft(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((message, index) => (
          <article
            className={`chat-message chat-${message.role}`}
            key={`${index}-${message.role}`}
          >
            <span className="chat-role">
              {message.role === "assistant" ? "CASE ASSISTANT" : "YOU"}
            </span>
            <p>{message.content}</p>
            {message.role === "assistant" && message.evidence_status && (
              <span
                className={`chat-evidence-status status-${message.evidence_status}`}
              >
                {message.evidence_status === "supported" &&
                message.citations?.length
                  ? "Evidence cited"
                  : message.evidence_status === "partial"
                    ? "Partially supported"
                    : "Insufficient evidence"}
              </span>
            )}
            {message.citations?.map((citation, citationIndex) => (
              <div
                className="chat-citation"
                key={`${citation.evidence_id}-${citationIndex}`}
              >
                <div className="chat-citation-title">
                  <strong>{citation.evidence_id}</strong>
                  <code>
                    {typeof citation.locator === "string"
                      ? citation.locator
                      : JSON.stringify(citation.locator)}
                  </code>
                  {citation.source_id &&
                    sourceIds.includes(citation.source_id) && (
                      <button
                        type="button"
                        onClick={() => onOpenSource(citation.source_id!)}
                      >
                        Open source
                      </button>
                    )}
                </div>
                <blockquote>{citation.excerpt}</blockquote>
              </div>
            ))}
          </article>
        ))}
        {pending && (
          <div className="chat-pending">
            <LoaderCircle size={15} className="chat-spinner" /> Checking cited
            evidence…
          </div>
        )}
      </div>
      {error && (
        <div className="chat-error" role="alert">
          <span>{error}</span>
          <button type="button" onClick={retry} disabled={pending}>
            <RotateCw size={14} /> Retry
          </button>
        </div>
      )}
      <form className="chat-composer" onSubmit={submit}>
        <label className="sr-only" htmlFor="case-chat-input">
          Ask a question
        </label>
        <textarea
          id="case-chat-input"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask about the evidence…"
          rows={2}
          disabled={!status?.available || pending}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              event.currentTarget.form?.requestSubmit();
            }
          }}
        />
        {pending ? (
          <button
            type="button"
            className="chat-send"
            onClick={cancel}
            aria-label="Cancel request"
          >
            Cancel
          </button>
        ) : (
          <button
            type="submit"
            className="chat-send"
            disabled={!draft.trim() || !status?.available}
            aria-label="Send question"
          >
            <ArrowUp size={17} />
          </button>
        )}
      </form>
      <p className="chat-footnote">
        {!status
          ? "Checking for an authoritative case connection."
          : status.available
            ? "Sources are shown with their original evidence ID and locator."
            : "No answers are generated until this case is connected to its backend."}
      </p>
    </section>
  );
}
