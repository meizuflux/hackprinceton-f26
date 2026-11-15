import {
  memo,
  useEffect,
  useRef,
  type CSSProperties,
  type KeyboardEvent,
} from "react";
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import {
  AlertTriangle,
  ArrowUpRight,
  CalendarClock,
  ChevronUp,
  FileText,
  HelpCircle,
  Layers,
  Link2,
  Network,
} from "lucide-react";
import { cardIcons } from "./EvidenceNode";
import { cardKind } from "./board-colors";
import { formatCaseTime } from "./presentation";
import { paperOutline } from "./paper-note";
import "./story-board.css";

export type StoryExcerpt = { id: string; locator: string; text: string };

export type StoryCardData = {
  label: string;
  type: string;
  subtitle?: string;
  summary: string;
  citations: string[];
  time?: string;
  timeZone?: string;
  certainty?: string;
  gapId?: string;
  width: number;
  height: number;
  hero?: boolean;
  expanded?: boolean;
  active?: boolean;
  isFocused?: boolean;
  /** Up to three cited source excerpts, resolved from the case's sources. */
  excerpts: StoryExcerpt[];
  hiddenNeighbours: number;
  /** Offset from which a revealed card animates into place. */
  arriveFrom?: { x: number; y: number };
  onToggle: () => void;
  onCollapse: () => void;
  onInspect: () => void;
  onInspectGap?: () => void;
  onShowConnections: () => void;
};

export type StoryGroupData = {
  title: string;
  rule: string;
  nodeType: string;
  total: number;
  hidden: number;
  width: number;
  height: number;
  isFocused?: boolean;
  matches?: number;
  onToggle: () => void;
};

function Handles() {
  return (
    <>
      {[Position.Top, Position.Right, Position.Bottom, Position.Left].map(
        (side) => (
          <span key={side}>
            <Handle id={`target-${side}`} type="target" position={side} />
            <Handle id={`source-${side}`} type="source" position={side} />
          </span>
        ),
      )}
    </>
  );
}

const arriveStyle = (from?: {
  x: number;
  y: number;
}): CSSProperties | undefined =>
  from
    ? ({
        "--arrive-x": `${from.x}px`,
        "--arrive-y": `${from.y}px`,
      } as CSSProperties)
    : undefined;

/**
 * A compact story card that expands in place. The node keeps its compact
 * footprint, so threads stay put; the expanded paper overlays its neighbours.
 */
export const StoryCardNode = memo(function StoryCardNode({
  id,
  data,
}: NodeProps<Node<StoryCardData>>) {
  const Icon = cardIcons[data.type as keyof typeof cardIcons] || FileText;
  const toggleRef = useRef<HTMLButtonElement>(null);
  const wasExpanded = useRef(data.expanded);
  useEffect(() => {
    // Return focus to the card's button when it collapses from inside.
    if (wasExpanded.current && !data.expanded) {
      const active = document.activeElement;
      if (active && toggleRef.current?.closest(".story-card")?.contains(active))
        toggleRef.current?.focus();
    }
    wasExpanded.current = data.expanded;
  }, [data.expanded]);
  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === "Escape" && data.expanded) {
      event.stopPropagation();
      data.onCollapse();
      toggleRef.current?.focus();
    }
  };
  const sources = `${data.citations.length} source${data.citations.length === 1 ? "" : "s"}`;
  // One line: when it happened, else what it is, else how well it is sourced.
  const meta = data.time
    ? formatCaseTime(data.time, data.timeZone)
    : data.summary && data.summary.slice(0, 24) !== data.label.slice(0, 24)
      ? data.summary
      : sources;
  // A subtitle that only repeats the record type adds nothing.
  const kindNote =
    data.subtitle && data.subtitle.toLowerCase() !== data.type.toLowerCase()
      ? data.subtitle
      : undefined;
  return (
    <div
      className={`story-node ${data.arriveFrom ? "is-arriving" : ""}`}
      style={{
        width: data.width,
        height: data.height,
        ...arriveStyle(data.arriveFrom),
      }}
    >
      <Handles />
      <article
        className={`story-card kind-${cardKind(data.type)} ${data.hero ? "is-hero" : ""} ${data.expanded ? "is-expanded" : ""} ${data.certainty === "inferred" ? "is-inferred" : ""} ${data.gapId ? "has-gap" : ""} ${data.active ? "active" : ""} ${data.isFocused ? "is-focused" : ""}`}
        onKeyDown={onKeyDown}
        aria-label={data.expanded ? `${data.label}, expanded` : undefined}
      >
        <svg
          className="pin-outline"
          viewBox="0 0 248 224"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <path d={paperOutline(id)} />
        </svg>
        <span className="pushpin" aria-hidden="true" />
        {data.gapId && (
          <span className="pin-gap-flag" aria-hidden="true">
            <HelpCircle size={13} strokeWidth={2.25} />
          </span>
        )}
        <button
          ref={toggleRef}
          type="button"
          className="story-card-toggle nodrag nopan"
          aria-expanded={Boolean(data.expanded)}
          aria-label={`${data.label}. ${data.type}${data.certainty === "inferred" ? ", inferred" : ""}${data.gapId ? ", open question" : ""}. ${data.expanded ? "Collapse card" : "Expand card"}`}
          onClick={(event) => {
            event.stopPropagation();
            data.onToggle();
          }}
        >
          <span className="story-card-type">
            <span className="pin-kind-chip">
              <Icon size={12} strokeWidth={2.25} aria-hidden="true" />
              {data.hero ? `${data.type} · story centre` : data.type}
            </span>
            {data.certainty === "inferred" && (
              <span className="pin-certainty">Inferred</span>
            )}
          </span>
          <span className="story-card-title">{data.label}</span>
          {!data.expanded && (
            <span className="story-card-meta">
              {data.hero ? data.summary : meta}
            </span>
          )}
        </button>
        {data.expanded && (
          <div className="story-card-body nodrag nopan nowheel">
            {(data.time || kindNote) && (
              <p className="story-card-when">
                {data.time && <CalendarClock size={12} aria-hidden="true" />}
                {data.time ? formatCaseTime(data.time, data.timeZone) : null}
                {data.time && kindNote ? " · " : ""}
                {kindNote}
              </p>
            )}
            {data.summary && (
              <p className="story-card-summary">{data.summary}</p>
            )}
            {data.excerpts.length > 0 && (
              <ul className="story-card-excerpts" aria-label="Key sources">
                {data.excerpts.map((excerpt) => (
                  <li key={excerpt.id}>
                    <span>{excerpt.locator}</span>
                    <q>{excerpt.text}</q>
                  </li>
                ))}
              </ul>
            )}
            <p className="story-card-count">
              <Link2 size={11} aria-hidden="true" /> {sources}
              {data.certainty === "inferred" && " · inferred by analysis"}
            </p>
            <div className="story-card-actions">
              <button
                type="button"
                className="story-action primary"
                onClick={(event) => {
                  event.stopPropagation();
                  data.onInspect();
                }}
              >
                Inspect sources <ArrowUpRight size={13} aria-hidden="true" />
              </button>
              <button
                type="button"
                className="story-action"
                disabled={data.hiddenNeighbours === 0}
                onClick={(event) => {
                  event.stopPropagation();
                  data.onShowConnections();
                }}
              >
                <Network size={13} aria-hidden="true" />
                {data.hiddenNeighbours
                  ? `Show connections · ${data.hiddenNeighbours}`
                  : "All connections shown"}
              </button>
              {data.gapId && (
                <button
                  type="button"
                  className="story-action question"
                  onClick={(event) => {
                    event.stopPropagation();
                    data.onInspectGap?.();
                  }}
                >
                  <AlertTriangle size={12} aria-hidden="true" /> Open question
                </button>
              )}
              <button
                type="button"
                className="story-action icon"
                aria-label={`Collapse ${data.label}`}
                title="Collapse (Esc)"
                onClick={(event) => {
                  event.stopPropagation();
                  data.onCollapse();
                }}
              >
                <ChevronUp size={15} aria-hidden="true" />
              </button>
            </div>
          </div>
        )}
      </article>
    </div>
  );
});

/** A labelled stack standing for cards folded out of the story. Not evidence. */
export const StoryGroupNode = memo(function StoryGroupNode({
  data,
}: NodeProps<Node<StoryGroupData>>) {
  const Icon = cardIcons[data.nodeType as keyof typeof cardIcons] || Layers;
  const open = data.hidden === 0;
  const shown = data.total - data.hidden;
  return (
    <div
      className="story-node"
      style={{ width: data.width, height: data.height }}
    >
      <Handles />
      <button
        type="button"
        className={`story-group kind-${cardKind(data.nodeType)} ${open ? "is-open" : ""} ${data.isFocused ? "is-focused" : ""} nodrag nopan`}
        aria-expanded={open}
        aria-label={`${data.title}: group of ${data.total} cards, ${data.hidden} hidden. ${data.rule}. ${open ? "Fold the cards back into the group" : `Show ${data.hidden} cards`}`}
        title={data.rule}
        onClick={(event) => {
          event.stopPropagation();
          data.onToggle();
        }}
      >
        <span className="story-group-sheet" aria-hidden="true" />
        <span className="story-group-sheet" aria-hidden="true" />
        <span className="story-group-face">
          <span className="story-card-type">
            <span className="pin-kind-chip">
              <Icon size={12} strokeWidth={2.25} aria-hidden="true" />
              Group
            </span>
            <span className="story-group-count">{data.total}</span>
          </span>
          <span className="story-card-title">{data.title}</span>
          <span className="story-card-meta">
            {open
              ? `All ${data.total} on the board · fold back`
              : shown
                ? `${data.hidden} hidden, ${shown} on the board · show`
                : `${data.total} cards · show`}
            {data.matches
              ? ` · ${data.matches} match${data.matches === 1 ? "" : "es"}`
              : ""}
          </span>
        </span>
      </button>
    </div>
  );
});
