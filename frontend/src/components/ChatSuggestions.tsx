import { KeyRound, RotateCw } from "lucide-react";
import type { ChatStatus } from "../api/chat";
import type { ChatFailure } from "./useCaseChat";

/** Suggested questions: recorded answers replay without a model call; others need a live (billed) call. */
export function ChatSuggestions({
  status,
  live,
  disabled,
  onAsk,
}: {
  status: ChatStatus;
  live: boolean;
  disabled: boolean;
  onAsk: (question: string) => void;
}) {
  const suggestions = status.suggestions ?? [];
  if (!suggestions.length) return null;
  const anyRecorded = suggestions.some((s) => s.recorded);
  return (
    <div className="chat-suggestions">
      <h3 id="chat-suggestions-heading">Suggested questions</h3>
      {!live && !anyRecorded && (
        <p className="chat-hint">
          <KeyRound size={13} aria-hidden="true" />
          Answers to these questions have not been recorded, and live questions
          need an Anthropic API key on the server.
        </p>
      )}
      <ul aria-labelledby="chat-suggestions-heading">
        {suggestions.map((s) => {
          const usable = s.recorded || live;
          return (
            <li key={s.question}>
              <button
                type="button"
                className={`chat-suggestion ${s.recorded ? "is-recorded" : ""}`}
                disabled={disabled || !usable}
                onClick={() => onAsk(s.question)}
              >
                <span>{s.question}</span>
                <small>
                  {s.recorded
                    ? "Recorded answer · no model call"
                    : live
                      ? "Live model call"
                      : "Not recorded yet"}
                </small>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function ChatFailureNotice({
  failure,
  pending,
  onRetry,
}: {
  failure: ChatFailure;
  pending: boolean;
  onRetry: () => void;
}) {
  if (failure.code === "needs_api_key") {
    return (
      <div className="chat-notice" role="status">
        <KeyRound size={14} aria-hidden="true" />
        <p>
          <strong>Needs an API key.</strong> This answer has not been recorded,
          and live questions need an Anthropic API key on the server. Try a
          recorded suggested question instead.
        </p>
      </div>
    );
  }
  return (
    <div className="chat-error" role="alert">
      <span>{failure.message}</span>
      <button type="button" onClick={onRetry} disabled={pending}>
        <RotateCw size={14} aria-hidden="true" /> Retry
      </button>
    </div>
  );
}
