import { LoaderCircle, MessageSquare, RotateCw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
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
  busy = false,
  onPlaying,
}: {
  chat: CaseChat;
  sourceIds: readonly string[];
  onOpenSource: (sourceId: string) => void;
  compact?: boolean;
  /** A request is out or an answer is still playing: suggestions wait. */
  busy?: boolean;
  onPlaying?: (playing: boolean) => void;
}) {
  const { status, messages, pending, failure, live } = chat;
  const scrollRef = useRef<HTMLDivElement>(null);
  const sources = useMemo(() => new Set(sourceIds), [sourceIds]);

  // A new question scrolls to the top of the view as soon as it is asked, so its answer plays out below it and the
  // reader never lands mid-way through the previous reply. Later growth (steps, typing) does not move the view.
  // A spacer below the conversation gives the latest question room to reach the top before its answer exists; it
  // shrinks as the answer grows, so a finished conversation ends without blank space.
  const spacerRef = useRef<HTMLDivElement>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const fitSpacer = () => {
    const scroller = scrollRef.current;
    const spacer = spacerRef.current;
    const log = logRef.current;
    if (!scroller || !spacer || !log) return;
    const questions = log.querySelectorAll<HTMLElement>(".chat-user");
    const last = questions[questions.length - 1];
    if (!last) {
      spacer.style.height = "0px";
      return;
    }
    const below =
      log.getBoundingClientRect().bottom - last.getBoundingClientRect().top;
    spacer.style.height = `${Math.max(0, scroller.clientHeight - below - 40)}px`;
  };
  useEffect(() => {
    const log = logRef.current;
    if (!log || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(fitSpacer);
    observer.observe(log);
    return () => observer.disconnect();
  }, []);
  const asked = messages.filter((m) => m.role === "user").length;
  useEffect(() => {
    const scroller = scrollRef.current;
    if (!scroller || !asked) return;
    const questions = scroller.querySelectorAll<HTMLElement>(".chat-user");
    const last = questions[questions.length - 1];
    if (!last) return;
    fitSpacer();
    scroller.scrollTo({
      top:
        scroller.scrollTop +
        last.getBoundingClientRect().top -
        scroller.getBoundingClientRect().top -
        12,
      behavior: "smooth",
    });
  }, [asked]);
  useEffect(() => {
    // Errors and notices appear at the end; keep them in view.
    const scroller = scrollRef.current;
    if (scroller && failure) scroller.scrollTop = scroller.scrollHeight;
  }, [failure]);

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
      {status?.available && messages.length === 0 && (
        <ChatSuggestions
          status={status}
          live={live}
          disabled={busy}
          onAsk={chat.ask}
        />
      )}
      <div className="chat-log" aria-live="polite" ref={logRef}>
        {messages.map((message, index) => (
          <ChatMessageView
            key={`${index}-${message.role}`}
            entry={message}
            sourceIds={sources}
            onOpenSource={onOpenSource}
            compact={compact}
            onPlaying={onPlaying}
          />
        ))}
        {pending && (
          <div className="chat-pending" role="status">
            <LoaderCircle size={15} className="chat-spinner" /> Thinking…
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
      <div className="chat-spacer" ref={spacerRef} aria-hidden="true" />
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
  const chat = useCaseChat(caseId, { takeQueued: true });
  // New questions wait until the current answer has finished playing, so two answers never animate at once.
  const [playing, setPlaying] = useState(false);
  const busy = chat.pending || playing;
  const asked = chat.messages
    .filter((m) => m.role === "user")
    .map((m) => m.content);
  return (
    <section className="chat-panel" aria-label="Ask about this case">
      <header className="chat-panel-heading">
        <MessageSquare size={18} aria-hidden="true" />
        <h2>Ask about this case</h2>
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
        busy={busy}
        onPlaying={setPlaying}
      />
      {chat.status?.available && chat.messages.length > 0 && (
        <ChatSuggestions
          status={chat.status}
          live={chat.live}
          disabled={busy}
          onAsk={chat.ask}
          compact
          asked={asked}
        />
      )}
      <ChatComposer
        inputId="case-chat-input"
        live={chat.live}
        available={chat.status?.available === true}
        pending={chat.pending}
        holding={playing}
        onAsk={chat.ask}
        onCancel={chat.cancel}
      />
    </section>
  );
}
