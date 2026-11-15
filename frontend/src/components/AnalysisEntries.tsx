import { CircleHelp, Lightbulb, Target, type LucideIcon } from "lucide-react";
import type { CaseData } from "../api/types";
import type { Tab } from "./board-focus";
import "./analysis-entries.css";

export const analysisEntries: ReadonlyArray<{
  id: Tab;
  label: string;
  noun: string;
  icon: LucideIcon;
}> = [
  { id: "gaps", label: "Gaps", noun: "open questions", icon: CircleHelp },
  { id: "insights", label: "Insights", noun: "insights", icon: Lightbulb },
  {
    id: "suggestions",
    label: "Next evidence",
    noun: "evidence requests",
    icon: Target,
  },
];

export function analysisCount(data: CaseData, tab: Tab) {
  return tab === "gaps"
    ? data.gaps.length
    : tab === "insights"
      ? data.insights.length
      : data.suggestions.length;
}

/**
 * One labelled entry per kind of analysis, each opening the review dock on the
 * tab it names. On the board the entries toggle the dock (pressing the open
 * one closes it); elsewhere they return to the board with that tab open.
 */
export function AnalysisEntries({
  data,
  active,
  onOpen,
}: {
  data: CaseData;
  /**
   * The tab shown in the dock, or null when it shows no analysis. Leave
   * undefined outside the board, where the entries navigate instead of toggle.
   */
  active?: Tab | null;
  onOpen: (tab: Tab) => void;
}) {
  const toggles = active !== undefined;
  return (
    <div className="analysis-entries" role="group" aria-label="Case analysis">
      {analysisEntries.map(({ id, label, noun, icon: Icon }) => {
        const count = analysisCount(data, id);
        const open = toggles && active === id;
        return (
          <button
            key={id}
            id={toggles ? `analysis-entry-${id}` : undefined}
            type="button"
            className={`analysis-entry entry-${id}`}
            aria-pressed={toggles ? open : undefined}
            aria-controls={toggles ? "review-dock" : undefined}
            aria-label={`${label}: ${count} ${noun}`}
            title={
              open
                ? `Close ${label.toLowerCase()}`
                : `Open ${label.toLowerCase()} beside the mind map`
            }
            onClick={() => onOpen(id)}
          >
            <Icon size={15} aria-hidden="true" />
            <span className="analysis-entry-label">{label}</span>
            <strong>{count}</strong>
          </button>
        );
      })}
    </div>
  );
}
