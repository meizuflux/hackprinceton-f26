import { useEffect, useRef, useState } from "react";
import { Camera, ChevronDown, FileText, HelpCircle } from "lucide-react";
import type { EvidenceEdge, EvidenceNode } from "../api/types";
import {
  CARD_KINDS,
  THREAD_CATEGORIES,
  cardColors,
  cardKind,
  threadCategory,
  threadColors,
  MARKED_ORIGINS,
  originMarks,
  markedOrigin,
} from "./board-colors";
import { relationshipKind } from "./relationships";
import { OriginIcon } from "./OriginBadge";
import { cardIcons } from "./EvidenceNode";

/**
 * Key to the board's color coding; lists only what this case contains.
 * `yield` collapses it while the review dock is open, so the board keeps its
 * visible area; the reader's own choice returns when the dock closes.
 */
export function BoardLegend({
  nodes,
  edges,
  yield: yieldSpace = false,
}: {
  nodes: EvidenceNode[];
  edges: EvidenceEdge[];
  yield?: boolean;
}) {
  const [open, setOpen] = useState(
    () =>
      typeof window === "undefined" ||
      !window.matchMedia("(max-width: 1199px)").matches,
  );
  const openRef = useRef(open);
  useEffect(() => {
    openRef.current = open;
  }, [open]);
  const openBeforeYield = useRef<boolean | null>(null);
  useEffect(() => {
    if (yieldSpace) {
      if (openBeforeYield.current === null)
        openBeforeYield.current = openRef.current;
      setOpen(false);
    } else if (openBeforeYield.current !== null) {
      setOpen(openBeforeYield.current);
      openBeforeYield.current = null;
    }
  }, [yieldSpace]);
  const kinds = new Set(nodes.map((node) => cardKind(node.type)));
  const categories = new Set(edges.map((edge) => threadCategory(edge.type)));
  const relationKinds = new Set(
    edges.map((edge) => relationshipKind(edge.type, edge.certainty)),
  );
  const hasInferredCard = nodes.some((node) => node.certainty === "inferred");
  const origins = new Set(
    [...nodes, ...edges].map((item) => markedOrigin(item.origin)),
  );
  const hasMedia = nodes.some((node) => node.media);
  const hasQuestion = nodes.some((node) => node.gapId);
  return (
    <section
      className="board-legend nopan nodrag nowheel"
      data-open={open}
      aria-label="Board legend"
    >
      <button
        type="button"
        className="board-legend-toggle"
        aria-expanded={open}
        aria-controls="board-legend-body"
        onClick={() => setOpen((value) => !value)}
      >
        Legend
        <ChevronDown size={14} aria-hidden="true" />
      </button>
      <div id="board-legend-body" className="board-legend-body" hidden={!open}>
        <div className="board-legend-row">
          <h3>Cards</h3>
          <ul>
            {[...CARD_KINDS, "other" as const]
              .filter((kind) => kinds.has(kind))
              .map((kind) => {
                const Icon =
                  kind === "other" ? FileText : (cardIcons[kind] ?? FileText);
                return (
                  <li key={kind} className={`kind-${kind}`}>
                    <i className="legend-card" aria-hidden="true">
                      <Icon size={11} strokeWidth={2.4} />
                    </i>
                    {cardColors[kind].label}
                  </li>
                );
              })}
            {hasMedia && (
              <li className="kind-event">
                <i className="legend-media-mark" aria-hidden="true">
                  <Camera size={11} strokeWidth={2.4} />
                </i>
                Photo / CCTV
              </li>
            )}
            {hasInferredCard && (
              <li className="legend-divider kind-other">
                <i className="legend-card is-inferred" aria-hidden="true" />
                Inferred card
              </li>
            )}
            {hasQuestion && (
              <li className={hasInferredCard ? "" : "legend-divider"}>
                <i className="legend-question" aria-hidden="true">
                  <HelpCircle size={11} strokeWidth={2.4} />
                </i>
                Open question
              </li>
            )}
          </ul>
        </div>
        <div className="board-legend-row">
          <h3>Threads</h3>
          <ul>
            {THREAD_CATEGORIES.filter((category) =>
              categories.has(category),
            ).map((category) => (
              <li key={category} className={`thread-${category}`}>
                <i
                  className={`legend-thread ${category === "claim" ? "is-claim" : ""}`}
                  aria-hidden="true"
                />
                {threadColors[category].label}
              </li>
            ))}
            <li className="legend-divider thread-other">
              <i className="legend-thread" aria-hidden="true" />
              Observed
            </li>
            {relationKinds.has("inference") && (
              <li className="thread-other">
                <i className="legend-thread is-inference" aria-hidden="true" />
                Inferred
              </li>
            )}
          </ul>
        </div>
        {MARKED_ORIGINS.some((origin) => origins.has(origin)) && (
          <div className="board-legend-row">
            <h3>Origin</h3>
            <ul>
              {MARKED_ORIGINS.filter((origin) => origins.has(origin)).map(
                (origin) => (
                  <li key={origin} className={`legend-origin origin-${origin}`}>
                    <i className="legend-origin-mark" aria-hidden="true">
                      <OriginIcon origin={origin} size={11} />
                    </i>
                    {originMarks[origin].label}
                  </li>
                ),
              )}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
