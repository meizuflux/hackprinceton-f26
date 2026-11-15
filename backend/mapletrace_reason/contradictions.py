"""Contradictions: conflicts between statements and records, and between records themselves.

Every contradiction lists the conflicting records, the records that are consistent with the statement,
several possible reasons (honest error, approximate memory, shared credential, clock error, untruth),
and the evidence that would resolve it. It never concludes that someone lied.
"""

from __future__ import annotations

import re
from datetime import timedelta

from .analytics import _HOME, Context, _is_presence, case_tz
from .model import Item, stable_key
from .store import haversine_m, iso, parse_ts


def _home_coords(ctx: Context, pid: int, window=None):
    """Where 'home' is for a person, with the basis for that assumption:
    a labelled home in location history; else where their phone usually is between 1 and 5 am on other nights;
    else where it was when the claimed period began."""
    case = ctx.case
    mine = [r for r in case.records.values() if r.lat is not None and any(p == pid for p, _, _ in ctx.persons_for(r))]
    pts = [(r.lat, r.lon) for r in mine
           if r.type == "place_visit" and _HOME.search(" ".join([r.content, str(r.attrs.get("semanticType", ""))]))]
    if pts:
        return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)), "home as labelled in location history"
    tz = case_tz(case)
    ws, we = window or (None, None)
    nights = [(r.lat, r.lon) for r in mine if r.ts and 1 <= r.ts.astimezone(tz).hour < 5 and not (ws and ws <= r.ts <= we)]
    if len(nights) >= 3:
        grid = {}
        for la, lo in nights:
            grid.setdefault((round(la, 3), round(lo, 3)), []).append((la, lo))
        best = max(grid.values(), key=len)
        return (sum(p[0] for p in best) / len(best), sum(p[1] for p in best) / len(best)), \
            "home assumed to be where the phone usually is between 1 and 5 am on other nights"
    if ws:
        first = min((r for r in mine if r.ts and ws <= r.ts <= we), key=lambda r: r.ts, default=None)
        if first:
            return (first.lat, first.lon), "home assumed to be where the phone was at the start of the claimed period"
    return None, None


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (s or "").lower()) if t not in {"the", "a", "of", "at", "to", "in"}}


def _reasons(ctx: Context, claim_rec, conflicting, attribution_kinds) -> list[str]:
    tz = ctx.case.info.get("assumed_timezone", "UTC")
    out = []
    if claim_rec is not None and ("human_reported" in claim_rec.flags or claim_rec.start != claim_rec.end):
        out.append("The account is a recollection with an approximate time; the conflict may come from misremembering when things happened.")
    if "inferred" in attribution_kinds:
        out.append("Some conflicting records identify the person only through a credential, account or device; someone else may have used it.")
    if any("tz_assumed" in r.flags for r in conflicting):
        out.append(f"Some record times have no time zone and were read as {tz}; a wrong assumption would shift them by hours.")
    if any(r.type in ("place_visit", "location_fix", "movement", "call") for r in conflicting):
        out.append("Location records follow the phone, not the person; the phone may have been elsewhere.")
    out.append("The statement may be inaccurate or untrue. This is one possibility among the others, not a finding.")
    return out


def claim_conflicts(ctx: Context, claims: list[Item]) -> list[Item]:
    case = ctx.case
    tz = case_tz(case)
    items = []
    for cl in claims:
        d = cl.data
        if not d.get("window"):
            continue
        ws, we = parse_ts(d["window"][0]), parse_ts(d["window"][1])
        subj = d["subject"]
        claim_rec = case.records[d["record_id"]]
        recs = [r for r in case.timed if ws <= r.ts <= we and r.reliability == "recorded"]
        mine = [(r, cert, basis) for r in recs for p, cert, basis in ctx.persons_for(r) if p == subj]
        conflicting, consistent = [], []
        home_basis = None
        if d["claim_type"] == "location" and d["polarity"] and d["place"] == "home":
            home, home_basis = _home_coords(ctx, subj, (ws, we))
            for r, cert, basis in mine:
                at_home_visit = r.type == "place_visit" and _HOME.search(r.content + str(r.attrs.get("semanticType", "")))
                if at_home_visit:
                    consistent.append((r, cert, basis))
                elif r.lat is not None and home and haversine_m(r.lat, r.lon, *home) < 300:
                    consistent.append((r, cert, basis))
                elif (r.place and _is_presence(r)) or (r.lat is not None and home and haversine_m(r.lat, r.lon, *home) > 1000) \
                        or r.type in ("place_visit", "movement"):
                    conflicting.append((r, cert, basis))
        elif d["claim_type"] == "location" and not d["polarity"] and d["place"]:
            want = _tokens(d["place"])
            for r in case.timed:
                if r.reliability != "recorded" or not (r.place or r.content):
                    continue
                if not any(p == subj for p, _, _ in ctx.persons_for(r)):
                    continue
                have = _tokens(r.place or "") | _tokens(r.content if r.type == "place_visit" else "")
                if want and len(want & have) / len(want) >= 0.6:
                    conflicting.extend((r, c, b) for p, c, b in ctx.persons_for(r) if p == subj)
        elif d["claim_type"] == "contact" and d.get("counterpart"):
            other = d["counterpart"]
            for r in recs:
                if r.type in ("message", "call", "email"):
                    ents = {e for e, role in r.entities}
                    if subj in ents and other in ents:
                        conflicting.append((r, "observed", "communication record"))
        if not conflicting:
            continue
        conflicting.sort(key=lambda x: (x[1] != "observed", x[0].ts))
        crecs = [c[0] for c in conflicting]
        kinds = {c[1] for c in conflicting}
        severity = "high" if "observed" in kinds and len(conflicting) >= 2 else "medium"
        first = crecs[0]
        what = {"location": "where they were", "contact": "contact with " + case.name(d.get("counterpart") or 0)}[d["claim_type"]]
        items.append(Item(
            "contradiction", stable_key("x-claim", cl.key),
            f"{case.name(subj)}'s account of {what} conflicts with records",
            f"{case.name(subj)} said: \"{d['quote'][:160]}\". {len(conflicting)} record(s) in the same window disagree, e.g. at "
            f"{first.ts.astimezone(tz):%a %d %b %H:%M} {first.content[:70]}" + (f" @ {first.place}" if first.place else "")
            + (f" ({conflicting[0][2]})." if conflicting[0][2] else ".")
            + (f" {len(consistent)} record(s) are consistent with the statement." if consistent else ""),
            certainty="inferred", score=0.8 if severity == "high" else 0.6,
            citations=[cl.citations[0]] + [case.cite(r.id) for r in crecs[:5]],
            data={"kind": "statement_vs_record", "claim": cl.key, "subject": subj, "statement_record": d["record_id"],
                  "conflicting_records": [r.id for r in crecs[:50]], "consistent_records": [c[0].id for c in consistent[:20]],
                  "attribution": sorted(kinds), "severity": severity, "window": d["window"],
                  "assumptions": ([home_basis] if home_basis else []) + d.get("assumptions", []),
                  "possible_reasons": _reasons(ctx, claim_rec, crecs, kinds)
                  + ([f"The home location is an assumption ({home_basis})."] if home_basis and "labelled" not in home_basis else []),
                  "resolving_evidence": ["cctv_review", "phone_location", "follow_up_interview"]
                  + (["device_forensics"] if d["claim_type"] == "contact" else [])}))
    return items


def record_conflicts(ctx: Context, findings: list[Item], groups) -> list[Item]:
    """Records that disagree with each other: one person in two places, or one event with two times."""
    case = ctx.case
    items = []
    for f in findings:
        if "two places" not in f.title:
            continue
        rids = f.data["record_ids"]
        recs = [case.records[r] for r in rids]
        kinds = {c for r in recs for p, c, _ in ctx.persons_for(r) if p == f.data["person"]}
        items.append(Item(
            "contradiction", stable_key("x-presence", f.key), f.title, f.text, certainty="inferred", score=f.score,
            citations=f.citations,
            data={"kind": "record_vs_record", "finding": f.key, "subject": f.data["person"], "conflicting_records": rids,
                  "consistent_records": [], "severity": "high" if f.data.get("biometric") else "medium",
                  "possible_reasons": [
                      "A credential, account or device was used by someone other than its owner.",
                      "The two places are closer than they look (adjacent rooms or a remote session).",
                      "One of the systems has a clock offset.",
                  ] + _reasons(ctx, None, recs, kinds)[1:-1],
                  "resolving_evidence": ["cctv_review", "access_system_audit", "device_forensics"]}))
    for g in groups:
        ms = [case.records[m] for m in g.data["members"] if case.records[m].ts]
        if len(ms) < 2:
            continue
        spread = (max(r.ts for r in ms) - min(r.ts for r in ms)).total_seconds()
        if spread > 120:
            items.append(Item(
                "contradiction", stable_key("x-time", g.key), "One event recorded with different times",
                f"{len(ms)} copies of the same information disagree on time by {spread / 60:.0f} minutes. Likely a clock "
                f"offset or time-zone difference between sources.", certainty="observed", score=0.4,
                citations=[case.cite(r.id) for r in ms[:4]],
                data={"kind": "timestamp_conflict", "conflicting_records": [r.id for r in ms], "consistent_records": [],
                      "severity": "low", "possible_reasons": ["Clock offset between systems.", "Different time-zone handling.",
                                                              "The copies describe two similar but separate events."],
                      "resolving_evidence": ["system_clock_check"]}))
    return items
