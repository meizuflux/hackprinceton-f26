import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  Files,
  FolderOpen,
  GitBranch,
  History,
  Lightbulb,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  ScanText,
} from "lucide-react";
import type { CaseData } from "../api/types";
import { casePath, type InsightsTab, type WorkspaceView } from "../routing";
import { isMock } from "../api/client";
import { EvidenceBrowser } from "./EvidenceBrowser";
import { RecordsBrowser } from "./RecordsBrowser";
import { RawEvidence } from "./RawEvidence";
import { InsightsPage } from "./InsightsPage";
import { ChatPanel } from "./ChatPanel";
import { Inspector, type Selection } from "./Inspector";
import { AnalysisEntries } from "./AnalysisEntries";
import type { Tab } from "./board-focus";
import "./case-workspace.css";

const views = [
  { id: "board", label: "Mind map", icon: GitBranch },
  { id: "insights", label: "Insights", icon: Lightbulb },
  { id: "evidence", label: "Raw evidence", icon: ScanText },
  { id: "files", label: "Generalized files", icon: Files },
  { id: "chat", label: "Chat", icon: MessageSquare },
] as const;

export function CaseWorkspace({
  data,
  projectName,
  view,
  sourceId,
  insightsTab,
  navigate,
  onFocusOnBoard,
  onOpenReview,
  children,
}: {
  data: CaseData;
  projectName?: string;
  view: WorkspaceView;
  sourceId?: string;
  insightsTab?: InsightsTab;
  navigate: (path: string) => void;
  onFocusOnBoard?: (selection: Selection) => void;
  /** Returns to the mind map with the review dock open on this panel. */
  onOpenReview?: (panel: Tab | "audit") => void;
  children: ReactNode;
}) {
  const [selection, setSelection] = useState<Selection | null>(null);
  const [toolbarExpanded, setToolbarExpanded] = useState(false);
  const toolbarToggle = useRef<HTMLButtonElement>(null);
  const workspaceRef = useRef<HTMLDivElement>(null);
  // React Flow needs a visible container for its initial fit. Retain it after
  // the first visit so later section changes preserve pan, zoom and selection.
  const [boardVisited, setBoardVisited] = useState(view === "board");
  const [filesVisited, setFilesVisited] = useState(view === "files");
  useEffect(() => {
    if (view === "files") setFilesVisited(true);
  }, [view]);
  useEffect(() => {
    if (view === "board") setBoardVisited(true);
  }, [view]);
  const opener = useRef<HTMLElement | null>(null);
  const inspectorDock = useRef<HTMLElement | null>(null);
  useEffect(() => setSelection(null), [view, sourceId, insightsTab]);
  useEffect(() => {
    if (selection && window.matchMedia("(max-width: 900px)").matches) {
      inspectorDock.current?.scrollIntoView({ block: "start" });
    }
  }, [selection]);

  useEffect(() => {
    const root = workspaceRef.current;
    if (!root) return;

    let resizeObserver: ResizeObserver | null = null;
    let observedElement: HTMLElement | null = null;

    const updateClearance = () => {
      const topbar = root.querySelector<HTMLElement>(
        ".board-toolbar, .workspace-topbar",
      );
      if (!topbar) return;
      const topbarRect = topbar.getBoundingClientRect();
      const rootRect = root.getBoundingClientRect();
      if (topbarRect.height > 0) {
        const bottomOffset = topbarRect.bottom - rootRect.top;
        const clearance = Math.round(bottomOffset + 16);
        root.style.setProperty("--topbar-clearance-y", `${clearance}px`);
        root.style.setProperty(
          "--topbar-height",
          `${Math.round(topbarRect.height)}px`,
        );
      }
    };

    const attachObserver = () => {
      const topbar = root.querySelector<HTMLElement>(
        ".board-toolbar, .workspace-topbar",
      );
      if (topbar === observedElement) return;

      if (resizeObserver && observedElement) {
        resizeObserver.unobserve(observedElement);
      }

      observedElement = topbar;
      if (topbar && typeof ResizeObserver !== "undefined") {
        if (!resizeObserver) {
          resizeObserver = new ResizeObserver(() => {
            updateClearance();
          });
        }
        resizeObserver.observe(topbar);
      }
      updateClearance();
    };

    attachObserver();

    let mutationObserver: MutationObserver | null = null;
    if (typeof MutationObserver !== "undefined") {
      mutationObserver = new MutationObserver(() => {
        attachObserver();
      });
      mutationObserver.observe(root, { childList: true, subtree: true });
    }

    window.addEventListener("resize", updateClearance);

    return () => {
      window.removeEventListener("resize", updateClearance);
      if (mutationObserver) {
        mutationObserver.disconnect();
      }
      if (resizeObserver && observedElement) {
        resizeObserver.unobserve(observedElement);
      }
    };
  }, [view, data.title, data.subtitle, projectName]);
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
    <div className="case-workspace" ref={workspaceRef}>
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
            <a
              href="/projects"
              aria-label="All projects"
              title={!toolbarExpanded ? "All projects" : undefined}
              onClick={(event) => {
                if (
                  event.metaKey ||
                  event.ctrlKey ||
                  event.shiftKey ||
                  event.altKey
                )
                  return;
                event.preventDefault();
                navigate("/projects");
              }}
            >
              <FolderOpen size={16} aria-hidden="true" />
              <span hidden={!toolbarExpanded}>All projects</span>
            </a>
          </nav>
        </div>
      </aside>
      {view !== "board" && (
        <header className="workspace-topbar">
          <div className="board-title">
            <h1>{projectName || data.title}</h1>
            <span>
              {data.subtitle} · {views.find((v) => v.id === view)?.label}
            </span>
          </div>
          <div className="board-actions">
            <button
              type="button"
              className="text-button"
              onClick={() => navigate(casePath(data.id))}
            >
              <GitBranch size={15} /> Mind map
            </button>
            <button
              type="button"
              className="text-button"
              onClick={() =>
                onOpenReview
                  ? onOpenReview("audit")
                  : navigate(casePath(data.id))
              }
            >
              <History size={15} /> Audit trail
            </button>
            <AnalysisEntries
              data={data}
              onOpen={(tab) =>
                onOpenReview ? onOpenReview(tab) : navigate(casePath(data.id))
              }
            />
          </div>
        </header>
      )}
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
          {isMock ? (
            <EvidenceBrowser
              data={data}
              mode="raw"
              selectedSourceId={sourceId}
              onInspect={openSource}
            />
          ) : (
            <RawEvidence
              data={data}
              sourceId={sourceId}
              onOpen={openSource}
              onInspectSource={(id) => inspect({ kind: "source", id })}
            />
          )}
        </section>
        <section
          className="case-content-panel"
          aria-label="Generalized files"
          hidden={view !== "files"}
        >
          {isMock ? (
            <EvidenceBrowser
              data={data}
              mode="generalized"
              generalizedRecords={data.normalizedRecords}
              onInspect={(id) => inspect({ kind: "source", id })}
            />
          ) : (
            (view === "files" || filesVisited) && (
              <RecordsBrowser
                data={data}
                onInspect={(id) => inspect({ kind: "source", id })}
                onOpenSource={openSource}
              />
            )
          )}
        </section>
        <section
          className="case-content-panel"
          aria-label="Insights"
          hidden={view !== "insights"}
        >
          <InsightsPage
            data={data}
            tab={insightsTab}
            navigate={navigate}
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
