"""The LLM <-> deterministic-engine contract.

`ClinicalFindings` is the only thing the dialogue layer is allowed to emit.
It deliberately has no triage-level / SET-level field: level assignment is
the deterministic engine's job, never the LLM's.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PresentingComplaint(str, Enum):
    CHEST_PAIN = "chest_pain"
    BREATHING_DIFFICULTY = "breathing_difficulty"
    FEVER = "fever"
    ABDOMINAL_PAIN = "abdominal_pain"
    WOUND = "wound"


class BleedingSeverity(str, Enum):
    NONE = "none"
    MINOR = "minor"
    SEVERE = "severe"


class ConsciousnessLevel(str, Enum):
    ALERT = "alert"
    DROWSY = "drowsy"
    UNRESPONSIVE = "unresponsive"


class BreathingDifficultySeverity(str, Enum):
    NONE = "none"
    MILD = "mild"
    SEVERE = "severe"


class ClinicalFindings(BaseModel):
    """Structured findings extracted from the patient interview.

    Every field besides `presenting_complaint` is optional so a partial
    interview (the interview was interrupted, or the LLM hasn't asked a
    given discriminator question yet) is representable.
    """

    presenting_complaint: PresentingComplaint
    pain_score: Optional[int] = Field(default=None, ge=0, le=10)
    bleeding: Optional[BleedingSeverity] = None
    consciousness: Optional[ConsciousnessLevel] = None
    breathing_difficulty: Optional[BreathingDifficultySeverity] = None
    chest_pain: Optional[bool] = None
    chest_pain_radiating: Optional[bool] = None
    stroke_signs_fast: Optional[bool] = None
    allergic_reaction_severe: Optional[bool] = None
    suicidal_ideation: Optional[bool] = None
    onset: Optional[str] = None
