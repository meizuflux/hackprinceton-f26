"""Build the Kestrel case: evidence files, manifest, upload ZIP, and ground truth. Deterministic."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import sys
import tempfile
import zipfile

from . import common, dna, location, logs, media, messages, texts, truth
from .cast import CASE_AS_OF, CASE_ID, CASE_TITLE
from .catalog import CATALOG
from .common import Out, Registry, iso_local

GENERATOR_VERSION = "1.0.0"
ZIP_NAME = "kestrel_case_upload.zip"
ZIP_TIME = (2026, 10, 22, 18, 0, 0)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_dna(g, mixes):
    """Assert that every inclusion/exclusion stated in the lab report holds for the generated alleles."""
    def contains(mix, prof):
        return all(set(prof[L]) <= mix[L] for L in prof)

    for who in ("K1", "K2", "K3"):
        assert g[who] != g["UF1"], f"{who} identical to UF1"
    assert contains(mixes["Q1"], g["K1"]) and contains(mixes["Q1"], g["K3"]) and contains(mixes["Q1"], g["UF1"])
    assert not contains(mixes["Q1"], g["K2"]), "K2 must be excluded from Q1"
    assert contains(mixes["Q2"], g["UF1"]), "UF1 must be included in Q2"
    assert not contains(mixes["Q2"], g["K1"]) and not contains(mixes["Q2"], g["K3"]), "K1/K3 excluded from Q2"


def write_manifest(out: Out):
    rows = []
    for e in CATALOG:
        p = out.path(e.path)
        rows.append([e.eid, e.path[len("evidence/"):], sha256_file(p), os.path.getsize(p), e.modality, e.fmt, e.title,
                     e.custodian, e.collected_by, e.collected_at, e.method, e.time_basis, e.sensitivity, e.admiralty,
                     "SYNTHETIC - FICTIONAL TRAINING DATA"])
    out.csv("evidence/MANIFEST.csv", ["evidence_id", "path", "sha256", "bytes", "modality", "format", "title",
                                      "custodian", "collected_by", "collected_at_local", "acquisition_method",
                                      "time_basis", "sensitivity", "admiralty_grade", "marking"], rows)


def write_zip(out: Out):
    members = ["evidence/MANIFEST.csv"] + [e.path for e in CATALOG]
    p = out._ensure(ZIP_NAME)
    with zipfile.ZipFile(p, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in sorted(members):
            info = zipfile.ZipInfo("kestrel_case/" + rel, date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(out.path(rel), "rb") as f:
                z.writestr(info, f.read(), compresslevel=9)


def case_readme() -> str:
    by_mod = {}
    for e in CATALOG:
        by_mod.setdefault(e.modality, []).append(e.eid)
    mods = "\n".join(f"| {m} | {len(v)} | {', '.join(v)} |" for m, v in sorted(by_mod.items()))
    return f"""# Kestrel case ({CASE_ID})

> **Synthetic and fictional.** Every person, company, phone number, plate, address and record here is invented
> for training and demonstrating Compstat. Any resemblance to real people or companies is coincidental.

**{CASE_TITLE}.** An unreleased AX-9 "Kestrel" GPU engineering sample disappeared from a secure cabinet in the
Executive Briefing Center of Aurion Compute, Inc. (a fictional GPU company) over the weekend of 2026-10-17.
The case file is current as of {iso_local(CASE_AS_OF)}.

Do not regenerate or edit these files by hand. Run `make data-generate` (or
`python generator/generate.py`) and check with `make data-verify`.

## Layout

| Path | What it is | Ship to the pipeline? |
| --- | --- | --- |
| `evidence/` | The original files, one per evidence item, plus `MANIFEST.csv` with SHA-256 hashes and provenance | Yes |
| `{ZIP_NAME}` | The demo upload: `evidence/` zipped under `kestrel_case/` | Yes (this is the demo ZIP) |
| `truth/` | Answer key and labels: solution, facts, insights, gaps, questions, record labels, annotations | **No.** Evaluation and training only |
| `BUILD_INFO.json` | Seed, versions and the hash of every generated file | No |

## Evidence by modality

| Modality | Count | Evidence IDs |
| --- | --- | --- |
{mods}

## Labels and classification

- `evidence/MANIFEST.csv`: provenance and classification for each file: custodian, collector, acquisition
  method, time basis (UTC, local, epoch, burned-in), sensitivity label, and an Admiralty grade (source
  reliability A-F, information credibility 1-6).
- `truth/record_labels.csv`: one row per record (badge event, message, cell record, scan, frame-free media
  file, tagged document line) with `relevance` in key / supporting / context / red_herring / background / noise,
  a `noise_type` where applicable, and the key tags it supports.
- `truth/key_locators.json`: every named locator (for example `CAB_1017_EXEC_OPEN -> EV-071 seq=...`).
- `truth/facts.json`, `insights.json`, `gaps.json`, `questions.json`, `red_herrings.json`, `artifact_value.json`:
  the expected reasoning output, each item citing exact locators.
- `truth/video_tracks.jsonl` and `truth/photo_annotations.json`: per-frame boxes and identities for the CCTV
  clips, and object boxes for the photos.

Timestamps deliberately mix formats (UTC, local without offset, epoch milliseconds, US 12-hour, a reader with
clock drift) and include duplicates, misreads, missed RFID reads, spam and low-confidence location points, so
the cleaning step has real work to do. Every noise record is labelled with its `noise_type`.

Protected attributes (for example `visitor_log.id_issuing_country`) must not be used as features.
"""


def build(root: str, seed: str = common.DEFAULT_SEED) -> dict:
    common.SEED = seed
    if os.path.isdir(root):
        for name in ("evidence", "truth"):
            shutil.rmtree(Out(root).path(name), ignore_errors=True)
    out = Out(root)
    reg = Registry()
    logs.write_all(out, reg)
    messages.write_all(out, reg)
    location.write_all(out, reg)
    g, mixes = dna.write_all(out, reg)
    check_dna(g, mixes)
    texts.write_all(out, reg)
    media.write_all(out, reg)
    out.jsonl("truth/video_tracks.jsonl", media.ANN_TRACKS)
    out.json("truth/photo_annotations.json", media.ANN_PHOTOS)
    truth.write_all(out, reg)
    missing = [e.eid for e in CATALOG if not os.path.exists(out.path(e.path))]
    assert not missing, f"catalog entries without files: {missing}"
    write_manifest(out)
    write_zip(out)
    out.text("README.md", case_readme())
    files = {}
    for rel in sorted(out.written):
        files[rel] = sha256_file(out.path(rel))
    import imageio_ffmpeg
    import numpy
    import PIL
    import piexif
    info = {"generator_version": GENERATOR_VERSION, "seed": seed, "case_id": CASE_ID,
            "python": platform.python_version(),
            "libraries": {"numpy": numpy.__version__, "Pillow": PIL.__version__, "piexif": piexif.VERSION,
                          "imageio-ffmpeg": imageio_ffmpeg.__version__,
                          "ffmpeg": imageio_ffmpeg.get_ffmpeg_version()},
            "note": "Text, CSV and JSON outputs are byte-stable across platforms. JPEG, MP4 and ZIP bytes are stable "
                    "for the pinned library versions in generator/requirements.txt.",
            "files": files}
    out.json("BUILD_INFO.json", info)
    return info


def verify(root: str) -> int:
    with open(Out(root).path("BUILD_INFO.json"), encoding="utf-8") as f:
        info = json.load(f)
    committed = info["files"]
    tmp = tempfile.mkdtemp(prefix="kestrel_verify_")
    fresh = build(tmp, info["seed"])["files"]
    problems = []
    for rel in sorted(set(committed) | set(fresh)):
        if rel not in fresh:
            problems.append(f"missing from fresh build: {rel}")
        elif rel not in committed:
            problems.append(f"not in committed BUILD_INFO: {rel}")
        elif committed[rel] != fresh[rel]:
            problems.append(f"hash differs: {rel}")
        else:
            p = Out(root).path(rel)
            if not os.path.exists(p):
                problems.append(f"missing on disk: {rel}")
            elif sha256_file(p) != committed[rel]:
                problems.append(f"on-disk file edited by hand: {rel}")
    shutil.rmtree(tmp, ignore_errors=True)
    if problems:
        print("VERIFY FAILED")
        for p in problems:
            print("  " + p)
        return 1
    print(f"VERIFY OK: {len(fresh)} files match a fresh build byte for byte.")
    return 0


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Generate the synthetic Kestrel case deterministically.")
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--out", default=os.path.join(here, "cases", "kestrel"), help="output case directory")
    ap.add_argument("--verify", action="store_true", help="rebuild in a temp dir and compare with --out")
    ap.add_argument("--seed", default=common.DEFAULT_SEED,
                    help="noise seed; other seeds give training variants with the same key facts")
    a = ap.parse_args(argv)
    if a.verify:
        return verify(a.out)
    info = build(a.out, a.seed)
    total = sum(os.path.getsize(Out(a.out).path(r)) for r in info["files"])
    print(f"Built {len(info['files'])} files ({total / 1e6:.1f} MB) in {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
