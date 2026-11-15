"""Formats seen in the team's Kestrel case: evidence manifests with per-file time basis, line-numbered
transcripts, phone exports with party+direction columns, iCalendar, and Google semantic location history."""

import hashlib
import json
import sqlite3
import sys
import zipfile
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mapletrace_ingest.pipeline import ingest_zip  # noqa: E402
from mapletrace_ingest.timeparse import parse_timestamp  # noqa: E402

KESTREL_ZIP = ROOT.parent / "cases" / "kestrel" / "kestrel_case_upload.zip"

PHONE = (
    "record_id,timestamp,direction,party_number,body\n"
    "M1,2026-10-17 21:00:00,Outgoing,+14085550147,meet at the garage\n"
    "M2,2026-10-17 21:05:00,Incoming,+14085550147,ok\n"
)
TRANSCRIPT = (
    "[0001] SOUTH BAY POLICE DEPARTMENT - INTERVIEW TRANSCRIPT\n"
    "[0002] Subject: Ann Smith (interview 1)\n"
    "[0003] Present: Det. Ana Reyes, Ann Smith\n\n"
    "[0004] REYES: Where were you on Saturday 10/17?\n"
    "[0005] SMITH: At home all evening.\n"
    "[0006] REYES: Did you go to the office?\n"
    "[0007] SMITH: No.\n"
)
ICS = (
    "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nX-WR-CALNAME:Ann Smith\r\nBEGIN:VEVENT\r\nUID:E1\r\n"
    "DTSTART;TZID=America/Los_Angeles:20261017T190000\r\nDTEND;TZID=America/Los_Angeles:20261017T203000\r\n"
    "SUMMARY:Board dinner\r\nLOCATION:Room 4-12\r\nATTENDEE:mailto:ann@example.com\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
)
TIMELINE = json.dumps({"timelineObjects": [
    {"placeVisit": {"visitId": "PV1", "location": {"latitudeE7": 373712000, "longitudeE7": -1221374000, "name": "Home"},
                    "duration": {"startTimestamp": "2026-10-18T02:00:00.000Z", "endTimestamp": "2026-10-18T06:00:00.000Z"},
                    "placeConfidence": "LOW_CONFIDENCE"}},
]})


def _manifest(files: dict[str, bytes], wrong_hash_for: str) -> str:
    rows = ["evidence_id,path,sha256,custodian,time_basis"]
    basis = {"msgs/smith_phone.csv": "local wall time (PDT), no offset", "loc/smith_timeline.json": "UTC ISO-8601 (Z)"}
    for i, (p, data) in enumerate(files.items(), 1):
        sha = "0" * 64 if p == wrong_hash_for else hashlib.sha256(data).hexdigest()
        rows.append(f"EV-{i:03d},{p},{sha},Ann Smith,{basis.get(p, 'n/a')}")
    return "\n".join(rows) + "\n"


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("fmt")
    files = {"msgs/smith_phone.csv": PHONE.encode(), "intv/smith.txt": TRANSCRIPT.encode(),
             "logs/cal.ics": ICS.encode(), "loc/smith_timeline.json": TIMELINE.encode()}
    z = tmp / "case.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for p, data in files.items():
            zf.writestr(f"case/evidence/{p}", data)
        zf.writestr("case/evidence/MANIFEST.csv", _manifest(files, wrong_hash_for="logs/cal.ics"))
    report = ingest_zip(z, tmp / "run")
    return sqlite3.connect(tmp / "run" / "case.db"), report


def q(con, sql):
    return con.execute(sql).fetchall()


def test_negative_numbers_are_not_epoch_times():
    assert parse_timestamp("-1221374000", ZoneInfo("UTC")) is None


def test_manifest_hashes_ids_and_time_basis(run):
    con, report = run
    assert report["manifest_check"]["matched"] == 3
    assert report["manifest_check"]["mismatched"] == ["logs/cal.ics"]
    assert report["case"]["assumed_timezone"] == "America/Los_Angeles"
    ids = dict(q(con, "SELECT original_path, external_id FROM evidence_files WHERE external_id IS NOT NULL"))
    assert ids["case/evidence/msgs/smith_phone.csv"] == "EV-001"


def test_phone_export_uses_local_basis_and_owner(run):
    con, _ = run
    rows = q(con, "SELECT ts_utc, actor, target FROM records WHERE record_type='message' ORDER BY record_id")
    assert rows[0] == ("2026-10-18T04:00:00Z", "Ann Smith", "+14085550147")  # 21:00 PDT, outgoing
    assert rows[1][1:] == ("+14085550147", "Ann Smith")  # incoming


def test_line_numbered_transcript(run):
    con, _ = run
    rows = q(con, "SELECT actor, json_extract(attributes_json,'$.speaker_role'), json_extract(locator_json,'$.doc_line'), content "
                  "FROM records WHERE record_type='interview_turn' ORDER BY record_id")
    assert rows[0][:3] == ("Det. Ana Reyes", "interviewer", 4)
    assert rows[1][:3] == ("Ann Smith", "interviewee", 5) and rows[1][3] == "At home all evening."


def test_icalendar_event(run):
    con, _ = run
    (ts, start, end, content), = q(con, "SELECT ts_utc, ts_start_utc, ts_end_utc, content FROM records WHERE record_type='calendar_event'")
    assert (start, end) == ("2026-10-18T02:00:00Z", "2026-10-18T03:30:00Z")
    assert content == "Board dinner @ Room 4-12"


def test_semantic_location_history(run):
    con, _ = run
    (lat, lon, start, end, attrs), = q(con, "SELECT lat, lon, ts_start_utc, ts_end_utc, attributes_json FROM records WHERE record_type='place_visit'")
    assert (round(lat, 4), round(lon, 4)) == (37.3712, -122.1374)
    assert (start, end) == ("2026-10-18T02:00:00Z", "2026-10-18T06:00:00Z")
    assert json.loads(attrs)["low_confidence"] is True


@pytest.mark.skipif(not KESTREL_ZIP.exists(), reason="Kestrel case not present in this checkout")
def test_kestrel_case_ingests_cleanly(tmp_path):
    report = ingest_zip(KESTREL_ZIP, tmp_path / "kestrel")
    statuses = {f["status"] for f in report["files"]}
    assert statuses <= {"parsed"}, [f for f in report["files"] if f["status"] != "parsed"]
    assert report["manifest_check"]["mismatched"] == [] and report["manifest_check"]["matched"] == 56
    assert {"interview", "statement", "calendar", "location", "messages", "call_log", "dna", "photo", "video", "email"} \
        <= set(report["by_evidence_type"])
    assert report["case"]["assumed_timezone"] == "America/Los_Angeles"
