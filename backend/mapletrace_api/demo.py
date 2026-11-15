"""Record the Kestrel LLM cache and build the demo snapshot through the same code path as an upload.

    python -m mapletrace_api.demo record      # one billed run: records backend/llm_cache/<archive sha256>.jsonl
    python -m mapletrace_api.demo record-vision  # billed: records only backend/llm_cache/vision-<sha>.jsonl
    python -m mapletrace_api.demo snapshot    # replays the cache (no API calls) -> backend/demo/kestrel.tar.gz

Both run an upload of cases/kestrel/kestrel_case_upload.zip exactly as POST /upload does, so the recorded requests
match what a later upload of the same archive sends. The snapshot holds the finished case directory except the
uploaded ZIP, which POST /demo restores from the repository after checking its hash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path


def _run(llm: bool, vision_record: bool = False) -> tuple[Path, dict]:
    data = Path(tempfile.mkdtemp(prefix="mapletrace-demo-"))
    os.environ["MAPLETRACE_DATA"] = str(data)
    from mapletrace_api import app as api  # imported after MAPLETRACE_DATA is set

    raw = api.DEMO_ARCHIVE.read_bytes()
    case_dir = api._cases() / api.DEMO_CASE_ID
    (case_dir / "uploads").mkdir(parents=True)
    shutil.copyfile(api.DEMO_ARCHIVE, case_dir / "uploads" / "upload_1.zip")
    meta = {"caseId": api.DEMO_CASE_ID, "title": "Kestrel", "created": api._now(), "timezone": None, "llm": llm,
            "uploads": [{"filename": api.DEMO_ARCHIVE.name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                         "time": api._now(), "stored": "upload_1.zip"}], "versions": [], "latest": None}
    api._write_json(case_dir / "case.json", meta)
    api._run_version("0" * 32, api.DEMO_CASE_ID, 1, None)
    job = json.loads((api._jobs() / f"{'0' * 32}.json").read_text(encoding="utf-8"))
    if job["status"] != "ready":
        raise SystemExit(f"analysis failed: {job['message']}")
    return case_dir, job["summary"]["llm"]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="mapletrace_api.demo")
    p.add_argument("command", choices=["record", "record-vision", "snapshot"])
    args = p.parse_args(argv)
    case_dir, llm = _run(llm=args.command == "record", vision_record=args.command == "record-vision")
    print(json.dumps(llm, indent=1))
    cache = (llm or {}).get("cache") or {}
    if args.command == "record-vision":
        v = (llm or {}).get("vision") or {}
        if not llm or cache.get("misses") or v.get("skipped") or v.get("error"):
            raise SystemExit(f"vision recording incomplete (the analysis cache must exist and replay fully): {v}")
        print(f"Recorded {v.get('recorded', 0)} image descriptions into backend/llm_cache/{v.get('cache')}")
    elif args.command == "record":
        print(f"Recorded {cache.get('recorded', 0)} responses into backend/llm_cache/{cache.get('file')}")
    else:
        if not llm or not llm.get("enabled") or cache.get("misses"):
            raise SystemExit("the LLM cache is missing or incomplete for this archive; run `record` first")
        from mapletrace_api import app as api
        api.DEMO_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(api.DEMO_SNAPSHOT, "w:gz") as t:
            t.add(case_dir, arcname=".", filter=lambda info: None if info.name.startswith("./uploads") else info)
        print(f"Wrote {api.DEMO_SNAPSHOT} ({api.DEMO_SNAPSHOT.stat().st_size // 1024} KB)")
    shutil.rmtree(case_dir.parents[1], ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
