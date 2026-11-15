"""Insights: conclusions an investigator can check.

Each insight separates what the records show (observations, cited) from what follows from them
(inference), and lists unknowns, counter-evidence, assumptions and limitations. Confidence is a label
derived from how many independent sources agree. It is never stated as certainty.
"""

from __future__ import annotations

from .analytics import Context, case_tz
from .model import Item, stable_key


def confidence(independent: int, observed: bool, contested: bool) -> str:
    if contested:
        return "low" if independent < 3 else "medium"
    if independent >= 3 and observed:
        return "high"
    if independent >= 2:
        return "medium"
    return "low"


def _obs(case, rid, text=None) -> dict:
    r = case.records[rid]
    return {"text": text or f"{r.content[:140]}" + (f" @ {r.place}" if r.place else ""), "citations": [case.cite(rid)]}


def _compose(ins: dict) -> str:
    parts = ["Observed: " + " ".join(f"{o['text']}." for o in ins["observations"][:4])]
    parts.append("Inference: " + ins["inference"])
    if ins["counterevidence"]:
        parts.append("Against: " + "; ".join(ins["counterevidence"][:3]) + ".")
    if ins["unknowns"]:
        parts.append("Unknown: " + "; ".join(ins["unknowns"][:3]) + ".")
    return " ".join(parts)


def build(ctx: Context, independence, findings, contradictions, hypotheses, verdicts, episodes) -> list[Item]:
    case = ctx.case
    tz = case_tz(case)
    out = []

    def add(key, title, ins, cites, certainty, conf, score):
        ins["confidence"] = conf
        out.append(Item("insight", stable_key("ins", key), title, _compose(ins), certainty=certainty, score=score,
                        citations=cites, data=ins))

    # 1. statements that conflict with records
    for x in sorted(contradictions, key=lambda i: -i.score)[:4]:
        d = x.data
        conf_recs = d.get("conflicting_records", [])
        indep = independence.independent(conf_recs)
        obs = []
        if d.get("statement_record"):
            obs.append(_obs(case, d["statement_record"], f"Statement: \"{case.records[d['statement_record']].content[:150]}\""))
        obs += [_obs(case, r) for r in conf_recs[:3]]
        ins = {"observations": obs,
               "inference": ("The account and these records cannot both be right for that window."
                             if d["kind"] == "statement_vs_record" else
                             "These records cannot all describe the same person acting in person."),
               "unknowns": ["which side is wrong, and why"],
               "counterevidence": [f"{len(d.get('consistent_records', []))} record(s) are consistent with the statement"]
               if d.get("consistent_records") else [],
               "assumptions": ["records attributed through a credential, account or device identify its owner"]
               if "inferred" in d.get("attribution", []) else [],
               "limitations": d.get("possible_reasons", [])[:3], "basis": [x.key], "independent_sources": indep}
        add(x.key, x.title, ins, x.citations, "inferred",
            confidence(indep, "observed" in d.get("attribution", ["observed"]), contested=True), x.score)
    # 2. repeated proximity
    for f in sorted([f for f in findings if "same place" in f.title], key=lambda i: -i.score)[:2]:
        a, b = f.data["subjects"]
        rids = f.data["record_ids"]
        indep = independence.independent(rids)
        ins = {"observations": [{"text": f"{f.data['observations']} matching location observations on {len(f.data['days'])} days "
                                 f"({f.data['days'][0]} to {f.data['days'][-1]})", "citations": f.citations[:4]}],
               "inference": f"{case.name(a)} and {case.name(b)} were repeatedly close to each other, which suggests an association.",
               "unknowns": [f"who uses {case.name(x)}" for x in (a, b) if case.etype(x) != "person"] + ["what they did together"],
               "counterevidence": [], "assumptions": ["each phone was with its usual user"],
               "limitations": (["several matches use cell-site areas up to about 1.5 km wide; this shows proximity, "
                                "not a meeting"] if f.data.get("approximate") else []) + ["location follows phones, not people"],
               "basis": [f.key], "independent_sources": indep}
        add(f.key, f.title, ins, f.citations, "inferred", confidence(indep, False, contested=False), f.score)
    # 3. notable communications and unnamed parties
    for f in sorted([f for f in findings if f.title.startswith(("Communication", "Unidentified"))], key=lambda i: -i.score)[:3]:
        ins = {"observations": [{"text": f.text, "citations": f.citations[:4]}],
               "inference": ("A frequently contacted identifier has no name attached; identifying its user is a priority."
                             if f.title.startswith("Unidentified") else
                             "The pattern of this relationship (deletions, saved names, timing) is worth examining."),
               "unknowns": ["message content beyond what was recovered"], "counterevidence": [],
               "assumptions": [], "limitations": ["deletion and contact names show behaviour, not intent"],
               "basis": [f.key], "independent_sources": 1}
        add(f.key, f.title, ins, f.citations, "observed", "medium", f.score * 0.9)
    # 4. key events and what explains them
    hyp = {h.key: h for h in hypotheses}
    for v in verdicts:
        ep = next(e for e in episodes if e.key == v["episode"])
        ranked = [hyp[k] for k in v["ranked"] if k in hyp]
        obs = [{"text": ep.text, "citations": ep.citations[:4]}]
        ins = {"observations": obs,
               "inference": v["verdict"],
               "unknowns": ["who was physically present"] if not v["decided"] else [],
               "counterevidence": [f"{h.text} ({h.data['label']}): " + "; ".join(c["reason"] for c in h.data["contradicting"][:2])
                                   for h in ranked if h.data["contradicting"]][:3],
               "assumptions": sorted({a for h in ranked for a in h.data["assumptions"]})[:3],
               "limitations": ["explanations are scored on the records available; new evidence can change the ranking"],
               "explanations": [{"key": h.key, "statement": h.text, "label": h.data["label"], "points": h.data["points"]}
                                for h in ranked],
               "discriminating_evidence": v["discriminating_evidence"], "basis": [ep.key] + v["ranked"],
               "independent_sources": independence.independent(ep.data["record_ids"])}
        add("verdict-" + ep.key, f"What explains the {ep.title[0].lower() + ep.title[1:]}?", ins, ep.citations[:6], "inferred",
            "medium" if v["decided"] else "low", 0.85)
    # 5. strongest single anomalies outside the key events
    used = {k for e in episodes for k in e.data.get("findings", [])}
    for f in sorted([f for f in findings if f.title.startswith("Unusual event") and f.key not in used], key=lambda i: -i.score)[:2]:
        ins = {"observations": [{"text": f.text, "citations": f.citations}], "inference": "An unusual event worth a look; "
               "on its own it does not indicate wrongdoing.", "unknowns": ["whether it relates to the incident"],
               "counterevidence": [], "assumptions": [], "limitations": ["anomaly scores compare against this log's own history"],
               "basis": [f.key], "independent_sources": 1}
        add(f.key, f.title, ins, f.citations, "observed", "low", f.score * 0.6)
    return out
