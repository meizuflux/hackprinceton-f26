import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  Fingerprint,
  FolderOpen,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { casePath } from "../routing";
import type { SessionProject } from "../onboarding/Onboarding";

export function WorkspaceNavigation({
  navigate,
  projects,
  activeCaseId,
}: {
  navigate: (path: string) => void;
  projects: SessionProject[];
  activeCaseId?: string;
}) {
  const [open, setOpen] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        toggle.current?.focus();
      }
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [open]);
  return (
    <nav className="workspace-navigation" aria-label="Workspace navigation">
      <button
        ref={toggle}
        className="navigation-toggle icon-button"
        aria-label={open ? "Collapse sidebar" : "Expand sidebar"}
        aria-expanded={open}
        aria-controls="workspace-sidebar"
        onClick={() => setOpen(!open)}
      >
        {open ? <PanelLeftClose size={20} /> : <PanelLeftOpen size={20} />}
      </button>
      <div className="workspace-sidebar" id="workspace-sidebar" hidden={!open}>
        <a
          className="sidebar-brand"
          href="/"
          onClick={(event) => {
            event.preventDefault();
            navigate("/");
          }}
        >
          <Fingerprint size={24} /> MapleTrace
        </a>
        <button className="text-button" onClick={() => navigate("/projects")}>
          <ArrowLeft size={16} /> All projects
        </button>
        <div className="sidebar-projects" aria-label="Session projects">
          {projects.map((project) => (
            <button
              key={project.caseId}
              aria-current={
                project.caseId === activeCaseId ? "page" : undefined
              }
              onClick={() => {
                navigate(casePath(project.caseId));
                setOpen(false);
              }}
            >
              <FolderOpen size={16} />
              <span>{project.name}</span>
            </button>
          ))}
        </div>
      </div>
    </nav>
  );
}
