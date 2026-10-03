# Proposal

## Why

The ECA framework promises Event-Condition-Action rules, but only Event, Condition, and Holder have executable Lean encodings — the Action (transition) leg lives nowhere, leaving Phase 2 with no transition table to implement from. Encoding transitions as pure Lean functions behind a new `oracle apply` verb closes the contract with a single source of rule semantics.

## What Changes

- Add a per-ECA pure transition function in `rules.lean` (`applyAnnounce`, `applyNominate`, `applyPrepare`, `applyVote`, `applyCount`, `applyProclaim`, plus `repeatAfterVoid` generalizing the orphaned `repeatFresh`), each guarded by the same Bool conditions as `check` and returning `Except String Snapshot` where the error doubles as the guide's rejection message.
- Add an `Act` inductive (+ `FromJson`) mirroring manifest ECA ids with parameters, and a single `apply : Act → Snapshot → Except String Snapshot` dispatch.
- Add an `oracle apply` CLI verb taking a `{"act": ..., "snapshot": ...}` envelope on stdin and returning the new snapshot (exit 0) or a JSON error (exit non-zero); `check` stays advisory and unchanged.
- **BREAKING**: drivers SHALL request transitions through `oracle apply` and SHALL NOT implement rule semantics in Python; the archived "transitions stay in Python" decision is superseded for enforcement (Python still owns clock, state custody, and display).
- Document the six mayor transitions plus quorum-repeat in `artefacts/README.md` next to the snapshot schema.

## Capabilities

### New Capabilities

None — this completes the existing ECA contract, it does not introduce a new capability.

### Modified Capabilities

- `law-framework`: the ECA metamodel gains an executable Action leg (pure Lean `apply` functions + `Act` JSON), and the oracle runtime interface gains the `apply` verb alongside `list`/`check`.

## Impact

- `artefacts/mayor-2027/rules.lean` and `artefacts/mayor-quorum/rules.lean` (new `Act`/`apply` sections; uniform interface extends to `apply`).
- `potato-hamlet-lean/OracleMain.lean` (new `cmdApply` + envelope parsing).
- `artefacts/README.md` (transition table + `apply` protocol docs).
- `scripts/build_oracle.py` output unchanged in shape (same exe, new verb); `scripts/test_oracle.py` / `test_quorum.py` extended with apply-trace tests.
- Both artefact sets require re-freeze after the rules change (freeze covers `rules.lean`).
- Downstream: `law-simulation-tui` (in progress) consumes `oracle apply` instead of implementing transitions.
