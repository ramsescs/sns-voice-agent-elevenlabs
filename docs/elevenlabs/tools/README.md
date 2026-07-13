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

## Implementation status — now backed by the real deterministic server

These tools are **no longer fake.** They are implemented in this repo at
[`src/triage/toolserver.py`](../../../src/triage/toolserver.py), a FastAPI app whose two POST
endpoints wrap the deterministic safety layer verbatim:

- `POST /tools/red_flag_check` → `redflag.check` (copied from the MVP into
  [`src/triage/redflag.py`](../../../src/triage/redflag.py) + `rules/red_flags.yaml`)
- `POST /tools/triage_set` → `set_engine.classify` (copied into
  [`src/triage/set_engine.py`](../../../src/triage/set_engine.py) + `rules/set_mapping.yaml`)

The input contract is unchanged (`clinical-findings.schema.json`), so the schemas registered on
the ElevenLabs tools still match. Covered by `tests/test_toolserver.py` (run `pytest`).

### Running it

```bash
uvicorn triage.toolserver:app --reload          # serves on http://127.0.0.1:8000
```

To let the ElevenLabs cloud reach it, expose the local port over a public HTTPS tunnel, e.g.:

```bash
cloudflared tunnel --url http://localhost:8000  # prints an https://<random>.trycloudflare.com URL
```

### Fake → real switch (what changes on the platform)

The **only** change on the ElevenLabs side is each tool's URL: replace the `https://example.com/...`
placeholder with `<public-base>/tools/red_flag_check` and `<public-base>/tools/triage_set`. No
schema or prompt changes. A `trycloudflare.com` quick-tunnel URL is **ephemeral** — it changes
every run, so re-point the tools (or use a named/stable tunnel or a deployment) for anything beyond
a one-off test.
