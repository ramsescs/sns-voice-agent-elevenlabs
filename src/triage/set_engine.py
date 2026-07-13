"""Deterministic SET mapping engine.

`classify()` maps `ClinicalFindings` onto a SET level via the open, versioned
rules in `rules/set_mapping.yaml`. It is a pure function: no I/O beyond the
module-level YAML load, no LLM calls.

Conservative by design: when a complaint's discriminators are missing or
don't match any rule, classification falls through to that complaint's
`default`, which always routes to a level no less urgent than the complaint's
safest non-self-care option and sets `uncertainty=True`. Under-triage is the
dangerous error this engine must never make on missing data.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from triage.findings import ClinicalFindings

_RULES_PATH = Path(__file__).parent / "rules" / "set_mapping.yaml"


class CareChannel(str, Enum):
    SELF_CARE = "self-care"
    PRIMARY_CARE = "primary-care appointment"
    URGENT_CARE = "urgent care"
    EMERGENCY = "emergency/112"


class TriageResult(BaseModel):
    level: int
    care_channel: CareChannel
    rationale: str
    uncertainty: bool


def _load_mapping(path: Path = _RULES_PATH) -> dict[str, Any]:
    with path.open() as f:
        return yaml.safe_load(f)


_MAPPING = _load_mapping()


def _condition_matches(findings: ClinicalFindings, field: str, expected: Any) -> bool:
    value = getattr(findings, field, None)
    if isinstance(value, Enum):
        value = value.value

    if isinstance(expected, dict):
        if value is None:
            return False
        if "min" in expected and value < expected["min"]:
            return False
        if "max" in expected and value > expected["max"]:
            return False
        return True

    return value == expected


def _rule_matches(findings: ClinicalFindings, conditions: dict[str, Any]) -> bool:
    return all(
        _condition_matches(findings, field, expected)
        for field, expected in conditions.items()
    )


def _care_channel_for_level(level: int, mapping: dict[str, Any]) -> CareChannel:
    return CareChannel(mapping["care_channel_by_level"][level])


def classify(
    findings: ClinicalFindings, mapping: dict[str, Any] | None = None
) -> TriageResult:
    """Map structured findings onto a SET level. Pure: no I/O, no LLM."""
    mapping = _MAPPING if mapping is None else mapping
    complaint = mapping["complaints"][findings.presenting_complaint.value]

    for rule in complaint["rules"]:
        if _rule_matches(findings, rule["conditions"]):
            return TriageResult(
                level=rule["level"],
                care_channel=_care_channel_for_level(rule["level"], mapping),
                rationale=rule["rationale"].strip(),
                uncertainty=False,
            )

    default = complaint["default"]
    return TriageResult(
        level=default["level"],
        care_channel=_care_channel_for_level(default["level"], mapping),
        rationale=default["rationale"].strip(),
        uncertainty=True,
    )
