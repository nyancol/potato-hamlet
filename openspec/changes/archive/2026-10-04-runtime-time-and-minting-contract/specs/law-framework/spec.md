# Spec Delta

## MODIFIED Requirements

### Requirement: Ontology profile grounded in GFO-light

Artefact ontologies SHALL subclass GFO-light/GFO-core categories (Object, ObjectAggregate, Role, Relator, Quality, InformationObject, Process, State, SituationAggregate) with mirror-by-name Lean counterparts, and every simulatable entity SHALL carry an `rdfs:label` for display.

Every law SHALL additionally declare the framework-invariant classes without which a law-agnostic consumer cannot operate: `ph:Citizen` as a subclass of `gfo-light:Object` whose every individual carries `rdfs:label` and a `ph:age` value; `ph:Clock` as a subclass of `gfo-light:TimeBoundary` carrying `ph:dayIndex` and `ph:atHour`; `ph:CalendarPoint` as a subclass of `gfo-light:TimeBoundary` carrying `rdfs:label`, `ph:atDate`, `ph:dayIndex`, and `ph:marksPhase`; and `ph:CalendarSpan` as a subclass of `gfo-light:Chronoid` related to its bounding `ph:CalendarPoint`s and optionally carrying `ph:marksPhase`. `ph:atDate` SHALL be a subproperty of `gfo-core:dateTimeValue`, and `ph:age`, `ph:atHour`, and `ph:dayIndex` SHALL be subproperties of `gfo-core:decimalValue`. `ph:atHour` and `ph:dayIndex` SHALL each declare `rdfs:domain gfo-light:TimeBoundary`: a day index names a moment, so it belongs on `ph:Clock`, on a `ph:CalendarPoint`, and on the bounds the oracle mints, and on no other individual. A process instance, an occurrence, or a span carries no position of its own, because a second copy of the present is a second source for a fact the framework already fixes.

A law SHALL declare as `owl:FunctionalProperty` every `ph:` property whose encoding is single-valued, including the flags, the outcome, the status, the index, and the moment properties of a bound. A property that may hold more than one value for one subject SHALL NOT be declared functional, such as `ph:marksPhase`, which one moment may carry for several phases. The declaration is what makes re-encoding a no-op rather than an accumulation, so a property the oracle rewrites on every act SHALL be functional unless it is deliberately set-valued.

Every law SHALL declare the relationships between its Process classes, each grounded in GFO rather than reusing a GFO property directly. Grounding SHALL be by `rdfs:subPropertyOf` where the relation coincides with a GFO one, and by GFO `rdfs:domain`/`rdfs:range` where GFO has no such relation but the types are knowable. A property may not be declared as a subproperty of a GFO relation it does not coincide with, even where the direction or the object type differs: `ph:hasPhase` over `gfo-core:hasSituationPart` for decomposition, `ph:hasParticipant` over `gfo-core:hasParticipant`, `ph:hasTime` over `gfo-core:timeOf`, `ph:relates` and `ph:containsRole` over `gfo-light:Relator`, and `ph:qualityOf` over `gfo-light:qualityOf`, with roles related by `roleIn` and `playedBy`.

Each Process class SHALL name its constituent phases through `ph:hasPhase` as a plain class-level assertion. Every Process class a law declares SHALL be reachable from a declared root Process through that relation, and every phase SHALL be marked by a `ph:CalendarSpan` carrying `ph:marksPhase`. A law SHALL NOT declare a Process class that no ECA, root, or other phase refers to.

Process instances SHALL take their temporal bounds in GFO's shape: an instance relates to a `Chronoid` by `ph:hasTime`, and that `Chronoid` carries `gfo-core:temporallyStartedBy` and `gfo-core:temporallyFinishedBy` pointing at `TimeBoundary` individuals. A `TimeBoundary` SHALL NOT be attached directly to a situation in place of a `Chronoid`. Absence of a start bound SHALL denote an instance that has not begun.

The ontology SHALL be a frozen schema of classes and properties only. Individuals SHALL NOT appear in it. Individuals that a law starts from SHALL live in a sibling `population.ttl` in the same case directory, in the same RDF serialisation as the schema, and individuals created during simulation SHALL be minted into the runtime knowledge graph. Both kinds SHALL carry labels through a `ph:label` property that the ontology declares as a subproperty of `rdfs:label`. Because the schema is frozen while the individuals in the runtime graph are not, freezing bounds the vocabulary of minting and not its extent: a law SHALL declare every class it will ever mint, and nothing bounds how many instances of those classes may come to exist.

The framework SHALL NOT fix who holds a duty when no office is filled, and SHALL NOT require every law to distinguish a time-scoped phase from a stateful per-occurrence entity: both are Process instances and differ only in cardinality and nesting.

#### Scenario: Mayor ontology validates
- **WHEN** the mayor `ontology.ttl` declares Citizen as `gfo-light:Object`, MayorRole as `gfo-light:Role` with `roleIn` + `playedBy`, and election phases as `gfo-core:Process`/`State`
- **THEN** OWL parsing plus the GFO-light consistency check passes and each class has a same-named Lean type

#### Scenario: Missing label rejected
- **WHEN** an ontology individual lacks `rdfs:label`
- **THEN** the Step 1 review gate fails with the offending IRI named

#### Scenario: Cycle individual validates
- **WHEN** the quorum ontology declares cycle date properties on `ph:MayorElectionCycle` and a cycle individual carries its label plus concrete day values
- **THEN** OWL parsing plus the GFO-light consistency check passes and the TUI resolves the cycle name by IRI lookup without date arithmetic

#### Scenario: Missing cycle label rejected
- **WHEN** a cycle individual lacks `rdfs:label`
- **THEN** the review gate fails with the offending IRI named, as for any simulatable individual

#### Scenario: Law omitting a framework invariant is rejected
- **WHEN** an ontology omits `ph:Citizen`, `ph:Clock`, `ph:CalendarPoint`, or `ph:CalendarSpan`, or omits the GFO superclass or subproperty grounding for any of them
- **THEN** the review gate fails naming the missing or ungrounded declaration, and the set is not freezable

#### Scenario: Frozen ontology carries no individuals
- **WHEN** a case's `ontology.ttl` declares a citizen, calendar point, or process individual
- **THEN** the review gate fails and names the offending IRI, directing the author to declare the class in `ontology.ttl` and the seeded individual in `population.ttl`

#### Scenario: Authority is law-determined
- **WHEN** two laws both leave a duty unheld by an office holder and resolve it to different citizens
- **THEN** each resolves per its own rules with no framework rule naming oldest, youngest, or any other fallback, and neither law requires a framework declaration to do so

#### Scenario: Calendar-to-phase grounding is by type
- **WHEN** a law declares a relation from a calendar node to the Process phase it bounds
- **THEN** it is grounded by declaring `gfo-light:Chronoid`/`gfo-light:TimeBoundary` as its domain and `gfo-core:Process` as its range, and is not declared as the inverse of `gfo-core:hasTime`, because that relation's object is an individual while a frozen shared calendar can only name a phase class

#### Scenario: Declared hierarchy is readable structure
- **WHEN** a consumer loads an ontology in which `ph:MayorElectionCycle` declares `ph:hasPhase ph:SelfNomination`
- **THEN** it reports nomination as a constituent phase of the election without knowing which law it is reading and without consulting the manifest

#### Scenario: Unreachable Process class rejected
- **WHEN** a law declares a Process class that no root Process reaches and no ECA refers to
- **THEN** the review gate fails naming the orphan class

#### Scenario: Phase without a calendar span rejected
- **WHEN** a law declares a phase that no `ph:CalendarSpan` marks
- **THEN** the review gate fails naming the phase, so no process structure exists that the law never scheduled

#### Scenario: Lifecycle bounds take the Chronoid shape
- **WHEN** a process instance carries temporal bounds
- **THEN** they reach a `Chronoid` by `ph:hasTime` whose start and finish point at `TimeBoundary` individuals, and the gate rejects a `TimeBoundary` attached directly to the situation

#### Scenario: Absent start bound means not begun
- **WHEN** a process instance exists with no start bound on its `Chronoid`
- **THEN** a consumer reports it as initialised and awaiting its trigger rather than as ongoing

#### Scenario: Overlapping phases need no causal chain
- **WHEN** the nomination window overlaps both announce and prepare
- **THEN** a consumer derives that overlap from the `Chronoid` bounds of their calendar spans, and the ontology needs no ordering relation between the phases

#### Scenario: A position outside a moment is rejected
- **WHEN** an individual that is not a `gfo-light:TimeBoundary` carries `ph:dayIndex` or `ph:atHour`
- **THEN** the review gate fails naming the subject and the property, because a process instance or a span holds no present of its own

#### Scenario: Functional properties are declared
- **WHEN** a law's oracle re-encodes a property on every act
- **THEN** the ontology declares it `owl:FunctionalProperty`, so a consumer can tell a re-encoding from a second value, and a property that may hold several values for one subject is not declared functional

#### Scenario: An undeclared functional property is caught
- **WHEN** a draft declares a single-valued property such as a flag or an outcome without `owl:FunctionalProperty`
- **THEN** the review gate fails naming the property, since its idempotent encoding cannot be checked

#### Scenario: Freezing bounds vocabulary, not extent
- **WHEN** a law declares the classes it will mint and then mints many instances of them over a long run
- **THEN** the set stays freezable because no new class appeared, and a class the law would need but did not declare is a review failure rather than a runtime surprise

### Requirement: Nat-day time model

Laws SHALL express time as `Nat` days plus hour integers, with named day arithmetic per cycle (election day, announce day = election day minus 10, prepare day = election day minus 1, polls 9am-7pm on election day). Periodic recurrence SHALL be a Nat function of the cycle index (e.g. election year = 2027 + 4k). Quorum repeats SHALL derive per-repeat dates as a Nat function of the repeat index (`E(k+1) = E(k)+30`, announce at `E-10`, prepare at `E-1`, polls 9am-7pm on E-day). Repeats SHALL NOT shift the 4-year election clock; they only shorten the mandate in office.

Each law SHALL name its calendar as `ph:CalendarPoint` and `ph:CalendarSpan` individuals. A node whose position is fixed when the law is reviewed SHALL co-locate a human-readable `ph:atDate` with the `ph:dayIndex` a consumer compares against, so a consumer can display a date without computing one. A span whose end falls a fixed interval after a moment that does not exist until the simulation runs SHALL instead carry `ph:gapDays` and no absolute position, because the law has fixed the interval and left the moment to be resolved; such a span names no day, and the oracle resolves it into concrete points when it accepts the act that schedules the work. A span that bounds a phase SHALL carry `ph:marksPhase` naming it.

The current position SHALL be carried by a single `ph:Clock`, whose `ph:dayIndex` and `ph:atHour` names are fixed by the framework rather than declared per law, and no other individual in the graph SHALL carry the current position. A process instance's own schedule SHALL follow from its declared index and the law's named day arithmetic, never from a position stored on the instance; where a consumer needs to know how far an instance has got, it reads the instance's `Chronoid` bounds and its flags, which record moments rather than a present. Because `ph:Clock` and `ph:CalendarPoint` share `ph:dayIndex`, the current calendar position SHALL follow from ordering a law's calendar points against the clock, with no law-specific comparison logic.

The clock SHALL be the runtime's one write into the graph. Only the runtime advances it, and it SHALL advance the clock monotonically: a consumer SHALL NOT move it to an earlier day or hour than the one the graph already carries. Totality over absurd values and monotonicity are separate guarantees. Totality says no value can crash the oracle. Monotonicity says no value can contradict a recorded moment, since a clock moved back would let a period a law has already closed reopen and admit an act into a process that has finished.

The frozen calendar is a seed rather than a ceiling. A law SHALL be able to mint further `ph:CalendarPoint` and `ph:CalendarSpan` individuals into the runtime graph during simulation, so that a process which schedules work at a moment not fixed when the law was reviewed still has a calendar the consumer can display. A minted point SHALL carry the same declared properties as a seeded one, including `ph:dayIndex`, `ph:atHour` where the moment has an hour, and, where it bounds a phase, `ph:marksPhase`; a minted span SHALL carry the same declared properties as a seeded one, which for a span in the relative form means `ph:gapDays` and no absolute position. Its IRI SHALL satisfy the freshness rule. Only Lean SHALL compute the date and day index a minted individual carries; a consumer SHALL NOT derive either.

Sequencing and overlap between phases SHALL be derivable from calendar bounds alone. No ordering relation SHALL appear between phases, because a chain of such relations cannot express two phases running at once and the calendar already answers ordering and overlap from one source.

A seed describes what the law permits and not how the oracle works out a moment. A seeded individual SHALL NOT carry a value whose purpose is to let a consumer reproduce a computation the oracle owns, and a seeded individual SHALL NOT state what an interval is measured from, because the method is the oracle's and declaring it puts the computation back into the artefacts. Where a law fixes an interval, it appears once as the interval on the calendar node that bounds the phase, and the moment it resolves to is computed by Lean when the act that needs it is accepted, whether that is the instance's initialisation or a later trigger.

#### Scenario: Election dates derive correctly
- **WHEN** cycle index 0 denotes the 2027 election
- **THEN** announce day, prepare day, and poll hours compute to Jan 2, Jan 11, and 9-19 on Jan 12 respectively

#### Scenario: Repeat dates derive per index
- **WHEN** the void election sits at E-day 10
- **THEN** repeat index 1 computes to E-day 40, announce day 30, prepare day 39, and polls 9am-7pm on day 40

#### Scenario: Four-year clock unaffected
- **WHEN** two repeats slip the 2027 election into March
- **THEN** the 2031 election date is unchanged

#### Scenario: Calendar resolves without date arithmetic
- **WHEN** a law declares a calendar point with `ph:dayIndex 0` and `ph:atDate "2027-01-02"` and the clock reads `ph:dayIndex 0`
- **THEN** a consumer displays that point's label and date read straight from the ontology, computing no calendar arithmetic

#### Scenario: Clock names need no per-law declaration
- **WHEN** a law is loaded by a consumer that reads only the framework-fixed `ph:dayIndex` and `ph:atHour` on `ph:Clock`
- **THEN** the consumer advances and reads the clock for that law with no law-specific field mapping

#### Scenario: Overlapping phases ordered by bounds
- **WHEN** two phases' calendar spans cover overlapping day ranges
- **THEN** a consumer reports both as running concurrently, deriving it from the bounds alone with no ordering relation in the artefacts

#### Scenario: Calendar grows as a process unfolds
- **WHEN** a law mints a further calendar span into the runtime graph for work it schedules at a moment not fixed at review
- **THEN** the span carries the same declared properties as a seeded one, resolves a date and a day index for display, and the consumer adds it to the displayed calendar without any law-specific handling

#### Scenario: Only Lean dates a minted calendar individual
- **WHEN** a minted calendar span appears in the graph
- **THEN** its `ph:atDate` and `ph:dayIndex` were computed by the oracle, and the consumer displays them without deriving either

#### Scenario: Advancing the clock moves every law
- **WHEN** a consumer writes a new `ph:Clock` day and hour into the graph of any conforming law and then calls `check`
- **THEN** the verdict reflects the new position, so the clock is the position for every law rather than for those whose shape happens to keep one, and no consumer needs to know how many places a given law records the day

#### Scenario: A process instance holds no position
- **WHEN** a law's oracle derives the current phase by comparing a moment against a process instance's schedule
- **THEN** the schedule comes from the instance's declared index and the law's day arithmetic, and no individual other than `ph:Clock` carries the present

#### Scenario: The clock does not move backwards
- **WHEN** a consumer sets the clock to an earlier day or hour than the graph already carries
- **THEN** a law whose conditions derive from the clock treats the recorded periods as they stand, so a period already closed cannot reopen

#### Scenario: A span whose end is relative names no day
- **WHEN** a law declares a span bounded by an interval after a moment that only exists once the simulation runs
- **THEN** the span carries `ph:gapDays` and no `ph:dayIndex` and no `ph:atDate`, so the frozen calendar does not assert a day that differs for each occurrence, and the oracle resolves the concrete points when it schedules the work

#### Scenario: A seed states no anchor for an interval
- **WHEN** a seed declares a span carrying `ph:gapDays`
- **THEN** nothing in the seed says what the interval is measured from or how the moment is derived, because the method belongs to the oracle and a declared anchor would put the computation back into the artefacts

#### Scenario: A seed value nothing reads is rejected
- **WHEN** a seed carries a property that no condition, guard, or verdict of the law consults, such as an interval held on a process instance that the oracle holds as a constant of its own
- **THEN** the review gate fails naming the property and the individual carrying it, since a value that duplicates the oracle's own arithmetic is a second source for a fact rather than a description of what the law permits

### Requirement: ECA metamodel with bounded FOL subset

Each law SHALL declare its dynamics as ECA rules with Event (clock tick or act), Condition over a state snapshot, Action transition, duty-holder role, deadline, modality (should vs must, preserved from the source text), and display message. Conditions SHALL use only the framework FOL subset: universal/existential quantification over finite sets, counting, Nat comparisons and arithmetic. The Action leg SHALL have an executable encoding: one pure transition function per ECA taking a snapshot to a snapshot (or a rejection reason), guarded by the same conditions the oracle checks, with actions addressed as data (ECA id plus parameters) over JSON. Quorum flavors SHALL declare `repeat` as a first-class ECA whose holder is the authority (mayor-or-oldest, same `authorityId` as announce/prepare/count/proclaim), whose modality is `must`, and whose message names the scheduled successor.

An ECA's parameters and duty-holder role SHALL be declared so that a consumer can build a complete act without law-specific code. Each ECA SHALL carry a `holder_role` naming a Role class, and each parameter SHALL name a wire field, the Role class it binds, and a source drawn from the closed set `selected` (bound to the acting citizen) or `choices` (supplied by the oracle). Every declared Role SHALL be one the ontology declares as participating in that ECA's Process class. Holders SHALL be read from oracle verdicts; a consumer SHALL NOT compute, infer, or default who holds a duty.

An ECA's `eca_process` SHALL name a Process class appearing in the law's declared `ph:hasPhase` hierarchy. An ECA whose action may bring a new Process instance into being SHALL declare the Process class it creates, so that starting a process is distinguishable in the artefacts from any other act. The declaration names the class to look for once the act is accepted; it does not promise that an individual appears, because which individuals exist follows from the state rather than from the declaration.

Causality SHALL be expressible where it is structural and SHALL NOT be duplicated where it is evaluated. A `ph:causedBy` relation, declared as a subproperty of `gfo-core:causedBy`, MAY relate a Process to a `gfo-core:State`, with the Process as subject and the State as object, stating that the situation the State holds can bring about a change in that Process. The direction follows `causedBy`'s own sense: the relation's subject is what is affected. Such a relation is read without evaluation: it says the dependency is permitted, not that it has occurred. Whether the State actually holds, and whether it therefore triggers the change, SHALL be evaluated only by the ECA's Lean guard. The ontology and manifest SHALL NOT carry an ordering relation between phases, and SHALL NOT carry a relation asserting that a causal dependency has in fact fired.

#### Scenario: All-ballots condition expressed
- **WHEN** the rule "authority must distribute one ballot per candidate to every citizen" is encoded
- **THEN** it reads as a finite universal over citizens and candidates with an existential over delivered ballots, decidable in Lean and evaluable by the oracle

#### Scenario: Modality preserved
- **WHEN** the source text says the authority "should communicate" (announce) but "must create" (ballots)
- **THEN** the two ECAs carry modality should and must respectively, and the guide conveys the difference instead of flattening both to obligations

#### Scenario: Prepare transition executable
- **WHEN** the driver requests the prepare act on a snapshot where prepare is due and an authority holds office
- **THEN** the transition returns a snapshot with the prepared flag set and the full citizen-by-candidate ballot set marked delivered, instead of only reporting that prepare is pending

#### Scenario: Repeat duty owned by authority
- **WHEN** a snapshot shows a void cycle (polls closed, counted, quorum failed) and an authority holds office
- **THEN** the repeat ECA fires with that citizen as holder and modality `must`

#### Scenario: Act parameters build a complete act
- **WHEN** a consumer loads a law whose vote ECA declares a voter parameter sourced from `selected` and a candidate parameter sourced from `choices`
- **THEN** it builds a vote act bound to the acting citizen and to a candidate the user picks, with no law-specific parameter code

#### Scenario: Declared roles checked against the ontology
- **WHEN** a manifest declares an ECA's `holder_role` or a parameter role that the ontology does not declare as participating in that ECA's Process class
- **THEN** the review gate fails naming the undeclared role

#### Scenario: ECA outside the declared hierarchy rejected
- **WHEN** a manifest names an `eca_process` the ontology's declared `ph:hasPhase` hierarchy does not contain
- **THEN** the review gate fails naming the undeclared Process class

#### Scenario: Causal trigger readable, evaluation in Lean
- **WHEN** a law makes an act conditional on a State arising, such as a candidate withdrawing during polls
- **THEN** the ontology declares a `ph:causedBy` relation whose subject is that Process and whose object is that State, a consumer can read that the dependency is permitted, and whether the State holds and so triggers the change is decided only by the Lean guard

#### Scenario: Ordering between phases is never asserted causally
- **WHEN** one phase follows another in the law
- **THEN** no ordering relation between them appears in the ontology, their sequence following from calendar bounds alone

#### Scenario: A fired causal dependency is not asserted in the artefacts
- **WHEN** a causal trigger has actually occurred
- **THEN** the ontology and manifest are unchanged, because they state what may happen rather than what did, and only the graph and the verdict record that it happened

#### Scenario: Starting a process is distinguishable
- **WHEN** an ECA's action may bring a Process instance into being, such as scheduling a repeat election
- **THEN** the manifest declares which Process class the act creates, so a consumer can tell a process-starting act from any other and knows which class to look for afterwards

### Requirement: OWL-Lean correspondence and snapshot identity

The snapshot SHALL be the knowledge graph itself: the set of typed individuals describing the simulated world. `check` and `apply` SHALL take that instance graph and Lean SHALL derive its state from it, so there is one representation of the world rather than a JSON state object plus a parallel graph. The ontology's class declarations SHALL be the snapshot's schema; every subject in the graph SHALL be typed by a class the ontology declares. Snapshot entity ids SHALL equal the entity IRIs, so ontology-declared entities, graph individuals, and Lean records denote the same entity. Every ECA action SHALL reference a GFO Process class, every post-state a GFO State class, and every holder a Role class.

The graph SHALL be total over the world: every fact a condition, a guard, or a verdict can read SHALL be expressible as triples in the graph. Nothing a law can decide SHALL live only inside the oracle, because an individual the graph cannot name is an event no consumer can display and no audit can reach. The graph after a sequence of accepted acts SHALL be a function of the seed graph, that sequence, and the clock positions supplied along the way, so a session's graph can be persisted and resumed exactly, and the clock is its only free variable.

The graph SHALL carry both the ongoing process instance and every historical instance of the same Process class. A historical instance SHALL carry a finish bound and an outcome, and the current instance SHALL follow from the absence of a finish bound rather than from an ordering convention such as "the current cycle is the last element" — the wire format is an unordered list of triples, so a position in it carries no meaning to consume. Absence of a START bound denotes a different and equally declared fact: an instance initialised and awaiting its trigger rather than one that has begun. Nothing derived from the graph SHALL depend on the order its triples are sent in, which includes which individual a witness names and in what order a set of references is listed.

No transition SHALL remove an individual from the graph. Once an individual exists — a vote cast, a nomination made, a ballot delivered — it persists for the remainder of the simulation, and no ECA SHALL delete, retract, or overwrite its existence. What a later rule MAY affect is only how that individual is counted: when a process instance is finished with an outcome that does not count its contributions, such as an election stopped part-way through polling, the instance's outcome SHALL record that those contributions do not count toward any result. Erasure is not a power a law lacks by policy; it is not a power a law has. This preserves the audit trail the graph exists to provide, and makes a cancelled process reachable by the same path as any other finished instance rather than a special case.

Non-removal is the weaker half of what the graph guarantees, and the stronger half SHALL hold with it: the returned graph re-encodes the state, and re-encoding an individual whose value has not changed SHALL emit no triple for it. Every accepted act materialises the whole state, so without stability a single-valued property rewritten on each act would accumulate a fresh value each time, and a consumer following a `Chronoid`'s bound could not tell which moment it was reading.

A `Chronoid` carries one start and one finish, so the moment an intermediate period within a process's life closed SHALL NOT be assumed to be recorded. Where a law needs that moment it SHALL declare a property for it and write it, which is an ordinary declared fact like any other; where it declares none, the moment is not in the graph. A consumer SHALL NOT reconstruct such a moment from a flag or from a calendar node, so a law that declines to record one is making a lawful choice rather than leaving an oversight — and a law that records one is not obliged to, so no framework vocabulary names the concept.

Identity SHALL hold across the graph, the verdict, and the seed for entities minted during simulation as well as seeded ones, and every entity's label SHALL resolve through the graph by IRI. A verdict and a rejection SHALL each reference the IRIs the graph already uses.

#### Scenario: Identity round-trips
- **WHEN** a consumer loads `ph:citizen/alice` into the graph, sends the graph, and receives a verdict
- **THEN** the verdict references the same IRI and the consumer resolves its `rdfs:label` from the graph for display

#### Scenario: Cycle identity round-trips
- **WHEN** the consumer sends a graph containing two election instances and receives a verdict
- **THEN** the verdict references cycle IRIs that resolve to the same labelled individuals the consumer displays

#### Scenario: Snapshot subjects bind to declared classes
- **WHEN** the consumer reads a graph subject
- **THEN** it resolves the subject's type and every one of its properties from the ontology's declarations, without knowing which law it is reading

#### Scenario: History is the same kind of entity as the present
- **WHEN** a law's graph holds an ongoing election instance and a previously void one
- **THEN** both are individuals of the same Process class, distinguished only by their `Chronoid` bounds, and a past-dependent condition addresses the finished one through that ordinary relation

#### Scenario: Runtime entity labels resolve
- **WHEN** a verdict references an entity minted during simulation rather than seeded from the law
- **THEN** the consumer resolves its label from the graph by IRI, with no second label source and no law-specific lookup

#### Scenario: Cancelled process keeps what it accumulated
- **WHEN** a candidate withdraws during polls and the election is stopped part-way through
- **THEN** the ballots already cast remain in the graph as labelled individuals, the instance's outcome records that they do not count, and no transition is available that would erase them

Also verified with a structurally equivalent ending rather than the one named. A mid-poll stop needs a law shape neither shipped law has; what `mayor-quorum` does have is a failed quorum at polls close, which exercises every clause of the `THEN` — the ballot cast before the failure is still in the graph and still typed `ph:CastVote`, the instance's `ph:outcome` records `void`, the successor starts from a fresh registry rather than inheriting anything, and no act exists that removes the ballot. What is untested is specifically a stop *during* polling, with ballots cast on both sides of it.

#### Scenario: No act removes an individual
- **WHEN** every ECA of a law is applied in turn to a graph and each resulting graph is compared with its input
- **THEN** every subject present before an accepted act is still present after it, so no act deletes an individual whatever the law intends

#### Scenario: Only counting is revisable
- **WHEN** a rule bears on a fact already in the graph, such as whether a cast vote counts toward an outcome
- **THEN** it changes how that fact is counted or which outcome it supports, and never whether the fact exists

#### Scenario: Termination mid-span is ordinary
- **WHEN** a process terminates at a moment inside one of its calendar spans rather than at a declared point
- **THEN** its `Chronoid` carries that finish bound, no new vocabulary is required to express it, and the finished instance is read the same way as one ending on a calendar point

The scenario is exercised on both shipped laws, in the two shapes it can take. `requisitions` ends strictly inside a span: a requisition withdrawn on day 1 of a window running days 0 to 30, against the same law's day-30 deadline ending. `mayor-quorum` cannot finish strictly inside a span in days, because every ending it has is guarded behind polls closing and its seeded spans all end at a polls-close point — so it exercises the other half, a finish at a moment that is not a declared calendar point within a span's day range: closing at day 40 hour 19 against day 40 hour 20, where hour 19 is the declared polls-close point and hour 20 is the moment the authority actually counted. Both record the same predicates on the `Chronoid` and the same shape on the bound, differing only in the moment. Neither ending needs a predicate the ontology has not declared, and each bound is a plain `gfo-light:TimeBoundary` carrying both `ph:dayIndex` and `ph:atHour`. `scripts/test_cancellation.py` covers the same law's later case independently, with a finish at day 12 hour 14 against the day-10 polls close.

#### Scenario: Occurrence is an instance of its phase
- **WHEN** a citizen nominates inside a nomination window
- **THEN** the nomination is a graph individual of the window's Process class, relating to that citizen and to the enclosing process instance, so several occurrences of one phase coexist without colliding

#### Scenario: Nothing exists only in the oracle
- **WHEN** a walk of accepted acts is applied and the resulting graph alone is used to reproduce every verdict
- **THEN** each verdict is reproduced without consulting oracle-internal state, so no fact a law can decide is unreachable from the graph

#### Scenario: Re-encoding an unchanged individual is a no-op
- **WHEN** two successive accepted acts leave one individual's properties unchanged
- **THEN** the graph carries exactly one value for each of that individual's functional properties, so a consumer reading a bound or a flag cannot be handed a value other than the one last written

#### Scenario: A session's graph is resumable
- **WHEN** a graph is persisted after a sequence of acts, reloaded, and the same sequence of acts applied from it at the same clock positions
- **THEN** the resulting graph is identical, because the graph is a function of the seed, the acts, and the clock, and the clock is its only free variable

#### Scenario: A period closing is not assumed to be recorded
- **WHEN** a law closes a period within a process's life and records no property for the moment
- **THEN** the graph carries the fact that the period closed and not when, and no consumer reconstructs the moment from a flag or a calendar node

#### Scenario: A law may record the moment itself
- **WHEN** a law declares a functional property for the moment a period closed and writes it
- **THEN** the graph carries it as an ordinary declared fact, with no framework vocabulary naming the concept and no requirement that any law do so

### Requirement: Oracle runtime interface

Each law SHALL ship a compiled Lean oracle speaking a fixed CLI protocol over JSON: a `list` query naming available ECAs (including `repeat` on quorum flavors), a `check` query taking the instance graph and returning conditions truth values, per-citizen pending actions (including the repeat duty on the authority when the current cycle is void), and violations with structured witnesses, and an `apply` query taking an act-plus-graph envelope and returning the new instance graph (or a JSON rejection naming the failed guard). `check` SHALL stay advisory; `apply` SHALL be the single enforcing path — drivers SHALL request transitions through it and SHALL NOT implement rule semantics themselves. `check`/`apply` SHALL scope phase, pending, and guards to the ongoing process instance while finished instances remain visible for past-dependent rules.

`apply` SHALL receive the whole graph and return the whole graph, so the graph never becomes a second source of truth alongside the oracle's state. The returned graph SHALL be the incoming graph extended by the encoding of the state that results from the act: individuals that existed and do not change are present and unchanged, individuals that change are present with their new values, and individuals that come into existence are present with the declared properties of their class. A consumer replaces its stored graph with the one returned rather than splicing the response into what it already holds. A consumer SHALL validate that every subject in a returned graph is typed by a class the ontology declares, and SHALL treat an untyped subject as an error rather than a partial write. The oracle SHALL be total over triples it does not need: conditions select what matters from the graph rather than being told in advance what to look at.

The verdict SHALL NOT carry a field named for any single process concept. Law-specific results SHALL be reported as entries in a generic `readings` list, each naming a law-chosen id, a kind drawn from the closed set `decimal`, `ref`, or `flag`, and a value; a `ref` reading SHALL name the ontology class of the individual it points at so the label resolves. `phase` SHALL remain a top-level reading. A law with no result of a given shape SHALL omit that reading rather than emit a placeholder.

Each violation SHALL carry a structured witness alongside its display string. The witness SHALL name the individuals that break a quantified condition under `refs` and any counts that fell short under `counts`, each count giving a name and a value; this SHALL suffice for the framework FOL subset, whose conditions are universal or existential over finite sets plus counting. A violation SHALL NOT require a law-specific witness field to be interpretable.

Each `pending` entry SHALL carry its ECA together with the parameter slots for it, including the choices available at that instant for any slot sourced from `choices`, so a consumer can present a complete act without reading law-specific state. Each `pending` entry SHALL also name the process instance the duty belongs to, so that duties on concurrently unfolding processes are distinguishable and a consumer can group them under the process they serve.

Because the clock is advanced by the driver rather than by a query, clock values are untrusted input. `check` and `apply` SHALL be total over all `day` and `hour` values, returning a well-formed verdict or a named rejection for any input including values far outside the law's calendar, and SHALL NOT fail on them. Because the clock is the graph's only free variable, `check` and `apply` SHALL also treat it as monotone: a clock earlier than the one the graph already carries SHALL NOT make a period a law has closed reopen, and SHALL NOT admit an act into a process that has finished. Monotonicity is enforced by reading: an oracle SHALL refuse to act as though time were earlier than a moment the graph already records, and SHALL leave the clock exactly as the runtime wrote it — not even echoing it, and never rewriting it forwards.

The oracle and the runtime own disjoint halves of the world. The runtime owns its **inputs**: it advances the clock, and it alone may bring a physical thing into being. The oracle owns only **interpretation**: what the state means, which duties are due, which Role an individual holds, which individual a verdict names. The oracle SHALL NOT write the clock and SHALL NOT create a physical individual; what it may mint is a meaning, an occurrence, a process instance, a calendar node, or a bound — none of which is a thing the law's duties are performed on. A law creates nothing either.

#### Scenario: Missing ballot reported with witness
- **WHEN** the graph has 39 of 40 expected ballots delivered
- **THEN** `check` returns false for all-distributed plus a witness naming the undelivered citizen IRI under `refs`, so the guide can name what is missing without a law-specific field

#### Scenario: Counting failure reported with structured witness
- **WHEN** the graph shows fewer than half the citizens voted at polls close
- **THEN** `check` returns the quorum violation with a witness whose `counts` give the voted and total counts, rather than conveying them only inside the display string

#### Scenario: Double vote rejected with reason
- **WHEN** the consumer requests a vote act for a citizen who already voted with polls open
- **THEN** `apply` returns a rejection naming the already-voted guard instead of a new graph, and the stored graph is unchanged

#### Scenario: Repeat offered as pending
- **WHEN** the graph shows a finished election instance with a failed quorum and an authority in office
- **THEN** `check` returns a pending entry for that citizen with eca `repeat` alongside the quorum violation witness

#### Scenario: Repeat on valid election rejected
- **WHEN** the consumer requests a repeat act on a graph whose quorum is valid
- **THEN** `apply` returns a rejection naming the quorum-not-failed guard and the stored graph is unchanged

#### Scenario: Results reported without a shape change
- **WHEN** a law whose outcome is a number reports it and a law whose outcome is a winning citizen reports that
- **THEN** both appear as `readings` entries differing only in id, kind, and value, and neither needs a verdict field of its own

#### Scenario: Result-free law emits no placeholder
- **WHEN** a law has no result of a given shape
- **THEN** it emits no such reading, and a consumer renders its absence as an absent reading rather than as a null value

#### Scenario: Pending entry carries available choices
- **WHEN** a pending entry has a parameter sourced from `choices`
- **THEN** the verdict names the choices available at that instant, and the consumer builds a complete act from the verdict and the declaration alone

#### Scenario: Pending entry names its process instance
- **WHEN** one citizen holds duties on two concurrently unfolding processes
- **THEN** each pending entry names the process instance it belongs to, so the consumer groups them under separate processes instead of one undifferentiated list

#### Scenario: Act targets a chosen instance
- **WHEN** two instances of one process type are ongoing and a duty on a third is offered
- **THEN** the consumer presents the open instances as a choice and the act names the one selected, with no ambiguity between them

#### Scenario: Absurd clock values stay total
- **WHEN** `check` or `apply` receives a day or hour far outside the law's calendar, including values before its first calendar point
- **THEN** it returns a well-formed verdict or a named rejection rather than failing, underflowing, or erroring

#### Scenario: Clock advanced without an oracle query
- **WHEN** a consumer writes a new `ph:Clock` value into the graph and then calls `check`
- **THEN** the verdict reflects the new position, with no clock-advancement verb required

#### Scenario: A backwards clock cannot reopen a closed period
- **WHEN** a graph records that polls closed on a day and a consumer sets the clock to an earlier moment
- **THEN** the oracle treats the recorded period as still closed, so an act its guard refuses while polls are open is still refused and no act is admitted into a process that has finished

#### Scenario: The oracle does not write the clock
- **WHEN** `apply` returns a graph for an accepted act
- **THEN** the returned `ph:Clock` carries the position the consumer supplied, so advancing time has exactly one writer and an act can neither move nor erase it

#### Scenario: A rewound clock is refused, not overwritten
- **WHEN** a consumer sets the clock to a moment earlier than one the graph already records and an act is applied
- **THEN** the act is evaluated as though time were the recorded moment, and the returned `ph:Clock` still carries what the consumer wrote, so the oracle declines to act on a rewound clock without becoming a writer of time

#### Scenario: The oracle does not create the world's furniture
- **WHEN** an act is applied and the graph gains a physical individual no seeded individual and no earlier act accounts for
- **THEN** that is the runtime's power and not the oracle's, so the act SHALL be refused; the oracle may mint a meaning, an occurrence, a process instance, a calendar node, or a bound, and never a thing a duty is performed on

#### Scenario: Whole graph round-trips
- **WHEN** the consumer sends the whole graph to `apply` and a new graph is returned
- **THEN** the returned graph is the sent graph plus the encoding of what the act changed, and the consumer replaces its stored one rather than merging into it, so the oracle's state and the graph never diverge

#### Scenario: Irrelevant triples are tolerated
- **WHEN** the graph contains individuals and triples a given law's conditions never address
- **THEN** `check` and `apply` remain well-formed and total, selecting what matters from the graph rather than requiring the framework to have declared in advance what the law needs

#### Scenario: Untyped subject is refused
- **WHEN** an `apply` response contains a subject typed by a class the ontology does not declare
- **THEN** the consumer reports the error and does not commit a partial write

## ADDED Requirements

### Requirement: Transformation of existing individuals

An ECA action MAY change what an individual already is rather than produce a new individual. Where it does, the individual SHALL keep its class and SHALL acquire a Role individual naming the meaning it now holds: the Role's `ph:roleIn` names the Process or other situation the meaning holds in, and its `ph:playedBy` names the individual that holds it. `ph:playedBy` names whatever holds the role and is not restricted to citizens. The same individual MAY hold a different Role in each situation it takes part in, and SHALL NOT be given the same Role twice in one situation.

A quality an individual acquires — a name written on it, a mark applied to it — SHALL attach to that individual through `ph:qualityOf` rather than by minting a new individual to carry it. An individual SHALL NOT change its declared class as a process unfolds, so that a consumer asking which individuals are of a kind gets the same answer whatever the process's progress.

An ECA action that transforms SHALL declare the individuals it acts on, and `apply` SHALL refuse the act naming any of them that the graph does not contain. An action SHALL NOT bring a physical thing into existence that no seeded individual and no previously accepted action accounts for: the world the law's duties refer to SHALL already contain the things those duties concern. Minting remains available for what is not a physical thing of the world's ongoing furniture — a process instance, a calendar node, a bound — because none of those is something a law's duty is performed on.

What an individual bears and what that bearing means SHALL be separable. Where a law's duty is to write or mark something, the marking SHALL be an individual related to the individual marked, carrying the literal the law says is written, and it SHALL exist whether or not anything has yet been made of it. The meaning of that marking SHALL be carried by a Role, in the situation the marking is made relevant, and SHALL relate the marking to whatever it stands for in that situation. A literal SHALL NOT on its own denote an individual: what it denotes SHALL follow from the Role, so the same literal written in two situations may denote two different things without either being wrong.

#### Scenario: A sheet bears an inscription before it is a ballot
- **WHEN** a player writes a name on a sheet and nothing has yet made that writing into anything
- **THEN** the sheet carries the inscription as an individual related to it and holding the literal written, and the sheet holds no Role for it, so the writing is recorded as having happened without asserting what it means

#### Scenario: The Role says what the writing means here
- **WHEN** a sheet bearing an inscription takes a Role in an election
- **THEN** the Role relates that inscription to the citizen it names, and the literal written on the sheet resolves to no citizen except through that Role

#### Scenario: One literal, two situations, two meanings
- **WHEN** the same literal is written in two different processes and denotes a different individual in each
- **THEN** each process's Role relates its own inscription to its own individual, so neither recording is wrong and no identity is inferred from the text

#### Scenario: A marking that names nothing is not yet a role
- **WHEN** an individual bears a marking whose Role has not been taken
- **THEN** no consumer can resolve what the marking stands for, which is a different and observable state from one whose Role has named it

#### Scenario: A sheet becomes a ballot by taking a role
- **WHEN** an authority writes a candidate's name on a sheet during a preparation phase
- **THEN** the sheet is still typed by its own class and there is a Role individual whose `ph:playedBy` names the sheet and whose `ph:roleIn` names the election, so the sheet is a ballot in that election without becoming a different kind of thing

#### Scenario: One individual, a meaning per situation
- **WHEN** the same individual takes part in two processes and holds a meaning in each
- **THEN** it holds a separate Role in each, distinguished by `ph:roleIn`, and no individual changes class between them

#### Scenario: A quality attaches to the thing that has it
- **WHEN** a name is written on a sheet
- **THEN** the name is a quality of that sheet through `ph:qualityOf`, and no new individual exists to carry it

#### Scenario: A marking is separable from its meaning
- **WHEN** a law's duty is to write something on a thing
- **THEN** the writing is an individual related to the thing and carrying the literal written, and what it denotes is carried by a Role in the situation where it matters, so the two are separately readable and neither implies the other

### Requirement: Physical actions and the meanings laws give them

The shared physical vocabulary SHALL declare not only the objects a governance text presupposes but the actions that can be performed on an object and the capabilities that qualify an object for an action, each subclassed in GFO and carrying `rdfs:label`. A declared action states the physical gesture and what it acts on — a writing performed with an instrument on a thing, a putting of one thing into a container — and SHALL NOT state what any law makes of it. Two actions that a law may draw on are writing on a thing and putting a thing into a container, each declared once so that every law performing them refers to the same action.

A capability SHALL be declared as a class an object belongs to, naming the kind of object that qualifies for an action, and SHALL NOT be declared as a restriction asserting which objects can be used on which. The ontology states that such instruments and such surfaces exist as kinds; which individual instruments and surfaces those are, and which combinations of them an action requires, SHALL be evaluated by the oracle per act. The reason is that a restriction can only require that some qualifying object be involved and cannot exclude a particular one, so an ontology claiming that one thing may be written with and another may not would assert more than it can establish.

A law SHALL qualify what an action needs by capability rather than by a named kind of object, so that text leaving the choice open leaves it open. Where a law's text says to write or mark without naming an instrument, the act's instrument SHALL be declared by the capability it must have and not by a particular class, so a hamlet whose only such instrument is of a different kind than another hamlet's still satisfies the duty. A law naming a particular kind of object where its text does not SHALL NOT narrow the requirement, because that would resolve the law's vagueness in the artefacts rather than in the world.

The meaning a law gives an action SHALL be a Role the acted-on individual takes on in the law's own process, not a property of the action and not a property of the individual. One individual MAY therefore be the acted-on thing of several declared actions in several situations and remain one individual throughout: a sheet that has been written on in an election and later placed in a ballot box is still the same sheet, holding a Role in each situation, and which Roles it holds is read from the graph rather than from its class. A law SHALL NOT re-declare a physical action it could draw on, and the report of a local redeclaration covers actions and capabilities as it does objects.

Because the action is shared and the meaning is the law's, two laws performing the same action on the same kind of thing reach different Roles and neither contradicts the other. What is shared is the gesture; what is law-determined is what the gesture constitutes, in which process, and of which process instance.

#### Scenario: An action is declared without its meaning
- **WHEN** the shared vocabulary declares that a thing may be written on with an instrument
- **THEN** the declaration says what the gesture is and what it acts on, and names no law, no process, and no class the gesture constitutes, because that is what each law supplies

#### Scenario: A capability names a kind, not a pairing
- **WHEN** the shared vocabulary declares that some instruments may inscribe and some things may be inscribed
- **THEN** the ontology says only that such instruments and such surfaces exist as kinds, and which instruments can be used on which surfaces is decided per act by the oracle rather than asserted by the schema

#### Scenario: Text leaving the instrument open leaves it open
- **WHEN** a law's text tells an actor to write a name without naming what to write with
- **THEN** the act is satisfied by any instrument of a kind that may inscribe, so a hamlet stocked only with a different such instrument is not blocked by a class the law never mentioned

#### Scenario: A law does not narrow what its text left open
- **WHEN** a draft names one particular kind of instrument where its law text named none
- **THEN** the review gate reports it, because choosing the instrument is the world's business and fixing it in the artefacts resolves the law's vagueness where the law left it

#### Scenario: One individual, several actions
- **WHEN** the same individual is written on in one process and put into a container in another
- **THEN** it is one individual holding a Role in each process, and a consumer reads which Roles it holds from the graph rather than from its class

#### Scenario: Two laws, one action, different meanings
- **WHEN** two laws both have a citizen write on a sheet and each means something different by it
- **THEN** both draw on the same declared action and each declares its own Role for what it constitutes, so neither law's meaning constrains the other's

#### Scenario: A local redeclaration of an action is reported
- **WHEN** a law declares locally an action or a capability the shared vocabulary also declares
- **THEN** the review gate reports it naming both, since two declarations of the same gesture or the same qualification would leave two ways of writing on a thing

#### Scenario: A law adding no physics
- **WHEN** a law's text says its actors write on a sheet and place it in a box
- **THEN** the law declares only the Roles those actions constitute in its own processes, and draws the gesture, the objects, and the capabilities from the shared vocabulary without restating any of them

#### Scenario: Acting on something absent is refused
- **WHEN** a law's action declares an individual it acts on and the graph contains no such individual
- **THEN** `apply` refuses the act naming the missing individual, rather than creating something to act on

#### Scenario: A duty on an object the world lacks is refused
- **WHEN** a law's action would bring into existence a physical thing to carry out a duty, and no individual of that kind exists
- **THEN** the act is refused, because a law cannot perform its duties on objects the world does not contain

#### Scenario: Minting a process instance is still available
- **WHEN** an accepted action brings a new Process instance or a new calendar node into existence
- **THEN** nothing is refused, since neither is a physical thing a duty is performed on and both are legitimately new

### Requirement: IRI freshness for minted individuals

Every individual that comes into existence during simulation SHALL be named by an IRI that is a deterministic function of the dimensions along which the fact can repeat, so that re-deriving the same fact yields the same individual and a distinct fact yields a distinct one. A minted IRI SHALL NOT be a function of the holder alone: where the same holder may bring several instances of one Process class into existence over a run, as a citizen may lodge successive requisitions or cast successive ballots, the IRI SHALL include the occurrence as well, so that two occurrences never collide. For a Role individual minted by a transformation, those dimensions are the individual holding the role and the situation it is held in, which is what keeps one individual's meanings in two situations from colliding.

A minted IRI already present in the graph SHALL name the same individual as the one already there, and a law SHALL NOT bring a fact into existence under an IRI that already encodes a different fact. Where that would happen the framework treats it as an error rather than an overwrite, because a collision is invisible to every check that exists: both individuals are typed by declared classes, so the graph is well-formed while stating something false.

Freshness is what makes re-encoding an individual a no-op. It is not a recipe for obtaining an unused name, and it does not depend on counting how many individuals exist, because a counter would make an individual's name depend on the order the acts arrived in, and the wire format carries no order.

#### Scenario: Two occurrences by one holder stay distinct
- **WHEN** a citizen brings a second instance of a Process class into existence after the first has finished
- **THEN** the two are distinct graph individuals with distinct IRIs, each carrying its own bounds and outcome, so finishing the second does not disturb the first

#### Scenario: A colliding IRI is refused
- **WHEN** a law brings a fact into existence under an IRI already present and encoding a different fact
- **THEN** the gate fails naming the IRI and the individual already there, rather than letting the graph gain a start bound on a finished instance or lose a recorded outcome

#### Scenario: Re-derivation yields one individual
- **WHEN** a law re-encodes an individual it has already materialised
- **THEN** the individual carries the same IRI as before and no duplicate of it appears

#### Scenario: Naming does not depend on arrival order
- **WHEN** the same set of acts is applied in a separate session from the same seed graph and the same clock positions
- **THEN** every individual produced carries the same IRI, because no name is derived from how many individuals already existed