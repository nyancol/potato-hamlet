# Tasks

## 1. Cycle-list snapshot and per-index dates in Lean

- [x] 1.1 Introduce the `Cycle` record and migrate `Snapshot` to `{ citizens, mayorId, cycles }` with current-is-last, and verify `lake env lean artefacts/mayor-quorum/rules.lean` typechecks with Prop/Bool agreement theorems intact
- [x] 1.2 Replace `electionDay`/`repeatElectionDay` constants with per-index `electionDay(k)`, `announce(k)`, `prepare(k)` and scope all guards plus `firedOf`/`pendingOf`/`violationsOf`/`phaseOf` to the current cycle, and verify the 39-of-40 distribution witness scenario still reports `(citizen, candidate)` through `check`
- [x] 1.3 Rework `repeatFresh`/`repeatAfterVoid` to append a fresh successor cycle (void cycle preserved with outcome, empty registry/ballots/box, recomputed dates, deterministic `(case, k)` IRI) and verify a two-failure trace yields three cycles with days 10, 40, 70

## 2. First-class repeat ECA and ontology calendar contract

- [x] 2.1 Add the `repeat` manifest stanza (authority holder, modality `must`, `eca_process`, message naming the successor), include `"repeat"` in oracle `ecaIds`, and offer the authority pending entry on the void condition, and verify `oracle list` equals manifest ids and `check` on a void snapshot pends `repeat` on the authority
- [x] 2.2 Declare cycle date datatype properties and the 30-day gap rule on `ph:MayorElectionCycle` in `artefacts/mayor-quorum/ontology.ttl` with `rdfs:label` on cycle individuals, and verify `scripts/check.py artefacts/mayor-quorum` passes including cycle label coverage
- [x] 2.3 Document the history JSON shape and `list`/`check`/`apply` protocol (including `repeat` and rejection envelopes) in `artefacts/README.md`, and verify the documented `oracle list` and `oracle check` commands run as written

## 3. Harness, acceptance, and refreeze

- [x] 3.1 Rewrite `scripts/test_quorum.py` traces to the history shape (void cycle preserved, successor fresh, repeat-until-valid chain, repeat-rejects-valid) and verify `uv run python scripts/test_quorum.py artefacts/mayor-quorum` passes
- [x] 3.2 Confirm `scripts/test_oracle.py` and `scripts/snapshot_roundtrip.py` against the new shape (updating fixtures only where the shape changed) and verify both pass on `artefacts/mayor-quorum` with `artefacts/mayor-2027` untouched or explicitly migrated
- [x] 3.3 Run `openspec validate election-cycle-history --type change --strict` and refreeze with `uv run python scripts/freeze.py artefacts/mayor-quorum`, and verify `freeze.py --verify` passes and the new freeze hash is recorded
