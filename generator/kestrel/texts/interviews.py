"""Interview transcripts."""
from __future__ import annotations

from ..common import Out, Registry
from .common import BANNER, _doc

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
