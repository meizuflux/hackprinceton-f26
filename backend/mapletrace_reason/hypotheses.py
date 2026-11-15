"""Competing explanations for each key event.

For every key event the engine proposes several explanations, then scores each against the evidence:
supporting and contradicting records, weighted by how directly they identify a person and counted by
independent origin. It names the evidence that would tell the explanations apart, and returns
"insufficient evidence" instead of forcing a conclusion when no explanation clearly leads.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from .analytics import _BIOMETRIC, _HOME, Context, _is_device_place, _is_presence, _same_place, case_tz
from .model import Item, stable_key
from .store import parse_ts

LABELS = [(4.0, "best supported"), (2.0, "plausible"), (0.01, "weakly supported"), (-99, "contradicted")]


def _label(points: float, independent: int) -> str:
    for threshold, label in LABELS:
        if points >= threshold:
            if label == "best supported" and independent < 2:
                return "plausible"
            return label
    return "contradicted"


def explanations(ctx: Context, episodes: list[Item], findings: list[Item], contradictions: list[Item], independence,
                 max_episodes: int = 2) -> tuple[list[Item], list[dict]]:
    case = ctx.case
    tz = case_tz(case)
    comms = [f for f in findings if f.key and f.title.startswith("Communication")]
    coloc = [f for f in findings if "same place" in f.title]
    concurrent = [f for f in findings if "two places" in f.title]
    drift_files = {fid for fid, f in case.files.items() if "drift" in str(f["manifest"].get("time_basis", "")).lower()}
    items, verdicts = [], []
    for ep in episodes[:max_episodes]:
        ws, we = parse_ts(ep.data["start"]), parse_ts(ep.data["end"])
        place = (ep.data.get("places") or ["the scene"])[0]
        when = f"{ws.astimezone(tz):%a %d %b %H:%M}–{we.astimezone(tz):%H:%M}"
        window_recs = [r for r in case.timed if ws <= r.ts <= we and r.reliability == "recorded"]
        direct = defaultdict(list)  # person -> [(rec, certainty, basis)]
        for r in window_recs:
            for p, cert, basis in ctx.persons_for(r):
                if case.etype(p) == "person":
                    direct[p].append((r, cert, basis))
        associates = set()
        for p in list(direct):
            for f in comms + coloc:
                pair = f.data.get("pair") or f.data.get("subjects") or []
                if p in pair:
                    associates |= {q for q in pair if q != p}
        hyps = []

        def hyp(kind, subject, statement):
            return {"kind": kind, "subject": subject, "statement": statement, "support": [], "against": [], "assumptions": []}

        # the key moment and the place(s) where the unusual activity happened (workstations excluded)
        key_t = parse_ts(ep.data.get("key_time")) or ws
        core = [r for r in window_recs if abs((r.ts - key_t).total_seconds()) <= 600]
        targets = {r.place for r in core if r.place and not _is_device_place(r) and r.id in set(ep.data["record_ids"])}
        targets = targets or set(ep.data.get("places", [])[:1])
        place = next((pl for pl in ep.data.get("places", []) if pl in targets), place)

        def at_target(r):
            return bool(r.place) and (r.place in targets or any(_same_place(r.place, t) for t in targets))

        def bio(r):
            return bool(_BIOMETRIC.search(" ".join(map(str, r.attrs.values()))))

        candidates = [p for p, recs in direct.items() if any(at_target(r) for r, _, _ in recs)]
        for p in sorted(candidates, key=lambda q: -len(direct[q]))[:3]:
            recs = direct[p]
            here = [(r, c, b) for r, c, b in recs if at_target(r)]
            elsewhere = [(r, c, b) for r, c, b in recs if not at_target(r) and r.place
                         and abs((r.ts - key_t).total_seconds()) <= 180 and _is_presence(r)]
            homes = [r for r in window_recs if r.type == "place_visit" and any(q == p for q, _, _ in ctx.persons_for(r))
                     and _HOME.search(r.content + str(r.attrs.get("semanticType", "")))]
            h = hyp("present", p, f"{case.name(p)} was physically at {case.place_name(place)} at the key moment "
                                  f"({key_t.astimezone(tz):%a %d %b %H:%M}).")
            for r, cert, basis in here:
                w = 2.0 if (cert == "observed" or bio(r)) else 1.0
                h["support"].append((r.id, f"{r.content[:60]} @ {case.place_name(r.place)} ({basis}{', biometric' if bio(r) else ''})", w))
            for r, cert, basis in elsewhere[:4]:
                h["against"].append((r.id, f"at the same time, {r.content[:50]} @ {case.place_name(r.place)} ({basis}"
                                           f"{', biometric' if bio(r) else ''})", 2.0 if bio(r) else 1.0))
            for r in homes[:1]:
                h["against"].append((r.id, f"location history: {case.name(p)}'s phone at home", 2.0))
            for x in contradictions:
                if x.data.get("subject") == p and x.data.get("kind") == "statement_vs_record":
                    h["support"].append((x.data["statement_record"], "their own account of that night conflicts with records "
                                         "(weak: an inaccurate account is not proof of presence)", 0.5))
            h["assumptions"].append("a credential record identifies the cardholder unless shown otherwise")
            hyps.append(h)
            if elsewhere or homes or any(c == "inferred" for _, c, _ in here) or \
                    any(f.data.get("person") == p for f in concurrent):
                h2 = hyp("credential", p, f"Someone else used {case.name(p)}'s credential at {case.place_name(place)} while {case.name(p)} "
                                          f"was elsewhere.")
                for r, cert, basis in elsewhere[:3]:
                    h2["support"].append((r.id, f"{case.name(p)} recorded at {case.place_name(r.place)} at the key moment"
                                                f"{' (biometric)' if bio(r) else ''}", 2.0 if bio(r) else 1.0))
                for r in homes[:1]:
                    h2["support"].append((r.id, f"location history: {case.name(p)}'s phone at home", 1.5))
                for f in concurrent:
                    if f.data.get("person") == p and ws <= parse_ts(f.data["time"]) <= we:
                        h2["support"].append((f.data["record_ids"][0], "the same identity is recorded in two places at once", 1.0))
                for r, cert, basis in here:
                    if bio(r):
                        h2["against"].append((r.id, "a biometric sign-in at the scene ties the owner to it", 2.0))
                h2["assumptions"].append("a credential can be shared, borrowed or stolen")
                hyps.append(h2)
        for q in sorted(associates - set(direct))[:2]:
            if case.etype(q) not in ("person", "phone"):
                continue
            h = hyp("associate", q, f"{case.name(q)} took part alongside {', '.join(case.name(p) for p in list(direct)[:1])}.")
            leads = [p for p in direct if p in candidates] or list(direct)
            for f in comms + coloc:
                pair = f.data.get("pair") or f.data.get("subjects") or []
                if q in pair and any(p in pair for p in leads):
                    h["support"].append((f.data.get("record_ids", [None])[0], f.title, 1.0))
            near = [r for r in case.timed if ws - timedelta(hours=6) <= r.ts <= we + timedelta(hours=6)
                    and r.type in ("message", "call") and q in {e for e, _ in r.entities}]
            if near:
                h["support"].append((near[0].id, f"{len(near)} messages/calls within 6 h of the key event", 1.0))
            h["cap"] = 3.0 if not near else 4.5  # association alone never makes participation 'best supported'
            h["assumptions"].append("contact or proximity shows association, not participation")
            hyps.append(h)
        herr = hyp("error", None, "The unusual records reflect system or clock errors rather than real activity.")
        for r in window_recs:
            if r.file_id in drift_files:
                herr["support"].append((r.id, "this log has a documented clock drift", 0.5))
                break
        origins = independence.independent([r.id for r in window_recs if r.id in set(ep.data["record_ids"])])
        if origins >= 2:
            herr["against"].append((ep.data["record_ids"][0], f"{origins} independent systems recorded the activity", 2.0))
        hyps.append(herr)

        scored = []
        for h in hyps:
            sup = [s for s in h["support"] if s[0]]
            ag = [a for a in h["against"] if a[0]]
            points = sum(w for _, _, w in sup) - sum(w for _, _, w in ag)
            indep = independence.independent([s[0] for s in sup]) if sup else 0
            points = min(points, 2.0 + 1.5 * indep, h.get("cap", 99))  # one system's records don't add up indefinitely
            status = _label(points, indep)
            cites = [case.cite(rid) for rid, _, _ in (sup + ag)[:8]]
            it = Item("hypothesis", stable_key("hyp", ep.key, h["kind"], case.name(h["subject"]) if h["subject"] else ""),
                      h["statement"][:90], h["statement"], certainty="inferred",
                      score=round(max(0.0, min(1.0, (points + 2) / 8)), 2), citations=cites,
                      data={"episode": ep.key, "kind": h["kind"], "subject": h["subject"], "points": round(points, 2),
                            "independent_support": indep, "label": status,
                            "supporting": [{"record_id": rid, "reason": why, "weight": w} for rid, why, w in sup[:12]],
                            "contradicting": [{"record_id": rid, "reason": why, "weight": w} for rid, why, w in ag[:12]],
                            "assumptions": h["assumptions"]})
            scored.append(it)
        scored.sort(key=lambda i: -i.data["points"])
        top = scored[0]
        second = scored[1] if len(scored) > 1 else None
        decided = top.data["label"] == "best supported" and (not second or top.data["points"] - second.data["points"] >= 2)
        discriminators = _discriminators(case, scored[:3], place, when, ep)
        verdicts.append({"episode": ep.key, "episode_title": ep.title, "key_time": ep.data.get("key_time"),
                         "target_places": sorted(targets), "place": place,
                         "verdict": (f"Best supported: {top.text}" if decided else
                                     "Insufficient evidence to choose between: " + "; ".join(s.text for s in scored[:3])),
                         "decided": decided, "ranked": [s.key for s in scored], "discriminating_evidence": discriminators})
        items.extend(scored)
    return items, verdicts


def _discriminators(case, top, place, when, ep) -> list[dict]:
    kinds = {h.data["kind"] for h in top}
    subj = [h.data["subject"] for h in top if h.data["subject"]]
    out = []
    if "present" in kinds or "credential" in kinds:
        out.append({"artifact": "cctv_review", "why": f"shows who was physically at {case.place_name(place)} ({when}), which separates "
                    "presence from use of someone else's credential", "params": {"place": case.place_name(place), "window": when}})
    for p in subj[:2]:
        out.append({"artifact": "phone_location", "why": f"places {case.name(p)}'s phone during {when}; consistent location "
                    "elsewhere supports the shared-credential explanation", "params": {"person": case.name(p), "window": when}})
    if "associate" in kinds:
        out.append({"artifact": "device_forensics", "why": "message content and deleted data around the event show coordination "
                    "or its absence", "params": {"window": when}})
    if "error" in kinds:
        out.append({"artifact": "system_clock_check", "why": "confirms whether system clocks were accurate, ruling the error "
                    "explanation in or out", "params": {"systems": ep.data.get("places", [])[:3]}})
    out.append({"artifact": "forensic_lab", "why": f"DNA or fingerprints on the objects at {case.place_name(place)} can identify who touched them",
                "params": {"place": case.place_name(place)}})
    return out
