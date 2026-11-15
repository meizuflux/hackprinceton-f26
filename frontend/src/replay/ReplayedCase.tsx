import { useMemo, type ReactNode } from "react";
import { isMock } from "../api/client";
import type { CaseData } from "../api/types";
import { ReplayHud } from "./ReplayHud";
import { emptyCase, revealCase } from "./reveal";
import { useReplay } from "./useReplay";

export interface ReplayContext {
  /** The full case, for layout: revealed cards keep their final positions. */
  layoutData: CaseData;
  hud: ReactNode;
  /** The board is filling in as the clock advances. */
  growing: boolean;
}

/**
 * Runs the replay for a case and hands the children the case as revealed so
 * far. `data` is undefined while a live run has not produced the board yet.
 */
export function ReplayedCase({
  caseId,
  data,
  title,
  fallback,
  children,
}: {
  caseId: string;
  data: CaseData | undefined;
  title: string;
  fallback: ReactNode;
  children: (shown: CaseData, context: ReplayContext) => ReactNode;
}) {
  const replay = useReplay(caseId, !isMock);
  const base = useMemo(
    () => data ?? emptyCase(caseId, title),
    [data, caseId, title],
  );
  const shown = useMemo(
    () => (replay.filtering ? revealCase(base, replay.progress) : base),
    [base, replay.filtering, replay.progress],
  );
  if (!data && replay.mode === "none") return <>{fallback}</>;
  return (
    <>
      {children(shown, {
        layoutData: base,
        hud: replay.mode === "none" ? null : <ReplayHud replay={replay} />,
        growing: replay.filtering && !replay.finished,
      })}
    </>
  );
}
