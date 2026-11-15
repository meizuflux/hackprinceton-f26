"""Command line:

    python -m mapletrace_ingest ingest case.zip --out runs/case1 --tz America/New_York
    python -m mapletrace_ingest verify runs/case1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .pipeline import IngestOptions, Ingestor
from .verify import verify_run


def cmd_ingest(a) -> int:
    opts = IngestOptions(timezone=a.tz, dayfirst=a.dayfirst, default_country_code=a.country_code,
                         case_name=a.case_name, overwrite=a.overwrite)
    report = Ingestor(Path(a.out), opts).run(Path(a.zip))
    t = report["totals"]
    print(f"Ingested {t['files']} files -> {t['records']} records ({t['timestamped_records']} timestamped), "
          f"{t['canonical_entities']} entities")
    for typ, v in sorted(report["by_evidence_type"].items(), key=lambda kv: -kv[1]["records"]):
        print(f"  {typ:<14} {v['files']:>3} files  {v['records']:>6} records")
    problems = report["coverage_gaps"]["files_needing_attention"]
    if problems:
        print(f"{len(problems)} file(s) need attention; see ingest_summary.md")
    print(f"Database: {Path(a.out) / 'case.db'}")
    return 0


def cmd_verify(a) -> int:
    result = verify_run(Path(a.run_dir))
    for c in result["checks"]:
        print(("OK   " if c["ok"] else "FAIL ") + c["message"])
    return 0 if result["ok"] else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="mapletrace_ingest", description="Ingest a forensic case archive into SQLite.")
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("ingest", help="ingest a .zip of case files")
    i.add_argument("zip")
    i.add_argument("--out", required=True, help="run directory to create")
    i.add_argument("--tz", default="UTC", help="IANA time zone for timestamps that have none (default UTC, "
                   "or the manifest's timezone)")
    i.add_argument("--dayfirst", action="store_true", help="read 03/04/2026 as 3 April (default: March 4)")
    i.add_argument("--country-code", default="1", help="country calling code for local phone numbers")
    i.add_argument("--case-name")
    i.add_argument("--overwrite", action="store_true", help="replace a previous run in --out")
    i.set_defaults(func=cmd_ingest)
    v = sub.add_parser("verify", help="re-check evidence hashes, database hash and audit chain")
    v.add_argument("run_dir")
    v.set_defaults(func=cmd_verify)
    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
