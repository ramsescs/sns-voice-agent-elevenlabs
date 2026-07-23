# Tool: `triage_set`

Deterministic SET-level assignment. Maps the gathered findings to a triage level (1–5) and a care
channel. The agent calls this once it has gathered enough discriminators, and reports the result
exactly as returned.

## Dashboard configuration

| Field | Value |
|-------|-------|
| Tool type | Webhook (server tool) |
| Name | `triage_set` |
| Tool ID | `tool_1101kx6c44v2e9p911cfx4r2rywk` |
| Method | `POST` |
| URL | `https://sns-triage-tools-3144072753.europe-west1.run.app/tools/triage_set` (Cloud Run, stable) |
| Headers | `X-Tool-Secret: <TOOL_WEBHOOK_SECRET>` (value in local `.env`) |
| Auth | shared webhook secret via the header above (server returns 401 without it) |
| Description (for the LLM) | "Deterministic triage classifier. Call once enough discriminators are gathered. Returns the SET priority level and care channel. Report `level` and `care_channel` to the caller exactly as returned; never assign or change the level yourself." |

## Request body

The [`ClinicalFindings`](./clinical-findings.schema.json) object. `presenting_complaint` required;
all other fields optional and omittable. Configure the webhook body parameters to match that
schema exactly.

## Response

```json
{
  "level": 4,
  "care_channel": "primary-care appointment",
  "rationale": "string explaining the assignment",
  "uncertainty": false
}
```

| Field | Type | Notes |
|-------|------|-------|
| `level` | integer 1–5 | SET priority level. |
| `care_channel` | string enum | Verbatim: `self-care`, `primary-care appointment`, `urgent care`, `emergency/112`. |
| `rationale` | string | Why this level was assigned. |
| `uncertainty` | boolean | `true` when the engine fell through to a conservative default (over-triage). |

Level → channel mapping (real engine): `1,2 → emergency/112`, `3 → urgent care`,
`4 → primary-care appointment`, `5 → self-care`.

## Implementation

Backed by the real deterministic function `set_engine.classify` in
[`src/triage/set_engine.py`](../../../src/triage/set_engine.py) (rules: `rules/set_mapping.yaml`),
served by [`src/triage/toolserver.py`](../../../src/triage/toolserver.py). No longer mocked.

## Example real responses

- **Mild fever, low pain** (input `{"presenting_complaint":"fever","pain_score":2}`):
  ```json
  { "level": 5, "care_channel": "self-care", "rationale": "Fever with a low associated pain score and no red-flag discriminators is appropriate for self-care.", "uncertainty": false }
  ```
- **Chest pain, no discriminators** — conservative default, over-triages upward with `uncertainty: true`
  (input `{"presenting_complaint":"chest_pain"}`):
  ```json
  { "level": 3, "care_channel": "urgent care", "rationale": "Chest pain with missing discriminator data defaults to an urgent care evaluation under the conservative over-triage policy.", "uncertainty": true }
  ```
