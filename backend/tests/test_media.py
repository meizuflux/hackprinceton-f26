"""Media cards and rule-backed links on the board (backend/MEDIA.md)."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mapletrace_ingest.pipeline import ingest_zip  # noqa: E402
from mapletrace_ingest.trace import TraceWriter  # noqa: E402
from mapletrace_reason.pipeline import analyze  # noqa: E402

KESTREL_ZIP = ROOT.parent / "cases" / "kestrel" / "kestrel_case_upload.zip"


@pytest.fixture(scope="module")
def kestrel(tmp_path_factory):
    if not KESTREL_ZIP.exists():
        pytest.skip("Kestrel case not present in this checkout")
    run = tmp_path_factory.mktemp("media") / "k"
    ingest_zip(KESTREL_ZIP, run)
    trace = TraceWriter(run / "trace.jsonl")
    summary = analyze(run, trace=trace)
    board = json.loads((Path(summary["out_dir"]) / "board.json").read_text(encoding="utf-8"))
    events = [json.loads(line) for line in (run / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    return run, board, events


def test_every_media_file_is_an_observed_card(kestrel):
    run, board, _ = kestrel
    cards = [n for n in board["nodes"] if n.get("media")]
    assert len(cards) == 15
    assert {c["media"]["kind"] for c in cards} == {"photo", "video"}
    sources = {s["id"] for s in board["sources"]}
    for c in cards:
        m = c["media"]
        assert c["type"] == "event" and c["certainty"] == "observed" and c["origin"] == "record" and c["stage"] == "ingest"
        assert c["evidenceIds"] == [m["evidenceId"]] and len(c["citations"]) == 1
        assert c["citations"][0].startswith(m["evidenceId"] + ":") and c["citations"][0] in sources
        assert m["capturedUtc"] and c["time"] == m["capturedUtc"]
        assert set(m) >= {"evidenceId", "kind", "mediaType", "captureSource", "timeFlags", "durationS", "width",
                          "height", "deviceMake", "deviceModel", "gps"}
        assert "vision" not in m, "no vision output without --llm"
        assert (m["kind"] == "video") == (m["durationS"] is not None)
    photo = next(c for c in cards if c["media"]["evidenceId"] == "EV-030")["media"]
    assert photo["deviceModel"] == "D7500" and photo["gps"]["lat"] == pytest.approx(37.3862, abs=1e-3)
    assert photo["mediaType"] == "image/jpeg"


def test_media_edges_cite_both_ends_and_follow_certainty_rules(kestrel):
    _, board, _ = kestrel
    nodes = {n["id"]: n for n in board["nodes"]}
    edges = [e for e in board["edges"] if e["stage"] == "media_links"]
    assert edges
    for e in edges:
        a, b = nodes[e["source"]], nodes[e["target"]]
        assert e["origin"] == "rules" and e["basis"].startswith(e["rule"] + ":")
        assert set(e["citations"]) & set(a["citations"]), "cites the media end"
        assert set(e["citations"]) & set(b["citations"]), "cites the other end"
        assert e["certainty"] == ("inferred" if e["rule"] == "place" else "observed")
        assert e["directed"] is False
        assert "evidenceIds" in e and e["evidenceIds"]
    place = [e for e in edges if e["rule"] == "place"]
    assert all(" m from the centre of " in e["basis"] for e in place)


def test_kestrel_edges_per_rule(kestrel):
    _, board, _ = kestrel
    by_rule = {}
    for e in board["edges"]:
        if e["stage"] == "media_links":
            by_rule.setdefault(e["rule"], []).append(e)
    assert {r: len(v) for r, v in by_rule.items()} == {"vms_export": 4, "capture_device": 10, "place": 9}
    clips = {e["source"]: e["target"] for e in by_rule["vms_export"]}
    assert clips["media-EV-021"] == clips["media-EV-022"], "both P2 clips join the one camera card"
    assert clips["media-EV-020"] != clips["media-EV-021"]
    unlinked = {n["id"] for n in board["nodes"] if n.get("media")} - {e["source"] for es in by_rule.values() for e in es}
    # no rule-backed link (kiosk photo without GPS; a GPS fix ~600 m from any cluster, whose device is shared though)
    assert "media-EV-040" in unlinked


def test_media_cards_stay_out_of_gaps(kestrel):
    _, board, _ = kestrel
    media_ids = {n["id"] for n in board["nodes"] if n.get("media")}
    for g in board["gaps"]:
        assert not media_ids & set(g["nodeIds"])
    assert not any(n["type"] == "statement" and n.get("stage") == "media_links" for n in board["nodes"])


def test_trace_has_media_links_stage(kestrel):
    _, _, events = kestrel
    ev = [e for e in events if e["type"] == "stage_finished" and e["stage"] == "media_links"]
    assert len(ev) == 1 and ev[0]["counts"]["media"] == 15 and ev[0]["counts"]["edges"] == 23


def test_layout_gives_media_cards_distinct_positions(kestrel):
    _, board, _ = kestrel
    pos = [(n["position"]["x"], n["position"]["y"]) for n in board["nodes"]]
    assert len(set(pos)) == len(pos)
