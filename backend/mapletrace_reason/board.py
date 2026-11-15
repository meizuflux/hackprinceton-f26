"""Adapter from analysis results to the investigation board.

Produces the frontend's `CaseData` shape (frontend/src/api/types.ts) plus extra fields the board can use
as it grows: certainty (observed vs inferred), contradictions, explanations, timeline, uncertain times,
missing periods, source groups, changes and overrides. The backend is authoritative: the frontend adapts
to these fields.
"""

from __future__ import annotations

import math

from . import media as media_mod
from .analytics import case_tz
from .store import iso

NODE_TYPE = {"person": "person", "phone": "device", "email": "device", "device": "device", "account": "device",
             "sample": "device"}
COLUMNS = {"event": 0, "person": 1, "device": 2, "location": 3, "statement": 4}
NODE_CITATIONS = 12
# Relations with a real direction (source -> target). Everything else (communication, co-location, identity) is
# symmetric and drawn without an arrowhead.
DIRECTED = {("claim", "stated"), ("contradicts", "conflicts with"), ("spatial", "occurred at"), ("temporal", "recorded at")}


def build_board(case, ctx, R, verdicts, timeline, changes, overrides, extras) -> dict:
    sources: dict[str, dict] = {}

    def src(c: dict) -> str:
        cid = c["id"]
        if cid not in sources:
            r = case.records.get(c["record_id"])
            f = case.files[r.file_id] if r else {}
            meta = {"evidence_id": c["evidence_id"], "locator": c["locator"], "record_type": r.type if r else "",
                    "reliability": r.reliability if r else "", "file_type": f.get("evidence_type") or "",
                    "time_precision": r.precision if r else "", "time_flags": ", ".join(r.flags) if r else "",
                    "who": ", ".join(case.name(p) for p, _, _ in ctx.persons_for(r)) if r else ""}
            sources[cid] = {"id": cid, "path": c["path"], "kind": r.type if r else "file",
                            "timestamp": iso(r.ts or r.start) if r and (r.ts or r.start) else "",
                            "hash": c["sha256"], "excerpt": (r.content if r else "")[:1200],
                            "metadata": {k: str(v) for k, v in meta.items() if v not in (None, "")}}
        return cid

    def cites(item_or_list) -> list[str]:
        lst = item_or_list.citations if hasattr(item_or_list, "citations") else item_or_list
        return list(dict.fromkeys(src(c) for c in lst))

    nodes: dict[str, dict] = {}
    edges: dict[str, dict] = {}

    def node(nid, ntype, label, citations, summary="", subtitle="", time=None, certainty="observed", extra=None,
             origin="record", stage="ingest"):
        if nid not in nodes:
            nodes[nid] = {"id": nid, "type": ntype, "label": label[:60], "citations": citations, "position": {"x": 0, "y": 0},
                          "summary": summary[:400], "subtitle": subtitle[:80], "certainty": certainty,
                          "origin": origin, "stage": stage, **(extra or {})}
            if time:
                nodes[nid]["time"] = time
        else:
            nodes[nid]["citations"] = list(dict.fromkeys(nodes[nid]["citations"] + citations))[:NODE_CITATIONS]
        return nid

    def ent_node(eid):
        t = NODE_TYPE.get(case.etype(eid), "device")
        return node(f"ent-{eid}", t, case.name(eid), [], subtitle=case.etype(eid))

    def edge(a, b, etype, label, citations, certainty, basis="", origin="rules", stage="findings"):
        eid = f"{etype}:{a}:{b}"
        if eid not in edges and a in nodes and b in nodes and a != b:
            edges[eid] = {"id": eid, "source": a, "target": b, "type": etype, "label": label[:60],
                          "citations": citations[:8], "certainty": certainty, "basis": basis[:200],
                          "directed": (etype, label) in DIRECTED, "origin": origin, "stage": stage}

    # key events and the places/people in them
    for ep in R.get("episode"):
        en = node(f"ev-{ep.key}", "event", ep.title, cites(ep), ep.text, "key event", ep.data["start"], "observed",
                  {"key": ep.key, "score": ep.score}, "rules", "key_events")
        for pl in ep.data.get("places", [])[:4]:
            ln = node(f"loc-{pl}", "location", pl, [], subtitle="place")
            recs = [r for r in ep.data["record_ids"] if case.records[r].place == pl][:3]
            edge(en, ln, "spatial", "occurred at", [src(case.cite(r)) for r in recs], "observed", stage="key_events")
        for p in ep.data.get("persons", [])[:6]:
            pn = ent_node(p)
            recs = [r for r in ep.data["record_ids"] if any(q == p for q, _, _ in ctx.persons_for(case.records[r]))]
            cert = "observed" if any(c == "observed" for r in recs for q, c, _ in ctx.persons_for(case.records[r]) if q == p) else "inferred"
            basis = "; ".join(sorted({b for r in recs for q, _, b in ctx.persons_for(case.records[r]) if q == p}))[:200]
            edge(pn, en, "temporal", "recorded at", [src(case.cite(r)) for r in recs[:4]], cert, basis, stage="key_events")
    # findings: anomalies, concurrent presence, co-location, communications
    for f in R.get("finding"):
        if f.title.startswith("Unusual event") or "two places" in f.title:
            fn = node(f"ev-{f.key}", "event", f.title.replace("Unusual event: ", ""), cites(f), f.text,
                      "unusual event" if f.title.startswith("Unusual") else "conflict", f.data.get("time"), f.certainty,
                      {"key": f.key, "score": f.score}, "rules", "findings")
            for p, c, b in f.data.get("persons", []) or ([[f.data["person"], "inferred", ""]] if f.data.get("person") else []):
                edge(ent_node(p), fn, "temporal", "recorded at", cites(f)[:2], c, b)
            if f.data.get("place"):
                edge(fn, node(f"loc-{f.data['place']}", "location", f.data["place"], [], subtitle="place"), "spatial",
                     "occurred at", cites(f)[:1], "observed")
        elif "same place" in f.title:
            a, b = f.data["subjects"]
            edge(ent_node(a), ent_node(b), "spatial", f"co-located on {len(f.data['days'])} days", cites(f), "inferred",
                 f.text)
        elif f.title.startswith("Communication"):
            a, b = f.data["pair"]
            edge(ent_node(a), ent_node(b), "communication", f"{f.data['count']} messages/calls", cites(f), "observed", f.text)
        elif f.title.startswith("Unidentified"):
            node(ent_node(f.data["entity"]), "device", "", cites(f))
            nodes[f"ent-{f.data['entity']}"]["summary"] = f.text
    for c in R.get("connection"):
        d = c.data
        if d.get("edge") == "alias" and d.get("target_entity"):
            edge(ent_node(d["source"]), ent_node(d["target_entity"]), "identity", "probably the same", cites(c), "inferred", c.text,
                 stage="connections")
        elif d.get("edge") == "alias" and d.get("entity_a"):
            edge(ent_node(d["entity_a"]), ent_node(d["entity_b"]), "identity", "may be the same", cites(c), "inferred", c.text,
                 stage="connections")
    # ML identity signals: only between people already on the board, so the layout of existing nodes is unchanged
    for s in R.get("signal"):
        if s.data.get("signal_type") == "identity_cluster":
            a, b = f"ent-{s.data['entity_a']}", f"ent-{s.data['entity_b']}"
            if a in nodes and b in nodes:
                edge(a, b, "identity", "may be the same (ML)", cites(s), "inferred", s.text, origin="ml",
                     stage="ml_signals")
    # statements and contradictions
    for x in R.get("contradiction"):
        d = x.data
        if d.get("statement_record"):
            sn = node(f"st-{d['statement_record']}", "statement", case.records[d["statement_record"]].content[:60],
                      [src(case.cite(d["statement_record"]))], case.records[d["statement_record"]].content, "statement",
                      iso(case.records[d["statement_record"]].ts), "observed")
            if d.get("subject"):
                edge(ent_node(d["subject"]), sn, "claim", "stated", [src(case.cite(d["statement_record"]))], "observed",
                     origin="record", stage="ingest")
            target = next((f"ev-{e.key}" for e in R.get("episode")
                           if set(d.get("conflicting_records", [])) & set(e.data["record_ids"])), None)
            if not target and d.get("conflicting_records"):
                r = case.records[d["conflicting_records"][0]]
                target = node(f"rec-{r.id}", "event", r.content[:60], [src(case.cite(r.id))], r.content, "record", iso(r.ts))
            if target:
                llm_claim = any(str(c.data.get("extraction", "")).startswith("llm:") and c.data.get("record_id") == d["statement_record"]
                                for c in R.get("claim"))
                edge(sn, target, "contradicts", "conflicts with", cites(x), "inferred", x.text,
                     origin="llm" if llm_claim else "rules", stage="claims" if llm_claim else "contradictions")
    _cite_from_edges(nodes, edges)
    # entities and places no edge cites: the records that name them (never an invented citation)
    for nid, n in nodes.items():
        if n["citations"]:
            continue
        if nid.startswith("ent-"):
            eid = int(nid[4:])
            rids = [r.id for r in case.timed if any(e == eid for e, _ in r.entities)][:NODE_CITATIONS] or \
                   sorted(r.id for r in case.records.values() if any(e == eid for e, _ in r.entities))[:NODE_CITATIONS]
        elif nid.startswith("loc-"):
            rids = [r.id for r in case.timed if r.place == nid[4:]][:NODE_CITATIONS]
        else:
            rids = []
        n["citations"] = [src(case.cite(r)) for r in rids]
    # gaps hang off the nodes they concern
    gap_nodes = _gap_nodes(case, R, nodes)
    for g in sorted(R.get("gap"), key=lambda g: -g.score):
        for nid in gap_nodes[g.id]:
            nodes[nid].setdefault("gapId", g.id)
    _signal_and_insight_nodes(case, R, nodes, edges, cites)
    # photos and video go on last: nothing above (gaps, leads) changes, and media never feeds the reasoning
    extras["media_stats"] = media_mod.add_media(case, R, nodes, edges, src, extras.get("vision"))
    for obj in [*nodes.values(), *edges.values()]:
        obj["evidenceIds"] = list(dict.fromkeys(c.split(":", 1)[0] for c in obj["citations"]))
    _layout(nodes)

    item_title = {it.key: f"{it.id} {it.title}" for b in R.items.values() for it in b}
    board = {
        "id": case.info.get("case_name", "case").lower().replace(" ", "-")[:60],
        "title": case.info.get("case_name", "Case"),
        "subtitle": f"{len(case.files)} files · {len(case.records)} records · analysed {extras['analysed_at']}",
        "timezone": getattr(case_tz(case), "key", "UTC"),
        "timeRange": {"start": timeline[0]["time"] if timeline else "", "end": timeline[-1]["time"] if timeline else ""},
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "gaps": [{"id": g.id, "title": g.title,
                  "description": f"{g.data['why_it_matters']} Missing: {g.data['missing']}. Next: {g.data['direction']}",
                  "score": g.score, "affectedClaims": [item_title.get(k, k) for k in g.data.get("affected", [])],
                  "nodeIds": gap_nodes[g.id],
                  "suggestedEvidence": [a["artifact"] for a in g.data["artifacts"]], "citations": cites(g),
                  "gapType": g.data["gap_type"], "status": g.status, "direction": g.data["direction"],
                  "missing": g.data["missing"], "whyItMatters": g.data["why_it_matters"],
                  "answer": g.data.get("answer"), "key": g.key,
                  "previousStatus": g.data.get("previous_status")} for g in R.get("gap")],
        "insights": [{"id": i.id, "title": i.title, "text": i.text, "score": i.score, "citations": cites(i),
                      "certainty": i.certainty, "confidence": i.data.get("confidence"), "status": i.status,
                      "origin": _insight_origin(i),
                      "observations": [{"text": o["text"], "citations": cites(o["citations"])} for o in i.data["observations"]],
                      "inference": i.data["inference"], "unknowns": i.data["unknowns"],
                      "counterevidence": i.data["counterevidence"], "assumptions": i.data["assumptions"],
                      "limitations": i.data["limitations"], "key": i.key,
                      **({"explanations": i.data["explanations"]} if "explanations" in i.data else {})} for i in R.get("insight")],
        "suggestions": [{"id": s.id, "title": s.title, "description": " · ".join(s.data["reasons"]), "priority": s.data["priority"],
                         "query": s.data["query"], "citations": cites(s),
                         "gapId": next((g.id for g in R.get("gap") if g.key in s.data["gaps"]), ""),
                         "gapIds": [g.id for g in R.get("gap") if g.key in s.data["gaps"]], "artifact": s.data["artifact"],
                         "score": s.score, "key": s.key} for s in R.get("suggestion")],
        "contradictions": [{"id": x.id, "title": x.title, "text": x.text, "severity": x.data["severity"], "kind": x.data["kind"],
                            "possibleReasons": x.data["possible_reasons"], "resolvingEvidence": x.data["resolving_evidence"],
                            "citations": cites(x), "status": x.status, "key": x.key} for x in R.get("contradiction")],
        "explanations": [{"episode": v["episode_title"], "verdict": v["verdict"], "decided": v["decided"],
                          "hypotheses": [{"id": h.id, "statement": h.text, "label": h.data["label"], "points": h.data["points"],
                                          "independentSupport": h.data["independent_support"],
                                          "supporting": [{"reason": s["reason"], "citation": src(case.cite(s["record_id"]))}
                                                         for s in h.data["supporting"]],
                                          "contradicting": [{"reason": s["reason"], "citation": src(case.cite(s["record_id"]))}
                                                            for s in h.data["contradicting"]],
                                          "assumptions": h.data["assumptions"], "key": h.key}
                                         for k in v["ranked"] for h in R.get("hypothesis") if h.key == k],
                          "discriminatingEvidence": v["discriminating_evidence"]} for v in verdicts],
        "timeline": [{**t, "citation": src(t["citation"])} for t in timeline],
        "uncertainTimes": [{"id": u.id, "title": u.title, "text": u.text, "count": u.data["count"], "citations": cites(u)}
                           for u in R.get("uncertain_time")[:30]],
        "missingPeriods": [{"id": m.id, "title": m.title, "text": m.text, "kind": m.data["kind"], "start": m.data["start"],
                            "end": m.data["end"], "citations": cites(m)} for m in R.get("missing_period")],
        "sourceGroups": [{"id": s.id, "title": s.title, "text": s.text, "citations": cites(s)} for s in R.get("source_group")],
        "signals": [{"id": s.id, "title": s.title, "text": s.text, "type": s.data.get("signal_type"), "score": s.score,
                     "certainty": s.certainty, "method": s.data.get("method", {}), "citations": cites(s), "key": s.key,
                     "origin": "ml",
                     "status": s.status} for s in R.get("signal")],
        "changes": changes,
        "overrides": overrides,
        "audit": extras["audit"],
    }
    for a in board["audit"]:
        a["citations"] = [src(c) if isinstance(c, dict) else c for c in a.get("citations", [])]
    board["sources"] = list(sources.values())
    return board


def _cite_from_edges(nodes: dict, edges: dict) -> None:
    """Entity and place nodes cite the records behind the threads that put them on the board."""
    for n in nodes.values():
        if n["id"].startswith(("ent-", "loc-")):
            extra = [c for e in edges.values() if n["id"] in (e["source"], e["target"]) for c in e["citations"]]
            n["citations"] = list(dict.fromkeys(n["citations"] + extra))[:NODE_CITATIONS]


def _gap_nodes(case, R, nodes: dict) -> dict[str, list[str]]:
    """Board node ids each gap concerns. A gap's `affected` keys name hypotheses, findings, contradictions and
    missing periods; each resolves to the episode, person, statement or record nodes it is about. Event and statement
    nodes that cite the same records as the gap are included too."""
    by_key = {it.key: it for b in R.items.values() for it in b}
    ep_of_record: dict[int, str] = {}
    for ep in R.get("episode"):
        for rid in ep.data.get("record_ids", []):
            ep_of_record.setdefault(rid, f"ev-{ep.key}")

    def resolve(key: str, depth: int = 0) -> list[str]:
        it = by_key.get(key)
        out = [nid for nid, n in nodes.items() if n.get("key") == key]
        if not it or depth > 2:
            return out
        d = it.data
        if it.kind == "hypothesis":
            out.append(f"ev-{d.get('episode')}")
        for k in ("subject", "person", "entity"):
            if isinstance(d.get(k), int):
                out.append(f"ent-{d[k]}")
        for k in ("subjects", "pair"):
            out += [f"ent-{e}" for e in d.get(k) or [] if isinstance(e, int)]
        if d.get("statement_record"):
            out.append(f"st-{d['statement_record']}")
        for rid in d.get("conflicting_records", []):
            out += [ep_of_record.get(rid, ""), f"rec-{rid}"]
        if d.get("episode") and it.kind != "hypothesis":
            out.append(f"ev-{d['episode']}")
        for k in ("finding", "claim"):
            if d.get(k):
                out += resolve(d[k], depth + 1)
        return out

    result = {}
    for g in R.get("gap"):
        ids = [nid for k in g.data.get("affected", []) for nid in resolve(k)]
        cited = {c["id"] for c in g.citations}
        ids += [nid for nid, n in nodes.items() if n["type"] in ("event", "statement") and cited & set(n["citations"])]
        result[g.id] = [nid for nid in dict.fromkeys(ids) if nid in nodes]
    return result


def _layout(nodes: dict) -> None:
    cols: dict[int, list] = {}
    for n in nodes.values():
        cols.setdefault(media_mod.MEDIA_COLUMN if n.get("media") else COLUMNS.get(n["type"], 2), []).append(n)
    for c, ns in cols.items():
        ns.sort(key=lambda n: (n.get("time") or "", n["label"]))
        for i, n in enumerate(ns):
            n["position"] = {"x": 80 + c * 320, "y": 60 + i * 130 + (40 if c % 2 else 0)}


def _insight_origin(i) -> str:
    return "agent" if str(i.data.get("generated_by", "")).startswith("agent") else "rules"


SIGNAL_NODE_TYPE = {"place_cluster": "location", "routine_outlier": "event", "message_triage": "device"}
LEAD_LINKS = 3  # board nodes a lead (ML signal or agent insight) is joined to


def _signal_and_insight_nodes(case, R, nodes: dict, edges: dict, cites) -> None:
    """ML signals and agent insights as inferred nodes joined to the nodes whose citations they share (the subject
    entity first, then the largest overlaps). A lead that shares nothing with the board is left off the graph (it stays
    in the side lists). Identity-cluster signals are already drawn as threads between people."""
    base = {nid: set(n["citations"]) for nid, n in nodes.items()}
    leads = [("ml", "ml_signals", f"sig-{s.key}", SIGNAL_NODE_TYPE.get(s.data.get("signal_type"), "event"), s, s.score)
             for s in R.get("signal") if s.data.get("signal_type") != "identity_cluster"]
    leads += [("agent", "agent_insights", f"ins-{i.key}", "event", i, i.score)
              for i in R.get("insight") if _insight_origin(i) == "agent"]
    for origin, stage, nid, ntype, it, _ in leads:
        cs = cites(it)
        subject = it.data.get("subject")
        targets = [(f"ent-{subject}", "subject")] if isinstance(subject, int) and f"ent-{subject}" in base else []
        ranked = sorted(((len(set(cs) & c), k) for k, c in base.items() if set(cs) & c), key=lambda t: (-t[0], t[1]))
        targets += [(k, f"shares {n} cited record{'s' if n != 1 else ''}") for n, k in ranked
                    if k not in {t for t, _ in targets}]
        targets = targets[:LEAD_LINKS]
        if not targets:
            continue
        nodes[nid] = {"id": nid, "type": ntype, "label": it.title[:60], "citations": cs[:NODE_CITATIONS],
                      "position": {"x": 0, "y": 0}, "summary": it.text[:400],
                      "subtitle": "ML signal" if origin == "ml" else "agent insight", "certainty": "inferred",
                      "origin": origin, "stage": stage, "itemId": it.id, "key": it.key}
        for t, why in targets:
            eid = f"inference:{nid}:{t}"
            edges[eid] = {"id": eid, "source": nid, "target": t, "type": "inference",
                          "label": "ML lead" if origin == "ml" else "agent lead", "citations": cs[:8],
                          "certainty": "inferred", "basis": f"{why} with {it.id}"[:200], "directed": False,
                          "origin": origin, "stage": stage}
