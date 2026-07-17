# Roadmap — what to do next, in order

*Written 2026-07-17. This is the single prioritized "what do I do next" guide. It ties
together `ELEVENLABS_OPTION_B_PLAN.md` (slices B0–B4), `PLATFORM_NEXT_STEPS.md` (§0–§5),
and `THESIS_HARDENING_PLAN.md` into one ordered sequence. Each step is small, has a clear
"done when", and should be its own branch/PR.*

## Where you are today

| Done | Not done |
|---|---|
| B0 agent exists on ElevenLabs (English, gemini-2.5-flash) | B3 audit trail (`audit.py` — no decision is persisted anywhere) |
| B1 deterministic tool server + 8 passing pytest tests | Webhook auth (endpoint is open to anyone who finds the URL) |
| B2 tools wired to the real server via cloudflared tunnel | Stable hosting (tunnel URL rotates every restart) |
| 12/12 agent-testing suite green (v2 prompt) | Real SET rule content (current rules are labelled placeholders) |
| Evaluation case study written up | Spanish / co-official languages, accessibility benchmark |

---

## Step 1 — Land the current branch (½ day)

You're on `feat/triage-tool-server` with untracked files and a stale README. Close this
unit of work before opening a new one.

1. Fix the README's stale "no application code yet" status line.
2. Commit the untracked docs (`docs/PLATFORM_NEXT_STEPS.md`, `docs/references/` PDFs) —
   either on this branch if they belong to it, or a separate `docs/` branch.
3. Run the B2 acceptance: one scripted live call against the real tunnel, following the
   checklist in `docs/elevenlabs/testing/test-suite.md`; note the result in the changelog.
4. Open the PR. (Merging is your call.)

**Done when:** PR open, working tree clean, `pytest` green.

## Step 2 — Secure the webhook endpoint (½–1 day) · `PLATFORM_NEXT_STEPS §0a`

Right now anyone with the tunnel URL can call your tools. Minimal fix, no new infra:

1. Add a shared-secret header check to both `POST /tools/*` routes (FastAPI dependency
   reading e.g. `X-Tool-Secret`, value from an env var; 401 otherwise).
2. Set the same secret as a workspace secret header on both tools in the ElevenLabs
   dashboard.
3. Add tests: request without/with wrong secret → 401; correct secret → existing behavior.

**Done when:** unauthenticated curl fails, live agent call still works, tests cover it.

## Step 3 — Audit trail, slice B3 (1 day) · `PLATFORM_NEXT_STEPS §0b`

This is the highest-value missing piece for the thesis: commitment O2 (open, reproducible
safety spec) requires a **persisted audit trail**, and today no decision is recorded.

1. Copy `audit.py` from `mvp-sns-voice-agent/src/triage/` and adapt (copy, never import).
2. On every `/tools/*` call, append one JSONL record: timestamp, endpoint, raw
   `ClinicalFindings` payload, full result, `rules_version`, and the ElevenLabs
   `conversation_id` if the platform passes one.
3. Keep it MVP: append-only JSONL file, path from env var. Defer databases.
4. Tests: a tool call produces exactly one well-formed record.

**Done when:** you can replay any decision from the log alone (input + rules version →
same output).

## Step 4 — Stable hosting (½ day) · `PLATFORM_NEXT_STEPS §0a`

The ephemeral tunnel means re-PATCHing tool URLs every restart — friction that will make
you stop testing. Cheapest durable options, pick one:

- **Named Cloudflare tunnel** (free, keeps your laptop as host, stable hostname), or
- a small PaaS (Render/Fly free tier) with a `Dockerfile` — better for demo-day, since it
  doesn't depend on your laptop being awake.

**Done when:** the tool URLs in the agent config have not changed across a server restart.

## Step 5 — Platform-side invariant enforcement (1–2 days) · `PLATFORM_NEXT_STEPS §2, then §1`

Now make the platform *verify* on every real call what your test suite verifies offline
(defense-in-depth — never the decision itself):

1. **Success Evaluation criteria** on the agent: "agent never states a triage level not
   returned by `triage_set`", "agent never gives diagnosis/medication", etc.
2. **Data Collection**: extract the level the agent *communicated*; cross-check offline
   against the tool's *actual* output from your audit log (Step 3 makes this possible —
   this is the extraction-fidelity oracle).
3. Then the **custom Guardrail** in blocking mode (`retry` → transfer-to-human, never
   `end_call`).

**Done when:** a deliberately-broken prompt (agent invents a level) is flagged by the
platform evaluation, and the cross-check script catches a mismatch end-to-end.

## Step 6 — Real SET rule content, objective O1 (2–4 days) · `PLATFORM_NEXT_STEPS §4`

You already collected the sources (`docs/references/*.pdf` — SET implementation manual
2015, SEMES 2016, etc.). Replace the *content* of `rules/*.yaml` with discriminators
grounded in those documents — the interface (`classify()`, `check()`, `ClinicalFindings`)
stays fixed.

1. For each of the ~5 placeholder complaints, extract real discriminators from the PDFs
   into `set_mapping.yaml` / `red_flags.yaml`; bump `rules_version`.
2. Update `MAPPING.md` with per-rule provenance (document + page). Keep the honest
   disclosure about what remains approximated (the accredited web_e-PAT tables are
   commercial and not public).
3. Grow `ClinicalFindings` only as the new discriminators demand (contract v2).
4. Extend tests for each new/changed rule, always including the fail-upward case.

**Done when:** every rule in the YAML cites a public source in `MAPPING.md`, tests green.

## Step 7 — Broaden the adversarial + accessibility test suite (ongoing) · `PLATFORM_NEXT_STEPS §3`

Grow the 12-scenario suite: multi-turn red-team personas (user insists on a diagnosis,
user downplays symptoms), and first accessibility probes (hesitant/fragmented answers must
route toward escalation, never silent under-triage). This directly feeds thesis
commitments 3 and 4.

## Step 8 — Spanish, then a co-official language (after 1–7)

Currently English-only. Switch the agent to Spanish (prompt + language setting + re-run
the suite translated), then add one co-official language (catalán is the best-resourced)
and test intra-call code-switching. Thesis commitment 5. Don't start this before the
safety/audit steps — a multilingual agent without an audit trail proves nothing.

---

## Deferred (mention in the thesis, don't build now)

- Database-backed audit storage, dashboards.
- Server-side red-flag re-check inside `triage_set` (hardening-plan item — cheap, can ride
  along with Step 3 if trivial).
- Synthetic-caller benchmark at scale; latency/cost measurement (old B4 remainder).
- HMAC-signed webhooks / mTLS (shared secret is enough for the thesis prototype).

## Rules of thumb while executing

- One branch per step, PR when the "done when" passes.
- Never let convenience collapse the invariant: the LLM gathers findings and calls tools;
  `classify()`/`check()` decide. Ambiguity fails upward.
- Every rules change bumps `rules_version` and lands in `MAPPING.md` with provenance.
