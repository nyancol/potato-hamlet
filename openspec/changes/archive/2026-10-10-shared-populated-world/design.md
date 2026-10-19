# Design

## Context

See `proposal.md` for motivation. The facts shaping the approach:

- **Identity is already global, storage is duplicated.** `mayor-2027/population.ttl` and `mayor-quorum/population.ttl` declare byte-identical IRIs (`<.../citizen/alice>`, mailboxes, sheets, townhall) in separate per-case copies. Same IRI means the same entity everywhere; nothing today stops two copies drifting.
- **The gate already merges.** `check.py` merges `framework/physical.ttl` (shared TBox) into the case TBox and judges coherence partly on the law's own declarations (`own_classes` in reachability/orphan checks). Extending the merge to a shared ABox follows the same pattern.
- **Freeze already versions shared meaning.** `freeze.py` records the shared-vocabulary hash in the manifest body beside the case hash, converting silent drift into informed re-review. The world needs the same treatment, not a new mechanism.
- **The oracle/runtime split already assigns furniture.** The runtime alone brings physical things into being; the oracle mints only meanings, occurrences, instances, calendar nodes and bounds. A shared world makes that split load-bearing across laws instead of within one case.

## Goals / Non-Goals

**Goals:**

- One populated world, reviewed once, referenced by every law by IRI.
- Per-case populations reduced to law-derived seeds; frozen cases re-freeze against a pinned world version.
- Single simulation over the shared world with one clock, one law active at a time.

**Non-Goals:**

- Simultaneous multi-law execution (deferred; laws are assumed non-conflicting).
- The pi drafting session itself — that is `law-drafting-clarification-loop`, which consumes the world as read-only background.
- Extracting framework boilerplate out of per-case `ontology.ttl` (the earlier two-ontology idea). Only the ABox moves here, plus the two identically-declared TBox stragglers (`ph:Hamlet`, `ph:ownedBy`) the world review needs resolvable; the invariant/relationship TBox stays per-case to bound the migration.

## Decisions

**1. The world cut: stock vs meaning.** The world holds who and what the hamlet *has*: citizens (+ label, age), the hamlet, townhall, ballot boxes, registry, board, the seeded mailboxes (+ `ownedBy`), the seeded sheet supply (+ `ownedBy`), instruments typed by capability. The citizen roster is the UNION of all cases (Alice, Bob, Cara, Ada, Barnaby, Cleo, Dara): one hamlet means one people, so electorate-dependent semantics such as quorum counts are hamlet-wide and the migration updates affected tests and re-freezes. Mailboxes and sheets stock the whole union roster (one mailbox per citizen per the law's own rule, five sheets each); the law-behavior suites proved a half-stocked world unusable (`prepare` refuses naming citizens with no paper). Law seeds hold when and what it *means*: calendar points/spans, process instances + Chronoids, state and role individuals. *Alternative considered:* world holds calendar too (a shared hamlet calendar). Rejected: each law's dates are its own arithmetic; a shared calendar would couple every law's schedule to one file.

**2. Clock identity in the world, reading outside the freeze.** The single `ph:Clock` individual is declared in the world (one hamlet, one present), but its `ph:dayIndex`/`ph:atHour` values are runtime-owned mutable state, excluded from the world hash — the same shape/frozen vs position/runtime distinction Chronoid bounds already carry. *Alternative considered:* clock stays per-case. Rejected: per-case clocks reintroduce one present per law, contradicting the single simulation.

**3. Reference-don't-restate extends to individuals.** The rule governing shared classes (`check_local_redeclaration` reports a case restating `ph:Mailbox`) extends to shared individuals: a case declaring a world-owned IRI fails the gate. Laws name Alice; they never declare her.

**4. World file mirrors the vocabulary pattern.** `framework/world.ttl` plus `framework/world.freeze`, beside `physical.ttl` / `physical.freeze`. Same review-mark mechanics. Pinning is UNIFORM: every law freezes against a recorded world version and any drift forces re-review — no furniture-level exemption. (An exemption was considered during planning for laws naming no furniture, and rejected during implementation: every law presupposes citizens and the clock, so no shipped law could qualify, and runtime verdicts depend on the roster even where seeds name nothing. "Available, not required" continues to live at the TBox level, where it already holds.)

**5. Gate merges world + law seeds; freeze pins both versions.** The merged graph is world ABox + law seeds + both TBoxes; law coherence (reachability, orphans) is still judged on the law's own declarations. The manifest records TBox version and world version; either moving prompts re-review, neither silently changes meaning.

**6. One law active at a time.** The simulation loads world + one frozen law; the shared clock and consumed supply persist across activations. Per-law oracles, verdict shapes and gate walks are unchanged. *Alternative considered:* simultaneous execution with act routing and verdict merging. Deferred as its own design problem (routing, cross-law supply contention such as two laws writing one sheet's label).

**7. Two TBox declarations move to the framework (surfaced during implementation, task 1.1).** All three cases declare `ph:Hamlet rdfs:subClassOf gfo-light:ObjectAggregate` identically, and both mayor cases declare `ph:ownedBy` with identical axioms (domain/range `gfo-light:Object`). A standalone world review cannot resolve world individuals typed by per-case declarations, so both move into `framework/physical.ttl` as pure dedup, and the local declarations are deleted in migration. *Alternative considered:* resolving world references against the union of shipped case ontologies. Rejected: that makes the world's meaning depend on whichever cases happen to exist. Note: `shared-physical-vocabulary` owns `physical.ttl`'s shape — coordinate the addition with that change. `ph:Goods`/`ph:sum` stay law-local (requisitions): `goods/seed` is that law's schedule, not hamlet furniture, so it remains a requisitions law seed.

## Risks / Trade-offs

- **[Risk] World writes are law-visible.** One shared paper supply makes reuse real: `prepare` in one election mutates furniture another law names. → Mitigation: runtime owns all world writes; laws run one at a time; supply sizing stays a world-authorship decision with shortfall refusal exercised on scratch seeds.
- **[Risk] One world edit re-reviews every law.** Alice aging invalidates all freezes at once. → Mitigation: that is the existing shared-vocabulary mechanism doing its job — pinned versions turn silent drift into an explicit re-review list. Accepted as the price of a single truth.
- **[Risk] Clock-value exclusion is subtle.** Hashing identity but not reading needs care in `freeze.py` (canonicalize the world with the clock's position stripped). → Mitigation: same treatment as mutable instance flags; verify by advancing the clock and confirming the world hash is stable.
- **[Trade-off] Migration touches everything at once.** All three populations, freeze semantics, gate merge, TUI loader. Accepted: split from the loop change precisely so this migration reviews alone; the loop declares it as prerequisite.

## Migration Plan

1. Author `framework/world.ttl` by deduplicating the three cases' world seeds (citizens, furniture, mailboxes, sheets, instruments, clock identity); review and freeze as `framework/world.freeze`.
2. Shrink each `population.ttl` to law seeds; delete world-owned individuals.
3. Update `check.py` (merge + individual redeclaration check) and `freeze.py` (world pin, clock exclusion); confirm all shipped cases pass.
4. Update the TUI loader to resolve world + active law; re-freeze all cases.
5. Rollback: per-case git history holds the pre-extraction populations; old freezes verify against old code only.

## Open Questions

None — the authorship question is settled (task 0.1): the hamlet (law) author stocks the world (citizen roster, sheet counts, instruments) as part of drafting, and a framework-level review freezes it, mirroring how `physical.ttl` is reviewed today. A world change therefore ships as: author edits `framework/world.ttl`, framework review re-freezes `framework/world.freeze`, every case re-verifies (re-review where drifted).
