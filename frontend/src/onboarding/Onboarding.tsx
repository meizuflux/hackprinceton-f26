import { useRef, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Fingerprint,
  FolderOpen,
  GitBranch,
  Plus,
  Search,
  ShieldCheck,
  X,
  FileText,
  Target,
  Copy,
  Check,
} from "lucide-react";
import type { CaseData } from "../api/types";
import "./onboarding.css";

type Navigate = (path: string) => void;
export function Landing({ navigate }: { navigate: Navigate }) {
  const sales = useRef<HTMLDialogElement>(null);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const [enquiry, setEnquiry] = useState(
    "Hi Compstat team, I’d like to discuss evidence review for our team.\n\nOur workflow:\nTeam size:\nBest way to reach me:",
  );
  return (
    <div className="onboarding landing-page">
      <header className="onboarding-nav">
        <a
          className="onboarding-brand"
          href="/"
          onClick={(e) => {
            e.preventDefault();
            navigate("/");
          }}
        >
          <Fingerprint size={28} />
          compstat<span className="onboarding-prototype">PROTOTYPE</span>
        </a>
        <nav aria-label="Website navigation">
          <a href="#how-it-works">How it works</a>
          <button
            className="onboarding-text"
            onClick={() => sales.current?.showModal()}
          >
            Contact sales <ArrowUpRight size={14} />
          </button>
          <button
            className="onboarding-button primary"
            onClick={() => navigate("/projects")}
          >
            Open app <ArrowRight size={16} />
          </button>
        </nav>
      </header>
      <main className="onboarding-main">
        <section className="landing-hero">
          <div className="landing-copy">
            <span className="onboarding-eyebrow">
              <span /> A CLEARER CHAIN OF EVIDENCE
            </span>
            <h1>
              See the story.
              <br />
              <em>Keep the proof.</em>
            </h1>
            <p>
              Scattered files. Unanswered questions. Bring the pieces together
              in one evidence workspace, with a path back to every source.
            </p>
            <div className="landing-actions">
              <button
                className="onboarding-button primary"
                onClick={() => navigate("/projects")}
              >
                Start a project <ArrowRight size={17} />
              </button>
              <a className="onboarding-button secondary" href="#how-it-works">
                See how it works <span aria-hidden="true">↓</span>
              </a>
            </div>
            <span className="landing-disclosure">
              <ShieldCheck size={15} /> Explore with fictional case files. No
              account needed.
            </span>
          </div>
          <div
            className="landing-preview"
            aria-label="Illustration of a source-linked evidence board"
          >
            <div className="landing-preview-top">
              <span>
                <span className="onboarding-status-dot" /> EVIDENCE WORKSPACE
              </span>
              <span>FICTIONAL PREVIEW</span>
            </div>
            <div className="landing-cork">
              <svg
                className="landing-threads"
                viewBox="0 0 520 410"
                preserveAspectRatio="none"
                aria-hidden="true"
              >
                <path d="M145 120 C260 110 290 230 390 280 M145 120 C140 250 190 280 230 310" />
              </svg>
              <article className="landing-pin person">
                <span className="landing-pushpin" />
                <span className="pin-label">
                  <Fingerprint size={13} /> PERSON
                </span>
                <div className="landing-monogram">AM</div>
                <h3>Alex Morgan</h3>
                <p>Inventory lead</p>
                <footer>
                  <FileText size={12} /> 2 linked sources
                </footer>
              </article>
              <article className="landing-pin question">
                <span className="landing-pushpin" />
                <span className="pin-label">OPEN QUESTION</span>
                <h3>
                  19 minutes.
                  <br />
                  What’s missing?
                </h3>
                <p>
                  A gap in camera coverage.
                  <br />A lead to verify, not proof.
                </p>
                <footer>
                  <Target size={12} /> Review the source{" "}
                  <ArrowUpRight size={12} />
                </footer>
              </article>
              <article className="landing-pin source">
                <span className="landing-pushpin" />
                <span className="pin-label">
                  <FileText size={12} /> ORIGINAL SOURCE
                </span>
                <h3>CAM-4E-notes.txt</h3>
                <p>
                  “Export has no frames from
                  <br />
                  20:31 to 20:50.”
                </p>
                <footer>Fictional source excerpt</footer>
              </article>
            </div>
            <div className="landing-preview-bottom">
              <GitBranch size={14} /> Every connection starts with a source.
            </div>
          </div>
        </section>
        <section id="how-it-works" className="landing-process">
          <div className="landing-section-label">
            <span className="onboarding-eyebrow">FROM FILES TO FOLLOW-UP</span>
            <h2>A place for the whole picture.</h2>
          </div>
          <div className="landing-process-grid">
            {[
              {
                icon: FolderOpen,
                title: "Start with a project",
                text: "Give your review a home. Select a ZIP or follow a guided example.",
              },
              {
                icon: GitBranch,
                title: "Follow the connections",
                text: "Explore an interactive board of people, events, and records. Inspect the sources behind each link.",
              },
              {
                icon: Search,
                title: "Know what to ask next",
                text: "Review open questions and suggested evidence. Keep observations separate from inference.",
              },
            ].map((step, i) => (
              <article key={step.title}>
                <div>
                  <step.icon size={21} />
                  <span>0{i + 1}</span>
                </div>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </article>
            ))}
          </div>
          <p className="landing-prototype-note">
            Current prototype: ZIP processing is simulated. Archives are never
            read or uploaded; analysis uses temporary fictional data.
          </p>
        </section>
      </main>
      <footer className="onboarding-footer">
        <span>
          compstat <span>/</span> Clarity from complexity.
        </span>
        <span>Hackathon prototype · Synthetic data only</span>
      </footer>
      <dialog
        className="sales-dialog"
        aria-labelledby="sales-title"
        ref={sales}
        onClose={() => {
          setCopied(false);
          setCopyError(false);
        }}
      >
        <button
          className="sales-close"
          aria-label="Close sales enquiry"
          onClick={() => sales.current?.close()}
        >
          <X size={20} />
        </button>
        <span className="onboarding-eyebrow">CONTACT SALES</span>
        <h2 id="sales-title">Let’s talk about your workflow.</h2>
        <p>
          Compstat is an early prototype. Prepare an enquiry to share with the
          team; this form doesn’t send a message.
        </p>
        <label htmlFor="sales-enquiry">Your enquiry</label>
        <textarea
          id="sales-enquiry"
          value={enquiry}
          onChange={(e) => {
            setEnquiry(e.target.value);
            setCopied(false);
          }}
        />
        <button
          className="onboarding-button primary"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(enquiry);
              setCopied(true);
              setCopyError(false);
            } catch {
              setCopyError(true);
            }
          }}
        >
          {copied ? <Check size={16} /> : <Copy size={16} />}{" "}
          {copied ? "Enquiry copied" : "Copy enquiry"}
        </button>
        <p aria-live="polite">
          {copyError
            ? "Select the enquiry above and copy it to share with the team."
            : copied
              ? "Ready to share with your Compstat contact."
              : ""}
        </p>
      </dialog>
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
  const matching = projects.filter((p) =>
    p.name.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <div className="onboarding project-page">
      <header className="onboarding-nav">
        <a
          className="onboarding-brand"
          href="/"
          onClick={(e) => {
            e.preventDefault();
            navigate("/");
          }}
        >
          <Fingerprint size={26} />
          compstat
        </a>
        <div className="project-session">
          <span className="onboarding-status-dot" /> Local session
        </div>
      </header>
      <main className="onboarding-main project-main">
        <div className="project-breadcrumb">
          WORKSPACE <span>/</span> PROJECT MANAGER
        </div>
        <div className="project-heading">
          <div>
            <h1>Your projects</h1>
            <p>
              A home for your evidence. A starting point for your next question.
            </p>
          </div>
          <button
            className="onboarding-button primary"
            onClick={() => navigate("/projects/new")}
          >
            <Plus size={17} /> New project
          </button>
        </div>
        <div className="project-toolbar">
          <h2>
            Projects <span>{projects.length}</span>
          </h2>
          <label>
            <Search size={16} />
            <input
              aria-label="Search projects"
              placeholder="Search projects…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
        </div>
        {projects.length === 0 ? (
          <section className="project-empty">
            <div className="project-folder">
              <FolderOpen size={36} strokeWidth={1} />
            </div>
            <span className="onboarding-eyebrow">
              ROOM FOR YOUR NEXT INVESTIGATION
            </span>
            <h2>Every case starts somewhere.</h2>
            <p>
              Create a project to try the ZIP workflow, or explore the evidence
              board with our fictional case files.
            </p>
            <button
              className="onboarding-button primary"
              onClick={() => navigate("/projects/new")}
            >
              <Plus size={17} /> Add a new project
            </button>
            <span className="project-local-note">
              Projects stay in this session. Refreshing clears the project list.
            </span>
          </section>
        ) : (
          <div className="project-grid">
            {matching.map((project) => (
              <button
                className="project-card"
                key={project.caseId}
                onClick={() =>
                  navigate(`/cases/${encodeURIComponent(project.caseId)}`)
                }
              >
                <FolderOpen size={27} />
                <span className="project-card-status">FICTIONAL CASE</span>
                <h3>{project.name}</h3>
                <p>
                  {data
                    ? `${data.sources.length} sources · ${data.nodes.length} evidence pins`
                    : "Source-linked evidence workspace"}
                </p>
                <footer>
                  Open evidence board <ArrowUpRight size={17} />
                </footer>
              </button>
            ))}
            {!matching.length && (
              <p className="project-no-results">
                No projects match “{search}”.
              </p>
            )}
          </div>
        )}
        <section className="project-demo">
          <div className="project-demo-icon">
            <GitBranch size={26} />
          </div>
          <div>
            <span className="onboarding-eyebrow">TAKE A LOOK AROUND</span>
            <h2>No files? Follow the evidence.</h2>
            <p>
              Explore the example case files: a fictional inventory case with
              linked sources, open questions, and a review trail.
            </p>
          </div>
          <button
            className="onboarding-button secondary"
            disabled={opening}
            onClick={onDemo}
          >
            {opening ? "Opening case files…" : "Open example case"}
            <ArrowRight size={16} />
          </button>
        </section>
        {error && (
          <p role="alert" className="error-message">
            {error}
          </p>
        )}
        <p className="project-local-note">
          Prototype workspace · No account, cloud storage, or real evidence
          analysis.
        </p>
      </main>
      <footer className="onboarding-footer">
        <a
          href="/"
          onClick={(e) => {
            e.preventDefault();
            navigate("/");
          }}
        >
          ← Back to Compstat
        </a>
        <span>Synthetic data only</span>
      </footer>
    </div>
  );
}
