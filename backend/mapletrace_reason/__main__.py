"""Command line:

    python -m mapletrace_reason analyze runs/kestrel                       # deterministic (no LLM)
    python -m mapletrace_reason analyze runs/kestrel --llm                 # + claim extraction and deep-agent investigator
    python -m mapletrace_reason analyze runs/kestrel --llm --llm-cache replay   # replay recorded responses, no API calls
    python -m mapletrace_reason analyze runs/kestrel_v2 --previous runs/kestrel/analysis
    python -m mapletrace_reason override runs/kestrel <stable_key> dismiss --note "badge reader under repair"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .history import ACTIONS, append_override
from .pipeline import analyze


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="mapletrace_reason", description="Reason over an ingested case.")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="run the reasoning pipeline on an ingestion run directory")
    a.add_argument("run_dir")
    a.add_argument("--out", help="analysis root (default: <run_dir>/analysis)")
    a.add_argument("--previous", help="previous analysis (dir or analysis.json) to compare against")
    a.add_argument("--overrides", help="overrides.jsonl (default: <run_dir>/../overrides.jsonl if present)")
    a.add_argument("--llm", action="store_true", help="enable LLM claim extraction and the deep-agent investigator "
                   "(needs the investigator model's API key, ANTHROPIC_API_KEY by default)")
    a.add_argument("--model", help="investigator model, provider:model (default: MAPLETRACE_INVESTIGATOR_MODEL or "
                   "claude-sonnet-5-5; see mapletrace_reason/models.py)")
    a.add_argument("--verifier-model", help="verifier model (default: the investigator model)")
    a.add_argument("--llm-cache", choices=["record", "replay", "off"], default="record",
                   help="record: reuse cached responses and record new ones (default); replay: cached responses only, "
                        "never calls the API; off: no cache")
    a.add_argument("--max-agent-steps", type=int, default=40)
    o = sub.add_parser("override", help="record an investigator correction (never deletes the machine result)")
    o.add_argument("run_dir")
    o.add_argument("target_key")
    o.add_argument("action", choices=sorted(ACTIONS))
    o.add_argument("--value")
    o.add_argument("--note", default="")
    o.add_argument("--investigator", default="investigator")
    args = p.parse_args(argv)
    if args.cmd == "override":
        e = append_override(Path(args.run_dir) / "overrides.jsonl", args.target_key, args.action, args.value, args.note,
                            args.investigator)
        print(json.dumps(e, indent=1))
        return 0
    overrides = args.overrides or (Path(args.run_dir) / "overrides.jsonl")
    llm = None
    if args.llm:
        from .models import parse, resolve
        model = parse(args.model).label if args.model else resolve("investigator").label
        llm = {"model": model, "verifier_model": parse(args.verifier_model).label if args.verifier_model else model,
               "vision_model": resolve("vision", model).label, "max_steps": args.max_agent_steps,
               "cache_mode": args.llm_cache}
    s = analyze(args.run_dir, args.out, args.previous, overrides, llm,
                progress=lambda stage, pct: print(f"  [{pct:3d}%] {stage}", flush=True))
    print(json.dumps(s, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
