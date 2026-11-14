import { memo } from "react";
import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { paperOutline } from "./paper-note";
import {
  UserRound,
  MapPin,
  Smartphone,
  CalendarClock,
  FileText,
  Link2,
  ArrowUpRight,
  AlertTriangle,
} from "lucide-react";
export type PinData = {
  label: string;
  type: string;
  subtitle?: string;
  summary: string;
  citations: string[];
  time?: string;
  gapId?: string;
  active?: boolean;
  onInspect: () => void;
  onInspectGap?: () => void;
};
const icons = {
  person: UserRound,
  location: MapPin,
  device: Smartphone,
  event: CalendarClock,
  statement: FileText,
};
export const EvidenceNode = memo(function EvidenceNode({
  id,
  data,
}: NodeProps<Node<PinData>>) {
  const Icon = icons[data.type as keyof typeof icons] || FileText;
  return (
    <div
      className={`evidence-pin ${data.type} ${data.gapId ? "has-gap" : ""} ${data.active ? "active" : ""}`}
    >
      <svg
        className="pin-outline"
        viewBox="0 0 248 224"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <path d={paperOutline(id)} />
      </svg>
      {[Position.Top, Position.Right, Position.Bottom, Position.Left].map(
        (side) => (
          <span key={side}>
            <Handle id={`target-${side}`} type="target" position={side} />
            <Handle id={`source-${side}`} type="source" position={side} />
          </span>
        ),
      )}
      <span className="pushpin" aria-hidden="true" />
      <div className="pin-type">
        <span>
          <Icon size={12} />
          {data.type}
        </span>
        {data.time && (
          <span className="pin-time">
            <CalendarClock size={11} />
            {data.time}
          </span>
        )}
      </div>
      <h3>{data.label}</h3>
      <p className="pin-subtitle" title={data.subtitle}>
        {data.subtitle}
      </p>
      <p className="pin-summary">{data.summary}</p>
      {data.gapId && (
        <button
          type="button"
          className="pin-gap nodrag nopan"
          aria-label={`Inspect linked question for ${data.label}`}
          onClick={(event) => {
            event.stopPropagation();
            data.onInspectGap?.();
          }}
        >
          <AlertTriangle size={12} aria-hidden="true" /> Open question
          <ArrowUpRight size={12} aria-hidden="true" />
        </button>
      )}
      <div className="pin-footer">
        <span>
          <Link2 size={11} />
          {data.citations.length} source{data.citations.length === 1 ? "" : "s"}
        </span>
        <button
          className="nodrag nopan pin-inspect"
          onClick={(event) => {
            event.stopPropagation();
            data.onInspect();
          }}
          aria-label={`Inspect ${data.label} and sources`}
          title={`Open ${data.label} and sources`}
        >
          <ArrowUpRight size={16} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
});
