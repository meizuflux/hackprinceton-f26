import { memo, useState } from "react";
import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { paperOutline } from "./paper-note";
import { formatCaseTime } from "./presentation";
import {
  UserRound,
  MapPin,
  Smartphone,
  CalendarClock,
  FileText,
  Link2,
  ArrowUpRight,
  AlertTriangle,
  HelpCircle,
  Play,
  Camera,
  ImageOff,
} from "lucide-react";
import { cardKind, markedOrigin } from "./board-colors";
import { OriginBadge } from "./OriginBadge";
import type { MediaInfo, Origin } from "../api/types";
import { api } from "../api/client";
import {
  formatDuration,
  mediaAlt,
  mediaDevice,
  mediaKindLabel,
  videoSrc,
} from "./media-card";
export type PinData = {
  label: string;
  type: string;
  subtitle?: string;
  summary: string;
  citations: string[];
  time?: string;
  timeZone?: string;
  certainty?: string;
  origin?: Origin;
  stage?: string;
  media?: MediaInfo;
  caseId?: string;
  gapId?: string;
  active?: boolean;
  isFocused?: boolean;
  width?: number;
  height?: number;
  onInspect: () => void;
  onInspectGap?: () => void;
};
export const cardIcons = {
  person: UserRound,
  location: MapPin,
  device: Smartphone,
  event: CalendarClock,
  statement: FileText,
};
function MediaFrame({ data, media }: { data: PinData; media: MediaInfo }) {
  const [failed, setFailed] = useState(false);
  const url =
    data.caseId !== undefined
      ? api.evidenceFileUrl(data.caseId, media.evidenceId, { inline: true })
      : undefined;
  const duration = formatDuration(media.durationS);
  const KindIcon = media.kind === "video" ? Play : Camera;
  return (
    <div className={`pin-media is-${media.kind}`}>
      {url && !failed ? (
        media.kind === "video" ? (
          <video
            src={videoSrc(url, media.durationS)}
            preload="metadata"
            muted
            playsInline
            draggable={false}
            aria-label={mediaAlt(data.label, media.kind)}
            onError={() => setFailed(true)}
          />
        ) : (
          <img
            src={url}
            alt={mediaAlt(data.label, media.kind)}
            loading="lazy"
            decoding="async"
            draggable={false}
            onError={() => setFailed(true)}
          />
        )
      ) : (
        <span
          className="pin-media-missing"
          role="img"
          aria-label="Media unavailable"
        >
          <ImageOff size={22} aria-hidden="true" />
          <span>Preview unavailable</span>
        </span>
      )}
      <span className="pin-media-kind">
        <KindIcon size={11} strokeWidth={2.4} aria-hidden="true" />
        {mediaKindLabel(media.kind)}
      </span>
      {media.kind === "video" && url && !failed && (
        <span className="pin-media-play" aria-hidden="true">
          <Play size={16} fill="currentColor" strokeWidth={0} />
        </span>
      )}
      {media.kind === "video" && duration && (
        <span className="pin-media-duration">{duration}</span>
      )}
    </div>
  );
}

export const EvidenceNode = memo(function EvidenceNode({
  id,
  data,
}: NodeProps<Node<PinData>>) {
  const Icon = cardIcons[data.type as keyof typeof cardIcons] || FileText;
  const pinStyle = {
    ...(data.width ? { width: `${data.width}px` } : {}),
    ...(data.height ? { height: `${data.height}px` } : {}),
  };
  return (
    <div
      className={`evidence-pin ${data.media ? "has-media" : ""} ${data.type} kind-${cardKind(data.type)} ${data.certainty === "inferred" ? "is-inferred" : ""} ${markedOrigin(data.origin) ? `has-origin origin-${data.origin}` : ""} ${data.gapId ? "has-gap" : ""} ${data.active ? "active" : ""} ${data.isFocused ? "is-focused" : ""}`}
      style={pinStyle}
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
      {data.gapId && (
        <span className="pin-gap-flag" aria-hidden="true">
          <HelpCircle size={13} strokeWidth={2.25} />
        </span>
      )}
      <div className="pin-type">
        <span className="pin-kind">
          <span className="pin-kind-chip">
            <Icon size={12} strokeWidth={2.25} aria-hidden="true" />
            {data.type}
          </span>
          {data.certainty === "inferred" && (
            <span className="pin-certainty">Inferred</span>
          )}
          <OriginBadge origin={data.origin} stage={data.stage} />
        </span>
        {data.time && (
          <span className="pin-time">
            <CalendarClock size={11} />
            {formatCaseTime(data.time, data.timeZone)}
          </span>
        )}
      </div>
      {data.media && <MediaFrame data={data} media={data.media} />}
      <h3>{data.label}</h3>
      {data.media ? (
        <p className="pin-subtitle" title={mediaDevice(data.media)}>
          {mediaDevice(data.media) ?? "Device not recorded"}
        </p>
      ) : (
        <>
          <p className="pin-subtitle" title={data.subtitle}>
            {data.subtitle}
          </p>
          <p className="pin-summary">{data.summary}</p>
        </>
      )}
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
