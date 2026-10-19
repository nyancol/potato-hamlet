# Design

## Context

See proposal.md (Why) for motivation. The contract this flavour is written against is the archived `law-framework`: the knowledge graph is the snapshot, `apply` is the single enforcing path, `ph:causedBy` may relate a Process to a State as a permitted dependency with evaluation in the Lean guard, cancellation retains individuals while recording non-count in the outcome, termination may land inside a calendar span, and a law may mint calendar individuals at `apply` time with only Lean dating them. The sibling to copy from is `artefacts/mayor-quorum/`: same election calendar, same ECA spine, and its `repeat` is the pattern for scheduling a successor with fresh preparation. Nothing in this design changes the framework, the gate, or any shipped set.

## Goals / Non-Goals

**Goals:**
- A frozen `mayor-revocation` set that a reviewer can read as the mayor law plus one clause.
- The first exercised instance of every framework guarantee the proposal names.
- An unmodified TUI binary plays the halt and the postponement.

**Non-Goals:**
- Changing what any existing flavour does, or rebuilding any existing oracle.
- Covering withdrawal outside election day; the clause triggers during polls.
- Deciding the postponement interval in this document; that is a law-text sentence, with a default proposed below.

## Decisions

**1. Annulled, not erased.** Ballots cast before the halt stay in the graph as labelled `CastVote` individuals; the stopped instance's outcome records that they do not count. This was settled before this change: erasure would destroy the audit trail the graph exists to provide, and the framework's non-removal rule leaves no other reading. *Alternative considered:* deleting the ballots on halt. Rejected — no ECA may remove an individual, so the law could not express it even if the text asked.

**2. The halt is an authority act, never automatic.** The oracle initiates no transition, so a withdrawal sitting in the graph stops nothing by itself; the authority must confirm the halt, and only then does the instance terminate. This keeps the Spirit discipline intact — the guide reports the withdrawal as a reading and the halt as a pending duty, and nothing moves until the holder acts. *Alternative considered:* terminating the instance inside the withdrawal act. Rejected — it would fold two holders' acts (the candidate's, the authority's) into one envelope and make the halt unrefusable.

**3. Revocation is the candidate's own act, offered during polls.** Holder is `CandidateRole`, parameter is the withdrawing citizen sourced from `selected`, guard is registered-and-not-already-withdrawn. The window is polls-open because the clause triggers "during election day"; withdrawing before polls is not modelled, since a name not yet balloted for needs no halt. *Alternative considered:* a single revoke-and-halt act. Rejected for the same reason as decision 2 — it collapses two duties into one.

**4. Withdrawal is a State individual, not a flag.** The act mints a `CandidacyWithdrawn` individual relating the candidate and the instance, and the stopping process declares `ph:causedBy` against that State class. The ontology therefore states that a withdrawal *can* stop an election; the Lean guard decides whether one *has*, by checking the individual exists. Registry membership is a relation, not an individual, so revising it violates no non-removal rule — the rule protects individuals, and none is deleted. *Alternative considered:* a withdrawn flag on the citizen. Rejected — a flag is untyped state the graph cannot name, and the framework's whole withdrawal story is written in terms of individuals.

**5. Postponement reuses the repeat shape.** The authority's postpone act appends a successor `MayorElectionCycle` with empty registry and ballots, and mints its calendar spans with dates Lean computes — the same mechanics as quorum's `repeat`, differing only in trigger (withdrawal-halt rather than quorum failure) and interval. The default interval is 30 days, mirroring the standing quorum rule, unless the authored law text states another; either way it appears once as `ph:gapDays` on the bounding span and Lean resolves the concrete points. *Alternative considered:* resuming the stopped instance after the withdrawal. Rejected — nominations and ballots were gathered for a race that no longer exists, and the quorum precedent (void instances never resume) already settles that a stopped instance stays stopped.

**6. The withdrawn candidate may stand again.** The successor starts from a fresh registry with no carry-over, exactly as a quorum successor does; the withdrawal belonged to the stopped instance, so nothing bars the citizen from re-nominating. This falls out of the fresh-registry rule rather than needing its own mechanism. *Alternative considered:* barring the withdrawing candidate from the postponed election. Rejected — the law text does not ask for it, and it would need vocabulary (a ban surviving across instances) that no framework concept provides.

**7. Verdict surface follows the existing shapes.** Once the withdrawal individual exists, `check` pends the halt on the authority alongside a violation naming the withdrawn candidate under `refs`; after the halt, `check` pends the postponement the way it pends `repeat` on a void cycle. Readings report the halt and the scheduled date; no new verdict field is needed. The TUI renders all of it from the manifest declarations, which is the law-swap proof.

## Risks / Trade-offs

- **[Risk] Revocation at the polls-close boundary** — a withdrawal at 19:00 races the count. → Mitigation: the revoke guard requires polls-open, evaluated against the clock the act carries; a withdrawal stamped after close is refused naming the closed-polls guard, and the election proceeds to count.
- **[Risk] Double withdrawal** — the same candidate revoking twice. → Mitigation: the guard requires not-already-withdrawn, refused naming it; the State individual exists at most once per candidate per instance.
- **[Risk] The successor's minted calendar collides with the frozen one.** → Mitigation: minted IRIs satisfy the freshness rule and minted spans carry the same declared properties as seeded ones; the gate's round-trip and freshness checks cover exactly this.
- **[Risk] Votes for the withdrawn candidate cast before the halt.** → Mitigation: there is nothing to mitigate — the whole instance is stopped and no ballot counts, which is what the outcome records. The scenario exists to assert this rather than to handle it.
- **[Trade-off] Three ECAs for one clause** (revoke, halt, postpone) where the text reads as one sentence. Accepted — the framework admits no holderless transition, so each holder's part is its own act, and each is separately refusable with a named guard.

## Migration Plan

New artefact set; nothing migrates. Order: law-text clause → ontology and seed → rules and manifest → oracle build → gate and trace tests → freeze. No existing set is touched, so rollback is deletion of the new directory. The TUI loads the frozen set unmodified.

## Open Questions

- Postponement interval if the authored law text does not mirror the 30-day quorum rule; decision 5 records the default, and the law text is the authority.
- Whether withdrawing during the nomination window (before any ballot exists) deserves its own lighter path rather than the full halt machinery; out of scope for the clause as stated, since no halt is needed when nothing has been cast.
