"""Phone message extractions (Cellebrite-style CSV): Halvorsen iPhone and Raman Android."""
from __future__ import annotations

from datetime import timedelta

from .cast import MEETINGS, PEOPLE as P, T
from .catalog import path_of
from .common import Out, Registry, daterange, iso_utc, lt, rng

# (local time, direction from the device owner's perspective, body, key tag or "", relevance)
SHEN_THREAD = [
    ("2026-06-11 22:14:05", "in", "It was a pleasure meeting you tonight. Your point about packaging being the real bottleneck stayed with me. - V.", "MSG_V_FIRST", "supporting"),
    ("2026-06-11 22:31:40", "out", "Likewise. Rare to meet someone who actually reads the substrate roadmaps. Coffee next time you're in the valley?", "", "supporting"),
    ("2026-06-12 08:05:12", "in", "I'm here through the autumn on a long engagement. Coffee would be lovely.", "MSG_V_LONG_ENGAGEMENT", "supporting"),
    ("2026-06-24 18:40:33", "out", "Still owe you that coffee. Thursday the 9th? Somewhere quieter than the summit.", "", "supporting"),
    ("2026-06-24 19:02:10", "in", "Thursday works. You choose.", "", "supporting"),
    ("2026-07-09 17:15:48", "out", "Osteria Lumen, 7:30. Back corner.", "MSG_V_OSTERIA_0709", "supporting"),
    ("2026-07-09 17:20:02", "in", "See you there.", "", "supporting"),
    ("2026-07-09 23:02:31", "in", "Thank you for tonight. I don't usually talk that long about anything.", "", "supporting"),
    ("2026-07-09 23:10:09", "out", "Neither do I. Again soon.", "", "supporting"),
    ("2026-07-22 12:30:44", "out", "Tomorrow, same place?", "", "supporting"),
    ("2026-07-22 12:41:20", "in", "Yes.", "", "supporting"),
    ("2026-07-23 23:15:02", "in", "Home safe. Thank you for the ride.", "MSG_V_RIDE_0723", "supporting"),
    ("2026-08-05 21:50:11", "in", "Is tomorrow still all right? I know it's a big week for you.", "", "supporting"),
    ("2026-08-05 22:03:37", "out", "Never too big. The Marlowe, 7:30.", "", "supporting"),
    ("2026-08-06 23:48:19", "in", "Drive safe.", "", "supporting"),
    ("2026-08-19 09:12:50", "out", "Thursday?", "", "supporting"),
    ("2026-08-19 09:30:05", "in", "Thursday.", "", "supporting"),
    ("2026-08-20 22:55:41", "out", "E. asked where I was. Told her supply chain dinner. Technically true.", "MSG_V_SUPPLY_COVER", "key"),
    ("2026-08-20 22:57:02", "in", "Technically.", "", "supporting"),
    ("2026-09-02 19:40:00", "out", "Tomorrow at the Marlowe?", "", "supporting"),
    ("2026-09-02 19:44:31", "in", "I'll be at the bar.", "", "supporting"),
    ("2026-09-16 20:15:10", "in", "Still on for tomorrow?", "", "supporting"),
    ("2026-09-16 20:20:55", "out", "Wouldn't miss it.", "", "supporting"),
    ("2026-09-17 23:30:12", "in", "You talk about the bird like it's your child.", "MSG_V_BIRD", "key"),
    ("2026-09-17 23:34:48", "out", "It sort of is. Wait until you see it.", "", "supporting"),
    ("2026-09-30 18:02:27", "out", "Tomorrow 7:30, usual spot.", "", "supporting"),
    ("2026-10-01 19:21:09", "out", "Running late, board call. 7:45?", "", "supporting"),
    ("2026-10-01 19:22:30", "in", "I'll be at the bar.", "", "supporting"),
    ("2026-10-05 16:20:14", "out", "Come by Wednesday afternoon. Jordan will set it up as a partner briefing. I'll show you the bird.", "MSG_V_TOUR_INVITE", "key"),
    ("2026-10-05 16:26:51", "in", "Are you sure that's wise?", "", "supporting"),
    ("2026-10-05 16:27:40", "out", "It's my company.", "", "supporting"),
    ("2026-10-07 16:12:03", "in", "Thank you for today. It's beautiful. I understand now why you never sleep.", "MSG_V_TOUR_THANKS", "key"),
    ("2026-10-07 16:15:20", "out", "Told you. Dinner? 7:15.", "", "supporting"),
    ("2026-10-14 22:40:16", "in", "My engagement ends soon. I fly home on the 23rd.", "MSG_V_FLY_HOME", "key"),
    ("2026-10-14 22:46:02", "out", "That's too soon.", "", "supporting"),
    ("2026-10-14 22:47:30", "in", "One more evening? Somewhere that's just ours.", "MSG_V_ONE_MORE", "supporting"),
    ("2026-10-15 09:12:44", "out", "Saturday. Dinner first, then I'll show you the view from my office. Nobody's around on weekends.", "MSG_V_SAT_PLAN", "key"),
    ("2026-10-15 09:20:01", "in", "I'd like that.", "", "supporting"),
    ("2026-10-17 20:05:30", "in", "Five minutes away.", "MSG_V_ARRIVING_1017", "supporting"),
    ("2026-10-17 23:24:11", "out", "Thank you for tonight. It was perfect.", "MSG_V_AFTER_1017", "key"),
    ("2026-10-17 23:27:40", "in", "It was. Sleep well, R.", "", "supporting"),
    ("2026-10-18 10:12:09", "in", "Thank you for everything. Truly.", "MSG_V_THANK_EVERYTHING", "key"),
    ("2026-10-18 10:40:33", "out", "Anytime. Brunch with E.'s parents, talk later.", "", "supporting"),
    ("2026-10-19 09:15:20", "out", "Something happened at work. Can you call me?", "MSG_V_SOMETHING_HAPPENED", "supporting"),
    ("2026-10-19 14:02:51", "in", "So sorry, back-to-back meetings all day. Is everything all right?", "", "supporting"),
    ("2026-10-19 21:30:06", "out", "Saturday, when I was on my laptop. Did you see anyone else on the floor?", "MSG_V_SAW_ANYONE", "key"),
    ("2026-10-19 21:46:18", "in", "No one. Just us. Why?", "MSG_V_JUST_US", "key"),
    ("2026-10-19 21:48:02", "out", "Nothing. Forget it.", "", "supporting"),
]
UNRECOVERABLE = {"2026-08-06 23:48:19", "2026-09-30 18:02:27", "2026-10-15 09:20:01"}

EXEC_STAFF = [("+14085550190", "Michael Okafor (CFO)"), ("+14085550192", "Lena Vogel (CTO)"),
              ("+14085550193", "Grace Liu (CMO)"), ("+14085550194", "Daniel Ruiz (General Counsel)")]
EXEC_LINES = ["Q3 close is on track.", "Keynote deck v7 is in the shared folder.", "Foundry call moved to Thursday.",
              "Can we push staff by 30 min?", "Hiring plan approved.", "Analyst day agenda attached.",
              "Need your sign-off on the press embargo.", "Thermal margins look better on rev B.",
              "Board pre-read goes out Friday.", "Customer escalation resolved.", "Kestrel launch checklist updated.",
              "Legal review of the partner NDA template is done.", "Supply update: substrates look fine for Q1.",
              "Who's covering the Tokyo call?", "Great quarter, team."]
ELAINE_LINES = [("in", "Can you pick up milk on the way home?"), ("out", "Will do."),
                ("in", "Dinner at 7?"), ("out", "Should make it."), ("in", "Don't forget the school fundraiser Saturday."),
                ("out", "On the calendar."), ("in", "Plumber is coming Thursday 9-11."), ("out", "Thanks."),
                ("in", "Mom says hi."), ("out", "Hi back.")]
JORDAN_LINES = [("in", "Your 3pm moved to 3:30."), ("in", "Car at 6:15 for SFO tomorrow."), ("out", "Thanks."),
                ("in", "Board pre-read is in your inbox."), ("out", "Can you move my 1:1s on Friday?"),
                ("in", "Done."), ("in", "Analyst dinner confirmed for the 24th."), ("in", "Reminder: keynote dry run 2pm."),
                ("out", "Running 10 min late."), ("in", "No problem, I'll let them know.")]


def _row(rid, thread_id, thread_name, t, direction, number, name, body, service="iMessage", deleted=False,
         deleted_t=None, attachment=""):
    return [rid, thread_id, thread_name, iso_utc(t), "Incoming" if direction == "in" else "Outgoing", number, name,
            body, service, "Read" if direction == "in" else "Delivered", "Yes" if deleted else "No",
            iso_utc(deleted_t) if deleted_t else "", attachment]


HEADER = ["record_id", "thread_id", "thread_name", "timestamp_utc", "direction", "party_number", "party_name", "body",
          "service", "status", "deleted", "deleted_utc", "attachment"]


def write_halvorsen(out: Out, reg: Registry):
    r = rng("msgs_h")
    eid = "EV-050"
    msgs = []  # (t, thread_id, thread_name, direction, number, name, body, service, deleted, tag, rel, noise)
    for t_str, d, body, tag, rel in SHEN_THREAD:
        b = "[message body unrecoverable]" if t_str in UNRECOVERABLE else body
        noise = "unrecoverable_body" if t_str in UNRECOVERABLE else ""
        msgs.append((lt(t_str), "T01", "Vince (Supply)", d, P["shen"]["phone"], "Vince (Supply)", b, "iMessage", True,
                     tag, rel, noise))
    # Elaine: cover stories on meeting nights + routine chatter
    e_num = P["e_halvorsen"]["phone"]
    covers = ["Supply chain dinner tonight, late.", "Dinner with suppliers, don't wait up.",
              "Supply chain dinner, back late.", "Late one tonight, supplier dinner."]
    for i, (day, _venue) in enumerate(MEETINGS):
        if day == "2026-10-17":
            continue
        tag = "MSG_E_COVER_0820" if day == "2026-08-20" else ""
        msgs.append((lt(f"{day} 18:31:{10 + i:02d}"), "T02", "Elaine", "out", e_num, "Elaine", covers[i % 4], "iMessage",
                     False, tag, "key" if tag else "supporting", ""))
    msgs += [
        (lt("2026-10-17 18:55:02"), "T02", "Elaine", "in", e_num, "Elaine", "Are you home for dinner?", "iMessage",
         False, "", "supporting", ""),
        (lt("2026-10-17 19:01:40"), "T02", "Elaine", "out", e_num, "Elaine", "Board prep tonight, sorry. Late one.",
         "iMessage", False, "MSG_E_BOARDPREP", "key", ""),
        (lt("2026-10-17 21:12:15"), "T02", "Elaine", "out", e_num, "Elaine", "Running long. Don't wait up.", "iMessage",
         False, "MSG_E_RUNNING_LONG", "key", ""),
        (lt("2026-10-17 23:41:05"), "T02", "Elaine", "out", e_num, "Elaine", "Home in 5.", "iMessage", False,
         "MSG_E_HOME_IN_5", "supporting", ""),
        (lt("2026-10-19 12:30:44"), "T02", "Elaine", "out", e_num, "Elaine", "Something happened at work. Long day. Will explain tonight.",
         "iMessage", False, "", "context", ""),
    ]
    for d in daterange(lt("2026-07-01 00:00"), lt("2026-10-20 00:00")):
        if r.random() < 0.3:
            direction, body = r.choice(ELAINE_LINES)
            msgs.append((d + timedelta(hours=r.randint(9, 20), minutes=r.randint(0, 59), seconds=r.randint(0, 59)),
                         "T02", "Elaine", direction, e_num, "Elaine", body, "iMessage", False, "", "background", ""))
    # Jordan Ellis
    j = P["ellis"]["phone"]
    msgs += [
        (lt("2026-10-05 16:40:10"), "T03", "Jordan Ellis", "out", j, "Jordan Ellis",
         "Can you set up a partner briefing Wed 10/7 at 2:30 for V. Shen, Pacific Harbor Advisory? Add an EBC walkthrough.",
         "iMessage", False, "MSG_J_BRIEFING_REQ", "key", ""),
        (lt("2026-10-05 16:44:22"), "T03", "Jordan Ellis", "in", j, "Jordan Ellis",
         "On it. Should Dana join for the EBC part?", "iMessage", False, "", "supporting", ""),
        (lt("2026-10-05 16:45:01"), "T03", "Jordan Ellis", "out", j, "Jordan Ellis",
         "Not needed, I'll walk her through it myself.", "iMessage", False, "MSG_J_NO_DANA", "key", ""),
        (lt("2026-10-15 14:55:30"), "T03", "Jordan Ellis", "out", j, "Jordan Ellis",
         "Can you block Saturday 9 to 11:30pm as board prep, private? And ask Tom whether the camera firmware work on 4 "
         "can happen in that window. I'd rather not have board material on a recording.", "iMessage", False,
         "MSG_J_CAMERA_REQ", "key", ""),
        (lt("2026-10-15 15:02:11"), "T03", "Jordan Ellis", "in", j, "Jordan Ellis",
         "Will do. Tom mentioned the update needs a two-hour window anyway.", "iMessage", False, "", "supporting", ""),
        (lt("2026-10-15 16:25:48"), "T03", "Jordan Ellis", "in", j, "Jordan Ellis",
         "Done. CHG-4471, Saturday 9:00-11:30pm.", "iMessage", False, "MSG_J_CHG_DONE", "key", ""),
        (lt("2026-10-19 08:25:30"), "T03", "Jordan Ellis", "in", j, "Jordan Ellis",
         "Police will be here at 9:45. I've booked 4-05 for them.", "iMessage", False, "", "context", ""),
    ]
    for d in daterange(lt("2026-07-01 00:00"), lt("2026-10-20 00:00")):
        if d.weekday() < 5 and r.random() < 0.3:
            direction, body = r.choice(JORDAN_LINES)
            msgs.append((d + timedelta(hours=r.randint(8, 18), minutes=r.randint(0, 59), seconds=r.randint(0, 59)),
                         "T03", "Jordan Ellis", direction, j, "Jordan Ellis", body, "iMessage", False, "",
                         "background", ""))
    # Security and EBC on Monday
    msgs += [
        (lt("2026-10-19 07:58:40"), "T05", "Dana Whitfield", "in", P["whitfield"]["phone"], "Dana Whitfield",
         "Richard, urgent: the Kestrel sample is not in the cabinet. Tom is on his way.", "iMessage", False,
         "MSG_D_URGENT", "supporting", ""),
        (lt("2026-10-19 08:01:12"), "T05", "Dana Whitfield", "out", P["whitfield"]["phone"], "Dana Whitfield",
         "On my way in.", "iMessage", False, "", "context", ""),
        (lt("2026-10-19 08:12:30"), "T04", "Tom Brandt", "in", P["brandt"]["phone"], "Tom Brandt",
         "Rich, ES-0007 is missing from the EBC cabinet. Cabinet log shows an executive-override opening Saturday night. Call me.",
         "iMessage", False, "MSG_T_MISSING", "supporting", ""),
        (lt("2026-10-19 08:13:05"), "T04", "Tom Brandt", "out", P["brandt"]["phone"], "Tom Brandt", "Calling.",
         "iMessage", False, "", "context", ""),
    ]
    # Exec staff group chat
    for d in daterange(lt("2026-07-01 00:00"), lt("2026-10-20 00:00")):
        if d.weekday() < 5 and r.random() < 0.35:
            num, name = r.choice(EXEC_STAFF)
            direction = "out" if r.random() < 0.25 else "in"
            msgs.append((d + timedelta(hours=r.randint(7, 21), minutes=r.randint(0, 59), seconds=r.randint(0, 59)),
                         "T06", "Exec Staff", direction, num if direction == "in" else "", name if direction == "in" else "",
                         r.choice(EXEC_LINES), "iMessage", False, "", "background", ""))
    # Automated notifications and spam (noise)
    for d in daterange(lt("2026-07-01 00:00"), lt("2026-10-20 00:00")):
        if r.random() < 0.18:
            kind = r.choice(["sso", "delivery", "bank", "spam"])
            body, number, name, noise = {
                "sso": (f"Your Aurion SSO code is {r.randint(100000, 999999)}. It expires in 10 minutes.", "AURION-SSO",
                        "", "automated_notification"),
                "delivery": ("Your package was delivered to the front door.", "DELIVERY", "", "automated_notification"),
                "bank": (f"Card ending 4417: ${r.randint(8, 240)}.{r.randint(0, 99):02d} at a merchant. Reply STOP to opt out.",
                         "BANK-ALERTS", "", "automated_notification"),
                "spam": ("Congratulations! You have been selected for an exclusive offer. Tap to claim.",
                         "+18885550147", "", "spam"),
            }[kind]
            msgs.append((d + timedelta(hours=r.randint(7, 22), minutes=r.randint(0, 59), seconds=r.randint(0, 59)),
                         "T07" if kind != "spam" else "T08", "Notifications" if kind != "spam" else "Unknown sender",
                         "in", number, name, body, "SMS", False, "", "noise", noise))
    msgs.sort(key=lambda m: (m[0], m[1]))
    rows, n = [], 0
    for m in msgs:
        t, tid, tname, d, num, name, body, svc, deleted, tag, rel, noise = m
        copies = [False]
        if not tag and rel != "noise" and r.random() < 0.01:
            copies.append(True)
        for dup in copies:
            n += 1
            rid = f"HMSG-{n:05d}"
            rows.append(_row(rid, tid, tname, t, d, num, name, body, svc, deleted,
                             T["thread_deleted"] if deleted else None))
            if dup:
                reg.rec(eid, f"record_id={rid}", "noise", "duplicate_sync_record")
                continue
            if tag:
                reg.key(tag, eid, f"record_id={rid}")
            reg.rec(eid, f"record_id={rid}", rel, noise, [tag] if tag else [],
                    "Thread deleted on device 2026-10-20 07:58 PDT; recovered from database free pages" if deleted else "")
    out.csv(path_of(eid), HEADER, rows)


def write_raman(out: Out, reg: Registry):
    r = rng("msgs_r")
    eid = "EV-051"
    m_num, d_num = P["iyer"]["phone"], P["whitfield"]["phone"]
    crew = [("+16505550191", "Sam K"), ("+14085550170", "Jess")]
    msgs = [
        ("2026-10-12 20:15:22", "T01", "Meera", "out", m_num, "Meera", "Got passed over for principal. Again. Third cycle.", "", "red_herring"),
        ("2026-10-12 20:18:40", "T01", "Meera", "in", m_num, "Meera", "Ugh, Priya. I'm sorry. You carried that thermal work.", "", "red_herring"),
        ("2026-10-12 20:22:05", "T01", "Meera", "out", m_num, "Meera", "Mensah got it. His name is on the Kestrel paper and he never touched the heat spreader.", "MSG_R_PASSED_OVER", "red_herring"),
        ("2026-10-14 21:40:11", "T01", "Meera", "in", m_num, "Meera", "Still on for Tahoe this weekend?", "", "supporting"),
        ("2026-10-14 21:41:30", "T01", "Meera", "out", m_num, "Meera", "More than ever. Leaving 6:30 Saturday.", "MSG_R_TAHOE_PLAN", "supporting"),
        ("2026-10-16 12:58:02", "T03", "Dana W", "out", d_num, "Dana W", "Coming up to sign out ES-0007 for thermal runs.", "MSG_R_SIGNOUT", "supporting"),
        ("2026-10-16 12:59:30", "T03", "Dana W", "in", d_num, "Dana W", "OK, meet you at the EBC at 1:05.", "", "supporting"),
        ("2026-10-16 13:01:44", "T01", "Meera", "out", m_num, "Meera", "Pulling the bird out for thermal runs, wish me luck", "", "red_herring"),
        ("2026-10-16 19:09:12", "T03", "Dana W", "out", d_num, "Dana W", "Depositing ES-0007 now. Thermal data looks great.", "MSG_R_DEPOSIT", "supporting"),
        ("2026-10-16 19:15:40", "T03", "Dana W", "in", d_num, "Dana W", "Thanks!", "", "context"),
        ("2026-10-16 21:10:33", "T01", "Meera", "out", m_num, "Meera", "Put the bird back in its cage tonight. They'll regret it when it ships with my thermal fix and my name nowhere on it.", "MSG_R_REGRET", "red_herring"),
        ("2026-10-16 21:12:01", "T01", "Meera", "in", m_num, "Meera", "Tahoe will fix you. Wine is packed.", "", "context"),
        ("2026-10-17 06:35:50", "T02", "Tahoe crew", "out", "", "", "On the road!", "", "supporting"),
        ("2026-10-17 07:02:18", "T02", "Tahoe crew", "in", crew[0][0], crew[0][1], "Coffee stop in Sac?", "", "context"),
        ("2026-10-17 11:02:40", "T02", "Tahoe crew", "out", "", "", "Lake is unreal. Phone going in a drawer.", "MSG_R_LAKE", "supporting"),
        ("2026-10-17 18:20:05", "T02", "Tahoe crew", "in", crew[1][0], crew[1][1], "Who's on grill duty", "", "context"),
        ("2026-10-17 22:48:51", "T02", "Tahoe crew", "out", "", "", "Who took my wine glass", "MSG_R_TAHOE_2248", "supporting"),
        ("2026-10-17 22:49:30", "T02", "Tahoe crew", "in", crew[0][0], crew[0][1], "Not me lol", "", "context"),
        ("2026-10-18 09:30:12", "T02", "Tahoe crew", "in", crew[1][0], crew[1][1], "Brunch at 10?", "", "context"),
        ("2026-10-18 19:20:44", "T01", "Meera", "out", m_num, "Meera", "Home. Back to the grind Monday.", "", "supporting"),
        ("2026-10-19 10:30:02", "T01", "Meera", "out", m_num, "Meera", "Something's going on at work. Police everywhere.", "", "context"),
        ("2026-10-19 10:31:15", "T01", "Meera", "in", m_num, "Meera", "What?!", "", "context"),
        ("2026-10-19 10:33:40", "T01", "Meera", "out", m_num, "Meera", "Can't say. The bird is gone.", "MSG_R_BIRD_GONE", "context"),
    ]
    full = []
    for t_str, tid, tname, d, num, name, body, tag, rel in msgs:
        full.append((lt(t_str), tid, tname, d, num, name, body, "SMS" if tid != "T02" else "RCS", tag, rel, ""))
    for d in daterange(lt("2026-10-01 00:00"), lt("2026-10-21 00:00")):
        if r.random() < 0.5:
            kind = r.choice(["sso", "delivery", "promo"])
            body, number, noise = {
                "sso": (f"Your Aurion SSO code is {r.randint(100000, 999999)}.", "AURION-SSO", "automated_notification"),
                "delivery": ("Your order has shipped.", "DELIVERY", "automated_notification"),
                "promo": ("Flash sale: 40% off running shoes today only.", "PROMO", "spam"),
            }[kind]
            full.append((d + timedelta(hours=r.randint(8, 21), minutes=r.randint(0, 59), seconds=r.randint(0, 59)),
                         "T09", "Notifications", "in", number, "", body, "SMS", "", "noise", noise))
    full.sort(key=lambda m: (m[0], m[1]))
    rows = []
    for n, m in enumerate(full, 1):
        t, tid, tname, d, num, name, body, svc, tag, rel, noise = m
        rid = f"RMSG-{n:05d}"
        rows.append(_row(rid, tid, tname, t, d, num, name, body, svc))
        if tag:
            reg.key(tag, eid, f"record_id={rid}")
        reg.rec(eid, f"record_id={rid}", rel, noise, [tag] if tag else [])
    out.csv(path_of(eid), HEADER, rows)


def write_all(out: Out, reg: Registry):
    write_halvorsen(out, reg)
    write_raman(out, reg)
