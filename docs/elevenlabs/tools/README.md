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

### Deployment (production path)

Deployed on **Google Cloud Run** from the repo's [`Dockerfile`](../../../Dockerfile)
(project `tfg-ai-voice-agent-sns`, region `europe-west1` — a Tier-1 pricing region so the
free tier applies; scale-to-zero, ~2–3s cold start, inside the 20s webhook timeout):

```bash
gcloud run deploy sns-triage-tools \
  --source . --region europe-west1 --allow-unauthenticated \
  --set-env-vars "TOOL_WEBHOOK_SECRET=$TOOL_WEBHOOK_SECRET"   # value in .env (gitignored)
```

Stable base URL: `https://sns-triage-tools-3144072753.europe-west1.run.app`. Redeploys are the
same command; the URL does not change.

**Auth:** `/tools/*` requires the `X-Tool-Secret` header matching the service's
`TOOL_WEBHOOK_SECRET` env var (401 otherwise; `/health` stays open). Both ElevenLabs tools carry
the header in their `api_schema.request_headers`. `--allow-unauthenticated` refers only to Google
IAM (ElevenLabs cannot present Google credentials); the secret header is the access control.

### Running locally (development)

```bash
uvicorn triage.toolserver:app --reload          # http://127.0.0.1:8000, auth off unless
                                                # TOOL_WEBHOOK_SECRET is exported
```

For a quick end-to-end test against the hosted agent without deploying, a cloudflared tunnel
(`cloudflared tunnel --url http://localhost:8000`) still works — but its URL is ephemeral, so
re-point the ElevenLabs tools back to the Cloud Run URL afterwards.
