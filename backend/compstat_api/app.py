"""Compstat HTTP API (FastAPI).

Run:  uvicorn compstat_api.app:app --reload --port 8000      (from backend/)

    POST /upload                         ZIP -> new case; returns {jobId, caseId}
    GET  /status/{jobId}                 {status: processing|ready|failed, progress, message, stage, caseId}
    GET  /cases                          list cases
    GET  /case                           latest ready case as CaseData (matches the frontend's getCase())
    GET  /cases/{caseId}                 CaseData for one case (board.json)
    GET  /cases/{caseId}/{section}       graph | gaps | insights | suggestions | contradictions | explanations |
                                         timeline | audit | changes | sources
    GET  /cases/{caseId}/source?id=...   one cited record in full (source inspector)
    GET  /cases/{caseId}/evidence/{evidenceId}   original evidence file (read-only copy)
    POST /cases/{caseId}/evidence        add a ZIP of new evidence -> new version, compared with the previous one
    GET  /cases/{caseId}/overrides       investigator corrections
    POST /cases/{caseId}/overrides       record a correction -> re-analysis job

Case data lives under $COMPSTAT_DATA (default backend/data/cases/<caseId>/). Evidence is never modified.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import traceback
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from compstat_ingest.pipeline import ingest_zip
from compstat_reason import history
from compstat_reason.pipeline import analyze

DATA = Path(os.environ.get("COMPSTAT_DATA", Path(__file__).resolve().parents[1] / "data"))
MAX_UPLOAD = int(os.environ.get("COMPSTAT_MAX_UPLOAD_MB", "100")) * 1024 * 1024
SECTIONS = {"graph", "gaps", "insights", "suggestions", "contradictions", "explanations", "timeline", "audit", "changes",
            "sources", "nodes", "edges", "uncertainTimes", "missingPeriods", "sourceGroups"}
_lock = threading.Lock()

app = FastAPI(title="Compstat API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_methods=["*"], allow_headers=["*"],
                   allow_origins=os.environ.get("COMPSTAT_CORS", "http://localhost:5173,http://127.0.0.1:5173").split(","))


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


@app.exception_handler(ApiError)
async def _api_error(_: Request, exc: ApiError):
    return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}})


@app.exception_handler(HTTPException)
async def _http_error(_: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": "http_error", "message": str(exc.detail)}})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _cases() -> Path:
    (DATA / "cases").mkdir(parents=True, exist_ok=True)
    return DATA / "cases"


def _jobs() -> Path:
    (DATA / "jobs").mkdir(parents=True, exist_ok=True)
    return DATA / "jobs"


def _case_dir(case_id: str) -> Path:
    if not re.fullmatch(r"[a-z0-9-]{1,64}", case_id):
        raise ApiError(400, "bad_case_id", "invalid case id")
    d = _cases() / case_id
    if not (d / "case.json").exists():
        raise ApiError(404, "case_not_found", f"no case {case_id}")
    return d


def _read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(p: Path, obj) -> None:
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=str), encoding="utf-8")
    tmp.replace(p)


def _job(job_id: str, **update) -> dict:
    p = _jobs() / f"{job_id}.json"
    with _lock:
        job = _read_json(p) if p.exists() else {"jobId": job_id}
        job.update(update, updated=_now())
        _write_json(p, job)
    return job


async def _save_upload(file: UploadFile, dest: Path) -> dict:
    if not (file.filename or "").lower().endswith(".zip"):
        raise ApiError(400, "not_a_zip", "upload a .zip file")
    dest.parent.mkdir(parents=True, exist_ok=True)
    sha, size = hashlib.sha256(), 0
    with open(dest, "wb") as out:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > MAX_UPLOAD:
                out.close()
                dest.unlink(missing_ok=True)
                raise ApiError(413, "too_large", f"upload exceeds {MAX_UPLOAD // (1024 * 1024)} MB")
            sha.update(chunk)
            out.write(chunk)
    if not zipfile.is_zipfile(dest):
        dest.unlink(missing_ok=True)
        raise ApiError(400, "not_a_zip", "the file is not a valid zip archive")
    return {"filename": file.filename, "sha256": sha.hexdigest(), "bytes": size, "time": _now()}


def _combined_zip(case_dir: Path, meta: dict, version: int) -> Path:
    """Evidence version N = every upload so far, each under its own folder (originals stay untouched)."""
    uploads = meta["uploads"]
    if len(uploads) == 1:
        return case_dir / "uploads" / uploads[0]["stored"]
    out = case_dir / "uploads" / f"combined_v{version}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for u in uploads:
            prefix = Path(u["stored"]).stem
            with zipfile.ZipFile(case_dir / "uploads" / u["stored"]) as src:
                for info in src.infolist():
                    if not info.is_dir():
                        z.writestr(f"{prefix}/{info.filename}", src.read(info))
    return out


def _run_version(job_id: str, case_id: str, version: int, previous: Optional[str], reingest: bool = True) -> None:
    case_dir = _cases() / case_id
    meta = _read_json(case_dir / "case.json")
    try:
        ingest_dir = case_dir / "ingest" / f"v{version}"
        if reingest:
            _job(job_id, status="processing", progress=5, stage="ingest", message="Hashing and reading evidence")
            src = _combined_zip(case_dir, meta, version)
            ingest_zip(src, ingest_dir, timezone=meta.get("timezone") or "UTC", case_name=meta.get("title"), overwrite=True)
        _job(job_id, status="processing", progress=40, stage="analysis", message="Analysing evidence")
        llm = {"model": "claude-opus-5-5", "verifier_model": "claude-sonnet-5-5"} if meta.get("llm") else None

        def progress(stage, pct):
            _job(job_id, status="processing", progress=40 + int(pct * 0.58), stage=stage, message=stage.replace("_", " "))
        summary = analyze(ingest_dir, None, previous, case_dir / "overrides.jsonl", llm, progress)
        with _lock:
            meta = _read_json(case_dir / "case.json")
            meta.setdefault("versions", []).append({"version": version, "ingest_dir": str(ingest_dir.relative_to(case_dir)),
                                                    "analysis_dir": str(Path(summary["out_dir"]).resolve().relative_to(case_dir.resolve())),
                                                    "created": _now(), "changes": summary["changes"]})
            meta["latest"] = len(meta["versions"]) - 1
            _write_json(case_dir / "case.json", meta)
        _job(job_id, status="ready", progress=100, stage="done", message="Analysis ready", summary=summary)
    except Exception as exc:  # noqa: BLE001 - report the failure to the client
        _job(job_id, status="failed", progress=100, stage="failed", message=f"{type(exc).__name__}: {exc}",
             trace=traceback.format_exc(limit=4))


def _board(case_id: str) -> dict:
    case_dir = _case_dir(case_id)
    meta = _read_json(case_dir / "case.json")
    if meta.get("latest") is None:
        raise ApiError(409, "not_ready", "the case has no finished analysis yet")
    v = meta["versions"][meta["latest"]]
    board = _read_json(case_dir / v["analysis_dir"] / "board.json")
    board["id"] = case_id
    return board


# --------------------------------------------------------------------------- routes
@app.get("/health")
def health():
    return {"ok": True, "time": _now()}


@app.post("/upload")
async def upload(background: BackgroundTasks, file: UploadFile = File(...), case_name: Optional[str] = Form(None),
                 timezone_name: Optional[str] = Form(None, alias="timezone"), llm: bool = Form(False)):
    # the /docs form pre-fills optional fields with the placeholder "string"; treat that as empty
    case_name = None if (case_name or "").strip() in ("", "string") else case_name
    timezone_name = None if (timezone_name or "").strip() in ("", "string") else timezone_name.strip()
    if timezone_name:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError):
            raise ApiError(400, "bad_timezone", f"unknown time zone {timezone_name!r}; use an IANA name such as "
                                                "America/Los_Angeles, or leave it empty")
    case_id = (re.sub(r"[^a-z0-9]+", "-", (case_name or Path(file.filename or "case").stem).lower()).strip("-")[:40] or "case")
    case_id = f"{case_id}-{uuid.uuid4().hex[:6]}"
    case_dir = _cases() / case_id
    info = await _save_upload(file, case_dir / "uploads" / "upload_1.zip")
    meta = {"caseId": case_id, "title": case_name or Path(file.filename or "case").stem, "created": _now(),
            "timezone": timezone_name, "llm": bool(llm), "uploads": [{**info, "stored": "upload_1.zip"}], "versions": [],
            "latest": None}
    _write_json(case_dir / "case.json", meta)
    job_id = uuid.uuid4().hex
    _job(job_id, status="processing", progress=0, stage="queued", message="Queued", caseId=case_id)
    background.add_task(_run_version, job_id, case_id, 1, None)
    return {"jobId": job_id, "caseId": case_id}


@app.get("/status/{job_id}")
def status(job_id: str):
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise ApiError(400, "bad_job_id", "invalid job id")
    p = _jobs() / f"{job_id}.json"
    if not p.exists():
        raise ApiError(404, "job_not_found", f"no job {job_id}")
    job = _read_json(p)
    job.pop("trace", None)
    return job


@app.get("/cases")
def list_cases():
    out = []
    for d in sorted(_cases().iterdir()):
        if (d / "case.json").exists():
            m = _read_json(d / "case.json")
            out.append({"caseId": m["caseId"], "title": m["title"], "created": m["created"], "versions": len(m["versions"]),
                        "ready": m.get("latest") is not None})
    return out


@app.get("/case")
def latest_case():
    ready = [c for c in list_cases() if c["ready"]]
    if not ready:
        raise ApiError(404, "no_cases", "no analysed case yet; POST /upload first")
    return _board(sorted(ready, key=lambda c: c["created"])[-1]["caseId"])


@app.get("/cases/{case_id}")
def get_case(case_id: str):
    return _board(case_id)


@app.get("/cases/{case_id}/source")
def get_source(case_id: str, id: str):
    board = _board(case_id)
    src = next((s for s in board["sources"] if s["id"] == id), None)
    if not src:
        raise ApiError(404, "source_not_found", f"no cited source {id}")
    return src


@app.get("/cases/{case_id}/evidence/{evidence_id}")
def get_evidence(case_id: str, evidence_id: str):
    case_dir = _case_dir(case_id)
    meta = _read_json(case_dir / "case.json")
    if meta.get("latest") is None:
        raise ApiError(409, "not_ready", "the case has no finished analysis yet")
    ingest_dir = case_dir / meta["versions"][meta["latest"]]["ingest_dir"]
    import sqlite3
    con = sqlite3.connect(f"file:{(ingest_dir / 'case.db').as_posix()}?mode=ro", uri=True)
    row = con.execute("SELECT stored_path, original_path FROM evidence_files WHERE external_id=? OR 'FILE-' || file_id = ?",
                      (evidence_id, evidence_id)).fetchone()
    con.close()
    if not row:
        raise ApiError(404, "evidence_not_found", f"no evidence {evidence_id}")
    return FileResponse(ingest_dir / row[0], filename=Path(row[1].split("::")[-1]).name)


@app.get("/cases/{case_id}/overrides")
def get_overrides(case_id: str):
    return history.load_overrides(_case_dir(case_id) / "overrides.jsonl")


class OverrideIn(BaseModel):
    target_key: str
    action: str
    value: Optional[str] = None
    note: str = ""
    investigator: str = "investigator"


@app.post("/cases/{case_id}/overrides")
def add_override(case_id: str, body: OverrideIn, background: BackgroundTasks):
    case_dir = _case_dir(case_id)
    if body.action not in history.ACTIONS:
        raise ApiError(400, "bad_action", f"action must be one of {sorted(history.ACTIONS)}")
    entry = history.append_override(case_dir / "overrides.jsonl", body.target_key, body.action, body.value, body.note,
                                    body.investigator)
    meta = _read_json(case_dir / "case.json")
    job_id = None
    if meta.get("latest") is not None:
        v = meta["versions"][meta["latest"]]
        job_id = uuid.uuid4().hex
        _job(job_id, status="processing", progress=0, stage="queued", message="Re-applying analysis", caseId=case_id)
        background.add_task(_reanalyse, job_id, case_id, v)
    return {"override": entry, "jobId": job_id}


def _reanalyse(job_id: str, case_id: str, v: dict) -> None:
    case_dir = _cases() / case_id
    ingest_dir = case_dir / v["ingest_dir"]
    try:
        summary = analyze(ingest_dir, None, case_dir / v["analysis_dir"], case_dir / "overrides.jsonl", None)
        with _lock:
            meta = _read_json(case_dir / "case.json")
            meta["versions"].append({**v, "analysis_dir": str(Path(summary["out_dir"]).resolve().relative_to(case_dir.resolve())),
                                     "created": _now(), "changes": summary["changes"], "reason": "override"})
            meta["latest"] = len(meta["versions"]) - 1
            _write_json(case_dir / "case.json", meta)
        _job(job_id, status="ready", progress=100, stage="done", message="Analysis ready", summary=summary)
    except Exception as exc:  # noqa: BLE001
        _job(job_id, status="failed", progress=100, stage="failed", message=f"{type(exc).__name__}: {exc}")


@app.post("/cases/{case_id}/evidence")
async def add_evidence(case_id: str, background: BackgroundTasks, file: UploadFile = File(...)):
    case_dir = _case_dir(case_id)
    meta = _read_json(case_dir / "case.json")
    n = len(meta["uploads"]) + 1
    info = await _save_upload(file, case_dir / "uploads" / f"upload_{n}.zip")
    previous = None
    if meta.get("latest") is not None:
        previous = str(case_dir / meta["versions"][meta["latest"]]["analysis_dir"])
    with _lock:
        meta = _read_json(case_dir / "case.json")
        meta["uploads"].append({**info, "stored": f"upload_{n}.zip"})
        _write_json(case_dir / "case.json", meta)
    version = len({v["ingest_dir"] for v in meta["versions"]}) + 1
    job_id = uuid.uuid4().hex
    _job(job_id, status="processing", progress=0, stage="queued", message="Queued", caseId=case_id)
    background.add_task(_run_version, job_id, case_id, version, previous)
    return {"jobId": job_id, "caseId": case_id, "version": version}


@app.get("/cases/{case_id}/{section}")
def get_section(case_id: str, section: str):
    if section not in SECTIONS:
        raise ApiError(404, "unknown_section", f"unknown section {section}")
    board = _board(case_id)
    if section == "graph":
        return {"nodes": board["nodes"], "edges": board["edges"]}
    return board.get(section, [])
