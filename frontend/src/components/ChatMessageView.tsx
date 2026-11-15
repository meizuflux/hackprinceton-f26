import {
  Activity,
  ArrowUpRight,
  FileText,
  ListChecks,
  LoaderCircle,
  Scale,
  Search,
  Sparkles,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  citationLabel,
  type ChatCitation,
  type ChatStep,
  type EvidenceStatus,
} from "../api/chat";
import {
  countWords,
  planPlayback,
  playbackAt,
  revealSegments,
  stepLabel,
  summarizeSteps,
} from "./chat-playback";
import type { ChatEntry } from "./useCaseChat";

const toolIcons: Record<string, LucideIcon> = {
  search_records: Search,
  get_record: FileText,
  list_open_questions: ListChecks,
  list_explanations: Scale,
  list_ml_signals: Activity,
};

const played = new WeakSet<object>();

function reducedMotion() {
  return (
    typeof window !== "undefined" &&
    !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );
}

/** Plays a just-arrived answer: steps one by one, then typed text, then citations. Older entries render at once. */
function useAnswerPlayback(entry: ChatEntry, segments: string[]) {
  const wanted = !!entry.animate && !played.has(entry) && !reducedMotion();
  const plan = useMemo(
    () => planPlayback(entry.steps ?? [], countWords(segments)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [entry],
  );
  const [skipped, setSkipped] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const finished = !wanted || skipped || elapsed >= plan.stepsMs + plan.typeMs;
  const start = useRef(0);
  useEffect(() => {
    if (finished) {
      played.add(entry);
      return;
    }
    start.current = performance.now() - elapsed;
    const id = window.setInterval(
      () => setElapsed(performance.now() - start.current),
      40,
    );
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finished]);
  const state = finished
    ? ({ phase: "done", stepsShown: plan.starts.length, typed: 1 } as const)
    : playbackAt(plan, elapsed);
  return { ...state, skip: () => setSkipped(true) };
}

function StepRow({ step, active }: { step: ChatStep; active: boolean }) {
  const { title, detail } = stepLabel(step);
  const Icon =
    step.type === "model_call" ? Sparkles : (toolIcons[step.tool] ?? Wrench);
  return (
    <li className={`chat-step is-${step.type} ${active ? "is-active" : ""}`}>
      {active ? (
        <LoaderCircle size={13} className="chat-spinner" aria-hidden="true" />
      ) : (
        <Icon size={13} aria-hidden="true" />
      )}
      <span className="chat-step-title">{title}</span>
      {detail && <span className="chat-step-detail">{detail}</span>}
    </li>
  );
}

const statusLabel: Record<EvidenceStatus, string> = {
  supported: "Supported by cited records",
  partial: "Partly supported",
  insufficient: "Insufficient evidence",
};

export function EvidenceStatusBadge({ status }: { status: EvidenceStatus }) {
  return (
    <span className={`chat-evidence-status status-${status}`}>
      <i aria-hidden="true" />
      {statusLabel[status]}
    </span>
  );
}

export function CitationChip({
  citation,
  canOpen,
  onOpenSource,
}: {
  citation: ChatCitation;
  canOpen: boolean;
  onOpenSource: (sourceId: string) => void;
}) {
  const label = citationLabel(citation);
  if (canOpen && citation.source_id) {
    const sourceId = citation.source_id;
    return (
      <button
        type="button"
        className="chat-cite"
        title={citation.excerpt}
        aria-label={`Open source ${label}`}
        onClick={() => onOpenSource(sourceId)}
      >
        {label}
        <ArrowUpRight size={11} aria-hidden="true" />
      </button>
    );
  }
  return (
    <span
      className="chat-cite is-static"
      title={`${citation.excerpt}\n(Not on the board, so it cannot be opened here.)`}
    >
      {label}
    </span>
  );
}

function AssistantMessage({
  entry,
  sourceIds,
  onOpenSource,
  compact,
  onPlaying,
}: {
  entry: ChatEntry;
  sourceIds: ReadonlySet<string>;
  onOpenSource: (sourceId: string) => void;
  compact: boolean;
  onPlaying?: (playing: boolean) => void;
}) {
  const citations = entry.citations ?? [];
  const chip = (index: number) => {
    const citation = citations[index];
    return citation ? (
      <CitationChip
        key={index}
        citation={citation}
        canOpen={!!citation.source_id && sourceIds.has(citation.source_id)}
        onOpenSource={onOpenSource}
      />
    ) : null;
  };
  const structured =
    entry.observations !== undefined || entry.summary !== undefined;
  const obs = entry.observations ?? [];
  const unknowns = entry.unknowns ?? [];
  const segments = structured
    ? [
        entry.summary ?? "",
        ...obs.map((o) => o.text),
        entry.inference ?? "",
        ...unknowns,
      ]
    : [entry.content];
  const playback = useAnswerPlayback(entry, segments);
  const done = playback.phase === "done";
  // Lets the thread hold new questions until this answer has finished playing.
  useEffect(() => {
    onPlaying?.(!done);
    return () => onPlaying?.(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [done]);
  const steps = entry.steps ?? [];
  const words = done
    ? Infinity
    : Math.floor(playback.typed * countWords(segments));
  const shown = revealSegments(segments, words);
  const at = (i: number) => shown[i] ?? "";
  const obsBase = 1;
  const infBase = obsBase + obs.length;
  const unkBase = infBase + 1;
  return (
    <article className="chat-message chat-assistant">
      <header className="chat-message-meta">
        <h3>Case assistant</h3>
        {entry.replayed !== undefined && (
          <span className="chat-origin">
            {entry.replayed ? "Replayed from a recorded run" : "Live"}
          </span>
        )}
        {!done && (
          <button type="button" className="chat-skip" onClick={playback.skip}>
            Skip
          </button>
        )}
      </header>
      {steps.length > 0 &&
        (done ? (
          <details className="chat-steps">
            <summary>{summarizeSteps(steps, entry.replayed)}</summary>
            <ol>
              {steps.map((step, i) => (
                <StepRow key={i} step={step} active={false} />
              ))}
            </ol>
          </details>
        ) : (
          <ol className="chat-steps is-playing" aria-label="Working">
            {steps.slice(0, playback.stepsShown).map((step, i, all) => (
              <StepRow
                key={i}
                step={step}
                active={playback.phase === "steps" && i === all.length - 1}
              />
            ))}
          </ol>
        ))}
      {done && entry.evidence_status && (
        <EvidenceStatusBadge status={entry.evidence_status} />
      )}
      {playback.phase === "steps" ? null : structured ? (
        <>
          {at(0) && <p className="chat-summary">{at(0)}</p>}
          {obs.length > 0 && at(obsBase) && (
            <section className="chat-section">
              <h4>Observed in the records</h4>
              <ul>
                {obs.map(
                  (o, i) =>
                    at(obsBase + i) && (
                      <li key={i}>
                        <span>{at(obsBase + i)}</span>
                        {done && (
                          <span className="chat-cites">
                            {o.citations.map(chip)}
                          </span>
                        )}
                      </li>
                    ),
                )}
              </ul>
            </section>
          )}
          {at(infBase) && (
            <section className="chat-section chat-inference">
              <h4>Inference, not established by the records</h4>
              <p>{at(infBase)}</p>
            </section>
          )}
          {unknowns.length > 0 && at(unkBase) && (
            <section className="chat-section">
              <h4>Not shown by the records</h4>
              <ul>
                {unknowns.map(
                  (_, i) =>
                    at(unkBase + i) && <li key={i}>{at(unkBase + i)}</li>,
                )}
              </ul>
            </section>
          )}
        </>
      ) : (
        <p className="chat-plain">{at(0)}</p>
      )}
      {done && !structured && citations.length > 0 && (
        <div className="chat-cites">{citations.map((_, i) => chip(i))}</div>
      )}
      {done && !compact && citations.length > 0 && (
        // Collapsed: each observation already carries its citation chips; the full excerpts are one click away.
        <details className="chat-section chat-excerpts">
          <summary>
            Cited excerpts <span>({citations.length})</span>
          </summary>
          {citations.map((citation, i) => (
            <figure key={i}>
              <figcaption>{chip(i)}</figcaption>
              <blockquote>{citation.excerpt}</blockquote>
            </figure>
          ))}
        </details>
      )}
    </article>
  );
}

/** One chat turn. `compact` (the board widget) shows citation chips only; the page also lists excerpts. */
export function ChatMessageView({
  entry,
  sourceIds,
  onOpenSource,
  compact = false,
  onPlaying,
}: {
  entry: ChatEntry;
  sourceIds: ReadonlySet<string>;
  onOpenSource: (sourceId: string) => void;
  compact?: boolean;
  /** Reported by an answer while its steps and text are still playing. */
  onPlaying?: (playing: boolean) => void;
}) {
  if (entry.role === "user") {
    return (
      <article className="chat-message chat-user">
        <h3 className="sr-only">You asked</h3>
        <p>{entry.content}</p>
      </article>
    );
  }
  return (
    <AssistantMessage
      entry={entry}
      sourceIds={sourceIds}
      onOpenSource={onOpenSource}
      compact={compact}
      onPlaying={onPlaying}
    />
  );
}
