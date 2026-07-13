# Tool: `red_flag_check`

Deterministic emergency red-flag check. High-precision: fires only on definite positive evidence,
and any fire forces an emergency (112) escalation. The agent calls this whenever it learns a new
finding.

## Dashboard configuration

| Field | Value |
|-------|-------|
| Tool type | Webhook (server tool) |
| Name | `red_flag_check` |
| Tool ID | `tool_4201kx6c44kaeqkrw0jtf2p4cz74` |
| Method | `POST` |
| URL | `https://example.com/tools/red_flag_check` (placeholder — mocked this iteration; swap for the real endpoint later) |
| Headers | none |
| Auth | none |
| Description (for the LLM) | "Deterministic emergency check. Call whenever a new clinical finding is learned. Returns whether an emergency red flag has fired. If `fired` is true, escalate to 112 immediately and end the call." |

## Request body

The [`ClinicalFindings`](./clinical-findings.schema.json) object. `presenting_complaint` required;
all other fields optional and omittable. Configure the webhook body parameters to match that
schema exactly.

## Response

```json
{
  "fired": true,
  "rule_id": "chest_pain_radiating",
  "rationale": "string explaining the fired rule",
  "rules_version": "2025-06-22-v1"
}
```

| Field | Type | Notes |
|-------|------|-------|
| `fired` | boolean | Whether an emergency red flag fired. |
| `rule_id` | string \| null | The matching rule id when fired; `null` when not fired. |
| `rationale` | string \| null | Explanation when fired; `null` when not fired. |
| `rules_version` | string | Always present, even when not fired. |

Real rule ids (for reference): `chest_pain_radiating`, `stroke_signs_fast`,
`severe_breathing_difficulty`, `severe_allergic_reaction`, `suicidal_ideation`.

## Mock responses (this iteration)

- **Fired (emergency demo):**
  ```json
  { "fired": true, "rule_id": "chest_pain_radiating", "rationale": "mock", "rules_version": "mock-0" }
  ```
- **Not fired (normal path):**
  ```json
  { "fired": false, "rule_id": null, "rationale": null, "rules_version": "mock-0" }
  ```
