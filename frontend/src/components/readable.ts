/**
 * Readable wording for board cards and cited excerpts. Presentation only: the
 * backend's `displayLabel`, `displaySummary` and `fileLabel` win when present;
 * otherwise raw labels are tidied (spacing, case, separators) without adding,
 * dropping into new meaning or changing any value. The raw label always stays
 * available as metadata so citations remain traceable.
 */
import type {
  CaseData,
  EvidenceNode,
  MlSignal,
  SourceRecord,
} from "../api/types";

type Labelled = Pick<EvidenceNode, "label"> &
  Partial<Pick<EvidenceNode, "displayLabel" | "summary" | "displaySummary">>;

/** Backend labels are cut at this length, so a last `k=v` pair this close may be partial. */
const BACKEND_LABEL_CUT = 58;

const CODE = /^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$/;

/** `DOOR_HELD_OPEN` → `Door held open`; other text is unchanged. */
export function humanizeCode(text: string) {
  return CODE.test(text)
    ? text.charAt(0) + text.slice(1).toLowerCase().replace(/_/g, " ")
    : text;
}

/** `reader_id` → `reader`, `officer_note` → `officer note`. */
function keyWords(key: string) {
  return key.replace(/_id$/i, "").replace(/_/g, " ").trim();
}

/**
 * Tidies a raw record label for display:
 * - `scan_id=RF-00111; reader_id=RF-SC-EBC-01; …` → `Scan RF-00111 · reader RF-SC-EBC-01`
 *   (at most three pairs; a pair cut short by the backend is dropped, never guessed);
 * - `DOOR_HELD_OPEN @ P2 lobby door` → `Door held open at P2 lobby door`.
 * Anything else is returned unchanged.
 */
export function tidyLabel(label: string) {
  const text = label.trim();
  if (/^\s*[\w.-]+=[^;]*(;\s*[\w.-]+=[^;]*)+;?\s*\S*$/.test(text)) {
    const parts = text.split(/;\s*/).filter(Boolean);
    let pairs = parts
      .map((part) => part.split("="))
      .filter((pair) => pair.length >= 2 && pair[0] && pair.slice(1).join("="));
    // The last pair of a label at the backend's cut length may be partial;
    // a trailing fragment without `=` has already been dropped above.
    if (
      text.length >= BACKEND_LABEL_CUT &&
      pairs.length > 1 &&
      parts.at(-1)?.includes("=")
    )
      pairs = pairs.slice(0, -1);
    const shown = pairs.slice(0, 3).map(([key, ...rest], index) => {
      const value = rest.join("=");
      const words = keyWords(key);
      const name =
        index === 0 ? words.charAt(0).toUpperCase() + words.slice(1) : words;
      return `${name} ${value}`;
    });
    if (shown.length) return shown.join(" · ");
  }
  const at = text.match(/^(.+?) @ (.+)$/);
  if (at) return `${humanizeCode(at[1])} at ${at[2]}`;
  return humanizeCode(text);
}

/** The card title: the backend's readable label, else the tidied raw label. */
export function cardTitle(node: Labelled) {
  return node.displayLabel?.trim() || tidyLabel(node.label);
}

/** The raw label as metadata, only when the title does not already show it verbatim. */
export function rawLabelNote(node: Labelled) {
  return cardTitle(node) === node.label ? undefined : node.label;
}

export function cardSummary(node: Labelled) {
  return node.displaySummary?.trim() || node.summary || "";
}

/** `row=72` → `row 72`; `event_id=BDG-000615` → `event BDG-000615`. */
export function formatLocator(locator: string) {
  return locator
    .split(/;\s*/)
    .map((part) => {
      const [key, ...rest] = part.split("=");
      return rest.length ? `${keyWords(key)} ${rest.join("=")}` : part;
    })
    .join(", ");
}

/** File name for an excerpt heading: the backend's label, else the stored file name. */
export function sourceFileLabel(
  source: Pick<SourceRecord, "path" | "id"> & { fileLabel?: string },
) {
  return source.fileLabel?.trim() || source.path.split("/").pop() || source.id;
}

/** `Workstation log · row 72`, with the citation ID kept for a secondary line. */
export function sourceHeading(source: SourceRecord) {
  const locator = source.metadata?.locator;
  return {
    heading: [sourceFileLabel(source), locator && formatLocator(locator)]
      .filter(Boolean)
      .join(" · "),
    citation: source.id,
  };
}

/** The ML signal behind an ML card (same stable key), for its method name. */
export function signalFor(
  node: Pick<EvidenceNode, "key" | "origin">,
  signals: CaseData["signals"],
): MlSignal | undefined {
  if (node.origin !== "ml" || !node.key) return undefined;
  return signals?.find((signal) => signal.key === node.key);
}

/**
 * Short method wording for a card: the reported name without parentheses or
 * trailing clauses (`IsolationForest on daily movement profiles` →
 * `IsolationForest`). The full name stays in the tooltip and inspector.
 */
export function shortMethod(name?: string) {
  if (!name) return undefined;
  const short = name
    .replace(/\s*\([^)]*\)/g, "")
    .split(/\s+on\s+|,\s*/)[0]
    .trim();
  return short.length > 30 ? `${short.slice(0, 29)}…` : short || undefined;
}
