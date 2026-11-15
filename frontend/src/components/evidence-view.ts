import type {
  EvidenceFile,
  EvidenceView,
  SourceRecord,
  ViewRange,
} from "../api/types";

/** Where a `/evidence/:sourceId` link points: a file, and optionally a citation locator inside it. */
export interface EvidenceTarget {
  evidenceId: string;
  locator?: string;
  /** Board source ID when the link is a citation the board knows. */
  sourceId?: string;
}

/**
 * Board source IDs are `{evidence_id}:{locator}` (`EV-070:event_id=BDG-000615`). Prefer the source's own
 * metadata; otherwise split at the first colon (evidence IDs never contain one). A bare ID opens the file.
 */
export function parseEvidenceTarget(
  sourceId: string,
  sources: SourceRecord[] = [],
): EvidenceTarget {
  const source = sources.find((item) => item.id === sourceId);
  const evidenceId = source?.metadata?.evidence_id;
  const locator = source?.metadata?.locator;
  if (evidenceId && locator)
    return { evidenceId, locator, sourceId: source.id };
  const split = sourceId.indexOf(":");
  if (split <= 0) return { evidenceId: sourceId };
  const rest = sourceId.slice(split + 1);
  return {
    evidenceId: sourceId.slice(0, split),
    ...(rest ? { locator: rest } : {}),
    ...(source ? { sourceId: source.id } : {}),
  };
}

/** The route segment that opens a file at a citation. */
export function evidenceLink(evidenceId: string, locator?: string): string {
  return locator ? `${evidenceId}:${locator}` : evidenceId;
}

export interface FileGroup {
  folder: string;
  files: EvidenceFile[];
}

/** Folder an evidence file was submitted in; files inside nested archives keep their container's folder. */
export function fileFolder(path: string): string {
  const outer = path.split("::")[0];
  const parts = outer.split("/").filter(Boolean);
  return parts.length > 1 ? parts[parts.length - 2] : "Archive root";
}

/** Group by submitted folder, in path order, keeping the inventory's order inside each folder. */
export function groupFiles(files: EvidenceFile[]): FileGroup[] {
  const groups = new Map<string, EvidenceFile[]>();
  const sorted = [...files].sort((a, b) =>
    a.path.localeCompare(b.path, undefined, { numeric: true }),
  );
  for (const file of sorted) {
    const folder = fileFolder(file.path);
    groups.set(folder, [...(groups.get(folder) ?? []), file]);
  }
  return [...groups].map(([folder, items]) => ({ folder, files: items }));
}

export function matchesFile(file: EvidenceFile, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return [
    file.filename,
    file.path,
    file.evidenceId,
    file.evidenceType,
    file.format,
    file.title ?? "",
  ]
    .join(" ")
    .toLowerCase()
    .includes(q);
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Index → highlight, for a set of 0-based inclusive ranges. */
export function rangeAt(
  ranges: ViewRange[] | undefined,
  index: number,
): ViewRange | undefined {
  return ranges?.find((range) => index >= range.start && index <= range.end);
}

/** Human description of where the citation landed, from the backend's resolved ranges. */
export function describeTarget(view: EvidenceView): string | undefined {
  const first = view.target?.ranges[0];
  if (view.target?.page) return `page ${view.target.page}`;
  if (view.target?.whole) return "the whole file";
  if (!first) return undefined;
  if (view.table) {
    const row = first.start + 2;
    return first.end > first.start
      ? `rows ${row}–${first.end + 2}`
      : `row ${row}`;
  }
  const unit = view.lines?.unit === "paragraph" ? "paragraph" : "line";
  return first.end > first.start
    ? `${unit}s ${first.start + 1}–${first.end + 1}`
    : `${unit} ${first.start + 1}`;
}

/** Column widths in `ch`, from the header and a sample of rows; long values are clipped and kept in a tooltip. */
export function columnWidths(
  columns: string[],
  rows: Array<{ cells: string[] }>,
  sample = 200,
): number[] {
  const count = Math.max(columns.length, ...rows.map((r) => r.cells.length));
  return Array.from({ length: count }, (_, index) => {
    let width = (columns[index] ?? "").length;
    for (const row of rows.slice(0, sample)) {
      width = Math.max(width, (row.cells[index] ?? "").length);
    }
    return Math.min(Math.max(width + 4, 7), 46);
  });
}

/** Which slice of a fixed-height list is visible, with overscan. */
export function visibleSlice(
  scrollTop: number,
  viewport: number,
  rowHeight: number,
  count: number,
  overscan = 12,
): { start: number; end: number } {
  const start = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
  const end = Math.min(
    count,
    Math.ceil((scrollTop + viewport) / rowHeight) + overscan,
  );
  return { start, end };
}
