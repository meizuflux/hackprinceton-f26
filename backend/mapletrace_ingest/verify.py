"""Re-verify an ingestion run: database hash, hash-chained audit log, and every evidence file hash."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .db import GENESIS_HASH, verify_audit_chain
from .intake import hash_file


def verify_run(run: Path) -> dict:
    """Re-check the database hash, the audit chain and every evidence file hash of an ingestion run.
    Opens case.db read-only. Returns {ok, head, checks: [{ok, message}]}."""
    run = Path(run)
    manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    checks = []
    db_sha, _ = hash_file(run / "case.db")
    checks.append({"ok": db_sha == manifest["database_sha256"],
                   "message": "database unchanged since ingestion" if db_sha == manifest["database_sha256"]
                   else "database changed since ingestion"})
    conn = sqlite3.connect(f"file:{(run / 'case.db').as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        chain_ok, msg = verify_audit_chain(conn)
        checks.append({"ok": chain_ok, "message": "audit log: " + msg})
        bad = 0
        for f in conn.execute("SELECT file_id, original_path, stored_path, sha256 FROM evidence_files"):
            p = run / f["stored_path"]
            if not p.exists() or hash_file(p)[0] != f["sha256"]:
                checks.append({"ok": False, "message": f"evidence file altered or missing: {f['original_path']}"})
                bad += 1
        n = conn.execute("SELECT COUNT(*) FROM evidence_files").fetchone()[0]
        checks.append({"ok": not bad, "message": f"evidence hashes: {n - bad}/{n} match"})
        row = conn.execute("SELECT entry_hash FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    return {"ok": all(c["ok"] for c in checks), "head": row[0] if row else GENESIS_HASH, "checks": checks}
