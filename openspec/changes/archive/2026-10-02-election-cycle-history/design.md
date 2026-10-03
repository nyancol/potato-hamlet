# Design

## Context

See proposal.md (Why) for motivation. Current state: `artefacts/mayor-quorum/rules.lean` holds a flat `Snapshot` (top-level day/registry/ballots/box/flags), `electionDay = 10` and `repeatElectionDay = 40` constants, `repeatFresh` overwriting in place, and `Act.repeat` hidden from `ecaIds`/`pendingOf`. `law-framework` already mandates `apply` as the single enforcing path. The TUI change (`law-simulation-tui`) is parked until this lands.

## Goals / Non-Goals

**Goals:**
- History-preserving snapshot where the void cycle survives and the successor appends.
- `repeat` discoverable by any generic driver via `list` + `pending`, owned by the authority.
- Calendar logic owned by ontology declarations + Lean per-index computation; drivers render only.

**Non-Goals:**
- Term-limit or other past-dependent rules beyond making history visible to them (example only, not specified here).
- TUI process-pane implementation (belongs to `law-simulation-tui`, which consumes this).
- Changing the 4-year recurrence or the six base ECA semantics.

## Decisions

1. **Cycle-list snapshot with current-is-last.** `Snapshot = { citizens, mayorId, cycles: List Cycle }` where each `Cycle` carries id, days, registry, ballots, box, flags, outcome. Alternative (past/current split struct) rejected: two shapes for one concept; last-element convention keeps JSON and Lean uniform, at the cost of drivers handling the empty-list impossibility (invariant: at least one cycle).
2. **Repeat as append, not replace.** `repeatAfterVoid` returns `s ++ [freshCycle k+1]` with dates from `electionDay(k+1)`. Alternative (in-place reset) rejected: destroys the void election the domain requires to keep; append costs snapshot growth, bounded in practice by human-driven cycles.
3. **Per-index date functions replace constants.** `electionDay(k) = base + 30*k` (with `base = 10` for the quorum flavor), `announce(k) = E(k)-10`, `prepare(k) = E(k)-1`. All guards (`announceDue?`, `prepareDue?`, `pollsOpen?/pollsClosed?`, `countDue?`, `proclaimDue?`) and `firedOf/pendingOf/violationsOf/phaseOf` scope to the current cycle. Alternative (constants + offset field) rejected: cannot express chains of failures.
4. **Deterministic cycle IRIs minted in Lean.** Scheme `<ontology>/election/<case>-r<k>` (e.g. `.../election/mayor-quorum-r1`), declared as `MayorElectionCycle` individuals with label + day properties. Alternative (UUIDs) rejected: breaks snapshot↔TTL identity and freeze comparability.
5. **Ontology declares, Lean computes, drivers render.** The `.ttl` gains cycle date datatype properties and gap individuals; Lean fills concrete values per `apply`; manifest `time:` block becomes derived documentation; `artefacts/README.md` documents the history JSON shape. Alternative (Python date math) rejected: violates the generic-TUI goal and duplicates law logic per driver.

## Risks / Trade-offs

- [Risk] Snapshot growth over many repeats → Mitigation: human-paced cycles; full per-cycle data retained for audit (void-cycle ballots queryable), revisit summarization only if a pathological chain appears.
- [Risk] `check.py` GFO/label checks must cover cycle individuals → Mitigation: extend the existing simulatable-individual label rule, no new harness.
- [Risk] Existing `test_quorum.py` traces assume flat shape → Mitigation: rewrite traces to history shape in this change (tasked below); keep the same acceptance meanings (violation text, day-40 successor, fresh registry/ballots).
- [Trade-off] Single `mayorId` at top level while cycles each have outcomes → Accepted; office is singular, cycles are plural. A cycle's winner feeds `mayorId` only via `proclaim` on a valid cycle.

## Migration Plan

Quorum-only migration, ordered: Lean `Cycle` struct + per-index dates + append-repeat + `ecaIds`/`pendingOf`/`phaseOf` scoping; ontology date properties + cycle class documentation; manifest `repeat` stanza; oracle rebuild; `test_quorum.py` + `test_oracle.py` update; `scripts/check.py` cycle-label coverage; refreeze `artefacts/mayor-quorum/` (freeze hash changes, expected). Baseline `mayor-2027` untouched unless it shares code paths. Rollback: previous oracle binary + pre-change frozen set remain runnable. TUI unblocks after this archives.

## Open Questions

None — IRI date formatting ("Feb 11" vs "day 40") is a display-string detail for implementation to choose within the label contract.
