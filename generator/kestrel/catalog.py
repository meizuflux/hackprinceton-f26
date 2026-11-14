"""Evidence catalog: one entry per original file, with provenance and classification labels.

Fields
- modality: what kind of evidence (drives which ingestion parser applies)
- fmt: file format
- custodian: who held the data before collection
- collected_by / collected_at: who acquired it and when (Pacific time)
- method: how it was acquired (legal basis or consent)
- time_basis: how timestamps inside the file are expressed (cleaning step must normalise)
- sensitivity: handling label (restricted-biometric, confidential-pii, confidential-corporate, internal)
- admiralty: source reliability (A-F) + information credibility (1-6), graded at intake
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Ev:
    eid: str
    path: str
    modality: str
    fmt: str
    title: str
    custodian: str
    collected_by: str
    collected_at: str
    method: str
    time_basis: str
    sensitivity: str
    admiralty: str


E = "evidence/"
CATALOG: list[Ev] = [
    # 00 intake
    Ev("EV-001", E + "00_intake/incident_report.txt", "report", "txt", "SBRPD initial incident report",
       "SBRPD", "Det. Ana Reyes", "2026-10-19 13:40", "Agency record", "local wall time (PDT)",
       "confidential-pii", "B2"),
    Ev("EV-002", E + "00_intake/insurer_fnol.txt", "report", "txt", "Insurer first notice of loss and SIU referral",
       "Lattice Specialty Insurance Co.", "Karen Doyle (SIU)", "2026-10-20 11:15", "Provided by insurer to SBRPD",
       "local wall time (PDT)", "confidential-corporate", "B3"),
    Ev("EV-003", E + "00_intake/custody_log.csv", "chain_of_custody", "csv", "Chain-of-custody log for physical and digital items",
       "SBRPD Property & Evidence", "CST Lee Park", "2026-10-22 17:30", "Agency record", "local wall time (PDT)",
       "confidential-pii", "A1"),
    # 01 biological
    Ev("EV-010", E + "01_bio/lab_report_dna.txt", "biological", "txt", "Forensic DNA (STR) laboratory report LAB-26-3318",
       "South Bay Regional Forensic Laboratory", "Det. Sam Okoye", "2026-10-22 15:05", "Lab request SBRPD-26-104417",
       "local wall time (PDT)", "restricted-biometric", "A2"),
    Ev("EV-011", E + "01_bio/str_profiles.csv", "biological", "csv", "STR allele calls for questioned and known samples",
       "South Bay Regional Forensic Laboratory", "Det. Sam Okoye", "2026-10-22 15:05", "Lab request SBRPD-26-104417",
       "n/a", "restricted-biometric", "A2"),
    # 02 video
    Ev("EV-020", E + "02_video/lobby01_1900.mp4", "video", "mp4", "CCTV CAM-E-L1-01 lobby, Sat 19:00:30-19:04:30",
       "Aurion Compute Security (VMS)", "Tom Brandt", "2026-10-19 11:20", "Voluntary export by owner",
       "burned-in local time (PDT)", "confidential-pii", "A2"),
    Ev("EV-021", E + "02_video/p2cam02_2135.mp4", "video", "mp4", "CCTV CAM-E-P2-02 garage level P2, Sat 21:35:00-21:38:00",
       "Aurion Compute Security (VMS)", "Tom Brandt", "2026-10-19 11:20", "Voluntary export by owner",
       "burned-in local time (PDT)", "confidential-pii", "A2"),
    Ev("EV-022", E + "02_video/p2cam02_2302.mp4", "video", "mp4", "CCTV CAM-E-P2-02 garage level P2, Sat 23:02:30-23:08:00",
       "Aurion Compute Security (VMS)", "Tom Brandt", "2026-10-19 11:20", "Voluntary export by owner",
       "burned-in local time (PDT)", "confidential-pii", "A2"),
    Ev("EV-023", E + "02_video/f4cam01_2059.mp4", "video", "mp4", "CCTV CAM-E-F4-01 floor 4 corridor, Sat 20:59:00-21:00:30",
       "Aurion Compute Security (VMS)", "Tom Brandt", "2026-10-19 11:20", "Voluntary export by owner",
       "burned-in local time (PDT)", "confidential-pii", "A2"),
    Ev("EV-024", E + "02_video/vms_export_index.csv", "video", "csv", "VMS export index and camera status, Building E",
       "Aurion Compute Security (VMS)", "Tom Brandt", "2026-10-19 11:20", "Voluntary export by owner",
       "local wall time (PDT), no offset", "confidential-corporate", "A1"),
    Ev("EV-025", E + "02_video/vms_analytics.csv", "video", "csv", "VMS video-analytics events (object counts), Building E",
       "Aurion Compute Security (VMS)", "Tom Brandt", "2026-10-19 11:20", "Voluntary export by owner",
       "local wall time (PDT), no offset", "confidential-corporate", "B2"),
    # 03 photo
    Ev("EV-030", E + "03_photo/csu_001.jpg", "photo", "jpg", "Scene photo: EBC cabinet SC-EBC-01, empty ES-0007 slot",
       "SBRPD CSU", "CST Lee Park", "2026-10-19 10:05", "Scene documentation", "EXIF DateTimeOriginal + OffsetTime",
       "confidential-corporate", "A1"),
    Ev("EV-031", E + "03_photo/csu_002.jpg", "photo", "jpg", "Scene photo: cabinet keypad (swab Q1 location)",
       "SBRPD CSU", "CST Lee Park", "2026-10-19 10:08", "Scene documentation", "EXIF DateTimeOriginal + OffsetTime",
       "confidential-corporate", "A1"),
    Ev("EV-032", E + "03_photo/csu_003.jpg", "photo", "jpg", "Scene photo: CEO office wastebasket with two wine glasses",
       "SBRPD CSU", "CST Lee Park", "2026-10-19 10:14", "Scene documentation", "EXIF DateTimeOriginal + OffsetTime",
       "confidential-corporate", "A1"),
    Ev("EV-033", E + "03_photo/csu_004.jpg", "photo", "jpg", "Scene photo: wine glasses Q3 and Q4 on evidence paper",
       "SBRPD CSU", "CST Lee Park", "2026-10-19 10:19", "Scene documentation", "EXIF DateTimeOriginal + OffsetTime",
       "confidential-corporate", "A1"),
    Ev("EV-034", E + "03_photo/csu_005.jpg", "photo", "jpg", "Scene photo: CEO office 4-01 desk and coat stand",
       "SBRPD CSU", "CST Lee Park", "2026-10-19 10:22", "Scene documentation", "EXIF DateTimeOriginal + OffsetTime",
       "confidential-corporate", "A1"),
    Ev("EV-035", E + "03_photo/csu_006.jpg", "photo", "jpg", "Scene photo: P2 elevator lobby door and reader",
       "SBRPD CSU", "CST Lee Park", "2026-10-19 10:31", "Scene documentation", "EXIF DateTimeOriginal + OffsetTime",
       "confidential-corporate", "A1"),
    Ev("EV-036", E + "03_photo/IMG_4471.jpg", "photo", "jpg", "Camera-roll photo from Halvorsen iPhone (restaurant table)",
       "Richard Halvorsen", "Det. Sam Okoye", "2026-10-20 19:40", "Consent extraction (partial)",
       "EXIF DateTimeOriginal + OffsetTime + GPS", "confidential-pii", "B2"),
    Ev("EV-037", E + "03_photo/IMG_4402.jpg", "photo", "jpg", "Camera-roll photo from Halvorsen iPhone (sunset)",
       "Richard Halvorsen", "Det. Sam Okoye", "2026-10-20 19:40", "Consent extraction (partial)",
       "EXIF DateTimeOriginal + OffsetTime + GPS", "confidential-pii", "B2"),
    Ev("EV-038", E + "03_photo/IMG_4433.jpg", "photo", "jpg", "Camera-roll photo from Halvorsen iPhone (whiteboard)",
       "Richard Halvorsen", "Det. Sam Okoye", "2026-10-20 19:40", "Consent extraction (partial)",
       "EXIF DateTimeOriginal + OffsetTime + GPS", "confidential-corporate", "B2"),
    Ev("EV-039", E + "03_photo/IMG_4458.jpg", "photo", "jpg", "Camera-roll photo from Halvorsen iPhone (coffee and notebook)",
       "Richard Halvorsen", "Det. Sam Okoye", "2026-10-20 19:40", "Consent extraction (partial)",
       "EXIF DateTimeOriginal + OffsetTime + GPS", "confidential-pii", "B2"),
    Ev("EV-040", E + "03_photo/visitor_kiosk_1007.jpg", "photo", "jpg",
       "Visitor kiosk capture, 2026-10-07 visit hosted by R. Halvorsen",
       "Aurion Compute Security (visitor system)", "Tom Brandt", "2026-10-21 09:10", "Voluntary export by owner",
       "EXIF DateTimeOriginal + OffsetTime", "confidential-pii", "A2"),
    # 04 messages
    Ev("EV-050", E + "04_msgs/halvorsen_iphone.csv", "text_message", "csv", "Halvorsen iPhone message extraction (incl. recovered deleted)",
       "Richard Halvorsen", "Det. Sam Okoye", "2026-10-20 19:40", "Consent extraction (messages only)",
       "UTC ISO-8601 (Z)", "confidential-pii", "A2"),
    Ev("EV-051", E + "04_msgs/raman_android.csv", "text_message", "csv", "Raman Android message extraction",
       "Priya Raman", "Det. Sam Okoye", "2026-10-21 10:20", "Consent extraction (messages only)",
       "UTC ISO-8601 (Z)", "confidential-pii", "A2"),
    Ev("EV-052", E + "04_msgs/extraction_notes.txt", "report", "txt", "Device extraction notes and scope",
       "SBRPD Digital Forensics", "Det. Sam Okoye", "2026-10-21 12:00", "Agency record", "local wall time (PDT)",
       "confidential-pii", "A1"),
    # 05 location
    Ev("EV-060", E + "05_loc/cdr_4085550147.csv", "location", "csv", "Carrier records with cell-site location, +1-408-555-0147",
       "Carrier (synthetic)", "Det. Ana Reyes", "2026-10-22 09:30", "Search warrant SW-26-2291",
       "UTC ISO-8601 (Z)", "confidential-pii", "A2"),
    Ev("EV-061", E + "05_loc/subscriber_0147.txt", "report", "txt", "Subscriber information, +1-408-555-0147",
       "Carrier (synthetic)", "Det. Ana Reyes", "2026-10-21 08:45", "Subpoena SBRPD-SP-26-0870",
       "local wall time (PDT)", "confidential-pii", "A1"),
    Ev("EV-062", E + "05_loc/cdr_4085550163.csv", "location", "csv", "Carrier records with cell-site location, +1-408-555-0163",
       "Carrier (synthetic)", "Det. Ana Reyes", "2026-10-21 16:00", "Consent (Priya Raman)",
       "UTC ISO-8601 (Z)", "confidential-pii", "A2"),
    Ev("EV-063", E + "05_loc/halvorsen_timeline.json", "location", "json", "Halvorsen phone location history export",
       "Richard Halvorsen", "Det. Sam Okoye", "2026-10-20 19:40", "Consent",
       "UTC ISO-8601 with milliseconds (Z)", "confidential-pii", "B2"),
    Ev("EV-064", E + "05_loc/garage_lpr.csv", "location", "csv", "Garage P2 license-plate reader log",
       "Aurion Compute Security", "Tom Brandt", "2026-10-19 11:20", "Voluntary export by owner",
       "local wall time, US 12-hour format", "confidential-pii", "B2"),
    # 06 logs
    Ev("EV-070", E + "06_logs/badge_bldg_e.csv", "access_log", "csv", "Building E badge access events",
       "Aurion Compute Security (access control)", "Tom Brandt", "2026-10-19 11:20", "Voluntary export by owner",
       "local wall time (PDT), no offset; reader E-2-LAB-A clock drift noted in EV-077", "confidential-pii", "A1"),
    Ev("EV-071", E + "06_logs/cabinet_audit.jsonl", "access_log", "jsonl", "Secure cabinet SC-EBC-01 audit trail",
       "Aurion Compute Security (cabinet controller)", "Tom Brandt", "2026-10-19 11:20", "Voluntary export by owner",
       "Unix epoch milliseconds (UTC)", "confidential-corporate", "A1"),
    Ev("EV-072", E + "06_logs/rfid_inventory.csv", "access_log", "csv", "Cabinet RFID inventory scans (hourly)",
       "Aurion Compute Security (cabinet controller)", "Tom Brandt", "2026-10-19 11:20", "Voluntary export by owner",
       "ISO-8601 with offset", "confidential-corporate", "A1"),
    Ev("EV-073", E + "06_logs/visitor_log.csv", "access_log", "csv", "Visitor management log, Oct 1-19",
       "Aurion Compute Security (visitor system)", "Tom Brandt", "2026-10-21 09:10", "Voluntary export by owner",
       "local wall time (PDT)", "confidential-pii", "A2"),
    Ev("EV-074", E + "06_logs/guard_tours.csv", "access_log", "csv", "Guard tour checkpoint scans, weekend Oct 17-18",
       "Aegis Patrol Services", "Tom Brandt", "2026-10-19 14:00", "Voluntary export by owner",
       "local wall time (PDT)", "internal", "B2"),
    Ev("EV-075", E + "06_logs/ws_exec0001.csv", "system_log", "csv", "Workstation AUR-EXEC-0001 security and activity events",
       "Aurion Compute IT", "Tom Brandt", "2026-10-20 10:30", "Voluntary export by owner",
       "UTC ISO-8601 with 7-digit fraction", "confidential-corporate", "A1"),
    Ev("EV-076", E + "06_logs/ceo_calendar.ics", "calendar", "ics", "CEO calendar export, Jul-Oct 2026",
       "Jordan Ellis (EA)", "Det. Ana Reyes", "2026-10-20 09:30", "Voluntary export by owner",
       "iCalendar with TZID America/Los_Angeles", "confidential-corporate", "A2"),
    Ev("EV-077", E + "06_logs/doors_readers.csv", "facility_reference", "csv", "Door, reader and camera reference list, Building E",
       "Aurion Compute Facilities", "Tom Brandt", "2026-10-19 11:20", "Voluntary export by owner",
       "n/a", "internal", "A1"),
    Ev("EV-078", E + "06_logs/cabinet_acl.csv", "facility_reference", "csv", "Cabinet SC-EBC-01 access control list",
       "Aurion Compute Security", "Tom Brandt", "2026-10-19 11:20", "Voluntary export by owner",
       "n/a", "confidential-corporate", "A1"),
    # 07 written statements
    Ev("EV-080", E + "07_stmt/whitfield.txt", "written_statement", "txt", "Written statement of Dana Whitfield",
       "Dana Whitfield", "Det. Ana Reyes", "2026-10-19 11:30", "Voluntary statement", "local wall time (PDT)",
       "confidential-pii", "B2"),
    Ev("EV-081", E + "07_stmt/brandt.txt", "written_statement", "txt", "Written statement of Tom Brandt",
       "Tom Brandt", "Det. Ana Reyes", "2026-10-19 12:15", "Voluntary statement", "local wall time (PDT)",
       "confidential-pii", "B2"),
    Ev("EV-082", E + "07_stmt/ortega.txt", "written_statement", "txt", "Written statement of Luis Ortega",
       "Luis Ortega", "Det. Sam Okoye", "2026-10-20 22:15", "Voluntary statement", "local wall time (PDT)",
       "confidential-pii", "C3"),
    Ev("EV-083", E + "07_stmt/ellis.txt", "written_statement", "txt", "Written statement of Jordan Ellis",
       "Jordan Ellis", "Det. Ana Reyes", "2026-10-20 09:30", "Voluntary statement", "local wall time (PDT)",
       "confidential-pii", "B2"),
    Ev("EV-084", E + "07_stmt/raman.txt", "written_statement", "txt", "Written statement of Priya Raman",
       "Priya Raman", "Det. Ana Reyes", "2026-10-19 16:00", "Voluntary statement", "local wall time (PDT)",
       "confidential-pii", "C3"),
    Ev("EV-085", E + "07_stmt/e_halvorsen.txt", "written_statement", "txt", "Written statement of Elaine Halvorsen",
       "Elaine Halvorsen", "Det. Sam Okoye", "2026-10-21 10:00", "Voluntary statement", "local wall time (PDT)",
       "confidential-pii", "C3"),
    # 08 interviews
    Ev("EV-090", E + "08_intv/halvorsen_1.txt", "interview", "txt", "Interview transcript: Richard Halvorsen (1)",
       "SBRPD", "Det. Ana Reyes", "2026-10-19 15:00", "Voluntary interview, recorded", "local wall time (PDT)",
       "confidential-pii", "C4"),
    Ev("EV-091", E + "08_intv/halvorsen_2.txt", "interview", "txt", "Interview transcript: Richard Halvorsen (2)",
       "SBRPD", "Det. Ana Reyes", "2026-10-20 16:30", "Voluntary interview with counsel, recorded",
       "local wall time (PDT)", "confidential-pii", "C4"),
    Ev("EV-092", E + "08_intv/raman.txt", "interview", "txt", "Interview transcript: Priya Raman",
       "SBRPD", "Det. Sam Okoye", "2026-10-20 11:00", "Voluntary interview, recorded", "local wall time (PDT)",
       "confidential-pii", "C3"),
    Ev("EV-093", E + "08_intv/chen.txt", "interview", "txt", "Interview transcript: Andrew Chen",
       "SBRPD", "Det. Sam Okoye", "2026-10-20 13:30", "Voluntary interview, recorded", "local wall time (PDT)",
       "confidential-pii", "C3"),
    Ev("EV-094", E + "08_intv/bellini.txt", "interview", "txt", "Interview transcript: Marco Bellini (telephone)",
       "SBRPD", "Det. Sam Okoye", "2026-10-20 10:00", "Voluntary interview, recorded", "local wall time (PDT)",
       "confidential-pii", "C3"),
    Ev("EV-095", E + "08_intv/shen.txt", "interview", "txt", "Interview transcript: Vivian Shen",
       "SBRPD", "Det. Ana Reyes", "2026-10-21 13:00", "Voluntary interview, recorded", "local wall time (PDT)",
       "confidential-pii", "C4"),
    # 09 email
    Ev("EV-100", E + "09_email/ellis_brandt.eml", "email", "eml", "Email: Ellis to Brandt, floor 4 camera maintenance",
       "Aurion Compute IT (mail archive)", "Tom Brandt", "2026-10-20 10:30", "Voluntary export by owner",
       "RFC 5322 Date header with offset", "confidential-corporate", "A2"),
    Ev("EV-101", E + "09_email/brandt_reply.eml", "email", "eml", "Email: Brandt to Ellis, CHG-4471 scheduled",
       "Aurion Compute IT (mail archive)", "Tom Brandt", "2026-10-20 10:30", "Voluntary export by owner",
       "RFC 5322 Date header with offset", "confidential-corporate", "A2"),
    Ev("EV-102", E + "09_email/inv_alert.eml", "email", "eml", "Email: automated cabinet inventory alert",
       "Aurion Compute IT (mail archive)", "Tom Brandt", "2026-10-20 10:30", "Voluntary export by owner",
       "RFC 5322 Date header with offset", "confidential-corporate", "A1"),
    Ev("EV-103", E + "09_email/halvorsen_2255.eml", "email", "eml", "Email: Halvorsen 'Re: Q4 keynote run of show'",
       "Aurion Compute IT (mail archive)", "Tom Brandt", "2026-10-20 10:30", "Voluntary export by owner",
       "RFC 5322 Date header with offset", "confidential-corporate", "A1"),
    Ev("EV-104", E + "09_email/chen_travel.eml", "email", "eml", "Email: travel approval for Andrew Chen, Shenzhen audit",
       "Aurion Compute IT (mail archive)", "Tom Brandt", "2026-10-20 10:30", "Voluntary export by owner",
       "RFC 5322 Date header with offset", "confidential-corporate", "A2"),
]

BY_ID = {e.eid: e for e in CATALOG}
assert len(BY_ID) == len(CATALOG)


def path_of(eid: str) -> str:
    return BY_ID[eid].path
