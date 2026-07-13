"""HTTP webhook server tools for the ElevenLabs triage agent.

Two POST endpoints wrap the deterministic safety layer verbatim:

- ``POST /tools/red_flag_check`` -> ``redflag.check``
- ``POST /tools/triage_set``     -> ``set_engine.classify``

The request body of each is a ``ClinicalFindings`` object (the LLM <-> engine
contract; ``presenting_complaint`` required, every other field optional). The
JSON response is exactly the pure function's result, which the ElevenLabs agent
reads back into the conversation.

The endpoints hold the architectural invariant: they do no clinical reasoning
of their own, they only call the deterministic functions. Level assignment and
emergency escalation come from those functions, never from this layer or the
model.

Run locally:

    uvicorn triage.toolserver:app --reload

and expose it to the ElevenLabs cloud with a tunnel (see
``docs/elevenlabs/tools/README.md``).
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI

from triage.findings import ClinicalFindings
from triage.redflag import RedFlagResult, check
from triage.set_engine import TriageResult, classify

app = FastAPI(
    title="SNS triage safety tools",
    description=(
        "Deterministic red-flag and SET-level tools called by the ElevenLabs "
        "triage agent. The LLM never assigns the level; these do."
    ),
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/tools/red_flag_check")
def red_flag_check(findings: ClinicalFindings) -> dict:
    """Deterministic emergency check. Returns the ``RedFlagResult`` as JSON.

    A ``fired: true`` result is the agent's cue to escalate to 112 and end the
    call. ``RedFlagResult`` is a frozen dataclass, so it is serialized with
    ``dataclasses.asdict`` (not ``model_dump``).
    """
    result: RedFlagResult = check(findings)
    return asdict(result)


@app.post("/tools/triage_set")
def triage_set(findings: ClinicalFindings) -> dict:
    """Deterministic SET classification. Returns the ``TriageResult`` as JSON.

    The agent reports ``level`` and ``care_channel`` to the caller exactly as
    returned. Incomplete/ambiguous findings fall through to the engine's
    conservative default (over-triage, ``uncertainty: true``), never a silent
    under-triage.
    """
    result: TriageResult = classify(findings)
    return result.model_dump(mode="json")
