"""Machine logs. `write_all` order is part of the output: record ids are assigned after noise is merged."""
from __future__ import annotations

from ..common import Out, Registry
from .access import write_badges_and_lpr, write_cabinet, write_rfid
from .facility import write_calendar, write_guard, write_reference, write_visitors, write_workstation


def write_all(out: Out, reg: Registry) -> None:
    write_badges_and_lpr(out, reg)
    write_cabinet(out, reg)
    write_rfid(out, reg)
    write_visitors(out, reg)
    write_guard(out, reg)
    write_workstation(out, reg)
    write_calendar(out, reg)
    write_reference(out, reg)
