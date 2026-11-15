"""Stage 0 traditional-ML signals: determinism, citations, Kestrel behaviour, identity gating, and no effect on the
rest of the reasoning pipeline."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))

from mapletrace_ingest.pipeline import ingest_zip  # noqa: E402
from mapletrace_reason import ml  # noqa: E402
from mapletrace_reason.analytics import Context  # noqa: E402
from mapletrace_reason.model import Results  # noqa: E402
from mapletrace_reason.pipeline import analyze  # noqa: E402
from mapletrace_reason.store import Case  # noqa: E402

KESTREL_ZIP = ROOT.parent / "cases" / "kestrel" / "kestrel_case_upload.zip"


@pytest.fixture(scope="module")
def kestrel_run(tmp_path_factory):
    if not KESTREL_ZIP.exists():
        pytest.skip("Kestrel case not present in this checkout")
    run = tmp_path_factory.mktemp("ml") / "k"
    ingest_zip(KESTREL_ZIP, run)
    return run


def _signals(run):
    case = Case(run)
    return case, ml.run(Context(case, Results()))


def test_signals_are_deterministic_and_cited(kestrel_run):
    case, first = _signals(kestrel_run)
    _, second = _signals(kestrel_run)
    assert [s.to_dict() for s in first] == [s.to_dict() for s in second], "same case.db must give the same signals"
    assert first
    for s in first:
        assert s.kind == "signal" and s.certainty == "inferred"
        assert s.citations and all(c["record_id"] in case.records for c in s.citations)
        assert s.data["method"]["name"] and s.data["record_ids"]
        assert set(s.data["record_ids"]) <= set(case.records)


def test_kestrel_signal_content(kestrel_run):
    _, sig = _signals(kestrel_run)
    by_type = {}
    for s in sig:
        by_type.setdefault(s.data["signal_type"], []).append(s)
    assert {"place_cluster", "routine_outlier", "message_triage"} <= set(by_type)
    homes = [s for s in by_type["place_cluster"] if s.data["role"] == "home"]
    assert any(s.title.endswith("Home") for s in homes), "location history labels the home cluster"
    work = [s for s in by_type["place_cluster"] if s.data["role"] == "work"]
    assert any("Aurion Park" in s.title for s in work)
    assert not any(s.data["role"] == "recurring_evening" and "Aurion Park" in s.data["label"] and "Halvorsen" in s.title
                   for s in by_type["place_cluster"]), "the workplace must not be reported as an evening place"
    assert any(s.data["day"] == "2026-10-17" for s in by_type["routine_outlier"]), "the Saturday stands out in routines"
    triage = {s.data["file"].rsplit("/", 1)[-1]: s for s in by_type["message_triage"]}
    assert triage, "message files are triaged"
    for s in triage.values():
        assert 0 < len(s.data["automated_record_ids"]) < s.data["messages"]
        assert s.data["method"]["cv_accuracy_on_seeds"] >= 0.8


def test_triage_never_flags_the_human_conversation_as_automated(kestrel_run):
    case, sig = _signals(kestrel_run)
    flagged = {rid for s in sig if s.data["signal_type"] == "message_triage" for rid in s.data["automated_record_ids"]}
    for rid in flagged:
        senders = [e for e, role in case.records[rid].entities if role == "sender"]
        assert not any(case.etype(e) == "person" for e in senders), case.records[rid].content


def test_signals_never_carry_protected_attributes(kestrel_run):
    _, sig = _signals(kestrel_run)
    blob = json.dumps([s.to_dict() for s in sig]).lower()
    for word in ("issuing_country", "nationality", "ethnicity", "citizenship"):
        assert word not in blob


# ---------------------------------------------------------------- identity clustering on a stub case
class _StubCase:
    def __init__(self, names, links=()):
        self.entities = {i: {"entity_type": "person", "value_norm": n.lower(), "display_name": n, "canonical_id": i}
                         for i, n in enumerate(names, 1)}
        self.links = [{"entity_a": a, "entity_b": b} for a, b in links]
        self.records = {100 + i: SimpleNamespace(id=100 + i, entities=[(i, "subject")]) for i in self.entities}

    def name(self, eid):
        return self.entities[eid]["display_name"]

    def etype(self, eid):
        return self.entities[eid]["entity_type"]

    def cite(self, rid):
        return {"id": f"EV-X:record={rid}", "evidence_id": "EV-X", "locator": f"record={rid}", "record_id": rid}


def _identity(names, links=()):
    case = _StubCase(names, links)
    return case, ml.identity_clusters(SimpleNamespace(case=case))


def test_identity_pairs_name_variants_but_not_different_people():
    case, out = _identity(["RAMAN, PRIYA", "Priya Raman", "V. Shen", "Vivian Shen", "Andrew Chen", "CHEN, ANDREW",
                           "Floor 2 east office door", "Floor 3 east office door", "Dana Whitfield"])
    pairs = {frozenset((case.name(s.data["entity_a"]), case.name(s.data["entity_b"]))) for s in out}
    assert frozenset(("RAMAN, PRIYA", "Priya Raman")) in pairs
    assert frozenset(("V. Shen", "Vivian Shen")) in pairs
    assert frozenset(("Andrew Chen", "CHEN, ANDREW")) in pairs
    assert not any({"Andrew Chen", "Vivian Shen"} <= p or {"V. Shen", "Andrew Chen"} <= p for p in pairs), \
        "similar-looking surnames are different people"
    assert not any("door" in n for p in pairs for n in p), "facility labels are not people"
    assert all(s.citations and s.data["similarity"] > 0 for s in out)


def test_identity_skips_pairs_ingestion_already_linked():
    case, out = _identity(["RAMAN, PRIYA", "Priya Raman"], links=[(1, 2)])
    assert out == []


# ---------------------------------------------------------------- the rest of the pipeline is unchanged
def _without_signals(analysis: dict) -> dict:
    a = {k: v for k, v in analysis.items() if k not in ("signals", "analysed_at", "verification")}
    # signals cite more records and files, so only the verifier's counters may differ; drops and failures may not
    a["verification"] = {k: v for k, v in analysis["verification"].items()
                         if k not in ("citations_checked", "files_verified")}
    return a


def test_ml_stage_does_not_change_other_results(tmp_path, monkeypatch):
    from make_sample_case import build
    z = build(tmp_path / "case.zip")
    ingest_zip(z, tmp_path / "run")
    s_on = analyze(tmp_path / "run", out_root=tmp_path / "on")
    monkeypatch.setattr(ml, "run", lambda ctx: [])
    s_off = analyze(tmp_path / "run", out_root=tmp_path / "off")
    on = json.loads((Path(s_on["out_dir"]) / "analysis.json").read_text(encoding="utf-8"))
    off = json.loads((Path(s_off["out_dir"]) / "analysis.json").read_text(encoding="utf-8"))
    assert _without_signals(on) == _without_signals(off)
    b_on = json.loads((Path(s_on["out_dir"]) / "board.json").read_text(encoding="utf-8"))
    b_off = json.loads((Path(s_off["out_dir"]) / "board.json").read_text(encoding="utf-8"))

    def _rules_nodes(b):  # ML leads are extra board nodes; every other node is unchanged apart from layout
        return [{k: v for k, v in n.items() if k != "position"} for n in b["nodes"] if n.get("origin") != "ml"]
    assert _rules_nodes(b_on) == _rules_nodes(b_off)
    for section in ("gaps", "insights", "suggestions", "contradictions", "explanations", "timeline"):
        assert b_on[section] == b_off[section], section
    assert "signals" in b_on and all(set(x["citations"]) <= {s["id"] for s in b_on["sources"]} for x in b_on["signals"])


def test_agent_tool_lists_signals(kestrel_run):
    from mapletrace_ingest.db import AuditLog
    import sqlite3
    from mapletrace_reason.llm import LLMRun
    case = Case(kestrel_run)
    R = Results()
    for s in ml.run(Context(case, R)):
        R.add(s)
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE audit_log (seq INTEGER PRIMARY KEY, ts_utc TEXT, stage TEXT, action TEXT, file_id INTEGER, "
                "detail_json TEXT, prev_hash TEXT, entry_hash TEXT)")
    run = LLMRun(case, Context(case, R), {"chat_model": object(), "model": "fake"}, AuditLog(con))
    rows = json.loads(run.build_tools(R, [], [])["list_ml_signals"]())
    assert rows and all(r["signal_id"].startswith("ML-") and r["method"] and r["record_ids"] for r in rows)
