"""Run trace, replay clock, board provenance and upload modes (backend/TRACE.md)."""

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))

from mapletrace_ingest.trace import TraceWriter  # noqa: E402


@pytest.fixture(scope="module")
def api(tmp_path_factory, monkeypatch_module=None):
    from fastapi.testclient import TestClient
    from make_sample_case import build
    tmp = tmp_path_factory.mktemp("trace")
    z = build(tmp / "case.zip")
    mp = pytest.MonkeyPatch()
    mp.setenv("MAPLETRACE_DATA", str(tmp / "data"))
    mp.delenv("ANTHROPIC_API_KEY", raising=False)
    import mapletrace_api.app as appmod
    importlib.reload(appmod)
    client = TestClient(appmod.app)
    with open(z, "rb") as fh:
        r = client.post("/upload", files={"file": ("harbor.zip", fh, "application/zip")})
    assert r.status_code == 200, r.text
    yield client, r.json()["caseId"], z, appmod
    mp.undo()


def test_trace_endpoint_covers_ingest_and_analysis(api):
    client, case_id, _, _ = api
    r = client.get(f"/cases/{case_id}/trace")
    assert r.status_code == 200
    body = r.json()
    ev = body["events"]
    assert body["status"] == "ready" and body["timing"] == "recorded" and body["next"] == ev[-1]["seq"]
    assert [e["seq"] for e in ev] == list(range(1, len(ev) + 1))
    assert all(a["tMs"] <= b["tMs"] for a, b in zip(ev, ev[1:]))
    types = {e["type"] for e in ev}
    assert {"run_started", "phase_started", "phase_finished", "file_hashed", "file_parsed", "entities_linked",
            "stage_finished", "ml_signal", "run_finished"} <= types
    assert ev[0]["type"] == "run_started" and ev[0]["mode"] == "replay" and ev[0]["archive"]["sha256"]
    parsed = [e for e in ev if e["type"] == "file_parsed"]
    assert parsed and all(e["records"] == sum(e["recordTypes"].values()) for e in parsed)
    stages = [e["stage"] for e in ev if e["type"] == "stage_finished"]
    assert stages[:2] == ["ml_signals", "connections"] and "gaps" in stages
    done = ev[-1]
    assert done["type"] == "run_finished" and done["status"] == "ready"
    board = client.get(f"/cases/{case_id}").json()
    assert done["totals"]["nodes"] == len(board["nodes"]) and done["totals"]["records"] > 0
    assert {e["id"] for e in ev if e["type"] == "ml_signal"} == {s["id"] for s in board["signals"]
                                                                  if s["type"] != "identity_cluster"} | \
        {s["id"] for s in board["signals"] if s["type"] == "identity_cluster"}


def test_trace_after_and_errors(api):
    client, case_id, _, _ = api
    full = client.get(f"/cases/{case_id}/trace").json()
    part = client.get(f"/cases/{case_id}/trace", params={"after": 5}).json()
    assert [e["seq"] for e in part["events"]] == [e["seq"] for e in full["events"] if e["seq"] > 5]
    tail = client.get(f"/cases/{case_id}/trace", params={"after": full["next"]}).json()
    assert tail["events"] == [] and tail["next"] == full["next"]
    for bad in ("x", "-1"):
        r = client.get(f"/cases/{case_id}/trace", params={"after": bad})
        assert r.status_code == 400 and r.json()["error"]["code"] == "bad_after"
    r = client.get("/cases/nope/trace")
    assert r.status_code == 404 and set(r.json()["error"]) == {"code", "message"}


def test_board_provenance(api):
    client, case_id, _, _ = api
    board = client.get(f"/cases/{case_id}").json()
    origins = {"record", "rules", "ml", "llm", "agent"}
    for obj in board["nodes"] + board["edges"]:
        assert obj["origin"] in origins and obj["stage"] and isinstance(obj["evidenceIds"], list)
        assert set(obj["evidenceIds"]) == {c.split(":", 1)[0] for c in obj["citations"]}
    assert all(i["origin"] in ("rules", "agent") for i in board["insights"])
    assert all(s["origin"] == "ml" for s in board["signals"])
    ml_nodes = [n for n in board["nodes"] if n["origin"] == "ml"]
    assert all(n["certainty"] == "inferred" for n in ml_nodes)
    ids = {n["id"] for n in board["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in board["edges"])
    for n in ml_nodes:
        assert any(e["origin"] == "ml" and n["id"] in (e["source"], e["target"]) for e in board["edges"])


def test_upload_modes(api, monkeypatch):
    client, _, z, appmod = api
    assert client.get("/health").json()["llmLive"] is False
    with open(z, "rb") as fh:
        r = client.post("/upload", data={"analysis_mode": "live"}, files={"file": ("harbor.zip", fh, "application/zip")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "needs_api_key"
    with open(z, "rb") as fh:
        r = client.post("/upload", data={"analysis_mode": "turbo"}, files={"file": ("harbor.zip", fh, "application/zip")})
    assert r.status_code == 400 and r.json()["error"]["code"] == "bad_analysis_mode"
    assert not [d for d in (appmod._cases()).iterdir() if d.name.startswith("harbor") and not (d / "case.json").exists()]
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert client.get("/health").json()["llmLive"] is True
    # live config never touches the committed cache
    cfg = appmod._llm_config({"analysis_mode": "live", "uploads": [{"sha256": "x"}]}, Path("/tmp/case"))
    assert cfg["cache_mode"] == "record" and cfg["cache_dir"] == "/tmp/case/llm_cache"


def test_replay_clock_advances_by_the_recorded_duration(tmp_path):
    t = TraceWriter(tmp_path / "trace.jsonl")
    a0, a1 = t.replayed_call(4000)
    b0, b1 = t.replayed_call(3000)          # starts when the first call finished on the clock
    assert a1 - a0 == 4000 and abs(b0 - a1) <= 5 and b1 - b0 == 3000
    assert 7000 <= t.now_ms() < 7200        # wall time is near zero, so the clock is the sum of the durations


def test_call_stats_and_latency_roundtrip(tmp_path):
    pytest.importorskip("langchain_core")
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langchain_core.messages import AIMessage
    from mapletrace_reason.llm_cache import ReplayCache, call_stats

    usage = {"input_tokens": 1000, "output_tokens": 550, "total_tokens": 1550,
             "input_token_details": {"cache_read": 400, "cache_creation": 100}}
    s = call_stats(AIMessage("x", usage_metadata=usage))
    assert s["inputTokens"] == 500 and s["cacheReadTokens"] == 400 and s["cacheWriteTokens"] == 100
    assert s["durationSource"] == "estimated" and s["durationMs"] == 800 + 10000
    assert s["costUsd"] == round((500 * 2 + 550 * 10 + 400 * 0.2 + 100 * 2.5) / 1e6, 6)
    assert call_stats(AIMessage("x"), 1234)["durationSource"] == "recorded"

    path = tmp_path / "c.jsonl"
    seen = []
    rec = ReplayCache(path, "record")
    rec.listener = seen.append
    GenericFakeChatModel(messages=iter([AIMessage("a", usage_metadata=usage)]), cache=rec).invoke("q")
    row = json.loads(path.read_text().splitlines()[0])
    assert row["latency_ms"] >= 0 and seen[0]["replayed"] is False
    replay = ReplayCache(path, "replay")
    seen2 = []
    replay.listener = seen2.append
    GenericFakeChatModel(messages=iter([]), cache=replay).invoke("q")
    assert seen2[0]["replayed"] and seen2[0]["latency_ms"] == row["latency_ms"]
    # an old entry without latency still loads and is estimated
    old = tmp_path / "old.jsonl"
    old.write_text(json.dumps({k: row[k] for k in ("key", "generations")}) + "\n")
    c = ReplayCache(old, "replay")
    seen3 = []
    c.listener = seen3.append
    GenericFakeChatModel(messages=iter([]), cache=c).invoke("q")
    assert seen3[0]["latency_ms"] is None
