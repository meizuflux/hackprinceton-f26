/** Shared wire types for the investigation board API. */
export type CitationId = string;

export type NodeType = "person" | "location" | "device" | "event" | "statement";

/** Backend label: `observed` comes straight from records, `inferred` is analysis. */
export type Certainty = "observed" | "inferred";

export interface EvidenceNode {
  id: string;
  type: NodeType;
  label: string;
  citations: CitationId[];
  position: { x: number; y: number };
  summary: string;
  subtitle: string;
  time?: string;
  gapId?: string;
  size?: { width: number; height: number };
  certainty?: Certainty;
  /** Backend stable key; investigator overrides target it. */
  key?: string;
  score?: number;
}

export interface EvidenceEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  label: string;
  citations: CitationId[];
  /** Arrowheads require an explicit direction from the adapter. */
  directed?: boolean;
  certainty?: Certainty;
  /** Why the backend drew this relationship. */
  basis?: string;
}

export interface SourceRecord {
  id: CitationId;
  path: string;
  kind: string;
  timestamp: string;
  hash: string;
  excerpt: string;
  metadata: Record<string, string>;
}

export interface EvidenceGap {
  id: string;
  title: string;
  description: string;
  score: number;
  affectedClaims: string[];
  suggestedEvidence: string[];
  citations: CitationId[];
  gapType?:
    "missing" | "failed_extraction" | "conflicting" | "uncertain" | string;
  status?: string;
  previousStatus?: string | null;
  missing?: string;
  whyItMatters?: string;
  direction?: string;
  answer?: string | null;
  /** Board node IDs the gap concerns. */
  nodeIds?: string[];
  key?: string;
}

export interface CitedText {
  text: string;
  citations: CitationId[];
}

export interface Insight {
  id: string;
  title: string;
  text: string;
  score: number;
  citations: CitationId[];
  certainty?: Certainty;
  /** A label set by independent sources; never a probability. */
  confidence?: "low" | "medium" | "high" | string;
  status?: string;
  observations?: CitedText[];
  inference?: string;
  unknowns?: string[];
  counterevidence?: string[];
  assumptions?: string[];
  limitations?: string[];
  key?: string;
}

export interface EvidenceSuggestion {
  id: string;
  title: string;
  description: string;
  priority: number;
  query: string;
  citations: CitationId[];
  gapId: string;
  gapIds?: string[];
  artifact?: string;
  score?: number;
  key?: string;
}

export interface AuditRecord {
  id: string;
  time: string;
  title: string;
  description: string;
  citations: CitationId[];
}

/** Presentation of authoritative ingestion output, never derived from fixtures. */
export interface NormalizedEvidenceRecord {
  id: string;
  recordType: string;
  fields: Record<string, string | number | boolean | null>;
  citations: Array<{ evidenceId: string; locator: string; sourceId?: string }>;
}

export interface CaseData {
  id: string;
  title: string;
  subtitle: string;
  timeRange: { start: string; end: string };
  nodes: EvidenceNode[];
  edges: EvidenceEdge[];
  gaps: EvidenceGap[];
  insights: Insight[];
  suggestions: EvidenceSuggestion[];
  sources: SourceRecord[];
  audit: AuditRecord[];
  normalizedRecords?: NormalizedEvidenceRecord[];
  /** IANA time zone the case is displayed in. Times on the wire are ISO 8601. */
  timezone?: string;
}

export type IngestionStatus = "processing" | "ready" | "failed";
export interface UploadOptions {
  /** Shown as the case title; the backend derives the case ID from it. */
  caseName?: string;
}
export interface UploadResult {
  jobId: string;
  caseId?: string;
}
export interface IngestionProgress {
  status: IngestionStatus;
  progress: number;
  message: string;
  stage?: string;
  caseId?: string;
}

/** One entry in the case list. Only the live API persists cases. */
export interface CaseSummary {
  caseId: string;
  title: string;
  created: string;
  versions: number;
  ready: boolean;
}

export type ApiMode = "mock" | "live";

export interface CaseApi {
  mode: ApiMode;
  createUpload(file: File, options?: UploadOptions): Promise<UploadResult>;
  getStatus(jobId: string): Promise<IngestionProgress>;
  /** Without an ID, returns the most recent ready case. */
  getCase(caseId?: string): Promise<CaseData>;
  listCases(): Promise<CaseSummary[]>;
  /** URL of the original evidence file, when the adapter can serve bytes. */
  evidenceFileUrl(caseId: string, evidenceId: string): string | undefined;
}
