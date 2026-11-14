"""Email archive items."""
from __future__ import annotations

from ..common import Out, Registry
from .common import _doc

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
