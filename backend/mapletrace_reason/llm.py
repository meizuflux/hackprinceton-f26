"""Optional LLM layer (LangChain + deepagents, Anthropic Claude).

1. Claim extraction: a structured-output call per statement/interview turns free text into the same claim
   structure the rule-based extractor produces, citing the exact sentence (by record ID).
2. Investigator: a deepagents agent with read-only tools over the analysis. It answers open questions and
   records extra insights. It may only record an insight whose citations resolve to real records, and it
   checks support with a verifier subagent first. Its output is labelled as agent-generated and inferred.

Every call is written to the audit log (model, input and output hashes). Needs ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .analytics import Context, case_tz
from .claims import _match_person, _night_window
from .model import Item, stable_key
from .store import iso, parse_ts

INVESTIGATOR_PROMPT = """You are an evidence analyst helping an investigator review a case. You work only from the
tools provided; never invent facts, names, times or records.

Rules:
- Cite or drop: every observation you record must cite record IDs returned by the tools.
- Keep observations (what a record says) separate from inferences (what follows) and unknowns.
- A gap in evidence is uncertainty, not proof. Missing records never count against a person.
- Word findings neutrally ("conflicts with records", not "lied"). Present several explanations when they fit.
- Never use nationality, ethnicity, religion or similar attributes.
- Before recording an insight, ask the `verifier` subagent to confirm that each cited record supports its observation.

Task: review the open questions and competing explanations, look for connections or contradictions the
automatic analysis missed (search records, read them), answer what you can with citations using
`answer_question`, and record at most {max_insights} new, non-duplicate insights with `record_insight`.
Stop when you have nothing well-supported left to add."""

VERIFIER_PROMPT = """You check citations. For each (statement, record_id) pair, call get_record and reply SUPPORTED,
PARTLY SUPPORTED or NOT SUPPORTED with one sentence of reason. Judge only from the record text."""


class ExtractedClaim(BaseModel):
    record_id: int = Field(description="ID of the sentence or turn the claim comes from")
    claim_type: Literal["location", "activity", "contact", "knowledge", "denial", "time"]
    polarity: bool = Field(description="true if asserted, false if denied ('I never went there')")
    place: Optional[str] = Field(default=None, description="place named or implied ('home', 'the office')")
    counterpart: Optional[str] = Field(default=None, description="other person named, if any")
    time_start_local: Optional[str] = Field(default=None, description="ISO 8601 local start if the text implies one")
    time_end_local: Optional[str] = Field(default=None, description="ISO 8601 local end if the text implies one")
    summary: str = Field(description="the claim in a few neutral words")


class ExtractedClaims(BaseModel):
    claims: list[ExtractedClaim]


def _h(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


class LLMRun:
    def __init__(self, case, ctx: Context, cfg: dict, audit):
        self.case, self.ctx, self.cfg, self.audit = case, ctx, cfg, audit
        self.calls: list[dict] = []
        self._lock = threading.Lock()  # LangGraph runs tools on worker threads
        self.claims_added = 0
        self.insights_added = 0
        self.answers = 0
        self._chat = cfg.get("chat_model")          # tests can inject a fake model
        self._verifier_chat = cfg.get("verifier_chat_model")
        if self._chat is None and not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("LLM mode needs the ANTHROPIC_API_KEY environment variable (or run without --llm)")

    def chat(self, verifier: bool = False):
        if verifier and self._verifier_chat is not None:
            return self._verifier_chat
        if not verifier and self._chat is not None:
            return self._chat
        from langchain_anthropic import ChatAnthropic
        model = self.cfg.get("verifier_model" if verifier else "model", "claude-opus-5-5")
        m = ChatAnthropic(model=model, max_tokens=16000, reasoning_effort="medium" if verifier else "high", max_retries=3,
                          timeout=600)
        if verifier:
            self._verifier_chat = m
        else:
            self._chat = m
        return m

    def _log(self, stage: str, model: str, inp, out) -> None:
        entry = {"stage": stage, "model": model, "input_sha256": _h(inp), "output_sha256": _h(out)}
        with self._lock:
            self.calls.append(entry)
            self.audit.write("llm", stage, entry)

    # ------------------------------------------------------------------ claims
    def extract_claims(self, episodes, existing: list[Item]) -> list[Item]:
        case, ctx = self.case, self.ctx
        tz = case_tz(case)
        have = {(c.data["record_id"], c.data["claim_type"]) for c in existing}
        by_file: dict[int, list] = {}
        for r in case.records.values():
            if r.type == "statement_claim" or (r.type == "interview_turn" and r.attrs.get("speaker_role") == "interviewee"):
                by_file.setdefault(r.file_id, []).append(r)
        model = self.chat().with_structured_output(ExtractedClaims, method="json_schema")
        ep_day = parse_ts(episodes[0].data["start"]).astimezone(tz) if episodes else None
        out = []
        for fid, recs in by_file.items():
            recs.sort(key=lambda r: r.locator.get("char_start", 0))
            speaker = next((case.name(p) for p, _, _ in ctx.persons_for(recs[0])), "unknown")
            lines = "\n".join(f"[{r.id}] {r.content}" for r in recs)
            prompt = (f"Statement or interview by {speaker} (file {case.files[fid]['original_path']}). Case time zone: {tz}. "
                      f"Key event date: {ep_day:%A %Y-%m-%d} (local)." if ep_day else "") + \
                     ("\nExtract every factual claim the speaker makes about where they were, what they did, who they were "
                      "in contact with, what they knew, or what they deny. Use only the record IDs shown in brackets. Give "
                      "times only when the text supports them.\n\n" + lines)
            try:
                res = model.invoke(prompt)
            except Exception as exc:  # noqa: BLE001 - one failed call must not stop the analysis
                self.audit.write("llm", "claim_extraction_failed", {"file": case.files[fid]["original_path"], "error": str(exc)[:300]})
                continue
            self._log("claim_extraction", self.cfg.get("model", "injected"), prompt, res.model_dump() if hasattr(res, "model_dump") else res)
            valid = {r.id: r for r in recs}
            for c in getattr(res, "claims", []):
                rec = valid.get(c.record_id)
                if rec is None or (c.record_id, c.claim_type) in have:
                    continue
                spk = next((p for p, _, _ in ctx.persons_for(rec)), None)
                if spk is None:
                    continue
                w, assumptions = self._window(c, rec, ep_day, tz)
                ctype = "location" if c.claim_type in ("location", "denial") and c.place else \
                    "contact" if c.claim_type == "contact" else c.claim_type
                place = "home" if (c.place or "").strip().lower() in ("home", "at home", "my house", "my place") else c.place
                out.append(Item("claim", stable_key("claim", rec.id, ctype, c.polarity, place, c.counterpart),
                                f"{case.name(spk)}: {c.summary[:60]}", rec.content, certainty="observed", score=0.5,
                                citations=[case.cite(rec.id)],
                                data={"speaker": spk, "subject": spk, "claim_type": ctype, "polarity": c.polarity,
                                      "place": place, "counterpart": _match_person(case, c.counterpart) if c.counterpart else None,
                                      "window": [iso(w[0]), iso(w[1])] if w else None, "record_id": rec.id,
                                      "assumptions": assumptions, "extraction": f"llm:{self.cfg.get('model', 'injected')}",
                                      "quote": rec.content}))
                have.add((c.record_id, c.claim_type))
        self.claims_added = len(out)
        return out

    def _window(self, c: ExtractedClaim, rec, ep_day, tz):
        if rec.start:
            return (rec.start, rec.end), []
        try:
            if c.time_start_local:
                s = datetime.fromisoformat(c.time_start_local)
                e = datetime.fromisoformat(c.time_end_local) if c.time_end_local else s
                s = s if s.tzinfo else s.replace(tzinfo=tz)
                e = e if e.tzinfo else e.replace(tzinfo=tz)
                return (s, e), ["time window read from the sentence by the language model"]
        except ValueError:
            pass
        if ep_day and re.search(r"\b(night|evening|saturday|that day|tonight)\b", rec.content, re.I):
            return _night_window(ep_day, tz), ["time window assumed to be the night of the key event"]
        return None, []

    # ------------------------------------------------------------------ investigator
    def build_tools(self, R, verdicts, created: list) -> dict:
        """Read-only tools over the analysis, plus two guarded writers (record_insight, answer_question)."""
        case, ctx = self.case, self.ctx
        tz = case_tz(case)
        max_insights = int(self.cfg.get("max_insights", 5))
        log = self._tool_logger

        def list_open_questions() -> str:
            """List the open investigative questions (gaps) with their type, what is missing and the suggested direction."""
            rows = [{"gap_id": g.id, "question": g.title, "type": g.data["gap_type"], "status": g.status,
                     "missing": g.data["missing"], "direction": g.data["direction"]} for g in R.get("gap")]
            return log("list_open_questions", {}, rows)

        def list_explanations() -> str:
            """List the competing explanations for each key event with their support, counter-evidence and verdict."""
            rows = [{"episode": v["episode_title"], "verdict": v["verdict"],
                     "explanations": [{"statement": h.text, "label": h.data["label"],
                                       "supporting": [s["reason"] for s in h.data["supporting"][:5]],
                                       "contradicting": [s["reason"] for s in h.data["contradicting"][:5]]}
                                      for k in v["ranked"] for h in R.get("hypothesis") if h.key == k]} for v in verdicts]
            return log("list_explanations", {}, rows)

        def list_ml_signals() -> str:
            """List the traditional-ML signals computed before reasoning: place clusters (home, work, recurring evening
            places), unusual days per person, message triage (automated vs human) and possible name variants. Each has
            its method and record IDs. Treat them as leads to check with get_record, not as facts."""
            from .ml import signals_for_agent
            return log("list_ml_signals", {}, signals_for_agent(R))

        def search_records(query: str, start: str = "", end: str = "", person: str = "", limit: int = 20) -> str:
            """Search case records by words in their text, place or actor. Optional ISO start/end times (UTC) and a
            person name. Returns record IDs you can cite."""
            words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2]
            s, e = parse_ts(start) if start else None, parse_ts(end) if end else None
            hits = []
            for r in case.timed:
                if s and r.ts < s or e and r.ts > e:
                    continue
                hay = " ".join([r.content, r.place or "", r.actor or "", r.target or ""]).lower()
                who = [case.name(p) for p, _, _ in ctx.persons_for(r)]
                if person and not any(person.lower() in w.lower() for w in who):
                    continue
                if words and not all(w in hay for w in words):
                    continue
                hits.append({"record_id": r.id, "time": r.ts.astimezone(tz).isoformat(timespec="minutes"), "type": r.type,
                             "who": who, "what": r.content[:160], "where": r.place, "reliability": r.reliability,
                             "citation": case.cite(r.id)["id"]})
                if len(hits) >= min(int(limit), 50):
                    break
            return log("search_records", {"query": query, "start": start, "end": end, "person": person}, hits)

        def get_record(record_id: int) -> str:
            """Read one record in full: text, time (with uncertainty), place, people, source file and citation."""
            r = case.records.get(int(record_id))
            if not r:
                return log("get_record", {"record_id": record_id}, {"error": "no such record"})
            return log("get_record", {"record_id": record_id}, {
                "record_id": r.id, "type": r.type, "time": iso(r.ts), "window": [iso(r.start), iso(r.end)],
                "precision": r.precision, "time_flags": r.flags, "reliability": r.reliability, "text": r.content,
                "place": r.place, "people": [[case.name(p), c, b] for p, c, b in ctx.persons_for(r)],
                "attributes": {k: v for k, v in r.attrs.items() if not isinstance(v, (dict, list))},
                "citation": case.cite(r.id)})

        def record_insight(title: str, observations: list[dict], inference: str, unknowns: list[str],
                           counterevidence: list[str], assumptions: list[str], limitations: list[str],
                           confidence: Literal["low", "medium", "high"]) -> str:
            """Record a new insight. observations: [{"text": ..., "record_ids": [..]}] with at least one valid record ID
            each. Insights without valid citations are rejected."""
            if len(created) >= max_insights:
                return log("record_insight", {"title": title}, {"error": f"limit of {max_insights} insights reached"})
            obs, cites = [], []
            for o in observations or []:
                ids = [int(i) for i in o.get("record_ids", []) if int(i) in case.records]
                if not ids:
                    return log("record_insight", {"title": title}, {"error": f"observation without a valid record ID: {o.get('text', '')[:80]}"})
                cs = [case.cite(i) for i in ids]
                obs.append({"text": str(o.get("text", ""))[:400], "citations": cs})
                cites += cs
            if not obs:
                return log("record_insight", {"title": title}, {"error": "at least one cited observation is required"})
            conf = "medium" if confidence == "high" and len({c["evidence_id"] for c in cites}) < 3 else confidence
            data = {"observations": obs, "inference": inference, "unknowns": unknowns, "counterevidence": counterevidence,
                    "assumptions": assumptions, "limitations": limitations + ["generated by the investigator agent; review "
                                                                             "before relying on it"],
                    "confidence": conf, "generated_by": f"agent:{self.cfg.get('model', 'injected')}", "basis": []}
            text = "Observed: " + " ".join(o["text"] + "." for o in obs) + " Inference: " + inference
            it = Item("insight", stable_key("agent-ins", title, [c["id"] for c in cites]), title[:120], text,
                      certainty="inferred", score=0.6, citations=cites, data=data)
            created.append(it)
            return log("record_insight", {"title": title}, {"ok": True, "citations": [c["id"] for c in cites]})

        def answer_question(gap_id: str, answer: str, record_ids: list[int]) -> str:
            """Attach a cited partial answer to an open question (gap). Investigators decide whether it is resolved."""
            g = R.by_id(gap_id)
            ids = [int(i) for i in record_ids or [] if int(i) in case.records]
            if not g or g.kind != "gap":
                return log("answer_question", {"gap_id": gap_id}, {"error": "no such gap"})
            if not ids:
                return log("answer_question", {"gap_id": gap_id}, {"error": "answers need at least one valid record ID"})
            g.data.setdefault("agent_answers", []).append({"answer": answer[:600], "citations": [case.cite(i) for i in ids]})
            g.citations += [case.cite(i) for i in ids[:3]]
            if g.status == "open":
                g.status = "partially_resolved"
            self.answers += 1
            return log("answer_question", {"gap_id": gap_id}, {"ok": True})

        return {"list_open_questions": list_open_questions, "list_explanations": list_explanations,
                "list_ml_signals": list_ml_signals, "search_records": search_records, "get_record": get_record, "record_insight": record_insight,
                "answer_question": answer_question}

    def investigate(self, R, verdicts) -> list[Item]:
        from deepagents import create_deep_agent
        case = self.case
        tz = case_tz(case)
        created: list[Item] = []
        max_insights = int(self.cfg.get("max_insights", 5))
        t = self.build_tools(R, verdicts, created)
        verifier = {"name": "verifier", "description": "Checks that each cited record supports a statement.",
                    "system_prompt": VERIFIER_PROMPT, "tools": [t["get_record"]], "model": self.chat(verifier=True)}
        agent = create_deep_agent(model=self.chat(), tools=list(t.values()),
                                  system_prompt=INVESTIGATOR_PROMPT.format(max_insights=max_insights),
                                  subagents=[verifier], name="mapletrace-investigator")
        task = (f"Case: {case.info.get('case_name')}. Time zone {tz}. Start with list_explanations and list_open_questions; "
                "list_ml_signals has clustering and classification leads you can check against the records.")
        try:
            agent.invoke({"messages": [{"role": "user", "content": task}]},
                         config={"recursion_limit": int(self.cfg.get("max_steps", 40)) * 3})
        except Exception as exc:  # noqa: BLE001 - keep whatever the agent recorded before failing
            with self._lock:
                self.audit.write("llm", "investigator_stopped", {"error": str(exc)[:300], "insights": len(created)})
        self.insights_added = len(created)
        return created

    def _tool_logger(self, name: str, args: dict, result) -> str:
        out = json.dumps(result, default=str)[:20000]
        with self._lock:
            self.audit.write("agent_tool", name, {"args": args, "result_sha256": _h(result)})
            self.calls.append({"stage": "tool", "tool": name})
        return out

    def summary(self) -> dict:
        return {"enabled": True, "model": self.cfg.get("model"), "verifier_model": self.cfg.get("verifier_model"),
                "llm_calls": sum(1 for c in self.calls if c.get("stage") != "tool"),
                "tool_calls": sum(1 for c in self.calls if c.get("stage") == "tool"),
                "claims_added": self.claims_added, "insights_added": self.insights_added, "answers": self.answers}
