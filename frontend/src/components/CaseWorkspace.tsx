import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  Files,
  FolderOpen,
  GitBranch,
  Lightbulb,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
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
  onFocusOnBoard,
  children,
}: {
  data: CaseData;
  projectName?: string;
  view: WorkspaceView;
  sourceId?: string;
  navigate: (path: string) => void;
  onFocusOnBoard?: (selection: Selection) => void;
  children: ReactNode;
}) {
  const [selection, setSelection] = useState<Selection | null>(null);
  const [toolbarExpanded, setToolbarExpanded] = useState(false);
  const toolbarToggle = useRef<HTMLButtonElement>(null);
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
      <aside
        className="case-toolbar"
        data-expanded={toolbarExpanded}
        aria-label="Workspace toolbar"
        onKeyDown={(event) => {
          if (event.key === "Escape" && toolbarExpanded) {
            event.preventDefault();
            setToolbarExpanded(false);
            toolbarToggle.current?.focus();
          }
        }}
      >
        <div className="case-toolbar-header">
          <button
            ref={toolbarToggle}
            className="case-toolbar-toggle"
            type="button"
            aria-label={
              toolbarExpanded
                ? "Collapse workspace toolbar"
                : "Expand workspace toolbar"
            }
            title={toolbarExpanded ? "Collapse toolbar" : "Expand toolbar"}
            aria-expanded={toolbarExpanded}
            aria-controls="case-toolbar-content"
            onClick={() => setToolbarExpanded((expanded) => !expanded)}
          >
            {toolbarExpanded ? (
              <PanelLeftClose size={16} />
            ) : (
              <PanelLeftOpen size={16} />
            )}
          </button>
          <span
            className="case-toolbar-caption"
            hidden={!toolbarExpanded}
            title={projectName || data.title}
          >
            Workspace
          </span>
        </div>
        <div id="case-toolbar-content" className="case-toolbar-content">
          <nav className="case-toolbar-sections" aria-label="Case sections">
            {views.map(({ id, label, icon: Icon }) => (
              <a
                key={id}
                href={casePath(data.id, id)}
                aria-current={view === id ? "page" : undefined}
                aria-label={label}
                title={!toolbarExpanded ? label : undefined}
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
                  if (window.matchMedia("(max-width: 640px)").matches)
                    setToolbarExpanded(false);
                }}
              >
                <Icon size={16} aria-hidden="true" />
                <span hidden={!toolbarExpanded}>{label}</span>
              </a>
            ))}
          </nav>
          <nav
            className="case-toolbar-project-actions"
            aria-label="Project navigation"
          >
            {[
              { label: "All projects", path: "/projects", icon: FolderOpen },
              { label: "New project", path: "/projects/new", icon: Plus },
            ].map(({ label, path, icon: Icon }) => (
              <a
                key={path}
                href={path}
                aria-label={label}
                title={!toolbarExpanded ? label : undefined}
                onClick={(event) => {
                  if (
                    event.metaKey ||
                    event.ctrlKey ||
                    event.shiftKey ||
                    event.altKey
                  )
                    return;
                  event.preventDefault();
                  navigate(path);
                }}
              >
                <Icon size={16} aria-hidden="true" />
                <span hidden={!toolbarExpanded}>{label}</span>
              </a>
            ))}
          </nav>
        </div>
      </aside>
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
            onFocusOnBoard={onFocusOnBoard}
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
              onFocusOnBoard={onFocusOnBoard}
              backLabel={`Back to ${views.find((item) => item.id === view)?.label.toLowerCase()}`}
            />
          </aside>
        )}
      </div>
    </div>
  );
}
