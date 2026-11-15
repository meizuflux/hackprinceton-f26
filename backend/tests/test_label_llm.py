"""Display labels: deterministic rules on the Kestrel board, and the optional LLM labels (cache keying, replay without a
key, silent skip without a cache, isolation from the reasoning and from every model input)."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mapletrace_ingest.pipeline import ingest_zip  # noqa: E402
from mapletrace_reason import label_llm, labels  # noqa: E402
from mapletrace_reason.pipeline import analyze  # noqa: E402
from mapletrace_reason.store import Case  # noqa: E402

KESTREL_ZIP = ROOT.parent / "cases" / "kestrel" / "kestrel_case_upload.zip"
LLM = {"model": "claude-sonnet-5-5", "verifier_model": "claude-sonnet-5-5", "cache_mode": "replay"}
DISPLAY = ("displayLabel", "displaySummary", "labelOrigin")


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory):
    if not KESTREL_ZIP.exists():
        pytest.skip("Kestrel case not present in this checkout")
    run = tmp_path_factory.mktemp("labels") / "k"
    ingest_zip(KESTREL_ZIP, run)
    return run


@pytest.fixture(scope="module")
def plain(run_dir, tmp_path_factory):
    """Replay of the committed analysis cache with no label cache: rules labels only."""
    s = analyze(run_dir, tmp_path_factory.mktemp("plain"), llm={**LLM, "label_cache_dir": str(run_dir / "none")})
    return s, _load(s, "board.json")


def _load(summary, name):
    return json.loads((Path(summary["out_dir"]) / name).read_text(encoding="utf-8"))


class FakeLabeler:
    def __init__(self):
        self.prompts = []

    def label(self, prompt):
        self.prompts.append(prompt)
        card = json.loads(prompt.split("Card data:\n", 1)[1])
        return json.dumps({"label": "Readable title", "summary": f"A plain sentence about a {card['type']} card."}), \
            {"input_tokens": 300, "output_tokens": 30}


# ---------------------------------------------------------------- rules
def test_rules_labels_on_kestrel(plain):
    _, board = plain
    nodes = {n["id"]: n for n in board["nodes"]}
    assert nodes["loc-SC-EBC-01"]["displayLabel"] == "Secure demo cabinet · EBC 4-12"
    assert nodes["loc-SC-EBC-01"]["label"] == "SC-EBC-01", "the original label is never changed"
    assert nodes["loc-AUR-EXEC-0001"]["displayLabel"] == "CEO desktop workstation · Office 4-01"
    rfid = next(n for n in board["nodes"] if n["label"].startswith("scan_id=RF-"))
    assert rfid["displayLabel"].startswith("Tag ES-0007") and "=" not in rfid["displaySummary"]
    phone = next(n for n in board["nodes"] if n["label"] == "+14085550147")
    assert phone["displayLabel"] == "Phone · Vince (Supply)" and "saved as" in phone["displaySummary"]
    surname = next(n for n in board["nodes"] if n["label"] == "HALVORSEN")
    assert surname["displayLabel"] == "Halvorsen (likely Richard Halvorsen)"
    clip = nodes["media-EV-021"]
    assert clip["displayLabel"] == "Garage P2 camera · 21:35–21:38"
    labelled = [n for n in board["nodes"] if "displayLabel" in n or "displaySummary" in n]
    assert len(labelled) > 40
    for n in labelled:
        assert n["labelOrigin"] == "rules"
        assert len(n.get("displayLabel", "")) <= labels.MAX_LABEL
        assert n.get("displayLabel") != n["label"]
    # file names for the source panel come from MANIFEST.csv titles
    src = {s["id"]: s for s in board["sources"]}
    assert all(s.get("fileLabel") for s in src.values())
    assert any(s["fileLabel"] == "Workstation AUR-EXEC-0001 security and activity events" for s in src.values())


def test_rules_labels_change_nothing_else(run_dir, plain, tmp_path, monkeypatch):
    """Without the labelling step the board is identical apart from the display fields."""
    with_labels = json.loads(json.dumps(plain[1]))
    monkeypatch.setattr(labels, "apply", lambda *a, **k: None)
    monkeypatch.setattr(labels, "file_label", lambda f: None)
    without = _load(analyze(run_dir, tmp_path, llm={**LLM, "label_cache_dir": str(tmp_path / "none")}), "board.json")
    for b in (with_labels, without):
        for k in ("analysed_at", "audit", "subtitle"):
            b.pop(k, None)
        for n in b["nodes"]:
            for k in DISPLAY:
                n.pop(k, None)
        for s in b["sources"]:
            s.pop("fileLabel", None)
    assert with_labels == without


def test_directory_and_helpers(run_dir):
    d = labels.Directory(Case(run_dir))
    assert d.find("CAM-E-P2-02").room == "Garage P2"
    assert d.find("p2 garage elevator lobby door").id == "E-P2-ELEV"
    assert d.find("Lobby") is None, "rooms are not entries"
    assert labels.person_name("CHEN, ANDREW") == "Andrew Chen"
    assert labels.person_name("DELGADO, RAY (AEGIS)") == "Ray Delgado (Aegis)"
    assert labels.person_name("Vivian Shen") == "Vivian Shen"
    assert labels.humanize_code("DOOR_HELD_OPEN") == "Door held open"
    assert labels.phone_number("+14085550147") == "+1 408-555-0147"
    assert len(labels.fit("word " * 20)) <= labels.MAX_LABEL


# ---------------------------------------------------------------- optional LLM labels
def test_key_and_reply_validation():
    k = label_llm.request_key("card", "p", "m")
    assert len({k, label_llm.request_key("card2", "p", "m"), label_llm.request_key("card", "q", "m"),
                label_llm.request_key("card", "p", "n")}) == 4
    src = '{"title": "scan_id=RF-00111; tag_id=ES-0007"}'
    assert label_llm.parse_reply('{"label": "Tag ES-0007 scan", "summary": "A scan."}', src)
    assert label_llm.parse_reply('```json\n{"label": "Tag ES-0007", "summary": ""}\n```', src)
    assert label_llm.parse_reply('{"label": "Tag ES-0007 at 22:51", "summary": ""}', src) is None, "invented time"
    assert label_llm.parse_reply('{"label": "' + "x" * 45 + '"}', src) is None, "too long"
    assert label_llm.parse_reply("not json", src) is None
    assert label_llm.DEFAULT_MODEL == "claude-haiku-5-5"


def test_record_replay_and_silent_skip(run_dir, plain, tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    case = Case(run_dir)
    _, board = plain
    fresh = lambda: json.loads(json.dumps(board))  # noqa: E731
    # no cache file and no client: skipped silently, board untouched
    b0 = fresh()
    assert label_llm.run(case, b0, {"label_cache_dir": str(tmp_path / "none")}) is None and b0 == board
    # record mode without a key never calls anything either
    assert label_llm.run(case, fresh(), {"label_mode": "record", "label_cache_dir": str(tmp_path / "none")}) is None

    client = FakeLabeler()
    b1 = fresh()
    s1 = label_llm.run(case, b1, {"label_mode": "record", "label_client": client, "label_cache_dir": str(tmp_path)})
    assert s1["recorded"] == len(client.prompts) > 0 and s1["skipped"] == 0 and s1["model"] == "claude-haiku-5-5"
    llm_nodes = [n for n in b1["nodes"] if n.get("labelOrigin") == "llm"]
    assert len(llm_nodes) == s1["labelled"] == len(client.prompts)
    for n in llm_nodes:
        assert n["displayLabel"] == "Readable title" and not n.get("media")
        orig = next(o for o in board["nodes"] if o["id"] == n["id"])
        assert n["label"] == orig["label"] and n["summary"] == orig["summary"] and "displayLabel" not in orig
    # rules labels are never overwritten
    assert all(n["labelOrigin"] == "rules" for n in b1["nodes"] if n.get("labelOrigin") and n not in llm_nodes)
    # the model never sees vision descriptions or media cards
    vision_texts = [n["media"]["vision"]["text"] for n in board["nodes"] if (n.get("media") or {}).get("vision")]
    assert vision_texts, "the replayed demo has image descriptions to leak"
    assert not any(v[:40] in p for v in vision_texts for p in client.prompts)

    b2 = fresh()
    s2 = label_llm.run(case, b2, {"label_cache_dir": str(tmp_path)})
    assert b2 == b1 and s2["misses"] == 0 and s2["recorded"] == 0 and s2["mode"] == "replay"


def test_llm_labels_never_change_findings_or_model_inputs(run_dir, plain, tmp_path):
    """Every analysis item, gap and insight is identical with and without LLM labels, and so are the investigator's
    replayed cache hits; the labels only touch display fields of the cards they name."""
    a_sum, a_board = plain
    b_sum = analyze(run_dir, tmp_path / "b", llm={**LLM, "label_mode": "record", "label_client": FakeLabeler(),
                                                  "label_cache_dir": str(tmp_path / "lc")})
    a, b = _load(a_sum, "analysis.json"), _load(b_sum, "analysis.json")
    assert b["llm"]["labels"]["labelled"] > 0 and "labels" not in a["llm"]
    for k in ("analysed_at", "llm", "version", "evidence"):
        a.pop(k, None), b.pop(k, None)
    assert a == b
    assert a_sum["llm"]["cache"]["hits"] == b_sum["llm"]["cache"]["hits"]
    assert b_sum["llm"]["cache"]["misses"] == 0
    ba, bb = json.loads(json.dumps(a_board)), _load(b_sum, "board.json")
    for brd in (ba, bb):
        for k in ("analysed_at", "audit", "subtitle"):
            brd.pop(k, None)
        for n in brd["nodes"]:
            if n.get("labelOrigin") == "llm":
                for k in DISPLAY:
                    n.pop(k, None)
    assert ba == bb
