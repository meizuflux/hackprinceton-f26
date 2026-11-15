"""Reasoning pipeline, board contract, updates/overrides, LLM guards and the HTTP API."""

import json
import sys
import time
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))

from mapletrace_ingest.pipeline import ingest_zip  # noqa: E402
from mapletrace_reason import history  # noqa: E402
from mapletrace_reason.pipeline import analyze  # noqa: E402

KESTREL_ZIP = ROOT.parent / "cases" / "kestrel" / "kestrel_case_upload.zip"
CASEDATA_KEYS = {"id", "title", "subtitle", "timeRange", "nodes", "edges", "gaps", "insights", "suggestions", "sources", "audit"}


@pytest.fixture(scope="module")
def sample(tmp_path_factory):
    from make_sample_case import build
    tmp = tmp_path_factory.mktemp("reason")
    z = build(tmp / "case.zip")
    ingest_zip(z, tmp / "run")
    summary = analyze(tmp / "run")
    out = Path(summary["out_dir"])
    return tmp, z, summary, json.loads((out / "analysis.json").read_text(encoding="utf-8")), \
        json.loads((out / "board.json").read_text(encoding="utf-8"))


def _all_citation_ids(board):
    ids = []
    for section in ("nodes", "edges", "gaps", "insights", "suggestions"):
        for item in board[section]:
            ids += item.get("citations", [])
    for x in board.get("contradictions", []):
        ids += x["citations"]
    return ids


def test_board_matches_frontend_contract(sample):
    _, _, _, _, board = sample
    assert CASEDATA_KEYS <= set(board)
    source_ids = {s["id"] for s in board["sources"]}
    assert set(_all_citation_ids(board)) <= source_ids, "every citation must resolve to a source entry"
    node_ids = {n["id"] for n in board["nodes"]}
    assert all(e["source"] in node_ids and e["target"] in node_ids for e in board["edges"])
    assert all(n["type"] in {"person", "location", "device", "event", "statement"} for n in board["nodes"])
    assert {n["certainty"] for n in board["nodes"]} <= {"observed", "inferred", "unknown"}
    for s in board["sources"]:
        assert s["path"] and len(s["hash"]) == 64 and "evidence_id" in s["metadata"]


DIRECTED_RELATIONS = {("claim", "stated"), ("contradicts", "conflicts with"), ("spatial", "occurred at"),
                      ("temporal", "recorded at")}


def _check_board_links(board):
    nodes = {n["id"]: n for n in board["nodes"]}
    source_ids = {s["id"] for s in board["sources"]}
    assert all(n["citations"] and set(n["citations"]) <= source_ids for n in nodes.values()), "every node is cited"
    for e in board["edges"]:
        assert isinstance(e["directed"], bool)
        assert e["directed"] == ((e["type"], e["label"]) in DIRECTED_RELATIONS)
        if e["directed"]:
            want = {"stated": ("person", "statement"), "conflicts with": ("statement", "event"),
                    "occurred at": ("event", "location"), "recorded at": (None, "event")}[e["label"]]
            assert nodes[e["target"]]["type"] == want[1]
            assert want[0] is None or nodes[e["source"]]["type"] == want[0]
    gaps = {g["id"]: g for g in board["gaps"]}
    assert all(set(g["nodeIds"]) <= set(nodes) for g in gaps.values())
    for n in nodes.values():
        if "gapId" in n:
            concerning = [g for g in gaps.values() if n["id"] in g["nodeIds"]]
            assert n["gapId"] == max(concerning, key=lambda g: g["score"])["id"]
    return nodes, gaps


def test_board_links_citations_direction_and_gaps(sample):
    tmp, _, _, _, board = sample
    nodes, gaps = _check_board_links(board)
    import sqlite3
    con = sqlite3.connect(tmp / "run" / "case.db")
    assert board["timezone"] == con.execute("SELECT value FROM case_info WHERE key='assumed_timezone'").fetchone()[0]
    con.close()
    assert any(e["directed"] for e in board["edges"])
    assert any(g["nodeIds"] for g in gaps.values()) and any("gapId" in n for n in nodes.values())


def test_silence_interval_wording():
    from mapletrace_reason.timeline import _interval
    assert [_interval(0), _interval(12), _interval(14 * 60), _interval(3 * 3600)] == \
        ["under a second", "12 s", "14 min", "3.0 h"]


def test_statement_contradicted_by_records(sample):
    _, _, _, a, _ = sample
    x = [c for c in a["contradictions"] if c["data"]["kind"] == "statement_vs_record"]
    assert x, "Vance's 'home all night' should conflict with his phone and car records"
    assert any("Vance" in c["title"] for c in x)
    c = x[0]
    assert c["data"]["possible_reasons"] and c["data"]["resolving_evidence"]
    assert all("lied" not in c["text"].lower() for c in a["contradictions"])


def test_insights_are_structured_and_cited(sample):
    _, _, _, a, _ = sample
    assert a["insights"]
    for i in a["insights"]:
        d = i["data"]
        assert i["citations"] and d["observations"] and d["inference"]
        assert d["confidence"] in ("low", "medium", "high")
        assert {"unknowns", "counterevidence", "assumptions", "limitations"} <= set(d)


def test_gaps_are_typed_with_directions(sample):
    _, _, _, a, _ = sample
    assert a["gaps"]
    for g in a["gaps"]:
        assert g["data"]["gap_type"] in ("missing", "failed_extraction", "conflicting", "uncertain")
        assert g["data"]["direction"] and g["data"]["why_it_matters"]
    assert any(g["data"]["gap_type"] == "failed_extraction" for g in a["gaps"]), "the unreadable binary is a failed-extraction gap"


def test_next_steps_ranked_and_explained(sample):
    _, _, _, a, _ = sample
    s = a["suggestions"]
    assert s and [x["data"]["priority"] for x in s] == list(range(1, len(s) + 1))
    assert all(x["data"]["reasons"] and x["data"]["request"] for x in s)


def test_audit_chain_continues_from_ingestion(sample):
    tmp, _, summary, _, _ = sample
    import sqlite3
    from mapletrace_ingest.db import canonical_json
    import hashlib
    head = json.loads((tmp / "run" / "run_manifest.json").read_text())["audit_head_hash"]
    con = sqlite3.connect(Path(summary["out_dir"]) / "analysis.db")
    prev = head
    for seq, ts, stage, action, fid, detail, prev_hash, entry in con.execute("SELECT * FROM audit_log ORDER BY seq"):
        assert prev_hash == prev
        assert hashlib.sha256(canonical_json([prev, ts, stage, action, fid, detail]).encode()).hexdigest() == entry
        prev = entry


def test_overrides_and_versions(sample):
    tmp, _, summary, a, _ = sample
    target = a["contradictions"][0]["key"]
    ov = tmp / "overrides.jsonl"
    history.append_override(ov, target, "dismiss", note="reader was being repaired", investigator="tester")
    s2 = analyze(tmp / "run", previous=summary["out_dir"], overrides_path=ov)
    a2 = json.loads((Path(s2["out_dir"]) / "analysis.json").read_text(encoding="utf-8"))
    x = next(c for c in a2["contradictions"] if c["key"] == target)
    assert x["status"] == "dismissed" and x["data"]["machine_status"] == "open"
    assert x["data"]["overrides"][0]["note"] == "reader was being repaired"
    assert a2["overrides"][0]["matched"] is True
    assert s2["version"] == summary["version"] + 1


def test_new_evidence_updates_gaps(sample, tmp_path):
    tmp, z, summary, a, _ = sample
    # new evidence: an interview with Marcus Ortiz whose account conflicts with the message records
    z2 = tmp_path / "case_v2.zip"
    with zipfile.ZipFile(z, "r") as src, zipfile.ZipFile(z2, "w") as dst:
        for info in src.infolist():
            dst.writestr(info, src.read(info))
        dst.writestr("interviews/interview_mortiz_2026-03-17.txt",
                     "INTERVIEW TRANSCRIPT\nDate: 2026-03-17 14:00\nInterviewer: Det. Ana Ruiz\nInterviewee: Marcus Ortiz\n"
                     "Date of incident: 2026-03-14\n\n"
                     "Det. Ruiz: Do you know Daniel Vance?\nMarcus Ortiz: A little. I haven't talked to Daniel in weeks.\n"
                     "Det. Ruiz: Where were you on Saturday night?\nMarcus Ortiz: I was home all night.\n")
    ingest_zip(z2, tmp_path / "run2")
    s2 = analyze(tmp_path / "run2", previous=summary["out_dir"])
    a2 = json.loads((Path(s2["out_dir"]) / "analysis.json").read_text(encoding="utf-8"))
    kinds = {c["change"] for c in a2["changes"]}
    assert any(c["kind"] == "evidence" and c["added"] for c in a2["changes"])
    assert kinds - {"evidence updated"}, "re-evaluation should report what changed"
    assert all("previous_status" in g["data"] for g in a2["gaps"])


class _FakeStructured:
    def __init__(self, payload):
        self.payload = payload

    def invoke(self, prompt):
        from mapletrace_reason.llm import ExtractedClaims
        ids = [int(x) for x in __import__("re").findall(r"^\[(\d+)\]", prompt, __import__("re").M)]
        claims = [dict(c, record_id=ids[0] if c["record_id"] == "first" else c["record_id"]) for c in self.payload]
        return ExtractedClaims(claims=claims)


class _FakeChat:
    def __init__(self, payload):
        self.payload = payload

    def with_structured_output(self, schema, method=None):
        assert method == "json_schema", "Opus 5.5 rejects forced tool use; structured output must use json_schema"
        return _FakeStructured(self.payload)


def test_llm_claims_and_agent_tools_are_guarded(sample):
    from mapletrace_ingest.db import AuditLog
    import sqlite3
    from mapletrace_reason import analytics
    from mapletrace_reason.llm import LLMRun
    from mapletrace_reason.model import Results
    from mapletrace_reason.store import Case
    tmp, _, _, _, _ = sample
    case = Case(tmp / "run")
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE audit_log (seq INTEGER PRIMARY KEY, ts_utc TEXT, stage TEXT, action TEXT, file_id INTEGER, "
                "detail_json TEXT, prev_hash TEXT, entry_hash TEXT)")
    payload = [{"record_id": "first", "claim_type": "activity", "polarity": True, "place": None, "counterpart": None,
                "time_start_local": None, "time_end_local": None, "summary": "watched a movie"},
               {"record_id": 999999, "claim_type": "location", "polarity": True, "place": "home", "counterpart": None,
                "time_start_local": None, "time_end_local": None, "summary": "invented record id"}]
    run = LLMRun(case, analytics.Context(case, Results()), {"chat_model": _FakeChat(payload), "model": "fake"}, AuditLog(con))
    claims = run.extract_claims([], existing=[])
    assert claims and all(c.citations and c.data["record_id"] in case.records for c in claims)
    assert all(c.data["extraction"] == "llm:fake" for c in claims)
    R, created = Results(), []
    tools = run.build_tools(R, [], created)
    bad = json.loads(tools["record_insight"]("x", [{"text": "made up", "record_ids": [999999]}], "y", [], [], [], [], "high"))
    assert "error" in bad and not created
    rid = next(iter(case.records))
    ok = json.loads(tools["record_insight"]("Real", [{"text": "a record", "record_ids": [rid]}], "something", [], [], [], [],
                                            "high"))
    assert ok["ok"] and created[0].citations[0]["record_id"] == rid
    assert created[0].data["confidence"] == "medium", "one source cannot be high confidence"
    assert json.loads(tools["search_records"]("Vance"))


def test_api_end_to_end(sample, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv("MAPLETRACE_DATA", str(tmp_path / "data"))
    import importlib
    import mapletrace_api.app as appmod
    importlib.reload(appmod)
    client = TestClient(appmod.app)
    _, z, _, _, _ = sample
    with open(z, "rb") as fh:
        r = client.post("/upload", files={"file": ("harbor.zip", fh, "application/zip")}, data={"case_name": "Harbor St"})
    assert r.status_code == 200, r.text
    job, case_id = r.json()["jobId"], r.json()["caseId"]
    st = client.get(f"/status/{job}").json()
    assert st["status"] == "ready", st
    board = client.get(f"/cases/{case_id}").json()
    assert CASEDATA_KEYS <= set(board) and board["id"] == case_id
    assert client.get("/case").json()["id"] == case_id
    for section in ("gaps", "insights", "suggestions", "contradictions", "explanations", "timeline", "audit", "graph",
                    "signals"):
        assert client.get(f"/cases/{case_id}/{section}").status_code == 200
    sid = board["sources"][0]["id"]
    assert client.get(f"/cases/{case_id}/source", params={"id": sid}).json()["id"] == sid
    ev = board["sources"][0]["metadata"]["evidence_id"]
    assert client.get(f"/cases/{case_id}/evidence/{ev}").status_code == 200
    key = board["gaps"][0]["key"]
    r = client.post(f"/cases/{case_id}/overrides", json={"target_key": key, "action": "set_status", "value": "resolved",
                                                        "note": "answered by phone call", "investigator": "tester"})
    assert r.status_code == 200 and client.get(f"/status/{r.json()['jobId']}").json()["status"] == "ready"
    assert next(g for g in client.get(f"/cases/{case_id}/gaps").json() if g["key"] == key)["status"] == "resolved"
    assert client.get("/cases/nope-000000").json()["error"]["code"] == "case_not_found"

    # evidence inventory, normalized records and the audit chain (not shadowed by /cases/{id}/{section})
    files = client.get(f"/cases/{case_id}/files").json()
    assert files and {"evidenceId", "fileId", "path", "filename", "sha256", "bytes", "format", "evidenceType",
                      "parseStatus", "recordCount", "manifestMatch", "origin"} <= set(files[0])
    assert all(len(f["sha256"]) == 64 and f["manifestMatch"] in (True, False, None) for f in files)
    board = client.get(f"/cases/{case_id}").json()
    ev = board["sources"][0]["metadata"]["evidence_id"]
    f = next(f for f in files if f["evidenceId"] == ev)
    recs = client.get(f"/cases/{case_id}/records", params={"evidenceId": ev, "limit": 500}).json()
    assert recs["total"] == f["recordCount"] and len(recs["items"]) == min(500, f["recordCount"])
    item = recs["items"][0]
    assert {"id", "recordType", "fields", "citations"} <= set(item)
    assert all(not isinstance(v, (dict, list)) for v in item["fields"].values())
    assert item["citations"][0]["evidenceId"] == ev
    source_ids = {s["id"] for s in board["sources"]}
    linked = [c["sourceId"] for i in recs["items"] for c in i["citations"] if "sourceId" in c]
    assert linked and set(linked) <= source_ids
    assert board["sources"][0]["id"] in linked
    page = client.get(f"/cases/{case_id}/records", params={"limit": 1, "offset": 1}).json()
    assert len(page["items"]) == 1 and page["total"] > 1
    assert client.get(f"/cases/{case_id}/records", params={"limit": 501}).json()["error"]["code"] == "bad_paging"
    assert client.get(f"/cases/{case_id}/records", params={"evidenceId": "EV-NOPE"}).status_code == 404
    chain = client.get(f"/cases/{case_id}/audit-chain").json()
    assert chain["verified"] is True, chain["checks"]
    srcs = [e["source"] for e in chain["entries"]]
    assert srcs[0] == "ingest" and srcs[-1] == "analysis" and chain["head"] == chain["entries"][-1]["hash"]
    for prev, cur in zip(chain["entries"], chain["entries"][1:]):
        assert cur["prevHash"] == prev["hash"], "one unbroken chain from upload to board"
    bad = client.post("/upload", files={"file": ("x.txt", b"hello", "text/plain")})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "not_a_zip"


@pytest.mark.skipif(not KESTREL_ZIP.exists(), reason="Kestrel case not present in this checkout")
def test_kestrel_reasoning(tmp_path):
    ingest_zip(KESTREL_ZIP, tmp_path / "k")
    s = analyze(tmp_path / "k")
    a = json.loads((Path(s["out_dir"]) / "analysis.json").read_text(encoding="utf-8"))
    assert s["dropped_by_verifier"] == 0
    v = a["verdicts"][0]
    assert "22:51" in v["episode_title"], "the key event is the Saturday-night cabinet opening"
    top = [h for k in v["ranked"][:2] for h in a["hypotheses"] if h["key"] == k]
    assert any(h["data"]["kind"] == "credential" for h in top), "someone-else-used-the-credential must be a leading explanation"
    assert not v["decided"], "the evidence alone should not force a conclusion"
    assert any("Halvorsen" in x["title"] for x in a["contradictions"] if x["data"]["kind"] == "statement_vs_record")
    assert any(f["title"].startswith("Unidentified party: +14085550147") for f in a["findings"])
    assert a["suggestions"][0]["data"]["artifact"] in ("cctv_review", "media_analysis", "forensic_lab", "phone_location")
    board = json.loads((Path(s["out_dir"]) / "board.json").read_text(encoding="utf-8"))
    nodes, gaps = _check_board_links(board)
    assert board["timezone"] == "America/Los_Angeles"
    assert all(g["nodeIds"] for g in gaps.values()), "every Kestrel gap resolves to board nodes"
    assert any("gapId" in n for n in nodes.values())
    assert not any("every 0 min" in m["text"] for m in board["missingPeriods"])


def test_deep_agent_loop_records_cited_insights(sample):
    """Runs the real deepagents loop with a scripted model: tools execute, are audited, and only cited insights land."""
    import sqlite3
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langchain_core.messages import AIMessage
    from mapletrace_ingest.db import AuditLog
    from mapletrace_reason import analytics
    from mapletrace_reason.llm import LLMRun
    from mapletrace_reason.model import Results
    from mapletrace_reason.store import Case

    class ToolFake(GenericFakeChatModel):
        def bind_tools(self, tools, **kw):
            return self

    tmp, _, _, _, _ = sample
    case = Case(tmp / "run")
    rid = next(iter(case.records))
    script = iter([
        AIMessage(content="", tool_calls=[{"name": "list_explanations", "args": {}, "id": "t1"}]),
        AIMessage(content="", tool_calls=[{"name": "record_insight", "id": "t2", "args": {
            "title": "Uncited", "observations": [{"text": "nothing", "record_ids": [999999]}], "inference": "x",
            "unknowns": [], "counterevidence": [], "assumptions": [], "limitations": [], "confidence": "high"}}]),
        AIMessage(content="", tool_calls=[{"name": "record_insight", "id": "t3", "args": {
            "title": "Cited", "observations": [{"text": "a record", "record_ids": [rid]}], "inference": "y",
            "unknowns": [], "counterevidence": [], "assumptions": [], "limitations": [], "confidence": "low"}}]),
        AIMessage(content="Done."),
    ])
    con = sqlite3.connect(":memory:", check_same_thread=False)
    con.execute("CREATE TABLE audit_log (seq INTEGER PRIMARY KEY, ts_utc TEXT, stage TEXT, action TEXT, file_id INTEGER, "
                "detail_json TEXT, prev_hash TEXT, entry_hash TEXT)")
    fake = ToolFake(messages=script)
    run = LLMRun(case, analytics.Context(case, Results()),
                 {"chat_model": fake, "verifier_chat_model": fake, "model": "fake", "max_steps": 10}, AuditLog(con))
    out = run.investigate(Results(), [])
    assert [i.title for i in out] == ["Cited"]
    assert out[0].data["generated_by"] == "agent:fake" and out[0].certainty == "inferred"
    actions = [r[0] for r in con.execute("SELECT action FROM audit_log ORDER BY seq")]
    assert actions == ["list_explanations", "record_insight", "record_insight"]


def test_citation_labels_identify_one_record():
    from mapletrace_reason.store import unique_labels

    labels = unique_labels([
        (1, 7, {"row": 4}, {"event_id": "9001"}),   # event code shared by two rows -> position
        (2, 7, {"row": 5}, {"event_id": "9001"}),
        (3, 7, {"row": 6}, {"event_id": "BDG-1"}),  # unique record ID is kept
        (4, 8, {"row": 4}, {"event_id": "9001"}),   # another file: no collision
    ])
    assert labels == {1: "row=4", 2: "row=5", 3: "event_id=BDG-1", 4: "event_id=9001"}


def test_api_llm_mode_demo_and_rejected_upload(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv("MAPLETRACE_DATA", str(tmp_path / "data"))
    import importlib
    import mapletrace_api.app as appmod
    importlib.reload(appmod)
    client = TestClient(appmod.app)

    # an upload whose archive has recorded responses replays them; an explicit LLM request records
    cache_dir = tmp_path / "llm_cache"
    monkeypatch.setattr(appmod, "cache_path", lambda sha: cache_dir / f"{sha}.jsonl")
    meta = {"uploads": [{"sha256": "abc"}], "llm": False}
    assert appmod._llm_config(meta) is None
    cache_dir.mkdir()
    (cache_dir / "abc.jsonl").write_text("")
    assert appmod._llm_config(meta)["cache_mode"] == "replay"
    assert appmod._llm_config({**meta, "llm": True})["cache_mode"] == "record"

    # a rejected upload leaves no case folder
    r = client.post("/upload", files={"file": ("bad.zip", b"not a zip", "application/zip")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "not_a_zip"
    assert not [d for d in (tmp_path / "data" / "cases").iterdir() if not d.name.startswith(".")]

    monkeypatch.setattr(appmod, "DEMO_SNAPSHOT", tmp_path / "missing.tar.gz")
    r = client.post("/demo")
    assert r.status_code == 404 and r.json()["error"]["code"] == "no_demo_snapshot"
