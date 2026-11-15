import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  Controls,
  MarkerType,
  applyNodeChanges,
  type NodeChange,
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
  Minus,
  PanelRightOpen,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Target,
  Upload,
  X,
} from "lucide-react";
import { api, isMock } from "./api/client";
import { isApiError } from "./api/http";
import type { CaseData } from "./api/types";
import { CanvasMinimap } from "./components/CanvasMinimap";
import { EvidenceNode, type PinData } from "./components/EvidenceNode";
import { ThreadEdge, type ThreadData } from "./components/ThreadEdge";
import {
  arrangePins,
  layoutCaseGraph,
  getPinDimensions,
  settlePinMoves,
  threadHandles,
} from "./components/board-layout";
import { Inspector, type Selection } from "./components/Inspector";
import { relationshipKind } from "./components/relationships";
import {
  formatCaseTime,
  insightKind,
  insightStrength,
  scoreLabel,
} from "./components/presentation";
import {
  getFocusFitOptions,
  getNodesForSelection,
  getNodesForTab,
  type Tab,
} from "./components/board-focus";
import { casePath, useRouter } from "./routing";
import { WorkspaceNavigation } from "./components/WorkspaceNavigation";
import { CaseWorkspace } from "./components/CaseWorkspace";
import {
  Landing,
  ProjectManager,
  type SessionProject,
} from "./onboarding/Onboarding";
const nodeTypes = { evidence: EvidenceNode };
const edgeTypes = { thread: ThreadEdge };
function BoardCanvas({
  data,
  projectName,
  onOpenSource,
  active,
  focusSelection,
  onClearFocusSelection,
}: {
  data: CaseData;
  projectName?: string;
  onOpenSource: (sourceId: string) => void;
  active: boolean;
  focusSelection?: Selection | null;
  onClearFocusSelection?: () => void;
}) {
  const { fitView } = useReactFlow();
  const [selection, setSelection] = useState<Selection | null>(null);
  const [tab, setTab] = useState<Tab>("gaps");
  const [dockMode, setDockMode] = useState<
    "closed" | "analysis" | "inspector" | "audit"
  >("closed");
  const auditChain = useQuery({
    queryKey: ["audit-chain", data.id],
    queryFn: () => api.getAuditChain(data.id),
    enabled: !isMock && dockMode === "audit",
  });
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

  const focusTarget = useCallback(
    (
      targetNodeIds: Set<string> | string[],
      options?: { dockOpen?: boolean },
    ) => {
      const ids = Array.from(targetNodeIds);
      if (ids.length === 0) return;
      const isNarrow =
        typeof window !== "undefined" &&
        window.matchMedia("(max-width: 900px)").matches;
      const isDockOpen = options?.dockOpen ?? dockMode !== "closed";
      const fitOptions = getFocusFitOptions({
        nodeCount: ids.length,
        isNarrow,
        dockOpen: isDockOpen,
      });

      requestAnimationFrame(() => {
        try {
          fitView({
            nodes: ids.map((id) => ({ id })),
            ...fitOptions,
          });
        } catch {
          // Graceful fallback
        }
      });
    },
    [fitView, dockMode],
  );

  const resetBoardView = useCallback(() => {
    requestAnimationFrame(() => {
      try {
        fitView({
          padding: {
            top: "90px",
            bottom: "100px",
            left: "90px",
            right: "60px",
          },
          duration: 650,
          minZoom: 0.5,
          maxZoom: 1.1,
        });
      } catch {
        // Graceful fallback
      }
    });
  }, [fitView]);

  const inspect = useCallback(
    (kind: Selection["kind"], id: string, sourceId?: string) => {
      openerRef.current =
        document.activeElement instanceof HTMLElement &&
        document.activeElement !== document.body
          ? document.activeElement
          : null;
      setReturnMode(dockMode === "inspector" ? returnMode : dockMode);
      const nextSelection: Selection = { kind, id, sourceId };
      setSelection(nextSelection);
      setDockMode("inspector");

      const targetNodes = getNodesForSelection(nextSelection, data);
      if (targetNodes.size > 0) {
        focusTarget(targetNodes, { dockOpen: true });
      }
    },
    [dockMode, returnMode, data, focusTarget],
  );

  const closeInspector = useCallback(() => {
    setSelection(null);
    setDockMode(returnMode);
    if (returnMode === "closed") {
      resetBoardView();
    } else if (returnMode === "analysis") {
      const targetNodes = getNodesForTab(tab, data);
      if (targetNodes.size > 0) focusTarget(targetNodes, { dockOpen: true });
    }
    requestAnimationFrame(() => {
      if (openerRef.current?.isConnected) openerRef.current.focus();
      else if (returnMode === "analysis") analysisRef.current?.focus();
      else reviewButtonRef.current?.focus();
    });
  }, [returnMode, resetBoardView, tab, data, focusTarget]);

  useEffect(() => {
    if (focusSelection && active) {
      inspect(focusSelection.kind, focusSelection.id, focusSelection.sourceId);
      onClearFocusSelection?.();
    }
  }, [focusSelection, active, inspect, onClearFocusSelection]);
  // Fixture positions are hand-placed; backend positions are column placeholders.
  const layout = useMemo(
    () => (isMock ? undefined : layoutCaseGraph(data.nodes, data.edges)),
    [data],
  );
  const initialNodes: Node<PinData>[] = useMemo(
    () =>
      arrangePins(
        data.nodes.map((n) => {
          const dim = getPinDimensions(n);
          const laidOut = layout?.get(n.id);
          return {
            id: n.id,
            type: "evidence",
            ariaLabel: `${n.label}. ${n.type}. Inspect evidence and sources`,
            position: laidOut
              ? { x: 100 + laidOut.x, y: laidOut.y }
              : { x: 100 + n.position.x, y: n.position.y * 1.2 },
            width: dim.width,
            height: dim.height,
            data: {
              ...n,
              timeZone: data.timezone,
              width: dim.width,
              height: dim.height,
              onInspect: () => inspect("node", n.id),
              onInspectGap: n.gapId
                ? () => inspect("gap", n.gapId!)
                : undefined,
            },
          };
        }),
      ),
    [data, inspect, layout],
  );
  const initialEdges: Edge<ThreadData>[] = useMemo(
    () =>
      data.edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        data: {
          kind: relationshipKind(e.type, e.certainty),
          label: e.label,
          directed: e.directed === true,
          onInspect: () => inspect("edge", e.id),
        },
        ariaLabel: `${e.label}. Inspect relationship and sources`,
        type: "thread",
        markerEnd:
          e.directed === true
            ? {
                type: MarkerType.ArrowClosed,
                color: "#a1372f",
                width: 12,
                height: 12,
              }
            : undefined,
        style: {
          stroke: "#a1372f",
          strokeWidth: 3,
          strokeLinecap: "round",
          strokeDasharray:
            relationshipKind(e.type, e.certainty) === "observed"
              ? undefined
              : "8 7",
        },
      })),
    [data],
  );
  const [nodes, setNodes] = useNodesState(initialNodes);
  const onNodesChange = useCallback(
    (changes: NodeChange<Node<PinData>>[]) => {
      setNodes((current) => {
        const next = applyNodeChanges(changes, current);
        const settledIds = changes.flatMap((change) =>
          change.type === "position" && !change.dragging ? [change.id] : [],
        );
        return settledIds.length ? settlePinMoves(next, settledIds) : next;
      });
    },
    [setNodes],
  );
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);
  const normalizedSearch = search.trim().toLowerCase();
  const matchingNodes = useMemo(
    () =>
      normalizedSearch
        ? nodes.filter((n) =>
            `${n.data.label} ${n.data.summary}`
              .toLowerCase()
              .includes(normalizedSearch),
          )
        : nodes,
    [nodes, normalizedSearch],
  );
  const matchingNodeIds = useMemo(
    () => (normalizedSearch ? new Set(matchingNodes.map((n) => n.id)) : null),
    [matchingNodes, normalizedSearch],
  );
  const focusedNodeIds = useMemo(() => {
    if (selection) {
      return getNodesForSelection(selection, data);
    }
    if (dockMode === "analysis") {
      return getNodesForTab(tab, data);
    }
    return null;
  }, [selection, dockMode, tab, data]);

  const visibleNodes = useMemo(
    () =>
      nodes.map((n) => {
        const isFocused = focusedNodeIds ? focusedNodeIds.has(n.id) : false;
        const isDimmed =
          (matchingNodeIds && !matchingNodeIds.has(n.id)) ||
          (focusedNodeIds && !isFocused);
        return {
          ...n,
          className:
            `${isDimmed ? "dimmed-node" : ""} ${isFocused ? "focused-node" : ""}`.trim(),
          data: {
            ...n.data,
            active:
              selection?.kind === "node" ? selection.id === n.id : isFocused,
            isFocused,
            onInspect: () => inspect("node", n.id),
            onInspectGap: n.data.gapId
              ? () => inspect("gap", n.data.gapId!)
              : undefined,
          },
        };
      }),
    [nodes, matchingNodeIds, focusedNodeIds, selection, inspect],
  );

  const visibleEdges = useMemo(() => {
    const nodesById = new Map(nodes.map((node) => [node.id, node]));
    return edges.map((edge) => {
      const source = nodesById.get(edge.source);
      const target = nodesById.get(edge.target);
      const isFocused = focusedNodeIds
        ? focusedNodeIds.has(edge.source) && focusedNodeIds.has(edge.target)
        : false;
      const isDimmed = focusedNodeIds && !isFocused;
      return {
        ...edge,
        className:
          `${isDimmed ? "dimmed-edge" : ""} ${isFocused ? "focused-edge" : ""}`.trim(),
        ...(source && target
          ? threadHandles(source.position, target.position)
          : {}),
        selected:
          selection?.kind === "edge" ? selection.id === edge.id : isFocused,
        data: edge.data
          ? {
              ...edge.data,
              isFocused,
              onInspect: () => inspect("edge", edge.id),
            }
          : undefined,
      };
    });
  }, [edges, nodes, focusedNodeIds, selection, inspect]);
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
                  if (dockMode === "analysis") {
                    setDockMode("closed");
                    resetBoardView();
                  } else {
                    setDockMode("analysis");
                    setSelection(null);
                    setTab("gaps");
                    const targetNodes = getNodesForTab("gaps", data);
                    focusTarget(targetNodes, { dockOpen: true });
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
                  <button
                    key={n.id}
                    className={
                      focusedNodeIds && focusedNodeIds.has(n.id)
                        ? "is-focused"
                        : ""
                    }
                    onClick={() => inspect("node", n.id)}
                  >
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
                      !matchingNodeIds ||
                      matchingNodeIds.has(e.source) ||
                      matchingNodeIds.has(e.target),
                  )
                  .map((e) => (
                    <button key={e.id} onClick={() => inspect("edge", e.id)}>
                      <span className="list-record-type">
                        {relationshipKind(e.type, e.certainty) === "observed"
                          ? "Observed"
                          : relationshipKind(e.type, e.certainty) ===
                              "inference"
                            ? "Inference"
                            : "Claim"}
                      </span>
                      <strong>
                        {data.nodes.find((n) => n.id === e.source)?.label}{" "}
                        {e.directed ? (
                          <ArrowRight size={12} />
                        ) : (
                          <Minus size={12} />
                        )}{" "}
                        {e.label}{" "}
                        {e.directed ? (
                          <ArrowRight size={12} />
                        ) : (
                          <Minus size={12} />
                        )}{" "}
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
                edges={visibleEdges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                onNodeClick={(_, n) => inspect("node", n.id)}
                onEdgeClick={(_, e) => inspect("edge", e.id)}
                onPaneClick={() => {
                  if (dockMode === "inspector") closeInspector();
                }}
                fitView
                fitViewOptions={{
                  padding: {
                    top: "90px",
                    bottom: "100px",
                    left: "90px",
                    right: "60px",
                  },
                  minZoom: 0.5,
                  maxZoom: 1.1,
                }}
                panOnScroll
                panOnScrollSpeed={1}
                zoomOnScroll={false}
                zoomOnPinch
                minZoom={0.15}
                maxZoom={1.8}
                nodesConnectable={false}
                deleteKeyCode={null}
                proOptions={{ hideAttribution: true }}
              >
                <Controls
                  position="bottom-right"
                  showInteractive={false}
                  fitViewOptions={{
                    padding: {
                      top: "90px",
                      bottom: "100px",
                      left: "90px",
                      right: "60px",
                    },
                    minZoom: 0.5,
                    maxZoom: 1.1,
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
              <div className="board-legend">
                <span>
                  <i className="legend-line" />
                  Observed link
                </span>
                <span>
                  <i className="legend-line dashed" />
                  Claim / inference
                </span>
                <span>
                  <i className="legend-gap" />
                  Evidence gap
                </span>
              </div>
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
                  resetBoardView();
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
                      setSelection(null);
                      const targetNodes = getNodesForTab(next, data);
                      focusTarget(targetNodes, { dockOpen: true });
                      document.getElementById(`tab-${next}`)?.focus();
                    }
                  }}
                  className={tab === id ? "active" : ""}
                  onClick={() => {
                    setTab(id);
                    setSelection(null);
                    const targetNodes = getNodesForTab(id, data);
                    focusTarget(targetNodes, { dockOpen: true });
                  }}
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
                    ? isMock
                      ? "Priority order · illustrative scores"
                      : "Priority order · computed rank scores"
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
                        {scoreLabel(g.score, "rank")}
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
                      <Lightbulb size={13} /> {insightKind(g)} ·{" "}
                      {insightStrength(g)}
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
            onFocusOnBoard={(sel) => {
              const targetNodes = getNodesForSelection(sel, data);
              if (targetNodes.size > 0)
                focusTarget(targetNodes, { dockOpen: true });
            }}
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
            {auditChain.data && (
              <div
                className={`audit-chain ${auditChain.data.verified ? "verified" : "failed"}`}
                role="status"
              >
                <strong>
                  {auditChain.data.verified
                    ? "Audit chain verified"
                    : "Audit chain verification failed"}
                </strong>
                <span>
                  {auditChain.data.entries.length} hash-chained entries from
                  ingestion and analysis · head{" "}
                  <code>{auditChain.data.head.slice(0, 16)}…</code>
                </span>
                <ul>
                  {auditChain.data.checks.map((check) => (
                    <li key={check.message} className={check.ok ? "" : "bad"}>
                      {check.ok ? "✓" : "✗"} {check.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {auditChain.isError && (
              <p className="error-message" role="alert">
                Could not verify the audit chain: {auditChain.error.message}
              </p>
            )}
            <div className="audit-steps">
              {data.audit.map((a) => (
                <div className="audit-step" key={a.id}>
                  <Check size={13} />
                  <time dateTime={a.time}>
                    {formatCaseTime(a.time, data.timezone)}
                  </time>
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

function Board(props: {
  data: CaseData;
  projectName?: string;
  onOpenSource: (sourceId: string) => void;
  active: boolean;
  focusSelection?: Selection | null;
  onClearFocusSelection?: () => void;
}) {
  return (
    <ReactFlowProvider>
      <BoardCanvas {...props} />
    </ReactFlowProvider>
  );
}

export default function App() {
  const { route, navigate } = useRouter();
  const queryClient = useQueryClient();
  const [openingCase, setOpeningCase] = useState(false);
  const [focusSelection, setFocusSelection] = useState<Selection | null>(null);
  const uploadOpen = route.kind === "new-project";
  const [projectName, setProjectName] = useState("");
  const [projects, setProjects] = useState<SessionProject[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadedCaseId, setUploadedCaseId] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const routeCaseId = route.kind === "case" ? route.caseId : undefined;
  const caseQuery = useQuery({
    queryKey: ["case", routeCaseId ?? "latest"],
    queryFn: () => api.getCase(routeCaseId),
    enabled:
      route.kind === "case" ||
      route.kind === "projects" ||
      route.kind === "new-project",
    retry: (count, error) =>
      count < 2 && (!isApiError(error) || error.status >= 500),
  });
  const casesQuery = useQuery({
    queryKey: ["cases"],
    queryFn: () => api.listCases(),
    enabled: api.mode === "live" && route.kind !== "welcome",
  });
  const statusQuery = useQuery({
    queryKey: ["upload", jobId],
    queryFn: () => api.getStatus(jobId!),
    enabled: !!jobId,
    refetchInterval: (q) =>
      q.state.data?.status === "ready" || q.state.data?.status === "failed"
        ? false
        : 650,
  });
  const ready = statusQuery.data?.status === "ready";
  const uploadFailed =
    statusQuery.isError || statusQuery.data?.status === "failed";
  const caseNotFound =
    route.kind === "case" &&
    ((caseQuery.data !== undefined && caseQuery.data.id !== route.caseId) ||
      isApiError(caseQuery.error, "case_not_found") ||
      isApiError(caseQuery.error, "bad_case_id"));
  const listedProjects = useMemo(() => {
    const listed = (casesQuery.data ?? [])
      .filter((entry) => entry.ready)
      .map((entry) => ({ caseId: entry.caseId, name: entry.title }));
    return [
      ...projects,
      ...listed.filter(
        (entry) => !projects.some((project) => project.caseId === entry.caseId),
      ),
    ];
  }, [projects, casesQuery.data]);
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
    failed: uploadFailed,
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
      const result = await api.createUpload(file, { caseName: projectName });
      setJobId(result.jobId);
      setUploadedCaseId(result.caseId ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed. Try again.");
      setUploading(false);
    }
  }
  function closeUpload() {
    if (uploadOpen) navigate("/projects", { replace: true });
    setProjectName("");
    setJobId(null);
    setUploadedCaseId(null);
    setUploading(false);
    setFile(null);
    setError("");
  }
  closeUploadRef.current = closeUpload;
  /** Opens a case by ID, or the demo case when no ID is given. */
  async function openCase(requestedId?: string) {
    setError("");
    setOpeningCase(true);
    try {
      const caseId = requestedId ?? (await api.openDemo());
      const data = await queryClient.fetchQuery({
        queryKey: ["case", caseId],
        queryFn: () => api.getCase(caseId),
      });
      queryClient.setQueryData(["case", data.id], data);
      void queryClient.invalidateQueries({ queryKey: ["cases"] });
      setProjects((current) => [
        { caseId: data.id, name: projectName.trim() || data.title },
        ...current.filter((p) => p.caseId !== data.id),
      ]);
      if (uploadOpen) closeUpload();
      if (route.kind !== "case" || route.caseId !== data.id)
        navigate(casePath(data.id));
    } catch (e) {
      setError(
        isApiError(e, "no_demo_snapshot")
          ? "The demo case has not been prepared on this server. Upload a ZIP instead."
          : e instanceof Error
            ? e.message
            : "Could not open the case. Try again.",
      );
    } finally {
      setOpeningCase(false);
    }
  }
  if (route.kind === "welcome")
    return (
      <Landing
        navigate={navigate}
        onDemo={() => void openCase()}
        opening={openingCase}
        caseData={caseQuery.data}
      />
    );
  const projectRoute =
    route.kind === "projects" || route.kind === "new-project";
  return (
    <>
      {projectRoute ? (
        <ProjectManager
          data={caseQuery.data}
          projects={listedProjects}
          persistent={api.mode === "live"}
          navigate={navigate}
          onDemo={() => void openCase()}
          opening={openingCase}
          error={error}
        />
      ) : (
        <div className="app-shell">
          {(route.kind !== "case" || !caseQuery.data || caseNotFound) && (
            <WorkspaceNavigation
              navigate={navigate}
              projects={listedProjects}
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
            ) : caseNotFound ? (
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
            ) : isApiError(caseQuery.error, "not_ready") ? (
              <div className="center-state">
                <h2>This case is still being analysed</h2>
                <button
                  className="button button-primary"
                  onClick={() => caseQuery.refetch()}
                >
                  Check again
                </button>
              </div>
            ) : caseQuery.isError ? (
              <div className="center-state">
                <h2>Couldn’t load the case</h2>
                <p>{caseQuery.error.message}</p>
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
                insightsTab={
                  route.kind === "case" ? route.insightsTab : undefined
                }
                navigate={navigate}
                onFocusOnBoard={(sel) => {
                  setFocusSelection(sel);
                  if (route.kind !== "case" || route.view) {
                    navigate(casePath(caseQuery.data.id));
                  }
                }}
                projectName={
                  projects.find(
                    (project) => project.caseId === caseQuery.data.id,
                  )?.name
                }
              >
                <Board
                  data={caseQuery.data}
                  active={route.kind === "case" && !route.view}
                  focusSelection={focusSelection}
                  onClearFocusSelection={() => setFocusSelection(null)}
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
              (!uploading || ready || uploadFailed)
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
              disabled={openingCase || (uploading && !ready && !uploadFailed)}
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
                {file
                  ? file.name
                  : api.mode === "live"
                    ? "Choose a ZIP of case evidence"
                    : "Choose a ZIP to preview the workspace"}
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
                      : statusQuery.data?.status === "failed"
                        ? "Analysis failed"
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
                {statusQuery.data?.status === "failed" && (
                  <p className="error-message" role="alert">
                    {statusQuery.data.message ||
                      "The case service could not process this archive."}
                  </p>
                )}
              </div>
            )}
            <button
              className="button button-primary full-width"
              disabled={!file || (uploading && !ready) || openingCase}
              onClick={
                ready
                  ? () =>
                      void openCase(
                        statusQuery.data?.caseId ?? uploadedCaseId ?? undefined,
                      )
                  : upload
              }
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
              ) : api.mode === "live" ? (
                <>
                  Upload and analyse <ArrowRight size={16} />
                </>
              ) : (
                <>
                  Preview workspace <ArrowRight size={16} />
                </>
              )}
            </button>
            {api.mode === "live" ? (
              <p className="upload-disclosure">
                The ZIP is uploaded to the case service, which hashes every file
                and keeps read-only copies. Evidence is never modified. Limit
                100 MB.
              </p>
            ) : (
              <p className="upload-disclosure">
                Prototype: ZIP contents are not read or uploaded. This preview
                uses fictional case data and simulated progress.
              </p>
            )}
          </section>
        </div>
      )}
    </>
  );
}
