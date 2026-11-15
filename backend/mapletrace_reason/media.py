"""Photos and video on the board (backend/MEDIA.md): one observed card per `media` row and rule-backed links.

Everything here is deterministic and cites records: a card cites its file's media_capture record, and a link cites
the records on both ends. Nothing is written to case.db and nothing here reaches claims, contradictions,
explanations, gaps or insights: media cards are added to the board after those are final.
"""

from __future__ import annotations

import json
import mimetypes
import posixpath
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

    counts = {"media": len(cards), "edges": 0}
    for e in edges.values():
        if e.get("stage") == "media_links":
            counts["edges"] += 1
            counts[e["rule"]] = counts.get(e["rule"], 0) + 1
    return counts
