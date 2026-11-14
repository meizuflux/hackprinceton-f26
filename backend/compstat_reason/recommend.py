"""Next steps: which evidence to obtain, ranked.

A recommendation scores higher when it closes several important gaps, separates competing explanations,
is time-critical (retention windows), adds an independent kind of source, and is quick to obtain.
Each recommendation names the person, time and place it concerns, and explains its rank.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from .model import Item, stable_key
from .store import parse_ts

CATALOG = {
    "cctv_review": {"name": "CCTV footage", "source_class": "video", "retention_days": 30, "speed": "fast",
                    "request": "Export and review CCTV covering {place} for {window}; identify everyone entering or leaving.",
                    "process": "request to the system owner"},
    "media_analysis": {"name": "Analyse video already in the case", "source_class": "internal", "retention_days": None,
                       "speed": "fast", "request": "Review {files} frame by frame for people, faces and clothing.",
                       "process": "internal"},
    "phone_location": {"name": "Carrier location records", "source_class": "carrier", "retention_days": 365, "speed": "slow",
                       "request": "Cell-site and timing-advance location records for {person}'s phone, {window}.",
                       "process": "court order to the carrier"},
    "subscriber_records": {"name": "Subscriber and billing records", "source_class": "carrier", "retention_days": 730,
                           "speed": "slow", "request": "Subscriber identity, billing name, address and payment method for {identifier}.",
                           "process": "subpoena to the carrier"},
    "device_forensics": {"name": "Phone extraction", "source_class": "device", "retention_days": 60, "speed": "medium",
                         "request": "Full extraction of {person}'s phone, including deleted messages and app data{window_part}.",
                         "process": "consent or warrant"},
    "follow_up_interview": {"name": "Follow-up interview", "source_class": "testimonial", "retention_days": 21, "speed": "fast",
                            "request": "Re-interview {person} about {topic}; present the specific conflicting records.",
                            "process": "voluntary interview"},
    "access_system_audit": {"name": "Access-control audit", "source_class": "system", "retention_days": 90, "speed": "fast",
                            "request": "Export raw controller logs, credential assignment history and PIN/duress events for {place}, {window}.",
                            "process": "request to the facility"},
    "system_clock_check": {"name": "System clock check", "source_class": "system", "retention_days": None, "speed": "fast",
                           "request": "Measure clock offsets of {systems} against a reference time.", "process": "request to the facility"},
    "forensic_lab": {"name": "DNA / fingerprint examination", "source_class": "lab", "retention_days": None, "speed": "slow",
                     "request": "Swab and fingerprint objects at {place}; compare with reference samples from people in the case.",
                     "process": "lab request"},
    "financial_records": {"name": "Financial records", "source_class": "financial", "retention_days": 365, "speed": "slow",
                          "request": "Card and bank transactions for {person}, {window}.", "process": "subpoena or consent"},
    "file_recovery": {"name": "Readable copy of a submitted file", "source_class": "internal", "retention_days": None,
                      "speed": "fast", "request": "Obtain a readable copy of {file} or a tool that parses its format.",
                      "process": "internal"},
}
_SPEED_PENALTY = {"fast": 0.0, "medium": 0.05, "slow": 0.1}


def _fill(template: str, params: dict) -> str:
    p = {k: (", ".join(v) if isinstance(v, list) else (" to ".join(v) if isinstance(v, tuple) else str(v)))
         for k, v in (params or {}).items() if v}
    p.setdefault("window_part", f", {p['window']}" if p.get("window") else "")
    for k in ("place", "window", "person", "identifier", "files", "systems", "topic", "file"):
        p.setdefault(k, "the relevant period" if k == "window" else f"the relevant {k}")
    return template.format(**p)


def rank(case, gaps: list[Item], verdicts: list[dict], present_classes: set[str]) -> list[Item]:
    discriminating = {d["artifact"] for v in verdicts for d in v["discriminating_evidence"]}
    as_of = case_as_of(case)
    groups: dict[str, dict] = {}
    for g in gaps:
        if g.status == "resolved":
            continue
        for a in g.data["artifacts"]:
            art = a["artifact"]
            if art not in CATALOG:
                continue
            sig = stable_key(art, json.dumps(a.get("params", {}), sort_keys=True, default=str))
            entry = groups.setdefault(sig, {"artifact": art, "params": a.get("params", {}), "gaps": [], "why": set()})
            entry["gaps"].append(g)
            if a.get("why"):
                entry["why"].add(a["why"])
    items = []
    for sig, e in groups.items():
        spec = CATALOG[e["artifact"]]
        gs = e["gaps"]
        base = max(g.score for g in gs)
        multi = 0.12 * (len(gs) - 1)
        reasons = [f"helps answer {len(gs)} open question(s): " + "; ".join(g.title for g in gs[:3])]
        bonus = 0.0
        if e["artifact"] in discriminating or any(g.data["gap_type"] == "uncertain" and "explanation" in g.title for g in gs):
            bonus += 0.2
            reasons.append("distinguishes between competing explanations")
        days = _days_since(case, gs, as_of)
        ret = spec["retention_days"]
        if ret and days is not None:
            left = ret - days
            if left <= 14:
                bonus += 0.25
                reasons.append(f"urgent: typically kept about {ret} days and the event was {days} days before the case date"
                               + (" (may already be overwritten)" if left < 0 else ""))
        if spec["source_class"] not in present_classes and spec["source_class"] not in ("internal",):
            bonus += 0.15
            reasons.append("adds an independent kind of source the case does not have yet")
        if spec["speed"] == "slow":
            reasons.append(f"slower to obtain ({spec['process']})")
        score = min(1.0, base + multi + bonus - _SPEED_PENALTY[spec["speed"]])
        request = _fill(spec["request"], e["params"])
        items.append(Item(
            "suggestion", stable_key("sugg", sig), f"{spec['name']}: {request[:80]}", request, certainty="unknown",
            score=round(score, 2), citations=[c for g in gs for c in g.citations[:1]][:4],
            data={"artifact": e["artifact"], "artifact_name": spec["name"], "params": e["params"], "request": request,
                  "gaps": [g.key for g in gs], "reasons": reasons + sorted(e["why"])[:2], "process": spec["process"],
                  "source_class": spec["source_class"], "speed": spec["speed"], "query": request}))
    items.sort(key=lambda i: -i.score)
    for n, it in enumerate(items, 1):
        it.data["priority"] = n
    return items


def case_as_of(case) -> datetime:
    """The case date: latest machine-recorded evidence (future calendar entries excluded), capped at ingestion time."""
    ingested = parse_ts(case.info.get("ingested_at_utc")) or datetime.now(timezone.utc)
    ts = [r.ts for r in case.timed if r.reliability == "recorded" and r.type != "calendar_event" and r.ts <= ingested]
    return max(ts) if ts else ingested


def _days_since(case, gaps, as_of):
    times = []
    for g in gaps:
        for c in g.citations:
            r = case.records.get(c.get("record_id"))
            if r and r.ts:
                times.append(r.ts)
    return (as_of - max(times)).days if times else None
