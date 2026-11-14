import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
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
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronRight,
  FileArchive,
  Fingerprint,
  FolderOpen,
  GitBranch,
  History,
  Layers,
  Lightbulb,
  LoaderCircle,
  PanelRightOpen,
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
import { casePath, useRouter } from "./routing";
import {
  Landing,
  ProjectManager,
  type SessionProject,
} from "./onboarding/Onboarding";
const nodeTypes = { evidence: EvidenceNode };
type Tab = "gaps" | "insights" | "suggestions";
function Board({
  data,
  projectName,
}: {
  data: CaseData;
  projectName?: string;
}) {
  const [selection, setSelection] = useState<Selection | null>(null);
  const [tab, setTab] = useState<Tab>("gaps");
  const [dockMode, setDockMode] = useState<
    "closed" | "analysis" | "inspector" | "audit"
  >("closed");
  const [returnMode, setReturnMode] = useState<"closed" | "analysis" | "audit">(
    "analysis",
  );
  const [auditReturnMode, setAuditReturnMode] = useState<"closed" | "analysis">(
    "closed",
  );
  const [search, setSearch] = useState("");
  const [boardView, setBoardView] = useState<"graph" | "list">("graph");
  const analysisRef = useRef<HTMLElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const reviewButtonRef = useRef<HTMLButtonElement>(null);
  const inspect = useCallback(
    (kind: Selection["kind"], id: string, sourceId?: string) => {
      openerRef.current =
        document.activeElement instanceof HTMLElement &&
        document.activeElement !== document.body
          ? document.activeElement
          : null;
      setReturnMode(dockMode === "inspector" ? returnMode : dockMode);
      setSelection({ kind, id, sourceId });
      setDockMode("inspector");
    },
    [dockMode, returnMode],
  );
  const closeInspector = useCallback(() => {
    setSelection(null);
    setDockMode(returnMode);
    requestAnimationFrame(() => {
      if (openerRef.current?.isConnected) openerRef.current.focus();
      else if (returnMode === "analysis") analysisRef.current?.focus();
      else reviewButtonRef.current?.focus();
    });
  }, [returnMode]);
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
      onInspect: () => inspect("node", n.id),
    },
  }));
  return (
    <>
      <div className="case-toolbar">
        <div className="breadcrumbs">
          Workspace <ChevronRight size={12} /> Cases <ChevronRight size={12} />
          <span>{data.id}</span>
        </div>
        <div className="compact-case-title">{projectName || data.title}</div>
        <div className="toolbar-right">
          <button
            className="text-button"
            aria-expanded={
              dockMode === "audit" ||
              (dockMode === "inspector" && returnMode === "audit")
            }
            aria-controls="review-dock"
            onClick={() => {
              if (dockMode === "audit") setDockMode(auditReturnMode);
              else {
                setAuditReturnMode(
                  dockMode === "analysis"
                    ? "analysis"
                    : dockMode === "inspector"
                      ? returnMode === "analysis"
                        ? "analysis"
                        : "closed"
                      : "closed",
                );
                setDockMode("audit");
              }
            }}
          >
            <History size={15} /> Audit trail
          </button>
        </div>
      </div>
      <div className="workspace-shell">
        <div className="workspace-summary">
          <span>{data.subtitle}</span>
          <span className="workspace-summary-spacer" />
          <span>{data.sources.length} artifacts</span>
          <span>{data.nodes.length} entities</span>
          <button
            ref={reviewButtonRef}
            className={`review-toggle ${dockMode === "analysis" ? "selected" : ""}`}
            aria-expanded={
              dockMode === "analysis" ||
              (dockMode === "inspector" && returnMode === "analysis")
            }
            aria-controls="review-dock"
            onClick={() => {
              if (dockMode === "analysis") setDockMode("closed");
              else {
                setDockMode("analysis");
                setSelection(null);
              }
            }}
          >
            <PanelRightOpen size={15} /> Review gaps{" "}
            <strong>{data.gaps.length}</strong>
          </button>
        </div>
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
                          {e.citations.length} sources{" "}
                          <ArrowUpRight size={14} />
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
                  onPaneClick={() => {
                    if (dockMode === "inspector") closeInspector();
                  }}
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
          </div>
          <aside
            className={`review-dock ${dockMode !== "closed" ? "is-open" : ""}`}
            id="review-dock"
            data-mode={dockMode}
            aria-label="Review dock"
            hidden={dockMode === "closed"}
          >
            <div className="review-dock-header">
              <div>
                <span className="dock-kicker">CASE REVIEW</span>
                <h2>
                  {dockMode === "audit"
                    ? "Audit trail"
                    : dockMode === "inspector"
                      ? "Source inspection"
                      : "Follow the evidence"}
                </h2>
              </div>
              <button
                className="icon-button"
                aria-label="Close review dock"
                onClick={() => {
                  setSelection(null);
                  setDockMode("closed");
                  reviewButtonRef.current?.focus();
                }}
              >
                <X size={16} />
              </button>
            </div>
            <aside
              className="analysis-panel"
              ref={analysisRef}
              tabIndex={-1}
              aria-label="Case review"
              hidden={dockMode !== "analysis"}
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
                      if (
                        offset ||
                        event.key === "Home" ||
                        event.key === "End"
                      ) {
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
                Case analysis <span>·</span> All results traceable
              </div>
            </aside>
            <Inspector
              selection={dockMode === "inspector" ? selection : null}
              data={data}
              onSelect={setSelection}
              onClose={closeInspector}
              backLabel={
                returnMode === "audit"
                  ? "Back to audit"
                  : returnMode === "closed"
                    ? "Back to board"
                    : tab === "gaps"
                      ? "Back to gaps"
                      : tab === "insights"
                        ? "Back to insights"
                        : "Back to next evidence"
              }
            />
            <section className="audit-panel" hidden={dockMode !== "audit"}>
              <div className="audit-heading">
                <div>
                  <History size={16} />
                  <h2>Audit trail</h2>
                  <span>Processing record</span>
                </div>
                <button
                  className="icon-button"
                  aria-label="Close audit trail"
                  onClick={() => setDockMode(auditReturnMode)}
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
          </aside>
        </div>
      </div>
    </>
  );
}
export default function App() {
  const { route, navigate } = useRouter();
  const queryClient = useQueryClient();
  const [openingCase, setOpeningCase] = useState(false);
  const uploadOpen = route.kind === "new-project";
  const [projectName, setProjectName] = useState("");
  const [projects, setProjects] = useState<SessionProject[]>([]);
  function setUploadOpen(open: boolean) {
    navigate(open ? "/projects/new" : "/projects");
  }
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const caseQueryKey = ["case"] as const;
  const caseQuery = useQuery({
    queryKey: caseQueryKey,
    queryFn: () => api.getCase(),
    enabled:
      route.kind === "case" ||
      route.kind === "projects" ||
      route.kind === "new-project",
  });
  const statusQuery = useQuery({
    queryKey: ["upload", jobId],
    queryFn: () => api.getStatus(jobId!),
    enabled: !!jobId,
    refetchInterval: (q) => (q.state.data?.status === "ready" ? false : 650),
  });
  const ready = statusQuery.data?.status === "ready";
  useEffect(() => {
    if (route.kind !== "case" || caseQuery.data?.id !== route.caseId) return;
    const data = caseQuery.data;
    setProjects((current) =>
      current.some((project) => project.caseId === data.id)
        ? current
        : [...current, { caseId: data.id, name: data.title }],
    );
  }, [route, caseQuery.data]);
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
    (focusable()[0] ?? dialog)?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (
        event.key === "Escape" &&
        !openingCase &&
        (!uploading || ready || statusQuery.isError)
      ) {
        event.preventDefault();
        closeUpload();
      }
      if (event.key === "Tab") {
        const items = focusable();
        if (items.length === 0) {
          event.preventDefault();
          dialog?.focus();
          return;
        }
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
  }, [uploadOpen, uploading, ready, statusQuery.isError, openingCase]);

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
    if (uploadOpen) navigate("/projects", { replace: true });
    setProjectName("");
    setJobId(null);
    setUploading(false);
    setFile(null);
    setError("");
  }
  async function openCase() {
    setError("");
    setOpeningCase(true);
    try {
      const data = await queryClient.fetchQuery({
        queryKey: caseQueryKey,
        queryFn: () => api.getCase(),
      });
      setProjects((current) => [
        { caseId: data.id, name: projectName.trim() || data.title },
        ...current.filter((p) => p.caseId !== data.id),
      ]);
      if (uploadOpen) closeUpload();
      if (route.kind !== "case" || route.caseId !== data.id)
        navigate(casePath(data.id));
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not open the case. Try again.",
      );
    } finally {
      setOpeningCase(false);
    }
  }
  if (route.kind === "welcome") return <Landing navigate={navigate} />;
  const projectRoute =
    route.kind === "projects" || route.kind === "new-project";
  return (
    <>
      {projectRoute ? (
        <ProjectManager
          data={caseQuery.data}
          projects={projects}
          navigate={navigate}
          onDemo={() => void openCase()}
          opening={openingCase}
          error={error}
        />
      ) : (
        <div className="app-shell">
          <nav className="rail" aria-label="Main navigation">
            <a
              className="brand-mark"
              href="#"
              aria-label="Compstat home"
              onClick={(e) => {
                e.preventDefault();
                navigate("/");
              }}
            >
              <Fingerprint size={26} />
            </a>
            <div className="rail-links">
              <button
                className={route.kind === "case" ? "active" : ""}
                aria-label="Project manager"
                title="Project manager"
                onClick={() => navigate("/projects")}
              >
                <Layers size={21} />
                <span>Projects</span>
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
            </div>
          </nav>
          <main>
            <header className="app-header">
              <div className="wordmark">
                compstat<span> / </span>
                <small>Clarity from complexity.</small>
              </div>
              <div className="header-actions">
                <button
                  className="button button-secondary button-small"
                  onClick={() => navigate("/projects")}
                >
                  Projects
                </button>
                <button
                  className="button button-primary button-small"
                  onClick={() => setUploadOpen(true)}
                >
                  <Plus size={15} /> New case
                </button>
              </div>
            </header>
            {route.kind === "not-found" ? (
              <div className="center-state">
                <h2>Page not found</h2>
                <button
                  className="button button-primary"
                  onClick={() => navigate("/")}
                >
                  Go home
                </button>
              </div>
            ) : route.kind === "case" &&
              caseQuery.data &&
              caseQuery.data.id !== route.caseId ? (
              <div className="center-state">
                <h2>Case not found</h2>
                <button
                  className="button button-primary"
                  onClick={() => navigate("/")}
                >
                  Go home
                </button>
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
              <Board
                data={caseQuery.data}
                projectName={
                  projects.find(
                    (project) => project.caseId === caseQuery.data.id,
                  )?.name
                }
              />
            )}
            <footer className="app-footer">
              <span>
                <Fingerprint size={12} /> COMPSTAT{" "}
                <span className="dot-separator">/</span> A clearer chain of
                evidence.
              </span>
              <span>Source-linked evidence review</span>
            </footer>
          </main>
        </div>
      )}
      {uploadOpen && (
        <div
          className="modal-backdrop"
          onClick={(e) => {
            if (
              e.target === e.currentTarget &&
              !openingCase &&
              (!uploading || ready || statusQuery.isError)
            )
              closeUpload();
          }}
        >
          <section
            className="upload-modal"
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-labelledby="upload-title"
          >
            <button
              className="icon-button modal-close"
              disabled={
                openingCase || (uploading && !ready && !statusQuery.isError)
              }
              onClick={closeUpload}
              aria-label="Close upload"
            >
              <X size={20} />
            </button>
            <div className="upload-icon">
              <Upload size={24} />
            </div>
            <h2 id="upload-title">Add a new project</h2>
            <p>Name your project, then choose how to get started.</p>
            <label className="project-name-field">
              Project name <span>(optional)</span>
              <input
                maxLength={80}
                placeholder="e.g. Inventory review"
                value={projectName}
                disabled={uploading}
                onChange={(e) => setProjectName(e.target.value)}
              />
            </label>
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
              <strong>
                {file ? file.name : "Choose a ZIP to preview the workspace"}
              </strong>
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
                        "Preparing workspace preview…")}
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
              disabled={!file || (uploading && !ready) || openingCase}
              onClick={ready ? () => void openCase() : upload}
            >
              {openingCase ? (
                <>
                  <LoaderCircle size={16} className="spin" /> Opening evidence
                  board
                </>
              ) : ready ? (
                <>
                  <Check size={16} /> Open evidence board
                </>
              ) : uploading ? (
                <>
                  <LoaderCircle size={16} className="spin" /> Preparing
                  workspace
                </>
              ) : (
                <>
                  Preview workspace <ArrowRight size={16} />
                </>
              )}
            </button>
            <button
              className="demo-link"
              disabled={
                openingCase || (uploading && !ready && !statusQuery.isError)
              }
              onClick={() => void openCase()}
            >
              Try demo case files →
            </button>
          </section>
        </div>
      )}
    </>
  );
}
