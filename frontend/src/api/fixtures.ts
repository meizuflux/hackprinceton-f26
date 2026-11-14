import type { CaseData } from "./types";

/** Fictional and disposable demo data. Source excerpts are synthetic too. */
export const demoCase: CaseData = {
  id: "wh-2026-1112",
  title: "Northline warehouse inventory loss",
  subtitle: "Fictional case file · Warehouse 4 · Nov 12, 2026",
  timeRange: {
    start: "2026-11-12T18:00:00-05:00",
    end: "2026-11-12T23:59:00-05:00",
  },
  nodes: [
    {
      id: "alex",
      type: "person",
      label: "Alex Morgan",
      subtitle: "Inventory lead",
      summary: "Assigned closing inventory lead on the east shift.",
      citations: ["S01", "S05"],
      position: { x: 80, y: 100 },
    },
    {
      id: "jordan",
      type: "person",
      label: "Jordan Lee",
      subtitle: "Forklift operator",
      summary: "Badge record shows a Warehouse 4 entry during the shift.",
      citations: ["S02"],
      position: { x: 80, y: 300 },
    },
    {
      id: "wh4",
      type: "location",
      label: "Warehouse 4",
      subtitle: "Northline distribution site",
      summary: "The reported inventory loss occurred in the east cage.",
      citations: ["S01", "S03"],
      position: { x: 430, y: 220 },
    },
    {
      id: "badge",
      type: "device",
      label: "Badge reader BR-4E",
      subtitle: "East entrance",
      summary:
        "Reader log records badge 1842 at 20:14; assigned user is Jordan Lee.",
      citations: ["S02"],
      position: { x: 430, y: 430 },
    },
    {
      id: "camera",
      type: "device",
      label: "Camera CAM-4E",
      subtitle: "East cage corridor",
      summary:
        "Camera export has a 19-minute recording gap around the reported window.",
      citations: ["S03"],
      position: { x: 770, y: 430 },
      gapId: "gap-video",
    },
    {
      id: "loss",
      type: "event",
      label: "Inventory discrepancy",
      subtitle: "Reported 21:06",
      summary:
        "A cycle count reported 12 handheld scanners missing from the east cage.",
      citations: ["S01"],
      position: { x: 770, y: 100 },
      gapId: "gap-count",
    },
    {
      id: "van",
      type: "event",
      label: "Unverified van sighting",
      subtitle: "Approx. 20:40",
      summary:
        "A witness recalls a white van near the loading dock; no plate or driver identified.",
      citations: ["S04"],
      position: { x: 1100, y: 220 },
      gapId: "gap-vehicle",
    },
    {
      id: "statement",
      type: "statement",
      label: "Closing shift statement",
      subtitle: "Alex Morgan · 21:22",
      summary: "Alex said the east cage was secured after the 20:00 count.",
      citations: ["S05"],
      position: { x: 430, y: 60 },
    },
  ],
  edges: [
    {
      id: "e1",
      source: "alex",
      target: "wh4",
      type: "assigned_to",
      label: "assigned shift at",
      citations: ["S01", "S05"],
    },
    {
      id: "e2",
      source: "jordan",
      target: "badge",
      type: "associated_with",
      label: "badge assigned to",
      citations: ["S02"],
    },
    {
      id: "e3",
      source: "badge",
      target: "wh4",
      type: "logged_at",
      label: "entry logged at",
      citations: ["S02"],
    },
    {
      id: "e4",
      source: "camera",
      target: "wh4",
      type: "covers",
      label: "covers corridor at",
      citations: ["S03"],
    },
    {
      id: "e5",
      source: "loss",
      target: "wh4",
      type: "reported_at",
      label: "reported in",
      citations: ["S01"],
    },
    {
      id: "e6",
      source: "statement",
      target: "alex",
      type: "made_by",
      label: "statement by",
      citations: ["S05"],
    },
    {
      id: "e7",
      source: "statement",
      target: "wh4",
      type: "describes",
      label: "describes securing",
      citations: ["S05"],
    },
    {
      id: "e8",
      source: "van",
      target: "wh4",
      type: "reported_near",
      label: "witness recalled near",
      citations: ["S04"],
    },
    {
      id: "e9",
      source: "loss",
      target: "camera",
      type: "time_overlap",
      label: "time window overlaps recording gap",
      citations: ["S01", "S03"],
    },
  ],
  gaps: [
    {
      id: "gap-video",
      title: "Camera coverage missing",
      description:
        "The export lacks footage from 20:31–20:50, overlapping the approximate vehicle sighting. Missing footage does not establish what happened.",
      score: 0.92,
      affectedClaims: [
        "Who entered the east cage during the discrepancy window",
        "Whether activity near the cage coincided with the van sighting",
      ],
      suggestedEvidence: ["SG1"],
      citations: ["S03", "S04"],
    },
    {
      id: "gap-vehicle",
      title: "Van not identified",
      description:
        "The witness could not provide a plate, driver description, or a precise arrival time. The sighting remains uncorroborated.",
      score: 0.78,
      affectedClaims: ["Whether a vehicle was connected to the inventory loss"],
      suggestedEvidence: ["SG2"],
      citations: ["S04"],
    },
    {
      id: "gap-count",
      title: "No second count attached",
      description:
        "The incident report cites a count of 12 missing scanners, but the source packet contains no signed recount or transfer record.",
      score: 0.65,
      affectedClaims: [
        "Whether all 12 scanners were present before the reported loss",
      ],
      suggestedEvidence: ["SG3"],
      citations: ["S01"],
    },
  ],
  insights: [
    {
      id: "I1",
      title: "The reported loss follows the last logged count",
      text: "The report places discovery at 21:06, while the closing statement describes a 20:00 count. The interval is not independently verified.",
      score: 0.84,
      citations: ["S01", "S05"],
    },
    {
      id: "I2",
      title: "A badge event is not proof of cage access",
      text: "Badge 1842 was logged at the east entrance at 20:14, but the record does not show which person used it or whether the cage was entered.",
      score: 0.79,
      citations: ["S02", "S03"],
    },
    {
      id: "I3",
      title: "Two evidence threads share a time window",
      text: "The camera export gap and approximate van sighting overlap in time. This is a lead for follow-up, not evidence that the events are connected.",
      score: 0.72,
      citations: ["S03", "S04"],
    },
  ],
  suggestions: [
    {
      id: "SG1",
      title: "Request original camera recorder export",
      description:
        "Ask facilities for the native CAM-4E recording and recorder health logs covering 20:25–21:00.",
      priority: 1,
      query:
        "CAM-4E native recording and recorder health logs, 2026-11-12 20:25–21:00",
      citations: ["S03"],
      gapId: "gap-video",
    },
    {
      id: "SG2",
      title: "Check loading dock vehicle records",
      description:
        "Request dock gate logs and any retained lot camera footage for 20:20–21:00.",
      priority: 2,
      query:
        "Warehouse 4 loading dock gate log and lot footage, 2026-11-12 20:20–21:00",
      citations: ["S04"],
      gapId: "gap-vehicle",
    },
    {
      id: "SG3",
      title: "Obtain signed recount and transfer log",
      description:
        "Request the second count sheet and scanner issue/return records for the shift.",
      priority: 3,
      query:
        "East cage scanner count sheet and transfer log for 2026-11-12 evening shift",
      citations: ["S01"],
      gapId: "gap-count",
    },
  ],
  sources: [
    {
      id: "S01",
      path: "incident/incident-report.pdf",
      kind: "Incident report",
      timestamp: "2026-11-12T21:18:00-05:00",
      hash: "sha256:fictional-01",
      excerpt:
        "At 21:06 the cycle count identified twelve handheld scanners absent from the east cage. Last count noted at approximately 20:00.",
      metadata: {
        author: "Northline Loss Prevention",
        page: "1",
        status: "Fictional record",
      },
    },
    {
      id: "S02",
      path: "access/reader-BR-4E.csv",
      kind: "Access log",
      timestamp: "2026-11-12T20:14:00-05:00",
      hash: "sha256:fictional-02",
      excerpt:
        "20:14:32 — credential 1842 — east entrance BR-4E — access granted.",
      metadata: {
        system: "Badge reader BR-4E",
        credential: "1842",
        status: "Fictional record",
      },
    },
    {
      id: "S03",
      path: "video/CAM-4E-export-notes.txt",
      kind: "Video export note",
      timestamp: "2026-11-12T22:03:00-05:00",
      hash: "sha256:fictional-03",
      excerpt:
        "Export has no frames from 20:31 to 20:50. Recorder health and source footage not included in this packet.",
      metadata: {
        camera: "CAM-4E",
        interval: "20:31–20:50",
        status: "Fictional record",
      },
    },
    {
      id: "S04",
      path: "interviews/witness-01.txt",
      kind: "Witness note",
      timestamp: "2026-11-12T21:40:00-05:00",
      hash: "sha256:fictional-04",
      excerpt:
        "Witness recalls a white van by the loading dock around 20:40; could not see the plate or driver.",
      metadata: {
        witness: "W-01 (fictional)",
        status: "Uncorroborated recollection",
      },
    },
    {
      id: "S05",
      path: "interviews/alex-morgan.txt",
      kind: "Interview note",
      timestamp: "2026-11-12T21:22:00-05:00",
      hash: "sha256:fictional-05",
      excerpt:
        "Alex Morgan said the east cage was secured after the 20:00 count; no second count sheet was attached.",
      metadata: {
        interviewer: "Northline Loss Prevention",
        status: "Fictional record",
      },
    },
  ],
  audit: [
    {
      id: "A1",
      time: "2026-11-14T09:00:00-05:00",
      title: "Case loaded",
      description: "Loaded the fictional Northline Warehouse 4 case fixture.",
      citations: [],
    },
    {
      id: "A2",
      time: "2026-11-14T09:00:02-05:00",
      title: "Evidence links attached",
      description:
        "Fixture relationships and analytic notes reference source IDs shown in the source panel.",
      citations: ["S01", "S02", "S03", "S04", "S05"],
    },
  ],
};
