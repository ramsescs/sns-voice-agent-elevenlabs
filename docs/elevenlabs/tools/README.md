# Tools

The agent has **two webhook (server) tools**. Both take the same request body — the
[`ClinicalFindings`](./clinical-findings.schema.json) contract — and return different results.

| Tool | Purpose | Response |
|------|---------|----------|
| [`red_flag_check`](./red_flag_check.md) | Deterministic emergency check; can force a 112 escalation. | `{ fired, rule_id, rationale, rules_version }` |
| [`triage_set`](./triage_set.md) | Deterministic SET level + care channel assignment. | `{ level, care_channel, rationale, uncertainty }` |

## Why these schemas matter

The **input and output schemas here are the real, intended-final contract** — they mirror the MVP
`ClinicalFindings`, `RedFlagResult`, and `TriageResult`. Getting them exact now is the whole
point of this iteration: when we later build the deterministic Python server, we only redeploy
and change the URL. Nothing about the schemas or the prompt changes.

Key contract rules:

- `presenting_complaint` is the **only required** input field.
- Every other field is **optional and omittable**. Absent = "not asked", which is *not* the same
  as a negative (`"none"` / `false`). The agent must omit fields it has not established, never
  guess a negative.
- Enum string values are **verbatim** — including the `care_channel` values that contain spaces
  and slashes: `self-care`, `primary-care appointment`, `urgent care`, `emergency/112`.

## How they are "fake" this iteration

Each tool is registered on the agent as a `POST` webhook with a **placeholder URL**
(`https://TBD.invalid/tools/...`). The URL is never actually called: we exercise the tools using
ElevenLabs' **native tool mocking** in Agent Testing (`tool_mock_config` with
`MockingStrategy: all`). The canned mock responses live in each tool's file and in
[`../testing/scenarios.md`](../testing/scenarios.md).

## Fake → real (later slice)

1. Build the FastAPI server wrapping `redflag.check` / `set_engine.classify` (copied from the MVP
   per the repo's copy-not-import rule).
2. Deploy it (or tunnel it) to a public HTTPS URL.
3. Replace each tool's placeholder URL with the real endpoint. Done — schemas unchanged.
