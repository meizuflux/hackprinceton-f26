"""Photos and video on the board (backend/MEDIA.md): one observed card per `media` row and rule-backed links.

Everything here is deterministic and cites records: a card cites its file's media_capture record, and a link cites
the records on both ends. Nothing is written to case.db and nothing here reaches claims, contradictions,
explanations, gaps or insights: media cards are added to the board after those are final.
"""

from __future__ import annotations

import json
import mimetypes
import posixpath
import re
from collections import defaultdict

from .store import haversine_m

PLACE_RADIUS_M = 150.0  # a GPS fix this close to a clustered place is read as "at that place" (an inference)
MEDIA_COLUMN = 5        # placeholder column for the backend layout; the frontend lays live cases out itself


def media_rows(case) -> list[dict]:
    """The `media` table joined to each file's evidence ID, path and media_capture record (citation)."""
    rec_of_file: dict[int, int] = {}
    for r in case.records.values():
        if r.type == "media_capture" and r.duplicate_of is None:
            rec_of_file.setdefault(r.file_id, r.id)
    out = []
    for m in case.conn.execute("SELECT * FROM media ORDER BY media_id"):
        m = dict(m)
        f = case.files.get(m["file_id"])
        rid = rec_of_file.get(m["file_id"])
        if not f or rid is None or m["media_kind"] not in ("photo", "video"):
            continue  # audio and files without a capture record have no card
        meta = json.loads(m.get("metadata_json") or "{}")
        m.update(evidence_id=f["external_id"] or f"FILE-{f['file_id']}", path=f["original_path"], record_id=rid,
                 sha256=f["sha256"], meta=meta, flags=json.loads(m.get("time_flags") or "[]"))
        out.append(m)
    return out


def media_type(m: dict) -> str | None:
    rec_mime = m["meta"].get("mime_type")
    if rec_mime:
        return rec_mime
    fmt = m["meta"].get("format")
    if fmt:
        return f"image/{str(fmt).lower().replace('jpg', 'jpeg')}"
    return mimetypes.guess_type(m["path"])[0]


def _export_rows(case) -> dict[str, tuple]:
    """clip file name -> (export record, camera entity id | None, camera name): any record whose attributes name a
    `clip_file` (the VMS export index)."""
    out: dict[str, tuple] = {}
    for r in case.records.values():
        clip = r.attrs.get("clip_file")
        if not clip or r.duplicate_of is not None:
            continue
        cam = next((e for e, role in r.entities if role == "device" and case.etype(e) == "device"), None)
        name = case.name(cam) if cam is not None else (r.attrs.get("camera_id") or r.actor)
        if name:
            out.setdefault(posixpath.basename(str(clip)), (r, cam, name))
    return out


def camera_of_clip(case) -> dict[str, str]:
    """clip file name -> camera ID named by the export row that lists it."""
    return {clip: str(rec.attrs.get("camera_id") or name) for clip, (rec, _, name) in _export_rows(case).items()}


def _label(m: dict, camera: str | None) -> str:
    name = posixpath.basename(m["path"])
    if m["media_kind"] == "video":
        return f"CCTV clip · {camera}" if camera else f"Video · {name}"
    return f"Photo · {name}"


def _summary(m: dict, camera: str | None) -> str:
    bits = [f"{m['media_kind'].capitalize()} {posixpath.basename(m['path'])}"]
    if camera:
        bits.append(f"exported from camera {camera}")
    device = " ".join(x for x in (m["device_make"], m["device_model"]) if x)
    if device:
        bits.append(f"device {device}")
    if m["captured_utc"]:
        bits.append(f"time {m['captured_utc']} ({m['captured_source']})")
    if m["duration_s"]:
        bits.append(f"{m['duration_s']:g} s")
    return ", ".join(bits)


def add_media(case, R, nodes: dict, edges: dict, src, vision: dict | None = None) -> dict:
    """Add media cards and rule-backed links to the board dicts. `src(citation) -> source id` registers a citation.
    `vision` maps evidence ID to a vision description (see vision.py). Returns counts for the trace."""
    exports = _export_rows(case)
    centroids = []  # (node id, lat, lon): place clusters already on the board, with the record cited by that node
    for s in R.get("signal"):
        c = s.data.get("centroid")
        nid = f"sig-{s.key}"
        if s.data.get("signal_type") == "place_cluster" and c and nid in nodes:
            centroids.append((nid, float(c[0]), float(c[1])))
    linked_entities = defaultdict(set)
    for link in case.links:
        linked_entities[link["entity_a"]].add(link["entity_b"])
        linked_entities[link["entity_b"]].add(link["entity_a"])
    canon = lambda e: case.entities[e]["canonical_id"] or e  # noqa: E731

    def edge(a, b, etype, label, citations, certainty, basis, rule):
        eid = f"{etype}:{a}:{b}"
        citations = list(dict.fromkeys(citations))
        if eid not in edges and a in nodes and b in nodes and a != b and citations:
            edges[eid] = {"id": eid, "source": a, "target": b, "type": etype, "label": label,
                          "citations": citations[:8], "certainty": certainty, "basis": basis[:200], "directed": False,
                          "origin": "rules", "stage": "media_links", "rule": rule}

    cards: list[tuple[dict, str]] = []
    for m in media_rows(case):
        ex = exports.get(posixpath.basename(m["path"])) if m["media_kind"] == "video" else None
        camera = ex[2] if ex else None
        cite = src(case.cite(m["record_id"]))
        nid = f"media-{m['evidence_id']}"
        gps = {"lat": m["gps_lat"], "lon": m["gps_lon"]} if m["gps_lat"] is not None and m["gps_lon"] is not None else None
        info = {"evidenceId": m["evidence_id"], "kind": m["media_kind"], "mediaType": media_type(m),
                "capturedUtc": m["captured_utc"], "captureSource": m["captured_source"], "timeFlags": m["flags"],
                "durationS": m["duration_s"], "width": m["width"], "height": m["height"],
                "deviceMake": m["device_make"], "deviceModel": m["device_model"], "gps": gps}
        v = (vision or {}).get(m["evidence_id"])
        if v:
            info["vision"] = {**v, "citations": [cite]}
        nodes[nid] = {"id": nid, "type": "event", "label": _label(m, camera)[:60], "citations": [cite],
                      "position": {"x": 0, "y": 0}, "summary": _summary(m, camera)[:400],
                      "subtitle": "video clip" if m["media_kind"] == "video" else "photo", "certainty": "observed",
                      "origin": "record", "stage": "ingest", "media": info,
                      **({"time": m["captured_utc"]} if m["captured_utc"] else {})}
        cards.append((m, nid))

        # vms_export: the clip joins the camera named by the export row that lists its file
        if ex:
            rec, cam, name = ex
            cnid = f"ent-{canon(cam)}" if cam is not None else f"cam-{name}"
            export_cite = src(case.cite(rec.id))
            if cnid not in nodes:
                nodes[cnid] = {"id": cnid, "type": "device", "label": name[:60], "citations": [export_cite],
                               "position": {"x": 0, "y": 0}, "summary": f"Camera {name}, named in the VMS export index.",
                               "subtitle": "camera", "certainty": "observed", "origin": "record", "stage": "media_links"}
            else:
                nodes[cnid]["citations"] = list(dict.fromkeys(nodes[cnid]["citations"] + [export_cite]))[:12]
            edge(nid, cnid, "temporal", "recorded by camera", [cite, export_cite], "observed",
                 f"vms_export: {rec.attrs.get('record_id') or 'export row'} lists {posixpath.basename(m['path'])} for {name}",
                 "vms_export")

    # capture_device: the exact EXIF device entity. Joins an existing card for that entity or an explicitly linked
    # one (entity_links); otherwise photos that share the device get one device card. No name matching.
    by_device: dict[int, list[tuple[dict, str]]] = defaultdict(list)
    for m, nid in cards:
        if m["media_kind"] != "photo":
            continue
        rec = case.records[m["record_id"]]
        dev = next((canon(e) for e, role in rec.entities if role == "capture_device"), None)
        if dev is not None:
            by_device[dev].append((m, nid))
    for dev, items in by_device.items():
        targets = [f"ent-{e}" for e in [dev, *sorted(linked_entities.get(dev, ()))] if f"ent-{e}" in nodes]
        rule_basis = "capture_device: EXIF device matches an explicitly linked entity" if targets else None
        if not targets and len(items) >= 2:
            tid = f"ent-{dev}"
            cites = [nodes[n]["citations"][0] for _, n in items][:12]
            nodes[tid] = {"id": tid, "type": "device", "label": case.name(dev)[:60], "citations": cites,
                          "position": {"x": 0, "y": 0}, "subtitle": "capture device", "certainty": "observed",
                          "summary": f"{case.name(dev)} recorded in the EXIF data of {len(items)} photos.",
                          "origin": "record", "stage": "media_links"}
            targets, rule_basis = [tid], f"capture_device: the same EXIF device is recorded on {len(items)} photos"
        for m, nid in items:
            for t in targets[:1]:
                edge(nid, t, "temporal", "captured with", [nodes[nid]["citations"][0], nodes[t]["citations"][0]],
                     "observed", f"{rule_basis}: {case.name(dev)}", "capture_device")

    # place: a GPS fix inside a place cluster already on the board (inferred; the distance is in the basis)
    for m, nid in cards:
        if m["gps_lat"] is None or m["gps_lon"] is None:
            continue
        near = sorted((haversine_m(m["gps_lat"], m["gps_lon"], la, lo), t) for t, la, lo in centroids)
        if near and near[0][0] <= PLACE_RADIUS_M:
            d, t = near[0]
            edge(nid, t, "spatial", "photographed at", [nodes[nid]["citations"][0], nodes[t]["citations"][0]],
                 "inferred", f"place: EXIF GPS is {d:.0f} m from the centre of {nodes[t]['label'][:80]}", "place")

    _directory_links(case, R, nodes, cards, exports, edge, src)

    counts = {"media": len(cards), "edges": 0}
    for e in edges.values():
        if e.get("stage") == "media_links":
            counts["edges"] += 1
            counts[e["rule"]] = counts.get(e["rule"], 0) + 1
    return counts


CLIP_SLACK_S = 60  # an event this close to a clip's start or end counts as "during the clip"


def _directory_links(case, R, nodes: dict, cards: list, exports: dict, edge, src) -> None:
    """Links through the case's facility directory (labels.Directory), the MANIFEST.csv row of each media file and the
    records behind event cards. Every link cites the media record and the records on the other end; the directory row
    is cited whenever it places a camera or names a room."""
    from .labels import Directory
    from .store import parse_ts

    D = Directory(case)
    locs = [(nid, n) for nid, n in nodes.items() if nid.startswith("loc-")]

    def room_locs(room: str) -> list[str]:
        """Location cards named after the room, or naming a directory entry in it."""
        out = []
        for nid, n in locs:
            p = D.find(n["label"])
            if n["label"].casefold() == room.casefold() or (p and p.room.casefold() == room.casefold()):
                out.append(nid)
        return out

    def cite_of(nid: str) -> list[str]:
        return nodes[nid]["citations"][:1]

    persons = {}
    for eid, e in case.entities.items():
        if e["entity_type"] == "person":
            canon = e["canonical_id"] or eid
            for name in (e["display_name"], e["value_norm"]):
                if name:
                    persons.setdefault(name.casefold(), canon)

    items = {it.key: it for b in R.items.values() for it in b}
    events = []  # (node id, [records]) for record-backed event cards already on the board
    for nid, n in nodes.items():
        if n.get("media") or n["type"] != "event":
            continue
        if nid.startswith("rec-"):
            rids = [int(nid[4:])]
        elif nid.startswith("ev-") and n.get("key") in items:
            rids = items[n["key"]].data.get("record_ids") or []
        else:
            continue
        recs = [case.records[r] for r in rids if r in case.records and case.records[r].ts]
        if recs:
            events.append((nid, recs))

    for m, nid in cards:
        f = case.files.get(m["file_id"]) or {}
        man = f.get("manifest") or {}
        mcite = nodes[nid]["citations"][0]

        # custodian: the MANIFEST.csv custodian is, by exact name, a person card on the board
        cust = persons.get(str(man.get("custodian") or "").casefold())
        if cust is not None and f"ent-{cust}" in nodes:
            pid = f"ent-{cust}"
            edge(nid, pid, "temporal", "collected from", [mcite, *cite_of(pid)], "observed",
                 f"custodian: MANIFEST.csv lists {case.name(cust)} as the custodian of {m['evidence_id']}", "custodian")

        # camera_place: a clip's camera, placed in a room by the directory, joins location cards for that room
        cam = None
        if m["media_kind"] == "video":
            ex = exports.get(posixpath.basename(m["path"]))
            cam = D.find(str(ex[0].attrs.get("camera_id") or ex[2])) if ex else None
        if cam and cam.room:
            for loc in room_locs(cam.room):
                edge(nid, loc, "spatial", "filmed in", [mcite, src(case.cite(cam.record_id)), *cite_of(loc)],
                     "inferred", f"camera_place: the directory places camera {cam.id} in “{cam.room}”, "
                                 f"which names this location", "camera_place")

        # title_place: the MANIFEST.csv title names a directory ID or a room ("Scene photo: EBC cabinet SC-EBC-01")
        title = str(man.get("title") or "")
        named: list[tuple[str, list[str], int]] = []  # (what the title names, location cards, directory record)
        for pid, p in D.by_id.items():
            if re.search(rf"(?<![\w-]){re.escape(pid)}(?![\w-])", title):
                named.append((pid, [loc for loc, n in locs if D.find(n["label"]) is p], p.record_id))
        spans: list[tuple[int, int]] = []
        for room in D.rooms():
            hit = re.search(rf"(?<![\w-]){re.escape(room)}(?![\w-])", title, re.I)
            if hit and not any(a <= hit.start() and hit.end() <= b for a, b in spans):
                spans.append(hit.span())
                named.append((room, room_locs(room), D.in_room(room)[0].record_id))
        for what, targets, dir_rec in named:
            for loc in targets:
                edge(nid, loc, "spatial", "pictured at" if m["media_kind"] == "photo" else "shows",
                     [mcite, src(case.cite(dir_rec)), *cite_of(loc)], "inferred",
                     f"title_place: the MANIFEST.csv title “{title[:80]}” names {what}", "title_place")

        # same_place_time: an event recorded on the camera's floor while the clip runs ("same place, nearby time")
        if not (cam and cam.floor and cam.floor.lower() != "all" and m["captured_utc"] and m["duration_s"]):
            continue
        t0 = parse_ts(m["captured_utc"])
        start, end = t0.timestamp() - CLIP_SLACK_S, t0.timestamp() + float(m["duration_s"]) + CLIP_SLACK_S
        for enid, recs in events:
            for r in recs:
                q = D.for_record(r)
                if not (q and q.floor == cam.floor and start <= r.ts.timestamp() <= end):
                    continue
                same_room = bool(q.room) and q.room.casefold() == cam.room.casefold()
                rc = src(case.cite(r.id))
                cites = [mcite, rc] + ([] if rc in nodes[enid]["citations"] else cite_of(enid)) + \
                        [src(case.cite(cam.record_id)), src(case.cite(q.record_id))]
                where = f"room “{q.room}”" if same_room else f"floor {cam.floor}"
                edge(nid, enid, "temporal", f"same {'room' if same_room else 'floor'}, during clip", cites, "inferred",
                     f"same_place_time: {case.cite(r.id)['id']} ({q.name}) is on {where}, like camera {cam.id}, "
                     f"within {CLIP_SLACK_S} s of the clip", "same_place_time")
                break
