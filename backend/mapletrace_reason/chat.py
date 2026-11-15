"""Case chat: answer an investigator's question about one analysed case with cited records.

The model gets the investigator's read-only tools (`llm.read_tools`) plus two chat-only readers over the finished
analysis, and must finish with `submit_answer`. The answer is assembled here, not taken from free model text:
- each observation must cite record IDs that a tool returned in this conversation, otherwise it is dropped;
- the inference and the unknowns are kept apart from the observations;
- `evidence_status` is downgraded when citations were dropped, and is `insufficient` when none survive.

Nothing here writes to the case. Prompts hold nothing that varies between runs or installs (no case name, time or
random ID), so recorded responses (`llm_cache.py`) replay for the same archive.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from .analytics import Context, case_tz
from .llm import read_tools
from .model import Item, Results, plural
from .store import Case

MAX_STEPS = 10           # model calls per answer
TOOL_OUTPUT_CHARS = 12000
HISTORY_TURNS = 4        # previous question/answer pairs sent with a follow-up
Status = Literal["supported", "partial", "insufficient"]

SYSTEM_PROMPT = """You answer an investigator's questions about one case. You work only from the tools provided; never
invent facts, names, times or records. Case time zone: {tz}.

Rules:
- Cite or drop: every observation must cite record IDs that the tools returned. Read a record with get_record before
  you rely on it. An observation you cannot cite does not belong in the answer.
- list_explanations and list_open_questions are summaries without record IDs. To cite an explanation, gap or
  contradiction, open it with get_item (H-.., G-.., X-..) and use the record IDs it returns.
- Keep observations (what a record says) separate from inference (what may follow) and unknowns (what the records
  do not show).
- A gap in evidence is uncertainty, not proof. Missing records never count against a person.
- Word findings neutrally ("conflicts with records", not "lied"). Present several explanations when they fit.
- Never use nationality, ethnicity, religion or similar attributes.
- If the records do not answer the question, say so and set evidence_status to "insufficient".
- Keep it short: at most five observations. Use as few tool calls as you need.

Finish every answer by calling submit_answer exactly once."""


@dataclass
class Answer:
    content: str
    evidence_status: Status
    citations: list[dict]
    observations: list[dict] = field(default_factory=list)
    inference: str = ""
    unknowns: list[str] = field(default_factory=list)
    record_ids: list[int] = field(default_factory=list)
    model_calls: int = 0
    summary: str = ""
    steps: list[dict] = field(default_factory=list)

    def message(self) -> dict:
        return {"role": "assistant", "content": self.content, "evidence_status": self.evidence_status,
                "citations": self.citations, "summary": self.summary, "observations": self.observations,
                "inference": self.inference, "unknowns": self.unknowns}


# Steps (backend/TRACE.md "Chat steps"). Usage comes from the response's usage_metadata; cost is an estimate from
# list prices; duration is the measured wall time of a live call, else recorded latency_ms, else an estimate.
PRICE_PER_MTOK = {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_write": 3.75}
LIVE_MIN_MS = 150  # a cached response returns far faster than any real model call


def _short_args(args, limit: int = 120):
    if isinstance(args, str):
        return args if len(args) <= limit else args[:limit - 1] + "\u2026"
    if isinstance(args, dict):
        return {str(k): _short_args(v, limit) for k, v in list(args.items())[:8]}
    if isinstance(args, (list, tuple)):
        return [_short_args(v, limit) for v in list(args)[:8]]
    return args


def model_step(resp, elapsed_ms: float) -> dict:
    """One model call as a step. Private equivalent of llm_cache.call_stats (same estimate rule)."""
    u = getattr(resp, "usage_metadata", None) or {}
    details = u.get("input_token_details") or {}
    cache_read, cache_write = int(details.get("cache_read") or 0), int(details.get("cache_creation") or 0)
    out_tok = int(u.get("output_tokens") or 0)
    in_tok = int(u.get("input_tokens") or 0)
    fresh = max(in_tok - cache_read - cache_write, 0)
    cost = (fresh * PRICE_PER_MTOK["input"] + out_tok * PRICE_PER_MTOK["output"]
            + cache_read * PRICE_PER_MTOK["cache_read"] + cache_write * PRICE_PER_MTOK["cache_write"]) / 1e6
    recorded = (getattr(resp, "response_metadata", None) or {}).get("latency_ms")
    if elapsed_ms >= LIVE_MIN_MS:
        ms, src = elapsed_ms, "live"
    elif isinstance(recorded, (int, float)) and recorded > 0:
        ms, src = recorded, "recorded"
    else:
        ms, src = 800 + out_tok / 55 * 1000, "estimated"
    return {"type": "model_call", "inputTokens": in_tok, "outputTokens": out_tok, "costUsd": round(cost, 6),
            "durationMs": int(ms), "durationSource": src}


def load_results(analysis: dict) -> Results:
    """Rebuild the analysis results from analysis.json, keeping their IDs (no renumbering)."""
    R = Results()
    for kind in list(Results.PREFIX) + ["link"]:
        rows = analysis.get(plural(kind))
        if isinstance(rows, list):
            R.items[kind] = [Item(**row) for row in rows if isinstance(row, dict) and row.get("kind") == kind]
    return R


def suggested_questions(analysis: dict, limit: int = 4) -> list[str]:
    """Deterministic starter questions from the analysis: the undecided key event, the main contradiction and the
    highest-ranked open questions (gaps). Same analysis, same questions, so their answers can be recorded once."""
    out: list[str] = []

    def add(q: str) -> None:
        q = " ".join(q.split())
        if q and q not in out and len(out) < limit:
            out.append(q)

    verdicts = analysis.get("verdicts") or []
    if verdicts:
        v = verdicts[0]
        title = re.sub(r"^Key event\s+", "", v["episode_title"])
        add(f"Which explanations fit the key event {title}, and what evidence would tell them apart?"
            if not v.get("decided") else f"What evidence supports the leading explanation of the key event {title}?")
    contradictions = sorted(analysis.get("contradictions") or [], key=lambda x: -x.get("score", 0))
    if contradictions:
        add(f"{contradictions[0]['title'].rstrip('.')}: which records are involved, and what could explain the difference?")
    explanation_gap = any(g.get("data", {}).get("gap_type") == "uncertain" and "explanation" in g["title"].lower()
                          for g in analysis.get("gaps") or [])
    for g in sorted(analysis.get("gaps") or [], key=lambda g: -g.get("score", 0)):
        if g.get("status") == "resolved" or (explanation_gap and verdicts and "explanation" in g["title"].lower()):
            continue
        add(g["title"] if g["title"].endswith("?") else f"What is known about: {g['title']}?")
    return out


def _record_ids(obj, out: set[int]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("record_id", "statement_record") and isinstance(v, int):
                out.add(v)
            elif k in ("record_ids", "conflicting_records", "consistent_records") and isinstance(v, list):
                out.update(i for i in v if isinstance(i, int))
            else:
                _record_ids(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _record_ids(v, out)


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text")


_ITEM_DATA = ("gap_type", "missing", "direction", "kind", "label", "supporting", "contradicting", "observations",
              "inference", "unknowns", "counterevidence", "assumptions", "limitations", "confidence", "record_ids",
              "statement_record", "conflicting_records", "consistent_records", "possible_reasons",
              "resolving_evidence", "severity", "agent_answers", "artifact", "rationale", "window", "speaker")


class CaseChat:
    """Chat over the latest analysis of one case. Load once per analysis version; `answer` is thread-safe apart from
    the model, which LangChain calls synchronously."""

    def __init__(self, ingest_dir: Path, analysis_dir: Path, board: dict | None = None):
        self.analysis = json.loads((Path(analysis_dir) / "analysis.json").read_text(encoding="utf-8"))
        board = board or json.loads((Path(analysis_dir) / "board.json").read_text(encoding="utf-8"))
        self.source_ids = {s["id"] for s in board.get("sources", [])}
        self.suggestions = suggested_questions(self.analysis)
        self._ingest_dir = Path(ingest_dir)
        self._case: Case | None = None

    @property
    def archive_sha256(self) -> str:
        return (self.analysis.get("case") or {}).get("source_archive_sha256") or "unknown"

    def _load(self):
        if self._case is None:
            case = Case(self._ingest_dir)
            self.R = load_results(self.analysis)
            self.ctx = Context(case, self.R)
            self.tz = case_tz(case)
            self._case = case
        return self._case

    def citation(self, rid: int) -> dict:
        case = self._load()
        c = case.cite(rid)
        out = {"evidence_id": c["evidence_id"], "locator": c["locator"], "excerpt": case.records[rid].content[:280]}
        if c["id"] in self.source_ids:
            out["source_id"] = c["id"]
        return out

    def tools(self, seen: set[int], calls: list[str], steps: list[dict] | None = None) -> dict:
        case = self._load()
        R = self.R

        def log(name: str, args: dict, result) -> str:
            calls.append(name)
            _record_ids(result, seen)
            out = json.dumps(result, default=str)[:TOOL_OUTPUT_CHARS]
            if steps is not None:
                steps.append({"type": "tool_call", "tool": name, "args": _short_args(args), "resultChars": len(out)})
            return out

        tools = read_tools(case, self.ctx, R, self.analysis.get("verdicts") or [], log)

        def list_items(kind: Literal["contradiction", "insight", "suggestion", "finding", "hypothesis", "claim"]) -> str:
            """List analysis results of one kind (contradictions, insights, next-step suggestions, findings, competing
            explanations or statement claims) with their IDs. Read one with get_item."""
            rows = [{"id": i.id, "title": i.title, "certainty": i.certainty, "status": i.status, "score": round(i.score, 3)}
                    for i in R.get(kind)[:40]]
            return log("list_items", {"kind": kind}, rows)

        def get_item(item_id: str) -> str:
            """Read one analysis result (gap G-.., contradiction X-.., insight I-.., explanation H-.., suggestion S-..,
            finding F-.., ML signal ML-..) with its reasoning and the record IDs it cites."""
            it = R.by_id(str(item_id).strip())
            if not it:
                return log("get_item", {"item_id": item_id}, {"error": "no such item"})
            data = {k: it.data[k] for k in _ITEM_DATA if k in it.data}
            for k in ("record_ids", "conflicting_records", "consistent_records"):
                if isinstance(data.get(k), list):
                    data[k] = data[k][:30]
            for k in ("supporting", "contradicting"):
                if isinstance(data.get(k), list):
                    data[k] = data[k][:8]
            return log("get_item", {"item_id": item_id}, {
                "id": it.id, "kind": it.kind, "title": it.title, "text": it.text[:1500], "certainty": it.certainty,
                "status": it.status, "data": data,
                "citations": [{"record_id": c.get("record_id"), "citation": c.get("id")} for c in it.citations[:20]]})

        def submit_answer(summary: str, observations: list[dict], inference: str, unknowns: list[str],
                          evidence_status: Literal["supported", "partial", "insufficient"]) -> str:
            """Submit the final answer. summary: one or two neutral sentences answering the question. observations:
            [{"text": ..., "record_ids": [..]}], each citing record IDs returned by the tools. inference: what may follow
            from the observations, clearly as inference ("" if none). unknowns: what the records do not show.
            evidence_status: supported, partial or insufficient."""
            return "submitted"

        return {**tools, "list_items": list_items, "get_item": get_item, "submit_answer": submit_answer}

    def answer(self, question: str, history: list[tuple[str, str]], chat_model, prior_ids: set[int] | None = None) -> Answer:
        """Run the tool loop. `history` holds earlier (question, answer text) pairs of this thread. Exceptions from the
        model (including `CacheMiss` in replay mode) propagate to the caller; nothing is stored here."""
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

        self._load()
        seen: set[int] = set(prior_ids or ())
        calls: list[str] = []
        steps: list[dict] = []
        tools = self.tools(seen, calls, steps)
        model = chat_model.bind_tools(list(tools.values()))
        messages = [SystemMessage(SYSTEM_PROMPT.format(tz=self.tz))]
        for q, a in history[-HISTORY_TURNS:]:
            messages += [HumanMessage(q), AIMessage(a)]
        messages.append(HumanMessage(question))
        model_calls = 0
        for _ in range(MAX_STEPS):
            t0 = time.perf_counter()
            resp = model.invoke(messages)
            steps.append(model_step(resp, (time.perf_counter() - t0) * 1000))
            model_calls += 1
            messages.append(resp)
            tool_calls = getattr(resp, "tool_calls", None) or []
            if not tool_calls:
                return self._with_steps(self._from_text(_text(resp.content), seen, model_calls), steps)
            final = None
            for tc in tool_calls:
                fn = tools.get(tc["name"])
                if tc["name"] == "submit_answer":
                    final = tc["args"]
                    out = "submitted"
                elif fn is None:
                    out = json.dumps({"error": f"unknown tool {tc['name']}"})
                else:
                    try:
                        out = fn(**(tc.get("args") or {}))
                    except Exception as exc:  # noqa: BLE001 - a bad tool call is reported back to the model
                        out = json.dumps({"error": f"{type(exc).__name__}: {str(exc)[:200]}"})
                messages.append(ToolMessage(out, tool_call_id=tc["id"], name=tc["name"]))
            if final is not None:
                return self._with_steps(self._assemble(final, seen, model_calls), steps)
        return Answer("I could not finish this answer within the step limit. Try a narrower question.", "insufficient",
                      [], model_calls=model_calls, steps=steps)

    @staticmethod
    def _with_steps(ans: Answer, steps: list[dict]) -> Answer:
        ans.steps = steps
        return ans

    # ------------------------------------------------------------------ assembly
    def _assemble(self, args: dict, seen: set[int], model_calls: int) -> Answer:
        case = self._load()
        claimed = args.get("evidence_status") if args.get("evidence_status") in ("supported", "partial", "insufficient") \
            else "partial"
        kept, dropped = [], 0
        for o in args.get("observations") or []:
            if not isinstance(o, dict) or not str(o.get("text", "")).strip():
                continue
            ids = []
            for i in o.get("record_ids") or []:
                try:
                    i = int(i)
                except (TypeError, ValueError):
                    continue
                if i in seen and i in case.records and i not in ids:
                    ids.append(i)
            if ids:
                kept.append((str(o["text"]).strip()[:500], ids[:6]))
            else:
                dropped += 1  # cite or drop: only records a tool returned in this conversation count
        rid_order: list[int] = []
        observations = []
        for text, ids in kept[:8]:
            for i in ids:
                if i not in rid_order:
                    rid_order.append(i)
            observations.append({"text": text, "citations": [rid_order.index(i) for i in ids]})
        status: Status = claimed
        if not observations:
            status = "insufficient"
        elif dropped and status == "supported":
            status = "partial"
        summary = str(args.get("summary") or "").strip()[:800]
        inference = str(args.get("inference") or "").strip()[:800]
        unknowns = [str(u).strip()[:300] for u in (args.get("unknowns") or []) if str(u).strip()][:5]
        if dropped:
            unknowns.append(f"{dropped} statement{'s' if dropped > 1 else ''} without a valid record citation "
                            f"{'were' if dropped > 1 else 'was'} left out.")
        citations = [self.citation(i) for i in rid_order]
        return Answer(self._content(summary, observations, citations, inference, unknowns, status), status, citations,
                      observations, inference, unknowns, rid_order, model_calls, summary)

    def _from_text(self, text: str, seen: set[int], model_calls: int) -> Answer:
        """The model answered without submit_answer: keep its text, but cite nothing it did not read."""
        text = text.strip() or "No answer was produced."
        return Answer(self._content(text, [], [], "", ["This answer was not submitted with citations; treat it as "
                                                        "unsupported."], "insufficient"), "insufficient", [],
                      unknowns=["This answer was not submitted with citations; treat it as unsupported."],
                      model_calls=model_calls, summary=text)

    @staticmethod
    def _content(summary: str, observations: list[dict], citations: list[dict], inference: str, unknowns: list[str],
                 status: Status) -> str:
        parts = [summary] if summary else []
        if observations:
            lines = []
            for o in observations:
                refs = ", ".join(f"{citations[i]['evidence_id']} {citations[i]['locator']}" for i in o["citations"])
                lines.append(f"- {o['text']} [{refs}]")
            parts.append("Observed in the records:\n" + "\n".join(lines))
        if inference:
            parts.append("Inference (not established by the records): " + inference)
        if unknowns:
            parts.append("Not shown by the records:\n" + "\n".join(f"- {u}" for u in unknowns))
        if status == "insufficient" and not observations:
            parts.append("The records available do not answer this question.")
        return "\n\n".join(parts)
