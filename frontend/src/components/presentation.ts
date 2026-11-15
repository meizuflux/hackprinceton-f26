import { isMock } from "../api/client";

const ISO_TIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/;

/** Format an ISO time in the case time zone; other strings pass through unchanged. */
export function formatCaseTime(
  value: string | undefined,
  timeZone?: string,
  style: "short" | "full" = "short",
): string {
  if (!value || !ISO_TIME.test(value)) return value ?? "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  try {
    const parts = Object.fromEntries(
      new Intl.DateTimeFormat("en-GB", {
        timeZone,
        weekday: "short",
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hourCycle: "h23",
        timeZoneName: "short",
      })
        .formatToParts(date)
        .map((part) => [part.type, part.value]),
    );
    const day = `${parts.weekday} ${parts.day} ${parts.month}`;
    return style === "full"
      ? `${day} ${parts.year}, ${parts.hour}:${parts.minute}:${parts.second} ${parts.timeZoneName}`
      : `${day}, ${parts.hour}:${parts.minute}`;
  } catch {
    return value;
  }
}

/** Ranking scores are computed by the backend; fixture scores are illustrative. */
export function scoreLabel(
  score: number,
  kind: "rank" | "percent" = "percent",
) {
  const value = Math.round(score * 100);
  if (isMock) return `Illustrative · ${value}%`;
  return kind === "rank" ? `Priority score ${value}` : `Rank score ${value}`;
}

/** Insight confidence is a label, never a probability. */
export function insightStrength(insight: {
  score: number;
  confidence?: string;
}) {
  return insight.confidence
    ? `${insight.confidence[0].toUpperCase()}${insight.confidence.slice(1)} confidence`
    : scoreLabel(insight.score);
}

export function insightKind(insight: { certainty?: string }) {
  return insight.certainty === "observed" ? "Observed basis" : "Inference";
}

/**
 * Presentation-only formatting for the case subtitle the API supplies: embedded
 * ISO timestamps read as case-local times and long counts gain separators. The
 * wording and every value come from the API unchanged.
 */
export function formatCaseSubtitle(subtitle: string, timeZone?: string) {
  return subtitle
    .replace(/\d{4}-\d{2}-\d{2}T[\d:.]+(?:Z|[+-]\d{2}:\d{2})/g, (iso) =>
      formatCaseTime(iso, timeZone),
    )
    .replace(
      /(^|\s)(\d{4,})(?= [a-z])/g,
      (_, lead: string, count: string) =>
        `${lead}${Number(count).toLocaleString("en-US")}`,
    );
}
