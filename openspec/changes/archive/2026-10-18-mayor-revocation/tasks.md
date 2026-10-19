# Tasks

## 1. Law text and ontology

- [x] 1.1 Author the revocation clause in `artefacts/mayor-revocation/law.txt`, branched from the mayor baseline: a candidate revoking during election day stops the election, a postponed election is scheduled, cast votes do not count
- [x] 1.2 Declare `CandidacyWithdrawn` as a `gfo-core:State`, `RevokeCandidacy`, `StopElection`, and `PostponeElection` as `gfo-core:Process` classes reachable through `ph:hasPhase`, and a `ph:causedBy` relation from the stopping process to the withdrawal state, and verify OWL parse plus GFO grounding passes
- [x] 1.3 Seed `artefacts/mayor-revocation/population.ttl` from the mayor baseline (citizens with labels and ages, calendar points and spans, the initialised election instance) with no individual in `ontology.ttl`, and verify every subject is typed by a declared class

## 2. Rules and manifest

- [x] 2.1 Implement the revoke act in `rules.lean` (holder `CandidateRole`, guard registered-and-not-withdrawn during polls-open, mints the `CandidacyWithdrawn` individual) and verify a withdrawal outside polls is refused naming the guard
- [x] 2.2 Implement the halt act (holder the authority, guard a withdrawal individual exists for the ongoing instance, lands the `Chronoid` finish bound inside the election-day span, outcome records non-count) and verify the instance terminates with its cast ballots still present
- [x] 2.3 Implement the postpone act (holder the authority, appends a successor instance with empty registry and ballots, mints its calendar spans with Lean-computed dates) and verify the successor resolves displayable dates with no law-specific consumer handling
- [x] 2.4 Declare the three ECAs in `manifest.yaml` with holder roles, parameters (`selected` for the withdrawing citizen), modalities, messages, and reading templates, each `eca_process` appearing in the declared hierarchy, and verify `oracle list` agrees with the manifest ids

## 3. Oracle, gate, and trace tests

- [x] 3.1 Build the `mayor-revocation` oracle with `scripts/build_oracle.py` and verify `list`, `check`, and `apply` round-trip the seeded graph
- [x] 3.2 Run `scripts/check.py` against the new set and verify the framework-invariant, grounding, reachability, orphan, hierarchy-agreement, calendar-coverage, `ph:causedBy` shape, and clock-totality checks all pass
- [x] 3.3 Add a revocation trace script driving nominate, vote, revoke during polls, halt, and postpone, and verify the withdrawn candidate is named under `refs`, the halt pends on the authority, the stopped instance keeps every ballot with a non-count outcome, no act removes an individual, and the successor starts fresh
- [x] 3.4 Verify the boundary races: revoke after polls-close is refused, double withdrawal is refused, and withdrawing the only candidate still halts rather than producing an empty count

## 4. Freeze and validation

- [x] 4.1 Freeze `artefacts/mayor-revocation/` and verify `scripts/freeze.py --verify` passes for the new set, with no existing set modified
- [x] 4.2 Load the frozen set into the unmodified TUI binary (or its loader, if the TUI is mid-implementation) and verify the revoke, halt, and postpone duties render and play with zero consumer code change
- [x] 4.3 Run `openspec validate mayor-revocation --type change --strict` and verify the planning artifacts are complete and consistent
