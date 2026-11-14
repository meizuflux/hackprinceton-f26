"""Biological evidence: synthetic STR profiles (20 CODIS core loci + Amelogenin) and the lab report.

Truth: UF-1 (unknown female) is Vivian Shen. No reference sample from her exists in the case file;
obtaining one is the highest-value gap-closing action."""
from __future__ import annotations

from .catalog import path_of
from .common import Out, Registry, render_marked_text, rng

LOCI = [
    ("CSF1PO", ["9", "10", "11", "12", "13"]), ("D3S1358", ["14", "15", "16", "17", "18"]),
    ("D5S818", ["9", "10", "11", "12", "13"]), ("D7S820", ["8", "9", "10", "11", "12"]),
    ("D8S1179", ["10", "11", "12", "13", "14", "15", "16"]),
    ("D13S317", ["8", "9", "10", "11", "12", "13"]), ("D16S539", ["8", "9", "10", "11", "12", "13"]),
    ("D18S51", ["12", "13", "14", "15", "16", "17", "18", "19"]),
    ("D21S11", ["27", "28", "29", "30", "30.2", "31", "31.2", "32.2"]), ("FGA", ["19", "20", "21", "22", "23", "24", "25"]),
    ("TH01", ["6", "7", "8", "9", "9.3", "10"]), ("TPOX", ["8", "9", "10", "11", "12"]),
    ("vWA", ["14", "15", "16", "17", "18", "19"]), ("D1S1656", ["12", "13", "14", "15", "16", "17.3"]),
    ("D2S441", ["10", "11", "11.3", "12", "14", "15"]), ("D2S1338", ["17", "18", "19", "20", "23", "24", "25"]),
    ("D10S1248", ["12", "13", "14", "15", "16"]), ("D12S391", ["17", "18", "19", "20", "21", "22"]),
    ("D19S433", ["12", "13", "14", "14.2", "15", "15.2", "16"]), ("D22S1045", ["11", "14", "15", "16", "17"]),
]


def _key(a: str) -> float:
    return float(a)


def _genotypes(r):
    people = {}
    for who in ["K1", "K2", "K3", "UF1"]:
        g = {}
        for locus, pool in LOCI:
            w = [len(pool) - abs(i - len(pool) // 2) for i in range(len(pool))]
            a, b = r.choices(pool, w, k=2)
            g[locus] = sorted({a, b}, key=_key)
        people[who] = g
    return people


def _fmt(alleles) -> str:
    return ",".join(sorted(set(alleles), key=_key))


def write_all(out: Out, reg: Registry):
    r = rng("dna")
    g = _genotypes(r)
    eid = "EV-011"
    samples = [
        ("Q1", "questioned", "Swab, keypad of cabinet SC-EBC-01 (EBC 4-12)", "2026-10-19 10:30", 0.41, "3",
         {L: g["K1"][L] + g["K3"][L] + g["UF1"][L] for L, _ in LOCI}, "X,Y",
         "Mixture; at least three contributors", "DNA_PROFILE_Q1", "key"),
        ("Q2", "questioned", "Swab, handle of cabinet SC-EBC-01 glass door", "2026-10-19 10:33", 0.62, "2",
         {L: g["UF1"][L] + (g["K2"][L] if r.random() < 0.7 else []) for L, _ in LOCI}, "X",
         "Mixture; major female contributor plus low-level minor contributor (allele drop-out likely)",
         "DNA_PROFILE_Q2", "key"),
        ("Q3", "questioned", "Swab, rim of wine glass A from office 4-01 wastebasket", "2026-10-19 10:50", 1.85, "1",
         {L: g["K1"][L] for L, _ in LOCI}, "X,Y", "Single source, male", "DNA_PROFILE_Q3", "supporting"),
        ("Q4", "questioned", "Swab, rim of wine glass B (lipstick residue) from office 4-01 wastebasket",
         "2026-10-19 10:53", 2.10, "1", {L: g["UF1"][L] for L, _ in LOCI}, "X",
         "Single source, female; designated UF-1", "DNA_PROFILE_Q4", "key"),
        ("K1", "known", "Reference buccal swab, Richard Halvorsen", "2026-10-20 17:40", 3.20, "1",
         {L: g["K1"][L] for L, _ in LOCI}, "X,Y", "Reference", "DNA_PROFILE_K1", "supporting"),
        ("K2", "known", "Reference buccal swab, Priya Raman", "2026-10-20 12:05", 2.95, "1",
         {L: g["K2"][L] for L, _ in LOCI}, "X", "Reference", "DNA_PROFILE_K2", "red_herring"),
        ("K3", "known", "Reference buccal swab, Dana Whitfield", "2026-10-20 09:10", 3.05, "1",
         {L: g["K3"][L] for L, _ in LOCI}, "X", "Reference", "DNA_PROFILE_K3", "supporting"),
    ]
    header = ["sample_id", "sample_type", "description", "collected_at_local", "quant_ng_per_ul", "est_contributors"] \
        + [L for L, _ in LOCI] + ["AMEL", "notes"]
    rows = []
    mixes = {}
    for sid, stype, desc, when, q, nc, prof, amel, notes, tag, rel in samples:
        mixes[sid] = {L: set(prof[L]) for L, _ in LOCI}
        rows.append([sid, stype, desc, when, q, nc] + [_fmt(prof[L]) for L, _ in LOCI] + [amel, notes])
        reg.key(tag, eid, f"sample_id={sid}")
        reg.rec(eid, f"sample_id={sid}", rel, "", [tag])
    out.csv(path_of(eid), header, rows)

    report = f"""SYNTHETIC CASE DATA - FICTIONAL - FOR TRAINING AND DEMONSTRATION ONLY
SOUTH BAY REGIONAL FORENSIC LABORATORY - FORENSIC BIOLOGY UNIT
LABORATORY REPORT

Lab case:        LAB-26-3318
Agency case:     SBRPD-26-104417
Requested by:    Det. Sam Okoye, SBRPD High-Tech Theft Unit
Report date:     2026-10-22 15:05 PDT
Analyst:         R. Castellanos, DNA Analyst II (technical review: J. Moreau)
Method:          Quantification; PCR amplification of 20 CODIS core STR loci plus Amelogenin;
                 capillary electrophoresis; probabilistic genotyping for mixtures.
Allele calls:    see attached table str_profiles.csv

ITEMS RECEIVED (2026-10-20 08:30, sealed, seals intact)
  Q1  Swab, keypad of cabinet SC-EBC-01 (EBC 4-12)
  Q2  Swab, handle of cabinet SC-EBC-01 glass door
  Q3  Swab, rim of wine glass A (office 4-01 wastebasket)
  Q4  Swab, rim of wine glass B with lipstick residue (office 4-01 wastebasket)
  K1  Reference buccal swab, Richard Halvorsen (received 2026-10-21)
  K2  Reference buccal swab, Priya Raman (received 2026-10-21)
  K3  Reference buccal swab, Dana Whitfield (received 2026-10-21)

RESULTS AND CONCLUSIONS
1. Q4 (wine glass B) yielded a single-source female DNA profile, designated UF-1 (unknown female 1). {{{{DNA_Q4_UF1}}}}
   K1, K2 and K3 are excluded as the source of UF-1. {{{{DNA_UF1_EXCLUSIONS}}}}
2. UF-1 was searched against the state and national DNA indexes on 2026-10-22. No candidate match was returned. {{{{DNA_CODIS_NOHIT}}}}
3. Q3 (wine glass A) yielded a single-source male profile that matches K1 (Richard Halvorsen).
   Random match probability: approximately 1 in 3.1 x 10^24 (synthetic statistic). {{{{DNA_Q3_K1}}}}
4. Q2 (cabinet handle) is a two-person mixture. The major contributor profile matches UF-1
   (likelihood ratio approximately 8.4 x 10^19 in favour of UF-1 as a contributor; synthetic statistic). {{{{DNA_Q2_UF1_MAJOR}}}}
   The minor component is low-level with probable allele drop-out. K2 (Priya Raman) cannot be excluded
   as the minor contributor (likelihood ratio approximately 4.2 x 10^3, limited support; synthetic statistic). {{{{DNA_Q2_K2_MINOR}}}}
   K1 (Richard Halvorsen) and K3 (Dana Whitfield) are excluded as contributors to Q2. {{{{DNA_Q2_K1_EXCLUDED}}}}
5. Q1 (cabinet keypad) is a mixture of at least three contributors. K1 and K3 cannot be excluded
   (likelihood ratios approximately 3.8 x 10^9 and 1.2 x 10^6; synthetic statistics). The remaining alleles
   are consistent with UF-1 (likelihood ratio approximately 2.6 x 10^7; synthetic statistic). K2 is excluded. {{{{DNA_Q1_MIXTURE}}}}

LIMITATIONS
- DNA results cannot establish when or how DNA was deposited. Touch DNA may persist on surfaces between cleanings.
- Per the requesting agency, the EBC cabinet glass and handle are wiped by the executive-floor cleaning crew on
  Friday evenings; the keypad is not cleaned. This information was provided by the agency and was not verified
  by the laboratory. {{{{DNA_CLEANING_NOTE}}}}
- No reference samples were submitted for any individual other than K1, K2 and K3. UF-1 can be compared
  with additional reference samples if they are submitted. {{{{DNA_NO_OTHER_REFERENCES}}}}

Retention: DNA extracts retained at -20 C. Remaining swab material returned to SBRPD Property 2026-10-22.
"""
    out.text(path_of("EV-010"), render_marked_text(report, "EV-010", reg))
    for tag in ["DNA_Q4_UF1", "DNA_UF1_EXCLUSIONS", "DNA_CODIS_NOHIT", "DNA_Q3_K1", "DNA_Q2_UF1_MAJOR",
                "DNA_Q2_K2_MINOR", "DNA_Q2_K1_EXCLUDED", "DNA_Q1_MIXTURE", "DNA_CLEANING_NOTE",
                "DNA_NO_OTHER_REFERENCES"]:
        reg.rec("EV-010", reg.keys[tag]["locator"], "key" if tag in {"DNA_Q4_UF1", "DNA_Q2_UF1_MAJOR",
                                                                       "DNA_CODIS_NOHIT", "DNA_Q2_K1_EXCLUDED",
                                                                       "DNA_NO_OTHER_REFERENCES"}
                else ("red_herring" if tag == "DNA_Q2_K2_MINOR" else "supporting"), "", [tag])
    return g, mixes
