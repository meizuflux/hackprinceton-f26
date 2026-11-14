"""Badge access, garage plate reads, cabinet audit, and RFID inventory."""
from __future__ import annotations

from datetime import timedelta

from ..cast import ITEMS, PEOPLE as P
from ..catalog import path_of
from ..common import PDT, Out, Registry, epoch_ms, iso_local, local_str, lt, rng
from .common import CAST_HOLDER, LAB_SKEW, READERS, _Ev, _g, _lpr, _rex, roster

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
