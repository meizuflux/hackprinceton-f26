import type { MediaInfo } from "../api/types";

/** Presentation helpers for photo and video cards; they never create case facts. */

export const MEDIA_FRAME = {
  photo: { width: 230, height: 173 },
  video: { width: 230, height: 130 },
} as const;

export function mediaKindLabel(kind: MediaInfo["kind"]): "CCTV" | "Photo" {
  return kind === "video" ? "CCTV" : "Photo";
}

/** Poster frame for a clip: halfway through when the duration is known. */
export function posterTime(durationS?: number | null): number {
  return durationS && durationS > 0 ? Math.round(durationS * 5) / 10 : 0.1;
}

export function videoSrc(url: string, durationS?: number | null): string {
  return `${url}#t=${posterTime(durationS)}`;
}

export function mediaAlt(label: string, kind: MediaInfo["kind"]): string {
  return `${mediaKindLabel(kind)}: ${label}`;
}

export function formatDuration(durationS?: number | null): string | undefined {
  if (durationS === undefined || durationS === null || durationS < 0)
    return undefined;
  const total = Math.round(durationS);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function mediaDevice(media: MediaInfo): string | undefined {
  const parts = [media.deviceMake, media.deviceModel]
    .map((part) => part?.trim())
    .filter(Boolean);
  return parts.length ? parts.join(" ") : undefined;
}

export function mediaResolution(media: MediaInfo): string | undefined {
  return media.width && media.height
    ? `${media.width} × ${media.height}`
    : undefined;
}

export function formatFrameTime(frameS: number): string {
  return formatDuration(frameS) ?? "0:00";
}
