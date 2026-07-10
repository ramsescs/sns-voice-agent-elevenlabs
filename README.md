# SNS Voice Agent — ElevenLabs

Workspace for a **voice agent** that performs **triage** and **post-contact follow-up** for
patients of the Spanish public health system (SNS), built on the **ElevenLabs Agents
Platform**.

The agent runs on ElevenLabs (which owns speech-to-text, the LLM, turn-taking, and
text-to-speech). This repository holds the work *around* the hosted agent:

- **Documentation** of the agent and its configuration (`docs/`).
- **Plans** for building it out (`docs/`).
- The **deterministic clinical-safety tools** the agent calls over HTTP (to be built).

## Design invariant

The LLM never assigns the triage level. A separate deterministic layer maps structured
findings to a SET level and care channel, and a red-flag detector can force emergency
escalation (112). See [`CLAUDE.md`](CLAUDE.md) for the full architecture and conventions.

## Reference material

- [`docs/ELEVENLABS_OPTION_B_PLAN.md`](docs/ELEVENLABS_OPTION_B_PLAN.md) — the proposed first
  ElevenLabs iteration.
- [`docs/IMPLEMENTED_SOLUTION.md`](docs/IMPLEMENTED_SOLUTION.md) — architecture of the earlier
  text-only MVP whose safety layer we reuse.
- `mvp-sns-voice-agent/` — the earlier text MVP, kept locally as **read-only reference**
  (gitignored, not part of this project).

## Status

Documentation / scaffolding stage. No application code yet.
