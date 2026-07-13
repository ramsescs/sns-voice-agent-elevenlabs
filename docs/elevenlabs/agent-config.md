# Agent configuration snapshot

> Canonical record of the agent's ElevenLabs dashboard settings. Update this file whenever the
> agent is changed in the dashboard. Fill the `TBD` values in once the agent is created.

## Identity

| Setting | Value |
|---------|-------|
| Agent name | `SNS Triage Agent (mock tools)` |
| Iteration | Mocked (fake) tools — iteration 1 |
| Config version | `2026-07-12-v2` |
| Language | English (`en`) — single language this iteration |
| ElevenLabs agent ID | `agent_8001kx6c62v2fx9a395vzb5gwkat` |
| Created via | ElevenLabs API (`POST /v1/convai/agents/create`) on 2026-07-10 |

## Model & voice

| Setting | Value |
|---------|-------|
| LLM | `gemini-2.5-flash` (fast, billed from ElevenLabs credits) |
| Voice | `21m00Tcm4TlvDq8ikWAM` (Rachel, English) |
| TTS model | `eleven_flash_v2` |
| STT / turn-taking | Platform defaults (owned by ElevenLabs) |

## Prompts

- **System prompt:** see [`system-prompt.md`](./system-prompt.md) — paste it verbatim into the
  agent's *System prompt* field.
- **First message (AI-disclosure greeting):**

  ```
  Hello, this is an automated AI assistant from the public health service. I am not a
  human and I cannot make medical decisions — I only ask a few questions and a separate
  system decides how to prioritise your case. This is not for life-threatening emergencies:
  if this is an emergency, hang up and call 112. To start, what is the main problem you are
  calling about today?
  ```

## Tools attached

| Tool | Type | Tool ID | Defined in |
|------|------|---------|-----------|
| `red_flag_check` | Webhook (server), `POST` | `tool_4201kx6c44kaeqkrw0jtf2p4cz74` | [`tools/red_flag_check.md`](./tools/red_flag_check.md) |
| `triage_set` | Webhook (server), `POST` | `tool_1101kx6c44v2e9p911cfx4r2rywk` | [`tools/triage_set.md`](./tools/triage_set.md) |

Both are now backed by the **real deterministic tool server** at
[`src/triage/toolserver.py`](../../src/triage/toolserver.py) (see [`tools/README.md`](./tools/README.md)).

> **Live URL is a cloudflared quick tunnel — ephemeral.** The two tools' `api_schema.url` currently
> point at `https://<random>.trycloudflare.com/tools/...`. That URL is valid only while both the
> local `uvicorn` server **and** the `cloudflared` tunnel are running; it changes on every tunnel
> restart. Re-point the tools (PATCH `api_schema.url`) after any restart, or move to a stable host.
> The tools are exercised for real once the tunnel is up; the earlier mocked path (`tool_mock_config`)
> is still available for offline agent tests.

## Change log

| Date | Change |
|------|--------|
| 2026-07-10 | Initial mock-tools iteration config drafted. |
| 2026-07-12 | `v2`: system prompt amended after test HP-4 failed — added the rule that `presenting_complaint` alone sets no other field; established findings (incl. the main complaint) must also be sent in their own field. Pushed live via `PATCH /v1/convai/agents/{id}` and verified. See `testing/test-suite.md`. |
| 2026-07-13 | Real tool server built (`src/triage/toolserver.py`, FastAPI wrapping the copied `redflag.check` / `set_engine.classify`; `pytest` 8/8 green). Both tools switched from the `example.com` placeholder to a live cloudflared quick tunnel via `PATCH /v1/convai/tools/{id}`, verified reachable. URL is ephemeral — see note above. |
