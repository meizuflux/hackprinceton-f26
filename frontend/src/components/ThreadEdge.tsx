import { memo } from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type Edge,
  type EdgeProps,
} from "@xyflow/react";
import type { Origin } from "../api/types";
import {
  markedOrigin,
  originMarks,
  threadColors,
  type ThreadCategory,
} from "./board-colors";
import { OriginIcon } from "./OriginBadge";
import { sideOf, threadPoint, THREAD_CURVATURE } from "./thread-geometry";

export type ThreadData = {
  kind: "observed" | "claim" | "inference";
  category: ThreadCategory;
  /** Color-independent wording for claims, inferences and contradictions. */
  badge?: string;
  label: string;
  directed: boolean;
  origin?: Origin;
  isFocused?: boolean;
  isDimmed?: boolean;
  /** Story view: the label waits for hover, focus or selection. */
  quiet?: boolean;
  /** Where the label sits along the thread (0 source, 1 target), chosen to clear cards. */
  labelT?: number;
  /** No clear spot: the label folds to a small knot until hovered, focused or selected. */
  labelCovered?: boolean;
  /** Stands for this many real threads into a group's hidden cards. */
  aggregateCount?: number;
  ariaLabel?: string;
  onInspect: () => void;
};

export const ThreadEdge = memo(function ThreadEdge(
  props: EdgeProps<Edge<ThreadData>>,
) {
  const [path, midX, midY] = getBezierPath({
    ...props,
    curvature: THREAD_CURVATURE,
  });
  const data = props.data;
  if (!data) return null;
  const t = data.labelT ?? 0.5;
  const { x, y } =
    t === 0.5
      ? { x: midX, y: midY }
      : threadPoint(
          {
            x: props.sourceX,
            y: props.sourceY,
            side: sideOf(props.sourcePosition),
          },
          {
            x: props.targetX,
            y: props.targetY,
            side: sideOf(props.targetPosition),
          },
          t,
        );
  const mark = markedOrigin(data.origin);
  return (
    <>
      <BaseEdge
        id={props.id}
        path={path}
        markerEnd={props.markerEnd}
        style={props.style}
        interactionWidth={24}
      />
      <EdgeLabelRenderer>
        <button
          type="button"
          className={`thread-label nodrag nopan ${data.kind} thread-${data.category} ${props.selected || data.isFocused ? "is-selected" : ""} ${data.isDimmed ? "is-dimmed" : ""} ${data.quiet ? "is-quiet" : ""} ${data.aggregateCount ? "is-aggregate" : ""} ${data.labelCovered && !data.aggregateCount ? "is-covered" : ""} ${mark ? `has-origin origin-${mark}` : ""}`}
          data-edge={props.id}
          data-source={props.source}
          data-target={props.target}
          style={{
            transform: `translate(-50%, -50%) translate(${x}px, ${y}px)`,
          }}
          onClick={(event) => {
            event.stopPropagation();
            data.onInspect();
          }}
          aria-label={
            data.ariaLabel ??
            `${data.kind === "observed" ? "Observed" : data.kind === "claim" ? "Claim" : "Inference"}${mark ? `, from ${originMarks[mark].label}` : ""}, ${threadColors[data.category].label.toLowerCase()}: ${data.label}. Inspect relationship and sources`
          }
          title={
            data.aggregateCount
              ? data.label
              : `${threadColors[data.category].label}: ${data.label}`
          }
        >
          {data.aggregateCount ? (
            <strong className="thread-count">{data.aggregateCount}</strong>
          ) : (
            data.badge && <strong className="thread-badge">{data.badge}</strong>
          )}
          <span className="thread-text">
            {mark && <OriginIcon origin={data.origin} size={11} />}
            {data.label}
          </span>
        </button>
      </EdgeLabelRenderer>
    </>
  );
});
