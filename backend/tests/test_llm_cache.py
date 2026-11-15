"""Record/replay cache for the LLM layer: replay answers from the file and never reaches the model."""

import pytest

pytest.importorskip("langchain_core")

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

from mapletrace_reason.llm_cache import CacheMiss, ReplayCache, request_key  # noqa: E402


def _model(cache, replies):
    return GenericFakeChatModel(messages=iter([AIMessage(content=r) for r in replies]), cache=cache)


def test_record_then_replay(tmp_path):
    path = tmp_path / "abc.jsonl"
    rec = ReplayCache(path, "record")
    assert _model(rec, ["first answer"]).invoke("question").content == "first answer"
    assert rec.stats()["recorded"] == 1

    replay = ReplayCache(path, "replay")
    model = _model(replay, [])  # no scripted replies: any real call would fail
    assert model.invoke("question").content == "first answer"
    with pytest.raises(CacheMiss):
        model.invoke("a different question")
    assert replay.stats() == {"file": "abc.jsonl", "mode": "replay", "entries": 1, "hits": 1, "misses": 1,
                              "recorded": 0}


def test_record_reuses_cached_responses(tmp_path):
    path = tmp_path / "abc.jsonl"
    _model(ReplayCache(path, "record"), ["one"]).invoke("q")
    again = ReplayCache(path, "record")
    assert _model(again, ["should not be used"]).invoke("q").content == "one"
    assert again.stats()["recorded"] == 0 and path.read_text().count("\n") == 1


def test_key_ignores_random_message_ids():
    from langchain_core.load import dumps

    a = dumps([HumanMessage("hi", id="11111111-aaaa"), AIMessage("yo", id="run-1")])
    b = dumps([HumanMessage("hi", id="22222222-bbbb"), AIMessage("yo", id="run-2")])
    assert request_key(a, "m") == request_key(b, "m")
    assert request_key(a, "m") != request_key(a, "other model")


def test_replayed_history_matches_the_recording(tmp_path):
    """LangChain marks cached responses with total_cost=0; a conversation that continues from a replayed response
    must still hash like the recorded one."""
    from langchain_core.load import dumps

    usage = {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7}
    live = dumps([HumanMessage("q"), AIMessage("a", usage_metadata=usage), HumanMessage("next")])
    replayed = dumps([HumanMessage("q"), AIMessage("a", usage_metadata={**usage, "total_cost": 0}), HumanMessage("next")])
    assert request_key(live, "m") == request_key(replayed, "m")


def test_multi_turn_replay(tmp_path):
    path = tmp_path / "abc.jsonl"
    model = _model(ReplayCache(path, "record"), ["one", "two"])
    first = model.invoke([HumanMessage("q")])
    model.invoke([HumanMessage("q"), first, HumanMessage("more")])

    replay = _model(ReplayCache(path, "replay"), [])
    first = replay.invoke([HumanMessage("q")])  # comes back with total_cost=0
    assert replay.invoke([HumanMessage("q"), first, HumanMessage("more")]).content == "two"
