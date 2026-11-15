# Kestrel case (SBRPD-26-104417)

> **Synthetic and fictional.** Every person, company, phone number, plate, address and record here is invented
> for training and demonstrating Mapletrace. Any resemblance to real people or companies is coincidental.

**Theft of AX-9 'Kestrel' engineering sample ES-0007.** An unreleased AX-9 "Kestrel" GPU engineering sample disappeared from a secure cabinet in the
Executive Briefing Center of Aurion Compute, Inc. (a fictional GPU company) over the weekend of 2026-10-17.
The case file is current as of 2026-10-22T18:00:00-07:00.

Do not regenerate or edit these files by hand. Run `make data-generate` (or
`python generator/generate.py`) and check with `make data-verify`.

## Layout

| Path | What it is | Ship to the pipeline? |
| --- | --- | --- |
| `evidence/` | The original files, one per evidence item, plus `MANIFEST.csv` with SHA-256 hashes and provenance | Yes |
| `kestrel_case_upload.zip` | The demo upload: `evidence/` zipped under `kestrel_case/` | Yes (this is the demo ZIP) |
| `BUILD_INFO.json` | Seed, versions and the hash of every generated file | No |

There is no answer key in the repository: the model has to work the case out from the evidence. For scoring
a pipeline run afterwards, `make data-truth` writes the answer key to the git-ignored `.truth/kestrel/` folder.
Never put that folder (or the `generator/` source, which encodes the solution) in the model's input.

## Evidence by modality

| Modality | Count | Evidence IDs |
| --- | --- | --- |
| access_log | 5 | EV-070, EV-071, EV-072, EV-073, EV-074 |
| biological | 2 | EV-010, EV-011 |
| calendar | 1 | EV-076 |
| chain_of_custody | 1 | EV-003 |
| email | 5 | EV-100, EV-101, EV-102, EV-103, EV-104 |
| facility_reference | 2 | EV-077, EV-078 |
| interview | 6 | EV-090, EV-091, EV-092, EV-093, EV-094, EV-095 |
| location | 4 | EV-060, EV-062, EV-063, EV-064 |
| photo | 11 | EV-030, EV-031, EV-032, EV-033, EV-034, EV-035, EV-036, EV-037, EV-038, EV-039, EV-040 |
| report | 4 | EV-001, EV-002, EV-052, EV-061 |
| system_log | 1 | EV-075 |
| text_message | 2 | EV-050, EV-051 |
| video | 6 | EV-020, EV-021, EV-022, EV-023, EV-024, EV-025 |
| written_statement | 6 | EV-080, EV-081, EV-082, EV-083, EV-084, EV-085 |

## Classification

`evidence/MANIFEST.csv` classifies every file: modality, format, custodian, collector, acquisition method,
time basis (UTC, local, epoch, burned-in), sensitivity label, and an Admiralty grade (source reliability A-F,
information credibility 1-6). It says nothing about which evidence matters.

Timestamps deliberately mix formats (UTC, local without offset, epoch milliseconds, US 12-hour, a reader with
clock drift) and include duplicates, misreads, missed RFID reads, spam and low-confidence location points, so
the cleaning step has real work to do.

Protected attributes (for example `visitor_log.id_issuing_country`) must not be used as features.
