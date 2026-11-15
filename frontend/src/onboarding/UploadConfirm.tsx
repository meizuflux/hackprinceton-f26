import { LoaderCircle, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export type AnalysisMode = "replay" | "live";

const steps = [
  "Ingestion: every file is hashed and parsed into records.",
  "Deterministic rules: connections, findings, contradictions and gaps.",
  "Traditional ML: clustering and outlier signals.",
  "Claude agent (deepagents): claim extraction, then an investigator that searches the records and records insights.",
];

/** Explains what an upload will run and asks how to run the model stages. */
export function UploadConfirm({
  fileName,
  llmLive,
  busy,
  error,
  onConfirm,
  onCancel,
}: {
  fileName: string;
  /** From `GET /health`; undefined hides the live option. */
  llmLive: boolean;
  busy: boolean;
  error: string;
  onConfirm: (mode: AnalysisMode) => void;
  onCancel: () => void;
}) {
  const [mode, setMode] = useState<AnalysisMode>("replay");
  const dialog = useRef<HTMLElement>(null);

  useEffect(() => {
    const root = dialog.current;
    const focusable = () =>
      Array.from(
        root?.querySelectorAll<HTMLElement>(
          "button:not(:disabled), input:not(:disabled)",
        ) ?? [],
      );
    (root?.querySelector<HTMLElement>("input:checked") ?? root)?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) {
        event.preventDefault();
        event.stopPropagation();
        onCancel();
      }
      if (event.key === "Tab") {
        const items = focusable();
        if (!items.length) return;
        const first = items[0];
        const last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [busy, onCancel]);

  return (
    <div className="modal-backdrop confirm-backdrop">
      <section
        ref={dialog}
        className="upload-modal confirm-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        tabIndex={-1}
      >
        <button
          className="icon-button modal-close"
          disabled={busy}
          onClick={onCancel}
          aria-label="Cancel import"
        >
          <X size={20} />
        </button>
        <h2 id="confirm-title">What will run on {fileName}</h2>
        <ol className="confirm-steps">
          {steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
        <fieldset className="confirm-modes" disabled={busy}>
          <legend>How to run the model stages</legend>
          <label>
            <input
              type="radio"
              name="analysis-mode"
              checked={mode === "replay"}
              onChange={() => setMode("replay")}
            />
            <span>
              Replay recorded analysis
              <small>Free, if this archive was recorded.</small>
            </span>
          </label>
          {llmLive && (
            <label>
              <input
                type="radio"
                name="analysis-mode"
                checked={mode === "live"}
                onChange={() => setMode("live")}
              />
              <span>
                Run live analysis
                <small>
                  Billed, about $1.30 and a few minutes for a Kestrel-sized
                  case. Uses the server API key.
                </small>
              </span>
            </label>
          )}
        </fieldset>
        {error && (
          <p className="error-message" role="alert">
            {error}
          </p>
        )}
        <div className="confirm-actions">
          <button
            type="button"
            className="button button-secondary"
            disabled={busy}
            onClick={onCancel}
          >
            Cancel
          </button>
          <button
            type="button"
            className="button button-primary"
            disabled={busy}
            onClick={() => onConfirm(mode)}
          >
            {busy ? (
              <>
                <LoaderCircle size={16} className="spin" /> Starting
              </>
            ) : mode === "live" ? (
              "Start live analysis"
            ) : (
              "Start import"
            )}
          </button>
        </div>
      </section>
    </div>
  );
}
