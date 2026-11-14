import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  Files,
  GitBranch,
  Lightbulb,
  MessageSquare,
  ScanText,
} from "lucide-react";
import type { CaseData } from "../api/types";
import { casePath, type WorkspaceView } from "../routing";
import { EvidenceBrowser } from "./EvidenceBrowser";
import { InsightsPage } from "./InsightsPage";
import { ChatPanel } from "./ChatPanel";
import { Inspector, type Selection } from "./Inspector";
import "./case-workspace.css";

const views = [
  { id: "board", label: "Mind map", icon: GitBranch },
  { id: "evidence", label: "Raw evidence", icon: ScanText },
  { id: "files", label: "Generalized files", icon: Files },
  { id: "insights", label: "Insights", icon: Lightbulb },
  { id: "chat", label: "Chat", icon: MessageSquare },
] as const;

export function CaseWorkspace({
  data,
  projectName,
  view,
  sourceId,
  navigate,
  children,
}: {
  data: CaseData;
  projectName?: string;
  view: WorkspaceView;
  sourceId?: string;
  navigate: (path: string) => void;
  children: ReactNode;
}) {
  const [selection, setSelection] = useState<Selection | null>(null);
  // React Flow needs a visible container for its initial fit. Retain it after
  // the first visit so later section changes preserve pan, zoom and selection.
  const [boardVisited, setBoardVisited] = useState(view === "board");
  useEffect(() => {
    if (view === "board") setBoardVisited(true);
  }, [view]);
  const opener = useRef<HTMLElement | null>(null);
  const inspectorDock = useRef<HTMLElement | null>(null);
  useEffect(() => setSelection(null), [view, sourceId]);
  useEffect(() => {
    if (selection && window.matchMedia("(max-width: 900px)").matches) {
      inspectorDock.current?.scrollIntoView({ block: "start" });
    }
  }, [selection]);
  const inspect = (next: Selection) => {
    opener.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    setSelection(next);
  };
  const closeInspector = () => {
    setSelection(null);
    requestAnimationFrame(
      () => opener.current?.isConnected && opener.current.focus(),
    );
  };
  const openSource = (id: string) =>
    navigate(casePath(data.id, "evidence", id));
  return (
    <div className="case-workspace">
      <header className="case-navigation">
        <nav aria-label="Case sections">
          {views.map(({ id, label, icon: Icon }) => (
            <a
              key={id}
              href={casePath(data.id, id)}
              aria-current={view === id ? "page" : undefined}
              onClick={(event) => {
                if (
                  event.metaKey ||
                  event.ctrlKey ||
                  event.shiftKey ||
                  event.altKey
                )
                  return;
                event.preventDefault();
                navigate(casePath(data.id, id));
              }}
            >
              <Icon size={15} aria-hidden="true" />
              <span>{label}</span>
            </a>
          ))}
        </nav>
        <span
          className="case-navigation-name"
          title={projectName || data.title}
        >
          {projectName || data.title}
        </span>
      </header>
      <div className="case-panels">
        <section
          className="case-board-panel"
          aria-label="Mind map"
          hidden={view !== "board"}
        >
          {(view === "board" || boardVisited) && children}
        </section>
        <section
          className="case-content-panel"
          aria-label="Raw evidence"
          hidden={view !== "evidence"}
        >
          <EvidenceBrowser
            data={data}
            mode="raw"
            selectedSourceId={sourceId}
            onInspect={openSource}
          />
        </section>
        <section
          className="case-content-panel"
          aria-label="Generalized files"
          hidden={view !== "files"}
        >
          <EvidenceBrowser
            data={data}
            mode="generalized"
            generalizedRecords={data.normalizedRecords}
            onInspect={(id) => inspect({ kind: "source", id })}
          />
        </section>
        <section
          className="case-content-panel"
          aria-label="Insights"
          hidden={view !== "insights"}
        >
          <InsightsPage
            data={data}
            onInspect={inspect}
            onOpenSource={openSource}
          />
        </section>
        <section
          className="case-content-panel"
          aria-label="Chat"
          hidden={view !== "chat"}
        >
          <ChatPanel
            caseId={data.id}
            onOpenSource={openSource}
            sourceIds={data.sources.map((source) => source.id)}
          />
        </section>
        {view !== "board" && selection && (
          <aside
            ref={inspectorDock}
            className="review-dock is-open section-inspector"
            aria-label="Source review"
          >
            <Inspector
              data={data}
              selection={selection}
              onSelect={setSelection}
              onClose={closeInspector}
              onOpenSource={openSource}
              backLabel={`Back to ${views.find((item) => item.id === view)?.label.toLowerCase()}`}
            />
          </aside>
        )}
      </div>
    </div>
  );
}
