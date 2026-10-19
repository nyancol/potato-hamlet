# Design

## Context

See `proposal.md` (Why) for motivation. See `runtime-time-and-minting-contract` for the transformation semantics this change provides a stage for, and `mayor-quorum-transformation-rewrite` for the law that will use them. Four facts about the current layout shape the approach.

**The freeze is per-case and hashes exactly four files.** `scripts/freeze.py:28` sets `TRACKED = ["law.txt", "ontology.ttl", "population.ttl", "rules.lean"]` and digests them into `manifest.yaml`'s `freeze` field. The comment above it records that `population.ttl` was once omitted and that its omission silently dropped the seed from the hash — so the hash's completeness is already something this project has been bitten by once.

**Every declared class currently lives in one file per case.** `check_framework_invariants`, `check_grounding`, `check_tbox`, and `check_phase_reachability` all take the law's `og` alone, and `parse` is called once per artefact. Nothing in the gate currently merges two ontologies, so a shared file means every one of those checks needs a second graph.

**`mayor-quorum` declares five physical classes and seeds none.** `ph:Townhall`, `ph:Mailbox`, `ph:BallotBox`, `ph:ResultsBoard`, `ph:CandidateRegistry` at `ontology.ttl:110-117`, with zero individuals of any of them in `population.ttl`. `requisitions` declares its own small set. Two laws that both referred to a mailbox would declare two classes, and nothing in the gate would notice they should be one.

**The gate's type discipline is what makes "available" cheap.** `check_population` and the `apply`-response check both require every subject to be typed by a class the ontology declares. If the shared file is merged into the ontology graph at load time, that check keeps working unchanged for a subject typed by either source — which is why the shared vocabulary needs no exemption from the transformation requirement's input check.

## Goals / Non-Goals

**Goals:**
- One place a physical concept is declared, so two laws referring to a mailbox refer to the same class.
- No obligation on laws that have no physical concerns.
- A freeze that cannot verify while the vocabulary under it has moved.
- Keep the existing type discipline intact, so "available" costs no exemption.

**Non-Goals:**
- Rewriting any law, or seeding any physical individual. `mayor-quorum` still seeds none.
- The transformation semantics, which the prerequisite change lands.
- Deciding what belongs in the shared vocabulary by rule. The first version is seeded from what the three shipped laws' texts already name, plus what their texts obviously presuppose; growth is by a law declaring something the shared file lacks and it being recognised as generally useful.
- Any ontology-level guarantee that a law's text has been fully grounded in the vocabulary. That is an extraction-quality question, not a checkable property, and pretending otherwise would produce a check that passes vacuously.

## Decisions

**1. Available, not required, and the distinction is drawn at the point of obligation.** The framework already separates classes a consumer operates on from classes a law's text presupposes: `ph:Citizen`, `ph:Clock`, `ph:CalendarPoint`, `ph:CalendarSpan` are mandatory because `check_framework_invariants` fails a law that omits them. The physical vocabulary is the second kind. So it is not enforced by an omission check; it is available, and a law that references no physical concept passes without it. *Alternative considered:* require the vocabulary's classes in every law. Rejected: `requisitions` has no paper in its duties and would have to declare one, which is a seed to justify and cannot. Making a concept available where it is not wanted is the same error as requiring an ordering relation between phases — an obligation with no consumer.

**2. One shared file, resolved and merged at load, not copied into each case.** The vocabulary is a single Turtle file under a framework directory, with its own IRI base. `scripts/check.py` parses it once and merges it into the ontology graph every check already receives, so the existing checks see one graph and none of them changes shape. Each law's `ontology.ttl` references the shared classes rather than redeclaring them. *Alternative considered:* the extraction harness copying the relevant classes into each case's `ontology.ttl` at draft time. Rejected: it makes a law's frozen file look self-contained while its semantics depend on a copy that could drift from the original, and it hides the sharedness that is the entire point.

**3. The freeze hash covers the shared file, and the manifest names the version frozen against.** `TRACKED` gains the shared path, and `manifest.yaml` gains a field recording which version of the vocabulary the set was frozen against, so a case can be verified as frozen against the vocabulary it was reviewed with rather than whatever is current. This follows the lesson already recorded at `freeze.py:22-27`, where a tracked file was dropped from the hash and a freeze silently stopped being a freeze of the set. *Alternative considered:* hash the shared file's content into the existing `freeze` field with no separate record. Rejected: it verifies but does not say which vocabulary a reviewed law was reviewed against, so upgrading the vocabulary forces a blind re-freeze rather than an informed one.

**4. Type resolution merges the two graphs; the shared file does not become a second ontology.** Every check that resolves a subject's type takes the merged graph. A class declared in either source satisfies the "typed by a declared class" rule, so the transformation requirement's input check needs no exemption and no special case for shared-typed individuals. *Alternative considered:* require a law to re-declare the classes it draws on, so each file stays standalone. Rejected: that is a copy, and a copy is not a shared vocabulary — it is the current situation with more files.

**5. A law-local class colliding with a shared one is reported, not failed.** A law that declares `ph:Mailbox` locally when the shared file has one is almost certainly a law written before the vocabulary existed, or a draft that failed to notice it. Failing would break the two shipped laws on day one for no benefit, since both currently work. So the gate reports the collision and names both, and the shared class does not silently win. *Alternative considered:* fail on collision. Rejected for now on the grounds that it blocks the prerequisite work; it becomes the right behaviour once the shipped laws have been migrated, and that migration is this change's own tasks.

**6. The escape hatch is deliberate: a law declares what the vocabulary lacks, and that is where sharing ends.** A law whose text presupposes something undeclared declares it locally, which is correct — the alternative is growing a shared vocabulary to anticipate every noun any governance text might contain, which would make the shared file a superset of all laws rather than a stage they perform on. The cost is that such a concept is that law's alone, and a second law needing it will declare its own. *Alternative considered:* require a law to propose additions to the shared file for review. Rejected as too heavy for a single occurrence — it turns "I need a concept" into a framework change, which is the friction that would push authors back to declaring locally anyway. Worth revisiting if the same local class appears across laws.

**7. Objects, actions, and capabilities are declared together, because an object with nothing performable on it is not a stage.** The vocabulary holds nouns, the verbs that act on them, and the capabilities that qualify an object for a verb. Writing a name on a sheet makes it a ballot; placing that sheet in a box makes it a cast vote. Both are the same sheet taking a Role in a different situation, and both are the same physical gesture under a law's reading of it. If the vocabulary supplied only nouns, every law would have to invent its verbs as well, and two laws that both write on paper would end up with unrelated ways of saying so — reintroducing exactly the per-law vocabulary this change exists to remove.

Capabilities are the third category because an act needs to say what qualifies an object, and the honest answer is a kind rather than an object. `ph:Inscriptible` and `ph:Inscribable` name instruments and surfaces; a law's act says its instrument must be of a kind that may inscribe, which a hamlet full of pencils satisfies as well as one full of pens. Without the third category the act would name a class of object, and that is the law making a choice its text left open.

This is what makes the physical layer a stage rather than a prop cupboard. The distinction the framework draws is between the gesture, which is shared, and the meaning, which is the law's — and drawing it in the shared file is what keeps the two from collapsing. A law's ontology adds no physics: it names what the gesture constitutes in its own process and leaves the gesture itself alone. *Alternative considered:* declaring actions per law. Rejected: that is the current situation with an extra layer, and it means two laws' writing actions are unrelated despite being the same human act.

**7a. An action is a `gfo-core:Process`, and a law's process specialises it.** An action is something-happening — a hand moves, ink is dispensed, paper is altered — and a GFO Process is what something-happening is. A `gfo-light:Relator` is a truthmaker that binds relata in a state and does nothing itself, which is the wrong category for something an actor does. So `ph:PhysicalAction`, `ph:Inscribe` and `ph:Deposit` are Processes, and `ph:actedOn` / `ph:actedWith` / `ph:placedIn` are grounded over `gfo-core:hasParticipant` rather than `gfo-light:relates`: the thing acted on, the instrument used and the container entered are the things *taking part* in the process.

This is what makes the two levels coexist, and it replaces an earlier draft that made actions Relators on the grounds that a Process would have to be reachable from a law's root. A law's own process is a **specialisation** of the shared one — `ph:CastVote rdfs:subClassOf ph:Deposit` — so in `mayor-quorum` a physical `Deposit` has a sheet of paper going into a box while the legal `CastVote` has a ballot vote going into a ballot box. Two processes, two sets of participants, the same moment, related by the transformation rather than by a shared class. A subclass is enough to ground the shared action, so the reachability and orphan checks accept a Process that a reached Process specialises into; and because "available, not required" applies to Processes as much as to objects, both checks are scoped to the classes the **law itself** declares, so an unused shared action is framework vocabulary rather than a defect in this law. The gate is narrowed by scope, not by silence: a stray law-declared Process is still refused, including a stray subclass of a shared action.

**7b. A capability is a `gfo-light:Quality`, not an `Object`.** The same category correction one level down, and the first draft got it wrong. What "inscriptible" names is not a sort of thing; it is a qualification a thing may have. Declaring it an Object made `ph:Mailbox rdfs:subClassOf ph:Container` say a mailbox *is* container-ness rather than that it *has* the quality of being a container — and a mailbox is not a kind of abstract qualification, it is a thing you put letters in.

So the three qualification kinds are pure Qualities under `ph:PhysicalCapability`, and each concrete thing is declared an `Object` and inherits the qualification it bears. That is the reading GFO intends and the one the existing relations already assume:

```
  ph:PhysicalCapability  ⊑ gfo-light:Quality        (the quality itself)
  ph:Inscriptible        ⊑ ph:PhysicalCapability    (a qualification, not a sort)
  ph:Inscribable         ⊑ ph:PhysicalCapability
  ph:Container           ⊑ ph:PhysicalCapability

  ph:Sheet               ⊑ gfo-light:Object , ph:Inscribable    (an object, and)
  ph:Mailbox             ⊑ gfo-light:Object , ph:Container      (a bearer of it)
  ph:ResultsBoard        ⊑ gfo-light:Object , ph:Inscribable
```

`ph:PhysicalCapability` stays the root the narrowing check looks under, so a new qualification still needs no code change — and the check still distinguishes a qualification from a named kind, which is the distinction the whole requirement turns on.

**8. A capability is a class, not a restriction, because OWL restrictions cannot express the exclusion that matters.** The question worth answering properly is whether "a pen may write on a sheet" can live in the ontology. It cannot, and the reason is specific: `owl:some` requires that *a* qualifying object be involved and cannot say that one object qualifies and another does not. So `ph:Pencil rdfs:subClassOf [ ph:actedOn some ph:Inscribable ]` is expressible and is almost useless — a reasoner could derive that a pencil is used on *some* surface while nothing stops it concluding the same of a chisel. And no ontology in this project currently uses a restriction at all: all three declare only `rdfs:subClassOf` against named classes plus properties with domain and range, partly because `law-extraction` requires every `ph:` property grounded in GFO.

So the pairing is evaluated per act instead, in three layers that each own one question:

```
  1. CAPABILITY    "inscribing" is a kind of instrument   -> ph:Inscriptible  (schema)
     "inscribable" is a kind of surface                   -> ph:Inscribable   (schema)

  2. COMPATIBILITY  does THIS instrument work on THIS surface?
                    -> the oracle, per act, against the seeded instances

  3. MEANING        writing this on it makes it a ballot in this election
                    -> a Role in the law's own process  (already settled)
```

The schema answers what kinds exist, the oracle answers what works here, and the law answers what it means. Nothing is lost by the first layer not answering the second, and the alternative — freezing a judgement about the physical world into the file that gets reviewed and hashed — would be the same error as asserting an ordering relation between phases. *Alternative considered:* express the pairing with `owl:some` restrictions and let the reasoner decide. Rejected on the negation argument above, and it would be the first restrictions in these ontologies, so it would also arrive untested.

**9. The first version of the vocabulary is seeded from what the shipped texts already name.** Rather than a designed taxonomy, it starts as the union of physical nouns, gestures, and capabilities the three laws' texts use and the classes they already declare locally, deduplicated — `ph:Townhall`, `ph:Mailbox`, `ph:BallotBox`, `ph:ResultsBoard`, plus what the texts presuppose without declaring: paper, an instrument that may inscribe, the dwelling that has a mailbox, and the two gestures those objects exist for. Note the seed says *an instrument that may inscribe* and not *a pen*: `mayor-quorum/law.txt:11-12` says to "make the ballot votes" and have people "write their name", and never names what to write with, so the vocabulary must not either. Growth is thereafter by recognition, not by design. *Alternative considered:* designing a principled physical ontology up front. Rejected: three laws' texts are a thin basis for a taxonomy of everything physical, and a designed one would encode assumptions about what governance is about that the project's whole point is to leave to the law text.

**AMENDED — the growth rule is a coverage target, not "recognition only".** The reasoning above conflated two different things: *what a law's text names*, which governs what a law **requires**, and *what the file may offer*, which is a shared library's whole purpose. A vocabulary sized to the three shipped laws is not a stage to perform on; it is a superset of those laws, and a fourth law naming "pencil" would have to invent one. So the vocabulary MAY declare named kinds beneath a capability it already declares — `ph:Pen` and `ph:Pencil` under `ph:Inscriptible` — and the `law-extraction` requirement now says so.

What does **not** change, and is the part that mattered: a law still qualifies by the **capability**, never by a kind, unless its own text names one. Both election laws declare `requires: [{class: Inscriptible }]` and are satisfied by a hamlet stocked with a chisel. The gate's instrument-narrowing report is what keeps this honest, and it is silent for a capability exactly as it is loud for a kind. Offering kinds therefore costs a law nothing and saves the next one a declaration. Waiting for a law to name a kind before the file offers it is the friction decision 6 already rejects, where "I need a concept" becomes a framework change.

Still refused: a kind with no capability above it, and any OWL restriction attaching a capability to a class — decision 8's reason is unaffected by this amendment.

## Risks / Trade-offs

- **[Risk] The shared file now makes claims about what instruments exist and what they do**, which is a further kind of commitment from naming a mailbox. → Mitigation: keep the capability list to what a shipped text forces — a kind that may inscribe, a kind that may be inscribed — and add only when a law's own words cannot be acted on without it. A capability class names a kind and stops there; it deliberately does not enumerate which physical objects have it, so the file commits to a vocabulary rather than to an inventory.
- **[Risk] The compatibility check has no home in the schema**, so "this instrument cannot inscribe" lives only in the oracle and a law could disagree with the oracle's judgement without anything noticing. → Mitigation: the capability requirement is declared per ECA in the manifest rather than being implicit in a property, so the requirement is readable and a law that requires a narrower kind says so visibly. The judgement of whether a given instrument qualifies is the oracle's, as it already is for whether a duty is due.
- **[Risk] The vocabulary grows into a dumping ground**, since any concept a law needs and does not find is a candidate for adding. → Mitigation: the local escape hatch means there is no pressure to add speculatively, and the gate reports local declarations of concepts the shared file covers, so growth is visible and reviewable rather than silent. The discipline that keeps it a stage rather than a catalogue is reviewing each addition as "is this generally true of governance texts", not "does a law need it".
- **[Risk] Merging two graphs weakens the existing checks**, since a class the law never declared would now satisfy a type check. → Mitigation: no check becomes weaker, because each was already asking whether a subject's type is *declared somewhere the law can reach*, and the shared file is somewhere the law can reach. The risk is a law depending on a shared class it did not intend to, which the extraction prompt's naming requirement makes visible at review.
- **[Risk] Two ontologies in one graph is the kind of change that quietly breaks a mirror-by-name rule** — the profile requires every `ph:` class to have a same-named Lean counterpart. Shared classes have no Lean counterpart in any one law's `rules.lean`. → Mitigation: the mirror rule applies to a law's own declarations; a shared class is resolved from the shared file and its counterpart, if any, is not required per law. This needs stating in the profile, and it is the single most likely place for this change to cause an obscure failure.
- **[Risk] The freeze now depends on a file outside the case directory**, so a case is no longer self-verifying from its own directory. → Mitigation: the manifest records the shared version, so verification can say *which* vocabulary moved rather than only that something did. The cost is that verifying a case requires the vocabulary to be present.
- **[Trade-off] Availability means a law can be written with no physical grounding at all and pass**, since nothing requires it to draw on the vocabulary. Accepted: requiring grounding would need a completeness check over natural language, which cannot be made sound, and a check that cannot fail is worse than no check. The signal that a law has duties with nothing to perform on is left to review.

## Migration Plan

No data migration; no `population.ttl` changes. The shared file is added and reviewed, the two laws' ontologies are edited to reference rather than redeclare, and all sets are re-frozen with the shared version recorded. Rollback is deleting the file and reverting the ontology edits, at the cost of the freeze no longer covering a shared artefact that does not exist.

## Open Questions

- **Should a shared class be required to be in every law that references it, or may a law reference it without declaring the reference?** As stated the reference is implicit — the law simply uses the IRI. An explicit declaration would make the law's dependence auditable from its own file, at the cost of a line per concept used. Deferred: it is a readability choice, and the merged-graph approach works either way.
- **What is the growth rule for the shared file?** This change seeds it and leaves additions to review judgement. Whether an addition needs one law or two is undecided, and two is the cheaper bar but slower to clear.