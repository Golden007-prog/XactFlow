from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    """How serious a Diagnostic is."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class Diagnostic:
    """One finding produced by library scanning, linking, or SCR checking.

    rule_id and rule_name are set when the finding corresponds to an IEEE 1685-2022
    Annex B semantic consistency rule (e.g. rule_id "SCR 1.1", rule_name "uniqueVLNV").
    They are left None for findings that are not an Annex B rule, such as a file that
    failed to parse at all.
    """

    message: str
    severity: Severity
    location: str
    rule_id: Optional[str] = None
    rule_name: Optional[str] = None

    def __str__(self) -> str:
        prefix = f"[{self.rule_id}] " if self.rule_id else ""
        return f"{self.severity.value}: {prefix}{self.message} ({self.location})"
