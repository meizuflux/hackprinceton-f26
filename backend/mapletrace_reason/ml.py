"""Stage 0: traditional ML signals (clustering and classification), run first in the reasoning pipeline.

Every model here is unsupervised or weakly supervised from rules on the evidence itself; nothing is trained
on an answer key. Each output is a `signal` item: a cited lead with the model, its parameters and the input
records, never a conclusion. Signals are their own kind, so they add to the board and give the investigator
agent more to work with without changing the findings, explanations or gaps that later stages compute.

    place_clusters     DBSCAN (haversine) on each subject's location points -> home / work / recurring evening places
    routine_outliers   IsolationForest on per-day movement profiles -> days that break a subject's routine
    message_triage     TF-IDF + logistic regression, weakly labelled -> automated/spam vs human messages
    identity_clusters  character TF-IDF + agglomerative clustering, gated by name rules -> likely name variants

All models use fixed seeds and deterministic solvers, so the same case.db always gives the same signals.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

from .analytics import Context, case_tz
from .model import Item, stable_key
from .store import haversine_m

RANDOM_STATE = 7
EARTH_RADIUS_M = 6371000.0


def run(ctx: Context) -> list[Item]:
    """All ML signals for a case, in a stable order. A model that has too little data simply returns nothing."""
    places = place_clusters(ctx)
    return places + routine_outliers(ctx, places) + message_triage(ctx) + identity_clusters(ctx)


# --------------------------------------------------------------------------- shared helpers
def _accuracy_m(rec) -> float:
    for k in ("accuracy_m", "est_radius_m", "radius"):
        try:
            v = float(rec.attrs.get(k) or 0)
        except (TypeError, ValueError):
            v = 0.0
        if v:
            return v
    return 50.0


def _located_by_subject(ctx: Context) -> dict[int, list]:
    out: dict[int, list] = defaultdict(list)
    for r in ctx.case.timed:
        if r.lat is None or r.lon is None:
            continue
        if _accuracy_m(r) > 5000:  # timing-advance-only fixes are too vague to cluster
            continue
        subj = ctx.subject_of(r)
        if subj is not None:
            out[subj].append(r)
    return out


def _sample(ids: list[int], n: int = 6) -> list[int]:
    if len(ids) <= n:
        return ids
    step = len(ids) / n
    return [ids[int(i * step)] for i in range(n)]


# --------------------------------------------------------------------------- place clusters (DBSCAN)
def _cluster_label(case, recs, centroid) -> str:
    names = Counter(r.attrs.get("name") or r.place for r in recs if r.type == "place_visit" and (r.attrs.get("name") or r.place))
    if names:
        return names.most_common(1)[0][0]
    # coarse points (cell sites) have no name: borrow the nearest named place from any precise source
    best, best_d = None, 1500.0
    for r in case.timed:
        if r.type == "place_visit" and r.lat is not None and (r.attrs.get("name") or r.place):
            d = haversine_m(centroid[0], centroid[1], r.lat, r.lon)
            if d < best_d:
                best, best_d = r.attrs.get("name") or r.place, d
    if best:
        return f"area near {best} (~{int(round(best_d, -2))} m)"
    return f"area around {centroid[0]:.4f}, {centroid[1]:.4f}"


def place_clusters(ctx: Context, min_points: int = 20) -> list[Item]:
    import numpy as np
    from sklearn.cluster import DBSCAN

    case, tz = ctx.case, case_tz(ctx.case)
    items = []
    for subj, recs in sorted(_located_by_subject(ctx).items()):
        if len(recs) < min_points:
            continue
        acc = sorted(_accuracy_m(r) for r in recs)
        coarse = acc[len(acc) // 2] > 300
        eps_m = 800.0 if coarse else 200.0
        X = np.radians(np.array([[r.lat, r.lon] for r in recs]))
        labels = DBSCAN(eps=eps_m / EARTH_RADIUS_M, min_samples=3, metric="haversine", algorithm="ball_tree").fit(X).labels_
        clusters: dict[int, list] = defaultdict(list)
        for lab, r in zip(labels, recs):
            if lab >= 0:
                clusters[int(lab)].append(r)
        if not clusters:
            continue
        all_weekdays = {r.ts.astimezone(tz).date() for r in recs if r.ts.astimezone(tz).weekday() < 5}
        stats = []
        for lab, rs in clusters.items():
            local = [r.ts.astimezone(tz) for r in rs]
            days = {t.date() for t in local}
            night = sum(1 for t in local if t.hour < 6 or t.hour >= 23) / len(rs)
            weekdays = {t.date() for t in local if t.weekday() < 5 and 7 <= t.hour < 19}
            evening_days = {t.date() for t in local if t.hour >= 18}
            centroid = (sum(r.lat for r in rs) / len(rs), sum(r.lon for r in rs) / len(rs))
            stats.append({"label": lab, "recs": rs, "days": days, "night": night, "weekdays": weekdays,
                          "evening_days": evening_days, "centroid": centroid})
        home = max(stats, key=lambda s: (s["night"] * len(s["recs"]), len(s["days"]), len(s["recs"])))
        others = [s for s in stats if s is not home]
        work = max(others, key=lambda s: (len(s["weekdays"]), len(s["recs"]))) if others else None
        if work and len(work["weekdays"]) < max(3, 0.25 * len(all_weekdays)):
            work = None
        method = {"name": "DBSCAN (haversine)", "eps_m": eps_m, "min_samples": 3, "points": len(recs),
                  "clusters": len(stats), "noise_points": int((labels < 0).sum()),
                  "roles": "home = most night-time points; work = present on the most weekdays 07-19 "
                           "(at least a quarter of observed weekdays)"}
        for role, s in (("home", home), ("work", work)):
            if not s:
                continue
            label = _cluster_label(case, s["recs"], s["centroid"])
            ids = [r.id for r in s["recs"]]
            items.append(Item(
                "signal", stable_key("ml-place", case.name(subj), role, round(s["centroid"][0], 3), round(s["centroid"][1], 3)),
                f"Likely {role} of {case.name(subj)}: {label}",
                f"Clustering {len(recs)} location points for {case.name(subj)} groups {len(ids)} of them here on "
                f"{len(s['days'])} days ({'night-time share ' + format(s['night'], '.0%') if role == 'home' else 'present on ' + str(len(s['weekdays'])) + ' of ' + str(len(all_weekdays)) + ' observed weekdays'}). "
                "This is a statistical label from location data, not a confirmed address.",
                certainty="inferred", score=0.3, citations=[case.cite(i) for i in _sample(ids)],
                data={"signal_type": "place_cluster", "role": role, "subject": subj, "label": label,
                      "centroid": [round(s["centroid"][0], 5), round(s["centroid"][1], 5)], "days": len(s["days"]),
                      "method": method, "record_ids": ids[:300]}))
        for s in sorted(others, key=lambda s: -len(s["evening_days"])):
            if s is work or len(s["evening_days"]) < 3:
                continue
            label = _cluster_label(case, s["recs"], s["centroid"])
            ev = sorted(s["evening_days"])
            ids = [r.id for r in s["recs"] if r.ts.astimezone(tz).hour >= 18]
            items.append(Item(
                "signal", stable_key("ml-evening", case.name(subj), round(s["centroid"][0], 3), round(s["centroid"][1], 3)),
                f"Recurring evening place for {case.name(subj)}: {label}",
                f"{case.name(subj)}'s location data clusters here on {len(ev)} different evenings "
                f"({ev[0]:%d %b} to {ev[-1]:%d %b}), away from their likely home"
                + (" and work" if work else "") + " clusters. A repeated evening place is a lead to check, not evidence of "
                "who else was there." + (" Points are cell-site areas, so the place is approximate." if coarse else ""),
                certainty="inferred", score=round(min(0.85, 0.35 + 0.06 * len(ev)), 2),
                citations=[case.cite(i) for i in _sample(ids)],
                data={"signal_type": "place_cluster", "role": "recurring_evening", "subject": subj, "label": label,
                      "centroid": [round(s["centroid"][0], 5), round(s["centroid"][1], 5)],
                      "evenings": [str(d) for d in ev], "approximate": coarse, "method": method, "record_ids": ids[:300]}))
    return items


# --------------------------------------------------------------------------- routine outliers (IsolationForest)
def routine_outliers(ctx: Context, place_signals: list[Item], min_days: int = 14, per_subject: int = 3) -> list[Item]:
    import numpy as np
    from sklearn.ensemble import IsolationForest

    case, tz = ctx.case, case_tz(ctx.case)
    homes = {s.data["subject"]: s.data["centroid"] for s in place_signals if s.data.get("role") == "home"}
    items = []
    for subj, recs in sorted(_located_by_subject(ctx).items()):
        if subj not in homes:
            continue
        hlat, hlon = homes[subj]
        by_day: dict = defaultdict(list)
        for r in recs:
            by_day[r.ts.astimezone(tz).date()].append(r)
        if len(by_day) < min_days:
            continue
        days = sorted(by_day)
        feats, why = [], []
        for d in days:
            rs = by_day[d]
            local = [(r, r.ts.astimezone(tz), haversine_m(hlat, hlon, r.lat, r.lon)) for r in rs]
            away = [(r, t, dist) for r, t, dist in local if dist > 1000]
            late_away = [t for _, t, _ in away if t.hour >= 21 or t.hour < 2]
            max_km = max((dist for _, _, dist in local), default=0) / 1000
            last_away_hour = max(((t.hour + t.minute / 60) if t.hour >= 12 else 24 + t.hour + t.minute / 60
                                  for _, t, _ in away), default=0.0)
            cells = len({(round(r.lat, 2), round(r.lon, 2)) for r in rs})
            feats.append([math.log1p(len(rs)), cells, max_km, len(late_away), last_away_hour,
                          1.0 if d.weekday() >= 5 else 0.0])
            why.append({"points": len(rs), "distinct_areas": cells, "max_km_from_home": round(max_km, 1),
                        "late_points_away": len(late_away), "last_away_hour": round(last_away_hour, 1),
                        "record_ids": [r.id for r, _, _ in (away or local)]})
        X = np.array(feats)
        cont = min(0.1, max(0.02, 3 / len(days)))
        model = IsolationForest(n_estimators=300, contamination=cont, random_state=RANDOM_STATE).fit(X)
        raw = -model.score_samples(X)
        flagged = model.predict(X) == -1
        order = sorted(range(len(days)), key=lambda i: (-raw[i], days[i]))
        med = {k: float(np.median(X[:, j])) for j, k in enumerate(["points", "areas", "max_km", "late", "last_hour", "weekend"])}
        picked = 0
        for i in order:
            if not flagged[i] or picked >= per_subject:
                continue
            w = why[i]
            reasons = []
            if w["late_points_away"] > med["late"]:
                reasons.append(f"{w['late_points_away']} records away from home after 21:00 (typical: {med['late']:.0f})")
            if w["max_km_from_home"] > med["max_km"] * 1.5:
                reasons.append(f"up to {w['max_km_from_home']} km from home (typical: {med['max_km']:.1f} km)")
            if w["last_away_hour"] > med["last_hour"] + 1:
                h = w["last_away_hour"] % 24
                reasons.append(f"still away from home at about {int(h):02d}:{int(h % 1 * 60):02d}")
            if w["distinct_areas"] > med["areas"] + 2:
                reasons.append(f"{w['distinct_areas']} distinct areas (typical: {med['areas']:.0f})")
            if not reasons:
                continue  # unusual only in ways we cannot explain in plain words: leave it out
            picked += 1
            d = days[i]
            ids = w["record_ids"]
            items.append(Item(
                "signal", stable_key("ml-routine", case.name(subj), str(d)),
                f"Unusual day for {case.name(subj)}: {d:%a %d %b %Y}",
                f"Compared with {len(days)} days of their own location data, this day stands out: " + "; ".join(reasons)
                + ". An unusual day is a lead for where to look, not evidence of wrongdoing.",
                certainty="inferred", score=round(float(min(0.8, 0.3 + raw[i] - raw.mean())), 2),
                citations=[case.cite(r) for r in _sample(ids)],
                data={"signal_type": "routine_outlier", "subject": subj, "day": str(d), "features": {k: v for k, v in w.items() if k != "record_ids"},
                      "method": {"name": "IsolationForest on daily movement profiles", "n_estimators": 300,
                                 "contamination": round(cont, 3), "random_state": RANDOM_STATE, "days": len(days),
                                 "features": ["log(points)", "distinct areas", "max km from home", "points away after 21:00",
                                              "last hour away from home", "weekend"]},
                      "record_ids": ids[:300]}))
    return items


# --------------------------------------------------------------------------- message triage (classification)
_AUTO_TEXT = re.compile(r"\b(code|passcode|verification|otp)\b[^.]*\d{4,}|reply stop|unsubscribe|opt out|has shipped|"
                        r"was delivered|card ending \d{4}|flash sale|% off|congratulations!? you|tap to claim|"
                        r"selected for an exclusive", re.I)
_SHORTCODE = re.compile(r"^[A-Z0-9][A-Z0-9\-_ ]{2,}$")


def message_triage(ctx: Context, min_per_class: int = 5) -> list[Item]:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold, cross_val_score

    case = ctx.case
    msgs = sorted((r for r in case.records.values() if r.type == "message" and not r.duplicate_of and r.content.strip()),
                  key=lambda r: r.id)
    if not msgs:
        return []
    thread_senders: dict = defaultdict(set)
    for r in msgs:
        tkey = (r.file_id, r.attrs.get("thread_id") or r.attrs.get("thread_name") or "")
        thread_senders[tkey] |= {e for e, role in r.entities if role == "sender"}
    seeds = {}
    for r in msgs:
        senders = [e for e, role in r.entities if role == "sender"]
        sname = case.name(senders[0]) if senders else (r.actor or "")
        tkey = (r.file_id, r.attrs.get("thread_id") or r.attrs.get("thread_name") or "")
        if _AUTO_TEXT.search(r.content) or (_SHORTCODE.match(sname) and not re.search(r"\d{7,}", sname)):
            seeds[r.id] = 1
        elif len(thread_senders[tkey]) >= 2 and any(case.etype(e) in ("person", "phone") for e in senders):
            seeds[r.id] = 0
    labels = Counter(seeds.values())
    if labels.get(0, 0) < min_per_class or labels.get(1, 0) < min_per_class:
        return []
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1)
    X_all = vec.fit_transform([r.content.lower() for r in msgs])
    idx = {r.id: i for i, r in enumerate(msgs)}
    seed_ids = sorted(seeds)
    Xs, ys = X_all[[idx[i] for i in seed_ids]], np.array([seeds[i] for i in seed_ids])
    clf = LogisticRegression(solver="liblinear", C=2.0, class_weight="balanced", max_iter=1000, random_state=RANDOM_STATE)
    folds = min(5, labels[0], labels[1])
    cv = cross_val_score(clf, Xs, ys, cv=StratifiedKFold(n_splits=folds, shuffle=True, random_state=RANDOM_STATE)) \
        if folds >= 2 else np.array([float("nan")])
    clf.fit(Xs, ys)
    prob = clf.predict_proba(X_all)[:, 1]
    method = {"name": "TF-IDF (char 3-5 grams) + logistic regression, weakly labelled", "C": 2.0,
              "seed_automated": labels[1], "seed_human": labels[0], "cv_accuracy_on_seeds": round(float(cv.mean()), 3),
              "seed_rules": "automated: one-time codes, delivery/bank/marketing phrases, short-code senders; "
                            "human: two-way threads between people or phone numbers", "threshold": 0.5}
    by_file: dict[int, list] = defaultdict(list)
    for r in msgs:
        by_file[r.file_id].append((r, float(prob[idx[r.id]])))
    items = []
    for fid, rows in sorted(by_file.items()):
        auto = [(r, p) for r, p in rows if p >= 0.5]
        if not auto:
            continue
        human_only_threads = Counter((r.attrs.get("thread_name") or r.attrs.get("thread_id") or "?") for r, p in rows if p < 0.5)
        auto_threads = Counter((r.attrs.get("thread_name") or r.attrs.get("thread_id") or "?") for r, _ in auto)
        disagreements = [r.id for r, p in rows if r.id in seeds and (p >= 0.5) != bool(seeds[r.id])]
        path = case.files[fid]["original_path"].split("::")[-1].rsplit("/", 1)[-1]
        ids = [r.id for r, _ in sorted(auto, key=lambda x: -x[1])]
        items.append(Item(
            "signal", stable_key("ml-triage", path),
            f"Message triage for {path}: {len(auto)} of {len(rows)} look automated or spam",
            f"A text classifier marks {len(auto)} of {len(rows)} messages as automated or spam (mostly in "
            + ", ".join(f"{t} ({n})" for t, n in auto_threads.most_common(3))
            + f"); {len(rows) - len(auto)} look like human conversation. Reading can start with the human threads. "
            "Classification is probabilistic; nothing is deleted or hidden.",
            certainty="inferred", score=0.25, citations=[case.cite(i) for i in _sample(ids, 4)],
            data={"signal_type": "message_triage", "file": case.files[fid]["original_path"], "messages": len(rows),
                  "automated_record_ids": ids, "automated_threads": dict(auto_threads),
                  "human_threads": dict(human_only_threads), "seed_disagreements": disagreements[:50],
                  "method": method, "record_ids": ids[:300]}))
    return items


# --------------------------------------------------------------------------- identity clusters (record linkage)
_TITLES = re.compile(r"^(det|dr|mr|mrs|ms|cst|officer|sgt|lt)\.?\s+", re.I)
# ingestion can type facility labels ("Floor 2 east office door") as names; those are not people
_NOT_A_NAME = re.compile(r"\b(door|floor|office|lobby|camera|entrance|room|lab|suite|gate|reader|corridor|garage|level|"
                         r"building|cabinet|center|centre|checkpoint|elevator|dock|street|st|ave|road|inc|llc|ltd|co)\b|\d",
                         re.I)


def _name_tokens(s: str) -> list[str]:
    s = re.sub(r"<[^>]*>", "", s)
    s = re.sub(r"\([^)]*\)", "", s).strip()
    if ("@" in s and " " not in s) or _NOT_A_NAME.search(s):
        return []
    if "," in s:
        last, _, first = s.partition(",")
        s = f"{first.strip()} {last.strip()}"
    s = _TITLES.sub("", s.strip())
    toks = [t for t in re.findall(r"[a-z]+", s.lower()) if t]
    return toks if 2 <= len(toks) <= 4 else []


def _compatible(a: list[str], b: list[str]) -> bool:
    if len(a) < 2 or len(b) < 2 or a[-1] != b[-1]:
        return False
    fa, fb = a[0], b[0]
    return fa == fb or (len(fa) == 1 and fb.startswith(fa)) or (len(fb) == 1 and fa.startswith(fb))


def identity_clusters(ctx: Context, max_distance: float = 0.45) -> list[Item]:
    import numpy as np
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_distances

    case = ctx.case
    cands = []
    for eid in sorted(case.entities):
        e = case.entities[eid]
        if e["canonical_id"] not in (None, eid) or e["entity_type"] not in ("person", "email", "account"):
            continue
        toks = _name_tokens(case.name(eid))
        if len(toks) >= 2:
            cands.append((eid, toks))
    if len(cands) < 2:
        return []
    texts = [" ".join(t) for _, t in cands]
    X = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True).fit_transform(texts)
    D = cosine_distances(X)
    labels = AgglomerativeClustering(n_clusters=None, metric="precomputed", linkage="average",
                                     distance_threshold=max_distance).fit(D).labels_
    linked = {frozenset((l["entity_a"], l["entity_b"])) for l in case.links}
    # candidate pairs: same cluster, or same surname block (an initial shares too few characters to cluster)
    pairs: dict[tuple[int, int], str] = {}
    groups: dict[int, list[int]] = defaultdict(list)
    for i, lab in enumerate(labels):
        groups[int(lab)].append(i)
    for members in groups.values():
        for x in range(len(members)):
            for y in range(x + 1, len(members)):
                pairs[(members[x], members[y])] = "clustered"
    blocks: dict[str, list[int]] = defaultdict(list)
    for i, (_, toks) in enumerate(cands):
        blocks[toks[-1]].append(i)
    for members in blocks.values():
        for x in range(len(members)):
            for y in range(x + 1, len(members)):
                pairs.setdefault((members[x], members[y]), "surname block")
    record_for: dict[int, list[int]] = defaultdict(list)
    for r in case.records.values():
        for eid, _ in r.entities:
            if len(record_for[eid]) < 2:
                record_for[eid].append(r.id)
    items = []
    for (i, j), how in sorted(pairs.items()):
        (ea, ta), (eb, tb) = cands[i], cands[j]
        if frozenset((ea, eb)) in linked or not _compatible(ta, tb):
            continue
        sim = 1 - float(D[i, j])
        initial_only = ta[0] != tb[0]
        rids = record_for[ea][:1] + record_for[eb][:1]
        if len(rids) < 2:
            continue
        items.append(Item(
            "signal", stable_key("ml-identity", case.name(ea), case.name(eb)),
            f"{case.name(ea)} and {case.name(eb)} may be the same person",
            f"The two name forms {'cluster together' if how == 'clustered' else 'share a surname'} (character similarity "
            f"{sim:.2f}) and agree on surname and {'first initial' if initial_only else 'first name'}. Ingestion did not "
            "merge them because no record states it; confirm before relying on it."
            + (" An initial matches many people, so this is weaker." if initial_only else ""),
            certainty="inferred", score=round((0.15 if initial_only else 0.2) + 0.4 * sim, 2),
            citations=[case.cite(r) for r in rids],
            data={"signal_type": "identity_cluster", "entity_a": ea, "entity_b": eb, "similarity": round(sim, 3),
                  "candidate_by": how, "initial_only": initial_only,
                  "method": {"name": "record linkage: surname blocking + character TF-IDF agglomerative clustering, "
                                     "name-rule gated", "ngram_range": [2, 4], "linkage": "average",
                             "distance_threshold": max_distance,
                             "gate": "same surname and compatible first name or initial"},
                  "record_ids": rids}))
    return sorted(items, key=lambda it: (-it.score, it.title))


def signals_for_agent(results) -> list[dict]:
    """Compact view of ML signals for the investigator agent (read-only)."""
    rows = []
    for s in results.get("signal"):
        rows.append({"signal_id": s.id, "type": s.data.get("signal_type"), "title": s.title, "detail": s.text,
                     "score": s.score, "method": s.data.get("method", {}).get("name"),
                     "record_ids": s.data.get("record_ids", [])[:15], "citations": [c["id"] for c in s.citations[:6]]})
    return rows


__all__ = ["run", "place_clusters", "routine_outliers", "message_triage", "identity_clusters", "signals_for_agent"]
