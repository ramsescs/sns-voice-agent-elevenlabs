# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A **voice agent** for **triage** and **post-contact follow-up** of patients in the Spanish
public health system (Sistema Nacional de Salud, SNS), built on the **ElevenLabs Agents
Platform**. The agent itself is configured and runs *on the ElevenLabs platform* (it owns
STT, turn-taking, the LLM, and TTS). **This repository is the primary workspace** and holds
everything *around* the hosted agent:

- **documentation** describing the agent and its configuration,
- **plans** for building it out, and
- the **tools** we develop and host for the agent to call (a deterministic clinical-safety
  layer, exposed over HTTP as webhook server tools).

It succeeds an earlier **text-only** MVP (Gemini + Python, no voice platform). That MVP is
**reference only** — see below.

## Repository layout and the MVP reference

- `docs/` — project documentation and plans (see "Reference documents" below).
- `mvp-sns-voice-agent/` — **the old text-agent MVP, kept locally as read-only reference.**
  It is **gitignored and not part of this project.** Do **not** import from it, depend on
  it, or modify it. When we need one of its building blocks, we **copy** the relevant file
  into this repo and adapt it here. Treat it as documentation of prior art, not as code we
  ship.

Application code (a `src/` tool server, `tests/`, `pyproject.toml`, etc.) does **not exist
yet** — this repo is currently at the documentation/scaffolding stage. Create that structure
when the first tool slice is actually built, not before.

## Reference documents (context, not binding specs)

Read these for background. They describe intent and prior art; they are **not** literal
build instructions, and their file paths/module names are **not** to be followed verbatim
(most were written against the old MVP's layout).

- `docs/ELEVENLABS_OPTION_B_PLAN.md` — the proposed first ElevenLabs iteration ("Option B":
  the platform owns STT/LLM/turn-taking/TTS; we own only the deterministic safety tools).
  Use it for the shape of the approach and the demo slices, not for exact paths.
- `docs/IMPLEMENTED_SOLUTION.md` — a self-contained write-up of the old text MVP's
  architecture and its honest limitations. This is the best explanation of the safety layer
  we will be reusing (findings contract, red-flag detector, SET engine).

## Architectural invariant (non-negotiable)

**The LLM / conversational layer never assigns the triage level.** A separate,
**deterministic** component maps structured clinical findings onto a SET level and care
channel, and a **red-flag detector** can force emergency escalation (112) at any point. On
the ElevenLabs platform this means:

- The agent's LLM only gathers findings and decides *when* to call our tools; it must never
  state a diagnosis, medication, urgency, or triage level itself.
- Level assignment lives behind a deterministic `classify()`; escalation behind a
  deterministic `check()`. These run in **our** tool server, not in the model.
- Incomplete/ambiguous input must fail **upward** (conservative over-triage), never toward a
  silent under-triage.

Preserving this separation is the basis for the thesis's auditability and regulatory claims
(EU AI Act high-risk, MDR SaMD, GDPR/LOPDGDD). Do not collapse it for convenience.

## The tools we own (to be built by copying from the MVP reference)

When building the safety tool server, copy these from `mvp-sns-voice-agent/src/triage/` and
adapt them here — do not reimplement from scratch and do not import across the gitignore
boundary:

- `findings.py` — `ClinicalFindings` (the Pydantic tool-payload contract; **no** level field).
- `set_engine.py` — `classify(findings) -> TriageResult{level, care_channel, rationale, uncertainty}`.
- `redflag.py` — `check(findings) -> RedFlagResult{fired, rule_id, rationale, rules_version}`.
- `rules/*.yaml` + `rules/MAPPING.md` — the open, versioned safety rules and their provenance.

These are wrapped as **HTTP webhook server tools** (intended stack: Python 3.11+, FastAPI +
uvicorn, pydantic) that the ElevenLabs agent calls. The SET mapping copied from the MVP is a
**labelled placeholder**, not sourced from the real accredited SET tables — preserve that
disclosure.

## Thesis commitments (inform every design decision)

1. **SET-grounding** — prioritisation anchored on the *Sistema Español de Triaje* (SET).
2. **Open, reproducible safety specification** — the deterministic layer is specified openly
   enough to be independently rebuilt (versioned rule files + a persisted audit trail).
3. **Under-triage benchmark stratified by accessibility** — under-triage rate always reported
   broken down by speech profile, age, and language, never only in aggregate.
4. **Accessibility for atypical and older-adult speech** — degradation must route toward
   escalation, never toward a silent misclassification.
5. **Co-official-language support** — Spanish plus at least one co-official language
   (catalán, euskera, gallego), including intra-call code-switching.

## Commands

There is no application code yet, so there is nothing to build/test in-repo today. When the
tool server exists, follow these conventions:

- **Tests:** run the bare `pytest` command (not `python3 -m pytest`) so the rtk Claude Code
  hook can recognise and compact the output.
- **Run the tool server:** `uvicorn <module>:app --reload` (module path set once it exists).
- **Lint/format:** `ruff format` + `ruff check --fix` — already wired as a `PostToolUse` hook
  in `.claude/settings.json`, so `.py` files are auto-formatted on Write/Edit.

## Git workflow

- One branch per unit of work (e.g. `feat/<slug>`); open a PR when its acceptance criteria
  pass. **Do not merge PRs — that is the user's call.**
- Stage files explicitly by name — never `git add -A`, `git add .`, or `git add -u`.
- Bias to the simplest MVP of what's asked; defer optional modules and mention them rather
  than building them. Write plans to markdown files in the repo; do not start implementing
  until told.

## Data policy

No real or identifiable patient data anywhere — only synthetic vignettes and public speech
corpora. No LLM API keys are needed by our tool server itself (the ElevenLabs platform owns
the model).
