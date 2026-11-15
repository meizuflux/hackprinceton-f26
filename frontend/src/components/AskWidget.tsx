import { ArrowUp, MessageSquareText } from "lucide-react";
import { useState } from "react";
import { queueQuestion } from "./chat-handoff";
import { useCaseChat } from "./useCaseChat";
import "./chat-panel.css";
import "./ask-widget.css";

/** Queues the question for the chat tab and asks the host to open it. Returns whether it was submitted. */
export function submitToChat(
  caseId: string,
  text: string,
  available: boolean,
  onAsk: () => void,
) {
  const question = text.trim();
  if (!question || !available) return false;
  queueQuestion(caseId, question);
  onAsk();
  return true;
}

/**
 * Small "Ask a question" box on the mind map. It renders no answers: submitting opens the chat tab, which asks the
 * question and plays the answer there. Sits above the minimap and zoom controls, clear of the legend.
 */
export function AskWidget({
  caseId,
  onAsk,
}: {
  caseId: string;
  /** Called after the question is queued; the host navigates to the chat tab. */
  onAsk: () => void;
}) {
  const chat = useCaseChat(caseId);
  const [draft, setDraft] = useState("");
  const available = chat.status?.available === true;
  const recorded = (chat.status?.suggestions ?? []).filter(
    (s) => s.recorded || chat.live,
  );

  const submit = (text: string) => {
    if (submitToChat(caseId, text, available, onAsk)) setDraft("");
  };

  return (
    <form
      className="ask-widget"
      aria-label="Ask a question"
      onSubmit={(event) => {
        event.preventDefault();
        if (chat.live) submit(draft);
      }}
    >
      {available && recorded.length > 0 && (
        <ul className="ask-chips" aria-label="Suggested questions">
          {recorded.slice(0, 3).map((s) => (
            <li key={s.question}>
              <button
                type="button"
                className="ask-chip"
                title={s.question}
                onClick={() => submit(s.question)}
              >
                {s.question}
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="ask-box">
        <MessageSquareText size={16} aria-hidden="true" />
        <label className="sr-only" htmlFor="ask-widget-input">
          Ask a question
        </label>
        <input
          id="ask-widget-input"
          value={draft}
          maxLength={1000}
          onChange={(event) => setDraft(event.target.value)}
          disabled={!available || !chat.live}
          placeholder={
            !available
              ? "Chat is unavailable"
              : chat.live
                ? "Ask about the evidence…"
                : "Pick a recorded question"
          }
        />
        <button
          type="submit"
          className="ask-send"
          aria-label="Send question"
          disabled={!draft.trim() || !available || !chat.live}
        >
          <ArrowUp size={15} />
        </button>
      </div>
    </form>
  );
}
