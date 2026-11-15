import { useCallback, useMemo, useState } from "react";
import {
  ArrowUpRight,
  FileText,
  GitBranch,
  Lightbulb,
  Scale,
  Search,
  ShieldCheck,
  Target,
} from "lucide-react";
import type { CaseData, ExplanationSet } from "../api/types";
import { insightKind, insightStrength, scoreLabel } from "./presentation";
import type { Selection } from "./Inspector";
import "./insights-page.css";

export function InsightsPage({
  data,
  onInspect,
  onOpenSource,
  onFocusOnBoard,
}: {
  data: CaseData;
  onInspect: (selection: Selection) => void;
  onOpenSource: (sourceId: string) => void;
  onFocusOnBoard?: (selection: Selection) => void;
}) {
  const [search, setSearch] = useState("");
  const query = search.trim().toLocaleLowerCase();
  const sourceById = useMemo(
    () => new Map(data.sources.map((source) => [source.id, source])),
    [data.sources],
  );
  const matches = useCallback(
    (values: string[]) =>
      !query ||
      values.some((value) => value.toLocaleLowerCase().includes(query)),
    [query],
  );
  const insights = useMemo(
    () =>
      data.insights.filter((item) =>
        matches([item.title, item.text, ...item.citations]),
      ),
    [data.insights, matches],
  );
  const gaps = useMemo(
    () =>
      data.gaps.filter((item) =>
        matches([item.title, item.description, ...item.citations]),
      ),
    [data.gaps, matches],
  );
  const suggestions = useMemo(
    () =>
      data.suggestions.filter((item) =>
        matches([item.title, item.description, item.query, ...item.citations]),
      ),
    [data.suggestions, matches],
  );

  return (
    <div className="insights-page">
      <header className="insights-hero">
        <div className="insights-hero-row">
          <div>
            <h1>Insights</h1>
            <p>
              Review possible connections, open questions, and the evidence that
              supports each one.
            </p>
          </div>
          <label className="insights-search">
            <Search size={16} aria-hidden="true" />
            <span className="sr-only">
              Search insights, gaps, and next evidence
            </span>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search analysis"
            />
          </label>
        </div>
        <div className="insights-caution">
          <ShieldCheck size={16} />
          <span>
            Insights are inferences that need verification. A gap is a question
            about missing evidence, not proof of an event.
          </span>
        </div>
      </header>

      {(data.explanations ?? []).map((set) => (
        <ExplanationsSection
          key={set.episode}
          set={set}
          sourceById={sourceById}
          onOpenSource={onOpenSource}
        />
      ))}

      {data.contradictions && data.contradictions.length > 0 && (
        <section
          className="insights-section"
          aria-labelledby="contradictions-heading"
        >
          <div className="insights-section-heading">
            <div>
              <span className="insights-section-icon inference-icon">
                <Scale size={16} />
              </span>
              <div>
                <h2 id="contradictions-heading">Contradictions</h2>
                <p>
                  Accounts and records that disagree · each has several possible
                  reasons
                </p>
              </div>
            </div>
            <span className="insights-count">{data.contradictions.length}</span>
          </div>
          <div className="insights-grid">
            {data.contradictions
              .filter((item) =>
                matches([item.title, item.text, ...item.citations]),
              )
              .map((item) => (
                <article className="insight-page-card" key={item.id}>
                  <div className="insight-card-main as-static">
                    <div className="insight-card-label">
                      <span>{humanize(item.kind)}</span>
                      <span className="illustrative-score">
                        {humanize(item.severity)} severity
                      </span>
                    </div>
                    <h3>{item.title}</h3>
                    <p>{item.text}</p>
                    <h4>Possible reasons</h4>
                    <ul>
                      {item.possibleReasons.map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                    {item.resolvingEvidence.length > 0 && (
                      <p className="explanation-meta">
                        Would resolve it:{" "}
                        {item.resolvingEvidence.map(humanize).join(", ")}
                      </p>
                    )}
                  </div>
                  <CitationLinks
                    ids={item.citations}
                    sourceById={sourceById}
                    onOpenSource={onOpenSource}
                  />
                </article>
              ))}
          </div>
        </section>
      )}

      <section
        className="insights-section"
        aria-labelledby="inferences-heading"
      >
        <div className="insights-section-heading">
          <div>
            <span className="insights-section-icon inference-icon">
              <Lightbulb size={16} />
            </span>
            <div>
              <h2 id="inferences-heading">Possible connections</h2>
              <p>Inferences · review against cited source material</p>
            </div>
          </div>
          <span className="insights-count">{insights.length}</span>
        </div>
        {insights.length ? (
          <div className="insights-grid">
            {insights.map((item) => (
              <article className="insight-page-card" key={item.id}>
                <button
                  className="insight-card-main"
                  onClick={() => onInspect({ kind: "insight", id: item.id })}
                >
                  <div className="insight-card-label">
                    <span>{insightKind(item)}</span>
                    <span className="illustrative-score">
                      {insightStrength(item)}
                    </span>
                  </div>
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                  <div className="insight-card-footer-actions">
                    <span className="insight-card-action">
                      Inspect inference <ArrowUpRight size={14} />
                    </span>
                    {onFocusOnBoard && (
                      <span
                        role="button"
                        tabIndex={0}
                        className="insight-board-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          onFocusOnBoard({ kind: "insight", id: item.id });
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            e.stopPropagation();
                            onFocusOnBoard({ kind: "insight", id: item.id });
                          }
                        }}
                      >
                        <GitBranch size={13} aria-hidden="true" /> View on mind
                        map
                      </span>
                    )}
                  </div>
                </button>
                <CitationLinks
                  ids={item.citations}
                  sourceById={sourceById}
                  onOpenSource={onOpenSource}
                />
              </article>
            ))}
          </div>
        ) : (
          <EmptyState query={query} label="inferences" />
        )}
      </section>

      <section className="insights-section" aria-labelledby="gaps-heading">
        <div className="insights-section-heading">
          <div>
            <span className="insights-section-icon question-icon">
              <ShieldCheck size={16} />
            </span>
            <div>
              <h2 id="gaps-heading">Questions to verify</h2>
              <p>Evidence gaps · absence is not proof</p>
            </div>
          </div>
          <span className="insights-count">{gaps.length}</span>
        </div>
        {gaps.length ? (
          <div className="insights-grid">
            {gaps.map((item) => (
              <article
                className="insight-page-card gap-page-card"
                key={item.id}
              >
                <button
                  className="insight-card-main"
                  onClick={() => onInspect({ kind: "gap", id: item.id })}
                >
                  <div className="insight-card-label">
                    <span>Question to verify</span>
                    <span className="illustrative-score">
                      {scoreLabel(item.score, "rank")}
                    </span>
                  </div>
                  <h3>{item.title}</h3>
                  <p>{item.description}</p>
                  <div className="insight-card-footer-actions">
                    <span className="insight-card-action">
                      Inspect gap <ArrowUpRight size={14} />
                    </span>
                    {onFocusOnBoard && (
                      <span
                        role="button"
                        tabIndex={0}
                        className="insight-board-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          onFocusOnBoard({ kind: "gap", id: item.id });
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            e.stopPropagation();
                            onFocusOnBoard({ kind: "gap", id: item.id });
                          }
                        }}
                      >
                        <GitBranch size={13} aria-hidden="true" /> View on mind
                        map
                      </span>
                    )}
                  </div>
                </button>
                <CitationLinks
                  ids={item.citations}
                  sourceById={sourceById}
                  onOpenSource={onOpenSource}
                />
              </article>
            ))}
          </div>
        ) : (
          <EmptyState query={query} label="questions" />
        )}
      </section>

      <section
        className="insights-section"
        aria-labelledby="next-evidence-heading"
      >
        <div className="insights-section-heading">
          <div>
            <span className="insights-section-icon next-icon">
              <Target size={16} />
            </span>
            <div>
              <h2 id="next-evidence-heading">Suggested next evidence</h2>
              <p>Possible follow-up requests · not findings</p>
            </div>
          </div>
          <span className="insights-count">{suggestions.length}</span>
        </div>
        {suggestions.length ? (
          <div className="insights-grid">
            {suggestions.map((item, index) => (
              <article
                className="insight-page-card suggestion-page-card"
                key={item.id}
              >
                <button
                  className="insight-card-main"
                  onClick={() => onInspect({ kind: "suggestion", id: item.id })}
                >
                  <div className="insight-card-label">
                    <span>Suggested request · {index + 1}</span>
                    <span className="illustrative-score">
                      Priority {item.priority}
                    </span>
                  </div>
                  <h3>{item.title}</h3>
                  <p>{item.description}</p>
                  <span className="insight-card-action">
                    Inspect suggestion <ArrowUpRight size={14} />
                  </span>
                </button>
                <CitationLinks
                  ids={item.citations}
                  sourceById={sourceById}
                  onOpenSource={onOpenSource}
                />
              </article>
            ))}
          </div>
        ) : (
          <EmptyState query={query} label="suggestions" />
        )}
      </section>
    </div>
  );
}

function CitationLinks({
  ids,
  sourceById,
  onOpenSource,
}: {
  ids: string[];
  sourceById: Map<string, CaseData["sources"][number]>;
  onOpenSource: (sourceId: string) => void;
}) {
  const sources = ids
    .map((id) => sourceById.get(id))
    .filter((source): source is CaseData["sources"][number] => Boolean(source));
  return (
    <div className="insight-citations">
      <span>
        <FileText size={13} /> Original sources · {sources.length}
      </span>
      {sources.length > 0 && (
        <div>
          {sources.map((source) => (
            <button
              key={source.id}
              title={`${source.id} · ${source.path}`}
              onClick={() => onOpenSource(source.id)}
            >
              {source.id}
              <ArrowUpRight size={11} />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function EmptyState({ query, label }: { query: string; label: string }) {
  return (
    <div className="insights-empty">
      {query
        ? `No ${label} match “${query}”.`
        : `No ${label} available for this case.`}
    </div>
  );
}

function ExplanationsSection({
  set,
  sourceById,
  onOpenSource,
}: {
  set: ExplanationSet;
  sourceById: Map<string, CaseData["sources"][number]>;
  onOpenSource: (sourceId: string) => void;
}) {
  return (
    <section
      className="insights-section explanations-section"
      aria-label={`Competing explanations: ${set.episode}`}
    >
      <div className="insights-section-heading">
        <div>
          <span className="insights-section-icon next-icon">
            <GitBranch size={16} />
          </span>
          <div>
            <h2>Competing explanations · {set.episode}</h2>
            <p>
              Scored from supporting and contradicting records, capped by
              independent sources · inference, not a finding
            </p>
          </div>
        </div>
        <span className="insights-count">{set.hypotheses.length}</span>
      </div>
      <p className={`explanation-verdict ${set.decided ? "decided" : ""}`}>
        <strong>{set.decided ? "Best supported" : "Undecided"}:</strong>{" "}
        {set.verdict}
      </p>
      <div className="insights-grid">
        {set.hypotheses.map((hypothesis) => {
          const supporting = dedupe(hypothesis.supporting);
          const contradicting = dedupe(hypothesis.contradicting);
          return (
            <article className="insight-page-card" key={hypothesis.id}>
              <div className="insight-card-main as-static">
                <div className="insight-card-label">
                  <span>
                    {hypothesis.id} · {humanize(hypothesis.label)}
                  </span>
                  <span className="illustrative-score">
                    {hypothesis.independentSupport} independent source
                    {hypothesis.independentSupport === 1 ? "" : "s"}
                  </span>
                </div>
                <h3>{hypothesis.statement}</h3>
                {supporting.length > 0 && (
                  <>
                    <h4>Supports</h4>
                    <ul>
                      {supporting.map((entry) => (
                        <li key={entry.reason}>{entry.reason}</li>
                      ))}
                    </ul>
                  </>
                )}
                {contradicting.length > 0 && (
                  <>
                    <h4>Against</h4>
                    <ul>
                      {contradicting.map((entry) => (
                        <li key={entry.reason}>{entry.reason}</li>
                      ))}
                    </ul>
                  </>
                )}
                {hypothesis.assumptions.length > 0 && (
                  <p className="explanation-meta">
                    Assumes: {hypothesis.assumptions.join("; ")}
                  </p>
                )}
              </div>
              <CitationLinks
                ids={[
                  ...new Set(
                    [...hypothesis.supporting, ...hypothesis.contradicting].map(
                      (entry) => entry.citation,
                    ),
                  ),
                ]}
                sourceById={sourceById}
                onOpenSource={onOpenSource}
              />
            </article>
          );
        })}
      </div>
      {set.discriminatingEvidence.length > 0 && (
        <div className="explanation-discriminators">
          <h4>Evidence that would tell them apart</h4>
          <ul>
            {set.discriminatingEvidence.map((entry) => (
              <li key={`${entry.artifact}-${entry.why}`}>
                <strong>{humanize(entry.artifact)}:</strong> {entry.why}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

/** Several records can give the same reason; list each reason once. */
function dedupe<T extends { reason: string }>(entries: T[]): T[] {
  return [...new Map(entries.map((entry) => [entry.reason, entry])).values()];
}

/** `follow_up_interview` → `Follow up interview`. */
function humanize(value: string) {
  const text = value
    .replace(/_/g, " ")
    .replace(/\b(cctv|dna|lpr|ml)\b/gi, (acronym) => acronym.toUpperCase());
  return text.charAt(0).toUpperCase() + text.slice(1);
}
