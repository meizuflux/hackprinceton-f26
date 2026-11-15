import {
  ArrowRight,
  ArrowUpRight,
  FolderOpen,
  Plus,
  Search,
  X,
} from "lucide-react";
import { useState } from "react";
import type { CaseData } from "../api/types";
import { BrandMark } from "../components/BrandMark";
import "./onboarding.css";

export { LandingPage as Landing } from "./LandingPage";

type Navigate = (path: string) => void;

export interface SessionProject {
  caseId: string;
  name: string;
}

export function ProjectManager({
  data,
  projects,
  persistent = false,
  navigate,
  onDemo,
  opening,
  error,
}: {
  data?: CaseData;
  projects: SessionProject[];
  /** True when cases come from the backend rather than session state. */
  persistent?: boolean;
  navigate: Navigate;
  onDemo: () => void;
  opening: boolean;
  error: string;
}) {
  const [search, setSearch] = useState("");
  const matching = projects.filter((project) =>
    project.name.toLowerCase().includes(search.toLowerCase()),
  );
  const hasFictionalCase =
    data && projects.some((project) => project.caseId === data.id);

  return (
    <div className="onboarding project-page">
      <header className="onboarding-nav">
        <a
          className="onboarding-brand"
          href="/"
          onClick={(event) => {
            event.preventDefault();
            navigate("/");
          }}
        >
          <BrandMark size={20} />
          MapleTrace
        </a>
      </header>

      <main className="onboarding-main project-main">
        <div className="project-heading">
          <div>
            <h1>Projects</h1>
            <p>
              {persistent
                ? "Cases analysed by the case service."
                : "Projects are kept for this session."}
            </p>
          </div>
          <button
            className="button button-primary"
            onClick={() => navigate("/projects/new")}
          >
            <Plus size={17} aria-hidden="true" /> New project
          </button>
        </div>

        <div className="project-toolbar">
          <h2>
            Your projects <span>{projects.length}</span>
          </h2>
          <label className="project-search">
            <Search size={16} aria-hidden="true" />
            <input
              aria-label="Search projects"
              placeholder="Search projects"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            {search && (
              <button
                type="button"
                className="icon-button"
                aria-label="Clear project search"
                onClick={() => setSearch("")}
              >
                <X size={14} aria-hidden="true" />
              </button>
            )}
          </label>
        </div>

        {matching.length > 0 ? (
          <div className="project-list">
            {matching.map((project) => (
              <button
                className="project-card"
                key={project.caseId}
                onClick={() =>
                  navigate(`/cases/${encodeURIComponent(project.caseId)}`)
                }
              >
                <span className="project-card-icon">
                  <FolderOpen size={20} aria-hidden="true" />
                </span>
                <span className="project-card-content">
                  <span className="project-card-title">{project.name}</span>
                  <span className="project-card-detail">
                    {data?.id === project.caseId
                      ? `${data.sources.length} sources · ${data.nodes.length} evidence pins`
                      : persistent
                        ? "Analysed case"
                        : "Session project"}
                  </span>
                </span>
                <span className="project-card-kind">
                  {persistent
                    ? "Case"
                    : data?.id === project.caseId
                      ? "Fictional data"
                      : "Session project"}
                </span>
                <ArrowUpRight size={17} aria-hidden="true" />
              </button>
            ))}
          </div>
        ) : projects.length > 0 ? (
          <p className="project-no-results">No projects match “{search}”.</p>
        ) : (
          <section className="project-empty">
            <h2>No projects yet</h2>
            <p>
              {persistent
                ? "Select New project to upload a ZIP of case evidence."
                : "Select New project to choose a ZIP, or open the fictional case below."}
            </p>
          </section>
        )}

        {!persistent && !hasFictionalCase && data && (
          <section className="fictional-case">
            <div>
              <h2>{data.title}</h2>
              <p>
                Fictional case · source-linked records, open questions, and an
                audit trail.
              </p>
            </div>
            <button
              className="button button-secondary"
              disabled={opening}
              onClick={onDemo}
            >
              {opening ? "Opening case…" : "Open case"}
              {!opening && <ArrowRight size={16} aria-hidden="true" />}
            </button>
          </section>
        )}

        {error && (
          <p role="alert" className="error-message">
            {error}
          </p>
        )}
      </main>
    </div>
  );
}
