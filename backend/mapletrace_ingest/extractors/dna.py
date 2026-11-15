"""Biological evidence: STR profiles, lab comparison tables, lab report text, FASTA and VCF.

Mapletrace does not perform DNA analysis. It ingests the lab's *results* as
expert findings (who/what sample, which loci, what conclusion and statistic)
so they can be placed in the case alongside the digital evidence.
"""

from __future__ import annotations

import hashlib
import re
from collections import OrderedDict
from pathlib import Path

from ..classify import STR_LOCI, norm_col
from ..intake import decode_text_file
from ..timeparse import HumanTimeResolver, find_reference_date, parse_timestamp
from . import Outcome
from .documents import Locator, parse_header, sentences

_FINDING = re.compile(r"\b(match|matches|consistent with|cannot be excluded|excluded|inconclusive|likelihood ratio|"
                      r"random match|contributor|mixture|profile|identified|source of)\b", re.I)
_SAMPLE_ID = re.compile(r"\b(?:[A-Z]{1,5}-\d{1,4}[A-Z]?|Item\s+\d+[A-Z]?|Exhibit\s+[A-Z0-9\-]+)\b")


def _sample_entity(sample):
    return (("sample", str(sample).strip().lower(), str(sample).strip()), "sample") if sample else (None, "sample")


def extract_dna_table(ctx, file_id: int, payload: dict, decision) -> Outcome:
    rows, cmap = payload["rows"], decision.column_map
    cols = payload["columns"]
    created = 0
    data_fmt = payload.get("data_format")

    def loc(i):
        return {"row": i + 2, "row_kind": "line"} if data_fmt == "csv" else {"row": i, "row_kind": "index"}

    if "comparison" in cmap:
        for i, r in enumerate(rows):
            q = r.get(cmap.get("questioned", "")) or r.get(cmap.get("sample", ""))
            ref = r.get(cmap.get("reference", ""))
            result = r.get(cmap["comparison"])
            stats = {c: r[c] for c in cols if norm_col(c) in {"likelihoodratio", "lr", "rmp", "randommatchprobability", "matchprobability"} and r.get(c)}
            conclusion = next((r[c] for c in cols if norm_col(c) in {"conclusion", "result", "interpretation"} and r.get(c)), result)
            ts = parse_timestamp(r.get(cmap.get("timestamp", "")) or r.get(cmap.get("date_only", "")), ctx.tz, ctx.dayfirst)
            attrs = {k: v for k, v in r.items() if v not in (None, "")}
            text = f"DNA comparison: {q} vs {ref}: {conclusion}" + (f" ({', '.join(f'{k}={v}' for k, v in stats.items())})" if stats else "")
            ctx.add_record(file_id, "dna_comparison", ts=ts, actor=None, target=ref, content=text, attributes=attrs,
                           locator=loc(i), reliability="expert_finding",
                           entities=[_sample_entity(q), (_sample_entity(ref)[0], "reference_sample")])
            created += 1
        ctx.save_schema(file_id, payload, decision, len(rows), {})
        return Outcome("parsed", "dna_comparison_table", [f"{created} sample comparisons"])

    profiles: "OrderedDict[str, dict]" = OrderedDict()
    first_row: dict[str, int] = {}
    sample_col = cmap.get("sample")
    if "locus" in cmap:  # long format: one row per sample+locus
        allele_cols = cmap.get("allele", "").split("|") if cmap.get("allele") else []
        for i, r in enumerate(rows):
            s = r.get(sample_col) if sample_col else "unlabelled"
            locus = r.get(cmap["locus"])
            alleles = [r.get(c) for c in allele_cols if r.get(c) not in (None, "")]
            profiles.setdefault(s, {})[locus] = alleles
            first_row.setdefault(s, i)
    else:  # wide format: one row per sample, loci as columns
        loci = [c for c in cols if norm_col(c) in STR_LOCI]
        for i, r in enumerate(rows):
            s = r.get(sample_col) if sample_col else f"row{i + 1}"
            profiles[s] = {c: [a for a in re.split(r"[,/; ]+", str(r.get(c) or "")) if a] for c in loci}
            first_row[s] = i
    for s, loci in profiles.items():
        typed = {k: v for k, v in loci.items() if v}
        attrs = {"loci": loci, "loci_typed": len(typed), "loci_total": len(loci),
                 "profile_hash": hashlib.sha256(repr(sorted(typed.items())).encode()).hexdigest()[:16]}
        partial = len(typed) < len(loci) or len(typed) < 10
        if partial:
            attrs["partial_profile"] = True
        ctx.add_record(file_id, "dna_profile", ts=None, content=f"STR profile for sample {s}: {len(typed)}/{len(loci)} loci typed",
                       attributes=attrs, locator={**loc(first_row[s]), "sample": s}, reliability="expert_finding",
                       entities=[_sample_entity(s)])
        created += 1
    ctx.save_schema(file_id, payload, decision, len(rows), {})
    return Outcome("parsed" if created else "partial", "dna_str_table", [f"{created} sample profiles"])


def extract_fasta(ctx, file_id: int, path: Path) -> Outcome:
    text, _ = decode_text_file(path)
    created = 0
    for m in re.finditer(r"^>(?P<hdr>[^\n]*)\n(?P<seq>[^>]*)", text, re.M):
        seq = re.sub(r"\s", "", m.group("seq")).upper()
        if not seq:
            continue
        gc = (seq.count("G") + seq.count("C")) / len(seq)
        sid = m.group("hdr").split()[0] if m.group("hdr").strip() else f"seq{created + 1}"
        ctx.add_record(file_id, "dna_sequence", content=f"Sequence {sid}: {len(seq)} bp",
                       attributes={"header": m.group("hdr"), "length_bp": len(seq), "gc_fraction": round(gc, 3),
                                   "sequence_sha256": hashlib.sha256(seq.encode()).hexdigest(), "preview": seq[:60]},
                       locator={"char_start": m.start(), "char_end": m.end()}, reliability="expert_finding",
                       entities=[_sample_entity(sid)])
        created += 1
    return Outcome("parsed" if created else "partial", "fasta", [f"{created} sequences (summarized, raw sequence hashed)"])


def extract_vcf(ctx, file_id: int, path: Path) -> Outcome:
    text, _ = decode_text_file(path)
    samples, variants, header_line = [], 0, None
    for i, line in enumerate(text.splitlines()):
        if line.startswith("#CHROM"):
            samples = line.split("\t")[9:]
            header_line = i + 1
        elif line and not line.startswith("#"):
            variants += 1
    for s in samples or ["unnamed"]:
        ctx.add_record(file_id, "dna_variant_summary", content=f"VCF sample {s}: {variants} variant sites",
                       attributes={"variant_sites": variants, "samples_in_file": samples},
                       locator={"line": header_line, "sample": s}, reliability="expert_finding",
                       entities=[_sample_entity(s)])
    return Outcome("parsed", "vcf", [f"{len(samples)} samples, {variants} variant sites (summarized)"])


def extract_lab_report(ctx, file_id: int, payload: dict) -> Outcome:
    """Narrative lab reports: every sentence with a finding becomes an expert-finding record."""
    text, loc = payload["text"], Locator(payload["text"], payload["segments"])
    fields, body_start = parse_header(text)
    analyst = fields.get("analyst") or fields.get("examiner") or fields.get("author") or fields.get("prepared by")
    if analyst:
        analyst = re.split(r",|\(", analyst)[0].strip() or analyst  # "R. Castellanos, DNA Analyst II (...)"
    report_date = parse_timestamp(fields.get("date") or fields.get("report date"), ctx.tz, ctx.dayfirst)
    resolver = HumanTimeResolver(ctx.tz, find_reference_date(text, ctx.dayfirst), ctx.dayfirst)
    findings = context = 0
    for sent, s, e in sentences(text, body_start):
        is_finding = bool(_FINDING.search(sent))
        samples = list(dict.fromkeys(_SAMPLE_ID.findall(sent)))
        mentions = resolver.resolve(sent, s)
        ts = next((m.value for m in mentions if m.value.utc), None)
        attrs = {"report_header": fields, "samples_mentioned": samples, "is_finding": is_finding,
                 "report_date": report_date.to_dict() if report_date else None}
        ctx.add_record(file_id, "lab_finding" if is_finding else "lab_note", ts=ts, actor=analyst, content=sent,
                       attributes=attrs, locator=loc.at(s, e), reliability="expert_finding",
                       entities=[(analyst, "analyst")] + [_sample_entity(x) for x in samples])
        findings += is_finding
        context += not is_finding
    return Outcome("parsed", "lab_report", [f"{findings} findings, {context} context sentences", f"analyst: {analyst or 'unknown'}"])
