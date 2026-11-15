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
  Sparkles,
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
import { cardVariant } from "./board-layout";

export type PinData = {
  /** Raw record label; the title falls back to it. */
  label: string;
  /** Readable title (backend `displayLabel`, else the tidied label). */
  title?: string;
  /** The raw label as small metadata when the title differs from it. */
  rawLabel?: string;
  /** The readable title was written by a model. */
  labelOrigin?: "rules" | "llm";
  type: string;
  subtitle?: string;
  summary: string;
  citations: string[];
  time?: string;
  timeZone?: string;
  certainty?: string;
  origin?: Origin;
  stage?: string;
  /** Short model name for ML cards (e.g. DBSCAN), with the full name as a tooltip. */
  method?: string;
  methodFull?: string;
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

/** The record kind in a word or two: the backend subtitle when it is short and specific. */
export function kindWord(type: string, subtitle?: string, origin?: Origin) {
  const sub = subtitle?.trim();
  if (markedOrigin(origin) || !sub || sub.length > 18) return type;
  return sub;
}

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

const SIDES = [Position.Top, Position.Right, Position.Bottom, Position.Left];
function Handles() {
  return (
    <>
      {SIDES.map((side) => (
        <span key={side}>
          <Handle id={`target-${side}`} type="target" position={side} />
          <Handle id={`source-${side}`} type="source" position={side} />
        </span>
      ))}
    </>
  );
}

function InspectButton({ data, title }: { data: PinData; title: string }) {
  return (
    <button
      className="nodrag nopan pin-inspect"
      onClick={(event) => {
        event.stopPropagation();
        data.onInspect();
      }}
      aria-label={`Inspect ${title} and sources`}
      title={`Open ${title} and sources`}
    >
      <ArrowUpRight size={16} aria-hidden="true" />
    </button>
  );
}

/** A model-written title is marked as LLM-inferred, apart from the record's own label. */
function LlmTitleMark() {
  return (
    <span
      className="pin-llm-title"
      title="Readable title written by an LLM (inferred); the record label is below"
    >
      <Sparkles size={10} strokeWidth={2.4} aria-hidden="true" />
      <span className="sr-only">Title inferred by an LLM.</span>
    </span>
  );
}

/** First letter of a person's name for the avatar disc; display only. */
function initialOf(name: string) {
  return name.match(/\p{L}/u)?.[0]?.toUpperCase() ?? "?";
}

/**
 * One evidence card in the full graph. The shape follows the record's role:
 * a person is a small name tag, phones, accounts and places are compact, and
 * events, statements, analysis cards and media carry more text.
 */
export const EvidenceNode = memo(function EvidenceNode({
  id,
  data,
}: NodeProps<Node<PinData>>) {
  const Icon = cardIcons[data.type as keyof typeof cardIcons] || FileText;
  const title = data.title ?? data.label;
  const variant = cardVariant(data);
  const mark = markedOrigin(data.origin);
  const pinStyle = {
    ...(data.width ? { width: `${data.width}px` } : {}),
    ...(data.height ? { height: `${data.height}px` } : {}),
  };
  const sources = `${data.citations.length} source${data.citations.length === 1 ? "" : "s"}`;
  const className = `evidence-pin variant-${variant} ${data.media ? "has-media" : ""} ${data.type} kind-${cardKind(data.type)} ${data.certainty === "inferred" ? "is-inferred" : ""} ${mark ? `has-origin origin-${mark}` : ""} ${data.gapId ? "has-gap" : ""} ${data.active ? "active" : ""} ${data.isFocused ? "is-focused" : ""}`;
  const outline = (
    <svg
      className="pin-outline"
      viewBox="0 0 248 224"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path d={paperOutline(id)} />
    </svg>
  );
  const gapFlag = data.gapId && (
    <span className="pin-gap-flag" aria-hidden="true">
      <HelpCircle size={13} strokeWidth={2.25} />
    </span>
  );
  const titleBlock = (
    <>
      <h3
        title={
          data.rawLabel ? `${title} (record label: ${data.rawLabel})` : title
        }
      >
        {data.labelOrigin === "llm" && <LlmTitleMark />}
        {title}
      </h3>
      {data.rawLabel && (
        <p className="pin-raw" title={data.rawLabel}>
          {data.rawLabel}
        </p>
      )}
    </>
  );

  if (variant === "person") {
    return (
      <div className={className} style={pinStyle}>
        {outline}
        <Handles />
        <span className="pushpin" aria-hidden="true" />
        {gapFlag}
        <span className="pin-avatar" aria-hidden="true">
          {initialOf(title)}
        </span>
        <div className="pin-person-text">
          {titleBlock}
          <p className="pin-person-meta">
            {data.certainty === "inferred" && (
              <span className="pin-certainty">Inferred</span>
            )}
            <OriginBadge origin={data.origin} stage={data.stage} />
            <span className="sr-only">Person. </span>
            {data.gapId ? (
              <button
                type="button"
                className="pin-gap is-inline nodrag nopan"
                aria-label={`Inspect linked question for ${title}`}
                onClick={(event) => {
                  event.stopPropagation();
                  data.onInspectGap?.();
                }}
              >
                <AlertTriangle size={11} aria-hidden="true" /> Question
              </button>
            ) : (
              <span>{sources}</span>
            )}
          </p>
        </div>
        <InspectButton data={data} title={title} />
      </div>
    );
  }

  const compact = variant === "compact";
  return (
    <div className={className} style={pinStyle}>
      {outline}
      <Handles />
      <span className="pushpin" aria-hidden="true" />
      {gapFlag}
      <div className="pin-type">
        <span className="pin-kind">
          <span className="pin-kind-chip">
            <Icon size={12} strokeWidth={2.25} aria-hidden="true" />
            {kindWord(data.type, data.subtitle, data.origin)}
          </span>
          {data.certainty === "inferred" && (
            <span className="pin-certainty">Inferred</span>
          )}
          <OriginBadge origin={data.origin} stage={data.stage} />
        </span>
        {data.time && (
          <span className="pin-time">
            <CalendarClock size={11} aria-hidden="true" />
            {formatCaseTime(data.time, data.timeZone)}
          </span>
        )}
      </div>
      {data.media && <MediaFrame data={data} media={data.media} />}
      {titleBlock}
      {data.media ? (
        <p className="pin-subtitle" title={mediaDevice(data.media)}>
          {mediaDevice(data.media) ??
            (data.media.kind === "video"
              ? "CCTV export"
              : "Device not recorded")}
        </p>
      ) : (
        data.summary &&
        !(compact && data.rawLabel) && (
          <p className={`pin-summary ${compact ? "is-short" : ""}`}>
            {data.summary}
          </p>
        )
      )}
      {data.gapId && (
        <button
          type="button"
          className="pin-gap nodrag nopan"
          aria-label={`Inspect linked question for ${title}`}
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
          {data.method ? (
            <span className="pin-method" title={data.methodFull}>
              {data.method}
            </span>
          ) : null}
          <Link2 size={11} aria-hidden="true" />
          {sources}
        </span>
        <InspectButton data={data} title={title} />
      </div>
    </div>
  );
});
