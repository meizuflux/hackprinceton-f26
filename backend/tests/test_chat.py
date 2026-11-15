"""Case chat: cited answers, cite-or-drop, suggested questions, record/replay and the no-key behaviour.

Every model here is a scripted fake; these tests never call the API."""

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402


class ToolFake(GenericFakeChatModel):
    def bind_tools(self, tools, **kw):
        return self


def _call(name, args, i):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call-{i}"}])


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    """One analysed sample case behind the API, with the chat cache in a temporary folder."""
    from fastapi.testclient import TestClient
    from make_sample_case import build
    tmp = tmp_path_factory.mktemp("chat")
    mp = pytest.MonkeyPatch()
    mp.setenv("MAPLETRACE_DATA", str(tmp / "data"))
    mp.delenv("ANTHROPIC_API_KEY", raising=False)
    import mapletrace_api.app as appmod
    importlib.reload(appmod)
    client = TestClient(appmod.app)
    z = build(tmp / "case.zip")
    with open(z, "rb") as fh:
        r = client.post("/upload", files={"file": ("harbor.zip", fh, "application/zip")})
    case_id = r.json()["caseId"]
    assert client.get(f"/status/{r.json()['jobId']}").json()["status"] == "ready"
    board = client.get(f"/cases/{case_id}").json()
    from mapletrace_reason.store import Case
    ingest_dir, _ = appmod._latest_dirs(case_id)
    case = Case(ingest_dir)
    sources = {s["id"] for s in board["sources"]}
    cited = next(r.id for r in case.timed if case.cite(r.id)["id"] in sources)
    yield appmod, client, case_id, board, cited, tmp / "llm_cache"
    mp.undo()


def _service(appmod, cache_dir, fake):
    from mapletrace_api.chat import ChatService

    def factory(cache):
        fake.cache = cache
        return fake
    appmod.chat_service = ChatService(cache_dir=cache_dir, model_factory=factory)
    return appmod.chat_service


def test_status_lists_deterministic_suggestions(api):
    appmod, client, case_id, _, _, cache_dir = api
    _service(appmod, cache_dir, ToolFake(messages=iter([])))
    st = client.get("/chat/status", params={"case_id": case_id}).json()
    assert st["available"] is True and st["authoritative"] is True and st["case_id"] == case_id
    assert st["live"] is False and st["mode"] == "replay" and "API key" in st["reason"]
    assert 3 <= len(st["suggestions"]) <= 5
    assert all(s["recorded"] is False and s["question"].endswith("?") for s in st["suggestions"])
    again = client.get("/chat/status", params={"case_id": case_id}).json()
    assert [s["question"] for s in again["suggestions"]] == [s["question"] for s in st["suggestions"]]
    missing = client.get("/chat/status", params={"case_id": "nope-000000"}).json()
    assert missing["available"] is False and missing["case_id"] == "nope-000000"


def test_cache_miss_without_key_never_calls_the_model(api):
    appmod, client, case_id, _, _, cache_dir = api

    class Exploding(ToolFake):
        def _generate(self, *a, **kw):
            raise AssertionError("the model must not be called without a key")
    _service(appmod, cache_dir, Exploding(messages=iter([])))
    r = client.post(f"/cases/{case_id}/chat", json={"message": "Who opened the door?"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "needs_api_key"
    assert client.post(f"/cases/{case_id}/chat", json={"message": "  "}).json()["error"]["code"] == "empty_message"


def test_answers_cite_sources_drop_uncited_and_replay(api, monkeypatch):
    appmod, client, case_id, board, rid, cache_dir = api
    question = client.get("/chat/status", params={"case_id": case_id}).json()["suggestions"][0]["question"]
    script = [
        _call("get_record", {"record_id": rid}, 1),
        _call("submit_answer", {"summary": "One record bears on this.", "observations": [
            {"text": "The record shows the event", "record_ids": [rid]},
            {"text": "An invented detail", "record_ids": [999999]}],
            "inference": "It may be relevant.", "unknowns": ["Who was present"], "evidence_status": "supported"}, 2),
    ]
    # record: a key is set, so a miss calls the (fake) model and stores its responses
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-used")
    _service(appmod, cache_dir, ToolFake(messages=iter(script)))
    r = client.post(f"/cases/{case_id}/chat", json={"message": question})
    assert r.status_code == 200, r.text
    first = r.json()
    msg = first["message"]
    assert first["thread_id"] and first["suggested"] is True and first["replayed"] is False
    assert msg["role"] == "assistant" and msg["evidence_status"] == "partial", "a dropped citation downgrades support"
    assert len(msg["citations"]) == 1 and len(msg["observations"]) == 1
    c = msg["citations"][0]
    assert {"evidence_id", "locator", "excerpt", "source_id"} <= set(c)
    assert c["source_id"] in {s["id"] for s in board["sources"]}
    assert "Inference" in msg["content"] and "left out" in msg["content"]
    kinds = [(st["type"], st.get("tool")) for st in first["steps"]]
    assert kinds == [("model_call", None), ("tool_call", "get_record"), ("model_call", None)]
    tool = first["steps"][1]
    assert tool["args"] == {"record_id": rid} and tool["resultChars"] > 0
    assert all({"inputTokens", "outputTokens", "costUsd", "durationMs", "durationSource"} <= set(st)
               for st in first["steps"] if st["type"] == "model_call")

    # replay: no key, a fresh service and an exhausted fake; the recorded answer comes back unchanged
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    _service(appmod, cache_dir, ToolFake(messages=iter([])))
    st = client.get("/chat/status", params={"case_id": case_id}).json()
    assert next(s for s in st["suggestions"] if s["question"] == question)["recorded"] is True
    assert not any(s["recorded"] for s in st["suggestions"] if s["question"] != question)
    # threads live in server memory: an unknown thread starts a new one
    r = client.post(f"/cases/{case_id}/chat", json={"message": question, "thread_id": first["thread_id"]})
    assert r.status_code == 200 and r.json()["replayed"] is True and r.json()["message"] == msg
    assert [st["type"] for st in r.json()["steps"]] == ["model_call", "tool_call", "model_call"], "replay keeps steps"
    thread = r.json()["thread_id"]
    assert thread != first["thread_id"]
    # a suggested question replays standalone even after other turns in the same thread
    r = client.post(f"/cases/{case_id}/chat", json={"message": question.upper(), "thread_id": thread})
    assert r.status_code == 200 and r.json()["thread_id"] == thread and r.json()["message"] == msg
    assert (cache_dir / f"chat-{appmod._read_json(appmod._latest_dirs(case_id)[1] / 'analysis.json')['case']['source_archive_sha256']}.jsonl").exists()


def test_step_helpers_truncate_args_and_estimate_duration():
    from mapletrace_reason.chat import _short_args, model_step
    from mapletrace_reason.llm_cache import EST_BASE_MS, EST_TOKENS_PER_S
    long = "x" * 300
    assert len(_short_args({"query": long})["query"]) == 120
    resp = AIMessage(content="", usage_metadata={"input_tokens": 1000, "output_tokens": 550, "total_tokens": 1550})
    est = model_step(resp, 5, cached=True)
    assert est["durationSource"] == "estimated" and est["durationMs"] == round(EST_BASE_MS + 550 / EST_TOKENS_PER_S * 1000)
    assert est["costUsd"] == round((1000 * 2.0 + 550 * 10.0) / 1e6, 6), "LLM_COSTS.md prices"
    live = model_step(resp, 2500, cached=False)
    assert live["durationSource"] == "live" and live["durationMs"] == 2500
    resp.response_metadata["latency_ms"] = 1234
    rec = model_step(resp, 5, cached=True)
    assert rec["durationSource"] == "recorded" and rec["durationMs"] == 1234


def test_uncited_answer_is_insufficient(api, monkeypatch):
    appmod, client, case_id, _, rid, cache_dir = api
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-used")
    script = [_call("submit_answer", {"summary": "The vehicle was there.", "observations": [
        {"text": "Not read through a tool", "record_ids": [rid]}], "inference": "", "unknowns": [],
        "evidence_status": "supported"}, 1)]
    _service(appmod, cache_dir, ToolFake(messages=iter(script)))
    r = client.post(f"/cases/{case_id}/chat", json={"message": "Was the vehicle at the station?"})
    msg = r.json()["message"]
    assert msg["evidence_status"] == "insufficient" and msg["citations"] == []
    assert "do not answer" in msg["content"]

    # a plain-text reply without submit_answer cites nothing
    _service(appmod, cache_dir, ToolFake(messages=iter([AIMessage(content="Probably yes.")])))
    msg = client.post(f"/cases/{case_id}/chat", json={"message": "Anything else?"}).json()["message"]
    assert msg["evidence_status"] == "insufficient" and msg["citations"] == []


def test_suggestions_follow_the_analysis():
    from mapletrace_reason.chat import suggested_questions
    analysis = {"verdicts": [{"episode_title": "Key event Sat 17 Oct 22:51 at Door 4", "decided": False}],
                "contradictions": [{"title": "A's account conflicts with records", "score": 0.8}],
                "gaps": [{"title": "Which explanation of the key event fits the evidence?", "score": 0.9,
                          "status": "open", "data": {"gap_type": "uncertain"}},
                         {"title": "Who uses +15555550147?", "score": 0.8, "status": "open", "data": {}},
                         {"title": "Done", "score": 0.99, "status": "resolved", "data": {}}]}
    qs = suggested_questions(analysis)
    assert qs[0].startswith("Which explanations fit the key event Sat 17 Oct 22:51 at Door 4")
    assert qs[1].startswith("A's account conflicts with records:")
    assert qs[2] == "Who uses +15555550147?" and len(qs) == 3
