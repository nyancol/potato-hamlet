# Design

## Context

See `proposal.md` (Why) for motivation. The two prerequisite changes land the semantics and the stage; this is the law that uses them. Four facts about the current law shape the approach.

**`Ballot` carries a `delivered` field that is always set true.** `fullBallots` at `rules.lean:1072` is `citizens.flatMap (fun c => cands.map (fun cand => Ballot.mk c.id cand true))`, so the flag is a constructor argument no caller ever passes as anything else. The `allDistributed?` theorem at `:847` and its `Prop` twin agree trivially, because nothing can make it false.

**`applyPrepare` is one atomic act with one guard.** `rules.lean:1075` checks `authorityId` and `prepareDue?` and then assigns the full ballot list. There is no intermediate state, no second guard, and no way for the graph to show forty papers made and none yet carried.

**The declarations the transformation needs are already present and unwritten.** `ph:playedBy`, `ph:roleIn`, `ph:qualityOf`, and `ph:relates` are declared and GFO-grounded at `ontology.ttl:82-104`, and no `rules.lean` writes `qualityOf` or `relates`. `roleTriplesAt` at `:565` already builds the three-triple shape a role needs, taking the subject as a parameter precisely so a non-context-derived subject can be used — the comment at `:559` says as much.

**The law's physical nouns have no individuals.** `ph:Mailbox`, `ph:BallotBox`, `ph:Townhall`, `ph:ResultsBoard`, `ph:CandidateRegistry` are declared at `ontology.ttl:110-117`; `population.ttl` seeds none. `test_conformance.py:321` already reasons about the one licence to name an individual not yet minted, which is the `mints` declaration — and `prepare` mints forty individuals of a class it does not declare as minted, so that licence does not currently cover it.

## Goals / Non-Goals

**Goals:**
- `prepare` does what `law.txt:11-13` says, in as many steps as the law takes.
- Every physical thing a duty is performed on exists as an individual, from the start.
- The delivered flag becomes state a guard can read and a witness can name.
- Exercise the transformation semantics from the prerequisite change in a real law, so those requirements are demonstrated rather than merely declared.

**Non-Goals:**
- Changing the law text, the calendar, the quorum or repeat arithmetic, the tie-break, or the election's phase structure.
- Making every duty in the law a separate act. Only `prepare` is split, because only `prepare` is stated as two duties with an intermediate state the graph should show.
- Extending the shared vocabulary beyond what this law's text names. Paper and pen are the additions; the rest already exist there.
- Any new framework vocabulary. Everything here uses `ph:playedBy`, `ph:roleIn`, `ph:qualityOf`, and `ph:hasParticipant`.

## Decisions

**1. Split into `prepare` and `deliver`, two ECAs, rather than one act with a step.** The law says "must make the ballot votes" and "must put these papers in the mailbox". Two duties with an obligation between them is two acts, because the whole point is that the state between them is real: papers made and not yet delivered is a world the guide should be able to show and a quorum witness should be able to name. One ECA with an internal step would hide exactly the state the change exists to make representable. *Alternative considered:* one ECA whose action performs both halves. Rejected: that is the current code with better comments, and it would leave the delivered flag set at construction.

**2. The sheet keeps its class; the ballot is a Role it takes.** `ph:BallotVote` becomes a Role class rather than the class of the paper, and `prepare` mints one Role individual per sheet whose `ph:playedBy` names the sheet and whose `ph:roleIn` names the current election. This follows the prerequisite change's decision that a new meaning is a Role, and it has a property this law needs specifically: one sheet could in principle be a ballot in one election and something else in another, and because `roleIn` differs the two never collide. *Alternative considered:* typing the sheet as `ph:BallotVote` directly. Rejected: it makes "which individuals are ballots" a function of how far the process has got, and the prerequisite change forbids an individual changing class.

**3. SUPERSEDED by decision 8 — retained only to show what changed.** This originally read: *"The candidate's name is a quality of the sheet, via `ph:qualityOf`. … That is a quality of the sheet, not a separate individual."* Decision 8 considers that exact proposal as an alternative and rejects it, so this decision no longer holds. Two things were wrong with it. It put the candidate on the **sheet**, which makes the fact unconditional: one supply of paper serves every election, so a sheet reused by a later election would carry two candidates at once under `ph:qualityOf`. And it left the marking nowhere — decision 8's stated reason for rejecting it. `ph:qualityOf` was never written by any `rules.lean`; the replacement is `ph:denotes`, on the Role.

**4. The sheets are seeded, not minted, and the seed is per citizen per candidate.** The law says the authority must make one paper per candidate for each citizen, and it is a fixed consequence of the population and the registry at prepare time — but the count depends on who nominated, which is not known at seed time. So the sheets are seeded as a pool large enough for the population times the maximum plausible candidacy, and `prepare` claims the ones it needs. Hmm — that is ugly and unbounded. **Better: the sheets are minted by `prepare` from a seeded pool of blank sheets and pens, one blank sheet seeded per citizen, and the authority writes each candidate's name on a blank sheet during `prepare`.** That is what the law describes, it needs no bound, and the IRI of each written sheet is a function of the sheet and the candidate, which is the freshness pair. Recorded here because the first attempt at this decision was wrong and the correction is the useful part: a pool big enough for every pairing is not expressible without a bound the law does not state.

**5. Delivery is by mailbox, chosen from the choices, so the player performs it.** The law says put the papers in the mailbox of each citizen. Which mailbox each paper goes to is determined by who owns it, so the act does not need a parameter — but the guide should show it, and the choice is available. *Alternative considered:* `deliver` takes no parameters and delivers everything outstanding. Referred: this is the law-specific question of whether delivery is one act or one per recipient, and it is deferred in the tasks rather than settled here, because both are lawful readings of "must put these papers in the mailbox of each citizen".

**6. The delivered flag moves from the constructor to the graph.** `Ballot` keeps a delivered field for the guards, but it is derived from the graph — a sheet is delivered when a Role or a relation records that it reached its owner's mailbox — rather than set at construction. The change is that `prepare` writes `false` and `deliver` writes `true`, and `allDistributed?` becomes a theorem about the graph rather than a tautology. *Alternative considered:* keep the field and flip it. Rejected as equivalent; either works, and deriving it is better because then the graph and the state cannot disagree, which is the property the prerequisite change's totality requirement is about.

**7. `prepare` declares its inputs, and the gate's input check becomes real.** `prepare` names the blank sheets and the pen it acts on. If any is missing, `apply` refuses naming it. This is the first law to exercise the requirement, so the check is verified here rather than only against a scratch law. *Alternative considered:* seeding enough blanks that absence is impossible and skipping the declaration. Rejected: it makes the declaration untested in the one place it can be.

**8. The marking is on the sheet; the meaning is the Role's; delivery is the Role's.** The three facts a ballot turns on are separable in the world, so they are encoded separately and each on the thing it is about:

| fact | where it lives | register |
|---|---|---|
| the marking on the paper | the sheet, as its `ph:label` | physical, present state |
| which candidate it meant | the Role, as `ph:denotes` | contextual |
| whether it reached the mailbox | the Role, as `ph:deliveredTo` | contextual |

The sheet is a **reusable physical object**: one supply of paper serves every election, so a sheet that was carried to its owner's mailbox for one election is still sitting there for the next, and a later election strikes the old name and writes a new one on the same paper. The marking is therefore the sheet's *present* state and holds exactly one name — re-written, never accumulated. Which candidate each earlier election's ballot carried is not lost by that, because it was never on the paper to begin with: it is what that election's Role denotes. Two Roles over one sheet, each denoting its own candidate, is the whole of the history, and the completed process individual does not need to keep the superseded marking.

This is why **delivery is on the Role and not on the sheet.** Recording it on the sheet makes a later election's ballots read as delivered before anyone carried them, because the sheet is still in the mailbox from last time — and then `allDistributed` passes on nothing. Delivery answers "was *this* ballot delivered in *this* election", which is contextual, and a Role's IRI is a function of the occurrence, so scoping it there is free. Verified: after a repeat and a second preparation, the new cycle's ballots read undelivered and `deliver` is pending again.

It also settles the literal-versus-IRI question. The law says *write the name*, so a literal is faithful to it. Identity does not depend on the literal: the Role's `denotes` carries the candidate's IRI, so matching never compares text. Verified by destroying the markings — every sheet rewritten to a string matching no citizen — after which all nine ballots still resolved to the right citizen and the tie still elected the older candidate.

The `denotes` and `deliveredTo` relations need grounding like any other: `rdfs:domain` on the Role class and `rdfs:range` on `gfo-light:Object`, since GFO has no relation from a meaning to a thing it concerns. *Alternative considered (rejected):* the sheet carrying `ph:qualityOf citizen/bob` directly — this is superseded decision 3, and putting the candidate on the sheet would make it unconditional across elections. *Alternative considered (rejected):* a minted `ph:Inscription` individual carrying the literal, hung on the sheet by `ph:writtenOn`. The framework's list of what the oracle may mint is closed — a meaning, an occurrence, a process instance, a calendar node, a bound — and an inscription would be a sixth kind, added by the very change that closes the finding the list exists to catch. Writing a name on paper the hamlet already has creates no thing: the mark is a literal on an existing sheet, so `ph:label` holds it and no IRI is minted that could collide.

Note what this costs. Task 0.4 settled that writing and taking the Role are one act, so a sheet "written on but not yet a ballot" is **not** expressible — the intermediate state this decision originally existed to create. That is the accepted consequence of 0.4, not a gap.

**8a. `vote` declares the ballot box, and puts the ballot in it.** `law.txt:13` requires "a big closed box, the ballot box, in the townhall" and `law.txt:15` has each citizen put their vote *into* it. So the box is a **named, seeded individual** — and it is the one thing in this law that an act can be said to act on by name rather than on a supply. The manifest declares it under `acts_on`, and `apply` refuses the vote naming the box when the world has none, rather than recording a vote that reached nothing: a vote in no box would otherwise be counted toward the quorum.

That refusal is the whole of what the framework's "an ECA declares the individuals it acts on" requirement means here, and it is deliberately *not* extended to `prepare`. `prepare`'s inputs are a supply the act draws from at run time, fixed by the registry, so the law cannot name them in advance; naming fifteen sheet IRIs would assert something the law does not care about and would break whenever the seed changed. `prepare` refuses on the **shortfall** instead, naming the citizen who is short and by how much — which is the more useful refusal anyway, since a supply is short *for someone*.

`vote` also records `ph:placedIn` from the citizen's own ballot to the box, which is the first use that shared relation has in any law. It goes on the **sheet**, unlike a ballot's delivery to a mailbox, which goes on the Role: "the paper is in the box" is a physical fact about the paper, while "this ballot reached its mailbox in this election" is contextual and the same sheet serves every election.

*Implementation note worth keeping:* the manifest key is `acts_on` and **not** `on`. YAML 1.1 resolves a bare `on` key to the boolean `True`, so `e.get("on")` is silently `None`, the gate's validation loop never runs, and a check that reads as correct checks nothing. It was found by mutating the declared class to one the ontology lacks and watching the gate pass.

## Readings settled from the law text

Four questions this change could not answer on its own, resolved against `law.txt` rather than by preference. Recorded here because each one changes what lands in `manifest.yaml`, and a later reader must be able to see they came from the text.

**Delivery is one ECA, iterated by recipient.** `law.txt:11-12`: "the mayor — or the oldest person if there is no mayor yet — must make the ballot votes… **They** must put these papers in the mailbox of each citizen". The "they" is the mayor named in the same sentence, so delivery is the authority's duty and a citizen never holds it — which rules out one act per recipient with the citizen as holder. But "in the mailbox of *each* citizen" is an iteration, and the framework's own missing-ballot scenario needs a partial state to exist: *"WHEN the graph has 39 of 40 expected ballots delivered"*. A single bulk `deliver` could never produce 39 of 40. So one ECA, `holder_role: MayorRole`, one parameter naming the recipient and sourced `choices`. The duty stays the authority's; iterating it is what makes the shortfall expressible.

**The seed supplies blank sheets; `prepare` writes on them and mints none.** "must make the ballot votes… one paper per candidate for each citizen" is a creation, and its count depends on the registry at prepare time — unknowable at seed time. A per-citizen seed is not the answer either: three citizens and N candidates need 3N papers, not three, so the seed has to be a *supply* representing what the hamlet has in the drawer. If the registry needs more than the supply, `prepare` refuses naming the shortfall. That refusal is the honest edge rather than a workaround — how much paper a hamlet has is a fact about the hamlet, and `requisitions` draws the same lesson, drawing only `ph:Townhall` and nothing else.

**Delivery gets no phase of its own.** Both duties sit on "the 11th", inside `ph:CreateBallots`, so `deliver` names the same `eca_process` as `prepare`. A span from the prepare point to the election point would be expressible and would give delivery a real window — but declaring it asserts a date the law never states, which is the same error as naming an instrument.

**Writing and taking the ballot role are one act.** `law.txt:11-12` states making and delivery separately but nowhere separates the writing from the ballot. So `prepare` writes the inscription and confers the Role together, and the expressible intermediate state is written-and-undelivered rather than written-and-not-yet-a-ballot.

## Risks / Trade-offs

- **[Risk] `prepare` minting Role individuals reopens the freshness question**, since a Role IRI is a function of holder and situation, and the same sheet written for two candidates would need two Roles. → Mitigation: the Role names the sheet and the situation, not the candidate, so one sheet holds one Role in one election and the candidate is what that Role `denotes`. Two candidates on one sheet is then not expressible, which is correct — one paper per candidate is one sheet each.
- **[Risk] One supply of paper is reused by every election, so a sheet's marking and location are not per-election.** → Mitigation: neither is recorded per-election, deliberately. The marking is the sheet's present state and is re-written; delivery is on the Role, whose IRI is keyed by the occurrence, so a later election's ballots read undelivered rather than inheriting the last one's delivery. This was a live defect during implementation — delivery on the sheet made `allDistributed` pass on nothing after a repeat — and is the reason `ph:deliveredTo` exists at all.
- **[Risk] Splitting `prepare` changes the shipped law-swap proof for `law-simulation-tui`**, which loads this exact frozen set. → Mitigation: the TUI change has not started, and this gives it a second absent-ECA proof, so the dependency is now on a richer law rather than a different one. The re-freeze must land before the TUI builds.
- **[Risk] The law text does not say when delivery is due**, and the calendar has no span for it. → Mitigation: `deliver` is guarded by being after `prepare` and before polls open, both already declared days, so no new calendar node is needed. If a reviewer reads the law as requiring delivery by the prepare day, the calendar gains a deadline and this becomes a separate question.
- **[Risk] Seeding a sheet per citizen hardcodes a population shape** — the law's duty is one paper per citizen *per candidate*, so the seed is a lower bound and `prepare` must still mint. → Mitigation: the seed is of blank sheets and the minting is of written ones, so the seed fixes the paper stock and the registry fixes the count, and neither is a bound on the other. If a run nominates more candidates than sheets exist, `prepare` is refused naming the shortfall, which is the honest answer.
- **[Trade-off] `prepare` becomes a larger act**, since it now writes a Role and a quality per sheet rather than one list. Accepted: it is doing what the law says, and the work is bounded by the registry.
- **[Trade-off] Two laws' worth of vocabulary and behaviour land in one frozen set**, since this rewrite brings sheets, pens, and a delivery duty that the mayor baseline lacks. Accepted: the quorum flavour is already the richer law, and the TUI's law-swap claim depends on exactly that.

## Migration Plan

No data migration; no other case changes. The set is re-frozen and `law-simulation-tui` loads the re-frozen hash. Rollback is reverting `rules.lean`, `manifest.yaml`, `ontology.ttl`, and `population.ttl` to the prior frozen versions, at the cost of the law not doing what its text says.

## Open Questions

None outstanding. The three that were deferred here — whether delivery is one act or one per recipient, whether the sheets are seeded blank or minted outright, and whether delivery needs its own phase and calendar span — are answered in *Readings settled from the law text* above, and each answer quotes the words it rests on.

One is settled but not by the text alone, and is recorded because a later reader should know whose judgement it was:

- **What the graph does with a superseded marking.** The ruling is that a sheet is a reusable physical object, so its marking is present state and holds one name at a time; which candidate an earlier election's ballot carried is preserved by that election's Role, and the completed process individual does not need to keep the marking it used to bear. An implementation that recorded each election's writing separately would preserve more, and that surplus is the point: it is archive, not world, and it would put a second copy of a superseded fact beside the live one.