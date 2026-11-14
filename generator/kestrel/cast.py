"""The fictional world of the Kestrel case: organisation, people, places, devices, key times.

All people, companies, phone numbers (555-01xx range), plates, and addresses are invented.
"""
from __future__ import annotations

from .common import lt

CASE_ID = "SBRPD-26-104417"
CASE_TITLE = "Theft of AX-9 'Kestrel' engineering sample ES-0007"
CASE_AS_OF = lt("2026-10-22 18:00")
ORG = "Aurion Compute, Inc."
DOMAIN = "aurion-compute.example"
SITE_ADDRESS = "Aurion Park, Building E, 3100 Aurion Parkway, Santa Clara, CA 95054"
AGENCY = "South Bay Regional Police Department (SBRPD)"
LAB = "South Bay Regional Forensic Laboratory"
INSURER = "Lattice Specialty Insurance Co."
FRONT_COMPANY = "Pacific Harbor Advisory LLC"
SPONSOR_COMPANY = "Sundao Microelectronics (Shenzhen) Co., Ltd."
COMPETITOR = "Corvid Systems"

# truth_status vocabulary: perpetrator | unwitting_facilitator | cleared | witness | investigator | uninvolved
PEOPLE = {
    "halvorsen": dict(pid="P-01", name="Richard Halvorsen", role="Founder and CEO", org=ORG,
                      badge="BID-100001", phone="+14085550110", plate="8RHV521",
                      email=f"rhalvorsen@{DOMAIN}", truth_status="unwitting_facilitator"),
    "shen": dict(pid="P-02", name="Vivian Shen", role="Principal, Pacific Harbor Advisory (consultant)",
                 org=FRONT_COMPANY, badge=None, phone="+14085550147", plate=None,
                 email="v.shen@pacificharbor-advisory.example", truth_status="perpetrator"),
    "whitfield": dict(pid="P-03", name="Dana Whitfield", role="Executive Briefing Center (EBC) Manager", org=ORG,
                      badge="BID-200118", phone="+14085550138", plate="7DWH260",
                      email=f"dwhitfield@{DOMAIN}", truth_status="witness"),
    "raman": dict(pid="P-04", name="Priya Raman", role="Senior Staff Hardware Engineer, Thermal", org=ORG,
                  badge="BID-200233", phone="+14085550163", plate="7PRM334",
                  email=f"praman@{DOMAIN}", truth_status="cleared"),
    "chen": dict(pid="P-05", name="Andrew Chen", role="Staff Firmware Engineer", org=ORG,
                 badge="BID-200291", phone="+14085550152", plate="9ACH118",
                 email=f"achen@{DOMAIN}", truth_status="cleared"),
    "brandt": dict(pid="P-06", name="Tom Brandt", role="Director of Global Security", org=ORG,
                   badge="BID-100014", phone="+14085550131", plate="6TBR902",
                   email=f"tbrandt@{DOMAIN}", truth_status="cleared"),
    "ellis": dict(pid="P-07", name="Jordan Ellis", role="Executive Assistant to the CEO", org=ORG,
                  badge="BID-100022", phone="+14085550124", plate=None,
                  email=f"jellis@{DOMAIN}", truth_status="witness"),
    "ortega": dict(pid="P-08", name="Luis Ortega", role="Night Custodian (BrightPath Facility Services, contractor)",
                   org="BrightPath Facility Services", badge="BID-300417", phone="+14085550185", plate="8LOR441",
                   email=None, truth_status="witness"),
    "bellini": dict(pid="P-09", name="Marco Bellini", role="Former Senior Product Manager (resigned 2026-10-02)",
                    org=COMPETITOR, badge="BID-200157", phone="+15105550176", plate=None,
                    email=None, truth_status="cleared"),
    "e_halvorsen": dict(pid="P-10", name="Elaine Halvorsen", role="Spouse of Richard Halvorsen", org=None,
                        badge=None, phone="+14085550111", plate=None, email=None, truth_status="witness"),
    "iyer": dict(pid="P-11", name="Meera Iyer", role="Friend of Priya Raman", org=None,
                 badge=None, phone="+16505550168", plate=None, email=None, truth_status="uninvolved"),
    "delgado": dict(pid="P-12", name="Ray Delgado", role="Patrol Officer, Aegis Patrol Services (contract guard)",
                    org="Aegis Patrol Services", badge="BID-900031", phone=None, plate=None, email=None,
                    truth_status="uninvolved"),
    "reyes": dict(pid="P-13", name="Det. Ana Reyes", role="Lead Detective, SBRPD High-Tech Theft Unit", org=AGENCY,
                  badge=None, phone=None, plate=None, email=None, truth_status="investigator"),
    "okoye": dict(pid="P-14", name="Det. Sam Okoye", role="Detective, SBRPD High-Tech Theft Unit", org=AGENCY,
                  badge=None, phone=None, plate=None, email=None, truth_status="investigator"),
    "park": dict(pid="P-15", name="CST Lee Park", role="Crime Scene Technician, SBRPD", org=AGENCY,
                 badge=None, phone=None, plate=None, email=None, truth_status="investigator"),
    "doyle": dict(pid="P-16", name="Karen Doyle", role="SIU Investigator", org=INSURER,
                  badge=None, phone=None, plate=None, email=None, truth_status="investigator"),
}

# The handler number Shen called after the theft. The carrier masked the middle digits.
HK_NUMBER_MASKED = "+852-XXXX-0142"

# name, lat, lon, kind
PLACES = {
    "HQ": ("Aurion Park Building E, 3100 Aurion Parkway, Santa Clara", 37.38620, -121.97850, "workplace"),
    "OSTERIA": ("Osteria Lumen (restaurant), 1180 Franklin St, Santa Clara", 37.35230, -121.95480, "restaurant"),
    "MARLOWE": ("The Marlowe Hotel bar, 200 S 2nd St, San Jose", 37.33520, -121.88970, "hotel_bar"),
    "H_HOME": ("Halvorsen residence, Los Altos Hills", 37.37120, -122.13740, "residence"),
    "V_APT": ("Arbor Row Apartments, 455 Arbor Row, Sunnyvale", 37.37290, -122.02800, "residence"),
    "PLAZA": ("El Camino Plaza, Sunnyvale (ShipRight pack-and-ship, Bean Theory Coffee, CarePlus Pharmacy)",
              37.35300, -122.00900, "strip_mall"),
    "PD": ("SBRPD Headquarters, Santa Clara", 37.35410, -121.93620, "police"),
    "SF_FIDI": ("Financial District, San Francisco", 37.78970, -122.40000, "business_district"),
    "SJ_DT": ("Downtown San Jose", 37.33380, -121.89000, "business_district"),
    "PALO_ALTO": ("University Ave, Palo Alto", 37.44480, -122.16100, "business_district"),
    "SANTANA": ("Santana Row, San Jose", 37.32100, -121.94800, "shopping"),
    "R_HOME": ("Raman residence, Mountain View", 37.39610, -122.09280, "residence"),
    "TAHOE": ("Vacation rental, South Lake Tahoe", 38.93320, -119.98440, "residence_temp"),
    "C_HOME": ("Chen residence, San Jose", 37.30220, -121.86360, "residence"),
    "GOLF": ("Foothill Oaks Golf Club, Los Altos Hills", 37.36000, -122.11000, "recreation"),
    "GROCERY": ("Los Altos grocery", 37.37950, -122.11450, "shopping"),
    "SARATOGA": ("Residence of Elaine Halvorsen's parents, Saratoga", 37.26380, -122.02300, "residence"),
    "SFO": ("San Francisco International Airport", 37.62130, -122.37900, "airport"),
    "LUNCH1": ("Franklin Street lunch spots, Santa Clara", 37.35110, -121.95300, "restaurant"),
    "LUNCH2": ("Mission College Blvd cafes, Santa Clara", 37.38900, -121.98400, "restaurant"),
}

# Evenings Halvorsen and Shen spent together (venue key). 10-07 also includes the HQ visit.
MEETINGS = [
    ("2026-07-09", "OSTERIA"),
    ("2026-07-23", "OSTERIA"),
    ("2026-08-06", "MARLOWE"),
    ("2026-08-20", "MARLOWE"),
    ("2026-09-03", "MARLOWE"),
    ("2026-09-17", "OSTERIA"),
    ("2026-10-01", "MARLOWE"),
    ("2026-10-07", "OSTERIA"),
    ("2026-10-17", "OSTERIA"),
]
# Meeting nights on which Halvorsen dropped Shen at her apartment (visible in his location history).
DROPOFF_DATES = {"2026-07-23", "2026-08-20", "2026-09-17", "2026-10-07", "2026-10-17"}

ITEMS = {
    "ES-0007": "AX-9 'Kestrel' engineering sample, functional silicon (serial AX9-ES-0007-K)",
    "ES-0003": "AX-9 'Kestrel' thermal-mechanical sample, non-functional",
    "DK-0211": "Demo cable kit",
    "RS-0042": "PCIe riser set",
    "DS-0019": "Demo NVMe SSD",
}

# Ground-truth timeline anchors (Pacific time). Generators read these so every source agrees.
T = {
    "v_leaves_apt": lt("2026-10-17 19:55"),
    "dinner_start": lt("2026-10-17 20:12"),
    "photo_restaurant": lt("2026-10-17 20:58:12"),
    "depart_restaurant": lt("2026-10-17 21:21"),
    "lpr_in": lt("2026-10-17 21:35:48"),
    "p2_badge": lt("2026-10-17 21:36:31"),
    "p2_held_alarm": lt("2026-10-17 21:36:49"),
    "p2_closed": lt("2026-10-17 21:36:52"),
    "suite_badge": lt("2026-10-17 21:38:05"),
    "ws1_unlock": lt("2026-10-17 21:41:10"),
    "ws1_lock": lt("2026-10-17 21:52:40"),
    "rfid_last_present": lt("2026-10-17 22:00:00"),
    "ws2_unlock": lt("2026-10-17 22:49:02"),
    "suite_rex_1": lt("2026-10-17 22:50:31"),
    "ebc_badge": lt("2026-10-17 22:50:47"),
    "cab_auth": lt("2026-10-17 22:51:14"),
    "cab_open": lt("2026-10-17 22:51:16"),
    "cab_close": lt("2026-10-17 22:52:03"),
    "cab_lock": lt("2026-10-17 22:52:04"),
    "ebc_rex": lt("2026-10-17 22:52:40"),
    "suite_badge_2": lt("2026-10-17 22:53:09"),
    "email_sent": lt("2026-10-17 22:55:13"),
    "ws2_lock": lt("2026-10-17 22:58:30"),
    "rfid_first_absent": lt("2026-10-17 23:00:00"),
    "suite_rex_2": lt("2026-10-17 23:01:50"),
    "ortega_p2": lt("2026-10-17 23:02:15"),
    "p2_rex": lt("2026-10-17 23:03:40"),
    "lpr_out": lt("2026-10-17 23:07:31"),
    "dropoff": lt("2026-10-17 23:21"),
    "h_home": lt("2026-10-17 23:46"),
    "inv_alert": lt("2026-10-18 00:00:09"),
    "plaza_start": lt("2026-10-18 09:26"),
    "plaza_end": lt("2026-10-18 09:59"),
    "hk_call": lt("2026-10-18 10:05:12"),
    "discovery": lt("2026-10-19 07:40"),
    "alert_read": lt("2026-10-19 07:52:31"),
    "police_called": lt("2026-10-19 09:10"),
    "thread_deleted": lt("2026-10-20 07:58:20"),
}
