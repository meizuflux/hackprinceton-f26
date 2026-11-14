"""Written statements."""
from __future__ import annotations

from ..common import Out, Registry
from .common import BANNER, _doc

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
