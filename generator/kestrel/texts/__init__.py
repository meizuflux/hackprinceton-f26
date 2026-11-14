"""Narrative documents. Each writer registers its own `{{TAG}}` locators."""
from __future__ import annotations

from ..common import Out, Registry
from .emails import emails
from .interviews import interviews
from .reports import reports
from .statements import statements


def write_all(out: Out, reg: Registry) -> None:
    reports(out, reg)
    statements(out, reg)
    interviews(out, reg)
    emails(out, reg)
