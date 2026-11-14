"""Visitor log, guard tours, workstation events, calendar, and facility reference tables."""
from __future__ import annotations

from datetime import timedelta

from ..cast import MEETINGS
from ..catalog import path_of
from ..common import UTC, Out, Registry, local_str, lt, rng
from .common import FIRST, LAST, OTHER_DEVICES, READERS

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
