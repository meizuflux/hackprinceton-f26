import { useCallback, useEffect, useRef, useState } from "react";
import type { FitViewOptions, Node } from "@xyflow/react";
import {
  MORPH_MS,
  morphFromStyle,
  planToFull,
  planToStory,
  prefersReducedMotion,
  registerGrowingBoard,
  takeGrowingBoard,
  type Box,
  type GrowingSnapshot,
  type MorphPlan,
} from "./morph";
import "./morph.css";

type View = "story" | "full";

const boxes = (nodes: readonly Node[]) =>
  new Map<string, Box>(
    nodes.map((node) => [
      node.id,
      {
        ...node.position,
        width: node.width ?? node.measured?.width,
        height: node.height ?? node.measured?.height,
      },
    ]),
  );

/**
 * Animates the board between the full graph and the story view: when a replay
 * ends (the growing board hands over its camera and cards) and when the
 * Story / Full graph switch is used. Presentation only; with reduced motion
 * nothing animates and the board behaves as before.
 */
export function useStoryMorph({
  caseId,
  growing,
  active,
  opensOnStory,
  fullNodes,
  storyNodes,
  groups,
  shownIds,
  getViewport,
  fitView,
  storyPadding,
}: {
  caseId: string;
  growing: boolean;
  active: boolean;
  /** This board opens on the story view. */
  opensOnStory: boolean;
  /** Full-graph cards at their laid-out places. */
  fullNodes: readonly Node[];
  /** Story cards and group cards at their story places. */
  storyNodes: readonly Node[];
  groups: ReadonlyArray<{ id: string; memberIds: string[] }>;
  /** Full-graph cards on screen. */
  shownIds: ReadonlySet<string>;
  getViewport: () => GrowingSnapshot["viewport"];
  fitView: (options?: FitViewOptions) => unknown;
  /** The story fit's padding (room for the dock and run panel). */
  storyPadding: () => FitViewOptions["padding"];
}) {
  // While the board grows, let the board that replaces it read where it was.
  const snapshot = useRef<() => GrowingSnapshot>(() => ({
    viewport: getViewport(),
    shown: shownIds,
  }));
  snapshot.current = () => ({ viewport: getViewport(), shown: shownIds });
  useEffect(
    () =>
      growing
        ? registerGrowingBoard(caseId, () => snapshot.current())
        : undefined,
    [growing, caseId],
  );

  // The settled board that opens as a replay ends starts from the growing board's camera.
  const [handoff] = useState(() =>
    !growing && active && opensOnStory && !prefersReducedMotion()
      ? takeGrowingBoard(caseId)
      : null,
  );
  const [morph, setMorph] = useState<{
    plan: MorphPlan;
    to: View;
    id: number;
    /** Cards wait at their starting places until the camera starts to move. */
    held: boolean;
  } | null>(() =>
    handoff
      ? {
          plan: planToStory(
            boxes(fullNodes),
            boxes(storyNodes),
            groups,
            handoff.shown,
          ),
          to: "story",
          id: 0,
          held: true,
        }
      : null,
  );
  const morphingRef = useRef(morph !== null);
  morphingRef.current = morph !== null;
  useEffect(() => {
    if (!morph) return;
    // A held morph starts with the camera, or after a moment if the board never frames it.
    const timer = morph.held
      ? window.setTimeout(
          () => setMorph((m) => (m ? { ...m, held: false } : m)),
          1500,
        )
      : window.setTimeout(() => setMorph(null), MORPH_MS + 150);
    return () => window.clearTimeout(timer);
  }, [morph]);
  /** Releases a held morph as the camera starts moving. */
  const begin = useCallback(
    () => setMorph((m) => (m?.held ? { ...m, held: false } : m)),
    [],
  );

  const latest = useRef({ fullNodes, storyNodes, groups, shownIds });
  latest.current = { fullNodes, storyNodes, groups, shownIds };
  /** Starts the animation into a view; returns false when motion is reduced. */
  const start = useCallback((to: View) => {
    if (prefersReducedMotion()) return false;
    const { fullNodes, storyNodes, groups, shownIds } = latest.current;
    const full = boxes(fullNodes.filter((node) => shownIds.has(node.id)));
    const story = boxes(storyNodes);
    setMorph({
      plan:
        to === "story"
          ? planToStory(full, story, groups, shownIds)
          : planToFull(full, story, groups),
      to,
      id: Date.now(),
      held: false,
    });
    return true;
  }, []);

  /** Eases the camera to the story cards (never the ghosts) over the morph. */
  const fitStory = useCallback(() => {
    requestAnimationFrame(() => {
      try {
        void fitView({
          nodes: latest.current.storyNodes.map(({ id }) => ({ id })),
          padding: storyPadding(),
          duration: MORPH_MS,
          minZoom: 0.3,
          maxZoom: 1,
        });
      } catch {
        // The board may have unmounted.
      }
    });
  }, [fitView, storyPadding]);

  /** Adds the arrival styles to the incoming cards and the outgoing ghosts beneath them. */
  const decorate = useCallback(
    <N extends Node>(list: N[]): N[] => {
      if (!morph) return list;
      const out = list.map((node) => {
        const from = morph.plan.from.get(node.id);
        if (!from) return node;
        const { className, style } = morphFromStyle(from);
        return {
          ...node,
          className: `${node.className ?? ""} ${className}`.trim(),
          style: { ...node.style, ...style },
        };
      });
      if (!morph.plan.ghosts.length) return out;
      const byId = new Map(fullNodes.map((node) => [node.id, node]));
      const ghosts = morph.plan.ghosts.flatMap((ghost) => {
        const node = byId.get(ghost.id);
        if (!node) return [];
        return [
          {
            ...node,
            id: `morph-ghost:${ghost.id}`,
            className: ghost.shrink
              ? "morph-ghost morph-shrink"
              : "morph-ghost",
            style: {
              ...node.style,
              "--morph-x": `${ghost.x}px`,
              "--morph-y": `${ghost.y}px`,
            },
            ariaLabel: undefined,
            selectable: false,
            draggable: false,
            focusable: false,
          } as unknown as N,
        ];
      });
      return [...ghosts, ...out];
    },
    [morph, fullNodes],
  );

  return {
    /** Camera and cards the board opens from, after a replay. */
    handoff,
    morphing: morph !== null,
    morphingRef,
    start,
    decorate,
    begin,
    fitStory,
    className: morph
      ? ` story-morphing morph-to-${morph.to}${morph.held ? " morph-hold" : ""}`
      : "",
    style: { "--morph-ms": `${MORPH_MS}ms` } as Record<string, string>,
  };
}
