# Case data generator

Builds the synthetic **Kestrel** case in [`cases/kestrel/`](../cases/kestrel/README.md): an unreleased GPU
engineering sample stolen from a fictional chip company. The output is fully deterministic. Every run with the
same seed and pinned libraries produces byte-identical files.

Everything is fictional: people, companies (Aurion Compute, Pacific Harbor Advisory, Sundao Microelectronics),
phone numbers (the reserved 555-01xx range), plates, addresses and `.example` email domains.

## Run

Requires Python 3.11+. From the repository root:

```sh
make data-install     # pip install -r generator/requirements.txt
make data-generate    # rebuild cases/kestrel
make data-verify      # rebuild in a temp dir and compare every file hash with cases/kestrel/BUILD_INFO.json
```

Without Make: `python generator/generate.py`, `python generator/generate.py --verify`.

Training variants: `python generator/generate.py --seed variant-7 --out /tmp/kestrel-variant-7`. A different
seed changes the background noise (crowd badge traffic, spam, duplicates, misreads, schedules, DNA alleles)
while the scripted case events and their key tags stay the same.

## What it produces

| Modality | Files | Notes |
| --- | --- | --- |
| Biological | STR allele table + lab report | 20 CODIS core loci + Amelogenin; mixtures; the report's inclusions and exclusions are asserted against the alleles at build time |
| Video | 4 H.264 MP4 CCTV clips + VMS export index + VMS analytics | Rendered scenes with burned-in timestamps; per-frame boxes and identities in `truth/video_tracks.jsonl` |
| Photos | 11 JPEGs | Real EXIF `DateTimeOriginal`, `OffsetTime`, GPS, make/model; object boxes in `truth/photo_annotations.json` |
| Messages | 2 phone extractions (CSV) | Includes recovered deleted messages, spam, automated notifications, sync duplicates |
| Location | 2 carrier record sets, 1 location-history export, garage plate reads | Cell-site coarse location, precise visits, OCR misreads |
| Access and system logs | Badge, cabinet audit (JSONL), RFID, visitors, guard tours, workstation, calendar (ICS), reference tables | Mixed time formats; one reader with clock drift |
| Statements and interviews | 6 written statements, 6 transcripts | Line-addressable; tagged lines become citable locators |
| Email and reports | 5 EML, incident report, insurer FNOL, custody log, extraction notes, subscriber return | |

## Code map

| Module | Responsibility |
| --- | --- |
| `kestrel/common.py` | Seeded RNG streams, time helpers, file writer (stable bytes, long Windows paths), label registry |
| `kestrel/cast.py` | People, places, items, meeting dates and the ground-truth timeline anchors |
| `kestrel/catalog.py` | One entry per evidence file: provenance, time basis, sensitivity, Admiralty grade |
| `kestrel/logs.py` | Badge, LPR, cabinet, RFID, visitors, guard tours, workstation, calendar, reference tables |
| `kestrel/messages.py` | Phone message extractions |
| `kestrel/location.py` | Movement schedules, cell-site model, carrier records, location history |
| `kestrel/dna.py` | STR profiles and lab report |
| `kestrel/media.py` | Photos, CCTV clips, VMS tables, annotations |
| `kestrel/texts.py` | Reports, statements, interviews, emails |
| `kestrel/truth.py` | Answer key: facts, insights, gaps, questions, red herrings, entities, timeline, labels |
| `kestrel/build.py` | Orchestration, manifest, ZIP, README, `BUILD_INFO.json`, `--verify` |

## Rules for changes

- Change the generator, then regenerate. Never edit files under `cases/` by hand; `make data-verify` fails if you do.
- New evidence needs a `catalog.py` entry, a writer, `reg.rec(...)` labels for every record, and `reg.key(...)`
  tags for anything the answer key cites. `truth.py` resolves tags to exact locators and fails on unknown tags.
- Keep scripted events consistent across sources (`cast.T` holds the shared anchors).
- Do not add real people, companies or contact details. Do not make protected attributes predictive.
- Bump `GENERATOR_VERSION` in `build.py` when the output changes on purpose.
