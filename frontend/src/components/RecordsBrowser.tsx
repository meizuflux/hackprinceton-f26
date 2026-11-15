import { Fragment, useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronRight as Expand,
  Files,
  PanelRightOpen,
  Search,
} from "lucide-react";
import { api } from "../api/client";
import type { CaseData, NormalizedEvidenceRecord } from "../api/types";
import { formatCaseTime } from "./presentation";
import { evidenceLink, groupFiles } from "./evidence-view";
import { casePath } from "../routing";
import "./raw-evidence.css";
import "./records-browser.css";

const PAGE = 100;

/** The route of a raw file at a citation, when the segment is a safe path segment. */
function rawHref(caseId: string, segment: string): string | undefined {
  try {
    return casePath(caseId, "evidence", segment);
  } catch {
    return undefined;
  }
}

/** Plain clicks navigate in place; modified clicks keep the browser's own behaviour. */
function followLink(
  event: React.MouseEvent<HTMLAnchorElement>,
  open: () => void,
) {
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  open();
}

/** Normalized ingestion records from the backend, filtered by evidence file and record type, paged. */
export function RecordsBrowser({
  data,
  onInspect,
  onOpenSource,
}: {
  data: CaseData;
  /** Opens the board's source inspector for a cited record. */
  onInspect: (sourceId: string) => void;
  /** Opens the raw file at a citation (`EV-xxx:locator`). */
  onOpenSource: (id: string) => void;
}) {
  const [evidenceId, setEvidenceId] = useState("");
  const [recordType, setRecordType] = useState("");
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  const files = useQuery({
    queryKey: ["files", data.id],
    queryFn: () => api.listFiles(data.id),
  });
  const page = useQuery({
    queryKey: ["records", data.id, evidenceId, recordType, offset],
    queryFn: () =>
      api.getRecords(data.id, {
        evidenceId: evidenceId || undefined,
        recordType: recordType || undefined,
        limit: PAGE,
        offset,
      }),
    placeholderData: keepPreviousData,
  });
  const groups = useMemo(() => groupFiles(files.data ?? []), [files.data]);
  const selectedFile = files.data?.find((f) => f.evidenceId === evidenceId);
  const types = page.data?.types ?? {};
  const total = page.data?.total ?? 0;
  const items = page.data?.items ?? [];
  const cited = items.filter(
    (record) =>
      record.citations.length > 0 &&
      record.citations.every((c) => c.evidenceId.trim() && c.locator.trim()),
  );
  const q = search.trim().toLowerCase();
  const visible = q
    ? cited.filter((record) =>
        JSON.stringify([
          record.id,
          record.recordType,
          record.fields,
          record.citations,
        ])
          .toLowerCase()
          .includes(q),
      )
    : cited;

  const resetTo = (next: () => void) => {
    next();
    setOffset(0);
    setExpanded(null);
  };

  return (
    <section className="records-view" aria-label="Generalized files">
      <header className="records-heading">
        <Files size={17} aria-hidden="true" />
        <h2>Generalized files</h2>
        <p className="records-summary">
          Normalized ingestion records · each cites its original file
        </p>
      </header>
      <div className="records-toolbar">
        <label className="records-field">
          <span>File</span>
          <select
            value={evidenceId}
            onChange={(event) =>
              resetTo(() => {
                setEvidenceId(event.target.value);
                setRecordType("");
              })
            }
          >
            <option value="">All files ({files.data?.length ?? "…"})</option>
            {groups.map((group) => (
              <optgroup key={group.folder} label={group.folder}>
                {group.files.map((file) => (
                  <option key={file.evidenceId} value={file.evidenceId}>
                    {file.evidenceId} · {file.filename} ({file.recordCount})
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
        <label className="records-field">
          <span>Record type</span>
          <select
            value={recordType}
            onChange={(event) =>
              resetTo(() => setRecordType(event.target.value))
            }
          >
            <option value="">
              All types (
              {Object.values(types)
                .reduce((sum, n) => sum + n, 0)
                .toLocaleString()}
              )
            </option>
            {Object.entries(types).map(([type, count]) => (
              <option key={type} value={type}>
                {type} ({count.toLocaleString()})
              </option>
            ))}
          </select>
        </label>
        <label className="records-search">
          <Search size={14} aria-hidden="true" />
          <input
            type="search"
            aria-label="Search records on this page"
            placeholder="Search this page…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
      </div>
      {selectedFile && (
        <p className="records-file">
          <span className="mono">{selectedFile.evidenceId}</span>{" "}
          {selectedFile.path} · {selectedFile.evidenceType} ·{" "}
          {selectedFile.parseStatus} ·{" "}
          {selectedFile.manifestMatch === true ? (
            "manifest hash matches"
          ) : selectedFile.manifestMatch === false ? (
            <span className="is-bad">manifest hash does not match</span>
          ) : (
            "no manifest hash"
          )}{" "}
          ·{" "}
          <a
            href={rawHref(data.id, selectedFile.evidenceId)}
            onClick={(event) =>
              followLink(event, () => onOpenSource(selectedFile.evidenceId))
            }
          >
            Open raw file
          </a>
        </p>
      )}
      <div className="records-table-wrap" aria-busy={page.isFetching}>
        {page.isPending ? (
          <div className="records-loading" aria-label="Loading records">
            {Array.from({ length: 10 }, (_, i) => (
              <div key={i} className="skeleton-bar" />
            ))}
          </div>
        ) : page.isError ? (
          <p className="records-empty" role="alert">
            Records could not be loaded: {page.error.message}{" "}
            <button
              type="button"
              className="text-button"
              onClick={() => void page.refetch()}
            >
              Try again
            </button>
          </p>
        ) : visible.length === 0 ? (
          <p className="records-empty">
            {q
              ? "No record on this page matches the search."
              : "No records for this filter."}
          </p>
        ) : (
          <table className="records-table">
            <thead>
              <tr>
                <th scope="col" aria-label="Details" />
                <th scope="col">Type</th>
                <th scope="col">Time ({data.timezone ?? "UTC"})</th>
                <th scope="col">Actor → target</th>
                <th scope="col">Content</th>
                <th scope="col">Source</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((record) => (
                <RecordRow
                  key={record.id}
                  caseId={data.id}
                  record={record}
                  timezone={data.timezone}
                  open={expanded === record.id}
                  onToggle={() =>
                    setExpanded((current) =>
                      current === record.id ? null : record.id,
                    )
                  }
                  knownSource={(id) =>
                    data.sources.some((source) => source.id === id)
                  }
                  onInspect={onInspect}
                  onOpenSource={onOpenSource}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>
      <footer className="records-pager">
        <span>
          {total > 0
            ? `${(offset + 1).toLocaleString()}–${(offset + items.length).toLocaleString()} of ${total.toLocaleString()} records`
            : "0 records"}
          {q && ` · ${visible.length} match on this page`}
        </span>
        <button
          type="button"
          className="text-button"
          disabled={offset === 0 || page.isFetching}
          onClick={() => {
            setOffset(Math.max(0, offset - PAGE));
            setExpanded(null);
          }}
        >
          <ChevronLeft size={15} aria-hidden="true" /> Previous
        </button>
        <button
          type="button"
          className="text-button"
          disabled={offset + items.length >= total || page.isFetching}
          onClick={() => {
            setOffset(offset + PAGE);
            setExpanded(null);
          }}
        >
          Next <ChevronRight size={15} aria-hidden="true" />
        </button>
      </footer>
    </section>
  );
}

function RecordRow({
  caseId,
  record,
  timezone,
  open,
  onToggle,
  knownSource,
  onInspect,
  onOpenSource,
}: {
  caseId: string;
  record: NormalizedEvidenceRecord;
  timezone?: string;
  open: boolean;
  onToggle: () => void;
  knownSource: (id: string) => boolean;
  onInspect: (sourceId: string) => void;
  onOpenSource: (id: string) => void;
}) {
  const f = record.fields;
  const time = f.ts_utc ?? f.ts_start_utc;
  const actor = f.actor ?? "";
  const target = f.target ?? "";
  const content = f.content ?? "";
  const detailId = `record-${record.id}-detail`;
  return (
    <Fragment>
      <tr className={open ? "is-open" : undefined}>
        <td className="records-toggle">
          <button
            type="button"
            className="icon-button"
            aria-expanded={open}
            aria-controls={detailId}
            aria-label={`${open ? "Hide" : "Show"} all fields of record ${record.id}`}
            onClick={onToggle}
          >
            {open ? (
              <ChevronDown size={14} aria-hidden="true" />
            ) : (
              <Expand size={14} aria-hidden="true" />
            )}
          </button>
        </td>
        <td className="records-type">{record.recordType}</td>
        <td className="records-time mono">
          {time
            ? formatCaseTime(String(time), timezone, "full")
            : f.ts_raw
              ? `“${f.ts_raw}” (not resolved)`
              : "—"}
        </td>
        <td className="records-who">
          {actor || target ? (
            <>
              {String(actor) || "—"}
              {target !== "" && (
                <>
                  {" "}
                  <span aria-label="to">→</span> {String(target)}
                </>
              )}
            </>
          ) : (
            "—"
          )}
        </td>
        <td className="records-content" title={String(content)}>
          {String(content) || "—"}
        </td>
        <td className="records-source">
          {record.citations.map((citation, index) => {
            const segment = evidenceLink(citation.evidenceId, citation.locator);
            const href = rawHref(caseId, segment);
            return (
              <span key={index} className="records-citation">
                {href ? (
                  <a
                    href={href}
                    className="mono"
                    title="Open the raw file at this record"
                    onClick={(event) =>
                      followLink(event, () => onOpenSource(segment))
                    }
                  >
                    {citation.evidenceId} · {citation.locator}
                  </a>
                ) : (
                  <span className="mono">
                    {citation.evidenceId} · {citation.locator}
                  </span>
                )}
                {citation.sourceId && knownSource(citation.sourceId) && (
                  <button
                    type="button"
                    className="records-board-link"
                    title="Cited on the board: open the source inspector"
                    aria-label={`Inspect ${citation.sourceId} in the source inspector`}
                    onClick={() => onInspect(citation.sourceId!)}
                  >
                    <PanelRightOpen size={13} aria-hidden="true" /> On board
                  </button>
                )}
              </span>
            );
          })}
        </td>
      </tr>
      {open && (
        <tr className="records-detail" id={detailId}>
          <td />
          <td colSpan={5}>
            <dl>
              <div>
                <dt>record</dt>
                <dd className="mono">{record.id}</dd>
              </div>
              {Object.entries(f).map(([key, value]) => (
                <div
                  key={key}
                  className={key === "content" ? "is-wide" : undefined}
                >
                  <dt>{key}</dt>
                  <dd>{value === null ? "—" : String(value)}</dd>
                </div>
              ))}
            </dl>
          </td>
        </tr>
      )}
    </Fragment>
  );
}
