import {
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  Camera,
  CheckCircle2,
  Clock,
  Database,
  Dna,
  FileCheck,
  FileText,
  Fingerprint,
  Lock,
  Mail,
  MapPin,
  Phone,
  Radio,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import { useState } from "react";
import type { CaseData } from "../api/types";
import "./landing-page.css";

type Navigate = (path: string) => void;

interface LandingPageProps {
  navigate: Navigate;
  onDemo?: () => void;
  opening?: boolean;
  caseData?: CaseData;
}

interface Scenario {
  id: string;
  name: string;
  label: string;
  cardA: {
    type: string;
    title: string;
    subtitle: string;
    note: string;
    locator: string;
    reliability: string;
    badgeKind: "asserted" | "recorded";
  };
  cardB: {
    type: string;
    title: string;
    subtitle: string;
    note: string;
    locator: string;
    reliability: string;
    badgeKind: "asserted" | "recorded";
  };
  thread: {
    label: string;
    kind: "contradiction" | "gap" | "link";
  };
  inspection: {
    title: string;
    locator: string;
    hash: string;
    rawText: string;
    assessment: string;
  };
}

const SCENARIOS: Scenario[] = [
  {
    id: "contradiction",
    name: "Contradiction",
    label: "Witness Statement vs. Badge Swipe",
    cardA: {
      type: "statement",
      title: "Alex Morgan",
      subtitle: "Closing Shift Statement",
      note: "East cage was secured after the 20:00 count. Nobody entered after hours.",
      locator: "EV-080 · line 14",
      reliability: "asserted · witness",
      badgeKind: "asserted",
    },
    cardB: {
      type: "device",
      title: "Badge reader BR-4E",
      subtitle: "East Entrance Access Log",
      note: "Badge 1842 registered swipe at 20:14:22 PDT. Door unlatched 8s.",
      locator: "EV-071 · seq 40162",
      reliability: "recorded · NTP synced",
      badgeKind: "recorded",
    },
    thread: {
      label: "Contradiction detected (Δt = 14m)",
      kind: "contradiction",
    },
    inspection: {
      title: "Shift Statement vs. Electronic Access Log",
      locator: "EV-080 line 14 vs EV-071 seq 40162",
      hash: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      rawText:
        "[EV-080 line 14]: 'I completed the 20:00 count and verified east cage padlock engaged at 20:05. Nobody was authorized inside.'\n[EV-071 seq 40162]: 2026-10-17T20:14:22-07:00,READER_BR4E,BADGE_1842,ACCESS_GRANTED,DOOR_SEC_EAST",
      assessment:
        "The automated access record conflicts directly with the witness assertion. The reasoning engine isolates two testable hypotheses: (1) Jordan Lee used badge 1842 unannounced, or (2) badge 1842 was cloned/borrowed. Video analysis recommended.",
    },
  },
  {
    id: "gap",
    name: "Evidence Gap",
    label: "Corridor CCTV 19-Minute Blind Spot",
    cardA: {
      type: "device",
      title: "Camera CAM-4E",
      subtitle: "East Cage Corridor VMS",
      note: "Camera export has an unrecorded gap from 20:31 to 20:50. Feed flatlines.",
      locator: "EV-020 · vms_log",
      reliability: "recorded · camera outage",
      badgeKind: "recorded",
    },
    cardB: {
      type: "event",
      title: "Inventory Discrepancy",
      subtitle: "East Cage Count Audit",
      note: "12 handheld scanners and prototype components missing from locked shelf.",
      locator: "EV-001 · item_loss",
      reliability: "recorded · audit report",
      badgeKind: "recorded",
    },
    thread: {
      label: "Critical Gap (19m outage coincides with breach)",
      kind: "gap",
    },
    inspection: {
      title: "VMS Export Log vs. Inventory Discrepancy",
      locator: "EV-020:vms_export_index.csv:row=4",
      hash: "74b3d7a840e6981cf05cbf34a2e8c25790c58e7239efb925b3310065ad078d49",
      rawText:
        "2026-10-17T20:31:02-07:00,CAM-4E,STREAM_DROP,NO_SIGNAL\n2026-10-17T20:50:18-07:00,CAM-4E,STREAM_RESTORE,SIGNAL_RECOVERED,DROPPED_FRAMES=11520",
      assessment:
        "Surveillance outage perfectly brackets the physical inventory disappearance window. Next step ranked #1: Subpoena facility backup power telemetry and check physical junction switch J-04.",
    },
  },
  {
    id: "link",
    name: "Identity Link",
    label: "Active Workstation vs. Physical Badge",
    cardA: {
      type: "person",
      title: "Richard Halvorsen",
      subtitle: "Senior Systems Architect",
      note: "Active workstation session AURION\\rhalvorsen logged in Building 4.",
      locator: "EV-075 · session_log",
      reliability: "recorded · kerberos auth",
      badgeKind: "recorded",
    },
    cardB: {
      type: "location",
      title: "Executive Briefing Center",
      subtitle: "Building 2 Security Perimeter",
      note: "Physical badge swipe registered entry 4.2 miles away at 22:51.",
      locator: "EV-071 · seq 40889",
      reliability: "recorded · RFID swipe",
      badgeKind: "recorded",
    },
    thread: {
      label: "Concurrency Anomaly (Simultaneous presence)",
      kind: "link",
    },
    inspection: {
      title: "Kerberos Auth Log vs. RFID Perimeter Swipe",
      locator: "EV-075:line=412 vs EV-071:seq=40889",
      hash: "82f8a1290cb6460b64d08ef9186640cdad0ba33790e791b8fbfbaef32847a960",
      rawText:
        "2026-10-17T22:50:54-07:00 [EV-075]: HOST_WS402, USER=rhalvorsen, EVENT=KEYSTROKE_ACTIVE\n2026-10-17T22:51:04-07:00 [EV-071]: READER_EBC_EXT, BADGE=HALVORSEN_R, STATUS=VALID_ENTRY",
      assessment:
        "Spatiotemporal join detects physical impossibility: 4.2 miles separation traversed in 10 seconds. Multiple Working Hypotheses evaluates credential sharing against unauthorized badge duplication.",
    },
  },
];

interface Modality {
  id: string;
  name: string;
  category: "telemetry" | "comms" | "spatial" | "forensic";
  format: string;
  icon: typeof FileText;
  exampleId: string;
  recordCount: string;
  description: string;
  sampleRecord: string;
}

const MODALITIES: Modality[] = [
  {
    id: "badge",
    name: "Badge Access Logs",
    category: "telemetry",
    format: "CSV / JSON (RFID)",
    icon: Lock,
    exampleId: "EV-070",
    recordCount: "1,420 events",
    description:
      "Door readers, turnstiles, and cabinet latch sensors with millisecond UTC timestamps.",
    sampleRecord:
      '{"ts_utc": "2026-10-18T05:51:04Z", "reader": "BR-4E", "badge": "1842", "actor": "Jordan Lee", "action": "UNLATCH"}',
  },
  {
    id: "cdr",
    name: "Cell Detail Records (CDR)",
    category: "comms",
    format: "Carrier CSV / TSV",
    icon: Radio,
    exampleId: "EV-060",
    recordCount: "892 pings",
    description:
      "Tower cell ID, azimuth, carrier band, calling/called parties, and duration.",
    sampleRecord:
      '{"ts_utc": "2026-10-18T06:30:12Z", "caller": "+1-408-555-0147", "tower": "SBR-T04B", "azimuth": 120, "lat": 37.3861, "lon": -122.0839}',
  },
  {
    id: "location",
    name: "Google Location History",
    category: "spatial",
    format: "JSON (Semantic E7)",
    icon: MapPin,
    exampleId: "EV-062",
    recordCount: "509 visits",
    description:
      "Semantic place visits, path movements, and WiFi beacon cluster confidence scores.",
    sampleRecord:
      '{"place": "Aurion Campus B2", "start": "2026-10-18T05:40:00Z", "end": "2026-10-18T06:15:00Z", "confidence": 0.94}',
  },
  {
    id: "cctv",
    name: "Video & VMS Container Logs",
    category: "telemetry",
    format: "MP4 / VMS CSV",
    icon: Camera,
    exampleId: "EV-020",
    recordCount: "6 feeds",
    description:
      "Container capture timestamps, duration, frame rates, and dropout telemetry.",
    sampleRecord:
      '{"camera": "CAM-4E", "loss_start": "20:31:02", "loss_end": "20:50:18", "gap_seconds": 1156, "reason": "SIGNAL_DROP"}',
  },
  {
    id: "dna",
    name: "DNA & STR Profile Tables",
    category: "forensic",
    format: "STR Tables / Lab Reports",
    icon: Dna,
    exampleId: "EV-010",
    recordCount: "2 profiles",
    description:
      "Forensic STR marker profiles, match statistics, and lab conclusions.",
    sampleRecord:
      '{"locus": "D8S1179", "allele_1": "13", "allele_2": "15", "sample": "CABINET_HANDLE_SWAB", "match": "UNIDENTIFIED_MALE"}',
  },
  {
    id: "transcripts",
    name: "Interview Transcripts",
    category: "forensic",
    format: "TXT / DOCX (Line-numbered)",
    icon: FileText,
    exampleId: "EV-090",
    recordCount: "6 sessions",
    description:
      "Line-numbered investigator Q&A with speaker attribution and claim tags.",
    sampleRecord:
      '{"doc_line": 42, "speaker": "Det. Ana Reyes", "content": "When did you last see the AX-9 engineering sample in the cabinet?"}',
  },
  {
    id: "statements",
    name: "Written Statements",
    category: "forensic",
    format: "PDF / TXT",
    icon: FileCheck,
    exampleId: "EV-080",
    recordCount: "6 exhibits",
    description: "Signed witness declarations with narrative time resolution.",
    sampleRecord:
      '{"paragraph": 2, "declarant": "Alex Morgan", "time_asserted": "2026-10-17T20:00:00-07:00", "claim": "Cage locked"}',
  },
  {
    id: "whatsapp",
    name: "Chat & Messaging Exports",
    category: "comms",
    format: "WhatsApp / Signal TXT",
    icon: Phone,
    exampleId: "EV-050",
    recordCount: "348 messages",
    description:
      "Party direction, timestamped dialogues, shared attachments, and deleted messages.",
    sampleRecord:
      '{"from": "+1-408-555-0147", "to": "Halvorsen", "text": "Are we still meeting near building 2?", "ts": "22:15"}',
  },
  {
    id: "email",
    name: "Email & Mbox Archives",
    category: "comms",
    format: "EML / Mbox (RFC 822)",
    icon: Mail,
    exampleId: "EV-100",
    recordCount: "5 archives",
    description:
      "Headers, message IDs, custodian inboxes, and recursively ingested attachments.",
    sampleRecord:
      '{"from": "rhalvorsen@aurion.example", "subject": "ES-0007 Benchmark Schedule", "has_attachment": true}',
  },
  {
    id: "workstation",
    name: "Workstation Kerberos Logs",
    category: "telemetry",
    format: "Event Log JSON",
    icon: Terminal,
    exampleId: "EV-075",
    recordCount: "2,190 events",
    description:
      "Keystroke activity, lock/unlock events, screen saver states, and active logins.",
    sampleRecord:
      '{"host": "WS-402", "account": "AURION\\\\rhalvorsen", "status": "ACTIVE_SESSION", "ip": "10.4.12.88"}',
  },
  {
    id: "calendar",
    name: "Calendar Schedules",
    category: "spatial",
    format: "iCalendar .ics",
    icon: Clock,
    exampleId: "EV-076",
    recordCount: "224 events",
    description:
      "TZID-aware scheduled meetings, conference room bookings, and attendees.",
    sampleRecord:
      '{"summary": "AX-9 Architecture Review", "location": "EBC Briefing Room A", "tz": "America/Los_Angeles"}',
  },
  {
    id: "exif",
    name: "EXIF Forensic Photo Metadata",
    category: "forensic",
    format: "JPEG / HEIC / TIFF",
    icon: Camera,
    exampleId: "EV-030",
    recordCount: "11 images",
    description:
      "Camera serial numbers, GPS coordinates, capture offset, and software edit history.",
    sampleRecord:
      '{"make": "Sony", "model": "ILCE-7M4", "software": "Unedited Camera Raw", "gps": "37.3860° N, 122.0838° W"}',
  },
];

export function LandingPage({
  navigate,
  onDemo,
  opening,
  caseData,
}: LandingPageProps) {
  const [activeScenarioId, setActiveScenarioId] =
    useState<string>("contradiction");
  const [activePipelineStep, setActivePipelineStep] = useState<number>(2);
  const [activeModalityId, setActiveModalityId] = useState<string>("badge");
  const [inspectedOpen, setInspectedOpen] = useState<boolean>(true);

  const scenario =
    SCENARIOS.find((s) => s.id === activeScenarioId) || SCENARIOS[0];
  const selectedModality =
    MODALITIES.find((m) => m.id === activeModalityId) || MODALITIES[0];

  const demoButtonLabel = opening
    ? "Opening case…"
    : caseData?.title
      ? `Explore ${caseData.title}`
      : "Explore demo case";

  function handleOpenCase() {
    if (onDemo) {
      onDemo();
    } else {
      navigate("/projects");
    }
  }

  return (
    <div className="landing-viewport">
      {/* ── Top Navigation Bar ────────────────────────────────────────── */}
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
            <Fingerprint size={26} aria-hidden="true" />
            <span className="landing-brand-text">mapletrace</span>
          </a>

          <nav className="landing-links" aria-label="Page navigation">
            <a href="#pinboard" className="landing-link">
              Pinboard
            </a>
            <a href="#pipeline" className="landing-link">
              Pipeline
            </a>
            <a href="#contradiction" className="landing-link">
              Contradictions
            </a>
            <a href="#modalities" className="landing-link">
              14 Modalities
            </a>
            <a href="#kestrel" className="landing-link">
              Kestrel Case
            </a>
          </nav>

          <div className="landing-nav-actions">
            <button
              type="button"
              className="button button-secondary landing-nav-btn"
              onClick={() => navigate("/projects/new")}
            >
              New project
            </button>
            <button
              type="button"
              className="button button-primary landing-nav-btn"
              onClick={handleOpenCase}
              disabled={opening}
            >
              {opening ? "Opening case…" : "Open workspace"}
              <ArrowRight size={15} aria-hidden="true" />
            </button>
          </div>
        </div>
      </header>

      {/* ── Main Landing Body ────────────────────────────────────────── */}
      <main className="landing-main">
        {/* ── Section 1: Hero ────────────────────────────────────────── */}
        <section className="landing-hero-section" id="pinboard">
          <div className="landing-hero-container">
            <div className="landing-hero-copy">
              <h1 className="landing-hero-title">
                Evidence, connected.
                <br />
                Reasoning, defensible.
              </h1>
              <p className="landing-hero-lead">
                Turn multi-modal evidence dumps into inspectable, citeable
                pinboards. Unmask contradictions between human statements and
                machine logs—with every thread traceable to original files down
                to the exact line number.
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
                <button
                  type="button"
                  className="button button-secondary hero-btn-secondary"
                  onClick={() => navigate("/projects/new")}
                >
                  Upload case ZIP
                  <ArrowUpRight size={16} aria-hidden="true" />
                </button>
              </div>

              <div className="landing-hero-meta">
                <span className="hero-meta-dot" aria-hidden="true" />
                <span>
                  Fictional benchmark case · 57 files · 14 modalities · Zero
                  fabricated citations
                </span>
              </div>
            </div>

            {/* ── Interactive Hero Micro-Pinboard ─────────────────────── */}
            <div className="hero-pinboard-showcase">
              <div className="pinboard-frame-header">
                <div className="pinboard-scenario-tabs" role="tablist">
                  {SCENARIOS.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      role="tab"
                      aria-selected={activeScenarioId === s.id}
                      className={`scenario-tab ${activeScenarioId === s.id ? "active" : ""}`}
                      onClick={() => setActiveScenarioId(s.id)}
                    >
                      {s.name}
                    </button>
                  ))}
                </div>
                <span className="pinboard-badge">
                  Interactive Canvas Preview
                </span>
              </div>

              <div className="micro-pinboard-canvas">
                {/* SVG Connecting Thread */}
                <svg
                  className="micro-pinboard-svg"
                  viewBox="0 0 540 230"
                  aria-hidden="true"
                >
                  <path
                    d="M 170 115 C 230 40, 310 190, 370 115"
                    className={`micro-thread-path ${scenario.thread.kind}`}
                  />
                </svg>

                {/* Left Card: Card A */}
                <div
                  className={`micro-card card-a ${scenario.cardA.badgeKind}`}
                >
                  <div className="micro-pushpin" aria-hidden="true" />
                  <div className="micro-card-eyebrow">
                    <span>{scenario.cardA.subtitle}</span>
                  </div>
                  <h3 className="micro-card-title">{scenario.cardA.title}</h3>
                  <p className="micro-card-note">{scenario.cardA.note}</p>
                  <div className="micro-card-footer">
                    <span className="micro-locator">
                      {scenario.cardA.locator}
                    </span>
                    <span
                      className={`micro-reliability ${scenario.cardA.badgeKind}`}
                    >
                      [{scenario.cardA.reliability}]
                    </span>
                  </div>
                </div>

                {/* Center Thread Button */}
                <button
                  type="button"
                  className={`micro-thread-button ${scenario.thread.kind}`}
                  onClick={() => setInspectedOpen((prev) => !prev)}
                  aria-expanded={inspectedOpen}
                >
                  <span>{scenario.thread.label}</span>
                  <ArrowUpRight size={13} aria-hidden="true" />
                </button>

                {/* Right Card: Card B */}
                <div
                  className={`micro-card card-b ${scenario.cardB.badgeKind}`}
                >
                  <div className="micro-pushpin" aria-hidden="true" />
                  <div className="micro-card-eyebrow">
                    <span>{scenario.cardB.subtitle}</span>
                  </div>
                  <h3 className="micro-card-title">{scenario.cardB.title}</h3>
                  <p className="micro-card-note">{scenario.cardB.note}</p>
                  <div className="micro-card-footer">
                    <span className="micro-locator">
                      {scenario.cardB.locator}
                    </span>
                    <span
                      className={`micro-reliability ${scenario.cardB.badgeKind}`}
                    >
                      [{scenario.cardB.reliability}]
                    </span>
                  </div>
                </div>
              </div>

              {/* Source Inspection Drawer */}
              {inspectedOpen && (
                <div className="micro-inspector-drawer">
                  <div className="inspector-drawer-top">
                    <div className="inspector-drawer-title">
                      <FileCheck size={14} aria-hidden="true" />
                      <span>{scenario.inspection.title}</span>
                    </div>
                    <span className="inspector-hash">
                      SHA: {scenario.inspection.hash.slice(0, 16)}…
                    </span>
                  </div>
                  <pre className="inspector-raw-text">
                    <code>{scenario.inspection.rawText}</code>
                  </pre>
                  <p className="inspector-assessment">
                    <strong>Reasoning Engine:</strong>{" "}
                    {scenario.inspection.assessment}
                  </p>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* ── Section 2: The 4-Stage Ingestion & Reasoning Pipeline ─────── */}
        <section className="landing-section" id="pipeline">
          <div className="landing-section-header">
            <h2 className="landing-section-title">
              From raw evidence archive to court-ready graph
            </h2>
            <p className="landing-section-desc">
              Four deterministic pipeline stages transform heterogeneous
              forensic files into verified knowledge graphs and prioritized
              investigative next steps.
            </p>
          </div>

          <div className="pipeline-stepper-container">
            <div className="pipeline-stepper-nav" role="tablist">
              {[
                {
                  step: 1,
                  title: "1. Cryptographic Intake",
                  metric: "57 files · SHA-256 verified",
                },
                {
                  step: 2,
                  title: "2. Anomaly & Concurrency",
                  metric: "Isolation Forests · Co-location",
                },
                {
                  step: 3,
                  title: "3. Working Hypotheses",
                  metric: "Multiple hypotheses · No forced verdict",
                },
                {
                  step: 4,
                  title: "4. Retention-Aware Steps",
                  metric: "Subpoena ranking · Overwrite timers",
                },
              ].map((item) => (
                <button
                  key={item.step}
                  type="button"
                  role="tab"
                  aria-selected={activePipelineStep === item.step}
                  className={`pipeline-step-btn ${activePipelineStep === item.step ? "active" : ""}`}
                  onClick={() => setActivePipelineStep(item.step)}
                >
                  <span className="step-num">{item.step}</span>
                  <div className="step-label-group">
                    <span className="step-title">{item.title}</span>
                    <span className="step-metric">{item.metric}</span>
                  </div>
                </button>
              ))}
            </div>

            <div className="pipeline-stage-detail">
              {activePipelineStep === 1 && (
                <div className="pipeline-panel">
                  <div className="pipeline-panel-copy">
                    <h3>Intake, Content Classification, & Chain of Custody</h3>
                    <p>
                      Files are unpacked into read-only sandboxes. Extensions
                      are ignored: formats are classified by binary inspection
                      and mime probing. Every file is SHA-256 checked against
                      the case manifest and indexed into an immutable SQLite
                      store.
                    </p>
                    <ul className="pipeline-feature-list">
                      <li>
                        <CheckCircle2 size={16} aria-hidden="true" />
                        <span>Tamper-evident hash-chained audit log</span>
                      </li>
                      <li>
                        <CheckCircle2 size={16} aria-hidden="true" />
                        <span>
                          UTC normalization with explicit assumption flags
                        </span>
                      </li>
                      <li>
                        <CheckCircle2 size={16} aria-hidden="true" />
                        <span>
                          Line, row, doc_line, and byte-level locators
                        </span>
                      </li>
                    </ul>
                  </div>
                  <div className="pipeline-code-card">
                    <div className="code-header">
                      <span>mapletrace_ingest :: intake.py</span>
                      <span className="code-tag">STAGE 1</span>
                    </div>
                    <pre>
                      <code>{`def ingest_file(path, manifest_hash):
    digest = sha256_file(path)
    if digest != manifest_hash:
        raise EvidentiaryIntegrityError("Hash mismatch")
    
    # Content-based classification
    modality = classify_content(path)
    records = extract_locators(path, modality)
    
    db.write_immutable(records, hash_chain_head)
    return AuditEntry(status="VERIFIED", n_records=len(records))`}</code>
                    </pre>
                  </div>
                </div>
              )}

              {activePipelineStep === 2 && (
                <div className="pipeline-panel">
                  <div className="pipeline-panel-copy">
                    <h3>Unsupervised Anomaly Detection & Space-Time Joins</h3>
                    <p>
                      An unsupervised Isolation Forest evaluates access logs and
                      workstation activity for statistical deviations.
                      Spatiotemporal joins check physical trajectories,
                      instantly flagging when one credential is logged in two
                      distant buildings at the same time.
                    </p>
                    <ul className="pipeline-feature-list">
                      <li>
                        <CheckCircle2 size={16} aria-hidden="true" />
                        <span>
                          Isolation Forest per log to catch off-hours activity
                        </span>
                      </li>
                      <li>
                        <CheckCircle2 size={16} aria-hidden="true" />
                        <span>
                          Speed-of-travel bounds to detect credential sharing
                        </span>
                      </li>
                      <li>
                        <CheckCircle2 size={16} aria-hidden="true" />
                        <span>
                          Zero black-box guesses: all anomalies mathematically
                          scored
                        </span>
                      </li>
                    </ul>
                  </div>
                  <div className="pipeline-code-card">
                    <div className="code-header">
                      <span>mapletrace_reason :: analytics.py</span>
                      <span className="code-tag">STAGE 2</span>
                    </div>
                    <pre>
                      <code>{`# Space-time concurrency violation check
for (swipe, ws_session) in spatiotemporal_join(swipes, sessions):
    distance_km = haversine(swipe.latlon, ws_session.latlon)
    delta_t_sec = abs(swipe.ts - ws_session.ts)
    
    required_velocity = distance_km / (delta_t_sec / 3600.0)
    if required_velocity > MAX_TRANSIT_VELOCITY_KMH:
        yield ConcurrencyConflict(
            conflict_type="IMPOSSIBLE_TRAVEL",
            velocity_kmh=required_velocity,
            citations=[swipe.locator, ws_session.locator]
        )`}</code>
                    </pre>
                  </div>
                </div>
              )}

              {activePipelineStep === 3 && (
                <div className="pipeline-panel">
                  <div className="pipeline-panel-copy">
                    <h3>Multiple Working Hypotheses & Source Independence</h3>
                    <p>
                      Instead of forcing premature conclusions, Mapletrace
                      evaluates competing theories: borrowed credentials,
                      untruthful statements, clock drift, or associate
                      involvement. Echo chambers are rejected by tracking
                      independent custodian origins rather than counting
                      repeated forwarded emails.
                    </p>
                    <ul className="pipeline-feature-list">
                      <li>
                        <CheckCircle2 size={16} aria-hidden="true" />
                        <span>
                          Asserted claims separated from recorded facts
                        </span>
                      </li>
                      <li>
                        <CheckCircle2 size={16} aria-hidden="true" />
                        <span>
                          Source independence scoring based on distinct
                          custodians
                        </span>
                      </li>
                      <li>
                        <CheckCircle2 size={16} aria-hidden="true" />
                        <span>
                          Outputs "Insufficient evidence" until decisive records
                          arrive
                        </span>
                      </li>
                    </ul>
                  </div>
                  <div className="pipeline-code-card">
                    <div className="code-header">
                      <span>mapletrace_reason :: hypotheses.py</span>
                      <span className="code-tag">STAGE 3</span>
                    </div>
                    <pre>
                      <code>{`# Multiple Working Hypotheses evaluation
explanations = [
    Explanation("Credential shared with associate", supporting=2, opposing=0),
    Explanation("Declarant statement untruthful", supporting=4, opposing=0),
    Explanation("Reader clock drift", supporting=0, opposing=2)  # Disproven
]

if score_gap(explanations[0], explanations[1]) < THRESHOLD:
    return Verdict(
        status="INSUFFICIENT_EVIDENCE_TO_CHOOSE",
        discriminating_evidence=["CAM-4E corridor backup", "Swab STR profile"]
    )`}</code>
                    </pre>
                  </div>
                </div>
              )}

              {activePipelineStep === 4 && (
                <div className="pipeline-panel">
                  <div className="pipeline-panel-copy">
                    <h3>Retention-Aware Evidence Subpoenas</h3>
                    <p>
                      The gap engine identifies directed questions the evidence
                      cannot answer. It ranks concrete next steps by urgency:
                      surveillance video loop overwrites (7–14 days) and cell
                      tower carrier log purges (30 days) receive top priority.
                    </p>
                    <ul className="pipeline-feature-list">
                      <li>
                        <CheckCircle2 size={16} aria-hidden="true" />
                        <span>
                          Explicit countdown timers for surveillance overwrite
                          loops
                        </span>
                      </li>
                      <li>
                        <CheckCircle2 size={16} aria-hidden="true" />
                        <span>
                          Concrete subpoenas generated with names, places, and
                          times
                        </span>
                      </li>
                      <li>
                        <CheckCircle2 size={16} aria-hidden="true" />
                        <span>
                          Ranks evidence by how many competing hypotheses it
                          resolves
                        </span>
                      </li>
                    </ul>
                  </div>
                  <div className="pipeline-code-card">
                    <div className="code-header">
                      <span>mapletrace_reason :: recommend.py</span>
                      <span className="code-tag">STAGE 4</span>
                    </div>
                    <pre>
                      <code>{`# Rank evidence by investigative value and retention urgency
def rank_next_steps(gaps, hypotheses):
    for gap in gaps:
        urgency = retention_risk_score(gap.target_modality)
        discrimination = hypothesis_separation_power(gap, hypotheses)
        rank_score = (urgency * 0.6) + (discrimination * 0.4)
        
        yield Recommendation(
            action=gap.recommended_subpoena,
            deadline=gap.retention_deadline,
            rank=rank_score
        )`}</code>
                    </pre>
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* ── Section 3: The Contradiction Engine ───────────────────────── */}
        <section className="landing-section" id="contradiction">
          <div className="landing-section-header">
            <h2 className="landing-section-title">The Contradiction Engine</h2>
            <p className="landing-section-desc">
              Human memory is approximate. Badges get borrowed. Clocks drift.
              Mapletrace reconciles human claims against machine records without
              jumping to accusations.
            </p>
          </div>

          <div className="contradiction-showcase">
            <div className="contradiction-columns">
              {/* Left Column: Human Claim */}
              <div className="contradiction-col claim-col">
                <div className="col-header">
                  <span className="col-tag tag-asserted">HUMAN ASSERTION</span>
                  <span className="col-meta">EV-082 line 14</span>
                </div>
                <div className="contradiction-card">
                  <blockquote>
                    “I was at home all Saturday evening, October 17. Had dinner,
                    watched a movie, and went to sleep before 22:30. I did not
                    visit the office or briefing room until Monday.”
                  </blockquote>
                  <div className="card-source-citation">
                    <strong>Declarant:</strong> Richard Halvorsen · Senior
                    Architect
                    <br />
                    <strong>Reliability:</strong> Asserted (Subjective
                    recollection)
                  </div>
                </div>
              </div>

              {/* Right Column: Machine Ground Truth */}
              <div className="contradiction-col record-col">
                <div className="col-header">
                  <span className="col-tag tag-recorded">
                    MACHINE GROUND TRUTH
                  </span>
                  <span className="col-meta">EV-071 seq 40889</span>
                </div>
                <div className="contradiction-card">
                  <blockquote>
                    2026-10-17T22:51:04-07:00 · READER_BR4E_EAST
                    <br />
                    Credential: HALVORSEN_R (Valid RFID)
                    <br />
                    Cell Tower Ping: Tower 4B, Azimuth 120° (22:48 PDT)
                  </blockquote>
                  <div className="card-source-citation">
                    <strong>System:</strong> Facility Access Controller &
                    Carrier CDR
                    <br />
                    <strong>Reliability:</strong> Recorded (NTP Synced machine
                    log)
                  </div>
                </div>
              </div>
            </div>

            {/* Assessment Bar */}
            <div className="contradiction-verdict-bar">
              <div className="verdict-summary">
                <div className="verdict-title-group">
                  <AlertTriangle
                    size={18}
                    className="amber-icon"
                    aria-hidden="true"
                  />
                  <strong>Direct Contradiction Identified</strong>
                </div>
                <p>
                  Electronic access log conflicts with stated alibi window. The
                  reasoning engine generates four competing hypotheses:
                </p>
              </div>

              <div className="hypotheses-grid">
                <div className="hypothesis-item highlight">
                  <div className="hypothesis-header">
                    <span>Hypothesis 1: Associate Used Credential</span>
                    <span className="hyp-status leading">Leading</span>
                  </div>
                  <p>
                    Supported by concurrent active workstation session WS-402 in
                    Building 4 and 116 phone exchanges with an unidentified
                    number.
                  </p>
                </div>
                <div className="hypothesis-item">
                  <div className="hypothesis-header">
                    <span>Hypothesis 2: Declarant Untruthful</span>
                    <span className="hyp-status plausible">Plausible</span>
                  </div>
                  <p>
                    Supported by cell tower CDR Sector 4B ping near Aurion
                    campus at 22:48 PDT.
                  </p>
                </div>
                <div className="hypothesis-item">
                  <div className="hypothesis-header">
                    <span>Hypothesis 3: Reader Clock Drift</span>
                    <span className="hyp-status disproven">Disproven</span>
                  </div>
                  <p>
                    NTP sync log confirms BR-4E clock jitter was within ±180ms
                    during the incident window.
                  </p>
                </div>
              </div>

              <div className="verdict-action">
                <span>
                  <strong>Verdict:</strong> Insufficient evidence to choose
                  between Hypotheses 1 & 2.
                </span>
                <span className="verdict-next-step">
                  <strong>Decisive Action:</strong> Subpoena exterior parking
                  lot surveillance feed (Expires in 4 days).
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* ── Section 4: 14 Ingestion Modalities Matrix ──────────────────── */}
        <section className="landing-section" id="modalities">
          <div className="landing-section-header">
            <h2 className="landing-section-title">
              14 Ingestion Modalities. Zero Blind Spots.
            </h2>
            <p className="landing-section-desc">
              From forensic DNA STR profile comparisons to WhatsApp chat backups
              and carrier CDR towers, every piece of evidence is normalized into
              an immutable schema with byte-level citations.
            </p>
          </div>

          <div className="modalities-container">
            <div className="modalities-grid" role="tablist">
              {MODALITIES.map((mod) => {
                const IconComponent = mod.icon;
                const isSelected = activeModalityId === mod.id;
                return (
                  <button
                    key={mod.id}
                    type="button"
                    role="tab"
                    aria-selected={isSelected}
                    className={`modality-chip ${isSelected ? "selected" : ""}`}
                    onClick={() => setActiveModalityId(mod.id)}
                  >
                    <IconComponent size={18} aria-hidden="true" />
                    <div className="modality-chip-text">
                      <span className="mod-name">{mod.name}</span>
                      <span className="mod-count">{mod.recordCount}</span>
                    </div>
                  </button>
                );
              })}
            </div>

            <div className="modality-detail-card">
              <div className="mod-card-header">
                <div className="mod-card-title-group">
                  <selectedModality.icon
                    size={22}
                    className="green-icon"
                    aria-hidden="true"
                  />
                  <div>
                    <h3>{selectedModality.name}</h3>
                    <span className="mod-format-badge">
                      Format: {selectedModality.format} · Reference:{" "}
                      {selectedModality.exampleId}
                    </span>
                  </div>
                </div>
                <span className="mod-category-pill">
                  {selectedModality.category.toUpperCase()}
                </span>
              </div>

              <p className="mod-description">{selectedModality.description}</p>

              <div className="mod-code-preview">
                <span className="code-label">
                  Normalized SQLite Schema Output:
                </span>
                <pre>
                  <code>{selectedModality.sampleRecord}</code>
                </pre>
              </div>
            </div>
          </div>
        </section>

        {/* ── Section 5: Court-Ready Defensibility & Ethics ─────────────── */}
        <section className="landing-section" id="defensibility">
          <div className="landing-section-header">
            <h2 className="landing-section-title">
              Courtroom-grade defensibility
            </h2>
            <p className="landing-section-desc">
              Black-box AI models that generate ungrounded conclusions cannot be
              admitted into court. Mapletrace enforces strict mathematical and
              evidentiary guardrails.
            </p>
          </div>

          <div className="principles-grid">
            <div className="principle-card">
              <div className="principle-icon-wrap">
                <ShieldCheck size={24} aria-hidden="true" />
              </div>
              <h3>Admiralty Grading System</h3>
              <p>
                Every record carries an Admiralty evaluation: source reliability
                (A–F) and information credibility (1–6). Echo chambers are
                avoided by tracking independent custodian origins rather than
                counting repeated forwarded reports.
              </p>
            </div>

            <div className="principle-card">
              <div className="principle-icon-wrap">
                <Database size={24} aria-hidden="true" />
              </div>
              <h3>Cryptographic Audit Chain</h3>
              <p>
                Every file extraction, timeline parse, anomaly score, and
                investigator override appends to a hash-chained log. Running the
                built-in verify tool confirms evidence files and databases have
                not been retroactively altered.
              </p>
            </div>

            <div className="principle-card">
              <div className="principle-icon-wrap">
                <Lock size={24} aria-hidden="true" />
              </div>
              <h3>Ethical Guardrails & Bias Traps</h3>
              <p>
                Protected demographic attributes (nationality, issuing country)
                are strictly barred from being model features. The Kestrel
                dataset includes an intentional bias trap (RH-03) that
                Mapletrace systematically rejects.
              </p>
            </div>
          </div>
        </section>

        {/* ── Section 6: Case Study Spotlight ───────────────────────────── */}
        <section className="landing-section case-study-section" id="kestrel">
          <div className="case-study-banner">
            <div className="case-study-content">
              <div className="case-study-heading-group">
                <h2 className="case-study-title">
                  The Kestrel Incident · SBRPD-26-104417
                </h2>
                <span className="case-study-badge">BENCHMARK DATASET</span>
              </div>
              <p className="case-study-summary">
                An unreleased AX-9 “Kestrel” GPU engineering sample disappeared
                from a secure cabinet in the Executive Briefing Center of Aurion
                Compute, Inc. over the weekend of October 17.
              </p>

              <div className="case-study-stats">
                <div className="stat-item">
                  <strong>57</strong>
                  <span>Case files</span>
                </div>
                <div className="stat-item">
                  <strong>5,600+</strong>
                  <span>Normalized records</span>
                </div>
                <div className="stat-item">
                  <strong>14</strong>
                  <span>Modalities</span>
                </div>
                <div className="stat-item">
                  <strong>100%</strong>
                  <span>Hash verification</span>
                </div>
              </div>

              <div className="case-study-actions">
                <button
                  type="button"
                  className="button button-primary"
                  onClick={handleOpenCase}
                  disabled={opening}
                >
                  {opening ? "Opening case…" : "Inspect Kestrel case file"}
                  <ArrowRight size={16} aria-hidden="true" />
                </button>
              </div>
            </div>

            <div className="case-study-preview-box">
              <div className="preview-box-header">
                <span>EVIDENCE BRIEF</span>
                <span>SBRPD-26-104417</span>
              </div>
              <ul className="case-events-timeline">
                <li>
                  <span className="event-time">Oct 17 · 20:14</span>
                  <p>Badge 1842 access to East Cage corridor</p>
                </li>
                <li>
                  <span className="event-time">Oct 17 · 20:31–20:50</span>
                  <p className="highlight-text">
                    CAM-4E video outage (19m unrecorded blind spot)
                  </p>
                </li>
                <li>
                  <span className="event-time">Oct 17 · 22:51</span>
                  <p>Cabinet breached with Halvorsen credential</p>
                </li>
                <li>
                  <span className="event-time">Oct 17 · 22:51</span>
                  <p className="highlight-text">
                    Halvorsen workstation active in Bldg 4 (Concurrency
                    Conflict)
                  </p>
                </li>
              </ul>
            </div>
          </div>
        </section>

        {/* ── Section 7: Bottom CTA & Disclosures ────────────────────────── */}
        <section className="landing-bottom-cta">
          <div className="bottom-cta-container">
            <h2 className="bottom-cta-title">
              Step onto the evidence pinboard
            </h2>
            <p className="bottom-cta-lead">
              Experience how Mapletrace transforms messy case files into clear,
              defensible investigative truth.
            </p>

            <div className="bottom-cta-buttons">
              <button
                type="button"
                className="button button-primary cta-large-btn"
                onClick={handleOpenCase}
                disabled={opening}
              >
                {opening ? "Opening case…" : "Launch investigation workspace"}
                <ArrowRight size={17} aria-hidden="true" />
              </button>
              <button
                type="button"
                className="button button-secondary cta-large-btn"
                onClick={() => navigate("/projects/new")}
              >
                Start new project (ZIP)
                <ArrowUpRight size={16} aria-hidden="true" />
              </button>
            </div>

            <div className="synthetic-disclosure-box">
              <AlertTriangle size={15} aria-hidden="true" />
              <span>
                <strong>Synthetic & Fictional Case:</strong> Every individual,
                company, phone number (555-01xx), vehicle plate, and forensic
                record is synthetic for prototype demonstration.
              </span>
            </div>
          </div>
        </section>
      </main>

      {/* ── Footer ───────────────────────────────────────────────────── */}
      <footer className="landing-footer">
        <div className="landing-footer-inner">
          <div className="footer-brand-col">
            <div className="landing-brand">
              <Fingerprint size={20} aria-hidden="true" />
              <span className="landing-brand-text">mapletrace</span>
            </div>
            <p className="footer-tagline">
              Evidence-first investigative workspace and automated reasoning
              engine.
            </p>
          </div>

          <div className="footer-links-col">
            <span className="footer-group-title">WORKSPACE</span>
            <button
              type="button"
              className="footer-link-btn"
              onClick={handleOpenCase}
            >
              Demo Case
            </button>
            <button
              type="button"
              className="footer-link-btn"
              onClick={() => navigate("/projects")}
            >
              Project Manager
            </button>
            <button
              type="button"
              className="footer-link-btn"
              onClick={() => navigate("/projects/new")}
            >
              Upload Archive
            </button>
          </div>

          <div className="footer-links-col">
            <span className="footer-group-title">CONTROLS</span>
            <span className="footer-kbd-item">
              <kbd>Two-finger swipe</kbd> Pan canvas
            </span>
            <span className="footer-kbd-item">
              <kbd>Pinch / Scroll</kbd> Zoom canvas
            </span>
            <span className="footer-kbd-item">
              <kbd>Click thread</kbd> Source citation
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
