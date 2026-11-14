"""Ground truth (answer key) for evaluation and training. Never ship these files in the upload ZIP.

Facts are observations tied to exact source locators. Insights are inferences built from facts.
Gaps are directed questions the evidence cannot yet answer, with the artifacts that would close them."""
from __future__ import annotations

from collections import Counter

from .cast import CASE_ID, CASE_TITLE, ITEMS, MEETINGS, PEOPLE, PLACES
from .catalog import CATALOG
from .common import Out, Registry

MD = [f"{d[5:7]}{d[8:10]}" for d, _ in MEETINGS]

FACTS = [
    ("F-01", "ES-0007 was returned to cabinet SC-EBC-01 on Fri 2026-10-16 at 19:12:40 by Priya Raman and was detected present at the 20:00 RFID scan.",
     ["CAB_1016_DEPOSIT", "BADGE_1016_RAMAN_EBC_DEPOSIT", "RFID_1016_2000_PRESENT", "MSG_R_DEPOSIT"]),
    ("F-02", "RFID inventory detected ES-0007 present at 22:00 and absent from 23:00 on Sat 2026-10-17.",
     ["RFID_1017_2200_PRESENT", "RFID_1017_2300_ABSENT"]),
    ("F-03", "The only cabinet opening between the Friday return and the Monday CSU opening was an executive-override opening with badge BID-100001 at 22:51:14 Sat, preceded by a failed PIN attempt at 22:51:02; the door was open 22:51:16-22:52:03.",
     ["CAB_1017_PIN_FAIL", "CAB_1017_EXEC_OPEN", "CAB_1017_DOOR_OPEN", "CAB_1017_DOOR_CLOSE", "STMT_B_PIN_FAIL"]),
    ("F-04", "Only Richard Halvorsen (BID-100001) and Dana Whitfield (BID-200118) hold the executive-override PIN.",
     ["ACL_EXEC_OVERRIDE_HOLDERS", "STMT_W_EXEC_PIN", "REF_CABINET_RULES"]),
    ("F-05", "Halvorsen's car (8RHV521) entered garage P2 at 21:35:48 and left at 23:07:31 on Sat 2026-10-17.",
     ["LPR_H_IN_2135", "LPR_H_OUT_2307"]),
    ("F-06", "BID-100001 opened the P2 elevator lobby door at 21:36:31; the door-held alarm fired at 21:36:49 (open 16 s past threshold) and the door closed at 21:36:52.",
     ["BADGE_H_P2_ENTRY", "BADGE_P2_HELD_OPEN", "BADGE_P2_CLOSED"]),
    ("F-07", "Camera analytics counted two people at the P2 elevator door at 21:36 and two people leaving it at 23:03; the P2 clips show two occupants of the gray sedan arriving and leaving.",
     ["VA_P2_2136_TWO_PERSONS", "VA_P2_2136_DOOR_TWO", "VA_P2_2303_TWO_PERSONS", "VIDEO_P2_ARRIVAL_TWO", "VIDEO_P2_DEPART_TWO"]),
    ("F-08", "Workstation AUR-EXEC-0001 in office 4-01 was unlocked by Windows Hello face at 22:49:02, showed continuous input 22:49-22:57, sent an email at 22:55:13 and locked at 22:58:30.",
     ["WS_UNLOCK_2249", "WS_ACTIVE_2249", "WS_MAIL_2255", "EMAIL_H_2255", "WS_LOCK_2258", "REF_WORKSTATION"]),
    ("F-09", "The executive suite door released for egress at 22:50:31; BID-100001 opened the EBC door at 22:50:47; the EBC door released for egress at 22:52:40; BID-100001 re-entered the suite at 22:53:09.",
     ["BADGE_SUITE_REX_2250", "BADGE_EBC_H_BADGE_2250", "BADGE_EBC_REX_2252", "BADGE_SUITE_H_BADGE_2253"]),
    ("F-10", "Floor 4 cameras CAM-E-F4-01 and CAM-E-F4-02 were offline 21:00-23:30 Sat under change CHG-4471, which Jordan Ellis requested on Halvorsen's instruction.",
     ["VMS_F4_01_OUTAGE", "VMS_F4_02_OUTAGE", "VIDEO_F4_OUTAGE", "EMAIL_ELLIS_REQUEST", "EMAIL_BRANDT_CHG", "MSG_J_CAMERA_REQ", "STMT_E_CAMERA", "STMT_B_CHG"]),
    ("F-11", "Halvorsen's calendar was blocked 'Board prep (private)' 21:00-23:30 Sat; no board meeting was scheduled that weekend.",
     ["CAL_1017_BOARDPREP", "STMT_E_NO_BOARD"]),
    ("F-12", "Two wine glasses and a wine bottle were in the office 4-01 wastebasket on Monday; the floor is cleaned weekday evenings only and was cleaned Friday evening.",
     ["PHOTO_WASTEBASKET", "PHOTO_GLASSES", "IR_GLASSES", "IR_CLEANING", "STMT_W_CLEANING", "STMT_O_NO_F4"]),
    ("F-13", "Wine glass B (Q4) carries a single-source female profile UF-1 with no database match; Halvorsen, Raman and Whitfield are excluded as UF-1.",
     ["DNA_Q4_UF1", "DNA_UF1_EXCLUSIONS", "DNA_CODIS_NOHIT", "DNA_PROFILE_Q4"]),
    ("F-14", "The cabinet handle (Q2, wiped Friday evening) has UF-1 as major contributor; Raman cannot be excluded as a low-level minor contributor; Halvorsen and Whitfield are excluded.",
     ["DNA_Q2_UF1_MAJOR", "DNA_Q2_K2_MINOR", "DNA_Q2_K1_EXCLUDED", "DNA_CLEANING_NOTE", "DNA_PROFILE_Q2"]),
    ("F-15", "The keypad (Q1, not cleaned) is a mixture consistent with Halvorsen, Whitfield and UF-1.",
     ["DNA_Q1_MIXTURE", "DNA_PROFILE_Q1"]),
    ("F-16", "Wine glass A (Q3) matches Halvorsen.", ["DNA_Q3_K1", "DNA_PROFILE_Q3"]),
    ("F-17", "In interview 1 Halvorsen said he was home all Saturday evening and did not go to the office.",
     ["INT_H1_HOME_CLAIM", "INT_H1_NO_OFFICE"]),
    ("F-18", "In interview 2 Halvorsen admitted being at the office, said he was alone at his desk, and said his badge was probably on his jacket on the coat stand.",
     ["INT_H2_ADMITS_OFFICE", "INT_H2_ALONE", "INT_H2_AT_DESK", "INT_H2_BADGE_COAT", "INT_H2_NO_CONFIRM"]),
    ("F-19", "Elaine Halvorsen was told it was board prep; he left home about 19:40, texted that it was running long, and came home about 23:45.",
     ["STMT_EH_TIMES", "MSG_E_BOARDPREP", "MSG_E_RUNNING_LONG", "MSG_E_HOME_IN_5"]),
    ("F-20", "Halvorsen's location history shows Osteria Lumen 20:12-21:21, Building E 21:35-23:07, a 4-minute stop at Arbor Row Apartments 23:20-23:24, then home.",
     ["TL_H_OSTERIA_1017", "TL_H_HQ_1017", "TL_H_VAPT_1017", "TL_H_HOME_1017"]),
    ("F-21", "Halvorsen's photo IMG_4471 (20:58:12, GPS Osteria Lumen) shows two place settings, two wine glasses (one with lipstick), a large tan tote and a dark coat sleeve.",
     ["PHOTO_RESTAURANT_1017"]),
    ("F-22", "Halvorsen's phone holds a thread with contact 'Vince (Supply)' (+1-408-555-0147) from June to October, deleted on the device at 07:58 on 2026-10-20 and recovered.",
     ["MSG_V_FIRST", "MSG_V_AFTER_1017", "EXTRACT_DELETION"]),
    ("F-23", "+1-408-555-0147 is subscribed to Pacific Harbor Advisory LLC with authorized user 'V. Shen'.",
     ["SUB_0147_COMPANY", "SUB_0147_USER"]),
    ("F-24", "Vivian Shen of Pacific Harbor Advisory visited Building E 14:21-16:05 on 2026-10-07 for a 'partner briefing + EBC walkthrough' arranged by Halvorsen, who told Ellis that Whitfield need not attend.",
     ["VISITOR_SHEN_1007", "CAL_1007_BRIEFING", "MSG_J_BRIEFING_REQ", "MSG_J_NO_DANA", "STMT_E_BRIEFING", "STMT_W_1007_TOUR", "PHOTO_VISITOR_1007", "MSG_V_TOUR_INVITE"]),
    ("F-25", "Halvorsen opened the cabinet with the executive override at 15:08 on 2026-10-07, during Shen's visit.",
     ["CAB_1007_EXEC_OPEN"]),
    ("F-26", "+1-408-555-0147 used the cell sector serving Building E at 21:37, 22:21, 22:52 and 23:04 Sat, the Osteria-area sector at 20:15, and the Building E sector during the 2026-10-07 visit.",
     ["CDR_0147_HQ_1017_FIRST", "CDR_0147_HQ_1017_2221", "CDR_0147_HQ_1017_2252", "CDR_0147_HQ_1017_LAST", "CDR_0147_OSTERIA_1017", "CDR_0147_HQ_1007_A", "CDR_0147_HQ_1007_B"]),
    ("F-27", "In interview Shen said the relationship was business only, she was home before 9 pm Saturday, did not see Halvorsen, ran errands Sunday, shipped nothing, declined DNA and phone access, and flies to Hong Kong on Friday.",
     ["INT_S_BUSINESS_ONLY", "INT_S_MESSAGES", "INT_S_ALIBI_CLAIM", "INT_S_DENIES_SAT", "INT_S_SUNDAY_ERRANDS", "INT_S_NO_SHIPPING", "INT_S_DECLINES_DNA", "INT_S_DECLINES_PHONE", "INT_S_DEPARTURE"]),
    ("F-28", "On Sun 2026-10-18 +1-408-555-0147 used the sector covering El Camino Plaza (which includes a pack-and-ship store) 09:28-09:57, then placed a 134 s call to a masked Hong Kong number at 10:05.",
     ["CDR_0147_PLAZA_1", "CDR_0147_PLAZA_2", "CDR_0147_PLAZA_3", "CDR_0147_HK_CALL"]),
    ("F-29", "After the theft: 'Thank you for everything. Truly.' (Sun 10:12); Halvorsen asked 'Saturday, when I was on my laptop. Did you see anyone else on the floor?' and got 'No one. Just us.'",
     ["MSG_V_THANK_EVERYTHING", "MSG_V_SAW_ANYONE", "MSG_V_JUST_US"]),
    ("F-30", "Custodian Luis Ortega saw a man and a woman leave the P2 elevator lobby for a dark gray car 'around 11:30'; the woman carried a large light-brown tote with both arms. Video and his badge place him on P2 23:02-23:06.",
     ["STMT_O_SIGHTING", "STMT_O_BAG", "STMT_O_TIME_ESTIMATE", "BADGE_ORTEGA_P2_REENTRY", "VIDEO_P2_CUSTODIAN", "VA_P2_2302_CUSTODIAN"]),
    ("F-31", "Guard tours checked floor 4 at about 20:24 and 00:28; at 00:14 P2 held only the contractor van.",
     ["GUARD_2005_EBC", "GUARD_0010_EBC", "GUARD_0010_P2"]),
    ("F-32", "The inventory alert fired at 00:00:09 Sunday to a mailbox monitored only on weekdays and was first read Monday 07:52.",
     ["RFID_1018_0000_ALERT", "EMAIL_INV_ALERT", "STMT_W_ALERT_UNREAD", "STMT_B_RFID", "REF_RFID_ALERTING"]),
    ("F-33", "Priya Raman signed ES-0007 out at 13:05 Friday with Whitfield, texted resentment about a promotion, and her phone was at South Lake Tahoe from 10:41 Saturday through the theft window.",
     ["CAB_1016_SIGNOUT", "MSG_R_REGRET", "MSG_R_PASSED_OVER", "CDR_0163_TAHOE_ARRIVE", "CDR_0163_TAHOE_2247", "CDR_0163_TAHOE_2312", "MSG_R_TAHOE_2248", "STMT_R_TAHOE", "INT_R_ALIBI"]),
    ("F-34", "Marco Bellini's deactivated badge was denied twice at the lobby at 19:02 Saturday; lobby video shows him leave at 19:03:50; there are no later events for him.",
     ["BADGE_BELLINI_DENIED_1", "BADGE_BELLINI_DENIED_2", "VIDEO_LOBBY_BELLINI", "VA_LOBBY_1902", "INT_MB_EXPLAINS"]),
    ("F-35", "Andrew Chen was in Lab 2A 13:59-16:31 Saturday, is not on the cabinet access list, and his September Shenzhen trip was an approved supplier audit.",
     ["BADGE_CHEN_SAT_IN", "BADGE_CHEN_SAT_LAB", "BADGE_CHEN_SAT_OUT", "LPR_CHEN_SAT_IN", "LPR_CHEN_SAT_OUT", "INT_C_NO_ACCESS", "INT_C_TRAVEL", "EMAIL_CHEN_TRAVEL"]),
    ("F-36", "ES-0007 is the only functional Kestrel unit; the look-alike non-functional ES-0003 was left in the cabinet; 'the bird' is internal slang for Kestrel.",
     ["STMT_W_TWO_UNITS", "PHOTO_EMPTY_SLOT", "PHOTO_WHITEBOARD_BIRD", "INT_R_BIRD_COMMON", "MSG_V_BIRD"]),
    ("F-37", "'Supply chain dinner (private)' entries, created by Halvorsen, appear on eight evenings Jul-Oct; he sent 'supply chain dinner' texts to his spouse and wrote 'Told her supply chain dinner. Technically true.'",
     [f"CAL_DINNER_{m}" for m in MD if m != "1017"] + ["STMT_E_DINNERS", "MSG_E_COVER_0820", "MSG_V_SUPPLY_COVER", "STMT_EH_DINNERS"]),
    ("F-38", "Halvorsen's location history shows him at Osteria Lumen or The Marlowe on each of those evenings and stopping at Arbor Row Apartments on several of them.",
     [f"TL_H_MEET_{m}" for m in MD if m != "1017"] + ["TL_H_VAPT_0723", "TL_H_VAPT_0820", "TL_H_VAPT_0917", "TL_H_VAPT_1007"]),
    ("F-39", "+1-408-555-0147 used sectors serving the same venues on those evenings.",
     [f"CDR_0147_MEET_{m}" for m in MD if m not in ("1007", "1017")]),
    ("F-40", "Halvorsen habitually leaves his badge on a lanyard on his office coat stand; the CSU photo shows it there on Monday.",
     ["STMT_W_BADGE_HABIT", "PHOTO_BADGE_COATSTAND", "INT_H2_BADGE_COAT", "INT_H1_BADGE_ALWAYS"]),
    ("F-41", "On 2026-10-15 Halvorsen texted the 0147 number: 'Saturday. Dinner first, then I'll show you the view from my office. Nobody's around on weekends.'",
     ["MSG_V_SAT_PLAN"]),
    ("F-42", "Shen lives at Arbor Row Apartments, Sunnyvale, and told Halvorsen on 2026-10-14 she flies home on the 23rd.",
     ["INT_S_ADDRESS", "MSG_V_FLY_HOME"]),
]

INSIGHTS = [
    ("I-01", "Theft window narrowed to 22:00-23:00 Saturday; the 22:51 executive-override opening is the theft event.",
     "rule: temporal join of RFID presence with cabinet events", ["F-01", "F-02", "F-03"], 0.95, "obvious"),
    ("I-02", "Someone other than Halvorsen used his badge and PIN: his face-unlocked workstation 40 m away was in continuous use while the EBC door and cabinet opened, the suite was badged into while he was inside it, and a failed PIN preceded success (no failed PINs for BID-100001 in 90 days).",
     "rule: physical co-presence contradiction + anomaly vs. 90-day cabinet history", ["F-03", "F-08", "F-09", "F-40"], 0.85, "moderate"),
    ("I-03", "A second, unbadged person entered with Halvorsen at 21:36 (tailgating).",
     "anomaly: door-held alarm on a weekend night fused with video-analytics counts", ["F-06", "F-07"], 0.9, "moderate"),
    ("I-04", "Halvorsen's accounts are contradicted: not home (interview 1) and not alone (interview 2).",
     "rule: claim-vs-record contradiction", ["F-17", "F-18", "F-05", "F-20", "F-07", "F-12", "F-16", "F-21", "F-19"], 0.95, "moderate"),
    ("I-05", "'Vince (Supply)' is Vivian Shen of Pacific Harbor Advisory.",
     "entity resolution across phone contact, subscriber record, visitor log, address and location stops", ["F-22", "F-23", "F-24", "F-42", "F-20"], 0.85, "hidden"),
    ("I-06", "Halvorsen and the 0147 phone were co-located on nine evenings Jul-Oct, matching private 'supply chain dinner' blocks and cover texts: an undisclosed personal relationship.",
     "ml: spatiotemporal co-location clustering (e.g. DBSCAN on lat/lon/time) + calendar join", ["F-37", "F-38", "F-39", "F-26"], 0.85, "hidden"),
    ("I-07", "Shen's phone was in the Building E sector throughout 21:37-23:04 Saturday and near the restaurant earlier, contradicting her alibi.",
     "rule: claim-vs-record contradiction (cell-sector precision about 1.5 km)", ["F-26", "F-27", "F-21"], 0.8, "hidden"),
    ("I-08", "The unknown woman UF-1 drank from glass B in the CEO office and is the major contributor on the cabinet handle wiped Friday evening, so she handled the cabinet after Friday evening; Halvorsen did not.",
     "rule: DNA linkage + cleaning-schedule reasoning", ["F-13", "F-14", "F-15", "F-12"], 0.85, "moderate"),
    ("I-09", "Shen had opportunity and knowledge: she toured the EBC on 10-07 while Halvorsen opened the cabinet with his executive PIN, and the thief took the only functional unit, leaving the look-alike.",
     "reasoning over visit, cabinet log and item records", ["F-24", "F-25", "F-36"], 0.7, "hidden"),
    ("I-10", "Ortega's 'around 11:30' sighting is 23:03-23:04; his description (long dark coat, large tan tote carried with both arms) matches the P2 passenger and the restaurant photo.",
     "witness-time reconciliation against machine timestamps", ["F-30", "F-21", "F-07"], 0.75, "moderate"),
    ("I-11", "Halvorsen suspects Shen but hid the relationship and deleted the thread hours before interview 2: likely an unwitting facilitator obstructing to conceal an affair, not the thief.",
     "reasoning over post-event messages and device deletion artefacts", ["F-29", "F-22", "F-18", "F-08"], 0.7, "hidden"),
    ("I-12", "Possible disposal route: Sunday 09:26-09:59 near a pack-and-ship store, then a call to Hong Kong and 'Thank you for everything'. Unproven; needs business records.",
     "sequence pattern over location, calls and messages", ["F-28", "F-29", "F-27"], 0.5, "hidden"),
    ("I-13", "Red herring resolved: Raman's motive texts and minor handle DNA are explained by her legitimate Friday return (after the Friday wipe), and she was at Lake Tahoe during the theft window.",
     "alibi verification", ["F-33", "F-14", "F-01"], 0.9, "moderate"),
    ("I-14", "Red herrings resolved: Bellini never got in; Chen left at 16:31 while ES-0007 was still present at 22:00. Foreign travel is not evidence of guilt.",
     "alibi verification + bias guard", ["F-34", "F-35", "F-02"], 0.9, "obvious"),
    ("I-15", "Halvorsen arranged the camera outage for privacy, and the thief exploited it together with single-person executive override, unmonitored weekend alerts and the badge-on-coat-stand habit.",
     "reasoning over requests and security procedures", ["F-10", "F-11", "F-41", "F-32", "F-40"], 0.8, "moderate"),
    ("I-16", "Time pressure: Shen leaves on Friday 2026-10-23; floor 4 Wi-Fi logs expire around 2026-10-31; EBC footage from 2026-10-07 expires around 2026-11-06.",
     "deadline extraction from statements and retention notes", ["F-27", "F-42"], 0.9, "moderate"),
]
INSIGHT_EXTRA_CITES = {"I-16": ["REF_WIFI_LOGS", "REF_EBC_CAM_RETENTION", "STMT_B_RETENTION", "VMS_EBC_1007_AVAILABLE"],
                       "I-02": ["CAB_1007_EXEC_OPEN"]}

GAPS = [
    ("G-01", "Whose DNA is UF-1?", "Ties a named person to the CEO office and to the cabinet handle after the Friday wipe.",
     ["I-08", "I-05", "I-07"], "No reference sample from Vivian Shen; she declined voluntarily.",
     [("A-02", "Search warrant for a reference buccal swab from Vivian Shen; compare with UF-1 (LAB-26-3318 Q2, Q4).")],
     0.95, "2026-10-23 (departure)"),
    ("G-02", "Who was on floor 4, and at the EBC, during the camera outage?",
     "Physically places the badge user at the cabinet at 22:51.", ["I-02", "I-03"],
     "No floor 4 Wi-Fi association logs or elevator car-call logs were exported.",
     [("A-03", "WLAN controller export: client associations to AP-E4-01..06, 2026-10-17 21:00-23:30 PDT (client MAC, hostname, SSID, AP, RSSI, connect and disconnect)."),
      ("A-07", "LiftCore controller export: car calls and door events, cars 1-4, floors P2 and 4, 2026-10-17 21:30-23:10 PDT.")],
     0.85, "2026-10-31 (Wi-Fi retention)"),
    ("G-03", "Who was the passenger in Halvorsen's car?", "Halvorsen denies anyone was with him; identity links the second person to the theft window.",
     ["I-03", "I-04", "I-07"], "Video is too dark for faces; no restaurant or rideshare records.",
     [("A-06", "Osteria Lumen: reservation book, POS receipts and CCTV, 2026-10-17 19:30-21:45."),
      ("A-01", "Search warrant: phone used by +1-408-555-0147 (messages, photos, location, rideshare apps), 2026-06-01 to 2026-10-22.")],
     0.8, ""),
    ("G-04", "How did the opener know the executive PIN?", "Explains the failed-then-successful PIN entry and the knowledge needed.",
     ["I-09", "I-02"], "No footage of the 2026-10-07 EBC walkthrough has been exported.",
     [("A-05", "VMS export CAM-E-F4-02 (EBC interior), 2026-10-07 14:25-16:10 PDT."),
      ("A-11", "Re-interview Halvorsen: did he enter the executive PIN in Shen's presence on 10-07?")],
     0.7, "2026-11-06 (camera retention)"),
    ("G-05", "Where is ES-0007 now?", "Recovery of the unreleased GPU and export-control exposure.",
     ["I-12"], "No records from El Camino Plaza businesses; no shipping or courier data.",
     [("A-04", "ShipRight Sunnyvale: transactions, shipping labels and CCTV, 2026-10-18 09:15-10:15; outbound shipments to Hong Kong 2026-10-18 to 2026-10-22."),
      ("A-01", "Search warrant: phone used by +1-408-555-0147.")],
     0.9, "ASAP"),
    ("G-06", "Was Shen at her apartment on Saturday evening, as she claims?", "Tests her alibi with precise data instead of cell sectors.",
     ["I-07"], "No building access, garage or rideshare records for Arbor Row.",
     [("A-10", "Arbor Row Apartments: fob and garage access logs, 2026-10-17 18:00 to 2026-10-18 12:00."),
      ("A-06", "Osteria Lumen records and CCTV."), ("A-01", "Search warrant: phone used by +1-408-555-0147.")],
     0.6, ""),
    ("G-07", "Who directs or pays Shen? Is Pacific Harbor Advisory a front?", "Motive, tasking and possible economic-espionage charges.",
     ["I-05", "I-09"], "No corporate registry or financial records.",
     [("A-08", "Bank subpoena: Pacific Harbor Advisory LLC accounts and beneficial owners, 2026-05-01 to present; corporate registry filings.")],
     0.6, ""),
    ("G-08", "Who received the Sunday 10:05 call to Hong Kong?", "Possible handler or buyer contact right after the likely disposal.",
     ["I-12"], "Carrier masked the number; no device extraction.",
     [("A-09", "Carrier: unmasked B-number for the 2026-10-18 10:05:12 PDT call from +1-408-555-0147; international request for the subscriber."),
      ("A-01", "Search warrant: phone used by +1-408-555-0147.")],
     0.55, ""),
    ("G-09", "Did Halvorsen knowingly take part?", "Decides the insurer's officer-knowledge exclusion and possible charges.",
     ["I-02", "I-11"], "Consent extraction was limited by counsel; no financial review of Halvorsen.",
     [("A-01", "Search warrant: phone used by +1-408-555-0147 (communications about Halvorsen)."),
      ("A-08", "Financial records: payments between Pacific Harbor Advisory and Halvorsen, if any."),
      ("A-11", "Re-interview Halvorsen with the DNA and Wi-Fi results.")],
     0.75, ""),
]

ARTIFACTS = {
    "A-01": ("Device extraction of the phone used by +1-408-555-0147 (search warrant)", "digital_forensics"),
    "A-02": ("Reference DNA from Vivian Shen (search warrant)", "biological"),
    "A-03": ("Floor 4 Wi-Fi association logs", "network_log"),
    "A-04": ("Pack-and-ship store transactions, labels and CCTV", "business_records"),
    "A-05": ("EBC interior footage from 2026-10-07", "video"),
    "A-06": ("Restaurant reservation, receipts and CCTV", "business_records"),
    "A-07": ("Elevator controller logs", "building_systems"),
    "A-08": ("Bank and corporate records", "financial"),
    "A-09": ("Unmasked international call record and subscriber", "telecom"),
    "A-10": ("Apartment access and garage logs", "building_systems"),
    "A-11": ("Targeted re-interview of Halvorsen", "interview"),
}

QUESTIONS = [
    ("Q-01", "When was ES-0007 taken?", "answered", "Between 22:00 and 23:00 Sat 2026-10-17; the cabinet was opened at 22:51:14.", ["F-02", "F-03"], []),
    ("Q-02", "Whose credentials opened the cabinet?", "answered", "Halvorsen's badge BID-100001 with the executive PIN.", ["F-03", "F-04"], []),
    ("Q-03", "Was Halvorsen physically at the cabinet at 22:51?", "answered_inference", "Very unlikely; he was at his face-unlocked workstation in 4-01.", ["F-08", "F-09"], ["G-02"]),
    ("Q-04", "Where was Halvorsen on Saturday evening?", "answered", "Osteria Lumen, then Building E 21:35-23:07, a stop at Arbor Row, then home.", ["F-05", "F-20"], []),
    ("Q-05", "Was anyone with Halvorsen?", "answered_inference", "Yes, one unbadged person.", ["F-06", "F-07", "F-12", "F-21", "F-30"], ["G-03"]),
    ("Q-06", "Who is UF-1?", "gap", "Unknown until a reference sample is compared.", ["F-13"], ["G-01"]),
    ("Q-07", "Who is 'Vince (Supply)'?", "answered_inference", "Vivian Shen, Pacific Harbor Advisory.", ["F-22", "F-23", "F-24"], []),
    ("Q-08", "Was Shen near Building E during the theft window?", "answered_inference", "Her phone used the Building E sector 21:37-23:04.", ["F-26"], ["G-02", "G-06"]),
    ("Q-09", "Did Shen know where the GPU was kept and how the cabinet opens?", "partial", "She toured the EBC during an executive-override opening; PIN observation is unproven.", ["F-24", "F-25"], ["G-04"]),
    ("Q-10", "Where is the GPU now?", "gap", "Unknown; Sunday plaza visit suggests a shipment.", ["F-28"], ["G-05"]),
    ("Q-11", "Why were the floor 4 cameras offline?", "answered", "Requested by Halvorsen via Ellis for 'board prep'; no board meeting existed.", ["F-10", "F-11"], []),
    ("Q-12", "Could Priya Raman have taken it?", "answered", "No: returned it Friday, it was present at 22:00 Saturday, and she was at Lake Tahoe.", ["F-01", "F-02", "F-33"], []),
    ("Q-13", "Could Marco Bellini have taken it?", "answered", "No: denied entry and left at 19:03.", ["F-34"], []),
    ("Q-14", "Could Andrew Chen have taken it?", "answered", "No: left at 16:31 while the unit was still present at 22:00; no cabinet access.", ["F-35", "F-02"], []),
    ("Q-15", "Was Halvorsen complicit?", "partial", "Evidence points to an unwitting facilitator who concealed an affair.", ["F-08", "F-29", "F-22"], ["G-09"]),
    ("Q-16", "What is the relationship between Halvorsen and Shen?", "answered_inference", "A concealed personal relationship since July.", ["F-37", "F-38", "F-39", "F-41"], []),
    ("Q-17", "Who did Shen contact after the theft?", "gap", "A masked Hong Kong number at 10:05 Sunday.", ["F-28"], ["G-08"]),
    ("Q-18", "Who is directing or paying Shen?", "gap", "Unknown.", [], ["G-07"]),
]

RED_HERRINGS = [
    ("RH-01", "P-04", "Priya Raman", "Had custody Friday, resentful texts ('They'll regret it'), minor DNA on the handle, named by staff.",
     "Returned the unit at 19:12 Friday (present at 20:00 and 22:00 scans); at Lake Tahoe during the theft window; her handle DNA fits the Friday return after the Friday wipe.",
     ["F-01", "F-02", "F-33", "F-14"]),
    ("RH-02", "P-09", "Marco Bellini", "Former employee now at a competitor; badge activity Saturday evening.",
     "Badge denied twice; video shows him leave at 19:03:50; no further access.", ["F-34"]),
    ("RH-03", "P-05", "Andrew Chen", "In the building on Saturday; recent travel to Shenzhen (bias trap).",
     "Left at 16:31 while the unit was still present at 22:00; not on the cabinet access list; travel was an approved audit. Travel or nationality is not evidence.",
     ["F-35", "F-02"]),
    ("RH-04", "P-06", "Tom Brandt", "Scheduled the camera outage.",
     "The outage was requested by the CEO's office in writing; no badge activity for Brandt that weekend.", ["F-10"]),
    ("RH-05", "P-01", "Richard Halvorsen as the thief", "His badge and PIN opened the cabinet; he lied about his whereabouts.",
     "He was at his face-unlocked workstation during the opening; he lied to hide an affair, not the theft.", ["F-08", "F-09", "F-29"]),
]

TRUE_TIMELINE = [
    ("2026-06-11 21:00", "P-02", "Silicon Futures Summit, San Jose", "Shen meets Halvorsen at the summit and begins cultivating him.", "MSG_V_FIRST"),
    ("2026-07-09 19:15", "P-01;P-02", "Osteria Lumen", "First private dinner; relationship becomes personal over the summer.", "TL_H_MEET_0709"),
    ("2026-10-05 16:20", "P-01", "-", "Halvorsen invites Shen to see 'the bird' and arranges a partner briefing.", "MSG_V_TOUR_INVITE"),
    ("2026-10-07 15:08", "P-01;P-02", "EBC 4-12", "Halvorsen opens the cabinet with his executive PIN while Shen watches; she learns the PIN and which unit works.", "CAB_1007_EXEC_OPEN"),
    ("2026-10-14 22:40", "P-02", "-", "Shen says she flies home on the 23rd and asks for one more evening.", "MSG_V_FLY_HOME"),
    ("2026-10-15 14:55", "P-01", "-", "Halvorsen has Ellis arrange the floor 4 camera outage for Saturday night, for privacy.", "MSG_J_CAMERA_REQ"),
    ("2026-10-16 19:12", "P-04", "EBC 4-12", "Raman returns ES-0007 after thermal runs.", "CAB_1016_DEPOSIT"),
    ("2026-10-17 19:02", "P-09", "Lobby", "Bellini's deactivated badge is denied; he leaves.", "BADGE_BELLINI_DENIED_1"),
    ("2026-10-17 20:12", "P-01;P-02", "Osteria Lumen", "Dinner. Shen brings a large tan tote.", "PHOTO_RESTAURANT_1017"),
    ("2026-10-17 21:36", "P-01;P-02", "P2 elevator lobby", "Halvorsen badges in; Shen follows unbadged.", "BADGE_H_P2_ENTRY"),
    ("2026-10-17 22:49", "P-01", "Office 4-01", "Halvorsen goes to his desk to answer keynote email.", "WS_UNLOCK_2249"),
    ("2026-10-17 22:50", "P-02", "Executive suite to EBC", "Shen takes Halvorsen's badge from the coat stand and walks to the EBC.", "BADGE_EBC_H_BADGE_2250"),
    ("2026-10-17 22:51", "P-02", "EBC 4-12", "First PIN attempt fails; second succeeds. She takes ES-0007, leaves ES-0003.", "CAB_1017_EXEC_OPEN"),
    ("2026-10-17 22:53", "P-02", "Executive suite", "She re-enters the suite with the badge and returns it to the coat stand.", "BADGE_SUITE_H_BADGE_2253"),
    ("2026-10-17 23:03", "P-01;P-02", "P2", "They leave; she carries the tote with both arms. Ortega sees them.", "VIDEO_P2_DEPART_TWO"),
    ("2026-10-17 23:20", "P-01;P-02", "Arbor Row Apartments", "Halvorsen drops Shen at her apartment.", "TL_H_VAPT_1017"),
    ("2026-10-18 09:26", "P-02", "El Camino Plaza", "Shen ships ES-0007 from ShipRight declared as a camera lens assembly to a Hong Kong freight forwarder.", "CDR_0147_PLAZA_1"),
    ("2026-10-18 10:05", "P-02", "Arbor Row Apartments", "Shen calls her handler in Hong Kong.", "CDR_0147_HK_CALL"),
    ("2026-10-19 07:40", "P-03", "EBC 4-12", "Whitfield discovers the empty slot.", "STMT_W_DISCOVERY"),
    ("2026-10-20 07:58", "P-01", "-", "Halvorsen deletes the 'Vince (Supply)' thread before his second interview.", "EXTRACT_DELETION"),
    ("2026-10-23 12:00", "P-02", "SFO", "Scheduled departure to Hong Kong (future relative to case as-of time).", "INT_S_DEPARTURE"),
]


def solution_md() -> str:
    return f"""# Kestrel case: solution (ground truth)

> Synthetic, fictional training data. Do not include this folder in the upload ZIP.

**Case:** {CASE_ID}. {CASE_TITLE}.

## What happened

Vivian Shen, a principal of Pacific Harbor Advisory LLC, is a covert collector tasked through a handler
linked to Sundao Microelectronics (Shenzhen), a fictional chip company. Pacific Harbor is a front. She met
Aurion's founder and CEO, Richard Halvorsen, at a June industry summit and cultivated a personal relationship
with him. He saved her number as "Vince (Supply)" and covered their evenings as "supply chain dinners".

On 2026-10-07 Halvorsen gave her a private EBC walkthrough and opened secure cabinet SC-EBC-01 with his
executive PIN in front of her. She learned the PIN and which AX-9 unit was the working one (ES-0007).

On Saturday 2026-10-17 Halvorsen arranged for the floor 4 cameras to be off ("board prep"), to keep the
evening private. After dinner they went to his office. While he answered keynote email at his
face-unlocked workstation (22:49-22:58), she took his badge from the coat stand, opened the EBC and the cabinet
(one failed PIN, then success at 22:51:14), took ES-0007, left the look-alike ES-0003, and returned the badge.
She carried the GPU out in her tan tote at 23:03. On Sunday morning she shipped it from a pack-and-ship store
at El Camino Plaza to a Hong Kong freight forwarder and called her handler.

Halvorsen is an **unwitting facilitator**. He lied to police and deleted the thread to hide the affair, not
the theft. Priya Raman, Marco Bellini, Andrew Chen and Tom Brandt are cleared.

## Why it is not obvious

- The cabinet log points at the CEO's own credential, and staff point at Raman and Bellini.
- Shen appears only as a disguised contact name, a carrier subscriber, a visitor-log row, and an unknown DNA profile.
- Linking her requires entity resolution, co-location clustering, contradiction detection and DNA reasoning.

## Fair-reasoning note

Shen's nationality and the visitor log's `id_issuing_country` are protected attributes. The conclusion rests
on behaviour, access, location, DNA and communications only. Andrew Chen's Shenzhen trip is a deliberate bias
trap: a correct system must not raise suspicion from travel or national origin.

## Insurer view (Lattice Specialty, claim LSI-CC-26-009812)

Third-party theft facilitated by an officer's negligence, not officer dishonesty. The officer-knowledge
exclusion would likely not apply on current evidence, but G-09 must be closed first. Procedure failures
(single-person executive override, unmonitored weekend alerts, badge left unattended) are relevant to the claim.
"""


def write_all(out: Out, reg: Registry, R: str = ""):
    fact_ids = {f[0] for f in FACTS}
    facts = [{"id": fid, "kind": "observation", "statement": s, "citations": reg.cite(*tags)} for fid, s, tags in FACTS]
    out.json(R + "facts.json", facts)
    ins = []
    for iid, s, method, fids, conf, tier in INSIGHTS:
        assert all(f in fact_ids for f in fids), iid
        ins.append({"id": iid, "kind": "inference", "statement": s, "method": method, "supporting_facts": fids,
                    "extra_citations": reg.cite(*INSIGHT_EXTRA_CITES.get(iid, [])), "confidence": conf,
                    "difficulty": tier})
    out.json(R + "insights.json", ins)
    gaps = []
    closes = {}
    for gid, q, why, affects, missing, arts, prio, deadline in GAPS:
        for idx, (aid, _) in enumerate(arts):
            weight = 1.0 if idx == 0 else 0.5
            closes.setdefault(aid, []).append((gid, round(prio * weight * (1.25 if deadline else 1.0), 4)))
        gaps.append({"id": gid, "directed_question": q, "why_it_matters": why, "affected_insights": affects,
                     "missing_evidence": missing, "priority": prio, "deadline": deadline,
                     "recommended_artifacts": [{"artifact_id": a, "artifact": ARTIFACTS[a][0],
                                                "artifact_type": ARTIFACTS[a][1],
                                                "closes": "primary" if i == 0 else "partial",
                                                "example_request": req}
                                               for i, (a, req) in enumerate(arts)]})
    out.json(R + "gaps.json", gaps)
    ranked = sorted(([aid, ARTIFACTS[aid][0], ARTIFACTS[aid][1], [g for g, _ in v], round(sum(p for _, p in v), 2)]
                     for aid, v in closes.items()), key=lambda x: (-x[4], x[0]))
    out.json(R + "artifact_value.json", {
        "method": "value = sum over gaps of priority x (1.0 if the artifact is the gap's primary closer, else 0.5) "
                  "x (1.25 if the gap has a deadline)",
        "ranking": [{"rank": i, "artifact_id": a, "artifact": n, "artifact_type": t, "gaps_addressed": g,
                     "value_score": s} for i, (a, n, t, g, s) in enumerate(ranked, 1)]})
    out.json(R + "questions.json", [{"id": qid, "directed_question": q, "status": st, "expected_answer": a,
                                     "facts": fs, "gaps": gs} for qid, q, st, a, fs, gs in QUESTIONS])
    out.json(R + "red_herrings.json", [{"id": rid, "person_id": pid, "subject": who, "misleading_signals": sig,
                                        "resolution": res, "facts": fs} for rid, pid, who, sig, res, fs in RED_HERRINGS])
    persons = [{"id": p["pid"], "name": p["name"], "role": p["role"], "organization": p["org"],
                "badge_id": p["badge"], "phone": p["phone"], "vehicle_plate": p["plate"],
                "truth_status": p["truth_status"]} for p in PEOPLE.values()]
    places = [{"id": f"L-{k}", "name": v[0], "lat": v[1], "lon": v[2], "kind": v[3]} for k, v in PLACES.items()]
    out.json(R + "entities.json", {
        "persons": persons, "places": places,
        "items": [{"id": k, "description": v, "stolen": k == "ES-0007"} for k, v in ITEMS.items()],
        "aliases": [{"alias": "Vince (Supply)", "resolves_to": "P-02", "evidence": "I-05"},
                    {"alias": "UF-1 (unknown female DNA profile)", "resolves_to": "P-02", "evidence": "truth only"},
                    {"alias": "V. Shen", "resolves_to": "P-02", "evidence": "F-23, F-24"},
                    {"alias": "the bird", "resolves_to": "AX-9 Kestrel", "evidence": "F-36"}],
        "protected_attributes": ["visitor_log.id_issuing_country", "nationality", "ethnicity"]})
    rows = []
    for t, who, where, what, tag in TRUE_TIMELINE:
        k = reg.keys[tag]
        rows.append([t, who, where, what, k["evidence_id"], k["locator"]])
    out.csv(R + "true_timeline.csv", ["time_local", "actors", "place", "event", "best_evidence_id", "locator"], rows)
    out.text(R + "solution.md", solution_md())

    # Record-level labels and per-file labels
    recs = reg.records
    out.csv(R + "record_labels.csv", ["evidence_id", "locator", "relevance", "noise_type", "key_tags", "note"],
            [[r["evidence_id"], r["locator"], r["relevance"], r["noise_type"], r["key_tags"], r["note"]] for r in recs])
    by_e = {}
    for r in recs:
        by_e.setdefault(r["evidence_id"], Counter())[r["relevance"]] += 1
    order = ["key", "supporting", "red_herring", "context", "background", "noise"]
    erows = []
    for e in CATALOG:
        c = by_e.get(e.eid, Counter())
        top = next((o for o in order if c.get(o)), "background")
        erows.append([e.eid, e.path, e.modality, top, c.get("key", 0), c.get("supporting", 0), c.get("red_herring", 0),
                      c.get("context", 0), c.get("background", 0), c.get("noise", 0), sum(c.values())])
    out.csv(R + "evidence_labels.csv", ["evidence_id", "path", "modality", "highest_relevance", "n_key",
                                        "n_supporting", "n_red_herring", "n_context", "n_background", "n_noise",
                                        "n_records"], erows)
    out.json(R + "key_locators.json", reg.keys)
