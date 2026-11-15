"""Gaps: directed investigative questions the evidence cannot answer.

Each question is asked of the data. If it can't be answered, the gap records why it matters, what is
missing, a concrete direction, and the artifacts that could close it. Gap types are kept distinct:

  missing            no source covers it
  failed_extraction  the evidence exists but could not be read or has not been analysed
  conflicting        sources disagree
  uncertain          evidence exists but does not settle it (approximate, indirect, or only a credential)
"""

from __future__ import annotations

from datetime import timedelta

from .analytics import _BIOMETRIC, Context, _same_place, case_tz
from .model import Item, stable_key
from .store import parse_ts


def _gap(question, gtype, why, missing, direction, artifacts, priority, citations, affected, status="open", answer=None,
         key_parts=()):
    return Item("gap", stable_key("gap", *key_parts) if key_parts else stable_key("gap", question), question, why,
                certainty="unknown", score=round(priority, 2), citations=citations, status=status,
                data={"gap_type": gtype, "why_it_matters": why, "missing": missing, "direction": direction,
                      "artifacts": artifacts, "affected": affected, "answer": answer, "question": question})


def find_gaps(ctx: Context, episodes, findings, contradictions, hypotheses, verdicts, missing_periods) -> list[Item]:
    case = ctx.case
    tz = case_tz(case)
    gaps = []
    videos = [r for r in case.records.values() if r.type == "media_capture" and r.attrs.get("media_kind") == "video"]
    hyp_by_ep = {}
    for h in hypotheses:
        hyp_by_ep.setdefault(h.data["episode"], []).append(h)
    for ep in episodes[:2]:
        ws, we = parse_ts(ep.data["start"]), parse_ts(ep.data["end"])
        when = f"{ws.astimezone(tz):%a %d %b %H:%M}–{we.astimezone(tz):%H:%M}"
        place = (ep.data.get("places") or ["the scene"])[0]
        hyps = hyp_by_ep.get(ep.key, [])
        affected = [h.key for h in hyps]
        # Q1: who was physically there?
        v = next((v for v in verdicts if v["episode"] == ep.key), {})
        scene = v.get("target_places") or ep.data.get("places", [])[:1]
        place = v.get("place") or place
        identity = [r for r in case.timed if ws <= r.ts <= we and r.reliability == "recorded"
                    and _BIOMETRIC.search(" ".join(map(str, r.attrs.values())))
                    and any(_same_place(r.place or "", p) for p in scene)]
        vids = [v for v in videos if v.start and v.end and v.start <= we and v.end >= ws]
        conflicts = [x for x in contradictions if x.data.get("kind") == "record_vs_record"
                     and any(r in set(ep.data["record_ids"]) for r in x.data.get("conflicting_records", []))]
        if not identity:
            if conflicts:
                gtype, missing = "conflicting", "records disagree about whose credential or account was used where"
            elif vids:
                gtype = "failed_extraction"
                missing = (f"{len(vids)} video file(s) overlap this window but their content has not been analysed; "
                           "only access logs identify anyone, and they identify credentials, not people")
            else:
                gtype, missing = "uncertain", "only credential or account records, which identify a card or login, not a person"
            arts = [{"artifact": "cctv_review", "params": {"place": case.place_name(place), "window": when}}]
            if vids:
                arts.insert(0, {"artifact": "media_analysis", "params": {"files": [case.files[v.file_id]["original_path"] for v in vids]}})
            arts.append({"artifact": "forensic_lab", "params": {"place": case.place_name(place)}})
            gaps.append(_gap(
                f"Who was physically at {case.place_name(place)} during the key event ({when})?", gtype,
                f"Every explanation of the key event depends on who was actually there. It affects {len(hyps)} competing "
                f"explanation(s).", missing,
                f"Identify the people at {case.place_name(place)} between {when}: review camera coverage of the approach routes and the room, "
                f"and compare with credential holders.", arts, 0.95,
                ep.citations[:4] + [case.cite(v.id) for v in vids[:2]], affected, key_parts=("who-present", ep.key)))
        # Q2: where was each person of interest?
        for h in hyps:
            p = h.data.get("subject")
            if h.data["kind"] != "present" or not p or case.etype(p) != "person":
                continue
            locs = [r for r in case.timed if ws <= r.ts <= we and r.type in ("place_visit", "location_fix", "movement")
                    and any(q == p for q, _, _ in ctx.persons_for(r))]
            confl = [x for x in contradictions if x.data.get("subject") == p]
            if confl:
                gtype, status = "conflicting", "partially_resolved" if locs else "open"
                missing = "records disagree with each other or with the person's own account"
            elif locs:
                continue
            else:
                gtype, status, missing = "missing", "open", "no location record for this person in the window"
            gaps.append(_gap(
                f"Where was {case.name(p)} during {when}?", gtype,
                f"Decides between '{h.text}' and the alternatives.", missing,
                f"Obtain an independent location source for {case.name(p)} covering {when} and put the conflicting records "
                f"to them in a follow-up interview.",
                [{"artifact": "phone_location", "params": {"person": case.name(p), "window": when}},
                 {"artifact": "cctv_review", "params": {"place": case.place_name(place), "window": when}},
                 {"artifact": "follow_up_interview", "params": {"person": case.name(p), "topic": f"whereabouts {when}"}}],
                0.85, [c for x in confl[:2] for c in x.citations[:2]] or h.citations[:2], [h.key] + [x.key for x in confl],
                status=status, key_parts=("whereabouts", ep.key, case.name(p))))
    # Q3: explanations the evidence cannot separate. Cites the records behind the leading explanations it asks about.
    hyp_by_key = {h.key: h for h in hypotheses}
    for v in verdicts:
        if not v["decided"]:
            leading = [hyp_by_key[k] for k in v["ranked"][:3] if k in hyp_by_key]
            cites = list({c["id"]: c for h in leading for c in h.citations[:3]}.values())
            gaps.append(_gap(
                f"Which explanation of the {v['episode_title'][0].lower() + v['episode_title'][1:]} fits the evidence?", "uncertain",
                "Several explanations remain plausible; acting on the wrong one risks a wrong conclusion.",
                "no evidence yet distinguishes the leading explanations", v["verdict"],
                [{"artifact": d["artifact"], "params": d["params"], "why": d["why"]} for d in v["discriminating_evidence"]],
                0.9, cites, v["ranked"][:3], key_parts=("which-explanation", v["episode"])))
    # Q4: unidentified parties
    unidentified = sorted((f for f in findings if f.title.startswith("Unidentified party")), key=lambda f: -f.data["count"])[:3]
    for f in unidentified:
        eid = f.data["entity"]
        mentions = [r for r in case.records.values() if any(e == eid and role == "mentioned" for e, role in r.entities)
                    and r.type in ("document_chunk", "email", "statement_claim", "interview_turn", "lab_note")]
        named = [r for r in mentions if any(case.etype(e) == "person" for e, role in r.entities if role == "mentioned")]
        status, answer = ("partially_resolved", f"{len(named)} document(s) mention this identifier next to a named person; "
                          "the link is not confirmed by an official record") if named else ("open", None)
        gaps.append(_gap(
            f"Who uses {case.name(eid)}?", "uncertain" if named else "missing",
            f"{case.name(eid)} is in heavy contact with {', '.join(case.name(p) for p in f.data['partners'])}; its user may be "
            "a key participant.", "an official record tying the identifier to a person",
            f"Request subscriber and billing records for {case.name(eid)} and compare names, addresses and payment details "
            "with people in the case.",
            [{"artifact": "subscriber_records", "params": {"identifier": case.name(eid)}},
             {"artifact": "device_forensics", "params": {"person": ", ".join(case.name(p) for p in f.data['partners'])}}],
            0.8, f.citations[:2] + [case.cite(r.id) for r in named[:2]], [f.key], status=status, answer=answer,
            key_parts=("who-uses", case.name(eid))))
    # Q5: statements that conflict with records
    for x in contradictions:
        if x.data.get("kind") != "statement_vs_record":
            continue
        p = x.data["subject"]
        gaps.append(_gap(
            f"Is {case.name(p)}'s account accurate?", "conflicting",
            "An account that conflicts with records changes how much weight the rest of that person's statement can carry.",
            "an explanation for the discrepancy", "Put the specific conflicting records to the person; check the "
            "alternative reasons listed with the contradiction (time error, shared device, clock offset).",
            [{"artifact": "follow_up_interview", "params": {"person": case.name(p), "topic": "the conflicting records"}},
             {"artifact": "phone_location", "params": {"person": case.name(p), "window": x.data.get("window")}}],
            0.7, x.citations[:3], [x.key], key_parts=("account", x.key)))
    # Q6: evidence that could not be read
    for fid, fl in case.files.items():
        if fl["parse_status"] in ("failed", "unsupported", "partial") and fl["evidence_type"] not in ("empty", "case_manifest"):
            gaps.append(_gap(
                f"What does {fl['original_path'].rsplit('/', 1)[-1]} contain?", "failed_extraction",
                "Evidence that was submitted but could not be read may hold relevant facts.",
                f"the file could not be parsed ({fl['type_reason'] or fl['parse_status']})",
                "Obtain a readable copy or use a tool that supports this format; the original is preserved and hashed.",
                [{"artifact": "file_recovery", "params": {"file": fl["original_path"]}}], 0.4, [], [],
                key_parts=("unreadable", fl["original_path"])))
    # Q7: people unaccounted for around the key event
    for m in missing_periods:
        if m.data.get("kind") != "unaccounted_person":
            continue
        p = m.data["person"]
        gaps.append(_gap(
            f"Where was {case.name(p)} {m.title.split(case.name(p))[-1].strip()}?", "missing",
            "Unknown whereabouts around the key event leave room for several explanations.", "any record placing them",
            f"Check location, card and access records for {case.name(p)} in that window.",
            [{"artifact": "phone_location", "params": {"person": case.name(p), "window": f"{m.data['start']} – {m.data['end']}"}},
             {"artifact": "financial_records", "params": {"person": case.name(p), "window": f"{m.data['start']} – {m.data['end']}"}}],
            0.5, m.citations[:2], [m.key], key_parts=("unaccounted", m.key)))
    return gaps
