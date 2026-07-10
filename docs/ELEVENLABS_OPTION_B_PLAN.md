# Plan: Build Option B — vanilla ElevenLabs Agent, in demoable slices

## Context

The project is pivoting to the ElevenLabs Agents Platform now that platform access is
granted. **Option B** is the fastest variant: ElevenLabs owns STT, turn-taking, the LLM,
and TTS; the project owns **only** the deterministic SET engine and red-flag check,
exposed as **HTTP webhook server tools** the agent calls. The LLM decides *when* to call
those tools (safety-by-prompt), which is the deliberately weakest-but-fastest point on the
B→C→D control-flow spectrum — the right place to start to get a demo on screen quickly and
learn the platform before hardening.

**Goal:** a spoken triage agent you can demo in the ElevenLabs web test widget, in English,
built in small independently-demoable increments, then extended.

**Decisions locked in (from clarifying questions):**
- Demo surface: **web test widget now, telephony later.**
- Language: **English first**, switch to Spanish/multilingual in a later slice.

**Scope guardrails:**
- B is **purely additive**. It reuses the pure functions `set_engine.classify` and
  `redflag.check` and the `ClinicalFindings` contract, and does **not** modify
  `dialogue.py`, `orchestrator.py`, or `cli.py` — the existing Gemini path stays intact as
  the future Option-A comparison arm.
- The architectural invariant holds: the agent's LLM never assigns a SET level; the
  deterministic tool server does. Level assignment lives behind `classify()`; escalation
  behind `check()`.

## Reused building blocks (do not reimplement)

- `src/triage/findings.py` — `ClinicalFindings` (the tool payload schema, verbatim).
- `src/triage/set_engine.py` — `classify(findings) -> TriageResult{level, care_channel, rationale, uncertainty}`.
- `src/triage/redflag.py` — `check(findings) -> RedFlagResult{fired, rule_id, rationale, rules_version}`.
- `src/triage/dialogue.py` — `SYSTEM_PROMPT` and `GREETING` (in `orchestrator.py`) are the
  starting text to adapt for the agent's prompt / first message.
- `tests/red_flag_suite.yaml`, `tests/vignettes.yaml` — scenario seeds for eval slices.
- `src/triage/audit.py` — stub to be implemented in slice B3.

---

## Slice B0 — Talking agent skeleton (no project tools) ⟶ day-one demo

**Goal:** a voice conversation you can show today, zero code.

**Build (in the ElevenLabs dashboard):**
- Create an agent; select a built-in LLM (recommend a fast Gemini/GPT model — billed from
  the granted ElevenLabs credits, which is the whole point of moving off the Gemini free tier).
- System prompt: adapt `dialogue.SYSTEM_PROMPT` (triage interviewer; one short question at a
  time; **never** state a diagnosis, medication, urgency, or level).
- First message: adapt `orchestrator.GREETING` (AI-disclosure per EU AI Act Art. 50).
- English voice.
- Record the exact config in a new `docs/elevenlabs/agent-config.md` (prompt, model, voice,
  version) so the setup is reproducible — supports thesis commitment #2.

**Demo / acceptance:** open the dashboard "Test AI agent" widget, hold a spoken conversation;
the agent discloses it's an AI, asks discriminator questions, and never states a level.

**Independently testable:** yes — no repo code, no server. Pure dashboard.

**Issue/branch:** `issues/007-eleven-agent-skeleton.md` → `feat/007-eleven-agent-skeleton`
(commits only the config-record doc).

---

## Slice B1 — Deterministic tool server (local, HTTP-tested, not yet wired)

**Goal:** the two safety tools reachable over HTTP, fully testable without ElevenLabs.

**Build:**
- Add `fastapi` and `uvicorn[standard]` to `pyproject.toml` dependencies.
- New `src/triage/toolserver.py` — a FastAPI app with two POST endpoints:
  - `POST /tools/red_flag_check` — body = `ClinicalFindings` fields → `redflag.check()` →
    JSON `{fired, rule_id, rationale}`.
  - `POST /tools/triage_set` — body = `ClinicalFindings` fields → `set_engine.classify()` →
    JSON `{level, care_channel, rationale, uncertainty}`.
  - Each builds `ClinicalFindings(**payload)` and calls the pure function verbatim. On a
    Pydantic `ValidationError`, return a structured error the agent can act on
    (conservative: missing/invalid discriminators already route upward via the engines'
    defaults — preserve that, never swallow into a non-urgent answer).
- Response shapes must match the JSON an ElevenLabs server tool reads back into the LLM.

**Demo / acceptance:** `uvicorn triage.toolserver:app`, then `curl` (or new
`tests/test_toolserver.py`): a chest-pain-radiating payload → `fired=true`; a mild-fever
payload → the expected SET level and care channel.

**Independently testable:** yes — pure Python + HTTP, no ElevenLabs account needed. Run with `pytest`.

**Issue/branch:** `issues/008-tool-server.md` → `feat/008-tool-server`.

---

## Slice B2 — Wire tools into the agent (this is the real Option B) ⟶ headline demo

**Goal:** end-to-end spoken triage where the agent calls the deterministic tools.

**Build:**
- Expose the local tool server to ElevenLabs' cloud via a tunnel (ngrok or cloudflared);
  document the command in `docs/elevenlabs/agent-config.md`.
- Register two **webhook server tools** on the agent pointing at the tunnel URLs, with
  parameter schemas mirroring the `ClinicalFindings` fields (`presenting_complaint` required;
  the rest optional).
- Extend the system prompt: call `red_flag_check` whenever a new finding is learned; call
  `triage_set` once enough discriminators are gathered; on `fired=true`, deliver the 112
  escalation and end the call; otherwise report the returned level + care channel.

**Demo / acceptance:** two spoken calls in the widget — (a) a mild case → correct SET level +
care channel; (b) "crushing chest pain spreading down my arm" → agent calls `red_flag_check`,
gets `fired=true`, escalates to 112. Tool-server logs show both calls with correct payloads.

**Independently testable:** the tool server is already covered by B1's tests; B2 adds a
manual scripted-call checklist (documented in the issue).

**Issue/branch:** `issues/009-wire-agent-tools.md` → `feat/009-wire-agent-tools`.

---

## Slice B3 — Audit trail (implement the `audit.py` stub)

**Goal:** every safety decision is logged and reproducible (thesis commitment #2; the
explainability/audit-log eval metric).

**Build:**
- Implement `src/triage/audit.py`: append-only JSON records
  `{timestamp, tool, findings_received, result, rules_version}`.
- `toolserver.py` writes one record per tool call; reuse the `rules_version` already carried
  by `RedFlagResult`.

**Demo / acceptance:** run a call, then show the audit log with one record per tool call,
each including `rules_version` and the human-readable rationale.

**Independently testable:** yes — assert records are written in `tests/test_toolserver.py` /
a new `tests/test_audit.py`.

**Issue/branch:** `issues/010-tool-audit-log.md` → `feat/010-tool-audit-log`.

---

## Slice B4 — Observability + red-flag eval (the "easy visibility" goal)

**Goal:** begin operationalizing the O5 safety-tool-reliability metric using platform features.

**Build:**
- Configure dashboard **evaluation criteria** (e.g. "did the agent escalate on red-flag
  input?").
- Seed simulated conversations from `tests/red_flag_suite.yaml`; run them via the platform's
  agent testing / simulation.
- Use the analytics dashboard for latency, cost, and per-criterion pass/fail.

**Demo / acceptance:** dashboard shows the red-flag suite results and latency/cost per call.

**Independently testable:** partially — the seed scenarios are local YAML; the run is on the
platform. Document results in `docs/elevenlabs/eval-results.md`.

**Issue/branch:** `issues/011-agent-observability-eval.md` → `feat/011-agent-observability-eval`.

---

## Fast-path summary

- **Today's demo:** B0 (talks) → then B1 + B2 (tools wired) is the real Option B.
- **Then add on:** B3 (audit), B4 (observability/eval). Telephony and Spanish/multilingual
  are later slices on top of this base.

## Git workflow (per CLAUDE.md)

One issue file + one branch per slice; stage files explicitly by name (never `git add -A`);
open a PR once each slice's acceptance criteria pass; merge, then start the next. New slices
continue the existing numbering at **007–011**.

## Verification

- **B1 / B3:** `pytest tests/test_toolserver.py tests/test_audit.py` — deterministic, offline.
- **Whole engine still green:** `pytest` (existing suite must stay passing; B is additive).
- **B0 / B2:** manual spoken calls in the ElevenLabs test widget per each slice's acceptance
  checklist; confirm tool-server logs and (B3) audit records.
- **B4:** red-flag suite run visible in the dashboard; results recorded under `docs/elevenlabs/`.

## Follow-up (not in this plan)

Once B is demoable, fold the platform decision into `thesis-proposals/platform-decision.md`
(flip status to decided) and rewrite `thesis-proposals/platform-options/elevenlabs.md` around
the B→C→D re-design. Separate task; ask before doing.
