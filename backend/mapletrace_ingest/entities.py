"""Identifier normalization (people, phone numbers, emails, devices).

Deterministic and conservative on purpose: the ingestion stage only merges
identities when there is explicit evidence (a contacts entry, an email
"Name <address>" header). Fuzzy matching is left to later stages, which can
cite the links recorded here.
"""

from __future__ import annotations

import re
from email.utils import getaddresses

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<![\w])(?:\+?\d[\d\s().\-]{6,}\d)(?![\w])")
_TITLES = {"det", "detective", "officer", "ofc", "sgt", "sergeant", "lt", "mr", "mrs", "ms", "miss", "dr", "prof", "insp", "inspector", "agent", "pc"}


def normalize_phone(raw: str, default_country_code: str = "1") -> str | None:
    s = str(raw).strip()
    plus = s.startswith("+")
    digits = re.sub(r"\D", "", s)
    if len(digits) < 7 or len(digits) > 15:
        return None
    if plus:
        return "+" + digits
    if default_country_code and len(digits) == 10:
        return "+" + default_country_code + digits
    if default_country_code and len(digits) == 11 and digits.startswith(default_country_code):
        return "+" + digits
    return digits


def normalize_email(raw: str) -> str | None:
    m = EMAIL_RE.search(str(raw))
    return m.group(0).lower() if m else None


# Words that mark a value as a place, thing or organisation rather than a person.
_NOT_PERSON = {
    "camera", "cam", "door", "doors", "reader", "checkpoint", "corridor", "floor", "room", "lobby", "garage", "cabinet",
    "server", "system", "systems", "office", "building", "gate", "elevator", "dock", "lab", "laboratory", "inc",
    "llc", "ltd", "corp", "company", "co", "security", "services", "service", "department", "dept", "team", "group",
    "desk", "store", "shop", "station", "notifications", "promo", "delivery", "bank", "hotel", "airport", "street",
    "parkway", "avenue", "road", "entrance", "exit", "interior", "exterior", "zone", "sensor", "unit", "vehicle",
    "printer", "workstation", "laptop", "device", "network", "admin", "support", "noreply", "alerts", "carrier",
    "inventory", "audit", "log", "report", "sso", "alert", "controller", "kiosk", "portal", "app", "bot", "edr",
    "outlook", "microsoft", "windows", "defender", "chrome", "teams", "zoom", "slack", "update", "client", "kernel",
    "auditing", "antivirus", "firewall", "backup", "scheduler", "daemon", "auto", "automatic", "system",
}


def looks_like_person(name: str) -> bool:
    s = re.sub(r"\s*\(.*?\)", "", str(name)).strip()
    if not s or re.search(r"\d|[@_\\/]", s):
        return False
    tokens = [t for t in re.split(r"[^\w']+", s.lower()) if t]
    if not tokens or len(tokens) > 5 or any(t in _NOT_PERSON for t in tokens):
        return False
    if any(re.search(r"[a-z][A-Z]", t) for t in s.split()):  # "AurionEDR", "WindowsUpdate"
        return False
    if any("-" in t and t.isupper() for t in s.split()):  # "AURION-SSO"
        return False
    return True


def person_key(name: str) -> str | None:
    name = re.sub(r"\s*\(.*?\)", "", str(name)).strip()  # "DELGADO, RAY (AEGIS)" -> "DELGADO, RAY"
    parts = [p.strip() for p in name.split(",")]
    if len(parts) == 2 and len(parts[0].split()) == 1 and 1 <= len(parts[1].split()) <= 2 \
            and all(re.fullmatch(r"[A-Za-z][A-Za-z.'\-]*(?: [A-Za-z.'\-]+)?", p) for p in parts):
        name = f"{parts[1]} {parts[0]}"  # "LAST, FIRST" -> "FIRST LAST"
    tokens = [t for t in re.split(r"[^\w']+", name.lower()) if t]
    tokens = [t for t in tokens if t not in _TITLES]
    if not tokens or not any(c.isalpha() for c in "".join(tokens)):
        return None
    return " ".join(tokens)


def clean_display(name: str) -> str:
    return re.sub(r"\s+", " ", str(name)).strip().strip("\"'")


def classify_identifier(raw, default_cc: str = "1") -> tuple[str, str, str] | None:
    """Return (entity_type, normalized_value, display) for a sender/recipient-style field."""
    if raw is None:
        return None
    s = clean_display(raw)
    if not s or s.lower() in {"unknown", "n/a", "none", "null", "me", "self"}:
        return None
    email = normalize_email(s) if "@" in s else None
    if email:
        return "email", email, s
    if re.fullmatch(r"[+\d\s().\-]{7,}", s):
        phone = normalize_phone(s, default_cc)
        if phone:
            return "phone", phone, s
    key = person_key(s)
    if key and len(key) <= 60 and len(key.split()) <= 6:
        if looks_like_person(s):
            return "person", key, s
        return "account", re.sub(r"\s+", " ", s.lower()), s  # a named thing: camera, system, company, ...
    return None


def split_people_field(raw: str) -> list[str]:
    """Split 'a@x.com; Bob <b@y.com>' or 'Alice, Bob' into individual identifiers."""
    s = str(raw)
    if "@" in s:
        return [f"{n} <{a}>" if n else a for n, a in getaddresses([s]) if a]
    parts = re.split(r"\s*[;|]\s*", s)
    return [p for p in parts if p.strip()]


def parse_named_address(raw: str) -> tuple[str | None, str | None]:
    pairs = getaddresses([raw])
    if not pairs:
        return None, None
    name, addr = pairs[0]
    return (clean_display(name) or None), (addr.lower() or None)
