import { LoaderCircle, RotateCw } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";
import { ChatComposer } from "./ChatComposer";
import { ChatMessageView } from "./ChatMessageView";
import { ChatFailureNotice, ChatSuggestions } from "./ChatSuggestions";
import { useCaseChat } from "./useCaseChat";
import "./chat-panel.css";

type CaseChat = ReturnType<typeof useCaseChat>;

/** The conversation body shared by the /chat page and the board's "Ask a question" widget. */
export function ChatThread({
  chat,
  sourceIds,
  onOpenSource,
  compact = false,
}: {
  chat: CaseChat;
  sourceIds: readonly string[];
  onOpenSource: (sourceId: string) => void;
  compact?: boolean;
}) {
  const { status, messages, pending, failure, live } = chat;
  const scrollRef = useRef<HTMLDivElement>(null);
  const sources = useMemo(() => new Set(sourceIds), [sourceIds]);

  useEffect(() => {
    if (scrollRef.current && messages.length)
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, pending, failure]);

  return (
    <div className="chat-transcript" ref={scrollRef}>
      {!status && (
        <div className="chat-pending" role="status">
          <LoaderCircle size={15} className="chat-spinner" /> Checking chat
          availability…
        </div>
      )}
      {status && !status.available && (
        <div className="chat-unavailable" role="status">
          <div className="chat-unavailable-heading">
            <strong>Case chat is unavailable</strong>
            <button
              type="button"
              onClick={chat.recheck}
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
      {status?.available && (
        <ChatSuggestions
          status={status}
          live={live}
          disabled={pending}
          onAsk={chat.ask}
        />
      )}
      <div className="chat-log" aria-live="polite">
        {messages.map((message, index) => (
          <ChatMessageView
            key={`${index}-${message.role}`}
            entry={message}
            sourceIds={sources}
            onOpenSource={onOpenSource}
            compact={compact}
          />
        ))}
        {pending && (
          <div className="chat-pending" role="status">
            <LoaderCircle size={15} className="chat-spinner" /> Reading the
            cited records…
          </div>
        )}
        {failure && (
          <ChatFailureNotice
            failure={failure}
            pending={pending}
            onRetry={chat.retry}
          />
        )}
      </div>
    </div>
  );
}

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
  const chat = useCaseChat(caseId);
  return (
    <section className="chat-panel" aria-label="Ask about this case">
      <header className="chat-panel-heading">
        <h1>Ask about this case</h1>
        {chat.status?.available && (
          <span className="chat-connection">
            {chat.live ? "Live answers" : "Recorded answers only"}
          </span>
        )}
      </header>
      <ChatThread
        chat={chat}
        sourceIds={sourceIds}
        onOpenSource={onOpenSource}
      />
      <ChatComposer
        inputId="case-chat-input"
        live={chat.live}
        available={chat.status?.available === true}
        pending={chat.pending}
        onAsk={chat.ask}
        onCancel={chat.cancel}
      />
    </section>
  );
}
