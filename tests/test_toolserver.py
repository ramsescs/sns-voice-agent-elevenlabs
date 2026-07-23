"""HTTP-level tests for the safety tool server.

These exercise the two webhook endpoints exactly as the ElevenLabs agent will
call them: a JSON ``ClinicalFindings`` body in, the pure function's result as
JSON out. Pure Python + FastAPI TestClient, no ElevenLabs account needed.

    pytest
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from triage.toolserver import app

client = TestClient(app)


def test_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_red_flag_fires_on_radiating_chest_pain() -> None:
    resp = client.post(
        "/tools/red_flag_check",
        json={"presenting_complaint": "chest_pain", "chest_pain_radiating": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["fired"] is True
    assert body["rule_id"] == "chest_pain_radiating"
    assert body["rationale"]
    assert body["rules_version"]


def test_red_flag_does_not_fire_on_mild_fever() -> None:
    resp = client.post(
        "/tools/red_flag_check",
        json={"presenting_complaint": "fever", "pain_score": 2},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["fired"] is False
    assert body["rule_id"] is None
    assert body["rationale"] is None
    # rules_version is present even when nothing fires.
    assert body["rules_version"]


def test_triage_set_mild_fever_is_non_emergency() -> None:
    resp = client.post(
        "/tools/triage_set",
        json={"presenting_complaint": "fever", "pain_score": 2},
    )
    assert resp.status_code == 200
    body = resp.json()
    # fever with low pain -> self-care band (level 5), certain.
    assert body["level"] == 5
    assert body["care_channel"] == "self-care"
    assert body["uncertainty"] is False
    assert body["rationale"]


def test_triage_set_radiating_chest_pain_is_high_acuity() -> None:
    resp = client.post(
        "/tools/triage_set",
        json={"presenting_complaint": "chest_pain", "chest_pain_radiating": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["level"] == 2
    assert body["care_channel"] == "emergency/112"
    assert body["uncertainty"] is False


def test_triage_set_missing_discriminators_fail_upward() -> None:
    """Only the required complaint, no discriminators -> conservative default
    with uncertainty flagged. Must never silently under-triage."""
    resp = client.post(
        "/tools/triage_set",
        json={"presenting_complaint": "chest_pain"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["uncertainty"] is True
    assert body["level"] <= 3  # no less urgent than urgent care


def test_missing_presenting_complaint_is_rejected() -> None:
    """A malformed call (no required complaint) is a 422, not a silent
    non-urgent answer."""
    resp = client.post("/tools/triage_set", json={"pain_score": 5})
    assert resp.status_code == 422


def test_invalid_enum_value_is_rejected() -> None:
    resp = client.post(
        "/tools/red_flag_check",
        json={"presenting_complaint": "not_a_real_complaint"},
    )
    assert resp.status_code == 422


def test_secret_required_when_configured(monkeypatch) -> None:
    """With TOOL_WEBHOOK_SECRET set (as deployed), tool calls without the
    correct X-Tool-Secret header are rejected; /health stays open."""
    monkeypatch.setenv("TOOL_WEBHOOK_SECRET", "s3cret")
    payload = {"presenting_complaint": "fever"}

    missing = client.post("/tools/red_flag_check", json=payload)
    assert missing.status_code == 401

    wrong = client.post(
        "/tools/triage_set", json=payload, headers={"X-Tool-Secret": "nope"}
    )
    assert wrong.status_code == 401

    ok = client.post(
        "/tools/red_flag_check", json=payload, headers={"X-Tool-Secret": "s3cret"}
    )
    assert ok.status_code == 200

    assert client.get("/health").status_code == 200
