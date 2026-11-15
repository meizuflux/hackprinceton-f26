import { ArrowUp } from "lucide-react";
import { type Ref, useState } from "react";

/** Free-typed questions always go to the model live (billed), so they need a server key. */
export function ChatComposer({
  inputId,
  inputRef,
  live,
  available,
  pending,
  onAsk,
  onCancel,
}: {
  inputId: string;
  inputRef?: Ref<HTMLTextAreaElement>;
  live: boolean;
  available: boolean;
  pending: boolean;
  onAsk: (text: string) => boolean;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState("");
  const enabled = available && live;
  const hintId = `${inputId}-hint`;
  return (
    <form
      className="chat-composer-wrap"
      onSubmit={(event) => {
        event.preventDefault();
        if (enabled && onAsk(draft)) setDraft("");
      }}
    >
      <div className="chat-composer">
        <label className="sr-only" htmlFor={inputId}>
          Ask a question
        </label>
        <textarea
          id={inputId}
          ref={inputRef}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={
            !available
              ? "Chat is unavailable"
              : live
                ? "Ask about the evidence…"
                : "Typing needs an API key on the server"
          }
          rows={2}
          maxLength={1000}
          aria-describedby={hintId}
          disabled={!enabled || pending}
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
            onClick={onCancel}
            aria-label="Cancel request"
          >
            Cancel
          </button>
        ) : (
          <button
            type="submit"
            className="chat-send"
            disabled={!draft.trim() || !enabled}
            aria-label="Send question"
          >
            <ArrowUp size={17} />
          </button>
        )}
      </div>
      <p className="chat-footnote" id={hintId}>
        {!available
          ? "No answers are generated until this case is connected to its backend."
          : live
            ? "Typed questions call the model live and are billed per question. Answers cite their source records."
            : "Without a server API key, only recorded answers to suggested questions are available."}
      </p>
    </form>
  );
}
