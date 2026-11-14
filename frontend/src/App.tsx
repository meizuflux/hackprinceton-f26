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
  const [boardView, setBoardView] = useState<"graph" | "list">("graph");
  const analysisRef = useRef<HTMLElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (audit)
      document
        .getElementById("case-audit")
        ?.scrollIntoView({ block: "nearest" });
  }, [audit]);
  const inspect = useCallback(
    (kind: Selection["kind"], id: string, sourceId?: string) =>
      setSelection({ kind, id, sourceId }),
    [],
  );
  const closeInspector = useCallback(() => {
    setSelection(null);
    requestAnimationFrame(() => analysisRef.current?.focus());
  }, []);
  const initialNodes: Node<PinData>[] = useMemo(
    () =>
      data.nodes.map((n) => ({
        id: n.id,
        type: "evidence",
        ariaLabel: `${n.label}. ${n.type}. Inspect evidence and sources`,
        position: { x: n.position.x, y: n.position.y * 1.2 },
        data: {
          ...n,
          onInspect: () => inspect("node", n.id),
          gapScore: data.gaps.find((g) => g.id === n.gapId)?.score,
        },
      })),
    [data, inspect],
  );
  const initialEdges: Edge[] = useMemo(
    () =>
      data.edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.label,
        ariaLabel: `${e.label}. Inspect relationship and sources`,
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
        labelStyle: { fill: "#f4e8cd", fontSize: 12 },
        labelBgStyle: { fill: "#444039", fillOpacity: 0.95 },
        labelBgPadding: [7, 4] as [number, number],
        labelBgBorderRadius: 3,
      })),
    [data],
  );
  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);
  const matchingNodes = nodes.filter((n) =>
    `${n.data.label} ${n.data.summary}`
      .toLowerCase()
      .includes(search.trim().toLowerCase()),
  );
  const visibleNodes = nodes.map((n) => ({
    ...n,
    className:
      search.trim() && !matchingNodes.some((match) => match.id === n.id)
        ? "dimmed-node"
        : "",
    data: {
      ...n.data,
      active: selection?.kind === "node" && selection.id === n.id,
    },
  }));
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
            aria-expanded={audit}
            aria-controls="case-audit"
            onClick={() => setAudit(!audit)}
          >
            <History size={15} /> Audit trail
          </button>
        </div>
      </div>
      <section className="case-heading">
        <div>
          <h1>
            {data.title}
            <span className="case-status">
              <span /> In review
            </span>
          </h1>
          <p className="case-description">
            <span className="demo-tag">Synthetic demo</span>
            {data.subtitle}
          </p>
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
                  ref={searchRef}
                  aria-label="Find evidence"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Find a pin…"
                />
                {search && (
                  <button
                    className="icon-button"
                    aria-label="Clear evidence search"
                    onClick={() => {
                      setSearch("");
                      searchRef.current?.focus();
                    }}
                  >
                    <X size={13} />
                  </button>
                )}
              </label>
              <button
                className="text-button view-toggle"
                aria-pressed={boardView === "list"}
                onClick={() =>
                  setBoardView(boardView === "graph" ? "list" : "graph")
                }
              >
                {boardView === "graph" ? (
                  <Layers size={15} />
                ) : (
                  <GitBranch size={15} />
                )}
                {boardView === "graph" ? "List" : "Board"}
              </button>
            </div>
          </div>
          <div className="canvas-wrap">
            {boardView === "list" ? (
              <div className="evidence-list">
                <h2>Evidence & connections</h2>
                <p>Inspect any record to review its original sources.</p>
                {matchingNodes.map((n) => (
                  <button key={n.id} onClick={() => inspect("node", n.id)}>
                    <span className="list-record-type">{n.data.type}</span>
                    <strong>{n.data.label}</strong>
                    <span>
                      {n.data.citations.length} sources{" "}
                      <ArrowUpRight size={14} />
                    </span>
                  </button>
                ))}
                <h3>Relationships</h3>
                {data.edges
                  .filter(
                    (e) =>
                      !search.trim() ||
                      matchingNodes.some(
                        (n) => n.id === e.source || n.id === e.target,
                      ),
                  )
                  .map((e) => (
                    <button key={e.id} onClick={() => inspect("edge", e.id)}>
                      <span className="list-record-type">
                        {["claim", "describes", "reported_near"].includes(
                          e.type,
                        )
                          ? "Claim"
                          : "Observed"}
                      </span>
                      <strong>
                        {data.nodes.find((n) => n.id === e.source)?.label}{" "}
                        <ArrowRight size={12} /> {e.label}{" "}
                        <ArrowRight size={12} />{" "}
                        {data.nodes.find((n) => n.id === e.target)?.label}
                      </strong>
                      <span>
                        {e.citations.length} sources <ArrowUpRight size={14} />
                      </span>
                    </button>
                  ))}
              </div>
            ) : (
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
                fitViewOptions={{ padding: 0.1 }}
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
            )}
            {search.trim() && (
              <div className="search-feedback" role="status">
                {matchingNodes.length
                  ? `${matchingNodes.length} matching pin${matchingNodes.length === 1 ? "" : "s"}.${boardView === "graph" ? " Other pins are dimmed." : ""}`
                  : "No matching evidence. Try a name, device, or location."}
              </div>
            )}
            {boardView === "graph" && (
              <>
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
              </>
            )}
          </div>
          <div className="board-bottom">
            <span>
              <ShieldCheck size={13} /> Fictional evidence · Original sources
              linked
            </span>
            <span>
              Drag pins to arrange <span className="dot-separator">·</span>{" "}
              Scroll to zoom
            </span>
          </div>
        </div>
        <aside
          className="analysis-panel"
          ref={analysisRef}
          tabIndex={-1}
          aria-label="Case review"
          hidden={!!selection}
        >
          <div className="analysis-heading">
            <div className="intelligence-icon">
              <GitBranch size={17} />
            </div>
            <div>
              <h2>Follow the evidence</h2>
              <p>Open a lead. Check its sources.</p>
            </div>
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
                id={`tab-${id}`}
                aria-controls={`panel-${id}`}
                aria-selected={tab === id}
                tabIndex={tab === id ? 0 : -1}
                onKeyDown={(event) => {
                  const tabs: Tab[] = ["gaps", "insights", "suggestions"];
                  const offset =
                    event.key === "ArrowRight"
                      ? 1
                      : event.key === "ArrowLeft"
                        ? -1
                        : 0;
                  if (offset || event.key === "Home" || event.key === "End") {
                    event.preventDefault();
                    const next =
                      event.key === "Home"
                        ? "gaps"
                        : event.key === "End"
                          ? "suggestions"
                          : tabs[
                              (tabs.indexOf(tab) + offset + tabs.length) %
                                tabs.length
                            ];
                    setTab(next);
                    document.getElementById(`tab-${next}`)?.focus();
                  }
                }}
                className={tab === id ? "active" : ""}
                onClick={() => setTab(id)}
              >
                {label}
                {count !== null && <span>{count}</span>}
              </button>
            ))}
          </div>
          <div
            className="panel-content"
            role="tabpanel"
            id={`panel-${tab}`}
            aria-labelledby={`tab-${tab}`}
          >
            <div className="panel-section-label">
              <span>
                {tab === "gaps"
                  ? "Priority order · illustrative scores"
                  : tab === "insights"
                    ? "Inferences · require verification"
                    : "Suggested evidence to request"}
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
                      <span>Demo score</span> {Math.round(g.score * 100)}
                    </span>
                  </div>
                  <h3>{g.title}</h3>
                  <p>{g.description}</p>
                  <div className="card-bottomline">
                    <span>
                      <ShieldCheck size={12} /> {g.citations.length} cited
                      source{g.citations.length === 1 ? "" : "s"}
                    </span>
                    <span>
                      Review gap <ArrowUpRight size={13} />
                    </span>
                  </div>
                </button>
              ))}
            {tab === "insights" &&
              data.insights.map((g) => (
                <button
                  key={g.id}
                  className={`analysis-card insight-card ${selection?.id === g.id ? "selected" : ""}`}
                  onClick={() => inspect("insight", g.id)}
                >
                  <div className="insight-label">
                    <Lightbulb size={13} /> Inference · illustrative{" "}
                    {Math.round(g.score * 100)}%
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
                  className={`analysis-card ${selection?.id === g.id ? "selected" : ""}`}
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
        <Inspector
          selection={selection}
          data={data}
          onSelect={setSelection}
          onClose={closeInspector}
        />
      </div>
      {audit && (
        <section className="audit-panel" id="case-audit">
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
                      inspect("source", id);
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
      if (
        event.key === "Escape" &&
        (!uploading || ready || statusQuery.isError)
      ) {
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
  }, [uploadOpen, uploading, ready, statusQuery.isError]);

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
            <span>Board</span>
          </button>
          <button
            aria-label="Upload case"
            title="Upload case"
            onClick={() => setUploadOpen(true)}
          >
            <FolderOpen size={21} />
            <span>New case</span>
          </button>
        </div>
        <div className="rail-bottom">
          <span className="rail-version">v.01</span>
          <span className="rail-local">
            Local
            <br />
            demo
          </span>
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
                <button className="button button-primary" onClick={demo}>
                  Explore demo case <ArrowRight size={16} />
                </button>
                <button
                  className="button button-secondary"
                  onClick={() => setUploadOpen(true)}
                >
                  <Upload size={16} /> Try a ZIP
                </button>
              </div>
              <div className="welcome-trust">
                <ShieldCheck size={15} />
                <span>Synthetic case. Every lead linked to its sources.</span>
              </div>
            </div>
            <div className="welcome-board">
              <div className="welcome-board-label">
                <span /> FICTIONAL CASE PREVIEW
              </div>
              <div className="preview-thread thread-a" />
              <div className="preview-thread thread-b" />
              <div className="preview-card preview-person">
                <span className="pushpin" />
                <div className="preview-avatar">
                  <Fingerprint size={55} strokeWidth={0.8} />
                </div>
                <h3>Alex Morgan</h3>
                <p>Inventory lead</p>
                <span className="mini-source">
                  <ShieldCheck size={12} /> 2 linked sources
                </span>
              </div>
              <div className="preview-card preview-note">
                <span className="pushpin" />
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
                <div className="preview-excerpt">
                  “Export has no frames from 20:31 to 20:50.”
                </div>
              </div>
              <div className="welcome-board-footer">
                <LinkLabel /> One board. A clearer way forward.
              </div>
            </div>
            <div className="welcome-bottom">
              <span>
                <GitBranch size={16} /> Connect the evidence
              </span>
              <span>
                <Search size={16} /> Find the gaps
              </span>
              <span>
                <Target size={16} /> Know what’s next
              </span>
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
            if (
              e.target === e.currentTarget &&
              (!uploading || ready || statusQuery.isError)
            )
              closeUpload();
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
              disabled={uploading && !ready && !statusQuery.isError}
              onClick={closeUpload}
              aria-label="Close upload"
            >
              <X size={20} />
            </button>
            <div className="upload-icon">
              <Upload size={24} />
            </div>
            <h2 id="upload-title">Try the demo upload</h2>
            <p>Select a ZIP to walk through simulated processing.</p>
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
                  : "ZIP archive · up to 100 MB"}
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
                  Start simulated processing <ArrowRight size={16} />
                </>
              )}
            </button>
            <button
              className="demo-link"
              disabled={uploading && !ready && !statusQuery.isError}
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
