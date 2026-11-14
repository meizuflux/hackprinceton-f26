"""Intake reports, custody log, extraction notes, and the subscriber return."""
from __future__ import annotations

import hashlib

from ..catalog import path_of
from ..common import Out, Registry
from ..messages import SHEN_THREAD
from .common import BANNER, _doc, header

def reports(out: Out, reg: Registry):
    _doc(out, reg, "EV-001", header("INCIDENT REPORT", [
        "Case number:       SBRPD-26-104417",
        "Offense:           Grand theft / theft of trade secrets (under investigation)",
        "Reported:          2026-10-19 09:10 by Tom Brandt, Director of Global Security, Aurion Compute, Inc.",
        "Location:          Aurion Park, Building E, 3100 Aurion Parkway, Santa Clara, CA 95054",
        "                   Executive Briefing Center (EBC), room 4-12",
        "Occurred between:  2026-10-16 19:12 (last confirmed return) and 2026-10-19 07:40 (discovery)",
        "Reporting officer: Det. Ana Reyes #2217",
        "Assisting:         Det. Sam Okoye #2380; CST Lee Park #3105",
    ]) + """
PROPERTY
  1. AX-9 "Kestrel" GPU engineering sample, asset ES-0007, serial AX9-ES-0007-K. Unreleased product.
     Owner valuation: $380,000 replacement build cost. Owner describes intellectual-property exposure as critical.

NARRATIVE
On 2026-10-19 at about 0945 hours I responded to Building E with Det. Okoye and CST Park.
EBC manager Dana Whitfield reported that at about 0740 hours she saw through the glass door of secure cabinet
SC-EBC-01 that the foam slot for ES-0007 was empty. She did not open the cabinet.
Brandt reported that the cabinet audit log shows an executive-override opening on Saturday 2026-10-17 at
2251 hours using credential BID-100001, which is assigned to the CEO, Richard Halvorsen. {{IR_EXEC_OVERRIDE_REPORTED}}
Brandt also reported that the floor 4 cameras were offline Saturday 2100-2330 under a scheduled maintenance change. {{IR_CAMERA_OUTAGE}}
The building is unstaffed after 1800 on weekends. A contract guard patrols on a four-hour tour.
CST Park photographed the scene and swabbed the cabinet keypad (Q1) and handle (Q2) before the cabinet was opened
at 1041 hours with the EBC manager's credential. Two wine glasses and an empty wine bottle were found in the
wastebasket of office 4-01 (CEO office). The glasses were collected (Q3, Q4). {{IR_GLASSES}}
Per Whitfield, the executive floor is cleaned on weekday evenings only; office 4-01 was last cleaned Friday
2026-10-16 in the evening. {{IR_CLEANING}}
The owner provided exports of badge access, cabinet audit, RFID inventory, camera clips and status, and garage
plate-reader records.
Halvorsen was in meetings and will be interviewed at 1500 today.
Persons of interest named by the owner's staff: Priya Raman (signed the sample out on Friday) and Marco Bellini
(former employee, now with a competitor). {{IR_OWNER_POI}}

DISPOSITION: Open. Assigned to the High-Tech Theft Unit.
""", file_rel="supporting")

    _doc(out, reg, "EV-002", f"""{BANNER}
LATTICE SPECIALTY INSURANCE CO.
FIRST NOTICE OF LOSS AND SPECIAL INVESTIGATIONS UNIT (SIU) REFERRAL

Claim number:      LSI-CC-26-009812
Policy:            Commercial Crime CC-2026-118842, policy period 2026-02-01 to 2027-02-01
Insured:           Aurion Compute, Inc.
Coverage parts:    Employee Theft; Premises Theft (Inside the Premises); Computer Fraud
Date of loss:      2026-10-17 (per insured)
Reported:          2026-10-20 08:40 by Aurion Compute Risk Management
SIU investigator:  Karen Doyle

AMOUNT CLAIMED (PRELIMINARY): $1,150,000
  Replacement engineering sample build and expedite       $380,000
  Incident response and forensic costs                    $270,000
  Launch event rescheduling costs                         $500,000

REASONS FOR SIU REFERRAL
  1. The cabinet was opened with an executive officer's credential and executive PIN. {{{{FNOL_OFFICER_CREDENTIAL}}}}
  2. The camera outage during the loss window was requested by the officer's office. {{{{FNOL_CAMERA}}}}
  3. Single high-value item of unreleased technology; possible trade-secret exposure.

COVERAGE QUESTIONS FOR INVESTIGATION
  a. Was the loss caused by an employee or officer, alone or in collusion (Employee Theft), or by a third party
     (Premises Theft)? {{{{FNOL_COVERAGE_Q}}}}
  b. Exclusions to review: loss caused by an officer of the insured with knowledge; loss of trade secrets or other
     intangible value beyond scheduled amounts. {{{{FNOL_EXCLUSIONS}}}}
  c. Did the insured follow its own security procedures (dual authorization, alert monitoring)? {{{{FNOL_PROCEDURES}}}}

Liaison with SBRPD (Det. Ana Reyes) established 2026-10-20 11:15. Reserve set pending investigation.
""", file_rel="key")

    custody = [
        ["Q1", "Swab, cabinet keypad", "CST Lee Park", "2026-10-19 10:30", "EBC 4-12", "S-77120",
         "SBRPD Property", "2026-10-19 13:10", "Storage"],
        ["Q1", "Swab, cabinet keypad", "SBRPD Property", "2026-10-19 13:10", "Property room", "S-77120",
         "South Bay Regional Forensic Laboratory", "2026-10-20 08:30", "DNA analysis"],
        ["Q2", "Swab, cabinet handle", "CST Lee Park", "2026-10-19 10:33", "EBC 4-12", "S-77121",
         "South Bay Regional Forensic Laboratory", "2026-10-20 08:30", "DNA analysis"],
        ["Q3", "Wine glass A", "CST Lee Park", "2026-10-19 10:50", "Office 4-01", "S-77122",
         "South Bay Regional Forensic Laboratory", "2026-10-20 08:30", "DNA analysis"],
        ["Q4", "Wine glass B (lipstick residue)", "CST Lee Park", "2026-10-19 10:53", "Office 4-01", "S-77123",
         "South Bay Regional Forensic Laboratory", "2026-10-20 08:30", "DNA analysis"],
        ["X1", "Empty wine bottle", "CST Lee Park", "2026-10-19 10:55", "Office 4-01", "S-77124", "SBRPD Property",
         "2026-10-19 13:10", "Latent prints (pending)"],
        ["K3", "Reference buccal swab, Dana Whitfield", "Det. Ana Reyes", "2026-10-20 09:10", "Building E", "S-77130",
         "South Bay Regional Forensic Laboratory", "2026-10-21 08:15", "Reference"],
        ["K2", "Reference buccal swab, Priya Raman", "Det. Sam Okoye", "2026-10-20 12:05", "Building E", "S-77131",
         "South Bay Regional Forensic Laboratory", "2026-10-21 08:15", "Reference"],
        ["K1", "Reference buccal swab, Richard Halvorsen", "Det. Ana Reyes", "2026-10-20 17:40", "SBRPD HQ",
         "S-77132", "South Bay Regional Forensic Laboratory", "2026-10-21 08:15", "Reference"],
        ["D1", "Logical extraction image, Halvorsen iPhone (consent scope)", "Det. Sam Okoye", "2026-10-20 19:40",
         "SBRPD Digital Forensics", "", "Case file", "2026-10-20 20:05", "Analysis; device returned to owner 19:45"],
        ["D2", "Logical extraction image, Raman Android (consent)", "Det. Sam Okoye", "2026-10-21 10:20",
         "SBRPD Digital Forensics", "", "Case file", "2026-10-21 10:40", "Analysis; device returned to owner 10:25"],
        ["E1", "Owner export: badge, cabinet, RFID, LPR, VMS clips and status (USB)", "Det. Ana Reyes",
         "2026-10-19 11:20", "Building E", "S-77125", "Case file", "2026-10-19 13:30", "Analysis"],
        ["E2", "Owner export: workstation events, email archive items", "Det. Ana Reyes", "2026-10-20 10:30",
         "Building E", "", "Case file", "2026-10-20 10:45", "Analysis"],
        ["E3", "Carrier return: subscriber +1-408-555-0147", "Det. Ana Reyes", "2026-10-21 08:45", "Carrier portal",
         "", "Case file", "2026-10-21 08:50", "Analysis"],
        ["E4", "Carrier return: records +1-408-555-0147 (2026-07-01 to 2026-10-21)", "Det. Ana Reyes",
         "2026-10-22 09:30", "Carrier portal", "", "Case file", "2026-10-22 09:40", "Analysis"],
    ]
    rows = []
    for i, c in enumerate(custody, 1):
        h = hashlib.sha256(("custody:" + "|".join(c)).encode()).hexdigest() if c[0][0] in "DE" else ""
        rows.append([f"COC-{i:03d}"] + c + [h])
        reg.rec("EV-003", f"entry_id=COC-{i:03d}", "context")
    reg.key("COC_GLASSES_COLLECTED", "EV-003", "entry_id=COC-004")
    out.csv(path_of("EV-003"), ["entry_id", "item_id", "description", "collected_or_released_by", "at_local",
                                "location", "seal_no", "transferred_to", "transferred_at_local", "purpose",
                                "acquisition_sha256"], rows)

    n_thread = len(SHEN_THREAD)
    _doc(out, reg, "EV-052", f"""{BANNER}
SBRPD DIGITAL FORENSICS - EXTRACTION NOTES
Case: SBRPD-26-104417     Examiner: Det. Sam Okoye

DEVICE D1
  Apple iPhone 16 Pro, owner Richard Halvorsen, number +1-408-555-0110.
  Consent (2026-10-20 17:30, with counsel): messages and attachments 2026-06-01 to 2026-10-20; camera roll
  2026-08-01 to 2026-10-20; location history export. Email, notes and other apps excluded. {{{{EXTRACT_SCOPE_H}}}}
  Method: logical extraction plus database parsing; deleted message records recovered from database free pages.
  Thread T01, contact saved as "Vince (Supply)", number +1-408-555-0147: {n_thread} records, all marked deleted on
  the device on 2026-10-20 at 07:58:20 PDT (morning of the second interview). 3 message bodies unrecoverable. {{{{EXTRACT_DELETION}}}}
  Camera roll: 212 items in scope. Four items exported to the case file after relevance review (IMG_4402,
  IMG_4433, IMG_4458, IMG_4471); the remainder were reviewed and not exported. {{{{EXTRACT_PHOTOS}}}}

DEVICE D2
  Samsung Galaxy, owner Priya Raman, number +1-408-555-0163.
  Consent (2026-10-21 09:20): messages 2026-10-01 to 2026-10-21; carrier location records 2026-10-14 to 2026-10-20.

NOT EXAMINED
  No device associated with +1-408-555-0147 (subscriber Pacific Harbor Advisory LLC) has been examined.
  The user declined consent on 2026-10-21. {{{{EXTRACT_NO_SHEN_DEVICE}}}}
""")

    _doc(out, reg, "EV-061", f"""{BANNER}
SUBSCRIBER INFORMATION RESPONSE (synthetic carrier)
Legal process:     Subpoena SBRPD-SP-26-0870, served 2026-10-20 20:15, response 2026-10-21 08:45
Target number:     +1-408-555-0147
Account type:      Postpaid business line
Subscriber:        Pacific Harbor Advisory LLC {{{{SUB_0147_COMPANY}}}}
Billing address:   1 Market Plaza, Suite 3700, San Francisco, CA 94105 (virtual office)
Authorized user:   V. Shen {{{{SUB_0147_USER}}}}
Account opened:    2026-05-28
Device:            Apple iPhone (IMEI withheld pending separate process)
Plan features:     International calling add-on (Asia-Pacific); international roaming enabled
Payment:           Corporate card ending 2093
""", file_rel="key")
