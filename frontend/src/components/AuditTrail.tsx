import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Check,
  History,
  Search,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { api, isMock } from "../api/client";
import type { AuditChainEntry, CaseData } from "../api/types";
import { formatCaseTime } from "./presentation";
import "./audit-trail.css";

type SourceFilter = "all" | AuditChainEntry["source"];

const sourceLabel: Record<AuditChainEntry["source"], string> = {
  ingest: "Ingestion",
  analysis: "Analysis",
};

/** Hashes are shown shortened; the full value is in the title and copyable. */
const shortHash = (hash: string) => `${hash.slice(0, 12)}…`;
const words = (value: string) => value.replace(/_/g, " ");

/**
 * The audit trail: every ingestion and analysis step from the backend's
 * hash-chained audit log, with the backend's verification result. Each entry
 * shows its own hash and the hash it chains from, so the chain reads top to
 * bottom. Nothing here is recomputed; the frontend only lists and filters.
 */
export function AuditTrail({
  data,
  onOpenEvidence,
  onInspectSource,
}: {
  data: CaseData;
  /** Opens a raw evidence file by its manifest evidence ID. */
  onOpenEvidence: (evidenceId: string) => void;
  /** Opens a cited source in the section inspector (mock audit records). */
  onInspectSource: (sourceId: string) => void;
}) {
  const chain = useQuery({
    queryKey: ["audit-chain", data.id],
    queryFn: () => api.getAuditChain(data.id),
    enabled: !isMock,
  });
  const files = useQuery({
    queryKey: ["files", data.id],
    queryFn: () => api.listFiles(data.id),
    enabled: !isMock,
  });
  const evidenceByFile = useMemo(
    () =>
      new Map((files.data ?? []).map((file) => [file.fileId, file.evidenceId])),
    [files.data],
  );
  const [source, setSource] = useState<SourceFilter>("all");
  const [search, setSearch] = useState("");

  const entries = chain.data?.entries ?? [];
  const counts = useMemo(
    () => ({
      all: entries.length,
      ingest: entries.filter((entry) => entry.source === "ingest").length,
      analysis: entries.filter((entry) => entry.source === "analysis").length,
    }),
    [entries],
  );
  const visible = useMemo(() => {
    const query = search.trim().toLowerCase();
    return entries.filter(
      (entry) =>
        (source === "all" || entry.source === source) &&
        (!query ||
          `${entry.stage} ${entry.action} ${words(entry.action)} ${entry.hash} ${JSON.stringify(entry.detail)}`
            .toLowerCase()
            .includes(query)),
    );
  }, [entries, source, search]);

  const showChain = !isMock && !!chain.data;

  return (
    <section className="audit-trail" aria-label="Audit trail">
      <header className="audit-trail-heading">
        <History size={17} aria-hidden="true" />
        <h2>Audit trail</h2>
        <p className="audit-trail-summary">
          {showChain
            ? `${entries.length} hash-chained steps from ingestion and analysis`
            : `${data.audit.length} recorded steps`}
        </p>
      </header>
      {chain.data && (
        <div
          className={`audit-chain ${chain.data.verified ? "verified" : "failed"}`}
          role="status"
        >
          <div className="audit-chain-status">
            {chain.data.verified ? (
              <ShieldCheck size={16} aria-hidden="true" />
            ) : (
              <ShieldAlert size={16} aria-hidden="true" />
            )}
            <strong>
              {chain.data.verified
                ? "Audit chain verified"
                : "Audit chain verification failed"}
            </strong>
            <span>
              head{" "}
              <code title={chain.data.head}>{shortHash(chain.data.head)}</code>
            </span>
          </div>
          <ul>
            {chain.data.checks.map((check) => (
              <li key={check.message} className={check.ok ? "" : "bad"}>
                {check.ok ? "✓" : "✗"} {check.message}
              </li>
            ))}
          </ul>
        </div>
      )}
      {chain.isError && (
        <p className="error-message audit-chain-error" role="alert">
          Could not verify the audit chain: {chain.error.message}
        </p>
      )}
      {showChain ? (
        <>
          <div className="audit-toolbar">
            <div
              className="audit-filter"
              role="group"
              aria-label="Audit log source"
            >
              {(["all", "ingest", "analysis"] as const).map((id) => (
                <button
                  key={id}
                  type="button"
                  aria-pressed={source === id}
                  onClick={() => setSource(id)}
                >
                  {id === "all" ? "All" : sourceLabel[id]}
                  <span>{counts[id]}</span>
                </button>
              ))}
            </div>
            <label className="audit-search">
              <Search size={14} aria-hidden="true" />
              <input
                type="search"
                aria-label="Filter audit steps"
                placeholder="Filter by step, hash or detail…"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </label>
          </div>
          <p className="audit-chain-note">
            Each step records the hash of the step before it, so changing any
            step breaks every hash after it. The analysis log continues from the
            ingestion head.
          </p>
          <ol className="audit-chain-list">
            {visible.map((entry) => {
              const evidenceId =
                entry.fileId != null
                  ? evidenceByFile.get(entry.fileId)
                  : undefined;
              return (
                <li
                  key={`${entry.source}-${entry.seq}`}
                  className="audit-entry"
                  data-source={entry.source}
                >
                  <span className="audit-entry-seq">#{entry.seq}</span>
                  <div className="audit-entry-body">
                    <div className="audit-entry-title">
                      <h3>
                        <span>{words(entry.stage)}</span> ·{" "}
                        {words(entry.action)}
                      </h3>
                      <span className="audit-entry-source">
                        {sourceLabel[entry.source]}
                      </span>
                      <time dateTime={entry.time}>
                        {formatCaseTime(entry.time, data.timezone)}
                      </time>
                    </div>
                    <div className="audit-entry-actions">
                      <p className="audit-entry-hashes">
                        <span title={entry.prevHash}>
                          <span className="audit-hash-label">prev</span>{" "}
                          {shortHash(entry.prevHash)}
                        </span>
                        <span aria-hidden="true">→</span>
                        <span title={entry.hash}>
                          <span className="audit-hash-label">hash</span>{" "}
                          {shortHash(entry.hash)}
                        </span>
                      </p>
                      {evidenceId && (
                        <button
                          type="button"
                          className="audit-cite"
                          onClick={() => onOpenEvidence(evidenceId)}
                        >
                          {evidenceId} <ArrowUpRight size={11} />
                        </button>
                      )}
                      {Object.keys(entry.detail).length > 0 && (
                        <details>
                          <summary>Details</summary>
                          <AuditFields value={entry.detail} />
                        </details>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
          {visible.length === 0 && (
            <p className="audit-empty">No steps match this filter.</p>
          )}
        </>
      ) : !chain.isPending || isMock ? (
        <div className="audit-steps">
          {data.audit.map((step) => (
            <div className="audit-step" key={step.id}>
              <Check size={13} aria-hidden="true" />
              <time dateTime={step.time}>
                {formatCaseTime(step.time, data.timezone)}
              </time>
              <h3>{step.title}</h3>
              <AuditDescription text={step.description} />
              {step.citations.map((id) => (
                <button
                  key={id}
                  type="button"
                  className="audit-cite"
                  onClick={() => onInspectSource(id)}
                >
                  {data.sources
                    .find((s) => s.id === id)
                    ?.path.split("/")
                    .pop() ?? id}{" "}
                  <ArrowUpRight size={11} />
                </button>
              ))}
            </div>
          ))}
        </div>
      ) : (
        <p className="audit-empty" role="status">
          Loading the audit chain…
        </p>
      )}
    </section>
  );
}

/** Step payload as labelled fields, long hashes shortened (full value on hover). */
function AuditFields({ value }: { value: Record<string, unknown> }) {
  const fields = Object.entries(value).map(([key, field]) => [
    words(key),
    field === null
      ? "none"
      : typeof field === "object"
        ? JSON.stringify(field)
        : String(field),
  ]);
  return (
    <dl className="audit-fields">
      {fields.map(([key, text]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd title={text.length > 24 ? text : undefined}>
            {/^[0-9a-f]{32,}$/i.test(text) ? `${text.slice(0, 16)}…` : text}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * Audit records carry their step payload as JSON. Show it as labelled fields
 * instead of a raw JSON string; anything else is shown as written.
 */
function AuditDescription({ text }: { text: string }) {
  if (text.trim().startsWith("{")) {
    try {
      const parsed: unknown = JSON.parse(text);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed))
        return <AuditFields value={parsed as Record<string, unknown>} />;
    } catch {
      // Not JSON: show as written.
    }
  }
  return <p>{text}</p>;
}
