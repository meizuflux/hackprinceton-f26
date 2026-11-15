"""Read-only evidence viewer: every board citation opens its file at the cited row or line, files are never modified,
and responses stay windowed and safe."""

import hashlib
import importlib
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))

from mapletrace_api import viewer  # noqa: E402


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    from fastapi.testclient import TestClient
    from make_sample_case import build
    tmp = tmp_path_factory.mktemp("viewer")
    z = build(tmp / "case.zip")
    mp = pytest.MonkeyPatch()
    mp.setenv("MAPLETRACE_DATA", str(tmp / "data"))
    import mapletrace_api.app as appmod
    importlib.reload(appmod)
    client = TestClient(appmod.app)
    with open(z, "rb") as fh:
        r = client.post("/upload", files={"file": ("harbor.zip", fh, "application/zip")})
    assert r.status_code == 200, r.text
    case_id = r.json()["caseId"]
    assert client.get(f"/status/{r.json()['jobId']}").json()["status"] == "ready"
    case_dir = tmp / "data" / "cases" / case_id
    ingest_dir = next(p for p in (case_dir / "ingest").iterdir() if (p / "case.db").exists())
    yield client, case_id, ingest_dir
    mp.undo()


def _view(client, case_id, ev, **params):
    r = client.get(f"/cases/{case_id}/evidence/{ev}/view", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _highlighted(view: dict) -> list[str]:
    body = view.get("table") or view.get("lines")
    out = []
    for rng in view["target"]["ranges"]:
        for i in range(rng["start"], rng["end"] + 1):
            item = body["items"][i - body["offset"]]
            text = " ".join(item["cells"]) if "cells" in item else item["text"]
            if "colStart" in rng:
                text = text[rng["colStart"]:rng["colEnd"]]
            out.append(text)
    return out


def test_every_board_citation_resolves_to_a_position(api):
    client, case_id, _ = api
    board = client.get(f"/cases/{case_id}").json()
    kinds = set()
    for src in board["sources"]:
        ev, loc = src["metadata"]["evidence_id"], src["metadata"]["locator"]
        assert src["id"] == f"{ev}:{loc}"
        v = _view(client, case_id, ev, locator=loc)
        kinds.add(v["kind"])
        t = v["target"]
        assert t["resolved"], (src["id"], v["notes"])
        assert len(t["recordIds"]) >= 1
        if v["kind"] in ("table", "text", "json", "document"):
            assert t["ranges"], (src["id"], t)
            body = v.get("table") or v.get("lines")
            assert body["offset"] <= t["ranges"][0]["start"] < body["offset"] + len(body["items"])
            text = " ".join(_highlighted(v))
            if v["kind"] in ("text", "document") and src["excerpt"] and v["format"] not in ("eml", "mbox", "gpx", "kml"):
                # the highlighted span is the cited sentence or turn, as stored
                words = src["excerpt"].split()[:3]
                assert all(w in text for w in words), (src["id"], text, src["excerpt"])
        else:
            assert t["whole"] or t["page"]
    assert {"table", "text"} <= kinds


def test_table_rows_match_ingestion_numbering(api):
    client, case_id, ingest_dir = api
    files = client.get(f"/cases/{case_id}/files").json()
    sms = next(f for f in files if f["filename"] == "sms_export.csv")
    v = _view(client, case_id, sms["evidenceId"], locator="row=4")
    assert v["kind"] == "table" and v["table"]["columns"] == ["Date/Time", "From", "To", "Message"]
    assert v["table"]["total"] == 8
    assert v["target"]["ranges"] == [{"start": 2, "end": 2}]
    row = v["table"]["items"][2]
    assert row["row"] == 4 and row["line"] == 4 and row["cells"][3] == "yeah. back door, they only have cameras out front"


def test_formats_documents_json_media_and_binary(api):
    client, case_id, _ = api
    files = {f["filename"]: f for f in client.get(f"/cases/{case_id}/files").json()}
    docx = _view(client, case_id, files["witness_statement_tbriggs.docx"]["evidenceId"])
    assert docx["kind"] == "document" and docx["lines"]["unit"] == "paragraph" and docx["lines"]["items"]
    js = _view(client, case_id, files["sms_backup.json"]["evidenceId"])
    assert js["kind"] in ("json", "text") and js["lines"]["total"] > 3
    img = _view(client, case_id, files["IMG_2041.JPG"]["evidenceId"])
    assert img["kind"] == "image" and img["mediaType"] == "image/jpeg" and "lines" not in img
    vid = _view(client, case_id, files["cam2_rear_door.mp4"]["evidenceId"])
    assert vid["kind"] == "video"
    gpx = _view(client, case_id, files["vehicle_gps_vance.gpx"]["evidenceId"])
    assert gpx["kind"] == "text"
    zipped = _view(client, case_id, files["old_phone_backup.zip"]["evidenceId"])
    assert zipped["kind"] == "binary" and "table" not in zipped and "lines" not in zipped

    r = client.get(f"/cases/{case_id}/evidence/{files['IMG_2041.JPG']['evidenceId']}", params={"inline": True})
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert r.headers["content-disposition"].startswith("inline")
    assert r.headers["x-content-type-options"] == "nosniff"
    # text is never served inline, so a stored file can never render as a page on the API origin
    r = client.get(f"/cases/{case_id}/evidence/{files['sms_export.csv']['evidenceId']}", params={"inline": True})
    assert r.headers["content-disposition"].startswith("attachment")
    assert r.headers["content-type"] == "application/octet-stream" and "sandbox" in r.headers["content-security-policy"]


def test_windowing_paging_and_errors(api):
    client, case_id, _ = api
    files = {f["filename"]: f for f in client.get(f"/cases/{case_id}/files").json()}
    loc = files["phone_location_dvance.csv"]
    full = _view(client, case_id, loc["evidenceId"])
    total = full["table"]["total"]
    page = _view(client, case_id, loc["evidenceId"], offset=10, limit=5)
    assert page["table"]["total"] == total and [r["row"] for r in page["table"]["items"]] == [12, 13, 14, 15, 16]
    last = _view(client, case_id, loc["evidenceId"], locator=f"row={total + 1}", limit=10)
    assert last["target"]["ranges"] == [{"start": total - 1, "end": total - 1}]
    assert any(r["row"] == total + 1 for r in last["table"]["items"]), "the window covers the cited row"
    missing = _view(client, case_id, loc["evidenceId"], locator="seq=does-not-exist")
    assert missing["target"]["resolved"] is False and missing["target"]["ranges"] == [] and missing["notes"]
    bad = client.get(f"/cases/{case_id}/evidence/{loc['evidenceId']}/view", params={"limit": viewer.MAX_LIMIT + 1})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "bad_paging"
    assert client.get(f"/cases/{case_id}/evidence/EV-NOPE/view").status_code == 404
    assert client.get(f"/cases/{case_id}/evidence/..%2F..%2Fcase.json/view").status_code == 404


def test_viewer_never_writes_and_refuses_paths_outside_evidence(api, tmp_path):
    client, case_id, ingest_dir = api
    db = ingest_dir / "case.db"
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    files = con.execute("SELECT external_id, file_id, stored_path, sha256 FROM evidence_files").fetchall()
    con.close()
    for ev, fid, _, _ in files:
        _view(client, case_id, ev or f"FILE-{fid}", locator="row=2")
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    for _, _, stored, sha in files:
        assert hashlib.sha256((ingest_dir / stored).read_bytes()).hexdigest() == sha

    with pytest.raises(viewer.ViewError) as exc:
        viewer.stored_file(ingest_dir, "evidence/../case.db")
    assert exc.value.status == 403
    with pytest.raises(viewer.ViewError):
        viewer.stored_file(ingest_dir, "../../../etc/hosts")


def test_records_filter_by_type(api):
    client, case_id, _ = api
    everything = client.get(f"/cases/{case_id}/records", params={"limit": 1}).json()
    types = everything["types"]
    assert types and sum(types.values()) == everything["total"]
    kind, count = next(iter(types.items()))
    page = client.get(f"/cases/{case_id}/records", params={"recordType": kind, "limit": 500}).json()
    assert page["total"] == count and {i["recordType"] for i in page["items"]} == {kind}
    assert page["types"] == types, "type counts ignore the type filter itself"


def test_pretty_json_paths_and_line_caps():
    lines, spans = viewer.pretty_json({"timelineObjects": [{"placeVisit": {"id": "PV-1"}}, {"activitySegment": {}}]})
    first, last = spans[viewer._parse_path("timelineObjects[0].placeVisit")]
    assert lines[first].strip().startswith('"placeVisit"') and lines[last].strip().startswith("}")
    assert viewer._parse_path("a..b") is None
    assert viewer._cap("x" * (viewer.MAX_LINE_CHARS + 5)) == ("x" * viewer.MAX_LINE_CHARS, True)
