"""Photos (JPEG with EXIF) and CCTV clips (H.264 MP4 with burned-in timestamps), plus the VMS export
index, VMS analytics events, and ground-truth annotations (per-frame tracks and photo boxes).

Scenes are simple renders, not photographs: the point is realistic metadata, timing, and labels.
Swap in real footage later (e.g. public CCTV datasets) without changing the manifest schema."""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from datetime import timedelta

import imageio_ffmpeg
import numpy as np
import piexif
from PIL import Image, ImageDraw, ImageFont

from .cast import PLACES, T
from .catalog import path_of
from .common import UTC, Out, Registry, iso_local, local_str, lt, rng

FONT = {s: ImageFont.load_default(size=s) for s in (9, 11, 13, 15, 18, 22, 28, 40, 64)}
W, H = 640, 360
ANN_TRACKS: list[dict] = []
ANN_PHOTOS: dict[str, list[dict]] = {}


# ----------------------------------------------------------------------------- helpers
def grain(img: Image.Image, seed: str, amp: int = 6) -> Image.Image:
    g = np.random.default_rng(int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16))
    a = np.asarray(img).astype(np.int16)
    a = a + g.integers(-amp, amp + 1, size=a.shape[:2])[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def _rat(x: float):
    d = int(abs(x))
    m = int((abs(x) - d) * 60)
    s = round((((abs(x) - d) * 60) - m) * 60 * 100)
    return ((d, 1), (m, 1), (s, 100))


def exif_bytes(dt, make, model, desc, gps_key=None, software="", unique=""):
    zeroth = {piexif.ImageIFD.Make: make, piexif.ImageIFD.Model: model,
              piexif.ImageIFD.ImageDescription: desc, piexif.ImageIFD.Software: software or "SyntheticCase 1.0",
              piexif.ImageIFD.DateTime: dt.strftime("%Y:%m:%d %H:%M:%S")}
    ex = {piexif.ExifIFD.DateTimeOriginal: dt.strftime("%Y:%m:%d %H:%M:%S"),
          piexif.ExifIFD.DateTimeDigitized: dt.strftime("%Y:%m:%d %H:%M:%S"),
          piexif.ExifIFD.OffsetTime: "-07:00", piexif.ExifIFD.OffsetTimeOriginal: "-07:00",
          piexif.ExifIFD.OffsetTimeDigitized: "-07:00"}
    if unique:
        ex[piexif.ExifIFD.ImageUniqueID] = unique
    gps = {}
    if gps_key:
        _, lat, lon, _ = PLACES[gps_key]
        u = dt.astimezone(UTC)
        gps = {piexif.GPSIFD.GPSLatitudeRef: "N" if lat >= 0 else "S", piexif.GPSIFD.GPSLatitude: _rat(lat),
               piexif.GPSIFD.GPSLongitudeRef: "E" if lon >= 0 else "W", piexif.GPSIFD.GPSLongitude: _rat(lon),
               piexif.GPSIFD.GPSDateStamp: u.strftime("%Y:%m:%d"),
               piexif.GPSIFD.GPSTimeStamp: ((u.hour, 1), (u.minute, 1), (u.second, 1)),
               piexif.GPSIFD.GPSHPositioningError: (8, 1)}
    return piexif.dump({"0th": zeroth, "Exif": ex, "GPS": gps, "1st": {}, "thumbnail": None})


def save_jpeg(out: Out, eid: str, img: Image.Image, exif: bytes):
    p = out._ensure(path_of(eid))
    img.save(p, "JPEG", quality=86, exif=exif, optimize=False, progressive=False, subsampling=2)


def placard(d: ImageDraw.ImageDraw, x, y, n, s=1.0):
    w, h = int(46 * s), int(40 * s)
    d.polygon([(x, y + h), (x + w // 2, y), (x + w, y + h)], fill=(240, 200, 30), outline=(30, 30, 30))
    d.text((x + w // 2, y + h * 0.62), str(n), fill=(10, 10, 10), font=FONT[22 if s >= 1 else 15], anchor="mm")
    return [x, y, w, h]


def ruler(d, x, y, length, s=1.0):
    d.rectangle([x, y, x + length, y + int(18 * s)], fill=(235, 235, 225), outline=(40, 40, 40))
    for i in range(0, length + 1, max(4, int(10 * s))):
        d.line([x + i, y, x + i, y + (int(10 * s) if (i // max(4, int(10 * s))) % 5 == 0 else int(5 * s))],
               fill=(30, 30, 30))
    return [x, y, length, int(18 * s)]


def ann(eid, label, box, note=""):
    ANN_PHOTOS.setdefault(eid, []).append({"label": label, "bbox_xywh": [int(v) for v in box], "note": note})


def wine_glass(d, x, y, s=1.0, lipstick=False, lying=False):
    if lying:
        d.ellipse([x, y, x + 70 * s, y + 46 * s], outline=(200, 210, 215), width=3)
        d.line([x + 70 * s, y + 23 * s, x + 150 * s, y + 23 * s], fill=(200, 210, 215), width=4)
        d.line([x + 150 * s, y + 5 * s, x + 150 * s, y + 41 * s], fill=(200, 210, 215), width=4)
        if lipstick:
            d.arc([x - 2, y + 4 * s, x + 18 * s, y + 42 * s], 110, 250, fill=(170, 20, 40), width=5)
        return [x, y, 150 * s, 46 * s]
    d.ellipse([x, y, x + 40 * s, y + 52 * s], outline=(215, 220, 225), width=3)
    d.rectangle([x + 2 * s, y + 26 * s, x + 38 * s, y + 46 * s], fill=(120, 20, 40))
    d.line([x + 20 * s, y + 52 * s, x + 20 * s, y + 92 * s], fill=(215, 220, 225), width=3)
    d.ellipse([x + 4 * s, y + 88 * s, x + 36 * s, y + 98 * s], outline=(215, 220, 225), width=3)
    if lipstick:
        d.arc([x + 2 * s, y - 4 * s, x + 18 * s, y + 10 * s], 180, 300, fill=(185, 25, 45), width=4)
    return [x, y - 4 * s, 40 * s, 102 * s]


# ----------------------------------------------------------------------------- photos
def photos(out: Out, reg: Registry):
    vis_vid = reg.keys["VISITOR_SHEN_1007"]["locator"].split("=")[1]
    # EV-030 cabinet
    img = Image.new("RGB", (1280, 960), (58, 62, 72))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 760, 1280, 960], fill=(70, 66, 60))
    d.rectangle([430, 120, 850, 820], fill=(120, 124, 130), outline=(30, 30, 30), width=4)
    d.rectangle([450, 140, 830, 800], fill=(30, 32, 36))
    for i, yy in enumerate([200, 380, 560]):
        d.rectangle([460, yy, 820, yy + 140], fill=(18, 18, 20))
    d.rounded_rectangle([480, 215, 800, 325], 10, fill=(8, 8, 8), outline=(60, 60, 60))
    d.text((640, 270), "ES-0007", fill=(200, 200, 200), font=FONT[18], anchor="mm")
    d.rectangle([490, 395, 790, 505], fill=(20, 90, 40))
    d.rectangle([520, 410, 760, 470], fill=(140, 140, 150))
    d.text((640, 500), "ES-0003  THERMAL-MECH (NON-FUNCTIONAL)", fill=(220, 220, 220), font=FONT[11], anchor="mm")
    d.rectangle([500, 590, 640, 660], fill=(60, 60, 140))
    d.rectangle([680, 590, 790, 650], fill=(150, 150, 150))
    d.polygon([(850, 120), (1010, 170), (1010, 770), (850, 820)], fill=(160, 190, 200), outline=(30, 30, 30))
    d.rectangle([862, 380, 918, 470], fill=(25, 25, 30))
    d.rectangle([872, 392, 908, 412], fill=(70, 200, 90))
    pb = placard(d, 600, 860, 1)
    img = grain(img, "csu_001")
    ann("EV-030", "cabinet", [430, 120, 580, 700]); ann("EV-030", "empty_slot_ES-0007", [480, 215, 320, 110])
    ann("EV-030", "item_ES-0003", [490, 395, 300, 110]); ann("EV-030", "keypad_badge_reader", [862, 380, 56, 90])
    ann("EV-030", "evidence_placard", pb, "1")
    save_jpeg(out, "EV-030", img, exif_bytes(lt("2026-10-19 10:05:31"), "Nikon", "D7500",
                                             "SBRPD CSU. Item 1: cabinet SC-EBC-01. SYNTHETIC", "HQ",
                                             unique="CSU-26-104417-001"))
    # EV-031 keypad close-up
    img = Image.new("RGB", (1280, 960), (140, 144, 150))
    d = ImageDraw.Draw(img)
    d.rectangle([380, 140, 900, 760], fill=(40, 42, 46), outline=(20, 20, 20), width=6)
    for row in range(4):
        for col in range(3):
            x0, y0 = 450 + col * 130, 330 + row * 100
            d.rounded_rectangle([x0, y0, x0 + 110, y0 + 80], 10, fill=(90, 92, 98))
            d.text((x0 + 55, y0 + 40), "123456789*0#"[row * 3 + col], fill=(230, 230, 230), font=FONT[28], anchor="mm")
    d.rectangle([520, 170, 760, 290], fill=(25, 25, 25)); d.ellipse([620, 200, 660, 240], fill=(220, 40, 40))
    g = rng("powder")
    for _ in range(40):
        x, y = g.randint(450, 820), g.randint(330, 720)
        d.ellipse([x, y, x + g.randint(10, 40), y + g.randint(8, 26)], fill=(150, 150, 150))
    rb = ruler(d, 400, 800, 480); pb = placard(d, 960, 780, 2)
    img = grain(img, "csu_002")
    ann("EV-031", "keypad", [450, 330, 370, 380]); ann("EV-031", "badge_reader", [520, 170, 240, 120])
    ann("EV-031", "fingerprint_powder", [450, 330, 410, 410], "swab Q1 collected after photo")
    ann("EV-031", "scale_ruler", rb); ann("EV-031", "evidence_placard", pb, "2")
    save_jpeg(out, "EV-031", img, exif_bytes(lt("2026-10-19 10:08:12"), "Nikon", "D7500",
                                             "SBRPD CSU. Item 2: keypad SC-EBC-01 (swab Q1). SYNTHETIC", "HQ",
                                             unique="CSU-26-104417-002"))
    # EV-032 wastebasket
    img = Image.new("RGB", (1280, 960), (96, 84, 72))
    d = ImageDraw.Draw(img)
    g = rng("carpet")
    for _ in range(3000):
        x, y = g.randint(0, 1279), g.randint(0, 959)
        d.point((x, y), fill=(80 + g.randint(0, 30), 70 + g.randint(0, 25), 60 + g.randint(0, 20)))
    d.polygon([(420, 260), (860, 260), (800, 820), (480, 820)], fill=(40, 40, 44), outline=(15, 15, 15))
    d.ellipse([420, 230, 860, 300], fill=(25, 25, 28), outline=(15, 15, 15), width=4)
    gb1 = wine_glass(d, 520, 160, 1.4); gb2 = wine_glass(d, 680, 170, 1.4, lipstick=True)
    d.rectangle([600, 120, 640, 260], fill=(30, 60, 40)); d.rectangle([608, 90, 632, 125], fill=(30, 60, 40))
    pb = placard(d, 960, 820, 3)
    img = grain(img, "csu_003")
    ann("EV-032", "wastebasket", [420, 230, 440, 590]); ann("EV-032", "wine_glass", gb1, "later Q3")
    ann("EV-032", "wine_glass", gb2, "later Q4; lipstick residue on rim"); ann("EV-032", "wine_bottle", [600, 90, 40, 170])
    ann("EV-032", "evidence_placard", pb, "3")
    save_jpeg(out, "EV-032", img, exif_bytes(lt("2026-10-19 10:14:47"), "Nikon", "D7500",
                                             "SBRPD CSU. Item 3: wastebasket office 4-01. SYNTHETIC", "HQ",
                                             unique="CSU-26-104417-003"))
    # EV-033 glasses on evidence paper
    img = Image.new("RGB", (1280, 960), (176, 140, 98))
    d = ImageDraw.Draw(img)
    b = wine_glass(d, 200, 560, 2.4, lipstick=True, lying=True)
    a = wine_glass(d, 200, 260, 2.4, lying=True)
    for (x, y, t) in [(820, 300, "Q3  GLASS A"), (820, 600, "Q4  GLASS B")]:
        d.rectangle([x, y, x + 260, y + 60], fill=(250, 250, 245), outline=(30, 30, 30), width=2)
        d.text((x + 130, y + 30), t, fill=(10, 10, 10), font=FONT[22], anchor="mm")
    rb = ruler(d, 200, 850, 600); pb = placard(d, 1100, 820, 4)
    img = grain(img, "csu_004")
    ann("EV-033", "wine_glass_Q3", a); ann("EV-033", "wine_glass_Q4", b)
    ann("EV-033", "lipstick_mark", [195, 565, 50, 100], "on Q4 rim"); ann("EV-033", "scale_ruler", rb)
    ann("EV-033", "evidence_placard", pb, "4")
    save_jpeg(out, "EV-033", img, exif_bytes(lt("2026-10-19 10:19:05"), "Nikon", "D7500",
                                             "SBRPD CSU. Item 4: glasses Q3 and Q4. SYNTHETIC", "HQ",
                                             unique="CSU-26-104417-004"))
    # EV-034 CEO desk and coat stand
    img = Image.new("RGB", (1280, 960), (205, 200, 190))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 1280, 300], fill=(160, 185, 205)); d.line([640, 0, 640, 300], fill=(90, 90, 90), width=6)
    d.rectangle([80, 520, 900, 600], fill=(110, 75, 45)); d.rectangle([100, 600, 140, 900], fill=(90, 60, 35))
    d.rectangle([840, 600, 880, 900], fill=(90, 60, 35))
    d.rectangle([300, 300, 700, 520], fill=(20, 20, 24)); d.rectangle([315, 315, 685, 505], fill=(20, 40, 90))
    d.text((500, 395), "Locked", fill=(230, 230, 240), font=FONT[22], anchor="mm")
    d.text((500, 430), "AUR-EXEC-0001", fill=(200, 200, 220), font=FONT[13], anchor="mm")
    d.rectangle([360, 530, 640, 560], fill=(50, 50, 55))
    d.line([1080, 220, 1080, 900], fill=(40, 30, 25), width=10); d.line([1020, 900, 1140, 900], fill=(40, 30, 25), width=10)
    d.polygon([(1030, 240), (1130, 240), (1150, 560), (1010, 560)], fill=(35, 38, 48))
    d.line([1060, 250, 1075, 470], fill=(20, 20, 160), width=4); d.line([1100, 250, 1085, 470], fill=(20, 20, 160), width=4)
    d.rectangle([1050, 470, 1110, 555], fill=(245, 245, 245), outline=(30, 30, 30))
    d.text((1080, 492), "AURION", fill=(20, 20, 20), font=FONT[11], anchor="mm")
    d.rectangle([1062, 505, 1098, 540], fill=(170, 170, 175))
    pb = placard(d, 160, 460, 5)
    img = grain(img, "csu_005")
    ann("EV-034", "workstation_monitor", [300, 300, 400, 220], "AUR-EXEC-0001 locked")
    ann("EV-034", "coat_stand", [1010, 220, 140, 690]); ann("EV-034", "jacket", [1010, 240, 140, 320])
    ann("EV-034", "badge_on_lanyard", [1050, 250, 60, 305], "employee badge left on coat stand")
    ann("EV-034", "evidence_placard", pb, "5")
    save_jpeg(out, "EV-034", img, exif_bytes(lt("2026-10-19 10:22:40"), "Nikon", "D7500",
                                             "SBRPD CSU. Item 5: office 4-01. SYNTHETIC", "HQ",
                                             unique="CSU-26-104417-005"))
    # EV-035 P2 elevator lobby door
    img = Image.new("RGB", (1280, 960), (110, 110, 108))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 760, 1280, 960], fill=(80, 80, 78))
    d.rectangle([440, 180, 800, 780], fill=(150, 155, 160), outline=(40, 40, 40), width=5)
    d.rectangle([580, 260, 660, 380], fill=(60, 70, 80)); d.rectangle([760, 470, 785, 500], fill=(30, 30, 30))
    d.rectangle([850, 430, 920, 520], fill=(25, 25, 28)); d.ellipse([875, 445, 895, 465], fill=(40, 200, 80))
    d.rectangle([470, 110, 770, 160], fill=(20, 60, 140)); d.text((620, 135), "P2 ELEVATOR LOBBY", fill=(240, 240, 240),
                                                                  font=FONT[22], anchor="mm")
    d.rectangle([700, 180, 790, 215], fill=(60, 60, 60))
    pb = placard(d, 300, 820, 6)
    img = grain(img, "csu_006")
    ann("EV-035", "door", [440, 180, 360, 600], "E-P2-ELEV"); ann("EV-035", "badge_reader", [850, 430, 70, 90])
    ann("EV-035", "door_closer", [700, 180, 90, 35]); ann("EV-035", "evidence_placard", pb, "6")
    save_jpeg(out, "EV-035", img, exif_bytes(lt("2026-10-19 10:31:18"), "Nikon", "D7500",
                                             "SBRPD CSU. Item 6: door E-P2-ELEV. SYNTHETIC", "HQ",
                                             unique="CSU-26-104417-006"))
    # EV-036 restaurant (Halvorsen iPhone)
    img = Image.new("RGB", (1600, 1200), (60, 35, 20))
    d = ImageDraw.Draw(img)
    g = rng("bokeh")
    for _ in range(26):
        x, y, rr = g.randint(0, 1600), g.randint(0, 420), g.randint(18, 60)
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(200 + g.randint(0, 55), 150 + g.randint(0, 60), 60))
    d.rectangle([0, 600, 1600, 1200], fill=(70, 40, 22))
    d.polygon([(1080, 300), (1420, 300), (1460, 640), (1040, 640)], fill=(50, 30, 20))
    d.rounded_rectangle([1130, 420, 1380, 640], 20, fill=(196, 164, 112), outline=(120, 95, 60), width=4)
    d.arc([1170, 330, 1340, 470], 180, 360, fill=(150, 120, 80), width=10)
    d.polygon([(1000, 560), (1220, 600), (1200, 690), (980, 650)], fill=(28, 28, 34))
    d.ellipse([300, 760, 640, 900], fill=(235, 232, 225)); d.ellipse([860, 760, 1200, 900], fill=(235, 232, 225))
    gl1 = wine_glass(d, 560, 600, 2.0); gl2 = wine_glass(d, 900, 600, 2.0, lipstick=True)
    d.rectangle([740, 700, 760, 780], fill=(240, 230, 200)); d.ellipse([738, 680, 762, 704], fill=(255, 200, 80))
    img = grain(img, "img_4471", 5)
    ann("EV-036", "wine_glass", gl1); ann("EV-036", "wine_glass", gl2, "lipstick on rim")
    ann("EV-036", "tote_bag_tan", [1130, 330, 250, 310], "large light-brown tote on opposite chair")
    ann("EV-036", "dark_coat_sleeve", [980, 560, 240, 130]); ann("EV-036", "place_settings", [300, 760, 900, 140], "two")
    save_jpeg(out, "EV-036", img, exif_bytes(T["photo_restaurant"], "Apple", "iPhone 16 Pro", "IMG_4471. SYNTHETIC",
                                             "OSTERIA", software="iOS 20.0.1", unique="IMG_4471"))
    reg.key("PHOTO_RESTAURANT_1017", "EV-036", "file", "EXIF 2026-10-17 20:58:12 -07:00, GPS Osteria Lumen")
    # EV-037 sunset
    img = Image.new("RGB", (1600, 1200))
    a = np.zeros((1200, 1600, 3), dtype=np.uint8)
    for y in range(1200):
        f = y / 1200
        a[y, :, :] = (int(250 - 120 * f), int(150 - 90 * f), int(80 + 40 * f))
    img = Image.fromarray(a)
    d = ImageDraw.Draw(img)
    d.polygon([(0, 900), (300, 760), (700, 860), (1100, 720), (1600, 840), (1600, 1200), (0, 1200)], fill=(40, 30, 40))
    d.ellipse([700, 600, 900, 800], fill=(255, 200, 120))
    img = grain(img, "img_4402", 4)
    ann("EV-037", "landscape_sunset", [0, 0, 1600, 1200])
    save_jpeg(out, "EV-037", img, exif_bytes(lt("2026-08-16 19:48:30"), "Apple", "iPhone 16 Pro", "IMG_4402. SYNTHETIC",
                                             "H_HOME", software="iOS 19.6", unique="IMG_4402"))
    # EV-038 whiteboard
    img = Image.new("RGB", (1600, 1200), (225, 228, 230))
    d = ImageDraw.Draw(img)
    d.rectangle([80, 80, 1520, 1120], fill=(250, 250, 250), outline=(120, 120, 120), width=8)
    d.text((800, 170), "KESTREL KEYNOTE - RUN OF SHOW", fill=(20, 40, 160), font=FONT[40], anchor="mm")
    boxes = [("1. Why now", 200, 300), ("2. perf/W", 560, 300), ("3. the bird (live demo)", 920, 300),
             ("4. customers", 200, 600), ("5. availability", 560, 600), ("6. Q&A", 920, 600)]
    for t, x, y in boxes:
        d.rectangle([x, y, x + 320, y + 160], outline=(30, 30, 30), width=4)
        d.text((x + 160, y + 80), t, fill=(30, 30, 30), font=FONT[22], anchor="mm")
    d.line([520, 380, 560, 380], fill=(200, 30, 30), width=5); d.line([880, 380, 920, 380], fill=(200, 30, 30), width=5)
    d.text((800, 950), "demo unit = ES-0007 (the working one!)", fill=(200, 30, 30), font=FONT[28], anchor="mm")
    img = grain(img, "img_4433", 3)
    ann("EV-038", "whiteboard_text", [80, 80, 1440, 1040], "'the bird' used internally for Kestrel; ES-0007 is the working unit")
    save_jpeg(out, "EV-038", img, exif_bytes(lt("2026-10-13 11:20:05"), "Apple", "iPhone 16 Pro", "IMG_4433. SYNTHETIC",
                                             "HQ", software="iOS 20.0.1", unique="IMG_4433"))
    reg.key("PHOTO_WHITEBOARD_BIRD", "EV-038", "file", "'the bird' is internal slang for Kestrel; ES-0007 is the working unit")
    # EV-039 coffee and notebook
    img = Image.new("RGB", (1600, 1200), (150, 120, 90))
    d = ImageDraw.Draw(img)
    d.ellipse([500, 400, 900, 800], fill=(240, 240, 235)); d.ellipse([560, 460, 840, 740], fill=(110, 70, 40))
    d.rectangle([950, 350, 1400, 900], fill=(30, 30, 35)); d.line([1000, 450, 1350, 450], fill=(200, 200, 200), width=3)
    img = grain(img, "img_4458", 4)
    ann("EV-039", "coffee_cup", [500, 400, 400, 400]); ann("EV-039", "notebook", [950, 350, 450, 550])
    save_jpeg(out, "EV-039", img, exif_bytes(lt("2026-09-09 12:31:44"), "Apple", "iPhone 16 Pro", "IMG_4458. SYNTHETIC",
                                             "LUNCH2", software="iOS 19.6", unique="IMG_4458"))
    # EV-040 visitor kiosk capture
    img = Image.new("RGB", (640, 800), (190, 192, 196))
    d = ImageDraw.Draw(img)
    d.ellipse([230, 150, 410, 360], fill=(60, 50, 45))
    d.rectangle([230, 230, 410, 420], fill=(60, 50, 45))
    d.ellipse([250, 170, 390, 340], fill=(170, 150, 135))
    d.polygon([(140, 800), (180, 470), (320, 420), (460, 470), (500, 800)], fill=(232, 222, 200))
    d.rectangle([0, 700, 640, 800], fill=(20, 30, 50))
    d.text((320, 728), f"VISITOR  {vis_vid}", fill=(240, 240, 240), font=FONT[22], anchor="mm")
    d.text((320, 765), "2026-10-07 14:21  HOST: R. HALVORSEN", fill=(220, 220, 220), font=FONT[15], anchor="mm")
    img = grain(img, "visitor", 4)
    ann("EV-040", "person_head_shoulders", [140, 150, 360, 550], "visitor; cream-coloured jacket; face not rendered")
    save_jpeg(out, "EV-040", img, exif_bytes(lt("2026-10-07 14:21:37"), "Aurion", "VisitorKiosk K2",
                                             f"Visitor capture {vis_vid}. SYNTHETIC", None, software="LobbyDesk 5.2",
                                             unique=vis_vid))
    reg.key("PHOTO_VISITOR_1007", "EV-040", "file", f"visit {vis_vid}")
    for e in ["EV-030", "EV-031", "EV-032", "EV-033", "EV-034", "EV-035", "EV-036", "EV-038", "EV-040"]:
        reg.rec(e, "file", "key" if e in ("EV-033", "EV-036", "EV-034") else "supporting")
    for e in ["EV-037", "EV-039"]:
        reg.rec(e, "file", "noise", "irrelevant_media")


# ----------------------------------------------------------------------------- video
def person(d, x, y, h, color, phase=0.0, coat=False, bag=None, holding=False):
    hr = h * 0.11
    d.ellipse([x - hr, y - h, x + hr, y - h + 2 * hr], fill=(120, 112, 105))
    top = y - h + 2 * hr
    bottom = y - h * (0.18 if coat else 0.45)
    d.rectangle([x - h * 0.15, top, x + h * 0.15, bottom], fill=color)
    sw = np.sin(phase) * h * 0.12
    d.line([x - h * 0.06, bottom, x - h * 0.06 + sw, y], fill=(25, 25, 28), width=max(2, int(h * 0.07)))
    d.line([x + h * 0.06, bottom, x + h * 0.06 - sw, y], fill=(25, 25, 28), width=max(2, int(h * 0.07)))
    box = [x - h * 0.17, y - h, h * 0.34, h]
    if bag == "side":
        d.rectangle([x + h * 0.15, y - h * 0.62, x + h * 0.42, y - h * 0.32], fill=(190, 160, 110))
        box = [x - h * 0.17, y - h, h * 0.6, h]
    elif bag == "front":
        d.rectangle([x - h * 0.2, y - h * 0.66, x + h * 0.2, y - h * 0.36], fill=(190, 160, 110))
    return [round(v) for v in box]


def car(d, x, y, color=(92, 94, 100), plate="8RHV521"):
    w, h = 132, 46
    d.rounded_rectangle([x, y - h, x + w, y - 10], 8, fill=color)
    d.polygon([(x + 28, y - h), (x + 40, y - h - 22), (x + 98, y - h - 22), (x + 112, y - h)], fill=color)
    d.polygon([(x + 36, y - h - 2), (x + 45, y - h - 18), (x + 94, y - h - 18), (x + 104, y - h - 2)], fill=(40, 45, 55))
    d.ellipse([x + 14, y - 22, x + 38, y + 2], fill=(15, 15, 15)); d.ellipse([x + 94, y - 22, x + 118, y + 2], fill=(15, 15, 15))
    d.rectangle([x + w - 6, y - 38, x + w, y - 30], fill=(200, 30, 30))
    d.rectangle([x + w - 34, y - 24, x + w - 8, y - 16], fill=(230, 230, 230))
    d.text((x + w - 21, y - 20), plate, fill=(20, 20, 20), font=FONT[9], anchor="mm")
    return [x, y - h - 22, w, h + 24]


def path_pos(keys, t):
    if t < keys[0][0] or t > keys[-1][0]:
        return None
    for (t0, x0, y0), (t1, x1, y1) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            f = 0 if t1 == t0 else (t - t0) / (t1 - t0)
            return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, (x1 != x0 or y1 != y0)
    return keys[-1][1], keys[-1][2], False


def garage_bg(seed):
    img = Image.new("RGB", (W, H), (62, 62, 60))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 70], fill=(48, 48, 50))
    for x in (180, 460):
        d.rectangle([x, 60, x + 24, 330], fill=(85, 85, 84))
    for x in range(150, 600, 70):
        d.line([x, 330, x + 40, 250], fill=(170, 170, 120), width=2)
    d.rectangle([60, 140, 125, 262], fill=(130, 134, 138), outline=(30, 30, 30))
    d.rectangle([132, 190, 144, 206], fill=(20, 20, 20))
    d.text((92, 128), "ELEV LOBBY", fill=(200, 200, 200), font=FONT[9], anchor="mm")
    d.rectangle([560, 150, 610, 250], fill=(120, 110, 100), outline=(30, 30, 30))
    d.text((585, 140), "SERVICE", fill=(200, 200, 200), font=FONT[9], anchor="mm")
    d.rectangle([520, 300, 600, 350], fill=(40, 80, 50))
    return grain(img, seed, 3)


def lobby_bg(seed):
    img = Image.new("RGB", (W, H), (150, 148, 142))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 260, W, H], fill=(120, 118, 112))
    d.rectangle([200, 60, 440, 280], fill=(35, 40, 55), outline=(30, 30, 30), width=4)
    d.line([320, 60, 320, 280], fill=(30, 30, 30), width=4)
    d.rectangle([452, 150, 470, 176], fill=(30, 30, 30))
    d.rectangle([20, 200, 160, 280], fill=(90, 80, 70))
    d.ellipse([520, 180, 600, 260], fill=(50, 90, 50)); d.rectangle([550, 250, 570, 290], fill=(80, 60, 40))
    return grain(img, seed, 3)


def corridor_bg(seed):
    img = Image.new("RGB", (W, H), (120, 122, 126))
    d = ImageDraw.Draw(img)
    d.polygon([(0, H), (250, 200), (390, 200), (W, H)], fill=(95, 92, 88))
    d.polygon([(0, 0), (250, 120), (390, 120), (W, 0)], fill=(150, 152, 156))
    d.rectangle([250, 120, 390, 200], fill=(70, 72, 78))
    d.polygon([(40, 60), (110, 100), (110, 250), (40, 300)], fill=(110, 90, 70))
    d.text((80, 50), "4-SUITE", fill=(30, 30, 30), font=FONT[11], anchor="mm")
    d.polygon([(480, 110), (520, 130), (520, 220), (480, 240)], fill=(110, 90, 70))
    d.text((500, 100), "4-12 EBC", fill=(30, 30, 30), font=FONT[11], anchor="mm")
    return grain(img, seed, 3)


def overlay(img, t, cam):
    d = ImageDraw.Draw(img)
    s = local_str(t)
    d.text((9, 9), s, fill=(0, 0, 0), font=FONT[15]); d.text((8, 8), s, fill=(255, 255, 255), font=FONT[15])
    d.text((9, H - 21), cam, fill=(0, 0, 0), font=FONT[13]); d.text((8, H - 22), cam, fill=(255, 255, 0), font=FONT[13])


def render_clip(out: Out, eid: str, cam: str, label: str, start, seconds: int, fps: int, bg, actors, extras=None):
    """actors: dicts with id, cls, identity, kind, keys [(t,x,y)], color, h, coat, bag."""
    tmpdir = tempfile.mkdtemp(prefix="kestrel_")
    tmp = os.path.join(tmpdir, "clip.mp4")
    creation = start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000000Z")
    writer = imageio_ffmpeg.write_frames(
        tmp, (W, H), fps=fps, codec="libx264", quality=None, pix_fmt_out="yuv420p", macro_block_size=8,
        output_params=["-crf", "28", "-preset", "medium", "-g", str(fps * 60), "-threads", "1",
                       "-movflags", "+faststart", "-map_metadata", "-1", "-fflags", "+bitexact",
                       "-flags:v", "+bitexact", "-metadata", f"creation_time={creation}",
                       "-metadata", f"title={cam} {local_str(start)}",
                       "-metadata", "comment=SYNTHETIC CCTV RENDER - FICTIONAL TRAINING DATA"])
    writer.send(None)
    n = seconds * fps
    for fi in range(n):
        tsec = fi / fps
        t = start + timedelta(seconds=tsec)
        img = bg.copy()
        if extras:
            extras(img, tsec)
        d = ImageDraw.Draw(img)
        for a in actors:
            p = path_pos(a["keys"], tsec)
            if p is None:
                continue
            x, y, moving = p
            if a["kind"] == "car":
                box = car(d, x, y, a.get("color", (92, 94, 100)), a.get("plate", ""))
            elif a["kind"] == "cart":
                d.rectangle([x - 14, y - 26, x + 14, y - 4], fill=(200, 170, 30)); d.ellipse([x - 12, y - 6, x - 4, y + 2], fill=(20, 20, 20))
                d.ellipse([x + 4, y - 6, x + 12, y + 2], fill=(20, 20, 20))
                box = [x - 14, y - 26, 28, 28]
            else:
                phase = tsec * 9 if moving else 0.0
                box = person(d, x, y, a.get("h", 70), a["color"], phase, a.get("coat", False), a.get("bag"))
            ANN_TRACKS.append({"evidence_id": eid, "camera_id": cam, "frame": fi, "t_local": iso_local(t),
                               "track_id": a["id"], "class": a["cls"], "identity_truth": a["identity"],
                               "bbox_xywh": [int(v) for v in box], "attributes": a.get("attrs", {})})
        overlay(img, t, label)
        writer.send(np.asarray(img).tobytes())
    writer.close()
    dst = out._ensure(path_of(eid))
    shutil.copyfile(tmp, dst)
    shutil.rmtree(tmpdir, ignore_errors=True)


def videos(out: Out, reg: Registry):
    # EV-020 lobby, Marco Bellini denied
    start = lt("2026-10-17 19:00:30")
    led = {"red": [(101, 103), (114, 116)]}

    def lobby_extras(img, t):
        on = any(a <= t <= b for a, b in led["red"])
        ImageDraw.Draw(img).ellipse([456, 156, 466, 166], fill=(230, 30, 30) if on else (40, 40, 40))

    marco = {"id": "trk-lobby-1", "cls": "person", "identity": "P-09 Marco Bellini", "kind": "person",
             "color": (110, 30, 35), "h": 120,
             "keys": [(60, 640, 300), (95, 405, 285), (190, 405, 285), (215, 640, 300)],
             "attrs": {"location": "outside glass entrance", "outcome": "badge denied twice, left"}}
    render_clip(out, "EV-020", "CAM-E-L1-01", "CAM-E-L1-01 LOBBY", start, 240, 2, lobby_bg("lobby"), [marco],
                lobby_extras)
    # EV-021 P2 arrival
    start = lt("2026-10-17 21:35:00")
    door_open = (93, 112)

    def p2_extras_a(img, t):
        if door_open[0] <= t <= door_open[1]:
            ImageDraw.Draw(img).rectangle([62, 142, 123, 260], fill=(15, 15, 18))

    actors = [
        {"id": "trk-p2a-car", "cls": "vehicle", "identity": "V-01 gray sedan 8RHV521 (Halvorsen)", "kind": "car",
         "plate": "8RHV521", "keys": [(50, 660, 300), (62, 300, 300), (180, 300, 300)]},
        {"id": "trk-p2a-1", "cls": "person", "identity": "P-01 Richard Halvorsen", "kind": "person",
         "color": (40, 45, 62), "h": 72, "keys": [(70, 300, 312), (91, 112, 262), (110, 100, 262)],
         "attrs": {"role": "driver"}},
        {"id": "trk-p2a-2", "cls": "person", "identity": "P-02 Vivian Shen", "kind": "person", "color": (28, 28, 34),
         "h": 68, "coat": True, "bag": "side", "keys": [(72, 440, 312), (93, 125, 264), (98, 95, 262)],
         "attrs": {"role": "passenger", "clothing": "long dark coat", "carrying": "large light-brown tote"}},
    ]
    render_clip(out, "EV-021", "CAM-E-P2-02", "CAM-E-P2-02 P2 GARAGE", start, 180, 4, garage_bg("p2"), actors,
                p2_extras_a)
    # EV-022 P2 departure
    start = lt("2026-10-17 23:02:30")

    def p2_extras_b(img, t):
        d = ImageDraw.Draw(img)
        if 70 <= t <= 80:
            d.rectangle([62, 142, 123, 260], fill=(15, 15, 18))
        if t <= 4 or 213 <= t <= 219:
            d.rectangle([562, 152, 608, 248], fill=(15, 15, 18))

    actors = [
        {"id": "trk-p2b-car", "cls": "vehicle", "identity": "V-01 gray sedan 8RHV521 (Halvorsen)", "kind": "car",
         "plate": "8RHV521", "keys": [(0, 300, 300), (275, 300, 300), (290, 660, 300)]},
        {"id": "trk-p2b-3", "cls": "person", "identity": "P-08 Luis Ortega", "kind": "person", "color": (90, 100, 120),
         "h": 66, "keys": [(0, 585, 258), (10, 560, 330), (150, 560, 330), (213, 585, 258), (218, 585, 252)],
         "attrs": {"role": "custodian"}},
        {"id": "trk-p2b-cart", "cls": "object", "identity": "custodial cart", "kind": "cart",
         "keys": [(0, 600, 262), (10, 580, 332), (150, 580, 332), (213, 600, 262), (216, 600, 258)]},
        {"id": "trk-p2b-1", "cls": "person", "identity": "P-01 Richard Halvorsen", "kind": "person",
         "color": (40, 45, 62), "h": 72, "keys": [(72, 100, 262), (97, 290, 312), (258, 290, 312), (259, 300, 308)],
         "attrs": {"role": "driver"}},
        {"id": "trk-p2b-2", "cls": "person", "identity": "P-02 Vivian Shen", "kind": "person", "color": (28, 28, 34),
         "h": 68, "coat": True, "bag": "front", "keys": [(74, 100, 262), (100, 440, 312), (262, 440, 312), (263, 430, 308)],
         "attrs": {"clothing": "long dark coat", "carrying": "large light-brown tote, held with both arms"}},
    ]
    render_clip(out, "EV-022", "CAM-E-P2-02", "CAM-E-P2-02 P2 GARAGE", start, 330, 4, garage_bg("p2"), actors,
                p2_extras_b)
    # EV-023 floor 4 corridor, outage begins 21:00:00
    start = lt("2026-10-17 20:59:00")
    cbg = corridor_bg("f4")
    lost = Image.new("RGB", (W, H), (10, 20, 90))
    dd = ImageDraw.Draw(lost)
    dd.text((W // 2, H // 2), "NO VIDEO", fill=(240, 240, 240), font=FONT[40], anchor="mm")

    def f4_extras(img, t):
        if t >= 60:
            img.paste(lost)

    render_clip(out, "EV-023", "CAM-E-F4-01", "CAM-E-F4-01 FLOOR 4 CORRIDOR", start, 90, 2, cbg, [], f4_extras)
    for e, rel in [("EV-020", "red_herring"), ("EV-021", "key"), ("EV-022", "key"), ("EV-023", "supporting")]:
        reg.rec(e, "file", rel)
    reg.key("VIDEO_LOBBY_BELLINI", "EV-020", "t=19:02:05-19:03:50")
    reg.key("VIDEO_P2_ARRIVAL_TWO", "EV-021", "t=21:36:10-21:36:52", "two occupants exit the gray sedan; passenger carries a large tote")
    reg.key("VIDEO_P2_DEPART_TWO", "EV-022", "t=23:03:40-23:07:20", "two people leave the elevator lobby; tote carried with both arms")
    reg.key("VIDEO_P2_CUSTODIAN", "EV-022", "t=23:02:30-23:06:05")
    reg.key("VIDEO_F4_OUTAGE", "EV-023", "t=21:00:00", "video loss begins")


def vms_tables(out: Out, reg: Registry):
    eid = "EV-024"
    rows = []
    for i, (e, cam, s, en, fps) in enumerate([
            ("EV-020", "CAM-E-L1-01", "2026-10-17 19:00:30", "2026-10-17 19:04:30", 2),
            ("EV-021", "CAM-E-P2-02", "2026-10-17 21:35:00", "2026-10-17 21:38:00", 4),
            ("EV-022", "CAM-E-P2-02", "2026-10-17 23:02:30", "2026-10-17 23:08:00", 4),
            ("EV-023", "CAM-E-F4-01", "2026-10-17 20:59:00", "2026-10-17 21:00:30", 2)], 1):
        p = out.path(path_of(e))
        with open(p, "rb") as f:
            sha = hashlib.sha256(f.read()).hexdigest()
        rid = f"VX-{i:03d}"
        rows.append([rid, "CLIP", cam, path_of(e).split("/")[-1], s, en, fps, f"{W}x{H}", sha, "EXPORTED", ""])
        reg.rec(eid, f"record_id={rid}", "supporting")
    status = [("CAM-E-F4-01", "2026-10-17 21:00:00", "2026-10-17 23:30:00", "OFFLINE_MAINTENANCE",
               "CHG-4471 NVR firmware update (requested 2026-10-15)", "VMS_F4_01_OUTAGE", "key"),
              ("CAM-E-F4-02", "2026-10-17 21:00:00", "2026-10-17 23:30:00", "OFFLINE_MAINTENANCE",
               "CHG-4471 NVR firmware update (requested 2026-10-15)", "VMS_F4_02_OUTAGE", "key"),
              ("CAM-E-P2-02", "2026-10-16 00:00:00", "2026-10-19 12:00:00", "RECORDING", "Continuous", "", "context"),
              ("CAM-E-L1-01", "2026-10-16 00:00:00", "2026-10-19 12:00:00", "RECORDING", "Continuous", "", "context"),
              ("CAM-E-F4-02", "2026-10-07 00:00:00", "2026-10-07 23:59:59", "RECORDING",
               "Continuous; not exported (retention 30 days)", "VMS_EBC_1007_AVAILABLE", "key")]
    for i, (cam, s, en, st, note, tag, rel) in enumerate(status, len(rows) + 1):
        rid = f"VX-{i:03d}"
        rows.append([rid, "STATUS", cam, "", s, en, "", "", "", st, note])
        if tag:
            reg.key(tag, eid, f"record_id={rid}")
        reg.rec(eid, f"record_id={rid}", rel, "", [tag] if tag else [])
    out.csv(path_of(eid), ["record_id", "record_type", "camera_id", "clip_file", "start_local", "end_local", "fps",
                           "resolution", "sha256", "status", "notes"], rows)

    eid = "EV-025"
    r = rng("vms_analytics")
    evs = []
    for day in ["2026-10-16", "2026-10-19"]:
        t = lt(f"{day} 07:00")
        end = lt(f"{day} 19:30") if day == "2026-10-16" else lt(f"{day} 12:00")
        while t < end:
            cam, zone, cls = r.choice([("CAM-E-L1-01", "L1-ENTRANCE", "person"), ("CAM-E-P2-02", "P2-ROW-C", "vehicle"),
                                       ("CAM-E-P2-02", "P2-ELEV-DOOR", "person"), ("CAM-E-F4-01", "F4-CORRIDOR", "person")])
            evs.append((t, cam, zone, cls, r.randint(1, 4), round(r.uniform(0.7, 0.97), 2), "COUNT_CHANGE",
                        [], "background", ""))
            t += timedelta(minutes=r.randint(3, 25), seconds=r.randint(0, 59))
    for _ in range(14):
        t = lt("2026-10-16 00:00") + timedelta(minutes=r.randint(0, 60 * 84))
        evs.append((t, r.choice(["CAM-E-P2-02", "CAM-E-L1-01"]), "ANY", r.choice(["animal", "unknown"]), 1,
                    round(r.uniform(0.21, 0.44), 2), "OBJECT_DETECTED", [], "noise", "false_positive_detection"))
    key = [
        ("2026-10-17 19:01:58", "CAM-E-L1-01", "L1-ENTRANCE-EXT", "person", 1, 0.91, "ZONE_ENTER", ["VA_LOBBY_1902"], "red_herring"),
        ("2026-10-17 19:03:58", "CAM-E-L1-01", "L1-ENTRANCE-EXT", "person", 0, 0.88, "ZONE_EXIT", [], "red_herring"),
        ("2026-10-17 21:35:52", "CAM-E-P2-02", "P2-ROW-C", "vehicle", 1, 0.95, "ZONE_ENTER", ["VA_P2_2135_VEHICLE"], "supporting"),
        ("2026-10-17 21:36:14", "CAM-E-P2-02", "P2-ROW-C", "person", 2, 0.86, "COUNT_CHANGE", ["VA_P2_2136_TWO_PERSONS"], "key"),
        ("2026-10-17 21:36:33", "CAM-E-P2-02", "P2-ELEV-DOOR", "person", 2, 0.83, "COUNT_CHANGE", ["VA_P2_2136_DOOR_TWO"], "key"),
        ("2026-10-17 21:36:52", "CAM-E-P2-02", "P2-ELEV-DOOR", "person", 0, 0.90, "ZONE_EXIT", [], "supporting"),
        ("2026-10-17 23:02:31", "CAM-E-P2-02", "P2-SVC", "person", 1, 0.84, "ZONE_ENTER", ["VA_P2_2302_CUSTODIAN"], "supporting"),
        ("2026-10-17 23:03:41", "CAM-E-P2-02", "P2-ELEV-DOOR", "person", 2, 0.81, "COUNT_CHANGE", ["VA_P2_2303_TWO_PERSONS"], "key"),
        ("2026-10-17 23:04:06", "CAM-E-P2-02", "P2-ROW-C", "person", 3, 0.79, "COUNT_CHANGE", [], "supporting"),
        ("2026-10-17 23:07:05", "CAM-E-P2-02", "P2-ROW-C", "vehicle", 0, 0.93, "ZONE_EXIT", ["VA_P2_2307_VEHICLE_EXIT"], "supporting"),
    ]
    for t, cam, zone, cls, cnt, conf, et, tags, rel in key:
        evs.append((lt(t), cam, zone, cls, cnt, conf, et, tags, rel, ""))
    evs.sort(key=lambda x: (x[0], x[1]))
    rows = []
    for i, (t, cam, zone, cls, cnt, conf, et, tags, rel, noise) in enumerate(evs, 1):
        rid = f"VA-{i:05d}"
        rows.append([rid, cam, local_str(t), zone, cls, cnt, conf, et])
        for tg in tags:
            reg.key(tg, eid, f"event_id={rid}")
        reg.rec(eid, f"event_id={rid}", rel, noise, tags)
    out.csv(path_of(eid), ["event_id", "camera_id", "timestamp_local", "zone", "object_class", "count", "confidence",
                           "event_type"], rows)


def write_all(out: Out, reg: Registry):
    ANN_TRACKS.clear()
    ANN_PHOTOS.clear()
    photos(out, reg)
    reg.key("PHOTO_WASTEBASKET", "EV-032", "file", "two wine glasses and a bottle in office 4-01 wastebasket")
    reg.key("PHOTO_GLASSES", "EV-033", "file", "Q4 has lipstick residue on the rim")
    reg.key("PHOTO_BADGE_COATSTAND", "EV-034", "file", "badge on lanyard hanging on office coat stand")
    reg.key("PHOTO_EMPTY_SLOT", "EV-030", "file", "ES-0007 slot empty; ES-0003 still present")
    videos(out, reg)
    vms_tables(out, reg)
