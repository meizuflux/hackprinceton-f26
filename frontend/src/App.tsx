import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
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
  Focus,
  Lightbulb,
  LoaderCircle,
  Network,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Target,
  Upload,
  X,
} from "lucide-react";
import { api, isMock } from "./api/client";
import { isApiError } from "./api/http";
import type { CaseData, EvidenceEdge } from "./api/types";
import {
  CanvasMinimap,
  ZoomReadout,
  nodeSize,
} from "./components/CanvasMinimap";
import { boundsOf } from "./components/minimap-geometry";
import { EvidenceNode, type PinData } from "./components/EvidenceNode";
import { ThreadEdge, type ThreadData } from "./components/ThreadEdge";
import {
  arrangePins,
  layoutCaseGraph,
  getPinDimensions,
  settlePinMoves,
  threadHandles,
  type Pin,
  type Point,
} from "./components/board-layout";
import {
  StoryCardNode,
  StoryGroupNode,
  type StoryExcerpt,
} from "./components/StoryCard";
import {
  STORY_CARD,
  STORY_EXPANDED,
  STORY_GROUP,
  STORY_HERO,
  aggregateLabel,
  buildStoryGroups,
  hiddenNeighbours,
  isGroupId,
  layoutStory,
  placeAround,
  planFocus,
  resolveStory,
  revealAnchor,
  storyThreads,
} from "./components/board-story";
import { Inspector, type Selection } from "./components/Inspector";
import { relationshipKind } from "./components/relationships";
import {
  boardColorVars,
  threadBadge,
  threadCategory,
  threadColors,
  threadDash,
} from "./components/board-colors";
import { BoardLegend } from "./components/BoardLegend";
import {
  formatCaseSubtitle,
  insightKind,
  insightStrength,
  scoreLabel,
} from "./components/presentation";
import {
  getFocusFitOptions,
  getFocusPadding,
  getStoryPadding,
  getNodesForSelection,
  getNodesForTab,
  type Tab,
} from "./components/board-focus";
import { casePath, useRouter } from "./routing";
import { WorkspaceNavigation } from "./components/WorkspaceNavigation";
import { CaseTitle, CaseWorkspace } from "./components/CaseWorkspace";
import { AskWidget } from "./components/AskWidget";
import { AnalysisEntries } from "./components/AnalysisEntries";
import { HeadlinePanel } from "./components/HeadlinePanel";
import { resolveHeadline } from "./components/headline";
import { ReplayedCase } from "./replay/ReplayedCase";
import { replayRequested, requestReplay } from "./replay/intent";
import { RUN_PANEL_EVENT } from "./replay/ReplayHud";
import { useStoryMorph } from "./replay/useStoryMorph";
import { UploadConfirm, type AnalysisMode } from "./onboarding/UploadConfirm";
import { UPLOADS_ENABLED, UPLOADS_OFF_REASON } from "./config";
import {
  Landing,
  ProjectManager,
  type SessionProject,
} from "./onboarding/Onboarding";
const nodeTypes = {
  evidence: EvidenceNode,
  storyCard: StoryCardNode,
  storyGroup: StoryGroupNode,
};
const edgeTypes = { thread: ThreadEdge };

const isNarrowViewport = () =>
  typeof window !== "undefined" &&
  window.matchMedia("(max-width: 900px)").matches;
// A replay's expanded run panel covers the left of the board; story fits make room for it.
const isRunPanelOpen = () =>
  typeof document !== "undefined" && !!document.querySelector(".replay-hud");

/** Story-view node state; card content is read from the case at render. */
type StoryNodeState = { arriveFrom?: Point };

const centreOf = (node: {
  position: Point;
  width?: number;
  height?: number;
}): Point => ({
  x: node.position.x + (node.width ?? 0) / 2,
  y: node.position.y + (node.height ?? 0) / 2,
});

/** One React Flow thread for an API relationship, shared by both views. */
function threadEdge(e: EvidenceEdge): Edge<ThreadData> {
  const kind = relationshipKind(e.type, e.certainty);
  const category = threadCategory(e.type);
  const ink = threadColors[category].ink;
  return {
    id: e.id,
    source: e.source,
    target: e.target,
    data: {
      kind,
      category,
      badge: threadBadge(e.type, e.certainty),
      label: e.label,
      directed: e.directed === true,
      origin: e.origin,
      onInspect: () => {},
    },
    ariaLabel: `${threadColors[category].label}: ${e.label}. Inspect relationship and sources`,
    type: "thread",
    markerEnd:
      e.directed === true
        ? {
            type: MarkerType.ArrowClosed,
            color: ink,
            width: 12,
            height: 12,
          }
        : undefined,
    style: {
      stroke: ink,
      strokeWidth: 3,
      strokeLinecap: "round",
      strokeDasharray: threadDash(kind),
    },
  };
}

/** Labels of parallel threads between the same two cards are stacked apart. */
function labelOffsets(
  edges: Array<{ id: string; source: string; target: string }>,
) {
  const pairs = new Map<string, string[]>();
  for (const edge of edges) {
    const key = [edge.source, edge.target].sort().join("|");
    pairs.set(key, [...(pairs.get(key) ?? []), edge.id]);
  }
  const offsets = new Map<string, number>();
  for (const ids of pairs.values()) {
    if (ids.length < 2) continue;
    ids.forEach((id, index) =>
      offsets.set(id, (index - (ids.length - 1) / 2) * 34),
    );
  }
  return offsets;
}
function BoardCanvas({
  data,
  layoutData = data,
  growing = false,
  projectName,
  onOpenSource,
  active,
  focusSelection,
  onClearFocusSelection,
}: {
  data: CaseData;
  /** The full case, laid out once so cards revealed by a replay keep their final positions. */
  layoutData?: CaseData;
  /** A replay is revealing the board: animate arrivals and gently refit. */
  growing?: boolean;
  projectName?: string;
  onOpenSource: (sourceId: string) => void;
  active: boolean;
  focusSelection?: Selection | null;
  onClearFocusSelection?: () => void;
}) {
  const { fitView, fitBounds, getViewport, setViewport } = useReactFlow();
  const [selection, setSelection] = useState<Selection | null>(null);

  // Story view: the backend's opening selection, with the rest of the board
  // folded into presentation-only group cards.
  const story = useMemo(() => resolveStory(data), [data]);
  const groups = useMemo(
    () =>
      story ? buildStoryGroups(data.nodes, data.edges, story.nodeIds) : [],
    [data, story],
  );
  const groupById = useMemo(
    () => new Map(groups.map((group) => [group.id, group])),
    [groups],
  );
  const nodeById = useMemo(
    () => new Map(data.nodes.map((node) => [node.id, node])),
    [data],
  );
  const sourceById = useMemo(
    () => new Map(data.sources.map((source) => [source.id, source])),
    [data],
  );
  const [viewMode, setViewMode] = useState<"story" | "full">(
    story ? "story" : "full",
  );
  // A running replay grows the full layout; the story view takes over once the run has finished.
  const storyMode = viewMode === "story" && story !== null && !growing;
  // The dock state is declared below; story fits read it when they run.
  const dockOpenRef = useRef(false);
  const storyPadding = useCallback(
    () =>
      getStoryPadding({
        runPanelOpen: isRunPanelOpen(),
        isNarrow: isNarrowViewport(),
        dockOpen: dockOpenRef.current,
      }),
    [],
  );
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);
  const storyPin = useCallback(
    (id: string, position: Point, arriveFrom?: Point): Node<StoryNodeState> => {
      const size = isGroupId(id)
        ? STORY_GROUP
        : id === story?.centerId
          ? STORY_HERO
          : STORY_CARD;
      return {
        id,
        type: isGroupId(id) ? "storyGroup" : "storyCard",
        position,
        width: size.width,
        height: size.height,
        data: arriveFrom ? { arriveFrom } : {},
      };
    },
    [story],
  );
  const initialStoryNodes = useMemo(
    () =>
      story
        ? Array.from(layoutStory(story, data.edges, groups), ([id, point]) =>
            storyPin(id, point),
          )
        : [],
    [story, data.edges, groups, storyPin],
  );
  const [storyNodes, setStoryNodes] =
    useNodesState<Node<StoryNodeState>>(initialStoryNodes);
  const storyNodesRef = useRef(storyNodes);
  storyNodesRef.current = storyNodes;
  const expandedRef = useRef(expandedId);
  expandedRef.current = expandedId;
  const storyVisibleIds = useMemo(
    () => new Set(storyNodes.map((node) => node.id)),
    [storyNodes],
  );
  const arrivalTimer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(arrivalTimer.current), []);

  /** Puts hidden cards on the story board beside a linked visible card, animating out of it. */
  const revealCards = useCallback(
    (ids: string[], anchorId?: string) => {
      if (!story || ids.length === 0) return;
      setStoryNodes((current) => {
        const present = new Set(current.map((node) => node.id));
        const fresh = ids.filter((id) => !present.has(id) && nodeById.has(id));
        if (!fresh.length) return current;
        const centre = current.find((node) => node.id === story.centerId);
        const away = centre ? centreOf(centre) : { x: 0, y: 0 };
        const obstacles: Pin[] = current.map((node) =>
          node.id === expandedRef.current
            ? {
                id: node.id,
                position: {
                  x:
                    node.position.x -
                    (STORY_EXPANDED.width - (node.width ?? 0)) / 2,
                  y: node.position.y,
                },
                ...STORY_EXPANDED,
              }
            : {
                id: node.id,
                position: node.position,
                width: node.width,
                height: node.height,
              },
        );
        const byAnchor = new Map<string, string[]>();
        for (const id of fresh) {
          const anchor =
            anchorId ??
            revealAnchor(id, data.edges, present, groups) ??
            story.centerId;
          byAnchor.set(anchor, [...(byAnchor.get(anchor) ?? []), id]);
        }
        const added: Node<StoryNodeState>[] = [];
        for (const [anchor, list] of byAnchor) {
          const anchorNode = current.find((node) => node.id === anchor);
          if (!anchorNode) continue;
          const spots = placeAround(
            {
              id: anchor,
              position: anchorNode.position,
              width: anchorNode.width,
              height: anchorNode.height,
            },
            list.map((id) => ({ id, ...STORY_CARD })),
            [
              ...obstacles,
              ...added.map((node) => ({
                id: node.id,
                position: node.position,
                ...STORY_CARD,
              })),
            ],
            away,
          );
          const from = centreOf(anchorNode);
          for (const id of list) {
            const spot = spots.get(id)!;
            added.push(
              storyPin(id, spot, {
                x: from.x - (spot.x + STORY_CARD.width / 2),
                y: from.y - (spot.y + STORY_CARD.height / 2),
              }),
            );
          }
        }
        return [...current, ...added];
      });
      window.clearTimeout(arrivalTimer.current);
      arrivalTimer.current = window.setTimeout(
        () =>
          setStoryNodes((current) =>
            current.map((node) =>
              node.data.arriveFrom ? { ...node, data: {} } : node,
            ),
          ),
        900,
      );
    },
    [story, nodeById, data.edges, groups, storyPin, setStoryNodes],
  );
  const hideCards = useCallback(
    (ids: string[]) => {
      const hide = new Set(ids.filter((id) => !story?.nodeIds.includes(id)));
      setStoryNodes((current) => current.filter((node) => !hide.has(node.id)));
      setExpandedId((current) =>
        current && hide.has(current) ? null : current,
      );
    },
    [story, setStoryNodes],
  );
  const fitCards = useCallback(
    (ids: string[], delay = 80) => {
      window.setTimeout(
        () =>
          requestAnimationFrame(() => {
            try {
              fitView({
                nodes: ids.map((id) => ({ id })),
                padding: storyPadding(),
                duration: 650,
                minZoom: 0.4,
                maxZoom: 1,
              });
            } catch {
              // Graceful fallback
            }
          }),
        delay,
      );
    },
    [fitView, storyPadding],
  );
  /** Fans a group's hidden cards out around it, or folds them all back. */
  const toggleGroup = useCallback(
    (groupId: string) => {
      const group = groupById.get(groupId);
      if (!group) return;
      const visible = new Set(storyNodesRef.current.map((node) => node.id));
      const hidden = group.memberIds.filter((id) => !visible.has(id));
      if (hidden.length) {
        revealCards(hidden, groupId);
        fitCards([groupId, ...group.memberIds]);
      } else {
        hideCards(group.memberIds);
        // Settle the view back on what is left.
        fitCards(
          [...visible].filter(
            (id) =>
              !group.memberIds.includes(id) || story?.nodeIds.includes(id),
          ),
        );
      }
    },
    [groupById, story, revealCards, hideCards, fitCards],
  );
  const showConnections = useCallback(
    (id: string) => {
      const visible = new Set(storyNodesRef.current.map((node) => node.id));
      const hidden = hiddenNeighbours(id, data.edges, visible);
      if (!hidden.length) return;
      revealCards(hidden, id);
      fitCards([id, ...hidden]);
    },
    [data.edges, revealCards, fitCards],
  );
  /** An aggregate thread opens the hidden cards it stands for, beside its card. */
  const openAggregate = useCallback(
    (source: string, edgeIds: string[]) => {
      const ids = edgeIds.flatMap((edgeId) => {
        const edge = data.edges.find((entry) => entry.id === edgeId);
        if (!edge) return [];
        return [edge.source === source ? edge.target : edge.source];
      });
      revealCards(ids, source);
      fitCards([source, ...ids]);
    },
    [data.edges, revealCards, fitCards],
  );
  const storyModeRef = useRef(storyMode);
  storyModeRef.current = storyMode;
  const [tab, setTab] = useState<Tab>("gaps");
  // The backend's headline finding opens in the dock when the case loads.
  const headline = useMemo(() => resolveHeadline(data), [data]);
  const [dockMode, setDockMode] = useState<
    "closed" | "overview" | "analysis" | "inspector"
  >(() => (headline ? "overview" : "closed"));
  const [returnMode, setReturnMode] = useState<
    "closed" | "overview" | "analysis"
  >("analysis");
  const [search, setSearch] = useState("");
  const dockRef = useRef<HTMLElement>(null);
  const analysisRef = useRef<HTMLElement>(null);
  const previousDockMode = useRef(dockMode);
  useEffect(() => {
    // The headline opens with the case; on narrow screens it waits below the
    // board instead of scrolling the page away from it. Only a change of mode
    // scrolls (a ref, not a mount flag, so StrictMode's rerun is a no-op).
    if (previousDockMode.current === dockMode) return;
    previousDockMode.current = dockMode;
    if (
      dockMode !== "closed" &&
      window.matchMedia("(max-width: 900px)").matches
    ) {
      dockRef.current?.scrollIntoView({ block: "start" });
    }
  }, [dockMode]);
  const searchRef = useRef<HTMLInputElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const focusAnalysisEntry = useCallback(
    () => document.getElementById(`analysis-entry-${tab}`)?.focus(),
    [tab],
  );

  const focusTarget = useCallback(
    (
      targetNodeIds: Set<string> | string[],
      options?: { dockOpen?: boolean; reveal?: boolean },
    ) => {
      let ids = Array.from(targetNodeIds);
      if (ids.length === 0) return;
      let delay = 0;
      if (storyModeRef.current) {
        // Hidden targets come onto the story board first; for broad focus
        // (a whole analysis tab) their group cards stand in for them.
        const visible = new Set(storyNodesRef.current.map((node) => node.id));
        const plan = planFocus(ids, visible, groups, options?.reveal ?? true);
        if (plan.reveal.length) {
          revealCards(plan.reveal);
          delay = 80;
        }
        ids = plan.focus;
        if (ids.length === 0) return;
      }
      const isNarrow =
        typeof window !== "undefined" &&
        window.matchMedia("(max-width: 900px)").matches;
      const isDockOpen = options?.dockOpen ?? dockMode !== "closed";
      const fitOptions = getFocusFitOptions({
        nodeCount: ids.length,
        isNarrow,
        dockOpen: isDockOpen,
      });
      if (storyModeRef.current)
        fitOptions.padding = getStoryPadding({
          runPanelOpen: isRunPanelOpen(),
          isNarrow,
          dockOpen: isDockOpen,
        });

      const fit = () =>
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
      if (delay) window.setTimeout(fit, delay);
      else fit();
    },
    [fitView, dockMode, groups, revealCards],
  );

  const resetBoardView = useCallback(() => {
    requestAnimationFrame(() => {
      try {
        fitView(
          storyModeRef.current
            ? {
                padding: storyPadding(),
                duration: 650,
                minZoom: 0.3,
                maxZoom: 1,
              }
            : {
                padding: {
                  top: "90px",
                  bottom: "100px",
                  left: "90px",
                  right: "60px",
                },
                duration: 650,
                minZoom: 0.5,
                maxZoom: 1.1,
              },
        );
      } catch {
        // Graceful fallback
      }
    });
  }, [fitView, storyPadding]);
  // The story fit leaves room for an open run panel; refit when it opens or collapses so the story uses the space.
  useEffect(() => {
    const refit = () => {
      // A morph is already easing the camera to the story.
      if (storyModeRef.current && !morph.morphingRef.current) resetBoardView();
    };
    window.addEventListener(RUN_PANEL_EVENT, refit);
    return () => window.removeEventListener(RUN_PANEL_EVENT, refit);
  }, [resetBoardView]);

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
      if (targetNodes.size > 0)
        focusTarget(targetNodes, { dockOpen: true, reveal: false });
    }
    requestAnimationFrame(() => {
      if (openerRef.current?.isConnected) openerRef.current.focus();
      else if (returnMode === "analysis") analysisRef.current?.focus();
      else focusAnalysisEntry();
    });
  }, [returnMode, resetBoardView, tab, data, focusTarget, focusAnalysisEntry]);

  /** Opens the dock on one analysis tab; pressing the open tab's entry closes it. */
  const openAnalysis = useCallback(
    (next: Tab, options?: { toggle?: boolean }) => {
      if (
        options?.toggle !== false &&
        dockMode === "analysis" &&
        tab === next
      ) {
        setDockMode("closed");
        resetBoardView();
        return;
      }
      setDockMode("analysis");
      setSelection(null);
      setTab(next);
      focusTarget(getNodesForTab(next, data), {
        dockOpen: true,
        reveal: false,
      });
    },
    [dockMode, tab, data, focusTarget, resetBoardView],
  );
  const analysisShown =
    dockMode === "analysis" ||
    (dockMode === "inspector" && returnMode === "analysis");
  /** One tab strip serves the headline ("Key finding") and the analysis lists. */
  const dockTabs = useMemo(
    () =>
      [
        ...(headline ? [["overview", "Key finding", null] as const] : []),
        ["gaps", "Gaps", data.gaps.length] as const,
        ["insights", "Insights", data.insights.length] as const,
        ["suggestions", "Next evidence", data.suggestions.length] as const,
      ] as ReadonlyArray<readonly [Tab | "overview", string, number | null]>,
    [headline, data],
  );
  const activeDockTab: Tab | "overview" =
    dockMode === "overview" ? "overview" : tab;
  const selectDockTab = useCallback(
    (next: Tab | "overview") => {
      setSelection(null);
      if (next === "overview") {
        setDockMode("overview");
        return;
      }
      setDockMode("analysis");
      setTab(next);
      // Tab-level focus highlights group cards rather than revealing every hidden card.
      focusTarget(getNodesForTab(next, data), {
        dockOpen: true,
        reveal: false,
      });
    },
    [data, focusTarget],
  );

  useEffect(() => {
    if (focusSelection && active) {
      inspect(focusSelection.kind, focusSelection.id, focusSelection.sourceId);
      onClearFocusSelection?.();
    }
  }, [focusSelection, active, inspect, onClearFocusSelection]);
  // Fixture positions are hand-placed; backend positions are column placeholders.
  const layout = useMemo(
    () =>
      isMock ? undefined : layoutCaseGraph(layoutData.nodes, layoutData.edges),
    [layoutData],
  );
  const initialNodes: Node<PinData>[] = useMemo(
    () =>
      arrangePins(
        layoutData.nodes.map((n) => {
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
              timeZone: layoutData.timezone,
              caseId: layoutData.id,
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
    [layoutData, inspect, layout],
  );
  const initialEdges: Edge<ThreadData>[] = useMemo(
    () => layoutData.edges.map(threadEdge),
    [layoutData],
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
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  // The full board arrives after the run when a live import started on an empty map.
  const laidOutFor = useRef(layoutData);
  useEffect(() => {
    if (laidOutFor.current === layoutData) return;
    laidOutFor.current = layoutData;
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [layoutData, initialNodes, initialEdges, setNodes, setEdges]);
  const revealedNodeIds = useMemo(
    () => new Set(data.nodes.map((n) => n.id)),
    [data.nodes],
  );
  const revealedEdgeIds = useMemo(
    () => new Set(data.edges.map((e) => e.id)),
    [data.edges],
  );
  // Full graph <-> story animation, also when a replay hands over to the story.
  const morph = useStoryMorph({
    caseId: data.id,
    growing,
    active,
    opensOnStory: storyMode,
    fullNodes: nodes,
    storyNodes,
    groups,
    shownIds: revealedNodeIds,
    getViewport,
    fitView,
    storyPadding,
  });
  // Fit the board beside the dock when it is open, including the headline on load.
  dockOpenRef.current = dockMode !== "closed";
  const fitPadding = storyMode
    ? getStoryPadding({
        runPanelOpen: isRunPanelOpen(),
        isNarrow: isNarrowViewport(),
        dockOpen: dockMode !== "closed",
      })
    : {
        ...getFocusPadding({
          isNarrow: isNarrowViewport(),
          dockOpen: dockMode !== "closed",
        }),
        top: "90px" as const,
      };
  // An expanded card must be readable whole: once it has grown, pan the view
  // (never the layout) so it sits inside the visible canvas.
  useEffect(() => {
    if (!expandedId) return;
    const timer = window.setTimeout(() => {
      const card = document.querySelector(
        `.react-flow__node[data-id="${CSS.escape(expandedId)}"] .story-card`,
      );
      const wrap = card?.closest(".canvas-wrap");
      if (!card || !wrap) return;
      const box = card.getBoundingClientRect();
      const area = wrap.getBoundingClientRect();
      const pad = getStoryPadding({
        runPanelOpen: isRunPanelOpen(),
        isNarrow: isNarrowViewport(),
        dockOpen: dockOpenRef.current,
      });
      const bounds = {
        top: area.top + parseFloat(pad.top),
        bottom: area.bottom - parseFloat(pad.bottom),
        left: area.left + parseFloat(pad.left),
        right: area.right - parseFloat(pad.right),
      };
      let dx = 0;
      let dy = 0;
      if (box.bottom > bounds.bottom) dy = bounds.bottom - box.bottom;
      if (box.top + dy < bounds.top) dy = bounds.top - box.top;
      if (box.right > bounds.right) dx = bounds.right - box.right;
      if (box.left + dx < bounds.left) dx = bounds.left - box.left;
      if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return;
      const view = getViewport();
      void setViewport(
        { x: view.x + dx, y: view.y + dy, zoom: view.zoom },
        { duration: 320 },
      );
    }, 380);
    return () => window.clearTimeout(timer);
  }, [expandedId, getViewport, setViewport]);
  // The story always fits whole, so its group cards are never cropped.
  const fitZoom = storyMode
    ? { minZoom: 0.3, maxZoom: 1 }
    : { minZoom: 0.5, maxZoom: 1.1 };
  const normalizedSearch = search.trim().toLowerCase();
  const revealedNodes = useMemo(
    () => nodes.filter((n) => revealedNodeIds.has(n.id)),
    [nodes, revealedNodeIds],
  );
  const matchingNodes = useMemo(
    () =>
      normalizedSearch
        ? revealedNodes.filter((n) =>
            `${n.data.label} ${n.data.summary}`
              .toLowerCase()
              .includes(normalizedSearch),
          )
        : revealedNodes,
    [revealedNodes, normalizedSearch],
  );
  const matchingNodeIds = useMemo(
    () => (normalizedSearch ? new Set(matchingNodes.map((n) => n.id)) : null),
    [matchingNodes, normalizedSearch],
  );
  const rawFocusedNodeIds = useMemo(() => {
    if (selection) {
      return getNodesForSelection(selection, data);
    }
    if (dockMode === "analysis") {
      return getNodesForTab(tab, data);
    }
    return null;
  }, [selection, dockMode, tab, data]);
  // In the story view, a hidden target is represented by its group card.
  const focusedNodeIds = useMemo(
    () =>
      rawFocusedNodeIds && storyMode
        ? new Set(
            planFocus(rawFocusedNodeIds, storyVisibleIds, groups, false).focus,
          )
        : rawFocusedNodeIds,
    [rawFocusedNodeIds, storyMode, storyVisibleIds, groups],
  );
  /** Search matches still folded into groups. */
  const hiddenMatches = useMemo(
    () =>
      storyMode && matchingNodeIds
        ? Array.from(matchingNodeIds).filter((id) => !storyVisibleIds.has(id))
        : [],
    [storyMode, matchingNodeIds, storyVisibleIds],
  );

  const excerptsFor = useCallback(
    (citations: string[]): StoryExcerpt[] =>
      citations.slice(0, 3).flatMap((id) => {
        const source = sourceById.get(id);
        if (!source) return [];
        const evidenceId = source.metadata?.evidence_id;
        const locator = source.metadata?.locator;
        return [
          {
            id,
            locator: evidenceId
              ? `${evidenceId}${locator ? ` ${locator}` : ""}`
              : source.path.split("/").pop() || id,
            text: source.excerpt,
          },
        ];
      }),
    [sourceById],
  );

  const storyFlowNodes = useMemo(() => {
    if (!storyMode || !story) return [];
    return storyNodes.map((n) => {
      const isFocused = focusedNodeIds ? focusedNodeIds.has(n.id) : false;
      const group = groupById.get(n.id);
      if (group) {
        const matches = matchingNodeIds
          ? group.memberIds.filter(
              (id) => matchingNodeIds.has(id) && !storyVisibleIds.has(id),
            ).length
          : 0;
        const isDimmed =
          (matchingNodeIds && matches === 0) || (focusedNodeIds && !isFocused);
        return {
          ...n,
          className:
            `${isDimmed ? "dimmed-node" : ""} ${isFocused ? "focused-node" : ""}`.trim(),
          data: {
            title: group.title,
            rule: group.rule,
            nodeType: group.nodeType,
            total: group.memberIds.length,
            hidden: group.memberIds.filter((id) => !storyVisibleIds.has(id))
              .length,
            width: n.width ?? STORY_GROUP.width,
            height: n.height ?? STORY_GROUP.height,
            isFocused,
            matches,
            onToggle: () => toggleGroup(n.id),
          },
        };
      }
      const source = nodeById.get(n.id)!;
      const expanded = expandedId === n.id;
      const isDimmed =
        (matchingNodeIds && !matchingNodeIds.has(n.id)) ||
        (focusedNodeIds && !isFocused);
      return {
        ...n,
        zIndex: expanded ? 1000 : undefined,
        className:
          `${isDimmed && !expanded ? "dimmed-node" : ""} ${isFocused ? "focused-node" : ""}`.trim(),
        data: {
          label: source.label,
          type: source.type,
          subtitle: source.subtitle,
          summary: source.summary,
          citations: source.citations,
          time: source.time,
          timeZone: data.timezone,
          certainty: source.certainty,
          gapId: source.gapId,
          width: n.width ?? STORY_CARD.width,
          height: n.height ?? STORY_CARD.height,
          hero: n.id === story.centerId,
          expanded,
          active:
            selection?.kind === "node" ? selection.id === n.id : isFocused,
          isFocused,
          excerpts: expanded ? excerptsFor(source.citations) : [],
          hiddenNeighbours: hiddenNeighbours(n.id, data.edges, storyVisibleIds)
            .length,
          arriveFrom: n.data.arriveFrom,
          onToggle: () =>
            setExpandedId((current) => (current === n.id ? null : n.id)),
          onCollapse: () => setExpandedId(null),
          onInspect: () => inspect("node", n.id),
          onInspectGap: source.gapId
            ? () => inspect("gap", source.gapId!)
            : undefined,
          onShowConnections: () => showConnections(n.id),
        },
      };
    });
  }, [
    storyMode,
    story,
    storyNodes,
    focusedNodeIds,
    groupById,
    matchingNodeIds,
    storyVisibleIds,
    toggleGroup,
    nodeById,
    expandedId,
    data,
    selection,
    excerptsFor,
    inspect,
    showConnections,
  ]);

  /** Story threads: real threads between visible cards, plus one aggregate per card and group. */
  const storyEdges = useMemo(() => {
    if (!storyMode || !story) return [];
    const { shown, aggregates } = storyThreads(
      data.edges,
      storyVisibleIds,
      groups,
    );
    const inStory = new Set(story.nodeIds);
    const real = shown.map((e) => {
      const edge = threadEdge(e);
      return {
        ...edge,
        data: {
          ...edge.data!,
          quiet: !(inStory.has(e.source) && inStory.has(e.target)),
        },
      };
    });
    const folded: Edge<ThreadData>[] = aggregates.map((thread) => {
      const category = thread.category ?? "other";
      const kind = thread.kind === "mixed" ? "inference" : thread.kind;
      const label = aggregateLabel(thread);
      const group = groupById.get(thread.target);
      const from = nodeById.get(thread.source)?.label ?? thread.source;
      return {
        id: thread.id,
        source: thread.source,
        target: thread.target,
        type: "thread",
        className: "aggregate-edge",
        ariaLabel: `${label} between ${from} and cards in ${group?.title}`,
        data: {
          kind,
          category,
          label,
          directed: false,
          aggregateCount: thread.count,
          quiet: true,
          ariaLabel: `${label} between ${from} and cards folded into ${group?.title}. Show those ${thread.count === 1 ? "card" : "cards"}`,
          onInspect: () => openAggregate(thread.source, thread.edgeIds),
        },
        style: {
          stroke: threadColors[category].ink,
          strokeWidth: 3,
          strokeLinecap: "round",
          strokeDasharray: threadDash(kind),
        },
      };
    });
    return [...real, ...folded];
  }, [
    storyMode,
    story,
    data.edges,
    storyVisibleIds,
    groups,
    groupById,
    nodeById,
    openAggregate,
  ]);

  // Items revealed in the same tick fade in a few tens of ms apart.
  const revealDelays = useRef(new Map<string, number>());
  const visibleNodes = useMemo(() => {
    let fresh = 0;
    return revealedNodes.map((n) => {
      const isFocused = focusedNodeIds ? focusedNodeIds.has(n.id) : false;
      const isDimmed =
        (matchingNodeIds && !matchingNodeIds.has(n.id)) ||
        (focusedNodeIds && !isFocused);
      if (growing && !revealDelays.current.has(n.id))
        revealDelays.current.set(n.id, Math.min(fresh++, 6) * 50);
      const delay = revealDelays.current.get(n.id);
      return {
        ...n,
        ...(delay
          ? { style: { ...n.style, "--reveal-delay": `${delay}ms` } }
          : {}),
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
    });
  }, [
    revealedNodes,
    matchingNodeIds,
    focusedNodeIds,
    selection,
    inspect,
    growing,
  ]);

  const { decorate: decorateMorph } = morph;
  const flowNodes = useMemo(
    () => decorateMorph((storyMode ? storyFlowNodes : visibleNodes) as Node[]),
    [decorateMorph, storyMode, storyFlowNodes, visibleNodes],
  );

  const visibleEdges = useMemo(() => {
    // In the full graph a running replay shows only the threads revealed so far.
    const list = storyMode
      ? storyEdges
      : edges.filter((edge) => revealedEdgeIds.has(edge.id));
    const positioned: Array<{
      id: string;
      position: Point;
      width?: number;
      height?: number;
    }> = storyMode ? storyNodes : nodes;
    const nodesById = new Map(positioned.map((node) => [node.id, node]));
    const offsets = labelOffsets(list);
    return list.map((edge) => {
      const source = nodesById.get(edge.source);
      const target = nodesById.get(edge.target);
      const isFocused = focusedNodeIds
        ? focusedNodeIds.has(edge.source) && focusedNodeIds.has(edge.target)
        : false;
      const isDimmed = focusedNodeIds && !isFocused;
      const touches = (id: string | null) =>
        id !== null && (edge.source === id || edge.target === id);
      return {
        ...edge,
        className:
          `${edge.className ?? ""} ${isDimmed ? "dimmed-edge" : ""} ${isFocused ? "focused-edge" : ""}`.trim(),
        ...(source && target
          ? storyMode
            ? // Story cards differ in size, so threads attach by centres.
              threadHandles(centreOf(source), centreOf(target))
            : threadHandles(source.position, target.position)
          : {}),
        selected:
          selection?.kind === "edge" ? selection.id === edge.id : isFocused,
        data: edge.data
          ? {
              ...edge.data,
              isFocused,
              isDimmed: Boolean(isDimmed),
              labelOffset: offsets.get(edge.id),
              hovered: hoveredEdgeId === edge.id || touches(hoveredNodeId),
              onInspect: edge.data.aggregateCount
                ? edge.data.onInspect
                : () => inspect("edge", edge.id),
            }
          : undefined,
      };
    });
  }, [
    storyMode,
    storyEdges,
    storyNodes,
    edges,
    revealedEdgeIds,
    nodes,
    focusedNodeIds,
    selection,
    inspect,
    hoveredEdgeId,
    hoveredNodeId,
    expandedId,
  ]);

  const switchView = useCallback(
    (mode: "story" | "full") => {
      if (mode === viewMode) return;
      setExpandedId(null);
      const morphing = morph.start(mode);
      setViewMode(mode);
      window.setTimeout(() => {
        const targets = selection
          ? getNodesForSelection(selection, data)
          : null;
        if (targets && targets.size && mode === "full")
          focusTarget(targets, { reveal: false });
        else if (morphing && mode === "story") morph.fitStory();
        else resetBoardView();
      }, 40);
    },
    [viewMode, selection, data, focusTarget, resetBoardView, morph],
  );
  const onStoryNodesChange = useCallback(
    (changes: NodeChange<Node<StoryNodeState>>[]) => {
      setStoryNodes((current) => {
        const next = applyNodeChanges(changes, current);
        const settledIds = changes.flatMap((change) =>
          change.type === "position" && !change.dragging ? [change.id] : [],
        );
        return settledIds.length ? settlePinMoves(next, settledIds) : next;
      });
    },
    [setStoryNodes],
  );
  // A replay frames the finished layout once, so cards appear in place while the camera holds still.
  // An import starts before its layout exists (an empty case), so frame once per layout, and only
  // when it has cards; otherwise the camera would stay fixed on an empty frame.
  const framedReplay = useRef<CaseData | null>(null);
  const [flowReady, setFlowReady] = useState(false);
  // Opening on the story as a replay ends: ease from the growing board's camera.
  const morphFit = useRef(false);
  const { handoff: morphHandoff, begin: beginMorph, fitStory } = morph;
  useEffect(() => {
    if (!morphHandoff || !flowReady || morphFit.current) return;
    morphFit.current = true;
    window.setTimeout(() => {
      beginMorph();
      fitStory();
    }, 30);
  }, [morphHandoff, flowReady, beginMorph, fitStory]);
  useEffect(() => {
    if (!growing) {
      framedReplay.current = null;
      return;
    }
    if (
      framedReplay.current === layoutData ||
      nodes.length === 0 ||
      !flowReady ||
      !active ||
      dockMode !== "closed"
    )
      return;
    framedReplay.current = layoutData;
    const bounds = boundsOf(
      nodes.map((node) => ({ ...node.position, ...nodeSize(node) })),
    );
    // Leave room on the left for the run panel.
    const panel = bounds.width * 0.3;
    void fitBounds(
      { ...bounds, x: bounds.x - panel, width: bounds.width + panel },
      { padding: 0.08, duration: 400 },
    );
  }, [growing, flowReady, active, dockMode, fitBounds, nodes, layoutData]);
  return (
    <>
      <div className="workspace">
        <div className="board-area">
          <div className="board-toolbar">
            <CaseTitle
              title={projectName || data.title}
              subtitle={formatCaseSubtitle(data.subtitle, data.timezone)}
            />
            <div className="board-actions">
              <label className="board-search">
                <Search size={14} />
                <input
                  ref={searchRef}
                  aria-label="Find evidence"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  onKeyDown={(e) => {
                    // Enter brings matches folded into story groups onto the board.
                    if (e.key !== "Enter" || !hiddenMatches.length) return;
                    const ids = hiddenMatches.slice(0, 12);
                    revealCards(ids);
                    fitCards(ids, 120);
                  }}
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
              <AnalysisEntries
                data={data}
                active={analysisShown ? tab : null}
                onOpen={(next) => openAnalysis(next)}
              />
            </div>
          </div>
          <div
            className={`canvas-wrap ${storyMode ? "is-story" : ""}${growing ? " replay-growing" : ""}${morph.className}`}
            style={{ ...boardColorVars(), ...morph.style }}
          >
            <ReactFlow
              nodes={flowNodes}
              edges={visibleEdges}
              onNodesChange={
                (storyMode ? onStoryNodesChange : onNodesChange) as (
                  changes: NodeChange<Node>[],
                ) => void
              }
              onEdgesChange={onEdgesChange}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              onNodeClick={(event, n) => {
                if (!storyMode) {
                  inspect("node", n.id);
                  return;
                }
                if (isGroupId(n.id)) toggleGroup(n.id);
                else if (
                  !(event.target as HTMLElement).closest(".story-card-body")
                )
                  setExpandedId((current) => (current === n.id ? null : n.id));
              }}
              onEdgeClick={(_, e) => {
                const edge = visibleEdges.find((entry) => entry.id === e.id);
                if (edge?.data?.aggregateCount) edge.data.onInspect();
                else inspect("edge", e.id);
              }}
              onNodeMouseEnter={(_, n) => setHoveredNodeId(n.id)}
              onNodeMouseLeave={() => setHoveredNodeId(null)}
              onEdgeMouseEnter={(_, e) => setHoveredEdgeId(e.id)}
              onEdgeMouseLeave={() => setHoveredEdgeId(null)}
              onPaneClick={() => {
                if (expandedId) setExpandedId(null);
                else if (dockMode === "inspector") closeInspector();
              }}
              onInit={() => setFlowReady(true)}
              fitView={!growing && !morph.handoff}
              defaultViewport={morph.handoff?.viewport}
              fitViewOptions={{ padding: fitPadding, ...fitZoom }}
              panOnScroll
              panOnScrollSpeed={1}
              zoomOnScroll={false}
              zoomOnPinch
              minZoom={0.15}
              maxZoom={1.8}
              nodesConnectable={false}
              // Each card's inspect button and each thread's label button are
              // the keyboard stops; the wrappers would add a second, unstyled
              // stop per card and thread.
              nodesFocusable={false}
              edgesFocusable={false}
              deleteKeyCode={null}
              proOptions={{ hideAttribution: true }}
            >
              <Controls
                position="bottom-right"
                showInteractive={false}
                fitViewOptions={{ padding: fitPadding, ...fitZoom }}
              >
                <ZoomReadout />
              </Controls>
              {!storyMode && <CanvasMinimap frameNodes={nodes} />}
            </ReactFlow>
            {story && !growing && (
              <div
                className="board-view-switch"
                role="group"
                aria-label="Board view"
              >
                <button
                  type="button"
                  aria-pressed={storyMode}
                  title={`${story.reason} ${storyVisibleIds.size - groups.length} of ${data.nodes.length} cards on the board.`}
                  onClick={() => switchView("story")}
                >
                  <Focus size={14} aria-hidden="true" /> Story
                  <span className="board-view-count">
                    {storyVisibleIds.size - groups.length}
                  </span>
                </button>
                <button
                  type="button"
                  aria-pressed={!storyMode}
                  onClick={() => switchView("full")}
                >
                  <Network size={14} aria-hidden="true" /> Full graph
                  <span className="board-view-count">{data.nodes.length}</span>
                </button>
              </div>
            )}
            {search.trim() && (
              <div className="search-feedback" role="status">
                {matchingNodes.length
                  ? `${matchingNodes.length} matching pin${matchingNodes.length === 1 ? "" : "s"}. Other pins are dimmed.`
                  : "No matching evidence. Try a name, device, or location."}
                {hiddenMatches.length > 0 && (
                  <>
                    {" "}
                    {hiddenMatches.length} folded into groups.{" "}
                    <button
                      type="button"
                      className="search-feedback-action"
                      onClick={() => {
                        const ids = hiddenMatches.slice(0, 12);
                        revealCards(ids);
                        fitCards(ids, 120);
                      }}
                    >
                      Show {hiddenMatches.length > 12 ? "first 12" : "them"}
                    </button>
                  </>
                )}
              </div>
            )}
            <BoardLegend
              nodes={data.nodes}
              edges={data.edges}
              yield={dockMode !== "closed"}
            />
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
                <h2>Analysis</h2>
              </div>
              <button
                className="icon-button"
                aria-label="Close review dock"
                onClick={() => {
                  setSelection(null);
                  setDockMode("closed");
                  resetBoardView();
                  focusAnalysisEntry();
                }}
              >
                <X size={16} />
              </button>
            </div>
          )}
          <div
            className="analysis-tabs"
            role="tablist"
            aria-label="Case analysis"
            hidden={dockMode !== "analysis" && dockMode !== "overview"}
          >
            {dockTabs.map(([id, label, count]) => (
              <button
                key={id}
                role="tab"
                id={`tab-${id}`}
                aria-controls={`panel-${id}`}
                aria-selected={activeDockTab === id}
                tabIndex={activeDockTab === id ? 0 : -1}
                onKeyDown={(event) => {
                  const ids = dockTabs.map(([entry]) => entry);
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
                        ? ids[0]
                        : event.key === "End"
                          ? ids[ids.length - 1]
                          : ids[
                              (ids.indexOf(activeDockTab) +
                                offset +
                                ids.length) %
                                ids.length
                            ];
                    selectDockTab(next);
                    document.getElementById(`tab-${next}`)?.focus();
                  }
                }}
                className={activeDockTab === id ? "active" : ""}
                onClick={() => selectDockTab(id)}
              >
                {label}
                {count !== null && <span>{count}</span>}
              </button>
            ))}
          </div>
          {headline && (
            <section
              className="panel-content overview-panel"
              role="tabpanel"
              id="panel-overview"
              aria-labelledby="tab-overview"
              hidden={dockMode !== "overview"}
            >
              <HeadlinePanel
                headline={headline}
                data={data}
                onInspectSource={(sourceId) =>
                  inspect(headline.kind, headline.id, sourceId)
                }
                onReviewSources={() => {
                  inspect(headline.kind, headline.id);
                  // Land on the full source list rather than the item summary.
                  requestAnimationFrame(() =>
                    requestAnimationFrame(() =>
                      dockRef.current
                        ?.querySelector(".inspector .sources-section")
                        ?.scrollIntoView({ block: "start" }),
                    ),
                  );
                }}
              />
            </section>
          )}
          <aside
            className="analysis-panel"
            ref={analysisRef}
            tabIndex={-1}
            aria-label="Analysis"
            hidden={dockMode !== "analysis"}
          >
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
              returnMode === "overview"
                ? "Back to key finding"
                : returnMode === "closed"
                  ? "Back to board"
                  : tab === "gaps"
                    ? "Back to gaps"
                    : tab === "insights"
                      ? "Back to insights"
                      : "Back to next evidence"
            }
          />
        </aside>
      </div>
    </>
  );
}

function Board(props: {
  data: CaseData;
  layoutData?: CaseData;
  growing?: boolean;
  /** Run panel from the replay, mounted beside the Ask widget. */
  hud?: ReactNode;
  projectName?: string;
  onOpenSource: (sourceId: string) => void;
  onAskQuestion: () => void;
  active: boolean;
  focusSelection?: Selection | null;
  onClearFocusSelection?: () => void;
}) {
  return (
    <>
      <ReactFlowProvider>
        <BoardCanvas {...props} />
      </ReactFlowProvider>
      {props.hud}
      <AskWidget caseId={props.data.id} onAsk={props.onAskQuestion} />
    </>
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
  const [confirmOpen, setConfirmOpen] = useState(false);
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
    // A case opened while its import still runs becomes loadable when it finishes.
    refetchInterval: (query) =>
      isApiError(query.state.error, "not_ready") ? 1500 : false,
  });
  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: () => api.getHealth?.() ?? Promise.resolve({ llmLive: false }),
    enabled: uploadOpen && api.mode === "live",
    staleTime: 30_000,
    retry: false,
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
  const caseNotReady = isApiError(caseQuery.error, "not_ready");
  // A query with no data goes back to "pending" on every refetch. While an import runs, those
  // refetches must not swap the board for the opening spinner: that remounts the replay and
  // restarts it, so the run would never be seen growing. Once a case has answered "not ready"
  // (or opened to replay), keep the board mounted until its data arrives.
  const awaitingRunRef = useRef<string | null>(null);
  if (routeCaseId && (caseNotReady || replayRequested(routeCaseId)))
    awaitingRunRef.current = routeCaseId;
  const caseOpening =
    caseQuery.isPending &&
    !(routeCaseId && awaitingRunRef.current === routeCaseId);
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
      // The confirmation dialog handles its own Escape and Tab.
      if (document.querySelector(".confirm-modal")) return;
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

  async function upload(analysisMode?: AnalysisMode) {
    if (!file) return;
    setError("");
    setUploading(true);
    try {
      const result = await api.createUpload(file, {
        caseName: projectName,
        analysisMode,
      });
      setConfirmOpen(false);
      if (api.mode === "live" && result.caseId) {
        // Go straight to the empty map; the run is shown as it happens.
        const caseId = result.caseId;
        const name = projectName.trim() || file.name.replace(/\.zip$/i, "");
        requestReplay(caseId);
        setProjects((current) => [
          { caseId, name },
          ...current.filter((p) => p.caseId !== caseId),
        ]);
        void queryClient.invalidateQueries({ queryKey: ["cases"] });
        setProjectName("");
        setFile(null);
        setUploading(false);
        navigate(casePath(caseId));
        return;
      }
      setJobId(result.jobId);
      setUploadedCaseId(result.caseId ?? null);
    } catch (e) {
      setError(
        isApiError(e, "needs_api_key")
          ? "Live analysis needs an Anthropic API key on the server. Choose the free replay instead, or ask the server owner to configure a key."
          : e instanceof Error
            ? e.message
            : "Upload failed. Try again.",
      );
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
    setConfirmOpen(false);
  }
  closeUploadRef.current = closeUpload;
  /** Opens a case by ID, or the demo case when no ID is given. */
  async function openCase(requestedId?: string) {
    setError("");
    setOpeningCase(true);
    try {
      const caseId = requestedId ?? (await api.openDemo());
      // The demo opens on an empty map and replays its recorded run.
      if (!requestedId && api.mode === "live") requestReplay(caseId);
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
          {(route.kind !== "case" ||
            (!caseQuery.data && !caseNotReady && caseOpening) ||
            caseNotFound) && (
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
            ) : caseOpening ? (
              <div className="center-state">
                <LoaderCircle className="spin" />
                <h2>Opening evidence workspace…</h2>
              </div>
            ) : caseQuery.isError &&
              !isApiError(caseQuery.error, "not_ready") ? (
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
            ) : route.kind === "case" ? (
              <ReplayedCase
                caseId={route.caseId}
                data={caseQuery.data}
                title={
                  projects.find((project) => project.caseId === route.caseId)
                    ?.name ?? route.caseId
                }
                fallback={
                  <div className="center-state">
                    <h2>This case is still being analysed</h2>
                    <button
                      className="button button-primary"
                      onClick={() => caseQuery.refetch()}
                    >
                      Check again
                    </button>
                  </div>
                }
              >
                {(shown, context) => (
                  <CaseWorkspace
                    key={route.caseId}
                    data={shown}
                    view={
                      route.kind === "case" ? (route.view ?? "board") : "board"
                    }
                    sourceId={
                      route.kind === "case" ? route.sourceId : undefined
                    }
                    insightsTab={
                      route.kind === "case" ? route.insightsTab : undefined
                    }
                    navigate={navigate}
                    onFocusOnBoard={(sel) => {
                      setFocusSelection(sel);
                      if (route.kind !== "case" || route.view) {
                        navigate(casePath(route.caseId));
                      }
                    }}
                    projectName={
                      projects.find(
                        (project) => project.caseId === route.caseId,
                      )?.name
                    }
                  >
                    <Board
                      // The story is laid out from complete data, so the board starts afresh when a replay ends.
                      key={context.growing ? "replay-growing" : "settled"}
                      layoutData={context.layoutData}
                      growing={context.growing}
                      hud={context.hud}
                      data={shown}
                      active={route.kind === "case" && !route.view}
                      focusSelection={focusSelection}
                      onClearFocusSelection={() => setFocusSelection(null)}
                      projectName={
                        projects.find(
                          (project) => project.caseId === route.caseId,
                        )?.name
                      }
                      onAskQuestion={() =>
                        navigate(casePath(route.caseId, "chat"))
                      }
                      onOpenSource={(sourceId) =>
                        navigate(casePath(route.caseId, "evidence", sourceId))
                      }
                    />
                  </CaseWorkspace>
                )}
              </ReplayedCase>
            ) : null}
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
            <p>
              {UPLOADS_ENABLED
                ? "Name your project and select a ZIP archive."
                : `${UPLOADS_OFF_REASON} Open the fictional Kestrel case instead.`}
            </p>
            <label className="project-name-field" hidden={!UPLOADS_ENABLED}>
              Project name <span>(optional)</span>
              <input
                maxLength={80}
                placeholder="e.g. Inventory review"
                value={projectName}
                disabled={uploading || !UPLOADS_ENABLED}
                onChange={(e) => setProjectName(e.target.value)}
              />
            </label>
            <div
              className={`dropzone ${dragging ? "dragging" : ""} ${UPLOADS_ENABLED ? "" : "is-off"}`}
              aria-disabled={UPLOADS_ENABLED ? undefined : true}
              onDragOver={(e) => {
                e.preventDefault();
                if (UPLOADS_ENABLED) setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                if (!uploading && UPLOADS_ENABLED) {
                  setFile(e.dataTransfer.files[0] ?? null);
                  setError("");
                }
              }}
            >
              <FileArchive size={30} />
              <strong>
                {file
                  ? file.name
                  : !UPLOADS_ENABLED
                    ? "ZIP uploads are off"
                    : api.mode === "live"
                      ? "Choose a ZIP of case evidence"
                      : "Choose a ZIP to preview the workspace"}
              </strong>
              <span>
                {file
                  ? `${(file.size / 1024 / 1024).toFixed(2)} MB`
                  : UPLOADS_ENABLED
                    ? "ZIP archive"
                    : "The demo case shows a finished analysis."}
              </span>
              <button
                disabled={uploading || !UPLOADS_ENABLED}
                hidden={!UPLOADS_ENABLED}
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
              disabled={
                UPLOADS_ENABLED
                  ? !file || (uploading && !ready) || openingCase
                  : openingCase
              }
              onClick={
                !UPLOADS_ENABLED
                  ? () => void openCase()
                  : ready
                    ? () =>
                        void openCase(
                          statusQuery.data?.caseId ??
                            uploadedCaseId ??
                            undefined,
                        )
                    : api.mode === "live"
                      ? () => {
                          setError("");
                          setConfirmOpen(true);
                        }
                      : () => void upload()
              }
            >
              {openingCase ? (
                <>
                  <LoaderCircle size={16} className="spin" /> Opening evidence
                  board
                </>
              ) : !UPLOADS_ENABLED ? (
                <>
                  Explore the demo case <ArrowRight size={16} />
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
            {!UPLOADS_ENABLED && api.mode === "live" ? null : api.mode ===
              "live" ? (
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
          {confirmOpen && file && (
            <UploadConfirm
              fileName={file.name}
              llmLive={healthQuery.data?.llmLive === true}
              busy={uploading}
              error={error}
              onCancel={() => {
                setConfirmOpen(false);
                setError("");
              }}
              onConfirm={(mode) => void upload(mode)}
            />
          )}
        </div>
      )}
    </>
  );
}
