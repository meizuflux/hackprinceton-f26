"""Logical reasoning pipeline (post-ingestion).

    case.db ──► ML signals (Stage 0: clustering + classification, see ml.py)
            ──► connections, findings (Stage A) ──► key events ──► source independence ──► timeline
            ──► claims ──► contradictions ──► competing explanations ──► gaps ──► next steps ──► insights
            ──► [optional LLM: more claims + deep-agent investigator] ──► verification ──► overrides
            ──► comparison with the previous version ──► board.json / analysis.json / graph.json

case.db is opened read-only. Every step is written to a hash-chained audit log in analysis.db that
starts from the ingestion audit head, so the chain runs unbroken from upload to board.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from compstat_ingest.db import AuditLog, canonical_json

from . import analytics, board as board_mod, claims as claims_mod, contradictions as contra_mod, gaps as gaps_mod
from . import history, hypotheses as hyp_mod, insights as insights_mod, ml, recommend, sources, timeline as tl
from .model import Results, plural
from .store import Case
from .verify import Verifier

VERSION = "0.1.0"
_CLASS_OF_TYPE = {"video": "video", "photo": "video", "call_log": "carrier", "messages": "device", "location": "device",
                  "statement": "testimonial", "interview": "testimonial", "records": "system", "dna": "lab",
                  "email": "device", "calendar": "system", "contacts": "device"}


def _hash(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode()).hexdigest()


def analyze(run_dir: str | Path, out_root: str | Path | None = None, previous: str | Path | None = None,
            overrides_path: str | Path | None = None, llm: dict | None = None, progress=None) -> dict:
    run_dir = Path(run_dir)
    out_root = Path(out_root) if out_root else run_dir / "analysis"
    version, out = history.next_version_dir(out_root)
    say = progress or (lambda stage, pct: None)
    adb = sqlite3.connect(out / "analysis.db", check_same_thread=False)  # agent tools run on worker threads
    adb.executescript("""
        CREATE TABLE audit_log (seq INTEGER PRIMARY KEY, ts_utc TEXT NOT NULL, stage TEXT NOT NULL, action TEXT NOT NULL,
            file_id INTEGER, detail_json TEXT, prev_hash TEXT NOT NULL, entry_hash TEXT NOT NULL);
        CREATE TABLE items (item_id TEXT, kind TEXT, stable_key TEXT, status TEXT, certainty TEXT, score REAL,
            payload_json TEXT, PRIMARY KEY (kind, stable_key));
    """)
    audit = AuditLog(adb)
    ingest_manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8")) \
        if (run_dir / "run_manifest.json").exists() else {}
    if ingest_manifest.get("audit_head_hash"):
        audit.head = ingest_manifest["audit_head_hash"]  # continue the ingestion chain
    case = Case(run_dir)
    audit.write("analysis", "started", {"version": version, "pipeline_version": VERSION, "case_db_sha256":
                                        ingest_manifest.get("database_sha256"), "previous": str(previous) if previous else None,
                                        "llm": bool(llm)})
    R = Results()
    ctx = analytics.Context(case, R)

    def stage(name, items, pct):
        for it in items:
            R.add(it)
        audit.write("analysis", name, {"items": len(items), "output_sha256": _hash([i.to_dict() for i in items])})
        say(name, pct)
        return items

    # Stage 0: ML signals are leads for the board and the investigator agent. They are their own kind and are not
    # passed to the later stages, so findings, explanations, gaps and next steps stay exactly as rules compute them.
    stage("ml_signals", ml.run(ctx), 5)
    stage("connections", analytics.credential_and_alias_links(ctx), 10)
    findings = stage("findings", analytics.colocation(ctx) + analytics.access_anomalies(ctx) + analytics.concurrent_presence(ctx)
                     + analytics.communication_patterns(ctx), 25)
    episodes = stage("key_events", analytics.key_episodes(ctx, findings), 30)
    ind = sources.Independence(case)
    stage("source_independence", ind.items, 35)
    stage("uncertain_times", tl.uncertain_times(ctx, episodes), 40)
    missing = sorted(tl.missing_periods(ctx, episodes), key=lambda m: (m.data["kind"] != "unaccounted_person", -m.score))[:15]
    stage("missing_periods", missing, 45)
    claims = claims_mod.extract_claims(ctx, episodes)
    llm_run = None
    if llm:
        from . import llm as llm_mod
        llm_run = llm_mod.LLMRun(case, ctx, llm, audit)
        claims += llm_run.extract_claims(episodes, existing=claims)
    stage("claims", claims, 55)
    contradictions = stage("contradictions", contra_mod.claim_conflicts(ctx, claims)
                           + contra_mod.record_conflicts(ctx, findings, ind.items), 62)
    hyps, verdicts = hyp_mod.explanations(ctx, episodes, findings, contradictions, ind)
    stage("explanations", hyps, 70)
    gap_items = stage("gaps", gaps_mod.find_gaps(ctx, episodes, findings, contradictions, hyps, verdicts, missing), 78)
    present = {_CLASS_OF_TYPE.get(f["evidence_type"], "other") for f in case.files.values()}
    stage("next_steps", recommend.rank(case, gap_items, verdicts, present), 84)
    stage("insights", insights_mod.build(ctx, ind, findings, contradictions, hyps, verdicts, episodes), 88)
    if llm_run:
        stage("agent_insights", llm_run.investigate(R, verdicts), 92)

    for kind in list(R.items):
        R.renumber(kind, lambda i: -i.score)
    verification = Verifier(case).check(R)
    audit.write("analysis", "verified", verification)
    applied = history.apply_overrides(R, history.load_overrides(Path(overrides_path) if overrides_path else None))
    if applied:
        audit.write("analysis", "overrides_applied", {"overrides": applied})
    evidence = {"files": [{"path": f["original_path"], "sha256": f["sha256"], "evidence_id": f["external_id"]}
                          for f in case.files.values()],
                "source_archive_sha256": case.info.get("source_archive_sha256")}
    changes = history.compare(history.load_previous(previous), R, evidence)
    if changes:
        audit.write("analysis", "compared_with_previous", {"changes": len(changes)})

    conflicts: dict[int, list[str]] = {}
    for x in R.get("contradiction"):
        for rid in x.data.get("conflicting_records", []) + ([x.data["statement_record"]] if x.data.get("statement_record") else []):
            conflicts.setdefault(rid, []).append(x.id)
    rids = set(conflicts)
    for it in R.get("episode") + R.get("finding") + R.get("claim"):
        rids |= set(it.data.get("record_ids", [])[:40]) | ({it.data["record_id"]} if it.data.get("record_id") else set())
    timeline = tl.timeline_entries(ctx, rids, conflicts)

    analysed_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    adb.executemany("INSERT OR REPLACE INTO items VALUES (?,?,?,?,?,?,?)",
                    [(it.id, it.kind, it.key, it.status, it.certainty, it.score, canonical_json(it.to_dict()))
                     for b in R.items.values() for it in b])
    analysis = {"version": version, "pipeline_version": VERSION, "analysed_at": analysed_at, "case": case.info,
                "evidence": evidence, "verdicts": verdicts, "timeline": timeline, "changes": changes, "overrides": applied,
                "verification": verification, "coverage": tl.source_coverage(ctx),
                "llm": llm_run.summary() if llm_run else {"enabled": False}}
    for kind, b in R.items.items():
        analysis[plural(kind)] = [it.to_dict() for it in b]
    audit_rows = [{"id": f"A-{r[0]}", "time": r[1], "title": f"{r[2]}: {r[3].replace('_', ' ')}",
                   "description": r[4][:300], "citations": []}
                  for r in adb.execute("SELECT seq, ts_utc, stage, action, detail_json FROM audit_log ORDER BY seq")]
    brd = board_mod.build_board(case, ctx, R, verdicts, timeline, changes, applied,
                                {"analysed_at": analysed_at, "audit": audit_rows})
    graph = {"nodes": brd["nodes"], "edges": brd["edges"]}
    outputs = {"analysis.json": analysis, "board.json": brd, "graph.json": graph}
    for name, obj in outputs.items():
        (out / name).write_text(json.dumps(obj, indent=1, default=str, ensure_ascii=False), encoding="utf-8")
    audit.write("analysis", "outputs_written", {name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in outputs})
    adb.commit()
    head = audit.head
    adb.close()
    (out_root / "LATEST").write_text(f"v{version}", encoding="utf-8")
    summary = {"version": version, "out_dir": str(out), "audit_head": head,
               "counts": {k: len(v) for k, v in R.items.items()}, "changes": len(changes),
               "dropped_by_verifier": len(verification["items_dropped"]), "llm": analysis["llm"]}
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary
