# Tasks

The world is populated once and every law references it. Everything here serves that: extract the world, pin it, refuse restatement, and re-freeze the cases against it.

## 0. Settle the open question before freezing

- [x] 0.1 DECIDED and recorded in `design.md`: the hamlet (law) author stocks the world (citizen roster, sheet counts, instruments) and a framework-level review freezes it, mirroring `physical.ttl` review — verified the Open Questions section now records the decision

## 1. Author and freeze the world store

- [x] 1.1 Wrote `framework/world.ttl` by deduplicating the world-owned seeds out of the three cases (union roster of 7 citizens, hamlet, townhall, ballotbox/registry/board, 3 mailboxes + `ownedBy`, 15 sheets + `ownedBy`, authority instrument, single `ph:Clock` at 0/0; `goods/seed` stays a requisitions law seed; moved identically-declared `ph:Hamlet` + `ph:ownedBy` into `framework/physical.ttl`) — verified it parses (76 triples), every subject typed by a declared class, `physical.ttl` vocabulary review still clean
- [x] 1.2 Added the world review mark (`framework/world.freeze`) with `check_world`/`freeze_world`/`verify_world` in `freeze.py` (`--world`/`--verify-world`, reusing the `--vocabulary` mechanics: parse, declared-type/predicate resolution, one-clock check, citizen label+age) — verified `--world` passes, a scratch copy with an ungrounded property is refused naming it, and `--verify-world` passes
- [x] 1.3 Documented the world-vs-law cut in `artefacts/README.md` (world = who/what the hamlet has incl. singleton clock with runtime-owned reading; law seeds = calendar/instances/states/roles; placement rule) — verified the rule places every existing individual unambiguously

## 2. Gate: merge the world, refuse restatement

- [x] 2.1 Merged the world ABox with law seeds in `check.py` (`WORLD` + `parse_world`, merged into a copy of the seed graph; `own_classes` scoping untouched) — verified full `check.py` green on all three cases; pulled seed-parity scoping forward (law seeds only, world exempt as available-not-required) after the merge exposed requisitions failing on world-owned `ownedBy`; remaining redeclaration REPORTs are the 4.1 migration debt
- [x] 2.2 Added the individual-redeclaration check (`check_world_restatement`, wired as refusal `world restatement`: only subjects count, object references are fine) — verified by injecting a restated citizen into a scratch population and confirming the gate FAILs naming the IRI; diverged deliberately from the class-level REPORT convention (two states on one thing corrupt the runtime graph, and 4.1 removes every restatement); all shipped cases now fail this check until migration, which is the debt 4.2 clears
- [x] 2.3 Population checks verified on the merged graph via a scratch case (mayor-2027 seeds minus world blocks + a Role `playedBy` a world sheet): population/parity/restatement all green, proving reference-by-IRI passes; same scratch plus an individual typed by an absent class is refused naming it, proving law seeds still need typing (first attempt appended malformed turtle and failed at parse — redone well-formed via rdflib)

## 3. Freeze: pin the world, exclude the clock reading

- [x] 3.1 Recorded the world version in the manifest body on freeze (`world` key, mirroring `shared_vocabulary`) with drift refusal naming the world store — verified end-to-end on a shrunk scratch case (freeze → verify passes → world touched with a real triple → verify names the drift with both hashes → world restored → verifies again); this forced pulling the runtime loader merge forward (see 5.1 note below), without which shrunk seeds cannot drive
- [x] 3.2 Clock reading excluded from the world hash (`world_version` canonicalises over sorted triples minus the clock's `dayIndex`/`atHour`) — verified moving the clock to day 1461/hour 19 leaves the hash stable while adding a citizen moves it
- [x] 3.3 Confirmed uniform pinning on the least world-dependent law: a shrunk requisitions scratch (39 triples, names no furniture) freezes, then a world move adding one sheet it never names STILL refuses naming the world with both hashes — no furniture-level exemption (design decision 4 corrected accordingly: every law presupposes citizens+clock)

## 4. Migrate the three cases

- [x] 4.1 Shrunk each `population.ttl` to law seeds only via world-subject subtraction (mayor-2027: 17 subjects; mayor-quorum: 13; requisitions: 11 + `goods/seed` kept as law schedule; zero world-owned subjects remain in any file), refreshed headers, and deleted the now-framework `ph:Hamlet`/`ph:ownedBy` local TBox declarations — verified no citizen, mailbox, sheet, furniture or clock individual remains
- [x] 4.2 Full gate green on all three cases against the merged world — fixes surfaced: monotonicity probe restore-fix (false positive on probe-minted cycles under the floored clock, exposed by the union roster), 5 mutation fixtures retargeted to the world, world restocked to 7 sheets × 7 citizens + 7 mailboxes after suites proved a half-stocked world unusable, electorate-count updates (`test_oracle`, `test_quorum`, `test_conformance`, README example); `test_gate.py` 35/35 green per case and all law-behavior suites green
- [x] 4.3 Re-froze all three cases against the pinned world — verified `scripts/freeze.py --verify` passes per case with the recorded world version named

## 5. Consumer loads world + one active law

- [x] 5.1 The frozen-set loader (`graphwire.load_artefact_case`, the single runtime path via `OracleClient`) resolves world + active law and refuses a set whose recorded world moved (`WorldDriftError` naming recorded vs current versions; unrecorded drafts/scratch load against current world) — verified refusal on a drifted world and clean load after restore; `world_version` now lives in `graphwire` as the single definition used by both loader and freezer; all three gates re-verified green
- [x] 5.2 One law at a time against the persistent world — verified all three loaded laws share the single clock IRI with no per-law clock state, and sequential activations via an operator-persisted world store carry the present over (mayor-2027 advanced to (10,20), mayor-quorum reads (10,20) with calendar positions resolving per law); production world file untouched by activations

## 6. Prove the layering claim

- [x] 6.1 End-to-end recorded run: fresh world freeze + verify, all three full gates green, all three case verifies green, drifted world refused by both loader (`WorldDriftError`) and `freeze --verify` (naming recorded vs current hashes), restore re-verifies clean
- [x] 6.2 Confirmed `law-drafting-clarification-loop` declares the world as prerequisite (read-only background) with no changes needed here — noted in that change's design Migration Plan rather than by code
