import {
  ArrowRight,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Lightbulb,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import type { CaseData } from "../api/types";
import { FileKindIcon } from "./FileKindIcon";
import { sourceRow, supportingSources, type Headline } from "./headline";
import "./headline-panel.css";

const STATUS_ICON = {
  contradiction: TriangleAlert,
  gap: CircleHelp,
  insight: Lightbulb,
};

/**
 * The case's headline finding, shown in the review dock when the board opens.
 * Everything here is the backend's item and its cited sources; the panel adds
 * no facts. Rows open a source in the inspector; the button opens them all.
 */
export function HeadlinePanel({
  headline,
  data,
  onInspectSource,
  onReviewSources,
}: {
  headline: Headline;
  data: CaseData;
  onInspectSource: (sourceId: string) => void;
  onReviewSources: () => void;
}) {
  const Icon = STATUS_ICON[headline.kind];
  const rows = supportingSources(data, headline.citations, 3).map((source) =>
    sourceRow(source, data.timezone),
  );
  const total = new Set(headline.citations).size;
  return (
    <div className={`headline-panel is-${headline.kind}`}>
      <p className="headline-status-row">
        <span className="headline-status">
          <Icon size={14} aria-hidden="true" />
          {headline.status}
        </span>
        <span>To verify, not proof</span>
      </p>
      <h3 className="headline-title">{headline.title}</h3>
      {headline.statement && (
        <figure className="headline-statement">
          <blockquote>{headline.statement.quote}</blockquote>
          <figcaption>Asserted by {headline.statement.speaker}</figcaption>
        </figure>
      )}
      {headline.summary && (
        <p className="headline-summary">{headline.summary}</p>
      )}

      {rows.length > 0 && (
        <section
          className="headline-sources"
          aria-labelledby="headline-sources-title"
        >
          <h4 id="headline-sources-title">Supporting evidence</h4>
          <ul>
            {rows.map((row) => (
              <li key={row.id}>
                <button
                  type="button"
                  onClick={() => onInspectSource(row.id)}
                  aria-label={`Inspect source: ${row.title}, ${row.file}${row.time ? `, ${row.time}` : ""}`}
                >
                  <span className="headline-source-icon">
                    <FileKindIcon format={row.format} size={16} />
                  </span>
                  <span className="headline-source-text">
                    <strong>
                      {row.title}
                      {row.asserted && <em>Asserted</em>}
                    </strong>
                    <span className="headline-source-detail">{row.detail}</span>
                    <span className="headline-source-meta">
                      {row.time && (
                        <>
                          <time>{row.time}</time>
                          {" · "}
                        </>
                      )}
                      {row.file}
                      {row.locator && <> · {row.locator}</>}
                    </span>
                  </span>
                  <ChevronRight
                    size={15}
                    aria-hidden="true"
                    className="headline-source-go"
                  />
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Pinned to the bottom of the dock so the primary action stays in view on short screens. */}
      <div className="headline-actions">
        <button
          type="button"
          className="button button-primary full-width"
          onClick={onReviewSources}
        >
          Review sources{total > rows.length ? ` (${total})` : ""}
          <ArrowRight size={16} aria-hidden="true" />
        </button>
      </div>

      {headline.context.items.length > 0 && (
        <details className="headline-context">
          <summary>
            {headline.context.label}
            <span>{headline.context.items.length}</span>
            <ChevronDown size={14} aria-hidden="true" />
          </summary>
          <ul>
            {headline.context.items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </details>
      )}
      <p className="headline-note">
        <ShieldCheck size={15} aria-hidden="true" />
        {headline.note}
      </p>
    </div>
  );
}
