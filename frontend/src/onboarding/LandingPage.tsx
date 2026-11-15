import { ArrowRight, Lock } from "lucide-react";
import { api } from "../api/client";
import type { CaseData } from "../api/types";
import { BrandMark } from "../components/BrandMark";
import { UPLOADS_ENABLED, UPLOADS_OFF_REASON } from "../config";
import "./landing-page.css";

type Navigate = (path: string) => void;

interface LandingPageProps {
  navigate: Navigate;
  onDemo?: () => void;
  opening?: boolean;
  caseData?: CaseData;
}

/*
 * Every example on this page is quoted from the fictional Kestrel case in cases/kestrel/evidence,
 * with the citation the backend gives it in the committed demo snapshot (backend/demo/kestrel.tar.gz):
 * the hero is contradiction X-01, the side-by-side example is X-02 with its listed possible reasons,
 * and the evidence counts come from that run's ingest summary. They are illustrations for the page,
 * not data the workspace reads.
 */

const PIPELINE_STEPS = [
  {
    title: "Hash and parse every file",
    body: "Each file is hashed with SHA-256 and checked against the case manifest before it is read. Working copies are read-only. Every row, line or page becomes a record that remembers where it came from.",
    detail: "56 of 56 manifest hashes match",
  },
  {
    title: "Put every time on one clock",
    body: "Times are converted to UTC with an uncertainty window. When a file has no time zone, the assumed one is flagged. Times people give in statements stay marked as asserted, not recorded.",
    detail: "EV-070 · local time, no offset → flagged",
  },
  {
    title: "Flag patterns with rules and classical ML",
    body: "Rules find conflicting records, missing periods and gaps in coverage. Clustering and outlier models add leads, such as a day that breaks someone's routine. Model leads never change the findings.",
    detail: "DBSCAN · Isolation Forest · TF-IDF",
  },
  {
    title: "An AI agent proposes cited insights",
    body: "An agent reads the records through search tools and suggests connections. Each suggestion must cite records that exist, and it is shown as an inference, apart from what the records show.",
    detail: "uncited insights are rejected",
  },
  {
    title: "Everything links back to the source",
    body: "Every card, thread, gap and insight opens the original file at the cited row or line. Each step is written to a hash-chained audit log that can be verified afterwards.",
    detail: "EV-075 row 72 → ws_exec0001.csv, line 72",
  },
];

const POSSIBLE_REASONS = [
  "A credential, account or device was used by someone other than its owner.",
  "The two places are closer than they look (adjacent rooms or a remote session).",
  "One of the systems has a clock offset.",
  "Some record times have no time zone and were read as America/Los_Angeles; a wrong assumption would shift them by hours.",
];

const EVIDENCE_TYPES = [
  { type: "Carrier call records", files: 2, records: "2,216" },
  { type: "System and access logs", files: 12, records: "2,145" },
  { type: "Phone location history", files: 1, records: "509" },
  { type: "Calendar", files: 1, records: "224" },
  { type: "Messages", files: 2, records: "208" },
  { type: "Written statements", files: 9, records: "175" },
  { type: "Interview transcripts", files: 3, records: "63" },
  { type: "DNA lab results", files: 2, records: "54" },
  { type: "Reports and notes", files: 4, records: "16" },
  { type: "Photos", files: 11, records: "11" },
  { type: "Email", files: 5, records: "5" },
  { type: "CCTV clips", files: 4, records: "4" },
];

export function LandingPage({
  navigate,
  onDemo,
  opening,
  caseData,
}: LandingPageProps) {
  const demoButtonLabel = opening
    ? "Opening case…"
    : caseData?.title
      ? `Explore ${caseData.title}`
      : "Explore the demo case";

  function handleOpenCase() {
    if (onDemo) {
      onDemo();
    } else {
      navigate("/projects");
    }
  }

  return (
    <div className="landing-viewport">
      <header className="landing-nav">
        <div className="landing-nav-inner">
          <a
            className="landing-brand"
            href="/"
            onClick={(e) => {
              e.preventDefault();
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
          >
            <BrandMark size={20} />
            <span className="landing-brand-text">MapleTrace</span>
          </a>

          <nav className="landing-links" aria-label="Page sections">
            <a href="#pipeline" className="landing-link">
              How it works
            </a>
            <a href="#contradiction" className="landing-link">
              Contradictions
            </a>
            <a href="#evidence" className="landing-link">
              Evidence
            </a>
            <a href="#kestrel" className="landing-link">
              Kestrel case
            </a>
          </nav>

          <div className="landing-nav-actions">
            <button
              type="button"
              className="button button-primary landing-nav-btn"
              onClick={handleOpenCase}
              disabled={opening}
            >
              {opening ? "Opening case…" : "Explore demo"}
              <ArrowRight size={15} aria-hidden="true" />
            </button>
          </div>
        </div>
      </header>

      <main className="landing-main">
        <section className="landing-hero-section">
          <div className="landing-hero-container">
            <div className="landing-hero-copy">
              <h1 className="landing-hero-title">
                <span className="hero-line">Evidence, connected.</span>{" "}
                <span className="hero-line">Reasoning, defensible.</span>
              </h1>
              <p className="landing-hero-lead">
                MapleTrace turns a case archive of logs, phone extractions,
                photos, CCTV and statements into an evidence board. Every card
                and thread opens the file and line it came from, and where a
                statement and a record disagree, the board shows you both.
              </p>

              <div className="landing-hero-ctas">
                <button
                  type="button"
                  className="button button-primary hero-btn-primary"
                  onClick={handleOpenCase}
                  disabled={opening}
                >
                  {demoButtonLabel}
                  <ArrowRight size={17} aria-hidden="true" />
                </button>
                <UploadButton
                  className="hero-btn-secondary"
                  noteId="hero-upload-note"
                  onUpload={() => navigate("/projects/new")}
                />
              </div>
              {!UPLOADS_ENABLED && (
                <p className="landing-hero-note" id="hero-upload-note">
                  <Lock size={13} aria-hidden="true" />
                  {UPLOADS_OFF_REASON} The demo opens a fictional case.
                </p>
              )}
            </div>

            <figure className="hero-pinboard-showcase">
              <div
                className="micro-pinboard-canvas"
                role="img"
                aria-label="Two pinned cards joined by a red contradiction thread: Richard Halvorsen's interview statement and a badge record"
              >
                <svg
                  className="micro-pinboard-svg"
                  viewBox="0 0 540 230"
                  preserveAspectRatio="none"
                  aria-hidden="true"
                >
                  <path
                    d="M 170 115 C 230 50, 310 180, 370 115"
                    className="micro-thread-path"
                  />
                </svg>

                <div className="micro-card card-a statement">
                  <span className="micro-pushpin" aria-hidden="true" />
                  <span className="micro-card-type">Statement</span>
                  <span className="micro-card-title">Richard Halvorsen</span>
                  <span className="micro-card-note">
                    “At home. A quiet night. My wife and I watched something and
                    I went to bed early.”
                  </span>
                  <span className="micro-card-footer">
                    <span>EV-090 · line 14</span>
                    <span className="micro-reliability asserted">Asserted</span>
                  </span>
                </div>

                <span className="micro-thread-label">Contradiction</span>

                <div className="micro-card card-b event">
                  <span className="micro-pushpin" aria-hidden="true" />
                  <span className="micro-card-type">Event</span>
                  <span className="micro-card-title">Badge BID-100001</span>
                  <span className="micro-card-note">
                    Access granted at the P2 garage elevator lobby door, Sat 17
                    Oct, 21:36.
                  </span>
                  <span className="micro-card-footer">
                    <span>EV-070 · BDG-000614</span>
                    <span className="micro-reliability recorded">Recorded</span>
                  </span>
                </div>
              </div>

              <figcaption className="micro-sources">
                <span className="micro-sources-title">Cited sources</span>
                <dl className="micro-source-list">
                  <div>
                    <dt>EV-090:line=14</dt>
                    <dd>
                      [0014] HALVORSEN: At home. A quiet night. My wife and I
                      watched something and I went to bed early.
                    </dd>
                  </div>
                  <div>
                    <dt>EV-070:event_id=BDG-000614</dt>
                    <dd>
                      BDG-000614,2026-10-17 21:36:31,E-P2-ELEV,P2 garage
                      elevator lobby door,BID-100001,"HALVORSEN,
                      RICHARD",ACCESS_GRANTED
                    </dd>
                  </div>
                </dl>
                <p className="micro-sources-note">
                  A badge record shows the card was used, not who held it. The
                  board raises this as a question to check, not as proof.
                </p>
              </figcaption>
            </figure>
          </div>
        </section>

        <section className="landing-section" id="pipeline">
          <div className="landing-section-header">
            <h2 className="landing-section-title">
              What happens to a case archive
            </h2>
            <p className="landing-section-desc">
              Five steps, in this order. Each one is written to the audit log.
            </p>
            {api.mode === "mock" && (
              <p className="landing-mock-note">
                This build uses the mock adapter: it shows fictional data and
                does not run these steps.
              </p>
            )}
          </div>

          <ol className="pipeline-steps">
            {PIPELINE_STEPS.map((step, index) => (
              <li key={step.title} className="pipeline-step">
                <span className="pipeline-step-num" aria-hidden="true">
                  {index + 1}
                </span>
                <h3 className="pipeline-step-title">{step.title}</h3>
                <p className="pipeline-step-body">{step.body}</p>
                <span className="pipeline-step-detail">{step.detail}</span>
              </li>
            ))}
          </ol>
        </section>

        <section className="landing-section" id="contradiction">
          <div className="landing-section-header">
            <h2 className="landing-section-title">When two records disagree</h2>
            <p className="landing-section-desc">
              MapleTrace puts both records side by side with their sources,
              lists what could explain the conflict, and leaves the conclusion
              to you.
            </p>
          </div>

          <div className="dispute">
            <div className="dispute-records">
              <article className="dispute-record">
                <p className="dispute-cite">
                  <span>EV-075 · row 72</span>
                  <span className="dispute-kind">Recorded</span>
                </p>
                <p className="dispute-time">
                  22:50:30 <span>PDT · Sat 17 Oct</span>
                </p>
                <h3>Keyboard or mouse activity on workstation AUR-EXEC-0001</h3>
                <p className="dispute-meta">
                  Account AURION\rhalvorsen. The file stores UTC (05:50:30Z).
                </p>
              </article>

              <div className="dispute-gap" aria-hidden="true">
                <span>17 s apart</span>
              </div>

              <article className="dispute-record">
                <p className="dispute-cite">
                  <span>EV-070 · BDG-000620</span>
                  <span className="dispute-kind">Recorded</span>
                </p>
                <p className="dispute-time">
                  22:50:47 <span>PDT · Sat 17 Oct</span>
                </p>
                <h3>
                  Halvorsen&rsquo;s badge opens the Executive Briefing Center,
                  room 4-12
                </h3>
                <p className="dispute-meta">
                  Badge BID-100001. The file stores local time with no offset,
                  so the time zone is flagged as an assumption.
                </p>
              </article>
            </div>

            <div className="dispute-reading">
              <div>
                <h3 className="dispute-subhead">Possible reasons</h3>
                <ul className="dispute-reasons">
                  {POSSIBLE_REASONS.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </div>
              <p className="dispute-note">
                <strong>Not proof.</strong> A contradiction is an open question.
                MapleTrace does not decide which record is right or say that
                anyone lied. It suggests what would settle it: CCTV, an
                access-system audit, or the workstation itself.
              </p>
            </div>
          </div>
        </section>

        <section className="landing-section" id="evidence">
          <div className="landing-section-header">
            <h2 className="landing-section-title">
              What the Kestrel archive holds
            </h2>
            <p className="landing-section-desc">
              57 files of twelve kinds, read into 5,630 records. Each file’s
              type is detected from its contents, with the file name as a hint.
            </p>
          </div>

          <table className="evidence-table">
            <caption className="landing-sr-only">
              Files and records by evidence type in the Kestrel case
            </caption>
            <thead>
              <tr>
                <th scope="col">Evidence</th>
                <th scope="col">Files</th>
                <th scope="col">Records</th>
              </tr>
            </thead>
            <tbody>
              {EVIDENCE_TYPES.map((row) => (
                <tr key={row.type}>
                  <th scope="row">{row.type}</th>
                  <td>{row.files}</td>
                  <td>{row.records}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="landing-section" id="defensibility">
          <div className="landing-section-header">
            <h2 className="landing-section-title">Built to be checked</h2>
          </div>

          <div className="principles-grid">
            <div className="principle">
              <h3>Independent sources, not repeats</h3>
              <p>
                Corroboration counts independent origins. Ten forwarded copies
                of one email count once.
              </p>
            </div>
            <div className="principle">
              <h3>An audit chain you can verify</h3>
              <p>
                Every parse, analysis step and investigator override is appended
                to a hash-chained log. A verify command confirms nothing was
                changed afterwards.
              </p>
            </div>
            <div className="principle">
              <h3>No protected attributes</h3>
              <p>
                Nationality and similar fields are never model features and
                never returned. The Kestrel case includes a deliberate bias trap
                to test this.
              </p>
            </div>
          </div>
        </section>

        <section className="landing-section case-study-section" id="kestrel">
          <div className="case-study-banner">
            <div className="case-study-content">
              <h2 className="case-study-title">The Kestrel case</h2>
              <p className="case-study-summary">
                An unreleased AX-9 “Kestrel” GPU engineering sample went missing
                from a secure cabinet in the Executive Briefing Center of Aurion
                Compute over the weekend of October 17. Every person, company
                and record in it is fictional.
              </p>

              <dl className="case-study-stats">
                <div className="stat-item">
                  <dt>Files</dt>
                  <dd>57</dd>
                </div>
                <div className="stat-item">
                  <dt>Records</dt>
                  <dd>5,630</dd>
                </div>
                <div className="stat-item">
                  <dt>Photos and clips</dt>
                  <dd>15</dd>
                </div>
              </dl>

              <div className="case-study-actions">
                <button
                  type="button"
                  className="button button-primary"
                  onClick={handleOpenCase}
                  disabled={opening}
                >
                  {opening ? "Opening case…" : "Open the Kestrel case"}
                  <ArrowRight size={16} aria-hidden="true" />
                </button>
              </div>
            </div>

            <div className="case-study-preview-box">
              <h3 className="preview-box-header">Saturday 17 October</h3>
              <ul className="case-events-timeline">
                <li>
                  <span className="event-time">21:00–23:30 · EV-024</span>
                  <p className="highlight-text">
                    Floor 4 cameras offline for scheduled maintenance
                  </p>
                </li>
                <li>
                  <span className="event-time">21:36 · EV-070</span>
                  <p>Halvorsen’s badge opens the P2 garage elevator door</p>
                </li>
                <li>
                  <span className="event-time">22:50 · EV-075, EV-070</span>
                  <p className="highlight-text">
                    His workstation is active as his badge opens room 4-12
                  </p>
                </li>
                <li>
                  <span className="event-time">22:51 · EV-001</span>
                  <p>Cabinet opened with an executive override on his badge</p>
                </li>
              </ul>
            </div>
          </div>
        </section>

        <section className="landing-bottom-cta">
          <div className="bottom-cta-container">
            <h2 className="bottom-cta-title">Open the Kestrel case</h2>
            <p className="bottom-cta-lead">
              Watch the recorded run build the board, then open any card to see
              the file and line it came from.
            </p>

            <div className="bottom-cta-buttons">
              <button
                type="button"
                className="button button-primary cta-large-btn"
                onClick={handleOpenCase}
                disabled={opening}
              >
                {demoButtonLabel}
                <ArrowRight size={17} aria-hidden="true" />
              </button>
            </div>

            <p className="synthetic-disclosure">
              Fictional case: every person, company, phone number (555-01xx),
              plate and record is made up for this prototype.
            </p>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <div className="landing-footer-inner">
          <div className="footer-brand-col">
            <div className="landing-brand">
              <BrandMark size={16} />
              <span className="landing-brand-text">MapleTrace</span>
            </div>
            <p className="footer-tagline">
              An evidence board where every card cites its source. Built at
              HackPrinceton Fall 2026.
            </p>
          </div>

          <div className="footer-links-col">
            <span className="footer-group-title">Workspace</span>
            <button
              type="button"
              className="footer-link-btn"
              onClick={handleOpenCase}
            >
              Demo case
            </button>
            <button
              type="button"
              className="footer-link-btn"
              onClick={() => navigate("/projects")}
            >
              Projects
            </button>
            {UPLOADS_ENABLED ? (
              <button
                type="button"
                className="footer-link-btn"
                onClick={() => navigate("/projects/new")}
              >
                Upload a case ZIP
              </button>
            ) : (
              <span className="footer-link-off">
                Upload a case ZIP <span>(off for the demo)</span>
              </span>
            )}
          </div>

          <div className="footer-links-col">
            <span className="footer-group-title">On the board</span>
            <span className="footer-kbd-item">
              <kbd>Two-finger swipe</kbd> Pan
            </span>
            <span className="footer-kbd-item">
              <kbd>Pinch</kbd> Zoom
            </span>
            <span className="footer-kbd-item">
              <kbd>Thread label</kbd> Open its sources
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}

/**
 * "Upload case ZIP". While uploads are off it stays visible but inert: aria-disabled keeps it
 * focusable so screen readers reach it and read the reason from the note it points to.
 */
function UploadButton({
  className,
  noteId,
  onUpload,
}: {
  className?: string;
  noteId: string;
  onUpload: () => void;
}) {
  if (UPLOADS_ENABLED)
    return (
      <button
        type="button"
        className={`button button-secondary ${className ?? ""}`}
        onClick={onUpload}
      >
        Upload case ZIP
      </button>
    );
  return (
    <button
      type="button"
      className={`button button-secondary is-off ${className ?? ""}`}
      aria-disabled="true"
      aria-describedby={noteId}
    >
      Upload case ZIP
    </button>
  );
}
