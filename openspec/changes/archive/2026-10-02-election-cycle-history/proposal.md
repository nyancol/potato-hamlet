# Proposal

## Why

The quorum repeat as built wipes the void election (`repeatFresh` overwrites the snapshot in place) and `repeat` is a ghost act (enforceable via `apply` but absent from `list`, manifest, and `pending`). A void election is still an election: history must survive for audit, for the TUI process pane, and for past-dependent rules (e.g. term limits). This change promotes the repeat to a first-class, holder-owned ECA over a history-preserving snapshot before the TUI is built against it.

## What Changes

- **BREAKING**: Snapshot gains an election-cycle history. Per-cycle state (registry, ballots, box, announced/prepared/counted/proclaimed flags, outcome) moves inside a cycle record; only population (`citizens`) and office (`mayorId`) stay top-level. The current cycle is the last element; dates derive per index (`E(k+1) = E(k)+30`).
- Promote `repeat` to a first-class ECA: authority holder (mayor-or-oldest, same `authorityId` as announce/prepare/count/proclaim), modality `must`, manifest stanza with `eca_process` + message, inclusion in oracle `list`, and a `pending` entry on the void condition.
- Define the ontology calendar contract (option A): the `.ttl` declares cycle date properties and gap rules; Lean computes concrete per-cycle dates at `apply` time and mints deterministic cycle IRIs from `(case, k)`; verdicts carry date-filled display strings. Python never computes dates.
- Record the mandate assumption: repeats never shift the 4-year `2027+4K` election clock; they only shorten the mandate in office.
- Refreeze `artefacts/mayor-quorum/` (and any baseline touch) through the existing `check` + `freeze` gate; update `test_quorum.py` traces to the history shape.

## Capabilities

### New Capabilities

None — all behavior changes refine the existing framework contract.

### Modified Capabilities

- `law-framework`: quorum repeat becomes schedule-a-new-cycle (not wipe-in-place); ECA metamodel and oracle `list`/`pending` cover `repeat` as holder-owned; snapshot identity extends to cycle IRIs; time model gains per-repeat date arithmetic; transition table defines repeat as append.

## Impact

- `artefacts/mayor-quorum/ontology.ttl`, `rules.lean`, `manifest.yaml` plus refreeze hashes; mirror updates to `artefacts/README.md` protocol section (`list`/`check`/`apply`).
- `potato-hamlet-lean/` oracle (`ecaIds`, `pendingOf`, `phaseOf` per-cycle, `repeatFresh` -> append, cycle IRI minting).
- `scripts/test_quorum.py`, `scripts/test_oracle.py`, `scripts/check.py` (cycle-aware checks), `scripts/freeze.py` (no logic change, re-run).
- Blocks `law-simulation-tui` (TUI builds against the new snapshot shape and `apply`-as-path); no TUI code in this change.
