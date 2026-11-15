"""Run trace: presentation telemetry written as `ingest/vN/trace.jsonl` while a case is processed (backend/TRACE.md).

One JSON event per line, appended and flushed as things happen, so the API can serve it while the job runs. The trace
is telemetry only. It never feeds the analysis, does not replace the hash-chained audit log and never touches evidence.

Replay clock: `tMs` is the run's wall clock plus a skew. A model response served from the committed LLM cache returns
almost at once, so the cache layer calls `replayed_call(duration_ms)`, which moves the clock to
`start + recorded_or_estimated_duration`. The skew is raised with `max(skew, start + duration - wall)`, so durations
are placed on the clock rather than summed blindly. Claim extraction and the investigator's model calls run one after
another in the code (and in the recording), so replayed calls are sequential on the clock too. The cache does not
record start times, so overlap between concurrent calls of the original run cannot be reconstructed; a replay
therefore never reports a shorter run than the sum of its sequential calls.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

PHASES = ("ingest", "rules", "ml", "llm", "agent", "output")


def short(value, limit: int = 120):
    """Copy of an arguments object with long strings truncated, for `agent_tool.args`."""
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + "…"
    if isinstance(value, dict):
        return {str(k): short(v, limit) for k, v in list(value.items())[:12]}
    if isinstance(value, (list, tuple)):
        return [short(v, limit) for v in list(value)[:12]]
    return value


class TraceWriter:
    def __init__(self, path: str | Path, context: dict | None = None):
        self.path = Path(path)
        self.context = context or {}      # run_started fields supplied by the caller (mode, llm, model, archive)
        self._lock = threading.RLock()
        self._t0 = time.monotonic()
        self._skew = 0.0                  # milliseconds added by replayed model calls
        self._seq = 0
        if self.path.exists():            # a later run on the same ingest version (for example re-analysis) continues it
            self._seq = sum(1 for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip())
        self._phase: tuple[str, str, float] | None = None   # (phase, label, started tMs)
        self.totals = {"llmCalls": 0, "toolCalls": 0, "costUsd": 0.0}
        self.replayed = self.estimated = 0
        self.finished = False

    # ------------------------------------------------------------------ clock
    def now_ms(self) -> int:
        with self._lock:
            return int((time.monotonic() - self._t0) * 1000 + self._skew)

    def replayed_call(self, duration_ms: float) -> tuple[int, int]:
        """Account for a replayed model call that starts now and takes `duration_ms`. Returns (startMs, endMs)."""
        with self._lock:
            wall = (time.monotonic() - self._t0) * 1000
            start = wall + self._skew
            self._skew = max(self._skew, start + duration_ms - wall)
            return int(start), int(start + duration_ms)

    # ------------------------------------------------------------------ events
    def emit(self, phase: str, type_: str, t_ms: int | None = None, **fields) -> dict:
        with self._lock:
            self._seq += 1
            event = {"seq": self._seq, "tMs": self.now_ms() if t_ms is None else t_ms, "phase": phase, "type": type_,
                     **fields}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, default=str, ensure_ascii=False) + "\n")
                f.flush()
            return event

    def phase(self, phase: str, label: str) -> None:
        """Close the open phase (phase_finished) and open a new one (phase_started)."""
        with self._lock:
            self._close_phase()
            self._phase = (phase, label, self.now_ms())
            self.emit(phase, "phase_started", label=label)

    def _close_phase(self) -> None:
        if self._phase:
            phase, label, started = self._phase
            self.emit(phase, "phase_finished", label=label, durationMs=self.now_ms() - started)
            self._phase = None

    @property
    def current_phase(self) -> str:
        return self._phase[0] if self._phase else "rules"

    def stage_finished(self, stage: str, label: str, counts: dict, started_ms: int) -> None:
        self.emit(self.current_phase, "stage_finished", stage=stage, label=label, counts=counts,
                  durationMs=self.now_ms() - started_ms)

    def llm_call(self, purpose: str, model: str, stats: dict, replayed: bool, t_ms: int | None = None,
                 start_ms: int | None = None) -> None:
        with self._lock:
            self.totals["llmCalls"] += 1
            self.totals["costUsd"] += stats["costUsd"]
            if replayed:
                self.replayed += 1
                self.estimated += stats["durationSource"] == "estimated"
            self.emit("agent" if purpose != "claim_extraction" else "llm", "llm_call", t_ms, purpose=purpose, model=model,
                      **stats, replayed=replayed, **({"startMs": start_ms} if start_ms is not None else {}))

    def agent_tool(self, tool: str, args: dict, result_chars: int) -> None:
        with self._lock:
            self.totals["toolCalls"] += 1
            self.emit("agent", "agent_tool", tool=tool, args=short(args), resultChars=result_chars)

    def finish(self, status: str = "ready", totals: dict | None = None) -> None:
        with self._lock:
            if self.finished:
                return
            self.finished = True
            self._close_phase()
            t = {**(totals or {}), **self.totals}
            t["costUsd"] = round(t["costUsd"], 4)
            self.emit("output", "run_finished", status=status, durationMs=self.now_ms(), totals=t)
