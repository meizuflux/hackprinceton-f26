import { ArrowUpRight } from "lucide-react";
import {
  citationLabel,
  type ChatCitation,
  type EvidenceStatus,
} from "../api/chat";
import type { ChatEntry } from "./useCaseChat";

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

/** One chat turn. `compact` (the board widget) shows citation chips only; the page also lists excerpts. */
export function ChatMessageView({
  entry,
  sourceIds,
  onOpenSource,
  compact = false,
}: {
  entry: ChatEntry;
  sourceIds: ReadonlySet<string>;
  onOpenSource: (sourceId: string) => void;
  compact?: boolean;
}) {
  if (entry.role === "user") {
    return (
      <article className="chat-message chat-user">
        <h3 className="sr-only">You asked</h3>
        <p>{entry.content}</p>
      </article>
    );
  }
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
  return (
    <article className="chat-message chat-assistant">
      <header className="chat-message-meta">
        <h3>Case assistant</h3>
        {entry.replayed !== undefined && (
          <span className="chat-origin">
            {entry.replayed
              ? "Recorded answer, no model call"
              : "Live model call"}
          </span>
        )}
      </header>
      {entry.evidence_status && (
        <EvidenceStatusBadge status={entry.evidence_status} />
      )}
      {structured ? (
        <>
          {entry.summary && <p className="chat-summary">{entry.summary}</p>}
          {!!entry.observations?.length && (
            <section className="chat-section">
              <h4>Observed in the records</h4>
              <ul>
                {entry.observations.map((o, i) => (
                  <li key={i}>
                    <span>{o.text}</span>
                    <span className="chat-cites">{o.citations.map(chip)}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {entry.inference && (
            <section className="chat-section chat-inference">
              <h4>Inference, not established by the records</h4>
              <p>{entry.inference}</p>
            </section>
          )}
          {!!entry.unknowns?.length && (
            <section className="chat-section">
              <h4>Not shown by the records</h4>
              <ul>
                {entry.unknowns.map((u, i) => (
                  <li key={i}>{u}</li>
                ))}
              </ul>
            </section>
          )}
        </>
      ) : (
        <p className="chat-plain">{entry.content}</p>
      )}
      {!structured && citations.length > 0 && (
        <div className="chat-cites">{citations.map((_, i) => chip(i))}</div>
      )}
      {!compact && citations.length > 0 && (
        <section className="chat-section chat-excerpts">
          <h4>Cited excerpts</h4>
          {citations.map((citation, i) => (
            <figure key={i}>
              <figcaption>{chip(i)}</figcaption>
              <blockquote>{citation.excerpt}</blockquote>
            </figure>
          ))}
        </section>
      )}
    </article>
  );
}
