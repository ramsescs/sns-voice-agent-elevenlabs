# SNS Voice Agent — ElevenLabs

Workspace for a **voice agent** that performs **triage** and **post-contact follow-up** for
patients of the Spanish public health system (SNS), built on the **ElevenLabs Agents
Platform**.

The agent runs on ElevenLabs (which owns speech-to-text, the LLM, turn-taking, and
text-to-speech). This repository holds the work *around* the hosted agent:

- **Documentation** of the agent and its configuration (`docs/`).
- **Plans** for building it out (`docs/` — start at [`docs/ROADMAP.md`](docs/ROADMAP.md)).
- The **deterministic clinical-safety tools** the agent calls over HTTP (`src/triage/`).

## Design invariant

The LLM never assigns the triage level. A separate deterministic layer maps structured
findings to a SET level and care channel, and a red-flag detector can force emergency
escalation (112). See [`CLAUDE.md`](CLAUDE.md) for the full architecture and conventions.

## The safety tool server

`src/triage/` is the deterministic safety layer, exposed as two HTTP webhook tools the
ElevenLabs agent calls:

- `POST /tools/red_flag_check` — emergency red-flag check that can force a 112 escalation.
- `POST /tools/triage_set` — SET-level + care-channel assignment.

Both take a `ClinicalFindings` body (`presenting_complaint` required, everything else
optional) and return the deterministic result verbatim. The clinical rule content
(`src/triage/rules/`) is currently a **labelled placeholder**, not sourced from the real SET
tables — see [`src/triage/rules/MAPPING.md`](src/triage/rules/MAPPING.md).

### Run and test

No application config is needed to run the tools (the ElevenLabs platform owns the LLM). An
unrelated `triage` package may shadow this one, so set `PYTHONPATH=src` when running the
server directly.

```bash
# 1. Run the test suite (8 HTTP-level tests, no ElevenLabs account needed)
pytest

# 2. Run the server locally
PYTHONPATH=src uvicorn triage.toolserver:app --reload

# 3. Exercise it — the invariant in action: missing data fails UPWARD
curl -s localhost:8000/health
curl -s -X POST localhost:8000/tools/red_flag_check \
  -H 'Content-Type: application/json' \
  -d '{"presenting_complaint":"chest_pain","chest_pain_radiating":true}'   # fires -> 112
curl -s -X POST localhost:8000/tools/triage_set \
  -H 'Content-Type: application/json' \
  -d '{"presenting_complaint":"chest_pain"}'   # no discriminators -> level 3, uncertainty:true
```

The hosted agent's configuration (system prompt, tools, tests) lives under
[`docs/elevenlabs/`](docs/elevenlabs/).

## Reference material

- [`docs/ROADMAP.md`](docs/ROADMAP.md) — the single prioritised "what to do next" guide.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system architecture and technology stack.
- [`docs/ELEVENLABS_OPTION_B_PLAN.md`](docs/ELEVENLABS_OPTION_B_PLAN.md) — the proposed first
  ElevenLabs iteration.
- [`docs/IMPLEMENTED_SOLUTION.md`](docs/IMPLEMENTED_SOLUTION.md) — architecture of the earlier
  text-only MVP whose safety layer we reuse.
- `mvp-sns-voice-agent/` — the earlier text MVP, kept locally as **read-only reference**
  (gitignored, not part of this project).

## Status

The deterministic tool server is built and tested (`pytest` green); the ElevenLabs agent
(iteration 1, English, mocked→real tools) is live and passing its agent-testing suite. Next
steps — securing/hosting the endpoint, native analytics, real SET rules — are tracked in
[`docs/ROADMAP.md`](docs/ROADMAP.md).
