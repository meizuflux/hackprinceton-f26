"""Shared helpers for the log writers: facility tables, roster noise, event constructors."""
from __future__ import annotations

from datetime import timedelta

from ..cast import PEOPLE as P
from ..common import lt, rng

FIRST = ["Aaron", "Abigail", "Adebayo", "Aiko", "Alejandro", "Amara", "Amir", "Ana", "Anders", "Arjun", "Beatriz",
         "Ben", "Bianca", "Carlos", "Chiara", "Chloe", "Daniel", "Deepa", "Diego", "Elena", "Emeka", "Emily", "Ethan",
         "Fatima", "Felix", "Grace", "Hannah", "Hiro", "Ines", "Isaac", "Jae", "James", "Jasmine", "Javier", "Jin",
         "Julia", "Kai", "Kavya", "Kenji", "Kofi", "Laila", "Leo", "Lin", "Lucas", "Maya", "Mei", "Mohammed",
         "Nadia", "Naveen", "Nina", "Noah", "Olivia", "Omar", "Paulo", "Rafael", "Rahul", "Rosa", "Ryan", "Sana",
         "Sebastian", "Sofia", "Sun", "Tariq", "Theo", "Uma", "Valeria", "Wei", "Yara", "Yusuf", "Zoe"]
LAST = ["Adams", "Agarwal", "Alvarez", "Andersen", "Baker", "Banerjee", "Becker", "Bose", "Brooks", "Campbell",
        "Castillo", "Cohen", "Costa", "Das", "Diaz", "Dubois", "Edwards", "Fischer", "Flores", "Fujita", "Garcia",
        "Gupta", "Hall", "Hansen", "Hassan", "Hughes", "Ibrahim", "Ito", "Johnson", "Kapoor", "Kim", "Kowalski",
        "Kumar", "Larsen", "Lee", "Lopez", "Mahmoud", "Martin", "Mehta", "Moreno", "Nakamura", "Nguyen", "Novak",
        "Nwosu", "Ortiz", "Patel", "Perez", "Petrov", "Quinn", "Rao", "Rossi", "Sanchez", "Sato", "Schmidt", "Silva",
        "Singh", "Suzuki", "Tan", "Taylor", "Thompson", "Torres", "Tran", "Wagner", "Walker", "Wang", "Weber",
        "Williams", "Wong", "Yamamoto", "Young", "Zhang", "Zhou"]

READERS = [
    ("E-L1-LOBBY-N", "Lobby north entrance", "L1", "Lobby", "perimeter", ""),
    ("E-L1-DOCK", "Loading dock door", "L1", "Dock", "perimeter", ""),
    ("E-P2-ELEV", "P2 garage elevator lobby door", "P2", "P2 elevator lobby", "perimeter",
     "Door-held alarm threshold 15 s"),
    ("E-P2-SVC", "P2 service corridor door", "P2", "Service corridor", "perimeter", "Custodial and deliveries"),
    ("E-2-EAST", "Floor 2 east office door", "2", "2 East", "interior", ""),
    ("E-2-LAB-A", "Lab 2A hardware validation", "2", "Lab 2A", "restricted",
     "Reader clock drift +00:02:47 observed 2026-10-12, ticket FAC-2210 open (logged times are late)"),
    ("E-3-EAST", "Floor 3 east office door", "3", "3 East", "interior", ""),
    ("E-3-WEST", "Floor 3 west office door", "3", "3 West", "interior", ""),
    ("E-4-SUITE", "Executive suite entrance (offices 4-01 to 4-06)", "4", "Executive suite", "restricted",
     "Office 4-01 (CEO) is inside the suite"),
    ("E-4-12-EBC", "Executive Briefing Center, room 4-12", "4", "EBC 4-12", "restricted",
     "Houses secure cabinet SC-EBC-01; about 40 m from office 4-01"),
]
OTHER_DEVICES = [
    ("CAM-E-L1-01", "camera", "Lobby camera facing north entrance", "L1", "Lobby", "", ""),
    ("CAM-E-P2-02", "camera", "Garage P2 camera covering elevator lobby door, service door and rows B-C", "P2",
     "Garage P2", "", "Low light; faces not resolvable at distance"),
    ("CAM-E-F4-01", "camera", "Floor 4 corridor camera (suite entrance to EBC)", "4", "Corridor 4", "",
     "Offline 2026-10-17 21:00-23:30 under change CHG-4471 (NVR firmware)"),
    ("CAM-E-F4-02", "camera", "EBC interior camera", "4", "EBC 4-12", "",
     "Offline 2026-10-17 21:00-23:30 under change CHG-4471; footage retention 30 days"),
    ("SC-EBC-01", "cabinet", "Secure demo cabinet with keypad and badge reader", "4", "EBC 4-12", "",
     "Dual authorization for removal; executive override allows single badge + executive PIN"),
    ("RF-SC-EBC-01", "rfid_reader", "Cabinet RFID inventory reader (hourly scans)", "4", "EBC 4-12", "",
     "Alerts after 2 consecutive absences of an item not checked out; alerts mail secops-alerts (weekday monitoring)"),
    ("AUR-EXEC-0001", "workstation", "CEO desktop workstation (Windows Hello face sign-in)", "4", "Office 4-01", "",
     "Wired; no remote-desktop access enabled"),
    ("ELEV-E-1..4", "elevator", "Passenger elevators P2-L1-2-3-4", "all", "Core", "",
     "Not on access control after hours; car call and door logs kept by LiftCore controller, retained 30 days, not exported"),
    ("AP-E4-01..06", "wifi_ap", "Floor 4 Wi-Fi access points (corp and guest SSIDs)", "4", "Floor 4", "",
     "WLAN controller association logs retained 14 days, not exported"),
    ("E-4-CP1", "guard_checkpoint", "Guard checkpoint, floor 4 corridor", "4", "Corridor 4", "", ""),
    ("E-4-CP2", "guard_checkpoint", "Guard checkpoint, EBC exterior door", "4", "Corridor 4", "", ""),
]

LAB_SKEW = timedelta(seconds=167)
CAST_HOLDER = {
    "halvorsen": "HALVORSEN, RICHARD", "whitfield": "WHITFIELD, DANA", "raman": "RAMAN, PRIYA",
    "chen": "CHEN, ANDREW", "brandt": "BRANDT, TOM", "ellis": "ELLIS, JORDAN",
    "ortega": "ORTEGA, LUIS (BRIGHTPATH)", "bellini": "BELLINI, MARCO", "delgado": "DELGADO, RAY (AEGIS)",
}


def _plate(r) -> str:
    letters = "ABCDEFGHJKLMNPRSTUVWXYZ"
    return f"{r.randint(5, 9)}{''.join(r.choice(letters) for _ in range(3))}{r.randint(100, 999)}"


def roster():
    r = rng("roster")
    used, out = set(), []
    for i in range(110):
        while True:
            f, l = r.choice(FIRST), r.choice(LAST)
            if (f, l) not in used:
                used.add((f, l))
                break
        floor = r.choice(["2", "3"])
        door = "E-2-EAST" if floor == "2" else r.choice(["E-3-EAST", "E-3-WEST"])
        car = r.random() < 0.7
        out.append(dict(name=f"{f} {l}", holder=f"{l.upper()}, {f.upper()}", badge=f"BID-{210000 + i * 11}",
                        door=door, lab=(floor == "2" and r.random() < 0.25), car=car,
                        plate=_plate(r) if car else None, color=r.choice(
                            ["white sedan", "black SUV", "silver sedan", "blue hatchback", "gray SUV", "red sedan",
                             "white SUV", "black sedan", "green hatchback"])))
    return out


class _Ev:
    __slots__ = ("t", "reader", "badge", "holder", "etype", "result", "detail", "rel", "tags", "noise", "note")

    def __init__(self, t, reader, badge="", holder="", etype="ACCESS_GRANTED", result="GRANTED", detail="",
                 rel="background", tags=(), note=""):
        self.t, self.reader, self.badge, self.holder = t, reader, badge, holder
        self.etype, self.result, self.detail = etype, result, detail
        self.rel, self.tags, self.noise, self.note = rel, list(tags), "", note


def _g(t, reader, who, rel="supporting", tags=(), note=""):
    return _Ev(lt(t), reader, P[who]["badge"], CAST_HOLDER[who], rel=rel, tags=tags, note=note)


def _rex(t, reader, rel="background", tags=(), note=""):
    return _Ev(lt(t), reader, etype="REX_EGRESS", result="", rel=rel, tags=tags, note=note)


def _lpr(t, lane, plate, desc, rel="background", tags=(), note=""):
    return dict(t=lt(t), lane=lane, plate=plate, desc=desc, rel=rel, tags=list(tags), noise="", note=note, conf=None)
