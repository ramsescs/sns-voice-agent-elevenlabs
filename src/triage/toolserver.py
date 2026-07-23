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

Authentication: when the ``TOOL_WEBHOOK_SECRET`` environment variable is set
(as it is in the deployed service), every ``/tools/*`` request must carry it in
an ``X-Tool-Secret`` header; the ElevenLabs tools are configured to send it.
When unset (local development), the endpoints are open. ``/health`` is always
open.

Run locally:

    uvicorn triage.toolserver:app --reload

Deployed on Google Cloud Run (see ``Dockerfile`` and
``docs/elevenlabs/tools/README.md``).
"""

from __future__ import annotations

import os
import secrets
from dataclasses import asdict
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException

from triage.findings import ClinicalFindings
from triage.redflag import RedFlagResult, check
from triage.set_engine import TriageResult, classify


def require_tool_secret(
    x_tool_secret: Annotated[str | None, Header()] = None,
) -> None:
    """Reject the request unless it carries the shared webhook secret.

    Enforced only when ``TOOL_WEBHOOK_SECRET`` is set, so local development
    and the offline test suite need no credentials. Comparison is
    constant-time.
    """
    expected = os.environ.get("TOOL_WEBHOOK_SECRET")
    if expected and not secrets.compare_digest(x_tool_secret or "", expected):
        raise HTTPException(status_code=401, detail="invalid or missing tool secret")


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


@app.post("/tools/red_flag_check", dependencies=[Depends(require_tool_secret)])
def red_flag_check(findings: ClinicalFindings) -> dict:
    """Deterministic emergency check. Returns the ``RedFlagResult`` as JSON.

    A ``fired: true`` result is the agent's cue to escalate to 112 and end the
    call. ``RedFlagResult`` is a frozen dataclass, so it is serialized with
    ``dataclasses.asdict`` (not ``model_dump``).
    """
    result: RedFlagResult = check(findings)
    return asdict(result)


@app.post("/tools/triage_set", dependencies=[Depends(require_tool_secret)])
def triage_set(findings: ClinicalFindings) -> dict:
    """Deterministic SET classification. Returns the ``TriageResult`` as JSON.

    The agent reports ``level`` and ``care_channel`` to the caller exactly as
    returned. Incomplete/ambiguous findings fall through to the engine's
    conservative default (over-triage, ``uncertainty: true``), never a silent
    under-triage.
    """
    result: TriageResult = classify(findings)
    return result.model_dump(mode="json")
