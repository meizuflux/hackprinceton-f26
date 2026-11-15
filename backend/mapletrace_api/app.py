"""Mapletrace HTTP API (FastAPI).

Run:  uvicorn mapletrace_api.app:app --reload --port 8000      (from backend/)

    POST /upload                         ZIP -> new case; returns {jobId, caseId}
    GET  /status/{jobId}                 {status: processing|ready|failed, progress, message, stage, caseId}
    GET  /cases                          list cases
    GET  /case                           latest ready case as CaseData (matches the frontend's getCase())
    GET  /cases/{caseId}                 CaseData for one case (board.json)
    GET  /cases/{caseId}/{section}       graph | gaps | insights | suggestions | contradictions | explanations |
                                         timeline | audit | changes | sources | signals
    GET  /cases/{caseId}/source?id=...   one cited record in full (source inspector)
    GET  /cases/{caseId}/evidence/{evidenceId}   original evidence file (read-only copy)
    GET  /cases/{caseId}/files           evidence inventory from the latest ingestion (hash, format, parse status, ...)
    GET  /cases/{caseId}/records?evidenceId=&limit=&offset=   normalized ingestion records, read-only, with citations
    GET  /cases/{caseId}/audit-chain     ingestion + analysis audit entries with hashes, re-verified
    POST /cases/{caseId}/evidence        add a ZIP of new evidence -> new version, compared with the previous one
    POST /demo                           install the committed Kestrel demo snapshot (instant, no model calls) -> {caseId}
    GET  /chat/status?case_id=...        case chat availability and suggested questions
    POST /cases/{caseId}/chat            {message, thread_id?} -> cited answer (see mapletrace_api/chat.py)
    GET  /cases/{caseId}/overrides       investigator corrections
    POST /cases/{caseId}/overrides       record a correction -> re-analysis job

Case data lives under $MAPLETRACE_DATA (default backend/data/cases/<caseId>/). Evidence is never modified.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import tarfile
import tempfile
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

from mapletrace_api.chat import ChatError, ChatService
from mapletrace_ingest.verify import verify_run
from mapletrace_ingest.db import GENESIS_HASH, verify_audit_chain
from mapletrace_ingest.pipeline import ingest_zip
from mapletrace_reason import history
from mapletrace_reason.llm_cache import cache_path
from mapletrace_reason.pipeline import analyze
from mapletrace_reason.store import PROTECTED_KEYS, citation_id, unique_labels

DATA = Path(os.environ.get("MAPLETRACE_DATA", Path(__file__).resolve().parents[1] / "data"))
MAX_UPLOAD = int(os.environ.get("MAPLETRACE_MAX_UPLOAD_MB", "100")) * 1024 * 1024
SECTIONS = {"graph", "gaps", "insights", "suggestions", "contradictions", "explanations", "timeline", "audit", "changes",
            "sources", "nodes", "edges", "uncertainTimes", "missingPeriods", "sourceGroups", "signals"}
_lock = threading.Lock()
LLM_MODEL = os.environ.get("MAPLETRACE_LLM_MODEL", "claude-sonnet-5-5")
REPO = Path(__file__).resolve().parents[2]
DEMO_SNAPSHOT = Path(__file__).resolve().parents[1] / "demo" / "kestrel.tar.gz"
DEMO_ARCHIVE = REPO / "cases" / "kestrel" / "kestrel_case_upload.zip"
DEMO_CASE_ID = "kestrel-demo"

app = FastAPI(title="Mapletrace API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_methods=["*"], allow_headers=["*"],
                   allow_origins=os.environ.get("MAPLETRACE_CORS", "http://localhost:5173,http://127.0.0.1:5173").split(","))


chat_service = ChatService()


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


def _llm_config(meta: dict) -> Optional[dict]:
    """LLM settings for a case. An upload whose archive has recorded responses (`backend/llm_cache/`) replays them for
    free, without calling the API; an explicit LLM request records responses it does not have yet (billed)."""
    sha = meta["uploads"][0]["sha256"] if len(meta.get("uploads", [])) == 1 else None
    cached = bool(sha) and cache_path(sha).exists()
    if meta.get("llm"):
        mode = "record"
    elif cached:
        mode = "replay"
    else:
        return None
    return {"model": LLM_MODEL, "verifier_model": LLM_MODEL, "cache_mode": mode}


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
        llm = _llm_config(meta)

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


def _latest_dirs(case_id: str) -> tuple[Path, Path]:
    """(ingest run dir, analysis dir) of the latest finished version."""
    case_dir = _case_dir(case_id)
    meta = _read_json(case_dir / "case.json")
    if meta.get("latest") is None:
        raise ApiError(409, "not_ready", "the case has no finished analysis yet")
    v = meta["versions"][meta["latest"]]
    return case_dir / v["ingest_dir"], case_dir / v["analysis_dir"]


def _ro(db: Path) -> sqlite3.Connection:
    """Read-only connection: the API never writes to case.db or analysis.db."""
    if not db.exists():
        raise ApiError(404, "db_not_found", f"{db.name} is missing for this case")
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _evidence_id(row) -> str:
    return row["external_id"] or f"FILE-{row['file_id']}"


def _scalar(v) -> bool:
    return v is None or isinstance(v, (str, int, float, bool))


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
    try:
        info = await _save_upload(file, case_dir / "uploads" / "upload_1.zip")
    except ApiError:
        shutil.rmtree(case_dir, ignore_errors=True)  # a rejected upload leaves no empty case behind
        raise
    meta = {"caseId": case_id, "title": case_name or Path(file.filename or "case").stem, "created": _now(),
            "timezone": timezone_name, "llm": bool(llm), "uploads": [{**info, "stored": "upload_1.zip"}], "versions": [],
            "latest": None}
    _write_json(case_dir / "case.json", meta)
    job_id = uuid.uuid4().hex
    _job(job_id, status="processing", progress=0, stage="queued", message="Queued", caseId=case_id)
    background.add_task(_run_version, job_id, case_id, 1, None)
    return {"jobId": job_id, "caseId": case_id}


@app.post("/demo")
def open_demo():
    """Install the committed Kestrel snapshot (ingestion + analysis with recorded LLM results) once, then reuse it."""
    case_dir = _cases() / DEMO_CASE_ID
    if (case_dir / "case.json").exists():
        return {"caseId": DEMO_CASE_ID}
    if not DEMO_SNAPSHOT.exists():
        raise ApiError(404, "no_demo_snapshot", "no demo snapshot; build it with make backend-demo-snapshot")
    with _lock:
        tmp = Path(tempfile.mkdtemp(dir=_cases(), prefix=".demo-"))
        try:
            with tarfile.open(DEMO_SNAPSHOT) as t:
                t.extractall(tmp, filter="data")
            meta = _read_json(tmp / "case.json")
            # the uploaded archive is not in the snapshot; it is the repository's Kestrel ZIP (checked by hash)
            upload = meta["uploads"][0]
            if DEMO_ARCHIVE.exists() and hashlib.sha256(DEMO_ARCHIVE.read_bytes()).hexdigest() == upload["sha256"]:
                (tmp / "uploads").mkdir(exist_ok=True)
                shutil.copyfile(DEMO_ARCHIVE, tmp / "uploads" / upload["stored"])
            if not (case_dir / "case.json").exists():
                shutil.rmtree(case_dir, ignore_errors=True)
                tmp.rename(case_dir)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return {"caseId": DEMO_CASE_ID}


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


@app.get("/cases/{case_id}/files")
def get_files(case_id: str):
    ingest_dir, _ = _latest_dirs(case_id)
    con = _ro(ingest_dir / "case.db")
    try:
        counts = dict(con.execute("SELECT file_id, COUNT(*) FROM records GROUP BY file_id").fetchall())
        out = []
        for f in con.execute("SELECT * FROM evidence_files ORDER BY file_id"):
            m = json.loads(f["manifest_json"]) if f["manifest_json"] else {}
            listed = (m.get("sha256") or "").lower()
            ext = (f["extension"] or "").lstrip(".")
            out.append({"evidenceId": _evidence_id(f), "fileId": f["file_id"], "path": f["original_path"],
                        "filename": Path(f["original_path"].split("::")[-1]).name, "sha256": f["sha256"],
                        "bytes": f["size_bytes"], "format": m.get("format") or ext or f["sniffed_format"] or "",
                        "sniffedFormat": f["sniffed_format"], "evidenceType": f["evidence_type"],
                        "parseStatus": f["parse_status"], "recordCount": counts.get(f["file_id"], 0),
                        "manifestMatch": (listed == f["sha256"]) if listed else None, "origin": f["origin"],
                        "title": m.get("title")})
    finally:
        con.close()
    return out


_RECORD_FIELDS = ("ts_utc", "ts_start_utc", "ts_end_utc", "ts_raw", "ts_precision", "actor", "target", "lat", "lon",
                  "content", "reliability", "duplicate_of")


@app.get("/cases/{case_id}/records")
def get_records(case_id: str, evidenceId: Optional[str] = None, limit: int = 100, offset: int = 0):  # noqa: N803
    if limit < 1 or limit > 500 or offset < 0:
        raise ApiError(400, "bad_paging", "limit must be 1-500 and offset >= 0")
    ingest_dir, analysis_dir = _latest_dirs(case_id)
    board = _read_json(analysis_dir / "board.json")
    source_ids = {s["id"] for s in board.get("sources", [])}
    con = _ro(ingest_dir / "case.db")
    try:
        where, args = "", []
        if evidenceId:
            f = con.execute("SELECT file_id FROM evidence_files WHERE external_id=? OR 'FILE-' || file_id = ?",
                            (evidenceId, evidenceId)).fetchone()
            if not f:
                raise ApiError(404, "evidence_not_found", f"no evidence {evidenceId}")
            where, args = " WHERE r.file_id = ?", [f["file_id"]]
        total = con.execute(f"SELECT COUNT(*) FROM records r{where}", args).fetchone()[0]
        rows = con.execute(f"SELECT r.*, f.external_id FROM records r JOIN evidence_files f ON f.file_id = r.file_id"
                           f"{where} ORDER BY r.record_id LIMIT ? OFFSET ?", args + [limit, offset]).fetchall()
        def attrs_of(raw):
            return {k: v for k, v in json.loads(raw or "{}").items() if not PROTECTED_KEYS.search(k)}
        file_ids = sorted({r["file_id"] for r in rows})
        labels = unique_labels(
            (x["record_id"], x["file_id"], json.loads(x["locator_json"] or "{}"), attrs_of(x["attributes_json"]))
            for x in con.execute(f"SELECT record_id, file_id, locator_json, attributes_json FROM records "
                                 f"WHERE file_id IN ({','.join('?' * len(file_ids))})", file_ids)) if file_ids else {}
        items = []
        for r in rows:
            attrs = attrs_of(r["attributes_json"])
            fields = {k: r[k] for k in _RECORD_FIELDS if r[k] is not None}
            flags = json.loads(r["ts_flags"] or "[]")
            if flags:
                fields["ts_flags"] = ", ".join(flags)
            fields.update({k: v for k, v in attrs.items() if _scalar(v) and v is not None and k not in fields})
            ev = r["external_id"] or f"FILE-{r['file_id']}"
            label = labels[r["record_id"]]
            cit = {"evidenceId": ev, "locator": label}
            if citation_id(ev, label) in source_ids:
                cit["sourceId"] = citation_id(ev, label)
            items.append({"id": r["record_id"], "recordType": r["record_type"], "fields": fields, "citations": [cit]})
    finally:
        con.close()
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@app.get("/cases/{case_id}/audit-chain")
def get_audit_chain(case_id: str):
    ingest_dir, analysis_dir = _latest_dirs(case_id)
    checks = []
    try:
        ingest = verify_run(ingest_dir)
        checks += [{"source": "ingest", **c} for c in ingest["checks"]]
        ingest_head = ingest["head"]
    except (OSError, KeyError, ValueError) as exc:
        checks.append({"source": "ingest", "ok": False, "message": f"ingestion run could not be verified: {exc}"})
        ingest_head = GENESIS_HASH

    def rows(db: Path, source: str) -> list[dict]:
        con = _ro(db)
        try:
            return [{"seq": r["seq"], "time": r["ts_utc"], "stage": r["stage"], "action": r["action"],
                     "fileId": r["file_id"], "detail": json.loads(r["detail_json"] or "{}"), "hash": r["entry_hash"],
                     "prevHash": r["prev_hash"], "source": source}
                    for r in con.execute("SELECT * FROM audit_log ORDER BY seq")]
        finally:
            con.close()

    entries = rows(ingest_dir / "case.db", "ingest")
    if (analysis_dir / "analysis.db").exists():
        con = _ro(analysis_dir / "analysis.db")
        try:
            ok, msg = verify_audit_chain(con, start=ingest_head)
        finally:
            con.close()
        checks.append({"source": "analysis", "ok": ok, "message": "analysis audit log: " + msg})
        analysis = rows(analysis_dir / "analysis.db", "analysis")
        written = next((e for e in reversed(analysis) if e["action"] == "outputs_written"), None)
        if written:
            for name, sha in written["detail"].items():
                p = analysis_dir / name
                same = p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() == sha
                checks.append({"source": "analysis", "ok": same,
                               "message": f"{name} {'matches' if same else 'does not match'} the hash in the audit log"})
        entries += analysis
    else:
        checks.append({"source": "analysis", "ok": False, "message": "analysis.db is missing"})
    return {"verified": all(c["ok"] for c in checks), "head": entries[-1]["hash"] if entries else GENESIS_HASH,
            "checks": checks, "entries": entries}


class ChatIn(BaseModel):
    message: str
    thread_id: Optional[str] = None


@app.get("/chat/status")
def chat_status(case_id: str):
    try:
        ingest_dir, analysis_dir = _latest_dirs(case_id)
    except ApiError as exc:
        return {"available": False, "case_id": case_id, "reason": exc.message}
    return chat_service.status(case_id, chat_service.case_chat(case_id, ingest_dir, analysis_dir))


@app.post("/cases/{case_id}/chat")
def chat(case_id: str, body: ChatIn):
    ingest_dir, analysis_dir = _latest_dirs(case_id)
    try:
        return chat_service.ask(case_id, chat_service.case_chat(case_id, ingest_dir, analysis_dir), body.message,
                                body.thread_id)
    except ChatError as exc:
        raise ApiError(exc.status, exc.code, exc.message) from None


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
        meta = _read_json(case_dir / "case.json")
        summary = analyze(ingest_dir, None, case_dir / v["analysis_dir"], case_dir / "overrides.jsonl", _llm_config(meta))
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
