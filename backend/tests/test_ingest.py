import json
import sqlite3
import sys
import zipfile
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))

from mapletrace_ingest.__main__ import main as cli  # noqa: E402
from mapletrace_ingest.classify import classify_table, classify_text  # noqa: E402
from mapletrace_ingest.intake import Limits, extract_zip  # noqa: E402
from mapletrace_ingest.pipeline import ingest_zip  # noqa: E402
from mapletrace_ingest.timeparse import HumanTimeResolver, parse_timestamp  # noqa: E402

NY = ZoneInfo("America/New_York")


# ----------------------------------------------------------------- time
def test_epoch_milliseconds():
    tv = parse_timestamp("1773540000000", NY)
    assert tv.as_columns()["ts_utc"] == "2026-03-15T02:00:00Z"
    assert "epoch_milliseconds" in tv.flags


def test_naive_time_is_localized_and_flagged():
    tv = parse_timestamp("2026-03-14 23:38:10", NY)
    assert tv.as_columns()["ts_utc"] == "2026-03-15T03:38:10Z"
    assert "tz_assumed" in tv.flags


def test_explicit_offset_not_flagged():
    tv = parse_timestamp("2026-03-14T23:49:00-04:00", NY)
    assert tv.flags == [] and tv.as_columns()["ts_utc"] == "2026-03-15T03:49:00Z"


def test_ambiguous_day_month_is_flagged():
    assert "day_month_ambiguous" in parse_timestamp("03/12/2026 18:02", NY).flags
    assert "day_month_ambiguous" not in parse_timestamp("03/14/2026 18:02", NY).flags


def test_time_of_day_without_date_is_rejected():
    assert parse_timestamp("23:15", NY) is None


def test_human_times_follow_narrative_and_roll_over_midnight():
    r = HumanTimeResolver(NY, date(2026, 3, 14))
    a = r.resolve("At around 11:30 pm I heard a bang.")[0].value
    b = r.resolve("Shortly after 11:45 he left.")[0].value
    c = r.resolve("I got there at about 12:05 am.")[0].value
    assert a.as_columns()["ts_utc"] == "2026-03-15T03:30:00Z"
    assert (a.end - a.start).total_seconds() == 3600  # "around" -> +/- 30 min
    assert b.utc.astimezone(NY).hour == 23 and "am_pm_inferred_from_sequence" in b.flags
    assert c.utc.astimezone(NY).date() == date(2026, 3, 15) and "date_rolled_overnight" in c.flags


def test_human_time_without_any_date_is_not_placed():
    tv = HumanTimeResolver(NY, None).resolve("I left at 9:15 pm.")[0].value
    assert tv.utc is None and "date_unknown" in tv.flags


# ------------------------------------------------------------ classify
def test_table_classification():
    p = Path("x.csv")
    assert classify_table(p, ["Date/Time", "From", "To", "Message"], [{}]).evidence_type == "messages"
    assert classify_table(p, ["timestamp", "latitude", "longitude"], [{}]).evidence_type == "location"
    assert classify_table(p, ["time", "caller", "callee", "duration_s"], [{}]).evidence_type == "call_log"
    assert classify_table(p, ["Name", "Phone", "Email"], [{}]).evidence_type == "contacts"
    assert classify_table(p, ["sample_id", "locus", "allele_1", "allele_2"], [{}]).evidence_type == "dna"
    assert classify_table(p, ["Sample", "D8S1179", "D21S11", "TH01", "FGA"], [{}]).evidence_type == "dna"


def test_text_classification():
    p = Path("doc.txt")
    interview = "Det. Ruiz: Where were you?\nJohn Doe: Home.\nDet. Ruiz: All night?\nJohn Doe: Yes.\n"
    assert classify_text(p, interview).evidence_type == "interview"
    chat = "\n".join(f"3/14/26, 8:1{i} PM - Ann: hello {i}" for i in range(5))
    assert classify_text(p, chat).evidence_type == "messages"
    statement = "I was walking my dog when I saw a man. I heard a crash. I was scared and I called the police."
    assert classify_text(p, statement).evidence_type == "statement"


# -------------------------------------------------------------- intake
def test_zip_slip_and_absolute_paths_are_skipped(tmp_path):
    z = tmp_path / "evil.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("../escape.txt", "x")
        zf.writestr("/abs.txt", "x")
        zf.writestr("ok/fine.txt", "hello")
    warnings = []
    members = extract_zip(z, tmp_path / "out", Limits(), lambda a, d: warnings.append(a))
    assert [m.original_path for m in members] == ["ok/fine.txt"]
    assert warnings.count("unsafe_path_skipped") == 2
    assert not (tmp_path / "escape.txt").exists()


# --------------------------------------------------------- end to end
@pytest.fixture(scope="module")
def demo_run(tmp_path_factory):
    from make_sample_case import build
    tmp = tmp_path_factory.mktemp("case")
    z = build(tmp / "case.zip")
    out = tmp / "run"
    report = ingest_zip(z, out)
    return out, report


def test_every_file_is_inventoried_and_none_failed(demo_run):
    out, report = demo_run
    statuses = {f["path"]: f["status"] for f in report["files"]}
    assert "failed" not in statuses.values()
    assert statuses["misc/device_dump.bin"] == "unsupported"
    assert "email/tip_from_neighbor.eml::plate_photo.jpg" in statuses  # attachment re-ingested
    assert "misc/old_phone_backup.zip::notes_from_old_phone.txt" in statuses  # nested archive expanded


def test_expected_types_detected(demo_run):
    _, report = demo_run
    types = set(report["by_evidence_type"])
    assert {"messages", "call_log", "location", "contacts", "photo", "video", "audio", "statement",
            "interview", "dna", "email", "records"} <= types


def test_records_are_traceable(demo_run):
    out, _ = demo_run
    con = sqlite3.connect(out / "case.db")
    rows = con.execute("SELECT r.locator_json, f.stored_path FROM records r JOIN evidence_files f USING(file_id)").fetchall()
    assert rows
    for loc, stored in rows:
        assert json.loads(loc), "every record needs a locator"
        assert (out / stored).exists()


def test_cleaning_and_dedup(demo_run):
    out, _ = demo_run
    con = sqlite3.connect(out / "case.db")
    skipped = con.execute("SELECT s.skip_reasons_json FROM inferred_schemas s JOIN evidence_files f USING(file_id) "
                          "WHERE f.original_path LIKE '%phone_location%'").fetchone()[0]
    assert json.loads(skipped) == {"invalid_coordinates": 1, "exact_duplicate_row": 1}
    assert con.execute("SELECT COUNT(*) FROM records WHERE duplicate_of IS NOT NULL").fetchone()[0] == 2
    assert con.execute("SELECT COUNT(*) FROM records WHERE record_type='location_fix' AND ts_utc IS NULL").fetchone()[0] == 0


def test_entity_resolution(demo_run):
    out, _ = demo_run
    con = sqlite3.connect(out / "case.db")
    canon = dict(con.execute("SELECT e.value_norm, c.display_name FROM entities e JOIN entities c ON c.entity_id = e.canonical_id"))
    assert canon["+16095550142"] == "Daniel Vance"
    assert canon["dan v"] == "Daniel Vance"
    assert canon["filename:vance"] == "Daniel Vance"
    assert canon["+16095550187"] == "Marcus Ortiz"
    assert canon["iphone 14"] == "iPhone 14"  # devices are never merged into people


def test_statement_times_land_on_incident_night(demo_run):
    out, _ = demo_run
    con = sqlite3.connect(out / "case.db")
    ts = [r[0] for r in con.execute("SELECT ts_utc FROM records WHERE record_type='statement_claim' AND actor='Jamie Lee' AND ts_utc IS NOT NULL")]
    assert ts == ["2026-03-15T03:30:00Z", "2026-03-15T03:45:00Z", "2026-03-15T03:50:00Z", "2026-03-15T03:52:00Z"]


def test_verify_detects_tampering(demo_run, capsys):
    out, _ = demo_run
    assert cli(["verify", str(out)]) == 0
    con = sqlite3.connect(out / "case.db")
    con.execute("UPDATE audit_log SET detail_json='{}' WHERE seq=3")
    con.commit()
    con.close()
    assert cli(["verify", str(out)]) == 1
