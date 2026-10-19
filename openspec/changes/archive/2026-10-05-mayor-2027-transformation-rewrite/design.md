# Design

## Context

This change is a **port**, not a derivation. Every question it answers was answered once, from `law.txt`, in `mayor-quorum-transformation-rewrite`. `mayor-2027/law.txt:11-13` is word-for-word identical, so the readings hold without re-reading and are cited rather than restated.

What is genuinely different, and what this design has to account for:

**`mayor-2027` has no quorum requirement and no repeat.** Its `ecaIds` is six entries where the quorum law's is eight. Everything about the missing-ballot witness, the shortfall refusal and the successor cycle therefore has no counterpart here. The transformation work is the same; the surrounding machinery is smaller.

**`Snapshot` is flat.** The quorum law carries a `Cycle` and a list of them, because a repeat preserves a void instance. This law has one election per run and no repeat, so `candidates`, `ballots`, `registry` and `box` are fields on `Snapshot` itself (`rules.lean:116-131`). Four new fields go on `Snapshot` rather than on a cycle, and `ensureOccurrences` is not a per-cycle fold here — the seeded furniture is read once.

**It declares no physical vocabulary at all.** `grep -cE '^ph:Mailbox|^ph:BallotBox|…' artefacts/mayor-2027/ontology.ttl` returns `0`. Where the quorum law had classes declared and unseeded, this law has neither. So the ontology work here is larger in one respect — every class comes from the shared file — and smaller in another, because there is nothing to unpick.

## Decisions

**1. Port the quorum law's shape unchanged, and inherit its readings.** The four readings — delivery is one ECA iterated by recipient, the seed supplies blank sheets and `prepare` refuses on the shortfall, delivery gets no phase or span, and writing and taking the Role are one act — rest on `law.txt:11-12`, which this law shares verbatim. Re-deriving them would produce the same answers with a weaker justification, because a second reading of the same sentence is not independent evidence.

**2. The ballot is a Role the sheet plays; the marking is the sheet's own label; delivery is the Role's.** Carried over without change, including the reasoning that survives it. A sheet is a reusable physical object, so its marking is present state and holds one name; which candidate an earlier election's ballot carried is what that election's Role denotes, and was never on the paper to begin with. Delivery goes on the Role rather than the sheet because one supply of paper serves every election, so a sheet left in a mailbox by one election is still there for the next — delivery on the sheet would make the next election's ballots read as delivered before anyone carried them.

**3. `vote` declares the ballot box, and refuses without it.** `law.txt:13` requires the box and `law.txt:15` has the citizen put their vote into it, so it is a named seeded individual and the one thing an act here acts on by name. `vote` records `ph:placedIn` from the citizen's own ballot to the box, giving the shared relation its first user in this law. `prepare` declares nothing: its inputs are a run-time supply and it refuses on the shortfall instead, naming the citizen who is short.

**4. The manifest key is `acts_on`, never `on`.** YAML 1.1 resolves a bare `on:` to the boolean `True`, so `e.get("on")` is silently `None` and the gate's validation loop never runs — a check that reads as correct and checks nothing. This was found by mutating a declared class to one the ontology lacks and watching the gate pass.

**5. Fix the suites to read the shape off the oracle.** `test_oracle.py` runs against both mayor flavours and `check_apply_props.py` is quorum-flavour only. Both have already broken on this law during the quorum work — the first when quorum-only assertions were added to the shared suite, the second when `Snapshot`'s arity diverged. Corrected once here, by branching on what the oracle serves and skipping with a printed reason rather than a bare Lean failure. A suite that fails a law for another law's rewrite is worse than no suite.

## Risks / Trade-offs

- **[Risk] Porting invites copying rather than reading.** → Mitigation: every design decision above cites the quorum change rather than restating it, so a divergence in this law's text would show up as a decision with no source. `law.txt:11-13` is quoted in the proposal so the claim is checkable.
- **[Risk] The quorum change is not yet archived, so both changes' deltas are live at once.** → Mitigation: this change declares no spec deltas, so there is nothing to conflict. The requirements are already in `law-framework` and `law-extraction`; if archiving the quorum change reveals it needs a delta, that delta belongs to the quorum change and this one is unaffected.
- **[Risk] Two laws with the same shape drift apart.** → Mitigation: the tests assert the *shape* (a ballot is played by a distinct sheet; delivery is per election) rather than counts, so a divergence in one law shows up as a failure rather than as two similar-looking implementations nobody compared.
- **[Trade-off] The 2027 law's suite coverage stays thinner than the quorum law's.** It has no quorum, no repeat and no shortfall path in practice with three candidates and five sheets each. Accepted: those paths are exercised by the quorum law, and duplicating a shortfall scenario here would test the framework twice rather than the law once.

## Migration Plan

No data migration. `requisitions` is untouched and stays frozen. `mayor-quorum` is untouched by this change. Rollback is reverting `rules.lean`, `manifest.yaml`, `ontology.ttl` and `population.ttl` to their prior frozen versions, at the cost of the law not doing what its text says.

## Open Questions

None. The readings are settled in the quorum change and hold verbatim; see its design's *Readings settled from the law text*.