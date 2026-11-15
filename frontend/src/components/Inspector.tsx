import { OriginIcon } from "./OriginBadge";
import { originLabel } from "./board-colors";
import {
  ArrowLeft,
  ArrowUpRight,
  ChevronDown,
  GitBranch,
  X,
} from "lucide-react";
import { useEffect, useRef } from "react";
import { isMock } from "../api/client";
import type { CaseData } from "../api/types";
import { MediaInspector, mediaNodeFor } from "./MediaInspector";
import { relationshipLabel } from "./relationships";
import {
  formatCaseTime,
  insightKind,
  insightStrength,
  scoreLabel,
} from "./presentation";

export type Selection = {
  kind: "node" | "edge" | "gap" | "insight" | "suggestion" | "source";
  id: string;
  sourceId?: string;
};

type InspectorProps = {
  selection: Selection | null;
  data: CaseData;
  onClose: () => void;
  onSelect: (selection: Selection) => void;
  backLabel?: string;
  onOpenSource?: (sourceId: string) => void;
  onFocusOnBoard?: (selection: Selection) => void;
};

/** Method name an ML signal reports, when the item is (or is keyed like) one. */
function methodFor(item: unknown): string | undefined {
  const method = (item as { method?: { name?: string } }).method;
  return method?.name;
}

export function Inspector({
  selection,
  data,
  onClose,
  onSelect,
  backLabel = "Back to review",
  onOpenSource,
  onFocusOnBoard,
}: InspectorProps) {
  const panelRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (selection) panelRef.current?.focus();
  }, [selection?.id, selection?.kind]);
  useEffect(() => {
    if (!selection) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (
        event.key === "Escape" &&
        !document.querySelector('[aria-modal="true"]')
      )
        onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose, !!selection]);

  if (!selection) return null;

  const item = (() => {
    switch (selection.kind) {
      case "node":
        return data.nodes.find((entry) => entry.id === selection.id);
      case "edge":
        return data.edges.find((entry) => entry.id === selection.id);
      case "gap":
        return data.gaps.find((entry) => entry.id === selection.id);
      case "insight":
        return data.insights.find((entry) => entry.id === selection.id);
      case "suggestion":
        return data.suggestions.find((entry) => entry.id === selection.id);
      case "source": {
        const source = data.sources.find((entry) => entry.id === selection.id);
        return source
          ? {
              ...source,
              title: source.path,
              description: source.kind,
              citations: [source.id],
            }
          : undefined;
      }
    }
  })();
  if (!item) return null;

  const mediaNode = mediaNodeFor(data.nodes, selection);
  const citations = item.citations;
  const sources = citations
    .map((id) => data.sources.find((source) => source.id === id))
    .filter((source): source is CaseData["sources"][number] => Boolean(source))
    .sort(
      (a, b) =>
        Number(b.id === selection.sourceId) -
        Number(a.id === selection.sourceId),
    );
  const title = "label" in item ? item.label : item.title;
  const score = "score" in item ? item.score : undefined;
  const edge =
    selection.kind === "edge" ? (item as CaseData["edges"][number]) : undefined;
  const connector = edge?.directed ? " → " : " — ";
  const description = edge
    ? [
        data.nodes.find((entry) => entry.id === edge.source)?.label ??
          edge.source,
        edge.label,
        data.nodes.find((entry) => entry.id === edge.target)?.label ??
          edge.target,
      ].join(connector)
    : "summary" in item
      ? item.summary
      : "description" in item
        ? item.description
        : "text" in item
          ? item.text
          : item.type;
  const gap =
    selection.kind === "gap" ? (item as CaseData["gaps"][number]) : undefined;
  const suggestion =
    selection.kind === "suggestion"
      ? (item as CaseData["suggestions"][number])
      : undefined;
  const node =
    selection.kind === "node" ? (item as CaseData["nodes"][number]) : undefined;
  const linkedGap = node?.gapId
    ? data.gaps.find((entry) => entry.id === node.gapId)
    : undefined;
  const linkedSuggestions = gap
    ? data.suggestions.filter(
        (entry) => entry.gapId === gap.id || entry.gapIds?.includes(gap.id),
      )
    : [];
  const insight =
    selection.kind === "insight"
      ? (item as CaseData["insights"][number])
      : undefined;
  const structuredInsight = Boolean(insight?.observations?.length);
  const suggestionGaps = suggestion
    ? data.gaps.filter(
        (entry) =>
          entry.id === suggestion.gapId ||
          suggestion.gapIds?.includes(entry.id),
      )
    : [];
  const producedOrigin = (item as { origin?: import("../api/types").Origin })
    .origin;
  const producedBy = originLabel(
    producedOrigin,
    (item as { stage?: string }).stage,
    methodFor(item),
  );
  const citeButtons = (citations: string[]) =>
    citations.length > 0 && (
      <span className="cite-list">
        {citations.map((id) => (
          <button
            key={id}
            type="button"
            className="cite-chip"
            onClick={() =>
              onOpenSource ? onOpenSource(id) : onSelect({ kind: "source", id })
            }
            title={`Open source ${id}`}
          >
            {id}
          </button>
        ))}
      </span>
    );

  const claimName = (claim: string) => {
    const referencedNode = data.nodes.find((entry) => entry.id === claim);
    const referencedInsight = data.insights.find((entry) => entry.id === claim);
    return referencedNode?.label ?? referencedInsight?.title ?? claim;
  };

  return (
    <aside
      className="inspector"
      ref={panelRef}
      tabIndex={-1}
      aria-label={`${selection.kind} details`}
    >
      <header className="inspector-head">
        <div>
          <button className="text-button inspector-back" onClick={onClose}>
            <ArrowLeft size={14} /> {backLabel}
          </button>
          <h2>{title}</h2>
        </div>
        <button
          className="icon-button"
          type="button"
          onClick={onClose}
          aria-label="Close inspector"
        >
          <X size={18} aria-hidden="true" />
        </button>
      </header>

      <div className="inspector-body">
        <div className="inspector-tags">
          <span className={`kind-badge kind-${selection.kind}`}>
            {selection.kind === "gap"
              ? "Question to verify"
              : selection.kind === "insight"
                ? insightKind(item as CaseData["insights"][number])
                : selection.kind === "suggestion"
                  ? "Suggested next step"
                  : selection.kind === "node"
                    ? "Evidence record"
                    : selection.kind === "edge"
                      ? relationshipLabel(edge!.type, edge!.certainty)
                      : "Source excerpt"}
          </span>
          {score !== undefined && (
            <span className="detail-score">
              {selection.kind === "insight"
                ? insightStrength(item as CaseData["insights"][number])
                : scoreLabel(
                    score,
                    selection.kind === "gap" ? "rank" : "percent",
                  )}
            </span>
          )}
          {gap?.gapType && (
            <span className="detail-score">
              {humanize(gap.gapType)} · {humanize(gap.status ?? "open")}
            </span>
          )}
          {onFocusOnBoard && (
            <button
              type="button"
              className="focus-board-button"
              onClick={() => onFocusOnBoard(selection)}
              aria-label={`Locate ${title} on mind map`}
            >
              <GitBranch size={13} aria-hidden="true" /> Locate on mind map
            </button>
          )}
        </div>
        {producedBy && (
          <p className="inspector-provenance">
            <OriginIcon origin={producedOrigin} size={13} />
            <span>
              <strong>Produced by</strong> {producedBy}
            </span>
          </p>
        )}
        {mediaNode && (
          <MediaInspector
            node={mediaNode}
            caseId={data.id}
            timeZone={data.timezone}
          />
        )}
        {gap?.whyItMatters ? (
          <p className="inspector-description">{gap.whyItMatters}</p>
        ) : structuredInsight ? null : (
          <p className="inspector-description">{description}</p>
        )}

        {gap?.missing && (
          <section className="inspector-section inspector-structured">
            <h3>What is missing</h3>
            <p>{gap.missing}</p>
            {gap.direction && (
              <>
                <h3>How to close it</h3>
                <p>{gap.direction}</p>
              </>
            )}
            {gap.answer && (
              <>
                <h3>Partial answer</h3>
                <p>{gap.answer}</p>
              </>
            )}
          </section>
        )}

        {insight && structuredInsight && (
          <section className="inspector-section inspector-structured">
            <h3>Observed in the evidence</h3>
            <ul>
              {insight.observations!.map((observation) => (
                <li key={observation.text}>
                  {observation.text} {citeButtons(observation.citations)}
                </li>
              ))}
            </ul>
            {insight.inference && (
              <>
                <h3>Inference (not proof)</h3>
                <p>{insight.inference}</p>
              </>
            )}
            {(
              [
                ["Unknowns", insight.unknowns],
                ["Counter-evidence", insight.counterevidence],
                ["Assumptions", insight.assumptions],
                ["Limitations", insight.limitations],
              ] as const
            ).map(([heading, entries]) =>
              entries?.length ? (
                <div key={heading}>
                  <h3>{heading}</h3>
                  <ul>
                    {entries.map((entry) => (
                      <li key={entry}>{entry}</li>
                    ))}
                  </ul>
                </div>
              ) : null,
            )}
          </section>
        )}

        {edge?.basis && (
          <section className="inspector-section inspector-structured">
            <h3>Why this thread is drawn</h3>
            <p>{edge.basis}</p>
          </section>
        )}

        <section className="inspector-section sources-section">
          <h3>
            Original sources <span>({sources.length})</span>
          </h3>
          {sources.length ? (
            sources.map((source) => (
              <details
                className="source-item"
                key={source.id}
                open={sources[0]?.id === source.id}
              >
                <summary>
                  <span>
                    <strong>{source.path}</strong>
                    <small>{source.kind}</small>
                  </span>
                  <ChevronDown size={16} aria-hidden="true" />
                </summary>
                <div className="source-meta">
                  <blockquote>{source.excerpt}</blockquote>
                  {onOpenSource && (
                    <button
                      className="text-button open-raw-button"
                      type="button"
                      onClick={() => onOpenSource(source.id)}
                    >
                      Open in raw evidence <ArrowUpRight size={14} />
                    </button>
                  )}
                  <p>
                    <strong>Recorded:</strong>{" "}
                    {formatCaseTime(source.timestamp, data.timezone, "full")}
                  </p>
                  <p>
                    <strong>
                      {isMock ? "Placeholder hash:" : "File SHA-256:"}
                    </strong>{" "}
                    <code>{source.hash}</code>
                  </p>
                  {Object.keys(source.metadata).length > 0 && (
                    <dl>
                      {Object.entries(source.metadata).map(([key, value]) => (
                        <div key={key}>
                          <dt>{key}</dt>
                          <dd>{value}</dd>
                        </div>
                      ))}
                    </dl>
                  )}
                </div>
              </details>
            ))
          ) : (
            <p className="muted">No source citations attached.</p>
          )}
        </section>

        {gap && (
          <section className="inspector-section">
            <h3>Claims affected</h3>
            {gap.affectedClaims.length ? (
              <ul>
                {gap.affectedClaims.map((claim) => (
                  <li key={claim}>{claimName(claim)}</li>
                ))}
              </ul>
            ) : (
              <p>No claims listed.</p>
            )}
            <h3>Recommended evidence</h3>
            {gap.suggestedEvidence.length ? (
              <ul>
                {/* A gap can request the same kind of evidence for several people; list each kind once. */}
                {[...new Set(gap.suggestedEvidence)].map((evidence) => (
                  <li key={evidence}>
                    {data.suggestions.find((s) => s.id === evidence)?.title ??
                      humanize(evidence)}
                  </li>
                ))}
              </ul>
            ) : (
              <p>No evidence suggestions listed.</p>
            )}
            {linkedSuggestions.length > 0 && (
              <>
                <h3>Suggested searches</h3>
                <ul className="linked-suggestions">
                  {linkedSuggestions.map((entry) => (
                    <li key={entry.id}>
                      <button
                        className="text-button"
                        type="button"
                        onClick={() =>
                          onSelect({ kind: "suggestion", id: entry.id })
                        }
                      >
                        {entry.title}
                      </button>
                      <p>{entry.query}</p>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </section>
        )}

        {linkedGap && (
          <section className="inspector-section linked-gap">
            <h3>Related evidence gap</h3>
            <button
              className="text-button"
              type="button"
              onClick={() => onSelect({ kind: "gap", id: linkedGap.id })}
            >
              Inspect linked evidence gap: {linkedGap.title}
            </button>
            <p>{linkedGap.description}</p>
          </section>
        )}

        {suggestion && (
          <section className="inspector-section">
            <h3>Example search</h3>
            <blockquote className="query-block">{suggestion.query}</blockquote>
            {suggestion.description && !isMock && (
              <>
                <h3>Why it ranks here</h3>
                <p>{suggestion.description}</p>
              </>
            )}
            {suggestionGaps.length > 0 && (
              <>
                <h3>Addresses</h3>
                <ul className="linked-suggestions">
                  {suggestionGaps.map((entry) => (
                    <li key={entry.id}>
                      <button
                        className="text-button"
                        type="button"
                        onClick={() => onSelect({ kind: "gap", id: entry.id })}
                      >
                        {entry.title}
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </section>
        )}
      </div>
    </aside>
  );
}

/** `failed_extraction` → `Failed extraction`. */
function humanize(value: string) {
  const text = value.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}
