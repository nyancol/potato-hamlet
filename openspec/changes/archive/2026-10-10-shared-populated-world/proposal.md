# Proposal

## Why

Every law case carries its own complete copy of the hamlet: the same Alice, Bob and Cara IRIs, the same townhall, mailboxes, sheets and instruments are re-declared in `mayor-2027/population.ttl`, `mayor-quorum/population.ttl` and every future case. Identity is already global (same IRI means the same Alice everywhere), but storage is per-case duplication — so nothing stops two cases' copies of the world drifting apart, and a pi drafting session has no single populated reality to reference, only copies to imitate. The world should be populated once, before any law is proposed, with each law enriching that shared reality by reference rather than restating it.

## What Changes

- **A new shared world artifact**: one versioned, reviewable store holding the populated reality every law presupposes — citizens, the hamlet, physical furniture (townhall, ballot box, registry, board), per-citizen mailboxes, the sheet supply, instruments with their capability typing, and the single `ph:Clock` individual (identity frozen; its reading stays runtime-owned and out of the freeze hash).
- **Per-case populations shrink to law seeds**: `population.ttl` keeps only what the law derives — calendar points/spans, process instances + Chronoids, state and role individuals. World-owned individuals move out; re-declaring one in a case becomes a gate offense like re-declaring a shared class.
- **Freeze pins the world version**: a case freeze records the world version it was reviewed against (extending the existing shared-vocabulary mechanism), so world drift prompts informed re-review instead of silent meaning change.
- **Gate merges world + law seeds**: checks run over the merged graph, with the law's coherence still judged on what the law declares.
- **One simulation, one clock, one law at a time**: laws are assumed non-conflicting; the simulation activates a single law against the persistent world, carrying the shared clock across laws. Simultaneous multi-law execution is explicitly deferred.
- **BREAKING**: existing frozen cases re-freeze against the world (one migration of seed individuals into the shared store); `population.ttl` scope change is a format-level contract change for every consumer of artefact sets.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `law-framework`: the artefact contract changes — a shared world ABox exists alongside the shared TBox; per-case populations hold law-derived seeds only; freeze records the world version; a single `ph:Clock` carries the shared present and its reading is runtime-owned rather than frozen.
- `law-extraction`: "Law variant input layout" changes — `population.ttl` no longer holds all individuals the law starts from, only the law-derived seeds; world individuals are referenced by IRI from the shared store.

## Impact

- **`framework/`**: new world store file plus its review mark (beside `physical.ttl` / `physical.freeze`); world authorship and review process to define.
- **`artefacts/<case>/population.ttl`** (all three shipped cases): world seeds extracted once into the shared store; files shrink to calendar, instances, states, roles.
- **`scripts/check.py`**: merge world ABox with law seeds; new local-redeclaration check for individuals; `own_classes` scoping unchanged in spirit.
- **`scripts/freeze.py`**: TRACKED semantics plus world-version pinning; clock reading excluded from the hash.
- **Consumers (TUI via `law-simulation-tui`)**: loader resolves world + active law instead of a self-contained set.
- **In-flight changes**: prerequisite for the pi-driven loop in `law-drafting-clarification-loop` (which consumes the world as read-only background); touches files `shared-physical-vocabulary` also owns.
