"""Machine logs: badge access, garage LPR, cabinet audit, RFID inventory, visitors, guard tours,
workstation events, CEO calendar, and facility reference tables."""
from __future__ import annotations

from datetime import timedelta

from .cast import ITEMS, MEETINGS, PEOPLE as P, T
from .catalog import path_of
from .common import PDT, UTC, Out, Registry, epoch_ms, iso_local, local_str, lt, rng

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


def workforce(reg: Registry):
    """Badge events and garage LPR reads for 2026-10-16 00:00 to 2026-10-19 12:00."""
    r = rng("workforce")
    ev: list[_Ev] = []
    lpr: list[dict] = []

    def emp_day(e, day: str, until_noon: bool):
        arrive = lt(f"{day} 07:30") + timedelta(minutes=r.randint(0, 150), seconds=r.randint(0, 59))
        if e["car"]:
            lpr.append(dict(t=arrive - timedelta(seconds=r.randint(60, 170)), lane="ENTRY", plate=e["plate"],
                            desc=e["color"], rel="background", tags=[], noise="", note="", conf=None))
            ev.append(_Ev(arrive, "E-P2-ELEV", e["badge"], e["holder"]))
        else:
            ev.append(_Ev(arrive, "E-L1-LOBBY-N", e["badge"], e["holder"]))
        t = arrive + timedelta(minutes=r.randint(1, 4), seconds=r.randint(0, 59))
        ev.append(_Ev(t, e["door"], e["badge"], e["holder"]))
        end = lt(f"{day} 12:00") if until_noon else lt(f"{day} 16:30") + timedelta(minutes=r.randint(0, 180))
        for _ in range(r.randint(1, 3)):
            tt = t + timedelta(minutes=r.randint(20, 400), seconds=r.randint(0, 59))
            if tt < end:
                ev.append(_Ev(tt, e["lab"] and r.random() < 0.5 and "E-2-LAB-A" or e["door"], e["badge"], e["holder"]))
        if r.random() < 0.5:
            out_t = lt(f"{day} 11:45") + timedelta(minutes=r.randint(0, 60), seconds=r.randint(0, 59))
            if out_t < end:
                ev.append(_Ev(out_t, "E-L1-LOBBY-N", etype="REX_EGRESS", result=""))
                back = out_t + timedelta(minutes=r.randint(30, 60))
                if back < end:
                    ev.append(_Ev(back, "E-L1-LOBBY-N", e["badge"], e["holder"]))
        if r.random() < 0.04 and not e["lab"]:
            tt = t + timedelta(minutes=r.randint(30, 200))
            if tt < end:
                ev.append(_Ev(tt, "E-2-LAB-A", e["badge"], e["holder"], etype="ACCESS_DENIED", result="DENIED",
                              detail="NOT_IN_ACCESS_GROUP"))
        if not until_noon:
            ex = "E-P2-ELEV" if e["car"] else "E-L1-LOBBY-N"
            ev.append(_Ev(end, ex, etype="REX_EGRESS", result=""))
            if e["car"]:
                lpr.append(dict(t=end + timedelta(seconds=r.randint(100, 300)), lane="EXIT", plate=e["plate"],
                                desc=e["color"], rel="background", tags=[], noise="", note="", conf=None))

    staff = roster()
    for e in staff:
        if r.random() < 0.85:
            emp_day(e, "2026-10-16", until_noon=False)
        if r.random() < 0.85:
            emp_day(e, "2026-10-19", until_noon=True)
    # Two employees drop in on Sunday afternoon (background).
    for e in staff[3:5]:
        tin = lt("2026-10-18 13:10") + timedelta(minutes=r.randint(0, 40))
        ev.append(_Ev(tin, "E-L1-LOBBY-N", e["badge"], e["holder"]))
        ev.append(_Ev(tin + timedelta(minutes=3), e["door"], e["badge"], e["holder"]))
        ev.append(_Ev(tin + timedelta(minutes=r.randint(60, 120)), "E-L1-LOBBY-N", etype="REX_EGRESS", result=""))
    # Benign door-held alarms and unknown cards (background noise for anomaly models).
    for t, rd, d in [("2026-10-16 10:15:22", "E-L1-DOCK", "held 48s (threshold 15s)"),
                     ("2026-10-16 12:05:40", "E-L1-LOBBY-N", "held 22s (threshold 15s)"),
                     ("2026-10-16 14:40:05", "E-L1-DOCK", "held 95s (threshold 15s)"),
                     ("2026-10-19 09:20:11", "E-L1-DOCK", "held 61s (threshold 15s)")]:
        ev.append(_Ev(lt(t), rd, etype="DOOR_HELD_OPEN", result="", detail=d))
    for t in ["2026-10-16 06:12:09", "2026-10-19 06:48:30"]:
        ev.append(_Ev(lt(t), "E-L1-DOCK", "BID-UNKNOWN", "", etype="ACCESS_DENIED", result="DENIED",
                      detail="CARD_NOT_IN_SYSTEM"))

    # ---- scripted cast activity ----
    S = []
    # Friday 10-16
    S += [_g("2026-10-16 07:41:20", "E-P2-ELEV", "whitfield", "context"),
          _g("2026-10-16 07:52:10", "E-4-12-EBC", "whitfield", "context"),
          _g("2026-10-16 08:02:30", "E-L1-LOBBY-N", "ellis", "context"),
          _g("2026-10-16 08:04:10", "E-4-SUITE", "ellis", "context"),
          _g("2026-10-16 08:12:40", "E-P2-ELEV", "halvorsen", "context"),
          _g("2026-10-16 08:15:02", "E-4-SUITE", "halvorsen", "context"),
          _g("2026-10-16 08:40:31", "E-P2-ELEV", "brandt", "context"),
          _g("2026-10-16 08:49:02", "E-P2-ELEV", "raman", "context"),
          _g("2026-10-16 08:51:15", "E-2-EAST", "raman", "context"),
          _g("2026-10-16 09:30:40", "E-2-LAB-A", "raman", "context"),
          _g("2026-10-16 09:44:12", "E-2-EAST", "chen", "background"),
          _g("2026-10-16 10:30:15", "E-4-12-EBC", "halvorsen", "context", note="Keynote rehearsal"),
          _g("2026-10-16 11:02:48", "E-4-SUITE", "halvorsen", "context"),
          _g("2026-10-16 13:03:50", "E-4-12-EBC", "whitfield", "supporting", ["BADGE_1016_WHITFIELD_EBC"]),
          _g("2026-10-16 13:04:02", "E-4-12-EBC", "raman", "red_herring", ["BADGE_1016_RAMAN_EBC_SIGNOUT"]),
          _g("2026-10-16 13:15:20", "E-2-LAB-A", "raman", "red_herring", ["BADGE_1016_RAMAN_LAB"]),
          _g("2026-10-16 14:31:09", "E-4-SUITE", "halvorsen", "context"),
          _g("2026-10-16 16:20:33", "E-4-12-EBC", "whitfield", "context"),
          _rex("2026-10-16 17:45:02", "E-L1-LOBBY-N"),
          _g("2026-10-16 17:55:40", "E-P2-SVC", "ortega", "context"),
          _rex("2026-10-16 18:05:40", "E-P2-ELEV"),
          _g("2026-10-16 18:20:11", "E-3-EAST", "ortega", "background"),
          _g("2026-10-16 19:11:55", "E-4-12-EBC", "raman", "supporting", ["BADGE_1016_RAMAN_EBC_DEPOSIT"]),
          _rex("2026-10-16 19:24:30", "E-P2-ELEV", "context"),
          _rex("2026-10-16 19:35:50", "E-P2-ELEV", "context"),
          _g("2026-10-16 21:05:44", "E-2-EAST", "ortega", "background"),
          _g("2026-10-16 23:40:19", "E-3-WEST", "ortega", "background"),
          _rex("2026-10-17 02:33:05", "E-P2-SVC")]
    # Saturday 10-17
    guard_times = ["2026-10-17 08:00:30", "2026-10-17 12:00:40", "2026-10-17 16:00:20", "2026-10-17 20:04:30",
                   "2026-10-18 00:09:50", "2026-10-18 04:05:10", "2026-10-18 08:00:45", "2026-10-18 12:01:10",
                   "2026-10-18 16:00:30", "2026-10-18 20:05:15", "2026-10-19 00:10:20", "2026-10-19 04:04:50"]
    for gt in guard_times:
        S.append(_g(gt, "E-L1-LOBBY-N", "delgado", "context"))
    S += [_g("2026-10-17 13:59:30", "E-P2-ELEV", "chen", "red_herring", ["BADGE_CHEN_SAT_IN"]),
          _g("2026-10-17 14:02:10", "E-2-LAB-A", "chen", "red_herring", ["BADGE_CHEN_SAT_LAB"]),
          _g("2026-10-17 15:10:00", "E-2-LAB-A", "chen", "red_herring"),
          _rex("2026-10-17 16:31:40", "E-P2-ELEV", "red_herring", ["BADGE_CHEN_SAT_OUT"], "Andrew Chen leaving (per CCTV/LPR)"),
          _g("2026-10-17 17:55:12", "E-P2-SVC", "ortega", "supporting", ["BADGE_ORTEGA_SAT_IN"]),
          _g("2026-10-17 18:10:40", "E-3-EAST", "ortega", "background"),
          _g("2026-10-17 19:40:02", "E-3-WEST", "ortega", "background"),
          _Ev(lt("2026-10-17 19:02:11"), "E-L1-LOBBY-N", P["bellini"]["badge"], CAST_HOLDER["bellini"],
              etype="ACCESS_DENIED", result="DENIED", detail="BADGE_INACTIVE (deactivated 2026-10-02)",
              rel="red_herring", tags=["BADGE_BELLINI_DENIED_1"]),
          _Ev(lt("2026-10-17 19:02:24"), "E-L1-LOBBY-N", P["bellini"]["badge"], CAST_HOLDER["bellini"],
              etype="ACCESS_DENIED", result="DENIED", detail="BADGE_INACTIVE (deactivated 2026-10-02)",
              rel="red_herring", tags=["BADGE_BELLINI_DENIED_2"]),
          _g("2026-10-17 20:30:15", "E-2-EAST", "ortega", "background"),
          _g("2026-10-17 21:15:48", "E-2-EAST", "ortega", "background"),
          _g("2026-10-17 21:36:31", "E-P2-ELEV", "halvorsen", "key", ["BADGE_H_P2_ENTRY"]),
          _Ev(lt("2026-10-17 21:36:49"), "E-P2-ELEV", etype="DOOR_HELD_OPEN", result="",
              detail="held 16s (threshold 15s)", rel="key", tags=["BADGE_P2_HELD_OPEN"]),
          _Ev(lt("2026-10-17 21:36:52"), "E-P2-ELEV", etype="DOOR_CLOSED", result="", detail="open 19s",
              rel="supporting", tags=["BADGE_P2_CLOSED"]),
          _g("2026-10-17 21:38:05", "E-4-SUITE", "halvorsen", "key", ["BADGE_H_SUITE_ENTRY"]),
          _g("2026-10-17 22:40:18", "E-3-EAST", "ortega", "supporting", ["BADGE_ORTEGA_F3_2240"]),
          _rex("2026-10-17 22:50:31", "E-4-SUITE", "key", ["BADGE_SUITE_REX_2250"]),
          _g("2026-10-17 22:50:47", "E-4-12-EBC", "halvorsen", "key", ["BADGE_EBC_H_BADGE_2250"],
             note="Badge BID-100001 used; holder was at workstation per EV-075"),
          _rex("2026-10-17 22:52:40", "E-4-12-EBC", "key", ["BADGE_EBC_REX_2252"]),
          _g("2026-10-17 22:53:09", "E-4-SUITE", "halvorsen", "key", ["BADGE_SUITE_H_BADGE_2253"],
             note="Suite entry with BID-100001 while holder already inside suite"),
          _rex("2026-10-17 23:01:50", "E-4-SUITE", "supporting", ["BADGE_SUITE_REX_2301"]),
          _rex("2026-10-17 23:02:15", "E-P2-SVC", "supporting", ["BADGE_SVC_REX_2302"], "Luis Ortega to P2 (per CCTV)"),
          _rex("2026-10-17 23:03:40", "E-P2-ELEV", "key", ["BADGE_P2_REX_2303"]),
          _g("2026-10-17 23:06:05", "E-P2-SVC", "ortega", "supporting", ["BADGE_ORTEGA_P2_REENTRY"]),
          _g("2026-10-18 00:31:22", "E-3-WEST", "ortega", "background"),
          _rex("2026-10-18 02:38:10", "E-P2-SVC", "supporting", ["BADGE_ORTEGA_SUN_OUT"])]
    # Monday 10-19 (discovery morning)
    S += [_g("2026-10-19 07:31:05", "E-P2-ELEV", "whitfield", "supporting", ["BADGE_WHITFIELD_MON_IN"]),
          _g("2026-10-19 07:38:40", "E-4-12-EBC", "whitfield", "supporting", ["BADGE_WHITFIELD_MON_EBC"]),
          _g("2026-10-19 08:20:15", "E-L1-LOBBY-N", "ellis", "context"),
          _g("2026-10-19 08:22:40", "E-4-SUITE", "ellis", "context"),
          _g("2026-10-19 08:35:02", "E-P2-ELEV", "halvorsen", "context"),
          _g("2026-10-19 08:37:20", "E-4-SUITE", "halvorsen", "context"),
          _g("2026-10-19 08:41:12", "E-P2-ELEV", "brandt", "supporting"),
          _g("2026-10-19 08:52:30", "E-4-12-EBC", "brandt", "supporting", ["BADGE_BRANDT_MON_EBC"]),
          _g("2026-10-19 09:05:09", "E-P2-ELEV", "raman", "context"),
          _g("2026-10-19 09:40:44", "E-P2-ELEV", "chen", "context")]
    ev += S

    # LPR scripted reads
    lpr += [_lpr("2026-10-16 07:39:50", "ENTRY", "7DWH260", "white SUV", "context"),
            _lpr("2026-10-16 08:10:55", "ENTRY", "8RHV521", "gray sedan", "context", ["LPR_H_FRI_IN"]),
            _lpr("2026-10-16 08:38:40", "ENTRY", "6TBR902", "black SUV", "context"),
            _lpr("2026-10-16 08:47:30", "ENTRY", "7PRM334", "blue hatchback", "context"),
            _lpr("2026-10-16 09:41:02", "ENTRY", "9ACH118", "silver sedan", "background"),
            _lpr("2026-10-16 17:52:20", "ENTRY", "8LOR441", "white van", "context"),
            _lpr("2026-10-16 18:09:00", "EXIT", "7DWH260", "white SUV", "context"),
            _lpr("2026-10-16 18:31:45", "EXIT", "6TBR902", "black SUV", "context"),
            _lpr("2026-10-16 18:58:12", "EXIT", "9ACH118", "silver sedan", "background"),
            _lpr("2026-10-16 19:28:10", "EXIT", "7PRM334", "blue hatchback", "red_herring", ["LPR_RAMAN_FRI_OUT"]),
            _lpr("2026-10-16 19:39:20", "EXIT", "8RHV521", "gray sedan", "context"),
            _lpr("2026-10-17 02:36:40", "EXIT", "8LOR441", "white van", "background"),
            _lpr("2026-10-17 13:58:05", "ENTRY", "9ACH118", "silver sedan", "red_herring", ["LPR_CHEN_SAT_IN"]),
            _lpr("2026-10-17 16:35:12", "EXIT", "9ACH118", "silver sedan", "red_herring", ["LPR_CHEN_SAT_OUT"]),
            _lpr("2026-10-17 17:52:31", "ENTRY", "8LOR441", "white van", "supporting", ["LPR_ORTEGA_SAT_IN"]),
            _lpr("2026-10-17 21:35:48", "ENTRY", "8RHV521", "gray sedan", "key", ["LPR_H_IN_2135"]),
            _lpr("2026-10-17 23:07:31", "EXIT", "8RHV521", "gray sedan", "key", ["LPR_H_OUT_2307"]),
            _lpr("2026-10-18 02:41:30", "EXIT", "8LOR441", "white van", "supporting", ["LPR_ORTEGA_SUN_OUT"]),
            _lpr("2026-10-19 07:29:40", "ENTRY", "7DWH260", "white SUV", "supporting"),
            _lpr("2026-10-19 08:33:10", "ENTRY", "8RHV521", "gray sedan", "context"),
            _lpr("2026-10-19 08:39:30", "ENTRY", "6TBR902", "black SUV", "supporting"),
            _lpr("2026-10-19 09:03:20", "ENTRY", "7PRM334", "blue hatchback", "context"),
            _lpr("2026-10-19 09:38:55", "ENTRY", "9ACH118", "silver sedan", "context")]
    return ev, lpr


def write_badges_and_lpr(out: Out, reg: Registry):
    r = rng("badge-noise")
    ev, lpr = workforce(reg)
    # Duplicate ~1% of untagged events (export merge artefact).
    dups = []
    for e in ev:
        if not e.tags and r.random() < 0.01:
            d = _Ev(e.t, e.reader, e.badge, e.holder, e.etype, e.result, e.detail, rel="noise")
            d.noise = "duplicate_export_row"
            dups.append(d)
    ev += dups
    rows = []
    for e in ev:
        logged = e.t + LAB_SKEW if e.reader == "E-2-LAB-A" else e.t
        if e.reader == "E-2-LAB-A" and not e.noise:
            e.noise = "clock_skew_+167s"
        rows.append((logged, e))
    rows.sort(key=lambda x: (x[0], x[1].reader, x[1].badge, x[1].etype, x[1].rel))
    eid = "EV-070"
    table = []
    for i, (logged, e) in enumerate(rows, 1):
        rid = f"BDG-{i:06d}"
        door = next(d[1] for d in READERS if d[0] == e.reader)
        table.append([rid, local_str(logged), e.reader, door, e.badge, e.holder, e.etype, e.result, e.detail])
        for t in e.tags:
            reg.key(t, eid, f"event_id={rid}", e.note)
        reg.rec(eid, f"event_id={rid}", e.rel, e.noise, e.tags, e.note)
    out.csv(path_of(eid), ["event_id", "timestamp", "reader_id", "door", "badge_id", "cardholder", "event_type",
                           "result", "detail"], table)

    # ---- LPR ----
    rl = rng("lpr-noise")
    reads = []
    swaps = {"8": "B", "B": "8", "1": "I", "0": "O", "5": "S", "2": "Z"}
    for x in lpr:
        x["conf"] = round(rl.uniform(0.91, 0.995), 3)
        reads.append(x)
        if not x["tags"] and rl.random() < 0.02:
            mis = dict(x)
            p = list(x["plate"])
            idx = [i for i, c in enumerate(p) if c in swaps]
            if idx:
                j = rl.choice(idx)
                p[j] = swaps[p[j]]
            mis.update(plate="".join(p), conf=round(rl.uniform(0.55, 0.74), 3), rel="noise", noise="ocr_misread",
                       t=x["t"] + timedelta(seconds=1), tags=[])
            reads.append(mis)
        elif not x["tags"] and rl.random() < 0.015:
            d = dict(x)
            d.update(rel="noise", noise="double_read", t=x["t"] + timedelta(seconds=2), tags=[])
            reads.append(d)
    reads.sort(key=lambda x: (x["t"], x["lane"], x["plate"]))
    eid = "EV-064"
    table = []
    for i, x in enumerate(reads, 1):
        rid = f"LPR-{i:05d}"
        cam = "LPR-P2-IN" if x["lane"] == "ENTRY" else "LPR-P2-OUT"
        ts = x["t"].astimezone(PDT)
        us = f"{ts.month:02d}/{ts.day:02d}/{ts.year} {int(ts.strftime('%I'))}:{ts.strftime('%M:%S %p')}"
        table.append([rid, cam, x["lane"], x["plate"], x["conf"], us, x["desc"], f"lpr_{rid.lower()}.jpg"])
        for t in x["tags"]:
            reg.key(t, eid, f"read_id={rid}")
        reg.rec(eid, f"read_id={rid}", x["rel"], x["noise"], x["tags"])
    out.csv(path_of(eid), ["read_id", "camera_id", "lane", "plate_read", "confidence", "read_time",
                           "vehicle_desc", "image_ref"], table)


# ---------------------------------------------------------------- cabinet audit
def write_cabinet(out: Out, reg: Registry):
    r = rng("cabinet")
    eid = "EV-071"
    sessions = []  # (start, mode, creds, pin_fail_first, open_secs, tags, rel, note)
    engineers = ["BID-200233", "BID-200402", "BID-200517"]
    d = lt("2026-07-20 00:00")
    while d < lt("2026-10-16 00:00"):
        if d.weekday() in (1, 3) and r.random() < 0.6:
            start = d + timedelta(hours=9, minutes=30 + r.randint(0, 270), seconds=r.randint(0, 59))
            eng = r.choice(engineers)
            sessions.append((start, "DUAL", ["BID-200118", eng], False, r.randint(40, 120), [], "background", ""))
            sessions.append((start + timedelta(hours=r.randint(3, 6), minutes=r.randint(0, 59)), "DEPOSIT", [eng],
                             False, r.randint(20, 60), [], "background", ""))
        d += timedelta(days=1)
    for day in ["2026-08-03", "2026-09-01", "2026-10-01"]:
        sessions.append((lt(f"{day} 09:00:20"), "EXEC_OVERRIDE", ["BID-200118"], False, 190, [], "background",
                         "Monthly inventory"))
    sessions += [
        (lt("2026-08-12 10:05:11"), "EXEC_OVERRIDE", ["BID-100001"], False, 420, [], "context", "Board demo"),
        (lt("2026-09-22 14:10:40"), "EXEC_OVERRIDE", ["BID-100001"], False, 300, [], "context", "Customer demo"),
        (lt("2026-10-07 15:08:22"), "EXEC_OVERRIDE", ["BID-100001"], False, 260, ["CAB_1007_EXEC_OPEN"], "key",
         "During partner briefing / EBC walkthrough for V. Shen"),
        (lt("2026-10-16 13:05:10"), "DUAL", ["BID-200118", "BID-200233"], False, 75, ["CAB_1016_SIGNOUT"],
         "red_herring", "ES-0007 signed out for thermal validation"),
        (lt("2026-10-16 19:12:40"), "DEPOSIT", ["BID-200233"], False, 35, ["CAB_1016_DEPOSIT"], "supporting",
         "ES-0007 returned"),
        (lt("2026-10-17 22:51:14"), "EXEC_OVERRIDE", ["BID-100001"], True, 47, ["CAB_1017_EXEC_OPEN"], "key",
         "Theft opening"),
        (lt("2026-10-19 10:41:05"), "EXEC_OVERRIDE", ["BID-200118"], False, 900, ["CAB_1019_CSU_OPEN"], "supporting",
         "Opened for CSU after swabbing"),
    ]
    sessions.sort(key=lambda s: s[0])
    rows, seq = [], 40000
    for start, mode, creds, pin_fail, open_secs, tags, rel, note in sessions:
        evs = []
        if pin_fail:
            evs.append((start - timedelta(seconds=12), "AUTH_ATTEMPT", {"pin_result": "FAIL", "mode": mode,
                                                                         "credentials": creds}))
        evs.append((start, "AUTH_ATTEMPT", {"pin_result": "OK", "mode": mode, "credentials": creds}))
        evs.append((start + timedelta(seconds=1), "UNLOCK", {}))
        opened = start + timedelta(seconds=2)
        evs.append((opened, "DOOR_OPEN", {}))
        evs.append((opened + timedelta(seconds=open_secs), "DOOR_CLOSE", {}))
        evs.append((opened + timedelta(seconds=open_secs + 1), "LOCK", {}))
        for i, (t, kind, extra) in enumerate(evs):
            seq += 1
            row = {"seq": seq, "ts_epoch_ms": epoch_ms(t), "cabinet_id": "SC-EBC-01", "event": kind}
            row.update(extra)
            row["fw"] = "3.2.1"
            rows.append(row)
            loc = f"seq={seq}"
            my_tags = []
            if tags:
                base = tags[0]
                if kind == "AUTH_ATTEMPT" and extra.get("pin_result") == "FAIL":
                    my_tags = [base.replace("_EXEC_OPEN", "_PIN_FAIL")]
                elif kind == "AUTH_ATTEMPT":
                    my_tags = [base]
                elif kind == "DOOR_OPEN" and base == "CAB_1017_EXEC_OPEN":
                    my_tags = ["CAB_1017_DOOR_OPEN"]
                elif kind == "DOOR_CLOSE" and base == "CAB_1017_EXEC_OPEN":
                    my_tags = ["CAB_1017_DOOR_CLOSE"]
            for t_ in my_tags:
                reg.key(t_, eid, loc, note)
            reg.rec(eid, loc, rel, "", my_tags, note if i == 0 else "")
    out.jsonl(path_of(eid), rows)


# ---------------------------------------------------------------- RFID inventory
def write_rfid(out: Out, reg: Registry):
    r = rng("rfid")
    eid = "EV-072"
    rows = []
    t = lt("2026-10-16 00:00")
    end = lt("2026-10-19 11:00")
    n = 0
    absent_run = {k: 0 for k in ITEMS}
    while t <= end:
        for tag, desc in ITEMS.items():
            n += 1
            sid = f"RF-{n:05d}"
            status, custody, alert, rel, noise, tags = "PRESENT", "IN_CABINET", "", "background", "", []
            if tag == "ES-0007":
                rel = "context"
                if lt("2026-10-16 13:05:10") <= t < lt("2026-10-16 19:12:40"):
                    status, custody = "ABSENT", "CHECKED_OUT"
                elif t >= lt("2026-10-17 23:00"):
                    status, rel = "ABSENT", "key"
                if t == lt("2026-10-16 20:00"):
                    tags, rel = ["RFID_1016_2000_PRESENT"], "supporting"
                if t == lt("2026-10-17 22:00"):
                    tags, rel = ["RFID_1017_2200_PRESENT"], "key"
                if t == lt("2026-10-17 23:00"):
                    tags = ["RFID_1017_2300_ABSENT"]
            if (tag, t) in {("ES-0003", lt("2026-10-17 03:00")), ("DS-0019", lt("2026-10-18 14:00"))}:
                status, rel, noise = "ABSENT", "noise", "rf_missed_read"
            if status == "ABSENT" and custody == "IN_CABINET":
                absent_run[tag] += 1
            else:
                absent_run[tag] = 0
            if absent_run[tag] == 2:
                alert = "INV-ALERT-2210"
                if tag == "ES-0007":
                    tags = tags + ["RFID_1018_0000_ALERT"]
            rssi = "" if status == "ABSENT" else round(r.uniform(-58, -41), 1)
            rows.append([sid, iso_local(t), "RF-SC-EBC-01", tag, desc, status, custody, rssi, alert])
            for tg in tags:
                reg.key(tg, eid, f"scan_id={sid}")
            reg.rec(eid, f"scan_id={sid}", rel, noise, tags)
        t += timedelta(hours=1)
    out.csv(path_of(eid), ["scan_id", "scan_time", "reader_id", "tag_id", "item", "status", "custody_state",
                           "rssi_dbm", "alert"], rows)


# ---------------------------------------------------------------- visitors
def write_visitors(out: Out, reg: Registry):
    r = rng("visitors")
    eid = "EV-073"
    companies = ["Halcyon Capital", "Brightwater Ventures", "Northgate Cloud", "Tessellate Labs",
                 "Ridgeline Semiconductor Test", "Orbis Packaging GmbH", "Kaori Precision", "Lumen Datacenters",
                 "Vantage Recruiting", "Stellar Substrates Pte Ltd", "Pearl River Substrate Co.", "Cobalt Thermal Inc.",
                 "Polaris Power Systems", "Atlas Logistics", "Quartz Leaf AI", "Fernhill Audit Partners"]
    purposes = ["Supplier quality review", "Interview", "Investor meeting", "Customer briefing", "Vendor demo",
                "Audit fieldwork", "Partner meeting", "Facilities contractor", "Legal meeting"]
    hosts = ["Richard Halvorsen", "Dana Whitfield", "Priya Raman", "Andrew Chen", "Tom Brandt", "Jordan Ellis"]
    countries = ["US", "US", "US", "US", "US", "IN", "DE", "TW", "KR", "JP", "CN", "GB", "CA", "IL", "SG", "FR",
                 "HK", "MX", "BR"]
    rows = []
    d = lt("2026-10-01 00:00")
    n = 0
    while d <= lt("2026-10-19 00:00"):
        if d.weekday() < 5:
            for _ in range(r.randint(1, 4)):
                n += 1
                tin = d + timedelta(hours=8, minutes=r.randint(30, 480))
                tout = tin + timedelta(minutes=r.randint(30, 180))
                name = f"{r.choice(FIRST)} {r.choice(LAST)}"
                c = r.choice(countries)
                rows.append(dict(t=tin, row=[None, local_str(tin, "%Y-%m-%d"), local_str(tin, "%H:%M"),
                                             local_str(tout, "%H:%M"), name, r.choice(companies), r.choice(hosts),
                                             r.choice(purposes), "E", "Passport" if c != "US" else
                                             r.choice(["Driver license", "Passport"]), c, f"V-{r.randint(100, 999)}",
                                             "Y", None, r.choice(["Y", "Y", "N"])], tags=[], rel="background"))
        d += timedelta(days=1)
    shen = dict(t=lt("2026-10-07 14:21"),
                row=[None, "2026-10-07", "14:21", "16:05", "Vivian Shen", "Pacific Harbor Advisory LLC",
                     "Richard Halvorsen", "Partner briefing + EBC walkthrough", "E", "Passport", "HK", "V-442", "Y",
                     None, "Y"], tags=["VISITOR_SHEN_1007"], rel="key")
    rows.append(shen)
    rows.sort(key=lambda x: x["t"])
    table = []
    for i, x in enumerate(rows, 1):
        vid = f"VIS-{x['t'].strftime('%m%d')}-{i:04d}"
        x["row"][0] = vid
        x["row"][13] = f"{vid}.jpg"
        table.append(x["row"])
        for t in x["tags"]:
            reg.key(t, eid, f"visit_id={vid}")
        reg.rec(eid, f"visit_id={vid}", x["rel"], "", x["tags"],
                "id_issuing_country is a protected attribute; exclude from inference features")
    out.csv(path_of(eid), ["visit_id", "date", "sign_in", "sign_out", "visitor_name", "company", "host", "purpose",
                           "building", "id_type", "id_issuing_country", "visitor_badge", "escort_required",
                           "photo_ref", "nda_signed"], table)


# ---------------------------------------------------------------- guard tours
def write_guard(out: Out, reg: Registry):
    r = rng("guard")
    eid = "EV-074"
    cps = [("E-L1-CP1", "Lobby", 0), ("E-P2-CP1", "Garage P2", 4), ("E-2-CP1", "Floor 2 corridor", 9),
           ("E-3-CP1", "Floor 3 corridor", 13), ("E-4-CP1", "Floor 4 corridor", 19), ("E-4-CP2", "EBC exterior door", 21)]
    tours = ["2026-10-17 08:00", "2026-10-17 12:00", "2026-10-17 16:00", "2026-10-17 20:05", "2026-10-18 00:10",
             "2026-10-18 04:05", "2026-10-18 08:00", "2026-10-18 12:01", "2026-10-18 16:00", "2026-10-18 20:05",
             "2026-10-19 00:10", "2026-10-19 04:05"]
    p2_note = {"2026-10-17 08:00": "0 vehicles", "2026-10-17 12:00": "0 vehicles",
               "2026-10-17 16:00": "1 vehicle (9ACH118)", "2026-10-17 20:05": "1 vehicle (contractor van 8LOR441)",
               "2026-10-18 00:10": "1 vehicle (contractor van 8LOR441)"}
    rows, n = [], 0
    for tour in tours:
        base = lt(tour)
        for cp, name, off in cps:
            n += 1
            t = base + timedelta(minutes=off, seconds=r.randint(0, 50))
            note = "All secure"
            if cp == "E-P2-CP1":
                note = p2_note.get(tour, "0 vehicles")
            rid = f"GT-{n:04d}"
            rows.append([rid, local_str(t), "DELGADO, RAY (AEGIS)", cp, name, note])
            tags, rel = [], "background"
            if tour == "2026-10-17 20:05" and cp == "E-4-CP2":
                tags, rel = ["GUARD_2005_EBC"], "supporting"
            if tour == "2026-10-18 00:10" and cp == "E-4-CP2":
                tags, rel = ["GUARD_0010_EBC"], "supporting"
            if tour == "2026-10-18 00:10" and cp == "E-P2-CP1":
                tags, rel = ["GUARD_0010_P2"], "supporting"
            for tg in tags:
                reg.key(tg, eid, f"scan_id={rid}")
            reg.rec(eid, f"scan_id={rid}", rel, "", tags)
    out.csv(path_of(eid), ["scan_id", "timestamp", "officer", "checkpoint_id", "checkpoint", "officer_note"], rows)


# ---------------------------------------------------------------- workstation
def write_workstation(out: Out, reg: Registry):
    r = rng("workstation")
    eid = "EV-075"
    HELLO = "Windows Hello Face (NGC)"
    ev = []  # (t, event_id, logon_type, provider, source, message, rel, tags, noise)

    def lock(t, rel="background", tags=()):
        ev.append((lt(t), 4800, "", "", "Microsoft-Windows-Security-Auditing", "The workstation was locked.", rel,
                   list(tags), ""))

    def unlock(t, rel="background", tags=()):
        ev.append((lt(t), 4801, "7 (Unlock)", HELLO, "Microsoft-Windows-Security-Auditing",
                   "The workstation was unlocked.", rel, list(tags), ""))

    def active(t0, t1, rel="background", tag=None):
        t = lt(t0)
        end = lt(t1)
        first = True
        while t <= end:
            tags = [tag] if (tag and first) else []
            ev.append((t, 9001, "", "", "AurionEDR", "USER_INPUT_ACTIVE (keyboard/mouse activity in last 60s)",
                       rel, tags, ""))
            first = False
            t += timedelta(minutes=1)

    # Friday
    unlock("2026-10-16 08:16:05", "context"); active("2026-10-16 08:16:30", "2026-10-16 08:40:30")
    lock("2026-10-16 08:41:10"); unlock("2026-10-16 09:02:44"); active("2026-10-16 09:03:00", "2026-10-16 09:20:00")
    lock("2026-10-16 10:25:31"); unlock("2026-10-16 11:05:12"); lock("2026-10-16 12:15:09")
    unlock("2026-10-16 13:30:50"); lock("2026-10-16 17:02:11"); unlock("2026-10-16 17:40:22")
    lock("2026-10-16 19:33:58", "context")
    # Saturday (theft night)
    unlock("2026-10-17 21:41:10", "key", ["WS_UNLOCK_2141"])
    active("2026-10-17 21:41:30", "2026-10-17 21:51:30", "supporting")
    lock("2026-10-17 21:52:40", "key", ["WS_LOCK_2152"])
    unlock("2026-10-17 22:49:02", "key", ["WS_UNLOCK_2249"])
    active("2026-10-17 22:49:30", "2026-10-17 22:57:30", "key", "WS_ACTIVE_2249")
    ev.append((lt("2026-10-17 22:55:13"), 9100, "", "", "Outlook",
               "MAIL_SEND subject='Re: Q4 keynote run of show' to=keynote-core@aurion-compute.example", "key",
               ["WS_MAIL_2255"], ""))
    lock("2026-10-17 22:58:30", "key", ["WS_LOCK_2258"])
    # Monday
    unlock("2026-10-19 08:38:02", "context"); active("2026-10-19 08:38:30", "2026-10-19 08:50:30")
    lock("2026-10-19 08:51:15", "context"); unlock("2026-10-19 11:45:40")
    # Background system noise
    for t, eid_, src, msg in [("2026-10-16 03:00:12", 19, "Microsoft-Windows-WindowsUpdateClient",
                               "Installation Successful: Security Intelligence Update"),
                              ("2026-10-17 03:00:09", 19, "Microsoft-Windows-WindowsUpdateClient",
                               "Installation Successful: Security Intelligence Update"),
                              ("2026-10-18 02:15:40", 1001, "Microsoft-Windows-Windows Defender",
                               "Quick scan finished. No threats found."),
                              ("2026-10-18 03:00:11", 19, "Microsoft-Windows-WindowsUpdateClient",
                               "Installation Successful: Security Intelligence Update")]:
        ev.append((lt(t), eid_, "", "", src, msg, "noise", [], "system_housekeeping"))
    ev.sort(key=lambda x: (x[0], x[1]))
    rows = []
    for i, (t, code, lt_, prov, src, msg, rel, tags, noise) in enumerate(ev, 1):
        rid = f"WS-{i:05d}"
        frac = f"{r.randint(0, 9999999):07d}"
        ts = t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S")
        rows.append([rid, f"{ts}.{frac}Z", code, "AUR-EXEC-0001", "AURION\\rhalvorsen", lt_, prov, src, msg])
        for tg in tags:
            reg.key(tg, eid, f"record_id={rid}")
        reg.rec(eid, f"record_id={rid}", rel, noise, tags)
    out.csv(path_of(eid), ["record_id", "time_created_utc", "event_id", "computer", "account", "logon_type",
                           "credential_provider", "source", "message"], rows)


# ---------------------------------------------------------------- calendar
def write_calendar(out: Out, reg: Registry):
    r = rng("calendar")
    eid = "EV-076"
    evs = []  # (start, end, summary, organizer, location, cls, attendees, tags, rel)
    d = lt("2026-07-01 00:00")
    subjects = ["Customer call: hyperscaler", "Product review: AX-9", "Investor call", "Recruiting sync",
                "Ops review", "Kestrel tapeout review", "Marketing: keynote dry run", "Board subcommittee",
                "Finance: Q3 forecast", "Partner call: foundry", "All-hands prep"]
    meet_days = {m[0] for m in MEETINGS}
    while d <= lt("2026-10-31 00:00"):
        day = d.strftime("%Y-%m-%d")
        if d.weekday() == 0:
            evs.append((lt(f"{day} 09:00"), lt(f"{day} 10:30"), "Exec Staff", "jellis", "Bldg E 4-05", "PUBLIC", [],
                        [], "background"))
        if d.weekday() == 3:
            evs.append((lt(f"{day} 16:00"), lt(f"{day} 16:30"), "1:1 CFO (M. Okafor)", "jellis", "Bldg E 4-01",
                        "PUBLIC", [], [], "background"))
        if d.weekday() < 5:
            for _ in range(r.randint(1, 3)):
                s = lt(f"{day} 10:30") + timedelta(minutes=30 * r.randint(0, 13))
                evs.append((s, s + timedelta(minutes=r.choice([30, 45, 60])), r.choice(subjects), "jellis", "",
                            "PUBLIC", [], [], "background"))
        if day in meet_days and day != "2026-10-17":
            tag = f"CAL_DINNER_{day[5:7]}{day[8:10]}"
            evs.append((lt(f"{day} 19:00"), lt(f"{day} 22:30"), "Supply chain dinner (private)", "rhalvorsen", "",
                        "PRIVATE", [], [tag], "key"))
        d += timedelta(days=1)
    evs += [
        (lt("2026-08-12 09:00"), lt("2026-08-12 12:00"), "Board of Directors (Q2 review) + AX-9 demo in EBC",
         "jellis", "Bldg E 4-12 EBC", "PUBLIC", [], [], "context"),
        (lt("2026-09-22 14:00"), lt("2026-09-22 15:00"), "Customer demo: EBC", "jellis", "Bldg E 4-12 EBC", "PUBLIC",
         [], [], "context"),
        (lt("2026-10-07 14:30"), lt("2026-10-07 15:30"),
         "Partner briefing: Pacific Harbor Advisory (V. Shen) + EBC walkthrough", "jellis", "Bldg E 4-12 EBC",
         "PUBLIC", ["v.shen@pacificharbor-advisory.example"], ["CAL_1007_BRIEFING"], "key"),
        (lt("2026-10-17 21:00"), lt("2026-10-17 23:30"), "Board prep (private)", "jellis", "Bldg E 4-01", "PRIVATE",
         [], ["CAL_1017_BOARDPREP"], "key"),
        (lt("2026-10-18 11:00"), lt("2026-10-18 13:30"), "Brunch: E's parents (Saratoga)", "rhalvorsen", "",
         "PRIVATE", [], [], "context"),
        (lt("2026-10-27 10:00"), lt("2026-10-27 11:30"), "Kestrel launch keynote", "jellis", "SJ Civic", "PUBLIC", [],
         [], "context"),
    ]
    evs.sort(key=lambda x: (x[0], x[2]))
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Aurion Compute//Calendar Export 4.1//EN",
             "X-WR-CALNAME:Richard Halvorsen", "X-WR-TIMEZONE:America/Los_Angeles",
             "X-SYNTHETIC:Fictional training data"]
    fmt = "%Y%m%dT%H%M%S"
    for i, (s, e, summ, org, loc, cls, att, tags, rel) in enumerate(evs, 1):
        uid = f"KESTREL-CAL-{i:04d}@aurion-compute.example"
        lines += ["BEGIN:VEVENT", f"UID:{uid}", "DTSTAMP:20261020T163000Z",
                  f"DTSTART;TZID=America/Los_Angeles:{s.strftime(fmt)}",
                  f"DTEND;TZID=America/Los_Angeles:{e.strftime(fmt)}", f"SUMMARY:{summ}",
                  f"ORGANIZER:mailto:{org}@aurion-compute.example", f"CLASS:{cls}"]
        if loc:
            lines.append(f"LOCATION:{loc}")
        lines.append("ATTENDEE;ROLE=REQ-PARTICIPANT:mailto:rhalvorsen@aurion-compute.example")
        for a in att:
            lines.append(f"ATTENDEE;ROLE=REQ-PARTICIPANT:mailto:{a}")
        lines.append("END:VEVENT")
        for tg in tags:
            reg.key(tg, eid, f"uid={uid}")
        reg.rec(eid, f"uid={uid}", rel, "", tags)
    lines.append("END:VCALENDAR")
    out.raw(path_of(eid), ("\r\n".join(lines) + "\r\n").encode("utf-8"))


# ---------------------------------------------------------------- reference tables
def write_reference(out: Out, reg: Registry):
    eid = "EV-077"
    rows = []
    for rid, name, floor, room, zone, notes in READERS:
        rows.append([rid, "badge_reader", name, floor, room, zone, notes])
    for did, kind, name, floor, room, zone, notes in OTHER_DEVICES:
        rows.append([did, kind, name, floor, room, zone, notes])
    for row in rows:
        rel = "supporting" if row[0] in {"E-2-LAB-A", "CAM-E-F4-01", "CAM-E-F4-02", "ELEV-E-1..4", "AP-E4-01..06",
                                         "SC-EBC-01", "RF-SC-EBC-01", "AUR-EXEC-0001", "E-4-12-EBC", "E-4-SUITE"} \
            else "context"
        reg.rec(eid, f"id={row[0]}", rel)
    reg.key("REF_LAB_SKEW", eid, "id=E-2-LAB-A")
    reg.key("REF_ELEVATOR_LOGS", eid, "id=ELEV-E-1..4")
    reg.key("REF_WIFI_LOGS", eid, "id=AP-E4-01..06")
    reg.key("REF_EBC_CAM_RETENTION", eid, "id=CAM-E-F4-02")
    reg.key("REF_WORKSTATION", eid, "id=AUR-EXEC-0001")
    reg.key("REF_CABINET_RULES", eid, "id=SC-EBC-01")
    reg.key("REF_RFID_ALERTING", eid, "id=RF-SC-EBC-01")
    out.csv(path_of(eid), ["id", "kind", "name", "floor", "room", "zone", "notes"], rows)

    eid = "EV-078"
    acl = [["BID-100001", "Richard Halvorsen", "CEO", "N", "N", "Y", "2025-02-01", "Executive override PIN"],
           ["BID-200118", "Dana Whitfield", "EBC Manager", "Y", "Y", "Y", "2025-02-01",
            "Executive override PIN; second authorizer for removals"],
           ["BID-200233", "Priya Raman", "Hardware Engineer (thermal)", "Y", "Y", "N", "2026-03-15",
            "Removal requires second authorizer"],
           ["BID-200402", "Kofi Mensah", "Hardware Engineer (signal integrity)", "Y", "Y", "N", "2026-04-02",
            "Removal requires second authorizer"],
           ["BID-200517", "Sara Lindqvist", "Validation Engineer", "Y", "Y", "N", "2026-05-20",
            "Removal requires second authorizer"],
           ["BID-100014", "Tom Brandt", "Director of Global Security", "N", "N", "N", "2025-02-01",
            "Emergency open only with EBC Manager present"]]
    for row in acl:
        reg.rec(eid, f"badge_id={row[0]}", "supporting" if row[0] in {"BID-100001", "BID-200118", "BID-200233"}
                else "context")
    reg.key("ACL_EXEC_OVERRIDE_HOLDERS", eid, "badge_id=BID-100001;BID-200118")
    out.csv(path_of(eid), ["badge_id", "name", "role", "may_sign_out", "may_deposit", "exec_override",
                           "added", "notes"], acl)


def write_all(out: Out, reg: Registry):
    write_badges_and_lpr(out, reg)
    write_cabinet(out, reg)
    write_rfid(out, reg)
    write_visitors(out, reg)
    write_guard(out, reg)
    write_workstation(out, reg)
    write_calendar(out, reg)
    write_reference(out, reg)
