# Generator and case-document evaluation

Baseline reviewed November 14, 2026, on `generator-refinement` at `8b5107d`, before any generator refinement.

Method: read every module under `generator/`, then checked the committed Kestrel documents against the logs, allele table, manifest, calendar, and ZIP they describe. A second pass read every shipped `.txt` and `.eml` and spot-checked the rows those sentences depend on. Answer-key tags were used only to separate intentional contradictions from generator bugs. The answer key was not written into the tree. `make data-verify` was not run: this machine does not have the pinned Pillow/numpy stack. The ZIP platform split below was reproduced with the stdlib.

This is a baseline, not a post-change score. Intentional lies (the Saturday alibis, the "alone" claim, Ortega's "around 11:30", the staff pointing at Raman and Bellini) are not defects.

## Baseline health

| Criterion | Score / 4 | Main observation |
| --- | --- | --- |
| Deterministic text | 4 | Seeded streams, LF output, catalog-driven README. Committed text matches the writers. |
| Reproducible binaries | 1 | Committed ZIP and media were built on Windows. A macOS rebuild will not match. |
| Cross-document consistency | 2 | The theft window agrees. Door-held times, the next board date, a photo join, and one interview quote do not. |
| Investigative design | 3 | Gaps, red herrings, and citations are real. Interviews telegraph the next fact. |
| Document realism | 2 | Usable and distinct in content, not in voice. Photos are diagrams labeled as photos. |
| Citation integrity | 2 | Key tags resolve. Interview bracket numbers are not file lines. |
| Rule compliance | 3 | Fictional 555 numbers and `.example` domains. No answer key in the ZIP. Passport country is correlated with the handler call. |
| Verification | 2 | Hash verify is the only check, and it does not cover the claims the README says it covers. |
| **Total** | **19 / 32** | **Baseline. Not a measured accuracy score.** |

## What works

- The case is solvable from the upload and does not ship an answer key. `kestrel_case_upload.zip` has 57 members, all under `kestrel_case/`, and none are truth files or `README.md`. No shipped prose, filename, or manifest title names a culprit or labels a red herring.
- `cases/kestrel/README.md` is generated from the catalog. The committed tree matches it: 56 evidence files and the modality counts in the README. `BUILD_INFO.json` lists every generated file except itself. Python package pins match `generator/requirements.txt`.
- The theft window agrees across the incident report, Brandt, the Ellis/Brandt emails, the cabinet audit, RFID, the inventory alert, the 22:55 workstation mail, Elaine Halvorsen, and the guard tour. Lab 2A reader drift is `+00:02:47` (167 seconds) in `doors_readers.csv`, and the badge writer applies that skew.
- Extraction notes match the phone file: thread T01 has 48 records, all deleted at `2026-10-20T14:58:20Z`, and exactly three bodies are `[message body unrecoverable]`. All five `.eml` files parse.
- On the committed seed, the allele table supports the lab report's binary claims for Q1, Q3, and Q4. K1, K3, and UF-1 are fully contained in Q1; K2 is not (TH01 7 is absent). Q4 matches no known reference. Q3 matches K1. K1 is excluded from Q2. There are no peak heights, so "major contributor" is not recomputable from the table; the report is the authority for that adjective.
- People, numbers, and domains follow the fictional rules. RH-03 is a clean trap in the prose: Chen's Shenzhen trip is an approved audit, and no sentence says travel or origin implies guilt. HK is not unique in the visitor log (Hannah Flores, same day, is also HK).

## P1 — fix before relying on a rebuild or on these joins

### 1. Binary output is not portable, and verify will not say why

`cases/kestrel/BUILD_INFO.json` records Python 3.13.3 and ffmpeg `9.0.2-essentials_build-www.gyan.dev` (a Windows build). `generator/requirements.txt` pins the Python packages, not the ffmpeg binary and not the host OS.

The ZIP writer sets a fixed timestamp and Unix mode, but not `ZipInfo.create_system`:

```56:65:generator/kestrel/build.py
def write_zip(out: Out):
    members = ["evidence/MANIFEST.csv"] + [e.path for e in CATALOG]
    p = out._ensure(ZIP_NAME)
    with zipfile.ZipFile(p, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in sorted(members):
            info = zipfile.ZipInfo("kestrel_case/" + rel, date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
```

The committed archive has `create_system = 0` on all 57 members. The same `ZipInfo` written by Python 3.15 on this Mac comes back as `create_system = 3`. That alone changes the ZIP hash. JPEG and MP4 bytes can diverge further because Pillow and the bundled ffmpeg differ by platform. `verify()` then reports `hash differs` with no version check against `BUILD_INFO.json`.

The generator README and the `BUILD_INFO` note overclaim: text is byte-stable; JPEG, MP4, and ZIP are not stable across machines that merely share the pinned requirement file.

### 2. Visitor `photo_ref` points at files that were never generated

Every visitor row is given `photo_ref = "{visit_id}.jpg"`. The only kiosk image in the tree is `evidence/03_photo/visitor_kiosk_1007.jpg` (EV-040). Shen's row is `VIS-1007-0012.jpg` (`visitor_log.csv:13`). The same day also invents `VIS-1007-0010.jpg` and `VIS-1007-0011.jpg`. None of those names exist. A join from the visitor log to the photo file fails for the walkthrough the case is built around.

### 3. The door-held interval does not match itself

This is a machine-log contradiction, not an alibi.

| Source | What it says |
| --- | --- |
| Badge grant `BDG-000614` | `21:36:31` |
| Alarm `BDG-000615` | `21:36:49`, detail `held 16s (threshold 15s)` |
| Close `BDG-000616` | `21:36:52`, detail `open 19s` |
| Interview 2, file line 17 | "held open for sixteen seconds after you badged in" |

Grant to alarm is 18 seconds. Grant to close is 21 seconds. Neither detail string matches those spans, and the interview matches the detail string rather than the timestamps. The tailgate is load-bearing. One duration has to win, in the log and in the question.

### 4. Ellis names a board meeting the calendar does not have

`07_stmt/ellis.txt:11`: "The next board meeting is on 10/28. I did not ask about it." She manages that calendar and is not written as a liar. On 2026-10-28 the export has Finance: Q3 forecast, a hyperscaler call, and a foundry call (`ceo_calendar.ics` around line 2230). The only `Board of Directors` event in the file is 2026-08-12. Subcommittee blocks are not that meeting. Put the meeting on the calendar, or delete the date from the statement.

### 5. One interview quotes evidence the extraction notes say was not yet in hand

Priya Raman's interview is `2026-10-20 11:00`. Okoye says "We have texts where you wrote that they would regret it" (`08_intv/raman.txt:14`). The matching body is in `raman_android.csv`, whose catalog collection time is `2026-10-21 10:20`. The extraction notes date her consent to `2026-10-21 09:20`. Her written statement on `2026-10-19` consents to an exam and admits she "said some things," but it does not quote the line. The interview is written as if the quote is already in evidence.

The same notes, collected at 12:00 on 2026-10-21, say the 0147 user declined consent that day. The refusal is in the 13:00 interview. The notes anticipate a fact they cannot yet contain.

### 6. Custody does not describe the same items as the lab

Q1 has a property-room row. Q2, Q3, and Q4 go from CST Park at 10:33–10:53 straight to the lab the next morning (`custody_log.csv:3-6`), with no overnight holder. Custody calls Q3 and Q4 wine glasses. The lab received swabs of the rims. The report says remaining swab material was returned to Property on 2026-10-22. That return is not in the log. `acquisition_sha256` is `sha256("custody:" + row)`, not a hash of an artifact, despite the column name.

### 7. DNA sentences are harder than the assertions that guard them

`check_dna()` checks full allele containment for Q1 (K1, K3, UF-1 in; K2 out) and for Q2 (UF-1 in; K1 and K3 out). It does not check the sentence the report actually prints about Q2: K2 "cannot be excluded" at a likelihood ratio of about `4.2 x 10^3`. On the committed seed, K2 is fully present at 13 of 20 loci, partial at 6, and absent at 1. The ratio is a constant in `dna.py`, not a function of those alleles. There are no peak heights, so "major" cannot be audited from `str_profiles.csv`. The parenthetical "(synthetic statistic)" also breaks the document's frame. The subscriber return is labeled "(synthetic carrier)."

Q2's minor-contributor alleles are drawn per locus with `rng("dna")` at probability 0.7. Another seed can drop most of K2 and still emit the same sentence. The same seed can also make `check_dna()` fail: K2 can by chance be a subset of the Q1 mixture, or K1 a subset of the Q2 mixture. The README says variant seeds keep the key facts and only change noise. A variant that aborts in `check_dna()`, or that keeps a fixed LR over a different table, breaks that promise.

### 8. Interview locators and displayed numbers disagree

`render_marked_text(..., numbered=True)` cites `line={file line}` and also prefixes non-blank lines with `[NNNN]`. Blank lines are counted in the file and not in the bracket. In every transcript, `[0009]` is file line 10. The door-held sentence is file line 17 and display `[0016]`. The home alibi is file line 15 and display `[0014]`. The answer key uses file lines. A person, or a model, will cite the bracket. Pick one identifier and print only that.

## P2 — refinement, not blockers

- The Friday wipe is unordered. Whitfield says the crew wipes the cabinet handle on Friday evenings, and that Raman returned ES-0007 at 7:12 pm after Whitfield left at about 6 pm (`07_stmt/whitfield.txt:11-12`). The lab repeats "Friday evenings" and says the agency's cleaning note was not verified. The answer key resolves Raman's handle DNA by assuming the wipe happened before that return. No shipped sentence says so. If that order is part of the case, cite it. If it is not, stop treating it as established.
- Whitfield's Monday order is reversed against the machines. She says she texted and called, then checked the alerts mailbox (`whitfield.txt:13-14`). The alert was first read at `2026-10-19T07:52:31-07:00`. The iMessage "Tom is on his way" is `2026-10-19T14:58:40Z` (07:58:40 PDT). Brandt's "Dana called me" at about 7:58 fits the text, not the statement order. She is not written as a liar.
- Halvorsen says he last saw the sample "Friday morning, at the keynote rehearsal in the EBC" (`halvorsen_1.txt:13`). Friday 10/16 on the calendar is a foundry call at 11:00, not an EBC rehearsal. The keynote dry runs that week are Thursday 10/15. This is not tagged as an intentional lie.
- Statements share one frame: same banner, numbered paragraphs, same closing sentence. Ortega is slightly more spoken. Counsel in interview 2 is the only real voice break. Chen's interview is eight questions. Bellini's telephone interview still says "Recorded: audio and video" (`08_intv/bellini.txt:8`). For a three-minute demo this clarity helps. For training, it teaches the model that every question is a hint.
- Scene "photos" are diagrams. `csu_003.jpg` is a bin, two glasses, a bottle, and placard 3. `IMG_4471.jpg` is two place settings, a red rim mark, a tan tote, and a dark sleeve. The icons match the prose, so a vision model may still recover the intended objects. The catalog calls them camera-roll and scene photos. Only `media.py` admits they are renders. Say that in the case README.
- `inv_alert.eml` carries `X-Mailbox-First-Read`, and `halvorsen_2255.eml` carries `X-Originating-Host`. Useful, and not how a mail archive usually records those facts.
- `1 Market Plaza, Suite 3700, San Francisco, CA 94105` is a real complex used as the front company's virtual office. Pearl River Substrate Co. is invented, but the geographic name is real. Lena Vogel (CTO) approves Chen's travel and never appears in `PEOPLE`. The lab method names CODIS, a real program. That is vocabulary, not a clue.
- File-level Admiralty grades mix source reliability with whether the speaker is lying. Interview 1 is C4 at a collection time of 15:00 on 2026-10-19, the start of the interview, before the alibi had been confronted. A pipeline that trusts the grade will down-weight the recording before the contradiction exists. Raman, Chen, and Bellini stay C3, so the grades do not mark the red herrings as cleared. Soft steer, not an answer key.
- Shen's visitor row hardcodes `id_issuing_country=HK`, which matches the geography of the masked Sunday call. HK is not unique, and no prose uses the column as a clue. A model that ignores the README warning is still rewarded. Give the offender a non-matching issuing country, or stop aligning the handler's geography with that column.
- `relevance_by_tag` on `render_marked_text` is unused. `ANN_TRACKS` is cleared in `write_all`, which is good; the in-process global is still a trap if a caller writes photos without that clear.
- Truth facts are a second prose layer. Tags fail closed, but false sentences do not. F-35's "Lab 2A 13:59-16:31" compresses a P2 entry at 13:59 and a lab entry at 14:02. Guard "about 00:28" is 00:29:16 in the tour log. Small, and only in the unshipped key.

## What this review did not do

- Did not install generator dependencies or run `make data-verify` / `make data-truth`.
- Did not watch the four MP4s or open every JPEG. Two photos were inspected; EXIF was not re-parsed.
- Did not audit every background badge, CDR, or visitor row. Checks were aimed at claims the prose and the answer key treat as facts.
- Did not score a pipeline. There is still no `eval/score.py`. This document is about the generator and the documents it emits.

## Refinement order

1. Make ZIP bytes host-independent (`create_system`, extra fields) and make `verify()` refuse a Python, Pillow, or ffmpeg mismatch before it diffs hashes. Pin or record the ffmpeg binary the committed media was built with.
2. One door-held duration, in the grant, the alarm, the close, both detail strings, and the interview. Put a board meeting on 10/28, or take that date out of Ellis's statement.
3. Point Shen's `photo_ref` at EV-040, and stop inventing `.jpg` names for visits that have no file. Finish the custody log so it describes the same items the lab received, including the 10/22 return.
4. Move the Raman quote to after her extraction, or move the extraction to before the interview. Do not let the extraction notes record a refusal that happens an hour later.
5. Generate lab-report inclusion lines from the allele table, including dropout. Add peak heights if "major" must be auditable. Keep variant seeds from failing the asserts. Drop "(synthetic statistic)" and "(synthetic carrier)" from the documents.
6. Cite interviews by one stable locator. State the Friday wipe time if that order is load-bearing. Decouple passport country from the handler call.
7. Then, if the demo still needs it: disclose schematic media in the case README, vary statement voice, fix the telephone/video header, and stop grading interview 1 as C4 at the moment it starts.
