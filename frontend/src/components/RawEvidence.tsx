import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FileSearch, Search, ShieldAlert, ShieldCheck } from "lucide-react";
import { api } from "../api/client";
import type { CaseData, EvidenceFile } from "../api/types";
import { EvidenceFileViewer } from "./EvidenceFileViewer";
import { FileKindIcon } from "./FileKindIcon";
import { groupFiles, matchesFile, parseEvidenceTarget } from "./evidence-view";
import "./raw-evidence.css";

/**
 * Raw evidence: every ingested file, grouped by the folder it was submitted in, and a viewer that opens the
 * read-only copy at the cited row or line. `/evidence/:sourceId` selects the file and citation.
 */
export function RawEvidence({
  data,
  sourceId,
  onOpen,
  onInspectSource,
}: {
  data: CaseData;
  sourceId?: string;
  /** Navigates to `/evidence/:id` (a file ID, or a citation `EV-xxx:locator`). */
  onOpen: (id: string) => void;
  onInspectSource?: (sourceId: string) => void;
}) {
  const [search, setSearch] = useState("");
  const files = useQuery({
    queryKey: ["files", data.id],
    queryFn: () => api.listFiles(data.id),
  });
  const target = useMemo(
    () => (sourceId ? parseEvidenceTarget(sourceId, data.sources) : undefined),
    [sourceId, data.sources],
  );
  useEffect(() => {
    if (sourceId) setSearch("");
  }, [sourceId]);

  const all = files.data ?? [];
  const visible = useMemo(
    () => all.filter((file) => matchesFile(file, search)),
    [all, search],
  );
  const groups = useMemo(() => groupFiles(visible), [visible]);
  const matched = all.filter((f) => f.manifestMatch === true).length;
  const mismatched = all.filter((f) => f.manifestMatch === false).length;
  const citedCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const source of data.sources) {
      const ev = source.metadata?.evidence_id;
      if (ev) counts.set(ev, (counts.get(ev) ?? 0) + 1);
    }
    return counts;
  }, [data.sources]);

  return (
    <section className="raw-evidence" aria-label="Raw evidence files">
      <header className="raw-evidence-heading">
        <FileSearch size={17} aria-hidden="true" />
        <h2>Raw evidence</h2>
        {files.data && (
          <p className="raw-evidence-summary">
            {all.length} files ·{" "}
            {mismatched > 0 ? (
              <span className="is-bad">
                {mismatched} manifest {mismatched === 1 ? "hash" : "hashes"}{" "}
                mismatched
              </span>
            ) : (
              `${matched} manifest hashes match`
            )}{" "}
            · read-only copies
          </p>
        )}
      </header>
      <div className="raw-evidence-layout">
        <nav className="raw-files" aria-label="Evidence files">
          <label className="raw-search">
            <Search size={14} aria-hidden="true" />
            <input
              type="search"
              aria-label="Search evidence files"
              placeholder="Filter by name, ID, type…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <div className="raw-file-groups">
            {files.isPending && <FileListSkeleton />}
            {files.isError && (
              <p className="raw-files-empty" role="alert">
                The file inventory could not be loaded.{" "}
                <button
                  type="button"
                  className="text-button"
                  onClick={() => void files.refetch()}
                >
                  Try again
                </button>
              </p>
            )}
            {files.data && visible.length === 0 && (
              <p className="raw-files-empty">
                {all.length === 0
                  ? "This case has no ingested files."
                  : `No file matches “${search}”.`}
              </p>
            )}
            {groups.map((group) => (
              <section key={group.folder} className="raw-file-group">
                <h3>
                  {group.folder}
                  <span>{group.files.length}</span>
                </h3>
                <ul>
                  {group.files.map((file) => (
                    <FileRow
                      key={file.evidenceId}
                      file={file}
                      cited={citedCounts.get(file.evidenceId) ?? 0}
                      selected={target?.evidenceId === file.evidenceId}
                      onOpen={() => onOpen(file.evidenceId)}
                    />
                  ))}
                </ul>
              </section>
            ))}
          </div>
        </nav>
        <div className="raw-viewer-pane">
          {target ? (
            <EvidenceFileViewer
              caseId={data.id}
              target={target}
              onInspectSource={
                target.sourceId &&
                data.sources.some((source) => source.id === target.sourceId)
                  ? onInspectSource
                  : undefined
              }
            />
          ) : (
            <div className="raw-viewer-intro">
              <h3>Open a file, or follow a citation</h3>
              <p>
                Choose a file to read its stored copy. Citations on the board,
                in insights and in chat open the same viewer at the cited row or
                line, highlighted.
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function FileRow({
  file,
  cited,
  selected,
  onOpen,
}: {
  file: EvidenceFile;
  cited: number;
  selected: boolean;
  onOpen: () => void;
}) {
  const ref = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (selected) ref.current?.scrollIntoView({ block: "nearest" });
  }, [selected]);
  const nested = file.path.includes("::");
  return (
    <li>
      <button
        ref={ref}
        type="button"
        className="raw-file"
        aria-current={selected ? "true" : undefined}
        onClick={onOpen}
        title={file.path}
      >
        <FileKindIcon format={file.format} />
        <span className="raw-file-name">
          {file.filename}
          {nested && (
            <small> in {file.path.split("::")[0].split("/").at(-1)}</small>
          )}
        </span>
        <span className="raw-file-check">
          {file.manifestMatch === true ? (
            <ShieldCheck size={13} aria-label="Manifest hash matches" />
          ) : file.manifestMatch === false ? (
            <ShieldAlert
              size={13}
              className="is-bad"
              aria-label="Manifest hash does not match"
            />
          ) : null}
        </span>
        <span className="raw-file-meta">
          <span className="mono">{file.evidenceId}</span>
          <span>{file.evidenceType}</span>
          {file.parseStatus !== "parsed" && (
            <span className="raw-file-status">{file.parseStatus}</span>
          )}
          {cited > 0 && <span>{cited} cited</span>}
        </span>
      </button>
    </li>
  );
}

function FileListSkeleton() {
  return (
    <div className="raw-file-skeleton" aria-label="Loading files">
      {Array.from({ length: 8 }, (_, i) => (
        <div key={i} className="skeleton-bar" />
      ))}
    </div>
  );
}
