import { useEffect, useMemo, useState } from "react";
import { FileSearch, Files, Search, ShieldAlert } from "lucide-react";
import type { CaseData } from "../api/types";
import { listEvidenceFiles, type NormalizedEvidenceRecord } from "../api/files";
import "./evidence-browser.css";

export type EvidenceBrowserProps = {
  data: CaseData;
  mode: "raw" | "generalized";
  selectedSourceId?: string;
  onInspect: (sourceId: string) => void;
  generalizedRecords?: NormalizedEvidenceRecord[];
};

export function EvidenceBrowser({
  data,
  mode,
  selectedSourceId,
  onInspect,
  generalizedRecords = [],
}: EvidenceBrowserProps) {
  const [search, setSearch] = useState("");
  const [activeSourceId, setActiveSourceId] = useState(selectedSourceId);
  const files = useMemo(() => listEvidenceFiles(data), [data]);
  useEffect(() => {
    setActiveSourceId(selectedSourceId);
    if (selectedSourceId) setSearch("");
  }, [selectedSourceId]);
  const normalizedSearch = search.trim().toLowerCase();
  const visibleFiles = useMemo(
    () =>
      normalizedSearch
        ? files.filter((file) =>
            `${file.path} ${file.kind} ${file.id} ${file.excerpt}`
              .toLowerCase()
              .includes(normalizedSearch),
          )
        : files,
    [files, normalizedSearch],
  );
  const citedRecords = useMemo(
    () =>
      generalizedRecords.filter(
        (record) =>
          record.citations.length > 0 &&
          record.citations.every(
            (citation) => citation.evidenceId.trim() && citation.locator.trim(),
          ),
      ),
    [generalizedRecords],
  );
  const visibleRecords = useMemo(
    () =>
      normalizedSearch
        ? citedRecords.filter((record) =>
            JSON.stringify(record).toLowerCase().includes(normalizedSearch),
          )
        : citedRecords,
    [citedRecords, normalizedSearch],
  );

  if (mode === "generalized") {
    return (
      <section className="evidence-browser" aria-label="Generalized files">
        <header className="evidence-browser-heading">
          <div className="evidence-browser-icon">
            <Files size={17} />
          </div>
          <div>
            <h2>Generalized files</h2>
          </div>
          <span className="evidence-state-chip">
            {citedRecords.length
              ? `${citedRecords.length} normalized records`
              : "Unavailable in mock"}
          </span>
        </header>
        <label className="evidence-search">
          <Search size={15} aria-hidden="true" />
          <input
            type="search"
            aria-label="Search normalized records"
            placeholder="Search records, fields, source IDs…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        {generalizedRecords.length > 0 ? (
          <div className="normalized-records" aria-label="Normalized records">
            <p className="normalized-records-intro">
              Parsed ingestion records · original source citations are retained
            </p>
            {visibleRecords.length === 0 && (
              <p className="evidence-no-results">
                No cited records match this search.
              </p>
            )}
            {visibleRecords.map((record) => (
              <article className="normalized-record" key={record.id}>
                <header>
                  <span>{record.recordType}</span>
                  <code>{record.id}</code>
                </header>
                <dl>
                  {Object.entries(record.fields).map(([key, value]) => (
                    <div key={key}>
                      <dt>{key}</dt>
                      <dd>{value === null ? "—" : String(value)}</dd>
                    </div>
                  ))}
                </dl>
                <footer>
                  <span>Source citations</span>
                  {record.citations.map((citation, index) => {
                    const sourceId = citation.sourceId;
                    const knownSource =
                      sourceId &&
                      data.sources.some((source) => source.id === sourceId);
                    return knownSource ? (
                      <button
                        type="button"
                        key={index}
                        onClick={() => onInspect(sourceId)}
                      >
                        {citation.evidenceId} · {citation.locator}
                      </button>
                    ) : (
                      <span key={index}>
                        {citation.evidenceId} · {citation.locator}
                      </span>
                    );
                  })}
                </footer>
              </article>
            ))}
          </div>
        ) : (
          <div className="evidence-empty-state">
            <div className="evidence-empty-icon">
              <ShieldAlert size={22} />
            </div>
            <h3>No normalized records are available</h3>
            <p>
              This workspace has no backend ingestion output connected. Parsed
              records, extracted fields, and normalization details will appear
              here when the ingestion API provides them.
            </p>
            <div
              className="evidence-record-preview"
              aria-label="Record format preview"
            >
              <span>EXPECTED RECORD FIELDS</span>
              <code>record type · values · source locator</code>
              <small>
                Format guidance only; no case records are being shown.
              </small>
            </div>
          </div>
        )}
      </section>
    );
  }

  return (
    <section className="evidence-browser" aria-label="Raw evidence files">
      <header className="evidence-browser-heading">
        <div className="evidence-browser-icon">
          <FileSearch size={17} />
        </div>
        <div>
          <h2>Raw evidence</h2>
        </div>
        <span className="evidence-state-chip">
          {files.length} cited sources
        </span>
      </header>
      <label className="evidence-search">
        <Search size={15} aria-hidden="true" />
        <input
          type="search"
          aria-label="Search raw evidence sources"
          placeholder="Search files, IDs, excerpts…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </label>
      <div className="evidence-browser-layout">
        <div
          className="evidence-file-list"
          role="list"
          aria-label="Cited source list"
        >
          {visibleFiles.map((file) => (
            <div role="listitem" key={file.id}>
              <button
                type="button"
                className={`evidence-file-row ${activeSourceId === file.id ? "selected" : ""}`}
                aria-current={activeSourceId === file.id ? "true" : undefined}
                onClick={() => {
                  setActiveSourceId(file.id);
                  onInspect(file.id);
                }}
              >
                <span className="evidence-file-mark">
                  {file.kind.slice(0, 2).toUpperCase()}
                </span>
                <span className="evidence-file-copy">
                  <strong>{file.filename}</strong>
                  <small>{file.path}</small>
                  <span className="evidence-file-meta">
                    {file.id} · {file.citationCount} links
                  </span>
                </span>
              </button>
            </div>
          ))}
          {visibleFiles.length === 0 && (
            <p className="evidence-no-results">
              No cited sources match this search.
            </p>
          )}
        </div>
        <div className="evidence-preview" aria-live="polite">
          {(() => {
            const selected =
              files.find((file) => file.id === activeSourceId) ??
              (activeSourceId ? undefined : visibleFiles[0]);
            if (!selected)
              return (
                <p className="evidence-preview-placeholder">
                  {activeSourceId
                    ? `Source ${activeSourceId} is not available in this case.`
                    : "Choose a source to inspect its available citation."}
                </p>
              );
            return (
              <>
                <div className="evidence-preview-topline">
                  <span className="evidence-source-id">{selected.id}</span>
                  <span className="evidence-fiction-label">
                    FICTIONAL EXCERPT
                  </span>
                </div>
                <h3>{selected.filename}</h3>
                <p className="evidence-path">{selected.path}</p>
                <blockquote>{selected.excerpt}</blockquote>
                <dl className="evidence-details">
                  <div>
                    <dt>Source type</dt>
                    <dd>{selected.kind}</dd>
                  </div>
                  <div>
                    <dt>Timestamp</dt>
                    <dd>{selected.timestamp}</dd>
                  </div>
                  <div>
                    <dt>Illustrative hash</dt>
                    <dd>
                      <code>{selected.hash}</code>
                    </dd>
                  </div>
                  <div>
                    <dt>Graph and analysis links</dt>
                    <dd>{selected.citationCount}</dd>
                  </div>
                </dl>
                <div className="evidence-unavailable">
                  <ShieldAlert size={15} />
                  <span>
                    <strong>Original file unavailable.</strong> The mock upload
                    does not read ZIP contents; this excerpt is synthetic and
                    cannot open or download source bytes.
                  </span>
                </div>
              </>
            );
          })()}
        </div>
      </div>
    </section>
  );
}
