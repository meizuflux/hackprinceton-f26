"""Stage A: deterministic analysis (traditional ML and rules).

Each function returns citable findings with the method, parameters, input records and a plain-language
reason. Nothing here calls an LLM, so results are reproducible and the board works offline.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import timedelta

from .model import Item, stable_key
from .store import Case, Record, haversine_m, iso

_CRED_KEY = re.compile(r"^(badge|card|credential|employee|user|staff)_?(id|no|number)?$|^credentials?$", re.I)
_FAIL = re.compile(r"DENIED|FAIL|INVALID|ERROR|FORCED|HELD|ALARM|TAMPER|REJECT|DURESS|OVERRIDE|UNKNOWN", re.I)
_BIOMETRIC = re.compile(r"face|fingerprint|biometric|hello|iris|touch ?id", re.I)
_ALARM = re.compile(r"\bALARM\b|FORCED|BREAK-?IN|TAMPER|DURESS|INTRUSION|GLASS BREAK", re.I)
_COMM_TYPES = {"message", "call", "email"}


class Context:
    """Derived lookups shared by every stage: who a record is about, credential owners, aliases."""

    def __init__(self, case: Case, results):
        self.case = case
        self.results = results
        self.cred_owner: dict[str, tuple[int, list[int]]] = {}
        self.alias_person: dict[int, tuple[int, str, list[int]]] = {}  # entity -> (person, rule, evidence record ids)
        self._build_credentials()
        self._build_handle_aliases()

    # credentials seen next to a named person (badge log, ACL) can attribute credential-only records
    def _build_credentials(self) -> None:
        seen: dict[str, Counter] = defaultdict(Counter)
        cites: dict[tuple[str, int], list[int]] = defaultdict(list)
        for r in self.case.records.values():
            persons = self.case.person_of(r)
            if len(persons) != 1:
                continue
            for k, v in r.attrs.items():
                if _CRED_KEY.match(k) and isinstance(v, str) and ";" not in v and v and "UNKNOWN" not in v.upper():
                    seen[v][persons[0]] += 1
                    if len(cites[(v, persons[0])]) < 3:
                        cites[(v, persons[0])].append(r.id)
        for cred, counter in seen.items():
            (person, n), = counter.most_common(1)
            if n / sum(counter.values()) >= 0.9:
                self.cred_owner[cred] = (person, cites[(cred, person)])

    # account handles ("AURION\\rhalvorsen", "rhalvorsen@...") -> the one person whose name forms that handle
    def _build_handle_aliases(self) -> None:
        people = {pid: self.case.entities[pid]["value_norm"].split() for pid in self.case.persons
                  if len(self.case.entities[pid]["value_norm"].split()) >= 2}
        for eid, e in self.case.entities.items():
            if e["canonical_id"] != eid or e["entity_type"] not in ("account", "device", "email"):
                continue
            handle = re.split(r"[\\/]", e["value_norm"])[-1].split("@")[0].lower()
            handle = re.sub(r"[^a-z.]", "", handle)
            if len(handle) < 4:
                continue
            flat = handle.replace(".", "")
            cands = [pid for pid, t in people.items()
                     if flat in {t[0][0] + t[-1], t[0] + t[-1], t[-1] + t[0][0], t[0] + "." + t[-1]} or handle == f"{t[0]}.{t[-1]}"]
            if len(cands) == 1:
                rids = [r.id for r in self.case.records.values() if any(x == eid for x, _ in r.entities)][:3]
                self.alias_person[eid] = (cands[0], "account handle matches the person's name", rids)

    def persons_for(self, rec: Record) -> list[tuple[int, str, str]]:
        """(person, certainty, basis) for everyone a record is about. Mentions don't count."""
        out: dict[int, tuple[str, str]] = {}
        for eid, role in rec.entities:
            if role == "mentioned":
                continue
            if self.case.etype(eid) == "person":
                out.setdefault(eid, ("observed", f"named as {role}"))
            elif eid in self.alias_person:
                pid, rule, _ = self.alias_person[eid]
                out.setdefault(pid, ("inferred", f"{self.case.name(eid)}: {rule}"))
        for k, v in rec.attrs.items():
            if _CRED_KEY.match(k) and isinstance(v, str):
                for cred in [c.strip() for c in v.split(";")]:
                    if cred in self.cred_owner:
                        pid, _ = self.cred_owner[cred]
                        out.setdefault(pid, ("inferred", f"credential {cred} is registered to {self.case.name(pid)}"))
        return [(p, c, b) for p, (c, b) in out.items()]

    def subject_of(self, rec: Record) -> int | None:
        ps = self.persons_for(rec)
        if ps:
            return ps[0][0]
        for eid, role in rec.entities:
            if role in ("device_owner", "caller", "sender", "subject", "device") and self.case.etype(eid) in ("phone", "device", "account"):
                return eid
        return None


def credential_and_alias_links(ctx: Context) -> list[Item]:
    items = []
    case = ctx.case
    for cred, (pid, rids) in ctx.cred_owner.items():
        items.append(Item("connection", stable_key("cred", cred, case.name(pid)), f"Credential {cred} → {case.name(pid)}",
                          f"Records list credential {cred} together with {case.name(pid)}, so other records that show only "
                          f"this credential are attributed to them. A credential shows which card was used, not who held it.",
                          certainty="observed", score=0.6, citations=[case.cite(r) for r in rids],
                          data={"edge": "uses_credential", "source": pid, "target_label": cred}))
    for eid, (pid, rule, rids) in ctx.alias_person.items():
        items.append(Item("connection", stable_key("alias", case.name(eid), case.name(pid)),
                          f"{case.name(eid)} is probably {case.name(pid)}", f"Inferred link: {rule}.", certainty="inferred",
                          score=0.55, citations=[case.cite(r) for r in rids], data={"edge": "alias", "source": pid, "target_entity": eid}))
    for l in case.links:
        if l["confidence"] < 0.9:
            a, b = l["entity_a"], l["entity_b"]
            rids = [l["record_id"]] if l["record_id"] else []
            if not rids:  # cite one record where each name form appears
                for ent in (a, b):
                    hit = next((r.id for r in case.records.values()
                                if any(case.entities.get(x, {}).get("canonical_id") == ent or x == ent for x, _ in r.entities)), None)
                    if hit:
                        rids.append(hit)
            cites = [case.cite(r) for r in rids]
            items.append(Item("connection", stable_key("link", case.name(a), case.name(b), l["rule"]),
                              f"{case.name(a)} may be {case.name(b)}",
                              f"Inferred during ingestion by rule '{l['rule'].replace('_', ' ')}' (confidence {l['confidence']}).",
                              certainty="inferred", score=l["confidence"], citations=cites,
                              data={"edge": "alias", "entity_a": a, "entity_b": b}))
    return items


# --------------------------------------------------------------------------- co-location
def colocation(ctx: Context, min_days: int = 2) -> list[Item]:
    """Space-time co-location: two subjects within a distance tolerance at overlapping times, on several days."""
    case = ctx.case
    pts: dict[int, list[tuple]] = defaultdict(list)
    for r in case.timed:
        if r.lat is None or r.lon is None:
            continue
        subj = ctx.subject_of(r)
        if subj is None:
            continue
        radius = 0.0
        for k in ("accuracy_m", "est_radius_m", "radius"):
            try:
                radius = max(radius, float(r.attrs.get(k) or 0))
            except (TypeError, ValueError):
                pass
        start = r.start or r.ts
        end = r.end if (r.end and r.end > start) else start
        pts[subj].append((start, end, r.lat, r.lon, radius or 50.0, r.id))
    subjects = [s for s, p in pts.items() if len(p) >= 3]
    items = []
    tol = timedelta(minutes=15)
    for i, a in enumerate(subjects):
        for b in subjects[i + 1:]:
            if case.etype(a) == case.etype(b) == "person" and a == b:
                continue
            hits = []
            pb = sorted(pts[b])
            j0 = 0
            for (sa, ea, la, oa, ra, ida) in sorted(pts[a]):
                while j0 < len(pb) and pb[j0][1] < sa - tol:
                    j0 += 1
                for (sb, eb, lb, ob, rb, idb) in pb[j0:]:
                    if sb > ea + tol:
                        break
                    d = haversine_m(la, oa, lb, ob)
                    limit = max(150.0, min(ra + rb, 2000.0))
                    if d <= limit:
                        hits.append((max(sa, sb), d, max(ra, rb), ida, idb))
            if not hits:
                continue
            by_day = defaultdict(list)
            for h in hits:
                by_day[h[0].date()].append(h)
            if len(by_day) < min_days:
                continue
            approx = sum(1 for h in hits if h[2] > 300) / len(hits) > 0.5
            night = sum(1 for h in hits if h[0].hour >= 1 and h[0].hour <= 12) / len(hits)  # UTC; refined below in text
            days = sorted(by_day)
            sample = [h for d in days[:6] for h in by_day[d][:1]]
            cites = [case.cite(x) for h in sample for x in (h[3], h[4])]
            score = min(1.0, 0.35 + 0.08 * len(days)) * (0.8 if approx else 1.0)
            items.append(Item(
                "finding", stable_key("coloc", case.name(a), case.name(b)),
                f"{case.name(a)} and {case.name(b)} were repeatedly in the same place",
                f"Location records put them within {'cell-sector range' if approx else '150 m'} of each other at overlapping times "
                f"on {len(days)} separate days ({days[0]} to {days[-1]}), {len(hits)} matching observations in total."
                + (" Several matches rely on cell-site areas up to 1.5 km wide, so this shows proximity, not a meeting." if approx else ""),
                certainty="inferred", score=round(score, 2), citations=cites,
                data={"method": {"name": "space-time co-location", "distance_m": 150, "time_tolerance_min": 15,
                                 "min_days": min_days}, "subjects": [a, b], "days": [str(d) for d in days],
                      "approximate": approx, "observations": len(hits), "night_share_utc": round(night, 2),
                      "record_ids": [x for h in hits for x in (h[3], h[4])][:200]}))
    return items


# --------------------------------------------------------------------------- access anomalies
def access_anomalies(ctx: Context, max_items: int = 12, per_file: int = 2) -> list[Item]:
    """IsolationForest fitted per log (each system has its own normal), explained by its features.
    The top anomalies of each log compete for the final list, so one busy log cannot drown out the rest."""
    import numpy as np
    from sklearn.ensemble import IsolationForest

    case = ctx.case
    tz = case_tz(case)
    evs = [r for r in case.timed if r.type == "event" and (r.place or r.attrs.get("event"))]
    by_file = defaultdict(list)
    for r in evs:
        by_file[r.file_id].append(r)
    candidates = []
    for fid, rs in by_file.items():
        if len(rs) < 25:
            # too few events to learn what is normal: flag only explicit alarms and forced entry
            for r in rs:
                if _ALARM.search(" ".join(str(v) for v in [r.content, *r.attrs.values()])):
                    lt = r.ts.astimezone(tz)
                    night = 1.0 if (lt.hour >= 22 or lt.hour < 6) else 0.0
                    weekend = 1.0 if lt.weekday() >= 5 else 0.0
                    candidates.append((0.8 + 0.1 * night, r, (lt, weekend, night, 0, 0, 0, 1.0, 1, len(rs)), 0.0))
            continue
        text_freq = Counter(_norm_event(r) for r in rs)
        hour_freq = Counter(r.ts.astimezone(tz).hour for r in rs)
        actor_place, actor_n = Counter(), Counter()
        for r in rs:
            a = ctx.subject_of(r)
            actor_place[(a, r.place)] += 1
            actor_n[a] += 1
        feats, why_parts = [], []
        n = len(rs)
        for r in rs:
            lt = r.ts.astimezone(tz)
            rare_text = -math.log(text_freq[_norm_event(r)] / n)
            rare_hour = -math.log(hour_freq[lt.hour] / n)
            a = ctx.subject_of(r)
            rare_place = -math.log((actor_place[(a, r.place)] + 1) / (actor_n[a] + 2)) if a else 0.0
            fail = 1.0 if _FAIL.search(" ".join(str(v) for v in [r.content, *r.attrs.values()])) else 0.0
            weekend = 1.0 if lt.weekday() >= 5 else 0.0
            night = 1.0 if (lt.hour >= 22 or lt.hour < 6) else 0.0
            feats.append([math.sin(lt.hour / 24 * 2 * math.pi), math.cos(lt.hour / 24 * 2 * math.pi), weekend, night,
                          rare_text, rare_hour, rare_place, fail])
            why_parts.append((lt, weekend, night, rare_text, rare_hour, rare_place, fail, text_freq[_norm_event(r)], n))
        X = np.array(feats)
        cont = min(0.05, max(0.01, 5 / n))
        model = IsolationForest(n_estimators=200, contamination=cont, random_state=7).fit(X)
        flagged = model.predict(X) == -1
        raw = -model.score_samples(X)
        norm = (raw - raw.min()) / (raw.max() - raw.min() + 1e-9)
        picked, seen_sig = 0, set()
        for idx in np.argsort(-norm):
            if not flagged[idx] or picked >= per_file:
                continue
            r = rs[idx]
            sig = (_norm_event(r), r.place, ctx.subject_of(r))
            if sig in seen_sig:
                continue  # one representative per repeated pattern
            seen_sig.add(sig)
            picked += 1
            lt, weekend, night, rt, rh, rp, fail, tf, nf = why_parts[idx]
            severity = norm[idx] * (1 + 0.25 * fail + 0.2 * weekend + 0.2 * night)
            candidates.append((severity, r, why_parts[idx], cont))
    candidates.sort(key=lambda c: -c[0])
    items = []
    for severity, r, (lt, weekend, night, rt, rh, rp, fail, tf, nf), cont in candidates[:max_items]:
        why = []
        if night or weekend:
            why.append(f"at {lt:%H:%M} on a {lt:%A}" + (" night" if night else "") + (" (weekend)" if weekend else ""))
        if rt > 3:
            why.append(f"this event type is rare in its log ({tf} of {nf})")
        if rh > 3:
            why.append("few events in this log happen at that hour")
        if rp > 2:
            who = ctx.subject_of(r)
            why.append(f"unusual place for {case.name(who)}" if who else "unusual place")
        if fail:
            why.append("the record reports a failure, denial, held door or alarm")
        who = ", ".join(case.name(p) for p, _, _ in ctx.persons_for(r)) or (r.actor or "unattributed")
        items.append(Item(
            "finding", stable_key("anomaly", r.id),
            f"Unusual event: {r.content[:70]}" + (f" @ {case.place_name(r.place)}" if r.place and r.place not in r.content else ""),
            f"{who}: {r.content}. Flagged because " + ("; ".join(why) or "its combination of time, place and event is rare") + ".",
            certainty="observed", score=round(float(min(1.0, severity)), 2), citations=[case.cite(r.id)],
            data={"method": ({"name": "IsolationForest (per log)", "contamination": round(cont, 3), "n_estimators": 200,
                              "random_state": 7, "features": ["hour", "weekend", "night", "event rarity", "hour rarity",
                                                              "place rarity for actor", "failure flag"]}
                             if cont else {"name": "alarm rule (log too short to model)",
                                           "pattern": "ALARM|FORCED|BREAK-IN|TAMPER|DURESS|INTRUSION"}),
                  "record_ids": [r.id], "time": iso(r.ts), "place": r.place, "severity": round(float(severity), 3),
                  "persons": [[p, c, b] for p, c, b in ctx.persons_for(r)]}))
    return items


def _norm_event(r: Record) -> str:
    v = r.attrs.get("event") or r.attrs.get("event_type") or r.content
    return re.sub(r"\d+", "#", str(v))[:60]


def case_tz(case: Case):
    from zoneinfo import ZoneInfo
    try:
        return ZoneInfo(case.info.get("assumed_timezone") or "UTC")
    except Exception:  # noqa: BLE001
        return ZoneInfo("UTC")


# --------------------------------------------------------------------------- concurrent presence
_PRESENCE = re.compile(r"ACCESS_GRANTED|GRANTED|unlock|log ?on|logged on|USER_INPUT|input|active|DOOR_OPEN|opened|"
                       r"AUTH|scan|sign[_ ]?in|entry|badge", re.I)
_ABSENCE = re.compile(r"locked\b|log ?off|timeout|auto-?lock|DENIED|sleep|screensaver", re.I)
_HOME = re.compile(r"\bhome\b|TYPE_HOME|residence", re.I)


def _is_presence(r: Record) -> bool:
    text = " ".join([r.content, str(r.attrs.get("event", "")), str(r.attrs.get("event_type", ""))])
    return bool(_PRESENCE.search(text)) and not _ABSENCE.search(text)


def _is_device_place(r: Record) -> bool:
    return any(k in r.attrs for k in ("computer", "host", "hostname", "workstation"))


def concurrent_presence(ctx: Context) -> list[Item]:
    """One person active in two places at once. Three patterns, all strict to avoid flagging normal movement:
    (a) active at a workstation both just before and just after a record somewhere else;
    (b) location history says they were at home while a record places them elsewhere;
    (c) two GPS-grade fixes more than 1 km apart within 10 minutes."""
    case = ctx.case
    tz = case_tz(case)
    per_person = defaultdict(list)
    for r in case.timed:
        if not (r.place or r.lat is not None):
            continue
        for pid, cert, basis in ctx.persons_for(r):
            per_person[pid].append((r, cert, basis))
    items, seen = [], set()

    def add(pid, a, b, kind, text, score, extra):
        bucket = (pid, kind, b.ts.replace(minute=b.ts.minute // 10 * 10, second=0))
        if bucket in seen:
            return
        seen.add(bucket)
        items.append(Item("finding", stable_key("concurrent", kind, case.name(pid), a.id, b.id),
                          f"{case.name(pid)} recorded in two places at once", text, certainty="inferred", score=score,
                          citations=[case.cite(x) for x in [a.id, b.id, *extra]],
                          data={"method": {"name": f"concurrent-presence rule ({kind})"}, "person": pid,
                                "record_ids": [b.id, a.id, *extra], "time": iso(b.ts), "places": [a.place, b.place],
                                "biometric": any(_BIOMETRIC.search(" ".join(map(str, x.attrs.values()))) for x in (a, b))}))

    for pid, rs in per_person.items():
        rs.sort(key=lambda x: x[0].ts)
        recs = [x[0] for x in rs]
        basis = {x[0].id: x[2] for x in rs}
        device_active = [r for r in recs if _is_device_place(r) and _is_presence(r)]
        elsewhere = [r for r in recs if r.place and not _is_device_place(r) and _is_presence(r) and r.type == "event"]
        # (a) workstation session spans a record elsewhere
        for e in elsewhere:
            before = [d for d in device_active if timedelta(0) <= e.ts - d.ts <= timedelta(minutes=3)]
            after = [d for d in device_active if timedelta(0) < d.ts - e.ts <= timedelta(minutes=3)]
            if before and after:
                d0, d1 = before[-1], after[0]
                bio = any(_BIOMETRIC.search(" ".join(map(str, x.attrs.values()))) for x in device_active
                          if abs((x.ts - e.ts).total_seconds()) < 1800)
                add(pid, d0, e, "workstation", (
                    f"{case.name(pid)}'s workstation {case.place_name(d0.place)} shows activity at {d0.ts.astimezone(tz):%H:%M:%S} and "
                    f"{d1.ts.astimezone(tz):%H:%M:%S} ({d0.content[:50]}; {d1.content[:50]}), while at "
                    f"{e.ts.astimezone(tz):%a %d %b %H:%M:%S} {e.content[:50]} was recorded at {case.place_name(e.place)} ({basis[e.id]}). "
                    "The same person is unlikely to be in both places; possible reasons: someone else used the credential "
                    "or the workstation session, the two places are adjacent, or one clock is off."
                    + (" The workstation session used a biometric sign-in, which is harder to share." if bio else "")),
                    0.9 if bio else 0.7, [d1.id])
        # (b) home per location history vs a record elsewhere
        homes = [r for r in recs if r.type == "place_visit" and _HOME.search(" ".join([r.content, str(r.attrs.get("semanticType", ""))]))]
        for h in homes:
            hs, he = h.start or h.ts, h.end or h.ts
            for e in elsewhere:
                if hs + timedelta(minutes=10) <= e.ts <= he - timedelta(minutes=10):
                    add(pid, h, e, "home", (
                        f"Location history places {case.name(pid)} at home from {hs.astimezone(tz):%a %d %b %H:%M} to "
                        f"{he.astimezone(tz):%H:%M}, but at {e.ts.astimezone(tz):%H:%M} {e.content[:50]} was recorded at "
                        f"{case.place_name(e.place)} ({basis[e.id]}). Either the credential was used by someone else, or the phone stayed "
                        "home without its owner."), 0.75, [])
        # (c) two precise fixes far apart
        def acc(r):
            try:
                return float(r.attrs.get("accuracy_m") or r.attrs.get("est_radius_m") or 50)
            except (TypeError, ValueError):
                return 50.0
        geo = [r for r in recs if r.lat is not None and acc(r) < 300]
        for i, a in enumerate(geo):
            for b in geo[i + 1:]:
                if (b.ts - a.ts) > timedelta(minutes=10):
                    break
                d = haversine_m(a.lat, a.lon, b.lat, b.lon)
                if d > 2000 and a.file_id != b.file_id and d / max((b.ts - a.ts).total_seconds(), 60) > 55:  # > ~200 km/h
                    add(pid, a, b, "gps", (
                        f"Two location records for {case.name(pid)} are {d / 1000:.1f} km apart within "
                        f"{int((b.ts - a.ts).total_seconds() / 60)} minutes."), 0.6, [])
    return items


def _same_place(a: str, b: str) -> bool:
    ta = set(re.findall(r"[a-z0-9]+", a.lower()))
    tb = set(re.findall(r"[a-z0-9]+", b.lower()))
    return bool(ta & tb) and (len(ta & tb) / min(len(ta), len(tb)) >= 0.5)


# --------------------------------------------------------------------------- communications
def communication_patterns(ctx: Context) -> list[Item]:
    case = ctx.case
    pairs = defaultdict(list)
    for r in case.records.values():
        if r.type not in _COMM_TYPES or r.duplicate_of:
            continue
        snd = [e for e, role in r.entities if role in ("sender", "caller")]
        rcv = [e for e, role in r.entities if role in ("recipient", "callee")]
        for s in snd:
            for t in rcv:
                if s != t:
                    pairs[tuple(sorted((s, t)))].append(r)
    items = []
    tz = case_tz(case)
    for (a, b), rs in pairs.items():
        timed = sorted((r for r in rs if r.ts), key=lambda r: r.ts)
        deleted = [r for r in rs if str(r.attrs.get("deleted", "")).lower() in ("yes", "true", "1")]
        aliases = {str(r.attrs.get("party_name") or r.attrs.get("thread_name")) for r in rs
                   if (r.attrs.get("party_name") or r.attrs.get("thread_name"))}
        aliases = {x for x in aliases if x and x not in (case.name(a), case.name(b))}
        night = [r for r in timed if r.ts.astimezone(tz).hour >= 22 or r.ts.astimezone(tz).hour < 6]
        notable = []
        if deleted:
            notable.append(f"{len(deleted)} of {len(rs)} were deleted on the device")
        if aliases:
            notable.append(f"the contact is saved as {', '.join(sorted(aliases)[:3])}")
        if len(night) >= 3 and len(night) / max(len(timed), 1) > 0.3:
            notable.append(f"{len(night)} took place late at night")
        if not notable and len(rs) < 20:
            continue
        span = f" between {timed[0].ts.astimezone(tz):%d %b %Y} and {timed[-1].ts.astimezone(tz):%d %b %Y}" if timed else ""
        cites = [case.cite(r.id) for r in (deleted[:2] + timed[:2] + timed[-1:])]
        items.append(Item(
            "finding", stable_key("comms", case.name(a), case.name(b)),
            f"Communication: {case.name(a)} ↔ {case.name(b)}",
            f"{len(rs)} messages/calls{span}" + (": " + "; ".join(notable) if notable else "") + ".",
            certainty="observed", score=round(min(1.0, 0.3 + 0.15 * len(notable) + min(len(rs), 100) / 400), 2),
            citations=list({c["id"]: c for c in cites}.values()),
            data={"method": {"name": "communication pair statistics"}, "pair": [a, b], "count": len(rs),
                  "deleted": len(deleted), "aliases": sorted(aliases), "night": len(night),
                  "first": iso(timed[0].ts) if timed else None, "last": iso(timed[-1].ts) if timed else None,
                  "record_ids": [r.id for r in rs][:300]}))
    # identifiers that talk a lot with people but have no name attached
    for eid in {x for pr in pairs for x in pr}:
        if case.etype(eid) in ("phone", "email"):
            n = sum(len(v) for k, v in pairs.items() if eid in k)
            partners = {x for k in pairs if eid in k for x in k if x != eid and case.etype(x) == "person"}
            if n >= 10 and partners:
                rs = [r for k, v in pairs.items() if eid in k for r in v][:3]
                items.append(Item(
                    "finding", stable_key("unidentified", case.name(eid)), f"Unidentified party: {case.name(eid)}",
                    f"{case.name(eid)} exchanged {n} messages/calls with {', '.join(case.name(p) for p in partners)}, "
                    f"but no record in the case ties it to a named person.",
                    certainty="observed", score=round(min(1.0, 0.4 + n / 200), 2), citations=[case.cite(r.id) for r in rs],
                    data={"method": {"name": "unresolved identifier"}, "entity": eid, "count": n, "partners": sorted(partners)}))
    return items


# --------------------------------------------------------------------------- key events
def key_episodes(ctx: Context, findings: list[Item], top: int = 3) -> list[Item]:
    """Group the strongest anomalies and concurrent-presence findings into key events (episodes)."""
    case = ctx.case
    pts = []
    for f in findings:
        if f.data.get("time") and f.key and (f.title.startswith("Unusual event") or "two places" in f.title):
            pts.append((case.records[f.data["record_ids"][0]].ts, f))
    pts.sort(key=lambda x: x[0])
    clusters: list[list] = []
    for t, f in pts:
        if clusters and (t - clusters[-1][-1][0]) <= timedelta(hours=2):
            clusters[-1].append((t, f))
        else:
            clusters.append([(t, f)])
    def weight(c):
        files = {case.records[rid].file_id for _, f in c for rid in f.data.get("record_ids", [])}
        return sum(f.data.get("severity", f.score) for _, f in c) * (1 + 0.5 * (len(files) - 1))
    scored = sorted(clusters, key=lambda c: -weight(c))[:top]
    if scored:
        best = weight(scored[0])
        scored = [c for c in scored if weight(c) >= 0.4 * best]
    items = []
    tz = case_tz(case)
    for c in scored:
        start, end = c[0][0] - timedelta(minutes=30), c[-1][0] + timedelta(minutes=30)
        rids = [rid for _, f in c for rid in f.data.get("record_ids", [])]
        conflicts_t = [case.records[f.data["record_ids"][0]].ts for _, f in c if "two places" in f.title]
        def key_rank(f):
            t = case.records[f.data["record_ids"][0]].ts
            near_conflict = any(abs((t - ct).total_seconds()) <= 600 for ct in conflicts_t) and "two places" not in f.title
            return (not near_conflict, -f.data.get("severity", f.score))
        ranked_f = sorted((f for _, f in c), key=key_rank)
        places = []
        for f in ranked_f:  # places of the strongest findings first; workstations last
            for rid in f.data.get("record_ids", []):
                pl = case.records[rid].place
                if pl and pl not in places:
                    places.append(pl)
        places.sort(key=lambda pl: any(k in case.records[next(r for r in rids if case.records[r].place == pl)].attrs
                                       for k in ("computer", "host", "hostname", "workstation")))
        key_rec = case.records[ranked_f[0].data["record_ids"][0]]
        if key_rec.place in places:
            places.remove(key_rec.place)
            places.insert(0, key_rec.place)
        persons = sorted({p for r in rids for p, _, _ in ctx.persons_for(case.records[r])})
        items.append(Item(
            "episode", stable_key("episode", iso(c[0][0])),
            f"Key event {key_rec.ts.astimezone(tz):%a %d %b %H:%M}" + (f" at {case.place_name(places[0])}" if places else ""),
            f"{len(c)} unusual records between {start.astimezone(tz):%H:%M} and {end.astimezone(tz):%H:%M}"
            + (f" involving {', '.join(case.place_name(pl) for pl in places[:4])}" if places else "") + ".",
            certainty="observed", score=round(weight(c), 2),
            citations=[cc for _, f in c for cc in f.citations][:8],
            data={"start": iso(start), "end": iso(end), "places": places, "persons": persons, "record_ids": rids,
                  "findings": [f.key for _, f in c], "key_time": iso(key_rec.ts), "key_record": key_rec.id}))
    return items
