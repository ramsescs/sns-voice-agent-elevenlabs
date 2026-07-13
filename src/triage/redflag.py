"""Deterministic red-flag bypass.

`check()` is a pure function over `ClinicalFindings`: no I/O beyond the
module-level YAML rules load, no LLM. A hit forces an unambiguous
emergency/112 outcome with a human-readable rationale, and carries the
rules version so the audit log (slice 004) can record which version of
the rules produced the decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml

from triage.findings import ClinicalFindings

_RULES_PATH = Path(__file__).parent / "rules" / "red_flags.yaml"


@dataclass(frozen=True)
class RedFlagResult:
    fired: bool
    rule_id: Optional[str]
    rationale: Optional[str]
    rules_version: str


@dataclass(frozen=True)
class _Rule:
    id: str
    conditions: dict[str, Any]
    rationale: str


@dataclass(frozen=True)
class _RuleSet:
    version: str
    rules: tuple[_Rule, ...]


@lru_cache(maxsize=None)
def _load_rules(rules_path: Path = _RULES_PATH) -> _RuleSet:
    raw = yaml.safe_load(rules_path.read_text())
    rules = tuple(
        _Rule(
            id=rule["id"],
            conditions=rule["conditions"],
            rationale=rule["rationale"].strip(),
        )
        for rule in raw["rules"]
    )
    return _RuleSet(version=str(raw["version"]), rules=rules)


def _matches(findings: ClinicalFindings, conditions: dict[str, Any]) -> bool:
    for field, expected in conditions.items():
        if getattr(findings, field, None) != expected:
            return False
    return True


def check(findings: ClinicalFindings, rules_path: Path = _RULES_PATH) -> RedFlagResult:
    """Evaluate `findings` against the red-flag rules. Pure, no I/O beyond
    the (cached) YAML load, no LLM call."""
    rule_set = _load_rules(rules_path)
    for rule in rule_set.rules:
        if _matches(findings, rule.conditions):
            return RedFlagResult(
                fired=True,
                rule_id=rule.id,
                rationale=rule.rationale,
                rules_version=rule_set.version,
            )
    return RedFlagResult(
        fired=False,
        rule_id=None,
        rationale=None,
        rules_version=rule_set.version,
    )
