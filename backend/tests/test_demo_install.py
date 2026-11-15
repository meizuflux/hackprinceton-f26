"""POST /demo reinstalls a stale demo (no run trace, or another snapshot) and keeps investigator overrides."""

import importlib
import io
import json
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _snapshot(path: Path, board_title: str) -> None:
    """A minimal snapshot: case.json with one version, its trace and a board."""
    files = {
        "./case.json": json.dumps({"caseId": "kestrel-demo", "title": "Kestrel", "uploads": [
            {"filename": "k.zip", "sha256": "0" * 64, "bytes": 1, "stored": "upload_1.zip"}],
            "versions": [{"version": 1, "ingest_dir": "ingest/v1", "analysis_dir": "ingest/v1/analysis/v1"}],
            "latest": 0}),
        "./ingest/v1/trace.jsonl": '{"type": "run_started"}\n',
        "./ingest/v1/analysis/v1/board.json": json.dumps({"title": board_title, "nodes": [], "edges": []}),
    }
    with tarfile.open(path, "w:gz") as t:
        for name, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))


def test_demo_reinstalls_when_stale_and_keeps_overrides(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv("MAPLETRACE_DATA", str(tmp_path / "data"))
    import mapletrace_api.app as appmod
    importlib.reload(appmod)
    snap = tmp_path / "kestrel.tar.gz"
    monkeypatch.setattr(appmod, "DEMO_SNAPSHOT", snap)
    monkeypatch.setattr(appmod, "DEMO_ARCHIVE", tmp_path / "absent.zip")
    reapplied = []
    monkeypatch.setattr(appmod, "_reanalyse", lambda job_id, case_id, v: reapplied.append((case_id, v["ingest_dir"])))
    client = TestClient(appmod.app)
    case = tmp_path / "data" / "cases" / "kestrel-demo"

    _snapshot(snap, "first")
    assert client.post("/demo").json() == {"caseId": "kestrel-demo"}
    assert (case / "demo_snapshot.sha256").read_text() == appmod._demo_snapshot_sha256()
    board = case / "ingest/v1/analysis/v1/board.json"
    assert json.loads(board.read_text())["title"] == "first"

    # current install: reused as is (a local edit survives)
    board.write_text(json.dumps({"title": "edited"}))
    assert client.post("/demo").json() == {"caseId": "kestrel-demo"}
    assert json.loads(board.read_text())["title"] == "edited"

    # an install from before the run trace existed is replaced; overrides are kept and re-applied
    (case / "ingest/v1/trace.jsonl").unlink()
    (case / "overrides.jsonl").write_text('{"target_key": "k", "action": "dismiss"}\n')
    r = client.post("/demo").json()
    assert r["caseId"] == "kestrel-demo" and r["jobId"]
    assert (case / "ingest/v1/trace.jsonl").exists()
    assert json.loads(board.read_text())["title"] == "first"
    assert (case / "overrides.jsonl").read_text() == '{"target_key": "k", "action": "dismiss"}\n'
    assert reapplied == [("kestrel-demo", "ingest/v1")]

    # a new snapshot replaces an install made from the old one (no stamp counts as old too)
    _snapshot(snap, "second")
    assert "jobId" in client.post("/demo").json()
    assert json.loads(board.read_text())["title"] == "second"
    (case / "demo_snapshot.sha256").unlink()
    (case / "overrides.jsonl").unlink()
    assert client.post("/demo").json() == {"caseId": "kestrel-demo"}
    assert (case / "demo_snapshot.sha256").exists()
    assert not [d for d in (tmp_path / "data" / "cases").iterdir() if d.name.startswith(".demo")]
