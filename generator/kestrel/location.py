"""Location evidence: carrier call-detail records with cell-site location (coarse) and the
Halvorsen phone location history export (precise). Both are driven by movement schedules so
co-location analysis (e.g. DBSCAN over space-time) finds the real pattern and nothing else."""
from __future__ import annotations

import math
from datetime import timedelta

from .cast import DROPOFF_DATES, HK_NUMBER_MASKED, MEETINGS, PEOPLE as P, PLACES
from .catalog import path_of
from .common import Out, Registry, daterange, iso_utc, lt, rng
from .messages import SHEN_THREAD

STEP = 0.02  # cell-site grid spacing in degrees (~2 km)
MEET = dict(MEETINGS)


def place(key):
    _, lat, lon, _ = PLACES[key]
    return lat, lon


def haversine_m(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def bearing(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    x = math.sin(lon2 - lon1) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def serving_cell(pt):
    """Deterministic synthetic cell site serving a point: (cgi, site_lat, site_lon, azimuth, radius_m)."""
    i, j = round(pt[0] / STEP), round(pt[1] / STEP)
    r = rng(f"site:{i}:{j}")
    site = (round(i * STEP + r.uniform(-0.004, 0.004), 5), round(j * STEP + r.uniform(-0.004, 0.004), 5))
    sector = int(bearing(site, pt) // 120) if haversine_m(site, pt) > 30 else 0
    rural = pt[0] > 37.9 or pt[1] > -121.7
    lac = 4100 + (abs(i) % 37) * 3 + (abs(j) % 3)
    cid = 20000 + (abs(i) % 211) * 97 + (abs(j) % 97)
    cgi = f"310-410-{lac}-{cid}{'ABC'[sector]}"
    return cgi, site[0], site[1], 60 + 120 * sector, 4500 if rural else 1500


# --------------------------------------------------------------------------- schedules
class Sched:
    """Ordered (start, end, a, b) segments; a == b means a stay, otherwise linear travel a -> b."""

    def __init__(self):
        self.segs = []

    def stay(self, s, e, k):
        self.segs.append((s, e, k, k))

    def move(self, s, e, a, b):
        self.segs.append((s, e, a, b))

    def at(self, t):
        for s, e, a, b in self.segs:
            if s <= t < e:
                if a == b:
                    return place(a), a
                f = (t - s) / (e - s)
                pa, pb = place(a), place(b)
                return (pa[0] + (pb[0] - pa[0]) * f, pa[1] + (pb[1] - pa[1]) * f), f"{a}->{b}"
        return None, None


def shen_schedule():
    r = rng("v_sched")
    sc = Sched()
    for d in daterange(lt("2026-07-01 00:00"), lt("2026-10-21 00:00")):
        day = d.strftime("%Y-%m-%d")
        nxt = d + timedelta(days=1)
        T = lambda hm: lt(f"{day} {hm}")  # noqa: E731
        if day == "2026-10-07":
            sc.stay(d, T("13:40"), "V_APT"); sc.move(T("13:40"), T("14:12"), "V_APT", "HQ")
            sc.stay(T("14:12"), T("16:08"), "HQ"); sc.move(T("16:08"), T("16:35"), "HQ", "V_APT")
            sc.stay(T("16:35"), T("18:55"), "V_APT"); sc.move(T("18:55"), T("19:15"), "V_APT", "OSTERIA")
            sc.stay(T("19:15"), T("21:40"), "OSTERIA"); sc.move(T("21:40"), T("21:59"), "OSTERIA", "V_APT")
            sc.stay(T("21:59"), nxt, "V_APT")
            continue
        if day == "2026-10-17":
            sc.stay(d, T("19:55"), "V_APT"); sc.move(T("19:55"), T("20:10"), "V_APT", "OSTERIA")
            sc.stay(T("20:10"), T("21:21"), "OSTERIA"); sc.move(T("21:21"), T("21:35"), "OSTERIA", "HQ")
            sc.stay(T("21:35"), T("23:05"), "HQ"); sc.move(T("23:05"), T("23:21"), "HQ", "V_APT")
            sc.stay(T("23:21"), nxt, "V_APT")
            continue
        if day == "2026-10-18":
            sc.stay(d, T("09:12"), "V_APT"); sc.move(T("09:12"), T("09:26"), "V_APT", "PLAZA")
            sc.stay(T("09:26"), T("09:59"), "PLAZA"); sc.move(T("09:59"), T("10:04"), "PLAZA", "V_APT")
            sc.stay(T("10:04"), T("13:40"), "V_APT"); sc.move(T("13:40"), T("14:05"), "V_APT", "SANTANA")
            sc.stay(T("14:05"), T("16:30"), "SANTANA"); sc.move(T("16:30"), T("16:55"), "SANTANA", "V_APT")
            sc.stay(T("16:55"), nxt, "V_APT")
            continue
        if day == "2026-10-21":
            sc.stay(d, T("12:25"), "V_APT"); sc.move(T("12:25"), T("12:50"), "V_APT", "PD")
            sc.stay(T("12:50"), T("13:45"), "PD"); sc.move(T("13:45"), T("14:10"), "PD", "V_APT")
            sc.stay(T("14:10"), nxt, "V_APT")
            continue
        wake = d + timedelta(hours=8, minutes=r.randint(0, 90))
        cur = wake
        sc.stay(d, wake, "V_APT")
        if d.weekday() < 5:
            dest = r.choices(["SF_FIDI", "SJ_DT", "PALO_ALTO", "SANTANA", "V_APT"], [35, 25, 15, 10, 15])[0]
            if dest != "V_APT":
                travel = timedelta(minutes=50 if dest == "SF_FIDI" else 25)
                leave = wake + timedelta(minutes=r.randint(30, 90))
                back = T("16:30") + timedelta(minutes=r.randint(0, 90))
                sc.stay(wake, leave, "V_APT"); sc.move(leave, leave + travel, "V_APT", dest)
                sc.stay(leave + travel, back, dest); sc.move(back, back + travel, dest, "V_APT")
                cur = back + travel
        elif r.random() < 0.5:
            dest = r.choice(["SANTANA", "PALO_ALTO"])
            s = T("13:00") + timedelta(minutes=r.randint(0, 60))
            sc.stay(wake, s, "V_APT"); sc.move(s, s + timedelta(minutes=25), "V_APT", dest)
            sc.stay(s + timedelta(minutes=25), s + timedelta(hours=3), dest)
            sc.move(s + timedelta(hours=3), s + timedelta(hours=3, minutes=25), dest, "V_APT")
            cur = s + timedelta(hours=3, minutes=25)
        if day in MEET:
            venue = MEET[day]
            go = T("18:50")
            if cur > go:
                cur = go - timedelta(minutes=10)
            sc.stay(cur, go, "V_APT"); sc.move(go, T("19:15"), "V_APT", venue)
            sc.stay(T("19:15"), T("22:30"), venue); sc.move(T("22:30"), T("22:55"), venue, "V_APT")
            sc.stay(T("22:55"), nxt, "V_APT")
        else:
            sc.stay(cur, nxt, "V_APT")
    return sc


def raman_schedule():
    sc = Sched()
    for d in daterange(lt("2026-10-14 00:00"), lt("2026-10-20 00:00")):
        day = d.strftime("%Y-%m-%d")
        nxt = d + timedelta(days=1)
        T = lambda hm: lt(f"{day} {hm}")  # noqa: E731
        if day == "2026-10-17":
            sc.stay(d, T("06:40"), "R_HOME")
            sc.segs.append((T("06:40"), T("08:10"), "R_HOME", "SAC"))
            sc.segs.append((T("08:10"), T("09:20"), "SAC", "PLACERVILLE"))
            sc.segs.append((T("09:20"), T("10:30"), "PLACERVILLE", "TAHOE"))
            sc.stay(T("10:30"), nxt, "TAHOE")
        elif day == "2026-10-18":
            sc.stay(d, T("15:00"), "TAHOE")
            sc.segs.append((T("15:00"), T("16:10"), "TAHOE", "PLACERVILLE"))
            sc.segs.append((T("16:10"), T("17:20"), "PLACERVILLE", "SAC"))
            sc.segs.append((T("17:20"), T("19:10"), "SAC", "R_HOME"))
            sc.stay(T("19:10"), nxt, "R_HOME")
        elif d.weekday() < 5:
            start, end = ("08:20", "19:25") if day == "2026-10-16" else ("08:30", "18:30")
            sc.stay(d, T(start), "R_HOME"); sc.move(T(start), T(start) + timedelta(minutes=25), "R_HOME", "HQ")
            sc.stay(T(start) + timedelta(minutes=25), T(end), "HQ")
            sc.move(T(end), T(end) + timedelta(minutes=25), "HQ", "R_HOME")
            sc.stay(T(end) + timedelta(minutes=25), nxt, "R_HOME")
        else:
            sc.stay(d, nxt, "R_HOME")
    return sc


PLACES_EXTRA = {"SAC": ("Sacramento (US-50)", 38.58160, -121.49440, "route"),
                "PLACERVILLE": ("Placerville (US-50)", 38.72960, -120.79850, "route")}
PLACES.update(PLACES_EXTRA)


# --------------------------------------------------------------------------- CDR writer
def _cdr_rows(sched: Sched, msisdn: str, start, end, r, forced: list, dense_windows: list, other_numbers: list):
    """Build event list: (t, type, dur, direction, other, tags, rel, note)."""
    evs = []
    d = start
    while d < end:
        day_end = d + timedelta(days=1)
        t = d + timedelta(hours=7, minutes=r.randint(0, 60))
        while t < day_end + timedelta(minutes=30) and t < end:
            evs.append((t, "DATA", r.randint(5, 900), "", "", [], "background", ""))
            t += timedelta(minutes=r.randint(30, 110), seconds=r.randint(0, 59))
        for _ in range(r.randint(1, 2)):
            evs.append((d + timedelta(hours=2, minutes=r.randint(0, 180), seconds=r.randint(0, 59)), "DATA",
                        r.randint(2, 60), "", "", [], "background", ""))
        if r.random() < 0.6:
            ct = d + timedelta(hours=r.randint(9, 20), minutes=r.randint(0, 59), seconds=r.randint(0, 59))
            evs.append((ct, r.choice(["VOICE_MO", "VOICE_MT"]), r.randint(20, 900), "", r.choice(other_numbers), [],
                        "background", ""))
        d = day_end
    for ws, we, step_min, rel in dense_windows:
        t = ws
        while t < we:
            evs.append((t, "DATA", r.randint(5, 300), "", "", [], rel, ""))
            t += timedelta(minutes=step_min, seconds=r.randint(0, 50))
    evs += forced
    return [e for e in evs if start <= e[0] < end]


def write_cdr(out: Out, reg: Registry, eid: str, msisdn: str, sched: Sched, events, seed: str):
    r = rng(seed)
    rows_out = []
    events.sort(key=lambda e: (e[0], e[1]))
    final = []
    for e in events:
        final.append((e, ""))
        if not e[5] and r.random() < 0.015:
            final.append((e, "duplicate_record"))
    for n, (e, dup) in enumerate(final, 1):
        t, etype, dur, _dirn, other, tags, rel, note = e
        rid = f"{msisdn[-4:]}-{n:06d}"
        pt, where = sched.at(t)
        cgi, slat, slon, az, rad = serving_cell(pt)
        noise = dup
        if not tags and not dup:
            x = r.random()
            if x < 0.007:
                cgi, slat, slon, az, rad, noise = "", "", "", "", "", "missing_cell_location"
            elif x < 0.012:
                rad, noise = 12000, "low_precision_location"
        direction = {"VOICE_MO": "OUTGOING", "VOICE_MT": "INCOMING", "SMS_MO": "OUTGOING",
                     "SMS_MT": "INCOMING"}.get(etype, "")
        rows_out.append([rid, msisdn, etype, iso_utc(t), dur, direction, other, cgi, slat, slon, az,
                         120 if az != "" else "", rad])
        for tg in ([] if dup else tags):
            reg.key(tg, eid, f"record_id={rid}", note)
        reg.rec(eid, f"record_id={rid}", "noise" if dup else rel, noise, [] if dup else tags,
                note or (f"truth location: {where}" if rel in ("key", "supporting") else ""))
    out.csv(path_of(eid), ["record_id", "msisdn", "event_type", "start_utc", "duration_s", "direction",
                           "other_party", "cgi", "site_lat", "site_lon", "sector_azimuth_deg", "beamwidth_deg",
                           "est_radius_m"], rows_out)


def write_shen_cdr(out: Out, reg: Registry):
    r = rng("v_cdr_events")
    sc = shen_schedule()
    others = ["+14155550121", "+14155550133", "+16505550142", "+14085550188", "+12125550117", "+16505550199"]
    forced = []
    for t_str, *_ in SHEN_THREAD:
        t = lt(t_str)
        forced.append((t + timedelta(seconds=2), "DATA", r.randint(1, 20), "", "", [], "supporting",
                       "iMessage traffic with Halvorsen (data session)"))
    key_pings = [
        ("2026-10-07 14:20:12", "CDR_0147_HQ_1007_A", "key"), ("2026-10-07 15:09:40", "CDR_0147_HQ_1007_B", "key"),
        ("2026-10-17 20:15:33", "CDR_0147_OSTERIA_1017", "key"),
        ("2026-10-17 21:37:20", "CDR_0147_HQ_1017_FIRST", "key"), ("2026-10-17 22:21:40", "CDR_0147_HQ_1017_2221", "key"),
        ("2026-10-17 22:52:30", "CDR_0147_HQ_1017_2252", "key"), ("2026-10-17 23:04:10", "CDR_0147_HQ_1017_LAST", "key"),
        ("2026-10-17 23:23:05", "CDR_0147_APT_1017_2323", "supporting"),
        ("2026-10-18 09:28:40", "CDR_0147_PLAZA_1", "key"), ("2026-10-18 09:41:10", "CDR_0147_PLAZA_2", "key"),
        ("2026-10-18 09:57:30", "CDR_0147_PLAZA_3", "key"),
        ("2026-10-21 13:05:00", "CDR_0147_PD_1021", "context"),
    ]
    for t_str, tag, rel in key_pings:
        forced.append((lt(t_str), "DATA", r.randint(5, 120), "", "", [tag], rel, ""))
    forced.append((lt("2026-10-18 10:05:12"), "VOICE_MO", 134, "", HK_NUMBER_MASKED, ["CDR_0147_HK_CALL"], "key",
                   "International call; full number masked by carrier pending international request"))
    for day, venue in MEETINGS:
        if day in ("2026-10-07", "2026-10-17"):
            continue
        forced.append((lt(f"{day} 20:41:00"), "DATA", r.randint(5, 120), "", "", [f"CDR_0147_MEET_{day[5:7]}{day[8:10]}"],
                       "key", f"truth venue: {venue}"))
    dense = [(lt("2026-10-17 20:12"), lt("2026-10-17 21:20"), 22, "supporting"),
             (lt("2026-10-17 21:40"), lt("2026-10-17 23:02"), 19, "key"),
             (lt("2026-10-07 14:25"), lt("2026-10-07 16:05"), 28, "supporting")]
    for day, _ in MEETINGS:
        if day not in ("2026-10-07", "2026-10-17"):
            dense.append((lt(f"{day} 19:20"), lt(f"{day} 22:25"), 37, "supporting"))
    evs = _cdr_rows(sc, P["shen"]["phone"], lt("2026-07-01 00:00"), lt("2026-10-22 00:00"), r, forced, dense, others)
    write_cdr(out, reg, "EV-060", P["shen"]["phone"], sc, evs, "v_cdr_noise")
    return sc


def write_raman_cdr(out: Out, reg: Registry):
    r = rng("r_cdr_events")
    sc = raman_schedule()
    others = ["+16505550168", "+14085550170", "+14085550138", "+16505550191"]
    forced = [
        (lt("2026-10-16 19:05:44"), "DATA", 40, "", "", ["CDR_0163_FRI_HQ_1905"], "supporting",
         "exculpatory context: still at HQ before deposit"),
        (lt("2026-10-17 10:41:09"), "DATA", 80, "", "", ["CDR_0163_TAHOE_ARRIVE"], "supporting",
         "exculpatory: Raman at South Lake Tahoe"),
        (lt("2026-10-17 22:47:31"), "DATA", 60, "", "", ["CDR_0163_TAHOE_2247"], "supporting",
         "exculpatory: Raman at South Lake Tahoe during theft window"),
        (lt("2026-10-17 23:12:02"), "DATA", 30, "", "", ["CDR_0163_TAHOE_2312"], "supporting",
         "exculpatory: Raman at South Lake Tahoe during theft window"),
        (lt("2026-10-18 19:15:40"), "DATA", 50, "", "", ["CDR_0163_HOME_SUN"], "supporting", ""),
    ]
    evs = _cdr_rows(sc, P["raman"]["phone"], lt("2026-10-14 00:00"), lt("2026-10-21 00:00"), r, forced, [], others)
    write_cdr(out, reg, "EV-062", P["raman"]["phone"], sc, evs, "r_cdr_noise")


# --------------------------------------------------------------------------- Halvorsen timeline
NAMES = {"HQ": ("Aurion Park Building E", "3100 Aurion Parkway, Santa Clara, CA 95054", "TYPE_WORK"),
         "H_HOME": ("Home", "Los Altos Hills, CA", "TYPE_HOME"),
         "OSTERIA": ("Osteria Lumen", "1180 Franklin St, Santa Clara, CA", "TYPE_SEARCHED_ADDRESS"),
         "MARLOWE": ("The Marlowe Hotel", "200 S 2nd St, San Jose, CA", "TYPE_UNKNOWN"),
         "V_APT": ("Arbor Row Apartments", "455 Arbor Row, Sunnyvale, CA 94086", "TYPE_UNKNOWN"),
         "GOLF": ("Foothill Oaks Golf Club", "Los Altos Hills, CA", "TYPE_UNKNOWN"),
         "GROCERY": ("Los Altos Market", "Los Altos, CA", "TYPE_UNKNOWN"),
         "SARATOGA": ("Saratoga residence", "Saratoga, CA", "TYPE_UNKNOWN"),
         "SFO": ("San Francisco International Airport", "San Francisco, CA", "TYPE_UNKNOWN"),
         "LUNCH1": ("Franklin Street Kitchen", "Franklin St, Santa Clara, CA", "TYPE_UNKNOWN"),
         "LUNCH2": ("Mission Cafe", "Mission College Blvd, Santa Clara, CA", "TYPE_UNKNOWN"),
         "PD": ("South Bay Regional Police Department", "Santa Clara, CA", "TYPE_UNKNOWN")}


def drive(a: str, b: str) -> timedelta:
    return timedelta(minutes=max(6, round(haversine_m(place(a), place(b)) / 1000 * 1.5 + 5)))


TL_END = lt("2026-10-20 19:40")  # consent export time


def halvorsen_plan():
    """Ordered (start, end, place_key, tags, rel) stays. Home stays fill the time between outings."""
    r = rng("h_sched")
    outs = []
    for d in daterange(lt("2026-07-01 00:00"), lt("2026-10-20 00:00")):
        day = d.strftime("%Y-%m-%d")
        T = lambda hm: lt(f"{day} {hm}")  # noqa: E731
        md = f"{day[5:7]}{day[8:10]}"
        special = {
            "2026-10-17": [(T("20:12"), T("21:21"), "OSTERIA", ["TL_H_OSTERIA_1017"], "key"),
                           (T("21:35"), T("23:07"), "HQ", ["TL_H_HQ_1017"], "key"),
                           (T("23:20"), T("23:24"), "V_APT", ["TL_H_VAPT_1017"], "key")],
            "2026-10-18": [(T("11:00"), T("13:30"), "SARATOGA", [], "context")],
            "2026-10-19": [(T("08:33"), T("19:30"), "HQ", [], "context")],
            "2026-10-20": [(T("08:40"), T("15:55"), "HQ", [], "context"),
                           (T("16:15"), T("17:45"), "PD", [], "context")],
            "2026-08-25": [(T("06:30"), T("07:45"), "SFO", ["_TRAVEL"], "background")],
            "2026-08-26": [],
            "2026-08-27": [(T("21:00"), T("21:35"), "SFO", [], "background")],
        }
        if day in special:
            outs += special[day]
            continue
        wd = d.weekday()
        if wd < 5:
            arrive = T("08:05") + timedelta(minutes=r.randint(0, 40))
            leave = T("18:20") + timedelta(minutes=r.randint(0, 90))
            if day in MEET:
                leave = T("18:50") if day == "2026-10-07" else T("18:45")
            hq_tags, hq_rel = (["TL_H_HQ_1007"], "supporting") if day == "2026-10-07" else ([], "background")
            if r.random() < 0.3 and day not in MEET:
                l1 = T("12:10") + timedelta(minutes=r.randint(0, 20))
                outs += [(arrive, l1, "HQ", [], "background"),
                         (l1 + timedelta(minutes=8), l1 + timedelta(minutes=55), r.choice(["LUNCH1", "LUNCH2"]), [],
                          "background"),
                         (l1 + timedelta(minutes=63), leave, "HQ", [], "background")]
            else:
                outs.append((arrive, leave, "HQ", hq_tags, hq_rel))
            if day in MEET:
                venue = MEET[day]
                vs = T("19:08") if venue == "OSTERIA" else T("19:12")
                ve = T("21:40") if day == "2026-10-07" else T("22:30")
                outs.append((vs, ve, venue, [f"TL_H_MEET_{md}"], "key"))
                if day in DROPOFF_DATES:
                    ds = ve + drive(venue, "V_APT")
                    outs.append((ds, ds + timedelta(minutes=r.randint(4, 7)), "V_APT", [f"TL_H_VAPT_{md}"], "key"))
        else:
            if wd == 5 and r.random() < 0.6:
                gs = T("07:30") + timedelta(minutes=r.randint(0, 30))
                outs.append((gs, gs + timedelta(hours=4, minutes=r.randint(0, 50)), "GOLF", [], "background"))
            if wd == 6 and r.random() < 0.4:
                gs = T("10:00") + timedelta(minutes=r.randint(0, 60))
                outs.append((gs, gs + timedelta(minutes=45), "GROCERY", [], "background"))
    outs.sort(key=lambda s: s[0])
    stays = []
    prev_end, prev_key, travel = lt("2026-07-01 00:00"), "H_HOME", False
    first = True
    for s, e, k, tags, rel in outs:
        if travel:  # away on a trip: no data until the return
            pass
        elif first:
            stays.append((prev_end, s - drive("H_HOME", k), "H_HOME", [], "background"))
        elif s - prev_end > drive(prev_key, "H_HOME") + drive("H_HOME", k) + timedelta(minutes=45):
            hs, he = prev_end + drive(prev_key, "H_HOME"), s - drive("H_HOME", k)
            htags, hrel = [], "background"
            if hs.strftime("%Y-%m-%d %H") == "2026-10-17 23":
                htags, hrel = ["TL_H_HOME_1017"], "key"
            elif he.strftime("%Y-%m-%d") == "2026-10-17":
                hrel = "context"
            stays.append((hs, he, "H_HOME", htags, hrel))
        first = False
        travel = "_TRAVEL" in tags
        stays.append((s, e, k, [t for t in tags if not t.startswith("_")], rel))
        prev_end, prev_key = e, k
    stays.append((prev_end + drive(prev_key, "H_HOME"), TL_END, "H_HOME", [], "context"))
    return stays


def write_halvorsen_timeline(out: Out, reg: Registry):
    r = rng("h_tl")
    eid = "EV-063"
    stays = halvorsen_plan()
    objs = []
    pv = sg = 0
    prev = None
    for s, e, k, tags, rel in stays:
        if s >= TL_END:
            break
        e = min(e, TL_END)
        if prev is not None and prev[1] < s and s - prev[1] < timedelta(hours=6):
            sg += 1
            a, b = place(prev[2]), place(k)
            seg_id = f"AS-{sg:05d}"
            objs.append({"activitySegment": {
                "segmentId": seg_id,
                "startLocation": {"latitudeE7": int(a[0] * 1e7), "longitudeE7": int(a[1] * 1e7)},
                "endLocation": {"latitudeE7": int(b[0] * 1e7), "longitudeE7": int(b[1] * 1e7)},
                "duration": {"startTimestamp": iso_utc(prev[1]).replace("Z", ".000Z"),
                             "endTimestamp": iso_utc(s).replace("Z", ".000Z")},
                "distance": int(haversine_m(a, b) * 1.3),
                "activityType": "IN_PASSENGER_VEHICLE" if haversine_m(a, b) > 1500 else "WALKING",
                "confidence": "HIGH"}})
            reg.rec(eid, f"segmentId={seg_id}", "background" if rel == "background" else "context")
        pv += 1
        vid = f"PV-{pv:05d}"
        lat, lon = place(k)
        name, addr, stype = NAMES[k]
        jit = (r.uniform(-0.0003, 0.0003), r.uniform(-0.0003, 0.0003))
        objs.append({"placeVisit": {
            "visitId": vid,
            "location": {"latitudeE7": int(lat * 1e7), "longitudeE7": int(lon * 1e7), "placeId": f"synthetic:{k}",
                         "address": addr, "name": name, "semanticType": stype,
                         "locationConfidence": round(r.uniform(82, 99), 1)},
            "duration": {"startTimestamp": iso_utc(s).replace("Z", ".000Z"),
                         "endTimestamp": iso_utc(e).replace("Z", ".000Z")},
            "placeConfidence": "HIGH_CONFIDENCE",
            "visitConfidence": r.randint(80, 98),
            "centerLatE7": int((lat + jit[0]) * 1e7), "centerLngE7": int((lon + jit[1]) * 1e7)}})
        for tg in tags:
            reg.key(tg, eid, f"visitId={vid}")
        reg.rec(eid, f"visitId={vid}", rel, "", tags)
        if not tags and (e - s) > timedelta(minutes=50) and r.random() < 0.03:
            pv += 1
            nid = f"PV-{pv:05d}"
            mid = s + (e - s) / 3
            objs.append({"placeVisit": {
                "visitId": nid,
                "location": {"latitudeE7": int((lat + 0.0011) * 1e7), "longitudeE7": int((lon - 0.0009) * 1e7),
                             "placeId": "synthetic:NEARBY", "address": "nearby", "name": "Bean Theory Coffee (nearby)",
                             "semanticType": "TYPE_UNKNOWN", "locationConfidence": round(r.uniform(12, 30), 1)},
                "duration": {"startTimestamp": iso_utc(mid).replace("Z", ".000Z"),
                             "endTimestamp": iso_utc(mid + timedelta(minutes=6)).replace("Z", ".000Z")},
                "placeConfidence": "LOW_CONFIDENCE", "visitConfidence": r.randint(10, 30),
                "centerLatE7": int((lat + 0.0011) * 1e7), "centerLngE7": int((lon - 0.0009) * 1e7)}})
            reg.rec(eid, f"visitId={nid}", "noise", "low_confidence_visit")
        prev = (s, e, k)
    out.json(path_of(eid), {"timelineObjects": objs,
                            "exportNote": "Synthetic location history export (fictional). Times in UTC."})


def write_all(out: Out, reg: Registry):
    write_shen_cdr(out, reg)
    write_raman_cdr(out, reg)
    write_halvorsen_timeline(out, reg)
