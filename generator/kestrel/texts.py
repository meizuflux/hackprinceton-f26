"""Narrative documents: incident report, insurer FNOL, custody log, extraction notes, subscriber return,
written statements, interview transcripts, and emails. Lines tagged {{TAG}} become citable key locators."""
from __future__ import annotations

import hashlib

from .catalog import path_of
from .common import Out, Registry, render_marked_text
from .messages import SHEN_THREAD

BANNER = "SYNTHETIC CASE DATA - FICTIONAL - FOR TRAINING AND DEMONSTRATION ONLY"

# Relevance for tagged lines; anything not listed defaults to "supporting".
REL = {
    "IR_OWNER_POI": "red_herring", "STMT_R_DISAPPOINTED": "red_herring", "INT_H1_POINTS_TO_OTHERS": "red_herring",
    "INT_H1_CLONED": "red_herring", "INT_C_TRAVEL": "red_herring", "EMAIL_CHEN_TRAVEL": "red_herring",
    "INT_MB_EXPLAINS": "red_herring", "INT_MB_ALIBI": "red_herring", "INT_C_NO_ACCESS": "red_herring",
    "INT_R_ALIBI": "red_herring",
    "INT_H1_HOME_CLAIM": "key", "INT_H1_NO_OFFICE": "key", "INT_H2_ALONE": "key", "INT_H2_AT_DESK": "key",
    "INT_H2_BADGE_COAT": "key", "INT_S_ALIBI_CLAIM": "key", "INT_S_DENIES_SAT": "key", "INT_S_BUSINESS_ONLY": "key",
    "INT_S_DEPARTURE": "key", "INT_S_DECLINES_DNA": "key", "INT_S_ADDRESS": "key", "INT_S_MESSAGES": "key",
    "STMT_O_SIGHTING": "key", "STMT_O_BAG": "key", "STMT_W_1007_TOUR": "key", "STMT_W_TWO_UNITS": "key",
    "STMT_W_CLEANING": "key", "STMT_W_BADGE_HABIT": "key", "STMT_E_CAMERA": "key", "STMT_E_BRIEFING": "key",
    "STMT_E_DINNERS": "key", "STMT_EH_TIMES": "key", "SUB_0147_COMPANY": "key", "SUB_0147_USER": "key",
    "EXTRACT_DELETION": "key", "EMAIL_ELLIS_REQUEST": "key", "EMAIL_INV_ALERT": "key", "EMAIL_H_2255": "key",
    "STMT_B_PIN_FAIL": "key", "FNOL_COVERAGE_Q": "key", "EXTRACT_NO_SHEN_DEVICE": "key",
}


def _doc(out: Out, reg: Registry, eid: str, text: str, numbered: bool = False, file_rel: str = "supporting"):
    before = set(reg.keys)
    out.text(path_of(eid), render_marked_text(text, eid, reg, numbered=numbered))
    for tag in sorted(set(reg.keys) - before, key=lambda t: int(reg.keys[t]["locator"].split("=")[1])):
        reg.rec(eid, reg.keys[tag]["locator"], REL.get(tag, "supporting"), "", [tag])
    reg.rec(eid, "file", file_rel)


def header(kind: str, lines: list[str]) -> str:
    return "\n".join([BANNER, "SOUTH BAY REGIONAL POLICE DEPARTMENT", kind, ""] + lines + [""])


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


def statements(out: Out, reg: Registry):
    def st(name, role, by, when):
        return [BANNER, "SOUTH BAY REGIONAL POLICE DEPARTMENT - WRITTEN STATEMENT",
                f"Case: SBRPD-26-104417", f"Statement of: {name}, {role}", f"Taken by: {by}",
                f"Date and time: {when}", ""]

    _doc(out, reg, "EV-080", "\n".join(st("Dana Whitfield", "EBC Manager, Aurion Compute", "Det. Ana Reyes",
                                          "2026-10-19 11:30")) + """
1. I manage the Executive Briefing Center (EBC), room 4-12 in Building E. Secure cabinet SC-EBC-01 holds demo hardware, including the AX-9 "Kestrel" engineering samples.
2. There are two Kestrel units in the cabinet. ES-0007 is the only functional unit and the one we demo. ES-0003 is a thermal-mechanical sample that does not power on. From the outside they look almost the same. {{STMT_W_TWO_UNITS}}
3. Removing hardware takes two people: me plus an approved engineer. Mr. Halvorsen and I also have an executive PIN that lets either of us open the cabinet alone with our badge. The PIN is changed every quarter. {{STMT_W_EXEC_PIN}}
4. On Friday 10/16 at about 1:05 pm Priya Raman and I signed ES-0007 out for thermal runs. Returns only need one person. I left at about 6 pm. The system shows Priya returned it at 7:12 pm.
5. The executive-floor crew wipes the EBC glass and the cabinet handle on Friday evenings. They do not clean keypads. Floor 4 is not cleaned on weekends. {{STMT_W_CLEANING}}
6. On Monday 10/19 I arrived at about 7:30 and went to the EBC to prepare for keynote rehearsal. At about 7:40 I saw through the glass door that the ES-0007 slot was empty. I did not open the cabinet. I texted Mr. Halvorsen and called Tom Brandt. {{STMT_W_DISCOVERY}}
7. I then checked the security alerts mailbox and saw an automatic inventory alert from midnight Sunday saying ES-0007 was missing. Nobody watches that mailbox on weekends. {{STMT_W_ALERT_UNREAD}}
8. On Wednesday 10/7 Jordan asked me to prepare the EBC for a partner briefing at 2:30. Mr. Halvorsen told me I was not needed and that he would do the walkthrough himself. As I was leaving the floor at about 2:35 I saw him walking toward the EBC with a woman in a cream-colored jacket. I did not see what they did inside. {{STMT_W_1007_TOUR}}
9. Mr. Halvorsen often leaves his badge on its lanyard on the coat stand in his office. I have mentioned it to him before. {{STMT_W_BADGE_HABIT}}
10. I do not know who took the sample.

I have read this statement and it is true to the best of my knowledge. Signed: D. Whitfield
""")

    _doc(out, reg, "EV-081", "\n".join(st("Tom Brandt", "Director of Global Security, Aurion Compute",
                                          "Det. Ana Reyes", "2026-10-19 12:15")) + """
1. I am responsible for physical security at Aurion Park.
2. On Thursday 10/15 at about 3:48 pm Jordan Ellis emailed me asking that the floor 4 cameras not record on Saturday from 9:00 to 11:30 pm for a confidential board-prep session, and suggested I schedule the camera recorder firmware update in that window. I scheduled change CHG-4471 for CAM-E-F4-01 and CAM-E-F4-02, 21:00 to 23:30. Badge readers and the cabinet keep logging during camera maintenance. {{STMT_B_CHG}}
3. It is unusual for the CEO's office to ask for cameras to be off, but board material has been sensitive before. I did not question it. {{STMT_B_UNUSUAL}}
4. On Monday 10/19 at about 7:58 Dana called me. I arrived at 8:41 and went to the EBC at about 8:52. I did not open the cabinet and I asked that nobody touch it.
5. I pulled the cabinet audit trail. It shows an executive-override opening at 22:51:14 on Saturday using badge BID-100001 (Mr. Halvorsen's) with the executive PIN. It also shows one failed PIN attempt about twelve seconds before that. {{STMT_B_PIN_FAIL}}
6. RFID inventory shows ES-0007 present at the 22:00 scan and absent at 23:00. The automatic alert at midnight went to the secops-alerts mailbox, which we only monitor on weekdays. That is a process gap and it is mine. {{STMT_B_RFID}}
7. I exported badge, cabinet, RFID, garage plate-reader and camera records and clips for 10/16 to 10/19 and gave them to Det. Reyes at 11:20. I have not yet reviewed the garage video in detail. {{STMT_B_EXPORTS}}
8. Elevator controller logs (LiftCore) and Wi-Fi association logs are kept by those systems and were not part of my export. The Wi-Fi controller keeps 14 days of logs. The camera system keeps 30 days. {{STMT_B_RETENTION}}
9. Marco Bellini resigned on 10/2 and his badge was deactivated that day.

I have read this statement and it is true to the best of my knowledge. Signed: T. Brandt
""")

    _doc(out, reg, "EV-082", "\n".join(st("Luis Ortega", "Night Custodian, BrightPath Facility Services",
                                          "Det. Sam Okoye", "2026-10-20 22:15")) + """
1. I work nights for BrightPath at Aurion Building E, Thursday to Monday, about 6 pm to 2:30 am. I clean floors 1, 2 and 3 and take the trash down to the dumpster on P2. I do not clean floor 4. A different crew does floor 4 on weekdays. {{STMT_O_NO_F4}}
2. On Saturday 10/17 I started at about 6 pm.
3. Around 11:30 at night, maybe a little earlier, I took the trash cart down to P2. {{STMT_O_TIME_ESTIMATE}}
4. While I was at the dumpster I saw a man and a woman come out of the elevator lobby door and walk to a dark gray car in row C. They stood by the car talking for a few minutes and then drove away. {{STMT_O_SIGHTING}}
5. The woman had dark hair, a long dark coat and heels. She carried a big light-brown bag, like a shopping tote, in front of her with both arms, like it was heavy or she did not want it to bump. {{STMT_O_BAG}}
6. The man wore a dark jacket. He looked like an executive. I did not see either face well. It is dark in that part of the garage. {{STMT_O_NO_FACES}}
7. I did not see anyone else in the building that night except the guard on his rounds.
8. I did not tell anyone because people use the garage at night sometimes.

I have read this statement and it is true to the best of my knowledge. Signed: L. Ortega
""")

    _doc(out, reg, "EV-083", "\n".join(st("Jordan Ellis", "Executive Assistant to the CEO, Aurion Compute",
                                          "Det. Ana Reyes", "2026-10-20 09:30")) + """
1. I have been executive assistant to Richard Halvorsen since 2024. I manage his calendar, travel and meetings.
2. On 10/5 Richard asked me to set up a partner briefing on Wednesday 10/7 at 2:30 for "V. Shen" of Pacific Harbor Advisory, with an EBC walkthrough. He said Dana did not need to join. I registered the visitor under his name. {{STMT_E_BRIEFING}}
3. On 10/15 Richard asked me to block Saturday 9:00 to 11:30 pm as "Board prep (private)" and to ask Tom whether the camera firmware work on floor 4 could happen in that window. I emailed Tom at 3:48 pm and Tom confirmed change CHG-4471. {{STMT_E_CAMERA}}
4. I was not aware of any board meeting that weekend. The next board meeting is on 10/28. I did not ask about it. {{STMT_E_NO_BOARD}}
5. Since July there have been several "Supply chain dinner (private)" entries on Richard's calendar. He adds those himself. I do not create them and I do not know who attends. {{STMT_E_DINNERS}}
6. I do not know Ms. Shen apart from arranging the 10/7 visit.

I have read this statement and it is true to the best of my knowledge. Signed: J. Ellis
""")

    _doc(out, reg, "EV-084", "\n".join(st("Priya Raman", "Senior Staff Hardware Engineer, Aurion Compute",
                                          "Det. Ana Reyes", "2026-10-19 16:00")) + """
1. I lead thermal validation for AX-9 and I am on the cabinet access list for sign-out with a second authorizer.
2. On Friday 10/16 at about 1:05 pm I signed out ES-0007 with Dana Whitfield and ran thermal validation in Lab 2A. I returned it at 7:12 pm. It was in its slot when I closed the cabinet door. {{STMT_R_DEPOSIT}}
3. On Saturday 10/17 I left home at about 6:40 am for South Lake Tahoe with three friends. I came back on Sunday evening at about 7. {{STMT_R_TAHOE}}
4. I was disappointed about a promotion decision last week and I said some things to a friend in text messages. I would never take the sample. {{STMT_R_DISAPPOINTED}}
5. I consent to my phone being examined and to giving a DNA sample.

I have read this statement and it is true to the best of my knowledge. Signed: P. Raman
""", file_rel="red_herring")

    _doc(out, reg, "EV-085", "\n".join(st("Elaine Halvorsen", "spouse of Richard Halvorsen", "Det. Sam Okoye",
                                          "2026-10-21 10:00")) + """
1. Richard and I have been married for 19 years.
2. On Saturday 10/17 Richard told me in the afternoon that he had board prep in the evening. He left the house at about 7:40 pm. Later he texted that it was running long. He came home at about 11:45 pm. {{STMT_EH_TIMES}}
3. Since the summer he has had a number of late "supply chain dinners". {{STMT_EH_DINNERS}}
4. He did not mention anyone else being at the office. On Sunday we had brunch with my parents in Saratoga.
5. I do not know anything about the missing hardware.

I have read this statement and it is true to the best of my knowledge. Signed: E. Halvorsen
""")


def interviews(out: Out, reg: Registry):
    def head(subject, when, where, present):
        return "\n".join([BANNER, "SOUTH BAY REGIONAL POLICE DEPARTMENT - INTERVIEW TRANSCRIPT",
                          "Case: SBRPD-26-104417", f"Subject: {subject}", f"Date and time: {when}",
                          f"Location: {where}", f"Present: {present}", "Recorded: audio and video", ""])

    _doc(out, reg, "EV-090", head("Richard Halvorsen (interview 1)", "2026-10-19 15:00",
                                  "Aurion Building E, conference room 4-05",
                                  "Det. Ana Reyes, Det. Sam Okoye, Richard Halvorsen") + """
REYES: This is a voluntary interview. You're free to leave at any time. Do you understand?
HALVORSEN: Yes. Whatever you need.
REYES: When did you last see the Kestrel sample ES-0007?
HALVORSEN: Friday morning, at the keynote rehearsal in the EBC.
REYES: Where were you on Saturday evening, October 17?
HALVORSEN: At home. A quiet night. My wife and I watched something and I went to bed early. {{INT_H1_HOME_CLAIM}}
REYES: You didn't come to the office at any point on Saturday?
HALVORSEN: No. {{INT_H1_NO_OFFICE}}
REYES: Who knows the executive PIN for the cabinet?
HALVORSEN: Me and Dana. It's changed every quarter.
REYES: Has anyone else ever seen you enter it?
HALVORSEN: I wouldn't think so. I'm careful. {{INT_H1_PIN_CAREFUL}}
REYES: Where is your badge right now?
HALVORSEN: On me. Always. {{INT_H1_BADGE_ALWAYS}}
OKOYE: The cabinet log shows your badge and the executive PIN opened the cabinet at 10:51 on Saturday night.
HALVORSEN: That's not possible. Someone must have cloned my badge. Ask Tom about that. {{INT_H1_CLONED}}
OKOYE: Who would want the sample?
HALVORSEN: Half the industry. Internally, Priya Raman has been unhappy since the promotion round, and Marco Bellini just left for Corvid Systems. I'm not accusing anyone. {{INT_H1_POINTS_TO_OTHERS}}
REYES: Why were the floor 4 cameras offline on Saturday night?
HALVORSEN: Security does maintenance. I don't schedule it. {{INT_H1_CAMERA_DEFLECT}}
REYES: Has anyone outside the company been in the EBC recently?
HALVORSEN: Customers, board members, partners. It's a briefing center.
REYES: We'll want to talk again. Thank you.
[Interview ended 15:32]
""", numbered=True, file_rel="key")

    _doc(out, reg, "EV-091", head("Richard Halvorsen (interview 2)", "2026-10-20 16:30", "SBRPD Headquarters",
                                  "Det. Ana Reyes, Det. Sam Okoye, Richard Halvorsen, Amanda Pierce (counsel)") + """
REYES: Yesterday you told us you were home all Saturday evening. The garage plate reader shows your car entering P2 at 9:35 pm and leaving at 11:07 pm, and your badge opened the P2 elevator lobby door at 9:36.
PIERCE: My client would like to correct his statement.
HALVORSEN: I went to the office. I didn't want my wife to know I was working on a Saturday night again. I'm sorry. {{INT_H2_ADMITS_OFFICE}}
REYES: What did you do there?
HALVORSEN: Worked on the keynote. Email. {{INT_H2_WORKED}}
REYES: Was anyone with you?
HALVORSEN: No. {{INT_H2_ALONE}}
REYES: The garage door was held open for sixteen seconds after you badged in.
HALVORSEN: I was carrying things. My bag, my coat. {{INT_H2_DOOR_EXPLAIN}}
REYES: There were two wine glasses in your office wastebasket.
HALVORSEN: I had a glass while I worked. I don't know about the second one. Maybe it was from earlier in the week. {{INT_H2_GLASSES}}
OKOYE: The executive floor is cleaned every weekday evening, including Friday.
HALVORSEN: Then I don't know.
REYES: Your badge opened the EBC door at 10:50 pm and the cabinet at 10:51.
HALVORSEN: I did not open the cabinet on Saturday. I was at my desk. Check my computer. {{INT_H2_AT_DESK}}
REYES: Where was your badge while you were at your desk?
HALVORSEN: On my jacket, probably. On the coat stand. {{INT_H2_BADGE_COAT}}
REYES: Who asked for the floor 4 cameras to be turned off?
PIERCE: You don't have to answer that.
HALVORSEN: I asked Jordan to have them off for privacy. The keynote material is sensitive. {{INT_H2_CAMERAS_PRIVACY}}
REYES: Is there anyone who can confirm what you were doing on Saturday night?
HALVORSEN: No. {{INT_H2_NO_CONFIRM}}
REYES: Will you consent to an examination of your messages and location history?
PIERCE: After conferring, my client consents to messages and location history, limited in scope. There are personal matters on that phone and we ask for discretion. {{INT_H2_CONSENT}}
HALVORSEN: I want the sample found. I had nothing to do with it.
REYES: Will you provide a DNA reference sample?
HALVORSEN: Yes.
[Interview ended 17:28]
""", numbered=True, file_rel="key")

    _doc(out, reg, "EV-092", head("Priya Raman", "2026-10-20 11:00", "Aurion Building E, conference room 2-07",
                                  "Det. Sam Okoye, Priya Raman") + """
OKOYE: Walk me through Friday.
RAMAN: Dana and I signed out ES-0007 at 1:05 for thermal runs in Lab 2A. I deposited it at 7:12.
OKOYE: Was anyone with you when you returned it?
RAMAN: No. Returns only need one person.
OKOYE: We have texts where you wrote that they would regret it.
RAMAN: I was angry about the promotion. I meant they'd regret not crediting my thermal work. I was in Tahoe all weekend. My friends and my phone will tell you that. {{INT_R_ALIBI}}
OKOYE: Did you tell anyone outside work about the Kestrel samples?
RAMAN: My friend knows I call it "the bird". Everyone on the team calls it that. {{INT_R_BIRD_COMMON}}
OKOYE: Who knows the executive PIN?
RAMAN: Not me. Dana and Richard.
OKOYE: Will you give a DNA reference sample?
RAMAN: Yes.
[Interview ended 11:24]
""", numbered=True, file_rel="red_herring")

    _doc(out, reg, "EV-093", head("Andrew Chen", "2026-10-20 13:30", "Aurion Building E, conference room 2-07",
                                  "Det. Sam Okoye, Andrew Chen") + """
OKOYE: You were in the building on Saturday afternoon.
CHEN: From about 2 to 4:30, in Lab 2A. A firmware build for the keynote demo rig had to run on the bench.
OKOYE: Did you go to floor 4?
CHEN: No. I don't have access to the executive suite or the EBC, and I'm not on the cabinet list. {{INT_C_NO_ACCESS}}
OKOYE: You traveled to Shenzhen in September.
CHEN: For a supplier quality audit at Pearl River Substrate. My VP approved it. The approval is in my email. {{INT_C_TRAVEL}}
OKOYE: Did you see anyone else in the building?
CHEN: No. I left through P2 at about 4:30.
[Interview ended 13:46]
""", numbered=True, file_rel="red_herring")

    _doc(out, reg, "EV-094", head("Marco Bellini (telephone)", "2026-10-20 10:00", "Telephone",
                                  "Det. Sam Okoye, Marco Bellini") + """
OKOYE: Your old badge was used at the Building E lobby at 7:02 pm on Saturday.
BELLINI: That was me. I forgot it had been deactivated. I left a monitor arm and a plant in my old cube. I tried the door twice, then texted a friend on the team who told me to email facilities. I went home. {{INT_MB_EXPLAINS}}
OKOYE: Where did you go after that?
BELLINI: Dinner with my family in Fremont, around 8. {{INT_MB_ALIBI}}
OKOYE: You work for Corvid Systems now.
BELLINI: Yes, on networking products. I never worked on Kestrel hardware and I would never risk that.
[Interview ended 10:12]
""", numbered=True, file_rel="red_herring")

    _doc(out, reg, "EV-095", head("Vivian Shen", "2026-10-21 13:00", "SBRPD Headquarters",
                                  "Det. Ana Reyes, Det. Sam Okoye, Vivian Shen (declined counsel)") + """
REYES: Thank you for coming in. This interview is voluntary.
SHEN: Of course. I'm happy to help Richard's company.
REYES: What is your work?
SHEN: I'm a principal at Pacific Harbor Advisory. We advise Asian packaging and substrate suppliers entering the U.S. market. {{INT_S_COVER}}
REYES: Where are you living while you're here?
SHEN: A corporate apartment at Arbor Row, in Sunnyvale. {{INT_S_ADDRESS}}
REYES: How do you know Richard Halvorsen?
SHEN: We met at the Silicon Futures Summit in June. We've had a few business dinners. He is generous with his time. {{INT_S_BUSINESS_ONLY}}
REYES: Mr. Halvorsen's phone has messages with your number saved under a different name.
SHEN: Richard is a private man. Our messages are about the industry. {{INT_S_MESSAGES}}
REYES: Have you been to Aurion?
SHEN: Once, on October 7, for a partner briefing. He showed me the briefing center. {{INT_S_VISIT_ONCE}}
REYES: Did he open the cabinet to show you anything?
SHEN: He showed me several things. I don't remember a cabinet in particular. {{INT_S_NO_CABINET_MEMORY}}
REYES: Where were you on Saturday evening, October 17?
SHEN: I had dinner alone near my apartment and was home before nine. I watched a film and went to sleep. {{INT_S_ALIBI_CLAIM}}
REYES: Did you see Mr. Halvorsen that evening?
SHEN: No. {{INT_S_DENIES_SAT}}
REYES: And on Sunday morning?
SHEN: Errands. Coffee, the pharmacy. {{INT_S_SUNDAY_ERRANDS}}
OKOYE: Did you mail or ship anything over the weekend?
SHEN: I don't think so. {{INT_S_NO_SHIPPING}}
OKOYE: Would you give a DNA sample so we can eliminate visitors to the briefing center?
SHEN: I would want to speak with a lawyer first. {{INT_S_DECLINES_DNA}}
REYES: Would you allow us to look at your phone?
SHEN: Not without counsel. It has client information on it. {{INT_S_DECLINES_PHONE}}
REYES: How long are you staying in the area?
SHEN: My engagement ends this week. I fly home on Friday. {{INT_S_DEPARTURE}}
REYES: Home is where?
SHEN: Hong Kong.
REYES: Thank you. We may contact you again.
SHEN: Of course.
[Interview ended 13:34]
""", numbered=True, file_rel="key")


def emails(out: Out, reg: Registry):
    def eml(frm, to, date, subj, mid, body, extra=()):
        h = [f"From: {frm}", f"To: {to}", f"Date: {date}", f"Subject: {subj}", f"Message-ID: <{mid}>",
             "MIME-Version: 1.0", 'Content-Type: text/plain; charset="utf-8"', "X-Synthetic: fictional training data"]
        h += list(extra)
        return "\n".join(h) + "\n\n" + body

    _doc(out, reg, "EV-100", eml("Jordan Ellis <jellis@aurion-compute.example>",
                                 "Tom Brandt <tbrandt@aurion-compute.example>", "Thu, 15 Oct 2026 15:48:12 -0700",
                                 "Floor 4 cameras - Saturday evening", "20261015154812.jellis@aurion-compute.example", """Hi Tom,

Richard has a confidential board-prep session on 4 this Saturday evening (9:00-11:30pm) and asked that the floor 4 cameras not record during it. {{EMAIL_ELLIS_REQUEST}}
You mentioned the NVR firmware update needs a two-hour window. Could we schedule it then?

Thanks,
Jordan
"""), file_rel="key")
    _doc(out, reg, "EV-101", eml("Tom Brandt <tbrandt@aurion-compute.example>",
                                 "Jordan Ellis <jellis@aurion-compute.example>", "Thu, 15 Oct 2026 16:21:40 -0700",
                                 "Re: Floor 4 cameras - Saturday evening", "20261015162140.tbrandt@aurion-compute.example", """Sure. Scheduled as CHG-4471, Sat 10/17 21:00-23:30, CAM-E-F4-01 and CAM-E-F4-02. {{EMAIL_BRANDT_CHG}}
Heads up that the EBC cabinet and the badge readers are unaffected. Those keep logging normally. {{EMAIL_BRANDT_LOGGING}}

Tom
""", ["In-Reply-To: <20261015154812.jellis@aurion-compute.example>"]))
    _doc(out, reg, "EV-102", eml("Cabinet Inventory <inventory-noreply@aurion-compute.example>",
                                 "secops-alerts@aurion-compute.example", "Sun, 18 Oct 2026 00:00:09 -0700",
                                 "INV-ALERT-2210 SC-EBC-01: ES-0007 not detected",
                                 "20261018000009.inv2210@aurion-compute.example", """INV-ALERT-2210
Cabinet: SC-EBC-01 (EBC 4-12)
Item: ES-0007 (AX-9 'Kestrel' engineering sample, functional)
Condition: not detected in 2 consecutive scans (2026-10-17 23:00, 2026-10-18 00:00). Last detected 2026-10-17 22:00. {{EMAIL_INV_ALERT}}
Custody state: IN_CABINET (not checked out)
""", ["X-Mailbox-First-Read: 2026-10-19T07:52:31-07:00 by dwhitfield"]), file_rel="key")
    _doc(out, reg, "EV-103", eml("Richard Halvorsen <rhalvorsen@aurion-compute.example>",
                                 "keynote-core@aurion-compute.example", "Sat, 17 Oct 2026 22:55:13 -0700",
                                 "Re: Q4 keynote run of show", "20261017225513.rhalvorsen@aurion-compute.example", """Swap 14 and 15. Lead with perf/W, then the bird. Cut the roadmap slide. {{EMAIL_H_2255}}
- R
""", ["X-Originating-Client: Outlook Desktop 16.0", "X-Originating-Host: AUR-EXEC-0001 (10.40.4.21, wired, Building E floor 4)"]),
         file_rel="key")
    _doc(out, reg, "EV-104", eml("Lena Vogel <lvogel@aurion-compute.example>",
                                 "Andrew Chen <achen@aurion-compute.example>", "Fri, 28 Aug 2026 10:14:55 -0700",
                                 "Approved: supplier quality audit travel", "20260828101455.lvogel@aurion-compute.example", """Andrew,

Approved: supplier quality audit at Pearl River Substrate Co., Shenzhen, September 8-15. {{EMAIL_CHEN_TRAVEL}}
Please file the trip report in QMS when you are back.

Lena
"""), file_rel="red_herring")


def write_all(out: Out, reg: Registry):
    reports(out, reg)
    statements(out, reg)
    interviews(out, reg)
    emails(out, reg)
