"""Deterministic clinical-safety layer for the SNS triage agent.

Copied and adapted from the text-only MVP (`mvp-sns-voice-agent/src/triage/`),
which is reference-only and outside this repo. The pure functions
`redflag.check` and `set_engine.classify`, driven by the open, versioned YAML
rules in `rules/`, are the deterministic core; `toolserver` exposes them as the
HTTP webhook server tools the ElevenLabs agent calls.

The architectural invariant: the LLM never assigns the triage level. Level
assignment lives behind `set_engine.classify`; emergency escalation behind
`redflag.check`. Neither is a decision the conversational model is trusted to
make.
"""
