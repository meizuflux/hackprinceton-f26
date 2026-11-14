import { ArrowLeft, ChevronDown, X } from "lucide-react";
import { useEffect, useRef } from "react";
import type { CaseData } from "../api/types";

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
};

export function Inspector({
  selection,
  data,
  onClose,
  onSelect,
  backLabel = "Back to review",
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
  const description =
    "summary" in item
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
    ? data.suggestions.filter((entry) => entry.gapId === gap.id)
    : [];

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
                ? "Inference"
                : selection.kind === "suggestion"
                  ? "Suggested next step"
                  : selection.kind === "node"
                    ? "Evidence record"
                    : selection.kind === "edge"
                      ? "Relationship"
                      : "Source excerpt"}
          </span>
          {score !== undefined && (
            <span className="detail-score">
              Illustrative score · {Math.round(score * 100)}%
            </span>
          )}
          {selection.kind === "edge" && "type" in item && (
            <span className="kind-badge">{item.type}</span>
          )}
        </div>
        <p className="inspector-description">{description}</p>

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
                  <p>
                    <strong>Recorded:</strong> {source.timestamp}
                  </p>
                  <p>
                    <strong>Placeholder hash:</strong>{" "}
                    <code>{source.hash}</code>
                  </p>
                  <blockquote>{source.excerpt}</blockquote>
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
                {gap.suggestedEvidence.map((evidence) => (
                  <li key={evidence}>
                    {data.suggestions.find((s) => s.id === evidence)?.title ??
                      evidence}
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
            {suggestion.gapId && (
              <p>
                Addresses gap:{" "}
                {data.gaps.find((g) => g.id === suggestion.gapId)?.title ??
                  suggestion.gapId}
              </p>
            )}
          </section>
        )}
      </div>

      <footer className="inspector-footer">
        <strong>Fictional case material</strong>
        <span>
          Source excerpts are fictional. Scores are illustrative. Inferences
          require verification; a gap is not proof.
        </span>
      </footer>
    </aside>
  );
}
