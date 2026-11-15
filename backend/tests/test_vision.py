"""Image descriptions: cache keying, replay without a key or decoding, and isolation from the reasoning."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mapletrace_ingest.pipeline import ingest_zip  # noqa: E402
from mapletrace_reason import media as media_mod, vision  # noqa: E402
from mapletrace_reason.pipeline import analyze  # noqa: E402
from mapletrace_reason.store import Case  # noqa: E402

KESTREL_ZIP = ROOT.parent / "cases" / "kestrel" / "kestrel_case_upload.zip"


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory):
    if not KESTREL_ZIP.exists():
        pytest.skip("Kestrel case not present in this checkout")
    run = tmp_path_factory.mktemp("vision") / "k"
    ingest_zip(KESTREL_ZIP, run)
    return run


class FakeClient:
    def __init__(self):
        self.calls = []

    def describe(self, jpeg, prompt):
        assert jpeg[:2] == b"\xff\xd8", "frames and photos are sent as JPEG"
        self.calls.append(prompt)
        reply = json.dumps({"text": "A neutral description.", "observations": ["a visible object", "text: PLATE-1"]})
        return reply, {"input_tokens": 1600, "output_tokens": 300, "total_tokens": 1900}


def test_key_depends_on_sha_frame_prompt_and_model():
    k = vision.request_key("aa", 18.0, "p", "m")
    assert k == vision.request_key("aa", 18.0, "p", "m")
    assert len({k, vision.request_key("bb", 18.0, "p", "m"), vision.request_key("aa", 90.0, "p", "m"),
                vision.request_key("aa", 18.0, "q", "m"), vision.request_key("aa", 18.0, "p", "n")}) == 5


def test_record_then_replay_needs_no_key_or_decoding(run_dir, tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    case = Case(run_dir)
    client = FakeClient()
    cfg = {"model": "m", "cache_mode": "record", "vision_client": client, "vision_cache_dir": str(tmp_path)}
    out, summary = vision.run(case, cfg)
    assert len(client.calls) == 23 and summary["recorded"] == 23 and summary["skipped"] == 0
    assert len(out) == 15
    v = out["EV-021"]
    assert v["origin"] == "llm" and v["certainty"] == "inferred" and v["model"] == "m"
    assert {o["frameS"] for o in v["observations"]} == {18.0, 90.0, 162.0}  # 10/50/90% of the 180 s clip
    assert all(o["frameS"] is None for o in out["EV-030"]["observations"])
    assert (tmp_path / summary["cache"]).read_text().count("\n") == 23

    def no_decode(*a, **k):
        raise AssertionError("replay must not decode")
    monkeypatch.setattr(vision, "to_jpeg", no_decode)
    monkeypatch.setattr(vision, "video_frame", no_decode)
    out2, s2 = vision.run(case, {"model": "m", "cache_mode": "replay", "vision_cache_dir": str(tmp_path)})
    assert out2 == out and s2["misses"] == 0 and s2["recorded"] == 0 and s2["mode"] == "replay"
    # another model is another key: skipped with a flag, never an error
    out3, s3 = vision.run(case, {"model": "other", "cache_mode": "replay", "vision_cache_dir": str(tmp_path)})
    assert out3 == {} and s3["skipped"] == 23
    # a missing cache file behaves the same
    out4, s4 = vision.run(case, {"model": "m", "cache_mode": "replay", "vision_cache_dir": str(tmp_path / "none")})
    assert out4 == {} and s4["skipped"] == 23


def test_prompt_forbids_identification():
    p = vision.PROMPT.lower()
    assert "do not identify" in p and "transcribe" in p and "intent" in p


def test_vision_never_changes_findings(run_dir, tmp_path):
    """Descriptions are attached to media cards only: every analysis item, gap and insight is identical with and
    without them, and so is what the replayed LLM cache sees."""
    llm = {"model": "claude-sonnet-5-5", "verifier_model": "claude-sonnet-5-5", "cache_mode": "replay"}
    plain = analyze(run_dir, tmp_path / "a", llm={**llm, "vision_cache_dir": str(tmp_path / "empty")})
    with_v = analyze(run_dir, tmp_path / "b", llm={**llm, "vision_client": FakeClient(), "cache_mode": "replay",
                                                   "vision_cache_dir": str(tmp_path / "vc")})

    def load(s, name):
        return json.loads((Path(s["out_dir"]) / name).read_text(encoding="utf-8"))

    a, b = load(plain, "analysis.json"), load(with_v, "analysis.json")
    for k in ("analysed_at", "llm", "version", "evidence"):
        a.pop(k, None), b.pop(k, None)
    assert a == b
    assert plain["llm"]["cache"]["hits"] == with_v["llm"]["cache"]["hits"]
    assert plain["llm"]["cache"]["misses"] == with_v["llm"]["cache"]["misses"]
    ba, bb = load(plain, "board.json"), load(with_v, "board.json")
    described = [n for n in bb["nodes"] if (n.get("media") or {}).get("vision")]
    assert len(described) == 15 and not any((n.get("media") or {}).get("vision") for n in ba["nodes"])
    for n in described:
        assert n["media"]["vision"]["citations"] == n["citations"]
        n["media"].pop("vision")
    for k in ("analysed_at", "audit", "subtitle", "sources"):
        ba.pop(k, None), bb.pop(k, None)
    assert ba == bb
    assert with_v["llm"]["vision"]["recorded"] == 23


def test_media_cards_do_not_change_what_the_llm_cache_sees(run_dir, tmp_path, monkeypatch):
    """Replay hits and misses are the same with the media stage switched off."""
    llm = {"model": "claude-sonnet-5-5", "verifier_model": "claude-sonnet-5-5", "cache_mode": "replay"}
    with_media = analyze(run_dir, tmp_path / "a", llm=dict(llm))
    monkeypatch.setattr(media_mod, "add_media", lambda *a, **k: {"media": 0, "edges": 0})
    without = analyze(run_dir, tmp_path / "b", llm=dict(llm))
    assert with_media["llm"]["cache"]["hits"] == without["llm"]["cache"]["hits"]
    assert with_media["llm"]["cache"]["misses"] == without["llm"]["cache"]["misses"]
    assert with_media["counts"] == without["counts"]
    assert without["llm"]["cache"]["misses"] == 0, "the committed analysis cache must replay fully (is PyAV installed?)"
