import type { CaseData, SourceRecord } from "../api/types";
import { formatCaseTime } from "./presentation";

export type HeadlineKind = "contradiction" | "gap" | "insight";

/** Presentation of the backend's headline finding. Every value comes from the item itself. */
export interface Headline {
  kind: HeadlineKind;
  id: string;
  /** Chip text; neutral wording, never a verdict. */
  status: string;
  title: string;
  /** A quoted statement when the backend text opens with one (`X said: "…"`). */
  statement?: { speaker: string; quote: string };
  summary: string;
  citations: string[];
  context: { label: string; items: string[] };
  note: string;
}

const STATUS: Record<HeadlineKind, string> = {
  contradiction: "Possible contradiction",
  gap: "Open question",
  insight: "Insight",
};

/**
 * Resolves `story.headline` against the case. Returns null without a story,
 * or when the named item is missing, so the board keeps its ordinary opening.
 */
export function resolveHeadline(data: CaseData): Headline | null {
  const ref = data.story?.headline;
  if (!ref) return null;
  if (ref.kind === "contradiction") {
    const item = data.contradictions?.find((entry) => entry.id === ref.id);
    if (!item) return null;
    const split = splitStatement(item.text);
    return {
      kind: "contradiction",
      id: item.id,
      status: STATUS.contradiction,
      title: item.title,
      statement: split.statement,
      summary: plainCounts(split.rest),
      citations: item.citations,
      context: { label: "Possible reasons", items: item.possibleReasons },
      note: "A contradiction is not proof. Records and statements can disagree for ordinary reasons; review the sources before drawing a conclusion.",
    };
  }
  if (ref.kind === "gap") {
    const item = data.gaps.find((entry) => entry.id === ref.id);
    if (!item) return null;
    return {
      kind: "gap",
      id: item.id,
      status: STATUS.gap,
      title: item.title,
      summary: item.whyItMatters || item.description,
      citations: item.citations,
      context: {
        label: "What is missing",
        items: [item.missing, item.direction].filter((entry): entry is string =>
          Boolean(entry),
        ),
      },
      note: "A gap is a question to verify, not a conclusion.",
    };
  }
  const item = data.insights.find((entry) => entry.id === ref.id);
  if (!item) return null;
  return {
    kind: "insight",
    id: item.id,
    status: STATUS.insight,
    title: item.title,
    summary: item.inference || item.text,
    citations: item.citations,
    context: { label: "Unknowns", items: item.unknowns ?? [] },
    note: "An insight is an inference. Verify it against the cited sources.",
  };
}

/** `33 record(s)` → `33 records`; `1 record(s)` → `1 record`. Wording only. */
export function plainCounts(text: string): string {
  return text.replace(
    /\b(\d+) ([A-Za-z]+)\(s\)/g,
    (_, count: string, noun: string) =>
      count === "1" ? `1 ${noun}` : `${count} ${noun}s`,
  );
}

/** Splits `Name said: "quote". Rest` so the asserted statement reads apart from the records. */
export function splitStatement(text: string): {
  statement?: { speaker: string; quote: string };
  rest: string;
} {
  const match = /^([^".:]{1,80}?) said: "(.+?)"\.?(?:\s+|$)([\s\S]*)$/.exec(
    text.trim(),
  );
  if (!match) return { rest: text.trim() };
  return {
    statement: { speaker: match[1], quote: match[2] },
    rest: match[3].trim(),
  };
}

const evidenceKey = (source: SourceRecord) =>
  source.metadata.evidence_id || source.path;

/**
 * Picks a few cited sources to show first: asserted statements lead, then
 * records taken one file at a time so the rows span the evidence rather than
 * repeating one file. Order within each group follows the citation order.
 */
export function supportingSources(
  data: Pick<CaseData, "sources">,
  citations: string[],
  max = 4,
): SourceRecord[] {
  const byId = new Map(data.sources.map((source) => [source.id, source]));
  const cited = [...new Set(citations)]
    .map((id) => byId.get(id))
    .filter((source): source is SourceRecord => Boolean(source));
  const asserted = cited.filter((s) => s.metadata.reliability === "asserted");
  const rest = cited.filter((s) => s.metadata.reliability !== "asserted");
  const queues = new Map<string, SourceRecord[]>();
  for (const source of rest) {
    const key = evidenceKey(source);
    queues.set(key, [...(queues.get(key) ?? []), source]);
  }
  const interleaved: SourceRecord[] = [];
  while (interleaved.length < rest.length) {
    for (const queue of queues.values()) {
      const next = queue.shift();
      if (next) interleaved.push(next);
    }
  }
  return [...asserted, ...interleaved].slice(0, max);
}

const KIND_TITLES: Record<string, string> = {
  interview_turn: "Interview statement",
  place_visit: "Place visit",
  movement: "Movement",
  event: "Logged event",
};

export interface SourceRow {
  id: string;
  title: string;
  detail: string;
  file: string;
  format: string;
  locator?: string;
  time: string;
  asserted: boolean;
}

/** Readable labels for one supporting-source row; the excerpt and file are shown as recorded. */
export function sourceRow(source: SourceRecord, timeZone?: string): SourceRow {
  const file = source.path.split("/").pop() || source.path;
  const kind = source.kind || source.metadata.record_type || "";
  const title =
    KIND_TITLES[kind] ??
    (kind ? kind.charAt(0).toUpperCase() + kind.slice(1) : file).replace(
      /_/g,
      " ",
    );
  const excerpt = source.excerpt.replace(/\s+/g, " ").trim();
  return {
    id: source.id,
    title,
    detail:
      excerpt.length > 96 ? `${excerpt.slice(0, 95).trimEnd()}…` : excerpt,
    file,
    format: file.includes(".") ? (file.split(".").pop() ?? "") : "",
    locator: source.metadata.locator || undefined,
    time: formatCaseTime(source.timestamp, timeZone),
    asserted: source.metadata.reliability === "asserted",
  };
}
