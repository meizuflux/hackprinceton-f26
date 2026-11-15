import { OriginIcon } from "./OriginBadge";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import {
  ArrowUpRight,
  ChevronRight,
  FileText,
  GitBranch,
  ListChecks,
  Search,
  X,
} from "lucide-react";
import type {
  CaseData,
  CitationId,
  EvidenceSuggestion,
  ExplanationSet,
  Hypothesis,
  Insight,
  MlSignal,
  Origin,
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
  { label: string; noun: string; framing: string; caution: string }
> = {
  questions: {
    label: "Questions",
    noun: "questions",
    framing: "What we don’t know yet, and what to request next.",
    caution:
      "A question marks missing, conflicting or uncertain evidence. It is not proof that anything happened.",
  },
  evidence: {
    label: "Evidence",
    noun: "observed evidence",
    framing: "What the records directly show, and where they conflict.",
    caution:
      "Each item is read from cited records. A conflict or a silence is observed; its cause is not.",
  },
  inferences: {
    label: "Inferences",
    noun: "inferences",
    framing: "What the analysis infers from the evidence.",
    caution:
      "Every inference is a lead to verify, not a finding. Confidence is a label and a model score is a rank, never a probability.",
  },
};

interface RailEntry {
  id: string;
  title: string;
  count?: number;
  rank?: number;
  origin?: Origin;
}

const questionAnchor = (gapId: string) => `question-${gapId}`;

/** The jump list beside the content: what this tab holds, in page order. */
function railEntries(tab: InsightsTab, model: InsightsModel): RailEntry[] {
  if (tab === "questions") {
    const entries: RailEntry[] = model.questions.items.map((item, index) => ({
      id: questionAnchor(item.gap.id),
      title: item.gap.title,
      rank: index + 1,
    }));
    if (model.questions.unlinked.length)
      entries.push({
        id: "questions-other",
        title: "Other suggested requests",
        count: model.questions.unlinked.length,
      });
    return entries;
  }
  if (tab === "evidence") {
    const e = model.evidence;
    const all: RailEntry[] = [
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
    ];
    return all.filter((entry) => entry.count);
  }
  const i = model.inferences;
  const all: RailEntry[] = [
    {
      id: "inferences-explanations",
      title: "Competing explanations",
      count: i.explanations.length,
    },
    {
      id: "inferences-agent",
      title: "AI agent insights",
      count: i.agentInsights.length,
      origin: "agent",
    },
    {
      id: "inferences-signals",
      title: "ML model leads",
      count: i.signals.length,
      origin: "ml",
    },
    {
      id: "inferences-rules",
      title: "Rule-based inferences",
      count: i.ruleInsights.length,
      origin: "rules",
    },
  ];
  return all.filter((entry) => entry.count);
}

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
  // Board cards that stand for an analysis item: an ML lead is reached through its card.
  const nodeByItem = useMemo(
    () =>
      new Map(
        data.nodes.flatMap((node) =>
          node.itemId ? [[node.itemId, node.id] as const] : [],
        ),
      ),
    [data.nodes],
  );
  const model = useMemo(() => buildInsightsModel(data, query), [data, query]);
  const counts = tabCounts(model);
  const entries = useMemo(() => railEntries(tab, model), [tab, model]);

  const scroller = useRef<HTMLDivElement>(null);
  const header = useRef<HTMLElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  const [headerHeight, setHeaderHeight] = useState(64);
  const [active, setActive] = useState<string | undefined>();
  const spyPausedUntil = useRef(0);

  useEffect(() => {
    scroller.current?.scrollTo({ top: 0 });
  }, [tab]);

  useEffect(() => {
    const element = header.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() =>
      setHeaderHeight(element.offsetHeight),
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  // Mark the rail entry for the section just below the sticky header.
  const entryKey = entries.map((entry) => entry.id).join("|");
  useEffect(() => {
    const root = scroller.current;
    if (!root) return;
    const ids = entryKey ? entryKey.split("|") : [];
    const update = () => {
      if (Date.now() < spyPausedUntil.current) return;
      const line =
        root.getBoundingClientRect().top +
        (header.current?.offsetHeight ?? 0) +
        48;
      let current = ids[0];
      for (const id of ids) {
        const top = document.getElementById(id)?.getBoundingClientRect().top;
        if (top !== undefined && top <= line) current = id;
      }
      if (
        root.scrollTop > 0 &&
        root.scrollTop + root.clientHeight >= root.scrollHeight - 4
      )
        current = ids[ids.length - 1] ?? current;
      setActive(current);
    };
    update();
    root.addEventListener("scroll", update, { passive: true });
    return () => root.removeEventListener("scroll", update);
  }, [entryKey]);

  const jump = useCallback((id: string) => {
    const target = document.getElementById(id);
    if (!target) return;
    const reduce = window.matchMedia?.(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    spyPausedUntil.current = Date.now() + 800;
    setActive(id);
    target.scrollIntoView({
      behavior: reduce ? "auto" : "smooth",
      block: "start",
    });
    document.getElementById(`${id}-h`)?.focus({ preventScroll: true });
  }, []);

  const clearSearch = () => {
    setSearch("");
    searchInput.current?.focus();
  };

  const ctx: PanelContext = {
    data,
    query,
    sourceById,
    nodeByItem,
    counts,
    navigateTab: navigate
      ? (id: InsightsTab) => navigate(insightsPath(data.id, id))
      : undefined,
    onInspect,
    onOpenSource,
    onFocusOnBoard,
  };

  return (
    <div
      className="insights-page"
      ref={scroller}
      style={{ "--insights-header": `${headerHeight}px` } as CSSProperties}
    >
      <header className="insights-header" ref={header}>
        <div className="insights-header-row">
          <h2>Insights</h2>
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
                  {tabMeta[id].label}
                  <span
                    className="insights-tab-count"
                    aria-label={`${counts[id]} ${query ? "matching " : ""}items`}
                  >
                    {counts[id]}
                  </span>
                </a>
              );
            })}
          </nav>
          <div className="insights-search">
            <Search size={15} aria-hidden="true" />
            <input
              ref={searchInput}
              type="search"
              value={search}
              aria-label="Search questions, evidence and inferences"
              placeholder="Search all insights"
              onChange={(event) => setSearch(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Escape" && search) {
                  event.preventDefault();
                  event.stopPropagation();
                  setSearch("");
                }
              }}
            />
            {search && (
              <button
                type="button"
                className="insights-search-clear"
                aria-label="Clear search"
                onClick={clearSearch}
              >
                <X size={14} aria-hidden="true" />
              </button>
            )}
          </div>
        </div>
      </header>

      <div className="insights-layout">
        <aside className="insights-rail">
          {entries.length > 0 && (
            <nav aria-label={`In ${tabMeta[tab].label}`}>
              <ol>
                {entries.map((entry) => (
                  <li key={entry.id}>
                    <a
                      href={`#${entry.id}`}
                      aria-current={
                        active === entry.id ? "location" : undefined
                      }
                      onClick={(event) => {
                        event.preventDefault();
                        jump(entry.id);
                      }}
                    >
                      {entry.rank !== undefined && (
                        <span className="rail-rank">{entry.rank}</span>
                      )}
                      {entry.origin && (
                        <span className="rail-origin">
                          <OriginMark origin={entry.origin} size={13} />
                        </span>
                      )}
                      <span className="rail-title">{entry.title}</span>
                      {entry.count !== undefined && (
                        <span className="rail-count">{entry.count}</span>
                      )}
                    </a>
                  </li>
                ))}
              </ol>
            </nav>
          )}
        </aside>

        <div className="insights-main" data-tab={tab}>
          <div className="insights-lede">
            <p>
              <strong>{tabMeta[tab].framing}</strong> {tabMeta[tab].caution}
            </p>
            {query && (
              <p className="insights-filter" role="status">
                Showing matches for “{query}” across all three tabs.{" "}
                <button
                  type="button"
                  className="text-button"
                  onClick={clearSearch}
                >
                  Clear search
                </button>
              </p>
            )}
          </div>
          {tab === "questions" && <QuestionsPanel model={model} ctx={ctx} />}
          {tab === "evidence" && <EvidencePanel model={model} ctx={ctx} />}
          {tab === "inferences" && <InferencesPanel model={model} ctx={ctx} />}
        </div>
      </div>
    </div>
  );
}

interface PanelContext {
  data: CaseData;
  query: string;
  sourceById: SourceMap;
  nodeByItem: Map<string, string>;
  counts: Record<InsightsTab, number>;
  navigateTab?: (tab: InsightsTab) => void;
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
    return (
      <EmptyState
        tab="questions"
        ctx={ctx}
        hint="Questions appear when the analysis finds missing, conflicting or uncertain evidence."
      />
    );
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
          note="Follow-up requests not tied to a question above. Requests, not findings."
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
  const anchor = questionAnchor(gap.id);
  return (
    <li className="question-card" id={anchor}>
      <div className="question-rank" aria-hidden="true">
        {rank}
      </div>
      <article aria-labelledby={`${anchor}-h`}>
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
        <h3 id={`${anchor}-h`} tabIndex={-1}>
          {gap.title}
        </h3>
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
        <ItemFooter
          ids={gap.citations}
          ctx={ctx}
          inspectLabel="Inspect question"
          onInspect={() => ctx.onInspect({ kind: "gap", id: gap.id })}
          onLocate={
            ctx.onFocusOnBoard &&
            (() => ctx.onFocusOnBoard?.({ kind: "gap", id: gap.id }))
          }
        />
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
  const total =
    e.contradictions.length +
    e.observations.length +
    e.sourceGroups.length +
    e.missingPeriods.length +
    e.uncertainTimes.length;
  if (!total)
    return (
      <EmptyState
        tab="evidence"
        ctx={ctx}
        hint="Contradictions, cited observations, repeated sources and silent periods come from the case analysis."
      />
    );
  return (
    <>
      {e.contradictions.length > 0 && (
        <Section
          id="evidence-contradictions"
          title="Contradictions"
          note="Accounts and records that disagree. The disagreement is observed; its reason is not."
          count={e.contradictions.length}
        >
          <div className="item-stack">
            {e.contradictions.map((item) => (
              <article className="evidence-item conflict-item" key={item.id}>
                <div className="item-meta">
                  <span className="item-kind conflict-kind">
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
                <ItemFooter
                  ids={item.citations}
                  ctx={ctx}
                  inspectLabel="Inspect contradiction"
                  onInspect={() =>
                    ctx.onInspect({ kind: "contradiction", id: item.id })
                  }
                />
              </article>
            ))}
          </div>
        </Section>
      )}
      {e.observations.length > 0 && (
        <Section
          id="evidence-observations"
          title="Cited observations"
          note="Statements read from records, each with its sources. The inferences drawn from them are under Inferences."
          count={e.observations.length}
        >
          <ShowMore
            initial={8}
            noun="observations"
            items={e.observations.map((item) => (
              <article className="evidence-row" key={item.text}>
                <p>{item.text}</p>
                <div className="item-foot">
                  <CitationLinks ids={item.citations} ctx={ctx} />
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
          note="The same information in several files counts as one origin when weighing corroboration."
          count={e.sourceGroups.length}
        >
          <div className="item-stack">
            {e.sourceGroups.map((item) => (
              <article className="evidence-row" key={item.id}>
                <div className="item-meta">
                  <span className="item-id">{item.id}</span>
                </div>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
                <div className="item-foot">
                  <CitationLinks ids={item.citations} ctx={ctx} />
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
          note="Sources with no records for an unusual stretch. It may be inactivity, an outage or missing data; a silence is not proof."
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
                  <div className="item-foot">
                    <CitationLinks ids={item.citations} ctx={ctx} />
                  </div>
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
          note="Record times that carry an assumption. Conclusions about exact order use the full window."
          count={e.uncertainTimes.length}
        >
          <ShowMore
            initial={5}
            noun="uncertain times"
            items={e.uncertainTimes.map((item) => (
              <article className="evidence-row" key={item.id}>
                <div className="item-meta">
                  <span className="item-id">{item.id}</span>
                </div>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
                <div className="item-foot">
                  <CitationLinks ids={item.citations} ctx={ctx} />
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
  const { explanations, agentInsights, ruleInsights, signals } =
    model.inferences;
  if (
    !explanations.length &&
    !agentInsights.length &&
    !ruleInsights.length &&
    !signals.length
  )
    return (
      <EmptyState
        tab="inferences"
        ctx={ctx}
        hint="Explanations, agent insights, ML leads and rule-based inferences come from the case analysis."
      />
    );
  return (
    <>
      {explanations.length > 0 && (
        <Section
          id="inferences-explanations"
          title="Competing explanations"
          note="Scored from supporting and contradicting records and capped by independent sources. The verdict is the backend’s and may be undecided."
          count={explanations.length}
        >
          <div className="item-stack">
            {explanations.map((set) => (
              <ExplanationBlock key={set.episode} set={set} ctx={ctx} />
            ))}
          </div>
        </Section>
      )}
      {agentInsights.length > 0 && (
        <Section
          id="inferences-agent"
          title="AI agent insights"
          origin="agent"
          note="Recorded by the AI investigator, which may only cite records it has read. Each inference is shown apart from the observations it rests on."
          count={agentInsights.length}
        >
          <div className="item-stack">
            {agentInsights.map((item) => (
              <InferenceCard key={item.id} item={item} ctx={ctx} />
            ))}
          </div>
        </Section>
      )}
      {signals.length > 0 && (
        <Section
          id="inferences-signals"
          title="ML model leads"
          origin="ml"
          note="Traditional models trained only on this case flag places, days and messages worth checking. Leads only: they never change findings, explanations or questions."
          count={signals.length}
        >
          <ShowMore
            initial={6}
            noun="ML leads"
            items={signals.map((signal) => (
              <SignalCard key={signal.id} signal={signal} ctx={ctx} />
            ))}
          />
        </Section>
      )}
      {ruleInsights.length > 0 && (
        <Section
          id="inferences-rules"
          title="Rule-based inferences"
          origin="rules"
          note="Drawn by deterministic rules from cited records. Each inference is shown apart from the observations it rests on."
          count={ruleInsights.length}
        >
          <ShowMore
            initial={6}
            noun="rule-based inferences"
            items={ruleInsights.map((item) => (
              <InferenceCard key={item.id} item={item} ctx={ctx} />
            ))}
          />
        </Section>
      )}
    </>
  );
}

const HYPOTHESES_SHOWN = 3;

function ExplanationBlock({
  set,
  ctx,
}: {
  set: ExplanationSet;
  ctx: PanelContext;
}) {
  const [open, setOpen] = useState(false);
  // The backend orders hypotheses best first; the rest stay one click away.
  const limit = ctx.query ? set.hypotheses.length : HYPOTHESES_SHOWN;
  const shown = open ? set.hypotheses : set.hypotheses.slice(0, limit);
  const hidden = set.hypotheses.length - shown.length;
  return (
    <article className="explanation-block">
      <h3>{set.episode}</h3>
      <p className={`explanation-verdict ${set.decided ? "decided" : ""}`}>
        <strong>{set.decided ? "Best supported" : "Undecided"}</strong>
        <span>{set.verdict}</span>
      </p>
      <ol className="hypothesis-list">
        {shown.map((hypothesis) => (
          <HypothesisRow
            key={hypothesis.id}
            hypothesis={hypothesis}
            decided={set.decided}
            ctx={ctx}
          />
        ))}
      </ol>
      {hidden > 0 || open ? (
        <button
          type="button"
          className="show-more"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          {open
            ? "Show only the top explanations"
            : `Show ${hidden} more explanation${hidden === 1 ? "" : "s"}`}
        </button>
      ) : null}
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
            <CitationLinks ids={entry.citations} ctx={ctx} bare />
          </li>
        ))}
      </ul>
    </>
  );
}

const originText: Record<Origin, string> = {
  ml: "ML model",
  agent: "AI agent",
  llm: "LLM",
  rules: "Rules",
  record: "Record",
};

/** The board's origin icons, plus a checklist for the deterministic rules. */
function OriginMark({ origin, size }: { origin: Origin; size: number }) {
  if (origin === "rules")
    return <ListChecks size={size} strokeWidth={2.2} aria-hidden="true" />;
  return <OriginIcon origin={origin} size={size} />;
}

/** Names who produced an inference: icon plus words, never colour alone. */
function OriginTag({ origin }: { origin: Origin }) {
  return (
    <span className={`origin-tag origin-${origin}`}>
      <OriginMark origin={origin} size={12} />
      {originText[origin]}
    </span>
  );
}

function SignalCard({ signal, ctx }: { signal: MlSignal; ctx: PanelContext }) {
  const nodeId = ctx.nodeByItem.get(signal.id);
  return (
    <article className="inference-card signal-card">
      <div className="item-meta">
        <OriginTag origin="ml" />
        <span className="item-kind inferred-kind">
          Lead · {humanize(signal.type)}
        </span>
        <span className="item-id">{signal.id}</span>
        <span className="item-score">
          Model score {signal.score.toFixed(2)}
        </span>
      </div>
      <h3>{signal.title}</h3>
      <p className="inference-text">{signal.text}</p>
      {signal.method?.name && (
        <p className="signal-method">
          <span>Method</span> {signal.method.name}
        </p>
      )}
      <ItemFooter
        ids={signal.citations}
        ctx={ctx}
        inspectLabel={nodeId ? "Inspect lead" : undefined}
        onInspect={
          nodeId ? () => ctx.onInspect({ kind: "node", id: nodeId }) : undefined
        }
        onLocate={
          nodeId && ctx.onFocusOnBoard
            ? () => ctx.onFocusOnBoard?.({ kind: "node", id: nodeId })
            : undefined
        }
      />
    </article>
  );
}

const OBSERVATIONS_SHOWN = 3;

function InferenceCard({ item, ctx }: { item: Insight; ctx: PanelContext }) {
  const [showAll, setShowAll] = useState(false);
  const observations = item.observations ?? [];
  const inference = item.inference || item.text;
  const caveats = [
    ...(item.unknowns ?? []).map((text) => ["Unknown", text]),
    ...(item.counterevidence ?? []).map((text) => ["Against", text]),
    ...(item.assumptions ?? []).map((text) => ["Assumes", text]),
    ...(item.limitations ?? []).map((text) => ["Limit", text]),
  ];
  return (
    <article className="inference-card">
      <div className="item-meta">
        <OriginTag origin={item.origin ?? "rules"} />
        <span className="item-kind inferred-kind">
          {item.certainty === "observed"
            ? "Inference · observed basis"
            : "Inference"}
        </span>
        <span className="item-id">{item.id}</span>
        <span className="item-score">{insightStrength(item)}</span>
      </div>
      <h3>{item.title}</h3>
      <p className="inference-text">{inference}</p>
      {observations.length > 0 && (
        <div className="inference-basis">
          <h4>
            Observed in records <span>{observations.length}</span>
          </h4>
          <ul className="reason-list">
            {(showAll
              ? observations
              : observations.slice(0, OBSERVATIONS_SHOWN)
            ).map((observation, index) => (
              <li key={index}>
                <span>{observation.text}</span>
                <CitationLinks ids={observation.citations} ctx={ctx} bare />
              </li>
            ))}
          </ul>
          {observations.length > OBSERVATIONS_SHOWN && (
            <button
              type="button"
              className="show-more"
              aria-expanded={showAll}
              onClick={() => setShowAll((value) => !value)}
            >
              {showAll
                ? "Show fewer observations"
                : `Show all ${observations.length} observations`}
            </button>
          )}
        </div>
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
      <ItemFooter
        ids={item.citations}
        ctx={ctx}
        inspectLabel="Inspect inference"
        onInspect={() => ctx.onInspect({ kind: "insight", id: item.id })}
        onLocate={
          ctx.onFocusOnBoard &&
          (() => ctx.onFocusOnBoard?.({ kind: "insight", id: item.id }))
        }
      />
    </article>
  );
}

/* ------------------------------------------------------------------ Shared */

function Section({
  id,
  title,
  note,
  count,
  origin,
  children,
}: {
  id: string;
  title: string;
  note: string;
  count: number;
  origin?: Origin;
  children: ReactNode;
}) {
  return (
    <section className="insights-section" id={id} aria-labelledby={`${id}-h`}>
      <div className="insights-section-heading">
        <h2 id={`${id}-h`} tabIndex={-1}>
          {origin && <OriginMark origin={origin} size={15} />}
          {title} <span className="insights-count">{count}</span>
        </h2>
        <p>{note}</p>
      </div>
      {children}
    </section>
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

/** One row under each item: its original sources, then what you can do with it. */
function ItemFooter({
  ids,
  ctx,
  inspectLabel,
  onInspect,
  onLocate,
}: {
  ids: CitationId[];
  ctx: PanelContext;
  inspectLabel?: string;
  onInspect?: () => void;
  onLocate?: () => void;
}) {
  return (
    <div className="item-foot">
      <CitationLinks ids={ids} ctx={ctx} />
      {(onInspect || onLocate) && (
        <div className="item-actions">
          {onLocate && (
            <button
              type="button"
              className="item-action subtle"
              onClick={onLocate}
            >
              <GitBranch size={13} aria-hidden="true" /> Locate on mind map
            </button>
          )}
          {onInspect && inspectLabel && (
            <button type="button" className="item-action" onClick={onInspect}>
              {inspectLabel} <ArrowUpRight size={14} aria-hidden="true" />
            </button>
          )}
        </div>
      )}
    </div>
  );
}

const CITATIONS_SHOWN = 4;

function CitationLinks({
  ids,
  ctx,
  bare = false,
}: {
  ids: CitationId[];
  ctx: PanelContext;
  /** Inline chips without the "Sources" caption. */
  bare?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const sources = [...new Set(ids)]
    .map((id) => ctx.sourceById.get(id))
    .filter((source): source is CaseData["sources"][number] => Boolean(source));
  const shown = expanded ? sources : sources.slice(0, CITATIONS_SHOWN);
  return (
    <div className={`insight-citations${bare ? " bare" : ""}`}>
      {!bare && (
        <span className="citation-caption">
          <FileText size={13} aria-hidden="true" />
          {sources.length
            ? `${sources.length} source${sources.length === 1 ? "" : "s"}`
            : "No resolvable source"}
        </span>
      )}
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
  );
}

function EmptyState({
  tab,
  ctx,
  hint,
}: {
  tab: InsightsTab;
  ctx: PanelContext;
  hint: string;
}) {
  const label = tabMeta[tab].noun;
  if (!ctx.query)
    return (
      <div className="insights-empty">
        <p>
          <strong>No {label} for this case yet.</strong> {hint}
        </p>
      </div>
    );
  const elsewhere = insightsTabs.filter(
    (id) => id !== tab && ctx.counts[id] > 0,
  );
  return (
    <div className="insights-empty" role="status">
      <p>
        <strong>
          No {label} match “{ctx.query}”.
        </strong>{" "}
        {elsewhere.length
          ? "The search covers all three tabs:"
          : "Nothing in the other tabs matches either. Try a name, an evidence ID such as EV-071, or a place."}
      </p>
      {elsewhere.length > 0 && (
        <ul className="empty-elsewhere">
          {elsewhere.map((id) => (
            <li key={id}>
              {ctx.navigateTab ? (
                <button
                  type="button"
                  className="text-button"
                  onClick={() => ctx.navigateTab?.(id)}
                >
                  {ctx.counts[id]} in {tabMeta[id].label}
                </button>
              ) : (
                `${ctx.counts[id]} in ${tabMeta[id].label}`
              )}
            </li>
          ))}
        </ul>
      )}
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
