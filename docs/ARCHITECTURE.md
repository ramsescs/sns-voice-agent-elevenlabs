# System Architecture and Technology Stack

*Triage and post-contact follow-up voice agent for the Spanish public health system (SNS),
built on the ElevenLabs Agents Platform with a deterministic clinical-safety layer.*

This document describes the system's architecture and every component of its technology stack:
what each component **is**, what **purpose** it serves here, and **how it works**. It is written to
be self-contained for inclusion in the thesis.

---

## 1. Overview

The system is a **voice agent** that conducts a spoken triage interview with a patient and returns a
prioritisation (a triage level and a recommended care channel). It is deliberately split into two
halves with very different trust properties:

- **A hosted conversational layer** (the ElevenLabs Agents Platform) that handles speech and natural
  language. This half is *probabilistic*: it uses a large language model (LLM) and speech models
  whose outputs cannot be guaranteed.
- **A deterministic clinical-safety layer** (a small server we own) that assigns the triage level and
  can force an emergency escalation. This half is *deterministic and auditable*: given the same
  structured findings, it always produces the same decision, from open and versioned rules.

The two halves communicate over HTTP through a narrow, typed contract. The conversational layer's
only job is to *gather structured findings* and *decide when to ask the safety layer*; it is never
permitted to assign a triage level itself.

### 1.1 The architectural invariant (the reason the stack is split this way)

> **The LLM never assigns the triage level.** A separate deterministic component maps structured
> clinical findings onto a triage level and care channel, and a red-flag detector can force emergency
> escalation (112) at any point.

This invariant is the foundation of the thesis's auditability and regulatory arguments (EU AI Act
high-risk classification, MDR software-as-a-medical-device, GDPR/LOPDGDD). Every technology choice
below is made to preserve it: the clinical decision is pushed out of the non-deterministic model and
into deterministic, version-controlled code whose every decision can be reproduced and explained.

---

## 2. Layered architecture

```
        ┌──────────────────────────────────────────────────────────────┐
        │                         PATIENT (voice)                        │
        └───────────────────────────────┬──────────────────────────────┘
                                         │  audio in / audio out
        ╔════════════════════════════════▼══════════════════════════════╗
        ║        ELEVENLABS AGENTS PLATFORM  (hosted, managed)           ║
        ║                                                                ║
        ║   STT  ──►  Turn-taking  ──►  LLM (dialogue)  ──►  TTS         ║
        ║                                   │                            ║
        ║                    decides WHEN to call a tool                 ║
        ╚═══════════════════════════════════│════════════════════════════╝
                                            │  HTTPS webhook (JSON)
                                            │  request body = ClinicalFindings
        ┌───────────────────────────────────▼────────────────────────────┐
        │            PUBLIC EXPOSURE  (cloudflared tunnel, dev)            │
        └───────────────────────────────────┬────────────────────────────┘
                                            │  forwards to localhost:8000
        ╔═══════════════════════════════════▼════════════════════════════╗
        ║              OUR SAFETY TOOL SERVER  (Python)                   ║
        ║                                                                ║
        ║   uvicorn  (ASGI server: listens, parses HTTP, runs the app)   ║
        ║      │                                                          ║
        ║   FastAPI  (routing + request/response)                         ║
        ║      │            ├── Pydantic  (validate JSON → ClinicalFindings)
        ║      ▼            │                                              ║
        ║   toolserver.py endpoints:                                      ║
        ║      • /tools/red_flag_check ─► redflag.check()   ┐             ║
        ║      • /tools/triage_set     ─► set_engine.classify() │ pure    ║
        ║                                   │                  │ funcs    ║
        ║                          PyYAML loads rules/*.yaml   ┘          ║
        ╚═══════════════════════════════════│════════════════════════════╝
                                            │  JSON result
                                            ▼
                       RedFlagResult  /  TriageResult
                    (returned to the LLM, reported to patient)
```

The boundary between the two coloured boxes is the **LLM ↔ engine contract**: a single typed object,
`ClinicalFindings`, travels down; a typed result travels back up. Nothing else crosses.

---

## 3. Component reference

### 3.A The hosted conversational platform

#### ElevenLabs Agents Platform
- **What it is.** A managed cloud platform for building real-time voice agents. It bundles the entire
  speech pipeline — speech-to-text, turn-taking, an LLM, and text-to-speech — behind a single hosted
  "agent" that we configure rather than run.
- **Purpose here.** It owns everything *around* the clinical decision: hearing the patient, managing
  the back-and-forth of conversation, running the language model, and speaking back. We use it so the
  thesis can focus on the safety layer rather than reimplementing a speech stack.
- **How it works.** We define an *agent* (a system prompt, a first message, a voice, an LLM choice,
  and a set of tools) via the platform's API. The platform hosts that agent and, at call time, runs
  the pipeline below turn by turn. Configuration for our agent is recorded in
  [`docs/elevenlabs/agent-config.md`](./elevenlabs/agent-config.md).

#### Speech-to-Text (STT / ASR)
- **What it is.** An automatic speech recognition model that transcribes the patient's audio into
  text.
- **Purpose here.** Converts spoken symptoms into text the LLM can read. Because ASR quality degrades
  on atypical and older-adult speech and on co-official languages, it is also a primary *accessibility*
  concern for the thesis: degradation must route toward escalation, never toward silent
  under-triage.
- **How it works.** The platform streams the caller's audio to the ASR model and emits incremental
  transcripts. We do not train or host this model; it is a platform-managed component.

#### Turn-taking
- **What it is.** The logic that decides when the patient has finished speaking and when the agent
  should respond (handling pauses, interruptions, and back-channels).
- **Purpose here.** Makes the conversation feel natural and prevents the agent from talking over the
  patient. It is entirely platform-owned.

#### The LLM (dialogue / conversational layer)
- **What it is.** A large language model (a configurable built-in model, e.g. a fast Gemini or GPT
  variant) that reads the running transcript and decides what to say or do next.
- **Purpose here.** It conducts the interview — asking one discriminator question at a time — and,
  crucially, **decides when to call our tools** and with what structured arguments. It is the *only*
  non-deterministic component in the decision path.
- **How it works.** The LLM is steered by a **system prompt** (see
  [`docs/elevenlabs/system-prompt.md`](./elevenlabs/system-prompt.md)) that forbids it from stating a
  diagnosis, medication, urgency, or triage level, and instructs it to gather findings and call the
  tools. When the model determines a tool is needed, the platform performs the corresponding webhook
  call. This "the model decides *when* to call a deterministic tool" pattern is the platform-native
  way to keep the clinical decision out of the model — sometimes called *safety-by-prompt*, and it is
  the deliberately weakest link that the deterministic layer exists to backstop.

#### Text-to-Speech (TTS)
- **What it is.** A speech synthesis model that turns the agent's text responses into audio.
- **Purpose here.** Speaks the agent's questions and the final prioritisation back to the patient.
  Platform-owned.

#### Webhook server tools
- **What they are.** The platform's mechanism for letting an agent call an external HTTP API during a
  conversation. Each tool has a name, a natural-language description (which tells the LLM *when* to use
  it), an HTTP method and URL, and a **parameter schema** describing the JSON body.
- **Purpose here.** They are the bridge from the conversational layer to our safety layer. We expose
  exactly two: `red_flag_check` and `triage_set`. Their definitions are recorded in
  [`docs/elevenlabs/tools/`](./elevenlabs/tools/).
- **How they work.** When the LLM calls a tool, the platform fills the parameter schema from the
  conversation (extracting, e.g., `presenting_complaint: "chest_pain"`), issues an HTTPS `POST` to the
  tool's URL, and feeds the JSON response *back into the LLM* as the tool result. The parameter schema
  is the ElevenLabs-side mirror of our `ClinicalFindings` contract (§4), which is what makes the
  fake→real transition a pure URL swap.

### 3.B The safety tool server (the code we own)

This is a small Python HTTP service that wraps the deterministic decision functions. It is the part of
the system the thesis actually *builds*; everything above it is configured, not coded.

#### Python (3.11+)
- **What it is.** The programming language and runtime for the server.
- **Purpose / why.** Chosen for its clinical/scientific ecosystem and, pragmatically, to allow the
  deterministic layer to be *copied and adapted* from the earlier text-only MVP rather than rewritten.
- **How it works.** All server code lives under [`src/triage/`](../src/triage/); dependencies and build
  configuration are declared in [`pyproject.toml`](../pyproject.toml) and installed into an isolated
  virtual environment (`.venv`).

#### FastAPI — the web application framework
- **What it is.** A modern Python framework for building HTTP APIs. It provides *routing* (mapping a
  URL + method to a function) and automatic *request/response handling*, and it integrates Pydantic for
  data validation. Under the hood it is built on Starlette (the ASGI toolkit) for the HTTP plumbing.
- **Purpose here.** It defines *what the server does*: it declares the two endpoints and the shape of
  their inputs and outputs. See [`src/triage/toolserver.py`](../src/triage/toolserver.py).
- **How it works.** We create an application object, `app = FastAPI(...)`, and decorate Python
  functions to bind them to routes, e.g. `@app.post("/tools/red_flag_check")`. FastAPI inspects each
  function's type hints: because a parameter is typed as `ClinicalFindings`, FastAPI automatically
  parses and validates the incoming JSON body into that object before the function runs, and returns a
  `422 Unprocessable Entity` if it does not conform. The function's return value (a dict) is serialised
  to a JSON response. **Important:** FastAPI is only *logic*. By itself it does not open a network port
  or listen for traffic — that is uvicorn's job.

#### uvicorn — the ASGI server
- **What it is.** An **ASGI** (Asynchronous Server Gateway Interface) server: the process that actually
  listens on a TCP port, speaks HTTP, and runs an async application. ASGI is the standard contract
  between a Python web server and an async web app.
- **Purpose here.** It is the **runtime that turns the FastAPI app into a live service**. Without
  uvicorn running, the endpoints exist only as inert Python objects and nothing can reach them — which
  is precisely why the tools go dead the moment uvicorn stops.
- **How it works.** We launch it with `uvicorn triage.toolserver:app`, which means "import the object
  `app` from the module `triage.toolserver` and serve it." uvicorn then:
  1. binds and **listens** on a port (e.g. `127.0.0.1:8000`);
  2. **accepts** incoming HTTP connections and **parses** raw bytes into a structured request
     (method, path, headers, body);
  3. **invokes** the FastAPI app through ASGI, passing the request;
  4. takes the app's return value and **writes** it back as a well-formed HTTP response;
  5. does all of this concurrently on an asynchronous event loop, so many calls can be served at once.
  The `INFO: ... "POST /tools/red_flag_check" 200 OK` lines in the server log are uvicorn reporting
  step 4. In development we add `--reload`, which makes uvicorn watch the source files and restart
  itself when they change.

#### Pydantic — data validation and the typed contract
- **What it is.** A Python library that defines data models as classes and validates/parses untrusted
  data (like incoming JSON) against them, coercing types and rejecting anything that does not fit.
- **Purpose here.** It *is* the LLM ↔ engine contract. `ClinicalFindings`
  ([`src/triage/findings.py`](../src/triage/findings.py)) is a Pydantic model, and it is the only thing
  the conversational layer is allowed to send. Pydantic guarantees that malformed or out-of-range input
  (e.g. an unknown complaint, a pain score above 10) is rejected at the door rather than silently
  producing a wrong triage decision.
- **How it works.** Each field is declared with a type and constraints (enums for categorical fields,
  `0–10` bounds for the pain score, optional/nullable for everything except the required presenting
  complaint). When FastAPI hands Pydantic the request body, Pydantic validates it into a
  `ClinicalFindings` instance or raises a validation error. The results, `TriageResult` and
  `RedFlagResult`, are likewise typed so their JSON shape is stable and self-documenting.

#### PyYAML — loading the open rule files
- **What it is.** A library for reading YAML files into Python data structures.
- **Purpose here.** It loads the **open, versioned safety rules** from disk so the decision logic is
  data-driven and independently inspectable, not buried in code.
- **How it works.** At import time, the engines read `rules/red_flags.yaml` and `rules/set_mapping.yaml`
  ([`src/triage/rules/`](../src/triage/rules/)) into dictionaries. Each file carries a `version` string
  that is returned with every decision, so an audit record can be tied to the exact rules in force at
  decision time.

#### The deterministic decision layer (the clinical core)
Three modules and their rule files form the auditable heart of the system. They are **pure functions**:
no network calls, no LLM, no hidden state — the same findings always yield the same result.

- **`findings.py` — the contract.** Defines `ClinicalFindings`: the structured symptom record. It
  deliberately has **no triage-level field** — encoding the invariant in the type system itself. Fields
  are tri-state (a value, or *absent* meaning "not yet asked", which is distinct from a recorded
  negative), so a partial interview is representable without inventing negatives.
- **`redflag.py` — `check(findings) → RedFlagResult`.** A high-precision emergency detector driven by
  `rules/red_flags.yaml`. It fires only on definite positive evidence (e.g. chest pain radiating to the
  arm, FAST stroke signs) and, when it fires, forces an emergency/112 outcome with a human-readable
  rationale. `RedFlagResult` carries `{fired, rule_id, rationale, rules_version}`.
- **`set_engine.py` — `classify(findings) → TriageResult`.** Maps findings onto a triage level via the
  discriminator tables in `rules/set_mapping.yaml` (first match wins). When discriminators are missing
  or ambiguous, it falls through to a **conservative default** that over-triages upward and flags
  `uncertainty=True` — incomplete input *fails upward*, never toward a silent under-triage.
  `TriageResult` carries `{level, care_channel, rationale, uncertainty}`.
- **`toolserver.py` — the thin HTTP wrapper.** Exposes the two pure functions as the `/tools/…`
  endpoints. It does **no clinical reasoning of its own**; it only validates input and calls the
  deterministic functions, preserving the invariant at the network edge.

### 3.C Connectivity and exposure

#### cloudflared (the tunnel) — development-time exposure
- **What it is.** A command-line client from Cloudflare that creates a secure **tunnel** from a public
  HTTPS URL to a service running on `localhost`, without opening firewall ports or deploying anything.
- **Purpose here.** The ElevenLabs cloud can only call a webhook at a *public* URL, but during
  development the tool server runs on the developer's laptop. cloudflared bridges that gap so the hosted
  agent can reach the local server.
- **How it works.** Running `cloudflared tunnel --url http://localhost:8000` prints a public
  `https://<random>.trycloudflare.com` address; requests to it are forwarded through Cloudflare's edge
  to the local uvicorn process. **This is a development convenience, not the production architecture:**
  the "quick tunnel" URL is *ephemeral* (it changes on every restart and dies when the process stops),
  so the ElevenLabs tool URLs must be re-pointed after each restart. A production deployment would
  replace this with a stable, authenticated hosted endpoint (see §7).

### 3.D Development and quality tooling

- **pyproject.toml + virtual environment** — declare dependencies and pin the project to Python 3.11+;
  the `.venv` isolates them from the system Python.
- **pytest** — the test framework. [`tests/test_toolserver.py`](../tests/test_toolserver.py) drives the
  two endpoints over HTTP (via FastAPI's test client) to assert, offline and without any ElevenLabs
  account, that red flags fire, mild cases route to self-care, missing discriminators fail upward, and
  malformed input is rejected with `422`.
- **ruff** — the linter/formatter that keeps the code style consistent and catches common errors.

---

## 4. The data contract (what crosses the boundary)

Only three typed objects ever cross the LLM ↔ engine boundary.

**Input — `ClinicalFindings`** (`presenting_complaint` required; every other field optional and
*omittable*, where absent means "not asked", not "no"):

| Field | Type | Notes |
|-------|------|-------|
| `presenting_complaint` | enum | `chest_pain \| breathing_difficulty \| fever \| abdominal_pain \| wound` — **required** |
| `pain_score` | int 0–10 | |
| `bleeding` | enum | `none \| minor \| severe` |
| `consciousness` | enum | `alert \| drowsy \| unresponsive` |
| `breathing_difficulty` | enum | `none \| mild \| severe` |
| `chest_pain`, `chest_pain_radiating` | bool | |
| `stroke_signs_fast`, `allergic_reaction_severe`, `suicidal_ideation` | bool | |
| `onset` | string | free text |

**Output — `RedFlagResult`**: `{ fired: bool, rule_id: string?, rationale: string?, rules_version: string }`

**Output — `TriageResult`**: `{ level: int 1–5, care_channel: enum, rationale: string, uncertainty: bool }`
where `care_channel ∈ { self-care, primary-care appointment, urgent care, emergency/112 }`.

Because these shapes are fixed and typed, the ElevenLabs tool schemas were designed against them up
front, so swapping a mock endpoint for the real server required no schema or prompt change.

---

## 5. Request lifecycle (end to end)

A single tool call, traced through the whole stack:

1. **Patient speaks** → the platform's **STT** transcribes the audio.
2. The **LLM** reads the transcript, updates its understanding, and decides a tool is needed. It
   composes a `ClinicalFindings` argument (e.g. `{presenting_complaint: "chest_pain",
   chest_pain: true, chest_pain_radiating: true}`).
3. The platform issues an **HTTPS `POST`** to the tool's webhook URL.
4. The request reaches the **cloudflared** edge and is forwarded to **`localhost:8000`**.
5. **uvicorn** accepts the connection, parses the HTTP request, and hands it to the FastAPI app.
6. **FastAPI + Pydantic** validate the JSON body into a `ClinicalFindings` object (rejecting it with
   `422` if malformed).
7. The endpoint calls the **deterministic function** — `redflag.check()` or `set_engine.classify()` —
   which consults the **YAML rules** and returns a typed result.
8. FastAPI serialises the result to JSON; **uvicorn** writes it back as an HTTP `200` response.
9. The platform feeds the JSON result **back into the LLM**, which then follows the system prompt:
   on `fired: true` it delivers the 112 escalation and ends the call; otherwise it reports the returned
   `level` and `care_channel` — *verbatim, never of its own invention* — via **TTS** to the patient.

Steps 1–3 and 9 are the ElevenLabs platform; step 4 is the tunnel; steps 5–8 are our server. The
clinical decision is made entirely in steps 6–7, in deterministic code.

---

## 6. How the stack enforces the thesis claims

- **SET-grounding & determinism.** The triage level comes only from `set_engine.classify()` over
  open discriminator tables — reproducible and inspectable, unlike a closed LLM judgement.
- **Open, reproducible safety specification.** The rules are plain, versioned YAML files; the decision
  functions are pure; anyone can rebuild and re-run them. Every result carries the `rules_version` used.
- **Conservative failure (no silent under-triage).** Missing or ambiguous findings fall through to a
  conservative over-triaging default with `uncertainty=True`, and the red-flag detector can bypass the
  interview at any point to force 112.
- **Auditability / regulatory posture.** Because the clinical decision is deterministic and separated
  from the model, each decision can be explained by the rule that produced it — the basis for the EU AI
  Act, MDR, and GDPR/LOPDGDD arguments.
- **Accessibility as a first-class concern.** STT/LLM degradation on atypical speech and co-official
  languages is contained by design: the model can only ever *under-report findings*, and under-reported
  findings route **upward** through the conservative defaults, not toward a dangerous under-triage.

---

## 7. Current limitations and honest disclosures

- **The SET mapping is a labelled placeholder.** `rules/set_mapping.yaml` is authored from engineering
  judgement loosely informed by publicly described severity bands; it is **not** derived from the real
  accredited *Sistema Español de Triaje* tables (see
  [`src/triage/rules/MAPPING.md`](../src/triage/rules/MAPPING.md)). Its interface is final; its clinical
  content is not yet SET-sourced.
- **Safety-by-prompt is the weakest link.** The LLM deciding *when* to call the tools is enforced only
  by the system prompt. The deterministic layer backstops the *decision*, but not the model's choice to
  invoke it; strengthening that control flow is future work.
- **Development-grade exposure.** The cloudflared quick tunnel is ephemeral and the tool server
  currently has **no authentication** — acceptable only under the project's synthetic-data-only policy.
  Production requires a stable hosted endpoint and a webhook secret between the platform and the server.
- **Scope of the current iteration.** English only; a single-language voice; telephony, co-official
  languages, intra-call code-switching, and the persisted audit trail are planned later slices.

---

## 8. Technology stack at a glance

| Layer | Component | Category | Role in this system |
|-------|-----------|----------|---------------------|
| Conversation | ElevenLabs Agents Platform | Managed voice-agent platform | Hosts the agent; owns the speech pipeline |
| Conversation | STT / ASR | Speech recognition model | Transcribes patient audio |
| Conversation | Turn-taking | Dialogue timing | Manages conversational turns |
| Conversation | LLM | Large language model | Interviews; decides *when* to call tools; never assigns a level |
| Conversation | TTS | Speech synthesis | Speaks the agent's responses |
| Interface | Webhook server tools | HTTP tool-calling | Bridge from the LLM to our safety layer |
| Exposure | cloudflared | Tunnel (dev) | Public HTTPS → local server |
| Server | Python 3.11+ | Language/runtime | Runs the safety layer |
| Server | uvicorn | ASGI server | Listens on a port; runs the app |
| Server | FastAPI | Web framework | Routing + request/response |
| Server | Pydantic | Data validation | The typed `ClinicalFindings` contract |
| Server | PyYAML | Config loader | Loads the open, versioned rules |
| Server | redflag / set_engine + rules | Deterministic decision logic | Assigns level; forces 112 |
| Tooling | pytest, ruff, pyproject/venv | Dev tooling | Tests, linting, dependencies |

---

*See also:* [`docs/elevenlabs/`](./elevenlabs/) for the concrete agent configuration and tool
definitions, and [`src/triage/`](../src/triage/) for the implementation.
