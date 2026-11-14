import type { CaseData, SourceRecord } from "./types";
export type { NormalizedEvidenceRecord } from "./types";

/** A source as presented by the current case contract. This is not a raw file. */
export interface EvidenceFileEntry extends SourceRecord {
  filename: string;
  citationCount: number;
}

/**
 * Build the searchable source index from citations already present in CaseData.
 * The mock adapter only supplies synthetic excerpts; it does not supply bytes.
 */
export function listEvidenceFiles(data: CaseData): EvidenceFileEntry[] {
  const citationCounts = new Map<string, number>();
  const cited = [
    ...data.nodes,
    ...data.edges,
    ...data.gaps,
    ...data.insights,
    ...data.suggestions,
    ...data.audit,
  ];
  for (const item of cited) {
    for (const citation of item.citations) {
      citationCounts.set(citation, (citationCounts.get(citation) ?? 0) + 1);
    }
  }
  return data.sources.map((source) => ({
    ...source,
    filename: source.path.split("/").filter(Boolean).at(-1) ?? source.path,
    citationCount: citationCounts.get(source.id) ?? 0,
  }));
}
