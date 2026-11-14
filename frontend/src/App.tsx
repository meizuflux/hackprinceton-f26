import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ReactFlow,
  Controls,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from "@xyflow/react";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  FileArchive,
  GitBranch,
  History,
  Layers,
  Lightbulb,
  LoaderCircle,
  PanelRightOpen,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Target,
  Upload,
  X,
} from "lucide-react";
import { api } from "./api/client";
import type { CaseData } from "./api/types";
import { CanvasMinimap } from "./components/CanvasMinimap";
import { EvidenceNode, type PinData } from "./components/EvidenceNode";
import { Inspector, type Selection } from "./components/Inspector";
import { casePath, useRouter } from "./routing";
import { WorkspaceNavigation } from "./components/WorkspaceNavigation";
import { CaseWorkspace } from "./components/CaseWorkspace";
import {
  Landing,
  ProjectManager,
  type SessionProject,
} from "./onboarding/Onboarding";
const nodeTypes = { evidence: EvidenceNode };
type Tab = "gaps" | "insights" | "suggestions";
type RelationshipKind = "observed" | "claim" | "inference";

function relationshipKind(type: string): RelationshipKind {
  if (type === "time_overlap") return "inference";
  if (["claim", "describes", "reported_near"].includes(type)) return "claim";
  return "observed";
}
function Board({
  data,
  projectName,
  onOpenSource,
  active,
}: {
  data: CaseData;
  projectName?: string;
  onOpenSource: (sourceId: string) => void;
  active: boolean;
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
  const dockRef = useRef<HTMLElement>(null);
  const analysisRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (
      dockMode !== "closed" &&
      window.matchMedia("(max-width: 900px)").matches
    ) {
      dockRef.current?.scrollIntoView({ block: "start" });
    }
  }, [dockMode]);
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
        position: { x: 160 + n.position.x * 1.45, y: n.position.y * 2.15 },
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
          stroke:
            relationshipKind(e.type) === "observed" ? "#b86350" : "#bd985a",
          strokeWidth: 1.5,
          strokeDasharray:
            relationshipKind(e.type) === "observed" ? undefined : "5 5",
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
      <div className="workspace">
        <div className="board-area">
          <div className="board-toolbar">
            <div className="board-title">
              <h1>{projectName || data.title}</h1>
              <span>
                {data.subtitle} · {data.nodes.length} pins · {data.edges.length}{" "}
                connections
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
                        {relationshipKind(e.type) === "observed"
                          ? "Observed"
                          : relationshipKind(e.type) === "inference"
                            ? "Inference"
                            : "Claim"}
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
                onPaneClick={() => {
                  if (dockMode === "inspector") closeInspector();
                }}
                fitView
                fitViewOptions={{
                  padding: { top: "110px", bottom: "60px", x: "50px" },
                }}
                panOnScroll
                panOnScrollSpeed={1}
                zoomOnScroll={false}
                zoomOnPinch
                minZoom={0.3}
                maxZoom={1.8}
                nodesConnectable={false}
                deleteKeyCode={null}
                proOptions={{ hideAttribution: true }}
              >
                <Controls
                  showInteractive={false}
                  fitViewOptions={{
                    padding: { top: "110px", bottom: "60px", x: "50px" },
                  }}
                />
                <CanvasMinimap />
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
                <div className="board-legend">
                  <span>
                    <i className="legend-line" />
                    Observed link
                  </span>
                  <span>
                    <i className="legend-line dashed" />
                    To verify
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
          ref={dockRef}
          id="review-dock"
          data-mode={dockMode}
          aria-label="Review dock"
          hidden={dockMode === "closed"}
        >
          {dockMode !== "inspector" && (
            <div className="review-dock-header">
              <div>
                <h2>{dockMode === "audit" ? "Audit trail" : "Case review"}</h2>
              </div>
              <button
                className="icon-button"
                aria-label={
                  dockMode === "audit" && auditReturnMode !== "closed"
                    ? "Back to review"
                    : "Close review dock"
                }
                onClick={() => {
                  if (dockMode === "audit") {
                    setDockMode(auditReturnMode);
                    return;
                  }
                  setSelection(null);
                  setDockMode("closed");
                  reviewButtonRef.current?.focus();
                }}
              >
                <X size={16} />
              </button>
            </div>
          )}
          <aside
            className="analysis-panel"
            ref={analysisRef}
            tabIndex={-1}
            aria-label="Case review"
            hidden={dockMode !== "analysis"}
          >
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
                        <span>Illustrative</span> {Math.round(g.score * 100)}
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
                    : tab === "insights"
                      ? "An insight is an inference. Open it to inspect the cited sources."
                      : "A suggestion is a next request, not a finding. Open it to see the example and its source."}
                </p>
              </div>
            </div>
          </aside>
          <Inspector
            selection={active && dockMode === "inspector" ? selection : null}
            data={data}
            onSelect={setSelection}
            onClose={closeInspector}
            onOpenSource={onOpenSource}
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
  const uploadGuard = useRef({
    openingCase: false,
    uploading: false,
    ready: false,
    failed: false,
  });
  const closeUploadRef = useRef<() => void>(() => {});
  uploadGuard.current = {
    openingCase,
    uploading,
    ready,
    failed: statusQuery.isError,
  };
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
      const guard = uploadGuard.current;
      if (
        event.key === "Escape" &&
        !guard.openingCase &&
        (!guard.uploading || guard.ready || guard.failed)
      ) {
        event.preventDefault();
        closeUploadRef.current();
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
  }, [uploadOpen]);

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
  closeUploadRef.current = closeUpload;
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
          {(route.kind !== "case" ||
            !caseQuery.data ||
            caseQuery.data.id !== route.caseId) && (
            <WorkspaceNavigation
              navigate={navigate}
              projects={projects}
              activeCaseId={route.kind === "case" ? route.caseId : undefined}
            />
          )}
          <main className="workspace-main">
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
              <CaseWorkspace
                key={caseQuery.data.id}
                data={caseQuery.data}
                view={route.kind === "case" ? (route.view ?? "board") : "board"}
                sourceId={route.kind === "case" ? route.sourceId : undefined}
                navigate={navigate}
                projectName={
                  projects.find(
                    (project) => project.caseId === caseQuery.data.id,
                  )?.name
                }
              >
                <Board
                  data={caseQuery.data}
                  active={route.kind === "case" && !route.view}
                  projectName={
                    projects.find(
                      (project) => project.caseId === caseQuery.data.id,
                    )?.name
                  }
                  onOpenSource={(sourceId) =>
                    navigate(casePath(caseQuery.data.id, "evidence", sourceId))
                  }
                />
              </CaseWorkspace>
            )}
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
            <p>Name your project and select a ZIP archive.</p>
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
                  : "ZIP archive"}
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
            <p className="upload-disclosure">
              Prototype: ZIP contents are not read or uploaded. This preview
              uses fictional case data and simulated progress.
            </p>
          </section>
        </div>
      )}
    </>
  );
}
