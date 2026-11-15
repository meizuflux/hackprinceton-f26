import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronUp,
  Crosshair,
  Download,
  PanelRightOpen,
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
} from "lucide-react";
import { api } from "../api/client";
import { isApiError } from "../api/http";
import type { EvidenceView, ViewRange } from "../api/types";
import {
  columnWidths,
  describeTarget,
  formatBytes,
  rangeAt,
  visibleSlice,
  type EvidenceTarget,
} from "./evidence-view";
import { FileKindIcon } from "./FileKindIcon";

const WINDOW = 2000;
/** Above this many items, rows keep a fixed height (no wrapping) and only the visible slice renders. */
const VIRTUALIZE_AFTER = 600;
const LINE_HEIGHT = 22;
const ROW_HEIGHT = 30;

export function EvidenceFileViewer({
  caseId,
  target,
  onInspectSource,
}: {
  caseId: string;
  target: EvidenceTarget;
  /** Opens the board's source inspector; offered only for citations the board knows. */
  onInspectSource?: (sourceId: string) => void;
}) {
  const [offset, setOffset] = useState<number | undefined>(undefined);
  const [jump, setJump] = useState(0);
  useEffect(() => {
    setOffset(undefined);
    setJump((n) => n + 1);
  }, [target.evidenceId, target.locator]);

  const view = useQuery({
    queryKey: [
      "evidence-view",
      caseId,
      target.evidenceId,
      target.locator ?? "",
      offset ?? "auto",
    ],
    queryFn: () =>
      api.viewEvidence(caseId, target.evidenceId, {
        locator: target.locator,
        offset,
        limit: WINDOW,
      }),
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[2] === target.evidenceId &&
      previousQuery?.queryKey[3] === (target.locator ?? "")
        ? previous
        : undefined,
    retry: (count, error) => !isApiError(error) && count < 2,
  });

  if (view.isPending) return <ViewerSkeleton />;
  if (view.isError) {
    const missing = isApiError(view.error, "evidence_not_found");
    return (
      <div className="raw-viewer-message" role="alert">
        <ShieldAlert size={18} aria-hidden="true" />
        <div>
          <h3>
            {missing
              ? `Evidence ${target.evidenceId} is not in this case`
              : "The file could not be opened"}
          </h3>
          <p>
            {missing
              ? "The link names an evidence ID that the latest ingestion did not record. Choose a file from the list."
              : `${view.error.message} Try again, or download the read-only copy.`}
          </p>
          {!missing && (
            <button
              type="button"
              className="button button-secondary"
              onClick={() => void view.refetch()}
            >
              Try again
            </button>
          )}
        </div>
      </div>
    );
  }
  const data = view.data;
  if (!data) {
    return (
      <div className="raw-viewer-message">
        <ShieldAlert size={18} aria-hidden="true" />
        <div>
          <h3>Original file unavailable</h3>
          <p>This adapter has no ingestion output, so it cannot open files.</p>
        </div>
      </div>
    );
  }

  return (
    <article className="raw-viewer" aria-label={`${data.filename} viewer`}>
      <FileHeader caseId={caseId} view={data} />
      {data.target && (
        <CitationBar
          view={data}
          target={target}
          onJump={() => {
            if (offset !== undefined) setOffset(undefined);
            setJump((n) => n + 1);
          }}
          onInspectSource={onInspectSource}
        />
      )}
      {data.notes.length > 0 && (
        <ul className="raw-viewer-notes">
          {data.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
      <div className="raw-viewer-body" aria-busy={view.isFetching}>
        <ViewerBody
          caseId={caseId}
          view={data}
          jump={jump}
          onPage={(next) => setOffset(next)}
        />
      </div>
    </article>
  );
}

function ViewerSkeleton() {
  return (
    <div className="raw-viewer raw-viewer-skeleton" aria-label="Opening file">
      <div className="skeleton-bar" style={{ width: "38%" }} />
      <div className="skeleton-bar" style={{ width: "62%", height: 10 }} />
      <div className="skeleton-block" />
    </div>
  );
}

function ManifestCheck({ match }: { match: boolean | null }) {
  if (match === true)
    return (
      <span className="hash-check is-ok">
        <ShieldCheck size={14} aria-hidden="true" /> Manifest hash matches
      </span>
    );
  if (match === false)
    return (
      <span className="hash-check is-bad">
        <ShieldAlert size={14} aria-hidden="true" /> Manifest hash does not
        match
      </span>
    );
  return (
    <span className="hash-check">
      <ShieldQuestion size={14} aria-hidden="true" /> No manifest hash listed
    </span>
  );
}

function FileHeader({ caseId, view }: { caseId: string; view: EvidenceView }) {
  const download = api.evidenceFileUrl(caseId, view.evidenceId);
  return (
    <header className="raw-viewer-header">
      <div className="raw-viewer-title">
        <FileKindIcon kind={view.kind} format={view.format} size={18} />
        <div>
          <h3>{view.filename}</h3>
          <p className="raw-viewer-path">{view.path}</p>
        </div>
        {download && (
          <a
            className="button button-secondary raw-download"
            href={download}
            download
          >
            <Download size={15} aria-hidden="true" />
            Download original
          </a>
        )}
      </div>
      <dl className="raw-viewer-facts">
        <div>
          <dt>Evidence ID</dt>
          <dd className="mono">{view.evidenceId}</dd>
        </div>
        <div>
          <dt>Type</dt>
          <dd>{view.evidenceType}</dd>
        </div>
        <div>
          <dt>Format</dt>
          <dd>{view.format}</dd>
        </div>
        <div>
          <dt>Size</dt>
          <dd>{formatBytes(view.bytes)}</dd>
        </div>
        <div>
          <dt>Records</dt>
          <dd>{view.recordCount.toLocaleString()}</dd>
        </div>
        <div>
          <dt>Parse status</dt>
          <dd>{view.parseStatus}</dd>
        </div>
      </dl>
      <div className="raw-viewer-hash">
        <ManifestCheck match={view.manifestMatch} />
        <span className="raw-hash-label">SHA-256</span>
        <code title="SHA-256 of the read-only copy, computed at ingestion">
          {view.sha256}
        </code>
      </div>
    </header>
  );
}

function CitationBar({
  view,
  target,
  onJump,
  onInspectSource,
}: {
  view: EvidenceView;
  target: EvidenceTarget;
  onJump: () => void;
  onInspectSource?: (sourceId: string) => void;
}) {
  const t = view.target!;
  const where = describeTarget(view);
  const located = t.ranges.length > 0;
  const cited =
    view.table && located
      ? view.table.items.find((row) => row.row === t.ranges[0].start + 2)
      : undefined;
  return (
    <section
      className={`citation-bar ${t.resolved || located ? "" : "is-unresolved"}`}
      aria-label="Cited position"
    >
      <div className="citation-bar-line">
        <Crosshair size={15} aria-hidden="true" />
        <p>
          <span className="mono">
            {view.evidenceId} · {t.locator}
          </span>
          {where ? (
            <>
              {" "}
              resolves to <strong>{where}</strong>
              {view.pretty ? " of the pretty-printed rendering" : ""}
            </>
          ) : t.resolved ? (
            <> was found, but has no position in this view</>
          ) : (
            <> does not match a record in this file</>
          )}
        </p>
        <div className="citation-bar-actions">
          {located && (
            <button type="button" className="text-button" onClick={onJump}>
              Jump to citation
            </button>
          )}
          {target.sourceId && onInspectSource && (
            <button
              type="button"
              className="text-button"
              onClick={() => onInspectSource(target.sourceId!)}
            >
              <PanelRightOpen size={14} aria-hidden="true" /> Inspect source
            </button>
          )}
        </div>
      </div>
      {t.sharedRanges.length > 0 && (
        <p className="citation-bar-note">
          {t.sharedRecordIds.length} other{" "}
          {t.sharedRecordIds.length === 1 ? "record shares" : "records share"}{" "}
          this label; {t.sharedRecordIds.length === 1 ? "it is" : "they are"}{" "}
          marked more lightly.
        </p>
      )}
      {cited && view.table && (
        <dl className="citation-row" aria-label={`Row ${cited.row} as stored`}>
          {view.table.columns.map((column, index) =>
            cited.cells[index] ? (
              <div
                key={`${column}-${index}`}
                className={
                  cited.cells[index].length > 48 ? "is-wide" : undefined
                }
              >
                <dt>{column}</dt>
                <dd>{cited.cells[index]}</dd>
              </div>
            ) : null,
          )}
        </dl>
      )}
    </section>
  );
}

function ViewerBody({
  caseId,
  view,
  jump,
  onPage,
}: {
  caseId: string;
  view: EvidenceView;
  jump: number;
  onPage: (offset: number) => void;
}) {
  const inline = api.evidenceFileUrl(caseId, view.evidenceId, {
    inline: true,
  });
  switch (view.kind) {
    case "image":
      return (
        <figure className="raw-media">
          <img
            src={inline}
            alt={`Evidence ${view.evidenceId}, ${view.filename}`}
          />
        </figure>
      );
    case "video":
      return (
        <figure className="raw-media">
          <video src={inline} controls preload="metadata">
            <a href={inline}>Open the video</a>
          </video>
          <figcaption>
            Container metadata is what ingestion read; the frames themselves
            have not been analysed.
          </figcaption>
        </figure>
      );
    case "audio":
      return (
        <figure className="raw-media raw-media-audio">
          <audio src={inline} controls preload="metadata" />
        </figure>
      );
    case "pdf":
      return (
        <iframe
          className="raw-pdf"
          title={`${view.filename} (PDF)`}
          src={`${inline}${view.target?.page ? `#page=${view.target.page}` : ""}`}
        />
      );
    case "binary":
      return (
        <div className="raw-viewer-message">
          <ShieldQuestion size={18} aria-hidden="true" />
          <div>
            <h3>No preview for this format</h3>
            <p>
              The file is listed with its hash and parse status. Download the
              read-only copy to inspect it in a dedicated tool.
            </p>
          </div>
        </div>
      );
    case "table":
      return view.table ? (
        <Paged
          offset={view.table.offset}
          count={view.table.items.length}
          total={view.table.total}
          limit={view.table.limit}
          noun="rows"
          onPage={onPage}
        >
          <TableView view={view} jump={jump} />
        </Paged>
      ) : null;
    default:
      return view.lines ? (
        <Paged
          offset={view.lines.offset}
          count={view.lines.items.length}
          total={view.lines.total}
          limit={view.lines.limit}
          noun={view.lines.unit === "paragraph" ? "paragraphs" : "lines"}
          onPage={onPage}
        >
          <LinesView view={view} jump={jump} />
        </Paged>
      ) : null;
  }
}

function Paged({
  offset,
  count,
  total,
  limit,
  noun,
  onPage,
  children,
}: {
  offset: number;
  count: number;
  total: number;
  limit: number;
  noun: string;
  onPage: (offset: number) => void;
  children: ReactNode;
}) {
  const partial = offset > 0 || offset + count < total;
  return (
    <div className="raw-paged">
      {partial && (
        <div className="raw-window-bar">
          <span>
            Showing {noun} {(offset + 1).toLocaleString()}–
            {(offset + count).toLocaleString()} of {total.toLocaleString()}
          </span>
          <button
            type="button"
            className="text-button"
            disabled={offset === 0}
            onClick={() => onPage(Math.max(0, offset - limit))}
          >
            <ChevronUp size={14} aria-hidden="true" /> Earlier
          </button>
          <button
            type="button"
            className="text-button"
            disabled={offset + count >= total}
            onClick={() => onPage(offset + count)}
          >
            <ChevronDown size={14} aria-hidden="true" /> Later
          </button>
        </div>
      )}
      {children}
    </div>
  );
}

/** Scrolls a highlighted index into view whenever `jump` changes or the window changes. */
function useScrollToIndex(
  scroller: React.RefObject<HTMLDivElement | null>,
  index: number | undefined,
  rowHeight: number | undefined,
  jump: number,
  windowKey: string,
) {
  useLayoutEffect(() => {
    const el = scroller.current;
    if (!el || index === undefined) return;
    if (rowHeight) {
      el.scrollTop = Math.max(0, index * rowHeight - el.clientHeight / 3);
    } else {
      const row = el.querySelector<HTMLElement>(`[data-index="${index}"]`);
      if (row)
        el.scrollTop = Math.max(
          0,
          row.offsetTop - el.clientHeight / 3 + row.offsetHeight / 2,
        );
    }
  }, [scroller, index, rowHeight, jump, windowKey]);
}

function useScrollState(scroller: React.RefObject<HTMLDivElement | null>) {
  const [state, setState] = useState({ top: 0, height: 600 });
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const update = () =>
      setState({ top: el.scrollTop, height: el.clientHeight });
    update();
    el.addEventListener("scroll", update, { passive: true });
    const observer =
      typeof ResizeObserver !== "undefined"
        ? new ResizeObserver(update)
        : undefined;
    observer?.observe(el);
    return () => {
      el.removeEventListener("scroll", update);
      observer?.disconnect();
    };
  }, [scroller]);
  return state;
}

function hitClass(
  ranges: ViewRange[],
  shared: ViewRange[],
  index: number,
): string {
  const hit = rangeAt(ranges, index);
  if (hit)
    return `is-cited${index === hit.start ? " is-cited-start" : ""}${index === hit.end ? " is-cited-end" : ""}`;
  return rangeAt(shared, index) ? "is-shared" : "";
}

type Span = { start: number; end: number; shared: boolean };

/** Column spans on one line: the cited record, and records sharing its label. */
function lineSpans(
  ranges: ViewRange[],
  shared: ViewRange[],
  index: number,
): Span[] {
  const spans: Span[] = [];
  for (const [list, isShared] of [
    [ranges, false],
    [shared, true],
  ] as const) {
    for (const r of list) {
      if (
        r.start === index &&
        r.colStart !== undefined &&
        r.colEnd !== undefined
      )
        spans.push({ start: r.colStart, end: r.colEnd, shared: isShared });
    }
  }
  return spans.sort((a, b) => a.start - b.start);
}

function MarkedText({ text, spans }: { text: string; spans: Span[] }) {
  if (!spans.length) return <>{text || " "}</>;
  const parts: ReactNode[] = [];
  let at = 0;
  spans.forEach((span, i) => {
    const start = Math.max(span.start, at);
    if (start >= span.end) return;
    if (start > at) parts.push(text.slice(at, start));
    parts.push(
      <mark key={i} className={span.shared ? "is-shared" : undefined}>
        {text.slice(start, span.end)}
      </mark>,
    );
    at = span.end;
  });
  parts.push(text.slice(at));
  return <>{parts}</>;
}

function LinesView({ view, jump }: { view: EvidenceView; jump: number }) {
  const lines = view.lines!;
  const ranges = view.target?.ranges ?? [];
  const shared = view.target?.sharedRanges ?? [];
  const virtual = lines.items.length > VIRTUALIZE_AFTER;
  const scroller = useRef<HTMLDivElement>(null);
  const { top, height } = useScrollState(scroller);
  const anchor = ranges[0]?.start;
  const local =
    anchor !== undefined &&
    anchor >= lines.offset &&
    anchor < lines.offset + lines.items.length
      ? anchor - lines.offset
      : undefined;
  useScrollToIndex(
    scroller,
    local,
    virtual ? LINE_HEIGHT : undefined,
    jump,
    `${view.evidenceId}:${lines.offset}`,
  );
  const slice = virtual
    ? visibleSlice(top, height, LINE_HEIGHT, lines.items.length)
    : { start: 0, end: lines.items.length };
  const gutter = `${String(lines.offset + lines.items.length).length + 1}ch`;
  return (
    <div
      ref={scroller}
      className={`raw-lines ${virtual ? "is-virtual" : ""} ${lines.unit === "paragraph" ? "is-paragraphs" : ""}`}
      style={{ "--gutter": gutter } as React.CSSProperties}
      tabIndex={0}
      role="region"
      aria-label={`${view.filename}, ${lines.total.toLocaleString()} ${lines.unit}s`}
    >
      {virtual && <div style={{ height: slice.start * LINE_HEIGHT }} />}
      {lines.items.slice(slice.start, slice.end).map((item, i) => {
        const local = slice.start + i;
        const index = lines.offset + local;
        const hit = rangeAt(ranges, index);
        const cls = hitClass(ranges, shared, index);
        return (
          <div
            key={item.n}
            className={`raw-line ${cls}`}
            data-index={local}
            aria-current={hit && index === hit.start ? "location" : undefined}
          >
            <span className="raw-gutter" aria-hidden="true">
              {item.label ?? item.n}
            </span>
            <span className="raw-text">
              <MarkedText
                text={item.text}
                spans={lineSpans(ranges, shared, index)}
              />
              {item.truncated && (
                <em className="raw-truncated"> … line shortened for display</em>
              )}
            </span>
          </div>
        );
      })}
      {virtual && (
        <div
          style={{ height: (lines.items.length - slice.end) * LINE_HEIGHT }}
        />
      )}
    </div>
  );
}

function TableView({ view, jump }: { view: EvidenceView; jump: number }) {
  const table = view.table!;
  const ranges = view.target?.ranges ?? [];
  const shared = view.target?.sharedRanges ?? [];
  const scroller = useRef<HTMLDivElement>(null);
  const { top, height } = useScrollState(scroller);
  const virtual = table.items.length > VIRTUALIZE_AFTER;
  const widths = useMemo(
    () => columnWidths(table.columns, table.items),
    [table.columns, table.items],
  );
  const gutter = String(table.offset + table.items.length + 1).length + 3;
  const template = `${gutter}ch ${widths.map((w) => `${w}ch`).join(" ")}`;
  const anchor = ranges[0]?.start;
  const local =
    anchor !== undefined &&
    anchor >= table.offset &&
    anchor < table.offset + table.items.length
      ? anchor - table.offset
      : undefined;
  useScrollToIndex(
    scroller,
    local,
    virtual ? ROW_HEIGHT : undefined,
    jump,
    `${view.evidenceId}:${table.offset}`,
  );
  // rows keep one line each, so the fixed height also holds when the list is not virtualized
  const slice = virtual
    ? visibleSlice(
        Math.max(0, top - ROW_HEIGHT),
        height,
        ROW_HEIGHT,
        table.items.length,
      )
    : { start: 0, end: table.items.length };
  return (
    <div
      ref={scroller}
      className="raw-table"
      role="table"
      aria-label={`${view.filename}, ${table.total.toLocaleString()} rows`}
      aria-rowcount={table.total + 1}
      tabIndex={0}
      style={{ "--cols": template } as React.CSSProperties}
    >
      <div className="raw-table-head" role="row" aria-rowindex={1}>
        <span role="columnheader" className="raw-gutter">
          Row
        </span>
        {table.columns.map((column, index) => (
          <span role="columnheader" key={`${column}-${index}`} title={column}>
            {column}
          </span>
        ))}
      </div>
      {virtual && <div style={{ height: slice.start * ROW_HEIGHT }} />}
      {table.items.slice(slice.start, slice.end).map((row, i) => {
        const local = slice.start + i;
        const index = table.offset + local;
        const hit = rangeAt(ranges, index);
        return (
          <div
            key={row.row}
            role="row"
            aria-rowindex={row.row}
            aria-current={hit && index === hit.start ? "location" : undefined}
            className={`raw-table-row ${hitClass(ranges, shared, index)}`}
            data-index={local}
          >
            <span
              role="rowheader"
              className="raw-gutter"
              title={
                row.line !== row.row ? `Starts on line ${row.line}` : undefined
              }
            >
              {row.row}
            </span>
            {row.cells.map((cell, c) => (
              <span
                role="cell"
                key={c}
                title={cell.length > widths[c] - 4 ? cell : undefined}
              >
                {cell}
              </span>
            ))}
          </div>
        );
      })}
      {virtual && (
        <div
          style={{ height: (table.items.length - slice.end) * ROW_HEIGHT }}
        />
      )}
    </div>
  );
}
