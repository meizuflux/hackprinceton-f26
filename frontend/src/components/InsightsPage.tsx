import { useCallback, useMemo, useState } from "react";
import {
  ArrowUpRight,
  FileText,
  Lightbulb,
  Search,
  ShieldCheck,
  Target,
} from "lucide-react";
import type { CaseData } from "../api/types";
import type { Selection } from "./Inspector";
import "./insights-page.css";

export function InsightsPage({
  data,
  onInspect,
  onOpenSource,
}: {
  data: CaseData;
  onInspect: (selection: Selection) => void;
  onOpenSource: (sourceId: string) => void;
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
                    <span>Inference</span>
                    <span className="illustrative-score">
                      Illustrative · {Math.round(item.score * 100)}%
                    </span>
                  </div>
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                  <span className="insight-card-action">
                    Inspect inference <ArrowUpRight size={14} />
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
                      Illustrative · {Math.round(item.score * 100)}%
                    </span>
                  </div>
                  <h3>{item.title}</h3>
                  <p>{item.description}</p>
                  <span className="insight-card-action">
                    Inspect gap <ArrowUpRight size={14} />
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
