import { useRef, useState } from "react";
import { ImageOff, Sparkles } from "lucide-react";
import { api } from "../api/client";
import type { EvidenceNode } from "../api/types";
import { OriginBadge } from "./OriginBadge";
import { formatCaseTime } from "./presentation";
import {
  formatDuration,
  formatFrameTime,
  mediaAlt,
  mediaDevice,
  mediaKindLabel,
  mediaResolution,
} from "./media-card";

type MediaNode = EvidenceNode & { media: NonNullable<EvidenceNode["media"]> };

/** The media node behind a selection: the card itself, or a cited media file. */
export function mediaNodeFor(
  nodes: EvidenceNode[],
  selection: { kind: string; id: string; sourceId?: string },
): MediaNode | undefined {
  const evidenceId =
    selection.kind === "source" ? selection.id.split(/[:\s]/)[0] : undefined;
  return nodes.find(
    (node): node is MediaNode =>
      Boolean(node.media) &&
      (selection.kind === "node"
        ? node.id === selection.id
        : evidenceId !== undefined && node.media?.evidenceId === evidenceId),
  );
}

/** Photo or playable clip first, then metadata, then the LLM description kept apart as inferred. */
export function MediaInspector({
  node,
  caseId,
  timeZone,
}: {
  node: MediaNode;
  caseId: string;
  timeZone?: string;
}) {
  const { media } = node;
  const [failed, setFailed] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const url = api.evidenceFileUrl(caseId, media.evidenceId, { inline: true });
  const device = mediaDevice(media);
  const resolution = mediaResolution(media);
  const duration = formatDuration(media.durationS);
  const rows: Array<[string, string | undefined]> = [
    [
      "Captured",
      media.capturedUtc
        ? formatCaseTime(media.capturedUtc, timeZone, "full")
        : undefined,
    ],
    ["Time source", media.captureSource ?? undefined],
    [
      "Time flags",
      media.timeFlags?.length ? media.timeFlags.join(", ") : undefined,
    ],
    ["Device", device],
    ["Resolution", resolution],
    ["Duration", duration],
    [
      "GPS",
      media.gps
        ? `${media.gps.lat.toFixed(5)}, ${media.gps.lon.toFixed(5)}`
        : undefined,
    ],
  ];
  const vision = media.vision;
  const seek = (frameS: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = frameS;
  };
  return (
    <section className="inspector-media" aria-label="Media">
      {url && !failed ? (
        media.kind === "video" ? (
          <video
            ref={videoRef}
            src={url}
            controls
            preload="metadata"
            onError={() => setFailed(true)}
          >
            <a href={url}>Open the video</a>
          </video>
        ) : (
          <img
            src={url}
            alt={mediaAlt(node.label, media.kind)}
            decoding="async"
            onError={() => setFailed(true)}
          />
        )
      ) : (
        <p className="muted">
          <ImageOff size={14} aria-hidden="true" /> The{" "}
          {mediaKindLabel(media.kind).toLowerCase()} could not be loaded.
        </p>
      )}
      <dl>
        {rows
          .filter((row): row is [string, string] => Boolean(row[1]))
          .map(([key, value]) => (
            <div key={key} style={{ display: "contents" }}>
              <dt>{key}</dt>
              <dd>{value}</dd>
            </div>
          ))}
      </dl>
      {vision && (
        <div className="media-vision">
          <h3>
            <Sparkles size={13} aria-hidden="true" /> Description (LLM,
            inferred) <OriginBadge origin="llm" stage="media_vision" />
          </h3>
          <p>{vision.text}</p>
          {vision.observations.length > 0 && (
            <ul>
              {vision.observations.map((observation, index) => (
                <li key={`${index}-${observation.text}`}>
                  {media.kind === "video" &&
                    observation.frameS !== undefined &&
                    observation.frameS !== null && (
                      <button
                        type="button"
                        className="text-button seek-button"
                        onClick={() => seek(observation.frameS!)}
                        aria-label={`Seek video to ${formatFrameTime(observation.frameS)}`}
                      >
                        {formatFrameTime(observation.frameS)}
                      </button>
                    )}
                  {observation.text}
                </li>
              ))}
            </ul>
          )}
          <p className="muted">
            Model description, not observed fact
            {vision.model ? ` (${vision.model})` : ""}. Cited to the media
            record {node.citations[0] ?? media.evidenceId}.
          </p>
        </div>
      )}
    </section>
  );
}
