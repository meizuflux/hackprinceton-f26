import { MessageSquareText, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ChatComposer } from "./ChatComposer";
import { ChatThread } from "./ChatPanel";
import { useCaseChat } from "./useCaseChat";
import "./chat-panel.css";
import "./ask-widget.css";

/** Floating "Ask" pill on the mind map. Sits above the minimap (or in the corner without one), clear of the zoom controls and the key. */
export function AskWidget({
  caseId,
  sourceIds,
  onOpenSource,
}: {
  caseId: string;
  sourceIds: readonly string[];
  onOpenSource: (sourceId: string) => void;
}) {
  const chat = useCaseChat(caseId);
  const [open, setOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const wasOpen = useRef(false);

  useEffect(() => {
    if (open) {
      const panel = panelRef.current;
      const target =
        panel?.querySelector<HTMLElement>(
          ".chat-suggestion:not(:disabled), textarea:not(:disabled)",
        ) ?? panel;
      target?.focus();
    } else if (wasOpen.current) {
      toggleRef.current?.focus();
    }
    wasOpen.current = open;
  }, [open]);

  const recorded = chat.status?.suggestions?.filter((s) => s.recorded).length;

  return (
    <div
      className={`ask-widget ${open ? "is-open" : ""}`}
      onKeyDown={(event) => {
        // Escape closes the widget only; it must not also close the inspector.
        if (event.key === "Escape" && open) {
          event.stopPropagation();
          setOpen(false);
        }
      }}
    >
      <section
        ref={panelRef}
        id="ask-widget-panel"
        className="ask-panel"
        role="dialog"
        aria-modal="false"
        aria-labelledby="ask-widget-title"
        tabIndex={-1}
        hidden={!open}
      >
        <header className="ask-panel-head">
          <h2 id="ask-widget-title">Ask a question</h2>
          {chat.status?.available && (
            <span className={`ask-mode ${chat.live ? "is-live" : ""}`}>
              {chat.live ? "Live" : "Recorded only"}
            </span>
          )}
          <button
            type="button"
            className="icon-button"
            aria-label="Close questions"
            onClick={() => setOpen(false)}
          >
            <X size={16} />
          </button>
        </header>
        <ChatThread
          chat={chat}
          sourceIds={sourceIds}
          onOpenSource={onOpenSource}
          compact
        />
        <ChatComposer
          inputId="ask-widget-input"
          inputRef={inputRef}
          live={chat.live}
          available={chat.status?.available === true}
          pending={chat.pending}
          onAsk={chat.ask}
          onCancel={chat.cancel}
        />
      </section>
      <button
        ref={toggleRef}
        type="button"
        className="ask-toggle"
        aria-expanded={open}
        aria-controls="ask-widget-panel"
        aria-label="Ask a question about this case"
        title={
          recorded
            ? `Ask a question (${recorded} recorded answers)`
            : "Ask a question"
        }
        onClick={() => setOpen((value) => !value)}
      >
        <MessageSquareText size={15} aria-hidden="true" />
        <span>Ask</span>
      </button>
    </div>
  );
}
