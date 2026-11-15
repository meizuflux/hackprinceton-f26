import type {
  CaseData,
  CitationId,
  Contradiction,
  EvidenceGap,
  EvidenceSuggestion,
  ExplanationSet,
  Insight,
  MissingPeriod,
  MlSignal,
  SourceGroup,
  UncertainTime,
} from "../api/types";
import type { InsightsTab } from "../routing";

/**
 * Presentation-only grouping of the backend board into the three Insights
 * subsections. It sorts and filters what the API supplies; it never creates,
 * merges or scores case facts.
 */
export interface QuestionItem {
  gap: EvidenceGap;
  /** Suggested requests the backend tied to this gap, by priority. */
  suggestions: EvidenceSuggestion[];
}

export interface ObservationItem {
  text: string;
  citations: CitationId[];
  /** Insights that rest on this observation. */
  insights: Array<{ id: string; title: string }>;
}

export interface InsightsModel {
  questions: {
    items: QuestionItem[];
    /** Suggestions that name no gap present on the board. */
    unlinked: EvidenceSuggestion[];
  };
  evidence: {
    contradictions: Contradiction[];
    observations: ObservationItem[];
    sourceGroups: SourceGroup[];
    missingPeriods: MissingPeriod[];
    uncertainTimes: UncertainTime[];
  };
  inferences: {
    explanations: ExplanationSet[];
    insights: Insight[];
    signals: MlSignal[];
  };
}

export function suggestionGapIds(suggestion: EvidenceSuggestion): string[] {
  return suggestion.gapIds?.length ? suggestion.gapIds : [suggestion.gapId];
}

function matcher(query: string) {
  const q = query.trim().toLocaleLowerCase();
  return (values: Array<string | undefined | null>) =>
    !q ||
    values.some((value) => value && value.toLocaleLowerCase().includes(q));
}

export function buildInsightsModel(data: CaseData, query = ""): InsightsModel {
  const matches = matcher(query);
  const byPriority = (a: EvidenceSuggestion, b: EvidenceSuggestion) =>
    a.priority - b.priority;
  const suggestionMatches = (s: EvidenceSuggestion) =>
    matches([
      s.id,
      s.title,
      s.description,
      s.query,
      s.artifact,
      ...s.citations,
    ]);

  const gapIds = new Set(data.gaps.map((gap) => gap.id));
  const items: QuestionItem[] = [];
  for (const gap of data.gaps) {
    const linked = data.suggestions
      .filter((s) => suggestionGapIds(s).includes(gap.id))
      .sort(byPriority);
    const gapMatches = matches([
      gap.id,
      gap.title,
      gap.description,
      gap.missing,
      gap.whyItMatters,
      gap.direction,
      gap.gapType,
      gap.status,
      ...gap.citations,
    ]);
    const shown = gapMatches ? linked : linked.filter(suggestionMatches);
    if (gapMatches || shown.length) items.push({ gap, suggestions: shown });
  }
  const unlinked = data.suggestions
    .filter((s) => !suggestionGapIds(s).some((id) => gapIds.has(id)))
    .filter(suggestionMatches)
    .sort(byPriority);

  const observationsByText = new Map<string, ObservationItem>();
  for (const insight of data.insights) {
    for (const observation of insight.observations ?? []) {
      const existing = observationsByText.get(observation.text);
      if (existing) {
        existing.insights.push({ id: insight.id, title: insight.title });
        existing.citations = [
          ...new Set([...existing.citations, ...observation.citations]),
        ];
      } else {
        observationsByText.set(observation.text, {
          text: observation.text,
          citations: [...observation.citations],
          insights: [{ id: insight.id, title: insight.title }],
        });
      }
    }
  }
  const observations = [...observationsByText.values()].filter((item) =>
    matches([
      item.text,
      ...item.citations,
      ...item.insights.map((i) => i.title),
    ]),
  );

  const cited = <
    T extends { title: string; text: string; citations: string[] },
  >(
    list: T[] | undefined,
    extra: (item: T) => Array<string | undefined> = () => [],
  ) =>
    (list ?? []).filter((item) =>
      matches([item.title, item.text, ...item.citations, ...extra(item)]),
    );

  const explanations = (data.explanations ?? []).flatMap((set) => {
    if (matches([set.episode, set.verdict])) return [set];
    const hypotheses = set.hypotheses.filter((h) =>
      matches([
        h.id,
        h.statement,
        h.label,
        ...h.assumptions,
        ...[...h.supporting, ...h.contradicting].flatMap((entry) => [
          entry.reason,
          entry.citation,
        ]),
      ]),
    );
    return hypotheses.length ? [{ ...set, hypotheses }] : [];
  });

  return {
    questions: { items, unlinked },
    evidence: {
      contradictions: cited(data.contradictions, (c) => [
        c.kind,
        ...c.possibleReasons,
      ]),
      observations,
      sourceGroups: cited(data.sourceGroups),
      missingPeriods: cited(data.missingPeriods),
      uncertainTimes: cited(data.uncertainTimes),
    },
    inferences: {
      explanations,
      insights: data.insights.filter((item) =>
        matches([
          item.id,
          item.title,
          item.text,
          item.inference,
          ...(item.observations ?? []).map((o) => o.text),
          ...item.citations,
        ]),
      ),
      signals: cited(data.signals, (s) => [s.type, s.method?.name]).sort(
        (a, b) => b.score - a.score,
      ),
    },
  };
}

/** Item counts shown on each subsection tab. */
export function tabCounts(model: InsightsModel): Record<InsightsTab, number> {
  const e = model.evidence;
  const i = model.inferences;
  return {
    questions: model.questions.items.length,
    evidence:
      e.contradictions.length +
      e.observations.length +
      e.sourceGroups.length +
      e.missingPeriods.length +
      e.uncertainTimes.length,
    inferences: i.explanations.length + i.insights.length + i.signals.length,
  };
}

/** `follow_up_interview` → `Follow up interview`. */
export function humanize(value: string) {
  const text = value
    .replace(/_/g, " ")
    .replace(/\b(cctv|dna|lpr|ml|rfid)\b/gi, (acronym) =>
      acronym.toUpperCase(),
    );
  return text.charAt(0).toUpperCase() + text.slice(1);
}
