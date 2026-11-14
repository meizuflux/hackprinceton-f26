import {
  ArrowRight,
  ArrowUpRight,
  FileText,
  Fingerprint,
  FolderOpen,
  Plus,
  Search,
  X,
} from "lucide-react";
import { useState } from "react";
import type { CaseData } from "../api/types";
import "./onboarding.css";

type Navigate = (path: string) => void;

export function Landing({ navigate }: { navigate: Navigate }) {
  return (
    <div className="onboarding landing-page">
      <header className="onboarding-nav">
        <a
          className="onboarding-brand"
          href="/"
          onClick={(event) => {
            event.preventDefault();
            navigate("/");
          }}
        >
          <Fingerprint size={25} aria-hidden="true" />
          mapletrace
        </a>
        <button
          className="button button-primary"
          onClick={() => navigate("/projects")}
        >
          Open projects <ArrowRight size={16} aria-hidden="true" />
        </button>
      </header>

      <main className="onboarding-main landing-main">
        <section className="landing-hero">
          <div className="landing-copy">
            <h1>Evidence, connected.</h1>
            <p>
              Inspect records, trace connections to their original sources, and
              review what evidence may still be missing.
            </p>
            <button
              className="button button-primary"
              onClick={() => navigate("/projects")}
            >
              Open projects <ArrowRight size={17} aria-hidden="true" />
            </button>
          </div>

          <article
            className="source-preview"
            aria-label="Source excerpt preview"
          >
            <header className="source-preview-header">
              <span>
                <FileText size={15} aria-hidden="true" /> Source excerpt
              </span>
              <span className="source-preview-ref">S03</span>
            </header>
            <div className="source-preview-paper">
              <div className="source-paper-meta">CAMERA EXPORT NOTES</div>
              <blockquote>
                “Export has no frames from 20:31 to 20:50. Recorder health and
                source footage not included in this packet.”
              </blockquote>
              <div className="source-paper-citation">
                <span>Original source</span>
                <span>video/CAM-4E-export-notes.txt</span>
              </div>
            </div>
            <div className="source-preview-link">
              <span className="source-link-point" aria-hidden="true" />
              <div>
                <strong>Recording gap</strong>
                <span>Question to review · linked to S03</span>
              </div>
            </div>
          </article>
        </section>
      </main>
    </div>
  );
}

export interface SessionProject {
  caseId: string;
  name: string;
}

export function ProjectManager({
  data,
  projects,
  navigate,
  onDemo,
  opening,
  error,
}: {
  data?: CaseData;
  projects: SessionProject[];
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
          <Fingerprint size={25} aria-hidden="true" />
          mapletrace
        </a>
      </header>

      <main className="onboarding-main project-main">
        <div className="project-heading">
          <div>
            <h1>Projects</h1>
            <p>Projects are kept for this session.</p>
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
                      : "Session project"}
                  </span>
                </span>
                <span className="project-card-kind">
                  {data?.id === project.caseId
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
              Select New project to choose a ZIP, or open the fictional case
              below.
            </p>
          </section>
        )}

        {!hasFictionalCase && data && (
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
