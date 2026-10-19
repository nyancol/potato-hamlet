# Proposal

## Why

No shipped law stops part-way through. `mayor-quorum` ends its instances at polls close, `requisitions` ends its at a deadline or a withdrawal, and every finish in either law lands on a moment the calendar already named. So three framework guarantees have never been exercised by the law they were written for: a `ph:causedBy` relation between a State and a Process, a termination whose finish bound falls strictly inside a calendar span, and a calendar span minted at `apply` time for work scheduled after review. `law-framework` even names the untested case outright — "a candidate withdraws during polls and the election is stopped part-way through" — as the scenario for cancelled-process retention, and no artefact set can produce it.

A revocation flavour closes that gap with a single law-text clause: if a candidate revokes their candidacy during election day, the election is stopped and postponed, and the votes already cast are annulled. It is the first law whose halt is event-triggered rather than calendar-triggered, which is exactly the shape the generic-driver claim has not yet survived contact with.

## What Changes

- Add a new frozen artefact set `artefacts/mayor-revocation/`, branched from the mayor baseline: `law.txt` gains the revocation clause, and `ontology.ttl`, `population.ttl`, `rules.lean`, and `manifest.yaml` are authored for it and frozen, with its own compiled oracle.
- The ontology gains a `CandidacyWithdrawn` State, `RevokeCandidacy` / `StopElection` / `PostponeElection` Process classes in the declared `ph:hasPhase` hierarchy, and a `ph:causedBy` relation from the stopping process to the withdrawal state, stating the permitted dependency without evaluating it.
- `rules.lean` gains the revocation acts: the candidate's own withdrawal, the authority's halt, and the authority's postponement which mints the successor instance together with its calendar spans. The halt lands the instance's `Chronoid` finish bound inside the election-day span; the instance's outcome records that cast ballots do not count; the ballots themselves stay in the graph as labelled individuals.
- The manifest declares the new ECAs with holder roles, parameters, modalities, and messages, plus reading templates for the halt and postponement, so the unmodified TUI binary renders and plays the flavour with zero code change.
- A revocation trace test covers the full path — nominate, vote, revoke during polls, halt, successor scheduled — including that no act removes an individual and that the successor starts from a fresh registry.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None required. Every semantic this flavour exercises — `ph:causedBy` between a Process and a State with evaluation in the Lean guard, cancellation that retains individuals while recording non-count in the outcome, termination mid-span as an ordinary finish, runtime-minted calendar individuals dated only by Lean, ECAs declaring the Process class they create, and `pending` naming its process instance — is already in `law-framework` and `law-extraction`. This change is a new law satisfying those requirements without changing one, which is the point: the requirements do not need rewriting to accept a conforming law, and this flavour is the test that proves it.

## Impact

- **New:** `artefacts/mayor-revocation/` (`law.txt`, `ontology.ttl`, `population.ttl`, `rules.lean`, `manifest.yaml`, compiled `oracle`), frozen on completion.
- **New:** a revocation trace script (e.g. `scripts/test_revocation.py`) driving the withdraw-halt-postpone path and asserting retention, outcome, and successor shape.
- **Unchanged:** `artefacts/mayor-2027/`, `artefacts/mayor-quorum/`, `artefacts/requisitions/` and their oracles — no rebuild, no re-freeze. No framework, gate, script, or TUI change; the TUI consumes the new set unmodified, which is itself the law-swap proof.
- Depends on the archived framework contract only; it exercises `law-framework` as it stands.
