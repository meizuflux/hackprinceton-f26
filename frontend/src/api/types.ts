/** Shared wire types for the investigation board API. */
export type CitationId = string;

export type NodeType = "person" | "location" | "device" | "event" | "statement";

/** Which part of the pipeline produced a board item (backend/TRACE.md). Independent of certainty. */
export type Origin = "record" | "rules" | "ml" | "llm" | "agent";

/** Backend label: `observed` comes straight from records, `inferred` is analysis. */
export type Certainty = "observed" | "inferred";

/** A photo or video behind a board card (backend/MEDIA.md). */
export interface MediaInfo {
  evidenceId: string;
  kind: "photo" | "video";
  mediaType?: string | null;
  capturedUtc?: string | null;
  captureSource?: string | null;
  timeFlags?: string[];
  durationS?: number | null;
  width?: number | null;
  height?: number | null;
  deviceMake?: string | null;
  deviceModel?: string | null;
  gps?: { lat: number; lon: number } | null;
  /** LLM description: always inferred, never fed to findings. */
  vision?: {
    text: string;
    observations: Array<{ text: string; frameS?: number | null }>;
    model?: string;
    origin: Origin;
    certainty: Certainty;
  } | null;
}

export interface EvidenceNode {
  id: string;
  type: NodeType;
  /** Raw label from the records; stays visible as metadata so citations remain traceable. */
  label: string;
  /** Readable title (at most 44 characters); absent on older cases. */
  displayLabel?: string;
  /** Readable one-line context; absent on older cases. */
  displaySummary?: string;
  /** `llm` marks a model-written display label, shown as LLM-inferred. */
  labelOrigin?: "rules" | "llm";
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
  /** Pipeline provenance from the backend; absent on fixtures. */
  origin?: Origin;
  stage?: string;
  evidenceIds?: string[];
  media?: MediaInfo;
  /** Analysis item this card stands for (`ML-05`, `I-11`); absent on record cards. */
  itemId?: string;
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
  /** Pipeline provenance from the backend; absent on fixtures. */
  origin?: Origin;
  stage?: string;
  evidenceIds?: string[];
}

export interface SourceRecord {
  id: CitationId;
  path: string;
  /** Human file name for excerpt headings; absent on older cases. */
  fileLabel?: string;
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
  origin?: Origin;
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

export interface Contradiction {
  id: string;
  title: string;
  text: string;
  severity: string;
  kind: string;
  possibleReasons: string[];
  resolvingEvidence: string[];
  citations: CitationId[];
  status?: string;
  key?: string;
}

export interface Hypothesis {
  id: string;
  statement: string;
  /** e.g. best supported, plausible, weakly supported, contradicted. */
  label: string;
  points: number;
  independentSupport: number;
  supporting: Array<{ reason: string; citation: CitationId }>;
  contradicting: Array<{ reason: string; citation: CitationId }>;
  assumptions: string[];
  key?: string;
}

/** Competing explanations of one key event, with the backend's verdict. */
export interface ExplanationSet {
  episode: string;
  verdict: string;
  /** False means the evidence does not separate the explanations. */
  decided: boolean;
  hypotheses: Hypothesis[];
  /** Evidence that would tell the explanations apart. */
  discriminatingEvidence: Array<{
    artifact: string;
    why: string;
    params?: Record<string, string>;
  }>;
}

/** A traditional-ML lead (`ML-xx`). Always inferred; it never changes findings. */
export interface MlSignal {
  id: string;
  title: string;
  text: string;
  /** e.g. place_cluster, routine_outlier, message_triage. */
  type: string;
  /** Model ranking score, not a probability. */
  score: number;
  certainty?: Certainty;
  /** Model name and parameters as reported by the backend. */
  method?: { name?: string } & Record<string, unknown>;
  citations: CitationId[];
  status?: string;
  key?: string;
  /** Always `ml` from the backend. */
  origin?: Origin;
}

/** The same information repeated across several files; one origin. */
export interface SourceGroup {
  id: string;
  title: string;
  text: string;
  citations: CitationId[];
}

/** A source that is unusually silent; may be inactivity, an outage or missing data. */
export interface MissingPeriod {
  id: string;
  title: string;
  text: string;
  kind: string;
  start?: string;
  end?: string;
  citations: CitationId[];
}

/** Records whose time carries an assumption (for example no time zone). */
export interface UncertainTime {
  id: string;
  title: string;
  text: string;
  count?: number;
  citations: CitationId[];
}

/** The backend's opening view: a selection of existing board nodes, never new facts. */
export interface BoardStory {
  centerId: string;
  /** Centre first; at most 12. */
  nodeIds: string[];
  headline: { kind: "contradiction" | "gap" | "insight"; id: string } | null;
  reason: string;
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
  contradictions?: Contradiction[];
  explanations?: ExplanationSet[];
  signals?: MlSignal[];
  sourceGroups?: SourceGroup[];
  missingPeriods?: MissingPeriod[];
  uncertainTimes?: UncertainTime[];
  /** IANA time zone the case is displayed in. Times on the wire are ISO 8601. */
  timezone?: string;
  /** Opening story chosen by the backend; absent from the mock adapter. */
  story?: BoardStory | null;
}

export type IngestionStatus = "processing" | "ready" | "failed";
export interface UploadOptions {
  /** Shown as the case title; the backend derives the case ID from it. */
  caseName?: string;
  /** `live` makes billed model calls; `replay` (default) uses the committed cache. */
  analysisMode?: "replay" | "live";
}

/** Run trace event (backend/TRACE.md). Times are on the replay clock. */
export type TracePhase = "ingest" | "rules" | "ml" | "llm" | "agent" | "output";
export interface TraceEvent {
  seq: number;
  tMs: number;
  phase: TracePhase;
  type:
    | "run_started"
    | "phase_started"
    | "phase_finished"
    | "file_hashed"
    | "file_parsed"
    | "entities_linked"
    | "stage_finished"
    | "ml_signal"
    | "llm_call"
    | "agent_tool"
    | "insight_recorded"
    | "run_finished";
  [field: string]: unknown;
}
export interface TracePage {
  status: IngestionStatus;
  timing: "recorded" | "estimated" | "live";
  events: TraceEvent[];
  next: number;
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

/** One file from the authoritative ingestion inventory. */
export interface EvidenceFile {
  evidenceId: string;
  fileId: number;
  path: string;
  filename: string;
  sha256: string;
  bytes: number;
  format: string;
  evidenceType: string;
  parseStatus: string;
  recordCount: number;
  /** Null when the manifest lists no hash for the file. */
  manifestMatch: boolean | null;
  origin: string;
  title?: string | null;
}

export interface RecordPage {
  total: number;
  limit: number;
  offset: number;
  /** Record types and counts within the file filter. */
  types?: Record<string, number>;
  items: NormalizedEvidenceRecord[];
}

/** 0-based item range to highlight; a column span applies only to single-item ranges. */
export interface ViewRange {
  start: number;
  end: number;
  colStart?: number;
  colEnd?: number;
}

export type EvidenceViewKind =
  | "table"
  | "text"
  | "json"
  | "document"
  | "image"
  | "video"
  | "audio"
  | "pdf"
  | "binary";

/** A stored evidence file in viewable form, with a citation resolved by the backend. */
export interface EvidenceView {
  evidenceId: string;
  fileId: number;
  path: string;
  filename: string;
  sha256: string;
  bytes: number;
  format: string;
  evidenceType: string;
  parseStatus: string;
  manifestMatch: boolean | null;
  recordCount: number;
  kind: EvidenceViewKind;
  mediaType: string | null;
  notes: string[];
  pretty?: boolean;
  target: {
    locator: string;
    resolved: boolean;
    recordIds: number[];
    sharedRecordIds: number[];
    ranges: ViewRange[];
    sharedRanges: ViewRange[];
    page: number | null;
    whole: boolean;
    note?: string;
  } | null;
  table?: {
    columns: string[];
    total: number;
    offset: number;
    limit: number;
    items: Array<{ row: number; line: number; cells: string[] }>;
  };
  lines?: {
    unit: "line" | "paragraph";
    total: number;
    offset: number;
    limit: number;
    items: Array<{
      n: number;
      text: string;
      label?: string;
      truncated?: boolean;
    }>;
  };
}

export interface AuditChainEntry {
  seq: number;
  time: string;
  stage: string;
  action: string;
  /** Ingestion file the step concerns, when there is one. */
  fileId?: number | null;
  detail: Record<string, unknown>;
  hash: string;
  prevHash: string;
  source: "ingest" | "analysis";
}

export interface AuditChain {
  verified: boolean;
  head: string;
  checks: Array<{ source: string; ok: boolean; message: string }>;
  entries: AuditChainEntry[];
}

export type ApiMode = "mock" | "live";

export interface CaseApi {
  mode: ApiMode;
  createUpload(file: File, options?: UploadOptions): Promise<UploadResult>;
  getStatus(jobId: string): Promise<IngestionProgress>;
  /** Without an ID, returns the most recent ready case. */
  getCase(caseId?: string): Promise<CaseData>;
  listCases(): Promise<CaseSummary[]>;
  /** Run trace from `after` (exclusive); undefined when the adapter has no trace (the mock). */
  getTrace(caseId: string, after?: number): Promise<TracePage | undefined>;
  /** Whether the server can make billed model calls (`GET /health` `llmLive`); absent on the mock. */
  getHealth?(): Promise<{ llmLive: boolean }>;
  /** Opens the demo case (a prepared snapshot with the live adapter) and returns its ID. */
  openDemo(): Promise<string>;
  /** Evidence file inventory; empty when the adapter has no ingestion output. */
  listFiles(caseId: string): Promise<EvidenceFile[]>;
  getRecords(
    caseId: string,
    query?: {
      evidenceId?: string;
      recordType?: string;
      limit?: number;
      offset?: number;
    },
  ): Promise<RecordPage>;
  /** Hash-chained audit log, re-verified; undefined without ingestion output. */
  getAuditChain(caseId: string): Promise<AuditChain | undefined>;
  /** A stored file with a citation locator resolved; undefined without ingestion output. */
  viewEvidence(
    caseId: string,
    evidenceId: string,
    query?: { locator?: string; offset?: number; limit?: number },
  ): Promise<EvidenceView | undefined>;
  /** URL of the original evidence file, when the adapter can serve bytes. `inline` renders media in place. */
  evidenceFileUrl(
    caseId: string,
    evidenceId: string,
    options?: { inline?: boolean },
  ): string | undefined;
}
