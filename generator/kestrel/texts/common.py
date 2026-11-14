"""Shared document helpers. Tag relevance lives here so every writer labels the same way."""
from __future__ import annotations

from ..catalog import path_of
from ..common import Out, Registry, render_marked_text

BANNER = "SYNTHETIC CASE DATA - FICTIONAL - FOR TRAINING AND DEMONSTRATION ONLY"

# Relevance for tagged lines; anything not listed defaults to "supporting".
REL = {
    "IR_OWNER_POI": "red_herring", "STMT_R_DISAPPOINTED": "red_herring", "INT_H1_POINTS_TO_OTHERS": "red_herring",
    "INT_H1_CLONED": "red_herring", "INT_C_TRAVEL": "red_herring", "EMAIL_CHEN_TRAVEL": "red_herring",
    "INT_MB_EXPLAINS": "red_herring", "INT_MB_ALIBI": "red_herring", "INT_C_NO_ACCESS": "red_herring",
    "INT_R_ALIBI": "red_herring",
    "INT_H1_HOME_CLAIM": "key", "INT_H1_NO_OFFICE": "key", "INT_H2_ALONE": "key", "INT_H2_AT_DESK": "key",
    "INT_H2_BADGE_COAT": "key", "INT_S_ALIBI_CLAIM": "key", "INT_S_DENIES_SAT": "key", "INT_S_BUSINESS_ONLY": "key",
    "INT_S_DEPARTURE": "key", "INT_S_DECLINES_DNA": "key", "INT_S_ADDRESS": "key", "INT_S_MESSAGES": "key",
    "STMT_O_SIGHTING": "key", "STMT_O_BAG": "key", "STMT_W_1007_TOUR": "key", "STMT_W_TWO_UNITS": "key",
    "STMT_W_CLEANING": "key", "STMT_W_BADGE_HABIT": "key", "STMT_E_CAMERA": "key", "STMT_E_BRIEFING": "key",
    "STMT_E_DINNERS": "key", "STMT_EH_TIMES": "key", "SUB_0147_COMPANY": "key", "SUB_0147_USER": "key",
    "EXTRACT_DELETION": "key", "EMAIL_ELLIS_REQUEST": "key", "EMAIL_INV_ALERT": "key", "EMAIL_H_2255": "key",
    "STMT_B_PIN_FAIL": "key", "FNOL_COVERAGE_Q": "key", "EXTRACT_NO_SHEN_DEVICE": "key",
}


def _doc(out: Out, reg: Registry, eid: str, text: str, numbered: bool = False, file_rel: str = "supporting"):
    before = set(reg.keys)
    out.text(path_of(eid), render_marked_text(text, eid, reg, numbered=numbered))
    for tag in sorted(set(reg.keys) - before, key=lambda t: int(reg.keys[t]["locator"].split("=")[1])):
        reg.rec(eid, reg.keys[tag]["locator"], REL.get(tag, "supporting"), "", [tag])
    reg.rec(eid, "file", file_rel)


def header(kind: str, lines: list[str]) -> str:
    return "\n".join([BANNER, "SOUTH BAY REGIONAL POLICE DEPARTMENT", kind, ""] + lines + [""])
