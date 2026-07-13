# SET mapping spec — `set_mapping.yaml`

## ⚠️ Placeholder mapping — not SET-sourced

**This mapping is a deliberately simplified placeholder. It is *not* derived
from the real Sistema Español de Triaje (SET) discriminator tables.** SET is
an accredited (and possibly proprietary) clinical standard; the actual
discriminator tables have not yet been sourced for this project (see thesis
objective O1, "SET sourcing"). Until that sourcing happens, do not present
this mapping's level/rationale output as SET-grounded in any clinical,
regulatory, or thesis-evaluation context beyond demonstrating the
architecture. Replace this file's rule content — not the engine interface —
once real SET tables are available.

## Provenance

- **Source:** authored by project engineering judgment for the MVP, loosely
  informed by publicly described SET/Manchester-style severity bands (pain
  score, bleeding severity, consciousness, breathing difficulty). No
  licensed SET documentation was consulted.
- **Version:** tracked by the `version` field at the top of
  `set_mapping.yaml`; bump it on every content change so audit records
  (`issues/004`) stay reproducible against the rules in effect at decision
  time.
- **Scope:** 5 presenting complaints — chest pain, breathing difficulty,
  fever, abdominal pain, wound.

## How the mapping works

Each presenting complaint has:

- an ordered `rules` list — the first rule whose `conditions` all match the
  patient's `ClinicalFindings` wins;
- a `default` — used when no rule matches, i.e. the findings needed to
  discriminate are missing or don't fit any defined band.

A rule's `conditions` is a flat map of `ClinicalFindings` field → expected
value. A scalar is an equality check; `{min: x, max: y}` is an inclusive
numeric range. All conditions in a rule must hold.

`care_channel_by_level` maps each of the 5 SET levels to one of the 4 care
channels (`self-care`, `primary-care appointment`, `urgent care`,
`emergency/112`) — levels 1 and 2 both route to emergency/112.

## Conservative-default invariant

Every complaint's `default` routes to a level **no less urgent than that
complaint's safest non-self-care band**, and the engine sets
`uncertainty=True` on the resulting `TriageResult`. This is intentional:
under-triage (sending someone with a dangerous condition to self-care) is
the error this system must never make on missing or ambiguous data, so
incomplete interviews fail upward, not downward.

`uncertainty=True` fires when **no rule matches at all** (i.e. the
discriminators needed to place the complaint in any defined band are
absent), not whenever any single discriminator field is unset. A partial
finding that already matches a band — e.g. chest pain with a pain score but
no `chest_pain_radiating` answer — is scored against that band and reported
as certain. Per-discriminator required-ness is out of scope for this
placeholder mapping.

## Changing this mapping

1. Edit `set_mapping.yaml`.
2. Bump `version`.
3. Update or add cases in `tests/vignettes.yaml` covering the change.
4. Run `pytest tests/test_set_engine.py`.
