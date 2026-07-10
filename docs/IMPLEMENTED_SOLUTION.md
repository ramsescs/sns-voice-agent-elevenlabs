# Implemented Solution — Text-First SNS Triage Agent (First Prototype)

> **Purpose of this document.** This is a self-contained description of the first
> working prototype of the triage system, written to be lifted into the thesis as the
> initial, realised proposal of the solution: the **text-only** variant that owns its
> orchestration and does **not** depend on the ElevenLabs Agents Platform. It documents
> what has actually been built (not what is planned), the design decisions behind it and
> their rationale, how it maps onto the thesis objectives and commitments, how it is
> verified, and — explicitly — where it currently falls short.
>
> It corresponds to the platform-agnostic architecture of `thesis-proposals/core-proposal.md`
> minus the voice (STT/TTS) layer, and is the fallback path contemplated in
> `thesis-proposals/platform-decision.md` while the ElevenLabs credit grant remains pending.

---

## 1. Overview

The prototype implements the core clinical-safety architecture of the thesis as a small
Python package (`src/triage/`). A patient conducts a **text** interview; a Large Language
Model (Google Gemini) runs the conversation and extracts **structured clinical findings**;
and a **separate, deterministic layer** — not the LLM — performs the two safety-critical
functions: an emergency **red-flag bypass** and the assignment of a **triage level and care
channel**.

This realises the thesis's non-negotiable architectural invariant
(`core-proposal.md` §4.1): **the LLM never assigns the triage level.** The conversational
model only ever emits a validated findings object; every prioritisation decision is made by
auditable, testable, deterministic Python driven by open, versioned rule files.

The prototype is deliberately **text-first**. This is a constraint-respecting choice, not
merely a convenience: it keeps the work on the components the project owns regardless of the
eventual voice platform (the findings contract, the red-flag detector, the SET engine, the
dialogue manager and the orchestrator), and it avoids prematurely committing to an STT/TTS
vendor while the platform decision is still open. Voice becomes a thin adapter added later at
a single, well-identified seam (the CLI's `input()`/`print()`).

---

## 2. Scope

**In scope (built):** the triage flow end-to-end in text — greeting and AI disclosure,
LLM-driven structured interview, deterministic red-flag escalation, deterministic SET-level
and care-channel assignment with a conservative treatment of missing data, and an
open/versioned specification of the safety rules.

**Deferred (not built in this prototype), with seams left in place:**

- the post-contact **follow-up** module;
- **voice** (STT/TTS) and telephony;
- **co-official languages** and intra-call code-switching;
- **accessibility** handling for atypical and older-adult speech (an STT-layer concern);
- a **persisted audit trail** (currently a stub — see §8);
- sourcing of the **real SET discriminator tables** (the mapping is a labelled placeholder).

---

## 3. Architecture

```
                     ┌──────────────────────────────────────────────┐
   Patient (text) ──▶│  CLI  (input()/print()  ← STT/TTS seam)        │
                     └───────────────┬──────────────────────────────┘
                                     │ user utterance
                          ┌──────────▼───────────────┐
                          │  DialogueManager (Gemini) │  conversational intelligence
                          │  update_findings / finalize│  (LLM-mediated)
                          └──────────┬───────────────┘
                                     │ ClinicalFindings  (never a level)
                          ┌──────────▼───────────────┐
                          │  Orchestrator             │  deterministic control flow
                          └───┬───────────────────┬───┘
              every update ▼                       ▼ on finalize
                 ┌────────────────────┐   ┌────────────────────────┐
                 │  redflag.check()   │   │  set_engine.classify()  │  deterministic,
                 │  (bypass → 112)    │   │  → level + care channel │  rule-driven,
                 └────────────────────┘   └────────────────────────┘  auditable
                       rules/red_flags.yaml     rules/set_mapping.yaml
```

The dividing line runs between **conversational intelligence** (the Gemini dialogue manager,
LLM-mediated) and the **clinical-safety layer** (`redflag` and `set_engine`, pure
deterministic functions). The orchestrator owns control flow in ordinary Python, which is
what makes the red-flag bypass a genuine, server-side interrupt rather than something the
model is trusted to invoke.

---

## 4. Components as built

All modules live in `src/triage/`.

### 4.1 `findings.py` — the LLM ↔ engine contract
A Pydantic model, `ClinicalFindings`, is the **only** thing the dialogue layer may emit, and
it deliberately has **no triage-level field**. `presenting_complaint` (an enum of five:
chest pain, breathing difficulty, fever, abdominal pain, wound) is required; every clinical
discriminator is `Optional` and defaults to `None`, so a partial interview is representable
and the engine can distinguish "not yet asked" (`None`) from a recorded negative. Fields:
`pain_score` (0–10), `bleeding`, `consciousness`, `breathing_difficulty` (each an enum),
`chest_pain`, `chest_pain_radiating`, `stroke_signs_fast`, `allergic_reaction_severe`,
`suicidal_ideation` (booleans), and `onset` (free text).

### 4.2 `redflag.py` — deterministic emergency bypass
`check(findings) -> RedFlagResult` is a **pure function** over the structured findings
(no LLM, no I/O beyond a cached YAML load), driven by `rules/red_flags.yaml`. Five rules are
implemented: chest pain radiating to arm/jaw; FAST stroke signs; severe breathing
difficulty; severe allergic reaction (anaphylaxis); and suicidal ideation. A hit returns an
unambiguous escalate-to-112 outcome with a human-readable rationale and the **rules-file
version** that produced it. Rules fire only on definite positive evidence, keeping this layer
high-precision; the conservative handling of *missing* data lives in the SET engine.

### 4.3 `set_engine.py` — deterministic SET mapping
`classify(findings) -> TriageResult` maps findings onto a SET level (1–5), a care channel,
a rationale, and an `uncertainty` flag, driven by `rules/set_mapping.yaml`. The mapping is
structured as **one discriminator table per presenting complaint**, evaluated top-down with
**first match wins**, mirroring SET's flowchart-per-complaint shape. The level→channel map is
fixed: **levels 1–2 → emergency/112, 3 → urgent care, 4 → primary-care appointment,
5 → self-care**. When no rule matches (the discriminators needed to place the complaint in a
band are absent or ambiguous), classification falls through to the complaint's **conservative
`default`**, which routes to a level no less urgent than that complaint's safest non-self-care
band and sets `uncertainty=True`. Incomplete interviews therefore fail **upward**
(over-triage), never downward — under-triage being the error the system must not make.

### 4.4 `dialogue.py` — Gemini conversation layer
`DialogueManager` wraps a `google-genai` client (default model `gemini-2.5-flash`) and drives
the interview through two function-calling tools: `update_findings` (partial, incremental) and
`finalize`. A strict system prompt forbids the model from diagnosing, prescribing, naming a
medication, stating how serious the situation is, or producing any level or care
recommendation, and instructs it to ask one short discriminator question at a time. Each
`update_findings` payload is **merged into the accumulated findings and re-validated**; an
invalid payload is rejected and reported back to the model **without corrupting** previously
confirmed findings — a small but important robustness property.

### 4.5 `orchestrator.py` — deterministic control loop
Emits an **AI-disclosure greeting** at the start of the call (an EU AI Act Art. 50
transparency obligation) that also tells the patient to call 112 directly for a
life-threatening emergency. Then, each turn: pass the utterance to the dialogue manager; if
findings were updated, run `redflag.check` immediately — a hit ends the call with an
escalation message (the bypass); on `finalize`, run `set_engine.classify` and return the
level, channel and rationale, flagging conservative uncertainty when present.

### 4.6 `cli.py` — text entrypoint
A thin `python -m triage.cli` REPL over the orchestrator using `input()`/`print()`. It reads
`GEMINI_API_KEY` (or `GOOGLE_API_KEY`) from the environment/`.env`. This is precisely the seam
a voice STT/TTS adapter will replace; the orchestrator and safety layer are unchanged by that
substitution.

---

## 5. The open, versioned safety specification

All safety logic is expressed in human-readable, versioned rule files, not buried in Python —
directly serving the "open, reproducible safety specification" commitment.

- `rules/red_flags.yaml` — the five red-flag rules, each a flat map of findings field →
  required value, first match wins; carries a `version` string.
- `rules/set_mapping.yaml` — the per-complaint discriminator tables, the conservative
  defaults, and the level→channel map; carries a `version` string.
- `rules/MAPPING.md` — a one-page human-readable spec and, critically, a **provenance note**.

**Placeholder disclosure (must be preserved in the thesis).** The SET mapping is a
deliberately simplified placeholder authored from engineering judgement, loosely informed by
publicly described SET/Manchester-style severity bands. It is **not** derived from the real,
accredited SET discriminator tables, which have not yet been sourced (thesis objective O1).
Its output must not be presented as "SET-grounded" in any clinical, regulatory, or evaluation
context beyond demonstrating the architecture. Both `set_mapping.yaml` and `MAPPING.md` label
this explicitly. Replacing the placeholder with real tables changes only the rule content,
not the engine interface.

---

## 6. Key design decisions and rationale

These are the decisions that shaped the prototype and are the substance of the design chapter.

| Decision | Choice made | Rationale |
|---|---|---|
| **Modality** | Text-first; voice deferred to a single CLI seam | Keeps work on project-owned components; avoids premature STT/TTS vendor lock-in while the platform decision is open. |
| **Orchestration** | Server-side deterministic Python owns control flow | Makes the red-flag bypass a genuine interrupt, not a tool the model must be trusted to call. |
| **LLM role** | Extraction only, via constrained function calling; never a level | Realises the §4.1 invariant; confines the non-deterministic component to a validated, structured output. |
| **Red-flag detector** | Findings-based, pure function over the structured schema | Fully deterministic and unit-testable. The bypass is honestly scoped as **post-extraction**: its inputs are LLM-mediated, so extraction quality bounds its real-world recall (see §9). |
| **Missing-data policy** | Conservative default → over-triage + `uncertainty=True` | Under-triage is the dangerous failure; incomplete interviews must fail upward. |
| **Findings representation** | Tri-state (`None` = not yet established) | Lets the engine distinguish "unasked" from "denied", which the conservative policy depends on. |
| **SET mapping shape** | Per-complaint discriminator tables, first match wins | Mirrors SET's own flowchart-per-complaint structure; keeps each table small and auditable. |
| **Safety spec format** | Open, versioned YAML + Markdown provenance | Independently rebuildable; every decision records the rules version in effect. |

---

## 7. Mapping to thesis objectives and commitments

| Objective / commitment | Status in this prototype |
|---|---|
| **O2** Modular architecture, safety layer separate from LLM | **Done** — the separation is the backbone of the code. |
| **O3** Triage module: structured intake → SET level + channel + red-flag detection | **Done (text, placeholder mapping)**. |
| **O5** Open, reproducible safety spec + per-interaction rationale | **Partial** — rules and rationales are open and versioned; the **persisted audit trail is not yet implemented** (§8). |
| Commitment #1 **SET-grounding** | **Architecturally in place, clinically placeholder** — mapping labelled as not-yet-SET-sourced (O1 outstanding). |
| Commitment #2 **Open safety spec** | **Substantially met** for the rules; completed once the audit artefact lands. |
| **O1** Real SET grounding · **O4** Follow-up · **O6** Stratified evaluation · **O7** Accessibility · **O8** Co-official languages | **Deferred** — seams left open (see §10). |

---

## 8. Verification and current test status

The deterministic core is fully testable **without** the LLM — the point of the separation.

- **68 deterministic tests pass** (`pytest --ignore=tests/test_dialogue_live.py`): the
  findings schema (including a test asserting no level field exists on the model), every
  red-flag rule and a red-flag scenario suite, the SET vignette set (`tests/vignettes.yaml`)
  and the conservative-default behaviour, and the orchestrator's bypass and classification
  paths (using a scripted fake dialogue).
- The dialogue layer is unit-tested with a **mocked** Gemini client, so tool-call handling,
  incremental merging, and rejection-without-corruption are covered deterministically.
- The `tests/vignettes.yaml` set is **not throwaway**: it is the seed of the thesis's
  stratified under-triage benchmark (O6).

**The end-to-end conversational path is not currently demonstrated.** The live Gemini smoke
tests (`tests/test_dialogue_live.py`) skip automatically when no API key is present; with a
key present they currently **fail on HTTP 429 (quota exceeded)** on the free tier — an
infrastructure/billing limit, not a code defect. As a consequence, **at the time of writing
there is no live evidence that the full loop (Gemini extraction → red-flag bypass / SET
classification) behaves as intended**; only the deterministic core is verified. The intended
behaviour — a "chest pain radiating to the arm" utterance escalating to 112 once the model
extracts the radiating finding, and a mild complaint yielding a primary-care/self-care
recommendation — must be re-run and confirmed against a **billed key or a raised quota**
before any claim is made about live conversational behaviour in the thesis.

---

## 9. Honest limitations of the current prototype

State these plainly in the thesis; they are the difference between the realised prototype and
the full proposal.

1. **Language.** The system prompt and the AI-disclosure greeting are currently written in
   **English**. The intended target is **Spanish** (with co-official languages later);
   localising the patient-facing strings is outstanding work. The deterministic core is
   language-agnostic and unaffected.
2. **No persisted audit trail yet.** `audit.py` is a stub and the orchestrator carries
   `TODO` hooks where audit records should be written. The rationale and rules-version data
   already flow through the result objects, but nothing is written to disk. Completing this is
   required to fully satisfy O5 / commitment #2.
3. **Red-flag recall is bounded by extraction.** Because the bypass reads the *structured*
   findings, a red flag only fires if the LLM extracted the corresponding field. The bypass is
   deterministic and 100%-recall **on the rules**, but its end-to-end recall depends on the
   (non-deterministic, currently untested-in-CI) extraction step. This must be measured as a
   separate "extraction recall" number, not conflated with the deterministic guarantee.
4. **Placeholder SET mapping.** As in §5 — architecture-demonstrating only, not clinically
   authoritative.
5. **Coarse uncertainty semantics.** `uncertainty=True` fires when *no rule matches at all*,
   not per-discriminator; a partial finding that already lands in a band is scored as certain.
   Per-discriminator required-ness is out of scope for the placeholder mapping.
6. **No stratification fields captured.** Patient age and language are not yet recorded on the
   findings/audit, so the stratified benchmark (O6) has no data hooks in the prototype yet.

> **Repository housekeeping (not thesis-facing).** Separately from the limitations above,
> before the code is released as an artefact: remove the `DEBUG` print in the orchestrator,
> commit the pending local changes to `dialogue.py`, add an open licence, and add a CI
> workflow that runs the test suite (the existing `.github/workflows/` files are the Claude
> PR-assistant workflows, not a test runner). These are engineering to-dos, not intellectual
> limitations of the design.

---

## 10. Future work and the seams left open

- **Voice** — replace the CLI's `input()`/`print()` with an STT/TTS adapter; orchestrator and
  safety layer are untouched. ASR confidence then becomes an input to the deterministic layer,
  the natural insertion point for accessibility handling (O7).
- **Follow-up module** — reuses the orchestrator pattern and the (forthcoming) audit log.
- **Spanish + co-official languages** — the core is language-agnostic; work concentrates at
  the dialogue/STT layer (O8).
- **Real SET tables** — swap the placeholder rule content; the engine interface is stable (O1).
- **Audit artefact** — implement `audit.py` to persist a per-interaction JSON record
  (transcript, findings updates, red-flag result, final level/channel/rationale, model id and
  rules versions), completing the open, reproducible safety trail (O5).
- **Platform** — if the ElevenLabs credit grant is approved, the same safety layer is reused
  as server-side tools per `thesis-proposals/platform-options/elevenlabs.md`; otherwise this
  text-first, self-orchestrated variant is the basis to extend.

---

*Generated from the state of `src/triage/`, `tests/`, and `src/triage/rules/` at the time of
writing. English is used to match the existing thesis-proposal documents; translate as needed
for the final memoria.*
