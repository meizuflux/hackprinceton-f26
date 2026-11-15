import { OriginIcon } from "./OriginBadge";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  ArrowUpRight,
  ChevronRight,
  FileText,
  GitBranch,
  Search,
} from "lucide-react";
import type {
  CaseData,
  CitationId,
  EvidenceSuggestion,
  ExplanationSet,
  Hypothesis,
  Insight,
} from "../api/types";
import { insightsPath, insightsTabs, type InsightsTab } from "../routing";
import { formatCaseTime, insightStrength, scoreLabel } from "./presentation";
import type { Selection } from "./Inspector";
import {
  buildInsightsModel,
  humanize,
  suggestionGapIds,
  tabCounts,
  type InsightsModel,
  type QuestionItem,
} from "./insights-sections";
import "./insights-page.css";

type SourceMap = Map<string, CaseData["sources"][number]>;

const tabMeta: Record<
  InsightsTab,
  { label: string; framing: string; caution: string }
> = {
  questions: {
    label: "Questions",
    framing: "What we don’t know and what to request next",
    caution:
      "A question marks missing, conflicting or uncertain evidence. It is not proof that anything happened.",
  },
  evidence: {
    label: "Evidence",
    framing: "What the records directly show, and where they conflict",
    caution:
      "Each item is read from cited records. A conflict or a silence is observed; its cause is not.",
  },
  inferences: {
    label: "Inferences",
    framing: "What the analysis infers from the evidence",
    caution:
      "Inferences are leads to verify, not findings. Confidence is a label, never a probability.",
  },
};

export function InsightsPage({
  data,
  tab = "questions",
  navigate,
  onInspect,
  onOpenSource,
  onFocusOnBoard,
}: {
  data: CaseData;
  tab?: InsightsTab;
  navigate?: (path: string) => void;
  onInspect: (selection: Selection) => void;
  onOpenSource: (sourceId: string) => void;
  onFocusOnBoard?: (selection: Selection) => void;
}) {
  const [search, setSearch] = useState("");
  const query = search.trim();
  const sourceById = useMemo<SourceMap>(
    () => new Map(data.sources.map((source) => [source.id, source])),
    [data.sources],
  );
  const model = useMemo(() => buildInsightsModel(data, query), [data, query]);
  const counts = tabCounts(model);
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => {
    scroller.current?.scrollTo({ top: 0 });
  }, [tab]);

  const ctx: PanelContext = {
    data,
    query,
    sourceById,
    onInspect,
    onOpenSource,
    onFocusOnBoard,
  };

  return (
    <div className="insights-page" ref={scroller}>
      <header className="insights-hero">
        <h2>Insights</h2>
        <p>
          Open questions, what the records show, and what the analysis infers,
          each with its original sources.
        </p>
      </header>
      <div className="insights-bar">
        <nav className="insights-tabs" aria-label="Insights sections">
          {insightsTabs.map((id) => {
            const href = insightsPath(data.id, id);
            return (
              <a
                key={id}
                href={href}
                className="insights-tab"
                data-tab={id}
                aria-current={tab === id ? "page" : undefined}
                onClick={(event) => {
                  if (
                    !navigate ||
                    event.metaKey ||
                    event.ctrlKey ||
                    event.shiftKey ||
                    event.altKey
                  )
                    return;
                  event.preventDefault();
                  if (tab !== id) navigate(href);
                }}
              >
                <span className="insights-tab-label">
                  {tabMeta[id].label}
                  <span
                    className="insights-tab-count"
                    aria-label={`${counts[id]} ${query ? "matching " : ""}items`}
                  >
                    {counts[id]}
                  </span>
                </span>
                <span className="insights-tab-framing">
                  {tabMeta[id].framing}
                </span>
              </a>
            );
          })}
        </nav>
        <label className="insights-search">
          <Search size={16} aria-hidden="true" />
          <span className="sr-only">
            Search questions, evidence and inferences
          </span>
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search all three sections"
          />
        </label>
      </div>

      <div className="insights-panel" data-tab={tab}>
        <p className="insights-caution">{tabMeta[tab].caution}</p>
        {tab === "questions" && <QuestionsPanel model={model} ctx={ctx} />}
        {tab === "evidence" && <EvidencePanel model={model} ctx={ctx} />}
        {tab === "inferences" && <InferencesPanel model={model} ctx={ctx} />}
      </div>
    </div>
  );
}

interface PanelContext {
  data: CaseData;
  query: string;
  sourceById: SourceMap;
  onInspect: (selection: Selection) => void;
  onOpenSource: (sourceId: string) => void;
  onFocusOnBoard?: (selection: Selection) => void;
}

/* ---------------------------------------------------------------- Questions */

const gapTypeLabel: Record<string, string> = {
  missing: "Missing record",
  failed_extraction: "Failed extraction",
  conflicting: "Records conflict",
  uncertain: "Uncertain",
};

function QuestionsPanel({
  model,
  ctx,
}: {
  model: InsightsModel;
  ctx: PanelContext;
}) {
  const { items, unlinked } = model.questions;
  if (!items.length && !unlinked.length)
    return <EmptyState query={ctx.query} label="questions" />;
  return (
    <>
      {items.length > 0 && (
        <ol className="question-list">
          {items.map((item, index) => (
            <QuestionCard
              key={item.gap.id}
              item={item}
              rank={index + 1}
              ctx={ctx}
            />
          ))}
        </ol>
      )}
      {unlinked.length > 0 && (
        <Section
          id="questions-other"
          title="Other suggested requests"
          note="Follow-up requests not tied to a question above · not findings"
          count={unlinked.length}
        >
          <SuggestionList suggestions={unlinked} ctx={ctx} />
        </Section>
      )}
    </>
  );
}

function QuestionCard({
  item,
  rank,
  ctx,
}: {
  item: QuestionItem;
  rank: number;
  ctx: PanelContext;
}) {
  const { gap, suggestions } = item;
  const structured = gap.missing || gap.whyItMatters || gap.direction;
  return (
    <li className="question-card">
      <div className="question-rank" aria-hidden="true">
        {rank}
      </div>
      <article aria-labelledby={`q-${gap.id}`}>
        <div className="item-meta">
          <span className="item-kind question-kind">
            {gap.gapType
              ? (gapTypeLabel[gap.gapType] ?? humanize(gap.gapType))
              : "Question to verify"}
          </span>
          {gap.status && (
            <span className={`question-status status-${gap.status}`}>
              {humanize(gap.status)}
            </span>
          )}
          <span className="item-id">{gap.id}</span>
          <span className="item-score">{scoreLabel(gap.score, "rank")}</span>
        </div>
        <h3 id={`q-${gap.id}`}>{gap.title}</h3>
        {structured ? (
          <dl className="question-facts">
            {gap.missing && (
              <>
                <dt>Missing</dt>
                <dd>{gap.missing}</dd>
              </>
            )}
            {gap.whyItMatters && (
              <>
                <dt>Why it matters</dt>
                <dd>{gap.whyItMatters}</dd>
              </>
            )}
            {gap.direction && (
              <>
                <dt>Next step</dt>
                <dd>{gap.direction}</dd>
              </>
            )}
            {gap.answer && (
              <>
                <dt>Partial answer</dt>
                <dd>{gap.answer}</dd>
              </>
            )}
          </dl>
        ) : (
          <p className="item-text">{gap.description}</p>
        )}
        <ItemActions
          inspectLabel="Inspect question"
          onInspect={() => ctx.onInspect({ kind: "gap", id: gap.id })}
          onLocate={
            ctx.onFocusOnBoard &&
            (() => ctx.onFocusOnBoard?.({ kind: "gap", id: gap.id }))
          }
        />
        <CitationLinks ids={gap.citations} ctx={ctx} />
        {suggestions.length > 0 && (
          <div className="question-next">
            <h4>
              Suggested next evidence <span>{suggestions.length}</span>
            </h4>
            <SuggestionList
              suggestions={suggestions}
              ctx={ctx}
              currentGap={gap.id}
              limit={ctx.query ? undefined : 1}
            />
          </div>
        )}
      </article>
    </li>
  );
}

function SuggestionList({
  suggestions,
  ctx,
  currentGap,
  limit,
}: {
  suggestions: EvidenceSuggestion[];
  ctx: PanelContext;
  currentGap?: string;
  /** Show only the highest-priority requests until expanded. */
  limit?: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const hidden =
    limit !== undefined && !expanded ? suggestions.length - limit : 0;
  const shown = hidden > 0 ? suggestions.slice(0, limit) : suggestions;
  return (
    <ul className="suggestion-list">
      {shown.map((suggestion) => {
        const others = suggestionGapIds(suggestion).filter(
          (id) => id !== currentGap,
        );
        return (
          <li key={suggestion.id}>
            <button
              type="button"
              className="suggestion-row"
              onClick={() =>
                ctx.onInspect({ kind: "suggestion", id: suggestion.id })
              }
            >
              <span className="suggestion-priority">
                Priority {suggestion.priority}
              </span>
              <span className="suggestion-body">
                <strong>
                  {suggestion.artifact
                    ? humanize(suggestion.artifact)
                    : suggestion.title}
                </strong>
                <span>{suggestion.query || suggestion.description}</span>
                {currentGap && others.length > 0 && (
                  <span className="suggestion-also">
                    Also helps {others.join(", ")}
                  </span>
                )}
              </span>
              <ChevronRight size={14} aria-hidden="true" />
              <span className="sr-only">
                Inspect suggestion {suggestion.id}
              </span>
            </button>
          </li>
        );
      })}
      {limit !== undefined && suggestions.length > limit && (
        <li>
          <button
            type="button"
            className="show-more"
            aria-expanded={expanded}
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded
              ? "Show only the top request"
              : `Show ${hidden} more request${hidden === 1 ? "" : "s"}`}
          </button>
        </li>
      )}
    </ul>
  );
}

/* ----------------------------------------------------------------- Evidence */

function EvidencePanel({
  model,
  ctx,
}: {
  model: InsightsModel;
  ctx: PanelContext;
}) {
  const e = model.evidence;
  const sections = [
    {
      id: "evidence-contradictions",
      title: "Contradictions",
      count: e.contradictions.length,
    },
    {
      id: "evidence-observations",
      title: "Cited observations",
      count: e.observations.length,
    },
    {
      id: "evidence-repeated",
      title: "Repeated across sources",
      count: e.sourceGroups.length,
    },
    {
      id: "evidence-silences",
      title: "Silent periods",
      count: e.missingPeriods.length,
    },
    {
      id: "evidence-times",
      title: "Uncertain times",
      count: e.uncertainTimes.length,
    },
  ].filter((section) => section.count > 0);
  if (!sections.length)
    return (
      <EmptyState
        query={ctx.query}
        label="observed evidence"
        hint="Contradictions, cited observations, repeated sources and silent periods come from the case analysis."
      />
    );
  return (
    <>
      <SectionIndex sections={sections} />
      {e.contradictions.length > 0 && (
        <Section
          id="evidence-contradictions"
          title="Contradictions"
          note="Accounts and records that disagree · the disagreement is observed, its reason is not"
          count={e.contradictions.length}
        >
          <div className="item-stack">
            {e.contradictions.map((item) => (
              <article className="evidence-item conflict-item" key={item.id}>
                <div className="item-meta">
                  <span className="item-kind observed-kind">
                    {humanize(item.kind)}
                  </span>
                  <span className="item-id">{item.id}</span>
                  <span className="item-score">
                    {humanize(item.severity)} severity
                  </span>
                </div>
                <h3>{item.title}</h3>
                <p className="item-text">{item.text}</p>
                <details className="item-details">
                  <summary>
                    Possible reasons · {item.possibleReasons.length}
                  </summary>
                  <p className="details-note">
                    Each is one possibility; none is a finding.
                  </p>
                  <ul>
                    {item.possibleReasons.map((reason, index) => (
                      <li key={index}>{reason}</li>
                    ))}
                  </ul>
                  {item.resolvingEvidence.length > 0 && (
                    <p className="details-note">
                      Would resolve it:{" "}
                      {item.resolvingEvidence.map(humanize).join(", ")}
                    </p>
                  )}
                </details>
                <CitationLinks ids={item.citations} ctx={ctx} />
              </article>
            ))}
          </div>
        </Section>
      )}
      {e.observations.length > 0 && (
        <Section
          id="evidence-observations"
          title="Cited observations"
          note="Statements read from records, each with its sources · the inferences drawn from them are under Inferences"
          count={e.observations.length}
        >
          <ShowMore
            initial={8}
            noun="observations"
            items={e.observations.map((item) => (
              <article className="evidence-row" key={item.text}>
                <p>{item.text}</p>
                <div className="evidence-row-foot">
                  <span className="used-by">
                    Supports{" "}
                    {item.insights.map((insight, index) => (
                      <span key={insight.id}>
                        {index > 0 && ", "}
                        <button
                          type="button"
                          className="link-button"
                          title={insight.title}
                          onClick={() =>
                            ctx.onInspect({ kind: "insight", id: insight.id })
                          }
                        >
                          {insight.id}
                        </button>
                      </span>
                    ))}
                  </span>
                  <CitationLinks ids={item.citations} ctx={ctx} compact />
                </div>
              </article>
            ))}
          />
        </Section>
      )}
      {e.sourceGroups.length > 0 && (
        <Section
          id="evidence-repeated"
          title="Repeated across sources"
          note="The same information in several files counts as one origin when weighing corroboration"
          count={e.sourceGroups.length}
        >
          <div className="item-stack">
            {e.sourceGroups.map((item) => (
              <article className="evidence-row" key={item.id}>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
                <div className="evidence-row-foot">
                  <span className="item-id">{item.id}</span>
                  <CitationLinks ids={item.citations} ctx={ctx} compact />
                </div>
              </article>
            ))}
          </div>
        </Section>
      )}
      {e.missingPeriods.length > 0 && (
        <Section
          id="evidence-silences"
          title="Silent periods"
          note="Sources with no records for an unusual stretch · may be inactivity, an outage or missing data; a silence is not proof"
          count={e.missingPeriods.length}
        >
          <ShowMore
            initial={6}
            noun="silent periods"
            items={e.missingPeriods.map((item) => (
              <article className="evidence-row timed-row" key={item.id}>
                <div className="timed-when">
                  {item.start && (
                    <time dateTime={item.start}>
                      {formatCaseTime(item.start, ctx.data.timezone)}
                    </time>
                  )}
                  {item.end && (
                    <time dateTime={item.end}>
                      to {formatCaseTime(item.end, ctx.data.timezone)}
                    </time>
                  )}
                </div>
                <div>
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                  <CitationLinks ids={item.citations} ctx={ctx} compact />
                </div>
              </article>
            ))}
          />
        </Section>
      )}
      {e.uncertainTimes.length > 0 && (
        <Section
          id="evidence-times"
          title="Uncertain times"
          note="Record times that carry an assumption · conclusions about exact order use the full window"
          count={e.uncertainTimes.length}
        >
          <ShowMore
            initial={5}
            noun="uncertain times"
            items={e.uncertainTimes.map((item) => (
              <article className="evidence-row" key={item.id}>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
                <div className="evidence-row-foot">
                  <span className="item-id">{item.id}</span>
                  <CitationLinks ids={item.citations} ctx={ctx} compact />
                </div>
              </article>
            ))}
          />
        </Section>
      )}
    </>
  );
}

/* --------------------------------------------------------------- Inferences */

function InferencesPanel({
  model,
  ctx,
}: {
  model: InsightsModel;
  ctx: PanelContext;
}) {
  const { explanations, insights, signals } = model.inferences;
  const sections = [
    {
      id: "inferences-explanations",
      title: "Competing explanations",
      count: explanations.length,
    },
    {
      id: "inferences-analysis",
      title: "Analysis inferences",
      count: insights.length,
    },
    { id: "inferences-signals", title: "ML leads", count: signals.length },
  ].filter((section) => section.count > 0);
  if (!sections.length)
    return <EmptyState query={ctx.query} label="inferences" />;
  return (
    <>
      <SectionIndex sections={sections} />
      {explanations.length > 0 && (
        <Section
          id="inferences-explanations"
          title="Competing explanations"
          note="Scored from supporting and contradicting records, capped by independent sources · inference, not a finding"
          count={explanations.length}
        >
          <div className="item-stack">
            {explanations.map((set) => (
              <ExplanationBlock key={set.episode} set={set} ctx={ctx} />
            ))}
          </div>
        </Section>
      )}
      {insights.length > 0 && (
        <Section
          id="inferences-analysis"
          title="Analysis inferences"
          note="Each inference is shown apart from the cited observations it rests on"
          count={insights.length}
        >
          <div className="insights-grid">
            {insights.map((item) => (
              <InferenceCard key={item.id} item={item} ctx={ctx} />
            ))}
          </div>
        </Section>
      )}
      {signals.length > 0 && (
        <Section
          id="inferences-signals"
          title="ML leads"
          note="Pattern-finding models flag places, days and messages to check · leads only; they never change findings, explanations or questions"
          count={signals.length}
        >
          <ShowMore
            initial={6}
            noun="leads"
            items={signals.map((signal) => (
              <article className="evidence-row signal-row" key={signal.id}>
                <div className="item-meta">
                  <span className="item-kind inferred-kind">
                    Lead · {humanize(signal.type)}
                  </span>
                  <OriginTag origin="ml" />
                  <span className="item-id">{signal.id}</span>
                  <span className="item-score">
                    Model score {signal.score.toFixed(2)}
                  </span>
                </div>
                <h3>{signal.title}</h3>
                <p>{signal.text}</p>
                <div className="evidence-row-foot">
                  {signal.method?.name && (
                    <span className="signal-method">{signal.method.name}</span>
                  )}
                  <CitationLinks ids={signal.citations} ctx={ctx} compact />
                </div>
              </article>
            ))}
          />
        </Section>
      )}
    </>
  );
}

function ExplanationBlock({
  set,
  ctx,
}: {
  set: ExplanationSet;
  ctx: PanelContext;
}) {
  return (
    <article className="explanation-block">
      <h3>{set.episode}</h3>
      <p className={`explanation-verdict ${set.decided ? "decided" : ""}`}>
        <strong>{set.decided ? "Best supported" : "Undecided"}</strong>
        <span>{set.verdict}</span>
      </p>
      <ol className="hypothesis-list">
        {set.hypotheses.map((hypothesis) => (
          <HypothesisRow
            key={hypothesis.id}
            hypothesis={hypothesis}
            decided={set.decided}
            ctx={ctx}
          />
        ))}
      </ol>
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
    </article>
  );
}

function HypothesisRow({
  hypothesis,
  decided,
  ctx,
}: {
  hypothesis: Hypothesis;
  decided: boolean;
  ctx: PanelContext;
}) {
  const supporting = groupReasons(hypothesis.supporting);
  const contradicting = groupReasons(hypothesis.contradicting);
  const label = humanize(hypothesis.label);
  return (
    <li className="hypothesis-row" data-label={hypothesis.label}>
      <div className="item-meta">
        <span className="item-kind inferred-kind">
          {hypothesis.id} · {label}
          {!decided && hypothesis.label === "best supported" && ", undecided"}
        </span>
        <span className="item-score">
          {hypothesis.independentSupport} independent source
          {hypothesis.independentSupport === 1 ? "" : "s"}
        </span>
      </div>
      <p className="hypothesis-statement">{hypothesis.statement}</p>
      <details className="item-details">
        <summary>
          {supporting.length} for · {contradicting.length} against
          {hypothesis.assumptions.length > 0 &&
            ` · ${hypothesis.assumptions.length} assumption${hypothesis.assumptions.length === 1 ? "" : "s"}`}
        </summary>
        {supporting.length > 0 && (
          <ReasonList title="For" reasons={supporting} ctx={ctx} />
        )}
        {contradicting.length > 0 && (
          <ReasonList title="Against" reasons={contradicting} ctx={ctx} />
        )}
        {hypothesis.assumptions.length > 0 && (
          <p className="details-note">
            Assumes: {hypothesis.assumptions.join("; ")}
          </p>
        )}
      </details>
    </li>
  );
}

function ReasonList({
  title,
  reasons,
  ctx,
}: {
  title: string;
  reasons: Array<{ reason: string; citations: CitationId[] }>;
  ctx: PanelContext;
}) {
  return (
    <>
      <h4>{title}</h4>
      <ul className="reason-list">
        {reasons.map((entry) => (
          <li key={entry.reason}>
            <span>{entry.reason}</span>
            <CitationLinks ids={entry.citations} ctx={ctx} compact bare />
          </li>
        ))}
      </ul>
    </>
  );
}

const tagText = {
  ml: "Traditional ML",
  agent: "Agent insight",
  llm: "LLM claim",
  rules: "Rules",
  record: "Record",
} as const;

/** Names who produced an inference: icon plus words, never colour alone. */
function OriginTag({ origin }: { origin: keyof typeof tagText }) {
  return (
    <span className={`origin-tag origin-${origin}`}>
      <OriginIcon origin={origin} size={11} />
      {tagText[origin]}
    </span>
  );
}

function InferenceCard({ item, ctx }: { item: Insight; ctx: PanelContext }) {
  const observations = item.observations ?? [];
  const caveats = [
    ...(item.unknowns ?? []).map((text) => ["Unknown", text]),
    ...(item.counterevidence ?? []).map((text) => ["Against", text]),
    ...(item.assumptions ?? []).map((text) => ["Assumes", text]),
    ...(item.limitations ?? []).map((text) => ["Limit", text]),
  ];
  return (
    <article className="inference-card">
      <div className="item-meta">
        <span className="item-kind inferred-kind">
          {item.certainty === "observed"
            ? "Inference · observed basis"
            : "Inference"}
        </span>
        <OriginTag origin={item.origin ?? "rules"} />
        <span className="item-id">{item.id}</span>
        <span className="item-score">{insightStrength(item)}</span>
      </div>
      <h3>{item.title}</h3>
      <p className="inference-text">{item.inference || item.text}</p>
      {observations.length > 0 && (
        <details className="item-details">
          <summary>
            Rests on {observations.length} cited observation
            {observations.length === 1 ? "" : "s"}
          </summary>
          <ul className="reason-list">
            {observations.map((observation, index) => (
              <li key={index}>
                <span>{observation.text}</span>
                <CitationLinks
                  ids={observation.citations}
                  ctx={ctx}
                  compact
                  bare
                />
              </li>
            ))}
          </ul>
        </details>
      )}
      {caveats.length > 0 && (
        <details className="item-details">
          <summary>Unknowns and limits · {caveats.length}</summary>
          <ul>
            {caveats.map(([kind, text]) => (
              <li key={`${kind}-${text}`}>
                <strong>{kind}:</strong> {text}
              </li>
            ))}
          </ul>
        </details>
      )}
      <ItemActions
        inspectLabel="Inspect inference"
        onInspect={() => ctx.onInspect({ kind: "insight", id: item.id })}
        onLocate={
          ctx.onFocusOnBoard &&
          (() => ctx.onFocusOnBoard?.({ kind: "insight", id: item.id }))
        }
      />
      <CitationLinks ids={item.citations} ctx={ctx} />
    </article>
  );
}

/* ------------------------------------------------------------------ Shared */

function Section({
  id,
  title,
  note,
  count,
  children,
}: {
  id: string;
  title: string;
  note: string;
  count: number;
  children: ReactNode;
}) {
  return (
    <section className="insights-section" id={id} aria-labelledby={`${id}-h`}>
      <div className="insights-section-heading">
        <h2 id={`${id}-h`}>
          {title} <span className="insights-count">{count}</span>
        </h2>
        <p>{note}</p>
      </div>
      {children}
    </section>
  );
}

function SectionIndex({
  sections,
}: {
  sections: Array<{ id: string; title: string; count: number }>;
}) {
  if (sections.length < 2) return null;
  return (
    <nav className="insights-index" aria-label="Jump to">
      {sections.map((section) => (
        <a
          key={section.id}
          href={`#${section.id}`}
          onClick={(event) => {
            event.preventDefault();
            document
              .getElementById(section.id)
              ?.scrollIntoView({ behavior: "smooth", block: "start" });
          }}
        >
          {section.title} <span>{section.count}</span>
        </a>
      ))}
    </nav>
  );
}

function ShowMore({
  items,
  initial,
  noun,
}: {
  items: ReactNode[];
  initial: number;
  noun: string;
}) {
  const [open, setOpen] = useState(false);
  const shown = open ? items : items.slice(0, initial);
  return (
    <div className="item-stack">
      {shown}
      {items.length > initial && (
        <button
          type="button"
          className="show-more"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? `Show fewer ${noun}` : `Show all ${items.length} ${noun}`}
        </button>
      )}
    </div>
  );
}

function ItemActions({
  inspectLabel,
  onInspect,
  onLocate,
}: {
  inspectLabel: string;
  onInspect: () => void;
  onLocate?: () => void;
}) {
  return (
    <div className="item-actions">
      <button type="button" className="item-action" onClick={onInspect}>
        {inspectLabel} <ArrowUpRight size={14} aria-hidden="true" />
      </button>
      {onLocate && (
        <button type="button" className="item-action subtle" onClick={onLocate}>
          <GitBranch size={13} aria-hidden="true" /> Locate on mind map
        </button>
      )}
    </div>
  );
}

const CITATIONS_SHOWN = 4;

function CitationLinks({
  ids,
  ctx,
  compact = false,
  bare = false,
}: {
  ids: CitationId[];
  ctx: PanelContext;
  compact?: boolean;
  /** Inline chips without the "Original sources" caption. */
  bare?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const sources = [...new Set(ids)]
    .map((id) => ctx.sourceById.get(id))
    .filter((source): source is CaseData["sources"][number] => Boolean(source));
  const shown = expanded ? sources : sources.slice(0, CITATIONS_SHOWN);
  return (
    <div
      className={`insight-citations${compact ? " compact" : ""}${bare ? " bare" : ""}`}
    >
      {!bare && (
        <span className="citation-caption">
          <FileText size={13} aria-hidden="true" /> Sources · {sources.length}
        </span>
      )}
      {sources.length > 0 && (
        <div>
          {shown.map((source) => (
            <button
              type="button"
              key={source.id}
              title={`${source.id} · ${source.path}`}
              aria-label={`Open source ${source.id}`}
              onClick={() => ctx.onOpenSource(source.id)}
            >
              {source.id}
              <ArrowUpRight size={11} aria-hidden="true" />
            </button>
          ))}
          {sources.length > CITATIONS_SHOWN && (
            <button
              type="button"
              className="citation-more"
              aria-expanded={expanded}
              onClick={() => setExpanded((value) => !value)}
            >
              {expanded ? "Fewer" : `+${sources.length - CITATIONS_SHOWN} more`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function EmptyState({
  query,
  label,
  hint,
}: {
  query: string;
  label: string;
  hint?: string;
}) {
  return (
    <div className="insights-empty">
      {query
        ? `No ${label} match “${query}”. Other sections may still have matches.`
        : `No ${label} available for this case.${hint ? ` ${hint}` : ""}`}
    </div>
  );
}

/** Several records can give the same reason; list each reason once with all its sources. */
function groupReasons(
  entries: Array<{ reason: string; citation: CitationId }>,
) {
  const grouped = new Map<string, CitationId[]>();
  for (const entry of entries) {
    grouped.set(entry.reason, [
      ...(grouped.get(entry.reason) ?? []),
      entry.citation,
    ]);
  }
  return [...grouped].map(([reason, citations]) => ({ reason, citations }));
}
