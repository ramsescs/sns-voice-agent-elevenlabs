# ElevenLabs agent — configuration record

This folder is the **version-controlled source of truth** for our agent on the
[ElevenLabs Agents Platform](https://elevenlabs.io/docs/agents-platform). The agent itself is
built and hosted in the ElevenLabs dashboard; these files record *exactly* how it is configured
so the setup is reproducible and auditable (a thesis requirement).

## Current iteration: **mocked (fake) tools**

The goal of this first iteration is to validate three things **before** writing any backend code:

1. The agent exists and talks on the platform (ElevenLabs owns STT, turn-taking, LLM, TTS).
2. The tool-calling loop works — the agent decides *when* to call `red_flag_check` and
   `triage_set` and reads their results back.
3. The **architectural invariant** holds end-to-end: the LLM only gathers findings and calls
   tools; it **never** states a diagnosis, medication, urgency, or SET level itself. The level
   and any 112 escalation come from the *tool response*, not the model.

We do this with **fake tools** using ElevenLabs' **native tool mocking** (Agent Testing /
Simulate Conversations, `tool_mock_config`). There is **no tool endpoint, no tunnel, and no
application code** in this repo yet — only the config/documentation here.

Scope this iteration: **English only**. Spanish + co-official languages are deferred.

## Files

| File | What it is |
|------|------------|
| `agent-config.md` | Canonical snapshot of the agent's dashboard settings (name, LLM, voice, language, first message, version). |
| `system-prompt.md` | The full English system prompt pasted into the agent. |
| `tools/README.md` | The two tools, how they are mocked, and the fake→real swap plan. |
| `tools/clinical-findings.schema.json` | The shared tool **input** contract (must match the real `ClinicalFindings`). |
| `tools/red_flag_check.md` | `red_flag_check` tool definition + response shape + mock responses. |
| `tools/triage_set.md` | `triage_set` tool definition + response shape + mock responses. |
| `testing/scenarios.md` | The Agent Testing scenarios, `tool_mock_config`, and recorded results. |

## The fake→real path

The **two tool JSON schemas are the real deliverable** of this iteration and are intended to be
final. When the deterministic Python safety layer is built later (FastAPI wrapping
`redflag.check` / `set_engine.classify`), switching from fake to real is only:

1. deploy the real tool server, and
2. replace each tool's placeholder URL with the deployed endpoint.

No schema changes, no prompt changes.
