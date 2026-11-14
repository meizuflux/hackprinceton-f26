"""Build a fictional demo case: the Harbor Street Pharmacy break-in (night of 14 March 2026).

All people, numbers, places and lab results are invented. The evidence contains
deliberate contradictions for the reasoning stage to find:
  * the interviewee says he was home all night; his phone, car GPS and a photo place him at the pharmacy
  * he says he hasn't spoken to Marcus Ortiz in weeks; their messages and a call say otherwise
  * the DNA comparison does not exclude him as the source of the door-handle swab

Run:  python examples/make_sample_case.py   ->  examples/harbor_street_case.zip
"""

from __future__ import annotations

import io
import json
import random
import struct
import wave
import zipfile
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

from PIL import ExifTags, Image, ImageDraw

EDT = timezone(timedelta(hours=-4))
PHARMACY = (40.35012, -74.65905)
VANCE_HOME = (40.33010, -74.69200)
ORTIZ_PHONE, VANCE_PHONE = "(609) 555-0187", "+1 609-555-0142"


def local(h, m, s=0, day=14):
    return datetime(2026, 3, day, h, m, s, tzinfo=EDT)


def jpeg(text: str, when: datetime | None, gps: tuple[float, float] | None, make="Apple", model="iPhone 14",
         serial="F2LXK9PQ7M") -> bytes:
    img = Image.new("RGB", (640, 480), (90, 100, 115))
    ImageDraw.Draw(img).text((20, 220), text, fill=(240, 240, 240))
    exif = Image.Exif()
    exif[271], exif[272], exif[305] = make, model, "17.3.1"
    if when:
        stamp = when.strftime("%Y:%m:%d %H:%M:%S")
        exif[306] = stamp
        ifd = exif.get_ifd(ExifTags.IFD.Exif)
        ifd[36867] = stamp
        ifd[36881] = when.strftime("%z")[:3] + ":" + when.strftime("%z")[3:]
        ifd[42033] = serial
    if gps:
        g = exif.get_ifd(ExifTags.IFD.GPSInfo)

        def dms(v):
            v = abs(v)
            d = int(v)
            m = int((v - d) * 60)
            return (float(d), float(m), round(((v - d) * 60 - m) * 60, 2))
        g[1], g[2] = ("N" if gps[0] >= 0 else "S"), dms(gps[0])
        g[3], g[4] = ("E" if gps[1] >= 0 else "W"), dms(gps[1])
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def mp4_metadata_only(created_utc: datetime, duration_s: int) -> bytes:
    """Minimal MP4 container (ftyp + moov/mvhd) carrying a creation time and duration; no frames."""
    secs = int((created_utc - datetime(1904, 1, 1, tzinfo=timezone.utc)).total_seconds())
    body = struct.pack(">B3sIIII", 0, b"\0\0\0", secs, secs, 1000, duration_s * 1000)
    body += struct.pack(">IH", 0x00010000, 0x0100) + b"\0" * 10
    body += struct.pack(">9I", 0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000) + b"\0" * 24 + struct.pack(">I", 2)
    mvhd = struct.pack(">I4s", 8 + len(body), b"mvhd") + body
    moov = struct.pack(">I4s", 8 + len(mvhd), b"moov") + mvhd
    ftyp_body = b"isom" + struct.pack(">I", 512) + b"isomiso2mp41"
    return struct.pack(">I4s", 8 + len(ftyp_body), b"ftyp") + ftyp_body + moov


def wav_tone(seconds=2.0) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"".join(struct.pack("<h", int(3000 * ((i // 20) % 2 * 2 - 1))) for i in range(int(8000 * seconds))))
    return buf.getvalue()


def track(start: datetime, a, b, minutes: int, every_s: int, jitter=0.0004):
    rnd = random.Random(7)
    n = minutes * 60 // every_s
    for i in range(n + 1):
        f = i / n
        yield (start + timedelta(seconds=i * every_s),
               a[0] + (b[0] - a[0]) * f + rnd.uniform(-jitter, jitter),
               a[1] + (b[1] - a[1]) * f + rnd.uniform(-jitter, jitter))


def build(out_zip: Path) -> Path:
    files: dict[str, bytes | str] = {}

    files["case_manifest.json"] = json.dumps({
        "case_name": "Harbor Street Pharmacy break-in (fictional demo case)",
        "timezone": "America/New_York",
        "files": {
            "phones/vance_iphone/phone_location_dvance.csv": {"owner": "Daniel Vance", "device": "iPhone 14"},
            "phones/vance_iphone/sms_export.csv": {"owner": "Daniel Vance"},
            "phones/vance_iphone/call_log.csv": {"owner": "Daniel Vance"},
            "phones/vance_iphone/contacts.csv": {"owner": "Daniel Vance"},
        },
    }, indent=2)

    # --- Daniel Vance's phone extraction ------------------------------------
    sms = [
        ("03/12/2026 18:02", VANCE_PHONE, ORTIZ_PHONE, "you around this weekend?"),
        ("03/14/2026 19:42", ORTIZ_PHONE, VANCE_PHONE, "still on for the pickup tonight?"),
        ("03/14/2026 19:44", VANCE_PHONE, ORTIZ_PHONE, "yeah. back door, they only have cameras out front"),
        ("03/14/2026 19:45", ORTIZ_PHONE, VANCE_PHONE, "bring the big bag. text me when it's done"),
        ("03/14/2026 23:49", VANCE_PHONE, ORTIZ_PHONE, "done. heading to you"),
        ("03/14/2026 23:49", VANCE_PHONE, ORTIZ_PHONE, "done. heading to you"),  # duplicate row in export
        ("03/15/2026 00:31", ORTIZ_PHONE, VANCE_PHONE, "delete this thread"),
        ("03/15/2026 09:15", "+1 609-555-0110", VANCE_PHONE, "Mom: call me when you're up"),
    ]
    files["phones/vance_iphone/sms_export.csv"] = "Date/Time,From,To,Message\n" + "\n".join(
        f'{d},{f},{t},"{m}"' for d, f, t, m in sms) + "\n"
    # a second, partially overlapping export of the same thread (tests cross-source de-duplication)
    files["phones/vance_iphone/sms_backup.json"] = json.dumps({"device": "iPhone 14", "messages": [
        {"sent_at": "2026-03-14T19:44:00-04:00", "sender": VANCE_PHONE, "recipient": ORTIZ_PHONE,
         "text": "yeah. back door, they only have cameras out front"},
        {"sent_at": "2026-03-14T23:49:00-04:00", "sender": VANCE_PHONE, "recipient": ORTIZ_PHONE, "text": "done. heading to you"},
    ]}, indent=2)
    files["phones/vance_iphone/call_log.csv"] = (
        "timestamp,caller,callee,duration_s,direction\n"
        "2026-03-14 20:10:05,+1 609-555-0142,(609) 555-0187,212,outgoing\n"
        "2026-03-14 23:51:30,+1 609-555-0142,(609) 555-0187,45,outgoing\n"
        "2026-03-15 00:33:12,(609) 555-0187,+1 609-555-0142,0,missed\n")
    files["phones/vance_iphone/contacts.csv"] = (
        "Name,Phone,Email\nMarcus Ortiz,(609) 555-0187,m.ortiz@example.net\nMom,+1 609-555-0110,\n"
        "Daniel Vance,+1 609-555-0142,dan.vance@example.com\n")
    rows = ["timestamp_ms,latitude,longitude,accuracy_m,device"]
    seq = list(track(local(22, 0), VANCE_HOME, VANCE_HOME, 60, 300)) + \
        list(track(local(23, 5), VANCE_HOME, PHARMACY, 15, 60)) + \
        list(track(local(23, 21), PHARMACY, PHARMACY, 28, 120, 0.0001)) + \
        list(track(local(23, 52), PHARMACY, VANCE_HOME, 30, 120))
    for t, la, lo in seq:
        rows.append(f"{int(t.timestamp() * 1000)},{la:.6f},{lo:.6f},{random.Random(int(t.timestamp())).randint(5, 25)},iPhone 14")
    rows.append(f"{int(local(23, 30).timestamp() * 1000)},0,0,9999,iPhone 14")  # GPS glitch row
    rows.append(rows[5])  # exact duplicate row
    files["phones/vance_iphone/phone_location_dvance.csv"] = "\n".join(rows) + "\n"
    files["phones/vance_iphone/photos/IMG_2041.JPG"] = jpeg("rear entrance", local(21, 12, 40), (40.35041, -74.65872))
    files["phones/vance_iphone/photos/IMG_2043.JPG"] = jpeg("bag", local(23, 58, 3), None)
    img = Image.new("RGB", (390, 844), (20, 20, 20))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    files["phones/vance_iphone/photos/screenshot_0315.png"] = buf.getvalue()

    # --- WhatsApp-style chat export from Marcus Ortiz's phone ---------------
    files["phones/ortiz_android/WhatsApp Chat with Dan V.txt"] = "\n".join([
        "3/14/26, 8:15 PM - Marcus: you sure about tonight",
        "3/14/26, 8:16 PM - Dan V: yes. guard leaves at 9, does one walk around 10:30",
        "3/14/26, 8:16 PM - Marcus: and the alarm",
        "3/14/26, 8:18 PM - Dan V: rear door alarm goes to the monitoring company, takes them a few min to call anyone",
        "we'll be gone by then",
        "3/14/26, 11:53 PM - Marcus: <Media omitted>",
        "3/15/26, 12:40 AM - Dan V: got it all. talk tomorrow",
    ]) + "\n"

    # --- Vehicle GPS (owner only in the file name) --------------------------
    pts = "".join(f'<trkpt lat="{la:.6f}" lon="{lo:.6f}"><time>{t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}</time></trkpt>'
                  for t, la, lo in list(track(local(23, 6), VANCE_HOME, PHARMACY, 14, 120)) + list(track(local(23, 50), PHARMACY, VANCE_HOME, 30, 180)))
    files["vehicle/vehicle_gps_vance.gpx"] = (
        '<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="fleet-tracker" xmlns="http://www.topografix.com/GPX/1/1">'
        f"<trk><name>Grey Honda Accord</name><trkseg>{pts}</trkseg></trk></gpx>")

    # --- Pharmacy CCTV -------------------------------------------------------
    files["cctv/cam2_rear_door.mp4"] = mp4_metadata_only(local(23, 30).astimezone(timezone.utc), 1200)
    files["cctv/cam2_analytics_events.csv"] = (
        "event_time,camera_id,event,confidence\n"
        "2026-03-14 23:37:52,CAM2-REAR,motion detected at rear door,0.91\n"
        "2026-03-14 23:38:10,CAM2-REAR,person at door - hooded,0.87\n"
        "2026-03-14 23:38:41,CAM2-REAR,door opened (forced entry suspected),0.83\n"
        "2026-03-14 23:44:05,CAM2-REAR,person exits carrying large bag,0.88\n"
        "2026-03-14 23:46:30,CAM2-REAR,vehicle departs north - dark sedan,0.79\n")
    files["records/alarm_monitoring_log.csv"] = (
        "Date,Time,Zone,Event,Operator\n"
        "2026-03-14,21:01,ALL,System armed by user 'TBriggs',\n"
        "2026-03-14,23:38,Zone 4 Rear Door,ALARM - door contact,auto\n"
        "2026-03-14,23:41,Zone 4 Rear Door,Keyholder T. Briggs called,K. Shah\n"
        "2026-03-14,23:52,Zone 4 Rear Door,Police dispatched,K. Shah\n")
    files["records/card_transactions_vance.csv"] = (
        "timestamp,card_holder,merchant,amount_usd,city\n"
        "2026-03-14 18:25:11,Daniel Vance,Quick Fuel #12,41.20,Princeton\n"
        "2026-03-15 00:02:47,Daniel Vance,Quick Fuel #12,12.75,Princeton\n")

    # --- Statements and interview -------------------------------------------
    files["statements/witness_statement_jlee.txt"] = (
        "WITNESS STATEMENT\nName: Jamie Lee\nAddress: 14 Harbor Street, Apt 2\nDate of incident: March 14, 2026\n"
        "Date of statement: March 15, 2026\n\n"
        "I live in the apartment across the alley from the back of the pharmacy. On Saturday night I was up late watching TV. "
        "At around 11:30 pm I heard a loud bang from the alley, like metal hitting a door. "
        "I looked out of my kitchen window and saw a man in a grey hoodie at the pharmacy's back door. "
        "He was tall and was carrying a large dark bag. "
        "Shortly after 11:45 I saw him get into a dark four-door car parked by the dumpsters. "
        "The car drove off north toward Nassau Street at about 11:50 pm. I did not see his face clearly. "
        "I called 911 at 11:52 pm.\n\nSigned: Jamie Lee\n")
    from docx import Document
    d = Document()
    for line in ["STATEMENT OF WITNESS", "Name: Tom Briggs", "Role: Night security guard, Harbor Street Pharmacy",
                 "Date of incident: 14 March 2026", "",
                 "I locked the rear door at 9:00 pm and armed the alarm before leaving the building.",
                 "I came back for my patrol at around 10:30 pm and everything was secure. I checked the back door myself.",
                 "The alarm monitoring company called me at 11:41 pm to say the rear door alarm had gone off.",
                 "I got to the pharmacy at about 12:05 am and the police were already there.",
                 "The rear door frame was bent and there was a metal bar on the ground.",
                 "Only the manager and I have keys to the rear door. Signed, Tom Briggs."]:
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    files["statements/witness_statement_tbriggs.docx"] = buf.getvalue()
    files["interviews/interview_dvance_2026-03-16.txt"] = (
        "INTERVIEW TRANSCRIPT\nCase: HSP-2026-031\nDate: 2026-03-16 10:05\nInterviewer: Det. Ana Ruiz\n"
        "Interviewee: Daniel Vance\nDate of incident: 2026-03-14\n\n"
        "Det. Ruiz: Can you tell me where you were on Saturday night, the 14th?\n"
        "Daniel Vance: I was home all night. I watched a movie and went to bed around 10:30.\n"
        "Det. Ruiz: Did you leave the house at any point after that?\n"
        "Daniel Vance: No. I was asleep by 11.\n"
        "Det. Ruiz: Do you know Marcus Ortiz?\n"
        "Daniel Vance: I know him, but I haven't talked to Marcus in weeks.\n"
        "Det. Ruiz: Have you ever been to the Harbor Street Pharmacy?\n"
        "Daniel Vance: Never. I use the CVS on Route 1.\n"
        "Det. Ruiz: Who drives the grey Honda Accord registered to you?\n"
        "Daniel Vance: Just me. It was parked outside all night.\n")

    # --- Lab ------------------------------------------------------------------
    loci = ["D8S1179", "D21S11", "D7S820", "CSF1PO", "D3S1358", "TH01", "D13S317", "D16S539", "D2S1338",
            "D19S433", "vWA", "TPOX", "D18S51", "D5S818", "FGA", "AMEL"]
    dv = [("13", "14"), ("29", "30"), ("10", "11"), ("11", "12"), ("15", "16"), ("6", "9.3"), ("11", "12"), ("9", "12"),
          ("19", "23"), ("13", "14"), ("16", "18"), ("8", "11"), ("14", "17"), ("11", "13"), ("21", "24"), ("X", "Y")]
    mo = [("12", "15"), ("28", "31.2"), ("8", "12"), ("10", "11"), ("14", "17"), ("7", "8"), ("8", "13"), ("11", "13"),
          ("17", "24"), ("14", "15.2"), ("15", "17"), ("8", "9"), ("12", "15"), ("12", "12"), ("20", "22"), ("X", "Y")]
    lines = ["sample_id,description,locus,allele_1,allele_2"]
    for i, l in enumerate(loci):
        if i not in (8, 12, 14):  # partial profile: 3 loci did not amplify
            lines.append(f"SW-01,swab rear door handle,{l},{dv[i][0]},{dv[i][1]}")
        else:
            lines.append(f"SW-01,swab rear door handle,{l},,")
    lines += [f"REF-DV,reference buccal swab (D. Vance),{l},{a},{b}" for l, (a, b) in zip(loci, dv)]
    lines += [f"REF-MO,reference buccal swab (M. Ortiz),{l},{a},{b}" for l, (a, b) in zip(loci, mo)]
    files["lab/dna_str_profiles.csv"] = "\n".join(lines) + "\n"
    files["lab/dna_comparisons.csv"] = (
        "questioned_sample,reference_sample,loci_compared,likelihood_ratio,conclusion,report_date\n"
        "SW-01,REF-DV,13,1.2e9,cannot be excluded as a contributor,2026-03-19\n"
        "SW-01,REF-MO,13,,excluded as a contributor,2026-03-19\n")
    files["lab/lab_report_HSP-2026-031.txt"] = (
        "FORENSIC BIOLOGY REPORT\nLab case: L-26-0442\nAnalyst: J. Patel\nDate: 2026-03-19\n\n"
        "Item SW-01 is a swab collected from the exterior handle of the rear door on March 15, 2026. "
        "STR testing of SW-01 produced a partial single-source male DNA profile at 13 of 16 loci. "
        "Daniel Vance (REF-DV) cannot be excluded as the source of the DNA profile from SW-01. "
        "The likelihood ratio is approximately 1.2 billion in favour of Daniel Vance being the source. "
        "Marcus Ortiz (REF-MO) is excluded as a contributor to SW-01. "
        "Item MB-02, a metal bar recovered at the scene, did not yield a usable DNA profile. "
        "Results relate only to the items tested.\n")

    # --- Anonymous tip by email with a photo attachment -------------------------
    msg = EmailMessage()
    msg["From"] = "Concerned Neighbor <tips.anon@example.org>"
    msg["To"] = "Det. Ana Ruiz <a.ruiz@example.gov>"
    msg["Subject"] = "Car I saw near Harbor St Saturday"
    msg["Date"] = "Sun, 15 Mar 2026 08:12:44 -0400"
    msg["Message-ID"] = "<tip-20260315-0812@example.org>"
    msg.set_content("Hi Detective, I saw a grey Honda with a dented rear bumper idling behind the pharmacy around "
                    "11:20 Saturday night. I took a picture of the plate from my balcony, attached. "
                    "I think the driver was Dan Vance, he lives over on Witherspoon. Please keep my name out of it.")
    msg.add_attachment(jpeg("plate", local(23, 21, 15), (40.35090, -74.65950), make="Google", model="Pixel 7",
                            serial="GP7-77310"), maintype="image", subtype="jpeg", filename="plate_photo.jpg")
    files["email/tip_from_neighbor.eml"] = bytes(msg)

    # --- Misc: nested archive, voicemail, an unreadable blob -------------------
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr("notes_from_old_phone.txt", "Shopping: bolt cutters, gloves, big duffel bag\nCall M re: Saturday\n")
    files["misc/old_phone_backup.zip"] = inner.getvalue()
    files["misc/voicemail_0315.wav"] = wav_tone()
    rnd = random.Random(1)
    files["misc/device_dump.bin"] = bytes(rnd.getrandbits(8) for _ in range(2048))

    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 3, 16, 9, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data if isinstance(data, bytes) else data.encode("utf-8"))
    return out_zip


if __name__ == "__main__":
    p = build(Path(__file__).with_name("harbor_street_case.zip"))
    print(f"wrote {p} ({p.stat().st_size // 1024} KB)")
