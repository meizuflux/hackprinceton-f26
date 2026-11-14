import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from "@xyflow/react";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronRight,
  CircleHelp,
  FileArchive,
  Fingerprint,
  FolderOpen,
  GitBranch,
  History,
  Layers,
  Lightbulb,
  LoaderCircle,
  Plus,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Target,
  Upload,
  X,
} from "lucide-react";
import { api } from "./api/client";
import type { CaseData } from "./api/types";
import { EvidenceNode, type PinData } from "./components/EvidenceNode";
import { Inspector, type Selection } from "./components/Inspector";
const nodeTypes = { evidence: EvidenceNode };
type Tab = "gaps" | "insights" | "suggestions";
function Board({ data }: { data: CaseData }) {
  const [selection, setSelection] = useState<Selection | null>(null);
  const [tab, setTab] = useState<Tab>("gaps");
  const [audit, setAudit] = useState(false);
  const [search, setSearch] = useState("");
  const initialNodes: Node<PinData>[] = useMemo(
    () =>
      data.nodes.map((n) => ({
        id: n.id,
        type: "evidence",
        position: n.position,
        data: {
          ...n,
          gapScore: data.gaps.find((g) => g.id === n.gapId)?.score,
        },
      })),
    [data],
  );
  const initialEdges: Edge[] = useMemo(
    () =>
      data.edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.label,
        type: "default",
        style: {
          stroke: ["claim", "describes", "reported_near"].includes(e.type)
            ? "#bd985a"
            : "#b86350",
          strokeWidth: 1.5,
          strokeDasharray: ["claim", "describes", "reported_near"].includes(
            e.type,
          )
            ? "5 5"
            : undefined,
        },
        labelStyle: { fill: "#d9d0bd", fontSize: 10 },
        labelBgStyle: { fill: "#444039", fillOpacity: 0.95 },
        labelBgPadding: [7, 4] as [number, number],
        labelBgBorderRadius: 3,
      })),
    [data],
  );
  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);
  const visibleNodes = nodes.map((n) => ({
    ...n,
    className:
      search &&
      !`${n.data.label} ${n.data.summary}`
        .toLowerCase()
        .includes(search.toLowerCase())
        ? "dimmed-node"
        : "",
    data: {
      ...n.data,
      active: selection?.kind === "node" && selection.id === n.id,
    },
  }));
  const inspect = useCallback(
    (kind: Selection["kind"], id: string, sourceId?: string) =>
      setSelection({ kind, id, sourceId }),
    [],
  );
  return (
    <>
      <div className="case-toolbar">
        <div className="breadcrumbs">
          Workspace <ChevronRight size={12} /> Cases <ChevronRight size={12} />
          <span>{data.id}</span>
        </div>
        <div className="toolbar-right">
          <span className="saved">
            <span /> Local session
          </span>
          <button
            className={`text-button ${audit ? "selected" : ""}`}
            onClick={() => setAudit(!audit)}
          >
            <History size={15} /> Audit trail
          </button>
        </div>
      </div>
      <section className="case-heading">
        <div>
          <div className="eyebrow">
            INVESTIGATION WORKSPACE{" "}
            <span className="demo-tag">SYNTHETIC DEMO</span>
          </div>
          <h1>
            {data.title}
            <span className="case-status">
              <span /> In review
            </span>
          </h1>
          <p>{data.subtitle}</p>
        </div>
        <div className="case-stats">
          <div>
            <strong>{data.sources.length.toString().padStart(2, "0")}</strong>
            <span>Artifacts</span>
          </div>
          <div>
            <strong>{data.nodes.length.toString().padStart(2, "0")}</strong>
            <span>Entities</span>
          </div>
          <div className="stat-amber">
            <strong>{data.gaps.length.toString().padStart(2, "0")}</strong>
            <span>Open gaps</span>
          </div>
        </div>
      </section>
      <div className="workspace">
        <div className="board-area">
          <div className="board-toolbar">
            <div className="board-view">
              <GitBranch size={15} />
              <span>Evidence board</span>
              <span className="view-divider" />{" "}
              <span className="muted">
                {data.nodes.length} pins · {data.edges.length} connections
              </span>
            </div>
            <div className="board-actions">
              <label className="board-search">
                <Search size={14} />
                <input
                  aria-label="Find evidence"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Find a pin…"
                />
                <kbd>⌕</kbd>
              </label>
              <button
                className="icon-button"
                title="Toggle audit trail"
                aria-label="Toggle audit trail"
                onClick={() => {
                  setSelection(null);
                  setAudit(!audit);
                }}
              >
                <History size={16} />
              </button>
            </div>
          </div>
          <div className="canvas-wrap">
            <ReactFlow
              nodes={visibleNodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              nodeTypes={nodeTypes}
              onNodeClick={(_, n) => inspect("node", n.id)}
              onEdgeClick={(_, e) => inspect("edge", e.id)}
              onPaneClick={() => setSelection(null)}
              fitView
              fitViewOptions={{ padding: 0.17 }}
              minZoom={0.3}
              maxZoom={1.8}
              nodesConnectable={false}
              deleteKeyCode={null}
              proOptions={{ hideAttribution: true }}
            >
              <Background
                variant={BackgroundVariant.Dots}
                gap={20}
                size={1}
                color="#a48c692b"
              />
              <Controls showInteractive={false} />
              <MiniMap
                pannable
                zoomable
                nodeColor={(n) => (n.data.gapId ? "#ce9a53" : "#d4c9ae")}
                maskColor="#242721aa"
              />
            </ReactFlow>
            <div className="board-caption">
              <span className="live-dot" /> Every connection has a source.
            </div>
            <div className="board-legend">
              <span>
                <i className="legend-line" />
                Observed link
              </span>
              <span>
                <i className="legend-line dashed" />
                Claim to verify
              </span>
              <span>
                <i className="legend-gap" />
                Evidence gap
              </span>
            </div>
          </div>
          <div className="board-bottom">
            <span>
              <ShieldCheck size={13} /> Source-linked. Ready for review.
            </span>
            <span>
              Drag pins to arrange <span className="dot-separator">·</span>{" "}
              Scroll to zoom
            </span>
          </div>
        </div>
        <aside className="analysis-panel">
          <div className="analysis-heading">
            <div className="intelligence-icon">
              <Sparkles size={17} />
            </div>
            <div>
              <h2>Connect the dots</h2>
              <p>Follow the evidence forward.</p>
            </div>
            <span className="small-dot" />
          </div>
          <div
            className="analysis-tabs"
            role="tablist"
            aria-label="Case analysis"
          >
            {(
              [
                ["gaps", "Gaps", data.gaps.length],
                ["insights", "Insights", data.insights.length],
                ["suggestions", "Next evidence", null],
              ] as const
            ).map(([id, label, count]) => (
              <button
                key={id}
                role="tab"
                aria-selected={tab === id}
                className={tab === id ? "active" : ""}
                onClick={() => setTab(id)}
              >
                {label}
                {count !== null && <span>{count}</span>}
              </button>
            ))}
          </div>
          <div className="panel-content">
            <div className="panel-section-label">
              <span>
                {tab === "gaps"
                  ? "RANKED BY INVESTIGATIVE VALUE"
                  : tab === "insights"
                    ? "PATTERNS WORTH A CLOSER LOOK"
                    : "HIGHEST-VALUE NEXT STEPS"}
              </span>
              <SlidersHorizontal size={12} />
            </div>
            {tab === "gaps" &&
              data.gaps.map((g, i) => (
                <button
                  key={g.id}
                  className={`analysis-card gap-card ${selection?.id === g.id ? "selected" : ""}`}
                  onClick={() => inspect("gap", g.id)}
                >
                  <div className="card-topline">
                    <span className="card-index">0{i + 1}</span>
                    <span className="priority-badge">
                      {Math.round(g.score * 100)} <span>/ 100</span>
                    </span>
                  </div>
                  <h3>{g.title}</h3>
                  <p>{g.description}</p>
                  <div className="card-bottomline">
                    <span>
                      <Target size={12} /> {g.suggestedEvidence.length} next
                      step{g.suggestedEvidence.length === 1 ? "" : "s"}
                    </span>
                    <span>
                      Investigate <ArrowUpRight size={13} />
                    </span>
                  </div>
                </button>
              ))}
            {tab === "insights" &&
              data.insights.map((g) => (
                <button
                  key={g.id}
                  className="analysis-card insight-card"
                  onClick={() => inspect("insight", g.id)}
                >
                  <div className="insight-label">
                    <Lightbulb size={13} /> INFERENCE ·{" "}
                    {Math.round(g.score * 100)}% confidence
                  </div>
                  <h3>{g.title}</h3>
                  <p>{g.text}</p>
                  <div className="card-bottomline">
                    <span>{g.citations.length} cited sources</span>
                    <ArrowUpRight size={14} />
                  </div>
                </button>
              ))}
            {tab === "suggestions" &&
              data.suggestions.map((g, i) => (
                <button
                  key={g.id}
                  className="analysis-card"
                  onClick={() => inspect("suggestion", g.id)}
                >
                  <div className="insight-label">
                    <Target size={13} /> PRIORITY {i + 1}
                  </div>
                  <h3>{g.title}</h3>
                  <p>{g.description}</p>
                  <div className="card-bottomline">
                    <span>View example query</span>
                    <ArrowUpRight size={14} />
                  </div>
                </button>
              ))}
            <div className="reasoning-note">
              <ShieldCheck size={16} />
              <p>
                {tab === "gaps"
                  ? "A gap is a question, not a conclusion. Scores help prioritize what to verify next."
                  : "Inferences require investigator verification. Open any result to inspect its sources."}
              </p>
            </div>
          </div>
          <div className="analysis-footer">
            <span className="live-dot" />
            Mock analysis <span>·</span> All results traceable
          </div>
        </aside>
      </div>
      {audit && (
        <section className="audit-panel">
          <div className="audit-heading">
            <div>
              <History size={16} />
              <h2>Audit trail</h2>
              <span>Simulated processing record</span>
            </div>
            <button
              className="icon-button"
              aria-label="Close audit trail"
              onClick={() => setAudit(false)}
            >
              <X size={17} />
            </button>
          </div>
          <div className="audit-steps">
            {data.audit.map((a) => (
              <div className="audit-step" key={a.id}>
                <Check size={13} />
                <time>{a.time}</time>
                <h3>{a.title}</h3>
                <p>{a.description}</p>
                {a.citations.map((id) => (
                  <button
                    key={id}
                    onClick={() => {
                      const node = data.nodes.find((n) =>
                        n.citations.includes(id),
                      );
                      if (node) inspect("node", node.id, id);
                    }}
                  >
                    {data.sources
                      .find((s) => s.id === id)
                      ?.path.split("/")
                      .pop()}{" "}
                    <ArrowUpRight size={10} />
                  </button>
                ))}
              </div>
            ))}
          </div>
        </section>
      )}
      <Inspector
        selection={selection}
        data={data}
        onSelect={setSelection}
        onClose={() => setSelection(null)}
      />
    </>
  );
}
export default function App() {
  const [started, setStarted] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const caseQuery = useQuery({
    queryKey: ["case"],
    queryFn: () => api.getCase(),
    enabled: started,
  });
  const statusQuery = useQuery({
    queryKey: ["upload", jobId],
    queryFn: () => api.getStatus(jobId!),
    enabled: !!jobId,
    refetchInterval: (q) => (q.state.data?.status === "ready" ? false : 650),
  });
  const ready = statusQuery.data?.status === "ready";
  useEffect(() => {
    if (!uploadOpen) return;
    const previous = document.activeElement as HTMLElement | null;
    const dialog = document.querySelector<HTMLElement>(".upload-modal");
    const focusable = () =>
      Array.from(
        dialog?.querySelectorAll<HTMLElement>(
          'button:not(:disabled), input:not([hidden]):not(:disabled), [tabindex="0"]',
        ) ?? [],
      );
    focusable()[0]?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && (!uploading || ready)) {
        event.preventDefault();
        closeUpload();
      }
      if (event.key === "Tab") {
        const items = focusable();
        const first = items[0];
        const last = items.at(-1);
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => {
      window.removeEventListener("keydown", handleKey);
      previous?.focus();
    };
  }, [uploadOpen, uploading, ready]);

  async function upload() {
    if (!file) return;
    setError("");
    setUploading(true);
    try {
      const result = await api.createUpload(file);
      setJobId(result.jobId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed. Try again.");
      setUploading(false);
    }
  }
  function closeUpload() {
    setUploadOpen(false);
    setJobId(null);
    setUploading(false);
    setFile(null);
    setError("");
  }
  function demo() {
    setStarted(true);
    closeUpload();
  }
  return (
    <div className="app-shell">
      <nav className="rail" aria-label="Main navigation">
        <a
          className="brand-mark"
          href="#"
          aria-label="Compstat home"
          onClick={(e) => {
            e.preventDefault();
            setStarted(false);
          }}
        >
          <Fingerprint size={26} />
        </a>
        <div className="rail-links">
          <button
            className={!started ? "" : "active"}
            aria-label="Evidence workspace"
            title="Evidence workspace"
            onClick={() => setStarted(true)}
          >
            <Layers size={21} />
          </button>
          <button
            aria-label="Upload case"
            title="Upload case"
            onClick={() => setUploadOpen(true)}
          >
            <FolderOpen size={21} />
          </button>
        </div>
        <div className="rail-bottom">
          <span className="rail-version">v.01</span>
          <div className="avatar" title="Local investigator">
            JD
          </div>
        </div>
      </nav>
      <main>
        <header className="app-header">
          <div className="wordmark">
            compstat<span> / </span>
            <small>Clarity from complexity.</small>
          </div>
          <div className="header-actions">
            <span className="environment">
              <span /> DEMO ENVIRONMENT
            </span>
            <button
              className="button button-primary button-small"
              onClick={() => setUploadOpen(true)}
            >
              <Plus size={15} /> New case
            </button>
          </div>
        </header>
        {!started ? (
          <div className="welcome">
            <div className="welcome-copy">
              <div className="eyebrow">
                <span className="live-dot" /> EVIDENCE. CONNECTED.
              </div>
              <h1>
                The bigger picture.
                <br />
                <em>Every little detail.</em>
              </h1>
              <p>
                Bring scattered evidence into focus. Uncover connections, see
                what’s missing, and follow every insight back to its source.
              </p>
              <div className="welcome-actions">
                <button
                  className="button button-primary"
                  onClick={() => setUploadOpen(true)}
                >
                  <Upload size={16} /> Upload a case
                </button>
                <button className="button button-secondary" onClick={demo}>
                  Explore demo case <ArrowRight size={16} />
                </button>
              </div>
              <div className="welcome-trust">
                <ShieldCheck size={15} />
                <span>
                  Fully traceable evidence. Investigator-led decisions.
                </span>
              </div>
            </div>
            <div className="welcome-board">
              <div className="welcome-board-label">
                <span /> YOUR INVESTIGATION, IN FOCUS
              </div>
              <div className="preview-thread thread-a" />
              <div className="preview-thread thread-b" />
              <div className="preview-card preview-person">
                <span className="pushpin" />
                <div className="eyebrow">PERSON OF INTEREST</div>
                <div className="preview-avatar">
                  <Fingerprint size={55} strokeWidth={0.8} />
                </div>
                <h3>Alex Morgan</h3>
                <p>Inventory lead</p>
                <span className="mini-source">↗ 2 linked sources</span>
              </div>
              <div className="preview-card preview-note">
                <span className="pushpin" />
                <div className="eyebrow">A QUESTION WORTH ASKING</div>
                <h3>
                  What happened
                  <br />
                  from 20:31–20:50?
                </h3>
                <p>A 19-minute gap in camera coverage.</p>
                <div className="preview-gap">
                  EVIDENCE GAP <ArrowUpRight size={13} />
                </div>
              </div>
              <div className="preview-card preview-source">
                <span className="pushpin" />
                <FileArchive size={24} />
                <h3>CAM-4E-notes.txt</h3>
                <p>Original source · export note</p>
                <div className="mini-wave">▂ ▅ ▃ ▆ ▂ ▇ ▄ ▃ ▅ ▂ ▆ ▄ ▂ ▅</div>
              </div>
              <div className="welcome-board-footer">
                <LinkLabel /> One board. A clearer way forward.
              </div>
            </div>
            <div className="welcome-bottom">
              <span>01 / CONNECT THE EVIDENCE</span>
              <span>02 / FIND THE GAPS</span>
              <span>03 / KNOW WHAT’S NEXT</span>
            </div>
          </div>
        ) : caseQuery.isPending ? (
          <div className="center-state">
            <LoaderCircle className="spin" />
            <h2>Opening evidence workspace…</h2>
          </div>
        ) : caseQuery.isError ? (
          <div className="center-state">
            <h2>Couldn’t load the case</h2>
            <button
              className="button button-primary"
              onClick={() => caseQuery.refetch()}
            >
              Try again
            </button>
          </div>
        ) : (
          <Board data={caseQuery.data} />
        )}
        <footer className="app-footer">
          <span>
            <Fingerprint size={12} /> COMPSTAT{" "}
            <span className="dot-separator">/</span> A clearer chain of
            evidence.
          </span>
          <span>
            Hackathon prototype <span className="dot-separator">·</span>{" "}
            Synthetic data only
          </span>
        </footer>
      </main>
      {uploadOpen && (
        <div
          className="modal-backdrop"
          onClick={(e) => {
            if (e.target === e.currentTarget && !uploading) closeUpload();
          }}
        >
          <section
            className="upload-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="upload-title"
          >
            <button
              className="icon-button modal-close"
              disabled={uploading && !ready}
              onClick={closeUpload}
              aria-label="Close upload"
            >
              <X size={20} />
            </button>
            <div className="upload-icon">
              <Upload size={24} />
            </div>
            <div className="eyebrow">START AN INVESTIGATION</div>
            <h2 id="upload-title">Every detail starts somewhere.</h2>
            <p>Bring your case files together in one evidence workspace.</p>
            <div
              className={`dropzone ${dragging ? "dragging" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                if (!uploading) {
                  setFile(e.dataTransfer.files[0] ?? null);
                  setError("");
                }
              }}
            >
              <FileArchive size={30} />
              <strong>{file ? file.name : "Drop a case ZIP here"}</strong>
              <span>
                {file
                  ? `${(file.size / 1024 / 1024).toFixed(2)} MB`
                  : "Messages, locations, photo metadata, statements"}
              </span>
              <button
                disabled={uploading}
                className="text-button"
                onClick={() => inputRef.current?.click()}
              >
                {file ? "Choose another file" : "or browse files"}{" "}
                <ArrowUpRight size={13} />
              </button>
              <input
                ref={inputRef}
                type="file"
                accept=".zip,application/zip"
                hidden
                onChange={(e) => {
                  setFile(e.target.files?.[0] ?? null);
                  setError("");
                }}
              />
            </div>
            <div className="mock-notice">
              <CircleHelp size={16} />
              <p>
                Demo mode: ZIP contents are not read or uploaded. Processing and
                results use a temporary fictional case.
              </p>
            </div>
            {error && (
              <p className="error-message" role="alert">
                {error}
              </p>
            )}
            {uploading && (
              <div className="upload-progress" aria-live="polite">
                <div>
                  <span>
                    {statusQuery.isError
                      ? "Processing interrupted"
                      : (statusQuery.data?.message ??
                        "Preparing mock ingestion…")}
                  </span>
                  <span>{statusQuery.data?.progress ?? 0}%</span>
                </div>
                <progress max={100} value={statusQuery.data?.progress ?? 0} />
                {statusQuery.isError && (
                  <button onClick={() => statusQuery.refetch()}>
                    Retry status
                  </button>
                )}
              </div>
            )}
            <button
              className="button button-primary full-width"
              disabled={!file || (uploading && !ready)}
              onClick={ready ? demo : upload}
            >
              {ready ? (
                <>
                  <Check size={16} /> Open evidence board
                </>
              ) : uploading ? (
                <>
                  <LoaderCircle size={16} className="spin" /> Processing mock
                  case
                </>
              ) : (
                <>
                  Build evidence board <ArrowRight size={16} />
                </>
              )}
            </button>
            <button
              className="demo-link"
              disabled={uploading && !ready}
              onClick={demo}
            >
              No files yet? Explore the synthetic demo
            </button>
          </section>
        </div>
      )}
    </div>
  );
}
function LinkLabel() {
  return <Activity size={14} />;
}
